# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parser for DWD climate derived data."""

from __future__ import annotations

import datetime as dt
import logging
from io import BytesIO
from typing import TYPE_CHECKING

import polars as pl
from polars import selectors as cs

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.derived.metadata import (
    RADIATION_DATASETS,
    SOIL_DATASETS,
    DwdDerivedMetadata,
)

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.util.network import File


log = logging.getLogger(__name__)

# TODO für derived anpassen
DROPPABLE_PARAMETERS = {
    # EOR
    "eor",
    "struktur_version",
    # SOIL Monthly ends with ; which leads to an empty col:
    "",
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
    # soil moisture:
    "datum": "date",
    "stationsindex": "station_id",
    "monat": "date",
}


def parse_climate_derived_data(
    files: list[File],
    dataset: DatasetModel,
) -> pl.LazyFrame:
    """Parse the climate observations data from the DWD."""
    if dataset == DwdDerivedMetadata.hourly.radiation_global:
        data = [_parse_climate_derived_data(file, dataset) for file in files]
        try:
            df1, df2 = data
            df = df1.join(df2, on=["station_id", "date"], how="full", coalesce=True)
            return df.lazy()
        except ValueError:
            return data[0]
    else:
        data = []
        for file in files:
            data.append(_parse_climate_derived_data(file, dataset))
        return pl.concat(data)


def _parse_climate_derived_data(
    file: File,
    dataset: DatasetModel,
) -> pl.LazyFrame:
    """Parse the climate observations data from the DWD."""
    if isinstance(file.content, BytesIO):
        file.content = BytesIO(file.content.read().decode("latin1").encode("utf8"))

    try:
        df = pl.scan_csv(
            source=file.content,
            separator=";",
            null_values=["-999"],
        )
    except pl.exceptions.SchemaError:
        log.warning(f"The file representing {file.filename} could not be parsed and is skipped.")
        return pl.LazyFrame()
    except ValueError:
        log.warning(f"The file representing {file.filename} is None and is skipped.")
        return pl.LazyFrame()
    df = df.with_columns(cs.string().str.strip_chars())
    df = df.with_columns(cs.string().replace("-999", None), cs.numeric().replace(-999, None))
    df = df.with_columns(cs.string().replace("-9999", None), cs.numeric().replace(-9999, None))
    # Column names contain spaces, so strip them away.
    df = df.rename(mapping=lambda col: col.strip().lower())
    # End of record (EOR) has no value, so drop it right away.
    df = df.drop(*DROPPABLE_PARAMETERS, strict=False)
    # Assign meaningful column names (baseline).
    df = df.rename(mapping=lambda col: COLUMNS_MAPPING.get(col, col))
    if dataset in RADIATION_DATASETS:
        df = df.with_columns(
            (pl.col("date").cast(pl.String) + "00")
            .str.to_datetime("%Y%m%d%H%M", time_zone="UTC")
            .dt.round(dt.timedelta(hours=1))
        )
    if dataset in SOIL_DATASETS:
        if dataset.resolution.value.value == "daily":
            str_format = "%Y%m%d"
        elif dataset.resolution.value.value == "monthly":
            str_format = "%Y%m"
        df = df.with_columns((pl.col("date").cast(pl.String)).str.to_datetime(str_format, time_zone="UTC"))

    if dataset.resolution.value in (Resolution.MONTHLY, Resolution.ANNUAL):
        df = df.drop("end_date", strict=False)
    return df
