# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Result classes for timeseries data."""

from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal

import polars as pl
from typing_extensions import NotRequired, TypedDict

from wetterdienst.io.export import ExportMixin
from wetterdienst.model.util import filter_by_date

if TYPE_CHECKING:
    from datetime import datetime

    import plotly.graph_objects as go

    from wetterdienst import Settings
    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.values import TimeseriesValues
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest


class StationsFilter(Enum):
    """Enumeration for stations filter.

    This should help determine why only a subset of stations was returned.
    """

    ALL = "all"
    BY_STATION_ID = "by_station_id"
    BY_NAME = "by_name"
    BY_RANK = "by_rank"
    BY_DISTANCE = "by_distance"
    BY_BBOX = "by_bbox"
    BY_SQL = "by_sql"


# return types of StationsResult output formats
class _Provider(TypedDict):
    """Type definition for provider metadata."""

    name_local: str
    name_english: str
    country: str
    copyright: str
    url: str


class _Producer(TypedDict):
    """Type definition for producer metadata."""

    name: str
    version: str
    repository: str
    documentation: str
    doi: str


class _Metadata(TypedDict):
    """Type definition for metadata."""

    provider: _Provider
    producer: _Producer


class _Station(TypedDict):
    """Type definition for station."""

    resolution: str
    dataset: str
    station_id: str
    start_date: str | None
    end_date: str | None
    latitude: float
    longitude: float
    height: float
    name: str
    state: str


class _StationsDict(TypedDict):
    """Type definition for dictionary of stations."""

    metadata: NotRequired[_Metadata]
    stations: list[_Station]


class _OgcFeatureProperties(TypedDict):
    """Type definition for OGC feature properties."""

    resolution: str
    dataset: str
    id: str
    name: str
    state: str
    start_date: str | None
    end_date: str | None


class _OgcFeatureGeometry(TypedDict):
    """Type definition for OGC feature geometry."""

    type: Literal["Point"]
    coordinates: list[float]


class _StationsOgcFeature(TypedDict):
    """Type definition for OGC feature of stations."""

    type: Literal["Feature"]
    properties: _OgcFeatureProperties
    geometry: _OgcFeatureGeometry


class _StationsOgcFeatureCollectionData(TypedDict):
    """Type definition for OGC feature collection data of stations."""

    type: Literal["FeatureCollection"]
    features: list[_StationsOgcFeature]


class _StationsOgcFeatureCollection(TypedDict):
    """Type definition for OGC feature collection of stations."""

    metadata: NotRequired[_Metadata]
    data: _StationsOgcFeatureCollectionData


@dataclass
class StationsResult(ExportMixin):
    """Result class for stations."""

    stations: TimeseriesRequest | DwdMosmixRequest | DwdDmoRequest
    df: pl.DataFrame
    df_all: pl.DataFrame
    stations_filter: StationsFilter
    rank: int | None = None

    @property
    def settings(self) -> Settings:
        """Get settings for the request."""
        return self.stations.settings

    @property
    def parameters(self) -> list[ParameterModel]:
        """Get parameters from the request."""
        return self.stations.parameters

    @property
    def values(self) -> TimeseriesValues:
        """Get values from the request."""
        return self.stations._values.from_stations(self)  # noqa: SLF001

    @property
    def start_date(self) -> datetime:
        """Get start date from the request."""
        return self.stations.start_date

    @property
    def end_date(self) -> datetime:
        """Get end date from the request."""
        return self.stations.end_date

    @property
    def station_id(self) -> pl.Series:
        """Get station IDs from the DataFrame."""
        return self.df.get_column("station_id")

    def get_metadata(self) -> _Metadata:
        """Get metadata for the provider and producer."""
        from wetterdienst import Info  # noqa: PLC0415

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

    def to_dict(self, *, with_metadata: bool = False) -> _StationsDict:
        """Format station information as dictionary.

        Args:
            with_metadata: bool whether to include metadata

        Returns:
            Dictionary with station information.

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

    def to_json(self, *, with_metadata: bool = False, indent: int | bool | None = 4) -> str:
        """Format station information as JSON.

        Args:
            with_metadata: bool whether to include metadata
            indent: int or bool whether to indent the JSON

        Returns:
            JSON string with station information.

        """
        if indent is True:
            indent = 4
        elif indent is False:
            indent = None
        return json.dumps(self.to_dict(with_metadata=with_metadata), indent=indent)

    def to_ogc_feature_collection(self, *, with_metadata: bool = False, **_kwargs) -> _StationsOgcFeatureCollection:  # noqa: ANN003
        """Format station information as OGC feature collection.

        Will be used by ``.to_geojson()``.

        Args:
            with_metadata: bool whether to include metadata (information about the provider and producer)

        Returns:
            Dictionary with station information as OGC feature collection.

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
                        "resolution": station["resolution"],
                        "dataset": station["dataset"],
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

    def to_plot(self, **_kwargs: dict) -> go.Figure:
        """Create a plotly figure from the stations DataFrame."""
        try:
            import plotly.express as px  # noqa: PLC0415
            import plotly.graph_objects as go  # noqa: PLC0415
        except ImportError as e:
            msg = (
                "To use this method, please install the optional dependencies for plotly: "
                "pip install wetterdienst[plotting]"
            )
            raise ImportError(msg) from e

        df = self.df
        if df.is_empty():
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
        # for coloring of resolutions/datasets
        n_resolutions = df["resolution"].n_unique()
        n_datasets = df["dataset"].n_unique()
        # rename resolution and dataset to keep "dataset" name free
        df = df.rename({"resolution": "resolution_", "dataset": "dataset_"})
        df = df.with_columns(
            pl.lit(None, dtype=pl.String).alias("dataset"),
            pl.concat_str(
                pl.col("name"),
                pl.lit(" ("),
                pl.col("station_id"),
                pl.lit(")"),
            ).alias("name"),
        )
        if n_datasets and n_resolutions:
            df = df.with_columns(
                pl.concat_str(
                    pl.col("resolution_"),
                    pl.lit("/"),
                    pl.col("dataset_"),
                ).alias("dataset"),
            )
        elif n_datasets:
            df = df.with_columns(
                pl.col("dataset_").alias("dataset"),
            )
        elif n_resolutions:
            df = df.with_columns(
                pl.col("resolution_").alias("dataset"),
            )
        fig = px.scatter_map(
            df,
            lat="latitude",
            lon="longitude",
            text="name",
            color="dataset",
            zoom=zoom,
            center={
                "lat": center_lat,
                "lon": center_lon,
            },
        )
        return fig.update_layout(
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.01,
            },
            margin={"r": 10, "t": 10, "l": 10, "b": 10},
        )

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        **kwargs: dict,
    ) -> bytes | str:
        """Create an image from the plotly figure.

        This method is used by ``.to_image()`` to create an image for stations from the plotly figure.
        """
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            msg = f"Invalid format: {fmt}"
            raise KeyError(msg)
        return img


class _ValuesItemDict(TypedDict):
    """Type definition for dictionary of values."""

    station_id: str
    resolution: str
    dataset: str
    parameter: str
    date: str
    value: str
    quality: str


class _ValuesDict(TypedDict):
    """Type definition for dictionary of values."""

    metadata: NotRequired[_Metadata]
    stations: NotRequired[list[_Station]]
    values: list[_ValuesItemDict]


@dataclass
class _ValuesResult(ExportMixin):
    """Result class for values."""

    stations: StationsResult
    df: pl.DataFrame

    @staticmethod
    def _to_dict(df: pl.DataFrame) -> list[_ValuesItemDict]:
        """Format values as dictionary.

        This method is used both by ``to_dict()``,
        and ``to_ogc_feature_collection()``, however, the latter one splits
        the DataFrame into multiple DataFrames by station and calls this method for each of them.
        """
        if not df.is_empty():
            df = df.with_columns(
                pl.col("date").map_elements(lambda date: date.isoformat(), return_dtype=pl.String),
            )
        return df.to_dicts()

    def to_dict(self, *, with_metadata: bool = False, with_stations: bool = False) -> _ValuesDict:
        """Format values as dictionary."""
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        if with_stations:
            data["stations"] = self.stations.to_dict(with_metadata=False)["stations"]
        data["values"] = self._to_dict(self.df)
        return data

    def to_json(
        self,
        *,
        with_metadata: bool = False,
        with_stations: bool = False,
        indent: int | bool | None = 4,
    ) -> str:
        """Format values as JSON."""
        if indent is True:
            indent = 4
        elif indent is False:
            indent = None
        return json.dumps(self.to_dict(with_metadata=with_metadata, with_stations=with_stations), indent=indent)

    def filter_by_date(self, date: str) -> pl.DataFrame:
        """Filter values by date and return a new DataFrame."""
        self.df = filter_by_date(self.df, date=date)
        return self.df


class _ValuesOgcFeature(TypedDict):
    """Type definition for OGC feature of values."""

    type: Literal["Feature"]
    properties: _OgcFeatureProperties
    geometry: _OgcFeatureGeometry
    values: list[_ValuesItemDict]


class _ValuesOgcFeatureCollectionData(TypedDict):
    """Type definition for OGC feature collection data of values."""

    type: Literal["FeatureCollection"]
    features: list[_ValuesOgcFeature]


class _ValuesOgcFeatureCollection(TypedDict):
    """Type definition for OGC feature collection of values."""

    metadata: NotRequired[_Metadata]
    data: _ValuesOgcFeatureCollectionData


@dataclass
class ValuesResult(_ValuesResult):
    """Result class for values."""

    stations: StationsResult
    values: TimeseriesValues
    df: pl.DataFrame

    @property
    def df_stations(self) -> pl.DataFrame:
        """Get DataFrame with stations."""
        return self.stations.df.filter(pl.col("station_id").is_in(self.values.stations_collected))

    def to_ogc_feature_collection(self, *, with_metadata: bool = False, **_kwargs) -> _ValuesOgcFeatureCollection:  # noqa: ANN003
        """Format values as OGC feature collection."""
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
                        "resolution": station["resolution"],
                        "dataset": station["dataset"],
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

    def to_plot(self, **_kwargs: dict) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        try:
            import plotly.express as px  # noqa: PLC0415
            import plotly.graph_objects as go  # noqa: PLC0415
        except ImportError as e:
            msg = (
                "To use this method, please install the optional dependencies for plotly: "
                "pip install wetterdienst[plotting]"
            )
            raise ImportError(msg) from e

        df = self.df
        if df.is_empty():
            return go.Figure()
        # create unit mapping for title
        units = {
            parameter.name: self.values.unit_converter.targets[parameter.unit_type].symbol
            for parameter in self.values.sr.parameters
        }
        # used for subplots
        n = df.select(["resolution", "dataset", "parameter"]).n_unique()
        # used for name
        n_resolutions = df["resolution"].n_unique()
        n_datasets = df["dataset"].n_unique()
        df = df.with_columns(
            # add unit in brackets to parameter
            pl.concat_str(
                pl.col("parameter"),
                pl.lit(" ("),
                pl.col("parameter").replace(units),
                pl.lit(")"),
            ).alias("parameter"),
        )
        if n_datasets > 1:
            df = df.with_columns(
                pl.concat_str(
                    pl.col("dataset"),
                    pl.lit("<br>"),
                    pl.col("parameter"),
                ).alias("parameter"),
            )
        if n_resolutions > 1:
            df = df.with_columns(
                pl.concat_str(
                    pl.col("resolution"),
                    pl.lit("<br>"),
                    pl.col("parameter"),
                ).alias("parameter"),
            )
        fig = px.line(
            df,
            x="date",
            y="value",
            color="station_id",
            facet_row="parameter",
            height=300 * n,  # scale height with number of subplots
        )
        fig = fig.update_traces(
            mode="markers+lines",
        )
        fig = fig.update_yaxes(matches=None)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_layout(
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.01,
            },
            margin={"l": 10, "r": 10 + (n_resolutions + n_datasets) * 10, "t": 10, "b": 10},
        )
        return fig

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        **kwargs: dict,
    ) -> bytes | str:
        """Create an image from the plotly figure.

        This method is used by ``.to_image()`` to create an image for values from the plotly figure.
        """
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            msg = f"Invalid format: {fmt}"
            raise KeyError(msg)
        return img


class _InterpolatedOrSummarizedOgcFeatureProperties(TypedDict):
    """Type definition for OGC feature properties of interpolated or summarized values."""

    id: str
    name: str


class _InterpolatedValuesItemDict(TypedDict):
    """Type definition for dictionary of interpolated values."""

    station_id: str
    parameter: str
    date: str
    value: float
    distance_mean: float
    taken_station_ids: list[str]


class _InterpolatedValuesDict(TypedDict):
    """Type definition for dictionary of interpolated values."""

    metadata: NotRequired[_Metadata]
    stations: NotRequired[list[_Station]]
    values: list[_InterpolatedValuesItemDict]


class _InterpolatedValuesOgcFeature(TypedDict):
    """Type definition for OGC feature of interpolated values."""

    type: Literal["Feature"]
    properties: _InterpolatedOrSummarizedOgcFeatureProperties
    geometry: _OgcFeatureGeometry
    stations: list[_Station]
    values: list[_InterpolatedValuesItemDict]


class _InterpolatedValuesOgcFeatureCollectionData(TypedDict):
    """Type definition for OGC feature collection data of interpolated values."""

    type: Literal["FeatureCollection"]
    features: list[_InterpolatedValuesOgcFeature]


class _InterpolatedValuesOgcFeatureCollection(TypedDict):
    """Type definition for OGC feature collection of interpolated values."""

    metadata: NotRequired[_Metadata]
    data: _InterpolatedValuesOgcFeatureCollectionData


@dataclass
class InterpolatedValuesResult(_ValuesResult):
    """Result class for interpolated values."""

    stations: StationsResult
    df: pl.DataFrame
    latlon: tuple[float, float] | None

    if typing.TYPE_CHECKING:
        # We need to override the signature of the method to_dict() from ValuesResult here
        # because we want to return a slightly different type with columns related to interpolation.
        # Those are distance_mean and station_ids.
        # https://github.com/python/typing/discussions/1015
        def _to_dict(self, df: pl.DataFrame) -> list[_InterpolatedValuesItemDict]:
            """Format interpolated values as dictionary."""

        def to_dict(self, *, with_metadata: bool = False, with_stations: bool = False) -> _InterpolatedValuesDict:
            """Format interpolated values as dictionary."""

    def to_ogc_feature_collection(
        self,
        *,
        with_metadata: bool = False,
        **_kwargs,  # noqa: ANN003
    ) -> _InterpolatedValuesOgcFeatureCollection:
        """Format interpolated values as OGC feature collection."""
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        latitude, longitude = self.latlon
        name = f"interpolation({latitude:.4f},{longitude:.4f})"
        feature = {
            "type": "Feature",
            "properties": {
                "id": self.df.get_column("station_id").gather(0).item(),
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

    def to_plot(self, **_kwargs: dict) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        try:
            import plotly.express as px  # noqa: PLC0415
            import plotly.graph_objects as go  # noqa: PLC0415
        except ImportError as e:
            msg = (
                "To use this method, please install the optional dependencies for plotly: "
                "pip install wetterdienst[plotting]"
            )
            raise ImportError(msg) from e

        df = self.df
        if df.is_empty():
            return go.Figure()
        # create unit mapping for title
        units = {
            parameter.name: self.stations.values.unit_converter.targets[parameter.unit_type].symbol
            for parameter in self.stations.parameters
        }
        # used for subplots
        n = df.select(["dataset", "parameter"]).n_unique()
        # used for name
        n_resolutions = df["resolution"].n_unique()
        n_datasets = df["dataset"].n_unique()
        df = df.with_columns(
            # add unit in brackets to parameter
            pl.concat_str(
                pl.col("parameter"),
                pl.lit(" ("),
                pl.col("parameter").replace(units),
                pl.lit(")"),
            ).alias("parameter"),
            pl.col("taken_station_ids").list.join(",").alias("taken_station_ids"),
        )
        if n_datasets > 1:
            df = df.with_columns(
                pl.concat_str(
                    pl.col("dataset"),
                    pl.lit("<br>"),
                    pl.col("parameter"),
                ).alias("parameter"),
            )
        if n_resolutions > 1:
            df = df.with_columns(
                pl.concat_str(
                    pl.col("resolution"),
                    pl.lit("<br>"),
                    pl.col("parameter"),
                ).alias("parameter"),
            )
        fig = px.line(
            df,
            x="date",
            y="value",
            color="station_id",
            facet_row="parameter",
            height=300 * n,  # scale height with number of subplots
            text="taken_station_ids",
        )
        fig = fig.update_traces(
            mode="markers+lines",
        )
        fig = fig.update_yaxes(matches=None)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_layout(
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.01,
            },
            margin={"l": 10, "r": 10 + (n_resolutions + n_datasets) * 10, "t": 10, "b": 10},
        )
        return fig

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        **kwargs: dict,
    ) -> bytes | str:
        """Create an image from the plotly figure.

        This method is used by ``.to_image()`` to create an image for interpolated values from the plotly figure.
        """
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            msg = f"Invalid format: {fmt}"
            raise KeyError(msg)
        return img


class _SummarizedValuesItemDict(TypedDict):
    """Format summarized values as dictionary."""

    station_id: str
    parameter: str
    date: str
    value: float
    distance: float
    taken_station_id: str


class _SummarizedValuesDict(TypedDict):
    """Format summarized values as dictionary."""

    metadata: NotRequired[_Metadata]
    stations: NotRequired[list[_Station]]
    values: list[_SummarizedValuesItemDict]


class _SummarizedValuesOgcFeature(TypedDict):
    """Format summarized values as OGC feature."""

    type: Literal["Feature"]
    properties: _InterpolatedOrSummarizedOgcFeatureProperties
    geometry: _OgcFeatureGeometry
    stations: list[_Station]
    values: list[_SummarizedValuesItemDict]


class _SummarizedValuesOgcFeatureCollectionData(TypedDict):
    """Format summarized values as OGC feature collection data."""

    type: Literal["FeatureCollection"]
    features: list[_SummarizedValuesOgcFeature]


class _SummarizedValuesOgcFeatureCollection(TypedDict):
    """Format summarized values as OGC feature collection."""

    metadata: NotRequired[_Metadata]
    data: _SummarizedValuesOgcFeatureCollectionData


@dataclass
class SummarizedValuesResult(_ValuesResult):
    """Calculate summary of stations and parameters."""

    stations: StationsResult
    df: pl.DataFrame
    latlon: tuple[float, float]

    if typing.TYPE_CHECKING:
        # We need to override the signature of the method to_dict() from ValuesResult here
        # because we want to return a slightly different type with columns related to interpolation.
        # Those are distance and station_id.
        # https://github.com/python/typing/discussions/1015
        def _to_dict(self, df: pl.DataFrame) -> list[_SummarizedValuesItemDict]:
            """Format summarized values as dictionary."""

        def to_dict(self, *, with_metadata: bool = False, with_stations: bool = False) -> _SummarizedValuesDict:
            """Format summarized values as dictionary."""

    def to_ogc_feature_collection(
        self,
        *,
        with_metadata: bool = False,
        **_kwargs,  # noqa: ANN003
    ) -> _SummarizedValuesOgcFeatureCollection:
        """Export summarized values as OGC feature collection."""
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        latitude, longitude = self.latlon
        name = f"summary({latitude:.4f},{longitude:.4f})"
        feature = {
            "type": "Feature",
            "properties": {
                "id": self.df.get_column("station_id").gather(0).item(),
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

    def to_plot(self, **_kwargs: dict) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        try:
            import plotly.express as px  # noqa: PLC0415
            import plotly.graph_objects as go  # noqa: PLC0415
        except ImportError as e:
            msg = (
                "To use this method, please install the optional dependencies for plotly: "
                "pip install wetterdienst[plotting]"
            )
            raise ImportError(msg) from e

        df = self.df
        if df.is_empty():
            return go.Figure()
        # create unit mapping for title
        units = {
            parameter.name: self.stations.values.unit_converter.targets[parameter.unit_type].symbol
            for parameter in self.stations.parameters
        }
        # used for subplots
        n = df.select(["dataset", "parameter"]).n_unique()
        # used for name
        n_resolutions = df["resolution"].n_unique()
        n_datasets = df["dataset"].n_unique()
        df = df.with_columns(
            # add unit in brackets to parameter
            pl.concat_str(
                pl.col("parameter"),
                pl.lit(" ("),
                pl.col("parameter").replace(units),
                pl.lit(")"),
            ).alias("parameter"),
        )
        if n_datasets > 1:
            df = df.with_columns(
                pl.concat_str(
                    pl.col("dataset"),
                    pl.lit("<br>"),
                    pl.col("parameter"),
                ).alias("parameter"),
            )
        if n_resolutions > 1:
            df = df.with_columns(
                pl.concat_str(
                    pl.col("resolution"),
                    pl.lit("<br>"),
                    pl.col("parameter"),
                ).alias("parameter"),
            )
        fig = px.line(
            df,
            x="date",
            y="value",
            color="station_id",
            facet_row="parameter",
            height=300 * n,  # scale height with number of subplots
            text="taken_station_id",
        )
        fig = fig.update_traces(
            mode="markers+lines",
        )
        fig = fig.update_yaxes(matches=None)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_layout(
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.01,
            },
            margin={"l": 10, "r": 10 + (n_resolutions + n_datasets) * 10, "t": 10, "b": 10},
        )
        return fig

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        **kwargs: dict,
    ) -> bytes | str:
        """Create an image from the plotly figure.

        This method is used by ``.to_image()`` to create an image for summarized values from the plotly figure.
        """
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            msg = f"Invalid format: {fmt}"
            raise KeyError(msg)
        return img
