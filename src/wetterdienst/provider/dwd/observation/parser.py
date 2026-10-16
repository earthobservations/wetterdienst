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
from wetterdienst.model.quality_flags import RAW_SUFFIX, Sentinel, clear_sentinels, raw_column
from wetterdienst.provider.dwd.observation.download import ProductFile
from wetterdienst.provider.dwd.observation.fileindex import is_mez_file
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
    # hourly urban_temperature_air: radiation temperature, an instrument diagnostic (the 10 minute
    # dataset publishes it as `strahl_st_10` and declares it as temperature_radiant_2m)
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

# The hourly cloud fields carry -1 where the sky could not be seen at all, SYNOP's N = 9. DWD's own
# sheet documents only -999 as a missing value, but -1 stands in 1.2% of station 00003's hourly
# records, and fog codes (`ww` 40-49) accompany 69.1% of those against 0.8% of the rest -- 45 and
# 47, "fog, sky invisible", most of all. It is a statement that no amount could be given, not an
# amount: left alone it is read as -1 eighths and converts to -0.125 of the sky.
#
# Only the cover fields. `v_sN_cs` beside them is a cloud *type* code where -1 is DWD's own value
# for an automated observation, and dimensionless, so nothing distorts it.
SKY_OBSCURED = "-1"
CLOUD_COVER_PARAMETERS = {
    DwdObservationMetadata.hourly.cloudiness.cloud_cover_total.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_cover_total.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_cover_layer1.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_cover_layer2.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_cover_layer3.name_original,
    DwdObservationMetadata.hourly.cloud_type.cloud_cover_layer4.name_original,
}
# The hourly moisture dataset documents `missing value = -999`, but its files write -99.9 for the five
# moisture columns in every hour without a reading (station 03735, 1949-01-28 06:00, in
# stundenwerte_TF_03735_19490101_19511231_hist.zip; station 14006, 2025-01-05 01:00, in
# stundenwerte_TF_14006_20201104_20251231_hist.zip). `TT_STD` beside them is a reading, and `P_STD`
# is not touched by this rule. -99.9 is outside the physical range of all five. Only this dataset:
# GH-2669 sampled hourly air temperature, dew point and subdaily moisture and found none of them
# writing it, so the rule stays local rather than a blanket -99.9.
MOISTURE_MISSING = -99.9
MOISTURE_MISSING_PARAMETERS = {
    DwdObservationMetadata.hourly.moisture.humidity_absolute.name_original,
    DwdObservationMetadata.hourly.moisture.pressure_vapor.name_original,
    DwdObservationMetadata.hourly.moisture.temperature_wet_2m.name_original,
    DwdObservationMetadata.hourly.moisture.humidity_relative.name_original,
    DwdObservationMetadata.hourly.moisture.temperature_dew_point_2m.name_original,
}

# The hourly moisture file of a station without a barometer carries one pressure for the whole file, which is no
# reading (GH-2699; read 2026-10-15 in all 1314 files of recent/ and historical/ of opendata.dwd.de). `P_STD` is
# "Stundenwerte Luftdruck" ("hourly value of barometric pressure") in DWD's sheet, from SYNOP reports, and the sheet
# says nothing of a constant. 761 files hold a single distinct value in every one of their 8 to 202,384 readings
# (stundenwerte_TF_14072_akt.zip: 997.3 in 12,844 rows). 736 of them, and 55 more with two values, are zips without a
# `Metadaten_Geraete_Luftdruck_*.txt`, the instrument list of the barometer (818 files have none); 471 of the 496 zips
# that have one hold 10 or more distinct values (the others, 25, are constant). A mean, a trend or a pressure
# reduction over the constant reflects the station, not the weather.
#
# Judged per file, here, before the files of the periods are put together: a file of at least
# `STATION_CONSTANT_MIN_READINGS` readings with exactly one distinct value has it nulled, and the value stays as the
# text of `quality_flags`' `raw` token (`raw:997.3`). Fewer readings are no evidence (a file of 24 rows is one day).
# A constant that changed once in the file (953.1 and then 954.8 from 2026-10-13 at station 00142; 55 files) is two
# distinct values and is not caught.
STATION_CONSTANT_MIN_READINGS = 500
STATION_CONSTANT_PARAMETERS = (
    (DwdObservationMetadata.hourly.moisture, DwdObservationMetadata.hourly.moisture.pressure_air_site.name_original),
)

# The hourly weather phenomena file writes -1 in `WW` for every hour in which the present weather was not
# reported, and says so in the text column beside it: `       1869;2025040900;    3;  -1;Wetter wurde
# nicht gemeldet;eor` (stundenwerte_WW_01869_akt.zip; 9263 of the 13088 records of station 01869 are
# that row, and no other `WW_Text` goes with -1 nor does -1 go with another text). No description states
# it. It is "not reported", not a weather: left alone it is counted, maxed and averaged as one. Only
# this column: `v_sN_cs` of hourly cloud_type is a code where -1 is DWD's own value for an automated
# observation.
WEATHER_NOT_REPORTED = -1
WEATHER_NOT_REPORTED_PARAMETERS = {
    DwdObservationMetadata.hourly.weather_phenomena.weather.name_original,
}


# The wind files write 990 in the direction column where there is no direction (hourly: station 00003,
# 1975-10-16 08:00, `3;1975101608;    5;   1.3; 990;eor`, a speed of 1.3 m/s beside it; 10 minute:
# station 00198, 1994-05-02 13:50, `198;199405021350;    1;   1.1; 990;eor`). The descriptions
# document only -999, but 990 is the WMO code for a variable direction, lies outside 0 to 360 degrees,
# and left alone is returned as 990 degrees.
#
# Only the datasets whose files hold it (GH-2686): in every file of the other DWD wind directions
# (hourly wind_synop, subdaily wind, 10 minute extreme_wind, the urban ones) the direction lies
# between 0 and 360 or is -999.
WIND_DIRECTION_VARIABLE = 990
WIND_DIRECTION_PARAMETERS = (
    (DwdObservationMetadata.hourly.wind, DwdObservationMetadata.hourly.wind.wind_direction.name_original),
    (DwdObservationMetadata.minute_10.wind, DwdObservationMetadata.minute_10.wind.wind_direction.name_original),
)

# The wind files write a direction of 0 where there is no direction, and mostly 360 for north (GH-2805; read
# 2026-10-12 in 24 station files per dataset and period of opendata.dwd.de). Left alone it is returned as 0 degrees,
# north, which a wind rose or a mean direction counts. Where DWD's sheets say what 0 is, every 0 is null; where they
# do not and the files use it for north too, only a 0 beside a speed of 0 is:
#
# - hourly wind_synop DD: the sheet names the column "Windrichtung uml.,windstill DD=00", the code of a variable or
#   calm wind. 129,350 of the 129,420 historical hours with a speed of 0 have DD 0, and 27,714 more a speed above 0
#   (11,892 at 1.0 m/s). A few stations also write it at 7 m/s for hours (00785, 1986-02-14), where `raw:0` keeps it.
# - hourly wind D: the sheet gives a "36-teilige Windrose", which has no point 0. 141,852 of the 141,873 historical
#   hours with a speed of 0 have D 0; beside a wind that blows it falls from 1,447 of 180,845 hours below 0.5 m/s to 1
#   of 1,487,127 at 3 to 5 m/s, while 360 stays at 1.6 to 4.6 % of the hours up to 5 m/s. The hourly files of 01691
#   and 03761, which write north as 0 at 10 minutes, hold 0 to 3 zeros a year (1993 to 2007) at 1 m/s or more against
#   33 to 257 of 360.
# - subdaily wind DK_TER: the sheet gives a "32-teilige Windrose" (a point is 11.25 degrees, 32 north, GH-2808), which
#   has no point 0. 97,605 of the 97,610 terms with Beaufort 0 have 0, and 798 of the 1,284 in the recent files
#   Beaufort 1 or 2.
# - 10 minute wind DD_10 and extreme_wind DX_10 have no sheet text on it. 81,158 of the 82,475 historical 10 minutes
#   with a speed of 0 have DD_10 0 (DX_10: 68,166 of 70,458), but some stations also write north as 0 (DD_10: 01691,
#   1993 to 1999, and 03761, 2000 to 2006; DX_10: 00003): 01691 on 1994-05-01 reads 360, 360, 0, 360, 0, 360, 360 from
#   15:30 to 16:30 at 4 to 6 m/s, and from 1 m/s on 492 rows read 0 against 94,042 of 360. DWD documents no limit
#   between a calm and a wind (1,457 of the 29,704 10 minutes from 0.05 to 0.25 m/s read 0), so only a 0 beside a
#   speed of exactly 0 is null, with the gust for extreme_wind. A 0 beside a missing speed stays.
# - 10 minute urban_wind DD_ST_10 (GH-2809) is the same picture as 10 minute wind, with FF_ST_10 beside it. All six
#   stations (read 2026-10-13): 20 zeros in the recent files and 51 in the historical ones (they overlap in 2025),
#   every one beside a speed of 0.00, and every 10 minutes with a speed of 0.00 has the 0 (15818 on 2025-04-28: 220 at
#   0.10 m/s at 18:20, 0 at 0.00 at 18:30, 200 at 0.20 at 18:40). The sheet of the dataset answers 404, so it follows
#   the rule of 10 minute wind. The hourly urban_wind WINDRICHTUNG is not covered, and is deliberately left as the
#   source writes it: its 1,288 zeros in 295,005 hours (read 2026-10-12) never come beside a speed of 0 (the minimum
#   speed is 0.1 m/s), mostly at 0.2 to 0.4 m/s, 11 hours at 1 m/s or more, and DWD's sheet says nothing of a 0, so
#   whether it is a calm or north is not known.
CALM_WIND_DIRECTION_PARAMETERS = (
    (DwdObservationMetadata.hourly.wind, DwdObservationMetadata.hourly.wind.wind_direction.name_original, None),
    (
        DwdObservationMetadata.hourly.wind_synoptic,
        DwdObservationMetadata.hourly.wind_synoptic.wind_direction.name_original,
        None,
    ),
    (DwdObservationMetadata.subdaily.wind, DwdObservationMetadata.subdaily.wind.wind_direction.name_original, None),
    (
        DwdObservationMetadata.minute_10.wind,
        DwdObservationMetadata.minute_10.wind.wind_direction.name_original,
        DwdObservationMetadata.minute_10.wind.wind_speed.name_original,
    ),
    (
        DwdObservationMetadata.minute_10.wind_extreme,
        DwdObservationMetadata.minute_10.wind_extreme.wind_direction_gust_max.name_original,
        DwdObservationMetadata.minute_10.wind_extreme.wind_gust_max.name_original,
    ),
    (
        DwdObservationMetadata.minute_10.urban_wind,
        DwdObservationMetadata.minute_10.urban_wind.wind_direction.name_original,
        DwdObservationMetadata.minute_10.urban_wind.wind_speed.name_original,
    ),
)

# The subdaily wind direction is the point of a 32-point wind rose, not degrees (GH-2808; read 2026-10-13 in
# terminwerte_FK_00096_akt.zip against stundenwerte_F_00096_akt.zip, the hourly wind_synop DD in degrees, at the same
# hours: all 1799 pairs agree within 20 degrees once multiplied by 11.25): 24 beside DD 270 and 290, 20 beside 220
# and 230, 16 beside 170 and 190, 8 beside 100. The points run 0 to 32 in steps of 11.25 degrees, 32 is north, 24
# west, 16 south, 8 east. The 0 of a calm is null before this (see above), so every value left is a point from 1 to
# 32, 32 giving 360 degrees.
WIND_ROSE_DEGREES = 360 / 32
WIND_ROSE_PARAMETERS = (
    (DwdObservationMetadata.subdaily.wind, DwdObservationMetadata.subdaily.wind.wind_direction.name_original),
)

# the sentinels, as the files write them. -999 is the one every description documents, for every column; the others are
# what the notes above found in the files of one dataset or a few of its columns
_MISSING_VALUE = Sentinel("-999")
_SKY_OBSCURED = Sentinel(SKY_OBSCURED)
_MOISTURE_MISSING = Sentinel(str(MOISTURE_MISSING))
_WEATHER_NOT_REPORTED = Sentinel(str(WEATHER_NOT_REPORTED))
_WIND_DIRECTION_VARIABLE = Sentinel(str(WIND_DIRECTION_VARIABLE))
_NO_WIND_DIRECTION = Sentinel("0")
# the columns that identify a row or describe a station and are no parameter: no text is kept of their sentinel
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
}


def _is_quality(column: str) -> bool:
    """Tell the quality level column of a file (`QN_3`, `QUALITAETS_NIVEAU`) from a parameter."""
    return column.startswith(("qn", "qualitaet"))


CODED_STRING_PARAMETERS = {
    DwdObservationMetadata.hourly.cloud_type.cloud_cover_total_measurement_method.name_original,
    DwdObservationMetadata.hourly.cloudiness.cloud_cover_total_measurement_method.name_original,
    DwdObservationMetadata.hourly.visibility.visibility_measurement_method.name_original,
}


def _null_station_constant(df: pl.LazyFrame, column: str) -> pl.LazyFrame:
    """Null a column of one file that holds a single value, keeping the text of it as `raw` (GH-2699).

    A file is the unit: this runs on one file before the files are put together, so a station whose
    recent file is constant and whose historical file is not is judged on each. The value is judged
    as a number (`997.3` and `997.30` are one), and the `raw` token is the text the file wrote.
    """
    value = pl.col(column)
    readings = value.cast(pl.Float64, strict=False).drop_nulls()
    constant = (readings.len() >= STATION_CONSTANT_MIN_READINGS) & (readings.n_unique() == 1)
    raw = pl.when(constant & value.is_not_null()).then(value)
    if raw_column(column) in df.collect_schema():
        raw = pl.coalesce(pl.col(raw_column(column)), raw)
    return df.with_columns(
        pl.when(constant).then(pl.lit(None, dtype=pl.String)).otherwise(value).alias(column),
        raw.alias(raw_column(column)),
    )


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
}


# The hourly sun stamps of a period that DWD's `Metadaten_Parameter` calls "Stundenwerte in WOZ" are the hour of the
# station's true solar time ("Wahre Ortszeit"), not UTC, but are returned as the stamps are written, unshifted
# (GH-2816, GH-2617): the shift is the station's longitude over 15 plus the equation of time, 35 minutes at Aachen,
# 20 at Hamburg, about 0 at Goerlitz, +-16 minutes over the year, so no whole hour. Instead the rows of those periods
# are flagged `zone:woz` in `quality_flags`. The periods come from the metadata file of the station's archive
# (`ProductFile.woz_spans`), as they are not at one date: 140 of the 528 stations with a WOZ period end the last one on
# 2001-03-31, 172 have one that runs on (249,640 station days, to 2006), and some change back and forth by the month
# (read 2026-10-15 in all 636 historical archives). A boolean column of the wide frame, dropped in `_tidy_up_df`.
WOZ_COLUMN = "woz"


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
            df = df1.join(df2, on=["station_id", "timestamp"], how="full", coalesce=True)
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
        # every column as text, as it is cast at the very end: with `null_values=["-999"]`, which this read had, a
        # sentinel did not take part in the dtype of its column, and without it a column that opens with -999
        # is an integer one that the first padded value fails (GH-2759)
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
    columns = set(df.collect_schema().names())
    # every sentinel DWD writes is mapped to null here, with the text it was written as in `<column>__raw`, which
    # `DwdObservationValues._tidy_up_df` carries into `quality_flags` (GH-2759). The index and quality columns are
    # cleaned as before and keep no text.
    data_columns = sorted(column for column in columns if column not in _NO_RAW_COLUMNS and not _is_quality(column))
    df = clear_sentinels(df, sorted(columns), _MISSING_VALUE)
    df = df.drop(*(f"{column}{RAW_SUFFIX}" for column in sorted(columns) if column not in data_columns))
    # turn what the file writes as text into the numbers the value column can hold, before anything
    # downstream expects a number
    df = df.with_columns(
        pl.col(parameter).map_batches(_decode_measurement_method, return_dtype=pl.String)
        for parameter in sorted(CODED_STRING_PARAMETERS & columns)
    )
    df = clear_sentinels(df, sorted(CLOUD_COVER_PARAMETERS & columns), _SKY_OBSCURED)
    if dataset == DwdObservationMetadata.hourly.moisture:
        df = clear_sentinels(df, sorted(MOISTURE_MISSING_PARAMETERS & columns), _MOISTURE_MISSING)
    for constant_dataset, parameter in STATION_CONSTANT_PARAMETERS:
        if dataset == constant_dataset and parameter in columns:
            df = _null_station_constant(df, parameter)
    if dataset == DwdObservationMetadata.hourly.weather_phenomena:
        df = clear_sentinels(df, sorted(WEATHER_NOT_REPORTED_PARAMETERS & columns), _WEATHER_NOT_REPORTED)
    for wind_dataset, parameter in WIND_DIRECTION_PARAMETERS:
        if dataset == wind_dataset and parameter in columns:
            df = clear_sentinels(df, [parameter], _WIND_DIRECTION_VARIABLE)
    for wind_dataset, parameter, speed in CALM_WIND_DIRECTION_PARAMETERS:
        if dataset == wind_dataset and parameter in columns and (speed is None or speed in columns):
            # where the file has the speed, a 0 is only a calm beside a speed of exactly 0; a speed that is missing is
            # no calm
            calm = (
                _NO_WIND_DIRECTION
                if speed is None
                else Sentinel("0", where=pl.col(speed).cast(pl.Float64, strict=False).eq(0))
            )
            df = clear_sentinels(df, [parameter], calm)
    # after the sentinels: a rose point is only turned into degrees where it is a value (GH-2808)
    for rose_dataset, parameter in WIND_ROSE_PARAMETERS:
        if dataset == rose_dataset and parameter in columns:
            df = df.with_columns(
                (pl.col(parameter).cast(pl.Float64, strict=False) * WIND_ROSE_DEGREES).cast(pl.String).alias(parameter)
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
            return _mez_to_utc(_transform_minute_1_precipitation_historical(df), file, dataset, period)
        missing_parameters = (
            DwdObservationMetadata.minute_1.precipitation.precipitation_amount_droplet.name_original,
            DwdObservationMetadata.minute_1.precipitation.precipitation_amount_rocker.name_original,
        )
        df = df.with_columns(pl.lit(None, pl.String).alias(parameter) for parameter in missing_parameters)
    elif dataset == DwdObservationMetadata.minute_5.precipitation and period != Period.HISTORICAL:
        missing_parameters = [
            DwdObservationMetadata.minute_5.precipitation.precipitation_amount_rocker.name_original,
            DwdObservationMetadata.minute_5.precipitation.precipitation_amount_droplet.name_original,
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
            pl.col("timestamp")
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
    df = df.with_columns(pl.col("timestamp").cast(pl.String).str.pad_end(12, "0"))
    df = df.with_columns(
        pl.col("timestamp").str.to_datetime("%Y%m%d%H%M", time_zone="UTC"),
    )
    if dataset == DwdObservationMetadata.hourly.sun:
        spans = file.woz_spans if isinstance(file, ProductFile) else ()
        df = df.with_columns(
            pl.any_horizontal(
                pl.col("timestamp").dt.date().is_between(first, last, closed="both") for first, last in spans
            )
            .fill_null(value=False)
            .alias(WOZ_COLUMN)
            if spans
            else pl.lit(value=False).alias(WOZ_COLUMN)
        )
    return _mez_to_utc(df, file, dataset, period)


def _mez_to_utc(df: pl.LazyFrame, file: File, dataset: DatasetModel, period: Period) -> pl.LazyFrame:
    """Shift the stamps of a historical 1-, 5- or 10-minute file that are MEZ, the fixed UTC+1, to UTC.

    This is done per file, before the files are put together: the shift is a property of the file, and the
    files of 1999 and 2000 overlap in the hour 23:00 to 23:50 UTC of 1999-12-31, where a shift by the year of the
    stamp, after the files were put together, dropped the stamps of the UTC file as duplicates of the MEZ ones
    (GH-2815).
    """
    if (
        period == Period.HISTORICAL
        and dataset.resolution.value in (Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10)
        and is_mez_file(file.filename)
    ):
        return df.with_columns(pl.col("timestamp") - pl.duration(hours=1))
    return df


def _transform_minute_1_precipitation_historical(df: pl.LazyFrame) -> pl.LazyFrame:
    """Transform the 1 minute precipitation historical data.

    The data is stored in a way that the start and end date of the precipitation event is given.
    This function transforms the data into a format where each minute of the event is represented by a row.
    """
    df = df.with_columns(
        pl.col("timestamp").cast(str).str.to_datetime("%Y%m%d%H%M", time_zone="UTC"),
        pl.col("end_date").cast(str).str.to_datetime("%Y%m%d%H%M", time_zone="UTC"),
    )
    df = df.with_columns(
        pl.datetime_ranges(pl.col("timestamp"), pl.col("end_date"), interval="1m").alias(
            "timestamp",
        ),
    )
    df = df.drop(
        "end_date",
    )
    # Expand dataframe over calculated date ranges -> one datetime per row
    return df.explode("timestamp", empty_as_null=True)
