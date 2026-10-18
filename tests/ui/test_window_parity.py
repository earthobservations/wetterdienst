# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A bound names the same window in Python, over REST, on the command line and in MCP (GH-3133).

One table of inputs is given to a Python request as ``start`` and ``end``, to ``/api/stations`` and
``/api/values`` as ``timestamp``, to ``wetterdienst stations`` and ``values`` as ``--timestamp`` and as
``--start`` / ``--end``, and to the ``stations`` and ``values`` tools of MCP as ``timestamp``. Each says the
window it resolved (the ``metadata.request`` of its answer, or the ``start`` and ``end`` of the request) and
the readings it answered with, and all of them must say what the table says. A DWD station and its daily
readings are served from memory, so nothing leaves the machine.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst.exceptions import InvalidTimeIntervalError, ReversedTimeIntervalError
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app
from wetterdienst.util.datetime import format_timestamp

PARAMETER = "daily/kl/temperature_air_mean_2m"
STATION = "01048"
_UTC = ZoneInfo("UTC")
_LAST = dt.timedelta(microseconds=1)


def _utc(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=_UTC)


# (what Python is given, what REST is given as `timestamp`, the window both hold)
_SAME_INPUTS = [
    pytest.param(
        {"start": "2020-05-01", "end": "2020-05-03"},
        "2020-05-01/2020-05-03",
        (_utc(2020, 5, 1), _utc(2020, 5, 4) - _LAST),
        id="two dates: the end is the whole of the 3rd",
    ),
    pytest.param(
        {"start": "2020-05-01"},
        "2020-05-01",
        (_utc(2020, 5, 1), _utc(2020, 5, 2) - _LAST),
        id="a start alone is its day",
    ),
    pytest.param(
        {"end": "2020-05-01"},
        "2020-05-01",
        (_utc(2020, 5, 1), _utc(2020, 5, 2) - _LAST),
        id="an end alone is its day",
    ),
    pytest.param(
        {"start": "2020-05-01", "end": "2020-05-01"},
        "2020-05-01/2020-05-01",
        (_utc(2020, 5, 1), _utc(2020, 5, 2) - _LAST),
        id="one date as both bounds is its day",
    ),
    pytest.param(
        {"start": "2020-05-01T06:00:00", "end": "2020-05-03T00:00:00"},
        "2020-05-01T06:00:00/2020-05-03T00:00:00",
        (_utc(2020, 5, 1, 6), _utc(2020, 5, 3)),
        id="two datetimes stay exact, an end at midnight included",
    ),
    pytest.param(
        {"start": "2020-05-01T06:00:00", "end": "2020-05-03"},
        "2020-05-01T06:00:00/2020-05-03",
        (_utc(2020, 5, 1, 6), _utc(2020, 5, 4) - _LAST),
        id="a datetime start and a date end",
    ),
    pytest.param(
        {"start": "2020-05-01", "end": "2020-05-03T00:00:00"},
        "2020-05-01/2020-05-03T00:00:00",
        (_utc(2020, 5, 1), _utc(2020, 5, 3)),
        id="a date start and a datetime end, which stays exact",
    ),
    pytest.param(
        {"start": "2020-05-03T00:00:00+02:00"},
        "2020-05-03T00:00:00+02:00",
        (_utc(2020, 5, 2, 22), _utc(2020, 5, 2, 22)),
        id="an instant in another zone is that instant in UTC",
    ),
    pytest.param(
        {"start": "2020-05", "end": "2020-07"},
        "2020-05/2020-07",
        (_utc(2020, 5, 1), _utc(2020, 8, 1) - _LAST),
        id="two months: the end is the whole of July",
    ),
    pytest.param(
        {"start": "2019", "end": "2020"},
        "2019/2020",
        (_utc(2019, 1, 1), _utc(2021, 1, 1) - _LAST),
        id="two years: the end is the whole of 2020",
    ),
    pytest.param(
        {"start": "2020-05", "end": "2020-07-15"},
        "2020-05/2020-07-15",
        (_utc(2020, 5, 1), _utc(2020, 7, 16) - _LAST),
        id="a month start and a date end",
    ),
    pytest.param(
        {"start": "2020-05-10", "end": "2020-07"},
        "2020-05-10/2020-07",
        (_utc(2020, 5, 10), _utc(2020, 8, 1) - _LAST),
        id="a date start and a month end",
    ),
    pytest.param(
        {"start": "2020-05", "end": "2020-05"},
        "2020-05/2020-05",
        (_utc(2020, 5, 1), _utc(2020, 6, 1) - _LAST),
        id="one month as both bounds is the month",
    ),
    pytest.param(
        {"start": "2020-05"},
        "2020-05",
        (_utc(2020, 5, 1), _utc(2020, 6, 1) - _LAST),
        id="a start alone is its month",
    ),
    pytest.param(
        {"end": "2020-05"},
        "2020-05",
        (_utc(2020, 5, 1), _utc(2020, 6, 1) - _LAST),
        id="an end alone is its month",
    ),
    pytest.param(
        {"start": "2020"},
        "2020",
        (_utc(2020, 1, 1), _utc(2021, 1, 1) - _LAST),
        id="a start alone is its year",
    ),
    pytest.param(
        {"end": "2020"},
        "2020",
        (_utc(2020, 1, 1), _utc(2021, 1, 1) - _LAST),
        id="an end alone is its year",
    ),
    pytest.param(
        {"start": "2020-05-03T06:00:00", "end": "2020-07"},
        "2020-05-03T06:00:00/2020-07",
        (_utc(2020, 5, 3, 6), _utc(2020, 8, 1) - _LAST),
        id="a datetime start and a month end",
    ),
    pytest.param(
        {"start": "2020-05", "end": "2020-07-01T00:00:00"},
        "2020-05/2020-07-01T00:00:00",
        (_utc(2020, 5, 1), _utc(2020, 7, 1)),
        id="a month start and a midnight datetime end, which stays exact",
    ),
    pytest.param(
        {"end": "2020-05-03T00:00:00"},
        "2020-05-03T00:00:00",
        (_utc(2020, 5, 3), _utc(2020, 5, 3)),
        id="a midnight datetime end alone is that instant",
    ),
    pytest.param(
        {"end": "2020-05-03T12:00:00"},
        "2020-05-03T12:00:00",
        (_utc(2020, 5, 3, 12), _utc(2020, 5, 3, 12)),
        id="an end alone with a time is that instant",
    ),
]


@pytest.fixture(autouse=True)
def _serve_dwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve one DWD station and its daily readings from memory, so that nothing is read upstream."""
    stations = pl.DataFrame(
        {
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "station_id": [STATION],
            "start_timestamp": [dt.datetime(1934, 1, 1, tzinfo=_UTC)],
            "end_timestamp": [None],
            "latitude": [51.1278],
            "longitude": [13.7543],
            "elevation": [227.0],
            "name": ["Dresden-Klotzsche"],
            "state": ["Sachsen"],
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        # a reading a day from 2019 to the spring of 2021, so that every window of the table holds some
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        names = [parameter.name_original for parameter in dataset]
        days = [_utc(2019, 1, 1) + dt.timedelta(days=offset) for offset in range(800)]
        rows = len(days) * len(names)
        return pl.DataFrame(
            {
                "timestamp": [day for day in days for _ in names],
                "parameter": names * len(days),
                "value": [1.0] * rows,
                "quality_flags": ["1"] * rows,
                "resolution": ["daily"] * rows,
                "dataset": [dataset.name] * rows,
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _python_window(bounds: dict[str, Any]) -> tuple[dt.datetime | None, dt.datetime | None]:
    request = DwdObservationRequest(parameters="daily/kl", **bounds)
    return request.start, request.end


_SELECTION = {"provider": "dwd", "network": "observation", "parameters": PARAMETER}


def _from_answer(answer: dict[str, Any], kind: str) -> tuple[tuple[str, str], int]:
    """Read the window an answer says it resolved and the number of its readings, or of its stations."""
    request = answer["metadata"]["request"]
    return (request["start"], request["end"]), len(answer[kind])


def _python(kind: str, bounds: dict[str, Any]) -> tuple[tuple[str, str], int]:
    request = DwdObservationRequest(parameters=PARAMETER, **bounds)
    assert request.start is not None
    assert request.end is not None
    window = (format_timestamp(request.start), format_timestamp(request.end))
    if kind == "stations":
        return window, request.all().df.height
    return window, request.filter_by_station_id(STATION).values().all().df.height


def _rest(kind: str, timestamp: str) -> tuple[tuple[str, str], int]:
    selection = {"all": "true"} if kind == "stations" else {"stations": STATION}
    response = TestClient(app).get(f"/api/{kind}", params={**_SELECTION, **selection, "timestamp": timestamp})
    assert response.status_code == 200, response.text
    return _from_answer(response.json(), kind)


def _cli(kind: str, *window: str) -> tuple[tuple[str, str], int]:
    selection = ["--all"] if kind == "stations" else [f"--stations={STATION}"]
    result = CliRunner().invoke(
        cli, [kind, *(f"--{key}={value}" for key, value in _SELECTION.items()), *selection, *window]
    )
    assert result.exit_code == 0, result.output
    return _from_answer(json.loads(result.stdout), kind)


def _mcp(kind: str, timestamp: str) -> tuple[tuple[str, str], int]:
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    selection = {"all": True} if kind == "stations" else {"stations": STATION}

    async def call() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            result = await client.call_tool(kind, {**_SELECTION, **selection, "timestamp": timestamp})
            answer = result.structured_content
            assert answer is not None
            return answer.get("result", answer)

    return _from_answer(asyncio.run(call()), kind)


@pytest.mark.parametrize("kind", ["stations", "values"])
@pytest.mark.parametrize(("bounds", "timestamp", "window"), _SAME_INPUTS)
def test_every_interface_resolves_the_same_inputs_to_the_same_window(
    kind: str, bounds: dict[str, Any], timestamp: str, window: tuple[dt.datetime, dt.datetime]
) -> None:
    """`start`/`end` of Python, the `timestamp` of REST, CLI and MCP and `--start`/`--end` name one window.

    Each answers with the window it resolved and with what the window holds, which is one station for
    `stations` and the same readings for `values`.
    """
    pytest.importorskip("fastmcp")
    said = (format_timestamp(window[0]), format_timestamp(window[1]))
    cli_bounds = [f"--{name}={bound}" for name, bound in bounds.items()]

    answers = {
        "python": _python(kind, bounds),
        "rest": _rest(kind, timestamp),
        "cli --timestamp": _cli(kind, f"--timestamp={timestamp}"),
        "cli --start/--end": _cli(kind, *cli_bounds),
        "mcp": _mcp(kind, timestamp),
    }

    assert {name: answer[0] for name, answer in answers.items()} == dict.fromkeys(answers, said)
    counts = {answer[1] for answer in answers.values()}
    assert len(counts) == 1, answers
    if kind == "stations":
        assert counts == {1}


@pytest.mark.parametrize(
    "bound",
    [dt.date(2020, 5, 3), "2020-05-03"],
    ids=["date", "string"],
)
def test_a_date_is_the_whole_day_as_start_and_as_end(bound: dt.date | str) -> None:
    """A `datetime.date` and the string of the same date are one bound: the first instant, or the last, of the day."""
    assert _python_window({"start": bound}) == (_utc(2020, 5, 3), _utc(2020, 5, 4) - _LAST)
    assert _python_window({"start": "2020-05-01", "end": bound}) == (_utc(2020, 5, 1), _utc(2020, 5, 4) - _LAST)
    assert _python_window({"start": bound, "end": "2020-05-05"}) == (_utc(2020, 5, 3), _utc(2020, 5, 6) - _LAST)


@pytest.mark.parametrize(
    "bound",
    [
        dt.datetime(2020, 5, 3),  # noqa: DTZ001
        dt.datetime(2020, 5, 3, tzinfo=_UTC),
        "2020-05-03T00:00",
        "2020-05-03T00:00:00+00:00",
    ],
    ids=["naive datetime", "datetime", "string with a time", "string with a time and an offset"],
)
def test_a_datetime_at_midnight_is_an_instant_and_stays_exact(bound: dt.datetime | str) -> None:
    """Only a bound that names a day without a time is the day: midnight as a datetime is midnight."""
    assert _python_window({"start": "2020-05-01", "end": bound}) == (_utc(2020, 5, 1), _utc(2020, 5, 3))
    assert _python_window({"end": bound}) == (_utc(2020, 5, 3), _utc(2020, 5, 3))


def test_a_date_end_before_the_start_instant_of_the_same_day_is_not_reversed() -> None:
    """The end of a date is the end of its day, so a start inside that day is no reversed window."""
    assert _python_window({"start": "2020-05-03T12:00:00", "end": "2020-05-03"}) == (
        _utc(2020, 5, 3, 12),
        _utc(2020, 5, 4) - _LAST,
    )


@pytest.mark.parametrize(
    ("bound", "window"),
    [
        ("2020-05", (_utc(2020, 5, 1), _utc(2020, 6, 1) - _LAST)),
        ("2020-12", (_utc(2020, 12, 1), _utc(2021, 1, 1) - _LAST)),
        ("2020-02", (_utc(2020, 2, 1), _utc(2020, 3, 1) - _LAST)),
        ("2019-02", (_utc(2019, 2, 1), _utc(2019, 3, 1) - _LAST)),
        ("2020", (_utc(2020, 1, 1), _utc(2021, 1, 1) - _LAST)),
    ],
)
def test_a_month_or_a_year_is_the_whole_span_as_start_and_as_end(
    bound: str, window: tuple[dt.datetime, dt.datetime]
) -> None:
    """`"2020-05"` and `"2020"` are the month and the year: the first instant as `start`, the last as `end`."""
    assert _python_window({"start": bound}) == window
    assert _python_window({"end": bound}) == window
    assert _python_window({"start": bound, "end": "2030-01-01"})[0] == window[0]
    assert _python_window({"start": "1999-01-01", "end": bound})[1] == window[1]


def test_a_month_or_a_year_start_and_end_of_a_datetime_stay_exact() -> None:
    """A month or a year is a span only as a string: a `datetime` of the first of the month is that instant."""
    assert _python_window({"start": dt.datetime(2020, 5, 1), "end": dt.datetime(2020, 5, 1)}) == (  # noqa: DTZ001
        _utc(2020, 5, 1),
        _utc(2020, 5, 1),
    )


@pytest.mark.parametrize("argument", ["start", "end"])
@pytest.mark.parametrize("bound", ["foo", "2020-13", "2020-05/2020-07", "05.2020", "202005"])
def test_a_string_that_is_no_day_month_year_or_time_is_refused_naming_what_is_accepted(
    argument: str, bound: str
) -> None:
    """A bound that is none of them is a `ValueError` that lists the forms, not isoformat's own message."""
    with pytest.raises(
        InvalidTimeIntervalError, match=rf"{argument}='{bound}'.*month \(\"2020-05\"\).*year \(\"2020\"\)"
    ):
        DwdObservationRequest(parameters="daily/kl", **{argument: bound})  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("bound", ["9999", "9999-12", "9999-12-31"])
def test_a_span_reaching_past_the_last_year_a_datetime_holds_is_refused_as_it_is_over_rest(bound: str) -> None:
    """The last instant of such a span is no datetime: it is refused, not a bare `OverflowError`."""
    with pytest.raises(InvalidTimeIntervalError):
        DwdObservationRequest(parameters="daily/kl", end=bound)
    response = TestClient(app).get("/api/stations", params={**_SELECTION, "all": "true", "timestamp": bound})
    assert response.status_code == 400, response.text


@pytest.mark.parametrize(
    ("bounds", "timestamp"),
    [
        ({"start": "2020-07", "end": "2020-05"}, "2020-07/2020-05"),
        ({"start": "2021", "end": "2020"}, "2021/2020"),
        ({"start": "2020-05-04", "end": "2020-05-03"}, "2020-05-04/2020-05-03"),
        ({"start": "2020-05-03T12:00:00", "end": "2020-05-03T06:00:00"}, "2020-05-03T12:00:00/2020-05-03T06:00:00"),
    ],
)
def test_every_interface_refuses_a_window_that_ends_before_it_starts(bounds: dict[str, str], timestamp: str) -> None:
    """The month or the year of an end is its last instant, so only a window that really ends first is reversed."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    with pytest.raises(ReversedTimeIntervalError):
        DwdObservationRequest(parameters=PARAMETER, **bounds)
    rest = TestClient(app).get("/api/stations", params={**_SELECTION, "all": "true", "timestamp": timestamp})
    assert rest.status_code == 400, rest.text
    for window in ([f"--timestamp={timestamp}"], [f"--{name}={bound}" for name, bound in bounds.items()]):
        result = CliRunner().invoke(
            cli, ["stations", *(f"--{key}={value}" for key, value in _SELECTION.items()), "--all", *window]
        )
        assert result.exit_code == 2, result.output

    async def call() -> None:
        async with Client(build_mcp_server(app)) as client:
            await client.call_tool("stations", {**_SELECTION, "all": True, "timestamp": timestamp})

    with pytest.raises(ToolError, match="ends before it starts"):
        asyncio.run(call())
