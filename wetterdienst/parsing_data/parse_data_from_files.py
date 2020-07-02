""" function to read data from dwd server """
import logging
from typing import List, Tuple, Union
from io import BytesIO
import pandas as pd
from functools import partial
from multiprocessing import Pool

from wetterdienst.additionals.functions import create_station_data_dtype_mapping
from wetterdienst.constants.column_name_mapping import GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from wetterdienst.constants.metadata import NA_STRING, STATION_DATA_SEP
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns, DWDOrigColumns
from wetterdienst.enumerations.datetime_format_enumeration import DatetimeFormat
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution

log = logging.getLogger(__name__)


def parse_dwd_data(filenames_and_files: List[Tuple[str, BytesIO]],
                   parameter: Parameter,
                   time_resolution: Union[TimeResolution, str],
                   parallel: bool = False) -> pd.DataFrame:
    """
    This function is used to read the station data from given bytes object.
    The filename is required to defined if and where an error happened.

    Args:
        filenames_and_files: list of tuples of a filename and its local stored file
        that should be read
        parameter: enumeration of parameter used to correctly parse the date field
        time_resolution: enumeration of time resolution used to correctly parse the date field
        parallel: bool set for parallel processing

    Returns:
        pandas.DataFrame with requested data, for different station ids the data is still put into one DataFrame
    """

    time_resolution = TimeResolution(time_resolution)

    data = []

    if parallel:
        with Pool() as p:
            data.extend(
                p.map(
                    partial(_parse_dwd_data, parameter=parameter, time_resolution=time_resolution),
                    filenames_and_files)
            )
    else:
        for filename_and_file in filenames_and_files:
            data.append(_parse_dwd_data(filename_and_file, parameter, time_resolution))

    data = pd.concat(data).reset_index(drop=True)

    return data


def _parse_dwd_data(filename_and_file: Tuple[str, BytesIO],
                    parameter: Parameter,
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
            dtype="str",
            skipinitialspace=True
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
    data = data.drop(columns=DWDMetaColumns.EOR.value, errors='ignore')

    # Special handling for hourly solar data, as it has more date columns
    if time_resolution == TimeResolution.HOURLY and parameter == Parameter.SOLAR:
        # Rename date column correctly to end of interval, as it has additional minute information
        data = data.rename(
            columns={
                DWDOrigColumns.DATE.value: DWDOrigColumns.END_OF_INTERVAL.value
            }
        )

        # Duplicate the end of interval column to create real datetime column
        # remove minutes e.g. ":09" at the end of string
        data[DWDOrigColumns.DATE.value] = data[DWDOrigColumns.END_OF_INTERVAL.value].str[:-3]

        # Parse both extra timestamps correctly with additional minutes
        data[DWDOrigColumns.END_OF_INTERVAL.value] = pd.to_datetime(
            data[DWDOrigColumns.END_OF_INTERVAL.value], format=DatetimeFormat.YMDH_COLUMN_M.value)

        data[DWDOrigColumns.TRUE_LOCAL_TIME.value] = pd.to_datetime(
            data[DWDOrigColumns.TRUE_LOCAL_TIME.value], format=DatetimeFormat.YMDH_COLUMN_M.value)

        # Store columns for later reordering
        columns = data.columns.values.tolist()
        # Create newly ordered columns, date is inserted while original date was renamed above
        columns_reordered = [columns[0], columns[-1], *columns[1:-1]]

        # Reorder columns to general format
        data = data.reindex(columns=columns_reordered)

    # Assign meaningful column names (baseline).
    data = data.rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    # Properly handle timestamps from "hourly" resolution, subdaily also has hour in timestamp
    if time_resolution in [TimeResolution.HOURLY, TimeResolution.SUBDAILY]:
        data[DWDMetaColumns.DATE.value] = pd.to_datetime(
            data[DWDMetaColumns.DATE.value], format=DatetimeFormat.YMDH.value)

    # Coerce the data types appropriately.
    data = data.astype(create_station_data_dtype_mapping(data.columns))

    return data
