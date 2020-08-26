""" download scripts """
import gzip
import tarfile
from typing import List, Union, Tuple
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache

from requests.exceptions import InvalidURL

from wetterdienst.constants.access_credentials import DWDCDCBase
from wetterdienst.download.download_services import download_file_from_dwd
from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat
from wetterdienst.exceptions import FailedDownload, ProductFileNotFound

PRODUCT_FILE_IDENTIFIER = "produkt"


def download_climate_observations_data_parallel(
    remote_files: List[str],
) -> List[Tuple[str, BytesIO]]:
    """ wrapper for _download_dwd_data to provide a multiprocessing feature"""

    with ThreadPoolExecutor() as executor:
        files_in_bytes = executor.map(
            _download_climate_observations_data_parallel, remote_files
        )

    return list(zip(remote_files, files_in_bytes))


def _download_climate_observations_data_parallel(
    remote_file: Union[str, Path]
) -> BytesIO:
    """
    This function downloads the station data for which the link is
    provided by the 'select_dwd' function. It checks the shortened filepath (just
    the zipfile) for its parameters, creates the full filepath and downloads the
    file(s) according to the set up folder.

    Args:
        remote_file: contains path to file that should be downloaded
            and the path to the folder to store the files

    Returns:
        stores data on local file system

    """
    try:
        zip_file = download_file_from_dwd(remote_file, DWDCDCBase.CLIMATE_OBSERVATIONS)
    except InvalidURL as e:
        raise InvalidURL(
            f"Error: the station data {remote_file} couldn't be reached."
        ) from e
    except Exception:
        raise FailedDownload(f"Download failed for {remote_file}")

    try:
        zip_file_opened = ZipFile(zip_file)

        # Files of archive
        archive_files = zip_file_opened.namelist()

        for file in archive_files:
            # If found file load file in bytes, close zipfile and return bytes
            if file.startswith(PRODUCT_FILE_IDENTIFIER):
                file_in_bytes = BytesIO(zip_file_opened.open(file).read())

                zip_file_opened.close()

                return file_in_bytes

        # If whatsoever no file was found and returned already throw exception
        raise ProductFileNotFound(
            f"The archive of {remote_file} does not hold a 'produkt' file."
        )

    except BadZipFile as e:
        raise BadZipFile(f"The archive of {remote_file} seems to be corrupted.") from e


def download_radolan_data(
    date_time: datetime,
    remote_radolan_file_path: str,
) -> Tuple[datetime, BytesIO]:
    """
    Function used to download Radolan data for a given datetime. The function calls
    a separate download function that is cached for reuse which is especially used for
    historical data that comes packaged for multiple datetimes in one archive.

    Args:
        date_time: the datetime for the requested RADOLAN file, required for recognition
        of the returned binary, which has no obvious name tag
        remote_radolan_file_path: the remote filepath to the file that has the data
        for the requested datetime, either an archive of multiple files for a datetime
        in historical time or an archive with one file for the recent RADOLAN file

    Returns:
        string of requested datetime and binary file
    """
    archive_in_bytes = _download_radolan_data(remote_radolan_file_path)

    return _extract_radolan_data(date_time, archive_in_bytes)


@lru_cache(maxsize=750)
def _download_radolan_data(remote_radolan_filepath: str) -> BytesIO:
    """
    Function (cached) that downloads the RADOLAN file
    Args:
        remote_radolan_filepath: the file path to the file on the DWD server

    Returns:
        the file in binary, either an archive of one file or an archive of multiple
        files
    """
    return download_file_from_dwd(remote_radolan_filepath, DWDCDCBase.GRIDS_GERMANY)


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
