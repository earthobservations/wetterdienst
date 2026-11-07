# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An estimate tells, once, that source data was left out of it, with the cause and how many stations (GH-3848).

`interpolate` and `summarize` read the stations around a point as candidates and collect with the per-station warnings
off, so a file the provider let go (`file-skipped`) and the dates of another series it left out
(`other-window-left-out`) never reached the answer. They are told now as one `source-data-left-out` warning for the
answer, and never of each station.

Nothing here reaches the network: Frost and DWD are served from stubs, as the tests of their readers do.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from tests.provider.metno.frost.test_values_failures import (
    SOURCES,
    _answered_by,
    _offset_answer,
    _ok,
)
from tests.ui.test_empty_listing import dwd  # noqa: F401
from wetterdienst import Settings
from wetterdienst.model.parameter_rows import MAX_STATIONS_LISTED, EstimateLeftOut
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.response_warnings import (
    SOURCE_DATA_LEFT_OUT,
    begin_response,
    note_left_out,
    note_skipped_download,
    recorded_warnings,
)

if TYPE_CHECKING:
    from tests.ui.test_empty_listing import _Dwd
    from wetterdienst.util.network import File

UTC = dt.UTC
ESTIMATES = ["summarize", "interpolate"]

# --- Frost: the dates only the 18-18 UTC series has (`other-window-left-out`) ---------------------------------------

_FROST = "daily/data/precipitation_amount"
_FROST_NAME = "daily/data/precipitation_amount"
_FROST_POINT = (59.95, 10.73)
_STAMPS = ["2020-01-01T00:00:00.000Z", "2020-01-02T00:00:00.000Z", "2020-01-03T00:00:00.000Z"]


@pytest.fixture
def frost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve Oslo/Blindern, whose 06-06 UTC precipitation sum has the first date and the 18-18 UTC one all three."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")
    monkeypatch.setenv("WD_CACHE_DISABLE", "1")
    readings = [
        (_STAMPS[0], "PT18H", 4.0),
        (_STAMPS[0], "PT6H", 22.3),
        (_STAMPS[1], "PT18H", 7.0),
        (_STAMPS[2], "PT18H", 8.0),
    ]
    available = {
        "data": [
            {
                "validFrom": "1940-01-01T00:00:00Z",
                "timeOffset": offset,
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0"
                f"&timeoffsets={offset}",
            }
            for offset in ("PT18H", "PT6H")
        ]
    }
    observations = _answered_by("batch", _offset_answer("sum(precipitation_amount P1D)", readings), available)

    def download(*, url: str, **_: object) -> File:
        return _ok(url, SOURCES) if "/sources/" in url else observations(url)

    monkeypatch.setattr(frost_api, "download_file", download)
    monkeypatch.setattr(frost_api, "read_refusal", lambda *_args, **_kwargs: None)


def _frost_request() -> MetnoFrostRequest:
    return MetnoFrostRequest(
        parameters=[("daily", "data", "precipitation_amount")],
        start=dt.datetime(2020, 1, 1, tzinfo=UTC),
        end=dt.datetime(2020, 1, 3, tzinfo=UTC),
        settings=Settings(cache_disable=True),
    )


def _codes() -> list[str]:
    return [warning["code"] for warning in recorded_warnings()]


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_an_estimate_tells_the_dates_of_another_series_it_left_out(frost: None, estimate: str) -> None:  # noqa: ARG001
    """Two of the three dates are of the 18-18 UTC series only: one warning, with the cause, the station, the dates."""
    begin_response()

    getattr(_frost_request(), estimate)(_FROST_POINT)

    (warning,) = recorded_warnings()
    assert warning["code"] == SOURCE_DATA_LEFT_OUT
    assert warning["stations"] == ["SN18700"]
    assert "Source data was left out of this estimate at 1 of the 1 stations it read." in warning["message"]
    assert (
        f"Dates of another series of the source were left out at 1 station (SN18700): 2 of {_FROST_NAME}."
        in (warning["message"])
    )
    # the per-station warnings stay off for the estimate, and the source has values: no parameter is "without rows"
    assert not {"other-window-left-out", "file-skipped", "parameter-without-rows"} & set(_codes())


def test_an_estimate_logs_the_summary_warning_in_python(frost: None, caplog: pytest.LogCaptureFixture) -> None:  # noqa: ARG001
    """Without a response being built the warning is a log line at WARNING, as every response warning is."""
    with caplog.at_level(logging.WARNING):
        _frost_request().summarize(_FROST_POINT)

    assert [record.response_warning for record in caplog.records if hasattr(record, "response_warning")] == [
        SOURCE_DATA_LEFT_OUT
    ]


def test_a_values_request_still_tells_the_dates_by_its_own_code(frost: None) -> None:  # noqa: ARG001
    """The stations a request names are told by `other-window-left-out`, as before: this changes the estimates only."""
    begin_response()

    _frost_request().filter_by_station_id("SN18700").values().all()

    assert _codes() == ["other-window-left-out"]


def _surfaces() -> dict[str, list[dict[str, Any]]]:
    """Make the same summary on the library, the command line, REST and the MCP tool, and give the warnings of each."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    begin_response()
    _frost_request().summarize(_FROST_POINT)
    library = recorded_warnings()
    arguments = {
        "provider": "metno",
        "network": "frost",
        "parameters": _FROST,
        "latitude": str(_FROST_POINT[0]),
        "longitude": str(_FROST_POINT[1]),
        "timestamp": "2020-01-01/2020-01-03",
    }
    result = CliRunner().invoke(
        cli,
        ["summarize", *(f"--{key}={value}" for key, value in arguments.items()), "--with-metadata=true"],
    )
    assert result.exit_code == 0, result.output
    rest = TestClient(restapi.app, raise_server_exceptions=False).get("/api/summarize", params=arguments)
    assert rest.status_code == 200, rest.text

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as client:
            return (await client.call_tool("summarize", arguments)).structured_content

    answer = asyncio.run(call())
    return {
        "library": library,
        "cli": json.loads(result.stdout)["metadata"]["warnings"],
        "rest": rest.json()["metadata"]["warnings"],
        "mcp": answer.get("result", answer)["metadata"]["warnings"],
        "header": [{"code": code} for code in rest.headers["X-Wetterdienst-Warnings"].split(", ")],
    }


def test_the_summary_warning_is_told_alike_on_every_surface(frost: None) -> None:  # noqa: ARG001
    """The library, the command line, REST and the MCP tool carry the same warning once; REST names it in a header."""
    told = _surfaces()

    (warning,) = told["rest"]
    assert warning["code"] == SOURCE_DATA_LEFT_OUT
    assert warning["stations"] == ["SN18700"]
    assert told["cli"] == told["rest"] == told["mcp"] == told["library"]
    assert told["header"] == [{"code": SOURCE_DATA_LEFT_OUT}]


# --- DWD: a file let go, and a directory found empty (`file-skipped`) -----------------------------------------------

_MONTHLY = "monthly/climate_summary/temperature_air_mean_2m"
_MONTHLY_HISTORICAL = "climate/monthly/kl/historical/"
_STATIONS = ["00044", "00045", "00046", "00047", "00048"]
_DWD_POINT = (52.93, 8.23)


def _serving_three_months(monkeypatch: pytest.MonkeyPatch) -> None:
    """Have every station answer three monthly readings of 2026, after the reader has walked its files.

    The reader is called as it is (it meets the empty directory and says so to the walk), and what the other period
    holds is stood for by the frame: the station is left with the readings of the files that were there.
    """
    original = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001

    def collect(self: DwdObservationValues, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401
        original(self, station_id, parameter_or_dataset)
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        name = next(parameter.name_original for parameter in dataset if parameter.name == "temperature_air_mean_2m")
        stamps = [dt.datetime(2026, month, 1, tzinfo=UTC) for month in (1, 2, 3)]
        return pl.DataFrame(
            {
                "timestamp": stamps,
                "parameter": [name] * 3,
                "value": [10.0, 11.0, 12.0],
                "quality_flags": ["1"] * 3,
                "resolution": ["monthly"] * 3,
                "dataset": [dataset.name] * 3,
            }
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _dwd_request() -> DwdObservationRequest:
    return DwdObservationRequest(
        parameters=[_MONTHLY], start="2026-01-01", end="2026-03-01", settings=Settings(cache_disable=True)
    )


def _summary() -> list[dict[str, Any]]:
    return [warning for warning in recorded_warnings() if warning["code"] == SOURCE_DATA_LEFT_OUT]


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_an_estimate_tells_a_directory_found_empty(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    estimate: str,
) -> None:
    """The `historical` directory is empty: the lookup tells the directory, and the walk, now, the station."""
    _serving_three_months(monkeypatch)
    dwd.local = Settings(cache_disable=True)
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    begin_response()

    result = getattr(_dwd_request(), estimate)(_DWD_POINT)

    assert result.df.get_column("value").drop_nulls().to_list() == [10.0, 11.0, 12.0]
    (warning,) = _summary()
    assert warning["stations"] == ["00044"]
    assert "Source data was left out of this estimate at 1 of the 1 stations it read." in warning["message"]
    assert "a directory found empty) was left out at 1 station (00044)" in warning["message"]
    assert "Try again later." in warning["message"]
    # the lookup's warning names the directory and stays; the station is told by the summary and no `file-skipped`
    skipped = [w for w in recorded_warnings() if w["code"] == "file-skipped"]
    assert [("stations" in w, _MONTHLY_HISTORICAL in w["message"]) for w in skipped] == [(False, True)]


def test_an_estimate_that_lost_a_directory_over_rest_carries_the_warning_once(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REST answers a 200 with the summary in `metadata.warnings` and its code in the header."""
    _serving_three_months(monkeypatch)
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    dwd.local = Settings(cache_disable=True)

    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/v1/summarize",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": _MONTHLY,
            "latitude": str(_DWD_POINT[0]),
            "longitude": str(_DWD_POINT[1]),
            "timestamp": "2026-01-01/2026-03-01",
        },
    )

    assert response.status_code == 200, response.text
    warnings = response.json()["metadata"]["warnings"]
    assert [w["code"] for w in warnings].count(SOURCE_DATA_LEFT_OUT) == 1
    assert "source-data-left-out" in response.headers["X-Wetterdienst-Warnings"]


def test_an_interpolation_over_many_stations_that_lost_a_file_tells_it_once(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Five stations of one place, never four that surround it: the walk reads them all, and the answer says it once."""
    dwd.stations = _STATIONS
    dwd.server.default = [
        *(f"stundenwerte_KL_{station}_19700101_20241231_hist.zip" for station in _STATIONS),
        "KL_Beschreibung_Stationen.txt",
    ]
    _serving_three_months(monkeypatch)
    dwd.local = Settings(cache_disable=True)
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    begin_response()

    _dwd_request().interpolate(_DWD_POINT)

    (warning,) = _summary()
    assert warning["stations"] == _STATIONS
    assert f"at {len(_STATIONS)} of the {len(_STATIONS)} stations it read." in warning["message"]
    assert f"left out at {len(_STATIONS)} stations ({', '.join(_STATIONS)})" in warning["message"]
    # the lookup's `file-skipped` names the directory and no station, as before
    assert ["stations" in w for w in recorded_warnings() if w["code"] == "file-skipped"] == [False]


def test_an_estimate_with_nothing_left_out_has_no_summary(dwd: _Dwd, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """No empty directory, no file let go: the answer carries no `source-data-left-out`."""
    _serving_three_months(monkeypatch)
    dwd.local = Settings(cache_disable=True)
    begin_response()

    _dwd_request().summarize(_DWD_POINT)

    assert _summary() == []


# --- the tally on its own: what the warning says, and that it is one ------------------------------------------------


def _walk(
    *, skipped: tuple[str, ...] = (), dates: dict[str, int] | None = None, read: tuple[str, ...] = ()
) -> EstimateLeftOut:
    """Read the stations `read` (and those named in `skipped` and `dates`), as the walk of an estimate tells it."""
    left_out = EstimateLeftOut()
    from wetterdienst.model.parameter_rows import ParameterRows  # noqa: PLC0415

    request = _dwd_request()
    rows = ParameterRows(request, None, None, enabled=False, left_out=left_out)
    for station in dict.fromkeys([*read, *skipped, *(dates or {})]):
        with rows.collecting(station):
            if station in skipped:
                note_skipped_download()
            if dates and station in dates:
                note_left_out(_FROST_NAME, dates[station], "these dates are of another series")
    return left_out


def test_both_causes_are_one_warning_that_counts_the_stations_of_each() -> None:
    """A station with both causes is one of the stations the warning counts, and each cause names its own."""
    left_out = _walk(skipped=("A", "B"), dates={"B": 3, "C": 4}, read=("A", "B", "C", "D", "E"))
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["code"] == SOURCE_DATA_LEFT_OUT
    assert warning["stations"] == ["A", "B", "C"]
    message = warning["message"]
    assert "at 3 of the 5 stations it read." in message
    assert f"left out at 2 stations (B, C): 7 of {_FROST_NAME}." in message
    assert "left out at 2 stations (A, B): the values of these stations may be missing" in message


def test_the_listing_of_stations_is_capped_and_the_count_is_whole() -> None:
    """A walk over many stations lists the first ten and counts them all, in one warning."""
    stations = tuple(f"{number:05d}" for number in range(1, 26))
    left_out = _walk(skipped=stations)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == list(stations[:MAX_STATIONS_LISTED])
    assert "at 25 of the 25 stations it read." in warning["message"]
    assert "25 stations (the first 10 of them 00001, " in warning["message"]


def test_a_file_that_serves_every_station_is_every_stations() -> None:
    """A file all stations are read from (`whole_request`) is let go for each station the walk read."""
    left_out = EstimateLeftOut()
    for station in ("A", "B", "C"):
        left_out.collected(station)
    left_out.skipped("A", whole_request=True)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A", "B", "C"]
    assert "at 3 of the 3 stations it read." in warning["message"]


def test_nothing_left_out_is_no_warning() -> None:
    """Stations read, none of which lost anything, say nothing."""
    left_out = _walk(read=("A", "B"))
    begin_response()

    left_out.warn()

    assert recorded_warnings() == []
