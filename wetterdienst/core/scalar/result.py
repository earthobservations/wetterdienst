# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Union

import pandas as pd

from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Frequency, Resolution

if TYPE_CHECKING:
    from wetterdienst.core.scalar.request import ScalarRequestCore
    from wetterdienst.core.scalar.values import ScalarValuesCore
    from wetterdienst.provider.dwd.forecast import DwdMosmixRequest


class StationsResult:
    def __init__(
        self,
        stations: Union["ScalarRequestCore", "DwdMosmixRequest"],
        df: pd.DataFrame,
        **kwargs
    ) -> None:
        # TODO: add more attributes from ScalarStations class
        self.stations = stations

        self.df = df
        self._kwargs = kwargs

    def __eq__(self, other):
        return (self.stations == other.stations) and self.df.equals(other.df)

    @property
    def provider(self):
        return self.stations._provider

    @property
    def now(self):
        return self.stations._now

    @property
    def station_id(self) -> pd.Series:
        return self.df[Columns.STATION_ID.value]

    @property
    def parameter(self):
        return self.stations.parameter

    @property
    def _resolution_type(self):
        return self.stations._resolution_type

    @property
    def values(self) -> "ScalarValuesCore":
        return self.stations._values.from_stations(self)

    @property
    def resolution(self) -> Resolution:
        return self.stations.resolution

    @property
    def frequency(self) -> Frequency:
        return self.stations.frequency

    @property
    def period(self) -> Period:
        return self.stations.period

    @property
    def start_date(self) -> datetime:
        return self.stations.start_date

    @property
    def end_date(self) -> datetime:
        return self.stations.end_date

    @property
    def start_issue(self) -> datetime:
        return self.stations.start_issue

    @property
    def end_issue(self) -> datetime:
        return self.stations.end_issue

    @property
    def tidy(self) -> bool:
        return self.stations.tidy

    @property
    def humanize(self) -> bool:
        return self.stations.humanize

    def json(self) -> str:
        raise NotImplementedError()


@dataclass
class ValuesResult:
    stations: StationsResult
    df: pd.DataFrame

    def __add__(self, other):
        pass

    def json(self):
        raise NotImplementedError()
