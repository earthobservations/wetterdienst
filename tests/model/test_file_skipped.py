# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations whose file the provider let go are told by one `file-skipped` warning (GH-3552).

`parameter-without-rows` leaves those stations out (GH-3539), because their values may be missing for the file and not
for the source. Without a warning of their own an answer made of the others reads like a whole one. The warning is
raised from the walk (`ParameterRows.warn`) for every station a provider told `note_skipped_download` of, once for the
request, and not where the source answered that it has nothing. One test per family of providers, with the control
that is the answer of the source, over the same stubs as `test_parameter_without_rows_failures.py`.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from io import BytesIO
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.model.test_parameter_without_rows_failures import (
    _aemet_serving,
    _envelope,
    _frost_kind,
    _frost_listing,
    _refused,
)
from tests.provider.aemet.observation.test_api import BARCELONA, MADRID_RETIRO, _values
from tests.provider.fmi.observation.test_values_frames import _EXCEPTION_REPORT, _collection
from tests.provider.fmi.observation.test_values_frames import _serve as _serve_fmi
from tests.provider.fmi.observation.test_values_frames import _values as _fmi_values
from tests.provider.metno.frost.test_values_failures import _failed as _frost_answer
from tests.provider.metno.frost.test_values_failures import _values as _frost_values
from tests.provider.smhi.observation.test_api_download_failure import _STATION
from tests.provider.smhi.observation.test_api_download_failure import _request as _smhi_request
from wetterdienst import Settings
from wetterdienst.model.parameter_rows import ParameterRows
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation import download as dwd_observation_download
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File, _failed_file
from wetterdienst.util.response_warnings import (
    FILE_SKIPPED,
    begin_response,
    note_skipped_download,
    recorded_warnings,
)

if TYPE_CHECKING:
    from collections.abc import Callable

UTC = dt.UTC
NO_FILE = "https://example.invalid/none.zip"


def _told(code: str = FILE_SKIPPED) -> list[dict[str, Any]]:
    """Give the warnings of `code` that the request being served has recorded."""
    return [warning for warning in recorded_warnings() if warning["code"] == code]


# dwd/observation: the real download, a 404 for a file the index listed


def _dwd_stations(station_ids: tuple[str, ...]) -> StationsResult:
    """Stand daily stations up, for the request of the dataset `climate_summary` in the window of one day."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start=dt.datetime(2020, 5, 1, tzinfo=UTC),
        end=dt.datetime(2020, 5, 3, tzinfo=UTC),
        periods="recent",
        settings=Settings(cache_disable=True),
    )
    df = pl.DataFrame(
        {
            "resolution": ["daily"] * len(station_ids),
            "dataset": ["climate_summary"] * len(station_ids),
            "station_id": list(station_ids),
            "start_timestamp": [dt.datetime(1934, 1, 1, tzinfo=UTC)] * len(station_ids),
            "end_timestamp": [dt.datetime(2026, 1, 1, tzinfo=UTC)] * len(station_ids),
            "latitude": [50.0] * len(station_ids),
            "longitude": [10.0] * len(station_ids),
            "elevation": [100.0] * len(station_ids),
            "name": ["Stub"] * len(station_ids),
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    return StationsResult(request=request, df=df, _df_all=df, _stations_filter=StationsFilter.BY_STATION_ID)


def _dwd_serving(monkeypatch: pytest.MonkeyPatch, answers: dict[str, File | None]) -> None:
    """List a file for each station of `answers` and answer it as `answers` says; None lists none for the station."""

    def files(station_id: str, *_args: object, **_kwargs: object) -> pl.Series:
        return pl.Series(
            [] if answers[station_id] is None else [f"https://example.invalid/{station_id}.zip"], dtype=pl.String
        )

    def download_files(urls: list[str], **_kwargs: object) -> list[File]:
        return [answer for url in urls if (answer := answers[url.rsplit("/", 1)[-1][:-4]]) is not None]

    monkeypatch.setattr(dwd_observation_api, "create_file_list_for_climate_observations", files)
    monkeypatch.setattr(dwd_observation_download, "download_files", download_files)


def _withdrawn(station_id: str) -> File:
    return File(url=f"https://example.invalid/{station_id}.zip", content=FileNotFoundError(station_id), status=404)


def test_dwd_observation_names_the_station_whose_file_was_withdrawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """A listed file that is a 404 is let go: one warning with the station and the dataset, and the others silent."""
    _dwd_serving(monkeypatch, {"00001": _withdrawn("00001"), "00002": None})
    begin_response()

    assert _dwd_stations(("00001", "00002")).values().all().df.is_empty()

    (warning,) = _told()
    assert warning["stations"] == ["00001"]
    assert warning["message"].startswith("A file of station 00001 (daily/climate_summary) was not used")
    assert "Try again later." in warning["message"]
    # the source holds nothing at the other station, which is told as before, and the one let go is not
    (without_rows,) = _told("parameter-without-rows")
    assert without_rows["stations"] == ["00002"]


def test_dwd_observation_tells_nothing_when_no_file_was_let_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stations with no file listed are the source's answer, not a file let go."""
    _dwd_serving(monkeypatch, {"00001": None, "00002": None})
    begin_response()

    assert _dwd_stations(("00001", "00002")).values().all().df.is_empty()

    assert _told() == []
    assert [w["stations"] for w in _told("parameter-without-rows")] == [["00001", "00002"]]


def test_dwd_observation_names_each_station_once_in_the_order_of_the_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two stations whose file was withdrawn are one warning, as many periods or datasets of one are one entry."""
    _dwd_serving(monkeypatch, {"00001": _withdrawn("00001"), "00002": _withdrawn("00002")})
    begin_response()

    _dwd_stations(("00001", "00002")).values().all()

    (warning,) = _told()
    assert warning["stations"] == ["00001", "00002"]
    assert warning["message"].startswith("Files of stations 00001, 00002 (daily/climate_summary) were not used")
    assert _told("parameter-without-rows") == []


def test_dwd_observation_logs_the_warning_in_python(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """In Python, outside a request, the warning is a log line at level WARNING."""
    _dwd_serving(monkeypatch, {"00001": _withdrawn("00001")})
    with caplog.at_level(logging.WARNING, logger="wetterdienst.model.parameter_rows"):
        _dwd_stations(("00001",)).values().all()
    messages = [r.getMessage() for r in caplog.records if r.name == "wetterdienst.model.parameter_rows"]
    assert messages[0].startswith("A file of station 00001")


# the other providers: one family each, with the control that is the source's answer


@pytest.mark.parametrize(
    ("serving", "told"),
    [
        pytest.param(lambda url: _failed_file(url, FileNotFoundError("not found")), False, id="not reported"),
        pytest.param(lambda url: _refused(url, 403), True, id="refused"),
    ],
)
def test_smhi_names_the_station_whose_file_was_refused(
    monkeypatch: pytest.MonkeyPatch, serving: Callable[[str], File], *, told: bool
) -> None:
    """A 404 is SMHI answering that the station does not report the parameter; a refusal is a file let go."""

    def download_files(urls: list[str], **_: object) -> list[File]:
        body = json.dumps({"station": [_STATION]}).encode()
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    monkeypatch.setattr(smhi_api, "download_file", lambda url, **_: serving(url))
    begin_response()
    assert _smhi_request().values().all().df.is_empty()

    assert [w["stations"] for w in _told()] == ([["98230"]] if told else [])
    if told:
        assert "(daily/data)" in _told()[0]["message"]
        assert _told("parameter-without-rows") == []


_AEMET = [
    pytest.param(lambda url: _refused(url, 400), True, id="400"),
    pytest.param(lambda url: File(url=url, content=BytesIO(b"<html>maintenance</html>"), status=200), True, id="html"),
    pytest.param(lambda url: _envelope(url, 404), False, id="estado 404 is no data"),
    pytest.param(lambda url: _failed_file(url, FileNotFoundError(url)), False, id="404 is no data"),
]


@pytest.mark.parametrize(("answer", "told"), _AEMET)
def test_aemet_names_the_station_whose_chunk_was_let_go(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[str], File], *, told: bool
) -> None:
    """A refused chunk and a maintenance page are let go; AEMET's own answer that it has no data is not."""
    _aemet_serving(monkeypatch, answer)
    begin_response()
    assert _values("daily", years=1).is_empty()
    assert [w["stations"] for w in _told()] == ([[MADRID_RETIRO]] if told else [])


def test_aemet_names_only_the_station_whose_chunk_was_let_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """One station's chunk is refused and the other's is AEMET's answer of no data: each is told by its own warning."""
    _aemet_serving(
        monkeypatch,
        lambda url: _refused(url, 400) if f"/{MADRID_RETIRO}" in url else _envelope(url, 404),
    )
    begin_response()
    assert _values("daily", years=1, station_ids=(MADRID_RETIRO, BARCELONA)).is_empty()
    assert [w["stations"] for w in _told()] == [[MADRID_RETIRO]]
    assert [w["stations"] for w in _told("parameter-without-rows")] == [[BARCELONA]]


@pytest.mark.parametrize(
    ("answer", "told"),
    [
        pytest.param(_EXCEPTION_REPORT, True, id="exception report"),
        pytest.param(_collection(), False, id="empty collection"),
    ],
)
def test_fmi_names_the_station_whose_answer_was_an_exception_report(
    monkeypatch: pytest.MonkeyPatch, answer: bytes, *, told: bool
) -> None:
    """FMI answers 200 for an error as well as for a station that reports nothing; only the first is a file let go."""
    _serve_fmi(monkeypatch, answer)
    begin_response()
    start = dt.datetime(2024, 1, 1, tzinfo=UTC)
    assert _fmi_values("hourly", start, start + dt.timedelta(hours=1)).is_empty()
    assert [w["stations"] for w in _told()] == ([["100971"]] if told else [])


@pytest.mark.parametrize(("status", "told"), [(500, True), (404, False)], ids=["500 failed", "404 is no data"])
def test_frost_names_the_station_whose_series_failed(
    monkeypatch: pytest.MonkeyPatch, status: int, *, told: bool
) -> None:
    """A failed series is let go; Frost's 404 for it is its answer that there is no data."""

    def observations(url: str) -> File:
        kind = _frost_kind(url)
        if kind == "available":
            return _frost_listing(url)
        return _frost_answer(url, status if kind == "series" else 404)

    values, _seen = _frost_values(monkeypatch, observations)
    begin_response()
    assert values.all().df.is_empty()
    assert [w["stations"] for w in _told()] == ([["SN18700"]] if told else [])


# the places the walk learns of it from


def _walk(*stations: str) -> ParameterRows:
    """Give the walk of a request over `stations`, which has collected each of them for the daily climate summary."""
    request = _dwd_stations(stations).request
    rows = ParameterRows(request, None, None)
    metadata = request.metadata["daily"]["climate_summary"]
    for station in stations:
        rows.examine(station, [metadata])
        with rows.collecting(station):
            pass
    return rows


def test_a_file_that_serves_every_station_is_every_stations() -> None:
    """A reader that fails on a file all the stations are read from (`whole_request`) names the stations collected."""
    request = _dwd_stations(("00001", "00002", "00003")).request
    rows = ParameterRows(request, None, None)
    dataset = request.metadata["daily"]["climate_summary"]
    for station in ("00001", "00002", "00003"):
        rows.examine(station, [dataset])
        with rows.collecting(station):
            if station == "00001":
                note_skipped_download(whole_request=True)
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert warning["stations"] == ["00001", "00002", "00003"]
    assert warning["message"].startswith(
        "A file that every station of the request is read from (stations 00001, 00002, 00003 (daily/climate_summary)) "
        "was not used"
    )


def test_the_stations_are_cut_and_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A walk that let go the files of a whole network does not list every station: the first ones, and how many."""
    monkeypatch.setattr("wetterdienst.model.parameter_rows.MAX_STATIONS_LISTED", 2)
    stations = ("00001", "00002", "00003")
    request = _dwd_stations(stations).request
    rows = ParameterRows(request, None, None)
    dataset = request.metadata["daily"]["climate_summary"]
    for station in stations:
        rows.examine(station, [dataset])
        with rows.collecting(station):
            note_skipped_download()
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert warning["stations"] == ["00001", "00002"]
    assert (
        "Files of 3 stations, the first 2 of them 00001, 00002 (daily/climate_summary) were not used"
        in (warning["message"])
    )


def test_a_walk_that_let_go_nothing_tells_nothing() -> None:
    """No file let go is no warning, and a walk that is switched off (an estimate) says nothing either."""
    begin_response()
    _walk("00001", "00002").warn()
    assert _told() == []

    request = _dwd_stations(("00001",)).request
    rows = ParameterRows(request, None, None, enabled=False)
    with rows.collecting("00001"):
        note_skipped_download()
    rows.warn()
    assert _told() == []


def test_the_warning_is_recorded_once_whatever_the_number_of_files() -> None:
    """A station that lets go several files (periods, datasets) is named once, and the warning is told once."""
    request = _dwd_stations(("00001",)).request
    rows = ParameterRows(request, None, None)
    dataset = request.metadata["daily"]["climate_summary"]
    rows.examine("00001", [dataset])
    with rows.collecting("00001"):
        note_skipped_download()
        note_skipped_download()
    begin_response()

    rows.warn()
    rows.warn()

    (warning,) = _told()
    assert warning["stations"] == ["00001"]


def test_the_message_names_only_the_datasets_read_at_the_stations_let_go() -> None:
    """Two stations are read for different datasets and only the first one's file is let go: only its is named."""
    request = _dwd_stations(("00001", "00002")).request
    rows = ParameterRows(request, None, None)
    rows.examine("00001", [request.metadata["daily"]["climate_summary"]])
    rows.examine("00002", [request.metadata["daily"]["precipitation_more"]])
    with rows.collecting("00001"):
        note_skipped_download()
    with rows.collecting("00002"):
        pass
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert warning["stations"] == ["00001"]
    assert "(daily/climate_summary)" in warning["message"]
    assert "precipitation_more" not in warning["message"]


def test_a_station_passed_over_is_not_named() -> None:
    """A station the walk left out of the answer for an empty frame is not one the answer is partial for."""
    request = _dwd_stations(("00001", "00002")).request
    rows = ParameterRows(request, None, None)
    for station in ("00001", "00002"):
        rows.examine(station, [request.metadata["daily"]["climate_summary"]])
        with rows.collecting(station):
            note_skipped_download()
    rows.passed_over("00001")
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert warning["stations"] == ["00002"]
    assert warning["message"].startswith("A file of station 00002 ")

    # all of them passed over: nothing is told, and `parameter-without-rows` still leaves them out
    rows.passed_over("00002")
    begin_response()
    rows.warn()
    assert recorded_warnings() == []
