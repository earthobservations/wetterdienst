from datetime import datetime

import pandas as pd
import pytest
import pytz
from pandas._testing import assert_frame_equal

from wetterdienst import Parameter
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


@pytest.mark.xfail
def test_summary_temperature_air_mean_200_daily():
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.DAILY,
        start_date=datetime(1934, 1, 1),
        end_date=datetime(1965, 12, 31),
    )
    for result in (stations.summarize(latlon=(51.0221, 13.8470)), stations.summarize_by_station_id(station_id="1050")):
        summarized_df = result.df
        selected_dates = [
            datetime(1934, 1, 1, tzinfo=pytz.UTC),
            datetime(1940, 1, 1, tzinfo=pytz.UTC),
            datetime(1950, 1, 1, tzinfo=pytz.UTC),
        ]
        given = summarized_df.loc[summarized_df.date.isin(selected_dates)].reset_index(drop=True)
        expected = pd.DataFrame(
            {
                "date": pd.to_datetime(selected_dates, utc=True),
                "parameter": ["temperature_air_mean_200", "temperature_air_mean_200", "temperature_air_mean_200"],
                "value": [273.65, 267.65, 270.45],
                "distance": [13.41953430920589, 5.038443044950475, 0.0],
                "station_id": ["01048", "01051", "01050"],
            }
        )

        assert_frame_equal(given, expected)


def test_not_summarizable_dataset():
    stations = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2022, 1, 2),
    )

    result = stations.summarize(latlon=(50.0, 8.9))
    summarized_df = result.df
    assert summarized_df.shape[0] == 0
    assert summarized_df.dropna().shape[0] == 0

    expected_df = pd.DataFrame(
        columns=[
            Columns.DATE.value,
            Columns.PARAMETER.value,
            Columns.VALUE.value,
            Columns.DISTANCE.value,
            Columns.STATION_ID.value,
        ]
    ).reset_index(drop=True)
    expected_df[Columns.VALUE.value] = pd.Series(expected_df[Columns.VALUE.value].values, dtype=float)
    expected_df[Columns.DISTANCE.value] = pd.Series(expected_df[Columns.DISTANCE.value].values, dtype=float)
    expected_df[Columns.DATE.value] = pd.to_datetime([])

    assert_frame_equal(
        summarized_df,
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
    result = request.summarize(latlon=(50.0, 8.9))
    assert result.df.empty
    assert "Interpolation currently only works for DwdObservationRequest" in caplog.text


def test_not_supported_provider_ecc(caplog):
    station = EcccObservationRequest(
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2022, 1, 20),
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=EcccObservationResolution.DAILY,
    )
    result = station.summarize(latlon=(50.0, 8.9))
    assert result.df.empty
    assert "Interpolation currently only works for DwdObservationRequest" in caplog.text
