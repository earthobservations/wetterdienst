# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A file that the DWD file index lists and the server answers with a 404 drops the listing (GH-3892).

DWD renames the historical files at the annual rollover. The listing of a directory is kept for 12 hours, so the next
request asked for the old name until it expired, and the station's values stayed missing. The listing, the cache of it
and the downloads are the real ones, over a local server that answers as DWD's nginx does.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING
from zipfile import BadZipFile

import pytest

from tests.nginx_stub import NginxLike, serving
from wetterdienst import Settings
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.derived import download as derived_download
from wetterdienst.provider.dwd.derived.fileindex import create_file_list_for_climate_derived
from wetterdienst.provider.dwd.derived.metadata import DwdDerivedMetadata
from wetterdienst.provider.dwd.observation import download as observation_download
from wetterdienst.provider.dwd.observation import fileindex
from wetterdienst.provider.dwd.observation.fileindex import create_file_list_for_climate_observations
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.util import network
from wetterdienst.util.network import File, forget_remote_listing, list_remote_files_fsspec
from wetterdienst.util.response_warnings import SkipCause, collecting

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    import polars as pl

    from wetterdienst.metadata.cache import CacheExpiry

_DWD = "https://opendata.dwd.de"
_CDC = "/climate_environment/CDC/"
_OBSERVATION_DIRECTORY = f"{_CDC}observations_germany/climate/daily/kl/historical/"
_OBSERVATION_OLD = "tageswerte_KL_01048_19510101_20231231_hist.zip"
_OBSERVATION_NEW = "tageswerte_KL_01048_19510101_20241231_hist.zip"
_DERIVED_DIRECTORY = f"{_CDC}derived_germany/soil/daily/recent/"
_DERIVED_OLD = "derived_germany_soil_daily_recent_v2_44.txt.gz"
_DERIVED_NEW = "derived_germany_soil_daily_recent_v3_44.txt.gz"


class _Dwd:
    """DWD's server on a local port, and the settings the listings are cached with."""

    def __init__(self, server: NginxLike, settings: Settings) -> None:
        self.server = server
        self.settings = settings

    def rename(self, directory: str, old: str, new: str) -> None:
        """Rename a file of the directory: the listing names the new one and the old one is a 404."""
        self.server.directories[directory] = [new]
        self.server.files.discard(f"{directory}{old}")
        self.server.files.add(f"{directory}{new}")

    def download(self, urls: list[str], **kwargs: object) -> list[File]:
        """Download as the providers do, from the local server, and give each file the URL of DWD's."""
        files = network.download_files([url.replace(_DWD, self.server.base) for url in urls], **kwargs)
        return [dataclasses.replace(file, url=file.url.replace(self.server.base, _DWD)) for file in files]


@pytest.fixture
def dwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Dwd]:
    """Stand in for DWD's server: the listing, the cache of it and the downloads are the real ones."""
    with serving() as server:
        state = _Dwd(server, Settings(cache_dir=str(tmp_path / "cache")))

        def listing(url: str, settings: Settings, cache_expiry: CacheExpiry) -> list[str]:
            found = list_remote_files_fsspec(
                url.replace(_DWD, server.base), settings=settings, cache_expiry=cache_expiry
            )
            return [item.replace(server.base, _DWD) for item in found]

        def forget(url: str, settings: Settings, cache_expiry: CacheExpiry) -> None:
            forget_remote_listing(url.replace(_DWD, server.base), settings, cache_expiry)

        monkeypatch.setattr(fileindex, "list_remote_files_fsspec", listing)
        monkeypatch.setattr(fileindex, "forget_remote_listing", forget)
        monkeypatch.setattr(observation_download, "download_files", state.download)
        monkeypatch.setattr(derived_download, "download_files", state.download)
        yield state


def _causes() -> tuple[list[SkipCause], Callable[[bool, SkipCause], None]]:
    """Give a list and the callback that fills it with the causes a provider lets files go for."""
    told: list[SkipCause] = []
    return told, lambda _whole_request, cause: told.append(cause)


def _observation_files(dwd: _Dwd) -> pl.Series:
    return create_file_list_for_climate_observations(
        "01048", DwdObservationMetadata.daily.climate_summary, Period.HISTORICAL, dwd.settings
    )


def _derived_files(dwd: _Dwd) -> pl.Series:
    return create_file_list_for_climate_derived(
        "00044", DwdDerivedMetadata["daily"]["soil"], Period.RECENT, dwd.settings
    )


def test_dwd_observation_lists_a_renamed_file_afresh_after_its_404(dwd: _Dwd) -> None:
    """The next request finds the new name at once, not when the listing of 12 hours has expired."""
    dwd.server.directories[_OBSERVATION_DIRECTORY] = [_OBSERVATION_OLD]
    dwd.server.files.add(f"{_OBSERVATION_DIRECTORY}{_OBSERVATION_OLD}")
    old = _observation_files(dwd)
    assert old.to_list() == [f"{_DWD}{_OBSERVATION_DIRECTORY}{_OBSERVATION_OLD}"]

    dwd.rename(_OBSERVATION_DIRECTORY, _OBSERVATION_OLD, _OBSERVATION_NEW)
    # the control: the listing is cached, so the old name is still the one listed
    assert _observation_files(dwd).to_list() == old.to_list()

    told, note = _causes()
    with collecting(note):
        assert observation_download.download_climate_observations_data(old, dwd.settings) == []
    assert told == [SkipCause.WITHDRAWN]

    assert _observation_files(dwd).to_list() == [f"{_DWD}{_OBSERVATION_DIRECTORY}{_OBSERVATION_NEW}"]
    (new,) = dwd.download(_observation_files(dwd).to_list(), cache_dir=dwd.settings.cache_dir)
    assert new.status == 200


def test_dwd_derived_lists_a_renamed_file_afresh_after_its_404(dwd: _Dwd) -> None:
    """The same for `dwd/derived`, whose directories are listed by the same file index."""
    dwd.server.directories[_DERIVED_DIRECTORY] = [_DERIVED_OLD]
    dwd.server.files.add(f"{_DERIVED_DIRECTORY}{_DERIVED_OLD}")
    old = _derived_files(dwd)
    assert old.to_list() == [f"{_DWD}{_DERIVED_DIRECTORY}{_DERIVED_OLD}"]

    dwd.rename(_DERIVED_DIRECTORY, _DERIVED_OLD, _DERIVED_NEW)
    assert _derived_files(dwd).to_list() == old.to_list()

    told, note = _causes()
    with collecting(note):
        assert derived_download.download_climate_derived_data(old, dwd.settings) == []
    assert told == [SkipCause.WITHDRAWN]

    assert _derived_files(dwd).to_list() == [f"{_DWD}{_DERIVED_DIRECTORY}{_DERIVED_NEW}"]


def test_a_file_that_is_served_keeps_its_listing(dwd: _Dwd) -> None:
    """Only a 404 drops the listing: a served file asks the server for no new listing."""
    dwd.server.directories[_OBSERVATION_DIRECTORY] = [_OBSERVATION_OLD]
    dwd.server.files.add(f"{_OBSERVATION_DIRECTORY}{_OBSERVATION_OLD}")
    files = _observation_files(dwd)
    listings = [request for request in dwd.server.requests if request[1].endswith("/")]

    # the bytes the server serves are no archive: the download is made, the unpacking is not the test
    with pytest.raises(BadZipFile):
        observation_download.download_climate_observations_data(files, dwd.settings)
    _observation_files(dwd)

    assert [request for request in dwd.server.requests if request[1].endswith("/")] == listings
