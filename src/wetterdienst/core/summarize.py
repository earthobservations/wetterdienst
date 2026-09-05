# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Summarize timeseries data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import polars as pl
from tqdm import tqdm

from wetterdienst.core.util import (
    can_answer_at_height,
    collection_is_done,
    count_stations_in_reach,
    extract_station_values,
    lapse_rate_for,
    no_height_in_reach_error,
    open_parameter_data,
    parameters_still_in_reach,
    reduce_to_height,
    report_height_exclusions,
    unanswerable_at_height,
)
from wetterdienst.model.metadata import ParameterModel
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    import datetime as dt

    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import StationsResult
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# a summary answers with one station's reading, so one is all it wants
STATIONS_NEEDED = 1


def get_summarized_df(
    request: TimeseriesRequest,
    latitude: float,
    longitude: float,
    elevation: float | None = None,
) -> pl.DataFrame:
    """Get summarized DataFrame.

    Args:
        request: TimeseriesRequest
        latitude: float of the point to summarize
        longitude: float of the point to summarize
        elevation: elevation of the point in metres, to bring the station's readings to

    Returns:
        Summarized DataFrame

    Raises:
        NoStationsWithHeightError: where an elevation is asked about and leaving out the stations
            of unknown height leaves nothing that can answer it

    """
    stations_dict, param_dict, dropped_for_height = request_stations(request, latitude, longitude, elevation)
    df = calculate_summary(stations_dict, param_dict)
    report_height_exclusions(df, param_dict, dropped_for_height, elevation, stations_needed=STATIONS_NEEDED)
    return df


def request_stations(
    request: TimeseriesRequest,
    latitude: float,
    longitude: float,
    elevation: float | None = None,
) -> tuple[dict, dict, dict[tuple[str, str, str], int]]:
    """Request stations.

    A summary answers with one station's reading rather than a blend of several, so a height
    correction matters more here than in an interpolation, not less: nothing softens the difference
    between the station's altitude and the one asked about.
    """
    param_dict = {}
    stations_dict = {}
    dropped_for_height: dict[tuple[str, str, str], int] = {}
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
    # counted once, off the ranking, before a single value is downloaded: what each parameter has
    # in its own radius, and how much of that reports a height
    counts = count_stations_in_reach(df_stations_ranked, request.parameters, settings)
    unanswerable = unanswerable_at_height(counts, elevation, STATIONS_NEEDED)
    if unanswerable and unanswerable == set(counts):
        # every parameter asked for falls with height and not one station in reach reports one:
        # true of the request whatever the stations hold, so it is said without downloading them
        raise no_height_in_reach_error(unanswerable, elevation)
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
        if collection_is_done(
            param_dict, dropped_for_height.keys() & parameters_still_in_reach(counts, station["distance"])
        ):
            break
        if result.df.drop_nulls("value").is_empty():
            continue
        if apply_station_values_per_parameter(
            result.df,
            stations_ranked,
            param_dict,
            station,
            elevation,
            dropped_for_height=dropped_for_height,
        ):
            stations_dict[station["station_id"]] = (station["longitude"], station["latitude"], station["distance"])
    return stations_dict, param_dict, dropped_for_height


def apply_station_values_per_parameter(
    result_df: pl.DataFrame,
    stations_ranked: StationsResult,
    param_dict: dict,
    station: dict,
    elevation: float | None = None,
    *,
    dropped_for_height: dict[tuple[str, str, str], int],
) -> bool:
    """Apply station values per parameter.

    Returns whether the station gave a value to any parameter, so that the stations a summary
    draws on mean the same thing here as in the interpolation.
    """
    settings = cast("Settings", stations_ranked.stations.settings)
    # once, not once per parameter per station: `values` builds a `TimeseriesValues` and with it a
    # `UnitConverter`, whose tables run to a couple of hundred entries
    unit_converter = stations_ranked.values.unit_converter
    contributed = False
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
        lapse_rate = lapse_rate_for(parameter, unit_converter, convert_units=settings.ts_convert_units)
        if not can_answer_at_height(station.get("height"), lapse_rate, elevation):
            # asked before the parameter gets an entry of its own: an entry with no station column
            # in it comes back as rows with no resolution, dataset or parameter either, the date
            # grid padded out with nulls where the values would have been
            log.info(
                f"station {station['station_id']} has no height, so it says nothing about "
                f"{parameter.name} at {elevation} m and is left out",
            )
            # noted, not only logged: where this empties a parameter the caller is owed the
            # reason, and a log line is the one place a caller cannot read it from
            dropped_for_height[param_key] = dropped_for_height.get(param_key, 0) + 1
            continue
        # cast, not parsed: the request declares its dates as `str | datetime | None` because
        # that is what a caller may hand it, and resolves them to datetimes in `__post_init__`
        param_data = open_parameter_data(
            param_dict,
            param_key,
            dataset.resolution.value,
            cast("dt.datetime | None", stations_ranked.stations.start_date),
            cast("dt.datetime | None", stations_ranked.stations.end_date),
        )
        if param_data is None:
            continue
        result_series_param = param_data.values.select("date").join(result_series_param, on="date", how="left")
        result_series_param = result_series_param.get_column("value")
        reduced = reduce_to_height(result_series_param, lapse_rate, station.get("height"), elevation)
        if reduced is None:  # pragma: no cover - the check above turns such a station away already
            continue
        result_series_param = reduced.rename(station["station_id"])
        contributed |= extract_station_values(
            param_data,
            result_series_param,
            min_gain_of_value_pairs=settings.ts_geo_min_gain_of_value_pairs,
            num_additional_stations=settings.ts_geo_num_additional_stations,
            valid_station_groups_exists=True,
        )
    return contributed


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
        if param_data.values.width < 2:
            # a date grid and no station to answer against it. Concatenating that horizontally
            # pads the grid with nulls, and the rows come back with no resolution, dataset or
            # parameter either -- which is not a result for the parameter, it is noise
            continue
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
