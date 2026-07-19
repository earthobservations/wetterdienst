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
import math
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Sequence

_EMPTY_SCHEMA = {
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
}

# KNMI encodes "trace precipitation" (measured but below the 0.05mm resolution) as a
# literal -1 rather than a small positive value or a missing-value flag -- treated as
# effectively zero here rather than surfaced as a physically-nonsensical negative amount.
_TRACE_PRECIPITATION_PARAMETERS = ("RH",)


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
    internal "time" coordinate is not used for the returned date -- it marks the *end*
    of the aggregation period (e.g. the file for 2020-01-01 carries an internal time of
    2020-01-02), a KNMI labeling convention confirmed against the legacy CSV service,
    which dates the same values to 2020-01-01. `moment` (the date this file was
    requested for) is what gets attached instead.
    """
    import h5netcdf  # noqa: PLC0415

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
            # KNMI's _FillValue for a missing observation is NaN; emit null (not NaN) so the
            # framework's ts_drop_nulls handling treats it as missing and to_json stays valid.
            if math.isnan(value):
                value = None
            elif parameter in _TRACE_PRECIPITATION_PARAMETERS and value == -1:
                value = 0.0
            rows.append({"date": moment, "parameter": parameter, "value": value})
    return pl.DataFrame(rows, schema=_EMPTY_SCHEMA, orient="row")
