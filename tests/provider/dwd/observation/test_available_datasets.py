# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import polars as pl
import pytest

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.observation.metadata import (
    DwdObservationMetadata,
)
from wetterdienst.util.network import HTTPFileSystem

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
        listings_cache_location=default_settings.cache_dir,
        client_kwargs=default_settings.fsspec_client_kwargs,
    )
    base_url = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
    files = fs.expand_path(base_url, recursive=True, maxdepth=3)
    df = pl.DataFrame({"files": files}, orient="col")
    df = df.with_columns(pl.col("files").str.slice(len(base_url)).str.strip_chars_end("/"))
    # filter resolution folders
    df = df.filter(pl.col("files").str.count_matches("/", literal=True).eq(1))
    df = df.select(
        pl.col("files").str.split("/").list.first().alias("resolution"),
        pl.col("files").str.split("/").list.last().alias("dataset"),
    )
    for resolution, dataset in df.iter_rows():
        rd_pair = (resolution, dataset)
        if rd_pair in SKIP_DATASETS:
            continue
        try:
            DwdObservationMetadata[resolution][dataset]
        except KeyError:
            assert False, f"Dataset {resolution}/{dataset} not available in DwdObservationMetadata"
