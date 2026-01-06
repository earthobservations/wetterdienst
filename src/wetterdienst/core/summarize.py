# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Summarize timeseries data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl
from tqdm import tqdm

from wetterdienst.core.util import _ParameterData, extract_station_values
from wetterdienst.metadata.resolution import Frequency
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import StationsResult

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
    distance = max(request.settings.ts_interp_station_distance.values())
    stations_ranked = request.filter_by_distance(latlon=(latitude, longitude), distance=distance)
    df_stations_ranked = stations_ranked.df
    tqdm_out = TqdmToLogger(log, level=logging.INFO)
    for station, result in tqdm(
        zip(df_stations_ranked.iter_rows(named=True), stations_ranked.values.query(), strict=False),
        total=len(df_stations_ranked),
        desc="querying stations for summary",
        unit="station",
        file=tqdm_out,
    ):
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
    for parameter in stations_ranked.stations.parameters:
        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue
        ts_interpolation_station_distance = stations_ranked.stations.settings.ts_interp_station_distance
        if station["distance"] > ts_interpolation_station_distance.get(
            parameter.name,
            ts_interpolation_station_distance["default"],
        ):
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue
        if (parameter.dataset.resolution.name, parameter.dataset.name, parameter.name) in param_dict and param_dict[
            parameter.dataset.resolution.name,
            parameter.dataset.name,
            parameter.name,
        ].finished:
            continue
        # Filter only for exact parameter
        result_series_param = result_df.filter(
            pl.col("resolution").eq(parameter.dataset.resolution.name),
            pl.col("dataset").eq(parameter.dataset.name),
            pl.col("parameter").eq(parameter.name),
        )
        if result_series_param.drop_nulls("value").is_empty():
            continue
        if (parameter.dataset.resolution.name, parameter.dataset.name, parameter.name) not in param_dict:
            frequency = Frequency[parameter.dataset.resolution.value.name].value
            df = pl.DataFrame(
                {
                    "date": pl.datetime_range(
                        start=stations_ranked.stations.start_date,
                        end=stations_ranked.stations.end_date,
                        interval=frequency,
                        time_zone="UTC",
                        eager=True,
                    ).dt.round(frequency),
                },
                orient="col",
            )
            param_dict[parameter.dataset.resolution.name, parameter.dataset.name, parameter.name] = _ParameterData(df)
        result_series_param = (
            param_dict[parameter.dataset.resolution.name, parameter.dataset.name, parameter.name]
            .values.select("date")
            .join(result_series_param, on="date", how="left")
        )
        result_series_param = result_series_param.get_column("value").rename(station["station_id"])
        extract_station_values(
            param_dict[parameter.dataset.resolution.name, parameter.dataset.name, parameter.name],
            result_series_param,
            min_gain_of_value_pairs=stations_ranked.stations.settings.ts_interp_min_gain_of_value_pairs,
            num_additional_stations=stations_ranked.stations.settings.ts_interp_num_additional_stations,
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
        param_df = pl.concat([param_df, results], how="horizontal")
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

    This works by taking the first non-null value and its station id.
    """
    vals = {s: v for s, v in row.items() if v is not None}
    if not vals:
        return resolution, dataset, parameter, None, None, None
    value = next(iter(vals.values()))
    station_id = next(iter(vals.keys()))
    distance = stations_dict[station_id][2]
    return resolution, dataset, parameter, value, distance, station_id
