# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from typing import Optional
from urllib.parse import urljoin

import pandas as pd
from dateparser import parse

from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.metadata.constants import DWD_CDC_PATH, DWD_SERVER
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.radar.metadata import (
    RADAR_PARAMETERS_COMPOSITES,
    RADAR_PARAMETERS_RADOLAN,
    RADAR_PARAMETERS_RADVOR,
    RADAR_PARAMETERS_SITES,
    RADAR_PARAMETERS_SWEEPS,
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarParameter,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
from wetterdienst.provider.dwd.radar.util import (
    RADOLAN_DT_PATTERN,
    get_date_from_filename,
)
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import list_remote_files_fsspec


def use_cache() -> int:  # pragma: no cover
    """
    Only use caching when running the test suite to reduce its duration.
    In production, this won't always give us fresh enough data, especially
    when using the "MOST_RECENT" request option. So, let's skip it for that
    purpose for now.

    https://stackoverflow.com/a/58866220

    :return: Cache TTL in seconds.
    """
    if "PYTEST_CURRENT_TEST" in os.environ and "CI" not in os.environ:
        return 2 * 60
    else:
        return 0


def create_fileindex_radar(
    parameter: DwdRadarParameter,
    site: Optional[DwdRadarSite] = None,
    fmt: Optional[DwdRadarDataFormat] = None,
    subset: Optional[DwdRadarDataSubset] = None,
    resolution: Optional[Resolution] = None,
    period: Optional[Period] = None,
    parse_datetime: bool = False,
) -> pd.DataFrame:
    """
    Function to create a file index of the DWD radar data, which is shipped as
    bin bufr or odim-hdf5 data. The file index is created for a single parameter.

    :param parameter:       The radar moment to request
    :param site:            Site/station if parameter is one of
                            RADAR_PARAMETERS_SITES
    :param fmt:          Data format (BINARY, BUFR, HDF5)
    :param subset:          The subset (simple or polarimetric) for HDF5 data.
    :param resolution: Time resolution for RadarParameter.RADOLAN_CDC,
                            either daily or hourly or 5 minutes.
    :param period:     Period type for RadarParameter.RADOLAN_CDC
    :param parse_datetime:  Whether to parse datetimes from file names

    :return:                File index as pandas.DataFrame with FILENAME
                            and DATETIME columns
    """

    parameter_path = build_path_to_parameter(
        parameter=parameter,
        site=site,
        fmt=fmt,
        subset=subset,
        resolution=resolution,
        period=period,
    )

    url = urljoin(DWD_SERVER, parameter_path)

    files_server = list_remote_files_fsspec(url, ttl=CacheExpiry.NO_CACHE)

    files_server = pd.DataFrame(files_server, columns=[DwdColumns.FILENAME.value], dtype="str")

    # Some directories have both "---bin" and "---bufr" files within the same directory,
    # so we need to filter here by designated RadarDataFormat. Example:
    # https://opendata.dwd.de/weather/radar/sites/px/boo/
    if fmt is not None:
        if fmt == DwdRadarDataFormat.BINARY:
            files_server = files_server[files_server[DwdColumns.FILENAME.value].str.contains("--bin")]
        elif fmt == DwdRadarDataFormat.BUFR:
            files_server = files_server[files_server[DwdColumns.FILENAME.value].str.contains("--buf")]

    # Drop duplicates of files packed as .bz2, if not all files are .bz2
    if not all(files_server[DwdColumns.FILENAME.value].str.endswith(".bz2")):
        files_server = files_server[~files_server[DwdColumns.FILENAME.value].str.endswith(".bz2")]

    # Decode datetime of file for filtering.
    if parse_datetime:
        files_server[DwdColumns.DATETIME.value] = files_server[DwdColumns.FILENAME.value].apply(get_date_from_filename)

        return files_server.dropna()

    return files_server


def create_fileindex_radolan_cdc(resolution: Resolution, period: Period) -> pd.DataFrame:
    """
    Function used to create a file index for the RADOLAN_CDC product. The file index
    will include both recent as well as historical files. A datetime column is created
    from the filenames which contain some datetime formats. This datetime column is
    required for later filtering for the requested file.

    :param resolution: Time resolution for RadarParameter.RADOLAN_CDC,
                            either daily or hourly or 5 minutes.
    :param period:     Period type for RadarParameter.RADOLAN_CDC

    :return:                File index as DataFrame
    """
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=resolution,
        period=period,
    )

    file_index = file_index[
        file_index[DwdColumns.FILENAME.value].str.contains("/bin/")
        & file_index[DwdColumns.FILENAME.value].str.endswith((Extension.GZ.value, Extension.TAR_GZ.value))
    ].copy()

    # Decode datetime of file for filtering.
    file_index[DwdColumns.DATETIME.value] = file_index[DwdColumns.FILENAME.value].apply(
        lambda filename: parse(
            RADOLAN_DT_PATTERN.findall(filename)[0],
            date_formats=[DatetimeFormat.YM.value, DatetimeFormat.ymdhm.value],
        )
    )

    return file_index


def build_path_to_parameter(
    parameter: DwdRadarParameter,
    site: Optional[DwdRadarSite] = None,
    fmt: Optional[DwdRadarDataFormat] = None,
    subset: Optional[DwdRadarDataSubset] = None,
    resolution: Optional[Resolution] = None,
    period: Optional[Period] = None,
) -> str:
    """
    Compute URL path to data product.

    Supports composite- and site-based radar data as well as RADOLAN_CDC.

    Composites
    ----------
    - https://opendata.dwd.de/weather/radar/composit/
    - https://opendata.dwd.de/weather/radar/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    - https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/

    Sites
    -----
    - https://opendata.dwd.de/weather/radar/sites/


    :param parameter:       The radar moment to request
    :param site:            Site/station if parameter is one of
                            RADAR_PARAMETERS_SITES
    :param fmt:          Data format (BINARY, BUFR, HDF5)
    :param subset:          The subset (simple or polarimetric) for HDF5 data.
    :param resolution: Time resolution for RadarParameter.RADOLAN_CDC,
                            either daily or hourly or 5 minutes.
    :param period:     Period type for RadarParameter.RADOLAN_CDC

    :return:                URL path to data product
    """
    if parameter == DwdRadarParameter.RADOLAN_CDC:
        if resolution == Resolution.MINUTE_5:
            # See also page 4 on
            # https://opendata.dwd.de/climate_environment/CDC/help/RADOLAN/Unterstuetzungsdokumente/
            # Unterstuetzungsdokumente-Verwendung_von_RADOLAN-Produkten_im_ASCII-GIS-Rasterformat_in_GIS.pdf
            return f"{DWD_CDC_PATH}/grids_germany/{resolution.value}/radolan/reproc/2017_002/bin"
        else:
            return f"{DWD_CDC_PATH}/grids_germany/{resolution.value}/radolan/{period.value}/bin"

    elif parameter in RADAR_PARAMETERS_COMPOSITES:
        return f"weather/radar/composit/{parameter.value}"

    elif parameter in RADAR_PARAMETERS_RADOLAN:
        return f"weather/radar/radolan/{parameter.value}"

    elif parameter in RADAR_PARAMETERS_RADVOR:
        return f"weather/radar/radvor/{parameter.value}"

    elif parameter in RADAR_PARAMETERS_SITES:

        # Sanity checks.
        if site is None:
            raise ValueError("Argument 'site' is missing")

        if fmt is None:

            ambiguous_parameters = [
                DwdRadarParameter.PE_ECHO_TOP,
                DwdRadarParameter.PR_VELOCITY,
                DwdRadarParameter.PX_REFLECTIVITY,
                DwdRadarParameter.PZ_CAPPI,
            ]

            candidates = None
            if parameter in ambiguous_parameters:
                candidates = [DwdRadarDataFormat.BINARY, DwdRadarDataFormat.BUFR]
            if parameter in RADAR_PARAMETERS_SWEEPS:
                candidates = [DwdRadarDataFormat.BUFR, DwdRadarDataFormat.HDF5]

            if candidates:
                raise ValueError(f"Argument 'format' is missing, use one of {candidates}")

        # Compute path to BINARY/BUFR vs. HDF5.
        parameter_path = f"weather/radar/sites/{parameter.value}/{site.value}"
        if fmt == DwdRadarDataFormat.HDF5:
            if subset is None:
                candidates = [
                    DwdRadarDataSubset.SIMPLE,
                    DwdRadarDataSubset.POLARIMETRIC,
                ]
                raise ValueError(f"Argument 'subset' is missing, use one of {candidates}")
            return f"{parameter_path}/{fmt.value}/filter_{subset.value}/"

        return parameter_path

    else:  # pragma: no cover
        raise NotImplementedError(f"Acquisition for {parameter} not implemented yet")
