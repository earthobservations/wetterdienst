# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The buffer a station's published end gets against the request window, one rule for every surface (GH-3220).

A station is kept for a window unless it started after it or ended before it by more than the buffer: two days
by default, 62 for monthly and 732 for annual, or the `station_window_end_buffer` option (days, for every
resolution, 0 for the exact end). The start is compared exactly. The rule is `limit_to_window`; Python's
`filter_by_name` and the stations listing of REST, the command line and MCP apply it, and the tests here give
them the same catalogue and hold them to the same stations. The catalogue is served from memory.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from pydantic import ValidationError

from wetterdienst import Settings
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.request import limit_to_window
from wetterdienst.options import Options
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app

if TYPE_CHECKING:
    from pathlib import Path

_UTC = dt.UTC
_WINDOW = dt.datetime(2026, 10, 16, tzinfo=_UTC)
_WINDOW_END = dt.datetime(2026, 10, 16, 23, 59, 59, 999999, tzinfo=_UTC)
_DAY = dt.timedelta(days=1)

#: the buffer of each resolution when the option is not given
_DEFAULT_DAYS = {
    Resolution.MINUTE_1.value: 2,
    Resolution.MINUTE_10.value: 2,
    Resolution.HOURLY.value: 2,
    Resolution.SUBDAILY.value: 2,
    Resolution.DAILY.value: 2,
    Resolution.MONTHLY.value: 62,
    Resolution.ANNUAL.value: 732,
}


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the options."""
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def _frame(resolution: str, start: dt.datetime | None, end: dt.datetime | None) -> pl.DataFrame:
    return pl.DataFrame(
        {"station_id": ["1"], "resolution": [resolution], "start_timestamp": [start], "end_timestamp": [end]},
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )


def _kept(resolution: str, ends: dt.datetime | None, buffer: int | None, starts: dt.datetime | None = None) -> bool:
    """Tell whether a station of this resolution that started and ended as given is kept for the window."""
    return not limit_to_window(_frame(resolution, starts, ends), _WINDOW, _WINDOW_END, buffer).is_empty()


# the rule


@pytest.mark.parametrize("resolution", _DEFAULT_DAYS)
def test_the_default_buffer_of_each_resolution_inside_on_the_edge_and_outside(resolution: str) -> None:
    """An end the buffer short of the window start is kept, a day further away is not."""
    days = dt.timedelta(days=_DEFAULT_DAYS[resolution])

    assert _kept(resolution, _WINDOW - days + _DAY, None)
    assert _kept(resolution, _WINDOW - days, None), "the edge is kept"
    assert not _kept(resolution, _WINDOW - days - _DAY, None)
    assert not _kept(resolution, _WINDOW - days - dt.timedelta(microseconds=1), None)


@pytest.mark.parametrize("resolution", _DEFAULT_DAYS)
def test_a_buffer_of_zero_compares_the_end_exactly(resolution: str) -> None:
    """An end on the window start is in the window, one before it is not, whatever the resolution."""
    assert _kept(resolution, _WINDOW, 0)
    assert _kept(resolution, _WINDOW + _DAY, 0)
    assert not _kept(resolution, _WINDOW - dt.timedelta(microseconds=1), 0)
    assert not _kept(resolution, _WINDOW - _DAY, 0)


@pytest.mark.parametrize("resolution", _DEFAULT_DAYS)
def test_a_custom_buffer_is_the_same_number_of_days_for_every_resolution(resolution: str) -> None:
    """The option replaces the buffer of the resolution: a week for monthly and annual as for daily."""
    assert _kept(resolution, _WINDOW - 7 * _DAY, 7)
    assert not _kept(resolution, _WINDOW - 8 * _DAY, 7)
    # the default of a monthly or an annual index is gone with it
    assert not _kept(resolution, _WINDOW - 30 * _DAY, 7)
    # and a wider one keeps what the default of a daily would not
    assert _kept(resolution, _WINDOW - 300 * _DAY, 300)
    assert not _kept(resolution, _WINDOW - 301 * _DAY, 300)


def test_a_custom_buffer_can_be_narrower_than_the_default_of_the_resolution() -> None:
    """A narrower buffer drops what the default keeps; it is not a minimum."""
    assert _kept("annual", _WINDOW - 700 * _DAY, None)
    assert not _kept("annual", _WINDOW - 700 * _DAY, 30)
    assert _kept("monthly", _WINDOW - 60 * _DAY, None)
    assert not _kept("monthly", _WINDOW - 60 * _DAY, 0)


@pytest.mark.parametrize("buffer", [None, 0, 7, 3660])
@pytest.mark.parametrize("resolution", ["daily", "monthly", "annual"])
def test_a_bound_the_catalogue_does_not_publish_keeps_the_station(resolution: str, buffer: int | None) -> None:
    """A null end or start states nothing, so the station is kept, with every buffer."""
    assert _kept(resolution, None, buffer)
    assert _kept(resolution, None, buffer, starts=None)
    assert _kept(resolution, _WINDOW + _DAY, buffer, starts=None)
    assert _kept(resolution, None, buffer, starts=_WINDOW - 100 * _DAY)


@pytest.mark.parametrize("buffer", [None, 0, 7, 3660])
@pytest.mark.parametrize("resolution", ["daily", "monthly", "annual"])
def test_the_start_is_compared_exactly_and_no_buffer_reaches_it(resolution: str, buffer: int | None) -> None:
    """A station that started on the last instant of the window is in it, one a microsecond later is not."""
    assert _kept(resolution, None, buffer, starts=_WINDOW_END)
    assert not _kept(resolution, None, buffer, starts=_WINDOW_END + dt.timedelta(microseconds=1))
    assert not _kept(resolution, None, buffer, starts=_WINDOW_END + _DAY)
    # the catalogue starts at the first reading (DWD: 20098, 19856, 19912, ... first reading on `start_timestamp`)
    assert not _kept(resolution, None, buffer, starts=_WINDOW_END + 3 * _DAY)


def test_a_resolution_the_table_does_not_know_has_the_day_level_default() -> None:
    """A resolution that is no key of the table has the buffer of two days."""
    assert _kept("something_else", _WINDOW - 2 * _DAY, None)
    assert not _kept("something_else", _WINDOW - 3 * _DAY, None)


def test_without_a_window_the_list_is_left_as_it_is() -> None:
    """No `start` or no `end` is no filter, with or without a buffer."""
    df = _frame("daily", None, _WINDOW - 3000 * _DAY)

    for buffer in (None, 0, 7):
        assert limit_to_window(df, None, None, buffer).equals(df)
        assert limit_to_window(df, _WINDOW, None, buffer).equals(df)
        assert limit_to_window(df, None, _WINDOW_END, buffer).equals(df)


def test_the_rows_of_one_station_are_judged_by_their_own_resolution() -> None:
    """A station asked for two resolutions keeps the row whose record fits the window, with the buffer of that one."""
    end = _WINDOW - 40 * _DAY
    df = pl.concat([_frame("daily", None, end), _frame("monthly", None, end)])

    assert limit_to_window(df, _WINDOW, _WINDOW_END).get_column("resolution").to_list() == ["monthly"]
    assert limit_to_window(df, _WINDOW, _WINDOW_END, 0).is_empty()
    assert limit_to_window(df, _WINDOW, _WINDOW_END, 40).get_column("resolution").to_list() == ["daily", "monthly"]


# the option


def test_the_option_is_none_by_default_and_is_not_a_number_for_a_resolution() -> None:
    """Left out, the option is None, which is the buffer by resolution."""
    assert Options().station_window_end_buffer is None


@pytest.mark.parametrize("days", [0, 1, 732, 3660])
def test_the_option_takes_a_number_of_days_to_ten_years(days: int) -> None:
    """Zero is the exact end, and the bound is ten years."""
    assert Options(station_window_end_buffer=days).station_window_end_buffer == days


@pytest.mark.parametrize("days", [-1, 3661, 1.5, "a week", float("inf")])
def test_the_option_refuses_a_negative_a_fractional_or_an_unbounded_number(days: object) -> None:
    """A buffer below zero or past ten years, or not a whole number of days, is refused naming the option."""
    with pytest.raises(ValidationError, match="station_window_end_buffer"):
        Options(station_window_end_buffer=days)


def test_the_option_follows_the_environment_and_a_request_option_outranks_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_TS_STATION_WINDOW_END_BUFFER` sets it, and an option given replaces the variable."""
    monkeypatch.setenv("WD_TS_STATION_WINDOW_END_BUFFER", "9")

    assert Options().station_window_end_buffer == 9
    assert Options(station_window_end_buffer=0).station_window_end_buffer == 0
    assert Options().replace(station_window_end_buffer=None).station_window_end_buffer is None
    assert DwdObservationRequest(parameters="daily/kl", settings=Settings()).options.station_window_end_buffer == 9  # ty: ignore[unresolved-attribute]
    assert (
        DwdObservationRequest(
            parameters="daily/kl", options={"station_window_end_buffer": 3}
        ).options.station_window_end_buffer  # ty: ignore[unresolved-attribute]
        == 3
    )


def test_a_malformed_variable_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A variable out of range is told, not read as the default."""
    monkeypatch.setenv("WD_TS_STATION_WINDOW_END_BUFFER", "-5")

    with pytest.raises(ValidationError, match="station_window_end_buffer"):
        Options()


def test_the_option_round_trips_through_a_dump() -> None:
    """Dumped and built again, the options are the same ones."""
    options = Options(station_window_end_buffer=14)

    assert Options(**options.model_dump()) == options
    assert json.loads(options.model_dump_json())["station_window_end_buffer"] == 14


# Python and the surfaces

_NAME = "Teststadt"
_DATASETS = {
    "hourly": "temperature_air",
    "daily": "climate_summary",
    "monthly": "climate_summary",
    "annual": "climate_summary",
}

#: (resolution, days the catalogue's end is before the window, the buffer given, kept)
_CASES = [
    pytest.param("daily", 0, None, True, id="daily: ends on the window start"),
    pytest.param("daily", 2, None, True, id="daily: on the edge of the default"),
    pytest.param("daily", 3, None, False, id="daily: outside the default"),
    pytest.param("daily", 3, 3, True, id="daily: on the edge of a custom buffer"),
    pytest.param("daily", 4, 3, False, id="daily: outside a custom buffer"),
    pytest.param("daily", 1, 0, False, id="daily: buffer 0 is the exact end"),
    pytest.param("daily", 0, 0, True, id="daily: buffer 0, ends on the window start"),
    pytest.param("hourly", 2, None, True, id="hourly: on the edge of the default"),
    pytest.param("hourly", 3, None, False, id="hourly: outside the default"),
    pytest.param("monthly", 62, None, True, id="monthly: on the edge of the default"),
    pytest.param("monthly", 63, None, False, id="monthly: outside the default"),
    pytest.param("monthly", 62, 7, False, id="monthly: a custom buffer replaces the default"),
    pytest.param("monthly", 62, 62, True, id="monthly: a custom buffer on the edge"),
    pytest.param("annual", 732, None, True, id="annual: on the edge of the default"),
    pytest.param("annual", 733, None, False, id="annual: outside the default"),
    pytest.param("annual", 733, 733, True, id="annual: a wider custom buffer"),
    pytest.param("annual", 30, 0, False, id="annual: buffer 0"),
]


def _serve(monkeypatch: pytest.MonkeyPatch, resolution: str, ends: dt.datetime | None) -> list[str]:
    """Serve the catalogue of one station that ends as given, with a decoy that started after the window.

    Returns the parameters to ask for.
    """
    stations = pl.DataFrame(
        {
            "resolution": [resolution, resolution],
            "dataset": [_DATASETS[resolution]] * 2,
            "station_id": ["00001", "00002"],
            "start_timestamp": [dt.datetime(1990, 1, 1, tzinfo=_UTC), dt.datetime(2026, 10, 20, tzinfo=_UTC)],
            "end_timestamp": [ends, None],
            "latitude": [51.0, 51.0],
            "longitude": [13.0, 13.0],
            "elevation": [100.0, 100.0],
            "name": [_NAME, _NAME],
            "state": ["Sachsen", "Sachsen"],
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())
    return [f"{resolution}/{_DATASETS[resolution]}"]


def _python(parameters: list[str], buffer: int | None) -> list[str]:
    options = {} if buffer is None else {"station_window_end_buffer": buffer}
    request = DwdObservationRequest(
        parameters=parameters, start="2026-10-16", end="2026-10-16", options=options, settings=Settings()
    )
    return request.filter_by_name(_NAME, rank=5).df.get_column("station_id").unique(maintain_order=True).to_list()


def _selection(parameters: list[str]) -> dict[str, str]:
    return {"provider": "dwd", "network": "observation", "parameters": parameters[0]}


def _rest(parameters: list[str], buffer: int | None, selection: dict[str, str]) -> list[str]:
    params = {**_selection(parameters), **selection, "timestamp": "2026-10-16"}
    if buffer is not None:
        params["station_window_end_buffer"] = str(buffer)
    response = TestClient(app).get("/api/stations", params=params)
    assert response.status_code == 200, response.text
    return [station["station_id"] for station in response.json()["stations"]]


def _cli(parameters: list[str], buffer: int | None, selection: list[str]) -> list[str]:
    arguments = [f"--{key}={value}" for key, value in _selection(parameters).items()]
    arguments += [*selection, "--timestamp=2026-10-16"]
    if buffer is not None:
        arguments.append(f"--station-window-end-buffer={buffer}")
    result = CliRunner().invoke(cli, ["stations", *arguments])
    assert result.exit_code == 0, result.output
    return [station["station_id"] for station in json.loads(result.stdout)["stations"]]


def _mcp(parameters: list[str], buffer: int | None, selection: dict[str, Any]) -> list[str]:
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    arguments = {**_selection(parameters), **selection, "timestamp": "2026-10-16"}
    if buffer is not None:
        arguments["station_window_end_buffer"] = buffer

    async def call() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            result = await client.call_tool("stations", arguments)
            answer = result.structured_content
            assert answer is not None
            return answer.get("result", answer)

    return [station["station_id"] for station in asyncio.run(call())["stations"]]


@pytest.mark.parametrize(("resolution", "days", "buffer", "kept"), _CASES)
def test_python_and_every_surface_keep_the_same_stations(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    days: int,
    buffer: int | None,
    kept: bool,  # noqa: FBT001
) -> None:
    """`filter_by_name`, REST, the command line and MCP list a station for a name by one rule and one buffer.

    The decoy that starts after the window is in none of them.
    """
    pytest.importorskip("fastmcp")
    parameters = _serve(monkeypatch, resolution, _WINDOW - days * _DAY)
    expected = ["00001"] if kept else []

    assert _python(parameters, buffer) == expected
    assert _rest(parameters, buffer, {"name": _NAME}) == expected
    assert _cli(parameters, buffer, [f"--name={_NAME}"]) == expected
    assert _mcp(parameters, buffer, {"name": _NAME}) == expected


@pytest.mark.parametrize(("resolution", "days", "buffer", "kept"), _CASES)
def test_a_listing_of_all_stations_applies_the_same_buffer(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    days: int,
    buffer: int | None,
    kept: bool,  # noqa: FBT001
) -> None:
    """The listing of every station is cut by the rule that a name is matched with, over REST and the command line."""
    parameters = _serve(monkeypatch, resolution, _WINDOW - days * _DAY)
    expected = ["00001"] if kept else []

    assert _rest(parameters, buffer, {"all": "true"}) == expected
    assert _cli(parameters, buffer, ["--all"]) == expected


def test_the_environment_sets_the_buffer_of_python_and_the_surfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_TS_STATION_WINDOW_END_BUFFER` is the buffer where none is given, and a given one outranks it."""
    parameters = _serve(monkeypatch, "daily", _WINDOW - 10 * _DAY)
    assert _python(parameters, None) == []

    monkeypatch.setenv("WD_TS_STATION_WINDOW_END_BUFFER", "10")

    assert _python(parameters, None) == ["00001"]
    assert _rest(parameters, None, {"name": _NAME}) == ["00001"]
    assert _cli(parameters, None, [f"--name={_NAME}"]) == ["00001"]
    assert _mcp_or_skip(parameters, None) == ["00001"]
    # a request's own buffer replaces the variable, as every option does
    assert _python(parameters, 0) == []
    assert _rest(parameters, 0, {"name": _NAME}) == []
    assert _cli(parameters, 0, [f"--name={_NAME}"]) == []


def _mcp_or_skip(parameters: list[str], buffer: int | None) -> list[str]:
    pytest.importorskip("fastmcp")
    return _mcp(parameters, buffer, {"name": _NAME})


def test_values_by_name_use_the_buffer_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `values` request names its station by the same rule: the buffer that keeps it in a listing keeps it here."""
    from wetterdienst.ui import core  # noqa: PLC0415

    parameters = _serve(monkeypatch, "daily", _WINDOW - 10 * _DAY)
    request = core.ValuesRequest(
        provider="dwd",
        network="observation",
        parameters=parameters[0],
        name=_NAME,
        timestamp="2026-10-16",
        station_window_end_buffer=10,
    )
    options = Options(station_window_end_buffer=request.station_window_end_buffer)
    api = DwdObservationRequest

    kept = core.get_stations(api, request, request.timestamp, Settings(), options).df
    dropped = core.get_stations(api, request, request.timestamp, Settings(), Options()).df

    assert kept.get_column("station_id").to_list() == ["00001"]
    assert dropped.is_empty()


@pytest.mark.parametrize("value", ["-1", "3661", "1.5", "week"])
def test_every_surface_refuses_a_buffer_out_of_range(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """A buffer that is no whole number of days from 0 to 3660 is the request's error, not a station list."""
    parameters = _serve(monkeypatch, "daily", _WINDOW)

    response = TestClient(app).get(
        "/api/stations",
        params={**_selection(parameters), "all": "true", "timestamp": "2026-10-16", "station_window_end_buffer": value},
    )
    assert response.status_code == 422, response.text
    assert "station_window_end_buffer" in response.text

    result = CliRunner().invoke(
        cli,
        [
            "stations",
            *(f"--{key}={val}" for key, val in _selection(parameters).items()),
            "--all",
            "--timestamp=2026-10-16",
            f"--station-window-end-buffer={value}",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "station-window-end-buffer" in result.output


def test_a_malformed_server_variable_is_the_servers_error_and_not_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """The variable is read where the options are built, so a bad one is told by its name."""
    parameters = _serve(monkeypatch, "daily", _WINDOW)
    monkeypatch.setenv("WD_TS_STATION_WINDOW_END_BUFFER", "-5")

    result = CliRunner().invoke(
        cli,
        ["stations", *(f"--{key}={val}" for key, val in _selection(parameters).items()), "--all"],
    )

    assert result.exit_code != 0
    assert "STATION_WINDOW_END_BUFFER" in result.output.upper() or "station_window_end_buffer" in result.output


def test_the_other_selections_of_python_are_not_windowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only `filter_by_name` applies the window to the frame it returns: rank, distance and bbox keep their results."""
    parameters = _serve(monkeypatch, "daily", _WINDOW - 400 * _DAY)
    request = DwdObservationRequest(
        parameters=parameters, start="2026-10-16", end="2026-10-16", options={"station_window_end_buffer": 0}
    )

    assert request.all().df.height == 2
    assert request.filter_by_station_id(["00001"]).df.height == 1
    assert request.filter_by_rank(latlon=(51.0, 13.0), rank=2).df.height == 2
    assert request.filter_by_distance(latlon=(51.0, 13.0), distance=10).df.height == 2
    assert request.filter_by_bbox(left=12.0, bottom=50.0, right=14.0, top=52.0).df.height == 2
    assert request.filter_by_name(_NAME, rank=5).df.is_empty()
