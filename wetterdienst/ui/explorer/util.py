# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pandas as pd


def frame_summary(frame: pd.DataFrame):
    return f"{len(frame)} records and columns={list(frame.columns)}"
