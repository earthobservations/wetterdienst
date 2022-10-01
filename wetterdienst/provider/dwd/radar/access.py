# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import bz2
import gzip
import logging
import re
import tarfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Generator, Optional

import pandas as pd
from fsspec.implementations.tar import TarFileSystem

from wetterdienst.exceptions import FailedDownload
from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.radar.index import (
    create_fileindex_radar,
    create_fileindex_radolan_cdc,
)
from wetterdienst.provider.dwd.radar.metadata import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarDate,
    DwdRadarParameter,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
from wetterdienst.provider.dwd.radar.util import get_date_from_filename, verify_hdf5
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file

log = logging.getLogger(__name__)


@dataclass
class RadarResult:
    """
    Result object encapsulating radar data and metadata.
    Currently, this will relate to exactly one radar data file.
    """

    data: BytesIO
    timestamp: datetime = None
    url: str = None
    filename: str = None

    def __getitem__(self, index):
        """
        Backward compatibility to address this instance as a tuple.

        Formerly, this returned a tuple of ``(datetime, BytesIO)``.

        :param index:
        :return:
        """
        if index == 0:  # pragma: no cover
            return self.timestamp
        elif index == 1:
            return self.data
        else:  # pragma: no cover
            raise KeyError(f"Index {index} undefined on RadarResult")


def collect_radar_data(
    parameter: Optional[DwdRadarParameter],
    resolution: Optional[Resolution] = None,
    period: Optional[Period] = None,
    site: Optional[DwdRadarSite] = None,
    fmt: Optional[DwdRadarDataFormat] = None,
    subset: Optional[DwdRadarDataSubset] = None,
    elevation: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    verify: Optional[bool] = True,
) -> RadarResult:
    """
    Collect radar data for given parameters.

    :param parameter:       The radar moment to request
    :param resolution:      Time resolution for RadarParameter.RADOLAN_CDC,
                            either daily or hourly or 5 minutes.
    :param period:          Period type for RadarParameter.RADOLAN_CDC
    :param site:            Site/station if parameter is one of
                            RADAR_PARAMETERS_SITES
    :param fmt:             Data format (BINARY, BUFR, HDF5)
    :param subset:          The subset (simple or polarimetric) for HDF5 data.
    :param elevation:
    :param start_date:      Start date
    :param end_date:        End date
    :param verify:          Whether to verify the response

    :return:                ``RadarResult`` item
    """

    # Find latest file.
    if start_date == DwdRadarDate.LATEST:

        file_index = create_fileindex_radar(
            parameter=parameter,
            site=site,
            fmt=fmt,
            parse_datetime=False,
        )

        # Find "-latest-" file.
        filenames = file_index[DwdColumns.FILENAME.value].tolist()
        latest_file = list(filter(lambda x: "-latest-" in x, filenames))[0]

        # Yield single "RadarResult" item.
        result = next(_download_generic_data(url=latest_file))
        yield result

    else:

        if parameter == DwdRadarParameter.RADOLAN_CDC:

            if period:
                period_types = [period]
            else:
                period_types = [
                    Period.RECENT,
                    Period.HISTORICAL,
                ]

            results = []
            for period in period_types:

                file_index = create_fileindex_radolan_cdc(resolution=resolution, period=period)

                # Filter for dates range if start_date and end_date are defined.
                if period == Period.RECENT:
                    file_index = file_index[
                        (file_index[DwdColumns.DATETIME.value] >= start_date)
                        & (file_index[DwdColumns.DATETIME.value] < end_date)
                    ]

                # This is for matching historical data, e.g. "RW-200509.tar.gz".
                else:
                    file_index = file_index[
                        (file_index[DwdColumns.DATETIME.value].dt.year == start_date.year)
                        & (file_index[DwdColumns.DATETIME.value].dt.month == start_date.month)
                    ]

                results.append(file_index)

            file_index = pd.concat(results)

            if file_index.empty:
                # TODO: Extend this log message.
                log.warning(f"No radar file found for {parameter}, {site}, {fmt}")
                return

            # Iterate list of files and yield "RadarResult" items.
            for _, row in file_index.iterrows():
                url = row[DwdColumns.FILENAME.value]
                try:
                    yield from download_radolan_data(url, start_date, end_date)
                except FailedDownload as e:
                    log.exception(e)

        else:
            file_index = create_fileindex_radar(
                parameter=parameter,
                site=site,
                fmt=fmt,
                subset=subset,
                parse_datetime=True,
            )

            # Filter for dates range if start_date and end_date are defined.
            file_index = file_index[
                (file_index[DwdColumns.DATETIME.value] >= start_date)
                & (file_index[DwdColumns.DATETIME.value] < end_date)
            ]

            # Filter SWEEP_VOL_VELOCITY_H and SWEEP_VOL_REFLECTIVITY_H by elevation.
            if elevation is not None:
                filename = file_index[DwdColumns.FILENAME.value]
                file_index = file_index[
                    (filename.str.contains(f"vradh_{elevation:02d}"))
                    | (filename.str.contains(f"sweep_vol_v_{elevation}"))
                    | (filename.str.contains(f"dbzh_{elevation:02d}"))
                    | (filename.str.contains(f"sweep_vol_z_{elevation}"))
                ]

            if file_index.empty:
                log.warning(f"No radar file found for {parameter}, {site}, {fmt}")
                return

            # Iterate list of files and yield "RadarResult" items.
            for _, row in file_index.iterrows():
                date_time = row[DwdColumns.DATETIME.value]
                url = row[DwdColumns.FILENAME.value]

                try:
                    for result in _download_generic_data(url=url):
                        if result.timestamp is None:
                            result.timestamp = date_time

                        if verify:
                            if fmt == DwdRadarDataFormat.HDF5:
                                verify_hdf5(result.data)

                        yield result

                except Exception:  # pragma: no cover
                    log.exception("Unable to read HDF5 file")


def should_cache_download(url: str) -> bool:  # pragma: no cover
    """
    Determine whether this specific result should be cached.

    Here, we don't want to cache any files containing "-latest-" in their filenames.

    :param url: url string which is used to decide if result is cached
    :return: When cache should be dismissed, return False. Otherwise, return True.
    """
    if "-latest-" in url:
        return False
    return True


def _download_generic_data(url: str) -> Generator[RadarResult, None, None]:
    """
    Download radar data.

    :param url:         The URL to the file on the DWD server

    :return:            The file in binary, either an archive of one file
                        or an archive of multiple files.
    """

    ttl = CacheExpiry.FIVE_MINUTES
    if not should_cache_download(url):
        ttl = CacheExpiry.NO_CACHE

    data = download_file(url, ttl=ttl)

    # RadarParameter.FX_REFLECTIVITY
    if url.endswith(Extension.TAR_BZ2.value):
        tfs = TarFileSystem(data, compression="bz2")
        for file in tfs.glob("*"):
            yield RadarResult(
                data=tfs.open(file).read(),
                timestamp=get_date_from_filename(file.name),
                filename=file.name,
            )

    # RadarParameter.WN_REFLECTIVITY, RADAR_PARAMETERS_SWEEPS (BUFR)  # noqa: E800
    elif url.endswith(Extension.BZ2.value):
        with bz2.BZ2File(data, mode="rb") as archive:
            data = BytesIO(archive.read())
            yield RadarResult(url=url, data=data, timestamp=get_date_from_filename(url))

    # RADAR_PARAMETERS_RADVOR
    elif url.endswith(Extension.GZ.value):
        with gzip.GzipFile(fileobj=data, mode="rb") as archive:
            data = BytesIO(archive.read())
            yield RadarResult(url=url, data=data, timestamp=get_date_from_filename(url))

    else:
        yield RadarResult(url=url, data=data, timestamp=get_date_from_filename(url))


def download_radolan_data(url: str, start_date, end_date) -> RadarResult:
    """
    Function used to download RADOLAN_CDC data for a given datetime. The function calls
    a separate download function that is cached for reuse which is especially used for
    historical data that comes packaged for multiple time steps within a single archive.
    :param url:         The URL to the file that has the data
                        for the requested datetime, either an archive of multiple files
                        for a datetime in historical time or an archive with one file
                        for the recent RADOLAN file
    :param start_date:
    :param end_date:
    :return:            ``RadarResult`` item
    """
    archive_in_bytes = _download_radolan_data(url)

    for result in _extract_radolan_data(archive_in_bytes):
        if not result.timestamp:
            # if result has no timestamp, take it from main url instead of files in archive
            datetime_string = re.findall(r"\d{10}", url)[0]
            date_time = datetime.strptime("20" + datetime_string, "%Y%m%d%H%M")
            result.timestamp = date_time
        if result.timestamp < start_date or result.timestamp > end_date:
            continue
        result.url = url

        yield result


def _download_radolan_data(remote_radolan_filepath: str) -> BytesIO:
    """
    Function (cached) that downloads the RADOLAN_CDC file.

    Args:
        remote_radolan_filepath: the file path to the file on the DWD server

    Returns:
        the file in binary, either an archive of one file or an archive of multiple
        files
    """
    return download_file(remote_radolan_filepath, ttl=CacheExpiry.TWELVE_HOURS)


def _extract_radolan_data(archive_in_bytes: BytesIO) -> Generator[RadarResult, None, None]:
    """
    Function used to extract RADOLAN_CDC file for the requested datetime
    from the downloaded archive.

    Args:
        archive_in_bytes: downloaded archive of RADOLAN file
    Returns:
        the datetime formatted as string and the RADOLAN file for the datetime
    """
    # First try to unpack archive from archive (case for historical data)
    try:
        tfs = TarFileSystem(archive_in_bytes, compression="gzip")

        for file in tfs.glob("*"):
            datetime_string = re.findall(r"\d{10}", file)[0]
            date_time = datetime.strptime("20" + datetime_string, "%Y%m%d%H%M")
            file_in_bytes = tfs.tar.extractfile(file).read()

            yield RadarResult(
                data=BytesIO(file_in_bytes),
                timestamp=date_time,
                filename=file,
            )

    # Otherwise, if there's an error the data is from recent time period and only has to
    # be unpacked once
    except tarfile.ReadError:
        # Seek again for reused purpose
        archive_in_bytes.seek(0)
        with gzip.GzipFile(fileobj=archive_in_bytes, mode="rb") as gz_file:
            yield RadarResult(data=BytesIO(gz_file.read()), timestamp=None, filename=gz_file.name)
