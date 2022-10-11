import logging
from datetime import datetime
from typing import Tuple

import numpy as np
import pandas as pd

from wetterdienst import Parameter
from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.result import StationsResult
from wetterdienst.core.scalar.tools import _ParameterData, extract_station_values
from wetterdienst.metadata.columns import Columns

log = logging.getLogger(__name__)


def get_summarized_df(request: "ScalarRequestCore", latitude: float, longitude: float) -> pd.DataFrame:
    stations_dict, param_dict = request_stations(request, latitude, longitude)
    df = calculate_summary(stations_dict, param_dict)
    df[Columns.DISTANCE.value] = pd.Series(df[Columns.DISTANCE.value].values, dtype=float)
    df[Columns.VALUE.value] = pd.Series(df[Columns.VALUE.value].values, dtype=float)
    df[Columns.DATE.value] = pd.to_datetime(df[Columns.DATE.value], infer_datetime_format=True)
    return df


def request_stations(request: "ScalarRequestCore", latitude: float, longitude: float) -> Tuple[dict, dict]:
    param_dict = {}
    stations_dict = {}
    hard_distance_km_limit = 40

    stations_ranked = request.filter_by_rank(latitude=latitude, longitude=longitude, rank=20)
    stations_ranked_df = stations_ranked.df.dropna()

    for (_, station), result in zip(stations_ranked_df.iterrows(), stations_ranked.values.query()):
        if station[Columns.DISTANCE.value] > hard_distance_km_limit:
            break

        # check if all parameters found enough stations and the stations build a valid station group
        if len(param_dict) > 0 and all(param.finished for param in param_dict.values()):
            break

        if result.df.dropna().empty:
            continue

        # convert to utc
        result.df.date = result.df.date.dt.tz_convert("UTC")

        stations_dict[station.station_id] = (station.longitude, station.latitude, station.distance)
        apply_station_values_per_parameter(result.df, stations_ranked, param_dict, station)

    return stations_dict, param_dict


def apply_station_values_per_parameter(
    result_df: pd.DataFrame,
    stations_ranked: "StationsResult",
    param_dict: dict,
    station: pd.Series,
):
    km_limit = {
        Parameter.TEMPERATURE_AIR_MEAN_200.name: 40,
        Parameter.WIND_SPEED.name: 40,
        Parameter.PRECIPITATION_HEIGHT.name: 20,
    }

    for parameter, dataset in stations_ranked.stations.parameter:
        if parameter == dataset:
            log.info("only individual parameters can be interpolated")
            continue

        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue

        if station.distance > km_limit[parameter.name]:
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue

        parameter_name = parameter.name.lower()
        if parameter_name in param_dict and param_dict[parameter_name].finished:
            continue

        # Filter only for exact parameter
        result_series_param = result_df.loc[result_df[Columns.PARAMETER.value] == parameter_name]
        if result_series_param.dropna().empty:
            continue

        result_series_param = result_series_param.loc[:, Columns.VALUE.value]
        result_series_param.name = station.station_id

        if parameter_name not in param_dict:
            param_dict[parameter_name] = _ParameterData(
                pd.DataFrame(
                    {
                        Columns.DATE.value: pd.date_range(
                            start=stations_ranked.stations.start_date,
                            end=stations_ranked.stations.end_date,
                            freq=stations_ranked.frequency.value,
                            tz="UTC",
                        )
                    }
                )
                .set_index(Columns.DATE.value)
                .astype("datetime64")
            )

        extract_station_values(param_dict[parameter_name], result_series_param, True)


def calculate_summary(stations_dict: dict, param_dict: dict) -> pd.DataFrame:
    columns = [
        Columns.DATE.value,
        Columns.PARAMETER.value,
        Columns.VALUE.value,
        Columns.DISTANCE.value,
        Columns.STATION_ID.value,
    ]
    param_df_list = [pd.DataFrame(columns=columns)]

    for parameter, param_data in param_dict.items():
        param_df = pd.DataFrame(columns=columns)
        param_df[columns[1:]] = param_data.values.apply(
            lambda row, param=parameter: apply_summary(row, stations_dict, param),
            axis=1,
            result_type="expand",
        )
        param_df[Columns.DATE.value] = param_data.values.index
        param_df_list.append(param_df)

    return pd.concat(param_df_list).sort_values(by=[Columns.DATE.value, Columns.PARAMETER.value]).reset_index(drop=True)


def apply_summary(
    row,
    stations_dict: dict,
    parameter,
):
    vals_state = ~pd.isna(row.values)
    vals = row[vals_state]

    value, station_id, distance = np.nan, np.nan, np.nan

    if not vals.empty:
        value = float(vals[0])
        station_id = vals.index[0]
        distance = stations_dict[station_id][2]

    return parameter, value, distance, station_id


if __name__ == "__main__":
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    lat = 51.0221
    long = 13.8470
    start_date = datetime(2003, 1, 1)
    end_date = datetime(2004, 12, 31)

    stations = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="hourly",
        start_date=start_date,
        end_date=end_date,
    )

    df = stations.summarize(lat, long)

    log.info(df.df.dropna())
