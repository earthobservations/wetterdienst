# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core UI utilities for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import sys
from typing import TYPE_CHECKING, Literal

import polars as pl
from pydantic import BaseModel, confloat, conint, field_validator

from wetterdienst.exceptions import InvalidTimeIntervalError, StartDateEndDateError
from wetterdienst.metadata.period import Period
from wetterdienst.model.metadata import parse_parameters
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.util.datetime import parse_date
from wetterdienst.util.ui import read_list

if TYPE_CHECKING:
    import plotly.graph_objs as go

    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import (
        InterpolatedValuesResult,
        StationsResult,
        SummarizedValuesResult,
        ValuesResult,
    )
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


class StationsRequest(BaseModel):
    """Stations request with validated parameters."""

    model_config = {"extra": "forbid"}

    provider: str
    network: str
    parameters: list[str]

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    periods: list[str] | None = None

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v: str | list | None) -> list[str] | None:
        """Validate periods."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v, separator=",")
        periods = []
        for item in v:
            if "," in item:
                periods.extend(read_list(item, separator=","))
            else:
                periods.append(item)
        return periods

    # Mosmix/DMO
    lead_time: Literal["short", "long"] | None = None
    issue: str | None = None

    # station filter parameters
    all: bool | None = False
    # station ids
    station: list[str] | None = None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v: str | list | None) -> list[str] | None:
        """Validate station."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v)
        stations = []
        for item in v:
            if "," in item:
                stations.extend(read_list(item, separator=","))
            else:
                stations.append(item)
        return stations

    # station name
    name: str | None = None
    # latlon
    latitude: confloat(ge=-90, le=90) | None = None
    longitude: confloat(ge=-180, le=180) | None = None
    rank: conint(ge=1) | None = None
    distance: confloat(ge=0) | None = None
    # bbox
    left: confloat(ge=-180, le=180) | None = None
    bottom: confloat(ge=-90, le=90) | None = None
    right: confloat(ge=-180, le=180) | None = None
    top: confloat(ge=-90, le=90) | None = None
    # sql
    sql: str | None = None

    with_metadata: bool = True
    with_stations: bool = True

    format: Literal["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"] = "json"
    pretty: bool = False
    debug: bool = False

    # plot settings
    width: conint(gt=0) | None = None
    height: conint(gt=0) | None = None
    scale: confloat(gt=0) | None = None


class ValuesRequest(BaseModel):
    """Values request with validated parameters."""

    model_config = {"extra": "forbid"}

    # from stations
    provider: str
    network: str
    parameters: list[str]

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    periods: list[str] | None = None

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v: str | list | None) -> list[str] | None:
        """Validate periods."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v, separator=",")
        periods = []
        for item in v:
            if "," in item:
                periods.extend(read_list(item, separator=","))
            else:
                periods.append(item)
        return periods

    # Mosmix/DMO
    lead_time: Literal["short", "long"] | None = None
    issue: str | None = None

    # station filter parameters
    all: bool | None = False
    # station ids
    station: list[str] | None = None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v: str | list | None) -> list[str] | None:
        """Validate station."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v)
        stations = []
        for item in v:
            if "," in item:
                stations.extend(read_list(item, separator=","))
            else:
                stations.append(item)
        return stations

    # station name
    name: str | None = None
    # latlon
    latitude: confloat(ge=-90, le=90) | None = None
    longitude: confloat(ge=-180, le=180) | None = None
    rank: conint(ge=1) | None = None
    distance: confloat(ge=0) | None = None
    # bbox
    left: confloat(ge=-180, le=180) | None = None
    bottom: confloat(ge=-90, le=90) | None = None
    right: confloat(ge=-180, le=180) | None = None
    top: confloat(ge=-90, le=90) | None = None
    # sql
    sql: str | None = None

    with_metadata: bool = True
    with_stations: bool = True

    format: Literal["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"] = "json"
    pretty: bool = False
    debug: bool = False

    # plot settings
    width: conint(gt=0) | None = None
    height: conint(gt=0) | None = None
    scale: confloat(gt=0) | None = None

    # values
    date: str | None = None
    sql_values: str | None = None
    humanize: bool = True
    shape: Literal["long", "wide"] = "long"
    convert_units: bool = True
    unit_targets: dict[str, str] | None = None
    skip_empty: bool = False
    skip_threshold: confloat(ge=0, le=1) = 0.95
    skip_criteria: Literal["min", "mean", "max"] = "min"
    drop_nulls: bool = True

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v: str | dict | None) -> dict[str, str] | None:
        """Validate unit targets."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return json.loads(v)


class InterpolationRequest(BaseModel):
    """Interpolation request with validated parameters."""

    model_config = {"extra": "forbid"}

    provider: str
    network: str
    parameters: list[str]

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    periods: list[str] | None = None

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v: str | list | None) -> list[str] | None:
        """Validate periods."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v, separator=",")
        periods = []
        for item in v:
            if "," in item:
                periods.extend(read_list(item, separator=","))
            else:
                periods.append(item)
        return periods

    date: str

    # Mosmix/DMO
    lead_time: Literal["short", "long"] | None = None
    issue: str | None = None

    # station filter parameters
    station: str | None = None
    # latlon
    latitude: confloat(ge=-90, le=90) | None = None
    longitude: confloat(ge=-180, le=180) | None = None
    # sql
    sql_values: str | None = None
    humanize: bool = True
    convert_units: bool = True
    unit_targets: dict[str, str] | None = None

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v: str | None) -> dict[str, str] | None:
        """Validate unit targets."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return json.loads(v)

    interpolation_station_distance: dict[str, confloat(ge=0.0)] | None = None

    @field_validator("interpolation_station_distance", mode="before")
    @classmethod
    def validate_interpolation_station_distance(cls, v: str | None) -> dict[str, float] | None:
        """Validate interpolation station distance."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return json.loads(v)

    use_nearby_station_distance: confloat(ge=0) = 1.0
    format: Literal["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"] = "json"

    with_metadata: bool = True
    with_stations: bool = True

    pretty: bool = False
    debug: bool = False

    # plot settings
    width: conint(gt=0) | None = None
    height: conint(gt=0) | None = None
    scale: confloat(gt=0) | None = None


class SummaryRequest(BaseModel):
    """Summary request with validated parameters."""

    model_config = {"extra": "forbid"}

    provider: str
    network: str
    parameters: list[str]

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    periods: list[str] | None = None

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v: str | list | None) -> list[str] | None:
        """Validate periods."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v, separator=",")
        periods = []
        for item in v:
            if "," in item:
                periods.extend(read_list(item, separator=","))
            else:
                periods.append(item)
        return periods

    date: str

    # Mosmix/DMO
    lead_time: Literal["short", "long"] | None = None
    issue: str | None = None

    # station filter parameters
    station: str | None = None
    # latlon
    latitude: confloat(ge=-90, le=90) | None = None
    longitude: confloat(ge=-180, le=180) | None = None
    # sql
    sql_values: str | None = None
    humanize: bool = True
    convert_units: bool = True
    unit_targets: dict[str, str] | None = None

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v: str | None) -> dict[str, str] | None:
        """Validate unit targets."""
        if not v:
            return None
        return json.loads(v)

    format: Literal["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"] = "json"

    with_metadata: bool = True
    with_stations: bool = True

    pretty: bool = False
    debug: bool = False

    # plot settings
    width: conint(gt=0) | None = None
    height: conint(gt=0) | None = None
    scale: confloat(gt=0) | None = None


def _get_stations_request(
    api: type[TimeseriesRequest],
    request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest,
    date: str | None,
    settings: Settings,
) -> TimeseriesRequest:
    """Create a request object for stations."""
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest  # noqa: PLC0415

    # TODO: move this into Request core
    start_date, end_date = None, None
    if date:
        if "/" in date:
            if date.count("/") >= 2:
                msg = "Invalid ISO 8601 time interval"
                raise InvalidTimeIntervalError(msg)
            start_date, end_date = date.split("/")
            start_date = parse_date(start_date)
            end_date = parse_date(end_date)
        else:
            start_date = parse_date(date)

    parameters = parse_parameters(request.parameters, api.metadata)

    any_date_required = any(parameter.dataset.date_required for parameter in parameters)
    if any_date_required and (not start_date or not end_date):
        msg = "Start and end date required for single period datasets"
        raise StartDateEndDateError(msg)

    any_multiple_period_dataset = any(len(parameter.dataset.periods) > 1 for parameter in parameters)

    kwargs = {
        "parameters": parameters,
        "start_date": start_date,
        "end_date": end_date,
    }
    if any_multiple_period_dataset:
        kwargs["periods"] = request.periods

    if isinstance(api, DwdMosmixRequest):
        kwargs["issue"] = request.issue
    elif isinstance(api, DwdDmoRequest):
        kwargs["issue"] = request.issue
        kwargs["lead_time"] = request.lead_time

    return api(**kwargs, settings=settings)


def get_stations(
    api: type[TimeseriesRequest],
    request: StationsRequest | ValuesRequest | InterpolationRequest,
    date: str | None,
    settings: Settings,
) -> StationsResult:
    """Get stations based on request."""
    r = _get_stations_request(api=api, request=request, date=date, settings=settings)

    if request.all:
        return r.all()

    if request.station:
        return r.filter_by_station_id(request.station)

    if request.name:
        return r.filter_by_name(request.name)

    # Use coordinates twice in main if-elif to get same KeyError
    if request.latitude and request.longitude and request.rank:
        return r.filter_by_rank(
            latlon=(request.latitude, request.longitude),
            rank=request.rank,
        )

    if request.latitude and request.longitude and request.distance:
        return r.filter_by_distance(
            latlon=(request.latitude, request.longitude),
            distance=request.distance,
        )

    if request.left and request.bottom and request.right and request.top:
        return r.filter_by_bbox(
            left=request.left,
            bottom=request.bottom,
            right=request.right,
            top=request.top,
        )

    if request.sql:
        return r.filter_by_sql(request.sql)

    param_options = [
        "all (boolean)",
        "station (string)",
        "name (string)",
        "latitude (float), longitude (float) and rank (integer)",
        "latitude (float), longitude (float) and distance (float)",
        "left (float), bottom (float), right (float), top (float)",
    ]
    msg = f"Give one of the parameters: {', '.join(param_options)}"
    raise KeyError(msg)


def get_values(
    api: type[TimeseriesRequest],
    request: ValuesRequest,
    settings: Settings,
) -> ValuesResult:
    """Get values based on request."""
    stations_ = get_stations(
        api=api,
        request=request,
        date=request.date,
        settings=settings,
    )

    try:
        # TODO: Add stream-based processing here.
        values_ = stations_.values.all()
    except ValueError:
        log.exception("Error while fetching values")
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
            return values_

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_.filter_by_sql(request.sql_values)

    return values_


def get_interpolate(
    api: type[TimeseriesRequest],
    request: InterpolationRequest,
    settings: Settings,
) -> InterpolatedValuesResult:
    """Get interpolated values based on request."""
    r = _get_stations_request(api=api, request=request, date=request.date, settings=settings)

    if request.latitude and request.longitude:
        values_ = r.interpolate((request.latitude, request.longitude))
    elif request.station:
        values_ = r.interpolate_by_station_id(request.station)
    else:
        msg = "Either latitude and longitude or station must be provided"
        raise ValueError(msg)

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_.filter_by_sql(request.sql_values)

    return values_


def get_summarize(
    api: type[TimeseriesRequest],
    request: SummaryRequest,
    settings: Settings,
) -> SummarizedValuesResult:
    """Get summarized values based on request."""
    r = _get_stations_request(api=api, request=request, date=request.date, settings=settings)

    if request.latitude and request.longitude:
        values_ = r.summarize((request.latitude, request.longitude))
    elif request.station:
        values_ = r.summarize_by_station_id(request.station)
    else:
        msg = "Either latitude and longitude or station must be provided"
        raise ValueError(msg)

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_.filter_by_sql(request.sql_values)

    return values_


def _get_stripes_temperature_request(periods: Period = Period.HISTORICAL) -> DwdObservationRequest:
    """Need this for displaying stations in the interactive app."""
    return DwdObservationRequest(
        parameters=[("annual", "climate_summary", "temperature_air_mean_2m")],
        periods=periods,
    )


def _get_stripes_precipitation_request(periods: Period = Period.HISTORICAL) -> DwdObservationRequest:
    """Need this for displaying stations in the interactive app."""
    return DwdObservationRequest(
        parameters=[("annual", "precipitation_more", "precipitation_height")],
        periods=periods,
    )


CLIMATE_STRIPES_CONFIG = {
    "temperature": {
        "request": _get_stripes_temperature_request,
        "color_map": "RdBu",
    },
    "precipitation": {
        "request": _get_stripes_precipitation_request,
        "color_map": "BrBG",
    },
}


def _get_stripes_stations(kind: Literal["temperature", "precipitation"], *, active: bool = True) -> StationsResult:
    request = CLIMATE_STRIPES_CONFIG[kind]["request"]
    stations = request(periods=Period.HISTORICAL).all()
    if active:
        station_ids_active = request(periods=Period.RECENT).all().df.select("station_id")
        stations.df = stations.df.join(station_ids_active, on="station_id")
    return stations


def _plot_stripes(  # noqa: C901
    kind: Literal["temperature", "precipitation"],
    station_id: str | None = None,
    name: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    name_threshold: float = 0.9,
    *,
    show_title: bool = True,
    show_years: bool = True,
    show_data_availability: bool = True,
) -> go.Figure:
    """Create warming stripes for station in Germany.

    Code similar to: https://www.s4f-freiburg.de/temperaturstreifen/
    """
    if kind not in ["temperature", "precipitation"]:
        msg = "kind must be either 'temperature' or 'precipitation'"
        raise ValueError(msg)
    if start_year and end_year and start_year >= end_year:
        msg = "start_year must be less than end_year"
        raise ValueError(msg)
    if name_threshold < 0 or name_threshold > 1:
        msg = "name_threshold must be between 0.0 and 1.0"
        raise ValueError(msg)

    import plotly.graph_objects as go  # noqa: PLC0415

    request = CLIMATE_STRIPES_CONFIG[kind]["request"]()
    cmap = CLIMATE_STRIPES_CONFIG[kind]["color_map"]

    if station_id:
        stations = request.filter_by_station_id(station_id)
    elif name:
        stations = request.filter_by_name(name, threshold=name_threshold)
    else:
        param_options = [
            "station (string)",
            "name (string)",
        ]
        msg = f"Give one of the parameters: {', '.join(param_options)}"
        raise KeyError(msg)

    try:
        station_dict = stations.to_dict()["stations"][0]
    except IndexError as e:
        parameter = "station_id" if station_id else "name"
        msg = f"No station with a {parameter} similar to '{station_id or name}' found"
        raise ValueError(msg) from e

    df = stations.values.all().df.sort("date")
    df = df.set_sorted("date")
    df = df.select("date", "value")
    df = df.upsample("date", every="1y")
    df = df.with_columns(
        (1 - (pl.col("value") - pl.col("value").min()) / (pl.col("value").max() - pl.col("value").min())).alias(
            "value_scaled",
        ),
        pl.when(pl.col("value").is_not_null()).then(-0.02).otherwise(None).alias("availability"),
    )

    if start_year:
        df = df.filter(pl.col("date").dt.year().ge(start_year))
    if end_year:
        df = df.filter(pl.col("date").dt.year().le(end_year))

    if len(df) == 1:
        msg = "At least two years are required to create warming stripes."
        raise ValueError(msg)

    df_without_nulls = df.drop_nulls("value")

    fig = go.Figure()

    # Add bar trace
    fig.add_trace(
        go.Bar(
            x=df_without_nulls.get_column("date").dt.year(),
            y=[1.0] * len(df_without_nulls),
            marker={"color": df_without_nulls.get_column("value_scaled"), "colorscale": cmap, "cmin": 0, "cmax": 1},
            width=1.0,
        ),
    )

    # Add scatter trace for data availability
    if show_data_availability:
        fig.add_trace(
            go.Scatter(
                x=df.get_column("date").dt.year(),
                y=df.get_column("availability"),
                mode="lines",
                marker={"color": "gold", "size": 5},
                line={"color": "gold"},
            ),
        )
        fig.add_annotation(
            x=df.get_column("date").dt.year().min(),
            xanchor="left",
            y=-0.05,
            text="data availability",
            showarrow=False,
            align="right",
            font={"color": "gold"},
        )
    # Add source text
    fig.add_annotation(
        x=0.5,
        y=-0.05,
        text="Source: Deutscher Wetterdienst",
        showarrow=False,
        xref="paper",
        yref="paper",
    )
    if show_title:
        fig.update_layout(
            title=f"Climate stripes ({kind}) for {station_dict['name']}, Germany ({station_dict['station_id']})",
        )
    if show_years:
        fig.add_annotation(
            x=0.05,
            y=-0.05,
            text=str(df.get_column("date").min().year),
            showarrow=False,
            xref="paper",
            yref="paper",
            xanchor="right",
        )
        fig.add_annotation(
            x=0.95,
            y=-0.05,
            text=str(df.get_column("date").max().year),
            showarrow=False,
            xref="paper",
            yref="paper",
            xanchor="left",
        )
    fig.update_layout(
        plot_bgcolor="white",
        xaxis={
            "showticklabels": False,
        },
        yaxis={"range": [None, 1], "showticklabels": False},
        showlegend=False,
        margin={"l": 10, "r": 10, "t": 30, "b": 30},
    )
    return fig


def set_logging_level(*, debug: bool) -> None:
    """Set logging level for the wetterdienst package."""
    log_level = logging.INFO

    if debug:
        log_level = logging.DEBUG

    log.setLevel(log_level)
