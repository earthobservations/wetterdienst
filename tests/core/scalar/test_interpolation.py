from datetime import datetime

import pandas as pd
import pytest
from pandas._testing import assert_frame_equal

from wetterdienst import Parameter
from wetterdienst.exceptions import StationNotFoundError
from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationRequest,
    DwdObservationResolution,
)
from wetterdienst.provider.eccc.observation.api import EcccObservationRequest
from wetterdienst.provider.eccc.observation.metadata.resolution import (
    EcccObservationResolution,
)

pytest.importorskip("shapely")


@pytest.mark.skip
def test_interpolation_temperature_air_mean_200_hourly_by_coords():
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.HOURLY,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.interpolate(latlon=(50.0, 8.9))
    interpolated_df = result.df
    assert interpolated_df.shape[0] == 18001
    assert interpolated_df.dropna().shape[0] == 18001

    test_df = result.filter_by_date("2022-01-02 00:00:00+00:00").reset_index(drop=True)

    expected_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2022-01-02 00:00:00+00:00"], utc=True),
            "parameter": ["temperature_air_mean_200"],
            "value": [277.64609040058747],
            "distance_mean": [13.374012456145287],
            "station_ids": [["02480", "04411", "07341", "00917"]],
        }
    )

    assert_frame_equal(test_df, expected_df)


@pytest.mark.skip
def test_interpolation_temperature_air_mean_200_daily_by_station_id():
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.DAILY,
        start_date=datetime(1986, 10, 31),
        end_date=datetime(1986, 11, 1),
    )
    for result in (
        stations.interpolate(latlon=(48.2156, 8.9784)),
        stations.interpolate_by_station_id(station_id="00071"),
    ):
        interpolated_df = result.df

        assert interpolated_df.shape[0] == 2
        assert interpolated_df.dropna().shape[0] == 2

        expected_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["1986-10-31 00:00:00+00:00", "1986-11-01 00:00:00+00:00"], utc=True),
                "parameter": ["temperature_air_mean_200", "temperature_air_mean_200"],
                "value": [279.6484850656227, 281.84999999999997],
                "distance_mean": [16.991040957994503, 0.0],
                "station_ids": [["00072", "02074", "02638", "04703"], ["00071"]],
            }
        )

        assert_frame_equal(interpolated_df, expected_df)


@pytest.mark.slow
def test_interpolation_precipitation_height_minute_10():
    stations = DwdObservationRequest(
        parameter=Parameter.PRECIPITATION_HEIGHT,
        resolution=DwdObservationResolution.MINUTE_10,
        start_date=datetime(2021, 10, 1),
        end_date=datetime(2021, 10, 5),
    )

    result = stations.interpolate(latlon=(50.0, 8.9))
    interpolated_df = result.df

    assert interpolated_df.shape[0] == 577
    assert interpolated_df.dropna().shape[0] == 577

    test_df = result.filter_by_date("2021-10-05 00:00:00+00:00").reset_index(drop=True)

    expected_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-10-05 00:00:00+00:00"]),
            "parameter": ["precipitation_height"],
            "value": [0.0],
            "distance_mean": [9.379704118961323],
            "station_ids": [["04230", "02480", "04411", "07341"]],
        }
    )

    assert_frame_equal(test_df, expected_df)


def test_not_interpolatable_parameter():
    stations = DwdObservationRequest(
        parameter=Parameter.WIND_DIRECTION,
        resolution=DwdObservationResolution.HOURLY,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
    )

    result = stations.interpolate(latlon=(50.0, 8.9))
    interpolated_df = result.df
    assert interpolated_df.shape[0] == 0
    assert interpolated_df.dropna().shape[0] == 0

    expected_df = pd.DataFrame(
        columns=[
            Columns.DATE.value,
            Columns.PARAMETER.value,
            Columns.VALUE.value,
            Columns.DISTANCE_MEAN.value,
            Columns.STATION_IDS.value,
        ]
    ).reset_index(drop=True)
    expected_df[Columns.VALUE.value] = pd.Series(expected_df[Columns.VALUE.value].values, dtype=float)
    expected_df[Columns.DISTANCE_MEAN.value] = pd.Series(expected_df[Columns.DISTANCE_MEAN.value].values, dtype=float)
    expected_df[Columns.DATE.value] = pd.to_datetime([])

    assert_frame_equal(
        interpolated_df,
        expected_df,
    )


def test_not_interpolatable_dataset():
    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 2),
    )

    result = stations.interpolate(latlon=(50.0, 8.9))
    interpolated_df = result.df
    assert interpolated_df.shape[0] == 0
    assert interpolated_df.dropna().shape[0] == 0

    expected_df = pd.DataFrame(
        columns=[
            Columns.DATE.value,
            Columns.PARAMETER.value,
            Columns.VALUE.value,
            Columns.DISTANCE_MEAN.value,
            Columns.STATION_IDS.value,
        ]
    ).reset_index(drop=True)
    expected_df[Columns.VALUE.value] = pd.Series(expected_df[Columns.VALUE.value].values, dtype=float)
    expected_df[Columns.DISTANCE_MEAN.value] = pd.Series(expected_df[Columns.DISTANCE_MEAN.value].values, dtype=float)
    expected_df[Columns.DATE.value] = pd.to_datetime([])

    assert_frame_equal(
        interpolated_df,
        expected_df,
        check_categorical=False,
    )


def not_supported_provider_dwd_mosmix(caplog):
    request = DwdMosmixRequest(
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
        parameter=["DD", "ww"],
        mosmix_type=DwdMosmixType.SMALL,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.empty
    assert "Interpolation currently only works for DwdObservationRequest" in caplog.text


def test_not_supported_provider_ecc(caplog):
    station = EcccObservationRequest(
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=EcccObservationResolution.DAILY,
    )
    result = station.interpolate(latlon=(50.0, 8.9))
    assert result.df.empty
    assert "Interpolation currently only works for DwdObservationRequest" in caplog.text


def test_interpolation_temperature_air_mean_200_daily_three_floats():
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.DAILY,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
    )
    with pytest.raises(ValueError) as excinfo:
        stations.interpolate(latlon=(0, 1, 2))

    assert str(excinfo.value).startswith("too many values to unpack")


def test_interpolation_temperature_air_mean_200_daily_one_floats():
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.DAILY,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
    )
    with pytest.raises(ValueError) as excinfo:
        stations.interpolate(latlon=(0,))

    assert str(excinfo.value).startswith("not enough values to unpack")


def test_interpolation_temperature_air_mean_200_daily_no_station_found():
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.DAILY,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
    )
    with pytest.raises(StationNotFoundError) as excinfo:
        stations.interpolate_by_station_id(station_id="00")

    assert str(excinfo.value) == "no station found for 00000"
