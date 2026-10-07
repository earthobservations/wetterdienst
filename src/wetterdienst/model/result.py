# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Result classes for timeseries data."""

from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, cast

import polars as pl
from pydantic import ConfigDict, with_config
from typing_extensions import NotRequired, TypedDict

from wetterdienst.io.export import ExportMixin
from wetterdienst.model.util import create_station_id_from_string, filter_by_date

if TYPE_CHECKING:
    from datetime import datetime

    import plotly.graph_objects as go

    from wetterdienst import Settings
    from wetterdienst.model.history import History, TimeseriesHistory
    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.unit import UnitConverter
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


# Extra keys are allowed so the schema admits the station columns a provider adds to the core ones,
# such as `gauge_zero`; they differ per provider, so they are not declared one by one.
@with_config(ConfigDict(extra="allow"))
class _Station(TypedDict):
    """Type definition for station."""

    resolution: str
    dataset: str
    station_id: str
    start_timestamp: str | None
    end_timestamp: str | None
    # null where the provider gives a station no position, elevation or name
    latitude: float | None
    longitude: float | None
    elevation: float | None
    name: str | None
    region: str | None


class _StationsDict(TypedDict):
    """Type definition for dictionary of stations."""

    metadata: NotRequired[_Metadata]
    stations: list[_Station]


# open to extra keys: a feature also carries the station columns its provider declares beyond these,
# such as WSV's gauge_zero, and the served OpenAPI schema says so
@with_config(ConfigDict(extra="allow"))
class _OgcFeatureProperties(TypedDict):
    """Type definition for OGC feature properties."""

    resolution: str
    # null on a values feature of a resolution the wide shape merged several datasets into
    dataset: str | None
    id: str
    name: str | None
    region: str | None
    start_timestamp: str | None
    end_timestamp: str | None


class _OgcFeatureGeometry(TypedDict):
    """Type definition for OGC feature geometry."""

    type: Literal["Point"]
    coordinates: list[float]


class _StationsOgcFeature(TypedDict):
    """Type definition for OGC feature of stations."""

    type: Literal["Feature"]
    properties: _OgcFeatureProperties
    # null for a station without a position: RFC 7946 3.2 writes an unlocated feature that way
    geometry: _OgcFeatureGeometry | None


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
        return cast("Settings", self.stations.settings)

    @property
    def parameters(self) -> list[ParameterModel]:
        """Get parameters from the request."""
        return cast("list[ParameterModel]", self.stations.parameters)

    @property
    def values(self) -> TimeseriesValues:
        """Get values from the request."""
        return self.stations._values.from_stations(self)  # noqa: SLF001

    @property
    def history(self) -> TimeseriesHistory:
        """Get history from the request."""
        # If the request implementation does not provide a history implementation
        # we raise a NotImplementedError so callers can handle it explicitly.
        if not getattr(self.stations, "_history", None):
            cls_name = self.stations.__class__.__name__
            msg = "History not implemented for " + cls_name
            raise NotImplementedError(msg)
        return self.stations._history.from_stations(self)  # noqa: SLF001

    @property
    def start(self) -> datetime | None:
        """Get the start of the requested window."""
        return cast("datetime | None", self.stations.start)

    @property
    def end(self) -> datetime | None:
        """Get the end of the requested window."""
        return cast("datetime | None", self.stations.end)

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

    def to_dict(self, *, with_metadata: bool = False) -> _StationsDict:  # ty: ignore[invalid-method-override]
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
                    pl.col("start_timestamp").dt.to_string("iso:strict"),
                    pl.col("end_timestamp").dt.to_string("iso:strict"),
                ],
            )
        data["stations"] = df.to_dicts()
        return data  # ty: ignore[invalid-return-type]

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

    def _ogc_extra_columns(self) -> list[str]:
        """Name the station columns a provider declares beyond the core ones, such as WSV's gauge_zero.

        An OGC feature carries them in its properties. A result built from a bare frame, with no
        request behind it, has none.
        """
        from wetterdienst.model.request import TimeseriesRequest  # noqa: PLC0415

        core_columns = TimeseriesRequest._base_columns  # noqa: SLF001
        return [
            column
            for column in getattr(self.stations, "_base_columns", core_columns)
            if column not in core_columns and column in self.df.columns
        ]

    @staticmethod
    def _to_ogc_feature(station: dict, extra_columns: list[str]) -> _StationsOgcFeature:
        """Format one station row, with its dates already ISO strings, as an OGC feature."""
        # A position is "longitude, latitude [, elevation]" in WGS84 decimal degrees, and per
        # RFC 7946 3.1.1 it is two or more numbers, so a station without an elevation gets no z
        # rather than a null one, which strict parsers reject. A station without a latitude or
        # longitude, such as a postcode of DWD derived's climate_correction_factor, has no position
        # at all, and RFC 7946 3.2 writes such an unlocated feature with a null geometry.
        geometry: _OgcFeatureGeometry | None = None
        if station["longitude"] is not None and station["latitude"] is not None:
            coordinates = [station["longitude"], station["latitude"]]
            if station["elevation"] is not None:
                coordinates.append(station["elevation"])
            geometry = {"type": "Point", "coordinates": coordinates}
        return {
            "type": "Feature",
            "properties": {
                "resolution": station["resolution"],
                "dataset": station["dataset"],
                "id": station["station_id"],
                "name": station["name"],
                "region": station["region"],
                "start_timestamp": station["start_timestamp"],
                "end_timestamp": station["end_timestamp"],
                **{column: station[column] for column in extra_columns},
            },
            "geometry": geometry,
        }

    def to_ogc_feature_collection(self, *, with_metadata: bool = False, **_kwargs) -> _StationsOgcFeatureCollection:  # noqa: ANN003  # ty: ignore[invalid-method-override]
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
        extra_columns = self._ogc_extra_columns()
        features = []
        for station in self.df.with_columns(
            pl.col("start_timestamp").dt.to_string("iso:strict"),
            pl.col("end_timestamp").dt.to_string("iso:strict"),
        ).iter_rows(named=True):
            features.append(self._to_ogc_feature(station, extra_columns))
        data["data"] = {
            "type": "FeatureCollection",
            "features": features,
        }
        return data  # ty: ignore[invalid-return-type]

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
        min_lon = cast("float", self.df["longitude"].min())
        max_lon = cast("float", self.df["longitude"].max())
        min_lat = cast("float", self.df["latitude"].min())
        max_lat = cast("float", self.df["latitude"].max())
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

    def _to_image(  # ty: ignore[invalid-method-override]
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
    timestamp: str
    value: float | None
    quality: float | None


class _ValuesOgcItemDict(TypedDict):
    """Type definition for a value of a GeoJSON feature: the feature's properties carry its station."""

    resolution: str
    dataset: str
    parameter: str
    timestamp: str
    value: float | None
    quality: float | None


# A wide row holds one value and one quality column per parameter, named after it, so those keys
# differ per request and are typed as extra items rather than declared one by one; being numbers,
# they also keep a long row, whose `parameter` is a string, from passing for a wide one. Its
# dataset is null in a resolution the wide shape merged several requested datasets into (see
# TimeseriesValues._widen_df).
class _ValuesWideItemDict(TypedDict, extra_items=float | None):
    """Type definition for a wide row of values."""

    station_id: str
    resolution: str
    dataset: str | None
    timestamp: str


class _ValuesWideOgcItemDict(TypedDict, extra_items=float | None):
    """Type definition for a wide row of a GeoJSON feature: the feature's properties carry its station."""

    resolution: str
    dataset: str | None
    timestamp: str


class _ValuesDict(TypedDict):
    """Type definition for dictionary of values."""

    metadata: NotRequired[_Metadata]
    stations: NotRequired[list[_Station]]
    # one item per value in the long shape, one row per timestamp in the wide one
    values: list[_ValuesItemDict] | list[_ValuesWideItemDict]


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
        the DataFrame by resolution, dataset and station and calls this method for each part.
        """
        if not df.is_empty():
            df = df.with_columns(
                pl.col("timestamp").dt.to_string("iso:strict"),
            )
        return df.to_dicts()  # ty: ignore[invalid-return-type]

    def to_dict(self, *, with_metadata: bool = False, with_stations: bool = False) -> _ValuesDict:  # ty: ignore[invalid-method-override]
        """Format values as dictionary."""
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        if with_stations:
            data["stations"] = self.stations.to_dict(with_metadata=False)["stations"]
        data["values"] = self._to_dict(self.df)
        return data  # ty: ignore[invalid-return-type]

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

    def _unit_symbols(self, unit_converter: UnitConverter) -> dict[str, str]:
        """Map every parameter a frame can carry to the symbol its values are written in.

        Keyed the way `_unit_symbol_key` reads a frame, by resolution and dataset as well as name.
        A canonical name is only unique within its dataset -- `sunshine_duration` is published by
        DWD in hours at 10 minutes and in minutes at an hour -- so keying on the name alone let one
        of them label the other, which is the mislabel this method exists to prevent.

        Two things the plots used to get wrong. The frame carries `name_original` unless
        `ts_humanize` is on, while the mapping was keyed on the canonical name alone, so nothing
        matched and the label read `tmk (tmk)` -- the name where the unit belongs. And the symbol
        was always the target unit's, though `ts_convert_units=False` leaves the values in the unit
        the source published them in: `10_minutes/solar/sunshine_duration` came back in hours under
        a label saying seconds.
        """
        convert_units = self.stations.settings.ts_convert_units
        symbols = {}
        for parameter in self.stations.parameters:
            unit = (
                unit_converter.targets[parameter.unit_type]
                if convert_units
                else unit_converter.get_unit(parameter.unit, parameter.unit_type)
            )
            resolution = parameter.dataset.resolution.name
            dataset = parameter.dataset.name
            # either naming, since which one the frame carries depends on `ts_humanize`
            symbols[f"{resolution}/{dataset}/{parameter.name}"] = unit.symbol
            symbols[f"{resolution}/{dataset}/{parameter.name_original}"] = unit.symbol
        return symbols

    @staticmethod
    def _unit_symbol_key() -> pl.Expr:
        """Read the key of `_unit_symbols` off a frame.

        The metadata columns come back as Enum in aggregated results, which concat_str will not
        take, hence the casts.
        """
        return pl.concat_str(
            pl.col("resolution").cast(pl.String),
            pl.lit("/"),
            pl.col("dataset").cast(pl.String),
            pl.lit("/"),
            pl.col("parameter").cast(pl.String),
        )

    def filter_by_date(self, date: str) -> pl.DataFrame:
        """Filter values by date or date interval and return a new DataFrame.

        The date is read as the span it names, so ``"2020-05-01"`` keeps that whole day -- all 24
        readings of it for hourly data -- ``"2020-05"`` the month and ``"2020"`` the year. An
        interval such as ``"2017-01/2019-12"`` runs from the start of the first span to the end of
        the second, and a date carrying a time (``"2020-05-01T12"``) names one instant and is
        matched exactly. See :func:`wetterdienst.model.util.filter_by_date`.
        """
        self.df = filter_by_date(self.df, date=date)
        return self.df


class _ValuesOgcFeature(TypedDict):
    """Type definition for OGC feature of values."""

    type: Literal["Feature"]
    properties: _OgcFeatureProperties
    # null for a station without a position: RFC 7946 3.2 writes an unlocated feature that way
    geometry: _OgcFeatureGeometry | None
    values: list[_ValuesOgcItemDict] | list[_ValuesWideOgcItemDict]


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

    def to_ogc_feature_collection(self, *, with_metadata: bool = False, **_kwargs) -> _ValuesOgcFeatureCollection:  # noqa: ANN003  # ty: ignore[invalid-method-override]
        """Format values as OGC feature collection."""
        data = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        # The stations frame holds one row per resolution, dataset and station, so a feature is one
        # dataset of one station and carries that dataset's values only, save in a resolution the
        # wide shape merged several datasets into, which is one feature per station (see below).
        # The values frame stores these columns as Enum (see TimeseriesValues._cast_metadata_to_enum);
        # its partition keys are plain strings all the same, as the stations frame's are, and the
        # cast is for the join.
        values_by_series = {
            key: df.drop("station_id")
            for key, df in self.df.partition_by(
                ["resolution", "dataset", "station_id"], as_dict=True, maintain_order=True
            ).items()
        }
        # cut down to the stations that returned values before walking the rows: a ranked request
        # keeps every station with a position in the stations frame (see TimeseriesRequest.filter_by_rank)
        df_stations = self.stations.df.join(
            self.df.select(pl.col("resolution", "station_id").cast(pl.String)).unique(),
            on=["resolution", "station_id"],
            how="semi",
        )
        # The wide shape names no dataset on a row of a resolution it merged several requested
        # datasets into (see TimeseriesValues._widen_df), as such a row holds the columns of each.
        # A station there gets one feature with a null dataset, which spans the merged datasets'
        # dates: the earliest start and the latest end.
        merged_resolutions = {resolution for resolution, dataset, _ in values_by_series if dataset is None}
        if merged_resolutions:
            merged = pl.col("resolution").is_in(merged_resolutions)
            station_key = ["resolution", "station_id"]
            df_stations = df_stations.with_columns(
                pl.when(merged).then(None).otherwise(pl.col("dataset")).alias("dataset"),
                pl.when(merged)
                .then(pl.col("start_timestamp").min().over(station_key))
                .otherwise(pl.col("start_timestamp"))
                .alias("start_timestamp"),
                pl.when(merged)
                .then(pl.col("end_timestamp").max().over(station_key))
                .otherwise(pl.col("end_timestamp"))
                .alias("end_timestamp"),
            ).unique(subset=["resolution", "dataset", "station_id"], keep="first", maintain_order=True)
        extra_columns = self.stations._ogc_extra_columns()  # noqa: SLF001
        features = []
        for station in df_stations.with_columns(
            pl.col("start_timestamp").dt.to_string("iso:strict"),
            pl.col("end_timestamp").dt.to_string("iso:strict"),
        ).iter_rows(named=True):
            df_values = values_by_series.get((station["resolution"], station["dataset"], station["station_id"]))
            if df_values is None:
                continue
            feature = self.stations._to_ogc_feature(station, extra_columns)  # noqa: SLF001
            features.append({**feature, "values": self._to_dict(df_values)})
        data["data"] = {
            "type": "FeatureCollection",
            "features": features,
        }
        return data  # ty: ignore[invalid-return-type]

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
        if "parameter" not in df.columns:
            df = self._lengthen(df)
        if df.is_empty():
            return go.Figure()
        # create unit mapping for title
        units = self._unit_symbols(self.values.unit_converter)
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
                self._unit_symbol_key().replace(units),
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
            x="timestamp",
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

    def _lengthen(self, df: pl.DataFrame) -> pl.DataFrame:
        """Turn a wide values frame back into the long one `to_plot` draws.

        Undoes what `TimeseriesValues._widen_df` did. A column is named after its dataset as well
        whenever the request spans more than one dataset, and that name is how the dataset is told
        on a row of a resolution the wide shape merged several datasets into, which names none.

        A null is left out, as the long shape leaves it out by default: the wide shape writes one
        wherever a column has no reading at a row another column has one at, and a column of one
        resolution is null throughout the rows of another, as the widening joins on the resolution.
        Kept, those would draw a series under a resolution it does not belong to. The quality
        columns are not drawn.

        The rows are put in the order a long result holds them in, which is the order the plot
        lays its facets out and colours its stations in: station by station, as they were
        collected, and sorted within each station by resolution, dataset and parameter.
        """
        datasets_by_resolution: dict[str, set[str]] = {}
        for parameter in self.stations.parameters:
            datasets_by_resolution.setdefault(parameter.dataset.resolution.name, set()).add(parameter.dataset.name)
        prefixed = len(set().union(*datasets_by_resolution.values())) > 1
        keys = ("station_id", "resolution", "dataset", "timestamp")
        columns = [
            column
            for column in df.columns
            if column not in keys
            and not (column.endswith("_quality") and column.removesuffix("_quality") in df.columns)
        ]
        series = []
        for (resolution,), df_resolution in df.group_by("resolution", maintain_order=True):
            for column in columns:
                dataset = pl.col("dataset").cast(pl.String)
                parameter = column
                if prefixed:
                    matches = [
                        name
                        for name in datasets_by_resolution.get(str(resolution), ())
                        if column.startswith(f"{name}_")
                    ]
                    if not matches:
                        continue
                    # the longest, should one dataset's name begin with another's
                    name = max(matches, key=len)
                    dataset = pl.lit(name)
                    parameter = column.removeprefix(f"{name}_")
                series.append(
                    df_resolution.filter(pl.col(column).is_not_null()).select(
                        pl.col("station_id").cast(pl.String),
                        pl.col("resolution").cast(pl.String),
                        dataset.alias("dataset"),
                        pl.lit(parameter).alias("parameter"),
                        pl.col("timestamp"),
                        pl.col(column).cast(pl.Float64).alias("value"),
                    )
                )
        if not series:
            return pl.DataFrame()
        # the stations in the order they come in, and stable, so that a series keeps its timestamps' order
        stations = pl.Enum(df.get_column("station_id").cast(pl.String).unique(maintain_order=True))
        return pl.concat(series).sort(
            pl.col("station_id").cast(stations), "resolution", "dataset", "parameter", maintain_order=True
        )

    def _to_image(  # ty: ignore[invalid-method-override]
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


@dataclass
class HistoryResult:
    """Result class for history data."""

    stations: StationsResult
    history: History


class _InterpolatedOrSummarizedOgcFeatureProperties(TypedDict):
    """Type definition for OGC feature properties of interpolated or summarized values."""

    id: str
    name: str


class _InterpolatedValuesItemDict(TypedDict):
    """Type definition for dictionary of interpolated values."""

    station_id: str
    resolution: str
    dataset: str
    parameter: str
    timestamp: str
    value: float | None
    distance_mean: float | None
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
    latlon: tuple[float, float]
    elevation: float | None = None

    if typing.TYPE_CHECKING:
        # We need to override the signature of the method to_dict() from ValuesResult here
        # because we want to return a slightly different type with columns related to interpolation.
        # Those are distance_mean and station_ids.
        # https://github.com/python/typing/discussions/1015
        def _to_dict(self, df: pl.DataFrame) -> list[_InterpolatedValuesItemDict]:  # ty: ignore[invalid-method-override]
            """Format interpolated values as dictionary."""

        def to_dict(self, *, with_metadata: bool = False, with_stations: bool = False) -> _InterpolatedValuesDict:  # ty: ignore[invalid-method-override]
            """Format interpolated values as dictionary."""

    def to_ogc_feature_collection(  # ty: ignore[invalid-method-override]
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
        if self.elevation is not None:
            name = f"interpolation({latitude:.4f},{longitude:.4f},{self.elevation:.1f}m)"
        feature = {
            "type": "Feature",
            "properties": {
                # the id of the point, which is this name hashed -- read out of the frame, it took
                # a result that came back with no rows down with an out-of-bounds gather
                "id": create_station_id_from_string(name),
                "name": name,
            },
            "geometry": {
                # WGS84 is implied and coordinates represent decimal degrees
                # ordered as "longitude, latitude [,elevation]" with z expressed
                # as metres above mean sea level per WGS84.
                # -- http://wiki.geojson.org/RFC-001
                "type": "Point",
                # the z coordinate when there is one, which is what tells two answers for one
                # place apart: 200 m and 1500 m are different weather
                "coordinates": [longitude, latitude]
                if self.elevation is None
                else [longitude, latitude, self.elevation],
            },
            "stations": self.stations.to_dict(with_metadata=False)["stations"],
            "values": self.to_dict(with_metadata=False, with_stations=False)["values"],
        }
        data["data"] = {
            "type": "FeatureCollection",
            "features": [feature],
        }
        return data  # ty: ignore[invalid-return-type]

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
        units = self._unit_symbols(self.stations.values.unit_converter)
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
                self._unit_symbol_key().replace(units),
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
            x="timestamp",
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

    def _to_image(  # ty: ignore[invalid-method-override]
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
    resolution: str
    dataset: str
    parameter: str
    timestamp: str
    value: float | None
    distance: float | None
    taken_station_id: str | None


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
    elevation: float | None = None

    if typing.TYPE_CHECKING:
        # We need to override the signature of the method to_dict() from ValuesResult here
        # because we want to return a slightly different type with columns related to interpolation.
        # Those are distance and station_id.
        # https://github.com/python/typing/discussions/1015
        def _to_dict(self, df: pl.DataFrame) -> list[_SummarizedValuesItemDict]:  # ty: ignore[invalid-method-override]
            """Format summarized values as dictionary."""

        def to_dict(self, *, with_metadata: bool = False, with_stations: bool = False) -> _SummarizedValuesDict:  # ty: ignore[invalid-method-override]
            """Format summarized values as dictionary."""

    def to_ogc_feature_collection(  # ty: ignore[invalid-method-override]
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
        if self.elevation is not None:
            name = f"summary({latitude:.4f},{longitude:.4f},{self.elevation:.1f}m)"
        feature = {
            "type": "Feature",
            "properties": {
                # the id of the point, which is this name hashed -- read out of the frame, it took
                # a result that came back with no rows down with an out-of-bounds gather
                "id": create_station_id_from_string(name),
                "name": name,
            },
            "geometry": {
                # WGS84 is implied and coordinates represent decimal degrees
                # ordered as "longitude, latitude [,elevation]" with z expressed
                # as metres above mean sea level per WGS84.
                # -- http://wiki.geojson.org/RFC-001
                "type": "Point",
                # the z coordinate when there is one, which is what tells two answers for one
                # place apart: 200 m and 1500 m are different weather
                "coordinates": [longitude, latitude]
                if self.elevation is None
                else [longitude, latitude, self.elevation],
            },
            "stations": self.stations.to_dict(with_metadata=False)["stations"],
            "values": self.to_dict(with_metadata=False, with_stations=False)["values"],
        }
        data["data"] = {
            "type": "FeatureCollection",
            "features": [feature],
        }
        return data  # ty: ignore[invalid-return-type]

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
        units = self._unit_symbols(self.stations.values.unit_converter)
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
                self._unit_symbol_key().replace(units),
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
            x="timestamp",
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

    def _to_image(  # ty: ignore[invalid-method-override]
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
