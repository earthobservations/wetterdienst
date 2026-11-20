# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `wigos_id` that WMO OSCAR/Surface gives a station whose provider's id is the local part of one (GH-4074).

The rule is the exact one: the id of the provider is the local part of a WIGOS id of the country's own issuer, and
nothing is matched by name or position. These tests hold it on rows of the real register (`oscar_rows.py`, read
2026-11-19), the page that the reader asks of the register and what becomes of the stations when it cannot be read.
The last test reads the live register.
"""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.model.oscar_rows import register
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, MetaFileFormatError, NoInternetError, ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model import oscar
from wetterdienst.model.oscar import (
    OSCAR_SEARCH_URL,
    WIGOS_IDS_UNAVAILABLE,
    NationalWigosScheme,
    OscarRegisterError,
    oscar_url,
    parse_wigos_ids,
    read_register,
    wigos_ids_of_scheme,
    with_oscar_wigos_id,
)
from wetterdienst.provider.dmi.observation.api import DMI_WIGOS_SCHEME
from wetterdienst.provider.dwd.observation.api import DWD_WIGOS_SCHEME
from wetterdienst.provider.fmi.observation.api import FMI_WIGOS_SCHEME
from wetterdienst.util.network import File, download_file
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _wigos_ids(stations: pl.LazyFrame | pl.DataFrame) -> dict[str, str | None]:
    frame = stations.lazy().collect()
    return dict(zip(frame["station_id"], frame["wigos_id"], strict=True))


# what the schemes pick out of the register


def test_the_stub_is_the_register_as_oscar_answers_it() -> None:
    """The ids are read in the notation of `wigos_id`, each once, whatever status and issuer."""
    ids = parse_wigos_ids(register("DEU"), "DEU")
    assert "0-276-3-73" in ids
    assert "0-20000-0-10147" in ids
    assert len(ids) == len(set(ids))


def test_dwd_stations_ids_are_the_local_parts_of_the_ids_of_the_issue_numbers_that_are_its_own() -> None:
    """`0-276-3-73` is the DWD station `00073`: the register writes the id without the zeros DWD pads it with."""
    found = dict(wigos_ids_of_scheme(parse_wigos_ids(register("DEU"), "DEU"), DWD_WIGOS_SCHEME).iter_rows())
    assert found["73"] == "0-276-3-73"
    assert found["399"] == "0-276-6-399"  # a city climate station: issue number 6
    assert found["96"] == "0-276-2-96"
    assert "10103" not in found  # a radar, issue number 0
    assert "HEL" not in found  # issue number 0 is the issuer's other schemes (a radar, a profiler), no id of DWD's
    assert "10147" not in found  # Hamburg-Fuhlsbüttel has only the WMO's own id, which is no local id of DWD's


def test_the_wmo_issuer_is_never_read_as_a_local_id_of_the_provider() -> None:
    """`0-20000-0-06126` has the tail of DMI's `06126` and is the WMO number: the id of the national issuer is read."""
    found = dict(wigos_ids_of_scheme(parse_wigos_ids(register("DNK"), "DNK"), DMI_WIGOS_SCHEME).iter_rows())
    assert found["06126"] == "0-208-0-06126"
    assert set(found.values()) == {
        "0-208-0-06126",
        "0-208-0-06009",
        "0-208-0-06074",
        "0-208-0-06134",
        "0-208-0-06132",
        "0-208-0-06180",
        "0-208-0-06041",
    }


def test_another_issue_number_of_the_issuer_is_another_scheme() -> None:
    """FMI's fmisid is `0-246-0-<fmisid>`: the register's `0-246-3-000101` is not one."""
    ids = parse_wigos_ids(register("FIN"), "FIN")
    assert "0-246-3-000101" in ids
    found = dict(wigos_ids_of_scheme(ids, FMI_WIGOS_SCHEME).iter_rows())
    assert "000101" not in found
    assert found["101520"] == "0-246-0-101520"


def test_two_ids_of_one_register_station_are_each_the_id_of_their_own_station() -> None:
    """OSCAR lists `0-208-0-06134` and `0-208-0-06132` on one station: each is exact for the DMI station of its id."""
    found = dict(wigos_ids_of_scheme(parse_wigos_ids(register("DNK"), "DNK"), DMI_WIGOS_SCHEME).iter_rows())
    assert found["06134"] == "0-208-0-06134"
    assert found["06132"] == "0-208-0-06132"


def test_two_ids_for_one_local_part_are_left_null_and_the_log_says_so(caplog: pytest.LogCaptureFixture) -> None:
    """DWD's `73` is both `0-276-3-73` and `0-276-6-73`: which is the station's is not for the reader to guess."""
    ids = ["0-276-3-73", "0-276-6-73", "0-276-3-91"]
    with caplog.at_level(logging.WARNING, logger=oscar.log.name):
        found = dict(wigos_ids_of_scheme(ids, DWD_WIGOS_SCHEME).iter_rows())
    assert found == {"91": "0-276-3-91"}
    (record,) = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert "0-276-3-73 and 0-276-6-73" in record.getMessage()
    assert "dwd/observation" in record.getMessage()


def test_the_ids_of_another_issuer_are_not_the_countrys() -> None:
    """A scheme reads the ids of its issuer only, whatever the register of the territory lists."""
    ids = ["0-276-3-73", "0-208-0-74", "0-20000-0-00075", "0-246-0-76"]
    assert dict(wigos_ids_of_scheme(ids, DWD_WIGOS_SCHEME).iter_rows()) == {"73": "0-276-3-73"}


# what the stations get


def test_a_dwd_station_gets_the_id_of_its_stations_id_and_zeros_do_not_make_another_station() -> None:
    """`00073` is `73`; `00003` (Aachen) and the main stations have no `0-276-` id and so no `wigos_id`."""
    stations = pl.LazyFrame({"station_id": ["00073", "00091", "00003", "10147", "00044", "00399", "00096", "10103"]})
    found = _wigos_ids(with_oscar_wigos_id(stations, Settings(cache_disable=True), DWD_WIGOS_SCHEME))
    assert found == {
        "00073": "0-276-3-73",
        "00091": "0-276-3-91",
        "00003": None,
        "10147": None,
        "00044": "0-276-3-44",
        "00399": "0-276-6-399",
        "00096": "0-276-2-96",
        "10103": None,  # `0-276-0-10103` is the number of a radar, issue number 0: no id of DWD's
    }


def test_the_zeros_of_a_register_id_are_not_the_zeros_of_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """An id the register writes with a zero (`073`) is another local part than DWD's `00073` read without them."""
    scheme = NationalWigosScheme(
        territories=("DEU",), issuer=276, issue_numbers=frozenset({3}), provider="x", strip_zeros=True
    )
    ids = ["0-276-3-073", "0-276-3-91"]
    found = dict(wigos_ids_of_scheme(ids, scheme).iter_rows())
    assert found == {"073": "0-276-3-073", "91": "0-276-3-91"}
    monkeypatch.setattr(oscar, "read_register", lambda *_args: ids)
    stations = pl.LazyFrame({"station_id": ["00073", "00091"]})
    assert _wigos_ids(with_oscar_wigos_id(stations, Settings(cache_disable=True), scheme)) == {
        "00073": None,
        "00091": "0-276-3-91",
    }


def test_an_fmi_and_a_dmi_station_get_the_ids_written_the_way_the_provider_writes_its_own() -> None:
    """`100971` and `06126` are compared as they are, `06126` with its zero."""
    settings = Settings(cache_disable=True)
    fmi = with_oscar_wigos_id(
        pl.LazyFrame({"station_id": ["100971", "101009", "000101", "999999"]}), settings, FMI_WIGOS_SCHEME
    )
    assert _wigos_ids(fmi) == {
        "100971": "0-246-0-100971",
        "101009": "0-246-0-101009",
        "000101": None,
        "999999": None,
    }
    dmi = with_oscar_wigos_id(pl.LazyFrame({"station_id": ["06126", "6126", "06009"]}), settings, DMI_WIGOS_SCHEME)
    assert _wigos_ids(dmi) == {"06126": "0-208-0-06126", "6126": None, "06009": "0-208-0-06009"}


def test_a_wigos_id_the_provider_published_stays() -> None:
    """The list of the provider is the better source: OSCAR fills what it has not, and never replaces."""
    stations = pl.LazyFrame({"station_id": ["00073", "00091", "00044"], "wigos_id": ["0-1-2-x", None, None]})
    found = with_oscar_wigos_id(stations, Settings(cache_disable=True), DWD_WIGOS_SCHEME).collect()
    assert found.columns == ["station_id", "wigos_id"]
    assert _wigos_ids(found) == {"00073": "0-1-2-x", "00091": "0-276-3-91", "00044": "0-276-3-44"}


def test_the_order_and_the_other_columns_of_the_stations_are_kept() -> None:
    """A left join in the order of the stations, with the columns they had and no helper left behind."""
    stations = pl.LazyFrame({"station_id": ["00091", "00003", "00073"], "name": ["a", "b", "c"]})
    found = with_oscar_wigos_id(stations, Settings(cache_disable=True), DWD_WIGOS_SCHEME).collect()
    assert found.columns == ["station_id", "name", "wigos_id"]
    assert found["station_id"].to_list() == ["00091", "00003", "00073"]
    assert found.schema["wigos_id"] == pl.String


def test_a_list_without_a_station_is_not_asked_about() -> None:
    """No station, no register read: the core gives an empty list its columns."""
    found = with_oscar_wigos_id(pl.LazyFrame(), Settings(cache_disable=True), DWD_WIGOS_SCHEME)
    assert found.collect().is_empty()


# when the register cannot be read


def _fail_with(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def fail(*_args: object) -> list[str]:
        raise error

    monkeypatch.setattr(oscar, "read_register", fail)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NoInternetError("No internet connection: could not reach oscar.wmo.int"), id="no-connection"),
        pytest.param(DownloadError(oscar_url("DEU"), "503, message='Service Unavailable'"), id="bad-answer"),
        pytest.param(OscarRegisterError("DEU", "it has 2 pages"), id="not-the-register"),
    ],
)
def test_a_register_that_cannot_be_read_leaves_the_stations_as_they_were_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    """The list is the answer and the id an addition: the stations come back as without OSCAR, with a warning."""
    _fail_with(monkeypatch, error)
    stations = pl.LazyFrame({"station_id": ["00073", "00091"], "wigos_id": ["0-1-2-x", None]})
    begin_response()
    with caplog.at_level(logging.WARNING, logger=oscar.log.name):
        found = with_oscar_wigos_id(stations, Settings(cache_disable=True), DWD_WIGOS_SCHEME).collect()
    assert _wigos_ids(found) == {"00073": "0-1-2-x", "00091": None}
    (warning,) = [w for w in recorded_warnings() if w["code"] == WIGOS_IDS_UNAVAILABLE]
    assert "dwd/observation" in warning["message"]
    assert [record.response_warning for record in caplog.records if hasattr(record, "response_warning")] == [
        WIGOS_IDS_UNAVAILABLE
    ]


def test_without_a_wigos_id_column_the_unreadable_register_leaves_a_null_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The column is there where the provider's list has none, as it is for the core."""
    _fail_with(monkeypatch, NoInternetError("no"))
    found = with_oscar_wigos_id(
        pl.LazyFrame({"station_id": ["00073"]}), Settings(cache_disable=True), DWD_WIGOS_SCHEME
    ).collect()
    assert found.to_dict(as_series=False) == {"station_id": ["00073"], "wigos_id": [None]}
    assert found.schema["wigos_id"] == pl.String


def test_a_rate_limit_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 is never let go: the next request meets it too."""
    _fail_with(monkeypatch, ProviderRateLimitError(oscar_url("DEU"), "limited", 7))
    with pytest.raises(ProviderRateLimitError):
        with_oscar_wigos_id(pl.LazyFrame({"station_id": ["00073"]}), Settings(cache_disable=True), DWD_WIGOS_SCHEME)


# what the page has to be


def _one_station(**changes: object) -> dict:
    station: dict = {"id": 1, "name": "X", "wigosStationIdentifiers": [{"wigosStationIdentifier": "0-276-3-73"}]}
    return {**station, **changes}


@pytest.mark.parametrize(
    ("content", "error", "reason"),
    [
        pytest.param(b"<html><body>Please wait</body></html>", DownloadError, "not JSON", id="html-page"),
        pytest.param(b"", DownloadError, "not JSON", id="empty"),
        pytest.param(b"[]", OscarRegisterError, "stationSearchResults", id="a-list"),
        pytest.param(b'{"error": "unknown territory"}', OscarRegisterError, "stationSearchResults", id="an-error"),
        pytest.param(register("DEU", pageCount=2), OscarRegisterError, "2 pages", id="more-than-a-page"),
        pytest.param(register("DEU", totalCount=2495), OscarRegisterError, "2495 stations", id="cut-short"),
        pytest.param(register("DEU", stations=[]), OscarRegisterError, "has a WIGOS id", id="no-station"),
        pytest.param(
            register("DEU", stations=[_one_station(wigosStationIdentifiers=[])]),
            OscarRegisterError,
            "has a WIGOS id",
            id="no-id",
        ),
        pytest.param(
            register("DEU", stations=[_one_station(wigosStationIdentifiers=[{"wigosStationIdentifier": "junk"}])]),
            OscarRegisterError,
            "has a WIGOS id",
            id="only-junk",
        ),
    ],
)
def test_a_page_that_is_not_the_register_of_the_country_raises(content: bytes, error: type, reason: str) -> None:
    """Never an empty register: an HTML page, a JSON error, a second page, a cut-short list or no id is an error."""
    with pytest.raises(error, match=reason) as raised:
        parse_wigos_ids(content, "DEU")
    assert OSCAR_SEARCH_URL in str(raised.value)
    assert isinstance(raised.value, DownloadError | MetaFileFormatError)


def test_the_register_error_is_copied_as_it_is() -> None:
    """It is an `UpstreamError` that names the address, and pickles and copies without being worded twice."""
    import copy  # noqa: PLC0415
    import pickle  # noqa: PLC0415

    error = OscarRegisterError("DEU", "it has 2 pages")
    for clone in (copy.copy(error), pickle.loads(pickle.dumps(error))):  # noqa: S301
        assert str(clone) == str(error)
        assert oscar_url("DEU") in str(clone)


# the real download and cache, against a server of this machine


class _Oscar:
    """A server that answers the search with the body set for it, and counts the requests."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.body = b""
        self.status = 200
        self.hits = 0
        self.queries: list[str] = []


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Oscar]:
    """Serve OSCAR's search from this machine, and have the reader ask it through the real download and cache."""
    holder: dict[str, _Oscar] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state = holder["state"]
            state.hits += 1
            state.queries.append(self.path)
            self.send_response(state.status)
            self.send_header("Content-Type", "text/html" if state.body.startswith(b"<") else "application/json")
            self.send_header("Content-Length", str(len(state.body)))
            self.end_headers()
            self.wfile.write(state.body)

        def log_message(self, *args: object) -> None:
            """Say nothing."""

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state = _Oscar(f"http://127.0.0.1:{httpd.server_address[1]}")
    holder["state"] = state
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(oscar, "OSCAR_SEARCH_URL", f"{state.base}/surface/rest/api/search/station")
    monkeypatch.setattr(oscar, "download_file", download_file)
    yield state
    httpd.shutdown()
    httpd.server_close()


def test_the_register_is_asked_for_by_its_territory_only_and_kept_a_week(server: _Oscar, tmp_path: Path) -> None:
    """One request for a country, with `territoryName` and no other parameter (any other returns the whole register)."""
    server.body = register("FIN")
    settings = Settings(cache_dir=tmp_path)
    assert "0-246-0-101520" in read_register("FIN", settings)
    oscar.forget_registers()
    assert "0-246-0-101520" in read_register("FIN", settings)  # from the cache: the process forgot it
    assert server.hits == 1
    assert server.queries == ["/surface/rest/api/search/station?territoryName=FIN"]
    assert oscar.OSCAR_EXPIRY is CacheExpiry.ONE_WEEK


@pytest.mark.parametrize(
    ("body", "status"),
    [
        pytest.param(b"<html><body>Merci de votre patience</body></html>", 200, id="waiting-page"),
        pytest.param(b'{"error": "unavailable"}', 200, id="json-error-in-a-200"),
        pytest.param(register("FIN", pageCount=2), 200, id="more-than-a-page"),
        pytest.param(b"<html>Bad gateway</html>", 502, id="a-502"),
    ],
)
def test_a_page_that_is_no_register_is_raised_and_not_kept(
    server: _Oscar, tmp_path: Path, body: bytes, status: int
) -> None:
    """The cache holds a 200 for the week, so the page is dropped before it is raised: the next call asks again."""
    server.body, server.status = body, status
    settings = Settings(cache_dir=tmp_path)
    with pytest.raises((DownloadError, OscarRegisterError)):
        read_register("FIN", settings)
    assert server.hits >= 1
    asked = server.hits

    oscar.forget_registers()  # the process's memory of the failure is another rule, below
    server.body, server.status = register("FIN"), 200
    assert "0-246-0-101520" in read_register("FIN", settings)
    assert server.hits == asked + 1


def test_a_failure_is_remembered_for_five_minutes_and_a_good_register_for_a_day(
    server: _Oscar, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A register that is down is not asked for by every request, and is asked for again soon after it is up."""
    now = [1000.0]
    monkeypatch.setattr(oscar, "_clock", lambda: now[0])
    server.body = b"<html>Wartung</html>"
    settings = Settings(cache_dir=tmp_path)
    for _ in range(3):
        with pytest.raises(DownloadError):
            read_register("FIN", settings)
    assert server.hits == 1
    now[0] += oscar.OSCAR_FAILURE_MEMORY + 1
    server.body = register("FIN")
    assert "0-246-0-101520" in read_register("FIN", settings)
    assert server.hits == 2
    now[0] += oscar.OSCAR_MEMORY - 1
    read_register("FIN", settings)
    assert server.hits == 2
    now[0] += 2  # a day on: the process reads it again, from the cache, which keeps it for the week
    read_register("FIN", settings)
    assert server.hits == 2


def test_the_station_lists_through_the_real_download_carry_the_ids(server: _Oscar, tmp_path: Path) -> None:
    """The whole way: the page of the server, the cache, the reader and the join."""
    server.body = register("DNK")
    stations = pl.LazyFrame({"station_id": ["06126", "99999"]})
    found = with_oscar_wigos_id(stations, Settings(cache_dir=tmp_path), DMI_WIGOS_SCHEME)
    assert _wigos_ids(found) == {"06126": "0-208-0-06126", "99999": None}


def test_a_territory_the_stub_has_no_rows_of_is_not_answered_by_it() -> None:
    """Every other address, and a country that is none of the three, goes where it went."""
    from tests.model.oscar_rows import served  # noqa: PLC0415

    assert served("https://oscar.wmo.int/surface/rest/api/search/station?territoryName=POL") is None
    assert served("https://example.org/") is None
    file = served(oscar_url("DNK"))
    assert isinstance(file, File)
    assert isinstance(file.content, BytesIO)


# a scheme of more than one territory (GH-4074)


def test_the_stations_of_greenland_are_in_the_register_of_its_own_territory() -> None:
    """OSCAR files Pituffik `0-208-0-04202` under `GRL`, not `DNK`: DMI's scheme reads both registers."""
    settings = Settings(cache_disable=True)
    assert DMI_WIGOS_SCHEME.territories == ("DNK", "GRL")
    stations = pl.LazyFrame({"station_id": ["04202", "04205", "04250", "06126", "04999"]})
    assert _wigos_ids(with_oscar_wigos_id(stations, settings, DMI_WIGOS_SCHEME)) == {
        "04202": "0-208-0-04202",
        "04205": "0-208-0-04205",
        "04250": "0-208-0-04250",
        "06126": "0-208-0-06126",
        "04999": None,
    }
    assert "0-208-0-04202" not in parse_wigos_ids(register("DNK"), "DNK")


def test_one_territory_that_cannot_be_read_is_the_whole_register_that_cannot(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The stations of Denmark get no id from a register of Denmark alone: a list that is right in part is no list."""

    def read(territory: str, _settings: object) -> list[str]:
        if territory == "GRL":
            raise DownloadError(oscar_url("GRL"), "503, message='Service Unavailable'")
        return parse_wigos_ids(register("DNK"), "DNK")

    monkeypatch.setattr(oscar, "read_register", read)
    begin_response()
    with caplog.at_level(logging.WARNING, logger=oscar.log.name):
        found = with_oscar_wigos_id(
            pl.LazyFrame({"station_id": ["06126", "04202"]}), Settings(cache_disable=True), DMI_WIGOS_SCHEME
        )
    assert _wigos_ids(found) == {"06126": None, "04202": None}
    (warning,) = [w for w in recorded_warnings() if w["code"] == WIGOS_IDS_UNAVAILABLE]
    assert "dmi/observation" in warning["message"]


def test_the_registers_are_joined_before_the_rule_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two ids for one local part are two wherever they are listed: one in each territory is as ambiguous as in one."""
    scheme = NationalWigosScheme(
        territories=("AAA", "BBB"), issuer=208, issue_numbers=frozenset({0, 1}), provider="x", strip_zeros=False
    )
    registers = {"AAA": ["0-208-0-5", "0-208-0-6"], "BBB": ["0-208-1-5", "0-208-0-6", "0-208-0-7"]}
    monkeypatch.setattr(oscar, "read_register", lambda territory, _settings: registers[territory])
    found = with_oscar_wigos_id(pl.LazyFrame({"station_id": ["5", "6", "7"]}), Settings(cache_disable=True), scheme)
    # `0-208-0-6` is in both registers and is one id
    assert _wigos_ids(found) == {"5": None, "6": "0-208-0-6", "7": "0-208-0-7"}


def test_the_warning_of_an_id_listed_twice_is_made_once_for_each_time_the_register_is_read(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Every `_all` of a stations request asks, and the log says it once, not for each."""
    scheme = NationalWigosScheme(territories=("AAA",), issuer=208, issue_numbers=frozenset({0, 1}), provider="x")
    monkeypatch.setattr(oscar, "read_register", lambda *_args: ["0-208-0-5", "0-208-1-5", "0-208-0-6"])
    settings = Settings(cache_disable=True)
    with caplog.at_level(logging.WARNING, logger=oscar.log.name):
        for _ in range(3):
            found = with_oscar_wigos_id(pl.LazyFrame({"station_id": ["5", "6"]}), settings, scheme)
            assert _wigos_ids(found) == {"5": None, "6": "0-208-0-6"}
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == 1


# how the server is asked, and waited for (GH-4074)


def test_the_register_is_asked_once_and_waited_for_ten_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A host that drops connections costs a request ten seconds, not the minute of two attempts of 30 s."""
    asked: list[dict] = []

    def download(**kwargs: object) -> File:
        asked.append(kwargs)
        return File(url=str(kwargs["url"]), content=BytesIO(register("FIN")), status=200)

    monkeypatch.setattr(oscar, "download_file", download)
    read_register("FIN", Settings(cache_disable=True))
    (kwargs,) = asked
    assert kwargs["attempts"] == 1
    assert kwargs["client_kwargs"]["timeout"] == oscar.OSCAR_TIMEOUT == 10
    assert kwargs["ttl"] is CacheExpiry.ONE_WEEK


def test_the_threads_that_ask_together_share_one_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first read of a host that is slow or down is waited for by one thread; the others get what it left."""
    inside = threading.Event()
    release = threading.Event()
    downloads: list[str] = []

    def slow_download(**kwargs: object) -> File:
        downloads.append(str(kwargs["url"]))
        inside.set()
        assert release.wait(10)
        return File(url=str(kwargs["url"]), content=BytesIO(register("FIN")), status=200)

    monkeypatch.setattr(oscar, "download_file", slow_download)
    settings = Settings(cache_disable=True)
    results: list[list[str]] = []
    threads = [threading.Thread(target=lambda: results.append(read_register("FIN", settings))) for _ in range(6)]
    for thread in threads:
        thread.start()
    assert inside.wait(10)
    release.set()
    for thread in threads:
        thread.join(10)
    assert len(downloads) == 1
    assert len(results) == 6
    assert all("0-246-0-101520" in ids for ids in results)


def test_the_threads_that_ask_together_of_a_host_that_is_down_share_its_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One wait for the host, not one for each thread in turn."""
    inside = threading.Event()
    release = threading.Event()
    downloads: list[str] = []

    def down(**kwargs: object) -> File:
        downloads.append(str(kwargs["url"]))
        inside.set()
        assert release.wait(10)
        return File(url=str(kwargs["url"]), content=TimeoutError(), status=0)

    monkeypatch.setattr(oscar, "download_file", down)
    settings = Settings(cache_disable=True)
    errors: list[BaseException] = []

    def ask() -> None:
        try:
            read_register("FIN", settings)
        except DownloadError as error:
            errors.append(error)

    threads = [threading.Thread(target=ask) for _ in range(5)]
    for thread in threads:
        thread.start()
    assert inside.wait(10)
    release.set()
    for thread in threads:
        thread.join(10)
    assert len(downloads) == 1
    assert len(errors) == 5


def test_a_rate_limit_of_oscar_is_raised_as_oscars_and_not_remembered(server: _Oscar, tmp_path: Path) -> None:
    """A 429 is never let go; it names WMO OSCAR as the one that limits, and the next read asks again."""
    server.status, server.body = 429, b"Too many requests"
    settings = Settings(cache_dir=tmp_path)
    for expected in (1, 2):
        with pytest.raises(ProviderRateLimitError) as raised:
            read_register("FIN", settings)
        assert "WMO OSCAR" in raised.value.reason
        assert "provider" not in raised.value.reason
        assert raised.value.retry_after is not None
        assert server.hits == expected
    server.status, server.body = 200, register("FIN")
    assert "0-246-0-101520" in read_register("FIN", settings)
    assert server.hits == 3


def test_a_rate_limit_through_the_stations_is_raised_not_turned_into_a_warning(server: _Oscar, tmp_path: Path) -> None:
    """The repository's rule: a 429 fails the request, where any other failure of the register is a warning."""
    server.status, server.body = 429, b"Too many requests"
    with pytest.raises(ProviderRateLimitError):
        with_oscar_wigos_id(pl.LazyFrame({"station_id": ["100971"]}), Settings(cache_dir=tmp_path), FMI_WIGOS_SCHEME)


# the live register


@pytest.mark.remote
@pytest.mark.parametrize(
    ("territory", "scheme", "local", "expected"),
    [
        ("DEU", DWD_WIGOS_SCHEME, "73", "0-276-3-73"),  # Aldersbach-Kramersepp
        ("FIN", FMI_WIGOS_SCHEME, "101520", "0-246-0-101520"),  # Ahtari Myllymäki
        ("DNK", DMI_WIGOS_SCHEME, "06126", "0-208-0-06126"),  # Aarslev
    ],
)
def test_the_live_register_has_the_ids_of_the_issue(
    tmp_path: Path, territory: str, scheme: NationalWigosScheme, local: str, expected: str
) -> None:
    """Read 2026-11-19: Germany 372 numeric ids of 374, Finland 288, Denmark 86; a register moves slowly."""
    ids = read_register(territory, Settings(cache_dir=tmp_path))
    found = dict(wigos_ids_of_scheme(ids, scheme).iter_rows())
    assert found[local] == expected
    assert len(found) >= {"DEU": 300, "FIN": 200, "DNK": 60}[territory]
    assert all(wigos_id.startswith(f"0-{scheme.issuer}-") for wigos_id in found.values())
