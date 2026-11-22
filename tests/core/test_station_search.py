# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""One WMO number, WIGOS identifier or ICAO code at every provider that has it (GH-4075).

The station lists are stood in for by rows of the test's own (`station_search_stubs.serve`), so the selection, the
equivalence of the ids, the networks that fail and the order of the answer are held with no network; the readers of
the real lists, and the reading of GHCN's list without its inventory, are held against the stubs of their catalogues.
"""

from __future__ import annotations

import threading
import time
from io import BytesIO
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.core.station_search_stubs import KEYED, serve, station
from tests.provider.station_catalogue_stubs import _meteoswiss
from wetterdienst import Settings, Wetterdienst
from wetterdienst.core import station_search
from wetterdienst.core.station_search import COLUMNS, MAX_FILE_CHECKS, MAX_WORKERS, find_stations_by_id
from wetterdienst.exceptions import (
    CredentialMissingError,
    DownloadError,
    NoInternetError,
    ProviderRateLimitError,
    RequestError,
    UpstreamError,
)
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.provider.noaa.ghcn import api as ghcn_api
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from pathlib import Path

#: every network that declares a list, in the order of the registry, which is the order `searched` has
DECLARED = [
    f"{provider}/{network}"
    for provider, networks in Wetterdienst.registry.items()
    for network in networks
    if not Wetterdienst.is_standalone(provider, network)
    and Wetterdienst.resolve(provider, network).metadata.station_id_list is not None
]

#: Hamburg and Berlin as three providers list them
HAMBURG = {
    "dwd/observation": [station("01975", "Hamburg-Fuhlsbüttel", wmo_id="10147")],
    "dwd/mosmix": [station("10147", "HAMBURG-FU.", wmo_id="10147", icao_id="EDDH")],
    "noaa/ghcn": [station("GM000010147", "HAMBURG FUHLSBUETTEL", wmo_id="10147")],
}
BERLIN = {
    "dwd/observation": [station("00403", "Berlin-Dahlem (FU)", wmo_id="10381")],
    "dwd/mosmix": [station("10381", "BERLIN-DAHLEM", wmo_id="10381")],
    "noaa/ghcn": [station("GM000003319", "BERLIN-DAHLEM", wmo_id="10381")],
}


def _rows(result: station_search.StationIdSearchResult) -> list[tuple[str, str, str, str]]:
    """Give (network, station id, matched_by, match) of each row of an answer."""
    return [
        (f"{row['provider']}/{row['network']}", row["station_id"], row["matched_by"], row["match"])
        for row in result.df.iter_rows(named=True)
    ]


# --- the selection -----------------------------------------------------------------------------------------------


def test_a_wmo_number_is_found_at_every_network_that_lists_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """One row for each station, in the columns of the answer, naming the list it comes from and how it matched."""
    serve(monkeypatch, {key: [*BERLIN.get(key, []), *HAMBURG.get(key, [])] for key in {*BERLIN, *HAMBURG}})

    result = find_stations_by_id(wmo_id="10381")

    assert result.df.columns == COLUMNS
    assert _rows(result) == [
        ("dwd/mosmix", "10381", "wmo_id", "direct"),
        ("dwd/observation", "00403", "wmo_id", "direct"),
        ("noaa/ghcn", "GM000003319", "wmo_id", "direct"),
    ]
    row = result.df.filter(pl.col("provider").eq("dwd") & pl.col("network").eq("observation")).row(0, named=True)
    assert row == {
        "provider": "dwd",
        "network": "observation",
        "resolution": "daily",
        "dataset": "climate_summary",
        "station_id": "00403",
        "name": "Berlin-Dahlem (FU)",
        "latitude": 53.63,
        "longitude": 9.99,
        "elevation": 11.0,
        "wmo_id": "10381",
        "wigos_id": None,
        "icao_id": None,
        "matched_by": "wmo_id",
        "match": "direct",
    }
    # the other station of the lists is no row
    assert "01975" not in result.df["station_id"].to_list()


def test_the_ids_are_read_in_the_notation_of_their_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """A number or a short text is padded, an issuer's zeros are dropped, a code is upper case, and none is repeated."""
    serve(monkeypatch, {"dwd/observation": [station("00011", wmo_id="01001")]})

    result = find_stations_by_id(wmo_id=[1001, "1001", "01001"], wigos_id="0-056-101-01002", icao_id="eddh")

    assert result.request == {"wmo_id": ["01001"], "wigos_id": ["0-56-101-01002"], "icao_id": ["EDDH"]}
    assert _rows(result) == [("dwd/observation", "00011", "wmo_id", "direct")]


def test_a_wmo_number_on_several_stations_of_a_network_is_every_one_of_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """GHCN lists up to four stations under one number, so the answer is a list."""
    ghcn = [station(f"GM00000{index}", f"BERLIN {index}", wmo_id="10381") for index in range(4)]
    serve(monkeypatch, {"noaa/ghcn": ghcn, "dwd/mosmix": BERLIN["dwd/mosmix"]})

    result = find_stations_by_id(wmo_id="10381")

    assert [row[1] for row in _rows(result) if row[0] == "noaa/ghcn"] == [f"GM00000{index}" for index in range(4)]
    assert result.df.height == 5


def test_a_station_a_list_repeats_is_one_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same station id twice in one network's list is told once; two stations with one code are both told."""
    twice = station("10147", "HAMBURG-FU.", wmo_id="10147", icao_id="EDDH")
    serve(monkeypatch, {"dwd/mosmix": [twice, twice, station("10148", "HAMBURG-FU. B", icao_id="EDDH")]})

    result = find_stations_by_id(icao_id="EDDH")

    assert _rows(result) == [("dwd/mosmix", "10147", "icao_id", "direct"), ("dwd/mosmix", "10148", "icao_id", "direct")]


def test_a_search_that_finds_no_station_is_an_answer_with_the_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """No row is not an error: the frame is empty, has the columns of the answer, and every network is told as asked."""
    serve(monkeypatch, HAMBURG)

    result = find_stations_by_id(wmo_id="99999")

    assert result.df.is_empty()
    assert result.df.columns == COLUMNS
    assert result.warnings == []
    assert result.also_searched == {"wmo_id": [], "wigos_id": ["0-20000-0-99999"]}


def test_a_station_list_without_an_id_is_no_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station that carries none of the three ids cannot be found by one, whatever its name says."""
    serve(monkeypatch, {"dwd/observation": [station("00011", "Hamburg")]})

    assert find_stations_by_id(wmo_id="10147").df.is_empty()


# --- the ids are equivalent --------------------------------------------------------------------------------------


def test_a_wigos_id_of_wmos_issuer_finds_the_station_that_has_the_wmo_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """`0-20000-0-10381` is the number `10381`: the station that lists only the number matches, by an equivalence."""
    serve(monkeypatch, BERLIN)

    result = find_stations_by_id(wigos_id="0-20000-0-10381")

    assert _rows(result) == [
        ("dwd/mosmix", "10381", "wmo_id", "equivalent"),
        ("dwd/observation", "00403", "wmo_id", "equivalent"),
        ("noaa/ghcn", "GM000003319", "wmo_id", "equivalent"),
    ]
    assert result.also_searched == {"wmo_id": ["10381"], "wigos_id": []}


def test_a_wmo_number_finds_the_station_that_has_the_wigos_id_of_wmos_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The station that lists `0-20000-0-10381` and no number matches a search for `10381`, and its row says so."""
    serve(
        monkeypatch,
        {
            "chmi/observation": [station("11518", "Praha", wigos_id="0-20000-0-10381")],
            "dwd/mosmix": BERLIN["dwd/mosmix"],
        },
    )

    result = find_stations_by_id(wmo_id="10381")

    assert _rows(result) == [
        ("chmi/observation", "11518", "wigos_id", "equivalent"),
        ("dwd/mosmix", "10381", "wmo_id", "direct"),
    ]
    assert result.also_searched == {"wmo_id": [], "wigos_id": ["0-20000-0-10381"]}


def test_a_wigos_id_of_a_national_issuer_is_no_wmo_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """`0-756-0-06735` and `0-20000-0-06735` differ: the first is the Swiss scheme's own, however its local id looks."""
    serve(
        monkeypatch,
        {
            "meteoswiss/observation": [
                station("ABO", "Adelboden", wmo_id="06735", wigos_id="0-20000-0-06735"),
                station("BIA", "Biaschina", wigos_id="0-756-0-BIA"),
                station("XXX", "Elsewhere", wigos_id="0-756-0-06735"),
            ]
        },
    )

    national = find_stations_by_id(wigos_id="0-756-0-06735")
    wmo = find_stations_by_id(wmo_id="06735")

    assert _rows(national) == [("meteoswiss/observation", "XXX", "wigos_id", "direct")]
    assert national.also_searched == {"wmo_id": [], "wigos_id": []}
    assert _rows(wmo) == [("meteoswiss/observation", "ABO", "wmo_id", "direct")]


def test_a_direct_match_is_told_before_an_equivalent_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station that has the id asked for is `direct` whatever else it has, and the three ids go in a fixed order."""
    serve(
        monkeypatch,
        {
            "fmi/observation": [
                station("100907", "Marianhamina", wmo_id="02970", wigos_id="0-20000-0-02970", icao_id="EFMA")
            ]
        },
    )

    assert _rows(find_stations_by_id(wmo_id="02970", wigos_id="0-20000-0-02970", icao_id="EFMA")) == [
        ("fmi/observation", "100907", "wmo_id", "direct")
    ]
    assert _rows(find_stations_by_id(wigos_id="0-20000-0-02970", icao_id="EFMA")) == [
        ("fmi/observation", "100907", "wigos_id", "direct")
    ]
    assert _rows(find_stations_by_id(icao_id="EFMA")) == [("fmi/observation", "100907", "icao_id", "direct")]
    assert _rows(find_stations_by_id(wigos_id="0-20000-0-02970")) == [
        ("fmi/observation", "100907", "wigos_id", "direct")
    ]


def test_an_icao_code_also_searches_the_wmo_numbers_of_its_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    """`EDDH` finds the stations that list the code, and those that list Hamburg's number and no code."""
    serve(monkeypatch, {**HAMBURG, "dwd/poi": [station("10147", "HAMBURG-FU.", wmo_id="10147", icao_id="EDDH")]})

    result = find_stations_by_id(icao_id="EDDH")

    assert _rows(result) == [
        ("dwd/mosmix", "10147", "icao_id", "direct"),
        ("dwd/observation", "01975", "wmo_id", "equivalent"),
        ("dwd/poi", "10147", "icao_id", "direct"),
        ("noaa/ghcn", "GM000010147", "wmo_id", "equivalent"),
    ]
    assert result.also_searched == {"wmo_id": ["10147"], "wigos_id": ["0-20000-0-10147"]}


def test_an_icao_hit_whose_number_is_only_in_its_wigos_id_expands_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """The WMO number of a hit is its `wmo_id`, or else the local id of its WIGOS identifier of WMO's issuer."""
    serve(
        monkeypatch,
        {
            "fmi/observation": [station("100907", "Marianhamina", wigos_id="0-20000-0-02970", icao_id="EFMA")],
            "dwd/mosmix": [station("02970", "MARIEHAMN", wmo_id="02970")],
        },
    )

    result = find_stations_by_id(icao_id="EFMA")

    assert _rows(result) == [
        ("dwd/mosmix", "02970", "wmo_id", "equivalent"),
        ("fmi/observation", "100907", "icao_id", "direct"),
    ]


def test_an_icao_hit_with_no_number_expands_to_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A code the lists hold at stations that have no WMO number finds those stations and no other."""
    serve(monkeypatch, {"dwd/mosmix": [station("EDXX", "A field", icao_id="EDXX")], "noaa/ghcn": BERLIN["noaa/ghcn"]})

    result = find_stations_by_id(icao_id="EDXX")

    assert _rows(result) == [("dwd/mosmix", "EDXX", "icao_id", "direct")]
    assert result.also_searched == {"wmo_id": [], "wigos_id": []}


def test_a_wmo_hit_does_not_search_its_icao_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only an ICAO code is expanded: a station of a list that has the code and no number is not found by the number."""
    serve(
        monkeypatch,
        {
            "dwd/mosmix": [station("10147", wmo_id="10147", icao_id="EDDH")],
            "fmi/observation": [station("EDDH-A", icao_id="EDDH")],
        },
    )

    assert _rows(find_stations_by_id(wmo_id="10147")) == [("dwd/mosmix", "10147", "wmo_id", "direct")]


# --- the networks ------------------------------------------------------------------------------------------------


def test_every_declared_network_is_asked_and_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eighteen networks, once each and in the order of the registry, each named with its list and its columns."""
    asked = serve(monkeypatch, HAMBURG)

    result = find_stations_by_id(wmo_id="10147")

    assert sorted(asked) == sorted(DECLARED)
    assert [f"{n.provider}/{n.network}" for n in result.searched] == DECLARED
    assert len(DECLARED) == 18
    by_name = {f"{n.provider}/{n.network}": n for n in result.searched}
    assert (by_name["dwd/observation"].resolution, by_name["dwd/observation"].dataset) == ("daily", "climate_summary")
    assert by_name["dwd/observation"].ids == ("wmo_id", "wigos_id")
    assert by_name["dwd/observation"].status == "searched"
    assert by_name["dwd/observation"].stations_with_ids == 1
    assert by_name["dwd/dmo"].stations_with_ids == 0


def test_the_networks_are_asked_concurrently_and_not_all_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reads overlap (a bounded pool), and no more than `MAX_WORKERS` of them are under way at a time."""
    serve(monkeypatch, HAMBURG)
    read = station_search._read_network  # noqa: SLF001
    lock = threading.Lock()
    active = {"now": 0, "most": 0}

    def slow(*args: Any) -> Any:  # noqa: ANN401
        with lock:
            active["now"] += 1
            active["most"] = max(active["most"], active["now"])
        time.sleep(0.05)
        with lock:
            active["now"] -= 1
        return read(*args)

    monkeypatch.setattr(station_search, "_read_network", slow)

    assert find_stations_by_id(wmo_id="10147").df.height == 3
    assert 1 < active["most"] <= MAX_WORKERS


def test_a_network_that_fails_is_a_warning_and_the_others_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The failure names the network and says why; the others are read all the same and their rows are in the answer."""
    serve(
        monkeypatch, {**BERLIN, "dmi/observation": NoInternetError("https://opendataapi.dmi.dk/ could not be reached")}
    )

    result = find_stations_by_id(wmo_id="10381")

    assert [row[0] for row in _rows(result)] == ["dwd/mosmix", "dwd/observation", "noaa/ghcn"]
    failed = next(n for n in result.searched if (n.provider, n.network) == ("dmi", "observation"))
    assert failed.status == "failed"
    assert failed.stations_with_ids is None
    assert failed.message is not None
    assert failed.message.startswith("NoInternetError: ")
    (warning,) = result.warnings
    assert warning["code"] == "network-failed"
    assert "dmi/observation" in warning["message"]
    assert "could not be reached" in warning["message"]


def test_every_failure_but_a_rate_limit_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider's error page, a defect of one reader: the network is left out, whichever exception it was."""
    serve(
        monkeypatch,
        {
            **HAMBURG,
            "chmi/observation": DownloadError("https://opendata.chmi.cz/x", "502"),
            "eccc/observation": ValueError("a reader that cannot read"),
        },
    )

    result = find_stations_by_id(wmo_id="10147")

    assert result.df.height == 3
    assert sorted(w["message"].split(" ")[0] for w in result.warnings) == ["chmi/observation", "eccc/observation"]
    assert {w["code"] for w in result.warnings} == {"network-failed"}


def test_a_defect_is_logged_with_its_traceback_and_told_without_its_text(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Only the failure of a provider or of the configuration is told by its message: a defect is the log's."""
    serve(
        monkeypatch,
        {
            **HAMBURG,
            "chmi/observation": DownloadError("https://opendata.chmi.cz/x", "502"),
            "eccc/observation": ValueError("/srv/secret/path.py line 3 is wrong"),
        },
    )

    with caplog.at_level("ERROR"):
        result = find_stations_by_id(wmo_id="10147")

    by_name = {f"{n.provider}/{n.network}": n for n in result.searched}
    assert by_name["chmi/observation"].message is not None
    assert by_name["chmi/observation"].message.startswith("DownloadError: ")
    assert by_name["eccc/observation"].message == "an unexpected error occurred; the server's log has it"
    assert "secret" not in str(result.warnings)
    assert "secret" not in str(result.searched)
    logged = [record for record in caplog.records if record.exc_info and "eccc/observation" in record.getMessage()]
    assert len(logged) == 1
    assert isinstance(logged[0].exc_info[1], ValueError)
    assert not [record for record in caplog.records if record.exc_info and "chmi" in record.getMessage()]


def test_when_every_network_that_was_asked_fails_the_search_is_an_upstream_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An outage is no answer of no station: the error names every network that failed, and not the keyed ones."""
    failures = {name: NoInternetError(f"https://{name}.example/ is down") for name in DECLARED if name not in KEYED}
    serve(monkeypatch, {**failures, **{name: CredentialMissingError("set WD_AUTH__X") for name in KEYED}})

    with pytest.raises(UpstreamError) as raised:
        find_stations_by_id(wmo_id="10147")

    message = str(raised.value)
    assert message.startswith(f"None of the {len(failures)} networks that were asked could be read")
    assert all(name in message for name in failures)
    assert not any(name in message for name in KEYED)


def test_one_network_that_answers_is_enough_to_have_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The others fail, and the one that answered says there is no such station: an answer, with the warnings."""
    failures = {name: NoInternetError(f"https://{name}.example/ is down") for name in DECLARED if name != "dwd/mosmix"}
    serve(monkeypatch, {**failures, "dwd/mosmix": []})

    result = find_stations_by_id(wmo_id="10147")

    assert result.df.is_empty()
    assert len(result.warnings) == len(failures)


def test_networks_that_are_only_not_configured_are_not_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """With nothing asked at all there is nothing that failed: an empty answer, and a warning for each network."""
    serve(monkeypatch, {name: CredentialMissingError("set WD_AUTH__X") for name in DECLARED})

    result = find_stations_by_id(wmo_id="10147")

    assert result.df.is_empty()
    assert {w["code"] for w in result.warnings} == {"network-not-configured"}
    assert len(result.warnings) == len(DECLARED)


def test_a_network_that_cannot_be_imported_is_in_searched_and_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Its declaration is not known, so it has no list; it is told as failed, in the place of the registry."""
    serve(monkeypatch, HAMBURG)
    resolve = Wetterdienst.resolve

    def broken(provider: str, network: str) -> type:
        if (provider, network) == ("dmi", "observation"):
            missing = "No module named 'missing_extra'"
            raise ModuleNotFoundError(missing, name="missing_extra")
        return resolve(provider, network)

    monkeypatch.setattr(Wetterdienst, "resolve", staticmethod(broken))

    result = find_stations_by_id(wmo_id="10147")

    names = [f"{n.provider}/{n.network}" for n in result.searched]
    assert names == DECLARED
    dmi = result.searched[names.index("dmi/observation")]
    assert (dmi.status, dmi.resolution, dmi.dataset, dmi.ids) == ("failed", None, None, ())
    assert dmi.message == "it cannot be imported on this server: the module 'missing_extra' is missing"
    assert [w["code"] for w in result.warnings] == ["network-failed"]
    assert "dmi/observation" in result.warnings[0]["message"]
    assert result.df.height == 3


def test_a_rate_limit_is_never_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 ends the search and is raised as it is (the repository's rule), and no answer is made of the others."""
    serve(monkeypatch, {**HAMBURG, "noaa/ghcn": ProviderRateLimitError("https://noaa-ghcn-pds.s3/", "rate limited", 7)})

    with pytest.raises(ProviderRateLimitError):
        find_stations_by_id(wmo_id="10147")


def test_a_network_that_needs_a_key_the_settings_lack_is_named_and_no_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """The three keyed networks are told as `not-configured`, with the setting to make, and the others answer."""
    serve(
        monkeypatch,
        {**HAMBURG, **{name: CredentialMissingError(f"{name} requires a key: set WD_AUTH__X") for name in KEYED}},
    )

    result = find_stations_by_id(wmo_id="10147")

    assert result.df.height == 3
    assert {w["code"] for w in result.warnings} == {"network-not-configured"}
    assert [w["message"].split(" ")[0] for w in result.warnings] == list(KEYED)
    assert all("WD_AUTH__X" in w["message"] for w in result.warnings)
    statuses = {f"{n.provider}/{n.network}": n.status for n in result.searched}
    assert [name for name, status in statuses.items() if status == "not-configured"] == list(KEYED)
    assert [name for name, status in statuses.items() if status == "searched"] == [
        n for n in DECLARED if n not in KEYED
    ]


def test_a_keyed_network_without_its_key_is_not_asked_of_the_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The real request refuses at its construction, before a request is made: no network is reached for it."""
    declared = Wetterdienst.resolve("aemet", "observation").metadata.station_id_list
    assert declared is not None
    monkeypatch.setattr(station_search, "_declared_lists", lambda: ([("aemet", "observation", declared)], []))
    # no key from the environment, nor from a `.env` of the working directory, which `Settings` merges into `auth={}`
    monkeypatch.delenv("WD_AUTH__AEMET", raising=False)
    monkeypatch.chdir(tmp_path)

    result = find_stations_by_id(wmo_id="08222", settings=Settings(cache_disable=True, auth={}))

    assert result.df.is_empty()
    assert [(n.status, w["code"]) for n, w in zip(result.searched, result.warnings, strict=True)] == [
        ("not-configured", "network-not-configured")
    ]
    assert "WD_AUTH__AEMET" in result.warnings[0]["message"]


def test_what_a_network_warns_of_while_it_reads_is_in_the_answer_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A warning of a list (the stationslexikon that could not be read) is the answer's, and told once."""
    note = {"code": "wmo-ids-unavailable", "message": "the stations of dwd/observation have no wmo_id"}
    serve(monkeypatch, HAMBURG, warnings={"dwd/observation": [note], "dwd/derived": [note]})

    result = find_stations_by_id(wmo_id="10147")

    assert result.warnings == [note]


def test_the_warnings_of_the_search_are_recorded_for_the_response_being_served(monkeypatch: pytest.MonkeyPatch) -> None:
    """A surface that began a record (`begin_response`) has them in it, for its headers and its block."""
    serve(monkeypatch, {"dmi/observation": DownloadError("https://opendataapi.dmi.dk/x", "503")})
    begin_response()

    find_stations_by_id(wmo_id="10147")

    assert [w["code"] for w in recorded_warnings()] == ["network-failed"]


# --- the request -------------------------------------------------------------------------------------------------


def test_a_search_names_an_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """No id is a request error, and no network is asked."""
    asked = serve(monkeypatch, HAMBURG)

    with pytest.raises(RequestError, match="at least one of wmo_id, wigos_id and icao_id"):
        find_stations_by_id()
    assert asked == []


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        pytest.param({"wmo_id": "abc"}, ValueError, "is no wmo_id", id="wmo-text"),
        pytest.param({"wmo_id": "123456"}, ValueError, "five digits", id="wmo-long"),
        pytest.param({"wmo_id": [10.5]}, TypeError, "has to be a text or a number", id="wmo-float"),
        pytest.param({"wmo_id": []}, ValueError, "names no id", id="wmo-empty"),
        pytest.param({"wigos_id": "10381"}, ValueError, "is no wigos_id", id="wigos"),
        pytest.param({"icao_id": "EDD"}, ValueError, "four letters", id="icao"),
    ],
)
def test_an_id_that_cannot_be_one_is_refused_before_anything_is_asked(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict, error: type[Exception], message: str
) -> None:
    """The notation of each column is the one of the filters of a request, with the same words."""
    asked = serve(monkeypatch, HAMBURG)

    with pytest.raises(error, match=message):
        find_stations_by_id(**kwargs)
    assert asked == []


# --- the readers of the real lists ---------------------------------------------------------------------------------


def _only(monkeypatch: pytest.MonkeyPatch, provider: str, network: str) -> None:
    declared = Wetterdienst.resolve(provider, network).metadata.station_id_list
    assert declared is not None
    monkeypatch.setattr(station_search, "_declared_lists", lambda: ([(provider, network, declared)], []))


def test_the_real_read_of_a_list_gives_the_stations_with_an_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """MeteoSwiss's catalogue through its own reader: the number where WMO's issuer is the WIGOS id's, the id as is."""
    _meteoswiss(monkeypatch)
    _only(monkeypatch, "meteoswiss", "observation")
    settings = Settings(cache_disable=True)

    wmo = find_stations_by_id(wmo_id="06735", settings=settings)
    wigos = find_stations_by_id(wigos_id="0-756-0-BIA", settings=settings)
    equivalent = find_stations_by_id(wigos_id="0-20000-0-06660", settings=settings)

    assert _rows(wmo) == [("meteoswiss/observation", "ABO", "wmo_id", "direct")]
    assert wmo.df.row(0, named=True)["wigos_id"] == "0-20000-0-06735"
    assert wmo.df.row(0, named=True)["resolution"] == "daily"
    assert _rows(wigos) == [("meteoswiss/observation", "BIA", "wigos_id", "direct")]
    assert _rows(equivalent) == [("meteoswiss/observation", "SMA", "wigos_id", "direct")]
    assert wmo.searched[0].stations_with_ids == 5


def _ghcn_stations_file(*rows: tuple[str, float, float, float, str, str]) -> str:
    """Write rows (id, latitude, longitude, elevation, name, WMO number) as `ghcnd-stations.txt` has them."""
    return "".join(
        f"{sid:<11} {lat:8.4f} {lon:9.4f} {elev:6.1f}    {name:<30}         {wmo}\n"
        for sid, lat, lon, elev, name, wmo in rows
    )


HAMBURG_ROW = ("GM000010147", 53.635, 9.99, 11.0, "HAMBURG FUHLSBUETTEL", "10147")
GEISENHEIM_ROW = ("GMM00010628", 49.9833, 7.95, 100.0, "GEISENHEIM", "10628")
# a station the inventory has no line for: the list of `stations` leaves it out
EBEE_ROW = ("CAN03010010", 54.2833, -112.9667, 664.0, "ABEE AGDM", "71285")
GHCN_STATIONS = _ghcn_stations_file(HAMBURG_ROW, GEISENHEIM_ROW, EBEE_ROW)
READING = b"GM000010147,20260101,TMAX,50,,,E,\n"


def _ghcn_downloads(
    monkeypatch: pytest.MonkeyPatch, *, without_file: tuple[str, ...], inventory: str | None
) -> list[str]:
    """Serve the list of GHCN's stations, a file for each station but those named, and the inventory only if given."""
    asked: list[str] = []

    def download_file(url: str, **_: object) -> File:
        asked.append(url)
        if "ghcnd-stations" in url:
            return File(url=url, content=BytesIO(GHCN_STATIONS.encode("utf8")), status=200)
        if "ghcnd-inventory" in url:
            if inventory is None:
                msg = "the lookup reads no inventory"
                raise AssertionError(msg)
            return File(url=url, content=BytesIO(inventory.encode("utf8")), status=200)
        if any(station in url for station in without_file):
            return File(url=url, content=FileNotFoundError(url), status=404)
        return File(url=url, content=BytesIO(READING), status=200)

    monkeypatch.setattr(ghcn_api, "download_file", download_file)
    return asked


def test_ghcn_is_read_without_its_inventory_and_the_list_of_stations_is_not_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lookup reads the stations file alone, and `all()` is what it was: no station without an inventory line."""
    _only(monkeypatch, "noaa", "ghcn")
    settings = Settings(cache_disable=True)
    asked = _ghcn_downloads(monkeypatch, without_file=("GMM00010628",), inventory=None)

    found = find_stations_by_id(wmo_id=[10147, 71285, 10628], settings=settings)

    # Geisenheim is in the stations file and has no file at NCEI or the mirror: no row, and no warning
    assert found.warnings == []
    assert _rows(found) == [
        ("noaa/ghcn", "CAN03010010", "wmo_id", "direct"),
        ("noaa/ghcn", "GM000010147", "wmo_id", "direct"),
    ]
    assert found.df["resolution"].unique().to_list() == ["daily"]
    assert not any("inventory" in url for url in asked)

    inventory = "GM000010147  53.6350    9.9900 TMAX 1891 2026\nGMM00010628  49.9833    7.9500 TMAX 1891 2026\n"
    _ghcn_downloads(monkeypatch, without_file=(), inventory=inventory)
    listed = NoaaGhcnRequest(parameters=[("daily", "data")], settings=settings).all().df

    assert listed["station_id"].to_list() == ["GM000010147", "GMM00010628"]
    assert listed["start_timestamp"].null_count() == 0


# --- the data file of a GHCN hit ----------------------------------------------------------------------------------


def _ghcn_hits(count: int) -> list[dict]:
    return [station(f"GM0000{index:05d}", f"STATION {index}", wmo_id="10628") for index in range(count)]


def test_a_ghcn_hit_that_has_no_data_file_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Geisenheim (WMO 10628) is listed with no file and is no row; Hamburg's file is there and its row stays."""
    served = serve(
        monkeypatch,
        {
            "noaa/ghcn": [
                station("GMM00010628", "GEISENHEIM", wmo_id="10628"),
                station("GM000010147", "HAMBURG FUHLSBUETTEL", wmo_id="10147"),
            ],
            "dwd/mosmix": [station("10628", "GEISENHEIM", wmo_id="10628")],
        },
        files={"GMM00010628": False},
    )

    result = find_stations_by_id(wmo_id=[10628, 10147])

    assert _rows(result) == [
        ("dwd/mosmix", "10628", "wmo_id", "direct"),
        ("noaa/ghcn", "GM000010147", "wmo_id", "direct"),
    ]
    assert result.warnings == []
    # only the hits of the network that asks are checked
    assert sorted(served.checked) == ["GM000010147", "GMM00010628"]


def test_a_ghcn_check_that_cannot_be_made_keeps_the_row_and_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    """An outage is no file that is not there: the row stays, and the warning names the station and why."""
    serve(
        monkeypatch,
        {"noaa/ghcn": [station("GMM00010628", "GEISENHEIM", wmo_id="10628"), station("GM000010147", wmo_id="10147")]},
        files={"GMM00010628": NoInternetError("https://www.ncei.noaa.gov/ is down")},
    )

    result = find_stations_by_id(wmo_id=[10628, 10147])

    assert [row[1] for row in _rows(result)] == ["GM000010147", "GMM00010628"]
    (warning,) = result.warnings
    assert warning["code"] == "station-file-unchecked"
    assert warning["stations"] == ["GMM00010628"]
    assert "GMM00010628" in warning["message"]
    assert "NoInternetError" in warning["message"]
    assert "stays in the answer" in warning["message"]


def test_a_defect_in_a_check_is_told_without_its_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """As for a network: a bug keeps the row, is logged, and is not repeated in the answer."""
    serve(
        monkeypatch,
        {"noaa/ghcn": [station("GMM00010628", wmo_id="10628")]},
        files={"GMM00010628": KeyError("/srv/secret")},
    )

    result = find_stations_by_id(wmo_id=10628)

    assert result.df.height == 1
    assert "secret" not in result.warnings[0]["message"]
    assert "unexpected error" in result.warnings[0]["message"]


def test_a_rate_limit_of_a_check_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 is never a row kept with a warning."""
    serve(
        monkeypatch,
        {"noaa/ghcn": [station("GMM00010628", wmo_id="10628")]},
        files={"GMM00010628": ProviderRateLimitError("https://x/", "rate limited", 7)},
    )

    with pytest.raises(ProviderRateLimitError):
        find_stations_by_id(wmo_id=10628)


def test_the_checks_are_bounded_and_the_hits_beyond_stay_with_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """At most `MAX_FILE_CHECKS` requests for a network; the others are kept, and named."""
    served = serve(monkeypatch, {"noaa/ghcn": _ghcn_hits(MAX_FILE_CHECKS + 2)})

    result = find_stations_by_id(wmo_id=10628)

    assert len(served.checked) == MAX_FILE_CHECKS
    assert result.df.height == MAX_FILE_CHECKS + 2
    (warning,) = result.warnings
    assert warning["code"] == "station-file-unchecked"
    assert warning["stations"] == [f"GM0000{index:05d}" for index in range(MAX_FILE_CHECKS, MAX_FILE_CHECKS + 2)]


# --- a station a list repeats, and what a search also looked for --------------------------------------------------


def test_a_station_a_list_repeats_is_told_by_its_strongest_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """The row that matches by an equivalence is first in the list, and the one that matches directly is the row."""
    serve(
        monkeypatch,
        {
            "chmi/observation": [
                station("11518", "Praha", wigos_id="0-20000-0-10381"),
                station("11518", "Praha", wmo_id="10381", wigos_id="0-203-0-11518"),
                station("11518", "Praha", icao_id="LKPR"),
            ]
        },
    )

    assert _rows(find_stations_by_id(wmo_id="10381", icao_id="LKPR")) == [
        ("chmi/observation", "11518", "wmo_id", "direct")
    ]
    assert _rows(find_stations_by_id(icao_id="LKPR", wigos_id="0-20000-0-10381")) == [
        ("chmi/observation", "11518", "wigos_id", "direct")
    ]
    assert _rows(find_stations_by_id(wmo_id="10381")) == [("chmi/observation", "11518", "wmo_id", "direct")]
    assert _rows(find_stations_by_id(icao_id="LKPR")) == [("chmi/observation", "11518", "icao_id", "direct")]


def test_what_a_search_also_looked_for_does_not_depend_on_a_list_answering(monkeypatch: pytest.MonkeyPatch) -> None:
    """The equivalents of the ids given are the request's: the same with no station at all."""
    serve(monkeypatch, {})

    by_wmo = find_stations_by_id(wmo_id="10381")
    by_wigos = find_stations_by_id(wigos_id="0-20000-0-10381")
    by_icao = find_stations_by_id(icao_id="EDDH")

    assert by_wmo.also_searched == {"wmo_id": [], "wigos_id": ["0-20000-0-10381"]}
    assert by_wigos.also_searched == {"wmo_id": ["10381"], "wigos_id": []}
    assert by_icao.also_searched == {"wmo_id": [], "wigos_id": []}
    serve(monkeypatch, HAMBURG)
    assert find_stations_by_id(wmo_id="10381").also_searched == by_wmo.also_searched
    assert find_stations_by_id(wigos_id="0-20000-0-10381").also_searched == by_wigos.also_searched
