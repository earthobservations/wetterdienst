# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parsing helpers for AEMET OpenData responses."""

from __future__ import annotations

import polars as pl

from wetterdienst.model.quality_flags import Sentinel, null_sentinels


def parse_dms_coordinate(column: str) -> pl.Expr:
    """Parse an AEMET DMS coordinate string, e.g. "394924N" or "025309E", to decimal degrees."""
    col = pl.col(column)
    degrees = col.str.slice(0, 2).cast(pl.Float64, strict=False)
    minutes = col.str.slice(2, 2).cast(pl.Float64, strict=False)
    seconds = col.str.slice(4, 2).cast(pl.Float64, strict=False)
    hemisphere = col.str.slice(6, 1)
    decimal = degrees + minutes / 60 + seconds / 3600
    return pl.when(hemisphere.is_in(["S", "W"])).then(-decimal).otherwise(decimal)


def parse_decimal_comma(column: str) -> tuple[pl.Expr, pl.Expr]:
    """Parse an AEMET number string using a comma as decimal separator, e.g. "28,0", into a float.

    Returns the value and the ``raw`` text for ``quality_flags`` (GH-2759): a text that is no number is null and
    keeps its text.
    """
    return null_sentinels(pl.col(column).cast(pl.String).str.replace(",", "."), non_numeric=True)


def parse_wind_direction(column: str) -> tuple[pl.Expr, pl.Expr]:
    """Parse an AEMET wind direction code (tens of degrees, 99 = calm/variable) into degrees.

    Returns the value and the ``raw`` text for ``quality_flags``: the ``99`` is null and keeps its text.
    """
    code, raw = null_sentinels(pl.col(column).cast(pl.String).str.replace(",", "."), Sentinel("99"), non_numeric=True)
    return code * 10, raw


def parse_monthly_value(column: str) -> tuple[pl.Expr, pl.Expr]:
    """Parse an AEMET monthly/annual value, e.g. "24.2(20)" or "39.4(27/jul)", into a float.

    Unlike the daily endpoint, monthly/annual values use a plain decimal point, but may
    carry a trailing day-of-occurrence annotation in parentheses that needs stripping.
    Returns the value and the ``raw`` text for ``quality_flags``: a text with no number in front is null and keeps
    its text.
    """
    cell = pl.col(column).cast(pl.String)
    number = cell.str.extract(r"^(-?\d+(?:\.\d+)?)", 1)
    return null_sentinels(pl.coalesce(number, cell), non_numeric=True)
