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
from wetterdienst.model.quality_flags import RAW_SUFFIX, Sentinel, clear_sentinels
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
    "mess_datum": "timestamp",
    "stationshoehe": "elevation",
    "geobreite": "latitude",
    "geogr.breite": "latitude",
    "geolaenge": "longitude",
    "geogr.laenge": "longitude",
    # those two are only used in the historical 1 minute precipitation data
    # we keep start_date and end_date as it is internally named timestamp
    # after exploding the date ranges
    "mess_datum_beginn": "timestamp",
    "mess_datum_ende": "end_date",
    # soil moisture:
    "datum": "timestamp",
    "stationsindex": "station_id",
    "monat": "timestamp",
}


# -999 is what the descriptions of the DWD datasets give for a missing value, -9999 what the derived ones add; every
# column that is a parameter keeps the text it was written as, in `<column>__raw`, for `quality_flags` (GH-2759)
_MISSING_VALUE = Sentinel("-999", "-9999")
# the columns that identify a row and are no parameter, by the names the files give them
_NO_RAW_COLUMNS = {
    "stations_id",
    "mess_datum",
    "mess_datum_beginn",
    "mess_datum_ende",
    "stationshoehe",
    "geobreite",
    "geogr.breite",
    "geolaenge",
    "geogr.laenge",
    "datum",
    "stationsindex",
    "monat",
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
            df = df1.join(df2, on=["station_id", "timestamp"], how="full", coalesce=True)
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
    if isinstance(file.content, Exception):
        return pl.LazyFrame()
    if isinstance(file.content, BytesIO):
        file.content = BytesIO(file.content.read().decode("latin1").encode("utf8"))

    try:
        # every column as text, as the sentinels are matched on the text (see the observation parser)
        df = pl.scan_csv(
            source=file.content,
            separator=";",
            infer_schema=False,
        )
    except pl.exceptions.SchemaError:
        log.warning(f"The file representing {file.filename} could not be parsed and is skipped.")
        return pl.LazyFrame()
    except ValueError:
        log.warning(f"The file representing {file.filename} is None and is skipped.")
        return pl.LazyFrame()
    df = df.with_columns(cs.string().str.strip_chars())
    # Column names contain spaces, so strip them away.
    df = df.rename(mapping=lambda col: col.strip().lower())
    # End of record (EOR) has no value, so drop it right away.
    df = df.drop(*DROPPABLE_PARAMETERS, strict=False)
    columns = sorted(df.collect_schema().names())
    df = clear_sentinels(df, columns, _MISSING_VALUE)
    df = df.drop(
        *(
            f"{column}{RAW_SUFFIX}"
            for column in columns
            if column in _NO_RAW_COLUMNS or column.startswith(("qn", "qualitaet"))
        )
    )
    # Assign meaningful column names (baseline).
    df = df.rename(mapping=lambda col: COLUMNS_MAPPING.get(col, col))
    if dataset in RADIATION_DATASETS:
        df = df.with_columns(
            (pl.col("timestamp").cast(pl.String) + "00")
            .str.to_datetime("%Y%m%d%H%M", time_zone="UTC")
            .dt.round(dt.timedelta(hours=1))
        )
    if dataset in SOIL_DATASETS:
        if dataset.resolution.value.value == "daily":
            str_format = "%Y%m%d"
        elif dataset.resolution.value.value == "monthly":
            str_format = "%Y%m"
        df = df.with_columns((pl.col("timestamp").cast(pl.String)).str.to_datetime(str_format, time_zone="UTC"))

    if dataset.resolution.value in (Resolution.MONTHLY, Resolution.ANNUAL):
        df = df.drop("end_date", strict=False)
    return df
