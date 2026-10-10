# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for providers' timestamps on the days the clocks change (GH-2617).

A source that stamps in local time shows its mistakes on two days a year: the hour that is missing in
spring and the one that is repeated in autumn. No fixture elsewhere in the tests covers either day,
so the providers whose stamps carry a local clock are given one here. The providers that stamp in UTC
have nothing to show on these days and are not repeated.

Everything is served from the test, nothing leaves the machine.
"""

import datetime as dt
import json
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dmi.observation.api import DmiObservationValues
from wetterdienst.provider.dwd.alerts.parser import _parse_datetime
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.wsv.pegel import api as wsv_api
from wetterdienst.provider.wsv.pegel.api import WsvPegelRequest
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")
BERLIN = ZoneInfo("Europe/Berlin")


def _wsv_day(day: dt.date) -> list[dict]:
    """Return the 15-minute readings of a German civil day the way Pegelonline writes them, local with an offset."""
    start = dt.datetime.combine(day, dt.time(), tzinfo=BERLIN)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), tzinfo=BERLIN)
    # stepped in UTC and written in local time, so the day has the 92 or 100 readings it really has
    instants = pl.datetime_range(
        start.astimezone(UTC), end.astimezone(UTC), interval="15m", closed="left", time_zone="UTC", eager=True
    )
    return [
        {"timestamp": instant.astimezone(BERLIN).isoformat(timespec="seconds"), "value": float(index)}
        for index, instant in enumerate(instants)
    ]


@pytest.mark.parametrize(
    ("day", "readings"),
    [
        (dt.date(2026, 3, 29), 92),  # 02:00 to 03:00 does not exist
        (dt.date(2026, 10, 25), 100),  # 02:00 to 03:00 happens twice
        (dt.date(2026, 7, 1), 96),
    ],
)
def test_wsv_readings_of_a_clock_change_day_are_distinct_utc_instants(
    monkeypatch: pytest.MonkeyPatch, day: dt.date, readings: int
) -> None:
    """Test that Pegelonline's local stamps with an offset come out as the 15-minute grid in UTC.

    The stamps are legal time (CET/CEST) and each carries its UTC offset, which is what keeps the
    repeated hour of autumn apart: the two 02:30 differ by their offset. Read as local time without
    the offset they would collapse into one instant, and the library would drop one reading of each.
    """
    station = {
        "number": "dst",
        "shortname": "dst",
        "km": 1.0,
        "latitude": 50.0,
        "longitude": 10.0,
        "water": {"shortname": "TEST"},
        "timeseries": [{"shortname": "W", "equidistance": 15, "unit": "cm", "characteristicValues": []}],
    }
    listing = json.dumps([station]).encode()
    measurements = json.dumps(_wsv_day(day)).encode()

    def _download(**kwargs: object) -> File:
        url = str(kwargs["url"])
        content = measurements if url.endswith("measurements.json") else listing
        return File(url=url, content=BytesIO(content), status=200)

    monkeypatch.setattr(wsv_api, "download_file", _download)
    midnight = dt.datetime.combine(day, dt.time(), tzinfo=BERLIN)
    df = (
        WsvPegelRequest(
            parameters=[("15_minutes", "data", "stage")],
            start=midnight.astimezone(UTC),
            end=(midnight + dt.timedelta(days=1)).astimezone(UTC) - dt.timedelta(minutes=15),
        )
        .all()
        .values.all()
        .df
    )
    stamps = df.get_column("timestamp")
    assert df.height == readings
    assert stamps.n_unique() == readings
    # one grid with no hole and no repeat, whatever the clock on the wall did
    assert stamps.sort().diff().drop_nulls().unique().to_list() == [dt.timedelta(minutes=15)]
    assert stamps.min() == midnight.astimezone(UTC)


def test_dmi_stamps_of_the_clock_change_days_are_unique_utc_instants() -> None:
    """Test that DMI's hourly and daily stamps stay distinct over the 23 and 25 hour days.

    DMI writes hourly aggregates in UTC (`+00:00`), and the parse converts whatever offset a stamp
    carries, so the hours around both clock changes are given in UTC and, for one of each, as the
    local stamp a mistaken source would write: they must name the same instants. Daily ones carry the
    station's local offset, which changes on the transition day, and their civil date is taken from
    the string, so each day gets one distinct stamp whatever its length.
    """
    hourly = pl.DataFrame(
        {
            "from": [
                "2025-03-29T23:00:00+00:00",
                "2025-03-30T00:00:00+00:00",
                "2025-03-30T01:00:00+00:00",
                "2025-03-30T02:00:00+00:00",
                "2025-03-30T03:00:00+02:00",  # 01:00 UTC, written on the summer-time clock
                "2025-10-26T00:00:00+00:00",
                "2025-10-26T01:00:00+00:00",
                "2025-10-26T02:00:00+01:00",  # 01:00 UTC, written on the winter-time clock
                "2025-10-26T02:00:00+02:00",  # 00:00 UTC, the first of the two 02:00
            ]
        }
    ).select(DmiObservationValues._date_expression(Resolution.HOURLY).alias("timestamp"))  # noqa: SLF001
    assert hourly.get_column("timestamp").to_list() == [
        dt.datetime(2025, 3, 29, 23, tzinfo=UTC),
        dt.datetime(2025, 3, 30, 0, tzinfo=UTC),
        dt.datetime(2025, 3, 30, 1, tzinfo=UTC),
        dt.datetime(2025, 3, 30, 2, tzinfo=UTC),
        dt.datetime(2025, 3, 30, 1, tzinfo=UTC),
        dt.datetime(2025, 10, 26, 0, tzinfo=UTC),
        dt.datetime(2025, 10, 26, 1, tzinfo=UTC),
        dt.datetime(2025, 10, 26, 1, tzinfo=UTC),
        dt.datetime(2025, 10, 26, 0, tzinfo=UTC),
    ]

    daily = pl.DataFrame(
        {
            "from": [
                "2025-03-29T00:00:00.001000+01:00",
                "2025-03-30T00:00:00.001000+01:00",
                "2025-03-31T00:00:00.001000+02:00",
                "2025-10-25T00:00:00.001000+02:00",
                "2025-10-26T00:00:00.001000+02:00",
                "2025-10-27T00:00:00.001000+01:00",
            ]
        }
    ).select(DmiObservationValues._date_expression(Resolution.DAILY).alias("timestamp"))  # noqa: SLF001
    assert daily.get_column("timestamp").to_list() == [
        dt.datetime(2025, 3, 29, tzinfo=UTC),
        dt.datetime(2025, 3, 30, tzinfo=UTC),
        dt.datetime(2025, 3, 31, tzinfo=UTC),
        dt.datetime(2025, 10, 25, tzinfo=UTC),
        dt.datetime(2025, 10, 26, tzinfo=UTC),
        dt.datetime(2025, 10, 27, tzinfo=UTC),
    ]


def test_dwd_alerts_repeated_hour_of_autumn_stays_two_instants() -> None:
    """Test that a CAP stamp in the repeated hour is told from its twin by the offset it carries.

    DWD writes warnings in local time with the offset (`+02:00` before the clocks go back, `+01:00`
    after), so 02:30 on 2025-10-26 is two instants, an hour apart.
    """
    first = _parse_datetime("2025-10-26T02:30:00+02:00")
    second = _parse_datetime("2025-10-26T02:30:00+01:00")
    assert first == dt.datetime(2025, 10, 26, 0, 30, tzinfo=UTC)
    assert second == dt.datetime(2025, 10, 26, 1, 30, tzinfo=UTC)
    assert first.tzinfo == UTC
    # and the spring hour that does not exist is never produced: 03:00+02:00 follows 01:59+01:00
    assert _parse_datetime("2025-03-30T01:59:00+01:00") == dt.datetime(2025, 3, 30, 0, 59, tzinfo=UTC)
    assert _parse_datetime("2025-03-30T03:00:00+02:00") == dt.datetime(2025, 3, 30, 1, 0, tzinfo=UTC)


def test_dwd_minute_values_before_2000_are_shifted_by_one_hour_in_summer_too() -> None:
    """Test that the pre-2000 stamps of DWD's minute data are taken as MEZ, which has no daylight saving.

    DWD states: "The measurements are assigned to a time stamp in MEZ before the year 2000, and to a
    time stamp in UTC from the year 2000" (the descriptions of the 1, 5 and 10 minute datasets). MEZ
    is UTC+1 all year, so the shift is one hour in July as well as in January, and none from 2000.
    """
    stamps = ["1999-07-01T12:00", "1999-01-01T12:00", "1999-12-31T23:50", "2000-01-01T00:00", "2000-07-01T12:00"]
    df = DwdObservationValues._fix_timestamps(  # noqa: SLF001
        pl.DataFrame({"timestamp": stamps}).select(pl.col("timestamp").str.to_datetime("%Y-%m-%dT%H:%M")),
    )
    assert df.get_column("timestamp").dt.strftime("%Y-%m-%dT%H:%M").to_list() == [
        "1999-07-01T11:00",
        "1999-01-01T11:00",
        "1999-12-31T22:50",
        "2000-01-01T00:00",
        "2000-07-01T12:00",
    ]
