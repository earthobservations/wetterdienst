# -*- coding: utf-8 -*-
from dataclasses import dataclass

import pandas as pd


@dataclass
class Result:
    metadata: pd.DataFrame
    data: pd.DataFrame
