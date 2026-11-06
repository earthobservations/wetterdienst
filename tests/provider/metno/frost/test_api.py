# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for MET Norway Frost API provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from tests.conftest import FROST_RESOLVER_ON_MACOS
from wetterdienst.provider.metno.frost.api import MetnoFrostRequest

OSLO_BLINDERN = "SN18700"
UTC = ZoneInfo("UTC")

pytestmark = [
    pytest.mark.skipif(
        not MetnoFrostRequest.is_configured(),
        reason="MET Norway Frost credentials not set — provide WD_AUTH__METNO_FROST=<client_id>",
    ),
    FROST_RESOLVER_ON_MACOS,
]


@pytest.mark.remote
def test_metno_frost_stations() -> None:
    """Station metadata for Oslo/Blindern matches the Frost registry."""
    request = MetnoFrostRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start=dt.datetime(2020, 1, 1, tzinfo=UTC),
        end=dt.datetime(2020, 1, 2, tzinfo=UTC),
    ).filter_by_station_id(OSLO_BLINDERN)
    expected = pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "data",
                "station_id": OSLO_BLINDERN,
                "start_timestamp": dt.datetime(1931, 1, 1, tzinfo=UTC),
                "end_timestamp": None,
                "latitude": 59.9423,
                "longitude": 10.72,
                "elevation": 94.0,
                "name": "OSLO - BLINDERN",
                "region": "OSLO",
            }
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(request.df, expected)


@pytest.mark.remote
def test_metno_frost_values_hourly() -> None:
    """Hourly air temperature at Oslo/Blindern returns 25 rows for a one-day window.

    The window is closed: 2020-01-01 00:00 and 2020-01-02 00:00 are both in it.
    """
    df = (
        MetnoFrostRequest(
            parameters=[("hourly", "data", "temperature_air_2m")],
            start=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end=dt.datetime(2020, 1, 2, tzinfo=UTC),
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values()
        .all()
        .df
    )
    assert len(df) == 25
    assert df["station_id"].unique().to_list() == [OSLO_BLINDERN]
    assert df["resolution"].unique().to_list() == ["hourly"]
    assert df["parameter"].unique().to_list() == ["temperature_air_2m"]
    first = df.row(0, named=True)
    assert first["timestamp"] == dt.datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert first["value"] == pytest.approx(3.4)
    assert df["timestamp"].max() == dt.datetime(2020, 1, 2, 0, 0, 0, tzinfo=UTC)


@pytest.mark.remote
def test_metno_frost_values_daily() -> None:
    """Daily air temperature at Oslo/Blindern returns one row per day, the end date included."""
    df = (
        MetnoFrostRequest(
            parameters=[("daily", "data", "temperature_air_mean_2m")],
            start=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end=dt.datetime(2020, 1, 31, tzinfo=UTC),
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values()
        .all()
        .df
    )
    assert len(df) == 31
    assert df["resolution"].unique().to_list() == ["daily"]
    first = df.row(0, named=True)
    assert first["timestamp"] == dt.datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert first["value"] == pytest.approx(1.9)
    assert df["timestamp"].max() == dt.datetime(2020, 1, 31, 0, 0, 0, tzinfo=UTC)


@pytest.mark.remote
def test_metno_frost_values_monthly() -> None:
    """Monthly air temperature at Oslo/Blindern returns one row per month."""
    df = (
        MetnoFrostRequest(
            parameters=[("monthly", "data", "temperature_air_mean_2m")],
            start=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end=dt.datetime(2020, 12, 31, tzinfo=UTC),
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values()
        .all()
        .df
    )
    assert len(df) == 12
    assert df["resolution"].unique().to_list() == ["monthly"]
    first = df.row(0, named=True)
    assert first["timestamp"] == dt.datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert first["value"] == pytest.approx(2.7)


@pytest.mark.remote
def test_metno_frost_values_hourly_multi_parameter_batched(caplog: pytest.LogCaptureFixture) -> None:
    """Requesting multiple hourly parameters issues a single batched request.

    Datasets are declared `grouped: True` so all parameters of a resolution are
    fetched via one comma-separated `elements=` query instead of one request per
    parameter. The response covers every element of the dataset; the requested
    subset is filtered out of it afterward.
    """
    with caplog.at_level("INFO", logger="wetterdienst.provider.metno.frost.api"):
        df = (
            MetnoFrostRequest(
                parameters=[
                    ("hourly", "data", "temperature_air_2m"),
                    ("hourly", "data", "humidity_relative"),
                    ("hourly", "data", "wind_speed_mean_last_10min"),
                ],
                start=dt.datetime(2020, 1, 1, tzinfo=UTC),
                end=dt.datetime(2020, 1, 2, tzinfo=UTC),
            )
            .filter_by_station_id(OSLO_BLINDERN)
            .values()
            .all()
            .df
        )
    acquisitions = [r.message for r in caplog.records if r.message.startswith("Acquiring data from")]
    assert len(acquisitions) == 1
    # the single request's elements= list covers all three requested elements at once
    assert "air_temperature" in acquisitions[0]
    assert "relative_humidity" in acquisitions[0]
    assert "wind_speed" in acquisitions[0]
    assert sorted(df["parameter"].unique().to_list()) == [
        "humidity_relative",
        "temperature_air_2m",
        "wind_speed_mean_last_10min",
    ]
    temperature = df.filter(pl.col("parameter") == "temperature_air_2m")
    # closed one-day window: 00:00 of the 1st and of the 2nd are both in it
    assert len(temperature) == 25
    assert temperature["timestamp"].max() == dt.datetime(2020, 1, 2, 0, 0, 0, tzinfo=UTC)


@pytest.mark.remote
def test_metno_frost_values_6hour_precipitation_no_precipitation_is_zero() -> None:
    """6-hourly precipitation at Oslo/Blindern comes back, its -1 as the no precipitation it stands for (GH-3748).

    Frost answers the query for 2005-09-01 to 2006-01-01 with a 200 and exactly 2 observations, both `-1`
    (2005-09-07 00:00 and 2005-10-13 12:00). Its data clarifications state the code as "No precipitation" for this
    element (see `_decode_sentinels`), so the sum is 0.0 and the code stays in the flags. The range check had turned
    it into a null, which is dropped: "The source has no values".
    """
    df = (
        MetnoFrostRequest(
            parameters=[("6_hours", "data", "precipitation_amount")],
            start=dt.datetime(2005, 9, 1, tzinfo=UTC),
            end=dt.datetime(2006, 1, 1, tzinfo=UTC),
        )
        .filter_by_station_id(OSLO_BLINDERN)
        .values()
        .all()
        .df
    )
    assert len(df) == 2
    assert df["resolution"].unique().to_list() == ["6_hours"]
    assert df["parameter"].unique().to_list() == ["precipitation_amount"]
    assert df["timestamp"].to_list() == [
        dt.datetime(2005, 9, 7, 0, 0, 0, tzinfo=UTC),
        dt.datetime(2005, 10, 13, 12, 0, 0, tzinfo=UTC),
    ]
    assert df["value"].to_list() == [0.0, 0.0]
    # the quality code of Frost, then the code it wrote for the value
    assert df["quality_flags"].to_list() == ["2,raw:-1", "0,raw:-1"]


@pytest.mark.remote
def test_metno_frost_values_6hour_precipitation_before_1982_is_not_read() -> None:
    """6-hourly precipitation of Kjevik in 1951 is every reading -1, wet days included, and is no value (GH-3748).

    SN39040 has -1 for 1,096 of 1,096 readings in 1950 to 1952; on 1951-08-05 the 12-hourly sum is 67.3 mm. Read as a
    dry period it would write 0.0 into a wet day, so before 1982 the code is null (and, null, dropped).
    """
    request = MetnoFrostRequest(
        parameters=[("6_hours", "data", "precipitation_amount")],
        start=dt.datetime(1951, 8, 1, tzinfo=UTC),
        end=dt.datetime(1951, 8, 10, tzinfo=UTC),
        options={"drop_nulls": False},
    )
    df = request.filter_by_station_id("SN39040").values().all().df
    assert df.height > 0
    assert df["value"].null_count() == df.height
    assert all(flags.endswith("raw:-1") for flags in df["quality_flags"].to_list())


@pytest.mark.remote
def test_metno_frost_values_daily_answer_without_a_quality_code_is_read() -> None:
    """The daily precipitation of Skien on 2015-05-01 has no `qualityCode` and is read (GH-3748).

    Frost leaves the key out of the observation; selecting the column raised a `ColumnNotFoundError`. The value is -1,
    which Frost states as 0.0 mm and which is not read for the daily sum yet (GH-3820): null, as the range check made it
    before, with the code in the flags and no quality code in front of it.
    """
    df = (
        MetnoFrostRequest(
            parameters=[("daily", "data", "precipitation_amount")],
            start=dt.datetime(2015, 5, 1, tzinfo=UTC),
            end=dt.datetime(2015, 5, 1, tzinfo=UTC),
            options={"drop_nulls": False},
        )
        .filter_by_station_id("SN30320")
        .values()
        .all()
        .df
    )
    assert df["value"].to_list() == [None]
    assert df["quality_flags"].to_list() == ["rejected:range,raw:-1"]


@pytest.mark.remote
def test_metno_frost_values_window_over_the_limit_is_a_time_interval_error() -> None:
    """6-hourly precipitation of Bjornoya from 1920 to 2026 is over Frost's 100,000 observations (GH-3748).

    Frost answers it with a 403, the status of a refused client ID, whose body says "The estimated number of
    observations (...) exceeds the maximum number allowed (100000)". The client ID is fine and the caller is told to
    narrow the window.
    """
    from wetterdienst.exceptions import InvalidTimeIntervalError  # noqa: PLC0415

    request = MetnoFrostRequest(
        parameters=[("6_hours", "data", "precipitation_amount")],
        start=dt.datetime(1920, 1, 1, tzinfo=UTC),
        end=dt.datetime(2026, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(InvalidTimeIntervalError, match="narrow the window"):
        request.filter_by_station_id("SN99710").values().all()


def test_metno_frost_decodes_sentinels() -> None:
    """Test that Frost's in-band codes become the value they stand for.

    Frost writes these into the value, where nothing distinguishes them from a measurement. Its element descriptions
    state two: snow depth -1 is "no snow", a depth of zero rather than an absent one, and cloud cover -3 and 9 both
    mean the cover could not be estimated (in eighths the latter two convert to -0.375 and 1.125 of the sky). Its data
    clarifications state more (GH-3748, GH-3137): the 6-hourly precipitation sum -1 is "No precipitation", the wind
    direction -3 is "No unique wind direction is given when winds are weak" and the snow depth -3 is "Not possible to
    measure snowdepth", where a snow depth of 0 is "Snowdepth less than 0.5 cm" and a reading.
    """
    from wetterdienst.provider.metno.frost.api import _decode_sentinels  # noqa: PLC0415

    given = pl.DataFrame(
        {
            "parameter": [
                "surface_snow_thickness",
                "surface_snow_thickness",
                "surface_snow_thickness",
                "surface_snow_thickness",
                "cloud_area_fraction",
                "cloud_area_fraction",
                "cloud_area_fraction",
                "wind_from_direction",
                "wind_from_direction",
                "air_temperature",
                "air_temperature",
            ],
            "timestamp": [dt.datetime(2020, 1, 1, tzinfo=UTC)] * 11,
            "value": [-1.0, 12.0, 0.0, -3.0, -3.0, 9.0, 4.0, -3.0, 0.0, -1.0, -3.0],
            "quality_flags": ["0"] * 11,
        },
    )
    decoded = _decode_sentinels(given)
    values = decoded.get_column("value").to_list()
    # the code stays beside the value it stood for, after the quality code (GH-2759)
    assert decoded.get_column("quality_flags").to_list() == [
        "0,raw:-1",
        "0",
        "0",
        "0,raw:-3",
        "0,raw:-3",
        "0,raw:9",
        "0",
        "0,raw:-3",
        "0",
        "0",
        "0",
    ]
    # "no snow" is a depth of zero; a measured depth and a depth of less than 0.5 cm (0) are untouched
    assert values[:3] == [0.0, 12.0, 0.0]
    # a depth that could not be measured is no depth
    assert values[3] is None
    # both codes for "could not be estimated" become null; a real eighth is untouched
    assert values[4] is None
    assert values[5] is None
    assert values[6] == 4.0
    # no unique wind direction is null, and the 0 beside it stays what Frost wrote
    assert values[7] is None
    assert values[8] == 0.0
    # -1 and -3 mean nothing special anywhere else, and a temperature may legitimately be negative
    assert values[9:] == [-1.0, -3.0]


@pytest.mark.remote
def test_metno_frost_values_wind_direction_no_unique_direction_is_null() -> None:
    """The wind direction in weak winds is Frost's -3 and comes back null, the code in the flags (GH-3137).

    SN1165900, a WMO station Frost lists since 2026-11-03, has -3 at 2026-11-04 13:00 (beside a speed of 1 to 2 m/s):
    "No unique wind direction is given when winds are weak" in Frost's data clarifications. The range check used to turn
    it into a null as `rejected:range`, which says the reading is out of range.
    """
    df = (
        MetnoFrostRequest(
            parameters=[("hourly", "data", "wind_direction_mean_last_10min")],
            start=dt.datetime(2026, 11, 4, 13, tzinfo=UTC),
            end=dt.datetime(2026, 11, 4, 13, tzinfo=UTC),
            options={"drop_nulls": False},
        )
        .filter_by_station_id("SN1165900")
        .values()
        .all()
        .df
    )
    assert df["value"].to_list() == [None]
    assert df["quality_flags"].to_list() == ["2,raw:-3"]
