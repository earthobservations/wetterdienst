# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from io import BytesIO, StringIO
from typing import List, Tuple

import polars as pl

from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
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

DROPPABLE_PARAMETERS = {
    # EOR
    "eor",
    "struktur_version",
    # STRING_PARAMETERS
    # hourly
    # cloud_type
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_COVER_TOTAL_INDEX.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
    DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
    # cloudiness
    DwdObservationParameter.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDEX.value,
    # visibility
    DwdObservationParameter.HOURLY.VISIBILITY.VISIBILITY_RANGE_INDEX.value,
    # DATE_PARAMETERS_IRREGULAR
    DwdObservationParameter.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
    DwdObservationParameter.HOURLY.SOLAR.END_OF_INTERVAL.value,
    # URBAN_TEMPERATURE_AIR
    "strahlungstemperatur",
}

DATE_FIELDS_REGULAR = {
    Columns.DATE.value,
    Columns.FROM_DATE.value,
    Columns.TO_DATE.value,
}

DWD_TO_ENGLISH_COLUMNS_MAPPING = {
    "stations_id": Columns.STATION_ID.value,
    "mess_datum": Columns.DATE.value,
    "von_datum": Columns.FROM_DATE.value,
    "bis_datum": Columns.TO_DATE.value,
    "mess_datum_beginn": Columns.FROM_DATE.value,
    "mess_datum_ende": Columns.TO_DATE.value,
    "stationshoehe": Columns.HEIGHT.value,
    "geobreite": Columns.LATITUDE.value,
    "geogr.breite": Columns.LATITUDE.value,
    "geolaenge": Columns.LONGITUDE.value,
    "geogr.laenge": Columns.LONGITUDE.value,
    "stationsname": Columns.NAME.value,
    "bundesland": Columns.STATE.value,
}


def parse_climate_observations_data(
    filenames_and_files: List[Tuple[str, BytesIO]],
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
) -> pl.LazyFrame:
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

    return pl.concat(data)


def _parse_climate_observations_data(
    filename_and_file: Tuple[str, BytesIO],
    dataset: DwdObservationDataset,
    resolution: Resolution,
    period: Period,
) -> pl.LazyFrame:
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

    file = BytesIO(file.read().replace(b" ", b""))

    try:
        df = pl.read_csv(
            source=StringIO(file.read().decode("latin1").replace(" ", "")),
            separator=";",
            null_values=["-999"],
            infer_schema_length=0,
        ).lazy()
    except pl.exceptions.SchemaError:
        log.warning(f"The file representing {filename} could not be parsed and is skipped.")
        return pl.LazyFrame()
    except ValueError:
        log.warning(f"The file representing {filename} is None and is skipped.")
        return pl.LazyFrame()

    # Column names contain spaces, so strip them away.
    df = df.rename(mapping={col: col.strip().lower() for col in df.columns})

    # End of record (EOR) has no value, so drop it right away.
    df = df.drop(columns=[col for col in DROPPABLE_PARAMETERS if col in df.columns])

    if resolution == Resolution.MINUTE_1 and dataset == DwdObservationDataset.PRECIPITATION:
        # Need to unfold historical data, as it is encoded in its run length e.g.
        # from time X to time Y precipitation is 0
        if period == Period.HISTORICAL:
            df = (
                df.with_columns(
                    pl.col("mess_datum_beginn")
                    .cast(str)
                    .str.strptime(datatype=pl.Datetime(time_zone="UTC"), fmt=DatetimeFormat.YMDHM.value),
                    pl.col("mess_datum_ende")
                    .cast(str)
                    .str.strptime(datatype=pl.Datetime(time_zone="UTC"), fmt=DatetimeFormat.YMDHM.value),
                )
                .with_columns(
                    pl.date_range(pl.col("mess_datum_beginn"), pl.col("mess_datum_ende"), interval="1m").alias(
                        "mess_datum"
                    )
                )
                .drop(
                    columns=[
                        "mess_datum_beginn",
                        "mess_datum_ende",
                    ]
                )
            )

            # Expand dataframe over calculated date ranges -> one datetime per row
            df = df.explode("mess_datum")
        else:
            df = df.with_columns(pl.all(), PRECIPITATION_PARAMETERS)

    if resolution == Resolution.MINUTE_5 and dataset == DwdObservationDataset.PRECIPITATION:
        # apparently historical datasets differ from recent and now having all columns as described in the
        # parameter enumeration when recent and now datasets only have precipitation form and
        # precipitation height but not rocker and droplet information
        columns = ["stations_id", "mess_datum"]
        for parameter in DwdObservationParameter[resolution.name][dataset.name]:
            columns.append(parameter.value)

        df = df.with_columns(columns)

    # Special handling for hourly solar data, as it has more date columns
    if resolution == Resolution.HOURLY:
        if dataset == DwdObservationDataset.SOLAR:
            # Fix real date column by cutting of minutes
            df = df.with_columns(pl.col("mess_datum").str.slice(0, pl.col("mess_datum").str.n_chars() - 3))

    if resolution in (Resolution.MONTHLY, Resolution.ANNUAL):
        df = df.drop(columns=[col for col in ["bis_datum", "mess_datum_ende"] if col in df.columns]).rename(
            mapping={"mess_datum_beginn": "mess_datum"}
        )

    if resolution is Resolution.SUBDAILY and dataset is DwdObservationDataset.WIND_EXTREME:
        df = df.with_columns(
            pl.when("fx_911_3" in df.columns).then(pl.col("qn_8")).alias("qn_8_3"),
            pl.when("fx_911_6" in df.columns).then(pl.col("qn_8")).alias("qn_8_6"),
        )

    fmt = None
    if resolution is Resolution.MINUTE_5:
        fmt = "%Y%m%d%H%M"
    elif resolution is Resolution.MINUTE_10:
        fmt = "%Y%m%d%H%M"
    elif resolution is Resolution.HOURLY:
        fmt = "%Y%m%d%H"
    elif resolution is Resolution.SUBDAILY:
        fmt = "%Y%m%d%H"
    elif resolution is Resolution.DAILY:
        fmt = "%Y%m%d"
    elif resolution is Resolution.MONTHLY:
        fmt = "%Y%m%d"
    elif resolution is Resolution.ANNUAL:
        fmt = "%Y%m%d"

    if fmt:
        df = df.with_columns(
            pl.col("mess_datum").str.strptime(pl.Datetime(time_zone="UTC"), fmt),
        )

    # Assign meaningful column names (baseline).
    return df.rename(mapping={key: value for key, value in DWD_TO_ENGLISH_COLUMNS_MAPPING.items() if key in df.columns})
