# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Summarize timeseries data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import polars as pl
from tqdm import tqdm

from wetterdienst.core.util import _ParameterData, build_date_grid, extract_station_values
from wetterdienst.model.metadata import ParameterModel
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    import datetime as dt

    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import StationsResult
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


def get_summarized_df(request: TimeseriesRequest, latitude: float, longitude: float) -> pl.DataFrame:
    """Get summarized DataFrame.

    Args:
        request: TimeseriesRequest
        latitude: float of the point to summarize
        longitude: float of the point to summarize

    Returns:
        Summarized DataFrame

    """
    stations_dict, param_dict = request_stations(request, latitude, longitude)
    return calculate_summary(stations_dict, param_dict)


def request_stations(request: TimeseriesRequest, latitude: float, longitude: float) -> tuple[dict, dict]:
    """Request stations."""
    param_dict = {}
    stations_dict = {}
    settings = cast("Settings", request.settings)
    # the widest radius any requested parameter may draw on, as in `interpolate.request_stations`.
    # `max(...values())` used to stand here, which is the widest radius of the *populated* keys --
    # only the heterogeneous 20 km ones -- and so capped the search at 20 km for every parameter,
    # including the ones the setting gives 40 km
    distance = max(
        settings.ts_geo_station_distance_for(parameter.name, parameter.dataset.resolution.name)
        for parameter in request.parameters
        if isinstance(parameter, ParameterModel)
    )
    stations_ranked = request.filter_by_distance(latlon=(latitude, longitude), distance=distance)
    df_stations_ranked = stations_ranked.df
    # looked up by station id rather than zipped against the ranked frame positionally: `query()`
    # yields only the stations that returned data inside the requested window, so any station it
    # passes over shifts a positional pairing by one and every station after it is then read with
    # the coordinates and distance of its neighbour
    # one row per station, the nearest: the ranked frame carries a row per station *and* dataset,
    # so a multi-dataset request has several rows for one station, each with the coordinates and
    # distance its own dataset's meta index reported. `query()` yields one result per station, and
    # the row that answers for it is the closest one rather than whichever happened to sort last
    stations_by_id = {
        station["station_id"]: station
        for station in df_stations_ranked.unique(subset=["station_id"], keep="first", maintain_order=True).iter_rows(
            named=True,
        )
    }
    tqdm_out = TqdmToLogger(log, level=logging.INFO)
    for result in tqdm(
        stations_ranked.values.query(),
        total=len(stations_by_id),
        desc="querying stations for summary",
        unit="station",
        file=tqdm_out,
    ):
        station = stations_by_id[result.df.get_column("station_id")[0]]
        # check if all parameters found enough stations and the stations build a valid station group
        if len(param_dict) > 0 and all(param.finished for param in param_dict.values()):
            break
        if result.df.drop_nulls("value").is_empty():
            continue
        stations_dict[station["station_id"]] = (station["longitude"], station["latitude"], station["distance"])
        apply_station_values_per_parameter(result.df, stations_ranked, param_dict, station)
    return stations_dict, param_dict


def apply_station_values_per_parameter(
    result_df: pl.DataFrame,
    stations_ranked: StationsResult,
    param_dict: dict,
    station: dict,
) -> None:
    """Apply station values per parameter."""
    settings = cast("Settings", stations_ranked.stations.settings)
    for parameter in stations_ranked.stations.parameters:
        if not isinstance(parameter, ParameterModel):
            continue
        dataset = parameter.dataset
        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue
        # the radius follows the resolution for a parameter that decorrelates fast in space, so it
        # is asked for per parameter and resolution rather than read off a mapping. Nothing is
        # blended here, but the question the radius answers is the same one: how far away a
        # measurement still says something about the target point, which depends on how long the
        # quantity was accumulated for
        station_distance = settings.ts_geo_station_distance_for(parameter.name, dataset.resolution.name)
        if station["distance"] > station_distance:
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue
        param_key = (dataset.resolution.name, dataset.name, parameter.name)
        if param_key in param_dict and param_dict[param_key].finished:
            continue
        # Filter only for exact parameter
        result_series_param = result_df.filter(
            pl.col("resolution").eq(dataset.resolution.name),
            pl.col("dataset").eq(dataset.name),
            pl.col("parameter").eq(parameter.name),
        )
        if result_series_param.drop_nulls("value").is_empty():
            continue
        if param_key not in param_dict:
            # cast, not parsed: the request declares its dates as `str | datetime | None` because
            # that is what a caller may hand it, and resolves them to datetimes in `__post_init__`
            start_date = cast("dt.datetime | None", stations_ranked.stations.start_date)
            end_date = cast("dt.datetime | None", stations_ranked.stations.end_date)
            if start_date is None or end_date is None:
                continue
            param_dict[param_key] = _ParameterData(build_date_grid(dataset.resolution.value, start_date, end_date))
        result_series_param = (
            param_dict[param_key].values.select("date").join(result_series_param, on="date", how="left")
        )
        result_series_param = result_series_param.get_column("value").rename(station["station_id"])
        extract_station_values(
            param_dict[param_key],
            result_series_param,
            min_gain_of_value_pairs=settings.ts_geo_min_gain_of_value_pairs,
            num_additional_stations=settings.ts_geo_num_additional_stations,
            valid_station_groups_exists=True,
        )


def calculate_summary(stations_dict: dict, param_dict: dict) -> pl.DataFrame:
    """Calculate summary of stations and parameters."""
    data = [
        pl.DataFrame(
            schema={
                "date": pl.Datetime(time_zone="UTC"),
                "resolution": pl.String,
                "dataset": pl.String,
                "parameter": pl.String,
                "value": pl.Float64,
                "distance": pl.Float64,
                "taken_station_id": pl.String,
            },
        ),
    ]
    for (resolution, dataset, parameter), param_data in param_dict.items():
        param_df = pl.DataFrame({"date": param_data.values.get_column("date")})
        results = []
        for row in param_data.values.select(pl.all().exclude("date")).iter_rows(named=True):
            results.append(apply_summary(row, stations_dict, resolution, dataset, parameter))
        results = pl.DataFrame(
            results,
            schema={
                "resolution": pl.String,
                "dataset": pl.String,
                "parameter": pl.String,
                "value": pl.Float64,
                "distance": pl.Float64,
                "taken_station_id": pl.String,
            },
            orient="row",
        )
        param_df = pl.concat([param_df, results], how="horizontal_extend")
        data.append(param_df)
    df = pl.concat(data)
    df = df.with_columns(pl.col("value").round(2), pl.col("distance").round(2))
    return df.sort(
        by=[
            "resolution",
            "dataset",
            "parameter",
            "date",
        ],
    )


def apply_summary(
    row: dict,
    stations_dict: dict,
    resolution: str,
    dataset: str,
    parameter: str,
) -> tuple[str, str, str, float | None, float | None, str | None]:
    """Apply summary to row.

    This works by taking the first non-null value and its station id, which is the nearest station
    that has one: a row's columns are in the order the stations were collected, which is the order
    `filter_by_distance` ranked them in.
    """
    vals = {s: v for s, v in row.items() if v is not None}
    if not vals:
        return resolution, dataset, parameter, None, None, None
    value = next(iter(vals.values()))
    station_id = next(iter(vals.keys()))
    distance = stations_dict[station_id][2]
    return resolution, dataset, parameter, value, distance, station_id
