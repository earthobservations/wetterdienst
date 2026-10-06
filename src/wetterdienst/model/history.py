# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core for sources of timeseries where data is related to a station."""

from __future__ import annotations

import datetime as dt  # noqa: TC003
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field

from wetterdienst.model.result import HistoryResult, StationsResult

if TYPE_CHECKING:
    from collections.abc import Iterator

    import polars as pl

    from wetterdienst.model.metadata import DatasetModel

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
    valid_from: dt.datetime
    valid_to: dt.datetime | None


class _OperatorName(BaseModel):
    """Model for operator name history."""

    station_id: str
    operator_name: str
    valid_from: dt.datetime
    valid_to: dt.datetime | None


class _NameHistory(BaseModel):
    """Model for name history."""

    # Use pydantic-compatible defaults instead of dataclasses.field
    station: list[_StationName] = Field(default_factory=list)
    operator: list[_OperatorName] = Field(default_factory=list)


class _ParameterHistory(BaseModel):
    """Model for parameter history."""

    station_id: str
    valid_from: dt.datetime
    valid_to: dt.datetime
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
    station_name: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    station_elevation: float | None = None
    device_height: float | None = None
    valid_from: dt.datetime
    valid_to: dt.datetime
    method: str | None = None


class _GeographyHistory(BaseModel):
    """Model for geography history."""

    station_id: str
    station_elevation: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    valid_from: dt.datetime
    valid_to: dt.datetime | None = None
    station_name: str | None = None


class _MissingSummary(BaseModel):
    """Model for missing summary."""

    station_id: str
    station_name: str | None = None
    parameter: str
    valid_from: dt.datetime
    valid_to: dt.datetime
    missing_count: int | None = None
    description: str | None = None


class _MissingPeriod(BaseModel):
    """Model for missing period."""

    station_id: str
    station_name: str | None = None
    parameter: str
    valid_from: dt.datetime
    valid_to: dt.datetime
    missing_count: int | None = None
    description: str | None = None


class _MissingDataHistory(BaseModel):
    """Model for missing data history."""

    summary: list[_MissingSummary] = Field(default_factory=list)
    periods: list[_MissingPeriod] = Field(default_factory=list)


class History(BaseModel):
    """Model for history data.

    A collector yields up to one history per station and dataset when the provider publishes its
    station metadata per dataset, as DWD observation does, so `resolution` and `dataset` say which
    one an entry belongs to. A provider whose history covers the station as a whole would give them
    as None.
    """

    # the station the history belongs to, spelt as in the stations frame, so a history whose
    # sections hold no records still names its station
    station_id: str
    # the resolution and dataset the history was read for, spelt as in the stations and values frames
    resolution: str | None
    dataset: str | None
    name: _NameHistory
    parameter: list[_ParameterHistory] = Field(default_factory=list)
    device: list[_DeviceHistory] = Field(default_factory=list)
    geography: list[_GeographyHistory] = Field(default_factory=list)
    missing_data: _MissingDataHistory = Field(default_factory=_MissingDataHistory)


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
            for history in self._collect_station_history(station_id, available_datasets):  # , available_datasets
                yield HistoryResult(stations=self.sr, history=history)

    def _get_available_datasets(self, df: pl.DataFrame) -> list[DatasetModel]:
        """Extract available datasets for the station."""
        resolution_dataset_pairs = (
            df.select(["resolution", "dataset"]).unique().sort(["resolution", "dataset"]).rows(named=True)
        )
        return [self.sr.stations.metadata[pair["resolution"]][pair["dataset"]] for pair in resolution_dataset_pairs]

    @abstractmethod
    def _collect_station_history(self, station_id: str, available_datasets: list[DatasetModel]) -> Iterator[History]:
        """Collect history for a specific station."""
