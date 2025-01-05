import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)


def test_summary_temperature_air_mean_2m_daily(default_settings):
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
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
        [
            {
                "station_id": "7ac6c582",
                "parameter": "temperature_air_mean_2m",
                "date": selected_dates[0],
                "value": 0.5,
                "distance": 13.42,
                "taken_station_id": "01048",
            },
            {
                "station_id": "7ac6c582",
                "parameter": "temperature_air_mean_2m",
                "date": selected_dates[1],
                "value": -5.5,
                "distance": 5.05,
                "taken_station_id": "01051",
            },
            {
                "station_id": "7ac6c582",
                "parameter": "temperature_air_mean_2m",
                "date": selected_dates[2],
                "value": -2.7,
                "distance": 0.0,
                "taken_station_id": "01050",
            },
        ],
        orient="row",
    )
    for result in (request.summarize(latlon=(51.0221, 13.8470)), request.summarize_by_station_id(station_id="1050")):
        given_df = result.df
        given_df = given_df.filter(pl.col("date").is_in(selected_dates))
        assert_frame_equal(given_df, expected_df)


def test_not_summarizable_parameter(default_settings):
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "precipitation_form")],
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
            Columns.STATION_ID.value: pl.String,
            Columns.PARAMETER.value: pl.String,
            Columns.DATE.value: pl.Datetime(time_zone="UTC"),
            Columns.VALUE.value: pl.Float64,
            Columns.DISTANCE.value: pl.Float64,
            Columns.TAKEN_STATION_ID.value: pl.String,
        },
    )
    assert_frame_equal(
        given_df,
        expected_df,
    )


@pytest.mark.remote
def test_provider_dwd_mosmix(default_settings):
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "temperature_air_mean_2m")],
        start_date=dt.datetime.today() + dt.timedelta(days=1),
        end_date=dt.datetime.today() + dt.timedelta(days=8),
        settings=default_settings,
    )
    given_df = request.summarize(latlon=(50.0, 8.9)).df
    assert given_df.get_column("value").min() >= -40  # equals -40.0°C


def test_summary_error_no_start_date():
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
    )
    with pytest.raises(ValueError) as exec_info:
        request.summarize(latlon=(52.8, 12.9))
    assert exec_info.match("start_date and end_date are required for summarization")
