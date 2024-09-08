# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import polars as pl


def read_fwf_from_df(df: pl.DataFrame, column_specs: tuple[tuple[int, int], ...], header: bool = False) -> pl.DataFrame:
    """Function to split a column of a polars DataFrame into multiple columns by given column specs
    :param df: the polars DataFrame of which a column is split
    :param column_specs: definition of column widths in [start, end]
    :param header: boolean if header should be split as well, will only succeed if column header is long enough
    :return: polars DataFrame with split columns
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
        raise ValueError("reading fwf from a DataFrame only supports one column")
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
