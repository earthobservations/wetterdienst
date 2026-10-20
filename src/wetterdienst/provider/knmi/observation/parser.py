# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parser for KNMI's per-timestamp, all-stations NetCDF files.

Read directly with h5netcdf rather than xarray: the files are plain NetCDF4/HDF5 with
unpacked float variables (no scale_factor/add_offset, _FillValue is NaN) and vlen-string
station keys, so all we need is a couple of indexed reads -- xarray's labeled-array
machinery would be dead weight here.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
from wetterdienst.util.extras import import_optional

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Sequence

_ROW_SCHEMA = {
    "timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
}
_EMPTY_SCHEMA = _ROW_SCHEMA | {"quality_flags": pl.String}

# the _FillValue of a missing observation
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
# 344 from 2015 to 2024. The 10-minute `n` (lowercase) is a different variable that the text export does not carry, but
# the files do: 128 of the 11,293 readings of the 336 files of 05:00 to 08:50 UTC from 2026-10-05 to 2026-10-18 are a
# 9, at a mean horizontal visibility `vv` of 130 m (median) to 998 m (maximum), the fog of the code (GH-3135)
_CLOUD_COVER_CODE_PARAMETERS = ("N", "NG", "n")
_SKY_INVISIBLE = "9"

# the hourly wind direction DD is a bearing "360=north, 90=east, 180=south, 270=west, 0=calm, 990=variable" (KNMI's
# description of the variable): the two codes are no direction. The 10-minute `dd` (lowercase) is a different variable,
# in which a file read showed no code (GH-2850)
_WIND_DIRECTION_CODE_PARAMETERS = ("DD",)
_CALM = "0"
_VARIABLE = "990"


def decode_str(value: object) -> str:
    """Decode an HDF5 string cell to str (h5netcdf returns vlen strings as bytes)."""
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


def public_station_id(wsi: object) -> str:
    """Turn KNMI's full WSI station key into the friendlier trailing WMO station number.

    In the NetCDF files stations are keyed by their WSI (WIGOS Station Identifier), e.g.
    ``0-20000-0-06260`` for De Bilt. Only the last segment (``06260``, the WMO station
    number) varies between stations and it is unique across the whole network, so that is
    what's exposed as ``station_id`` -- much friendlier than the full WSI while staying an
    exact, stable identifier (unlike stripping the WMO block prefix, which would break the
    Caribbean Netherlands stations in block 78).
    """
    return decode_str(wsi).rsplit("-", 1)[-1]


def parse_knmi_netcdf(payload: bytes, station_id: str, parameters: Sequence[str], moment: dt.datetime) -> pl.DataFrame:
    """Extract one station's values for the given parameters from a KNMI NetCDF file.

    Each file covers a single timestamp for every station at once (the whole point of
    downloading it), so this returns at most one row per parameter. The file's own
    internal "time" coordinate is not read: `moment`, the `timestamp` the caller attaches, is
    computed from the file's name (``api._stamp``, which says what the real files hold). The
    coordinate is the end of the interval in all three datasets (10 minutes: the file's name; hourly:
    the name plus one hour; daily: the next 00:00, which is why the date is attached).
    """
    h5netcdf = import_optional("h5netcdf", "Reading KNMI NetCDF", extra="knmi")

    with h5netcdf.File(io.BytesIO(payload), "r") as file:
        variables = file.variables
        # the file is keyed by full WSI; map the public station_id (trailing WMO number)
        # back to that station's row index.
        row_by_public = {public_station_id(wsi): row for row, wsi in enumerate(variables["station"][:])}
        row = row_by_public.get(station_id)
        if row is None:
            return pl.DataFrame(schema=_EMPTY_SCHEMA)
        rows = []
        for parameter in parameters:
            if parameter not in variables:
                continue
            # data variables are (station, time) with a single time step per file
            cell = variables[parameter][row]
            value = float(cell[0]) if getattr(cell, "shape", ()) else float(cell)
            rows.append({"timestamp": moment, "parameter": parameter, "value": value})
    # KNMI's _FillValue for a missing observation is NaN; emit null (not NaN) so the framework's drop_nulls
    # handling treats it as missing and to_json stays valid. The -1 of a trace of precipitation is 0.0, and the 0 (calm)
    # and 990 (variable) of the hourly wind direction are no bearing, so null (GH-2850), as is the 9 of the cloud cover
    # (GH-3123). All keep what the file held as the `raw` token of `quality_flags` (GH-2759)
    value, raw = null_sentinels(
        pl.col("value"),
        Sentinel(_FILL_VALUE),
        Sentinel(_TRACE, where=pl.col("parameter").is_in(_TRACE_PRECIPITATION_PARAMETERS), to=0.0),
        Sentinel(_CALM, _VARIABLE, where=pl.col("parameter").is_in(_WIND_DIRECTION_CODE_PARAMETERS)),
        Sentinel(_SKY_INVISIBLE, where=pl.col("parameter").is_in(_CLOUD_COVER_CODE_PARAMETERS)),
        text=False,
    )
    return pl.DataFrame(rows, schema=_ROW_SCHEMA, orient="row").select(
        "timestamp", "parameter", value.alias("value"), join_quality_flags(None, raw=raw)
    )
