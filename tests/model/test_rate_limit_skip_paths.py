# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A 429 ends a walk that lets failed files go, with the `ProviderRateLimitError`, and asks nothing further (GH-4053).

#4052 made a 429 the rate-limit error where a failure reaches `File.raise_if_exception`, the listings or `as_outage`.
The places that let a failed download go with a `file-skipped` warning never got there: a limit is not a file to let go,
the files after it meet it too, and a provider that is asked on is a provider that is asked after it said to wait. A 404
or an empty listing on the same paths is still skipped, with its warning.

A local server that answers as DWD's does stands in for the upstream (`tests/nginx_stub.py`), and every request it
meets is counted: what is held is "asked once", read off the server and not off the code.
"""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

import polars as pl
import pytest

from tests.nginx_stub import NginxLike, serving
from wetterdienst import Settings
from wetterdienst.exceptions import ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import metaindex as derived_metaindex
from wetterdienst.provider.dwd.derived.download import download_climate_derived_data
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest, fileindex
from wetterdienst.provider.dwd.road.api import DwdRoadRequest
from wetterdienst.util.network import (
    File,
    download_file,
    download_files,
    list_remote_directory_fsspec,
    list_remote_files_fsspec,
)
from wetterdienst.util.response_warnings import SkipCause, begin_response, collecting, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

_DWD = "https://opendata.dwd.de"
_CDC = "/climate_environment/CDC/"
_RECENT = f"{_CDC}observations_germany/climate/daily/kl/recent/"
_HISTORICAL = f"{_CDC}observations_germany/climate/daily/kl/historical/"
_ARCHIVE = "tageswerte_KL_00044_akt.zip"
_DESCRIPTION = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "---------- ------\r\n"
    "00044 20070401 20261105            44     52.9336    8.2370 Großenkneten                             "
    "Niedersachsen                            Frei\r\n"
).encode("latin-1")
_DERIVED_DIRECTORY = f"{_CDC}derived_germany/climate/hourly/duett/sunshine_duration/"
_DERIVED_ARCHIVE = "stundenwerte_SD_00044_akt.zip"
_DERIVED_DESCRIPTION_PATH = f"{_CDC}help/sd_duett_Beschreibung_Stationen.txt"
_DERIVED_DESCRIPTION = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "---------- ------\r\n"
    "00044 20240401 20261014            44     52.9336    8.2370 Grossenkneten                             "
    "Niedersachsen                            Frei\r\n"
).encode("latin-1")
#: the seconds DWD's 429 asks for in these tests
WAIT = 7


class _Dwd:
    """The server, and what the lookups ask of it: its requests, as paths."""

    def __init__(self, server: NginxLike, settings: Settings) -> None:
        self.server = server
        self.settings = settings

    def asked(self, path: str) -> int:
        """Count the GETs the server met for a path."""
        return len([1 for method, asked in self.server.requests if method == "GET" and asked.split("?")[0] == path])

    def limit(self, path: str) -> None:
        """Answer a path with a 429 that asks for `WAIT` seconds."""
        self.server.statuses[path] = 429
        self.server.status_headers[path] = [("Retry-After", str(WAIT))]


@pytest.fixture
def dwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Dwd]:
    """Stand in for DWD's server: the listings of `opendata.dwd.de` go to a local one, which lists the URLs it holds.

    Every directory lists the archive of station 00044 and the description of the stations; the archive and the
    description are served from the same server, so the downloads are real ones.
    """
    with serving() as server:
        settings = Settings(cache_dir=str(tmp_path / "cache"))

        def listing(url: str, settings: Settings, cache_expiry: CacheExpiry = CacheExpiry.FILEINDEX) -> list[str]:
            return list_remote_files_fsspec(
                url.replace(_DWD, server.base), settings=settings, cache_expiry=cache_expiry
            )

        def download(url: str, **kwargs: object) -> File:
            return download_file(url.replace(_DWD, server.base), **kwargs)

        monkeypatch.setattr(fileindex, "list_remote_files_fsspec", listing)
        monkeypatch.setattr(derived_metaindex, "download_file", download)
        for period in ("recent", "historical"):
            server.directories[f"{_DERIVED_DIRECTORY}{period}/"] = [_DERIVED_ARCHIVE]
            server.files.add(f"{_DERIVED_DIRECTORY}{period}/{_DERIVED_ARCHIVE}")
        server.contents[_DERIVED_DESCRIPTION_PATH] = _DERIVED_DESCRIPTION
        for directory in (_RECENT, _HISTORICAL):
            server.directories[directory] = [_ARCHIVE, "KL_Tageswerte_Beschreibung_Stationen.txt"]
            server.contents[f"{directory}KL_Tageswerte_Beschreibung_Stationen.txt"] = _DESCRIPTION
            server.files.add(f"{directory}{_ARCHIVE}")
        begin_response()
        yield _Dwd(server, settings)


def _request(dwd: _Dwd) -> DwdObservationRequest:
    return DwdObservationRequest(parameters=[("daily", "climate_summary")], periods="recent", settings=dwd.settings)


def _derived(dwd: _Dwd) -> DwdDerivedRequest:
    return DwdDerivedRequest(parameters=[("hourly", "sunshine_duration")], periods="recent", settings=dwd.settings)


def _skipped() -> list[str]:
    return [warning["message"] for warning in recorded_warnings() if warning["code"] == "file-skipped"]


def test_a_429_on_the_listing_of_the_stations_lookup_raises(dwd: _Dwd) -> None:
    """The lookup lists the directory of each period: a 429 is raised, with DWD's wait, after one request."""
    dwd.limit(_RECENT)

    with pytest.raises(ProviderRateLimitError) as raised:
        _request(dwd).all()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(_RECENT) == 1


def test_an_empty_listing_of_the_stations_lookup_is_still_skipped(dwd: _Dwd) -> None:
    """What the lookup skipped before it still skips, with its `file-skipped` warning: the other side of the 429."""
    dwd.server.directories[_RECENT] = []

    _request(dwd).all()

    assert any("came back empty or missing" in message for message in _skipped())


def test_a_429_on_an_archive_of_the_values_walk_raises_and_the_archive_is_asked_once(dwd: _Dwd) -> None:
    """`download_climate_observations_data` lets a withdrawn archive go; a limit is raised, with DWD's wait."""
    dwd.limit(f"{_RECENT}{_ARCHIVE}")

    with pytest.raises(ProviderRateLimitError) as raised:
        _request(dwd).filter_by_station_id("00044").values().all()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(f"{_RECENT}{_ARCHIVE}") == 1


def test_a_404_on_an_archive_of_the_values_walk_is_still_skipped(dwd: _Dwd) -> None:
    """An archive withdrawn since the listing is let go with the `file-skipped` warning, as it was."""
    dwd.server.statuses[f"{_RECENT}{_ARCHIVE}"] = 404

    values = _request(dwd).filter_by_station_id("00044").values().all()

    assert values.df.is_empty()
    assert any("00044" in message for message in _skipped())


def test_a_429_on_the_listing_of_the_values_walk_raises(dwd: _Dwd) -> None:
    """The listing of the station's files: raised, not read as a station without files, and asked once."""
    stations = _request(dwd).filter_by_station_id("00044")
    assert stations.df.height == 1
    # a limit that comes after the stations were found, and for a listing that is not cached any more
    dwd.server.requests.clear()
    dwd.limit(_RECENT)
    stations.request.settings.cache_disable = True

    with pytest.raises(ProviderRateLimitError) as raised:
        stations.values().all()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(_RECENT) == 1


def test_a_429_on_the_description_of_the_stations_lookup_raises(dwd: _Dwd) -> None:
    """The description of the stations is downloaded to know them: a 429 is raised, asked once."""
    path = f"{_RECENT}KL_Tageswerte_Beschreibung_Stationen.txt"
    dwd.limit(path)

    with pytest.raises(ProviderRateLimitError) as raised:
        _request(dwd).all()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(path) == 1


def test_a_429_on_the_history_of_a_station_raises(dwd: _Dwd) -> None:
    """The history lists the `historical` directory (a 404 or an empty one is skipped) and reads a station's archive."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")], periods="historical", settings=dwd.settings
    ).filter_by_station_id("00044")
    dwd.limit(f"{_HISTORICAL}{_ARCHIVE}")

    with pytest.raises(ProviderRateLimitError) as raised:
        list(request.history().query())

    assert raised.value.retry_after == WAIT
    assert dwd.asked(f"{_HISTORICAL}{_ARCHIVE}") == 1


def test_a_429_on_the_listing_of_the_history_raises(dwd: _Dwd) -> None:
    """`history` skips a directory that is not there (`FileNotFoundError`): a 429 is not one."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")], periods="historical", settings=dwd.settings
    ).filter_by_station_id("00044")
    dwd.server.requests.clear()
    dwd.limit(_HISTORICAL)
    request.settings.cache_disable = True

    with pytest.raises(ProviderRateLimitError):
        list(request.history().query())

    assert dwd.asked(_HISTORICAL) == 1


def test_a_429_on_the_description_of_the_derived_stations_raises(dwd: _Dwd) -> None:
    """The description of the stations of `dwd/derived` is one file: a 429 is raised, asked once."""
    dwd.limit(_DERIVED_DESCRIPTION_PATH)

    with pytest.raises(ProviderRateLimitError) as raised:
        _derived(dwd).all()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(_DERIVED_DESCRIPTION_PATH) == 1


def test_a_429_on_the_listing_of_the_derived_lookup_raises(dwd: _Dwd) -> None:
    """The lookup of `dwd/derived` skips an empty directory, as the observations do: a 429 is not one."""
    dwd.limit(f"{_DERIVED_DIRECTORY}recent/")

    with pytest.raises(ProviderRateLimitError) as raised:
        _derived(dwd).all()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(f"{_DERIVED_DIRECTORY}recent/") == 1


def test_an_empty_listing_of_the_derived_lookup_is_still_skipped(dwd: _Dwd) -> None:
    """The other side: an empty directory is let go with its `file-skipped` warning."""
    dwd.server.directories[f"{_DERIVED_DIRECTORY}recent/"] = []

    _derived(dwd).all()

    assert any("came back empty or missing" in message for message in _skipped())


def test_a_429_on_an_archive_of_the_derived_values_walk_raises_and_the_archive_is_asked_once(dwd: _Dwd) -> None:
    """`download_climate_derived_data` lets a withdrawn archive go; a limit is raised with DWD's wait."""
    path = f"{_DERIVED_DIRECTORY}recent/{_DERIVED_ARCHIVE}"
    dwd.limit(path)

    with pytest.raises(ProviderRateLimitError) as raised:
        _derived(dwd).filter_by_station_id("00044").values().all()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(path) == 1


def test_a_404_on_an_archive_of_the_derived_download_is_still_skipped(dwd: _Dwd) -> None:
    """An archive withdrawn since the listing is let go and told to the walk (`note_skipped_download`), as it was."""
    path = f"{_DERIVED_DIRECTORY}recent/{_DERIVED_ARCHIVE}"
    dwd.server.statuses[path] = 404
    noted: list[SkipCause] = []

    with collecting(lambda _whole_request, cause: noted.append(cause)):
        files = download_climate_derived_data(pl.Series([dwd.server.base + path]), dwd.settings, Period.RECENT)

    assert files == []
    assert noted == [SkipCause.WITHDRAWN]


# --- dwd/road: a group is read from many files, and the ones that arrived answer for the ones that did not -----------

_ROAD_FILES = ("swis2-ISXD70_DWDD_131200-2609131200-DD---bin", "swis2-ISXD70_DWDD_131215-2609131215-DD---bin")


@pytest.fixture
def road(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Dwd]:
    """Serve a road group of two files from the local server: each is a 10 byte file, which the reader leaves out."""
    from wetterdienst.provider.dwd.road import api  # noqa: PLC0415

    with serving() as server:
        settings = Settings(cache_dir=str(tmp_path / "cache"))
        for name in _ROAD_FILES:
            server.contents[f"/road/DD/{name}"] = b"x" * 10
        monkeypatch.setattr(
            api,
            "list_remote_files_fsspec",
            lambda *_args, **_kwargs: [f"{server.base}/road/DD/{name}" for name in _ROAD_FILES],
        )
        yield _Dwd(server, settings)


def _collect_road_group(settings: Settings) -> list[SkipCause]:
    from tests.provider.dwd.road.test_api import _stub_stations  # noqa: PLC0415

    values = _stub_stations().values()
    values.sr.request.settings = settings
    noted: list[SkipCause] = []
    with collecting(lambda _whole_request, cause: noted.append(cause)):
        values._collect_station_parameter_or_dataset("A006", DwdRoadRequest.metadata["15_minutes"]["data"])  # noqa: SLF001
    return noted


def test_a_429_on_one_file_of_a_road_group_raises_and_every_file_is_asked_once(road: _Dwd) -> None:
    """A group whose other files arrived is answered from those, as a gap, for a 404: a limit is no gap."""
    road.limit(f"/road/DD/{_ROAD_FILES[1]}")

    with pytest.raises(ProviderRateLimitError) as raised:
        _collect_road_group(road.settings)

    assert raised.value.retry_after == WAIT
    assert [road.asked(f"/road/DD/{name}") for name in _ROAD_FILES] == [1, 1]


def test_a_404_on_one_file_of_a_road_group_is_still_skipped_with_the_files_that_arrived(road: _Dwd) -> None:
    """A file withdrawn since the listing is a gap in the window, which the walk is told."""
    road.server.statuses[f"/road/DD/{_ROAD_FILES[1]}"] = 404

    assert _collect_road_group(road.settings) == [SkipCause.WITHDRAWN]


# --- meteofrance: the failed files of a climate download are asked once more, which a 429 is not ----------------------


def test_a_429_of_a_meteofrance_climate_resource_is_not_asked_again(road: _Dwd) -> None:
    """The download asks a failed resource once more (a 5xx may be gone); a 429 is the provider saying to wait."""
    from wetterdienst.provider.meteofrance.observation.api import _download_climate_resources  # noqa: PLC0415

    url = f"{road.server.base}/climate/file.csv.gz"
    road.limit("/climate/file.csv.gz")

    files = _download_climate_resources([{"url": url, "title": "previous 1950-2025"}], road.settings)

    assert road.asked("/climate/file.csv.gz") == 1
    assert files[url].is_rate_limited
    with pytest.raises(ProviderRateLimitError) as raised:
        files[url].raise_if_exception()
    assert raised.value.retry_after == WAIT


def test_a_503_of_a_meteofrance_climate_resource_is_still_asked_once_more(road: _Dwd) -> None:
    """The other side: what may be gone the next time is asked again (the requests of the retries are counted)."""
    from wetterdienst.provider.meteofrance.observation.api import _download_climate_resources  # noqa: PLC0415

    url = f"{road.server.base}/climate/file.csv.gz"
    road.server.statuses["/climate/file.csv.gz"] = 503

    files = _download_climate_resources([{"url": url, "title": "previous 1950-2025"}], road.settings)

    assert not files[url].is_rate_limited
    assert road.asked("/climate/file.csv.gz") > 1


# --- the readers that degrade to a narrower answer for a failed read: DMO's coverage, Hubeau's elevations ------------


def _dmo(settings: Settings) -> DwdDmoRequest:
    return DwdDmoRequest(parameters=[("hourly", "icon")], settings=settings)


@pytest.fixture
def dmo(monkeypatch: pytest.MonkeyPatch, road: _Dwd) -> _Dwd:
    """Send the listings of DMO's directories to the local server, as `opendata.dwd.de` is not asked."""
    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    def to_local(function: Callable[..., object]) -> Callable[..., object]:
        return lambda url, *args, **kwargs: function(url.replace(_DWD, road.server.base), *args, **kwargs)

    monkeypatch.setattr(api, "list_remote_directory_fsspec", to_local(list_remote_directory_fsspec))
    monkeypatch.setattr(api, "list_remote_files_fsspec", to_local(list_remote_files_fsspec))
    return road


def test_a_429_on_the_listing_of_the_dmo_coverage_raises(dmo: _Dwd) -> None:
    """The directory that says which stations a product covers falls back to the wider catalogue; a 429 is raised."""
    directory = urlsplit(_dmo_directory_url()).path
    dmo.limit(directory)

    with pytest.raises(ProviderRateLimitError) as raised:
        _dmo(dmo.settings)._read_covered_station_ids("icon")  # noqa: SLF001

    assert raised.value.retry_after == WAIT
    assert dmo.asked(directory) == 1


def test_a_missing_directory_of_the_dmo_coverage_is_still_a_fallback_with_a_warning(dmo: _Dwd) -> None:
    """The other side: what is not a limit still degrades to the shared catalogue, as it did (`None` and a warning)."""
    dmo.server.statuses[urlsplit(_dmo_directory_url()).path] = 404

    assert _dmo(dmo.settings)._read_covered_station_ids("icon") is None  # noqa: SLF001


def test_a_429_on_the_listing_of_the_dmo_runs_raises(dmo: _Dwd) -> None:
    """The newest run of `all_stations` describes the stations the catalogue omits: a 429 is raised, not a `None`."""
    from wetterdienst.provider.dwd.dmo.api import DwdDmoStationGroup, _dmo_kmz_path  # noqa: PLC0415

    directory = urlsplit(urljoin(_DWD, _dmo_kmz_path("icon", DwdDmoStationGroup.ALL_STATIONS, station_id=None))).path
    dmo.limit(directory)

    with pytest.raises(ProviderRateLimitError):
        _dmo(dmo.settings)._read_station_metadata_from_placemarks("icon")  # noqa: SLF001

    assert dmo.asked(directory) == 1


def test_a_429_on_the_hubeau_referential_raises_and_a_server_error_only_leaves_the_elevations_out(
    monkeypatch: pytest.MonkeyPatch, road: _Dwd
) -> None:
    """The referential only adds the elevations, and is let go when it cannot be read: a limit is not that."""
    from wetterdienst.provider.eaufrance.hubeau import api as hubeau_api  # noqa: PLC0415

    monkeypatch.setattr(hubeau_api, "_SITES_ENDPOINT", f"{road.server.base}/sites")
    request = object.__new__(hubeau_api.HubeauRequest)
    request.settings = road.settings

    road.server.statuses["/sites"] = 404
    assert request._site_elevations().is_empty()  # noqa: SLF001

    road.limit("/sites")
    road.server.requests.clear()
    with pytest.raises(ProviderRateLimitError) as raised:
        request._site_elevations()  # noqa: SLF001
    assert raised.value.retry_after == WAIT
    assert road.asked("/sites") == 1


def _dmo_directory_url() -> str:
    from wetterdienst.provider.dwd.dmo.api import _dmo_station_dir  # noqa: PLC0415

    return urljoin(_DWD, _dmo_station_dir("icon"))


def test_a_429_in_a_batch_of_meteofrance_resources_stops_the_retries_and_the_next_batch_and_is_raised_first(
    road: _Dwd,
) -> None:
    """A 503 before the 429 is not asked again, the batch of another expiry is not downloaded, the 429 is raised."""
    from wetterdienst.provider.meteofrance.observation.api import (  # noqa: PLC0415
        _download_climate_resources,
        _raise_if_climate_download_failed,
    )

    base = road.server.base
    urls = {name: f"{base}/climate/{name}.csv.gz" for name in ("a", "b", "old")}
    road.server.statuses["/climate/a.csv.gz"] = 503
    road.limit("/climate/b.csv.gz")
    road.server.contents["/climate/old.csv.gz"] = b"x"
    recent = "previous 1950-2025"
    resources = [
        {"url": urls["a"], "title": recent},
        {"url": urls["b"], "title": recent},
        # kept for good: another group of the download, which comes after the first
        {"url": urls["old"], "title": "avant 1949"},
    ]

    files = _download_climate_resources(resources, road.settings)

    # the 503 is asked the retries of the download itself and not once more, the 429 once, the other batch not at all
    assert road.asked("/climate/b.csv.gz") == 1
    assert road.asked("/climate/old.csv.gz") == 0
    assert urls["old"] not in files
    # what one download of a 503 asks, retries included, is what the 503 of the batch was asked: no round of its own
    road.server.statuses["/climate/single.csv.gz"] = 503
    download_file(f"{base}/climate/single.csv.gz", cache_dir=road.settings.cache_dir, ttl=CacheExpiry.FIVE_MINUTES)
    assert road.asked("/climate/a.csv.gz") == road.asked("/climate/single.csv.gz")
    with pytest.raises(ProviderRateLimitError) as raised:
        _raise_if_climate_download_failed(files)
    assert raised.value.retry_after == WAIT


# --- download_files: the files that are queued are not asked once one of them is a 429 ----------------------------


def test_the_files_still_to_begin_are_not_asked_once_a_download_is_a_429(road: _Dwd) -> None:
    """A group of many files (a road group, the archives of a station): the queue behind a 429 is not sent."""
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    workers = ThreadPoolExecutor()._max_workers  # noqa: SLF001 -- how many downloads begin at once
    names = [f"/many/{n:03d}.zip" for n in range(workers * 3)]
    road.limit(names[0])
    for name in names[1:]:
        # under way for long enough that the 429 is known before any worker comes for the next file
        road.server.contents[name] = b"x"
        road.server.delays[name] = 0.3
    urls = [road.server.base + name for name in names]

    files = download_files(urls=urls, cache_dir=road.settings.cache_dir, ttl=CacheExpiry.NO_CACHE)

    asked = [name for name in names if road.asked(name)]
    assert asked == names[:workers], "only what had begun when the 429 came was asked"
    assert [file.url for file in files] == urls
    assert all(file.is_rate_limited for file in files[workers:])
    for file in (files[0], files[-1]):
        with pytest.raises(ProviderRateLimitError) as raised:
            file.raise_if_exception()
        assert raised.value.retry_after == WAIT
    # the ones that were under way arrived
    assert all(isinstance(file.content, BytesIO) for file in files[1:workers])


# --- aemet: the link of the data that is refused with a 429 is no chunk let go ---------------------------------------


def test_a_429_of_the_data_link_of_aemet_is_returned_to_be_raised_and_no_chunk_is_noted_as_let_go(
    monkeypatch: pytest.MonkeyPatch, road: _Dwd
) -> None:
    """The envelope says 200 and names the data, which is a 429: the readers raise it, so no `file-skipped` is told."""
    import stamina  # noqa: PLC0415

    from wetterdienst.provider.aemet.observation import api as aemet  # noqa: PLC0415

    monkeypatch.setattr(aemet, "_BASE_URL", road.server.base)
    road.server.contents["/envelope"] = f'{{"estado": 200, "datos": "{road.server.base}/datos"}}'.encode()
    road.limit("/datos")
    noted: list[SkipCause] = []
    settings = Settings(cache_dir=road.settings.cache_dir, auth={"aemet": "dummy-key"})

    with stamina.set_testing(True, attempts=1), collecting(lambda _whole_request, cause: noted.append(cause)):
        payload = aemet._fetch_datos(f"{road.server.base}/envelope", settings, CacheExpiry.NO_CACHE)  # noqa: SLF001

    assert isinstance(payload, ProviderRateLimitError)
    assert payload.retry_after == WAIT
    assert noted == []
