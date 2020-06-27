""" function to read data from dwd server """
import logging
from typing import List, Tuple, Union
from io import BytesIO
import pandas as pd

from python_dwd.additionals.helpers import create_station_data_dtype_mapping, convert_datetime_hourly
from python_dwd.constants.column_name_mapping import GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from python_dwd.constants.metadata import NA_STRING, STATION_DATA_SEP
from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution

log = logging.getLogger(__name__)


def parse_dwd_data(filenames_and_files: List[Tuple[str, BytesIO]],
                   time_resolution: Union[TimeResolution, str]) -> pd.DataFrame:
    """
    This function is used to read the station data from given bytes object.
    The filename is required to defined if and where an error happened.

    Args:
        filenames_and_files: list of tuples of a filename and its local stored file
        that should be read
        time_resolution: enumeration of time resolution used to correctly parse the date field

    Returns:
        pandas.DataFrame with requested data, for different station ids the data is still put into one DataFrame
    """

    time_resolution = TimeResolution(time_resolution)

    data = []
    for filename_and_file in filenames_and_files:
        data.append(_parse_dwd_data(filename_and_file, time_resolution))

    try:
        data = pd.concat(data).reset_index(drop=True)
    except ValueError:
        log.error(f"An error occurred while concatenating the data for files "
                  f"{[filename for filename, file in filenames_and_files]}. "
                  f"An empty DataFrame will be returned.")
        data = pd.DataFrame()

    return data


def _parse_dwd_data(filename_and_file: Tuple[str, BytesIO],
                    time_resolution: TimeResolution) -> pd.DataFrame:
    """
    A wrapping function that only handles data for one station id. The files passed to it are thus related to this id.
    This is important for storing the data locally as the DataFrame that is stored should obviously only handle one
    station at a time.

    Args:
        filename_and_file: the files belonging to one station
        time_resolution: enumeration of time resolution used to correctly parse the date field
    Returns:
        pandas.DataFrame with data from that station, acn be empty if no data is provided or local file is not found
    or has no data in it
    """
    filename, file = filename_and_file

    try:
        data = pd.read_csv(
            filepath_or_buffer=file,
            sep=STATION_DATA_SEP,
            na_values=NA_STRING,
            dtype="str"  # dtypes are mapped manually to ensure expected dtypes
        )
    except pd.errors.ParserError:
        log.warning(f"The file representing {filename} could not be parsed and is skipped.")
        return pd.DataFrame()
    except ValueError:
        log.warning(f"The file representing {filename} is None and is skipped.")
        return pd.DataFrame()

    # Column names contain spaces, so strip them away.
    data = data.rename(columns=str.strip)

    # Make column names uppercase.
    data = data.rename(columns=str.upper)

    # End of record (EOR) has no value, so drop it right away.
    data = data.drop(columns='EOR', errors='ignore')

    # Assign meaningful column names (baseline).
    data = data.rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    # Properly handle timestamps from "hourly" resolution.
    if time_resolution == TimeResolution.HOURLY:
        data[DWDMetaColumns.DATE.value] = data[DWDMetaColumns.DATE.value].apply(convert_datetime_hourly)

    # Coerce the data types appropriately.
    data = data.astype(create_station_data_dtype_mapping(data.columns))

    return data
