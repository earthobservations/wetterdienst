# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A history of `dwd/observation` whose station lookup meets a directory that came back empty (GH-3819).

The lookup lists the `historical` directory of a dataset (the dataset's own directory for the solar datasets, the
`meta_data` directory of the 1 minute precipitation) before the history is read, and an empty listing raised a
`FileNotFoundError` there, which the REST API answered with a 500 and the command line with a traceback. For a
history it is now the `file-skipped` warning of #3816, on a 200: the answer is partial, and says so. `stations` and
`values` keep failing as they did.

The listings are a stub of DWD's server (every directory lists one station, 00044, and its description; the ones a test
names are empty), so nothing here reaches the network.
"""

from __future__ import annotations

import copy
import functools
import http.server
import io
import json
import logging
import pickle
import threading
import zipfile
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.observation import DwdObservationRequest, api, fileindex, metaindex
from wetterdienst.provider.dwd.observation.fileindex import EmptyListingError
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.network import File, list_remote_files_fsspec
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
_DESCRIPTION = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "---------- ------\r\n"
    "00044 20070401 20261105            44     52.9336    8.2370 Großenkneten                             "
    "Niedersachsen                            Frei\r\n"
)
_DESCRIPTION_URBAN = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "----------\r\n"
    "00044 20230101 20261105 44 52.9336 8.2370 Grossenkneten Niedersachsen\r\n"
)
_HISTORY_FILES = {
    "Metadaten_Stationsname_Betreibername_00044.txt": (
        "Stations_ID;Stationsname;Von_Datum;Bis_Datum\n"
        "    44;Grossenkneten;20070401;\n"
        "\n"
        "Stations_ID;Betreibername;Von_Datum;Bis_Datum\n"
        "    44;DWD;20070401;\n"
        "generiert: 17.06.2026 --  Deutscher Wetterdienst  --\n"
    ),
}

#: the dataset, and the directory (below `observations_germany/`) whose listing is empty, for each case of the issue
_CASES = [
    pytest.param("monthly/climate_summary", "climate/monthly/kl/historical/", ["00044"], id="monthly-kl"),
    pytest.param("hourly/solar", "climate/hourly/solar/", None, id="hourly-solar"),
    pytest.param(
        "10_minutes/urban_temperature_air",
        "climate_urban/10_minutes/air_temperature/historical/",
        ["00044"],
        id="urban-10-minutes",
    ),
    pytest.param("1_minute/precipitation", "climate/1_minute/precipitation/meta_data/", ["00044"], id="1-minute-meta"),
]
_PARAMS = {"provider": "dwd", "network": "observation", "stations": "00044"}


def _description_for(url: str) -> bytes:
    return (_DESCRIPTION_URBAN if "climate_urban" in url else _DESCRIPTION).encode("latin-1")


def _history_zip() -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, text in _HISTORY_FILES.items():
            zf.writestr(name, text.encode("latin1"))
    buffer.seek(0)
    return buffer


@pytest.fixture
def listed(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """Stub DWD's server: each directory lists station 00044 and its description; the ones named list nothing.

    Returns a function that sets what is empty (`empty`, directories below `observations_germany/`) and what the
    listing raises (`raises`, by directory); the directories it was asked for come back from `asked`.
    """
    state: dict[str, Any] = {"empty": set(), "raises": {}, "asked": []}

    def listing(url: str, settings: Settings, cache_expiry: CacheExpiry | None = None) -> list[str]:  # noqa: ARG001
        directory = url.removeprefix(_BASE)
        state["asked"].append(directory)
        if directory in state["raises"]:
            raise state["raises"][directory]
        if directory in state["empty"]:
            return []
        return [
            f"{url}stundenwerte_KL_00044_19700101_20241231_hist.zip",
            f"{url}KL_Beschreibung_Stationen.txt",
            f"{url}Meta_Daten_zehn_min_rr_00044.zip",
        ]

    def download_file(url: str, **_: object) -> File:
        return File(url=url, content=io.BytesIO(_description_for(url)), status=200)

    monkeypatch.setattr(fileindex, "list_remote_files_fsspec", listing)
    monkeypatch.setattr(metaindex, "download_file", download_file)
    monkeypatch.setattr(api, "download_file", lambda url, **_: File(url=url, content=_history_zip(), status=200))

    def configure(*, empty: tuple[str, ...] = (), raises: dict[str, Exception] | None = None) -> list[str]:
        state["empty"] = set(empty)
        state["raises"] = raises or {}
        return state["asked"]

    return configure


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _warnings(body: dict[str, Any]) -> list[dict[str, Any]]:
    return body["metadata"]["warnings"]


def _cli_history(parameters: str) -> tuple[int, dict[str, Any] | None, str]:
    result = CliRunner().invoke(
        cli,
        [
            "history",
            "--provider",
            "dwd",
            "--network",
            "observation",
            "--parameters",
            parameters,
            "--stations",
            "00044",
            "--with-metadata=true",
        ],
    )
    output = result.output
    body = json.loads(output[output.index("{") :]) if "{" in output and result.exit_code == 0 else None
    return result.exit_code, body, output


# --- the cases of the issue, over REST and the command line ---------------------------------------------------------


@pytest.mark.parametrize(("parameters", "directory", "stations"), _CASES)
def test_rest_history_of_an_empty_directory_is_a_200_with_file_skipped(
    client: TestClient, listed: Callable[..., list[str]], parameters: str, directory: str, stations: list[str] | None
) -> None:
    """A 500 from the lookup before; now a 200 whose `file-skipped` names the directory that was listed (GH-3819)."""
    listed(empty=(directory,))

    response = client.get("/api/v1/history", params={**_PARAMS, "parameters": parameters})

    assert response.status_code == 200
    body = response.json()
    assert body["histories"] == []
    (skipped,) = [warning for warning in _warnings(body) if warning["code"] == "file-skipped"]
    assert f"The listing of the directory `{directory}` came back empty or missing" in skipped["message"]
    # the stations are named where the walk of the history met the directory; the lookup of a dataset that lists no
    # station at all (the solar datasets, whose one directory is every period's) has none to name
    assert skipped.get("stations") == stations
    if stations is None:
        # no station was found: the id asked for is unknown to the lookup, which says so as well
        assert [warning["code"] for warning in _warnings(body)] == ["unknown-station", "file-skipped"]
    # a partial answer is not kept: the next request can give another
    assert "Cache-Control" not in response.headers
    assert "ETag" not in response.headers
    assert "Last-Modified" not in response.headers


@pytest.mark.parametrize(("parameters", "directory", "stations"), _CASES)
def test_cli_history_of_an_empty_directory_is_exit_0_with_file_skipped(
    listed: Callable[..., list[str]], parameters: str, directory: str, stations: list[str] | None
) -> None:
    """The command line answered a traceback and exit 1; now the answer, with the warning in its metadata."""
    listed(empty=(directory,))

    exit_code, body, output = _cli_history(parameters)

    assert exit_code == 0, output
    assert body is not None
    assert body["histories"] == []
    (skipped,) = [warning for warning in _warnings(body) if warning["code"] == "file-skipped"]
    assert f"The listing of the directory `{directory}` came back empty or missing" in skipped["message"]
    assert skipped.get("stations") == stations


def test_the_directory_is_told_once_when_the_lookup_and_the_history_both_met_it(
    client: TestClient, listed: Callable[..., list[str]]
) -> None:
    """The lookup skipped the `historical` directory and the walk of the history met it again: one warning."""
    listed(empty=("climate/monthly/kl/historical/",))

    body = client.get("/api/v1/history", params={**_PARAMS, "parameters": "monthly/climate_summary"}).json()

    assert [warning["code"] for warning in _warnings(body)] == ["file-skipped"]


def test_an_empty_directory_the_history_does_not_read_is_told_by_the_lookup(
    client: TestClient, listed: Callable[..., list[str]]
) -> None:
    """The `recent` directory is no part of a history, but its stations are not in the lookup: told, with no station."""
    listed(empty=("climate/monthly/kl/recent/",))

    response = client.get("/api/v1/history", params={**_PARAMS, "parameters": "monthly/climate_summary"})

    assert response.status_code == 200
    body = response.json()
    (skipped,) = _warnings(body)
    assert skipped["code"] == "file-skipped"
    assert "`climate/monthly/kl/recent/` came back empty or missing" in skipped["message"]
    assert "stations" not in skipped
    # the history itself is whole: it came from `historical`
    assert [history["station_id"] for history in body["histories"]] == ["00044"]
    assert "Cache-Control" not in response.headers


# --- a request that is partly empty, and one that is not ------------------------------------------------------------


def test_rest_a_partly_empty_request_returns_the_datasets_that_are_listed(
    client: TestClient, listed: Callable[..., list[str]]
) -> None:
    """Several datasets, one empty: the good ones are answered, the warning names the other's directory."""
    listed(empty=("climate/monthly/kl/historical/",))

    response = client.get(
        "/api/v1/history", params={**_PARAMS, "parameters": "daily/climate_summary,monthly/climate_summary"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [(history["resolution"], history["dataset"]) for history in body["histories"]] == [
        ("daily", "climate_summary")
    ]
    (skipped,) = _warnings(body)
    assert skipped["code"] == "file-skipped"
    assert "`climate/monthly/kl/historical/`" in skipped["message"]
    assert "daily" not in skipped["message"]
    assert "Cache-Control" not in response.headers


def test_cli_a_partly_empty_request_returns_the_datasets_that_are_listed(listed: Callable[..., list[str]]) -> None:
    """The same on the command line."""
    listed(empty=("climate/monthly/kl/historical/",))

    exit_code, body, output = _cli_history("daily/climate_summary,monthly/climate_summary")

    assert exit_code == 0, output
    assert body is not None
    assert [(history["resolution"], history["dataset"]) for history in body["histories"]] == [
        ("daily", "climate_summary")
    ]
    (skipped,) = _warnings(body)
    assert "`climate/monthly/kl/historical/`" in skipped["message"]


def test_a_history_whose_directories_are_all_listed_has_no_warning_and_is_kept(
    client: TestClient, listed: Callable[..., list[str]]
) -> None:
    """The control: with nothing empty the answer is whole and carries the cache header an empty one does not."""
    listed()

    response = client.get("/api/v1/history", params={**_PARAMS, "parameters": "monthly/climate_summary"})

    assert response.status_code == 200
    body = response.json()
    assert [history["station_id"] for history in body["histories"]] == ["00044"]
    assert _warnings(body) == []
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    assert "ETag" in response.headers


# --- an outage is no empty directory --------------------------------------------------------------------------------


def _outages() -> list[Any]:
    return [
        pytest.param(NoInternetError("no connection to https://opendata.dwd.de/"), 503, id="no-internet"),
        pytest.param(DownloadError("https://opendata.dwd.de/", "HTTP 503"), 502, id="5xx"),
    ]


@pytest.mark.parametrize(("failure", "status"), _outages())
@pytest.mark.parametrize("directory", ["climate/monthly/kl/historical/", "climate/monthly/kl/recent/"])
def test_rest_an_outage_of_a_listing_stays_an_error_and_is_never_file_skipped(
    client: TestClient, listed: Callable[..., list[str]], directory: str, failure: Exception, status: int
) -> None:
    """A connection that cannot be made, or a 5xx, is not an empty directory: the lookup raises it, no 200."""
    listed(raises={directory: failure})

    response = client.get("/api/v1/history", params={**_PARAMS, "parameters": "monthly/climate_summary"})

    assert response.status_code == status
    assert "file-skipped" not in response.text
    assert "Cache-Control" not in response.headers


@pytest.mark.parametrize(("failure", "status"), _outages())
def test_cli_an_outage_of_a_listing_stays_an_error(
    listed: Callable[..., list[str]],
    failure: Exception,
    status: int,  # noqa: ARG001
) -> None:
    """The command line exits 1 and says nothing of a skipped file."""
    listed(raises={"climate/monthly/kl/historical/": failure})

    exit_code, body, output = _cli_history("monthly/climate_summary")

    assert exit_code == 1
    assert body is None
    assert "file-skipped" not in output


# --- what stays as it was: stations and values ---------------------------------------------------------------------


def test_rest_stations_and_values_of_an_empty_directory_still_fail(
    client: TestClient, listed: Callable[..., list[str]]
) -> None:
    """The decision is for the history: a stations list or values without the directory would be partial unsaid."""
    listed(empty=("climate/monthly/kl/historical/",))
    parameters = {"provider": "dwd", "network": "observation", "parameters": "monthly/climate_summary"}

    stations = client.get("/api/v1/stations", params={**parameters, "all": "true"})
    values = client.get("/api/v1/values", params={**parameters, "stations": "00044", "periods": "historical"})

    assert stations.status_code == 500
    assert values.status_code == 500


# --- the Python API -------------------------------------------------------------------------------------------------


def test_python_the_lookup_of_a_request_fails_on_an_empty_directory_unless_it_is_for_a_history(
    listed: Callable[..., list[str]],
) -> None:
    """`all()` raises the `FileNotFoundError` it always did (now an `EmptyListingError` that says which directory)."""
    listed(empty=("climate/monthly/kl/historical/",))
    request = DwdObservationRequest(parameters=["monthly/climate_summary"], settings=Settings(cache_disable=True))

    with pytest.raises(FileNotFoundError, match="does not have a list of files") as excinfo:
        request.all()

    assert isinstance(excinfo.value, EmptyListingError)
    assert excinfo.value.url == f"{_BASE}climate/monthly/kl/historical/"


def test_python_the_history_of_a_lookup_for_it_tells_the_directory_and_goes_on(
    listed: Callable[..., list[str]], caplog: pytest.LogCaptureFixture
) -> None:
    """The library flag of the surfaces: a lookup for a history skips the empty directory, the history warns."""
    listed(empty=("climate/monthly/kl/historical/",))
    request = DwdObservationRequest(parameters=["monthly/climate_summary"], settings=Settings(cache_disable=True))
    request._for_history = True  # noqa: SLF001
    begin_response()

    with caplog.at_level(logging.WARNING):
        histories = list(request.filter_by_station_id("00044").history().query())

    assert histories == []
    (skipped,) = recorded_warnings()
    assert skipped["code"] == "file-skipped"
    assert skipped["stations"] == ["00044"]
    assert "`climate/monthly/kl/historical/`" in skipped["message"]
    assert any(
        record.levelno == logging.WARNING and "came back empty" in record.getMessage() for record in caplog.records
    )


def test_python_an_outage_is_raised_by_the_lookup_for_a_history(listed: Callable[..., list[str]]) -> None:
    """Only an empty listing is told: a connection that cannot be made is raised, flag or not."""
    listed(raises={"climate/monthly/kl/historical/": NoInternetError("no connection")})
    request = DwdObservationRequest(parameters=["monthly/climate_summary"], settings=Settings(cache_disable=True))
    request._for_history = True  # noqa: SLF001

    with pytest.raises(NoInternetError):
        request.all()


def test_the_error_of_an_empty_listing_keeps_its_message_and_survives_a_copy() -> None:
    """The message is the one the function raised before, and a copy or a pickle rebuilds it from the url."""
    error = EmptyListingError("https://opendata.dwd.de/x/")

    assert str(error) == "url https://opendata.dwd.de/x/ does not have a list of files"
    for twin in (copy.copy(error), pickle.loads(pickle.dumps(error))):  # noqa: S301
        assert type(twin) is EmptyListingError
        assert twin.url == error.url
        assert str(twin) == str(error)


# --- how long an empty listing is kept --------------------------------------------------------------------------------


def test_an_empty_listing_is_not_kept_in_the_listing_cache(tmp_path: Path) -> None:
    """DWD fills the directory again: the next listing, within `CacheExpiry.METAINDEX`, finds the files.

    A listing with files is kept (12 hours for the lookup), an empty page and a 404 are not: no later request is served
    the empty answer from our cache. Measured against a local server that writes an index page as DWD's nginx does.
    """
    directories: dict[str, list[str]] = {}
    requests: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            requests.append(self.path)
            files = directories.get(self.path)
            if files is None:
                self.send_response(404)
                self.end_headers()
                return
            links = "".join(f'<a href="{name}">{name}</a>   06-Nov-2026 12:15:08   379\n' for name in files)
            page = '<html><body><h1>Index of {}</h1><hr><pre><a href="../">../</a>\n{}</pre><hr></body></html>'
            body = page.format(self.path, links)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode())

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        settings = Settings(cache_dir=str(tmp_path / "cache"))
        for path, present in (("/empty/", True), ("/missing/", False)):
            if present:
                directories[path] = []
            listing = functools.partial(
                list_remote_files_fsspec, f"{base}{path}", settings=settings, cache_expiry=CacheExpiry.METAINDEX
            )
            assert listing() == []

            directories[path] = ["tageswerte_KL_00044_hist.zip"]
            assert listing() == [f"{base}{path}tageswerte_KL_00044_hist.zip"]

            # the listing with a file is kept: no request reaches the server for the third
            requests.clear()
            assert len(listing()) == 1
            assert requests == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
