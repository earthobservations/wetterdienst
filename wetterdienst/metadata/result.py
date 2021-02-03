# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from dataclasses import dataclass

import pandas as pd


@dataclass
class Result:
    metadata: pd.DataFrame
    data: pd.DataFrame
