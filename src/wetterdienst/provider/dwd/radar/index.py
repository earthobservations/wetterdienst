# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Index for DWD radar data."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.radar.metadata import (
    RADAR_DATA_FORMATS,
    RADAR_PARAMETERS_COMPOSITES,
    RADAR_PARAMETERS_RADOLAN,
    RADAR_PARAMETERS_SITES,
    RADAR_PARAMETERS_SWEEPS,
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarParameter,
    radar_data_format,
)
from wetterdienst.provider.dwd.radar.util import (
    RADAR_DT_PATTERN,
    RADOLAN_DT_PATTERN,
    get_date_string_from_filename,
)
from wetterdienst.util.network import list_remote_files_fsspec

if TYPE_CHECKING:
    from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
    from wetterdienst.settings import Settings


def use_cache() -> int:  # pragma: no cover
    """Decorate a function to use caching.

    Only use caching when running the test suite to reduce its duration.
    In production, this won't always give us fresh enough data, especially
    when using the "MOST_RECENT" request option. So, let's skip it for that
    purpose for now.

    https://stackoverflow.com/a/58866220

    Returns:
        Cache TTL in seconds.

    """
    if "PYTEST_CURRENT_TEST" in os.environ and "CI" not in os.environ:
        return 2 * 60
    return 0


def create_fileindex_radar(
    parameter: DwdRadarParameter,
    settings: Settings,
    site: DwdRadarSite | None = None,
    fmt: DwdRadarDataFormat | None = None,
    subset: DwdRadarDataSubset | None = None,
    resolution: Resolution | None = None,
    period: Period | None = None,
    *,
    parse_datetime: bool = False,
) -> pl.DataFrame:
    """Create a file index of the DWD radar data, which is shipped as binary or ODIM HDF5 files.

    The file index is created for a single parameter.

    Args:
        parameter: The radar moment to request
        settings: Settings for the request
        site: Site/station if parameter is one of RADAR_PARAMETERS_SITES
        fmt: Data format (BINARY or HDF5), which a product is served in only one of: see RADAR_DATA_FORMATS
        subset: The subset (simple or polarimetric) for HDF5 data.
        resolution: Time resolution for RadarParameter.RADOLAN_CDC,
                    either daily or hourly or 5 minutes.
        period: Period type for RadarParameter.RADOLAN_CDC
        parse_datetime: Whether to parse datetimes from file names

    Returns:
        File index as DataFrame with FILENAME and DATETIME columns

    """
    fmt = radar_data_format(parameter, fmt)
    parameter_path = build_path_to_parameter(
        parameter=parameter,
        site=site,
        fmt=fmt,
        subset=subset,
        resolution=resolution,
        period=period,
    )
    url = f"https://opendata.dwd.de/{parameter_path}"
    files_serv = list_remote_files_fsspec(url, settings=settings, cache_expiry=CacheExpiry.NO_CACHE)
    df_fileindex = pl.DataFrame(files_serv, schema={"filename": pl.String}, orient="col")

    # The composites are one .tar a run (composite_rv_20261022_1130.tar, composite_rv_LATEST.tar), each
    # holding an ODIM HDF5 file for every lead time; the other HDF5 products are the files themselves.
    # https://opendata.dwd.de/weather/radar/composite/rv/
    if parameter in RADAR_PARAMETERS_COMPOSITES:
        df_fileindex = df_fileindex.filter(pl.col("filename").str.ends_with(f".{Extension.TAR.value}"))
    elif parameter in RADAR_DATA_FORMATS and fmt == DwdRadarDataFormat.HDF5:
        df_fileindex = df_fileindex.filter(pl.col("filename").str.ends_with("-hd5"))
    elif fmt == DwdRadarDataFormat.BINARY:
        df_fileindex = df_fileindex.filter(pl.col("filename").str.contains("--bin", literal=True))

    # Drop duplicates of files packed as .bz2, if not all files are .bz2
    if not df_fileindex.get_column("filename").str.ends_with(".bz2").all():
        df_fileindex = df_fileindex.filter(~pl.col("filename").str.ends_with(".bz2"))

    # the HDF5 products, the composites and the site ones, are dated with the year in four digits, the others in two
    is_hdf5 = parameter in RADAR_DATA_FORMATS and fmt == DwdRadarDataFormat.HDF5
    format_ = "%Y%m%d%H%M" if is_hdf5 else "%y%m%d%H%M"

    # Decode datetime of file for filtering.
    if parse_datetime:
        df_fileindex = df_fileindex.with_columns(
            pl.col("filename")
            .map_elements(
                lambda filename: get_date_string_from_filename(filename=filename, pattern=RADAR_DT_PATTERN),
                return_dtype=pl.String,
            )
            .str.to_datetime(format_, time_zone="UTC")
            .alias("datetime"),
        )

    return df_fileindex.drop_nulls()


def create_fileindex_radolan_cdc(resolution: Resolution, period: Period, settings: Settings) -> pl.DataFrame:
    """Create a file index for RADOLAN_CDC data."""
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

    format_ = "%Y%m" if period == Period.HISTORICAL else "%y%m%d%H%M"

    df_fileindex = df_fileindex.with_columns(
        pl.col("filename")
        .map_elements(
            lambda filename: get_date_string_from_filename(filename=filename, pattern=RADOLAN_DT_PATTERN),
            return_dtype=pl.String,
        )
        .str.to_datetime(format_, time_zone="UTC")
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
    """Compute URL path to data product.

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

    Args:
        parameter: The radar moment to request
        site: Site/station if parameter is one of RADAR_PARAMETERS_SITES
        fmt: Data format (BINARY or HDF5), which a product is served in only one of: see RADAR_DATA_FORMATS
        subset: The subset (simple or polarimetric) for HDF5 data.
        resolution: Time resolution for RadarParameter.RADOLAN_CDC,
                    either daily or hourly or 5 minutes.
        period: Period type for RadarParameter.RADOLAN_CDC

    Returns:
        URL path to data product

    """
    if parameter == DwdRadarParameter.RADOLAN_CDC:
        if resolution is None or period is None:
            msg = "resolution and period must be provided for RADOLAN_CDC"
            raise ValueError(msg)
        if resolution == Resolution.MINUTE_5:
            # See also page 4 on
            # https://opendata.dwd.de/climate_environment/CDC/help/RADOLAN/Unterstuetzungsdokumente/
            # Unterstuetzungsdokumente-Verwendung_von_RADOLAN-Produkten_im_ASCII-GIS-Rasterformat_in_GIS.pdf
            return f"climate_environment/CDC/grids_germany/{resolution.value}/radolan/reproc/2017_002/bin"
        return f"climate_environment/CDC/grids_germany/{resolution.value}/radolan/{period.value}/bin"

    if parameter in RADAR_PARAMETERS_COMPOSITES:
        return f"weather/radar/composite/{parameter.value}"

    if parameter in RADAR_PARAMETERS_RADOLAN:
        return f"weather/radar/radolan/{parameter.value}"

    if parameter in RADAR_PARAMETERS_SITES:
        # Sanity checks.
        if site is None:
            msg = "Argument 'site' is missing"
            raise ValueError(msg)

        # refuse a format the product is not served in, as the file index does
        radar_data_format(parameter, fmt)

        # The sweeps keep their HDF5 files in a folder of the filter, the other products in the one of the site.
        parameter_path = f"weather/radar/sites/{parameter.value}/{site.value}"
        if parameter in RADAR_PARAMETERS_SWEEPS:
            if subset is None:
                candidates = [
                    DwdRadarDataSubset.SIMPLE,
                    DwdRadarDataSubset.POLARIMETRIC,
                ]
                msg = f"Argument 'subset' is missing, use one of {candidates}"
                raise ValueError(msg)
            return f"{parameter_path}/hdf5/filter_{subset.value}/"

        return parameter_path

    # pragma: no cover
    msg = f"Acquisition for {parameter} not implemented yet"
    raise NotImplementedError(msg)
