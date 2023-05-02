# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst import boot

boot.monkeypatch()

import polars as pl
import pytest
from fsspec.implementations.http import HTTPFileSystem

from wetterdienst import Resolution
from wetterdienst.provider.dwd.observation import DwdObservationResolution
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    RESOLUTION_DATASET_MAPPING,
    DwdObservationDataset,
)
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationParameter,
)
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.enumeration import parse_enumeration_from_template

SKIP_DATASETS = (
    ("10_minutes", "wind_test"),
    ("subdaily", "standard_format"),
    ("monthly", "climate_indices"),
    ("annual", "climate_indices"),
    ("multi_annual", "mean_61-90"),
    ("multi_annual", "mean_61-90_obsolete"),
    ("multi_annual", "mean_71-00"),
    ("multi_annual", "mean_71-00_obsolete"),
    ("multi_annual", "mean_81-10"),
    ("multi_annual", "mean_81-10_obsolete"),
    ("multi_annual", "mean_91-20"),
)


@pytest.mark.remote
def test_compare_available_dwd_datasets(default_settings):
    """Test to compare the datasets made available with wetterdienst with the ones actually availabel on the DWD CDC
    server instance"""
    # similar to func list_remote_files_fsspec, but we don't want to get full depth
    fs = HTTPFileSystem(
        use_listings_cache=True,
        listings_expiry_time=CacheExpiry.TWELVE_HOURS.value,
        listings_cache_type="filedircache",
        listings_cache_location=default_settings.cache_dir,
        client_kwargs=default_settings.fsspec_client_kwargs,
    )
    base_url = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
    files = fs.expand_path(base_url, recursive=True, maxdepth=3)
    df = pl.DataFrame({"files": files})
    df = df.with_columns(pl.col("files").apply(lambda s: s[len(base_url) : -1]))
    # filter resolution folders
    df = df.filter(pl.col("files").apply(lambda s: s.count("/")) == 1)
    df = df.select(
        pl.col("files").str.split("/").arr.first().alias("resolution"),
        pl.col("files").str.split("/").arr.last().alias("dataset"),
    )
    for (resolution, dataset) in df.iter_rows():
        rd_pair = (resolution, dataset)
        if rd_pair in SKIP_DATASETS:
            continue
        resolution = parse_enumeration_from_template(resolution, DwdObservationResolution, Resolution)
        dataset = DwdObservationDataset(dataset)
        assert dataset in RESOLUTION_DATASET_MAPPING[resolution].keys()
        assert DwdObservationParameter[resolution.name][dataset.name]
