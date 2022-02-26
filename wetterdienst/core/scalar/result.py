# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Union

import pandas as pd

from wetterdienst.core.process import filter_by_date_and_resolution
from wetterdienst.core.scalar.export import ExportMixin
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Frequency, Resolution

if TYPE_CHECKING:
    from wetterdienst.core.scalar.request import ScalarRequestCore
    from wetterdienst.core.scalar.values import ScalarValuesCore
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest


class StationsResult(ExportMixin):
    def __init__(self, stations: Union["ScalarRequestCore", "DwdMosmixRequest"], df: pd.DataFrame, **kwargs) -> None:
        # TODO: add more attributes from ScalarStations class
        self.stations = stations
        self.df = df
        self._kwargs = kwargs

    def __eq__(self, other):
        return (self.stations == other.stations) and self.df.equals(other.df)

    @property
    def provider(self):
        return self.stations.provider

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

    def to_ogc_feature_collection(self) -> dict:
        """
        Format station information as OGC feature collection.
        Will be used by ``.to_geojson()``.

        Return:
             Dictionary in GeoJSON FeatureCollection format.
        """

        features = []
        for _, station in self.df.iterrows():
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": station["station_id"],
                        "name": station["name"],
                        "state": station["state"]
                        if pd.notna(station["state"]) and station["state"] is not None
                        else None,
                        "from_date": station["from_date"].isoformat()
                        if pd.notna(station["from_date"]) and station["from_date"] is not None
                        else None,
                        "to_date": station["to_date"].isoformat()
                        if pd.notna(station["to_date"]) and station["to_date"] is not None
                        else None,
                    },
                    "geometry": {
                        # WGS84 is implied and coordinates represent decimal degrees
                        # ordered as "longitude, latitude [,elevation]" with z expressed
                        # as metres above mean sea level per WGS84.
                        # -- http://wiki.geojson.org/RFC-001
                        "type": "Point",
                        "coordinates": [
                            station["longitude"],
                            station["latitude"],
                            station["height"],
                        ],
                    },
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
        }


@dataclass
class ValuesResult(ExportMixin):

    stations: StationsResult
    df: pd.DataFrame

    def to_ogc_feature_collection(self):
        raise NotImplementedError()

    def filter_by_date(self, date: str) -> pd.DataFrame:
        self.df = filter_by_date_and_resolution(self.df, date=date, resolution=self.stations.resolution)
        return self.df
