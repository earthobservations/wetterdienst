""" Data collection pipeline """
from typing import List
import pandas as pd

from python_dwd.file_path_handling.file_list_creation import create_file_list_for_dwd_server
from python_dwd.download.download import download_dwd_data
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution


def collect_dwd_data(station_ids: List[int],
                     parameter: Parameter,
                     time_resolution: TimeResolution,
                     period_type: PeriodType,
                     folder: str,
                     parallel_download: bool = False,
                     create_new_filelist: bool = None) -> pd.DataFrame:
    """
    Function that organizes the complete pipeline of data collection, either from the internet or from a local file.
    Args:
        station_ids:
        parameter:
        time_resolution:
        period_type:
        folder:
        parallel_download:
        create_new_filelist:

    Returns:

    """
    file_list = create_file_list_for_dwd_server(
        station_ids=station_ids,
        parameter=parameter,
        time_resolution=time_resolution,
        period_type=period_type,
        folder=folder,
        create_new_filelist=create_new_filelist
    )

    files_in_bytes = download_dwd_data(
        remote_files=file_list,
        parallel_download=parallel_download
    )
