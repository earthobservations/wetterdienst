# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
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
from wetterdienst.provider.dwd.radar.util import (
    RADAR_DT_PATTERN,
    RADOLAN_DT_PATTERN,
    get_date_from_filename,
)
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import list_remote_files_fsspec

if TYPE_CHECKING:
    from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
    from wetterdienst.settings import Settings


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
    settings: Settings,
    site: DwdRadarSite | None = None,
    fmt: DwdRadarDataFormat | None = None,
    subset: DwdRadarDataSubset | None = None,
    resolution: Resolution | None = None,
    period: Period | None = None,
    parse_datetime: bool = False,
) -> pl.DataFrame:
    """
    Function to create a file index of the DWD radar data, which is shipped as
    bin bufr or odim-hdf5 data. The file index is created for a single parameter.

    :param parameter:       The radar moment to request
    :param settings:
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
    url = f"https://opendata.dwd.de/{parameter_path}"
    files_serv = list_remote_files_fsspec(url, settings=settings, ttl=CacheExpiry.NO_CACHE)
    df_fileindex = pl.DataFrame(files_serv, schema={"filename": pl.String})

    # Some directories have both "---bin" and "---bufr" files within the same directory,
    # so we need to filter here by designated RadarDataFormat. Example:
    # https://opendata.dwd.de/weather/radar/sites/px/boo/
    if fmt is not None:
        if fmt == DwdRadarDataFormat.BINARY:
            df_fileindex = df_fileindex.filter(pl.col("filename").str.contains("--bin", literal=True))
        elif fmt == DwdRadarDataFormat.BUFR:
            df_fileindex = df_fileindex.filter(pl.col("filename").str.contains("--buf", literal=True))

    # Drop duplicates of files packed as .bz2, if not all files are .bz2
    if not df_fileindex.get_column("filename").str.ends_with(".bz2").all():
        df_fileindex = df_fileindex.filter(~pl.col("filename").str.ends_with(".bz2"))

    if parameter in RADAR_PARAMETERS_SWEEPS:
        formats = [DatetimeFormat.YMDHM.value]
    elif site and parameter is DwdRadarParameter.PX250_REFLECTIVITY:
        formats = [DatetimeFormat.YMDHM.value]
    elif site and fmt is DwdRadarDataFormat.BUFR:
        formats = [DatetimeFormat.YMDHM.value]
    else:
        formats = [DatetimeFormat.ymdhm.value]

    # Decode datetime of file for filtering.
    if parse_datetime:
        df_fileindex = df_fileindex.with_columns(
            pl.col("filename")
            .map_elements(
                lambda fn: get_date_from_filename(filename=fn, pattern=RADAR_DT_PATTERN, formats=formats),
                return_dtype=pl.Datetime,
            )
            .alias("datetime"),
        )

    return df_fileindex.drop_nulls()


def create_fileindex_radolan_cdc(resolution: Resolution, period: Period, settings: Settings) -> pl.DataFrame:
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
    df_fileindex = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=resolution,
        period=period,
        settings=settings,
    )

    df_fileindex = df_fileindex.filter(
        pl.col("filename").str.contains("/bin/", literal=True)
        & (
            pl.col("filename").str.ends_with(Extension.GZ.value) | pl.col("filename").str.ends_with(Extension.TAR.value)
        ),
    )

    if period == Period.HISTORICAL:
        formats = [DatetimeFormat.YM.value]
    else:
        formats = [DatetimeFormat.ymdhm.value]

    df_fileindex = df_fileindex.with_columns(
        pl.col("filename")
        .map_elements(
            lambda fn: get_date_from_filename(filename=fn, pattern=RADOLAN_DT_PATTERN, formats=formats),
            return_dtype=pl.Datetime,
        )
        .alias("datetime"),
    )

    return df_fileindex.drop_nulls()


def build_path_to_parameter(
    parameter: DwdRadarParameter,
    site: DwdRadarSite | None = None,
    fmt: DwdRadarDataFormat | None = None,
    subset: DwdRadarDataSubset | None = None,
    resolution: Resolution | None = None,
    period: Period | None = None,
) -> str:
    """
    Compute URL path to data product.

    Supports composite- and site-based radar data as well as RADOLAN_CDC.

    Composites
    ----------
    - https://opendata.dwd.de/weather/radar/composite/
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
            return f"climate_environment/CDC/grids_germany/{resolution.value}/radolan/reproc/2017_002/bin"
        else:
            return f"climate_environment/CDC/grids_germany/{resolution.value}/radolan/{period.value}/bin"

    elif parameter in RADAR_PARAMETERS_COMPOSITES:
        return f"weather/radar/composite/{parameter.value}"

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
