# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import polars as pl


def frame_summary(frame: pl.DataFrame):
    return f"{len(frame)} records and columns={list(frame.columns)}"
