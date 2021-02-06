# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from dataclasses import dataclass
import pandas as pd

from wetterdienst.core.scalar.stations import ScalarStationsCore
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.metadata.columns import Columns


class StationsResult:
    # TODO: add more information about filter and how it is applied, eventually hold
    #  back filter until later and use pandas.DataFrame.sql instead
    _filter = []

    def __init__(
        self,
        stations: ScalarStationsCore,
        df: pd.DataFrame,
        **kwargs
    ) -> None:
        # TODO: add more attributes from ScalarStations class
        self.stations = stations

        self.df = df
        self._kwargs = kwargs

    @property
    def source(self):
        return self.stations._source

    @property
    def now(self):
        return self.stations._now

    @property
    def station_id(self) -> pd.Series:
        return self.df[Columns.STATION_ID.value]

    @property
    def values(self) -> ScalarValuesCore:
        return self.stations._values.from_stations(self)

    def json(self):
        raise NotImplementedError()


@dataclass
class ValuesResult:
    stations: StationsResult
    values: pd.DataFrame

    def __add__(self, other):
        pass

    def json(self):
        raise NotImplementedError()
