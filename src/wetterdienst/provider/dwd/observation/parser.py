# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parser for DWD climate observations data."""

from __future__ import annotations

import datetime as dt
import logging
from io import BytesIO
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


# Columns that arrive in the files but are not parameters, and so are not declared in the metadata
# either -- `tests/provider/dwd/observation/test_api_metadata.py` holds those two halves apart, so
# that nothing can be declared and dropped at the same time.
#
# Named as literal strings rather than through `DwdObservationMetadata`, because the point is that
# they have no declaration to refer to.
DROPPABLE_PARAMETERS = {
    # record markers rather than data
    "eor",
    "struktur_version",
    # hourly cloud_type: the letter form of the numeric `v_sN_cs` code beside it, one for one
    # (0 = CI ... 9 = CB, -1 = -1), so it carries nothing the declared parameter does not
    "v_s1_csa",
    "v_s2_csa",
    "v_s3_csa",
    "v_s4_csa",
    # hourly weather_phenomena: German free text spelling out the numeric `ww` code beside it
    # ("Wetter wurde nicht gemeldet" for -1)
    "ww_text",
    # 10 minute urban_temperature_air: radiation temperature, an instrument diagnostic
    "strahlungstemperatur",
}

# DWD writes the two measurement-method indicators as letters -- P for a human person, I for an
# instrument -- in files that are otherwise numeric. Decoding them here is what lets them be
# returned at all: the value column is Float64, so a letter has nowhere to go and both parameters
# used to be dropped on the way out despite being declared.
#
# The digits are ours, not DWD's: 1 for P and 2 for I, following the order DWD lists them in. 0 is
# deliberately unused so that "not measured" stays distinguishable from either method.
#
# Written as text because DWD pads its fields with spaces, so every data column is read as text and
# cast to Float64 only at the very end; a numeric column here would not stack with its neighbours.
MEASUREMENT_METHOD_CODES = {"P": "1", "I": "2"}
CODED_STRING_PARAMETERS = {
    DwdObservationMetadata.hourly.cloud_type.cloud_cover_total_measurement_method.name_original,
    DwdObservationMetadata.hourly.cloudiness.cloud_cover_total_measurement_method.name_original,
    DwdObservationMetadata.hourly.visibility.visibility_range_measurement_method.name_original,
}


def _decode_measurement_method(series: pl.Series) -> pl.Series:
    """Decode the letter-coded measurement method indicators, reporting anything unexpected.

    Only P and I have ever been observed in the files. A letter outside the table has to become
    null, since there is no digit to give it, but that would otherwise make it indistinguishable
    from "not measured" -- the very thing the reserved 0 is meant to keep apart. So say so.
    """
    unknown = set(series.drop_nulls().unique()) - set(MEASUREMENT_METHOD_CODES)
    if unknown:
        log.warning(
            f"Unknown measurement method indicator(s) {sorted(unknown)} in column {series.name!r}; "
            f"expected one of {sorted(MEASUREMENT_METHOD_CODES)}. These values are returned as null.",
        )
    return series.replace_strict(MEASUREMENT_METHOD_CODES, default=None, return_dtype=pl.String)


# hourly solar stamps each record with the UTC instant of a whole true-solar-time hour, so the two
# timestamps sit apart by the solar correction: `1981010101:00` beside `1981010100:09`. That
# distance is the parameter -- longitude correction plus the equation of time, 40 to 71 minutes at
# station 00183, its monthly mean tracing the equation of time from 40.4 in February to 69.1 in
# November about a 54.7 minute longitude term.
#
# It has to be taken here, from the two timestamps as published. `mess_datum` is rounded to the hour
# a few lines further down so that a solar series lines up with every other hourly series, and that
# rounding is what discards the correction.
TIME_FORMAT_SOLAR = "%Y%m%d%H:%M"
TRUE_LOCAL_TIME = DwdObservationMetadata.hourly.solar.true_local_time_offset.name_original


def _encode_true_local_time_offset(series: pl.Series) -> pl.Series:
    """Express the true local time as its distance in minutes from the record's own timestamp."""
    frame = series.struct.unnest()
    published = frame.get_column(TRUE_LOCAL_TIME)
    true_local_time = published.str.to_datetime(TIME_FORMAT_SOLAR, strict=False)
    stamp = frame.get_column("mess_datum").str.to_datetime(TIME_FORMAT_SOLAR, strict=False)
    # a format change would otherwise turn every value null without a word, leaving a declared
    # parameter that answers with nothing -- the failure this whole area exists to prevent
    unparsed = published.filter(published.is_not_null() & true_local_time.is_null())
    if not unparsed.is_empty():
        log.warning(
            f"{unparsed.len()} value(s) of {TRUE_LOCAL_TIME!r} do not parse as "
            f"{TIME_FORMAT_SOLAR!r} and are returned as null, e.g. {unparsed.head(1).to_list()}.",
        )
    return (true_local_time - stamp).dt.total_minutes().cast(pl.String)


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
        if not data:
            return pl.LazyFrame()
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
        if not data:
            return pl.LazyFrame()
        return pl.concat(data)


def _parse_climate_observations_data(  # noqa: C901
    file: File,
    dataset: DatasetModel,
    period: Period,
) -> pl.LazyFrame:
    """Parse the climate observations data from the DWD."""
    if isinstance(file.content, Exception):
        return pl.LazyFrame()
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
    # Column names contain spaces, so strip them away.
    df = df.rename(mapping=lambda col: col.strip().lower())
    # End of record (EOR) has no value, so drop it right away.
    df = df.drop(*DROPPABLE_PARAMETERS, strict=False)
    # turn what the file writes as text into the numbers the value column can hold, before anything
    # downstream expects a number
    columns = set(df.collect_schema().names())
    df = df.with_columns(
        pl.col(parameter).map_batches(_decode_measurement_method, return_dtype=pl.String)
        for parameter in sorted(CODED_STRING_PARAMETERS & columns)
    )
    if TRUE_LOCAL_TIME in columns:
        df = df.with_columns(
            pl.struct("mess_datum", TRUE_LOCAL_TIME)
            .map_batches(_encode_true_local_time_offset, return_dtype=pl.String)
            .alias(TRUE_LOCAL_TIME),
        )
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
    return df.explode("date", empty_as_null=True)
