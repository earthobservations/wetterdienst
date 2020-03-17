""" function to read data from dwd server """
from typing import List, Tuple
from io import BytesIO

import pandas as pd

from python_dwd.additionals.functions import retrieve_parameter_from_filename, retrieve_period_type_from_filename, \
    retrieve_time_resolution_from_filename
from python_dwd.constants.column_name_mapping import DATE_NAME, GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from python_dwd.constants.metadata import DATA_FORMAT, NA_STRING, STATIONDATA_SEP


def parse_dwd_data(files_in_bytes: List[Tuple[str, BytesIO]] = None,
                   write_file: bool = False,
                   prefer_local: bool = False,
                   **kwargs) -> pd.DataFrame:
    """
    This function is used to read the stationdata for which the local zip link is
    provided by the 'download_dwd' function. It checks the zipfile from the link
    for its parameters, opens every zipfile in the list of files and reads in the
    containing product file, and if there's an error or it's wanted the zipfile is
    removed afterwards.

    Args:
        files_in_bytes: list of local stored files that should be read
        write_file: If true: The raw zip file will not be deleted, Default is: False.

    Returns:
        DataFrame with requested data

    """
    # For cases with interaction of a local file
    if write_file or prefer_local:
        try:
            sample_file = files_in_bytes[0][0]

            time_res = retrieve_time_resolution_from_filename(sample_file)
            parameter = retrieve_parameter_from_filename(sample_file, time_resolution=time_res)
            period = retrieve_period_type_from_filename(sample_file)
        except (IndexError, TypeError):
            pass
        finally:
            pass

    data = []

    for file in files_in_bytes:
        try:
            data_file = pd.read_csv(filepath_or_buffer=file,
                                    sep=STATIONDATA_SEP,
                                    na_values=NA_STRING)

            data.append(data_file)

        except pd.errors.ParserError as e:
            print(f"The file could be parsed to a dataframe."
                  f"Error: {str(e)}")

    data = pd.concat(data)

    column_names = data.columns

    column_names = [column_name.upper().strip()
                    for column_name in column_names]

    column_names = [GERMAN_TO_ENGLISH_COLUMNS_MAPPING.get(column_name, column_name)
                    for column_name in column_names]

    data.columns = column_names

    data[DATE_NAME] = pd.to_datetime(data[DATE_NAME],
                                     DATA_FORMAT)

    if write_file and not loaded_locallly:
        pass

    return data
