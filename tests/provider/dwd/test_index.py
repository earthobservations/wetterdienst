# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation file index creation."""

import pytest

from wetterdienst import Period
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.observation.fileindex import (
    _build_url_from_dataset_and_period,
    _create_file_index_for_dwd_server,
)
from wetterdienst.provider.dwd.observation.metadata import (
    DwdObservationMetadata,
)
from wetterdienst.settings import Settings
from wetterdienst.util.network import list_remote_files_fsspec


def test__build_url_from_dataset_and_period() -> None:
    """Test building of URL from dataset and period."""
    url = _build_url_from_dataset_and_period(
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.HISTORICAL,
    )
    assert url == "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/historical/"


@pytest.mark.remote
def test_list_files_of_climate_observations() -> None:
    """Test listing of files on DWD server."""
    files_server = list_remote_files_fsspec(
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/kl/recent",
        settings=Settings(),
        ttl=CacheExpiry.NO_CACHE,
    )
    assert (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "annual/kl/recent/jahreswerte_KL_01048_akt.zip" in files_server
    )


@pytest.mark.remote
def test_fileindex(default_settings: Settings) -> None:
    """Test file index creation for DWD server."""
    file_index = _create_file_index_for_dwd_server(
        url="https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent",
        settings=default_settings,
        ttl=CacheExpiry.NO_CACHE,
    ).collect()
    assert file_index.get_column("url").str.contains("daily/kl/recent").all()
