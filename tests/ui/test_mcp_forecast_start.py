# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A tool's forecast answer without a `timestamp` starts at now; no other surface does (GH-4025).

The latest MOSMIX run begins a few hours before the request, and a model reported one of those hours as the forecast.
So the `values` tool leaves out the rows of a forecast network stamped before the current hour (UTC), says so in a
`forecast-from-now` warning that names the `timestamp` window of the earlier part, and only then cuts to the size
budget, so that the budget keeps future hours. The REST API, the command line and the library answer the whole run.

Offline: the readers are stood in for with frames of the shape the core hands out, and the clock is pinned.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.ui.test_mcp_budget import _client_sees, _stub_values, _values_of
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from tests.ui.test_restapi import _values_result_of_shape
from wetterdienst.ui import forecast_start, restapi
from wetterdienst.ui.budget import ANSWER_BUDGET
from wetterdienst.ui.mcp import _mark_tool_requests
from wetterdienst.util.datetime import parse_date_window

if TYPE_CHECKING:
    from wetterdienst.model.result import ValuesResult

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

#: 14:28 UTC: the model run of the tests began at 10:00, four hours before the hour that is now
_CLOCK = dt.datetime(2026, 11, 12, 14, 28, 30, tzinfo=dt.UTC)
_HOUR = dt.datetime(2026, 11, 12, 14, tzinfo=dt.UTC)
_MOSMIX = {
    "provider": "dwd",
    "network": "mosmix",
    "parameters": "hourly/small/temperature_air_2m,hourly/small/wind_speed",
    "stations": "10381",
}
_OBSERVATION = {
    "provider": "dwd",
    "network": "observation",
    "parameters": "hourly/air_temperature/temperature_air_mean_2m",
    "stations": "01048",
}


@pytest.fixture(autouse=True)
def _pinned_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the clock of the cut, and the one the budget picks the end nearest to now by, to `_CLOCK`."""
    monkeypatch.setattr(forecast_start, "_now", lambda: _CLOCK)

    def nearer(first: dt.datetime, last: dt.datetime) -> bool:
        return abs(first - _CLOCK) <= abs(last - _CLOCK)

    monkeypatch.setattr("wetterdienst.ui.budget._start_is_nearer_now", nearer)


def _tool_client() -> TestClient:
    """Make a client of the REST app as an MCP tool's request reaches it."""
    return TestClient(_mark_tool_requests(restapi.app), raise_server_exceptions=False)


def _rest_client() -> TestClient:
    """Make a client of the REST app as any other caller reaches it."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _forecast(
    start: dt.datetime, hours: int, *, resolution: str = "hourly", step: dt.timedelta | None = None
) -> ValuesResult:
    """Give the values of one MOSMIX station and two parameters, `hours` timestamps from `start`, as the core does."""
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest  # noqa: PLC0415

    base = _values_result_of_shape("long")
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "temperature_air_2m"), ("hourly", "small", "wind_speed")]
    )
    df_stations = base.stations.df.filter(pl.col("dataset") == "climate_summary").with_columns(
        pl.lit("hourly").alias("resolution"),
        pl.lit("small").alias("dataset"),
        pl.lit("10381").alias("station_id"),
    )
    stations = replace(base.stations, df=df_stations, _df_all=df_stations, request=request)
    step = step or dt.timedelta(hours=1)
    df = pl.DataFrame(
        [
            {
                "station_id": "10381",
                "resolution": resolution,
                "dataset": "small",
                "parameter": parameter,
                "timestamp": start + step * hour,
                "value": 10.0 + hour / 10,
                "quality_flags": None,
            }
            for parameter in ("temperature_air_2m", "wind_speed")
            for hour in range(hours)
        ],
        schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")},
        orient="row",
    )
    return replace(base, stations=stations, df=df, data_updated_at=start)


def _note_of(answer: dict[str, Any], code: str = "forecast-from-now") -> str:
    notes = [w["message"] for w in answer["metadata"]["warnings"] if w["code"] == code]
    assert len(notes) == 1
    return notes[0]


def _stamps(answer: dict[str, Any]) -> list[dt.datetime]:
    return sorted({dt.datetime.fromisoformat(value["timestamp"]) for value in answer["values"]})


def _window_of(note: str) -> tuple[str, str]:
    start, end = re.search(r"`timestamp=([^/`]+)/([^`]+)`", note).groups()  # ty: ignore[unresolved-attribute]
    return start, end


# --- the cut ------------------------------------------------------------------------------------------------------


def test_a_mosmix_run_that_began_four_hours_ago_starts_at_the_current_hour(monkeypatch: pytest.MonkeyPatch) -> None:
    """The four hours before the current one are left out, the one stamped 14:00 stays, and the note asks for them."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 20))

    response = _tool_client().get("/api/values", params=_MOSMIX)

    assert response.status_code == 200
    answer = response.json()
    stamps = _stamps(answer)
    assert stamps[0] == _HOUR
    assert len(stamps) == 16
    assert len(answer["values"]) == 32
    assert answer["metadata"]["counts"]["rows"] == 32
    note = _note_of(answer)
    assert "starts at the current hour (2026-11-12T14:00:00+00:00)" in note
    assert "4 earlier timestamps (8 rows)" in note
    first, last = _window_of(note)
    # the window the tool accepts, and the left-out hours of it are exactly the four before the current one
    assert parse_date_window(first)[0] == _HOUR - dt.timedelta(hours=4)
    assert parse_date_window(last)[0] == _HOUR - dt.timedelta(hours=1)
    assert response.headers["x-wetterdienst-warnings"] == "forecast-from-now"
    # nothing of the request's place is in what the note tells
    assert "10381" not in note
    assert "latitude" not in note


def test_a_run_that_is_all_past_returns_no_row_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every hour of a stale run is before now: the answer is empty, and the note names the whole run's window."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=30), 24))

    response = _tool_client().get("/api/values", params=_MOSMIX)

    assert response.status_code == 200
    answer = response.json()
    assert answer["values"] == []
    assert answer["metadata"]["counts"] == {"stations": 0, "rows": 0}
    assert answer["metadata"]["data_updated_at"] is None
    note = _note_of(answer)
    assert "model run ends before the current hour" in note
    assert "none is returned" in note
    first, last = _window_of(note)
    assert parse_date_window(first)[0] == _HOUR - dt.timedelta(hours=30)
    assert parse_date_window(last)[0] == _HOUR - dt.timedelta(hours=7)


def test_a_run_that_begins_now_or_later_is_left_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is before the current hour, so nothing is left out and no note is attached."""
    _stub_values(monkeypatch, _forecast(_HOUR, 20))

    response = _tool_client().get("/api/values", params=_MOSMIX)

    answer = response.json()
    assert len(_stamps(answer)) == 20
    assert answer["metadata"]["warnings"] == []
    assert "x-wetterdienst-warnings" not in response.headers


@pytest.mark.parametrize(
    "timestamp",
    [
        # an hour window, a time part on either half, or a month or a year: served exactly as asked
        "2026-11-12T10:00/2026-11-12T20:00",
        "2026-11-12T14",
        "2026-11-12/2026-11-13T00:00",
        "2026-11-12T00:00/2026-11-14",
        "2026-11",
        "2026",
        # whole days wholly in the past or in the future
        "2026-11-10",
        "2026-11-13",
        "2026-11-10/2026-11-11",
        "2026-11-13/2026-11-14",
    ],
)
def test_a_window_that_is_no_day_around_now_is_left_as_the_caller_chose_it(
    monkeypatch: pytest.MonkeyPatch, timestamp: str
) -> None:
    """With a time part, or days that do not contain now, the past hours of the run are what was asked for."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 20))

    answer = _tool_client().get("/api/values", params={**_MOSMIX, "timestamp": timestamp}).json()

    assert _stamps(answer)[0] == _HOUR - dt.timedelta(hours=4)
    assert len(answer["values"]) == 40
    assert answer["metadata"]["warnings"] == []


@pytest.mark.parametrize("timestamp", ["2026-11-12", "2026-11-12/2026-11-14", "2026-11-11/2026-11-12", "20261112"])
def test_a_window_of_days_that_contains_now_starts_at_the_current_hour(
    monkeypatch: pytest.MonkeyPatch, timestamp: str
) -> None:
    """The instructions tell a model to give a day: today's hours before the current one are left out, with the note."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 20))

    response = _tool_client().get("/api/values", params={**_MOSMIX, "timestamp": timestamp})

    answer = response.json()
    assert _stamps(answer)[0] == _HOUR
    assert len(answer["values"]) == 32
    note = _note_of(answer)
    assert "4 earlier timestamps (8 rows)" in note
    first, last = _window_of(note)
    assert parse_date_window(first)[0] == _HOUR - dt.timedelta(hours=4)
    assert parse_date_window(last)[0] == _HOUR - dt.timedelta(hours=1)
    assert response.headers["x-wetterdienst-warnings"] == "forecast-from-now"


def test_the_days_of_a_window_before_today_are_what_the_caller_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """A span from yesterday keeps yesterday's rows of the run and loses only today's hours before now."""
    midnight = dt.datetime(2026, 11, 12, tzinfo=dt.UTC)
    _stub_values(monkeypatch, _forecast(midnight - dt.timedelta(hours=6), 30))

    answer = _tool_client().get("/api/values", params={**_MOSMIX, "timestamp": "2026-11-11/2026-11-12"}).json()

    stamps = _stamps(answer)
    # yesterday 18:00 to 23:00 stay, today's 00:00 to 13:00 go, 14:00 on stays
    assert stamps[:6] == [midnight - dt.timedelta(hours=6 - hour) for hour in range(6)]
    assert stamps[6] == _HOUR
    assert len(stamps) == 6 + 30 - 6 - 14
    first, last = _window_of(_note_of(answer))
    assert parse_date_window(first)[0] == midnight
    assert parse_date_window(last)[0] == _HOUR - dt.timedelta(hours=1)


def test_a_day_window_is_decided_from_the_text_not_from_what_it_parses_to() -> None:
    """`2026-11-12T00:00` parses to the same instant as the day `2026-11-12`, and is a time: left as asked."""
    here = forecast_start._is_day_window_around  # noqa: SLF001
    assert here("2026-11-12", _CLOCK)
    assert here("2026-11-12/2026-11-12", _CLOCK)
    assert here("2026-11-12/2026-11-14", _CLOCK)
    assert not here("2026-11-12T00:00", _CLOCK)
    assert not here("2026-11-12T00:00/2026-11-14", _CLOCK)
    assert not here("2026-11-12/2026-11-14T00:00", _CLOCK)
    assert not here("2026-11-12t12", _CLOCK)
    assert not here("2026-11-12+02:00", _CLOCK)
    assert not here("2026-11", _CLOCK)
    assert not here("2026-11-10", _CLOCK)
    assert not here("2026-11-13", _CLOCK)
    assert not here("2026-11-14/2026-11-12/2026-11-15", _CLOCK)
    assert not here("9999-12-31/9999-12-31", _CLOCK)


def test_a_day_window_around_now_is_not_cut_for_an_explicit_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run asked for by its issue is left whole, with a day window as without one."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=30), 24))

    answer = (
        _tool_client()
        .get("/api/values", params={**_MOSMIX, "issue": "2026-11-11T09:00:00Z", "timestamp": "2026-11-12"})
        .json()
    )

    assert len(answer["values"]) == 48
    assert answer["metadata"]["warnings"] == []


def test_a_day_window_around_now_is_not_cut_for_another_kind_of_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Observation values of today before the current hour are what an observation window is for."""
    start = _HOUR - dt.timedelta(hours=4)
    _stub_values(monkeypatch, _values_of(start, 20))

    answer = _tool_client().get("/api/values", params={**_OBSERVATION, "timestamp": "2026-11-12"}).json()

    assert _stamps(answer)[0] == start
    assert answer["metadata"]["warnings"] == []


def test_the_rest_api_answers_a_day_window_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not a tool's request: the day window around now returns every hour of the run."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 20))

    answer = _rest_client().get("/api/values", params={**_MOSMIX, "timestamp": "2026-11-12"}).json()

    assert len(answer["values"]) == 40
    assert answer["metadata"]["warnings"] == []


def test_a_run_asked_for_by_its_issue_is_left_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    """An older run is past by nature, and asking for it by its issue says so: cutting it would answer nothing."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=30), 24))

    answer = _tool_client().get("/api/values", params={**_MOSMIX, "issue": "2026-11-11T09:00:00Z"}).json()

    assert len(answer["values"]) == 48
    assert answer["metadata"]["warnings"] == []
    # `latest` is the default said out loud
    cut = _tool_client().get("/api/values", params={**_MOSMIX, "issue": "Latest"}).json()
    assert cut["values"] == []


def test_an_observation_network_is_left_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only a forecast network starts at now: a record of observations has rows before now by nature."""
    start = _HOUR - dt.timedelta(hours=4)
    _stub_values(monkeypatch, _values_of(start, 20))

    answer = _tool_client().get("/api/values", params=_OBSERVATION).json()

    assert _stamps(answer)[0] == start
    assert len(answer["values"]) == 40
    assert answer["metadata"]["warnings"] == []


# --- the resolutions ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("resolution", "period", "start"),
    [
        ("15_minutes", "hour", dt.datetime(2026, 11, 12, 14, tzinfo=dt.UTC)),
        ("hourly", "hour", dt.datetime(2026, 11, 12, 14, tzinfo=dt.UTC)),
        ("subdaily", "hour", dt.datetime(2026, 11, 12, 14, tzinfo=dt.UTC)),
        ("6_hours", "6-hour period", dt.datetime(2026, 11, 12, 12, tzinfo=dt.UTC)),
        ("daily", "day", dt.datetime(2026, 11, 12, tzinfo=dt.UTC)),
        ("monthly", "month", dt.datetime(2026, 11, 1, tzinfo=dt.UTC)),
        ("annual", "year", dt.datetime(2026, 1, 1, tzinfo=dt.UTC)),
    ],
)
def test_the_start_of_now_follows_the_resolution(resolution: str, period: str, start: dt.datetime) -> None:
    """An hour of an hourly forecast, the day of a daily one, ...: the period the clock is in, in UTC."""
    assert forecast_start._start_of(resolution, _CLOCK) == (period, start)  # noqa: SLF001


def test_a_daily_forecast_starts_at_the_current_day() -> None:
    """The days before today are left out and today, stamped at its start, stays, though its midnight has passed."""
    midnight = dt.datetime(2026, 11, 12, tzinfo=dt.UTC)
    result = _forecast(midnight - dt.timedelta(days=3), 10, resolution="daily", step=dt.timedelta(days=1))

    cut = forecast_start.forecast_from_now(result)

    stamps = sorted(cut.df.get_column("timestamp").unique().to_list())
    assert stamps[0] == midnight
    assert len(stamps) == 7
    assert cut.df.height == 14


def test_a_mixed_frame_is_cut_by_each_rows_resolution() -> None:
    """A row is judged by its own resolution: a daily row of today stays beside an hourly row of an hour ago."""
    hourly = _forecast(_HOUR - dt.timedelta(hours=3), 5)
    daily = _forecast(dt.datetime(2026, 11, 11, tzinfo=dt.UTC), 3, resolution="daily", step=dt.timedelta(days=1))
    result = replace(hourly, df=pl.concat([hourly.df, daily.df]))

    cut = forecast_start.forecast_from_now(result)

    assert cut.df.filter(pl.col("resolution") == "hourly").get_column("timestamp").min() == _HOUR
    assert cut.df.filter(pl.col("resolution") == "daily").get_column("timestamp").min() == dt.datetime(
        2026, 11, 12, tzinfo=dt.UTC
    )


def test_every_forecast_network_has_an_hourly_resolution_today() -> None:
    """The networks the cut applies to are found through their metadata, by `kind`; each is hourly."""
    from wetterdienst import Wetterdienst  # noqa: PLC0415

    found = {
        f"{provider}/{network}"
        for provider, networks in Wetterdienst.discover().items()
        for network, listing in networks.items()
        if listing["kind"] == "forecast"
    }
    assert found == {"dwd/mosmix", "dwd/dmo", "dwd/swsmos"}
    for name in found:
        provider, _, network = name.partition("/")
        metadata = Wetterdienst.resolve(provider, network).metadata
        assert {resolution.name for resolution in metadata.resolutions} == {"hourly"}


def test_a_single_timestamp_left_out_is_told_in_the_singular(monkeypatch: pytest.MonkeyPatch) -> None:
    """One earlier timestamp is `the earlier timestamp`, not `the 1 earlier timestamps`, and one row is `1 row`."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=1), 20))

    note = _note_of(_tool_client().get("/api/values", params=_MOSMIX).json())

    assert "the earlier timestamp (2 rows) of the model run is left out" in note
    assert "For it, ask again" in note
    assert "1 earlier" not in note
    one = forecast_start._amount  # noqa: SLF001
    assert one(1, 1) == "the earlier timestamp (1 row)"
    assert one(3, 6) == "the 3 earlier timestamps (6 rows)"


def test_a_mixed_frame_gets_one_window_for_each_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """A window of the hourly rows would span the daily rows that were kept: each resolution has its own."""
    hourly = _forecast(_HOUR - dt.timedelta(hours=3), 5)
    daily = _forecast(dt.datetime(2026, 11, 10, tzinfo=dt.UTC), 3, resolution="daily", step=dt.timedelta(days=1))
    result = replace(hourly, df=pl.concat([hourly.df, daily.df]))
    _stub_values(monkeypatch, result)

    answer = _tool_client().get("/api/values", params=_MOSMIX).json()

    note = _note_of(answer)
    assert (
        "the current period of each resolution (daily 2026-11-12T00:00:00+00:00, hourly 2026-11-12T14:00:00+00:00)"
        in note
    )
    assert "ask again by resolution, daily: `timestamp=2026-11-10T00:00:00+00:00/2026-11-11T00:00:00+00:00`" in note
    assert "hourly: `timestamp=2026-11-12T11:00:00+00:00/2026-11-12T13:00:00+00:00`" in note


# --- the budget ---------------------------------------------------------------------------------------------------


def test_the_cut_comes_first_and_the_budget_keeps_future_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """The budget counts the rows that are left and the note of the cut, and keeps the start of what is left."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 900))

    response = _tool_client().get("/api/values", params=_MOSMIX)

    answer = response.json()
    stamps = _stamps(answer)
    # the answer begins at the current hour, not at the model run's first hour
    assert stamps[0] == _HOUR
    assert response.headers["x-wetterdienst-warnings"] == "forecast-from-now, answer-truncated"
    truncated = _note_of(answer, "answer-truncated")
    assert "of 1,792 rows are returned" in truncated
    first, _ = _window_of(truncated)
    assert parse_date_window(first)[0] == stamps[-1] + dt.timedelta(hours=1)
    # the note of the cut is still there, with the window of the hours it left out
    assert "4 earlier timestamps" in _note_of(answer)
    assert len(json.dumps(answer, separators=(",", ":"), ensure_ascii=False)) + len('{"result":}') <= ANSWER_BUDGET


def test_the_note_of_the_cut_is_inside_what_the_budget_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """What a client receives, the note included, is within the budget: the note's characters are counted."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 900))

    result = _client_sees("values", _MOSMIX)

    assert not result.is_error, result.content
    structured = result.structured_content
    assert len(json.dumps(structured, separators=(",", ":"), ensure_ascii=False)) <= ANSWER_BUDGET
    assert "forecast-from-now" in [w["code"] for w in structured["result"]["metadata"]["warnings"]]


def test_the_budget_keeps_more_future_hours_than_before(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the cut the budget spends characters on the four past hours; with it all of them go to future ones."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 900))

    after = _stamps(_tool_client().get("/api/values", params=_MOSMIX).json())
    monkeypatch.setattr(forecast_start, "applies", lambda *_: False)
    before = _stamps(_tool_client().get("/api/values", params=_MOSMIX).json())

    assert before[0] == _HOUR - dt.timedelta(hours=4)
    assert after[0] == _HOUR
    assert len([stamp for stamp in before if stamp >= _HOUR]) == len(before) - 4
    # the note of the cut costs a few characters, which are fewer than the four hours it saves
    assert len(after) > len(before) - 4


# --- the formats --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["csv", "ndjson"])
def test_a_csv_or_ndjson_carries_the_note_in_a_header_and_the_sentence(
    monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """A format with no block has the note in `X-Wetterdienst-Forecast-From-Now` and in the tool's sentence."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 20))

    response = _tool_client().get("/api/values", params={**_MOSMIX, "format": fmt})

    assert response.status_code == 200
    header = response.headers["x-wetterdienst-forecast-from-now"]
    assert header.isascii()
    assert unquote(header).startswith("The answer starts at the current hour")
    assert response.headers["x-wetterdienst-warnings"] == "forecast-from-now"
    if fmt == "csv":
        assert len(response.text.splitlines()) - 1 == 32
        assert "2026-11-12T10:00" not in response.text
    result = _client_sees("values", {**_MOSMIX, "format": fmt})
    sentence = result.structured_content["result"]
    assert f"Forecast: {unquote(header)}" in sentence
    assert "Warnings: forecast-from-now." in sentence
    if fmt == "csv":
        assert "2026-11-12T10:00" not in sentence.split("\n\n", 1)[1]


def test_a_csv_that_is_cut_to_the_budget_tells_both_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sentence of a long CSV carries the note of the cut and then the note of the budget, and fits the budget."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 1500))

    result = _client_sees("values", {**_MOSMIX, "format": "csv"})

    sentence = result.structured_content["result"]
    assert len(sentence) <= ANSWER_BUDGET
    assert "Forecast: The answer starts at the current hour" in sentence
    assert "Truncated: The answer was cut to stay within 40,000 characters" in sentence


@pytest.mark.parametrize("fmt", ["json", "geojson"])
def test_geojson_is_cut_too(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """The chart-less structured formats come from the cut result."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 20))

    body = _tool_client().get("/api/values", params={**_MOSMIX, "format": fmt}).json()

    assert _note_of(body).startswith("The answer starts at the current hour")
    if fmt == "geojson":
        stamps = {value["timestamp"] for feature in body["data"]["features"] for value in feature["values"]}
        assert min(dt.datetime.fromisoformat(stamp) for stamp in stamps) == _HOUR


# --- the other surfaces -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv", "ndjson"])
def test_the_rest_api_answers_the_whole_run(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """A request that is not a tool's gets every hour of the run: no cut, no note, no header, byte for byte."""
    from tests.ui.test_restapi import _stub_stream  # noqa: PLC0415

    result = _forecast(_HOUR - dt.timedelta(hours=4), 20)
    _stub_values(monkeypatch, result)
    _stub_stream(monkeypatch, [result])

    response = _rest_client().get("/api/values", params={**_MOSMIX, "format": fmt})

    assert response.status_code == 200
    assert "forecast-from-now" not in response.text
    assert "x-wetterdienst-forecast-from-now" not in response.headers
    assert "forecast-from-now" not in response.headers.get("x-wetterdienst-warnings", "")
    if fmt == "json":
        body = response.json()
        assert len(body["values"]) == 40
        assert _stamps(body)[0] == _HOUR - dt.timedelta(hours=4)
        assert body["metadata"]["warnings"] == []
    if fmt == "csv":
        assert len(response.text.splitlines()) - 1 == 40


def test_the_rest_answer_is_the_same_bytes_with_the_cut_in_the_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """The JSON of the REST API for a forecast is the result's own, as `to_dict` writes it, plus the block."""
    result = _forecast(_HOUR - dt.timedelta(hours=4), 20)
    _stub_values(monkeypatch, result)

    body = _rest_client().get("/api/values", params=_MOSMIX).json()

    assert body["values"] == json.loads(result.to_json())["values"]


def test_python_and_the_cli_answer_the_whole_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A result in Python is whole, and the command line, which never imports the cut, writes every hour."""
    result: ValuesResult = _forecast(_HOUR - dt.timedelta(hours=4), 20)
    assert len(json.loads(result.to_json())["values"]) == 40
    from click.testing import CliRunner  # noqa: PLC0415

    from wetterdienst.ui import cli as cli_module  # noqa: PLC0415

    monkeypatch.setattr(cli_module, "get_values", lambda **_kwargs: result)
    output = CliRunner().invoke(
        cli_module.cli,
        [
            "values",
            "--provider",
            "dwd",
            "--network",
            "mosmix",
            "--parameters",
            _MOSMIX["parameters"],
            "--stations",
            "10381",
        ],
    )
    assert output.exit_code == 0, output.output
    assert len(json.loads(output.output)["values"]) == 40
    assert "forecast-from-now" not in output.output


def test_interpolate_and_summarize_take_a_required_timestamp() -> None:
    """They are out of scope because a window is always given: the request refuses one without it."""
    from pydantic import ValidationError  # noqa: PLC0415

    from wetterdienst.ui.core import InterpolationRequest, SummaryRequest  # noqa: PLC0415

    for request in (InterpolationRequest, SummaryRequest):
        assert request.model_fields["timestamp"].is_required()
        with pytest.raises(ValidationError):
            request(provider="dwd", network="mosmix", parameters="hourly/small/temperature_air_2m", station="10381")


def test_a_note_holds_no_coordinates(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """The note and the log line carry the window of the run and nothing of the place asked for."""
    _stub_values(monkeypatch, _forecast(_HOUR - dt.timedelta(hours=4), 20))

    with caplog.at_level("DEBUG"):
        response = _tool_client().get(
            "/api/values", params={**_MOSMIX, "stations": None, "latitude": 35.68, "longitude": 139.69, "rank": 1}
        )

    assert response.status_code == 200
    assert "35.68" not in _note_of(response.json())
    # the server's own log lines, not the test client's record of the URL it was given
    server_log = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("wetterdienst"))
    assert "35.68" not in server_log


# --- what the model is told ---------------------------------------------------------------------------------------


def test_the_instructions_stay_under_their_limit() -> None:
    """A sentence about the start of a forecast, if there is one, fits the 7,800 characters the instructions keep to."""
    from wetterdienst.ui.mcp import INSTRUCTIONS  # noqa: PLC0415

    assert len(INSTRUCTIONS) < 7800
