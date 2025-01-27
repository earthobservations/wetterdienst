# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import polars as pl
from typing_extensions import NotRequired, TypedDict

from wetterdienst.core.process import filter_by_date
from wetterdienst.core.timeseries.export import ExportMixin
from wetterdienst.metadata.columns import Columns

if TYPE_CHECKING:
    from datetime import datetime

    import plotly.graph_objects as go

    from wetterdienst.core.timeseries.request import TimeseriesRequest
    from wetterdienst.core.timeseries.values import TimeseriesValues
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest


class StationsFilter:
    ALL = "all"
    BY_STATION_ID = "by_station_id"
    BY_NAME = "by_name"
    BY_RANK = "by_rank"
    BY_DISTANCE = "by_distance"
    BY_BBOX = "by_bbox"
    BY_SQL = "by_sql"


# return types of StationsResult output formats
class _Provider(TypedDict):
    name_local: str
    name_english: str
    country: str
    copyright: str
    url: str


class _Producer(TypedDict):
    name: str
    version: str
    repository: str
    documentation: str
    doi: str


class _Metadata(TypedDict):
    provider: _Provider
    producer: _Producer


class _Station(TypedDict):
    station_id: str
    start_date: str | None
    end_date: str | None
    latitude: float
    longitude: float
    height: float
    name: str
    state: str


class _StationsDict(TypedDict):
    metadata: NotRequired[_Metadata]
    stations: list[_Station]


class _OgcFeatureProperties(TypedDict):
    id: str
    name: str
    state: str
    start_date: str | None
    end_date: str | None


class _OgcFeatureGeometry(TypedDict):
    type: Literal["Point"]
    coordinates: list[float]


class _StationsOgcFeature(TypedDict):
    type: Literal["Feature"]
    properties: _OgcFeatureProperties
    geometry: _OgcFeatureGeometry


class _StationsOgcFeatureCollectionData(TypedDict):
    type: Literal["FeatureCollection"]
    features: list[_StationsOgcFeature]


class _StationsOgcFeatureCollection(TypedDict):
    metadata: NotRequired[_Metadata]
    data: _StationsOgcFeatureCollectionData


class StationsResult(ExportMixin):
    def __init__(
        self,
        stations: TimeseriesRequest | DwdMosmixRequest | DwdDmoRequest,
        df: pl.DataFrame,
        df_all: pl.DataFrame,
        stations_filter: StationsFilter,
        rank: int | None = None,
        **kwargs,
    ) -> None:
        # TODO: add more attributes from ScalarStations class
        self.stations = stations
        self.df = df
        self.df_all = df_all
        self.stations_filter = stations_filter
        self.rank = rank
        self._kwargs = kwargs

    def __eq__(self, other):
        return (self.stations == other.stations) and self.df.equals(other.df)

    @property
    def settings(self):
        return self.stations.settings

    @property
    def station_id(self) -> pl.Series:
        return self.df.get_column(Columns.STATION_ID.value)

    @property
    def parameters(self):
        return self.stations.parameters

    @property
    def values(self) -> TimeseriesValues:
        return self.stations._values.from_stations(self)

    @property
    def start_date(self) -> datetime:
        return self.stations.start_date

    @property
    def end_date(self) -> datetime:
        return self.stations.end_date

    @property
    def tidy(self) -> bool:
        return self.stations.tidy

    @property
    def humanize(self) -> bool:
        return self.stations.humanize

    @property
    def convert_units(self) -> bool:
        return self.stations.convert_units

    @property
    def skip_empty(self) -> bool:
        return self.stations.skip_empty

    @property
    def skip_threshold(self) -> float:
        return self.stations.skip_threshold

    @property
    def complete(self) -> bool:
        return self.stations.complete

    @property
    def drop_nulls(self) -> float:
        return self.stations.drop_nulls

    def get_metadata(self) -> _Metadata:
        """
        Get metadata for stations result.
        :return: Dictionary with metadata.
        """
        from wetterdienst import Info

        info = Info()
        name_local = self.stations.metadata.name_local
        name_english = self.stations.metadata.name_english
        country = self.stations.metadata.country
        copyright_ = self.stations.metadata.copyright
        url = self.stations.metadata.url
        return {
            "provider": {
                "name_local": name_local,
                "name_english": name_english,
                "country": country,
                "copyright": copyright_,
                "url": url,
            },
            "producer": {
                "name": info.name,
                "version": info.version,
                "repository": info.repository,
                "documentation": info.documentation,
                "doi": "10.5281/zenodo.3960624",
            },
        }

    def to_dict(self, with_metadata: bool = False) -> _StationsDict:
        """
        Format station information as dictionary.
        :param with_metadata: bool whether to include metadata
        :return: Dictionary with station information.
        """
        data = {}
        if with_metadata:
            data["metadata"] = self.get_metadata()

        df = self.df
        if not df.is_empty():
            df = df.with_columns(
                [
                    pl.col("start_date").map_elements(
                        lambda date: date.isoformat() if date else None,
                        return_dtype=pl.String,
                    ),
                    pl.col("end_date").map_elements(
                        lambda date: date.isoformat() if date else None,
                        return_dtype=pl.String,
                    ),
                ],
            )
        data["stations"] = df.to_dicts()
        return data

    def to_json(self, with_metadata: bool = False, indent: int | bool | None = 4) -> str:
        """
        Format station information as JSON.
        :param with_metadata: bool whether to include metadata
        :param indent: int or bool whether to indent JSON, defaults to 4, if True indent is 4
        :return: JSON string with station information.
        """
        if indent is True:
            indent = 4
        elif indent is False:
            indent = None
        return json.dumps(self.to_dict(with_metadata=with_metadata), indent=indent)

    def to_ogc_feature_collection(self, with_metadata: bool = False) -> _StationsOgcFeatureCollection:
        """
        Format station information as OGC feature collection.
        Will be used by ``.to_geojson()``.

        :param with_metadata: bool whether to include metadata
        :return: Dictionary in GeoJSON FeatureCollection format.
        """
        data = {}
        if with_metadata:
            data["metadata"] = self.get_metadata()
        features = []
        for station in self.df.iter_rows(named=True):
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": station["station_id"],
                        "name": station["name"],
                        "state": station["state"],
                        "start_date": station["start_date"].isoformat() if station["start_date"] else None,
                        "end_date": station["end_date"].isoformat() if station["end_date"] else None,
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
                },
            )
        data["data"] = {
            "type": "FeatureCollection",
            "features": features,
        }
        return data

    def to_plot(self, **_kwargs) -> go.Figure:
        """Create a plotly figure from the stations DataFrame."""
        import plotly.graph_objects as go

        if self.df.is_empty():
            return go.Figure()

        # Calculate bounding box
        min_lon = self.df["longitude"].min()
        max_lon = self.df["longitude"].max()
        min_lat = self.df["latitude"].min()
        max_lat = self.df["latitude"].max()

        # Calculate center of the bounding box
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2

        # Calculate zoom level
        lat_diff = max_lat - min_lat
        zoom = 12 - lat_diff

        fig = go.Figure()
        fig.add_trace(
            go.Scattermap(
                lon=self.df.get_column("longitude"),
                lat=self.df.get_column("latitude"),
                text=self.df.select(pl.concat_str(pl.col("name"), pl.lit(" ("), pl.col("station_id"), pl.lit(")"))),
                mode="markers",
                marker=dict(
                    size=10,
                    color="rgb(255, 0, 0)",
                ),
            )
        )
        fig.update_layout(
            showlegend=False,
            map=dict(
                center=dict(
                    lat=center_lat,
                    lon=center_lon,
                ),
                zoom=zoom,
            ),
            margin=dict(l=0, r=0, t=0, b=0),
        )
        return fig

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        **kwargs,
    ) -> bytes | str:
        """Create an image from the plotly figure"""
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            raise KeyError(f"Invalid format: {fmt}")
        return img


class _ValuesItemDict(TypedDict):
    station_id: str
    dataset: str
    parameter: str
    date: str
    value: str
    quality: str


class _ValuesDict(TypedDict):
    metadata: NotRequired[_Metadata]
    stations: NotRequired[list[_Station]]
    values: list[_ValuesItemDict]


@dataclass
class _ValuesResult(ExportMixin):
    stations: StationsResult
    df: pl.DataFrame

    @staticmethod
    def _to_dict(df: pl.DataFrame) -> list[_ValuesItemDict]:
        """
        Format values as dictionary. This method is used both by ``to_dict()`` and ``to_ogc_feature_collection()``,
        however the latter one splits the DataFrame into multiple DataFrames by station and calls this method
        for each of them.
        :param df: DataFrame with values
        :return: Dictionary with values.
        """
        if not df.is_empty():
            df = df.with_columns(
                pl.col("date").map_elements(lambda date: date.isoformat(), return_dtype=pl.String),
            )
        return df.to_dicts()

    def to_dict(self, with_metadata: bool = False, with_stations: bool = False) -> _ValuesDict:
        """
        Format values as dictionary.
        :param with_metadata: bool whether to include metadata
        :param with_stations: bool whether to include station information
        :return: Dictionary with values.
        """
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        if with_stations:
            data["stations"] = self.stations.to_dict(with_metadata=False)["stations"]
        data["values"] = self._to_dict(self.df)
        return data

    def to_json(
        self,
        with_metadata: bool = False,
        with_stations: bool = False,
        indent: int | bool | None = 4,
    ) -> str:
        """
        Format values as JSON.
        :param with_metadata: bool whether to include metadata
        :param with_stations: bool whether to include station information
        :param indent: int or bool whether to indent JSON, defaults to 4, if True indent is 4
        :return: JSON string with values.
        """
        if indent is True:
            indent = 4
        elif indent is False:
            indent = None
        return json.dumps(self.to_dict(with_metadata=with_metadata, with_stations=with_stations), indent=indent)

    def filter_by_date(self, date: str) -> pl.DataFrame:
        self.df = filter_by_date(self.df, date=date)
        return self.df


class _ValuesOgcFeature(TypedDict):
    type: Literal["Feature"]
    properties: _OgcFeatureProperties
    geometry: _OgcFeatureGeometry
    values: list[_ValuesItemDict]


class _ValuesOgcFeatureCollectionData(TypedDict):
    type: Literal["FeatureCollection"]
    features: list[_ValuesOgcFeature]


class _ValuesOgcFeatureCollection(TypedDict):
    metadata: NotRequired[_Metadata]
    data: _ValuesOgcFeatureCollectionData


@dataclass
class ValuesResult(_ValuesResult):
    stations: StationsResult
    values: TimeseriesValues
    df: pl.DataFrame

    @property
    def df_stations(self):
        return self.stations.df.filter(pl.col("station_id").is_in(self.values.stations_collected))

    def to_ogc_feature_collection(self, with_metadata: bool = False) -> _ValuesOgcFeatureCollection:
        """
        Format values as OGC feature collection.
        :param with_metadata: bool whether to include metadata
        :return: Dictionary in GeoJSON FeatureCollection format.
        """
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        df_stations = self.stations.df.join(self.df.select("station_id").unique(), on="station_id")
        features = []
        for station in df_stations.iter_rows(named=True):
            df_values = self.df.filter(pl.col("station_id") == station["station_id"]).select(
                pl.all().exclude("station_id"),
            )
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": station["station_id"],
                        "name": station["name"],
                        "state": station["state"],
                        "start_date": station["start_date"].isoformat() if station["start_date"] else None,
                        "end_date": station["end_date"].isoformat() if station["end_date"] else None,
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
                    "values": self._to_dict(df_values),
                },
            )
        data["data"] = {
            "type": "FeatureCollection",
            "features": features,
        }
        return data

    def to_plot(self, **_kwargs) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        # create unit mapping for title
        units = {
            parameter.name: self.values.unit_converter.targets[parameter.unit_type].symbol
            for parameter in self.values.sr.parameters
        }
        # used for subplots
        n = self.df.select(["dataset", "parameter"]).n_unique()
        # used for name
        n_datasets = self.df["dataset"].n_unique()
        fig = make_subplots(rows=n, shared_xaxes=True, vertical_spacing=0.01)
        titles = []
        for i, (
            (
                dataset,
                parameter,
            ),
            df_group,
        ) in enumerate(self.df.group_by(["dataset", "parameter"], maintain_order=True)):
            dataset_prefix = f"{dataset}/<br>" if n_datasets > 1 else ""
            titles.append(f"{dataset_prefix}{parameter} ({units[parameter]})")
            fig.add_trace(
                go.Scatter(
                    x=df_group["date"],
                    y=df_group["value"],
                    mode="markers",
                    marker=go.scatter.Marker(colorscale="Viridis"),
                ),
                row=i + 1,
                col=1,
            )
        # update subplot titles
        for i, title in enumerate(titles):
            fig.update_yaxes(title_text=title, row=i + 1, col=1)
        # remove legend
        fig.update_layout(showlegend=False)
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=300 * n,  # important to scale height with number of subplots
        )
        return fig

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        **kwargs,
    ) -> bytes | str:
        """Create an image from the plotly figure"""
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            raise KeyError(f"Invalid format: {fmt}")
        return img


class _InterpolatedOrSummarizedOgcFeatureProperties(TypedDict):
    id: str
    name: str


class _InterpolatedValuesItemDict(TypedDict):
    station_id: str
    parameter: str
    date: str
    value: float
    distance_mean: float
    taken_station_ids: list[str]


class _InterpolatedValuesDict(TypedDict):
    metadata: NotRequired[_Metadata]
    stations: NotRequired[list[_Station]]
    values: list[_InterpolatedValuesItemDict]


class _InterpolatedValuesOgcFeature(TypedDict):
    type: Literal["Feature"]
    properties: _InterpolatedOrSummarizedOgcFeatureProperties
    geometry: _OgcFeatureGeometry
    stations: list[_Station]
    values: list[_InterpolatedValuesItemDict]


class _InterpolatedValuesOgcFeatureCollectionData(TypedDict):
    type: Literal["FeatureCollection"]
    features: list[_InterpolatedValuesOgcFeature]


class _InterpolatedValuesOgcFeatureCollection(TypedDict):
    metadata: NotRequired[_Metadata]
    data: _InterpolatedValuesOgcFeatureCollectionData


@dataclass
class InterpolatedValuesResult(_ValuesResult):
    stations: StationsResult
    df: pl.DataFrame
    latlon: tuple[float, float] | None

    if typing.TYPE_CHECKING:
        # We need to override the signature of the method to_dict() from ValuesResult here
        # because we want to return a slightly different type with columns related to interpolation.
        # Those are distance_mean and station_ids.
        # https://github.com/python/typing/discussions/1015
        def _to_dict(self, df: pl.DataFrame) -> list[_InterpolatedValuesItemDict]: ...

        def to_dict(self, with_metadata: bool = False, with_stations: bool = False) -> _InterpolatedValuesDict: ...

    def to_ogc_feature_collection(self, with_metadata: bool = False) -> _InterpolatedValuesOgcFeatureCollection:
        """
        Format interpolated values as OGC feature collection.
        :param with_metadata: bool whether to include metadata
        :return: Dictionary in GeoJSON FeatureCollection format
        """
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        latitude, longitude = self.latlon
        name = f"interpolation({latitude:.4f},{longitude:.4f})"
        feature = {
            "type": "Feature",
            "properties": {
                "id": self.df.get_column(Columns.STATION_ID.value).gather(0).item(),
                "name": name,
            },
            "geometry": {
                # WGS84 is implied and coordinates represent decimal degrees
                # ordered as "longitude, latitude [,elevation]" with z expressed
                # as metres above mean sea level per WGS84.
                # -- http://wiki.geojson.org/RFC-001
                "type": "Point",
                "coordinates": [
                    longitude,
                    latitude,
                ],
            },
            "stations": self.stations.to_dict(with_metadata=False)["stations"],
            "values": self.to_dict(with_metadata=False, with_stations=False)["values"],
        }
        data["data"] = {
            "type": "FeatureCollection",
            "features": [feature],
        }
        return data

    def to_plot(self, **_kwargs) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        # create unit mapping for title
        units = {
            parameter.name: self.stations.values.unit_converter.targets[parameter.unit_type].symbol
            for parameter in self.stations.parameters
        }
        # used for subplots
        n = self.df.select(["dataset", "parameter"]).n_unique()
        # used for name
        n_datasets = self.df["dataset"].n_unique()
        fig = make_subplots(rows=n, shared_xaxes=True, vertical_spacing=0.01)
        titles = []
        for i, (
            (
                dataset,
                parameter,
            ),
            df_group,
        ) in enumerate(self.df.group_by(["dataset", "parameter"], maintain_order=True)):
            dataset_prefix = f"{dataset}/<br>" if n_datasets > 1 else ""
            titles.append(f"{dataset_prefix}{parameter} ({units[parameter]})")
            fig.add_trace(
                go.Scatter(
                    x=df_group["date"],
                    y=df_group["value"],
                    mode="markers",
                    marker=go.scatter.Marker(colorscale="Viridis"),
                ),
                row=i + 1,
                col=1,
            )
        # update subplot titles
        for i, title in enumerate(titles):
            fig.update_yaxes(title_text=title, row=i + 1, col=1)
        # remove legend
        fig.update_layout(showlegend=False)
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=300 * n,  # important to scale height with number of subplots
        )
        return fig

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        **kwargs,
    ) -> bytes | str:
        """Create an image from the plotly figure"""
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            raise KeyError(f"Invalid format: {fmt}")
        return img


class _SummarizedValuesItemDict(TypedDict):
    station_id: str
    parameter: str
    date: str
    value: float
    distance: float
    taken_station_id: str


class _SummarizedValuesDict(TypedDict):
    metadata: NotRequired[_Metadata]
    stations: NotRequired[list[_Station]]
    values: list[_SummarizedValuesItemDict]


class _SummarizedValuesOgcFeature(TypedDict):
    type: Literal["Feature"]
    properties: _InterpolatedOrSummarizedOgcFeatureProperties
    geometry: _OgcFeatureGeometry
    stations: list[_Station]
    values: list[_SummarizedValuesItemDict]


class _SummarizedValuesOgcFeatureCollectionData(TypedDict):
    type: Literal["FeatureCollection"]
    features: list[_SummarizedValuesOgcFeature]


class _SummarizedValuesOgcFeatureCollection(TypedDict):
    metadata: NotRequired[_Metadata]
    data: _SummarizedValuesOgcFeatureCollectionData


@dataclass
class SummarizedValuesResult(_ValuesResult):
    stations: StationsResult
    df: pl.DataFrame
    latlon: tuple[float, float]

    if typing.TYPE_CHECKING:
        # We need to override the signature of the method to_dict() from ValuesResult here
        # because we want to return a slightly different type with columns related to interpolation.
        # Those are distance and station_id.
        # https://github.com/python/typing/discussions/1015
        def _to_dict(self, df: pl.DataFrame) -> list[_SummarizedValuesItemDict]: ...

        def to_dict(self, with_metadata: bool = False, with_stations: bool = False) -> _SummarizedValuesDict: ...

    def to_ogc_feature_collection(self, with_metadata: bool = False) -> _SummarizedValuesOgcFeatureCollection:
        """
        Format summarized values as OGC feature collection.
        :param with_metadata: bool whether to include metadata
        :return: Dictionary in GeoJSON FeatureCollection format
        """
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        latitude, longitude = self.latlon
        name = f"summary({latitude:.4f},{longitude:.4f})"
        feature = {
            "type": "Feature",
            "properties": {
                "id": self.df.get_column(Columns.STATION_ID.value).gather(0).item(),
                "name": name,
            },
            "geometry": {
                # WGS84 is implied and coordinates represent decimal degrees
                # ordered as "longitude, latitude [,elevation]" with z expressed
                # as metres above mean sea level per WGS84.
                # -- http://wiki.geojson.org/RFC-001
                "type": "Point",
                "coordinates": [
                    longitude,
                    latitude,
                ],
            },
            "stations": self.stations.to_dict(with_metadata=False)["stations"],
            "values": self.to_dict(with_metadata=False, with_stations=False)["values"],
        }
        data["data"] = {
            "type": "FeatureCollection",
            "features": [feature],
        }
        return data

    def to_plot(self, **_kwargs) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        if self.df.is_empty():
            return go.Figure()

        # create unit mapping for title
        units = {
            parameter.name: self.stations.values.unit_converter.targets[parameter.unit_type].symbol
            for parameter in self.stations.stations.parameters
        }
        # used for subplots
        n = self.df.select(["parameter"]).n_unique()
        # used for name
        n_datasets = self.df["dataset"].n_unique()
        # used for name
        fig = make_subplots(rows=n, shared_xaxes=True, vertical_spacing=0.01)
        titles = []
        for i, (
            (
                dataset,
                parameter,
            ),
            df_group,
        ) in enumerate(self.df.group_by(["dataset", "parameter"], maintain_order=True)):
            dataset_prefix = f"{dataset}/<br>" if n_datasets > 1 else ""
            titles.append(f"{dataset_prefix}{parameter} ({units[parameter]})")
            fig.add_trace(
                go.Scatter(
                    x=df_group["date"],
                    y=df_group["value"],
                    mode="markers",
                    marker=go.scatter.Marker(colorscale="Viridis"),
                ),
                row=i + 1,
                col=1,
            )
        # update subplot titles
        for i, title in enumerate(titles):
            fig.update_yaxes(title_text=title, row=i + 1, col=1)
        # remove legend
        fig.update_layout(showlegend=False)
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=300 * n,  # important to scale height with number of subplots
        )
        return fig

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        **kwargs,
    ) -> bytes | str:
        """Create an image from the plotly figure"""
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            raise KeyError(f"Invalid format: {fmt}")
        return img
