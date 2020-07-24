""" download scripts """
from typing import List, Union, Tuple
from pathlib import Path
import zipfile
from io import BytesIO
from requests.exceptions import InvalidURL
from concurrent.futures import ThreadPoolExecutor

from wetterdienst.download.download_services import (
    download_file_from_climate_observations,
)
from wetterdienst.exceptions.failed_download_exception import FailedDownload
from wetterdienst.exceptions.product_file_not_found_exception import ProductFileNotFound

PRODUCT_FILE_IDENTIFIER = "produkt"


def download_dwd_data_parallel(remote_files: List[str]) -> List[Tuple[str, BytesIO]]:
    """ wrapper for _download_dwd_data to provide a multiprocessing feature"""

    with ThreadPoolExecutor() as executor:
        files_in_bytes = executor.map(_download_dwd_data_parallel, remote_files)

    return list(zip(remote_files, files_in_bytes))


def _download_dwd_data_parallel(remote_file: Union[str, Path]) -> BytesIO:
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
        zip_file = download_file_from_climate_observations(remote_file)
    except InvalidURL as e:
        raise e(f"Error: the station data {remote_file} couldn't be reached.")
    except Exception:
        raise FailedDownload(f"Download failed for {remote_file}")

    try:
        zip_file_opened = zipfile.ZipFile(zip_file)

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

    except zipfile.BadZipFile as e:
        raise e(f"The archive of {remote_file} seems to be corrupted.\n {str(e)}")
