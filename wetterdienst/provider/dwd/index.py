# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from functools import reduce
from urllib.parse import urljoin

import pandas as pd

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.metadata.constants import (
    DWD_CDC_PATH,
    DWD_SERVER,
    DWDCDCBase,
)
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    DWD_URBAN_DATASETS,
    DwdObservationDataset,
)
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import list_remote_files_fsspec


def _create_file_index_for_dwd_server(
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
    cdc_base: DWDCDCBase,
) -> pd.DataFrame:
    """
    Function to create a file index of the DWD station data, which usually is shipped as
    zipped/archived data. The file index is created for an individual set of parameters.
    Args:
        dataset: dwd dataset enumeration
        resolution: time resolution of TimeResolution enumeration
        period: period type of PeriodType enumeration
        cdc_base: base path e.g. climate_observations/germany
    Returns:
        file index in a pandas.DataFrame with sets of parameters and station id
    """
    parameter_path = build_path_to_parameter(dataset, resolution, period)

    url = reduce(urljoin, [DWD_SERVER, DWD_CDC_PATH, cdc_base.value, parameter_path])

    files_server = list_remote_files_fsspec(url, ttl=CacheExpiry.TWELVE_HOURS)

    if not files_server:
        raise FileNotFoundError(f"url {url} does not have a list of files")

    return pd.DataFrame(files_server, columns=[DwdColumns.FILENAME.value], dtype=str)


def build_path_to_parameter(
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
) -> str:
    """
    Function to build a indexing file path
    Args:
        dataset: observation measure
        resolution: frequency/granularity of measurement interval
        period: recent or historical files

    Returns:
        indexing file path relative to climate observation path
    """
    if dataset == DwdObservationDataset.SOLAR and resolution in (
        Resolution.HOURLY,
        Resolution.DAILY,
    ):
        return f"{resolution.value}/{dataset.value}/"
    elif dataset in DWD_URBAN_DATASETS:
        return f"{resolution.value}/{dataset.value[6:]}/{period.value}/"
    else:
        return f"{resolution.value}/{dataset.value}/{period.value}/"
