import datetime as dt

import polars as pl
import pytest
from polars.testing import assert_frame_equal
from zoneinfo import ZoneInfo

from wetterdienst.provider.noaa.ghcn import NoaaGhcnParameter, NoaaGhcnRequest


@pytest.mark.slow
@pytest.mark.parametrize(
    "start_date,end_date",
    [
        (dt.datetime(2015, 1, 1), dt.datetime(2022, 1, 1)),
        (dt.datetime(2015, 1, 1, 1), dt.datetime(2022, 1, 1, 1)),
        (dt.datetime(2015, 1, 1, 1, 1), dt.datetime(2022, 1, 1, 1, 1)),
        (dt.datetime(2015, 1, 1, 1, 1, 1), dt.datetime(2022, 1, 1, 1, 1, 1)),
    ],
)
def test_api_amsterdam(start_date, end_date, default_settings):
    request = NoaaGhcnRequest(
        parameter=[NoaaGhcnParameter.DAILY.TEMPERATURE_AIR_MEAN_200],
        resolution="daily",
        start_date=start_date,
        end_date=end_date,
        settings=default_settings,
    ).filter_by_name("DE BILT")
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        {
            "station_id": ["NLM00006260"],
            "dataset": ["daily"],
            "parameter": ["temperature_air_mean_200"],
            "date": [dt.datetime(2021, 1, 1, 23, tzinfo=ZoneInfo("UTC"))],
            "value": [276.84999999999997],
            "quality": [None],
        },
        schema={
            "station_id": pl.Utf8,
            "dataset": pl.Utf8,
            "parameter": pl.Utf8,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
    )
    assert_frame_equal(
        given_df.filter(pl.col("date").eq(dt.datetime(2021, 1, 1, 23, tzinfo=ZoneInfo("UTC")))),
        expected_df,
    )
