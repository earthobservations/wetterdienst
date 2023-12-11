# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import sys
from typing import List, Literal, Optional, Tuple, Union

from wetterdienst.core.process import create_date_range
from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.result import StationsResult, ValuesResult
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.period import PeriodType
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.settings import Settings
from wetterdienst.util.enumeration import parse_enumeration_from_template

log = logging.getLogger(__name__)


def unpack_parameters(parameter: str) -> List[str]:
    """Parse parameters to either
    - list of str, each representing a parameter or
    - list of tuple of str representing a pair of parameter and dataset
    e.g.
       "precipitation_height,temperature_air_200" ->
           ["precipitation_height", "temperature_air_200"]

       "precipitation_height/precipitation_more,temperature_air_200/kl" ->
           [("precipitation_height", "precipitation_more"), ("temperature_air_200", "kl")]

    """

    def unpack_parameter(par: str) -> Union[str, Tuple[str, str]]:
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
    parameter: List[str],
    resolution: str,
    period: List[str],
    lead_time: str,
    date: Optional[str],
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
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, DwdMosmixType

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
        if issubclass(api, DwdMosmixRequest):
            mosmix_type = parse_enumeration_from_template(resolution, DwdMosmixType)

            if mosmix_type == DwdMosmixType.SMALL:
                res = Resolution.HOURLY
            else:
                res = Resolution.HOUR_6
        elif issubclass(api, DwdDmoRequest):
            res = Resolution.HOURLY
        else:
            res = parse_enumeration_from_template(resolution, api._resolution_base, Resolution)

        # Split date string into start and end date string
        start_date, end_date = create_date_range(date=date, resolution=res)

    if api._data_range == DataRange.LOOSELY and not start_date and not end_date:
        # TODO: use another property "network" on each class
        raise TypeError(
            f"Combination of provider {api._provider.name} and network {api._kind.name} requires start and end date"
        )

    # Todo: We may have to apply other measures to allow for
    #  different request initializations
    # DWD Mosmix has fixed resolution and rather uses SMALL
    # and large for the different datasets

    kwargs = {
        "parameter": unpack_parameters(parameter),
        "start_date": start_date,
        "end_date": end_date,
    }
    if issubclass(api, DwdMosmixRequest):
        kwargs["mosmix_type"] = resolution
        kwargs["start_issue"] = issue
    elif issubclass(api, DwdDmoRequest):
        kwargs["dmo_type"] = resolution
        kwargs["start_issue"] = issue
        kwargs["lead_time"] = lead_time
    elif api._resolution_type == ResolutionType.MULTI:
        kwargs["resolution"] = resolution

    if api._period_type == PeriodType.MULTI:
        kwargs["period"] = period

    return api(**kwargs, settings=settings)


def get_stations(
    api,
    parameter: List[str],
    resolution: str,
    period: List[str],
    lead_time: str,
    date: Optional[str],
    issue: Optional[str],
    all_: bool,
    station_id: List[str],
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
        parameter=parameter,
        resolution=resolution,
        period=period,
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
    parameter: List[str],
    resolution: str,
    lead_time: str,
    date: str,
    issue: str,
    period: List[str],
    all_,
    station_id: List[str],
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
        parameter=parameter,
        resolution=resolution,
        period=period,
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
            sys.exit(1)

    if sql_values:
        log.info(f"Filtering with SQL: {sql_values}")

        values_.filter_by_sql(sql_values)

    return values_


def get_interpolate(
    api: TimeseriesRequest,
    parameter: List[str],
    resolution: str,
    period: List[str],
    lead_time: str,
    date: str,
    issue: str,
    coordinates: str,
    station_id: str,
    sql_values: str,
    si_units: bool,
    humanize: bool,
    use_nearby_station_distance: float,
) -> ValuesResult:
    """Core function for querying values via cli and restapi"""
    r = _get_stations_request(
        api=api,
        parameter=parameter,
        resolution=resolution,
        period=period,
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
            sys.exit(1)

    if sql_values:
        log.info(f"Filtering with SQL: {sql_values}")
        values_.filter_by_sql(sql_values)

    return values_


def get_summarize(
    api: TimeseriesRequest,
    parameter: List[str],
    resolution: str,
    period: List[str],
    lead_time: str,
    date: str,
    issue: str,
    coordinates: str,
    station_id: str,
    sql_values: str,
    si_units: bool,
    humanize: bool,
) -> ValuesResult:
    """Core function for querying values via cli and restapi"""
    r = _get_stations_request(
        api=api,
        parameter=parameter,
        resolution=resolution,
        period=period,
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
            sys.exit(1)

    if sql_values:
        log.info(f"Filtering with SQL: {sql_values}")
        values_.filter_by_sql(sql_values)

    return values_


def set_logging_level(debug: bool):
    # Setup logging.
    log_level = logging.INFO

    if debug:  # pragma: no cover
        log_level = logging.DEBUG

    log.setLevel(log_level)
