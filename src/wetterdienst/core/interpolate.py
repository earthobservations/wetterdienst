# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Interpolation for weather data."""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from itertools import combinations
from queue import Queue
from typing import TYPE_CHECKING, cast

import polars as pl
import utm
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import QhullError
from shapely.geometry import MultiPoint, Point
from tqdm import tqdm

from wetterdienst.core.util import (
    can_answer_at_height,
    collection_is_done,
    count_stations_in_reach,
    extract_station_values,
    lapse_rate_for,
    open_parameter_data,
    parameters_still_in_reach,
    reduce_to_height,
    report_height_exclusions,
    unanswerable_at_height,
)
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model.metadata import ParameterModel
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    import datetime as dt

    from shapely.geometry.base import BaseGeometry

    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import StationsResult
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# what `apply_interpolation` wants before it can answer: four stations that surround the point
STATIONS_NEEDED = 4

# Occurrence thresholding is applied to the quantities the canonical parameter table marks
# `zero_inflated`: linear interpolation between a station that recorded rain and one that recorded
# none produces a spurious small positive, a drizzle that fell nowhere. We suppress those by also
# interpolating a binary occurrence field and zeroing out the result when fewer than half of the
# surrounding stations recorded a positive value. Which quantities those are is a property of the
# quantity, so it is declared once in `metadata.parameter_table` rather than listed here.


def get_interpolated_df(
    request: TimeseriesRequest,
    latitude: float,
    longitude: float,
    elevation: float | None = None,
) -> pl.DataFrame:
    """Get the interpolated DataFrame for the given request and location.

    Raises:
        NoStationsWithHeightError: where an elevation is asked about and leaving out the stations
            of unknown height leaves nothing that can answer it

    """
    utm_x, utm_y, _, _ = utm.from_latlon(latitude, longitude)
    settings = cast("Settings", request.settings)
    stations_dict, param_dict, dropped_for_height = request_stations(
        request,
        latitude,
        longitude,
        utm_x,
        utm_y,
        elevation,
    )
    df = calculate_interpolation(utm_x, utm_y, stations_dict, param_dict, settings.ts_geo_use_nearby_station_distance)
    # after the frame is built, not before: a parameter the exclusions left with three stations
    # holds columns and still interpolates to nothing, and only the frame knows that
    report_height_exclusions(df, param_dict, dropped_for_height, elevation, stations_needed=STATIONS_NEEDED)
    return df


def request_stations(
    request: TimeseriesRequest,
    latitude: float,
    longitude: float,
    utm_x: float,
    utm_y: float,
    elevation: float | None = None,
) -> tuple[dict, dict, dict[tuple[str, str, str], int]]:
    """Request the stations for the interpolation.

    Args:
        request: TimeseriesRequest object
        latitude: latitude of the point to interpolate
        longitude: longitude of the point to interpolate
        utm_x: longitude in UTM of the point to interpolate
        utm_y: latitude in UTM of the point to interpolate
        elevation: elevation of the point in metres, to bring each station's readings to

    Returns:
        the stations dict, the parameter dict, and how many stations each parameter lost for
        having no height of its own

    """
    param_dict = {}
    stations_dict = {}
    dropped_for_height: dict[tuple[str, str, str], int] = {}
    settings = cast("Settings", request.settings)
    max_interp_distance = max(
        settings.ts_geo_station_distance_for(parameter.name, parameter.dataset.resolution.name)
        for parameter in request.parameters
        if isinstance(parameter, ParameterModel)
    )
    stations_ranked = request.filter_by_distance(latlon=(latitude, longitude), distance=max_interp_distance)
    df_stations_ranked = stations_ranked.df
    # looked up by station id rather than zipped against the ranked frame positionally: `query()`
    # yields only the stations that returned data inside the requested window, so any station it
    # passes over shifts a positional pairing by one and every station after it is then read with
    # the coordinates and distance of its neighbour
    # one row per station, the nearest: the ranked frame carries a row per station *and* dataset,
    # so a multi-dataset request has several rows for one station, each with the coordinates and
    # distance its own dataset's meta index reported. `query()` yields one result per station, and
    # the row that answers for it is the closest one rather than whichever happened to sort last
    # counted once, off the ranking, before a single value is downloaded: what each parameter has
    # in its own radius, and how much of that reports a height
    counts = count_stations_in_reach(df_stations_ranked, request.parameters, settings)
    unanswerable = unanswerable_at_height(counts, elevation)
    if unanswerable and unanswerable == set(counts):
        # no station in reach can be brought to the height asked about, and every parameter wants
        # to be: there is nothing a download could add, so the report speaks for the whole request
        return stations_dict, param_dict, {key: counts[key].total for key in unanswerable}
    stations_by_id = {
        station["station_id"]: station
        for station in df_stations_ranked.unique(subset=["station_id"], keep="first", maintain_order=True).iter_rows(
            named=True,
        )
    }
    tqdm_out = TqdmToLogger(log, level=logging.INFO)
    for result in tqdm(
        stations_ranked.values.query(),
        total=len(stations_by_id),
        desc="querying stations for interpolation",
        unit="station",
        file=tqdm_out,
    ):
        station = stations_by_id[result.df.get_column("station_id")[0]]
        valid_station_groups_exists = has_valid_station_group(stations_dict, utm_x, utm_y)
        # check if all parameters found enough stations and the stations build a valid station group
        if (
            collection_is_done(
                param_dict, dropped_for_height.keys() & parameters_still_in_reach(counts, station["distance"])
            )
            and valid_station_groups_exists
        ):
            break
        if result.df.drop_nulls("value").is_empty():
            continue
        contributed = apply_station_values_per_parameter(
            result.df,
            stations_ranked,
            param_dict,
            station,
            elevation,
            dropped_for_height=dropped_for_height,
            valid_station_groups_exists=valid_station_groups_exists,
        )
        # only a station that gave something is one of the stations the interpolation has: the hull
        # that says whether four of them surround the point is built from this, and a station
        # counted here without a column of its own would let the search stop on a group that cannot
        # be interpolated from -- which is what a station with no height is, once an elevation is
        # asked for
        if contributed:
            utm_x_station, utm_y_station = utm.from_latlon(station["latitude"], station["longitude"])[:2]
            stations_dict[station["station_id"]] = (utm_x_station, utm_y_station, station["distance"])
    return stations_dict, param_dict, dropped_for_height


def apply_station_values_per_parameter(
    result_df: pl.DataFrame,
    stations_ranked: StationsResult,
    param_dict: dict,
    station: dict,
    elevation: float | None = None,
    *,
    dropped_for_height: dict[tuple[str, str, str], int],
    valid_station_groups_exists: bool,
) -> bool:
    """Apply the station values to the parameter data.

    Args:
        result_df: DataFrame containing the station values
        stations_ranked: stations_result with stations ranked by distance
        param_dict: dict containing the parameter data
        station: dict containing the station data
        elevation: elevation of the point in metres, to bring each station's readings to
        dropped_for_height: how many stations each parameter lost for having no height
        min_gain_of_value_pairs: minimum gain of value pairs to add a station
        num_additional_stations: number of additional stations to add if the gain is not reached
        valid_station_groups_exists: bool indicating if valid station groups exist

    Returns:
        Whether the station gave a value to any parameter; the parameter data is updated in place

    """
    contributed = False
    settings = cast("Settings", stations_ranked.stations.settings)
    # once, not once per parameter per station: `values` builds a `TimeseriesValues` and with it a
    # `UnitConverter`, whose tables run to a couple of hundred entries
    unit_converter = stations_ranked.values.unit_converter
    for parameter in stations_ranked.stations.parameters:
        if not isinstance(parameter, ParameterModel):
            continue
        dataset = parameter.dataset
        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue
        # the radius follows the resolution for a parameter that decorrelates fast in space, so it
        # is asked for per parameter and resolution rather than read off a mapping
        station_distance = settings.ts_geo_station_distance_for(parameter.name, dataset.resolution.name)
        if station["distance"] > station_distance:
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue
        param_key = (dataset.resolution.name, dataset.name, parameter.name)
        if param_key in param_dict and param_dict[param_key].finished:
            continue
        # Filter only for exact parameter
        result_series_param = result_df.filter(
            pl.col("resolution").eq(dataset.resolution.name),
            pl.col("dataset").eq(dataset.name),
            pl.col("parameter").eq(parameter.name),
        )
        if result_series_param.drop_nulls("value").is_empty():
            continue
        lapse_rate = lapse_rate_for(parameter, unit_converter, convert_units=settings.ts_convert_units)
        if not can_answer_at_height(station.get("height"), lapse_rate, elevation):
            # asked before the parameter gets an entry of its own: an entry with no station column
            # in it comes back as rows with no resolution, dataset or parameter either, the date
            # grid padded out with nulls where the values would have been
            log.info(
                f"station {station['station_id']} has no height, so it says nothing about "
                f"{parameter.name} at {elevation} m and is left out",
            )
            # noted, not only logged: where this empties a parameter the caller is owed the
            # reason, and a log line is the one place a caller cannot read it from
            dropped_for_height[param_key] = dropped_for_height.get(param_key, 0) + 1
            continue
        # cast, not parsed: the request declares its dates as `str | datetime | None` because
        # that is what a caller may hand it, and resolves them to datetimes in `__post_init__`
        param_data = open_parameter_data(
            param_dict,
            param_key,
            dataset.resolution.value,
            cast("dt.datetime | None", stations_ranked.stations.start_date),
            cast("dt.datetime | None", stations_ranked.stations.end_date),
        )
        if param_data is None:
            continue
        result_series_param = param_data.values.select("date").join(result_series_param, on="date", how="left")
        result_series_param = result_series_param.get_column("value")
        reduced = reduce_to_height(result_series_param, lapse_rate, station.get("height"), elevation)
        if reduced is None:  # pragma: no cover - the check above turns such a station away already
            continue
        result_series_param = reduced.rename(station["station_id"])
        # only a column actually taken makes this a station the answer draws on: `finished` turns
        # one away, and counting it would put a station with no column of its own into the hull
        contributed |= extract_station_values(
            param_data,
            result_series_param,
            min_gain_of_value_pairs=stations_ranked.settings.ts_geo_min_gain_of_value_pairs,
            num_additional_stations=stations_ranked.settings.ts_geo_num_additional_stations,
            valid_station_groups_exists=valid_station_groups_exists,
        )
    return contributed


def calculate_interpolation(
    utm_x: float,
    utm_y: float,
    stations_dict: dict,
    param_dict: dict,
    use_nearby_station_distance: float | None,
) -> pl.DataFrame:
    """Calculate the interpolation for the given data.

    Args:
        utm_x: longitude in UTM
        utm_y: latitude in UTM
        stations_dict: dict containing the station data including the location
        param_dict: dict containing the parameter data
        use_nearby_station_distance: distance in km to use nearby stations for interpolation

    Returns:
        DataFrame containing the interpolated data

    """
    data = [
        pl.DataFrame(
            schema={
                "date": pl.Datetime(time_zone="UTC"),
                "resolution": pl.String,
                "dataset": pl.String,
                "parameter": pl.String,
                "value": pl.Float64,
                "distance_mean": pl.Float64,
                "taken_station_ids": pl.List(inner=pl.String),
            },
        ),
    ]
    valid_station_groups = get_valid_station_groups(stations_dict, utm_x, utm_y)
    nearby_stations = [
        station_id
        for station_id, (_, _, distance) in stations_dict.items()
        if use_nearby_station_distance is not None and distance < use_nearby_station_distance
    ]
    for (resolution, dataset, parameter), param_data in param_dict.items():
        if param_data.values.width < 2:
            # a date grid and no station to answer against it. Concatenating that horizontally
            # pads the grid with nulls, and the rows come back with no resolution, dataset or
            # parameter either -- which is not a result for the parameter, it is noise
            continue
        param_df = pl.DataFrame({"date": param_data.values.get_column("date")})
        results = []
        for row in param_data.values.select(pl.all().exclude("date")).iter_rows(named=True):
            results.append(
                apply_interpolation(
                    row,
                    stations_dict,
                    valid_station_groups,
                    resolution,
                    dataset,
                    parameter,
                    utm_x,
                    utm_y,
                    nearby_stations,
                ),
            )
        results = pl.DataFrame(
            results,
            schema={
                "resolution": pl.String,
                "dataset": pl.String,
                "parameter": pl.String,
                "value": pl.Float64,
                "distance_mean": pl.Float64,
                "taken_station_ids": pl.List(inner=pl.String),
            },
            orient="row",
        )
        param_df = pl.concat([param_df, results], how="horizontal_extend")
        data.append(param_df)
    df = pl.concat(data)
    df = df.with_columns(pl.col("value").round(2), pl.col("distance_mean").round(2))
    return df.sort(
        by=[
            "resolution",
            "dataset",
            "parameter",
            "date",
        ],
    )


def _covers(hull: BaseGeometry, point: Point) -> bool:
    """Say whether the hull surrounds the point with room to interpolate in.

    Shapely below 2.0.6 raises out of `create_collection` when a geometry is built from
    coordinates under numpy 2, which is what the dependency floor rules out.

    Stations on a line, or all in one place, have a hull with no width. It still covers a point
    lying on it, and answering yes there would call such a group valid -- one that stops the
    collection of further stations while being no region to interpolate over, since
    `LinearNDInterpolator` has no triangle to work with. Duplicate coordinates still give a
    polygon, so the interpolator is guarded where it is called as well.
    """
    return hull.geom_type == "Polygon" and hull.covers(point)


def has_valid_station_group(stations_dict: dict, utm_x: float, utm_y: float) -> bool:
    """Say whether any four of the stations surround the given point.

    Asked once per station collected, where the groups themselves are not wanted -- only whether
    one exists. Enumerating them to find out costs C(N,4) hulls, which is 91390 of them for the 40
    stations a wide radius can reach, and seconds per station.

    The hull of all the stations answers it outright: if the point lies inside it, some three of
    them contain the point (Carathéodory in the plane) and any fourth station only widens the hull
    of those three, so a covering group exists. If it lies outside, no subset can cover it, every
    subset's hull being contained in the whole's.
    """
    if len(stations_dict) < 4:
        return False
    coords = [(x, y) for x, y, _ in stations_dict.values()]
    return _covers(MultiPoint(coords).convex_hull, Point(utm_x, utm_y))


def get_valid_station_groups(stations_dict: dict, utm_x: float, utm_y: float) -> Queue:
    """Get all valid station groups that cover the given point.

    Args:
        stations_dict: dict containing the station data including the location
        utm_x: longitude in UTM
        utm_y: latitude in UTM

    Returns:
        Queue containing the valid station groups

    """
    point = Point(utm_x, utm_y)
    valid_groups = Queue()
    # get all combinations of 4 stations
    for station_group in combinations(stations_dict.keys(), 4):
        coords = [(stations_dict[s][0], stations_dict[s][1]) for s in station_group]
        # the convex hull of the four, not a polygon through them in the order they are held. That
        # order is by distance from the point, which says nothing about the order around it, so
        # roughly half of all groups describe a self-intersecting polygon -- and `covers` on an
        # invalid polygon is undefined. Measured over random groups ordered as these are, one in
        # six disagreed with its own hull, every time by rejecting a group that does surround the
        # point. The hull is the region `LinearNDInterpolator` interpolates over, up to the
        # degenerate cases at its edge -- four stations on a line have a hull with no width, which
        # the interpolator cannot triangulate at all
        if _covers(MultiPoint(coords).convex_hull, point):
            valid_groups.put(station_group)
    return valid_groups


@lru_cache
def get_station_group_ids(valid_station_groups: Queue, vals_index: frozenset) -> list:
    """Get the station group ids that are a subset of the given values."""
    for item in valid_station_groups.queue:
        if set(item).issubset(vals_index):
            return list(item)
    return []


def apply_interpolation(
    row: dict,
    stations_dict: dict,
    valid_station_groups: Queue,
    resolution: str,
    dataset: str,
    parameter: str,
    utm_x: float,
    utm_y: float,
    nearby_stations: list[str],
) -> tuple[str, str, str, float | None, float | None, list[str]]:
    """Apply interpolation to a row of data.

    Args:
        row: dict containing the data across collected stations for a specific date
        stations_dict: dict containing the station data including the location
        valid_station_groups: Queue containing the valid station groups to use for interpolation
        resolution: resolution name
        dataset: dataset name
        parameter: parameter name
        utm_x: longitude in UTM
        utm_y: latitude in UTM
        nearby_stations: list of nearby stations

    Returns:
        tuple containing the resolution name, dataset name, parameter name, interpolated value, mean distance of the
        stations used for interpolation and the station ids used for interpolation

    """
    if nearby_stations:
        valid_values = {s: v for s, v in row.items() if s in nearby_stations and v is not None}
        if valid_values:
            # the first is the nearest: a row's columns are in the order the stations were
            # collected, which is the order `filter_by_distance` ranked them in
            first_station = next(iter(valid_values.keys()))
            return (
                resolution,
                dataset,
                parameter,
                valid_values[first_station],
                stations_dict[first_station][2],
                [first_station],
            )
    vals = {s: v for s, v in row.items() if v is not None}
    station_group_ids = get_station_group_ids(valid_station_groups, frozenset(vals))
    vals = {s: v for s, v in vals.items() if s in station_group_ids} if station_group_ids else None
    if not vals or len(vals) < 4:
        return resolution, dataset, parameter, None, None, []
    xs, ys, distances = map(list, zip(*[stations_dict[station_id] for station_id in station_group_ids], strict=False))
    distance_mean = sum(distances) / len(distances)
    try:
        f = LinearNDInterpolator(points=(xs, ys), values=list(vals.values()))
    except QhullError:
        # a group with no triangle to interpolate over. `_covers` turns away the collinear ones
        # before they are queued, so nothing production builds should arrive here; what remains is
        # whatever else Qhull declines to triangulate -- duplicate coordinates give a polygon and
        # so pass that check -- and scipy says so by raising rather than by answering NaN
        # debug rather than info: this is reached per timestamp, so one degenerate group would
        # otherwise write a line for every one of them
        log.debug(f"stations {station_group_ids} do not span a triangle, so they interpolate nothing")
        return resolution, dataset, parameter, None, None, []
    value = f(utm_x, utm_y)
    if math.isnan(value):
        # the interpolation had no answer, which is not the same as an answer of nothing: read
        # through the occurrence test below, a NaN would come out as a confident zero
        return resolution, dataset, parameter, None, None, []
    if PARAMETERS[parameter].zero_inflated:
        f_index = LinearNDInterpolator(points=(xs, ys), values=[float(v > 0) for v in list(vals.values())])
        value_index = f_index(utm_x, utm_y)
        value = value if value_index >= 0.5 else 0
    return resolution, dataset, parameter, float(value), distance_mean, station_group_ids
