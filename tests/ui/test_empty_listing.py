# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A directory of DWD's server that comes back empty or missing is a partial answer with a warning, not a 500 (GH-3819).

The lookup of the stations of `dwd/observation` (and `dwd/derived`) lists the `historical` directory of a dataset (the
dataset's own directory for the solar datasets, the `meta_data` directory of the 1 minute precipitation) before a
history or the values are read, and an empty listing raised a `FileNotFoundError` there, which the REST API answered
with a 500 and the command line with a traceback. `stations`, `values` and `history` now skip the directory, answer
with the rest and say with a `file-skipped` warning that the answer is partial, which keeps a history from being cached.
A connection that cannot be made or a failing server is still an error and never a `file-skipped`.

A directory that lists files and no description of its stations (the extreme wind: no FX3 or FX6) is skipped the same
way (GH-3834), and a station that only a skipped directory lists, asked for by `interpolate`, `summarize` or the
stripes, is a 502 that names the directory and no 404.

The server is `tests/nginx_stub.py`, one that answers as nginx does, so the listings are fsspec's own (an empty
directory is `[url]` there without the fix of `list_remote_files_fsspec`): every directory lists one station, 00044, and
its description, and the ones a test names are empty or not there. Nothing here reaches the network.
"""

from __future__ import annotations

import copy
import io
import json
import logging
import pickle
import zipfile
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import polars as pl
import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from tests.nginx_stub import NginxLike, serving
from tests.provider.station_catalogue import assert_sound
from wetterdienst import Settings
from wetterdienst.exceptions import (
    DownloadError,
    MetaFileNotFoundError,
    NoInternetError,
    StationListingIncompleteError,
    StationNotFoundError,
    UpstreamError,
)
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.period import Period
from wetterdienst.model.listing_gap import ListingGap
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import metaindex as derived_metaindex
from wetterdienst.provider.dwd.observation import DwdObservationRequest, api, fileindex, metaindex
from wetterdienst.provider.dwd.observation.fileindex import (
    EMPTY_LISTING,
    NO_DESCRIPTION,
    DescriptionFileMissingError,
    EmptyListingError,
)
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.network import File, forget_remote_listing, list_remote_files_fsspec
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from httpx2 import Response

_DWD = "https://opendata.dwd.de"
_OBSERVATIONS = "/climate_environment/CDC/observations_germany/"
_DERIVED = "/climate_environment/CDC/derived_germany/"
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
_DESCRIPTION_DERIVED = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "---------- ------\r\n"
    "00044 20240401 20261014            44     52.9336    8.2370 Grossenkneten                             "
    "Niedersachsen                            Frei\r\n"
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
_FILES = [
    "stundenwerte_KL_00044_19700101_20241231_hist.zip",
    "KL_Beschreibung_Stationen.txt",
    "Meta_Daten_zehn_min_rr_00044.zip",
]

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
    # the 5 and 10 minute `meta_data` directories: the warning of #3816, which a real nginx never reached
    pytest.param(
        "5_minutes/precipitation", "climate/5_minutes/precipitation/meta_data/", ["00044"], id="5-minutes-meta"
    ),
    pytest.param(
        "10_minutes/temperature_air", "climate/10_minutes/air_temperature/meta_data/", ["00044"], id="10-minutes-meta"
    ),
]
_PARAMS = {"provider": "dwd", "network": "observation", "stations": "00044"}
_MONTHLY = "monthly/climate_summary"
_MONTHLY_HISTORICAL = "climate/monthly/kl/historical/"
_MONTHLY_RECENT = "climate/monthly/kl/recent/"


#: the stations of the 1 minute precipitation `historical` meta index (the region is joined from the daily list)
_MINUTE_1 = pl.LazyFrame(
    {
        "station_id": ["00044"],
        "start_timestamp": ["20070401"],
        "end_timestamp": [None],
        "elevation": ["44"],
        "latitude": ["52.9"],
        "longitude": ["8.2"],
        "name": ["Grossenkneten"],
    },
    schema=dict.fromkeys(
        ("station_id", "start_timestamp", "end_timestamp", "elevation", "latitude", "longitude", "name"), pl.String
    ),
)


def _description_for(url: str, station_ids: list[str]) -> bytes:
    if "derived_germany" in url:
        return _DESCRIPTION_DERIVED.encode("latin-1")
    if "climate_urban" in url:
        return _DESCRIPTION_URBAN.encode("latin-1")
    header, rule, row = _DESCRIPTION.split("\r\n")[:3]
    rows = [row.replace("00044", station_id) for station_id in station_ids]
    return "\r\n".join([header, rule, *rows, ""]).encode("latin-1")


def _history_zip() -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, text in _HISTORY_FILES.items():
            zf.writestr(name, text.encode("latin1"))
    buffer.seek(0)
    return buffer


class _Dwd:
    """What a test sets of DWD's server: which directories are empty or not there, and which listing raises."""

    def __init__(self, server: NginxLike) -> None:
        self.server = server
        self.raises: dict[str, Exception] = {}
        #: the directories (below `CDC/`) the lookups listed, in order
        self.asked: list[str] = []
        #: the settings of the listings: the cache of a listing with files is kept, as it is for a request
        self.local = Settings()
        #: the stations the description lists
        self.stations = ["00044"]

    def _path(self, directory: str) -> str:
        if directory.startswith("derived_germany/"):
            return f"{_DERIVED}{directory.removeprefix('derived_germany/')}"
        return f"{_OBSERVATIONS}{directory}"

    def set(
        self, *, empty: tuple[str, ...] = (), missing: tuple[str, ...] = (), raises: dict[str, Exception] | None = None
    ) -> _Dwd:
        """Make the directories (below `observations_germany/`, or `derived_germany/...`) empty or not there."""
        for directory in empty:
            self.server.directories[self._path(directory)] = []
        for directory in missing:
            self.server.missing.add(self._path(directory))
        self.raises = {self._path(d): e for d, e in (raises or {}).items()}
        return self


@pytest.fixture
def dwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Dwd]:
    """Stand in for DWD's server: an nginx-like one on a local port, listed through fsspec as the lookups do.

    Every directory lists station 00044 and its description. The lookups call `list_remote_files_fsspec` with the URL of
    `opendata.dwd.de`, which is sent to the local server and the URLs it finds are sent back, so the listing, the cache
    of it and the redirect of nginx are the real ones. The downloads (the descriptions, the metadata of a history)
    are served from memory.
    """
    with serving() as server:
        server.default = _FILES
        state = _Dwd(server)
        state.local = Settings(cache_dir=str(tmp_path / "cache"))

        def listing(url: str, settings: Settings, cache_expiry: CacheExpiry = CacheExpiry.FILEINDEX) -> list:  # noqa: ARG001
            path = url.removeprefix(_DWD)
            state.asked.append(path.removeprefix("/climate_environment/CDC/"))
            if path in state.raises:
                raise state.raises[path]
            found = list_remote_files_fsspec(f"{server.base}{path}", settings=state.local, cache_expiry=cache_expiry)
            return [item.replace(server.base, _DWD) for item in found]

        def download_file(url: str, **_: object) -> File:
            return File(url=url, content=io.BytesIO(_description_for(url, state.stations)), status=200)

        def forget(url: str, settings: Settings, cache_expiry: CacheExpiry) -> None:  # noqa: ARG001
            forget_remote_listing(url.replace(_DWD, server.base), state.local, cache_expiry)

        monkeypatch.setattr(fileindex, "list_remote_files_fsspec", listing)
        monkeypatch.setattr(fileindex, "forget_remote_listing", forget)
        monkeypatch.setattr(metaindex, "download_file", download_file)
        monkeypatch.setattr(derived_metaindex, "download_file", download_file)
        monkeypatch.setattr(api, "download_file", lambda url, **_: File(url=url, content=_history_zip(), status=200))
        # the values: the archives are not served, so no period has data, which is what the tests of the values read
        monkeypatch.setattr(api, "download_climate_observations_data", lambda *_args, **_kwargs: [])
        yield state


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _warnings(body: dict[str, Any]) -> list[dict[str, Any]]:
    return body["metadata"]["warnings"]


def _skipped(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [warning for warning in _warnings(body) if warning["code"] == "file-skipped"]


def _cli(command: str, parameters: str, *extra: str) -> tuple[int, dict[str, Any] | None, str]:
    result = CliRunner().invoke(
        cli,
        [
            command,
            "--provider",
            "dwd",
            "--network",
            "observation",
            "--parameters",
            parameters,
            "--with-metadata=true",
            *extra,
        ],
    )
    output = result.output
    body = json.loads(output[output.index("{") :]) if "{" in output and result.exit_code == 0 else None
    return result.exit_code, body, output


# --- the history: the cases of the issue, over REST and the command line -------------------------------------------


@pytest.mark.parametrize("kind", ["empty", "missing"])
@pytest.mark.parametrize(("parameters", "directory", "stations"), _CASES)
def test_rest_history_of_an_empty_directory_is_a_200_with_file_skipped(
    client: TestClient, dwd: _Dwd, parameters: str, directory: str, stations: list[str] | None, kind: str
) -> None:
    """A 500 from the lookup before; now a 200 whose `file-skipped` names the directory that was listed (GH-3819)."""
    dwd.set(**{kind: (directory,)})

    response = client.get("/api/v1/history", params={**_PARAMS, "parameters": parameters})

    assert response.status_code == 200
    body = response.json()
    assert body["histories"] == []
    walk = [warning for warning in _skipped(body) if "stations" in warning]
    assert [warning["stations"] for warning in walk] == ([stations] if stations else [])
    assert all(f"The listing of the directory `{directory}` came back empty or missing" in w["message"] for w in walk)
    # the lookup names it as well, with the dataset and the periods it was to list
    lookup = [warning for warning in _skipped(body) if "stations" not in warning]
    assert all("stations of" in warning["message"] for warning in lookup)
    assert any(f"`{directory}`" in warning["message"] for warning in _skipped(body))
    # a partial answer is not kept: the next request can give another
    assert "Cache-Control" not in response.headers
    assert "ETag" not in response.headers
    assert "Last-Modified" not in response.headers


@pytest.mark.parametrize(("parameters", "directory", "stations"), _CASES)
def test_cli_history_of_an_empty_directory_is_exit_0_with_file_skipped(
    dwd: _Dwd,
    parameters: str,
    directory: str,
    stations: list[str] | None,  # noqa: ARG001
) -> None:
    """The command line answered a traceback and exit 1; now the answer, with the warning in its metadata."""
    dwd.set(empty=(directory,))

    exit_code, body, output = _cli("history", parameters, "--stations", "00044")

    assert exit_code == 0, output
    assert body is not None
    assert body["histories"] == []
    assert any(f"`{directory}`" in warning["message"] for warning in _skipped(body))


def test_the_history_of_a_station_of_recent_is_told_by_the_lookup_and_by_the_history(
    client: TestClient, dwd: _Dwd
) -> None:
    """The lookup tells the directory and the periods it skipped, the history the station whose history was not read."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    body = client.get("/api/v1/history", params={**_PARAMS, "parameters": _MONTHLY}).json()

    lookup, walk = _skipped(body)
    assert "stations" not in lookup
    assert lookup["message"] == (
        "The listing of the directory `climate/monthly/kl/historical/` came back empty or missing, so the historical "
        "stations of monthly/climate_summary were not looked up, and a station that only that release lists is not "
        "in the answer, which may be partial. Try again later."
    )
    assert walk["stations"] == ["00044"]
    assert "the history of station 00044 was not read" in walk["message"]


def test_an_empty_recent_directory_does_not_say_the_history_is_lost(client: TestClient, dwd: _Dwd) -> None:
    """At a low resolution the history reads `historical`: with `recent` empty nothing of 00044 is missing."""
    dwd.set(empty=(_MONTHLY_RECENT,))

    response = client.get("/api/v1/history", params={**_PARAMS, "parameters": _MONTHLY})

    assert response.status_code == 200
    body = response.json()
    assert [history["station_id"] for history in body["histories"]] == ["00044"]
    (skipped,) = _skipped(body)
    assert "`climate/monthly/kl/recent/`" in skipped["message"]
    assert "the recent stations of monthly/climate_summary were not looked up" in skipped["message"]
    # no claim of a history that was not read
    assert "history" not in skipped["message"]
    assert "stations" not in skipped
    assert "Cache-Control" not in response.headers


def test_the_warning_names_the_periods_skipped_not_the_directory_it_was_listed_for(
    client: TestClient, dwd: _Dwd
) -> None:
    """The 1 minute precipitation reads the daily `more_precip` directory for the region of its `historical` stations.

    That directory is empty, which costs the stations of the 1 minute `historical` release (the lookup of the
    stations that came from it): the warning says that, not that the stations of a daily directory were not looked up.
    """
    directory = "climate/daily/more_precip/historical/"
    dwd.set(empty=(directory,))
    with patch.object(metaindex, "_create_meta_index_for_1minute_historical_precipitation", return_value=_MINUTE_1):
        response = client.get(
            "/api/v1/stations",
            params={"provider": "dwd", "network": "observation", "parameters": "1_minute/precipitation", "all": "true"},
        )

    assert response.status_code == 200
    body = response.json()
    label = f"{DwdObservationMetadata.minute_1.precipitation.resolution.name}/precipitation"
    (skipped,) = _skipped(body)
    assert skipped["message"].startswith(
        f"The listing of the directory `{directory}` came back empty or missing, so the"
    )
    assert f"historical stations of {label} were not looked up" in skipped["message"]
    # the stations of `recent` and `now` are there
    assert [station["station_id"] for station in body["stations"]] == ["00044"]


def test_rest_stations_of_the_one_minute_precipitation_skip_an_empty_meta_data_directory(
    client: TestClient, dwd: _Dwd
) -> None:
    """The lookup of its `historical` stations lists `meta_data`: with it empty the period is skipped."""
    directory = "climate/1_minute/precipitation/meta_data/"
    dwd.set(empty=(directory,))

    response = client.get(
        "/api/v1/stations",
        params={"provider": "dwd", "network": "observation", "parameters": "1_minute/precipitation", "all": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    (skipped,) = _skipped(body)
    assert f"`{directory}` came back empty or missing" in skipped["message"]
    assert "the historical stations of" in skipped["message"]
    assert [station["station_id"] for station in body["stations"]] == ["00044"]


def test_an_empty_file_index_of_a_period_is_skipped_as_its_meta_index_is(client: TestClient, dwd: _Dwd) -> None:
    """Skip a period whose file index is the empty listing, as one whose meta index is.

    The second listing of a period may be the empty one: the 1 minute `historical` meta index lists `meta_data`, its
    file index the `historical` directory.
    """
    directory = "climate/1_minute/precipitation/historical/"
    dwd.set(empty=(directory,))

    with patch.object(metaindex, "_create_meta_index_for_1minute_historical_precipitation", return_value=_MINUTE_1):
        response = client.get(
            "/api/v1/stations",
            params={"provider": "dwd", "network": "observation", "parameters": "1_minute/precipitation", "all": "true"},
        )

    assert response.status_code == 200
    body = response.json()
    (skipped,) = _skipped(body)
    assert skipped["message"].startswith(f"The listing of the directory `{directory}` came back empty or missing")
    assert "historical stations of" in skipped["message"]
    assert [station["station_id"] for station in body["stations"]] == ["00044"]


# --- a request that is partly empty, and one that is not -----------------------------------------------------------


def test_rest_a_partly_empty_request_returns_the_datasets_that_are_listed(client: TestClient, dwd: _Dwd) -> None:
    """Several datasets, one empty: the good ones are answered, the warning names the other's directory."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get(
        "/api/v1/history", params={**_PARAMS, "parameters": "daily/climate_summary,monthly/climate_summary"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [(history["resolution"], history["dataset"]) for history in body["histories"]] == [
        ("daily", "climate_summary")
    ]
    assert {warning["message"].split(" came back")[0] for warning in _skipped(body)} == {
        "The listing of the directory `climate/monthly/kl/historical/`"
    }
    assert "daily" not in " ".join(warning["message"] for warning in _skipped(body))
    assert "Cache-Control" not in response.headers


def test_cli_a_partly_empty_request_returns_the_datasets_that_are_listed(dwd: _Dwd) -> None:
    """The same on the command line."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    exit_code, body, output = _cli("history", "daily/climate_summary,monthly/climate_summary", "--stations", "00044")

    assert exit_code == 0, output
    assert body is not None
    assert [(history["resolution"], history["dataset"]) for history in body["histories"]] == [
        ("daily", "climate_summary")
    ]
    assert all("`climate/monthly/kl/historical/`" in warning["message"] for warning in _skipped(body))


@pytest.mark.usefixtures("dwd")
def test_a_history_whose_directories_are_all_listed_has_no_warning_and_is_kept(client: TestClient) -> None:
    """The control: with nothing empty the answer is whole and carries the cache header an empty one does not."""
    response = client.get("/api/v1/history", params={**_PARAMS, "parameters": _MONTHLY})

    assert response.status_code == 200
    body = response.json()
    assert [history["station_id"] for history in body["histories"]] == ["00044"]
    assert _warnings(body) == []
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    assert "ETag" in response.headers


def test_a_directory_filled_again_is_listed_by_the_next_request(client: TestClient, dwd: _Dwd) -> None:
    """The empty listing is not kept: DWD fills the directory and the next request has the history, whole."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    first = client.get("/api/v1/history", params={**_PARAMS, "parameters": _MONTHLY})
    assert _skipped(first.json())

    dwd.server.directories[f"{_OBSERVATIONS}{_MONTHLY_HISTORICAL}"] = _FILES
    second = client.get("/api/v1/history", params={**_PARAMS, "parameters": _MONTHLY})

    assert second.status_code == 200
    body = second.json()
    assert _warnings(body) == []
    assert [history["station_id"] for history in body["histories"]] == ["00044"]
    assert second.headers["Cache-Control"] == "public, max-age=3600"


# --- stations and values -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["empty", "missing"])
def test_rest_stations_of_an_empty_directory_are_those_of_the_other_periods_with_a_warning(
    client: TestClient, dwd: _Dwd, kind: str
) -> None:
    """A 500 before: the stations of the `recent` release are answered, and the warning names what was left out."""
    dwd.set(**{kind: (_MONTHLY_HISTORICAL,)})

    response = client.get(
        "/api/v1/stations", params={"provider": "dwd", "network": "observation", "parameters": _MONTHLY, "all": "true"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [station["station_id"] for station in body["stations"]] == ["00044"]
    (skipped,) = _skipped(body)
    assert "`climate/monthly/kl/historical/` came back empty or missing" in skipped["message"]
    assert "historical stations of monthly/climate_summary were not looked up" in skipped["message"]
    assert "Cache-Control" not in response.headers


def test_rest_stations_of_a_dataset_whose_only_directory_is_empty_are_none_with_a_warning(
    client: TestClient, dwd: _Dwd
) -> None:
    """The solar datasets list one directory for every period: there is no station, and the warning says why."""
    dwd.set(empty=("climate/hourly/solar/",))

    response = client.get(
        "/api/v1/stations",
        params={"provider": "dwd", "network": "observation", "parameters": "hourly/solar", "all": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stations"] == []
    (skipped,) = _skipped(body)
    assert "`climate/hourly/solar/`" in skipped["message"]
    assert "historical and recent stations of hourly/solar" in skipped["message"]


def test_cli_stations_of_an_empty_directory_are_those_of_the_other_periods_with_a_warning(dwd: _Dwd) -> None:
    """The command line: exit 0 and the stations of `recent`."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    exit_code, body, output = _cli("stations", _MONTHLY, "--all")

    assert exit_code == 0, output
    assert body is not None
    assert [station["station_id"] for station in body["stations"]] == ["00044"]
    assert "`climate/monthly/kl/historical/`" in _skipped(body)[0]["message"]


def test_rest_values_of_a_station_whose_historical_directory_is_empty_name_the_station(
    client: TestClient, dwd: _Dwd
) -> None:
    """The values walk lists `historical` again for the station: the period is skipped and `file-skipped` names it."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get(
        "/api/v1/values",
        params={"provider": "dwd", "network": "observation", "parameters": _MONTHLY, "stations": "00044"},
    )

    assert response.status_code == 200
    body = response.json()
    skipped = _skipped(body)
    assert any(
        "stations" not in warning and "`climate/monthly/kl/historical/`" in warning["message"] for warning in skipped
    )
    assert any(warning.get("stations") == ["00044"] for warning in skipped)
    assert "Cache-Control" not in response.headers


def test_a_values_request_of_an_empty_directory_for_the_period_asked_is_empty_with_a_warning(
    client: TestClient, dwd: _Dwd
) -> None:
    """Only `historical` is asked for: no station is found, and the answer says the directory was empty."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get(
        "/api/v1/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": _MONTHLY,
            "stations": "00044",
            "periods": "historical",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["values"] == []
    assert any("`climate/monthly/kl/historical/`" in warning["message"] for warning in _skipped(body))


# --- an outage is no empty directory --------------------------------------------------------------------------------


def _outages() -> list[Any]:
    return [
        pytest.param(NoInternetError("no connection to https://opendata.dwd.de/"), 503, id="no-internet"),
        pytest.param(DownloadError("https://opendata.dwd.de/", "HTTP 503"), 502, id="5xx"),
    ]


@pytest.mark.parametrize(
    "route",
    [
        pytest.param(("history", {"stations": "00044"}), id="history"),
        pytest.param(("stations", {"all": "true"}), id="stations"),
        pytest.param(("values", {"stations": "00044"}), id="values"),
    ],
)
@pytest.mark.parametrize(("failure", "status"), _outages())
@pytest.mark.parametrize("directory", [_MONTHLY_HISTORICAL, _MONTHLY_RECENT])
def test_rest_an_outage_of_a_listing_stays_an_error_and_is_never_file_skipped(
    client: TestClient, dwd: _Dwd, directory: str, failure: Exception, status: int, route: tuple[str, dict[str, str]]
) -> None:
    """A connection that cannot be made, or a 5xx, is not an empty directory: it is raised, and the answer is no 200."""
    dwd.set(raises={directory: failure})
    name, extra = route

    response = client.get(
        f"/api/v1/{name}", params={"provider": "dwd", "network": "observation", "parameters": _MONTHLY, **extra}
    )

    assert response.status_code == status
    assert "file-skipped" not in response.text
    assert "Cache-Control" not in response.headers


@pytest.mark.parametrize(("failure", "status"), _outages())
def test_cli_an_outage_of_a_listing_stays_an_error(dwd: _Dwd, failure: Exception, status: int) -> None:  # noqa: ARG001
    """The command line exits 1 and says nothing of a skipped file."""
    dwd.set(raises={_MONTHLY_HISTORICAL: failure})

    exit_code, body, output = _cli("history", _MONTHLY, "--stations", "00044")

    assert exit_code == 1
    assert body is None
    assert "file-skipped" not in output


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        pytest.param(
            "text/html",
            b'<html><title>503 - CDN</title><a href="https://status.example.com/">status</a></html>',
            id="cdn",
        ),
        pytest.param("application/json", b'{"error": "unavailable"}', id="json"),
    ],
)
@pytest.mark.parametrize(
    ("route", "parameters", "directory"),
    [
        pytest.param("history", _MONTHLY, _MONTHLY_HISTORICAL, id="history-historical"),
        pytest.param(
            "history", "1_minute/precipitation", "climate/1_minute/precipitation/meta_data/", id="history-1min"
        ),
        pytest.param("stations", _MONTHLY, _MONTHLY_HISTORICAL, id="stations"),
    ],
)
def test_rest_a_200_page_that_is_no_index_is_a_502_and_never_an_empty_directory(
    client: TestClient, dwd: _Dwd, route: str, parameters: str, directory: str, content_type: str, body: bytes
) -> None:
    """A CDN's error page or a JSON error answered with a 200 is an outage, not "came back empty or missing"."""
    for path in (dwd._path(directory), dwd._path(directory).rstrip("/")):  # noqa: SLF001
        dwd.server.pages[path] = (content_type, body)
    extra = {"stations": "00044"} if route == "history" else {"all": "true"}

    response = client.get(
        f"/api/v1/{route}", params={"provider": "dwd", "network": "observation", "parameters": parameters, **extra}
    )

    assert response.status_code == 502
    assert "file-skipped" not in response.text
    assert "parameter-without-rows" not in response.text
    assert "Cache-Control" not in response.headers


# --- what an empty directory costs a walk -----------------------------------------------------------------------------

_COUNT_CASES = [
    pytest.param(
        "daily/climate_summary",
        "climate/daily/kl/",
        "tageswerte_KL_{}_19700101_20241231_akt.zip",
        id="daily-kl",
    ),
    pytest.param(
        "10_minutes/temperature_air",
        "climate/10_minutes/air_temperature/",
        "10minutenwerte_TU_{}_akt.zip",
        id="10-minutes",
    ),
]


def _requests_for_empty_directory(
    dwd: _Dwd,
    monkeypatch: pytest.MonkeyPatch,
    parameters: str,
    directory: str,
    name: str,
    stations: int,
    *,
    ahead: bool,
    remembered: bool = True,
) -> int:
    """Count the GETs for the empty `historical` directory of a response that looks up and reads some stations."""
    ids = [f"{number:05d}" for number in range(1, stations + 1)]
    dwd.stations = ids
    # no listings cache: the stations of the first count are not those of the second
    dwd.local = Settings(cache_disable=True)
    files = [name.format(station_id) for station_id in ids]
    for period in ("recent", "now"):
        dwd.server.directories[f"{_OBSERVATIONS}{directory}{period}/"] = [*files, "KL_Beschreibung_Stationen.txt"]
    dwd.set(empty=(f"{directory}historical/",))
    dwd.server.requests.clear()
    if not remembered:
        monkeypatch.setattr(fileindex, "_remembered_empty_directories", set)
    begin_response()
    request = DwdObservationRequest(parameters=[parameters], settings=Settings(cache_disable=True))
    found = request.all()
    values = found.values()
    model = request.metadata[parameters.split("/", maxsplit=1)[0]][parameters.split("/")[1]]

    @fileindex.remembering_empty_directories
    def walk() -> int:
        # the fetch-ahead asks the provider for the files of each station it reaches, inside the walk and its memory
        if ahead:
            for station_id in ids:
                values._files_ahead(station_id, [model])  # noqa: SLF001
        return len(list(values.query()))

    walk()
    path = f"{_OBSERVATIONS}{directory}historical"
    return len([request for request in dwd.server.requests if request[1].startswith(path)])


@pytest.mark.parametrize("ahead", [False, True], ids=["no-fetch-ahead", "fetch-ahead"])
@pytest.mark.parametrize(("parameters", "directory", "name"), _COUNT_CASES)
def test_a_walk_lists_a_directory_found_empty_once_whatever_the_number_of_stations(
    dwd: _Dwd, monkeypatch: pytest.MonkeyPatch, parameters: str, directory: str, name: str, *, ahead: bool
) -> None:
    """One listing of an empty directory per lookup and per walk, whatever the number of stations.

    An empty directory is five GETs, and the walk asked for it at every station (and the hook again): 100 stations
    were 500 requests. The count is the same for one station and for twenty.
    """
    one = _requests_for_empty_directory(dwd, monkeypatch, parameters, directory, name, 1, ahead=ahead)
    many = _requests_for_empty_directory(dwd, monkeypatch, parameters, directory, name, 20, ahead=ahead)

    assert one > 0
    assert many == one


def test_without_the_memory_a_walk_lists_an_empty_directory_at_every_station(
    dwd: _Dwd, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control of the above, with the memory off: what the count would be."""
    args = ("daily/climate_summary", "climate/daily/kl/", "tageswerte_KL_{}_19700101_20241231_akt.zip")
    one = _requests_for_empty_directory(dwd, monkeypatch, *args, 1, ahead=False, remembered=False)
    many = _requests_for_empty_directory(dwd, monkeypatch, *args, 20, ahead=False, remembered=False)

    assert many > 10 * one


def _file_skipped() -> list[dict[str, Any]]:
    return [warning for warning in recorded_warnings() if warning["code"] == "file-skipped"]


def test_a_second_lookup_after_the_directory_is_filled_sees_it_in_the_same_response(dwd: _Dwd) -> None:
    """`begin_response()` starts no memory: a lookup, the directory filled, a lookup again, in one context."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    begin_response()
    _request().all()
    assert len(_file_skipped()) == 1

    dwd.server.directories[f"{_OBSERVATIONS}{_MONTHLY_HISTORICAL}"] = _FILES
    dwd.server.requests.clear()
    _request().all()

    historical = f"{_OBSERVATIONS}{_MONTHLY_HISTORICAL}".rstrip("/")
    assert any(path.startswith(historical) for _, path in dwd.server.requests)
    assert len(_file_skipped()) == 1


def test_a_walk_left_open_holds_no_memory_in_the_context_of_its_caller() -> None:
    """A generator has no context of its own: what it remembers is set around its steps and not between them."""
    steps: list[set[str]] = []

    @fileindex.remembering_empty_directories
    def walk() -> Iterator[int]:
        for number in range(3):
            steps.append(fileindex._remembered_empty_directories())  # noqa: SLF001
            yield number

    generator = walk()
    assert next(generator) == 0
    assert fileindex._REMEMBERED.get() is None  # noqa: SLF001
    assert next(generator) == 1
    assert fileindex._REMEMBERED.get() is None  # noqa: SLF001
    generator.close()

    # one memory for the whole walk
    assert steps[0] is steps[1]
    assert fileindex._REMEMBERED.get() is None  # noqa: SLF001


def test_a_lookup_after_a_walk_left_open_sees_the_directory_filled(dwd: _Dwd) -> None:
    """The real walk, stopped after its first step: a lookup of the same context asks again and sees the files."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    ids = ["00044", "00045"]
    dwd.stations = ids
    dwd.server.directories[f"{_OBSERVATIONS}{_MONTHLY_RECENT}"] = [
        *(f"stundenwerte_KL_{station_id}_19700101_20241231_akt.zip" for station_id in ids),
        "KL_Beschreibung_Stationen.txt",
    ]
    values = _request().all().values()
    walk = values.query()
    next(walk, None)

    dwd.server.directories[f"{_OBSERVATIONS}{_MONTHLY_HISTORICAL}"] = [
        *(f"stundenwerte_KL_{station_id}_19700101_20241231_hist.zip" for station_id in ids),
        "KL_Beschreibung_Stationen.txt",
    ]
    assert fileindex._REMEMBERED.get() is None  # noqa: SLF001
    begin_response()
    assert len(_request().all().df) == len(ids)
    assert not [warning for warning in recorded_warnings() if warning["code"] == "file-skipped"]
    walk.close()


def test_a_populated_listing_and_an_error_are_not_remembered(dwd: _Dwd) -> None:
    """Only an empty directory is: a failure is asked again, a populated listing is the listings cache's."""
    dwd.set(raises={_MONTHLY_HISTORICAL: NoInternetError("no connection")})
    seen: list[set[str]] = []

    @fileindex.remembering_empty_directories
    def lookup() -> None:
        try:
            _request().all()
        finally:
            seen.append(set(fileindex._remembered_empty_directories()))  # noqa: SLF001

    with pytest.raises(NoInternetError):
        lookup()
    dwd.raises = {}
    lookup()

    assert seen == [set(), set()]


# --- the Python API --------------------------------------------------------------------------------------------------


def _request(parameters: str = _MONTHLY) -> DwdObservationRequest:
    return DwdObservationRequest(parameters=[parameters], settings=Settings(cache_disable=True))


def test_python_the_stations_of_a_request_skip_an_empty_directory_and_log_the_warning(
    dwd: _Dwd, caplog: pytest.LogCaptureFixture
) -> None:
    """`all()` answers the stations of the other periods and warns: a log line, and what a response records."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    begin_response()

    with caplog.at_level(logging.WARNING):
        stations = _request().all().df

    assert stations.get_column("station_id").to_list() == ["00044"]
    (skipped,) = recorded_warnings()
    assert skipped["code"] == "file-skipped"
    assert "`climate/monthly/kl/historical/`" in skipped["message"]
    assert any(
        record.levelno == logging.WARNING and "came back empty" in record.getMessage() for record in caplog.records
    )


def test_python_the_history_of_a_station_of_an_empty_directory_warns_and_goes_on(dwd: _Dwd) -> None:
    """`stations.history().query()` yields no history of the directory, and the walk says whose it did not read."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    begin_response()

    histories = list(_request().filter_by_station_id("00044").history().query())

    assert histories == []
    skipped = [warning for warning in recorded_warnings() if warning["code"] == "file-skipped"]
    assert [warning.get("stations") for warning in skipped] == [None, ["00044"]]


def test_python_the_values_of_a_station_of_an_empty_directory_warn_and_go_on(dwd: _Dwd) -> None:
    """`stations.values().query()` skips the period with no file and names the station."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    begin_response()

    results = list(_request().filter_by_station_id("00044").values().query())

    assert all(result.df.is_empty() for result in results)
    skipped = [warning for warning in recorded_warnings() if warning["code"] == "file-skipped"]
    assert any(warning.get("stations") == ["00044"] for warning in skipped)


def test_python_the_values_of_a_ten_minute_dataset_skip_an_empty_historical_directory(dwd: _Dwd) -> None:
    """The date ranges of the `historical` files of a 10 minute dataset come from the directory: a period skipped."""
    request = DwdObservationRequest(parameters=["10_minutes/temperature_air"], settings=Settings(cache_disable=True))
    stations = request.filter_by_station_id("00044")
    # empty after the lookup, so that it is the walk of the values that meets it (a listing with files is cached)
    dwd.local = Settings(cache_disable=True)
    dwd.set(empty=("climate/10_minutes/air_temperature/historical/",))
    begin_response()

    results = list(stations.values().query())

    assert all(result.df.is_empty() for result in results)
    skipped = [warning for warning in recorded_warnings() if warning["code"] == "file-skipped"]
    assert any(warning.get("stations") == ["00044"] for warning in skipped)


def test_python_the_values_of_derived_skip_an_empty_directory(dwd: _Dwd) -> None:
    """`dwd/derived` walks the periods of a station as the observations do: an empty directory is a period skipped."""
    request = DwdDerivedRequest(parameters=[("hourly", "radiation_global")], settings=Settings(cache_disable=True))
    stations = request.filter_by_station_id("00044")
    base = "derived_germany/climate/hourly/duett/radiation_global/"
    dwd.local = Settings(cache_disable=True)
    dwd.set(empty=(f"{base}historical/", f"{base}recent/"))
    begin_response()

    results = list(stations.values().query())

    assert all(result.df.is_empty() for result in results)
    skipped = [warning for warning in recorded_warnings() if warning["code"] == "file-skipped"]
    assert any(warning.get("stations") == ["00044"] for warning in skipped)


def test_python_an_outage_is_raised_by_the_lookup(dwd: _Dwd) -> None:
    """Only an empty listing is skipped: a connection that cannot be made is raised."""
    dwd.set(raises={_MONTHLY_HISTORICAL: NoInternetError("no connection")})

    with pytest.raises(NoInternetError):
        _request().all()


def test_python_describe_fields_of_an_empty_directory_is_still_an_error(dwd: _Dwd) -> None:
    """The description of a dataset is a file of one directory: with the directory empty there is nothing to answer."""
    dwd.set(empty=("climate/monthly/kl/",))

    with pytest.raises(EmptyListingError, match="does not have a list of files"):
        DwdObservationRequest.describe_fields("monthly/climate_summary", "recent")


def test_python_the_derived_lookup_skips_an_empty_directory_as_the_observations_do(dwd: _Dwd) -> None:
    """`dwd/derived` shares the listing: its station lookup goes on without the empty period and warns."""
    directory = "derived_germany/climate/hourly/duett/radiation_global/historical/"
    dwd.set(empty=(directory,))
    begin_response()

    request = DwdDerivedRequest(parameters=[("hourly", "radiation_global")], settings=Settings(cache_disable=True))
    stations = request.all().df

    assert stations.get_column("station_id").to_list() == ["00044"]
    (skipped,) = recorded_warnings()
    assert skipped["code"] == "file-skipped"
    assert "`derived_germany/climate/hourly/duett/radiation_global/historical/`" in skipped["message"]
    assert "historical stations of hourly/radiation_global were not looked up" in skipped["message"]


def test_a_tree_that_is_empty_everywhere_leaves_no_station_which_the_live_catalogue_tests_refuse(dwd: _Dwd) -> None:
    """DWD restructures its tree: every listing is empty, the lookup answers no station, and `assert_sound` says so.

    The live test of the catalogues fails on a catalogue with no station ("the catalogue is empty, so no rule was
    applied"), which is what the lookup skipping its directories leaves.
    """
    dwd.server.default = []
    begin_response()

    stations = _request().all().df

    assert stations.is_empty()
    assert {warning["code"] for warning in recorded_warnings()} == {"file-skipped"}
    with pytest.raises(AssertionError, match="the catalogue is empty"):
        assert_sound(stations, "dwd/observation monthly/climate_summary")


def test_the_error_of_an_empty_listing_keeps_its_message_and_survives_a_copy() -> None:
    """The message is the one the function raised before, and a copy or a pickle rebuilds it from the url."""
    error = EmptyListingError("https://opendata.dwd.de/x/")

    assert str(error) == "url https://opendata.dwd.de/x/ does not have a list of files"
    for twin in (copy.copy(error), pickle.loads(pickle.dumps(error))):  # noqa: S301
        assert type(twin) is EmptyListingError
        assert twin.url == error.url
        assert str(twin) == str(error)


# --- a period without a description file, and the extreme wind (GH-3834) -------------------------------------------

#: the files of a directory whose description is not (yet) there
_UNDESCRIBED = ["stundenwerte_KL_00044_19700101_20241231_hist.zip"]
_ANNUAL_HISTORICAL = "climate/annual/kl/historical/"
_WIND_HISTORICAL = "climate/subdaily/extreme_wind/historical/"
_WIND = "subdaily/wind_extreme"
_WIND_FILES = ["terminwerte_FX_00044_20100101_20201231_hist.zip"]
_FX3 = "FX3_Beschreibung_Stationen.txt"
_FX6 = "FX6_Beschreibung_Stationen.txt"
_NO_DESCRIPTION_WARNING = (
    "The directory `climate/monthly/kl/historical/` lists no description of its stations, so the historical stations "
    "of monthly/climate_summary were not looked up, and a station that only that release lists is not in the answer, "
    "which may be partial. Try again later."
)


def _without_description(dwd: _Dwd, directory: str = _MONTHLY_HISTORICAL, files: list[str] | None = None) -> None:
    """Make a directory list files and no description."""
    dwd.server.directories[dwd._path(directory)] = files if files is not None else _UNDESCRIBED  # noqa: SLF001


def test_rest_stations_of_a_period_without_a_description_are_those_of_the_others_with_a_warning(
    client: TestClient, dwd: _Dwd
) -> None:
    """The period was skipped with a log line and nothing in the answer; now `file-skipped` names the directory."""
    _without_description(dwd)

    response = client.get(
        "/api/v1/stations", params={"provider": "dwd", "network": "observation", "parameters": _MONTHLY, "all": "true"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [station["station_id"] for station in body["stations"]] == ["00044"]
    assert [warning["message"] for warning in _skipped(body)] == [_NO_DESCRIPTION_WARNING]
    assert "Cache-Control" not in response.headers


def test_rest_a_history_of_a_period_without_a_description_is_not_cached(client: TestClient, dwd: _Dwd) -> None:
    """A partial answer carried `public, max-age=3600` and an `ETag`: with the warning it carries neither."""
    _without_description(dwd)

    response = client.get("/api/v1/history", params={**_PARAMS, "parameters": _MONTHLY})

    assert response.status_code == 200
    body = response.json()
    assert [warning["message"] for warning in _skipped(body)] == [_NO_DESCRIPTION_WARNING]
    assert "Cache-Control" not in response.headers
    assert "ETag" not in response.headers


def test_cli_stations_of_a_period_without_a_description_are_those_of_the_others_with_a_warning(dwd: _Dwd) -> None:
    """The command line answers the stations of `recent`, exit 0, and the warning is in its metadata."""
    _without_description(dwd)

    exit_code, body, output = _cli("stations", _MONTHLY, "--all")

    assert exit_code == 0, output
    assert body is not None
    assert [station["station_id"] for station in body["stations"]] == ["00044"]
    assert [warning["message"] for warning in _skipped(body)] == [_NO_DESCRIPTION_WARNING]


def test_rest_stations_of_a_dataset_whose_only_directory_has_no_description_are_none_with_a_warning(
    client: TestClient, dwd: _Dwd
) -> None:
    """The solar datasets list one directory for every period: no station, and the warning says why."""
    _without_description(dwd, "climate/hourly/solar/")

    response = client.get(
        "/api/v1/stations",
        params={"provider": "dwd", "network": "observation", "parameters": "hourly/solar", "all": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stations"] == []
    (skipped,) = _skipped(body)
    assert "The directory `climate/hourly/solar/` lists no description of its stations" in skipped["message"]
    assert "historical and recent stations of hourly/solar" in skipped["message"]


def test_python_the_stations_of_a_period_without_a_description_log_and_record_the_warning(
    dwd: _Dwd, caplog: pytest.LogCaptureFixture
) -> None:
    """`all()` goes on without the period and warns once: a log line, and what a response records."""
    _without_description(dwd)
    begin_response()

    with caplog.at_level(logging.WARNING):
        stations = _request().all().df

    assert stations.get_column("station_id").to_list() == ["00044"]
    assert [warning["message"] for warning in recorded_warnings()] == [_NO_DESCRIPTION_WARNING]
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING] == [
        _NO_DESCRIPTION_WARNING
    ]


@pytest.mark.usefixtures("dwd")
def test_python_a_mocked_meta_file_error_without_a_url_is_the_period_skipped_all_the_same() -> None:
    """A `MetaFileNotFoundError` that names no directory (a caller's own, a mock) is told for the period's directory."""
    begin_response()
    with patch.object(api, "create_meta_index_for_climate_observations", side_effect=MetaFileNotFoundError("none")):
        stations = _request().all().df

    assert stations.is_empty()
    assert sorted(warning["message"].split(" lists no")[0] for warning in recorded_warnings()) == [
        "The directory `climate/monthly/kl/historical/`",
        "The directory `climate/monthly/kl/recent/`",
    ]


def test_a_directory_that_gets_its_description_is_looked_up_at_once(client: TestClient, dwd: _Dwd) -> None:
    """The listing of a directory with no description is not kept: DWD uploads it, the next request sees it.

    A listing with files is kept for 12 hours, so the skip would have outlived the directory being whole.
    """
    _without_description(dwd)
    first = client.get(
        "/api/v1/stations", params={"provider": "dwd", "network": "observation", "parameters": _MONTHLY, "all": "true"}
    )
    assert _skipped(first.json())

    dwd.server.directories[dwd._path(_MONTHLY_HISTORICAL)] = _FILES  # noqa: SLF001
    second = client.get(
        "/api/v1/stations", params={"provider": "dwd", "network": "observation", "parameters": _MONTHLY, "all": "true"}
    )

    assert _warnings(second.json()) == []
    assert [station["station_id"] for station in second.json()["stations"]] == ["00044"]


def test_a_directory_with_a_description_is_kept_in_the_listings_cache(client: TestClient, dwd: _Dwd) -> None:
    """The control: a whole directory is listed once for the 12 hours, so the second request asks nothing of it."""
    params = {"provider": "dwd", "network": "observation", "parameters": _MONTHLY, "all": "true"}
    assert client.get("/api/v1/stations", params=params).status_code == 200
    dwd.server.requests.clear()

    assert client.get("/api/v1/stations", params=params).status_code == 200

    assert [path for _, path in dwd.server.requests if "/monthly/kl/historical" in path] == []


@pytest.mark.parametrize(
    "files",
    [
        pytest.param([*_WIND_FILES, _FX6], id="no-fx3"),
        pytest.param([*_WIND_FILES, _FX3], id="no-fx6"),
        pytest.param(_WIND_FILES, id="neither"),
    ],
)
def test_rest_stations_of_the_extreme_wind_without_a_description_of_a_series_skip_the_period(
    client: TestClient, dwd: _Dwd, files: list[str]
) -> None:
    """The first of the two descriptions was indexed with `[0]` of nothing: an `IndexError`, a 500."""
    dwd.server.directories[dwd._path(_WIND_HISTORICAL)] = files  # noqa: SLF001
    dwd.server.directories[dwd._path(_WIND_HISTORICAL.replace("historical", "recent"))] = [  # noqa: SLF001
        *_WIND_FILES,
        _FX3,
        _FX6,
    ]

    response = client.get(
        "/api/v1/stations", params={"provider": "dwd", "network": "observation", "parameters": _WIND, "all": "true"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [station["station_id"] for station in body["stations"]] == ["00044"]
    (skipped,) = _skipped(body)
    assert skipped["message"].startswith(
        f"The directory `{_WIND_HISTORICAL}` lists no description of its stations, so the historical stations of "
    )


@pytest.mark.parametrize(("series", "files"), [("FX3", [*_WIND_FILES, _FX6]), ("FX6", [*_WIND_FILES, _FX3])])
def test_the_extreme_wind_names_the_series_it_found_no_description_of(dwd: _Dwd, series: str, files: list[str]) -> None:
    """The error says which of the two is missing, and the directory."""
    dwd.server.directories[dwd._path(_WIND_HISTORICAL)] = files  # noqa: SLF001
    settings = Settings(cache_disable=True)

    with pytest.raises(DescriptionFileMissingError, match=rf"No {series} meta file was found amongst the files at"):
        metaindex._create_meta_index_for_subdaily_extreme_wind(Period.HISTORICAL, settings)  # noqa: SLF001


def test_the_extreme_wind_with_both_descriptions_is_looked_up_whole(client: TestClient, dwd: _Dwd) -> None:
    """The control: with FX3 and FX6 listed, nothing is skipped and nothing is said."""
    for period in ("historical", "recent"):
        dwd.server.directories[dwd._path(_WIND_HISTORICAL.replace("historical", period))] = [  # noqa: SLF001
            *_WIND_FILES,
            _FX3,
            _FX6,
        ]

    response = client.get(
        "/api/v1/stations", params={"provider": "dwd", "network": "observation", "parameters": _WIND, "all": "true"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [station["station_id"] for station in body["stations"]] == ["00044"]
    assert _skipped(body) == []


def test_the_error_of_a_missing_description_keeps_its_message_and_survives_a_copy() -> None:
    """It is the `MetaFileNotFoundError` it was, with the message it had, and a copy or a pickle rebuilds it."""
    error = DescriptionFileMissingError("https://opendata.dwd.de/x/")

    assert isinstance(error, MetaFileNotFoundError)
    assert isinstance(error, FileNotFoundError)
    assert str(error) == "No meta file was found amongst the files at https://opendata.dwd.de/x/."
    for twin in (copy.copy(error), pickle.loads(pickle.dumps(error))):  # noqa: S301
        assert type(twin) is DescriptionFileMissingError
        assert (twin.url, twin.what) == (error.url, error.what)
        assert str(twin) == str(error)


# --- a station that only a skipped directory lists is no 404 (GH-3834) ----------------------------------------------


def _only_the_skipped_directory_lists_00044(dwd: _Dwd, how: str, directory: str = _MONTHLY_HISTORICAL) -> None:
    """Make `directory` the only one that lists 00044, and empty, missing or without its description."""
    recent = directory.replace("historical", "recent")
    dwd.server.directories[dwd._path(recent)] = [  # noqa: SLF001
        "stundenwerte_KL_00045_19700101_20241231_akt.zip",
        "KL_Beschreibung_Stationen.txt",
    ]
    if how == "undescribed":
        _without_description(dwd, directory)
    else:
        dwd.set(**{how: (directory,)})


_HOWS = [
    pytest.param("empty", "its listing came back empty or missing", id="empty"),
    pytest.param("missing", "its listing came back empty or missing", id="missing"),
    pytest.param("undescribed", "it lists no description of its stations", id="no-description"),
]
_ESTIMATE = {"parameters": "monthly/climate_summary/temperature_air_mean_2m"}


def _names_the_directory(response: Response, reason: str, directory: str = _MONTHLY_HISTORICAL) -> None:
    """Assert the answer is the 502 that says which directory the lookup went without."""
    assert response.status_code == 502, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:upstream-failed"
    assert body["detail"].startswith("No station found for 00044. The lookup of the stations went without ")
    assert f"the directory `{directory}` ({reason})" in body["detail"]
    assert "Try again later" in body["detail"]


@pytest.mark.parametrize(("how", "reason"), _HOWS)
@pytest.mark.parametrize("route", ["summarize", "interpolate"])
def test_rest_a_station_only_the_skipped_directory_lists_is_a_502_that_names_it(
    client: TestClient, dwd: _Dwd, route: str, how: str, reason: str
) -> None:
    """A 404 said the station does not exist, which it does: it is the 502 that names the directory (GH-3834)."""
    _only_the_skipped_directory_lists_00044(dwd, how)

    response = client.get(
        f"/api/v1/{route}",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "00044",
            "timestamp": "2020-01-01",
            **_ESTIMATE,
        },
    )

    _names_the_directory(response, reason)


@pytest.mark.parametrize(("how", "reason"), _HOWS)
@pytest.mark.parametrize(
    ("route", "extra"),
    [
        pytest.param("stripes/values", {}, id="stripes-values"),
        pytest.param("stripes/image", {"format": "png"}, id="image"),
    ],
)
def test_rest_a_stripes_station_only_the_skipped_directory_lists_is_a_502_that_names_it(
    client: TestClient, dwd: _Dwd, route: str, extra: dict[str, str], how: str, reason: str
) -> None:
    """The stripes list their stations from `annual/kl/historical`: with it skipped the station is no 404 either."""
    directory = _ANNUAL_HISTORICAL
    if how == "undescribed":
        _without_description(dwd, directory)
    else:
        dwd.set(**{how: (directory,)})

    response = client.get(f"/api/v1/{route}", params={"kind": "temperature", "station": "00044", **extra})

    _names_the_directory(response, reason, directory)


@pytest.mark.parametrize("route", ["summarize", "interpolate"])
def test_rest_a_station_that_does_not_exist_is_still_a_404_where_nothing_was_skipped(
    client: TestClient, dwd: _Dwd, route: str
) -> None:
    """The control: every directory is listed, so a station nobody lists is unknown, and a 404."""
    response = client.get(
        f"/api/v1/{route}",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "09999",
            "timestamp": "2020-01-01",
            **_ESTIMATE,
        },
    )

    assert response.status_code == 404
    assert "no station found for 09999" in response.json()["detail"]
    assert dwd.asked


@pytest.mark.usefixtures("dwd")
def test_rest_a_stripes_station_that_does_not_exist_is_still_a_404_where_nothing_was_skipped(
    client: TestClient,
) -> None:
    """The control for the stripes."""
    response = client.get("/api/v1/stripes/values", params={"kind": "temperature", "station": "09999"})

    assert response.status_code == 404


@pytest.mark.parametrize("route", ["summarize", "interpolate"])
def test_rest_a_station_that_does_not_exist_is_a_502_when_a_directory_was_skipped_and_may_have_listed_it(
    client: TestClient, dwd: _Dwd, route: str
) -> None:
    """A station that no listing has, with another directory skipped, is not known to be unknown: the 502 says so."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get(
        f"/api/v1/{route}",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "09999",
            "timestamp": "2020-01-01",
            **_ESTIMATE,
        },
    )

    assert response.status_code == 502
    assert "No station found for 09999." in response.json()["detail"]
    assert f"`{_MONTHLY_HISTORICAL}`" in response.json()["detail"]


@pytest.mark.parametrize("command", ["interpolate", "summarize"])
def test_cli_a_station_only_the_skipped_directory_lists_is_an_error_that_names_it(dwd: _Dwd, command: str) -> None:
    """The command line exits 1 with the error, not the usage error of a station that is not there (exit 2)."""
    _only_the_skipped_directory_lists_00044(dwd, "empty")

    result = CliRunner().invoke(
        cli,
        [
            command,
            "--provider",
            "dwd",
            "--network",
            "observation",
            "--parameters",
            "monthly/climate_summary/temperature_air_mean_2m",
            "--station",
            "00044",
            "--timestamp",
            "2020-01-01",
        ],
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, StationListingIncompleteError)
    assert f"the directory `{_MONTHLY_HISTORICAL}` (its listing came back empty or missing)" in str(result.exception)


def test_cli_a_stripes_station_only_the_skipped_directory_lists_is_an_error_that_names_it(dwd: _Dwd) -> None:
    """`stripes image` on the command line: the sentence, exit 1, and no usage error (exit 2) of a station not there."""
    dwd.set(empty=(_ANNUAL_HISTORICAL,))

    result = CliRunner().invoke(cli, ["stripes", "image", "--kind", "temperature", "--station", "00044"])

    assert result.exit_code == 1
    assert "No station found for 00044. The lookup of the stations went without" in result.output
    assert f"the directory `{_ANNUAL_HISTORICAL}` (its listing came back empty or missing)" in result.output


def test_mcp_a_station_only_the_skipped_directory_lists_is_a_tool_error_that_names_it(dwd: _Dwd) -> None:
    """The MCP tool answers the REST API's 502 and its text: the directory is there for the agent to read."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    _only_the_skipped_directory_lists_00044(dwd, "empty")
    mcp = build_mcp_server(restapi.app)

    async def _call() -> None:
        async with Client(mcp) as client:
            await client.call_tool(
                "interpolate",
                {
                    "provider": "dwd",
                    "network": "observation",
                    "station": "00044",
                    "timestamp": "2020-01-01",
                    **_ESTIMATE,
                },
            )

    with pytest.raises(ToolError, match="HTTP error 502") as error:
        asyncio.run(_call())
    assert f"the directory `{_MONTHLY_HISTORICAL}` (its listing came back empty or missing)" in str(error.value)


@pytest.mark.parametrize(("how", "reason"), _HOWS)
@pytest.mark.parametrize("method", ["interpolate_by_station_id", "summarize_by_station_id"])
def test_python_a_station_only_the_skipped_directory_lists_is_an_upstream_error_that_names_it(
    dwd: _Dwd, method: str, how: str, reason: str
) -> None:
    """The library raises it: an `UpstreamError`, not the `StationNotFoundError` that says it does not exist."""
    _only_the_skipped_directory_lists_00044(dwd, how)

    with pytest.raises(StationListingIncompleteError) as error:
        getattr(_request(), method)("00044")

    assert isinstance(error.value, UpstreamError)
    assert not isinstance(error.value, StationNotFoundError)
    assert error.value.station_id == "00044"
    assert error.value.gaps == {f"`{_MONTHLY_HISTORICAL}`": reason}


def test_python_a_station_that_a_skipped_directory_does_not_hide_is_found(dwd: _Dwd) -> None:
    """The control: 00044 is listed by `recent`, so the skipped `historical` costs nothing and nothing is raised."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))

    latitude, longitude, _ = _request()._get_position_by_station_id("00044")  # noqa: SLF001

    assert (latitude, longitude) == (52.9336, 8.237)


def test_python_a_lookup_that_skips_nothing_has_no_gaps_even_after_one_that_did(dwd: _Dwd) -> None:
    """The gaps are those of the last lookup: the directory is filled again, and the next `all()` clears them."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    request = _request()
    request.all()
    assert request._lookup_gaps() == {f"`{_MONTHLY_HISTORICAL}`": ListingGap(EMPTY_LISTING)}  # noqa: SLF001

    dwd.server.directories[dwd._path(_MONTHLY_HISTORICAL)] = _FILES  # noqa: SLF001
    request.all()

    assert request._lookup_gaps() == {}  # noqa: SLF001


def test_the_error_of_an_incomplete_listing_names_every_directory_and_survives_a_copy() -> None:
    """Two directories are two clauses of one sentence, and a copy or a pickle rebuilds the error."""
    error = StationListingIncompleteError("00044", {"`a/`": "its listing came back empty or missing", "`b/`": "x"})

    assert str(error) == (
        "No station found for 00044. The lookup of the stations went without the directory `a/` (its listing came "
        "back empty or missing) and the directory `b/` (x), so a station that only it lists is not found, and this "
        "may be one. Try again later."
    )
    for twin in (copy.copy(error), pickle.loads(pickle.dumps(error))):  # noqa: S301
        assert type(twin) is StationListingIncompleteError
        assert (twin.station_id, twin.gaps) == (error.station_id, error.gaps)
        assert str(twin) == str(error)


def test_the_listing_of_an_extreme_wind_directory_without_a_description_is_not_kept(
    client: TestClient, dwd: _Dwd
) -> None:
    """The extreme wind is listed with its own expiry: the directory that gets its FX3 and FX6 is looked up at once."""
    historical = dwd._path(_WIND_HISTORICAL)  # noqa: SLF001
    recent = dwd._path(_WIND_HISTORICAL.replace("historical", "recent"))  # noqa: SLF001
    dwd.server.directories[historical] = _WIND_FILES
    dwd.server.directories[recent] = [*_WIND_FILES, _FX3, _FX6]
    params = {"provider": "dwd", "network": "observation", "parameters": _WIND, "all": "true"}
    assert _skipped(client.get("/api/v1/stations", params=params).json())

    dwd.server.directories[historical] = [*_WIND_FILES, _FX3, _FX6]
    second = client.get("/api/v1/stations", params=params)

    assert _warnings(second.json()) == []


def test_python_the_derived_lookup_records_the_directory_it_went_without(dwd: _Dwd) -> None:
    """`dwd/derived` has the gaps of its lookup too, so its estimates name the directory as the observations do."""
    directory = "derived_germany/climate/hourly/duett/radiation_global/historical/"
    dwd.set(empty=(directory,))
    request = DwdDerivedRequest(parameters=[("hourly", "radiation_global")], settings=Settings(cache_disable=True))

    request.all()

    assert request._lookup_gaps() == {  # noqa: SLF001
        "`derived_germany/climate/hourly/duett/radiation_global/historical/`": ListingGap(EMPTY_LISTING)
    }


@pytest.mark.parametrize("how", ["empty", "undescribed"])
def test_rest_ndjson_stations_of_a_skipped_directory_tell_it_in_the_head_and_the_end(
    client: TestClient, dwd: _Dwd, how: str
) -> None:
    """The stream tells a skipped directory as the JSON answer does: in the headers, the head line and the end line."""
    if how == "undescribed":
        _without_description(dwd)
    else:
        dwd.set(empty=(_MONTHLY_HISTORICAL,))

    response = client.get(
        "/api/v1/stations",
        params={"provider": "dwd", "network": "observation", "parameters": _MONTHLY, "all": "true", "format": "ndjson"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["X-Wetterdienst-Warnings"] == "file-skipped"
    lines = [json.loads(line) for line in response.text.splitlines()]
    assert [warning["code"] for warning in lines[0]["metadata"]["warnings"]] == ["file-skipped"]
    assert [warning["code"] for warning in lines[-1]["end"]["warnings"]] == ["file-skipped"]
    assert "`climate/monthly/kl/historical/`" in lines[0]["metadata"]["warnings"][0]["message"]


def test_rest_ndjson_values_of_a_period_without_a_description_tell_it(client: TestClient, dwd: _Dwd) -> None:
    """The values of a station read the stations first: the stream carries the warning of the lookup too."""
    _without_description(dwd)

    response = client.get(
        "/api/v1/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": _MONTHLY,
            "stations": "00044",
            "format": "ndjson",
        },
    )

    assert response.status_code == 200, response.text
    assert "file-skipped" in response.headers["X-Wetterdienst-Warnings"]
    lines = [json.loads(line) for line in response.text.splitlines()]
    assert any(warning["code"] == "file-skipped" for warning in lines[-1]["end"]["warnings"])


# --- what a skipped directory can tell: its ids, or nothing (GH-3834) ------------------------------------------------


def test_python_an_undescribed_directory_records_the_stations_its_files_name(dwd: _Dwd) -> None:
    """The files carry the station ids, which the gap keeps, so an id that is not among them is no gap's business."""
    _without_description(
        dwd, files=["stundenwerte_KL_00044_19700101_20241231_hist.zip", "stundenwerte_KL_123_x_hist.zip"]
    )
    request = _request()

    request.all()

    assert request._lookup_gaps() == {  # noqa: SLF001
        f"`{_MONTHLY_HISTORICAL}`": ListingGap(NO_DESCRIPTION, frozenset({"00044", "00123"}))
    }
    assert request._gaps_that_may_list("44") == {f"`{_MONTHLY_HISTORICAL}`": NO_DESCRIPTION}  # noqa: SLF001
    assert request._gaps_that_may_list("00123") == {f"`{_MONTHLY_HISTORICAL}`": NO_DESCRIPTION}  # noqa: SLF001
    assert request._gaps_that_may_list("09999") == {}  # noqa: SLF001


def test_python_an_empty_directory_may_hold_any_station(dwd: _Dwd) -> None:
    """Nothing says which stations an empty or missing directory holds: every id may be one."""
    dwd.set(empty=(_MONTHLY_HISTORICAL,))
    request = _request()

    request.all()

    assert request._lookup_gaps() == {f"`{_MONTHLY_HISTORICAL}`": ListingGap(EMPTY_LISTING)}  # noqa: SLF001
    assert request._gaps_that_may_list("09999") == {f"`{_MONTHLY_HISTORICAL}`": EMPTY_LISTING}  # noqa: SLF001


def test_python_the_extreme_wind_without_a_description_records_the_stations_its_files_name(dwd: _Dwd) -> None:
    """The wind files name their stations too, whichever of the two descriptions is missing."""
    dwd.server.directories[dwd._path(_WIND_HISTORICAL)] = [*_WIND_FILES, _FX6]  # noqa: SLF001
    request = _request(_WIND)

    request.all()

    assert request._lookup_gaps()[f"`{_WIND_HISTORICAL}`"] == ListingGap(  # noqa: SLF001
        NO_DESCRIPTION, frozenset({"00044"})
    )


@pytest.mark.parametrize("route", ["summarize", "interpolate"])
def test_rest_a_station_the_undescribed_directory_does_not_name_is_the_404_it_was(
    client: TestClient, dwd: _Dwd, route: str
) -> None:
    """An id that is not in the file names of the directory without a description is unknown: the usual 404."""
    _only_the_skipped_directory_lists_00044(dwd, "undescribed")

    response = client.get(
        f"/api/v1/{route}",
        params={
            "provider": "dwd",
            "network": "observation",
            "station": "09999",
            "timestamp": "2020-01-01",
            **_ESTIMATE,
        },
    )

    assert response.status_code == 404, response.text
    assert "no station found for 09999" in response.json()["detail"]


@pytest.mark.parametrize("route", ["stripes/values", "stripes/image"])
def test_rest_a_stripes_station_the_undescribed_directory_does_not_name_is_the_404_it_was(
    client: TestClient, dwd: _Dwd, route: str
) -> None:
    """The same for the stripes, whose lookup is the `annual` directory."""
    _without_description(dwd, _ANNUAL_HISTORICAL)

    response = client.get(f"/api/v1/{route}", params={"kind": "temperature", "station": "09999"})

    assert response.status_code == 404, response.text


def test_rest_an_undescribed_directory_that_names_the_station_is_the_502(client: TestClient, dwd: _Dwd) -> None:
    """The control: the same directory, an id among its file names (padded or not), is the 502."""
    _only_the_skipped_directory_lists_00044(dwd, "undescribed")

    for station in ("00044", "44"):
        response = client.get(
            "/api/v1/summarize",
            params={
                "provider": "dwd",
                "network": "observation",
                "station": station,
                "timestamp": "2020-01-01",
                **_ESTIMATE,
            },
        )
        assert response.status_code == 502, response.text


def test_rest_a_cache_that_cannot_drop_the_listing_leaves_the_skip_a_200_with_the_warning(
    client: TestClient, dwd: _Dwd, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ListingStore.delete` raising (busy, read-only) is no 500: the period is skipped and the warning is told."""
    import sqlite3  # noqa: PLC0415

    from wetterdienst.util.listing_cache import ListingStore  # noqa: PLC0415

    def busy(_store: object, _key: object) -> bool:
        msg = "database is locked"
        raise sqlite3.OperationalError(msg)

    monkeypatch.setattr(ListingStore, "delete", busy)
    _without_description(dwd)

    response = client.get(
        "/api/v1/stations", params={"provider": "dwd", "network": "observation", "parameters": _MONTHLY, "all": "true"}
    )

    assert response.status_code == 200, response.text
    assert [warning["message"] for warning in _skipped(response.json())] == [_NO_DESCRIPTION_WARNING]
