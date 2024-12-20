from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl
from tqdm import tqdm

from wetterdienst.core.timeseries.tools import _ParameterData, extract_station_values
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import Frequency
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    from enum import Enum

    from wetterdienst.core.timeseries.request import TimeseriesRequest
    from wetterdienst.core.timeseries.result import StationsResult

log = logging.getLogger(__name__)


def get_summarized_df(request: TimeseriesRequest, latitude: float, longitude: float) -> pl.DataFrame:
    stations_dict, param_dict = request_stations(request, latitude, longitude)
    return calculate_summary(stations_dict, param_dict)


def request_stations(request: TimeseriesRequest, latitude: float, longitude: float) -> tuple[dict, dict]:
    param_dict = {}
    stations_dict = {}
    distance = max(request.settings.ts_interpolation_station_distance.values())
    stations_ranked = request.filter_by_distance(latlon=(latitude, longitude), distance=distance)
    df_stations_ranked = stations_ranked.df
    tqdm_out = TqdmToLogger(log, level=logging.INFO)
    for station, result in tqdm(
        zip(df_stations_ranked.iter_rows(named=True), stations_ranked.values.query()),
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
    for parameter in stations_ranked.stations.parameters:
        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue
        ts_interpolation_station_distance = stations_ranked.stations.settings.ts_interpolation_station_distance
        if station["distance"] > ts_interpolation_station_distance.get(
            parameter.name,
            ts_interpolation_station_distance["default"],
        ):
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue
        if parameter.name in param_dict and param_dict[parameter.name].finished:
            continue
        # Filter only for exact parameter
        result_series_param = result_df.filter(pl.col(Columns.PARAMETER.value).eq(parameter.name))
        if result_series_param.drop_nulls("value").is_empty():
            continue
        if parameter.name not in param_dict:
            frequency = Frequency[parameter.dataset.resolution.value.name].value
            df = pl.DataFrame(
                {
                    Columns.DATE.value: pl.datetime_range(
                        start=stations_ranked.stations.start_date,
                        end=stations_ranked.stations.end_date,
                        interval=frequency,
                        time_zone="UTC",
                        eager=True,
                    ).dt.round(frequency),
                },
                orient="col",
            )
            param_dict[parameter.name] = _ParameterData(df)
        result_series_param = (
            param_dict[parameter.name].values.select("date").join(result_series_param, on="date", how="left")
        )
        result_series_param = result_series_param.get_column(Columns.VALUE.value).rename(station["station_id"])
        extract_station_values(param_dict[parameter.name], result_series_param, True)


def calculate_summary(stations_dict: dict, param_dict: dict) -> pl.DataFrame:
    data = [
        pl.DataFrame(
            schema={
                Columns.DATE.value: pl.Datetime(time_zone="UTC"),
                Columns.PARAMETER.value: pl.String,
                Columns.VALUE.value: pl.Float64,
                Columns.DISTANCE.value: pl.Float64,
                Columns.TAKEN_STATION_ID.value: pl.String,
            },
        ),
    ]
    for parameter, param_data in param_dict.items():
        param_df = pl.DataFrame({Columns.DATE.value: param_data.values.get_column(Columns.DATE.value)})
        results = []
        for row in param_data.values.select(pl.all().exclude("date")).iter_rows(named=True):
            results.append(apply_summary(row, stations_dict, parameter))
        results = pl.DataFrame(
            results,
            schema={
                Columns.PARAMETER.value: pl.String,
                Columns.VALUE.value: pl.Float64,
                Columns.DISTANCE.value: pl.Float64,
                Columns.TAKEN_STATION_ID.value: pl.String,
            },
            orient="row",
        )
        param_df = pl.concat([param_df, results], how="horizontal")
        data.append(param_df)
    df = pl.concat(data)
    df = df.with_columns(pl.col(Columns.VALUE.value).round(2), pl.col(Columns.DISTANCE.value).round(2))
    return df.sort(
        by=[
            Columns.PARAMETER.value,
            Columns.DATE.value,
        ],
    )


def apply_summary(
    row: dict,
    stations_dict: dict,
    parameter: Enum,
) -> tuple[Enum, float | None, float | None, str | None]:
    vals = {s: v for s, v in row.items() if v is not None}
    if not vals:
        return parameter, None, None, None
    value = list(vals.values())[0]
    station_id = list(vals.keys())[0][1:]
    distance = stations_dict[station_id][2]
    return parameter, value, distance, station_id
