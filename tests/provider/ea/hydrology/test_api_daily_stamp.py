# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the stamp of Environment Agency hydrology daily values."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pytest

from tests.provider.ea.hydrology.test_api import (
    MEASURE_URL,
    STATION_URL,
    STATIONS_URL,
    _measure,
    _station,
    _values_for,
)
from wetterdienst.provider.ea.hydrology import EAHydrologyRequest
from wetterdienst.provider.ea.hydrology import api as ea_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from wetterdienst import Settings

# Readings of flow-m-86400 at station 052d0819-2a32-47df-9b99-c243c9c8235b, as the readings endpoint answers them: the
# daily mean is dated 09:00 of the day it names, whose 24 h run from there to 09:00 of the next day.
_READINGS = [
    {"dateTime": "2025-06-10T09:00:00", "value": 0.448, "quality": "Good"},
    {"dateTime": "2025-06-11T09:00:00", "value": 0.359, "quality": "Good"},
    {"dateTime": "2025-06-12T09:00:00", "value": 0.304, "quality": "Good"},
]


def _serve(
    monkeypatch: pytest.MonkeyPatch, notation: str = "flow-m-86400", readings_items: list[dict] | None = None
) -> None:
    station_id = "0004"
    listing = json.dumps({"items": [_station(station_id, [notation])]}).encode()
    station = json.dumps({"items": [{"measures": [_measure(station_id, notation)]}]}).encode()
    items = readings_items or _READINGS
    readings_url = f"{MEASURE_URL.format(notation=f'{station_id}-{notation}-m3s-qualified')}/readings.json"

    def _download(**kwargs: Any) -> File:  # noqa: ANN401
        url = kwargs["url"]
        if url == STATIONS_URL:
            body = listing
        elif url == STATION_URL.format(station_id=station_id):
            body = station
        elif url.startswith(readings_url):
            # the endpoint answers the oldest `_limit` readings of the window and says nothing of the rest
            limit = parse_qs(urlparse(url).query).get("_limit")
            body = json.dumps({"items": items[: int(limit[0])] if limit else items}).encode()
        else:
            msg = f"unexpected request to {url}"
            raise AssertionError(msg)
        return File(url=url, content=BytesIO(body), status=200)

    monkeypatch.setattr(ea_api, "download_file", _download)


@pytest.mark.parametrize("day", ["2025-06-10", "2025-06-11", "2025-06-12"])
def test_ea_daily_is_stamped_at_00_utc_of_the_day_it_names(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, day: str
) -> None:
    """Test that a daily value is stamped at 00:00 UTC of its day, so a request for that one day returns it.

    The reading is dated D 09:00 and covers the 24 h from there, and was stamped so: a request with start=end=D,
    bounded at 00:00 UTC, returned nothing for it (GH-2683).
    """
    _serve(monkeypatch)
    request = EAHydrologyRequest(
        parameters=[("daily", "data", "discharge_mean")], start=day, end=day, settings=default_settings
    )
    df = request.all().values().all().df
    midnight = dt.datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("UTC"))
    assert df.get_column("timestamp").to_list() == [midnight]
    assert df.get_column("value").to_list() == [{"2025-06-10": 0.448, "2025-06-11": 0.359, "2025-06-12": 0.304}[day]]


# Readings of flow-max-86400 at the same station: the maximum is dated at the instant of the extreme inside the 24 h
# from 09:00 of the day D it names to 09:00 of D+1, so 06-04T03:30 is the maximum of 06-03, 06-05T07:00 that of 06-04
# and 06-05T13:30 that of 06-05; two readings of one calendar date belong to two days.
_MAX_READINGS = [
    {"dateTime": "2025-06-04T03:30:00", "value": 1.096, "quality": "Good"},
    {"dateTime": "2025-06-05T07:00:00", "value": 0.93, "quality": "Good"},
    {"dateTime": "2025-06-05T13:30:00", "value": 1.316, "quality": "Good"},
]


@pytest.mark.parametrize(
    ("day", "expected"),
    [("2025-06-03", 1.096), ("2025-06-04", 0.93), ("2025-06-05", 1.316)],
)
def test_ea_daily_maximum_is_filed_under_the_day_of_its_window(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, day: str, expected: float
) -> None:
    """Test that a maximum dated at the instant of its extreme is stamped at 00:00 UTC of the day its window names.

    Taking the date of the instant gave 06-05 two readings, one of which the deduplication dropped, and left 06-03
    with none (GH-2683).
    """
    _serve(monkeypatch, "flow-max-86400", _MAX_READINGS)
    request = EAHydrologyRequest(
        parameters=[("daily", "data", "discharge_max")], start=day, end=day, settings=default_settings
    )
    df = request.all().values().all().df
    midnight = dt.datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("UTC"))
    assert df.get_column("timestamp").to_list() == [midnight]
    assert df.get_column("value").to_list() == [expected]


def test_ea_daily_readings_are_asked_for_up_to_09_of_the_day_after_the_window(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the readings request reaches the maximum of the window's last day, dated up to 09:00 after its end.

    The 24 h of the last day D run to D+1 09:00 and a maximum is dated at its instant inside them, so a request
    bound of D+1 00:00 left out the maximum of 2025-06-03 dated 2025-06-04T03:30 (GH-2683).
    """
    values, parameter = _values_for(
        ("daily", "data", "discharge_max"),
        default_settings,
        monkeypatch,
        start=dt.datetime(2025, 6, 3, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2025, 6, 3, tzinfo=ZoneInfo("UTC")),
    )
    url = values._readings_url(MEASURE_URL.format(notation="x"), parameter)  # noqa: SLF001
    query = parse_qs(urlparse(url).query)
    assert query["mineq-dateTime"] == ["2025-06-02T00:00:00"]
    assert query["maxeq-dateTime"] == ["2025-06-04T09:00:00"]


@pytest.mark.parametrize(
    ("day", "readings", "expected"),
    [
        # a placeholder with no value at the start of the window, then the reading with one (f22f80f8, level-max-86400)
        (
            "2022-12-11",
            [
                {"dateTime": "2022-12-11T09:00:00", "value": None, "quality": "Missing", "completeness": "Incomplete"},
                {"dateTime": "2022-12-11T18:45:00", "value": 0.319, "quality": "Good", "completeness": "Complete"},
            ],
            0.319,
        ),
        # both Unchecked: the complete reading wins on its completeness alone (052d0819, flow-min-86400), whichever
        # of the two the endpoint sends first
        (
            "2024-02-19",
            [
                {"dateTime": "2024-02-20T08:45:00", "value": 21.2, "quality": "Unchecked", "completeness": "Complete"},
                {
                    "dateTime": "2024-02-19T09:00:00",
                    "value": 23.0,
                    "quality": "Unchecked",
                    "completeness": "Incomplete",
                },
            ],
            21.2,
        ),
        # both Complete: the good one wins on its quality alone, though the unchecked one is later
        (
            "2024-02-19",
            [
                {"dateTime": "2024-02-19T10:00:00", "value": 5.0, "quality": "Good", "completeness": "Complete"},
                {"dateTime": "2024-02-19T11:00:00", "value": 6.0, "quality": "Unchecked", "completeness": "Complete"},
            ],
            5.0,
        ),
        # equal standing: the later one
        (
            "2024-02-19",
            [
                {"dateTime": "2024-02-19T10:00:00", "value": 5.0, "quality": "Good", "completeness": "Complete"},
                {"dateTime": "2024-02-19T11:00:00", "value": 6.0, "quality": "Good", "completeness": "Complete"},
            ],
            6.0,
        ),
    ],
    ids=["null-placeholder", "completeness", "quality", "equal-standing"],
)
def test_ea_daily_window_answered_twice_keeps_the_reading_with_a_value_complete_and_good(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, day: str, readings: list[dict], expected: float
) -> None:
    """Test that of two readings of one window, which share a stamp now, the one with a value, complete, good stays."""
    _serve(monkeypatch, "flow-max-86400", readings)
    request = EAHydrologyRequest(
        parameters=[("daily", "data", "discharge_max")], start=day, end=day, settings=default_settings
    )
    df = request.all().values().all().df
    assert df.get_column("value").to_list() == [expected]


def test_ea_daily_readings_request_sets_no_page_limit(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that a daily readings request carries no `_limit`, which counted one reading per day.

    A window holds more readings than days -- 052d0819 flow-min-86400 answered 7 readings for the 4 days
    2024-02-18 to 2024-02-21, and the `_limit` of 6 cut the newest, 2024-02-21 -- so the count of days is no bound
    (GH-2732).
    """
    values, parameter = _values_for(
        ("daily", "data", "discharge_min"),
        default_settings,
        monkeypatch,
        start=dt.datetime(2024, 2, 18, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2024, 2, 21, tzinfo=ZoneInfo("UTC")),
    )
    query = parse_qs(urlparse(values._readings_url(MEASURE_URL.format(notation="x"), parameter)).query)  # noqa: SLF001
    assert "_limit" not in query
    assert query["mineq-dateTime"] == ["2024-02-17T00:00:00"]
    assert query["maxeq-dateTime"] == ["2024-02-22T09:00:00"]


def test_ea_daily_window_with_more_readings_than_days_keeps_the_last_day(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the readings of a window with more readings than days are all taken, the last day included.

    The readings are those the endpoint answered for 052d0819 flow-min-86400, 2024-02-17 to 2024-02-22 (GH-2732).
    """
    readings = [
        {"dateTime": "2024-02-17T08:45:00", "value": 5.72, "quality": "Unchecked", "completeness": "Complete"},
        {"dateTime": "2024-02-17T11:30:00", "value": 4.18, "quality": "Unchecked", "completeness": "Complete"},
        {"dateTime": "2024-02-18T09:00:00", "value": 7.2, "quality": "Unchecked", "completeness": "Complete"},
        {"dateTime": "2024-02-19T09:00:00", "value": 23.0, "quality": "Unchecked", "completeness": "Incomplete"},
        {"dateTime": "2024-02-20T08:45:00", "value": 21.2, "quality": "Unchecked", "completeness": "Complete"},
        {"dateTime": "2024-02-21T08:45:00", "value": 9.05, "quality": "Unchecked", "completeness": "Complete"},
        {"dateTime": "2024-02-21T13:00:00", "value": 7.9, "quality": "Unchecked", "completeness": "Complete"},
    ]
    _serve(monkeypatch, "flow-min-86400", readings)
    request = EAHydrologyRequest(
        parameters=[("daily", "data", "discharge_min")],
        start="2024-02-18",
        end="2024-02-21",
        settings=default_settings,
    )
    df = request.all().values().all().df
    # 02-19 is answered twice (the 02-19T09:00 reading is incomplete), and the complete one stays
    assert df.get_column("value").to_list() == [7.2, 21.2, 9.05, 7.9]
    assert df.get_column("timestamp").dt.date().dt.strftime("%Y-%m-%d").to_list() == [
        "2024-02-18",
        "2024-02-19",
        "2024-02-20",
        "2024-02-21",
    ]


def test_ea_reading_quality_word_is_kept_in_quality_flags(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that a reading's `quality` word is returned verbatim in `quality_flags` (GH-2018, GH-2758).

    The word was part of the readings schema and then replaced by a null Float64. The Environment Agency's
    reference (environment.data.gov.uk/hydrology/doc/reference, "Quality flags"): "quality: The quality of this
    reading -- Good, Estimated, Suspect, Unchecked, Missing". Checked against the live readings of
    f22f80f8-1bb0-4e77-b225-291487060c6f-flow-m-86400 for 2023 on 2026-10-11: 348 Good and 16 Suspect.
    A reading without a `completeness` has the quality alone (GH-2762).
    """
    readings = [
        {"dateTime": "2025-06-10T09:00:00", "value": 0.448, "quality": "Good"},
        {"dateTime": "2025-06-11T09:00:00", "value": 0.359, "quality": "Suspect"},
        {"dateTime": "2025-06-12T09:00:00", "value": 0.304, "quality": "Estimated"},
    ]
    _serve(monkeypatch, "flow-m-86400", readings)
    request = EAHydrologyRequest(
        parameters=[("daily", "data", "discharge_mean")],
        start="2025-06-10",
        end="2025-06-12",
        settings=default_settings,
    )
    df = request.all().values().all().df.sort("timestamp")
    assert df.select("value", "quality_flags").rows() == [(0.448, "Good"), (0.359, "Suspect"), (0.304, "Estimated")]
    assert "quality" not in df.columns
    assert "quality_flag" not in df.columns


def test_ea_reading_completeness_follows_the_quality_word_in_quality_flags(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that a daily reading's `completeness` is written as a further kind after its quality (GH-2762).

    The reference ("Quality flags") gives `completeness` as "Whether the value is based on complete data or not":
    `Complete` or `Incomplete`. Sampled on 2026-10-15 from the 2015 readings of twelve measures of each kind: the
    daily flow and level carry `Complete` (mostly) or `Incomplete`, and an `Incomplete` reading is `Good` or
    `Missing` (no value); the 15 minute readings and some daily ones carry none, and have the quality alone.
    """
    readings = [
        {"dateTime": "2025-06-10T09:00:00", "value": 0.448, "quality": "Good", "completeness": "Complete"},
        {"dateTime": "2025-06-11T09:00:00", "value": 0.359, "quality": "Good", "completeness": "Incomplete"},
        {"dateTime": "2025-06-12T09:00:00", "value": None, "quality": "Missing", "completeness": "Incomplete"},
        {"dateTime": "2025-06-13T09:00:00", "value": 0.304, "quality": "Suspect", "completeness": None},
        {"dateTime": "2025-06-14T09:00:00", "value": 0.301, "quality": None, "completeness": "Complete"},
    ]
    _serve(monkeypatch, "flow-m-86400", readings)
    request = EAHydrologyRequest(
        parameters=[("daily", "data", "discharge_mean")],
        start="2025-06-10",
        end="2025-06-14",
        settings=default_settings,
        options={"drop_nulls": False},
    )
    df = request.all().values().all().df.sort("timestamp")
    assert df.get_column("quality_flags").to_list() == [
        "Good,completeness:Complete",
        "Good,completeness:Incomplete",
        "Missing,completeness:Incomplete",
        "Suspect",
        "completeness:Complete",
    ]


def test_ea_15_minute_reading_without_completeness_has_the_quality_alone(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that a 15 minute reading, which the endpoint gives no `completeness`, keeps its bare quality (GH-2762)."""
    readings = [{"dateTime": "2025-06-10T09:00:00", "value": 0.448, "quality": "Good"}]
    _serve(monkeypatch, "flow-i-900", readings)
    request = EAHydrologyRequest(
        parameters=[("15_minutes", "data", "discharge")],
        start="2025-06-10",
        end="2025-06-11",
        settings=default_settings,
    )
    df = request.all().values().all().df
    assert df.get_column("quality_flags").to_list() == ["Good"]


def test_ea_daily_descriptions_name_the_09_00_window_and_the_level_datum() -> None:
    """Every daily description says the day runs 09:00 to 09:00, and a level says its datum is unspecified (GH-3136).

    The reference page lists the daily mean, minimum and maximum without a window; the readings are dated 09:00 (the
    premise `_READINGS` above carries) and the mean equals that of the 15 minute flows from 09:00 to 09:00 on 84 of 84
    days of three station-months (2026-10-21). The unit of every river level measure is m, "meters with an
    unspecified datum" in the page's words, which the descriptions of the river water levels must not leave out.
    """
    descriptions = {
        parameter.name_original: parameter.description for parameter in EAHydrologyRequest.metadata["daily"]["data"]
    }
    assert set(descriptions) == {
        "flow-m-86400",
        "flow-max-86400",
        "flow-min-86400",
        "level-max-86400",
        "level-min-86400",
    }
    for notation, description in descriptions.items():
        assert "24 hours from 09:00 of the day it is dated to 09:00 of the next" in description, notation
        if notation.startswith("level"):
            assert "unspecified datum" in description, notation
    river_level = next(p for p in EAHydrologyRequest.metadata["15_minutes"]["data"] if p.name_original == "level-i-900")
    assert "unspecified datum" in river_level.description
