""" function to read data from dwd server """
from datetime import datetime as dt
from pathlib import Path
from typing import List
from zipfile import ZipFile
from io import BytesIO

import pandas as pd

from python_dwd.additionals.functions import check_parameters
from python_dwd.additionals.functions import determine_parameters
from python_dwd.constants.column_name_mapping import DATE_NAME, \
    GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from python_dwd.constants.metadata import STATIONDATA_MATCHSTRINGS, DATA_FORMAT


def parse_dwd_data(files_in_bytes: List[BytesIO],
                   write_file: bool = False) -> pd.DataFrame:
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
    # Test for types of input parameters
    assert isinstance(files_in_bytes, list)
    assert isinstance(write_file, bool)

    if not files_in_bytes:
        return pd.DataFrame()

    data = []

    for file in files_in_bytes:
        try:
            data_file = pd.read_csv(filepath_or_buffer=file,
                                    sep=";",
                                    na_values="-999")

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

    if write_file:
        # Todo function to write parsed file to a .csv or .ncdf4
        pass

    return data
