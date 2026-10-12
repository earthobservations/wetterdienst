# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Helper functions for polars DataFrames."""

from __future__ import annotations

from typing import Any

import polars as pl


def read_csv_without_header(source: Any, **kwargs: Any) -> pl.DataFrame:  # noqa: ANN401
    """Read a headerless CSV into columns named ``column_1``, ``column_2``, ... by position.

    polars 1 names the columns of a headerless file from ``column_1``; polars 2 from ``column_0``.
    The names are set here so the readers that select by them read the same file on both.

    Args:
        source: The path, bytes or file-like object ``pl.read_csv`` takes.
        **kwargs: Further arguments for ``pl.read_csv``; ``has_header`` is fixed to False.

    Returns:
        The DataFrame with the columns named by their one-based position.

    """
    df = pl.read_csv(source, has_header=False, **kwargs)
    df.columns = [f"column_{position}" for position in range(1, df.width + 1)]
    return df


def read_fwf_from_df(
    df: pl.DataFrame,
    column_specs: tuple[tuple[int, int], ...],
    *,
    header: bool = False,
) -> pl.DataFrame:
    """Split a column of a polars DataFrame into multiple columns by given column specs.

    Args:
        df: The DataFrame to split.
        column_specs: Tuple of tuples with start and end indices of the columns.
        header: If True, the columns will be named according to the header row.

    Returns:
        The DataFrame with the split columns.

    """

    def _get_columns(column: str) -> list[str]:
        cols = []
        for col_start, col_end in column_specs:
            col = column[col_start : (col_end + 1)]
            if not col:
                cols = []
                break
            cols.append(col)
        return cols

    if len(df.columns) > 1:
        msg = "reading fwf from a DataFrame only supports one column"
        raise ValueError(msg)
    old_column = df.columns[0]
    df = df.select(
        [
            pl.col(old_column)
            .str.slice(slice_tuple[0], slice_tuple[1] - slice_tuple[0] + 1)
            .str.strip_chars()
            .alias(f"column_{i}")
            for i, slice_tuple in enumerate(column_specs)
        ],
    )
    df = df.select(pl.all().replace("", None))
    if header:
        columns = _get_columns(old_column)
        if columns:
            df.columns = columns
    return df
