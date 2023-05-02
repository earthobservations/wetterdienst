import datetime as dt

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationRequest,
    DwdObservationResolution,
)
from wetterdienst.provider.eccc.observation.api import EcccObservationRequest


@pytest.mark.xfail
def test_summary_temperature_air_mean_200_daily(default_settings):
    request = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="daily",
        start_date=dt.datetime(1934, 1, 1),
        end_date=dt.datetime(1965, 12, 31),
        settings=default_settings,
    )
    selected_dates = [
        dt.datetime(1934, 1, 1, tzinfo=dt.timezone.utc),
        dt.datetime(1940, 1, 1, tzinfo=dt.timezone.utc),
        dt.datetime(1950, 1, 1, tzinfo=dt.timezone.utc),
    ]
    expected_df = pl.DataFrame(
        {
            "date": selected_dates,
            "parameter": ["temperature_air_mean_200", "temperature_air_mean_200", "temperature_air_mean_200"],
            "value": [273.65, 267.65, 270.45],
            "distance": [13.41953430920589, 5.038443044950475, 0.0],
            "station_id": ["01048", "01051", "01050"],
        }
    )
    for result in (request.summarize(latlon=(51.0221, 13.8470)), request.summarize_by_station_id(station_id="1050")):
        given_df = result.df
        given_df = given_df.loc[given_df.date.isin(selected_dates)].reset_index(drop=True)
        assert_frame_equal(given_df, expected_df)


def test_not_summarizable_dataset(default_settings):
    request = DwdObservationRequest(
        parameter=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.HOURLY,
        start_date=dt.datetime(2022, 1, 1),
        end_date=dt.datetime(2022, 1, 2),
        settings=default_settings,
    )
    result = request.summarize(latlon=(50.0, 8.9))
    given_df = result.df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    expected_df = pl.DataFrame(
        schema={
            Columns.DATE.value: pl.Datetime(time_zone="UTC"),
            Columns.PARAMETER.value: pl.Utf8,
            Columns.VALUE.value: pl.Float64,
            Columns.DISTANCE.value: pl.Float64,
            Columns.STATION_ID.value: pl.Utf8,
        },
    )
    assert_frame_equal(
        given_df,
        expected_df,
    )


def test_not_supported_provider_dwd_mosmix(default_settings, caplog):
    request = DwdMosmixRequest(
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        parameter=["DD", "ww"],
        mosmix_type=DwdMosmixType.SMALL,
        settings=default_settings,
    )
    given_df = request.summarize(latlon=(50.0, 8.9)).df
    assert given_df.is_empty()
    assert "Summary currently only works for DwdObservationRequest" in caplog.text


def test_not_supported_provider_ecc(default_settings, caplog):
    request = EcccObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="daily",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2022, 1, 20),
        settings=default_settings,
    )
    given_df = request.summarize(latlon=(50.0, 8.9)).df
    assert given_df.is_empty()
    assert "Summary currently only works for DwdObservationRequest" in caplog.text
