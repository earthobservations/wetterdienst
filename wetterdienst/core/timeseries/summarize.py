import logging
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

import polars as pl

from wetterdienst import Parameter
from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.result import StationsResult
from wetterdienst.core.timeseries.tools import _ParameterData, extract_station_values
from wetterdienst.metadata.columns import Columns

log = logging.getLogger(__name__)

SUMMARY_STATION_KM_LIMIT = defaultdict(
    lambda: 40,
    {
        Parameter.TEMPERATURE_AIR_MEAN_200.name: 40,
        Parameter.TEMPERATURE_AIR_MAX_200.name: 40,
        Parameter.TEMPERATURE_AIR_MIN_200.name: 40,
        Parameter.WIND_SPEED.name: 40,
        Parameter.PRECIPITATION_HEIGHT.name: 20,
    },
)


def get_summarized_df(request: "TimeseriesRequest", latitude: float, longitude: float) -> pl.DataFrame:
    stations_dict, param_dict = request_stations(request, latitude, longitude)
    return calculate_summary(stations_dict, param_dict)


def request_stations(request: "TimeseriesRequest", latitude: float, longitude: float) -> Tuple[dict, dict]:
    param_dict = {}
    stations_dict = {}

    stations_ranked = request.filter_by_rank(latlon=(latitude, longitude), rank=20)
    stations_ranked_df = stations_ranked.df.drop_nulls()

    for station, result in zip(stations_ranked_df.iter_rows(named=True), stations_ranked.values.query()):
        if station[Columns.DISTANCE.value] > max(SUMMARY_STATION_KM_LIMIT.values()):
            break

        # check if all parameters found enough stations and the stations build a valid station group
        if len(param_dict) > 0 and all(param.finished for param in param_dict.values()):
            break

        if result.df.drop_nulls().is_empty():
            continue

        stations_dict[station["station_id"]] = (station["longitude"], station["latitude"], station["distance"])
        apply_station_values_per_parameter(result.df, stations_ranked, param_dict, station)

    return stations_dict, param_dict


def apply_station_values_per_parameter(
    result_df: pl.DataFrame,
    stations_ranked: "StationsResult",
    param_dict: dict,
    station: dict,
) -> None:
    for parameter, dataset in stations_ranked.stations.parameter:
        if parameter == dataset:
            log.info("only individual parameters can be interpolated")
            continue

        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue

        if station["distance"] > SUMMARY_STATION_KM_LIMIT[parameter.name]:
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue

        parameter_name = parameter.name.lower()
        if parameter_name in param_dict and param_dict[parameter_name].finished:
            continue

        # Filter only for exact parameter
        result_series_param = result_df.filter(pl.col(Columns.PARAMETER.value).eq(parameter_name))
        if result_series_param.drop_nulls().is_empty():
            continue

        if parameter_name not in param_dict:
            df = pl.DataFrame(
                {
                    Columns.DATE.value: pl.datetime_range(
                        start=stations_ranked.stations.start_date,
                        end=stations_ranked.stations.end_date,
                        interval=stations_ranked.frequency_polars.value,
                        time_zone="UTC",
                        eager=True,
                    ).dt.round(stations_ranked.frequency_polars.value)
                }
            )
            param_dict[parameter_name] = _ParameterData(df)

        result_series_param = (
            param_dict[parameter_name].values.select("date").join(result_series_param, on="date", how="left")
        )
        result_series_param = result_series_param.get_column(Columns.VALUE.value).rename(station["station_id"])

        extract_station_values(param_dict[parameter_name], result_series_param, True)


def calculate_summary(stations_dict: dict, param_dict: dict) -> pl.DataFrame:
    data = [
        pl.DataFrame(
            schema={
                Columns.DATE.value: pl.Datetime(time_zone="UTC"),
                Columns.PARAMETER.value: pl.Utf8,
                Columns.VALUE.value: pl.Float64,
                Columns.DISTANCE.value: pl.Float64,
                Columns.TAKEN_STATION_ID.value: pl.Utf8,
            }
        )
    ]

    for parameter, param_data in param_dict.items():
        param_df = pl.DataFrame({Columns.DATE.value: param_data.values.get_column(Columns.DATE.value)})
        results = []
        for row in param_data.values.select(pl.all().exclude("date")).iter_rows(named=True):
            results.append(apply_summary(row, stations_dict, parameter))
        results = pl.DataFrame(
            results,
            schema={
                Columns.PARAMETER.value: pl.Utf8,
                Columns.VALUE.value: pl.Float64,
                Columns.DISTANCE.value: pl.Float64,
                Columns.TAKEN_STATION_ID.value: pl.Utf8,
            },
        )
        param_df = pl.concat([param_df, results], how="horizontal")
        data.append(param_df)

    df = pl.concat(data)
    df = df.with_columns(pl.col(Columns.VALUE.value).round(2), pl.col(Columns.DISTANCE.value).round(2))

    return df.sort(
        by=[
            Columns.PARAMETER.value,
            Columns.DATE.value,
        ]
    )


def apply_summary(
    row: dict,
    stations_dict: dict,
    parameter: Enum,
) -> Tuple[Enum, Optional[float], Optional[float], Optional[str]]:
    vals = {s: v for s, v in row.items() if v is not None}

    if not vals:
        return parameter, None, None, None

    value = list(vals.values())[0]
    station_id = list(vals.keys())[0][1:]
    distance = stations_dict[station_id][2]

    return parameter, value, distance, station_id


if __name__ == "__main__":
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    lat = 51.0221
    lon = 13.8470
    start_date = datetime(2003, 1, 1)
    end_date = datetime(2004, 12, 31)

    stations = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="hourly",
        start_date=start_date,
        end_date=end_date,
    )

    result = stations.summarize((lat, lon))

    log.info(result.df.drop_nulls())
