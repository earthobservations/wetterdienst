# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation file index creation."""

import pytest

from wetterdienst import Period
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.provider.dwd.observation.fileindex import (
    _build_url_from_dataset_and_period,
    _create_file_index_for_dwd_server,
)
from wetterdienst.provider.dwd.observation.metadata import (
    DWD_URBAN_DATASETS,
    DWD_URBAN_DATASETS_WITHOUT_PERIOD_DIRECTORIES,
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


@pytest.mark.parametrize(
    "period",
    [Period.HISTORICAL, Period.RECENT, Period.NOW],
)
def test__build_url_from_dataset_and_period_urban_10_minutes(period: Period) -> None:
    """The 10 minute climate_urban datasets have a directory per period, so the period reaches the URL."""
    url = _build_url_from_dataset_and_period(
        dataset=DwdObservationMetadata.minute_10.urban_wind,
        period=period,
    )
    assert url == (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/"
        f"10_minutes/wind/{period.value}/"
    )


@pytest.mark.parametrize(
    "period",
    [Period.HISTORICAL, Period.RECENT, Period.NOW],
)
def test__build_url_from_dataset_and_period_urban_hourly(period: Period) -> None:
    """The hourly climate_urban datasets only have a ``recent`` directory, holding the full record."""
    url = _build_url_from_dataset_and_period(
        dataset=DwdObservationMetadata.hourly.urban_wind,
        period=period,
    )
    assert url == (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/recent/"
    )


@pytest.mark.remote
def test_list_files_of_climate_observations() -> None:
    """Test listing of files on DWD server."""
    files_server = list_remote_files_fsspec(
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/annual/kl/recent",
        settings=Settings(),
        cache_expiry=CacheExpiry.NO_CACHE,
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


@pytest.mark.remote
@pytest.mark.parametrize("dataset", DWD_URBAN_DATASETS, ids=lambda d: f"{d.resolution.name}/{d.name}")
def test_dwd_urban_period_directories_match_the_server(dataset: DatasetModel, default_settings: Settings) -> None:
    """Every climate_urban dataset is classified the way the server is actually laid out.

    `DWD_URBAN_DATASETS_WITHOUT_PERIOD_DIRECTORIES` decides whether the requested period reaches the
    URL or is replaced by `recent`. Getting that wrong for a dataset that does have period
    directories answers a `historical` or `now` request with recent data and says nothing about it,
    so it is worth asking DWD rather than assuming the layout stays put.
    """
    url = _build_url_from_dataset_and_period(dataset=dataset, period=Period.RECENT).removesuffix(
        f"{Period.RECENT.value}/",
    )
    # the listing is recursive and names files, so the period directories are the path segment
    # between the dataset directory and the file
    files = list_remote_files_fsspec(url, settings=default_settings, cache_expiry=CacheExpiry.METAINDEX)
    segments = {file.removeprefix(url).split("/")[0] for file in files}
    period_directories = segments & {period.value for period in Period}
    if dataset in DWD_URBAN_DATASETS_WITHOUT_PERIOD_DIRECTORIES:
        assert period_directories == {Period.RECENT.value}
    else:
        assert period_directories == {Period.HISTORICAL.value, Period.RECENT.value, Period.NOW.value}
