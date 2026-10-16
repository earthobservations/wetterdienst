# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Result classes for timeseries data."""

from __future__ import annotations

import json
import typing
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from functools import update_wrapper
from typing import TYPE_CHECKING, Generic, Literal, NotRequired, Self, TypeVar, cast

import polars as pl
from pydantic import ConfigDict, with_config

# not `typing.TypedDict`: pydantic refuses that as a response model on Python below 3.12
from typing_extensions import TypedDict

from wetterdienst.io.export import ExportMixin, check_image_size, require_kaleido
from wetterdienst.model.unit import UnitConverter
from wetterdienst.model.util import create_station_id_from_string, filter_by_date
from wetterdienst.util.datetime import format_timestamp, timestamps_to_string
from wetterdienst.util.extras import import_optional

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from collections.abc import Set as AbstractSet
    from types import FunctionType

    import plotly.graph_objects as go

    from wetterdienst import Settings
    from wetterdienst.model.history import History, TimeseriesHistory
    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.values import TimeseriesValues
    from wetterdienst.options import Options


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
class _License(TypedDict):
    """Type definition for the terms a provider publishes its data under."""

    spdx_id: str | None
    name: str
    url: str


class _Provider(TypedDict):
    """Type definition for provider metadata."""

    name_local: str
    name_english: str
    country: str
    copyright: str
    url: str
    # null where the provider states no terms, or asks for no credit
    license: _License | None
    attribution: str | None


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


class _StationsDictBody(TypedDict):
    """The members of `_StationsDict` other than `metadata`."""

    stations: list[_Station]


class _StationsDict(_StationsDictBody):
    """Type definition for dictionary of stations."""

    metadata: NotRequired[_Metadata]


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


class _StationsOgcFeatureCollectionBody(TypedDict):
    """The members of `_StationsOgcFeatureCollection` other than `metadata`."""

    data: _StationsOgcFeatureCollectionData


class _StationsOgcFeatureCollection(_StationsOgcFeatureCollectionBody):
    """Type definition for OGC feature collection of stations."""

    metadata: NotRequired[_Metadata]


class _CalledMethod:
    """A method of a result that used to be a property, which refuses to be read as one.

    `stations.values.all()` read like an attribute and was a factory, building a new downloader on
    every access. The method it is now would answer `stations.values.all` with Python's "'method'
    object has no attribute 'all'", which says nothing of what to write instead.
    """

    def __init__(self, bound: Callable[..., object], owner: str, name: str) -> None:
        self._bound = bound
        self._owner = owner
        self._name = name
        update_wrapper(self, bound)

    def __call__(self, *args: object, **kwargs: object) -> object:
        """Call the method."""
        return self._bound(*args, **kwargs)

    def __repr__(self) -> str:
        """Show the bound method it stands for."""
        return repr(self._bound)

    @property
    def __self__(self) -> object:
        """Name the result the method is bound to, as a bound method does."""
        return getattr(self._bound, "__self__", None)

    @property
    def __func__(self) -> object:
        """Name the function the method is made of, as a bound method does."""
        return getattr(self._bound, "__func__", None)

    def __getattr__(self, attr: str) -> object:
        """Refuse the attribute of what the method returns, naming the call that gets there."""
        # a dunder is looked up by Python and by tools that inspect a callable, which is no mistake
        if attr.startswith("__"):
            raise AttributeError(attr)
        msg = f"{self._owner}.{self._name} is a method, not an attribute: write {self._name}().{attr}"
        raise AttributeError(msg)


class _FactoryMethod:
    """Descriptor that hands out a method as `_CalledMethod`, and the function itself on the class."""

    def __init__(self, func: FunctionType) -> None:
        self._func = func
        self._name = func.__name__
        self.__doc__ = func.__doc__

    def __get__(self, instance: object, owner: type | None = None) -> object:
        """Bind the method to the result it is read from."""
        if instance is None:
            return self._func
        return _CalledMethod(self._func.__get__(instance, owner), type(instance).__name__, self._name)


_MethodT = TypeVar("_MethodT", bound="Callable[..., object]")


def _factory_method(func: _MethodT) -> _MethodT:
    """Mark a method that builds a new object per call, so that reading it as an attribute says what to write."""
    # a type checker reads the method it was given: the descriptor only changes what a mistaken read says
    return cast("_MethodT", _FactoryMethod(cast("FunctionType", func)))


@dataclass(frozen=True)
class StationsResult(ExportMixin):
    """Result class for stations.

    Built by a request (`all()` and the `filter_by_*` methods), and immutable: a filter gives a new
    result, and nothing assigns to one. Callers use `df` (the stations the request selected), the
    formats (`to_dict`, `to_json`, `to_geojson`, `to_csv`, ...) and `values()` / `history()`.
    `settings`, `options`, `parameters`, `start` and `end` read what the request was given.

    `df_all`, `stations_filter` and `rank` say how `df` was selected from the stations of the request
    and are for the library: a caller reads `df`.
    """

    #: the request that made this result: what a later step reads the settings, the parameters and the
    #: window of, and what a provider reads its own arguments of
    request: TimeseriesRequest
    #: the selected stations, one row per resolution, dataset and station
    df: pl.DataFrame
    #: every station of the request, which `df` was selected from
    df_all: pl.DataFrame
    #: how `df` was selected, which says why only some of the stations are in it
    stations_filter: StationsFilter
    #: the number of stations a ranked selection asked for, which `values()` stops at
    rank: int | None = None

    @property
    def settings(self) -> Settings:
        """Get settings for the request."""
        return cast("Settings", self.request.settings)

    @property
    def options(self) -> Options:
        """Get the options of the request: how the values come back and how stations are chosen."""
        return cast("Options", self.request.options)

    @property
    def parameters(self) -> list[ParameterModel]:
        """Get parameters from the request."""
        return cast("list[ParameterModel]", self.request.parameters)

    @_factory_method
    def values(self) -> TimeseriesValues:
        """Build the reader of the values of these stations: `values().all()` or `values().query()`.

        A new one on every call, so that two readers never share the state of a walk over the stations.
        """
        return self.request._values.from_stations(self)  # noqa: SLF001

    @_factory_method
    def history(self) -> TimeseriesHistory:
        """Build the reader of the history of these stations: `history().query()`.

        A new one on every call.

        Raises:
            NotImplementedError: when the provider has no station history.

        """
        # If the request implementation does not provide a history implementation
        # we raise a NotImplementedError so callers can handle it explicitly.
        history = self.request._history  # noqa: SLF001
        if history is None:
            cls_name = self.request.__class__.__name__
            msg = "History not implemented for " + cls_name
            raise NotImplementedError(msg)
        return history.from_stations(self)

    @property
    def start(self) -> datetime | None:
        """Get the start of the requested window."""
        return cast("datetime | None", self.request.start)

    @property
    def end(self) -> datetime | None:
        """Get the end of the requested window."""
        return cast("datetime | None", self.request.end)

    @property
    def station_id(self) -> pl.Series:
        """Get station IDs from the DataFrame."""
        return self.df.get_column("station_id")

    def get_metadata(self) -> _Metadata:
        """Get metadata for the provider and producer."""
        from wetterdienst import Info  # noqa: PLC0415

        info = Info()
        name_local = self.request.metadata.name_local
        name_english = self.request.metadata.name_english
        country = self.request.metadata.country
        copyright_ = self.request.metadata.copyright
        url = self.request.metadata.url
        license_ = self.request.metadata.license
        return {
            "provider": {
                "name_local": name_local,
                "name_english": name_english,
                "country": country,
                "copyright": copyright_,
                "url": url,
                "license": cast("_License", license_.model_dump()) if license_ else None,
                "attribution": self.request.metadata.attribution,
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
        df = timestamps_to_string(self.df, ["start_timestamp", "end_timestamp"])
        # polars types its rows as dicts of Any; they carry the station columns, checked by the tests
        stations = cast("list[_Station]", df.to_dicts())
        if with_metadata:
            return {"metadata": self.get_metadata(), "stations": stations}
        return {"stations": stations}

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
            for column in getattr(self.request, "_base_columns", core_columns)
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

    def to_ogc_feature_collection(
        self, *, with_metadata: bool = False, **_kwargs: object
    ) -> _StationsOgcFeatureCollection:
        """Format station information as OGC feature collection.

        Will be used by ``.to_geojson()``.

        Args:
            with_metadata: bool whether to include metadata (information about the provider and producer)

        Returns:
            Dictionary with station information as OGC feature collection.

        """
        extra_columns = self._ogc_extra_columns()
        features = []
        for station in timestamps_to_string(self.df, ["start_timestamp", "end_timestamp"]).iter_rows(named=True):
            features.append(self._to_ogc_feature(station, extra_columns))
        collection: _StationsOgcFeatureCollectionData = {"type": "FeatureCollection", "features": features}
        if with_metadata:
            return {"metadata": self.get_metadata(), "data": collection}
        return {"data": collection}

    def to_plot(self, **_kwargs: object) -> go.Figure:
        """Create a plotly figure from the stations DataFrame."""
        px = import_optional("plotly.express", "Plotting", extra="plotting")
        go = import_optional("plotly.graph_objects", "Plotting", extra="plotting")

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

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        max_side: int | None = None,
        **kwargs: object,
    ) -> bytes | str:
        """Create an image from the plotly figure.

        This method is used by ``.to_image()`` to create an image for stations from the plotly figure.
        """
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            check_image_size(fig, width, height, scale, max_side)
            require_kaleido()
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
    quality_flags: str | None


class _ValuesOgcItemDict(TypedDict):
    """Type definition for a value of a GeoJSON feature: the feature's properties carry its station."""

    resolution: str
    dataset: str
    parameter: str
    timestamp: str
    value: float | None
    quality_flags: str | None


# The columns of a wide row beyond the declared ones are numbers, except the quality flags, which are
# strings. A TypedDict's `extra_items` has one type for all of them, so the schema is told apart
# here: `additionalProperties` stays numeric, which is what keeps a long row, whose `parameter` is a
# string, from passing for a wide one (GH-2282), and the flag columns are named by pattern.
def _wide_row_schema(schema: dict[str, typing.Any]) -> None:
    schema["additionalProperties"] = {"anyOf": [{"type": "number"}, {"type": "null"}]}
    schema["patternProperties"] = {"_quality_flags$": {"anyOf": [{"type": "string"}, {"type": "null"}]}}


# A wide row holds one value and one quality flags column per parameter, named after it,
# so those keys differ per request and are typed as extra items rather than declared one by one:
# a number for the value, a string for the flags. Its dataset is null in a resolution the wide
# shape merged several requested datasets into (see TimeseriesValues._widen_df).
@with_config(ConfigDict(json_schema_extra=_wide_row_schema))
class _ValuesWideItemDict(TypedDict, extra_items=float | str | None):
    """Type definition for a wide row of values."""

    station_id: str
    resolution: str
    dataset: str | None
    timestamp: str


@with_config(ConfigDict(json_schema_extra=_wide_row_schema))
class _ValuesWideOgcItemDict(TypedDict, extra_items=float | str | None):
    """Type definition for a wide row of a GeoJSON feature: the feature's properties carry its station."""

    resolution: str
    dataset: str | None
    timestamp: str


class _ValuesDictBody(TypedDict):
    """The members of `_ValuesDict` other than `metadata`."""

    stations: NotRequired[list[_Station]]
    # one item per value in the long shape, one row per timestamp in the wide one
    values: list[_ValuesItemDict] | list[_ValuesWideItemDict]


class _ValuesDict(_ValuesDictBody):
    """Type definition for dictionary of values."""

    metadata: NotRequired[_Metadata]


# What differs between the values results is what a row and the whole dictionary look like: an
# interpolated row has `distance_mean`, a summarized one `distance`. The result is generic over those
# two, so `to_dict()` is declared as what each returns without redeclaring the method in the subclass.
_RowsT = TypeVar("_RowsT")
_DictT = TypeVar("_DictT", bound="Mapping[str, object]")


@dataclass(frozen=True)
class _ValuesResult(ExportMixin, Generic[_RowsT, _DictT]):
    """What the results of values, interpolation and summary have in common.

    A frozen result of a frame of values (`df`) and the stations it describes (`stations`), which has
    `df_stations` (the stations behind the values), the formats and the plots. Where a method is not
    a format, it gives a new result back: `filtered_by_date` and `filtered_by_sql`.
    """

    stations: StationsResult
    df: pl.DataFrame

    @property
    def df_stations(self) -> pl.DataFrame:
        """Get the stations the values come from, one row per resolution, dataset and station.

        Only the stations that returned values: a request for the stations nearest a point lists
        every station with a position, and the walk stops at the ones with data. Read off the values,
        so that a `ValuesResult` cut down by `filtered_by_date` or `filtered_by_sql` names the stations
        that are left. An interpolated or summarized result names the stations it was made from.
        """
        if "station_id" not in self.df.columns:
            return self.stations.df.clear()
        return self.stations.df.filter(pl.col("station_id").is_in(self.df.get_column("station_id").implode()))

    @staticmethod
    def _to_dict(df: pl.DataFrame) -> _RowsT:
        """Format values as dictionary.

        This method is used both by ``to_dict()``,
        and ``to_ogc_feature_collection()``, however, the latter one splits
        the DataFrame by resolution, dataset and station and calls this method for each part.
        """
        # polars types its rows as dicts of Any; they carry the columns of the item, checked by the tests
        return cast("_RowsT", timestamps_to_string(df, ["timestamp"]).to_dicts())

    def to_dict(self, *, with_metadata: bool = False, with_stations: bool = False) -> _DictT:
        """Format values as dictionary."""
        # assembled key by key, as the keys come in this order and two of them are optional
        data: dict[str, object] = {}
        if with_metadata:
            data["metadata"] = self.stations.get_metadata()
        if with_stations:
            data["stations"] = self.stations.to_dict(with_metadata=False)["stations"]
        data["values"] = self._to_dict(self.df)
        return cast("_DictT", data)

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

    def _unit_symbols(self) -> dict[str, str]:
        """Map every parameter a frame can carry to the symbol its values are written in.

        Keyed the way `_unit_symbol_key` reads a frame, by resolution and dataset as well as name.
        A canonical name is only unique within its dataset -- `sunshine_duration` is published by
        DWD in hours at 10 minutes and in minutes at an hour -- so keying on the name alone let one
        of them label the other, which is the mislabel this method exists to prevent.

        Two things the plots used to get wrong. The frame carries `name_original` unless
        `humanize` is on, while the mapping was keyed on the canonical name alone, so nothing
        matched and the label read `tmk (tmk)` -- the name where the unit belongs. And the symbol
        was always the target unit's, though `convert_units=False` leaves the values in the unit
        the source published them in: `10_minutes/solar/sunshine_duration` came back in hours under
        a label saying seconds.
        """
        convert_units = self.stations.options.convert_units
        unit_converter = UnitConverter()
        unit_converter.update_targets(self.stations.options.unit_targets)
        symbols = {}
        for parameter in self.stations.parameters:
            unit = (
                unit_converter.targets[parameter.unit_type]
                if convert_units
                else unit_converter.get_unit(parameter.unit, parameter.unit_type)
            )
            resolution = parameter.dataset.resolution.name
            dataset = parameter.dataset.name
            # either naming, since which one the frame carries depends on `humanize`
            symbols[f"{resolution}/{dataset}/{parameter.name}"] = unit.symbol
            symbols[f"{resolution}/{dataset}/{parameter.name_original}"] = unit.symbol
        return symbols

    @staticmethod
    def _unit_symbol_key() -> pl.Expr:
        """Read the key of `_unit_symbols` off a frame."""
        return pl.concat_str(pl.col("resolution"), pl.lit("/"), pl.col("dataset"), pl.lit("/"), pl.col("parameter"))

    def filtered_by_date(self, date: str) -> Self:
        """Filter values by date or date interval and return a new result of them.

        This result is left as it is.

        The date is read as the span it names, so ``"2020-05-01"`` keeps that whole day -- all 24
        readings of it for hourly data -- ``"2020-05"`` the month and ``"2020"`` the year. An
        interval such as ``"2017-01/2019-12"`` runs from the start of the first span to the end of
        the second, and a date carrying a time (``"2020-05-01T12"``) names one instant and is
        matched exactly. See :func:`wetterdienst.model.util.filter_by_date`.
        """
        return replace(self, df=filter_by_date(self.df, date=date))


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


class _ValuesOgcFeatureCollectionBody(TypedDict):
    """The members of `_ValuesOgcFeatureCollection` other than `metadata`."""

    data: _ValuesOgcFeatureCollectionData


class _ValuesOgcFeatureCollection(_ValuesOgcFeatureCollectionBody):
    """Type definition for OGC feature collection of values."""

    metadata: NotRequired[_Metadata]


@dataclass(frozen=True)
class ValuesResult(_ValuesResult[list[_ValuesItemDict] | list[_ValuesWideItemDict], _ValuesDict]):
    """Result class for values."""

    stations: StationsResult
    df: pl.DataFrame

    def to_ogc_feature_collection(
        self, *, with_metadata: bool = False, **_kwargs: object
    ) -> _ValuesOgcFeatureCollection:
        """Format values as OGC feature collection."""
        # The stations frame holds one row per resolution, dataset and station, so a feature is one
        # dataset of one station and carries that dataset's values only, save in a resolution the
        # wide shape merged several datasets into, which is one feature per station (see below).
        values_by_series = {
            key: df.drop("station_id")
            for key, df in self.df.partition_by(
                ["resolution", "dataset", "station_id"], as_dict=True, maintain_order=True
            ).items()
        }
        # cut down to the stations that returned values before walking the rows: a ranked request
        # keeps every station with a position in the stations frame (see TimeseriesRequest.filter_by_rank)
        df_stations = self.stations.df.join(
            self.df.select("resolution", "station_id").unique(),
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
        features: list[_ValuesOgcFeature] = []
        for station in timestamps_to_string(df_stations, ["start_timestamp", "end_timestamp"]).iter_rows(named=True):
            df_values = values_by_series.get((station["resolution"], station["dataset"], station["station_id"]))
            if df_values is None:
                continue
            feature = self.stations._to_ogc_feature(station, extra_columns)  # noqa: SLF001
            # the frame lost its station_id above, so a row is the feature's own kind
            values = cast("list[_ValuesOgcItemDict] | list[_ValuesWideOgcItemDict]", self._to_dict(df_values))
            features.append(
                {
                    "type": feature["type"],
                    "properties": feature["properties"],
                    "geometry": feature["geometry"],
                    "values": values,
                }
            )
        collection: _ValuesOgcFeatureCollectionData = {"type": "FeatureCollection", "features": features}
        if with_metadata:
            return {"metadata": self.stations.get_metadata(), "data": collection}
        return {"data": collection}

    def to_plot(self, **_kwargs: object) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        px = import_optional("plotly.express", "Plotting", extra="plotting")
        go = import_optional("plotly.graph_objects", "Plotting", extra="plotting")

        df = self.df
        if "parameter" not in df.columns:
            df = self._lengthen(df)
        if df.is_empty():
            return go.Figure()
        # create unit mapping for title
        units = self._unit_symbols()
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
        flags columns are not drawn.

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
            and not (column.endswith("_quality_flags") and column.removesuffix("_quality_flags") in df.columns)
        ]
        series = []
        for (resolution,), df_resolution in df.group_by("resolution", maintain_order=True):
            for column in columns:
                dataset = pl.col("dataset")
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
                        pl.col("station_id"),
                        pl.col("resolution"),
                        dataset.alias("dataset"),
                        pl.lit(parameter).alias("parameter"),
                        pl.col("timestamp"),
                        pl.col(column).cast(pl.Float64).alias("value"),
                    )
                )
        if not series:
            return pl.DataFrame()
        # the stations in the order they come in, and stable, so that a series keeps its timestamps' order
        stations = pl.Enum(df.get_column("station_id").unique(maintain_order=True))
        return pl.concat(series).sort(
            pl.col("station_id").cast(stations), "resolution", "dataset", "parameter", maintain_order=True
        )

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        max_side: int | None = None,
        **kwargs: object,
    ) -> bytes | str:
        """Create an image from the plotly figure.

        This method is used by ``.to_image()`` to create an image for values from the plotly figure.
        """
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            check_image_size(fig, width, height, scale, max_side)
            require_kaleido()
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            msg = f"Invalid format: {fmt}"
            raise KeyError(msg)
        return img


class _HistoryDict(TypedDict):
    """Type definition for the dictionary of station histories."""

    metadata: NotRequired[_Metadata]
    stations: NotRequired[list[_Station]]
    # one history per station and dataset, each as the `History` model dumps it, its timestamps as text
    histories: list[dict[str, typing.Any]]


# `station_id`, `resolution` and `dataset` say which station and dataset a history belongs to; they are
# not sections of it and are always kept
_HISTORY_IDENTIFIERS = frozenset({"station_id", "resolution", "dataset"})


def select_history_sections(
    history: Mapping[str, typing.Any], sections: AbstractSet[str] | None
) -> dict[str, typing.Any]:
    """Keep the requested sections of a dumped station history, all of them when none are requested.

    In the history's own field order rather than the order of `sections`, which is a set, so the
    same request always answers the same document. `station_id`, `resolution` and `dataset` say
    which station and dataset the history belongs to, are not sections and are always kept.
    """
    if not sections:
        return dict(history)
    return {key: value for key, value in history.items() if key in _HISTORY_IDENTIFIERS or key in sections}


def _written_timestamps(value: typing.Any) -> typing.Any:  # noqa: ANN401
    """Give a dumped history with its datetimes written in the one format of the library."""
    if isinstance(value, datetime):
        return format_timestamp(value)
    if isinstance(value, dict):
        return {key: _written_timestamps(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_written_timestamps(item) for item in value]
    return value


def history_to_dict(
    stations: StationsResult,
    histories: Iterable[History],
    *,
    with_metadata: bool = False,
    with_stations: bool = False,
    sections: AbstractSet[str] | None = None,
) -> _HistoryDict:
    """Format station histories as one dictionary, which is the body REST and the CLI answer with."""
    # assembled key by key, as the keys come in this order and two of them are optional
    data: dict[str, object] = {}
    if with_metadata:
        data["metadata"] = stations.get_metadata()
    if with_stations:
        data["stations"] = stations.to_dict(with_metadata=False)["stations"]
    data["histories"] = [
        select_history_sections(_written_timestamps(history.model_dump(mode="python")), sections)
        for history in histories
    ]
    return cast("_HistoryDict", data)


def history_to_json(
    stations: StationsResult,
    histories: Iterable[History],
    *,
    with_metadata: bool = False,
    with_stations: bool = False,
    sections: AbstractSet[str] | None = None,
    indent: int | bool | None = 4,
) -> str:
    """Format station histories as JSON, as `history_to_dict` has them."""
    if indent is True:
        indent = 4
    elif indent is False:
        indent = None
    data = history_to_dict(
        stations, histories, with_metadata=with_metadata, with_stations=with_stations, sections=sections
    )
    return json.dumps(data, indent=indent)


@dataclass(frozen=True)
class HistoryResult:
    """Result class for history data: how one station and dataset changed over time."""

    stations: StationsResult
    history: History

    def to_dict(
        self,
        *,
        with_metadata: bool = False,
        with_stations: bool = False,
        sections: AbstractSet[str] | None = None,
    ) -> _HistoryDict:
        """Format the history as dictionary, with the one history under `histories`.

        Args:
            with_metadata: whether to include metadata about the provider and producer
            with_stations: whether to include the stations of the request
            sections: the sections of the history to keep (name, parameter, device, geography,
                missing_data), all of them when not given

        Returns:
            Dictionary with the history, its timestamps as text in the format of the other results.

        """
        return history_to_dict(
            self.stations,
            [self.history],
            with_metadata=with_metadata,
            with_stations=with_stations,
            sections=sections,
        )

    def to_json(
        self,
        *,
        with_metadata: bool = False,
        with_stations: bool = False,
        sections: AbstractSet[str] | None = None,
        indent: int | bool | None = 4,
    ) -> str:
        """Format the history as JSON, as `to_dict` has it."""
        return history_to_json(
            self.stations,
            [self.history],
            with_metadata=with_metadata,
            with_stations=with_stations,
            sections=sections,
            indent=indent,
        )


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


class _InterpolatedValuesDictBody(TypedDict):
    """The members of `_InterpolatedValuesDict` other than `metadata`."""

    stations: NotRequired[list[_Station]]
    values: list[_InterpolatedValuesItemDict]


class _InterpolatedValuesDict(_InterpolatedValuesDictBody):
    """Type definition for dictionary of interpolated values."""

    metadata: NotRequired[_Metadata]


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


class _InterpolatedValuesOgcFeatureCollectionBody(TypedDict):
    """The members of `_InterpolatedValuesOgcFeatureCollection` other than `metadata`."""

    data: _InterpolatedValuesOgcFeatureCollectionData


class _InterpolatedValuesOgcFeatureCollection(_InterpolatedValuesOgcFeatureCollectionBody):
    """Type definition for OGC feature collection of interpolated values."""

    metadata: NotRequired[_Metadata]


@dataclass(frozen=True)
class InterpolatedValuesResult(_ValuesResult[list[_InterpolatedValuesItemDict], _InterpolatedValuesDict]):
    """Result class for interpolated values."""

    stations: StationsResult
    df: pl.DataFrame
    latlon: tuple[float, float]
    elevation: float | None = None

    @property
    def df_stations(self) -> pl.DataFrame:
        """Get the stations the values were interpolated from, which `stations` is already cut down to."""
        return self.stations.df

    def to_ogc_feature_collection(
        self,
        *,
        with_metadata: bool = False,
        **_kwargs: object,
    ) -> _InterpolatedValuesOgcFeatureCollection:
        """Format interpolated values as OGC feature collection."""
        latitude, longitude = self.latlon
        name = f"interpolation({latitude:.4f},{longitude:.4f})"
        if self.elevation is not None:
            name = f"interpolation({latitude:.4f},{longitude:.4f},{self.elevation:.1f}m)"
        feature: _InterpolatedValuesOgcFeature = {
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
        collection: _InterpolatedValuesOgcFeatureCollectionData = {"type": "FeatureCollection", "features": [feature]}
        if with_metadata:
            return {"metadata": self.stations.get_metadata(), "data": collection}
        return {"data": collection}

    def to_plot(self, **_kwargs: object) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        px = import_optional("plotly.express", "Plotting", extra="plotting")
        go = import_optional("plotly.graph_objects", "Plotting", extra="plotting")

        df = self.df
        if df.is_empty():
            return go.Figure()
        # create unit mapping for title
        units = self._unit_symbols()
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

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        max_side: int | None = None,
        **kwargs: object,
    ) -> bytes | str:
        """Create an image from the plotly figure.

        This method is used by ``.to_image()`` to create an image for interpolated values from the plotly figure.
        """
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            check_image_size(fig, width, height, scale, max_side)
            require_kaleido()
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


class _SummarizedValuesDictBody(TypedDict):
    """The members of `_SummarizedValuesDict` other than `metadata`."""

    stations: NotRequired[list[_Station]]
    values: list[_SummarizedValuesItemDict]


class _SummarizedValuesDict(_SummarizedValuesDictBody):
    """Format summarized values as dictionary."""

    metadata: NotRequired[_Metadata]


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


class _SummarizedValuesOgcFeatureCollectionBody(TypedDict):
    """The members of `_SummarizedValuesOgcFeatureCollection` other than `metadata`."""

    data: _SummarizedValuesOgcFeatureCollectionData


class _SummarizedValuesOgcFeatureCollection(_SummarizedValuesOgcFeatureCollectionBody):
    """Format summarized values as OGC feature collection."""

    metadata: NotRequired[_Metadata]


@dataclass(frozen=True)
class SummarizedValuesResult(_ValuesResult[list[_SummarizedValuesItemDict], _SummarizedValuesDict]):
    """Calculate summary of stations and parameters."""

    stations: StationsResult
    df: pl.DataFrame
    latlon: tuple[float, float]
    elevation: float | None = None

    @property
    def df_stations(self) -> pl.DataFrame:
        """Get the stations the values were summarized from, which `stations` is already cut down to."""
        return self.stations.df

    def to_ogc_feature_collection(
        self,
        *,
        with_metadata: bool = False,
        **_kwargs: object,
    ) -> _SummarizedValuesOgcFeatureCollection:
        """Export summarized values as OGC feature collection."""
        latitude, longitude = self.latlon
        name = f"summary({latitude:.4f},{longitude:.4f})"
        if self.elevation is not None:
            name = f"summary({latitude:.4f},{longitude:.4f},{self.elevation:.1f}m)"
        feature: _SummarizedValuesOgcFeature = {
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
        collection: _SummarizedValuesOgcFeatureCollectionData = {"type": "FeatureCollection", "features": [feature]}
        if with_metadata:
            return {"metadata": self.stations.get_metadata(), "data": collection}
        return {"data": collection}

    def to_plot(self, **_kwargs: object) -> go.Figure:
        """Create a plotly figure from the values DataFrame."""
        px = import_optional("plotly.express", "Plotting", extra="plotting")
        go = import_optional("plotly.graph_objects", "Plotting", extra="plotting")

        df = self.df
        if df.is_empty():
            return go.Figure()
        # create unit mapping for title
        units = self._unit_symbols()
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

    def _to_image(
        self,
        fmt: Literal["html", "png", "jpg", "webp", "svg", "pdf"],
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        max_side: int | None = None,
        **kwargs: object,
    ) -> bytes | str:
        """Create an image from the plotly figure.

        This method is used by ``.to_image()`` to create an image for summarized values from the plotly figure.
        """
        fig = self.to_plot(**kwargs)
        if fmt == "html":
            img = fig.to_html()
        elif fmt in ("png", "jpg", "webp", "svg", "pdf"):
            check_image_size(fig, width, height, scale, max_side)
            require_kaleido()
            img = fig.to_image(format=fmt, width=width, height=height, scale=scale)
        else:
            msg = f"Invalid format: {fmt}"
            raise KeyError(msg)
        return img
