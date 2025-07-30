# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parser for DWD climate observations data."""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING

import polars as pl
from polars import selectors as cs

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.metadata import (
    DwdObservationMetadata,
)

if TYPE_CHECKING:
    from wetterdienst.util.network import File

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel

log = logging.getLogger(__name__)


DROPPABLE_PARAMETERS = {
    # EOR
    "eor",
    "struktur_version",
    # STRING_PARAMETERS
    # hourly
    # cloud_type
    DwdObservationMetadata.hourly.cloud_type.cloud_cover_total_index.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_type_layer1_abbreviation.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_type_layer2_abbreviation.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_type_layer3_abbreviation.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_type_layer4_abbreviation.name_original,
    # cloudiness
    DwdObservationMetadata.hourly.cloudiness.cloud_cover_total_index.name_original,
    # visibility
    DwdObservationMetadata.hourly.visibility.visibility_range_index.name_original,
    # DATE_PARAMETERS_IRREGULAR
    DwdObservationMetadata.hourly.solar.true_local_time.name_original,
    DwdObservationMetadata.hourly.solar.end_of_interval.name_original,
    # URBAN_TEMPERATURE_AIR
    "strahlungstemperatur",
}

COLUMNS_MAPPING = {
    "stations_id": "station_id",
    "mess_datum": "date",
    "stationshoehe": "height",
    "geobreite": "latitude",
    "geogr.breite": "latitude",
    "geolaenge": "longitude",
    "geogr.laenge": "longitude",
    # those two are only used in the historical 1 minute precipitation data
    # we keep start_date and end_date as it is internally named date
    # after exploding the date ranges
    "mess_datum_beginn": "date",
    "mess_datum_ende": "end_date",
}


def parse_climate_observations_data(
    files: list[File],
    dataset: DatasetModel,
    period: Period,
) -> pl.LazyFrame:
    """Parse the climate observations data from the DWD."""
    if dataset == DwdObservationMetadata.subdaily.wind_extreme:
        data = [_parse_climate_observations_data(file, dataset, period) for file in files]
        try:
            df1, df2 = data
            df = df1.join(df2, on=["station_id", "date"], how="full", coalesce=True)
            return df.lazy()
        except ValueError:
            return data[0]
    else:
        data = []
        for file in files:
            data.append(_parse_climate_observations_data(file, dataset, period))
        return pl.concat(data)


def _parse_climate_observations_data(  # noqa: C901
    file: File,
    dataset: DatasetModel,
    period: Period,
) -> pl.LazyFrame:
    """Parse the climate observations data from the DWD."""
    try:
        df = pl.read_csv(
            source=file.content,
            separator=";",
            null_values=["-999"],
            encoding="latin-1",
        )
        df = df.lazy()
    except pl.exceptions.SchemaError:
        log.warning(f"The file representing {file.filename} could not be parsed and is skipped.")
        return pl.LazyFrame()
    except ValueError:
        log.warning(f"The file representing {file.filename} is None and is skipped.")
        return pl.LazyFrame()
    df = df.with_columns(cs.string().str.strip_chars())
    df = df.with_columns(cs.string().replace("-999", None), cs.numeric().replace(-999, None))
    # Column names contain spaces, so strip them away.
    df = df.rename(mapping=lambda col: col.strip().lower())
    # End of record (EOR) has no value, so drop it right away.
    df = df.drop(*DROPPABLE_PARAMETERS, strict=False)
    # Assign meaningful column names (baseline).
    df = df.rename(mapping=lambda col: COLUMNS_MAPPING.get(col, col))
    if dataset == DwdObservationMetadata.minute_1.precipitation:
        if period == Period.HISTORICAL:
            # this is a special case, we return as the dates are already parsed and everything is done
            return _transform_minute_1_precipitation_historical(df)
        missing_parameters = (
            DwdObservationMetadata.minute_1.precipitation.precipitation_height_droplet.name_original,
            DwdObservationMetadata.minute_1.precipitation.precipitation_height_rocker.name_original,
        )
        df = df.with_columns(pl.lit(None, pl.String).alias(parameter) for parameter in missing_parameters)
    elif dataset == DwdObservationMetadata.minute_5.precipitation and period != Period.HISTORICAL:
        missing_parameters = [
            DwdObservationMetadata.minute_5.precipitation.precipitation_height_rocker.name_original,
            DwdObservationMetadata.minute_5.precipitation.precipitation_height_droplet.name_original,
        ]
        df = df.with_columns(pl.lit(None, dtype=pl.String).alias(parameter) for parameter in missing_parameters)
    # Special handling for hourly solar data, as it has more date columns
    elif dataset == DwdObservationMetadata.hourly.solar:
        # Fix timestamps of hourly solar data
        # The timestamps are sometimes given as e.g. 2024-12-08 17:59:00 instead of 2024-12-08 18:00:00
        # Other times they are off by 10 minutes, e.g. 2024-12-08 17:50:00 or 2024-12-08 17:10:00
        # @nkiessling proposed to round the timestamps to the nearest hour
        # Until further discussion, we will apply this rounding
        df = df.with_columns(
            pl.col("date")
            .str.to_datetime("%Y%m%d%H:%M", time_zone="UTC")
            .dt.round(dt.timedelta(hours=1))
            .dt.strftime("%Y%m%d%H%M")
        )
    elif dataset == DwdObservationMetadata.subdaily.wind_extreme:
        if "FX3" in file.filename:
            alias = "qn_8_3"
        elif "FX6" in file.filename:
            alias = "qn_8_6"
        else:
            msg = f"Unknown dataset for wind extremes, expected FX3 or FX6 in filename {file.filename}"
            raise ValueError(msg)
        df = df.rename({"qn_8": alias})
    if dataset.resolution.value in (Resolution.MONTHLY, Resolution.ANNUAL):
        df = df.drop("end_date")
    # prepare date column
    df = df.with_columns(pl.col("date").cast(pl.String).str.pad_end(12, "0"))
    return df.with_columns(
        pl.col("date").str.to_datetime("%Y%m%d%H%M", time_zone="UTC"),
    )


def _transform_minute_1_precipitation_historical(df: pl.LazyFrame) -> pl.LazyFrame:
    """Transform the 1 minute precipitation historical data.

    The data is stored in a way that the start and end date of the precipitation event is given.
    This function transforms the data into a format where each minute of the event is represented by a row.
    """
    df = df.with_columns(
        pl.col("date").cast(str).str.to_datetime("%Y%m%d%H%M", time_zone="UTC"),
        pl.col("end_date").cast(str).str.to_datetime("%Y%m%d%H%M", time_zone="UTC"),
    )
    df = df.with_columns(
        pl.datetime_ranges(pl.col("date"), pl.col("end_date"), interval="1m").alias(
            "date",
        ),
    )
    df = df.drop(
        "end_date",
    )
    # Expand dataframe over calculated date ranges -> one datetime per row
    return df.explode("date")
