# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parser for SMHI's multi-block CSV file format."""

from __future__ import annotations

import io

import polars as pl

_EMPTY_PARSED_SCHEMA = {"date": pl.Datetime(time_unit="us", time_zone="UTC"), "value": pl.String}


def parse_smhi_csv(text: str) -> pl.DataFrame:
    """Parse an SMHI observation CSV into a two-column (date, value) DataFrame.

    SMHI's CSV files stack several metadata blocks (station info, parameter info,
    historical station-position info) before the actual data table, and reuse the data
    table's trailing columns for unrelated footnote text (period/quality-code legend)
    that only appears on some rows. The date columns also differ by resolution: hourly
    and minute data have separate "Datum"/"Tid (UTC)" columns, while daily/monthly data
    instead has a single "Representativt dygn"/"Representativ månad" column. Minute data
    can also have entirely blank rows (a missing reading) -- those are dropped here,
    since the row's date can't be determined either.

    This locates the actual data header row (identified by its "Kvalitet" column,
    present in every resolution) and extracts just the date and value columns, ignoring
    everything else, returning "date" already parsed to a UTC datetime.
    """
    lines = text.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if "Kvalitet" in line), None)
    if header_idx is None:
        return pl.DataFrame(schema=_EMPTY_PARSED_SCHEMA)

    header = lines[header_idx].split(";")
    quality_idx = header.index("Kvalitet")
    value_column = header[quality_idx - 1]

    # SMHI's data block reuses its trailing columns for unrelated footnote text and can have
    # empty/duplicate trailing column names, so a `columns=`-restricted read is not robust
    # here -- read the block in full and select the (date, value) columns afterwards.
    df = pl.read_csv(
        io.StringIO("\n".join(lines[header_idx:])),
        separator=";",
        infer_schema_length=0,
        truncate_ragged_lines=True,
    )

    if "Tid (UTC)" in header:
        date_expr = pl.concat_str([pl.col("Datum"), pl.col("Tid (UTC)")], separator=" ").str.to_datetime(
            "%Y-%m-%d %H:%M:%S",
            strict=False,
        )
    elif "Representativt dygn" in header:
        date_expr = pl.col("Representativt dygn").str.to_datetime("%Y-%m-%d", strict=False)
    elif "Representativ månad" in header:
        date_expr = (pl.col("Representativ månad") + "-01").str.to_datetime("%Y-%m-%d", strict=False)
    else:
        return pl.DataFrame(schema=_EMPTY_PARSED_SCHEMA)

    return (
        df.select(date_expr.alias("date"), pl.col(value_column).alias("value"))
        .filter(pl.col("date").is_not_null())
        .with_columns(pl.col("date").dt.replace_time_zone("UTC"))
    )
