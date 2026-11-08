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
import io
import json
import logging
import math
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from tests.provider.metno.frost.catalogue_rows import is_series_listing, series_of
from tests.provider.metno.frost.test_values_failures import (
    SOURCES,
    _answered_by,
    _offset_answer,
    _ok,
)
from tests.ui.test_empty_listing import _DESCRIPTION, dwd  # noqa: F401
from wetterdienst import Settings
from wetterdienst.model.parameter_rows import MAX_STATIONS_LISTED, EstimateLeftOut
from wetterdienst.provider.dwd.observation import DwdObservationRequest, metaindex
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import (
    SOURCE_DATA_LEFT_OUT,
    SkipCause,
    advise_on_skip_causes,
    begin_response,
    note_left_out,
    note_skipped_download,
    recorded_warnings,
    tell_skip_causes,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.ui.test_empty_listing import _Dwd

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
        # the catalogue's request for the series of every station is served as the reader's own tests serve it
        if is_series_listing(url):
            return _ok(url, series_of("SN18700"))
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


def _surfaces(
    make: Callable[[], object], arguments: dict[str, str], estimate: str = "summarize"
) -> dict[str, list[dict[str, Any]]]:
    """Make the same estimate on the library, the command line, REST and the MCP tool, and give the warnings of each.

    `make` is the library's call, `arguments` the same request for the other three.
    """
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    begin_response()
    make()
    library = recorded_warnings()
    result = CliRunner().invoke(
        cli,
        [estimate, *(f"--{key}={value}" for key, value in arguments.items()), "--with-metadata=true"],
    )
    assert result.exit_code == 0, result.output
    rest = TestClient(restapi.app, raise_server_exceptions=False).get(f"/api/{estimate}", params=arguments)
    assert rest.status_code == 200, rest.text

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as client:
            return (await client.call_tool(estimate, arguments)).structured_content

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
    told = _surfaces(
        lambda: _frost_request().summarize(_FROST_POINT),
        {
            "provider": "metno",
            "network": "frost",
            "parameters": _FROST,
            "latitude": str(_FROST_POINT[0]),
            "longitude": str(_FROST_POINT[1]),
            "timestamp": "2020-01-01/2020-01-03",
        },
    )

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
    assert "was left out at 1 station (00044): the directory was found empty." in warning["message"]
    assert warning["message"].endswith("Try again later.")
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


# --- the station the walk stops at is read and not used (GH-3848) ----------------------------------------------------

_TWELVE = [f"{number:05d}" for number in range(44, 56)]


def _serving_stations(
    monkeypatch: pytest.MonkeyPatch,
    *,
    losing: set[str] = frozenset(),
    rejecting: set[str] = frozenset(),
    without_rows: set[str] = frozenset(),
) -> list[str]:
    """Have each station answer three monthly readings, give the stations read in order.

    A station in `losing` lets a file go on the way; one in `rejecting` reads 1000 degrees for the first month, which
    the range check (hard by default) makes null; one in `without_rows` answers no row at all, as a station does whose
    file was lost, and the walk passes it over.
    """
    read: list[str] = []

    def collect(self: DwdObservationValues, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        read.append(station_id)
        if station_id in losing:
            note_skipped_download(SkipCause.FAILED)
        if station_id in without_rows:
            return pl.DataFrame()
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        name = next(parameter.name_original for parameter in dataset if parameter.name == "temperature_air_mean_2m")
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(2026, month, 1, tzinfo=UTC) for month in (1, 2, 3)],
                "parameter": [name] * 3,
                "value": [1000.0 if station_id in rejecting else 10.0, 11.0, 12.0],
                "quality_flags": ["1"] * 3,
                "resolution": ["monthly"] * 3,
                "dataset": [dataset.name] * 3,
            }
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    return read


def _twelve_stations(dwd: _Dwd, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """List twelve stations around the point, nearest first, so that an estimate stops before the last of them.

    They lie on a spiral of eight directions at growing distances: four of the nearest surround the point, which an
    interpolation needs to be done, and a summary is done with the first.
    """
    dwd.stations = _TWELVE
    dwd.server.default = [
        *(f"stundenwerte_KL_{station}_19700101_20241231_hist.zip" for station in _TWELVE),
        "KL_Beschreibung_Stationen.txt",
    ]
    dwd.local = Settings(cache_disable=True)
    header, rule, row = _DESCRIPTION.split("\r\n")[:3]
    rows = []
    for index, station in enumerate(_TWELVE):
        angle = index * math.pi / 4
        distance = 0.02 * (index + 1)
        latitude, longitude = _DWD_POINT[0] + distance * math.sin(angle), _DWD_POINT[1] + distance * math.cos(angle)
        rows.append(
            row.replace("00044", station).replace("52.9336", f"{latitude:.4f}").replace("8.2370", f"{longitude:.4f}")
        )
    description = "\r\n".join([header, rule, *rows, ""]).encode("latin-1")
    monkeypatch.setattr(
        metaindex, "download_file", lambda url, **_: File(url=url, content=io.BytesIO(description), status=200)
    )


@pytest.mark.parametrize("cause", ["file", "rejected"])
@pytest.mark.parametrize("estimate", ESTIMATES)
def test_the_station_the_walk_stops_at_is_not_counted(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    estimate: str,
    cause: str,
) -> None:
    """An estimate reads one station more than it uses to find that it is done; what that one lost is no loss.

    The warning said "at 1 of the 9 stations it read (00052)" for a summary of twelve stations in one place, of
    which the answer was made from the first.
    """
    _twelve_stations(dwd, monkeypatch)
    clean = _serving_stations(monkeypatch)
    getattr(_dwd_request(), estimate)(_DWD_POINT)
    last = clean[-1]
    assert last != _TWELVE[-1], "the walk read every station: there is no station it stopped at"

    _serving_stations(
        monkeypatch, losing={last} if cause == "file" else set(), rejecting={last} if cause == "rejected" else set()
    )
    begin_response()
    result = getattr(_dwd_request(), estimate)(_DWD_POINT)

    taken = result.df.get_column("taken_station_id" if estimate == "summarize" else "taken_station_ids")
    assert last not in {*taken.explode().to_list()} if estimate == "interpolate" else last not in taken.to_list()
    assert _summary() == []


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_a_station_passed_over_after_the_walk_was_done_is_not_counted(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    estimate: str,
) -> None:
    """The station the clean walk stops at loses its file and has no row: it is passed over, and the next one stops it.

    The walk never hands such a station to the estimate, so it is not the station it breaks on, yet the answer is the
    clean one and the station could not have changed it.
    """
    _twelve_stations(dwd, monkeypatch)
    clean = _serving_stations(monkeypatch)
    begin_response()
    clean_df = getattr(_dwd_request(), estimate)(_DWD_POINT).df
    last = clean[-1]
    assert last != _TWELVE[-1], "the walk read every station: there is no station it stopped at"

    read = _serving_stations(monkeypatch, losing={last}, without_rows={last})
    begin_response()
    df = getattr(_dwd_request(), estimate)(_DWD_POINT).df

    assert read[: len(clean)] == clean
    assert len(read) == len(clean) + 1, "the walk read one more station to stop"
    assert df.equals(clean_df)
    assert _summary() == []


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_a_station_passed_over_after_the_last_used_one_is_not_counted_where_the_walk_runs_out(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    estimate: str,
) -> None:
    """Every station after the last one the answer is made of loses its file: the walk ends and none is counted."""
    _twelve_stations(dwd, monkeypatch)
    clean = _serving_stations(monkeypatch)
    begin_response()
    clean_df = getattr(_dwd_request(), estimate)(_DWD_POINT).df
    rest = set(_TWELVE) - set(clean[:-1])
    assert rest, "the answer is made of every station but the one it stopped at"

    read = _serving_stations(monkeypatch, losing=rest, without_rows=rest)
    begin_response()
    df = getattr(_dwd_request(), estimate)(_DWD_POINT).df

    assert sorted(read) == _TWELVE, "the walk ran out of stations"
    assert df.equals(clean_df)
    assert _summary() == []


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_a_station_passed_over_before_the_walk_was_done_stays_counted(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    estimate: str,
) -> None:
    """The first station loses its file and has no row: the answer was not complete, and it may have completed it."""
    _twelve_stations(dwd, monkeypatch)
    clean = _serving_stations(monkeypatch)
    getattr(_dwd_request(), estimate)(_DWD_POINT)
    first = clean[0]

    read = _serving_stations(monkeypatch, losing={first}, without_rows={first})
    begin_response()
    getattr(_dwd_request(), estimate)(_DWD_POINT)

    (warning,) = _summary()
    assert warning["stations"] == [first]
    # the station the walk stopped at is not one of the stations read
    assert f"at 1 of the {len(read) - 1} stations it read." in warning["message"]


def test_an_interpolation_that_never_had_four_stations_around_the_point_was_never_done(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Twelve stations at one place surround nothing: the walk reads them all, and a lost file of the last counts.

    The stations of the parameter are enough, but no four of them surround the point, which the walk is not done
    without, so a station without rows at its end was not read after the answer was complete.
    """
    dwd.stations = _TWELVE
    dwd.server.default = [
        *(f"stundenwerte_KL_{station}_19700101_20241231_hist.zip" for station in _TWELVE),
        "KL_Beschreibung_Stationen.txt",
    ]
    dwd.local = Settings(cache_disable=True)
    read = _serving_stations(monkeypatch)
    _dwd_request().interpolate(_DWD_POINT)
    assert sorted(read) == _TWELVE, "the walk stopped: four stations surround the point"
    last = read[-1]

    _serving_stations(monkeypatch, losing={last}, without_rows={last})
    begin_response()
    _dwd_request().interpolate(_DWD_POINT)

    (warning,) = _summary()
    assert warning["stations"] == [last]
    assert "at 1 of the 12 stations it read." in warning["message"]


def test_a_station_the_walk_used_is_counted_and_the_one_it_stopped_at_is_not(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first station loses a file and the answer is made from it: the count is of the stations before the last."""
    _twelve_stations(dwd, monkeypatch)
    clean = _serving_stations(monkeypatch)
    _dwd_request().summarize(_DWD_POINT)
    first, last = clean[0], clean[-1]

    _serving_stations(monkeypatch, losing={first, last})
    begin_response()
    _dwd_request().summarize(_DWD_POINT)

    (warning,) = _summary()
    assert warning["stations"] == [first]
    assert f"at 1 of the {len(clean) - 1} stations it read." in warning["message"]


# --- values a hard plausibility check rejected are a cause too (GH-3848) ---------------------------------------------


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_an_estimate_tells_the_values_a_plausibility_check_rejected(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    estimate: str,
) -> None:
    """Three stations read 1000 degrees in one month, which the range check nulls: told once, with the check."""
    _twelve_stations(dwd, monkeypatch)
    rejecting = set(_TWELVE[:3])
    _serving_stations(monkeypatch, rejecting=rejecting)
    begin_response()

    getattr(_dwd_request(), estimate)(_DWD_POINT)

    (warning,) = _summary()
    assert set(warning["stations"]) == rejecting
    assert "3 values at 3 stations (" in warning["message"]
    assert "were numbers a plausibility check rejected (range 3;" in warning["message"]
    assert "and are not used." in warning["message"]
    # the markers and the counts of a values request are no part of an estimate
    assert not {"rejected-by-plausibility", "missing-value-marker"} & set(_codes())


def test_a_soft_check_the_estimate_leaves_out_itself_is_not_counted(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A value a soft check flags `suspect:` is left out by the estimate in any mode, and is no value rejected."""
    _twelve_stations(dwd, monkeypatch)
    _serving_stations(monkeypatch, rejecting={_TWELVE[0]})
    begin_response()

    DwdObservationRequest(
        parameters=[_MONTHLY],
        start="2026-01-01",
        end="2026-03-01",
        settings=Settings(cache_disable=True),
        options={"plausibility": {"range": "soft"}},
    ).summarize(_DWD_POINT)

    assert _summary() == []


def test_the_rejected_values_are_told_alike_on_every_surface(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The library, the command line, REST and the MCP tool carry the one warning, REST names it in its header."""
    _twelve_stations(dwd, monkeypatch)
    _serving_stations(monkeypatch, rejecting={_TWELVE[0]})

    told = _surfaces(
        lambda: _dwd_request().summarize(_DWD_POINT),
        {
            "provider": "dwd",
            "network": "observation",
            "parameters": _MONTHLY,
            "latitude": str(_DWD_POINT[0]),
            "longitude": str(_DWD_POINT[1]),
            "timestamp": "2026-01-01/2026-03-01",
        },
    )

    (warning,) = [w for w in told["rest"] if w["code"] == SOURCE_DATA_LEFT_OUT]
    assert warning["stations"] == [_TWELVE[0]]
    assert "1 values at 1 station (00044) were numbers a plausibility check rejected (range 1;" in warning["message"]
    assert [w for w in told["cli"] if w["code"] == SOURCE_DATA_LEFT_OUT] == [warning]
    assert [w for w in told["mcp"] if w["code"] == SOURCE_DATA_LEFT_OUT] == [warning]
    assert [w for w in told["library"] if w["code"] == SOURCE_DATA_LEFT_OUT] == [warning]
    assert SOURCE_DATA_LEFT_OUT in [w["code"] for w in told["header"]]


# --- the tally on its own: what the warning says, and that it is one ------------------------------------------------


def _walk(
    *,
    skipped: tuple[str, ...] = (),
    dates: dict[str, int] | None = None,
    read: tuple[str, ...] = (),
    cause: SkipCause = SkipCause.FAILED,
) -> EstimateLeftOut:
    """Read the stations `read` (and those named in `skipped` and `dates`), as the walk of an estimate tells it.

    The provider lets the file of each station of `skipped` go for `cause`.
    """
    left_out = EstimateLeftOut()
    from wetterdienst.model.parameter_rows import ParameterRows  # noqa: PLC0415

    request = _dwd_request()
    rows = ParameterRows(request, None, None, enabled=False, left_out=left_out)
    for station in dict.fromkeys([*read, *skipped, *(dates or {})]):
        with rows.collecting(station):
            if station in skipped:
                note_skipped_download(cause)
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
    assert "left out at 2 stations (A, B): the download failed. The values of these stations may be missing" in message


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
    left_out.skipped("A", SkipCause.FAILED, whole_request=True)
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


def test_forget_leaves_a_station_out_of_every_cause() -> None:
    """The station the walk stops at is out of the count, the lists and the sums, and a parameter left empty is gone."""
    left_out = EstimateLeftOut()
    for station in ("A", "B", "C"):
        left_out.collected(station)
    left_out.skipped("C", SkipCause.FAILED, whole_request=False)
    left_out.left_out("C", _FROST_NAME, 4)
    left_out.left_out("A", "daily/data/other", 1)
    left_out.left_out("C", "daily/data/other", 2)
    left_out.rejected("C", 2, {"range": 2})
    begin_response()

    left_out.forget("C")
    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A"]
    assert "at 1 of the 2 stations it read." in warning["message"]
    assert "1 of daily/data/other" in warning["message"]
    assert _FROST_NAME not in warning["message"]
    assert "rejected" not in warning["message"]
    assert "file the provider" not in warning["message"]


def test_forget_of_the_only_station_of_a_cause_leaves_no_warning() -> None:
    """Every cause of the station was the one the walk stopped at: nothing was left out of the answer."""
    left_out = EstimateLeftOut()
    left_out.collected("A")
    left_out.collected("B")
    left_out.left_out("B", _FROST_NAME, 4)
    left_out.rejected("B", 1, {"range": 1})
    left_out.skipped("B", SkipCause.FAILED, whole_request=False)
    begin_response()

    left_out.forget("B")
    left_out.warn()

    assert recorded_warnings() == []


def test_forget_undoes_a_file_that_serves_every_station_only_where_that_station_let_it_go() -> None:
    """A file all stations are read from, let go while the stop station was read, is not every station's after it."""
    left_out = EstimateLeftOut()
    for station in ("A", "B"):
        left_out.collected(station)
    left_out.skipped("B", SkipCause.FAILED, whole_request=True)
    begin_response()
    left_out.forget("B")
    left_out.warn()
    assert recorded_warnings() == []

    # the station before it let the same file go: it stays every station's
    left_out = EstimateLeftOut()
    for station in ("A", "B"):
        left_out.collected(station)
    left_out.skipped("A", SkipCause.FAILED, whole_request=True)
    left_out.skipped("B", SkipCause.FAILED, whole_request=True)
    left_out.forget("B")
    left_out.warn()
    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A"]
    assert "at 1 of the 1 stations it read." in warning["message"]


def test_the_rejected_values_are_summed_by_check_and_a_zero_is_no_cause() -> None:
    """Several stations sum their counts, per check; a station with none rejected is not listed."""
    left_out = EstimateLeftOut()
    for station in ("A", "B", "C"):
        left_out.collected(station)
    left_out.rejected("A", 3, {"range": 2, "elevation": 1})
    left_out.rejected("B", 2, {"range": 2})
    left_out.rejected("C", 0, {})
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A", "B"]
    assert (
        "5 values at 2 stations (A, B) were numbers a plausibility check rejected (range 4, elevation 1;"
        in (warning["message"])
    )


@pytest.mark.parametrize("cause", [cause for cause in SkipCause if cause.may_heal])
def test_a_file_let_go_for_a_cause_that_can_heal_says_to_try_again_later(cause: SkipCause) -> None:
    """The estimate words its file advice by the cause, as `file-skipped` does (GH-3892)."""
    left_out = _walk(skipped=("A",), cause=cause)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert f"left out at 1 station (A): {tell_skip_causes([cause])}. The values of this station" in warning["message"]
    assert warning["message"].endswith(advise_on_skip_causes([cause]))
    assert warning["message"].endswith(" Try again later.")
    assert "report" not in warning["message"]


@pytest.mark.parametrize("cause", [cause for cause in SkipCause if not cause.may_heal])
def test_a_file_let_go_for_a_cause_that_stays_does_not_say_to_try_again_later(cause: SkipCause) -> None:
    """A refusal or a file that would not parse is the same at the next request: the advice is to report it."""
    left_out = _walk(skipped=("A",), cause=cause)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    message = warning["message"]
    assert f": {tell_skip_causes([cause])}. The values of this station" in message
    assert message.endswith(advise_on_skip_causes([cause]))
    assert "trying again will not help" in message
    assert "Try again later" not in message
    assert "may be back" not in message


def test_the_causes_of_the_stations_named_are_told_and_those_of_a_forgotten_station_are_not() -> None:
    """Each station's own cause is told, grouped as `file-skipped` groups them; a station left out takes its cause."""
    left_out = EstimateLeftOut()
    for station, cause in (("A", SkipCause.WITHDRAWN), ("B", SkipCause.UNPARSEABLE), ("C", SkipCause.REFUSED)):
        left_out.collected(station)
        left_out.skipped(station, cause, whole_request=False)
    left_out.forget("C")
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A", "B"]
    assert (
        ": the file was gone or it would not parse. The values of these stations may be missing from the estimate. "
        "A withdrawn file may be back later, so try again; a file that would not parse mostly stays as it is, and is "
        "worth reporting to the provider." in warning["message"]
    )
    assert "refused" not in warning["message"]


def test_the_cause_of_a_file_every_station_is_read_from_is_told_for_all_of_them() -> None:
    """The file of the whole request is every station's: its cause is in the advice with the stations' own."""
    left_out = EstimateLeftOut()
    for station in ("A", "B"):
        left_out.collected(station)
    left_out.skipped("A", SkipCause.MAINTENANCE, whole_request=True)
    left_out.skipped("B", SkipCause.FAILED, whole_request=False)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A", "B"]
    assert ": the download failed or an error page or an empty body came in its place." in warning["message"]
    assert warning["message"].endswith("Try again later.")


def test_the_estimate_and_file_skipped_say_the_same_for_the_same_cause() -> None:
    """Both warnings word the clause and the advice with the same helpers, so they cannot drift apart."""
    for causes in ((SkipCause.REFUSED,), (SkipCause.WITHDRAWN, SkipCause.UNPARSEABLE), (SkipCause.EMPTY_DIRECTORY,)):
        left_out = EstimateLeftOut()
        for number, cause in enumerate(causes):
            left_out.collected(str(number))
            left_out.skipped(str(number), cause, whole_request=False)
        begin_response()
        left_out.warn()
        (warning,) = recorded_warnings()
        assert tell_skip_causes(causes) in warning["message"]
        assert advise_on_skip_causes(causes) in warning["message"]


def test_forget_since_leaves_out_the_stations_read_since_the_mark_that_the_walk_was_done_for() -> None:
    """A station read before the mark stays; of those after it, those the walk was done at are out, the rest stay."""
    left_out = EstimateLeftOut()
    for station in ("A", "B", "C", "D"):
        left_out.collected(station)
        left_out.skipped(station, SkipCause.FAILED, whole_request=False)
    left_out.collected("E")
    left_out.skipped("E", SkipCause.FAILED, whole_request=False)
    begin_response()

    # `mark` was taken after B: C, D and E were read since. The walk was done at D and E, not at C
    left_out.forget_since(2, lambda station: station in {"D", "E"})
    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A", "B", "C"]
    assert "at 3 of the 3 stations it read." in warning["message"]


def test_the_mark_is_the_number_of_stations_read() -> None:
    """`mark` counts the stations read, and one forgotten is not counted."""
    left_out = EstimateLeftOut()
    assert left_out.mark() == 0
    left_out.collected("A")
    left_out.collected("B")
    assert left_out.mark() == 2
    left_out.forget("B")
    assert left_out.mark() == 1
