# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import json
import logging
import sys
from typing import TYPE_CHECKING, Literal

import polars as pl
from pydantic import BaseModel, Field, confloat, conint, field_validator

from wetterdienst.core.timeseries.metadata import parse_parameters
from wetterdienst.exceptions import InvalidTimeIntervalError, StartDateEndDateError
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.util.datetime import parse_date
from wetterdienst.util.ui import read_list

if TYPE_CHECKING:
    from plotly.graph_objs import Figure

    from wetterdienst.core.timeseries.request import TimeseriesRequest
    from wetterdienst.core.timeseries.result import (
        InterpolatedValuesResult,
        StationsResult,
        SummarizedValuesResult,
        ValuesResult,
    )
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


# only used by restapi for raw type hints
class StationsRequestRaw(BaseModel):
    provider: str
    network: str
    parameters: str
    periods: str | None = None

    # Mosmix/DMO
    lead_time: Literal["short", "long"] | None = None
    issue: str | None = None

    # station filter parameters
    all: bool | None = False
    station: str | None = Field(default=None)
    name: str | None = None
    coordinates: str | None = None
    rank: int | None = Field(default=None, ge=1)
    distance: float | None = Field(default=None, ge=0)
    bbox: str | None = None
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


class StationsRequest(StationsRequestRaw):
    parameters: list[str]
    periods: list[str] | None = None
    # comma separated list parameters
    station: list[str] | None = None
    coordinates: tuple[confloat(ge=-90, le=90), confloat(ge=-180, le=180)] | None = None
    bbox: (
        tuple[confloat(ge=-180, le=180), confloat(ge=-90, le=90), confloat(ge=-180, le=180), confloat(ge=-90, le=90)]
        | None
    ) = None

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v):
        return read_list(v)

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coordinates(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("bbox", mode="before")
    @classmethod
    def validate_bbox(cls, v):
        if v:
            return read_list(v)
        return None


class ValuesRequestRaw(StationsRequestRaw):
    format: Literal["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"] = "json"

    date: str | None = None
    sql_values: str | None = None
    humanize: bool = True
    shape: Literal["long", "wide"] = "long"
    convert_units: bool = True
    unit_targets: str | None = None
    skip_empty: bool = False
    skip_threshold: confloat(gt=0, le=1) = 0.95
    skip_criteria: Literal["min", "mean", "max"] = "min"
    drop_nulls: bool = True
    # plot settings
    width: conint(gt=0) | None = None
    height: conint(gt=0) | None = None
    scale: confloat(gt=0) | None = None


class ValuesRequest(ValuesRequestRaw):
    parameters: list[str]
    periods: list[str] | None = None
    # comma separated list parameters
    station: list[str] | None = None
    coordinates: tuple[confloat(ge=-90, le=90), confloat(ge=-180, le=180)] | None = None
    bbox: (
        tuple[confloat(ge=-180, le=180), confloat(ge=-90, le=90), confloat(ge=-180, le=180), confloat(ge=-90, le=90)]
        | None
    ) = None
    unit_targets: dict[str, str] | None = None

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v):
        return read_list(v)

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coordinates(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("bbox", mode="before")
    @classmethod
    def validate_bbox(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v):
        if v:
            return json.loads(v)
        return None


# start from scratch as parameters are different
class InterpolationRequestRaw(BaseModel):
    provider: str
    network: str
    parameters: str
    periods: str | None = None

    date: str

    # Mosmix/DMO
    lead_time: Literal["short", "long"] | None = None
    issue: str | None = None

    # station filter parameters
    station: str | None = Field(default=None)
    coordinates: str | None = None

    sql_values: str | None = None
    humanize: bool = True
    convert_units: bool = True
    unit_targets: str | None = None
    interpolation_station_distance: str | None = None
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


class InterpolationRequest(InterpolationRequestRaw):
    parameters: list[str]
    periods: list[str] | None = None
    # comma separated list parameters
    station: list[str] | None = None
    coordinates: tuple[confloat(ge=-90, le=90), confloat(ge=-180, le=180)] | None = None
    unit_targets: dict[str, str] | None = None
    interpolation_station_distance: dict[str, confloat(ge=0)] | None = None

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v):
        return read_list(v)

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coordinates(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v):
        if v:
            return json.loads(v)
        return None

    @field_validator("interpolation_station_distance", mode="before")
    @classmethod
    def validate_interpolation_station_distance(cls, v):
        if v:
            return json.loads(v)
        return None


class SummaryRequestRaw(BaseModel):
    provider: str
    network: str
    parameters: str
    periods: str | None = None

    date: str

    # Mosmix/DMO
    lead_time: Literal["short", "long"] | None = None
    issue: str | None = None

    # station filter parameters
    station: str | None = Field(default=None)
    coordinates: str | None = None

    sql_values: str | None = None
    humanize: bool = True
    convert_units: bool = True
    unit_targets: str | None = None
    format: Literal["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"] = "json"

    with_metadata: bool = True
    with_stations: bool = True

    pretty: bool = False
    debug: bool = False

    # plot settings
    width: conint(gt=0) | None = None
    height: conint(gt=0) | None = None
    scale: confloat(gt=0) | None = None


class SummaryRequest(SummaryRequestRaw):
    parameters: list[str]
    periods: list[str] | None = None
    # comma separated list parameters
    station: list[str] | None = None
    coordinates: tuple[confloat(ge=-90, le=90), confloat(ge=-180, le=180)] | None = None
    unit_targets: dict[str, str] | None = None

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v):
        return read_list(v)

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("coordinates", mode="before")
    @classmethod
    def validate_coordinates(cls, v):
        if v:
            return read_list(v)
        return None

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v):
        if v:
            return json.loads(v)
        return None


def unpack_parameters(parameter: str) -> list[str]:
    """Parse parameters to either
    - list of str, each representing a parameter or
    - list of tuple of str representing a pair of parameter and dataset
    e.g.
       "precipitation_height,temperature_air_2m" ->
           ["precipitation_height", "temperature_air_2m"]

       "precipitation_height/precipitation_more,temperature_air_2m/kl" ->
           [("precipitation_height", "precipitation_more"), ("temperature_air_2m", "kl")]

    """

    def unpack_parameter(par: str) -> str | tuple[str, str]:
        try:
            parameter_, dataset_ = par.split("/")
        except ValueError:
            return par

        return parameter_, dataset_

    # Create list of parameters from string if required
    try:
        parameter = parameter.split(",")
    except AttributeError:
        pass

    return [unpack_parameter(p) for p in parameter]


def _get_stations_request(
    api,
    request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest,
    date: str | None,
    settings: Settings,
):
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

    # TODO: move this into Request core
    start_date, end_date = None, None
    if date:
        if "/" in date:
            if date.count("/") >= 2:
                raise InvalidTimeIntervalError("Invalid ISO 8601 time interval")
            start_date, end_date = date.split("/")
            start_date = parse_date(start_date)
            end_date = parse_date(end_date)
        else:
            start_date = parse_date(date)

    parameters = parse_parameters(request.parameters, api.metadata)

    any_date_required = any(parameter.dataset.date_required for parameter in parameters)
    if any_date_required and (not start_date or not end_date):
        raise StartDateEndDateError("Start and end date required for single period datasets")

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
    api,
    request: StationsRequest | ValuesRequest | InterpolationRequest,
    date: str | None,
    settings,
) -> StationsResult:
    """Core function for querying stations via cli and restapi"""
    r = _get_stations_request(api=api, request=request, date=date, settings=settings)

    if request.all:
        return r.all()

    elif request.station:
        return r.filter_by_station_id(request.station)

    elif request.name:
        return r.filter_by_name(request.name)

    # Use coordinates twice in main if-elif to get same KeyError
    elif request.coordinates and request.rank:
        return r.filter_by_rank(
            latlon=request.coordinates,
            rank=request.rank,
        )

    elif request.coordinates and request.distance:
        return r.filter_by_distance(
            latlon=request.coordinates,
            distance=request.distance,
        )

    elif request.bbox:
        return r.filter_by_bbox(*request.bbox)

    elif request.sql:
        return r.filter_by_sql(request.sql)

    else:
        param_options = [
            "all (boolean)",
            "station (string)",
            "name (string)",
            "coordinates (float,float) and rank (integer)",
            "coordinates (float,float) and distance (float)",
            "bbox (left float, bottom float, right float, top float)",
        ]
        raise KeyError(f"Give one of the parameters: {', '.join(param_options)}")


def get_values(
    api: TimeseriesRequest,
    request: ValuesRequest,
    # date: str,
    # sql_values: str,
    settings: Settings,
) -> ValuesResult:
    """Core function for querying values via cli and restapi"""
    stations_ = get_stations(
        api=api,
        request=request,
        date=request.date,
        settings=settings,
    )

    try:
        # TODO: Add stream-based processing here.
        values_ = stations_.values.all()
    except ValueError as e:
        log.exception(e)
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
    api: TimeseriesRequest,
    request: InterpolationRequest,
    settings: Settings,
) -> InterpolatedValuesResult:
    """Core function for querying values via cli and restapi"""
    r = _get_stations_request(api=api, request=request, date=request.date, settings=settings)

    if request.coordinates:
        values_ = r.interpolate(request.coordinates)
    elif request.station:
        values_ = r.interpolate_by_station_id(request.station)
    else:
        raise ValueError("Either coordinates or station must be provided")

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_.filter_by_sql(request.sql_values)

    return values_


def get_summarize(
    api: TimeseriesRequest,
    request: SummaryRequest,
    settings: Settings,
) -> SummarizedValuesResult:
    """Core function for querying values via cli and restapi"""
    r = _get_stations_request(api=api, request=request, date=request.date, settings=settings)

    if request.coordinates:
        values_ = r.summarize(request.coordinates)
    elif request.station:
        values_ = r.summarize_by_station_id(request.station)
    else:
        raise ValueError("Either coordinates or station must be provided")

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_.filter_by_sql(request.sql_values)

    return values_


def _get_stripes_temperature_request(periods: Period = Period.HISTORICAL):
    """Need this for displaying stations in the interactive app."""
    return DwdObservationRequest(
        parameters=[("annual", "climate_summary", "temperature_air_mean_2m")],
        periods=periods,
    )


def _get_stripes_precipitation_request(periods: Period = Period.HISTORICAL):
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


def _get_stripes_stations(kind: Literal["temperature", "precipitation"], active: bool = True):
    request = CLIMATE_STRIPES_CONFIG[kind]["request"]
    stations = request(periods=Period.HISTORICAL).all()
    if active:
        station_ids_active = request(periods=Period.RECENT).all().df.select("station_id")
        stations.df = stations.df.join(station_ids_active, on="station_id")
    return stations


def _plot_stripes(
    kind: Literal["temperature", "precipitation"],
    station_id: str | None = None,
    name: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    name_threshold: float = 0.9,
    show_title: bool = True,
    show_years: bool = True,
    show_data_availability: bool = True,
) -> Figure:
    """Create warming stripes for station in Germany.
    Code similar to: https://www.s4f-freiburg.de/temperaturstreifen/
    """
    if kind not in ["temperature", "precipitation"]:
        raise ValueError("kind must be either 'temperature' or 'precipitation'")
    if start_year and end_year:
        if start_year >= end_year:
            raise ValueError("start_year must be less than end_year")
    if name_threshold < 0 or name_threshold > 1:
        raise ValueError("name_threshold must be between 0.0 and 1.0")

    import plotly.graph_objects as go

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
        raise KeyError(f"Give one of the parameters: {', '.join(param_options)}")

    try:
        station_dict = stations.to_dict()["stations"][0]
    except IndexError as e:
        parameter = "station_id" if station_id else "name"
        raise ValueError(f"No station with a {parameter} similar to '{station_id or name}' found") from e

    df = stations.values.all().df.sort("date")
    df = df.set_sorted("date")
    df = df.select("date", "value")
    df = df.upsample("date", every="1y")
    df = df.with_columns(
        (1 - (pl.col("value") - pl.col("value").min()) / (pl.col("value").max() - pl.col("value").min())).alias(
            "value_scaled"
        ),
        pl.when(pl.col("value").is_not_null()).then(-0.02).otherwise(None).alias("availability"),
    )

    if start_year:
        df = df.filter(pl.col("date").dt.year().ge(start_year))
    if end_year:
        df = df.filter(pl.col("date").dt.year().le(end_year))

    if len(df) == 1:
        raise ValueError("At least two years are required to create warming stripes.")

    df_without_nulls = df.drop_nulls("value")

    fig = go.Figure()

    # Add bar trace
    fig.add_trace(
        go.Bar(
            x=df_without_nulls.get_column("date").dt.year(),
            y=[1.0] * len(df_without_nulls),
            marker=dict(color=df_without_nulls.get_column("value_scaled"), colorscale=cmap, cmin=0, cmax=1),
            width=1.0,
        )
    )

    # Add scatter trace for data availability
    if show_data_availability:
        fig.add_trace(
            go.Scatter(
                x=df.get_column("date").dt.year(),
                y=df.get_column("availability"),
                mode="lines",
                marker=dict(color="gold", size=5),
                line=dict(color="gold"),
            )
        )
        fig.add_annotation(
            x=df.get_column("date").dt.year().min(),
            xanchor="left",
            y=-0.05,
            text="data availability",
            showarrow=False,
            align="right",
            font=dict(color="gold"),
        )
    # Add source text
    fig.add_annotation(
        x=0.5, y=-0.05, text="Source: Deutscher Wetterdienst", showarrow=False, xref="paper", yref="paper"
    )
    if show_title:
        fig.update_layout(
            title=f"Climate stripes ({kind}) for {station_dict['name']}, Germany ({station_dict['station_id']})"
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
        xaxis=dict(
            showticklabels=False,
        ),
        yaxis=dict(range=[None, 1], showticklabels=False),
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=30),
    )
    return fig


def set_logging_level(debug: bool):
    # Setup logging.
    log_level = logging.INFO

    if debug:  # pragma: no cover
        log_level = logging.DEBUG

    log.setLevel(log_level)
