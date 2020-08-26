""" function to read data from dwd server """
import logging
from typing import List, Tuple, Union
from io import BytesIO
import pandas as pd

from wetterdienst.additionals.functions import coerce_field_types
from wetterdienst.constants.column_name_mapping import GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from wetterdienst.constants.metadata import NA_STRING, STATION_DATA_SEP
from wetterdienst.enumerations.column_names_enumeration import (
    DWDOrigMetaColumns,
    DWDMetaColumns,
    DWDOrigDataColumns,
)
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution

log = logging.getLogger(__name__)


def parse_climate_observations_data(
    filenames_and_files: List[Tuple[str, BytesIO]],
    parameter: Parameter,
    time_resolution: Union[TimeResolution, str],
) -> pd.DataFrame:
    """
    This function is used to read the station data from given bytes object.
    The filename is required to defined if and where an error happened.
    Args:
        filenames_and_files: list of tuples of a filename and its local stored file
        that should be read
        parameter: enumeration of parameter used to correctly parse the date field
        time_resolution: enumeration of time resolution used to correctly parse the
        date field
    Returns:
        pandas.DataFrame with requested data, for different station ids the data is
        still put into one DataFrame
    """

    time_resolution = TimeResolution(time_resolution)

    data = [
        _parse_climate_observations_data(filename_and_file, parameter, time_resolution)
        for filename_and_file in filenames_and_files
    ]

    data = pd.concat(data).reset_index(drop=True)

    return data


def _parse_climate_observations_data(
    filename_and_file: Tuple[str, BytesIO],
    parameter: Parameter,
    time_resolution: TimeResolution,
) -> pd.DataFrame:
    """
    A wrapping function that only handles data for one station id. The files passed to
    it are thus related to this id. This is important for storing the data locally as
    the DataFrame that is stored should obviously only handle one station at a time.
    Args:
        filename_and_file: the files belonging to one station
        time_resolution: enumeration of time resolution used to correctly parse the
        date field
    Returns:
        pandas.DataFrame with data from that station, acn be empty if no data is
        provided or local file is not found or has no data in it
    """
    filename, file = filename_and_file

    try:
        data = pd.read_csv(
            filepath_or_buffer=BytesIO(
                file.read().replace(b" ", b"")
            ),  # prevent leading/trailing whitespace
            sep=STATION_DATA_SEP,
            dtype="str",
            na_values=NA_STRING,
        )
    except pd.errors.ParserError:
        log.warning(
            f"The file representing {filename} could not be parsed and is skipped."
        )
        return pd.DataFrame()
    except ValueError:
        log.warning(f"The file representing {filename} is None and is skipped.")
        return pd.DataFrame()

    # Column names contain spaces, so strip them away.
    data = data.rename(columns=str.strip)

    # Make column names uppercase.
    data = data.rename(columns=str.upper)

    # End of record (EOR) has no value, so drop it right away.
    data = data.drop(columns=DWDMetaColumns.EOR.value, errors="ignore")

    # Special handling for hourly solar data, as it has more date columns
    if time_resolution == TimeResolution.HOURLY and parameter == Parameter.SOLAR:
        # Rename date column correctly to end of interval, as it has additional minute
        # information. Also rename column with true local time to english one
        data = data.rename(
            columns={
                "MESS_DATUM_WOZ": DWDOrigDataColumns.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
            }
        )

        # Duplicate the date column to end of interval column
        data[DWDOrigDataColumns.HOURLY.SOLAR.END_OF_INTERVAL.value] = data[
            DWDOrigMetaColumns.DATE.value
        ]

        # Fix real date column by cutting of minutes
        data[DWDOrigMetaColumns.DATE.value] = data[DWDOrigMetaColumns.DATE.value].str[
            :-3
        ]

    # Assign meaningful column names (baseline).
    data = data.rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    # Coerce the data types appropriately.
    data = coerce_field_types(data, time_resolution)

    return data
