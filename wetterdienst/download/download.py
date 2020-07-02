""" download scripts """
from typing import List, Union, Tuple
from pathlib import Path
import urllib.request
import urllib.error
import zipfile
from io import BytesIO
from multiprocessing import Pool
import pandas as pd

from wetterdienst.constants.metadata import STATION_DATA_MATCH_STRINGS
from wetterdienst.download.download_services import download_file_from_climate_observations
from wetterdienst.additionals.functions import find_all_match_strings_in_string
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.exceptions.failed_download_exception import FailedDownload


def download_dwd_data(remote_files: List[str],
                      parallel: bool = False) -> List[Tuple[str, BytesIO]]:
    """ wrapper for _download_dwd_data to provide a multiprocessing feature"""

    if parallel:
        with Pool() as p:
            files_in_bytes = p.map(_download_dwd_data, remote_files)
        return list(
            zip(
                remote_files,
                files_in_bytes
            )
        )
    else:
        return [(remote_file, _download_dwd_data(remote_file))
                for remote_file in remote_files]


def _download_dwd_data(remote_file: Union[str, Path]) -> BytesIO:
    """
    This function downloads the stationdata for which the link is
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
    except urllib.error.URLError as e:
        raise e(f"Error: the station data {remote_file} couldn't be reached.")
    except Exception:
        raise FailedDownload(f"Download failed for {remote_file}")

    try:
        with zipfile.ZipFile(zip_file) as zip_file_opened:
            produkt_file = [file_in_zip
                            for file_in_zip in zip_file_opened.namelist()
                            if find_all_match_strings_in_string(file_in_zip, STATION_DATA_MATCH_STRINGS)].pop(0)
            file = BytesIO(zip_file_opened.open(produkt_file).read())
    except zipfile.BadZipFile as e:
        raise zipfile.BadZipFile(f"The zipfile seems to be corrupted.\n {str(e)}")

    return file
