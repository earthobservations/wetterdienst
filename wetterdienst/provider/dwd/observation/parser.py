# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

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
    from io import BytesIO

    from wetterdienst.core.timeseries.metadata import DatasetModel

log = logging.getLogger(__name__)

PRECIPITATION_MINUTE_1_QUALITY = DwdObservationMetadata.minute_1.precipitation.quality

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
    filenames_and_files: list[tuple[str, BytesIO]],
    dataset: DatasetModel,
    period: Period,
) -> pl.LazyFrame:
    """This function parses the climate observations data from the DWD.
    There's a special case for subdaily wind extremes, as they are stored in two files.
    Both files are parsed and joined together afterwards.
    """
    if dataset == DwdObservationMetadata.subdaily.wind_extreme:
        data = [
            _parse_climate_observations_data(filename_and_file, dataset, period)
            for filename_and_file in filenames_and_files
        ]
        try:
            df1, df2 = data
            df = df1.join(df2, on=["station_id", "date"], how="full", coalesce=True)
            return df.lazy()
        except ValueError:
            return data[0]
    else:
        data = []
        for filename_and_file in filenames_and_files:
            data.append(_parse_climate_observations_data(filename_and_file, dataset, period))
        return pl.concat(data)


def _parse_climate_observations_data(
    filename_and_file: tuple[str, BytesIO],
    dataset: DatasetModel,
    period: Period,
) -> pl.LazyFrame:
    """This function parses the climate observations data from the DWD.
    There's a special case for 1 minute precipitation data with an early return statement as the function
    _transform_minute_1_precipitation_historical already parses the data and especially the dates.
    """
    filename, file = filename_and_file
    try:
        df = pl.read_csv(
            source=file,
            separator=";",
            null_values=["-999"],
            encoding="latin-1",
        )
        df = df.lazy()
    except pl.exceptions.SchemaError:
        log.warning(f"The file representing {filename} could not be parsed and is skipped.")
        return pl.LazyFrame()
    except ValueError:
        log.warning(f"The file representing {filename} is None and is skipped.")
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
        else:
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
        # Fix real date column by cutting of minutes
        df = df.with_columns(pl.col("date").str.head(-3))
    elif dataset == DwdObservationMetadata.subdaily.wind_extreme:
        if "FX3" in filename:
            alias = "qn_8_3"
        elif "FX6" in filename:
            alias = "qn_8_6"
        else:
            raise ValueError(f"Unknown dataset for wind extremes, expected FX3 or FX6 in filename {filename}")
        df = df.select(
            pl.all().exclude("qn_8"),
            pl.col("qn_8").alias(alias),
        )
    if dataset.resolution.value in (Resolution.MONTHLY, Resolution.ANNUAL):
        df = df.drop("end_date")
    # prepare date column
    df = df.with_columns(pl.col("date").cast(pl.String).str.pad_end(12, "0"))
    return df.with_columns(
        pl.col("date").str.to_datetime("%Y%m%d%H%M", time_zone="UTC"),
    )


def _transform_minute_1_precipitation_historical(df: pl.LazyFrame) -> pl.LazyFrame:
    """We need to unfold historical data, as it is encoded in its run length e.g.
    from time X to time Y precipitation is 0
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
