# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import TYPE_CHECKING, Literal

import polars as pl

from wetterdienst.core.timeseries.metadata import parse_parameters
from wetterdienst.exceptions import InvalidTimeIntervalError, StartDateEndDateError
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.settings import Settings
from wetterdienst.util.datetime import parse_date

if TYPE_CHECKING:
    from wetterdienst.core.timeseries.request import TimeseriesRequest
    from wetterdienst.core.timeseries.result import (
        InterpolatedValuesResult,
        StationsResult,
        SummarizedValuesResult,
        ValuesResult,
    )

log = logging.getLogger(__name__)


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
    parameters: list[str],
    periods: list[str],
    lead_time: str,
    date: str | None,
    issue: str,
    si_units: bool,
    shape: Literal["long", "wide"],
    humanize: bool,
    skip_empty: bool,
    skip_threshold: float,
    skip_criteria: Literal["min", "mean", "max"],
    dropna: bool,
    use_nearby_station_distance: float,
):
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

    settings = Settings(
        ts_si_units=si_units,
        ts_shape=shape,
        ts_humanize=humanize,
        ts_skip_empty=skip_empty,
        ts_skip_criteria=skip_criteria,
        ts_skip_threshold=skip_threshold,
        ts_dropna=dropna,
        ts_interpolation_use_nearby_station_distance=use_nearby_station_distance,
    )

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

    parameters = parse_parameters(parameters, api.metadata)

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
        kwargs["periods"] = periods

    if isinstance(api, DwdMosmixRequest):
        kwargs["issue"] = issue
    elif isinstance(api, DwdDmoRequest):
        kwargs["issue"] = issue
        kwargs["lead_time"] = lead_time

    return api(**kwargs, settings=settings)


def get_stations(
    api,
    parameters: list[str],
    periods: list[str],
    lead_time: str,
    date: str | None,
    issue: str | None,
    all_: bool,
    station_id: list[str],
    name: str,
    coordinates: str,
    rank: int,
    distance: float,
    bbox: str,
    sql: str,
    si_units: bool,
    shape: Literal["wide", "long"],
    humanize: bool,
    skip_empty: bool,
    skip_threshold: float,
    skip_criteria: Literal["min", "mean", "max"],
    dropna: bool,
) -> StationsResult:
    """Core function for querying stations via cli and restapi"""
    r = _get_stations_request(
        api=api,
        parameters=parameters,
        periods=periods,
        lead_time=lead_time,
        date=date,
        issue=issue,
        si_units=si_units,
        shape=shape,
        humanize=humanize,
        skip_empty=skip_empty,
        skip_threshold=skip_threshold,
        skip_criteria=skip_criteria,
        dropna=dropna,
        use_nearby_station_distance=0,
    )

    if all_:
        return r.all()

    elif station_id:
        return r.filter_by_station_id(station_id)

    elif name:
        return r.filter_by_name(name)

    # Use coordinates twice in main if-elif to get same KeyError
    elif coordinates and rank:
        lat, lon = coordinates.split(",")

        return r.filter_by_rank(
            latlon=(float(lat), float(lon)),
            rank=rank,
        )

    elif coordinates and distance:
        lat, lon = coordinates.split(",")

        return r.filter_by_distance(
            latlon=(float(lat), float(lon)),
            distance=distance,
        )

    elif bbox:
        try:
            left, bottom, right, top = bbox.split(",")
        except ValueError as e:
            raise ValueError("bbox requires four floats separated by comma") from e

        return r.filter_by_bbox(
            left=float(left),
            bottom=float(bottom),
            right=float(right),
            top=float(top),
        )

    elif sql:
        return r.filter_by_sql(sql)

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
    parameters: list[str],
    lead_time: str,
    date: str,
    issue: str,
    periods: list[str],
    all_,
    station_id: list[str],
    name: str,
    coordinates: str,
    rank: int,
    distance: float,
    bbox: str,
    sql: str,
    sql_values: str,
    si_units: bool,
    shape: Literal["wide", "long"],
    humanize: bool,
    skip_empty: bool,
    skip_threshold: float,
    skip_criteria: Literal["min", "mean", "max"],
    dropna: bool,
) -> ValuesResult:
    """Core function for querying values via cli and restapi"""
    stations_ = get_stations(
        api=api,
        parameters=parameters,
        periods=periods,
        lead_time=lead_time,
        date=date,
        issue=issue,
        all_=all_,
        station_id=station_id,
        name=name,
        coordinates=coordinates,
        rank=rank,
        distance=distance,
        bbox=bbox,
        sql=sql,
        si_units=si_units,
        shape=shape,
        humanize=humanize,
        skip_empty=skip_empty,
        skip_threshold=skip_threshold,
        skip_criteria=skip_criteria,
        dropna=dropna,
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

    if sql_values:
        log.info(f"Filtering with SQL: {sql_values}")

        values_.filter_by_sql(sql_values)

    return values_


def get_interpolate(
    api: TimeseriesRequest,
    parameters: list[str],
    periods: list[str],
    lead_time: str,
    date: str,
    issue: str,
    coordinates: str,
    station_id: str,
    sql_values: str,
    si_units: bool,
    humanize: bool,
    use_nearby_station_distance: float,
) -> InterpolatedValuesResult:
    """Core function for querying values via cli and restapi"""
    r = _get_stations_request(
        api=api,
        parameters=parameters,
        periods=periods,
        lead_time=lead_time,
        date=date,
        issue=issue,
        si_units=si_units,
        shape="long",
        humanize=humanize,
        skip_empty=False,
        skip_threshold=0,
        skip_criteria="min",
        dropna=False,
        use_nearby_station_distance=use_nearby_station_distance,
    )

    try:
        if coordinates:
            lat, lon = coordinates.split(",")
            values_ = r.interpolate((float(lat), float(lon)))
        else:
            values_ = r.interpolate_by_station_id(station_id)
    except ValueError as e:
        log.exception(e)
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
            return values_

    if sql_values:
        log.info(f"Filtering with SQL: {sql_values}")
        values_.filter_by_sql(sql_values)

    return values_


def get_summarize(
    api: TimeseriesRequest,
    parameters: list[str],
    periods: list[str],
    lead_time: str,
    date: str,
    issue: str,
    coordinates: str,
    station_id: str,
    sql_values: str,
    si_units: bool,
    humanize: bool,
) -> SummarizedValuesResult:
    """Core function for querying values via cli and restapi"""
    r = _get_stations_request(
        api=api,
        parameters=parameters,
        periods=periods,
        lead_time=lead_time,
        date=date,
        issue=issue,
        si_units=si_units,
        shape="long",
        humanize=humanize,
        skip_empty=False,
        skip_threshold=0,
        skip_criteria="min",
        dropna=False,
        use_nearby_station_distance=0,
    )

    try:
        if coordinates:
            lat, lon = coordinates.split(",")
            values_ = r.summarize((float(lat), float(lon)))
        else:
            values_ = r.summarize_by_station_id(station_id)
    except ValueError as e:
        log.exception(e)
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
            return values_

    if sql_values:
        log.info(f"Filtering with SQL: {sql_values}")
        values_.filter_by_sql(sql_values)

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
    fmt: str | Literal["png", "jpg", "svg", "pdf"] = "png",
    dpi: int = 100,
) -> BytesIO:
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
    if dpi <= 0:
        raise ValueError("dpi must be more than 0")

    import matplotlib
    import matplotlib.pyplot as plt

    request = CLIMATE_STRIPES_CONFIG[kind]["request"]()
    cmap = CLIMATE_STRIPES_CONFIG[kind]["color_map"]

    matplotlib.use("agg")
    color_map = plt.get_cmap(cmap)

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
        raise ValueError(f"No station with a name similar to '{name}' found") from e

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
    df = df.with_columns(
        pl.col("value_scaled").map_elements(color_map, return_dtype=pl.List(pl.Float64)).alias("color")
    )

    if start_year:
        df = df.filter(pl.col("date").dt.year().ge(start_year))
    if end_year:
        df = df.filter(pl.col("date").dt.year().le(end_year))

    if len(df) == 1:
        raise ValueError("At least two years are required to create warming stripes.")

    fig, ax = plt.subplots(tight_layout=True)

    df_without_nulls = df.drop_nulls("value")

    ax.bar(
        df_without_nulls.get_column("date").dt.year(),
        1.0,
        width=1.0,
        color=df_without_nulls.get_column("color"),
    )
    ax.set_axis_off()
    if show_data_availability:
        ax.scatter(
            df.get_column("date").dt.year(),
            df.get_column("availability"),
            color="gold",
            marker=",",
            s=0.5,
        )
        ax.plot(
            df.get_column("date").dt.year(),
            df.get_column("availability"),
            color="gold",
        )
        ax.text(
            df.get_column("date").dt.year().min(),
            -0.03,
            "data availability",
            ha="left",
            va="top",
            color="gold",
        )
    ax.text(0.5, -0.04, "Source: Deutscher Wetterdienst", ha="center", va="center", transform=ax.transAxes)

    if show_title:
        ax.set_title(f"""Climate stripes ({kind}) for {station_dict["name"]}, Germany ({station_dict["station_id"]})""")
    if show_years:
        ax.text(0.05, -0.05, df.get_column("date").min().year, ha="center", va="center", transform=ax.transAxes)
        ax.text(0.95, -0.05, df.get_column("date").max().year, ha="center", va="center", transform=ax.transAxes)

    buf = BytesIO()
    plt.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return buf


def _thread_safe_plot_stripes(
    kind: Literal["temperature", "precipitation"],
    station_id: str | None = None,
    name: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    name_threshold: float = 0.9,
    show_title: bool = True,
    show_years: bool = True,
    show_data_availability: bool = True,
    fmt: str | Literal["png", "jpg", "svg", "pdf"] = "png",
    dpi: int = 100,
) -> BytesIO:
    """Thread-safe wrapper for _plot_warming_stripes because matplotlib is not thread-safe."""
    with ThreadPoolExecutor(1) as executor:
        return executor.submit(
            lambda: _plot_stripes(
                kind=kind,
                station_id=station_id,
                name=name,
                start_year=start_year,
                end_year=end_year,
                name_threshold=name_threshold,
                show_title=show_title,
                show_years=show_years,
                show_data_availability=show_data_availability,
                fmt=fmt,
                dpi=dpi,
            )
        ).result()


def set_logging_level(debug: bool):
    # Setup logging.
    log_level = logging.INFO

    if debug:  # pragma: no cover
        log_level = logging.DEBUG

    log.setLevel(log_level)
