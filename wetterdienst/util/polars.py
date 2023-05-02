# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import Generator

import polars as pl


def chunker(seq: pl.DataFrame, chunksize: int) -> Generator[pl.DataFrame, None, None]:
    """
    Chunks generator function for iterating pandas Dataframes and Series.

    https://stackoverflow.com/a/61798585
    :return:
    """
    for pos in range(0, len(seq), chunksize):
        yield seq[pos : pos + chunksize]
