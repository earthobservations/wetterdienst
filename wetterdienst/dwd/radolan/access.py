import gzip
import logging
import tarfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Tuple, List, Union

from wetterdienst import TimeResolution
from wetterdienst.dwd.metadata.repository import DWD_FOLDER_MAIN

from wetterdienst.dwd.network import download_file_from_dwd
from wetterdienst.dwd.radolan.index import create_file_index_for_radolan
from wetterdienst.dwd.radolan.store import restore_radolan_data, store_radolan_data
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.util.cache import payload_cache_twelve_hours

log = logging.getLogger(__name__)


def collect_radolan_data(
    date_times: List[datetime],
    time_resolution: TimeResolution,
    prefer_local: bool = False,
    write_file: bool = False,
    folder: Union[str, Path] = DWD_FOLDER_MAIN,
) -> List[Tuple[datetime, BytesIO]]:
    """
    Function used to collect RADOLAN data for given datetimes and a time resolution.
    Additionally the file can be written to a local folder and read from there as well.

    :param date_times:      List of datetime objects for which RADOLAN shall be acquired
    :param time_resolution: Time resolution for requested data, either hourly or daily
    :param prefer_local:    File should be read from local store instead
    :param write_file:      File should be stored on the drive
    :param folder:          Path for storage

    :return:                List of tuples: datetime and the corresponding file in bytes
    """
    if time_resolution not in (TimeResolution.HOURLY, TimeResolution.DAILY):
        raise ValueError("RADOLAN is only offered in hourly and daily resolution.")

    data = []
    # datetime = pd.to_datetime(datetime).replace(tzinfo=None)
    for date_time in date_times:
        if prefer_local:
            try:
                data.append(
                    (
                        date_time,
                        restore_radolan_data(date_time, time_resolution, folder),
                    )
                )

                log.info(f"RADOLAN data for {str(date_time)} restored from local")

                continue
            except FileNotFoundError:
                log.info(f"Acquiring RADOLAN data for {str(date_time)}")

        remote_radolan_file_path = create_filepath_for_radolan(
            date_time, time_resolution
        )

        if remote_radolan_file_path == "":
            log.warning(f"RADOLAN not found for {str(date_time)}, will be skipped.")
            continue

        date_time_and_file = download_radolan_data(date_time, remote_radolan_file_path)

        data.append(date_time_and_file)

        if write_file:
            store_radolan_data(date_time_and_file, time_resolution, folder)

    return data


def download_radolan_data(
    date_time: datetime,
    remote_radolan_file_path: str,
) -> Tuple[datetime, BytesIO]:
    """
    Function used to download Radolan data for a given datetime. The function calls
    a separate download function that is cached for reuse which is especially used for
    historical data that comes packaged for multiple datetimes in one archive.

    :param date_time:   The datetime for the requested RADOLAN file.
                        This is required for the recognition of the returned binary,
                        which has no obvious name tag.

    :param remote_radolan_file_path: The remote filepath to the file that has the data
        for the requested datetime, either an archive of multiple files for a datetime
        in historical time or an archive with one file for the recent RADOLAN file

    :return: String of requested datetime and binary file
    """
    archive_in_bytes = _download_radolan_data(remote_radolan_file_path)

    return _extract_radolan_data(date_time, archive_in_bytes)


@payload_cache_twelve_hours.cache_on_arguments()
def _download_radolan_data(remote_radolan_filepath: str) -> BytesIO:
    """
    Function (cached) that downloads the RADOLAN file
    Args:
        remote_radolan_filepath: the file path to the file on the DWD server

    Returns:
        the file in binary, either an archive of one file or an archive of multiple
        files
    """
    return download_file_from_dwd(remote_radolan_filepath)


def _extract_radolan_data(
    date_time: datetime, archive_in_bytes: BytesIO
) -> Tuple[datetime, BytesIO]:
    """
    Function used to extract RADOLAN file for the requested datetime from the downloaded
    and cached archive.

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
                        return date_time, BytesIO(tar_file.extractfile(file).read())

                raise FileNotFoundError(
                    f"Radolan file for {date_time_string} not found."
                )

    # Otherwise if there's an error the data is from recent time period and only has to
    # be unpacked once
    except tarfile.ReadError:
        # Seek again for reused purpose
        archive_in_bytes.seek(0)

        with gzip.GzipFile(fileobj=archive_in_bytes, mode="rb") as gz_file:
            return date_time, BytesIO(gz_file.read())


def create_filepath_for_radolan(
    date_time: datetime, time_resolution: TimeResolution
) -> str:
    """
    Function used to create a relative filepath for a requested datetime depending on
    the file index for the relevant time resolution.

    Args:
        date_time: datetime for requested RADOLAN file
        time_resolution: time resolution enumeration of the request

    Returns:
        a string, either empty if non found or with the relative path to the file
    """
    file_index = create_file_index_for_radolan(time_resolution)

    if date_time in file_index[DWDMetaColumns.DATETIME.value].tolist():
        file_index = file_index[file_index[DWDMetaColumns.DATETIME.value] == date_time]
    else:
        file_index = file_index[
            (file_index[DWDMetaColumns.DATETIME.value].dt.year == date_time.year)
            & (file_index[DWDMetaColumns.DATETIME.value].dt.month == date_time.month)
        ]

    if file_index.empty:
        return ""

    return f"{file_index[DWDMetaColumns.FILENAME.value].item()}"
