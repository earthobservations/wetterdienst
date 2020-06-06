""" function to read data from dwd server """
from typing import List, Tuple
from io import BytesIO
import pandas as pd

from python_dwd.additionals.helpers import create_stationdata_dtype_mapping
from python_dwd.constants.column_name_mapping import GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from python_dwd.constants.metadata import NA_STRING, STATIONDATA_SEP


def parse_dwd_data(filenames_and_files: List[Tuple[str, BytesIO]]) -> pd.DataFrame:
    """
    This function is used to read the station data from given bytes object.
    The filename is required to defined if and where an error happened.

    Args:
        filenames_and_files: list of tuples of a filename and its local stored file
        that should be read

    Returns:
        pandas.DataFrame with requested data, for different station ids the data is still put into one DataFrame
    """
    data = []
    for filename_and_file in filenames_and_files:
        data.append(_parse_dwd_data(filename_and_file))

    try:
        data = pd.concat(data).reset_index(drop=True)
    except ValueError:
        print(f"An error occurred while concatenating the data for files "
              f"{[filename for filename, file in filenames_and_files]}. "
              f"An empty DataFrame will be returned.")
        data = pd.DataFrame()

    return data


def _parse_dwd_data(filename_and_file: Tuple[str, BytesIO]) -> pd.DataFrame:
    """
    A wrapping function that only handles data for one station id. The files passed to it are thus related to this id.
    This is important for storing the data locally as the DataFrame that is stored should obviously only handle one
    station at a time.

    Args:
        filename_and_file: the files belonging to one station
    Returns:
        pandas.DataFrame with data from that station, acn be empty if no data is provided or local file is not found
    or has no data in it
    """
    filename, file = filename_and_file

    try:
        data = pd.read_csv(
            filepath_or_buffer=file,
            sep=STATIONDATA_SEP,
            na_values=NA_STRING,
            dtype="str"  # dtypes are mapped manually to ensure expected dtypes
        )
    except pd.errors.ParserError:
        print(f"The file representing {filename} could not be parsed and is skipped.")
        return pd.DataFrame()
    except ValueError:
        print(f"The file representing {filename} is None and is skipped.")
        return pd.DataFrame()

    data = data.rename(columns=str.upper).rename(GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    return data.astype(create_stationdata_dtype_mapping(data.columns))
