# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from io import BytesIO
from typing import List, Tuple

import pandas as pd

from wetterdienst.dwd.metadata.column_map import GERMAN_TO_ENGLISH_COLUMNS_MAPPING
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns, DWDOrigMetaColumns
from wetterdienst.dwd.metadata.constants import NA_STRING, STATION_DATA_SEP
from wetterdienst.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.dwd.observations.metadata import DWDObservationParameterSet
from wetterdienst.dwd.observations.metadata.parameter import (
    DWDObservationParameterSetStructure,
)
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution

log = logging.getLogger(__name__)

# Parameter names used to create full 1 minute precipitation dataset wherever those
# columns are missing (which is the case for non historical data)
PRECIPITATION_PARAMETERS = (
    DWDObservationParameterSetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT_DROPLET.value,  # Noqa: E501, B950
    DWDObservationParameterSetStructure.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT_ROCKER.value,  # Noqa: E501, B950
)

PRECIPITATION_MINUTE_1_QUALITY = (
    DWDObservationParameterSetStructure.MINUTE_1.PRECIPITATION.QUALITY
)


def parse_climate_observations_data(
    filenames_and_files: List[Tuple[str, BytesIO]],
    parameter: DWDObservationParameterSet,
    resolution: Resolution,
    period: Period,
) -> pd.DataFrame:
    """
    This function is used to read the station data from given bytes object.
    The filename is required to defined if and where an error happened.
    Args:
        filenames_and_files: list of tuples of a filename and its local stored file
        that should be read
        parameter: enumeration of parameter used to correctly parse the date field
        resolution: enumeration of time resolution used to correctly parse the
        date field
        period: enumeration of period of data
    Returns:
        pandas.DataFrame with requested data, for different station ids the data is
        still put into one DataFrame
    """

    data = [
        _parse_climate_observations_data(
            filename_and_file, parameter, resolution, period
        )
        for filename_and_file in filenames_and_files
    ]

    df = pd.concat(data).reset_index(drop=True)

    return df


def _parse_climate_observations_data(
    filename_and_file: Tuple[str, BytesIO],
    parameter_set: DWDObservationParameterSet,
    resolution: Resolution,
    period: Period,
) -> pd.DataFrame:
    """
    A wrapping function that only handles data for one station id. The files passed to
    it are thus related to this id. This is important for storing the data locally as
    the DataFrame that is stored should obviously only handle one station at a time.
    Args:
        filename_and_file: the files belonging to one station
        resolution: enumeration of time resolution used to correctly parse the
        date field
    Returns:
        pandas.DataFrame with data from that station, acn be empty if no data is
        provided or local file is not found or has no data in it
    """
    filename, file = filename_and_file

    try:
        df = pd.read_csv(
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
    df = df.rename(columns=str.strip)

    # Make column names uppercase.
    df = df.rename(columns=str.upper)

    # End of record (EOR) has no value, so drop it right away.
    df = df.drop(columns=DWDMetaColumns.EOR.value, errors="ignore")

    # Special handling for hourly solar data, as it has more date columns
    if (
        resolution == Resolution.HOURLY
        and parameter_set == DWDObservationParameterSet.SOLAR
    ):
        # Rename date column correctly to end of interval, as it has additional minute
        # information. Also rename column with true local time to english one
        df = df.rename(
            columns={
                "MESS_DATUM_WOZ": (
                    DWDObservationParameterSetStructure.HOURLY.SOLAR.TRUE_LOCAL_TIME.value  # Noqa: E501, B950
                ),
            }
        )

        # Duplicate the date column to end of interval column
        df[DWDObservationParameterSetStructure.HOURLY.SOLAR.END_OF_INTERVAL.value] = df[
            DWDOrigMetaColumns.DATE.value
        ]

        # Fix real date column by cutting of minutes
        df[DWDOrigMetaColumns.DATE.value] = df[DWDOrigMetaColumns.DATE.value].str[:-3]

    if (
        resolution == Resolution.MINUTE_1
        and parameter_set == DWDObservationParameterSet.PRECIPITATION
    ):
        # Need to unfold historical data, as it is encoded in its run length e.g.
        # from time X to time Y precipitation is 0
        if period == Period.HISTORICAL:
            df[DWDOrigMetaColumns.FROM_DATE_ALTERNATIVE.value] = pd.to_datetime(
                df[DWDOrigMetaColumns.FROM_DATE_ALTERNATIVE.value],
                format=DatetimeFormat.YMDHM.value,
            )
            df[DWDOrigMetaColumns.TO_DATE_ALTERNATIVE.value] = pd.to_datetime(
                df[DWDOrigMetaColumns.TO_DATE_ALTERNATIVE.value],
                format=DatetimeFormat.YMDHM.value,
            )

            # Insert date range column over the given from and to dates
            df.insert(
                1,
                DWDOrigMetaColumns.DATE.value,
                df.apply(
                    lambda x: pd.date_range(
                        x[DWDOrigMetaColumns.FROM_DATE_ALTERNATIVE.value],
                        x[DWDOrigMetaColumns.TO_DATE_ALTERNATIVE.value],
                        freq="1min",
                    ),
                    axis=1,
                ),
            )

            df = df.drop(
                columns=[
                    DWDOrigMetaColumns.FROM_DATE_ALTERNATIVE.value,
                    DWDOrigMetaColumns.TO_DATE_ALTERNATIVE.value,
                ]
            )

            # Expand dataframe over calculated date ranges -> one datetime per row
            df = df.explode(DWDOrigMetaColumns.DATE.value)
        else:
            for parameter in PRECIPITATION_PARAMETERS:
                if parameter not in df:
                    df[parameter] = pd.NA

    # Assign meaningful column names (baseline).
    df = df.rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)

    return df
