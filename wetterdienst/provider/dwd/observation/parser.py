# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from io import BytesIO
from typing import List, Tuple

import pandas as pd

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.metadata.column_map import (
    GERMAN_TO_ENGLISH_COLUMNS_MAPPING,
)
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns, DwdOrigColumns
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.observation.metadata.dataset import DwdObservationDataset
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationParameter,
)

log = logging.getLogger(__name__)

# Parameter names used to create full 1 minute precipitation dataset wherever those
# columns are missing (which is the case for non historical data)
PRECIPITATION_PARAMETERS = (
    DwdObservationParameter.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT_DROPLET.value,
    DwdObservationParameter.MINUTE_1.PRECIPITATION.PRECIPITATION_HEIGHT_ROCKER.value,
)

PRECIPITATION_MINUTE_1_QUALITY = DwdObservationParameter.MINUTE_1.PRECIPITATION.QUALITY


def parse_climate_observations_data(
    filenames_and_files: List[Tuple[str, BytesIO]],
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
) -> pd.DataFrame:
    """
    This function is used to read the station data from given bytes object.
    The filename is required to defined if and where an error happened.
    Args:
        filenames_and_files: list of tuples of a filename and its local stored file
        that should be read
        dataset: enumeration of parameter used to correctly parse the date field
        resolution: enumeration of time resolution used to correctly parse the
        date field
        period: enumeration of period of data
    Returns:
        pandas.DataFrame with requested data, for different station ids the data is
        still put into one DataFrame
    """
    data = [
        _parse_climate_observations_data(filename_and_file, dataset, resolution, period)
        for filename_and_file in filenames_and_files
    ]

    if resolution == Resolution.SUBDAILY and dataset == DwdObservationDataset.WIND_EXTREME:
        for i, df in enumerate(data):
            if set(df.columns).issuperset(["qn_8", "fx_911_3"]):
                data[i] = df.rename(columns={"qn_8": "qn_8_3"})
            elif set(df.columns).issuperset(["qn_8", "fx_911_6"]):
                data[i] = df.rename(columns={"qn_8": "qn_8_6"})

        return (
            pd.concat(data)
            .reset_index(drop=True)
            .reindex(columns=["station_id", "date", "qn_8_3", "fx_911_3", "qn_8_6", "fx_911_6"])
        )

    return pd.concat(data).reset_index(drop=True)


def _parse_climate_observations_data(
    filename_and_file: Tuple[str, BytesIO],
    dataset: DwdObservationDataset,
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
            filepath_or_buffer=file,  # prevent leading/trailing whitespace
            sep=";",
            dtype="str",
            na_values="-999",
            encoding="latin1",
            skipinitialspace=True,
        )
    except pd.errors.ParserError:
        log.warning(f"The file representing {filename} could not be parsed and is skipped.")
        return pd.DataFrame()
    except ValueError:
        log.warning(f"The file representing {filename} is None and is skipped.")
        return pd.DataFrame()

    # Column names contain spaces, so strip them away.
    df = df.rename(columns=str.strip)

    # Make column names lowercase.
    df = df.rename(columns=str.lower)

    # End of record (EOR) has no value, so drop it right away.
    df = df.drop(columns=[DwdColumns.EOR.value, "struktur_version"], errors="ignore")

    if resolution == Resolution.MINUTE_1 and dataset == DwdObservationDataset.PRECIPITATION:
        # Need to unfold historical data, as it is encoded in its run length e.g.
        # from time X to time Y precipitation is 0
        if period == Period.HISTORICAL:
            df[DwdOrigColumns.FROM_DATE_ALTERNATIVE.value] = pd.to_datetime(
                df[DwdOrigColumns.FROM_DATE_ALTERNATIVE.value],
                format=DatetimeFormat.YMDHM.value,
            )
            df[DwdOrigColumns.TO_DATE_ALTERNATIVE.value] = pd.to_datetime(
                df[DwdOrigColumns.TO_DATE_ALTERNATIVE.value],
                format=DatetimeFormat.YMDHM.value,
            )

            # Insert date range column over the given from and to dates
            df.insert(
                1,
                DwdOrigColumns.DATE.value,
                df.apply(
                    lambda x: pd.date_range(
                        x[DwdOrigColumns.FROM_DATE_ALTERNATIVE.value],
                        x[DwdOrigColumns.TO_DATE_ALTERNATIVE.value],
                        freq="1min",
                    ),
                    axis=1,
                ),
            )

            df = df.drop(
                columns=[
                    DwdOrigColumns.FROM_DATE_ALTERNATIVE.value,
                    DwdOrigColumns.TO_DATE_ALTERNATIVE.value,
                ]
            )

            # Expand dataframe over calculated date ranges -> one datetime per row
            df = df.explode(DwdOrigColumns.DATE.value)
        else:
            for parameter in PRECIPITATION_PARAMETERS:
                if parameter not in df:
                    df[parameter] = pd.NA

    if resolution == Resolution.MINUTE_5 and dataset == DwdObservationDataset.PRECIPITATION:
        # apparently historical datasets differ from recent and now having all columns as described in the
        # parameter enumeration when recent and now datasets only have precipitation form and
        # precipitation height but not rocker and droplet information
        columns = [DwdOrigColumns.STATION_ID.value, DwdOrigColumns.DATE.value]
        for parameter in DwdObservationParameter[resolution.name][dataset.name]:
            columns.append(parameter.value)

        df = df.reindex(columns=columns)

    # Special handling for hourly solar data, as it has more date columns
    if resolution == Resolution.HOURLY and dataset == DwdObservationDataset.SOLAR:
        # Rename date column correctly to end of interval, as it has additional minute
        # information. Also rename column with true local time to english one
        df = df.rename(
            columns={
                "mess_datum_woz": DwdObservationParameter.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
            }
        )

        # Duplicate the date column to end of interval column
        df[DwdObservationParameter.HOURLY.SOLAR.END_OF_INTERVAL.value] = df[DwdOrigColumns.DATE.value]

        # Fix real date column by cutting of minutes
        df[DwdOrigColumns.DATE.value] = df[DwdOrigColumns.DATE.value].str[:-3]

    if resolution in (Resolution.MONTHLY, Resolution.ANNUAL):
        df = df.rename(
            columns={
                DwdOrigColumns.FROM_DATE.value: DwdColumns.DATE.value,
                DwdOrigColumns.FROM_DATE_ALTERNATIVE.value: DwdColumns.DATE.value,
            }
        )
        df = df.drop(columns=[DwdOrigColumns.TO_DATE.value, DwdOrigColumns.TO_DATE_ALTERNATIVE.value], errors="ignore")

    # Assign meaningful column names (baseline).
    return df.rename(columns=GERMAN_TO_ENGLISH_COLUMNS_MAPPING)
