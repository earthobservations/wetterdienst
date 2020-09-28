import bz2
import gzip
import logging
import tarfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Tuple, List, Union, Optional, Generator

from deprecation import deprecated
import pandas as pd

from wetterdienst import TimeResolution, PeriodType
from wetterdienst.dwd.metadata.constants import DWD_FOLDER_MAIN

from wetterdienst.dwd.network import download_file_from_dwd
from wetterdienst.dwd.radar.index import (
    create_fileindex_radolan_cdc,
    create_fileindex_radar,
)
from wetterdienst.dwd.radar.util import get_date_from_filename
from wetterdienst.dwd.radar.metadata import (
    RadarParameter,
    RadarDate,
    RadarDataFormat,
    RadarDataSubset,
)
from wetterdienst.dwd.radar.sites import RadarSite
from wetterdienst.dwd.radar.store import restore_radar_data, store_radar_data
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.util.cache import (
    payload_cache_twelve_hours,
    payload_cache_five_minutes,
)


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
    parameter: RadarParameter,
    time_resolution: Optional[TimeResolution] = None,
    period_type: Optional[PeriodType] = None,
    site: Optional[RadarSite] = None,
    format: Optional[RadarDataFormat] = None,
    subset: Optional[RadarDataSubset] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> RadarResult:
    """
    Collect radar data for given parameters.

    :param parameter:       The radar moment to request
    :param site:            Site/station if parameter is one of
                            RADAR_PARAMETERS_SITES
    :param format:          Data format (BINARY, BUFR, HDF5)
    :param subset:          The subset (simple or polarimetric) for HDF5 data.
    :param start_date:      Start date
    :param end_date:        End date
    :param time_resolution: Time resolution for RadarParameter.RADOLAN_CDC,
                            either daily or hourly or 5 minutes.
    :param period_type:     Period type for RadarParameter.RADOLAN_CDC

    :return:                ``RadarResult`` item
    """

    # Find latest file.
    if start_date == RadarDate.LATEST:

        file_index = create_fileindex_radar(
            parameter=parameter,
            site=site,
            format=format,
            parse_datetime=False,
        )

        # Find "-latest-" file.
        filenames = file_index["FILENAME"].tolist()
        latest_file = list(filter(lambda x: "-latest-" in x, filenames))[0]

        # Yield single "RadarResult" item.
        result = next(_download_generic_data(url=latest_file))
        yield result

    else:

        if parameter == RadarParameter.RADOLAN_CDC:

            if period_type:
                period_types = [period_type]
            else:
                period_types = [PeriodType.RECENT, PeriodType.HISTORICAL]

            results = []
            for period_type in period_types:

                file_index = create_fileindex_radolan_cdc(
                    time_resolution=time_resolution, period_type=period_type
                )

                # Filter for dates range if start_date and end_date are defined.
                if period_type == PeriodType.RECENT:
                    file_index = file_index[
                        (file_index[DWDMetaColumns.DATETIME.value] >= start_date)
                        & (file_index[DWDMetaColumns.DATETIME.value] < end_date)
                    ]

                # This is for matching historical data, e.g. "RW-200509.tar.gz".
                else:
                    file_index = file_index[
                        (
                            file_index[DWDMetaColumns.DATETIME.value].dt.year
                            == start_date.year
                        )
                        & (
                            file_index[DWDMetaColumns.DATETIME.value].dt.month
                            == start_date.month
                        )
                    ]

                results.append(file_index)

            file_index = pd.concat(results)

            if file_index.empty:
                log.warning(f"No radar file found for {parameter}, {site}, {format}")
                return

            # Iterate list of files and yield "RadarResult" items.
            for _, row in file_index.iterrows():
                url = row[DWDMetaColumns.FILENAME.value]
                yield download_radolan_data(start_date, url)

        else:
            file_index = create_fileindex_radar(
                parameter=parameter,
                site=site,
                format=format,
                subset=subset,
                parse_datetime=True,
            )

            # Filter for dates range if start_date and end_date are defined.
            file_index = file_index[
                (file_index[DWDMetaColumns.DATETIME.value] >= start_date)
                & (file_index[DWDMetaColumns.DATETIME.value] < end_date)
            ]

            if file_index.empty:
                log.warning(f"No radar file found for {parameter}, {site}, {format}")
                return

            # Iterate list of files and yield "RadarResult" items.
            for _, row in file_index.iterrows():
                date_time = row[DWDMetaColumns.DATETIME.value]
                url = row[DWDMetaColumns.FILENAME.value]

                for result in _download_generic_data(url=url):
                    if result.timestamp is None:
                        result.timestamp = date_time
                    yield result


def should_cache_download(*args, **kwargs) -> bool:  # pragma: no cover
    """
    Determine whether this specific result should be cached.

    Here, we don't want to cache any files containing "-latest-" in their filenames.

    :param args: Arguments of decorated function.
    :param kwargs: Keyword arguments of decorated function.
    :return: When cache should be dimissed, return False. Otherwise, return True.
    """
    url = args[0]
    if "-latest-" in url:
        return False
    return True


@payload_cache_five_minutes.cache_on_arguments(should_cache_fn=should_cache_download)
def _download_generic_data_cached(url: str) -> BytesIO:
    return url, download_file_from_dwd(url)


def _download_generic_data(url: str) -> Generator[RadarResult, None, None]:
    """
    Download radar data.

    :param url:         The URL to the file on the DWD server

    :return:            The file in binary, either an archive of one file
                        or an archive of multiple files.
    """

    _, data = _download_generic_data_cached(url)

    data.seek(0)

    # RadarParameter.FX_REFLECTIVITY
    if url.endswith(".tar.bz2"):
        with bz2.BZ2File(data, mode="rb") as archive:
            with tarfile.open(fileobj=archive) as tar_file:
                for file in tar_file.getmembers():
                    yield RadarResult(
                        data=BytesIO(tar_file.extractfile(file).read()),
                        timestamp=get_date_from_filename(file.name),
                        filename=file.name,
                    )

    # RadarParameter.WN_REFLECTIVITY, RADAR_PARAMETERS_SWEEPS (BUFR)
    elif url.endswith(".bz2"):
        with bz2.BZ2File(data, mode="rb") as archive:
            data = BytesIO(archive.read())
            yield RadarResult(url=url, data=data, timestamp=get_date_from_filename(url))

    # RADAR_PARAMETERS_RADVOR
    elif url.endswith(".gz"):
        with gzip.GzipFile(fileobj=data, mode="rb") as archive:
            data = BytesIO(archive.read())
            yield RadarResult(url=url, data=data, timestamp=get_date_from_filename(url))

    else:
        yield RadarResult(url=url, data=data, timestamp=get_date_from_filename(url))


@deprecated
def _collect_radolan_cdc_data(
    time_resolution: TimeResolution,
    date_times: Optional[Union[str, List[Union[str, datetime]]]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    prefer_local: bool = False,
    write_file: bool = False,
    folder: Union[str, Path] = DWD_FOLDER_MAIN,
) -> List[Tuple[datetime, BytesIO]]:  # pragma: no cover
    """
    Collect RADOLAN_CDC data for given datetimes and time resolution.
    Additionally, the file can be written to a local folder and read from there as well.

    Args:
        time_resolution: the time resolution for requested data, either hourly or daily
        prefer_local: boolean if file should be read from local store instead
        write_file: boolean if file should be stored on the drive
        folder: path for storage
    Returns:
        list of tuples of a datetime and the corresponding file in bytes
    """
    data = []
    # datetime = pd.to_datetime(datetime).replace(tzinfo=None)
    for date_time in date_times:
        if prefer_local:
            try:
                data.append(
                    (
                        date_time,
                        restore_radar_data(
                            RadarParameter.RADOLAN_CDC,
                            date_time,
                            time_resolution,
                            folder,
                        ),
                    )
                )

                log.info(f"RADOLAN data for {str(date_time)} restored from local")

                continue
            except FileNotFoundError:
                log.info(
                    f"RADOLAN data for {str(date_time)} will be collected from internet"
                )

        remote_radolan_file_path = create_filepath_for_radolan(
            date_time, time_resolution
        )

        if remote_radolan_file_path == "":
            log.warning(f"RADOLAN not found for {str(date_time)}, will be skipped.")
            continue

        date_time_and_file = download_radolan_data(date_time, remote_radolan_file_path)

        data.append(date_time_and_file)

        if write_file:
            store_radar_data(
                RadarParameter.RADOLAN_CDC, date_time_and_file, time_resolution, folder
            )

    return data


def download_radolan_data(
    date_time: datetime,
    url: str,
) -> RadarResult:
    """
    Function used to download RADOLAN_CDC data for a given datetime. The function calls
    a separate download function that is cached for reuse which is especially used for
    historical data that comes packaged for multiple time steps within a single archive.

    :param date_time:   The datetime for the requested RADOLAN file.
                        This is required for the recognition of the returned binary,
                        which has no obvious name tag.

    :param url:         The URL to the file that has the data
                        for the requested datetime, either an archive of multiple files
                        for a datetime in historical time or an archive with one file
                        for the recent RADOLAN file

    :return:            ``RadarResult`` item
    """
    archive_in_bytes = _download_radolan_data(url)

    result = _extract_radolan_data(date_time, archive_in_bytes)
    result.url = url

    return result


@payload_cache_twelve_hours.cache_on_arguments()
def _download_radolan_data(remote_radolan_filepath: str) -> BytesIO:
    """
    Function (cached) that downloads the RADOLAN_CDC file.

    Args:
        remote_radolan_filepath: the file path to the file on the DWD server

    Returns:
        the file in binary, either an archive of one file or an archive of multiple
        files
    """
    return download_file_from_dwd(remote_radolan_filepath)


def _extract_radolan_data(
    date_time: datetime, archive_in_bytes: BytesIO
) -> RadarResult:
    """
    Function used to extract RADOLAN_CDC file for the requested datetime
    from the downloaded archive.

    Args:
        date_time: requested datetime of RADOLAN
        archive_in_bytes: downloaded archive of RADOLAN file

    Returns:
        the datetime formatted as string and the RADOLAN file for the datetime
    """
    # Need string of datetime to check if one of the files in the archive contains
    # the requested datetime
    date_time_string = date_time.strftime(DatetimeFormat.ymdhm.value)

    # First try to unpack archive from archive (case for historical data)
    try:
        # Have to seek(0) as the archive might be reused
        archive_in_bytes.seek(0)

        with gzip.GzipFile(fileobj=archive_in_bytes, mode="rb") as gz_file:
            file_in_archive = BytesIO(gz_file.read())

            with tarfile.open(fileobj=file_in_archive) as tar_file:
                for file in tar_file.getmembers():
                    if date_time_string in file.name:
                        return RadarResult(
                            data=BytesIO(tar_file.extractfile(file).read()),
                            timestamp=date_time,
                            filename=file.name,
                        )

                raise FileNotFoundError(
                    f"RADOLAN file for {date_time_string} not found."
                )  # pragma: no cover

    # Otherwise if there's an error the data is from recent time period and only has to
    # be unpacked once
    except tarfile.ReadError:
        # Seek again for reused purpose
        archive_in_bytes.seek(0)

        with gzip.GzipFile(fileobj=archive_in_bytes, mode="rb") as gz_file:
            return RadarResult(
                data=BytesIO(gz_file.read()), timestamp=date_time, filename=gz_file.name
            )


@deprecated
def create_filepath_for_radolan(
    date_time: datetime, time_resolution: TimeResolution
) -> str:  # pragma: no cover
    """
    Function used to create a relative filepath for a requested datetime depending on
    the file index for the relevant time resolution.

    Args:
        date_time: datetime for requested RADOLAN file
        time_resolution: time resolution enumeration of the request

    Returns:
        a string, either empty if non found or with the relative path to the file
    """
    file_index = create_fileindex_radolan_cdc(time_resolution)

    if date_time in file_index[DWDMetaColumns.DATETIME.value].tolist():
        file_index = file_index[file_index[DWDMetaColumns.DATETIME.value] == date_time]
    else:
        file_index = file_index[
            (file_index[DWDMetaColumns.DATETIME.value].dt.year == date_time.year)
            & (file_index[DWDMetaColumns.DATETIME.value].dt.month == date_time.month)
        ]

    if file_index.empty:
        return ""

    return (
        file_index[DWDMetaColumns.DATETIME.value].item(),
        f"{file_index[DWDMetaColumns.FILENAME.value].item()}",
    )
