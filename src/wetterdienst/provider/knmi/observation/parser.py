# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The codes of KNMI's observations, mapped to nulls: the one step every reading of KNMI goes through.

The readings come from KNMI's EDR API (`edr`). Until GH-3928 they came from the NetCDF files of the Open Data API, which
write the same codes in the same variables, and the rows that came out of them are the ones that `knmi_readings` still
makes of the API's (`tests/provider/knmi/observation/files/frozen_*.csv` hold them).
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels

ROW_SCHEMA = {
    "timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
}

# KNMI's missing observation is a NaN (a null of the EDR API, which is turned back into the NaN)
_FILL_VALUE = "NaN"

# KNMI encodes "trace precipitation" (measured but below the 0.05mm resolution) as a
# literal -1 rather than a small positive value or a missing-value flag -- treated as
# effectively zero here rather than surfaced as a physically-nonsensical negative amount.
# The sunshine duration SQ has the same code: "(-1 for <0.05 hour)" in the header of the hourly and the daily export
# (https://www.daggegevens.knmi.nl/klimatologie/uurgegevens, .../daggegevens; the daily one holds 246 of them for the
# stations 260, 240, 344, 235, 270 and 310 since 1960, read 2026-10-18), which was -3600 s once the hour was
# converted, see GH-3123
_TRACE_PRECIPITATION_PARAMETERS = ("RH", "SQ")
_TRACE = "-1"

# the hourly cloud cover N and the daily mean NG are octants, "9=sky invisible" (the same headers: "9=bovenlucht
# onzichtbaar"), which is no cover and was 1.125 once converted: 941 of the 87,696 hours of the stations 260, 240 and
# 344 from 2015 to 2024. The 10-minute `n` (lowercase) is a different variable that the text export does not carry,
# in which 128 of the 11,293 readings of the 336 files of 05:00 to 08:50 UTC from 2026-10-05 to 2026-10-18 are a
# 9, at a mean horizontal visibility `vv` of 130 m (median) to 998 m (maximum), the fog of the code (GH-3135)
_CLOUD_COVER_CODE_PARAMETERS = ("N", "NG", "n")
_SKY_INVISIBLE = "9"

# the hourly wind direction DD is a bearing "360=north, 90=east, 180=south, 270=west, 0=calm, 990=variable" (KNMI's
# description of the variable): the two codes are no direction. The 10-minute `dd` (lowercase) is a different variable,
# in which a read showed no code (GH-2850)
_WIND_DIRECTION_CODE_PARAMETERS = ("DD",)
_CALM = "0"
_VARIABLE = "990"

# the vector mean wind direction DDVEC of the monthly and the annual datasets is the same bearing and has the one code
# of the description: "360=north; 90=east; 180=south; 270=west; 0=calm/variable" (read 2026-11-11 from the monthly
# file of
# 2026-09 and the annual one of 2024, whose 62 to 67 stations hold bearings from 88 to 257 and no 0)
_VECTOR_WIND_DIRECTION_PARAMETERS = ("DDVEC",)


#: The first stamp of a variable that the files did not carry from the start: the 10-minute `tg` (the temperature at
#: 10 cm) is in no file before the one named 2020-07-23 07:40 (the file of 07:30 has none, the next 10 minutes have it;
#: found by bisection on 2026-11-12, `GET` of the 10-minute files of 2020-06-01 to 2026-11-01). The files route returned
#: no row of it before, where the EDR API leaves it out of the answer as it does for a station with no sensor, which
#: `parse_coverage_json` makes a NaN row: `without_rows_before_the_variable` takes those out, so that the rows are the
#: same. (A station without the sensor is a NaN row in both: the variable was in the file.)
_VARIABLE_SINCE = {Resolution.MINUTE_10: {"tg": dt.datetime(2020, 7, 23, 7, 40, tzinfo=dt.UTC)}}


def without_rows_before_the_variable(df: pl.DataFrame, resolution: Resolution) -> pl.DataFrame:
    """Leave out the rows of a variable from before the files carried it (`_VARIABLE_SINCE`)."""
    for name, since in _VARIABLE_SINCE.get(resolution, {}).items():
        df = df.filter((pl.col("parameter") != name) | (pl.col("timestamp") >= since))
    return df


def public_station_id(wsi: object) -> str:
    """Turn KNMI's full WSI station key into the friendlier trailing WMO station number.

    Stations are keyed by their WSI (WIGOS Station Identifier), e.g. ``0-20000-0-06260`` for De Bilt. Only the last
    segment (``06260``, the WMO station number) varies between stations and it is unique across the whole network, so
    that is what's exposed as ``station_id`` -- much friendlier than the full WSI while staying an exact, stable
    identifier (unlike stripping the WMO block prefix, which would break the Caribbean Netherlands stations in block
    78).
    """
    return (wsi.decode() if isinstance(wsi, (bytes, bytearray)) else str(wsi)).rsplit("-", 1)[-1]


def knmi_readings(df: pl.DataFrame, *, trace_codes: bool = True) -> pl.DataFrame:
    """Turn the readings as KNMI wrote them (`timestamp`, `parameter`, `value`) into the frame the provider hands over.

    `value` is what KNMI wrote, a NaN where it has no reading. `trace_codes` is whether the readings come from the
    10-minute, the hourly or the daily dataset, whose `-1` is a trace of precipitation or of sunshine. The monthly
    and the
    annual datasets are sums of them and describe no such code, so a `-1` there is no trace and is left as it is.
    """
    # KNMI's missing observation is NaN; emit null (not NaN) so the framework's drop_nulls
    # handling treats it as missing and to_json stays valid. The -1 of a trace of precipitation is 0.0, and the 0 (calm)
    # and 990 (variable) of the hourly wind direction are no bearing, so null (GH-2850), as is the 9 of the cloud cover
    # (GH-3123). All keep what KNMI wrote as the `raw` token of `quality_flags` (GH-2759)
    value, raw = null_sentinels(
        pl.col("value"),
        Sentinel(_FILL_VALUE),
        *(
            [Sentinel(_TRACE, where=pl.col("parameter").is_in(_TRACE_PRECIPITATION_PARAMETERS), to=0.0)]
            if trace_codes
            else []
        ),
        Sentinel(_CALM, _VARIABLE, where=pl.col("parameter").is_in(_WIND_DIRECTION_CODE_PARAMETERS)),
        Sentinel(_CALM, where=pl.col("parameter").is_in(_VECTOR_WIND_DIRECTION_PARAMETERS)),
        Sentinel(_SKY_INVISIBLE, where=pl.col("parameter").is_in(_CLOUD_COVER_CODE_PARAMETERS)),
        text=False,
    )
    return df.select("timestamp", "parameter", value.alias("value"), join_quality_flags(None, raw=raw))
