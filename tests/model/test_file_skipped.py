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
from unittest.mock import MagicMock

import polars as pl
import pytest
from aiohttp import ClientResponseError

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
    SkipCause,
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
    assert ": the file was gone." in warning["message"]
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


def _assert_advice(message: str, advice: str | None) -> None:
    """Hold a message to the advice it gives: `retry` (try again later) or `report` (a retry gets the same)."""
    if advice == "retry":
        assert message.endswith("Try again later.")
        assert "report" not in message
    else:
        assert advice == "report"
        assert "try again" not in message.lower()
        assert "report it to the provider" in message


# the other providers: one family each, with the control that is the source's answer


@pytest.mark.parametrize(
    ("serving", "told", "reason", "advice"),
    [
        pytest.param(
            lambda url: _failed_file(url, FileNotFoundError("not found")), False, None, None, id="not reported"
        ),
        pytest.param(lambda url: _refused(url, 403), True, "the download was refused", "report", id="403 refused"),
        pytest.param(lambda url: _refused(url, 429), True, "the download failed", "retry", id="429 rate limit"),
    ],
)
def test_smhi_names_the_station_whose_file_was_refused(
    monkeypatch: pytest.MonkeyPatch,
    serving: Callable[[str], File],
    reason: str | None,
    advice: str | None,
    *,
    told: bool,
) -> None:
    """A 404 is SMHI answering that the station does not report the parameter; a refusal is a file let go.

    A 403 stays as it is at the next request, so it is reported; a 429 is a rate limit, which may be gone.
    """

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
        assert f": {reason}." in _told()[0]["message"]
        _assert_advice(_told()[0]["message"], advice)
        assert _told("parameter-without-rows") == []


_AEMET = [
    pytest.param(lambda url: _refused(url, 400), True, "the download was refused", "report", id="400"),
    pytest.param(
        lambda url: File(url=url, content=BytesIO(b"<html>maintenance</html>"), status=200),
        True,
        "an error page or an empty body came in its place",
        "retry",
        id="html",
    ),
    pytest.param(lambda url: _envelope(url, 404), False, None, None, id="estado 404 is no data"),
    pytest.param(lambda url: _failed_file(url, FileNotFoundError(url)), False, None, None, id="404 is no data"),
]


@pytest.mark.parametrize(("answer", "told", "reason", "advice"), _AEMET)
def test_aemet_names_the_station_whose_chunk_was_let_go(
    monkeypatch: pytest.MonkeyPatch,
    answer: Callable[[str], File],
    reason: str | None,
    advice: str | None,
    *,
    told: bool,
) -> None:
    """A refused chunk and a maintenance page are let go; AEMET's own answer that it has no data is not."""
    _aemet_serving(monkeypatch, answer)
    begin_response()
    assert _values("daily", years=1).is_empty()
    assert [w["stations"] for w in _told()] == ([[MADRID_RETIRO]] if told else [])
    if told:
        assert f": {reason}." in _told()[0]["message"]
        _assert_advice(_told()[0]["message"], advice)


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


_FMI_REQUEST_ERROR = _EXCEPTION_REPORT.replace(b"OperationProcessingFailed", b"InvalidParameterValue").replace(
    b"Too many requests", b"Invalid parameter"
)


@pytest.mark.parametrize(
    ("answer", "told", "reason", "advice"),
    [
        pytest.param(
            _EXCEPTION_REPORT, True, "an error page or an empty body came in its place", "retry", id="rate limit"
        ),
        pytest.param(_FMI_REQUEST_ERROR, True, "the download was refused", "report", id="request error"),
        pytest.param(_collection(), False, None, None, id="empty collection"),
    ],
)
def test_fmi_names_the_station_whose_answer_was_an_exception_report(
    monkeypatch: pytest.MonkeyPatch,
    answer: bytes,
    reason: str | None,
    advice: str | None,
    *,
    told: bool,
) -> None:
    """FMI answers 200 for an error as well as for a station that reports nothing; only the first is a file let go."""
    _serve_fmi(monkeypatch, answer)
    begin_response()
    start = dt.datetime(2024, 1, 1, tzinfo=UTC)
    assert _fmi_values("hourly", start, start + dt.timedelta(hours=1)).is_empty()
    assert [w["stations"] for w in _told()] == ([["100971"]] if told else [])
    if told:
        assert f": {reason}." in _told()[0]["message"]
        _assert_advice(_told()[0]["message"], advice)


def test_fmi_names_the_station_whose_query_it_answers_with_a_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """FMI's 400 (an unknown fmisid, a stored query or parameter it no longer has) is the same at the next request."""
    _serve_fmi(monkeypatch, OSError("Unknown 'fmisid' value!"), status=400)
    begin_response()
    start = dt.datetime(2024, 1, 1, tzinfo=UTC)
    assert _fmi_values("hourly", start, start + dt.timedelta(hours=1)).is_empty()

    (warning,) = _told()
    assert warning["stations"] == ["100971"]
    assert ": the download was refused." in warning["message"]
    _assert_advice(warning["message"], "report")


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
                note_skipped_download(SkipCause.FAILED, whole_request=True)
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
            note_skipped_download(SkipCause.FAILED)
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
        note_skipped_download(SkipCause.FAILED)
    rows.warn()
    assert _told() == []


def test_the_warning_is_recorded_once_whatever_the_number_of_files() -> None:
    """A station that lets go several files (periods, datasets) is named once, and the warning is told once."""
    request = _dwd_stations(("00001",)).request
    rows = ParameterRows(request, None, None)
    dataset = request.metadata["daily"]["climate_summary"]
    rows.examine("00001", [dataset])
    with rows.collecting("00001"):
        note_skipped_download(SkipCause.FAILED)
        note_skipped_download(SkipCause.FAILED)
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
        note_skipped_download(SkipCause.FAILED)
    with rows.collecting("00002"):
        pass
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert warning["stations"] == ["00001"]
    assert "(daily/climate_summary)" in warning["message"]
    assert "precipitation_more" not in warning["message"]


def test_a_station_a_filled_rank_walk_passed_over_is_not_named() -> None:
    """The candidates a rank walk replaced are not a gap in an answer that holds as many stations as were asked for."""
    request = _dwd_stations(("00001", "00002")).request
    rows = ParameterRows(request, None, None)
    for station in ("00001", "00002"):
        rows.examine(station, [request.metadata["daily"]["climate_summary"]])
        with rows.collecting(station):
            note_skipped_download(SkipCause.FAILED)
    rows.passed_over("00001")
    begin_response()

    rows.warn(rank_filled=True)

    (warning,) = _told()
    assert warning["stations"] == ["00002"]
    assert warning["message"].startswith("A file of station 00002 ")

    # a walk that ended short, or empty, names them all
    begin_response()
    rows.warn(rank_filled=False)
    assert [w["stations"] for w in _told()] == [["00001", "00002"]]

    # and all of them replaced: nothing to tell
    rows.passed_over("00002")
    begin_response()
    rows.warn(rank_filled=True)
    assert _told() == []


def test_swsmos_names_every_station_of_a_rank_walk_whose_run_could_not_be_fetched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The run is every station's file: a rank walk that it empties out ends short, and names all it walked."""
    import dataclasses  # noqa: PLC0415

    from tests.provider.dwd.swsmos.test_api import _stub_stations as swsmos_stations  # noqa: PLC0415
    from wetterdienst.provider.dwd.swsmos import api as sws_api  # noqa: PLC0415

    listed = [f"{sws_api._BASE_URL}/{sws_api._LATEST_FILE}"]  # noqa: SLF001
    monkeypatch.setattr(sws_api, "list_remote_files_fsspec", lambda *_a, **_k: listed)
    monkeypatch.setattr(
        sws_api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=FileNotFoundError("404"), status=404),
    )
    stations = dataclasses.replace(
        swsmos_stations(("A006", "B999", "C111")), _stations_filter=StationsFilter.BY_RANK, _rank=2
    )
    begin_response()

    assert stations.values().all().df.is_empty()

    (warning,) = _told()
    assert warning["stations"] == ["A006", "B999", "C111"]
    assert warning["message"].startswith("A file that every station of the request is read from (stations A006, B999")
    # the run is not evidence that the source holds nothing
    assert _told("parameter-without-rows") == []


# the advice is worded by the cause the provider tells (GH-3874)

_HEALING = (SkipCause.FAILED, SkipCause.WITHDRAWN, SkipCause.MAINTENANCE, SkipCause.EMPTY_DIRECTORY)
_LASTING = (SkipCause.REFUSED, SkipCause.UNPARSEABLE)


def _told_for(*causes: SkipCause, whole_request: bool = False) -> str:
    """Give the message of `file-skipped` for a walk whose provider let a file go for each of `causes`."""
    stations = tuple(f"0000{number}" for number in range(1, len(causes) + 1))
    request = _dwd_stations(stations).request
    rows = ParameterRows(request, None, None)
    dataset = request.metadata["daily"]["climate_summary"]
    for station, cause in zip(stations, causes, strict=True):
        rows.examine(station, [dataset])
        with rows.collecting(station):
            note_skipped_download(cause, whole_request=whole_request)
    begin_response()
    rows.warn()
    (warning,) = _told()
    return warning["message"]


@pytest.mark.parametrize("cause", _HEALING)
def test_a_cause_that_can_heal_says_to_try_again_later(cause: SkipCause) -> None:
    """A failed download, a withdrawn file, a maintenance page and an empty directory may be back: retry."""
    message = _told_for(cause)

    assert f": {cause.reason}." in message
    assert message.endswith("which is partial. Try again later.")
    assert "report" not in message


@pytest.mark.parametrize("cause", _LASTING)
def test_a_cause_that_stays_never_says_to_try_again(cause: SkipCause) -> None:
    """A refused download and a file that would not parse stay as they are: the advice is to report it."""
    message = _told_for(cause)

    assert f": {cause.reason}." in message
    assert "try again" not in message.lower()
    assert "unlikely to change" in message
    assert "report it to the provider" in message
    assert message.count(cause.noun.capitalize()) == 1


def test_a_parse_failure_in_the_real_parser_is_a_cause_that_stays(monkeypatch: pytest.MonkeyPatch) -> None:
    """The DWD parser tells `UNPARSEABLE` for a file polars cannot read, and the warning does not send a retry."""
    from wetterdienst.metadata.period import Period  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import parser as observation_parser  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata  # noqa: PLC0415

    def broken(**_kwargs: object) -> None:
        msg = "x"
        raise pl.exceptions.SchemaError(msg)

    monkeypatch.setattr(pl, "scan_csv", broken)
    file = File(url="https://example.org/produkt.txt", content=BytesIO(b"a;b\n1;2\n"), status=200)
    request = _dwd_stations(("00001",)).request
    rows = ParameterRows(request, None, None)
    rows.examine("00001", [request.metadata["daily"]["climate_summary"]])
    with rows.collecting("00001"):
        observation_parser._parse_climate_observations_data(  # noqa: SLF001
            file, DwdObservationMetadata.daily.climate_summary, Period.RECENT
        )
    begin_response()
    rows.warn()

    (warning,) = _told()
    assert ": it would not parse." in warning["message"]
    assert "try again" not in warning["message"].lower()
    assert "report it to the provider" in warning["message"]


def test_causes_of_both_kinds_are_grouped_as_the_estimate_groups_them() -> None:
    """Several causes in one warning: the ones that heal are retried, the others reported, naming what occurred."""
    message = _told_for(SkipCause.WITHDRAWN, SkipCause.EMPTY_DIRECTORY, SkipCause.UNPARSEABLE)

    assert ": the file was gone, the directory was found empty or it would not parse." in message
    assert message.endswith(
        "A withdrawn file and an empty directory may be back later, so try again; a file that would not parse "
        "mostly stays as it is, and is worth reporting to the provider."
    )


def test_only_the_causes_of_the_stations_named_are_told() -> None:
    """A station a filled rank walk replaced does not bring its cause into the warning of the others."""
    request = _dwd_stations(("00001", "00002")).request
    rows = ParameterRows(request, None, None)
    for station, cause in (("00001", SkipCause.UNPARSEABLE), ("00002", SkipCause.FAILED)):
        rows.examine(station, [request.metadata["daily"]["climate_summary"]])
        with rows.collecting(station):
            note_skipped_download(cause)
    rows.passed_over("00001")
    begin_response()

    rows.warn(rank_filled=True)

    (warning,) = _told()
    assert warning["stations"] == ["00002"]
    assert warning["message"].endswith("Try again later.")
    assert "would not parse" not in warning["message"]


def test_a_file_that_serves_every_station_tells_its_own_cause() -> None:
    """The cause of a whole-request file is the file's, whichever station met it."""
    message = _told_for(SkipCause.REFUSED, whole_request=True)

    assert message.startswith("A file that every station of the request is read from")
    assert ": the download was refused." in message
    assert "try again" not in message.lower()


def test_the_structured_members_of_the_warning_are_unchanged() -> None:
    """The code and the members stay: the cause is in the message, not a new field (GH-3874)."""
    _told_for(SkipCause.UNPARSEABLE)

    (warning,) = _told()
    assert set(warning) == {"code", "message", "stations"}
    assert warning["code"] == "file-skipped"


def test_a_failed_download_is_told_as_refused_only_where_the_download_was_refused() -> None:
    """`File.skip_cause` reads the 404 as withdrawn, a refused body as refused and any other failure as failed."""
    from wetterdienst.exceptions import DownloadError  # noqa: PLC0415
    from wetterdienst.util.network import DownloadRefusedError, skip_cause_of_failure  # noqa: PLC0415

    url = "https://example.invalid/a.zip"
    refused = DownloadRefusedError("the file is larger than a download is held to")

    assert File(url=url, content=FileNotFoundError(url), status=404).skip_cause is SkipCause.WITHDRAWN
    # the real path: the network layer stores the refusal as a 500, not a 200
    stored = _failed_file(url, refused)
    assert stored is not None
    assert stored.skip_cause is SkipCause.REFUSED
    assert File(url=url, content=TimeoutError(), status=200).skip_cause is SkipCause.FAILED
    assert File(url=url, content=DownloadError(url, "500"), status=500).skip_cause is SkipCause.FAILED
    # the error a caller raised for the refusal names the file and keeps the refusal as its cause
    named = DownloadError(url, str(refused))
    named.__cause__ = refused
    assert skip_cause_of_failure(named) is SkipCause.REFUSED


def _client_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status, message="x")


@pytest.mark.parametrize(
    ("status", "cause"),
    [
        (400, SkipCause.REFUSED),
        (401, SkipCause.REFUSED),
        (403, SkipCause.REFUSED),
        (410, SkipCause.REFUSED),
        (422, SkipCause.REFUSED),
        (404, SkipCause.WITHDRAWN),
        (408, SkipCause.FAILED),
        (425, SkipCause.FAILED),
        (429, SkipCause.FAILED),
        (500, SkipCause.FAILED),
        (503, SkipCause.FAILED),
    ],
)
def test_a_4xx_other_than_the_ones_that_pass_is_a_refusal_for_good(status: int, cause: SkipCause) -> None:
    """A request the server turns down (400, 403, 410) is the same at the next; a 404, 408, 425, 429 and 5xx may not."""
    from wetterdienst.util.network import skip_cause_of_failure  # noqa: PLC0415

    url = "https://example.invalid/a.zip"
    stored = _failed_file(url, _client_error(status))
    assert stored is not None
    assert stored.skip_cause is cause
    # the exception alone, as the readers that keep no `File` (SMHI, KNMI, AEMET) hand it over
    if status != 404:
        assert skip_cause_of_failure(_client_error(status)) is cause


def test_a_redirect_that_was_not_followed_is_a_refusal_for_good() -> None:
    """`as_outage` reads an off-host redirect as a refusal, and the next request meets the same one."""
    from wetterdienst.util.network import RedirectRefusedError, skip_cause_of_failure  # noqa: PLC0415

    url = "https://example.invalid/a.zip"
    error = RedirectRefusedError("left the hosts of the provider")
    stored = _failed_file(url, error)

    assert stored is not None
    assert stored.skip_cause is SkipCause.REFUSED
    assert skip_cause_of_failure(error) is SkipCause.REFUSED


def test_a_station_whose_historical_directory_is_empty_is_told_as_an_empty_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The high resolutions list the `historical` directory for the date ranges of the station: empty, it heals."""
    from wetterdienst.provider.dwd.observation.fileindex import EmptyListingError  # noqa: PLC0415

    def empty(*_args: object, **_kwargs: object) -> None:
        url = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/x/historical/"
        raise EmptyListingError(url)

    monkeypatch.setattr(dwd_observation_api.DwdObservationValues, "_get_historical_date_ranges", empty)
    request = DwdObservationRequest(
        parameters=[("minute_10", "temperature_air")],
        start=dt.datetime(2020, 5, 1, tzinfo=UTC),
        end=dt.datetime(2020, 5, 3, tzinfo=UTC),
        periods="historical",
        settings=Settings(cache_disable=True),
    )
    df = pl.DataFrame(
        {
            "resolution": ["minute_10"],
            "dataset": ["temperature_air"],
            "station_id": ["00001"],
            "start_timestamp": [dt.datetime(1934, 1, 1, tzinfo=UTC)],
            "end_timestamp": [dt.datetime(2026, 1, 1, tzinfo=UTC)],
            "latitude": [50.0],
            "longitude": [10.0],
            "elevation": [100.0],
            "name": ["Stub"],
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    stations = StationsResult(request=request, df=df, _df_all=df, _stations_filter=StationsFilter.BY_STATION_ID)
    begin_response()

    assert stations.values().all().df.is_empty()

    (warning,) = _told()
    assert ": the directory was found empty." in warning["message"]
    _assert_advice(warning["message"], "retry")
