# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core for sources of timeseries where data is related to a station."""

from __future__ import annotations

import datetime as dt
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast
from zoneinfo import ZoneInfo

import polars as pl
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel
from tqdm import tqdm
from tzfpy import get_tz

from wetterdienst.metadata.resolution import DAILY_AT_MOST, Frequency, Resolution
from wetterdienst.model.result import HistoryResult, StationsResult, ValuesResult
from wetterdienst.model.unit import UnitConverter
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Iterator

    from wetterdienst.model.metadata import DatasetModel, ParameterModel

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)


class _StationName(BaseModel):
    """Model for station name history."""

    station_id: str
    station_name: str
    start_date: dt.datetime
    end_date: dt.datetime | None


class _OperatorName(BaseModel):
    """Model for operator name history."""

    station_id: str
    operator_name: str
    start_date: dt.datetime
    end_date: dt.datetime | None


class _NameHistory(BaseModel):
    """Model for name history."""

    station: list[_StationName] = field(default_factory=list)
    operator: list[_OperatorName] = field(default_factory=list)


class _ParameterHistory(BaseModel):
    """Model for parameter history."""

    station_id: str
    start_date: dt.datetime
    end_date: dt.datetime
    station_name: str
    parameter: str
    description: str | None = None
    unit: str | None = None
    data_source: str | None = None
    extra_info: str | None = None
    special: str | None = None
    literature: str | None = None


class _DeviceHistory(BaseModel):
    """Model for device history."""

    device_type: str | None = None
    station_id: str
    name: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    height: float | None = None
    device_height: float | None = None
    start_date: dt.datetime
    end_date: dt.datetime
    method: str | None = None


class _GeographyHistory(BaseModel):
    """Model for geography history."""

    station_id: str
    station_height: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    start_date: dt.datetime
    end_date: dt.datetime | None = None
    name: str | None = None


class _MissingSummary(BaseModel):
    """Model for missing summary."""

    station_id: str
    station_name: str | None = None
    parameter: str
    start_date: dt.datetime
    end_date: dt.datetime
    missing_count: int | None = None
    description: str | None = None


class _MissingPeriod(BaseModel):
    """Model for missing period."""

    station_id: str
    station_name: str | None = None
    parameter: str
    start_date: dt.datetime
    end_date: dt.datetime
    missing_count: int | None = None
    description: str | None = None


class _MissingDataHistory(BaseModel):
    """Model for missing data history."""

    summary: list[_MissingSummary] = field(default_factory=list)
    periods: list[_MissingPeriod] = field(default_factory=list)


class History(BaseModel):
    """Model for history data."""

    name: _NameHistory
    parameter: list[_ParameterHistory] = field(default_factory=list)
    device: list[_DeviceHistory] = field(default_factory=list)
    geography: list[_GeographyHistory] = field(default_factory=list)
    missing_data: _MissingDataHistory = field(default_factory=_MissingDataHistory)


@dataclass
class TimeseriesHistory(ABC):
    """Core for sources of timeseries where data is related to a station."""

    sr: StationsResult

    @classmethod
    def from_stations(cls, stations: StationsResult) -> TimeseriesHistory:
        """Create a new instance of the class from a StationsResult object."""
        return cls(stations)

    def query(self) -> Iterator[HistoryResult]:
        """Query data for all stations and parameters and return a DataFrame for each station."""
        for (station_id,), df_station_meta in self.sr.df.group_by(["station_id"], maintain_order=True):
            station_id = cast("str", station_id)
            available_datasets = self._get_available_datasets(df_station_meta)
            # Collect data for this station
            history = self._collect_station_history(station_id, available_datasets)  # , available_datasets
            yield HistoryResult(stations=self.sr, history=history)

    def _get_available_datasets(self, df: pl.DataFrame) -> list[DatasetModel]:
        """Extract available datasets for the station."""
        resolution_dataset_pairs = (
            df.select(["resolution", "dataset"]).unique().sort(["resolution", "dataset"]).rows(named=True)
        )
        return [self.sr.stations.metadata[pair["resolution"]][pair["dataset"]] for pair in resolution_dataset_pairs]

    @abstractmethod
    def _collect_station_history(self, station_id: str, available_datasets: list[DatasetModel]) -> History:
        """Collect history for a specific station."""
