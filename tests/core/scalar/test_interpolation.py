from datetime import datetime

import pandas as pd
import pytest
from pandas import Timestamp
from pandas._testing import assert_frame_equal

from wetterdienst import Parameter
from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)


def test_interpolation_temperature_air_mean_200_hourly():
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200.name,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.interpolate(latitude=50.0, longitude=8.9)
    interpolated_df = result.df
    assert interpolated_df.shape[0] == 18001
    assert interpolated_df.dropna().shape[0] == 12385

    test_df = result.filter_by_date("2022-01-02 00:00:00+0000").reset_index(drop=True)

    assert_frame_equal(
        test_df,
        pd.DataFrame(
            {
                "date": {0: Timestamp("2022-01-02 00:00:00+0000", tz="UTC")},
                "parameter": {0: Parameter.TEMPERATURE_AIR_MEAN_200.name.lower()},
                "value": {0: 276.94455095211555},
                "distance_mean": {0: 13.37185625092419},
                "station_ids": {0: ["02480", "04411", "07341", "00917"]},
            }
        ),
    )


@pytest.mark.slow
def test_interpolation_precipitation_height_minute_10():
    stations = DwdObservationRequest(
        parameter=Parameter.PRECIPITATION_HEIGHT.name,
        resolution=DwdObservationResolution.MINUTE_10,
        start_date=datetime(2021, 10, 1),
        end_date=datetime(2021, 10, 5),
    )

    result = stations.interpolate(latitude=50.0, longitude=8.9)
    interpolated_df = result.df
    assert interpolated_df.shape[0] == 577
    assert interpolated_df.dropna().shape[0] == 577

    test_df = result.filter_by_date("2021-10-05 00:00:00+0000").reset_index(drop=True)

    assert_frame_equal(
        test_df,
        pd.DataFrame(
            {
                "date": {0: Timestamp("2021-10-05 00:00:00+0000", tz="UTC")},
                "parameter": {0: Parameter.PRECIPITATION_HEIGHT.name.lower()},
                "value": {0: 0.0},  # TODO (NN): got -0.0014067201111032121
                "distance_mean": {0: 9.377547913740226},
                "station_ids": {0: ["04230", "02480", "04411", "07341"]},
            }
        ),
    )


def test_not_interpolatable_parameter():
    stations = DwdObservationRequest(
        parameter=Parameter.WIND_DIRECTION.name,
        resolution=DwdObservationResolution.HOURLY,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.interpolate(latitude=50.0, longitude=8.9)
    interpolated_df = result.df
    assert interpolated_df.shape[0] == 0
    assert interpolated_df.dropna().shape[0] == 0

    assert_frame_equal(
        interpolated_df,
        pd.DataFrame(
            columns=[
                Columns.DATE.value,
                Columns.PARAMETER.value,
                Columns.VALUE.value,
                Columns.DISTANCE_MEAN.value,
                Columns.STATION_IDS.value,
            ]
        ).reset_index(drop=True),
    )


def test_not_interpolatable_dataset():
    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR.name,
        resolution=DwdObservationResolution.HOURLY,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 2),
    )

    result = stations.interpolate(latitude=50.0, longitude=8.9)
    interpolated_df = result.df
    assert interpolated_df.shape[0] == 0
    assert interpolated_df.dropna().shape[0] == 0

    assert_frame_equal(
        interpolated_df,
        pd.DataFrame(
            columns=[
                Columns.DATE.value,
                Columns.PARAMETER.value,
                Columns.VALUE.value,
                Columns.DISTANCE_MEAN.value,
                Columns.STATION_IDS.value,
            ]
        ).reset_index(drop=True),
    )
