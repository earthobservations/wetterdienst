# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst import Period
from wetterdienst.provider.dwd.observation.fileindex import _create_file_index_for_dwd_server, build_path_to_parameter
from wetterdienst.provider.dwd.observation.metadata import (
    DwdObservationMetadata,
)
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import list_remote_files_fsspec


def test_build_index_path():
    path = build_path_to_parameter(
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.HISTORICAL,
    )
    assert path == "daily/kl/historical/"


@pytest.mark.remote
def test_list_files_of_climate_observations():
    files_server = list_remote_files_fsspec(
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/kl/recent",
        settings=Settings.default(),
        ttl=CacheExpiry.NO_CACHE,
    )
    assert (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "annual/kl/recent/jahreswerte_KL_01048_akt.zip" in files_server
    )


@pytest.mark.remote
def test_fileindex(default_settings):
    file_index = _create_file_index_for_dwd_server(
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.RECENT,
        cdc_base="observations_germany/climate/",
        settings=default_settings,
    ).collect()
    assert file_index.get_column("filename").str.contains("daily/kl/recent").all()
