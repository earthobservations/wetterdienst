import datetime as dt

import polars as pl
import pytest
from polars.testing import assert_frame_equal
from zoneinfo import ZoneInfo

from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationRequest,
    DwdObservationResolution,
)
from wetterdienst.provider.eccc.observation.api import EcccObservationRequest


def test_summary_temperature_air_mean_200_daily(default_settings):
    request = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="daily",
        start_date=dt.datetime(1934, 1, 1),
        end_date=dt.datetime(1965, 12, 31),
        settings=default_settings,
    )
    selected_dates = [
        dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1940, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1950, 1, 1, tzinfo=ZoneInfo("UTC")),
    ]
    expected_df = pl.DataFrame(
        {
            "station_id": ["7ac6c582", "7ac6c582", "7ac6c582"],
            "parameter": ["temperature_air_mean_200", "temperature_air_mean_200", "temperature_air_mean_200"],
            "date": selected_dates,
            "value": [273.65, 267.65, 270.45],
            "distance": [13.42, 5.05, 0.0],
            "taken_station_id": ["01048", "01051", "01050"],
        },
    )
    for result in (request.summarize(latlon=(51.0221, 13.8470)), request.summarize_by_station_id(station_id="1050")):
        given_df = result.df
        given_df = given_df.filter(pl.col("date").is_in(selected_dates))
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
            Columns.STATION_ID.value: pl.Utf8,
            Columns.PARAMETER.value: pl.Utf8,
            Columns.DATE.value: pl.Datetime(time_zone="UTC"),
            Columns.VALUE.value: pl.Float64,
            Columns.DISTANCE.value: pl.Float64,
            Columns.TAKEN_STATION_ID.value: pl.Utf8,
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


@pytest.mark.xfail
def test_not_supported_provider_eccc(default_settings, caplog):
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
