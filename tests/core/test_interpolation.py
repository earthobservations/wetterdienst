# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for interpolation."""

import datetime as dt
import logging
import random
from queue import Queue
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.core.interpolate import (
    apply_interpolation,
    get_valid_station_groups,
)
from wetterdienst.exceptions import NoStationsWithHeightError, StationNotFoundError
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

pytest.importorskip("shapely")

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Shared geometry for occurrence-threshold unit tests
# ---------------------------------------------------------------------------
# Four stations forming a 20 km x 20 km square in UTM-like coordinates.
# Station D (NW corner) is the only one that ever records a positive value.
# The target point is placed in the SW quadrant (close to A/B, away from D)
# so that it falls inside the Delaunay triangle whose nodes are ALL zero-value
# stations → occurrence index < 0.5 → zeroing is triggered for the sparse case.
# No network traffic is needed for these tests.
_STATIONS_DICT: dict = {
    "A": (490_000.0, 5_490_000.0, 14.14),  # SW corner
    "B": (510_000.0, 5_490_000.0, 14.14),  # SE corner
    "C": (510_000.0, 5_510_000.0, 14.14),  # NE corner
    "D": (490_000.0, 5_510_000.0, 14.14),  # NW corner — positive station
}
# Off-centre target, inside the triangle formed by A-B-C (all zero-value):
# occurrence index at this point ≈ 0.25 for the 1-of-4 case.
_UTM_X = 495_000.0
_UTM_Y = 5_495_000.0


def test_occurrence_threshold_zeroes_sparse_precipitation() -> None:
    """Interpolated precipitation must be zeroed when occurrence index < 0.5.

    Fewer than half of surrounding stations recorded a positive value triggers zeroing.
    """
    valid_groups = get_valid_station_groups(_STATIONS_DICT, _UTM_X, _UTM_Y)
    # Only 1 of 4 stations has precipitation → occurrence index ≈ 0.25 at centre
    row = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 5.0}
    _, _, _, value, _, _ = apply_interpolation(
        row,
        _STATIONS_DICT,
        valid_groups,
        "daily",
        "climate_summary",
        "precipitation_height",
        _UTM_X,
        _UTM_Y,
        [],
    )
    assert value == 0.0, "Expected zero when fewer than half of stations have precipitation"


def test_occurrence_threshold_preserves_majority_precipitation() -> None:
    """Interpolated precipitation must be kept when the majority of surrounding stations recorded a positive value.

    Occurrence index >= 0.5 preserves the interpolated value.
    """
    valid_groups = get_valid_station_groups(_STATIONS_DICT, _UTM_X, _UTM_Y)
    # 3 of 4 stations have precipitation → occurrence index ≈ 0.75 at centre
    row = {"A": 5.0, "B": 5.0, "C": 5.0, "D": 0.0}
    _, _, _, value, _, _ = apply_interpolation(
        row,
        _STATIONS_DICT,
        valid_groups,
        "daily",
        "climate_summary",
        "precipitation_height",
        _UTM_X,
        _UTM_Y,
        [],
    )
    assert value is not None
    assert value > 0.0, "Expected positive value when majority of stations have precipitation"


def test_occurrence_threshold_not_applied_to_temperature() -> None:
    """The occurrence threshold must NOT be applied to continuous parameters such as temperature.

    A non-zero interpolated value must be preserved even when only one station has a positive reading.
    """
    valid_groups = get_valid_station_groups(_STATIONS_DICT, _UTM_X, _UTM_Y)
    row = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 5.0}
    _, _, _, value, _, _ = apply_interpolation(
        row,
        _STATIONS_DICT,
        valid_groups,
        "daily",
        "climate_summary",
        "temperature_air_mean_2m",
        _UTM_X,
        _UTM_Y,
        [],
    )
    assert value is not None
    assert value > 0.0, "Temperature must not be zeroed by occurrence threshold"


def test_occurrence_threshold_applies_to_snow_depth_new() -> None:
    """The occurrence threshold must apply to snow_depth_new.

    snow_depth_new shares the zero-inflated character of precipitation.
    """
    valid_groups = get_valid_station_groups(_STATIONS_DICT, _UTM_X, _UTM_Y)
    row = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 3.0}
    _, _, _, value, _, _ = apply_interpolation(
        row,
        _STATIONS_DICT,
        valid_groups,
        "daily",
        "climate_summary",
        "snow_depth_new",
        _UTM_X,
        _UTM_Y,
        [],
    )
    assert value == 0.0, "Expected zero for snow_depth_new when fewer than half of stations have new snow"


def test_occurrence_based_parameters_set_contains_all_precipitation_variants() -> None:
    """Smoke-test that the zero-inflated flag covers core precipitation and new-snow parameters."""
    required = {
        "precipitation_height",
        "precipitation_height_liquid",
        "precipitation_height_last_1h",
        "precipitation_height_last_24h",
        "precipitation_duration",
        "precipitation_intensity",
        "snow_depth_new",
        "water_equivalent_snow_depth_new",
    }
    missing = sorted(name for name in required if not PARAMETERS[name].zero_inflated)
    assert not missing, f"not marked zero_inflated in the canonical parameter table: {missing}"


@pytest.fixture
def df_interpolated_empty() -> pl.DataFrame:
    """Provide empty DataFrame for interpolated values."""
    return pl.DataFrame(
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "distance_mean": pl.Float64,
            "taken_station_ids": pl.List(pl.String),
        },
    )


@pytest.mark.remote
def test_interpolation_temperature_air_mean_2m_hourly_by_coords(default_settings: Settings) -> None:
    """Test that the interpolation works with hourly data."""
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] == 18001
    assert result.df.drop_nulls().shape[0] == 17914
    given_df = result.filter_by_date("2022-01-02 00:00:00+00:00")
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "f674568e",
                "resolution": "hourly",
                "dataset": "temperature_air",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
                "value": 4.56,
                "distance_mean": 13.37,
                "taken_station_ids": ["02480", "04411", "07341", "00917"],
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_temperature_air_mean_2m_daily_by_station_id(default_settings: Settings) -> None:
    """Test that the interpolation works with daily data."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(1986, 10, 31, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(1986, 11, 1, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "6754d04d",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(1986, 10, 31, tzinfo=ZoneInfo("UTC")),
                "value": 6.37,
                "distance_mean": 16.99,
                "taken_station_ids": ["00072", "02074", "02638", "04703"],
            },
            {
                "station_id": "6754d04d",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(1986, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.7,
                "distance_mean": 0.0,
                "taken_station_ids": ["00071"],
            },
        ],
        orient="row",
    )
    given_df = request.interpolate(latlon=(48.2156, 8.9784)).df
    assert given_df.shape[0] == 2
    assert given_df.drop_nulls().shape[0] == 2
    assert_frame_equal(given_df, expected_df)

    # by station id the answer is at the station's own altitude, which the result says outright --
    # a surer contract than comparing two live interpolations, which can draw on different stations
    # under a slow or partial upstream and then differ for reasons of their own
    height = request.all().df.filter(pl.col("station_id").eq("00071")).get_column("height").item()
    assert request.interpolate_by_station_id(station_id="00071").elevation == height


@pytest.mark.parametrize("method", ["interpolate", "summarize"])
@pytest.mark.parametrize(
    ("resolution", "dataset", "expected_distance"),
    [
        ("minute_10", "precipitation", 15.0),
        ("hourly", "precipitation", 20.0),
        ("daily", "climate_summary", 40.0),
    ],
)
def test_search_radius_reaches_the_request(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    resolution: str,
    dataset: str,
    expected_distance: float,
) -> None:
    """Test that the radius a request searches is the one the resolution asks for.

    The settings answer this correctly on their own, and every other test of the scaling asks them
    directly -- so nothing would notice if `interpolate` and `summarize` stopped consulting them
    and went back to a single number. This catches the station search in the act, without a
    request leaving the machine.
    """

    class _StopError(Exception):
        """Raised once the distance has been seen, so no data is fetched."""

    seen = []

    def _record(self: DwdObservationRequest, latlon: tuple[float, float], distance: float) -> None:  # noqa: ARG001
        seen.append(distance)
        raise _StopError

    monkeypatch.setattr(DwdObservationRequest, "filter_by_distance", _record)
    request = DwdObservationRequest(
        parameters=[(resolution, dataset, "precipitation_height")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
    )
    with pytest.raises(_StopError):
        getattr(request, method)(latlon=(50.0, 8.9))
    assert seen == [expected_distance]


@pytest.mark.remote
def test_interpolation_precipitation_height_minute_10(default_settings: Settings) -> None:
    """Test that the interpolation works with precipitation."""
    request = DwdObservationRequest(
        parameters=[("minute_10", "precipitation", "precipitation_height")],
        start_date=dt.datetime(2021, 10, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 10, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] == 577
    assert result.df.drop_nulls().shape[0] == 577
    given_df = result.filter_by_date("2021-10-05 00:00:00+00:00")
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "f674568e",
                "resolution": "10_minutes",
                "dataset": "precipitation",
                "parameter": "precipitation_height",
                "date": dt.datetime(2021, 10, 5, tzinfo=ZoneInfo("UTC")),
                "value": 0.03,
                "distance_mean": 9.38,
                "taken_station_ids": ["04230", "02480", "04411", "07341"],
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_sunshine_duration_daily(default_settings: Settings) -> None:
    """Test that sunshine_duration can be interpolated (issue #1651)."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "sunshine_duration")],
        start_date=dt.datetime(2021, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 6, 10, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] > 0, "Expected interpolated sunshine_duration values but got none"
    assert result.df.drop_nulls().shape[0] > 0


@pytest.mark.remote
def test_interpolation_snow_depth_new_daily(default_settings: Settings) -> None:
    """Test that snow_depth_new can be interpolated and that the occurrence threshold is applied.

    Result must never be negative or spuriously positive when surrounding stations had no new snow.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "precipitation_more", "snow_depth_new")],
        start_date=dt.datetime(2021, 2, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 2, 10, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] > 0, "Expected interpolated snow_depth_new values but got none"
    # occurrence threshold must prevent negative or NaN values
    values = result.df.drop_nulls().get_column("value")
    assert (values >= 0).all(), "snow_depth_new interpolated values must be non-negative"


def test_valid_station_groups_ignore_the_order_the_stations_are_held_in() -> None:
    """Four stations surrounding a point are a valid group however they are ordered.

    The stations are held in the order they were ranked by distance from the point, which says
    nothing about the order *around* it, so drawing a polygon through them in that order describes
    a self-intersecting shape about half the time -- and `covers` on an invalid polygon is
    undefined. Over random groups ordered as these are, one in six disagreed with its own convex
    hull, every time by rejecting a group that does surround the point and that
    `LinearNDInterpolator` can answer for.

    The coordinates are chosen so that the old predicate actually rejects them, which the first
    version of this test failed to do: a ring can be self-intersecting and still be covered
    according to GEOS, so `is_valid` being False does not by itself make a discriminating case.
    """
    from shapely.geometry import Point, Polygon  # noqa: PLC0415

    # in distance order from the point at the origin, which makes a bowtie of the four
    stations = {
        "a": (-2.13, -6.59, 6.93),
        "b": (0.04, 9.64, 9.64),
        "c": (9.66, 1.86, 9.84),
        "d": (-9.13, 4.07, 10.0),
    }
    coords = [(x, y) for x, y, _ in stations.values()]
    # what the check used to do, kept here so the test fails if the fix is reverted
    assert not Polygon(coords).covers(Point(0.0, 0.0))

    groups = get_valid_station_groups(stations, 0.0, 0.0)
    assert groups.get_nowait() == ("a", "b", "c", "d")
    assert groups.empty()
    groups.put(("a", "b", "c", "d"))
    row = {"a": 1.0, "b": 3.0, "c": 4.0, "d": 2.0}
    _, _, _, value, _, taken = apply_interpolation(
        row, stations, groups, "daily", "kl", "temperature_air_mean_2m", 0.0, 0.0, []
    )
    assert value is not None
    assert sorted(taken) == ["a", "b", "c", "d"]


def test_reduce_to_height_brings_a_reading_to_the_point() -> None:
    """A reading is corrected by the rate its quantity falls at, over the difference in height."""
    from wetterdienst.core.util import reduce_to_height  # noqa: PLC0415

    values = pl.Series("00001", [10.0, 12.0])
    # 500 m above the station, at 0.65 K per 100 m, is 3.25 K colder
    corrected = reduce_to_height(values, 0.0065, station_height=100.0, target_height=600.0)
    assert corrected.to_list() == pytest.approx([6.75, 8.75])
    # and below it, warmer
    corrected = reduce_to_height(values, 0.0065, station_height=600.0, target_height=100.0)
    assert corrected.to_list() == pytest.approx([13.25, 15.25])


def test_lapse_rate_follows_the_unit_the_values_are_in() -> None:
    """The rate is declared per kelvin, and the values need not be.

    A step of a degree Fahrenheit is 1.8 times a step of a kelvin, so a rate left in kelvin would
    move a Fahrenheit series by 8.45 where 15.21 is meant -- and the unit targets are a documented
    setting rather than a corner.
    """
    from wetterdienst.core.util import lapse_rate_for  # noqa: PLC0415
    from wetterdienst.model.unit import UnitConverter  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationMetadata  # noqa: PLC0415

    parameter = DwdObservationMetadata["daily"]["kl"]["temperature_air_mean_2m"]
    converter = UnitConverter()
    assert lapse_rate_for(parameter, converter, convert_units=True) == pytest.approx(0.0065)
    converter.update_targets({"temperature": "degree_fahrenheit"})
    assert lapse_rate_for(parameter, converter, convert_units=True) == pytest.approx(0.0065 * 1.8)
    # 1300 m at the Fahrenheit rate is the 15.21 the Celsius answer comes to
    assert 1300 * lapse_rate_for(parameter, converter, convert_units=True) == pytest.approx(15.21, abs=0.01)
    # left unconverted the values keep the source's unit, which for DWD is Celsius
    assert lapse_rate_for(parameter, converter, convert_units=False) == pytest.approx(0.0065)


def test_near_ground_air_temperatures_carry_no_lapse_rate() -> None:
    """The 5 cm readings are made in the air but governed by the ground radiating beneath them.

    That is the same reason the soil and concrete temperatures carry no rate, so the grass minimum
    and its kin do not get the free-atmosphere one either.
    """
    for name in ("temperature_air_min_0_05m", "temperature_air_max_0_05m", "temperature_air_mean_0_1m"):
        assert PARAMETERS[name].lapse_rate is None, name


def test_reduce_to_height_leaves_alone_what_it_cannot_correct() -> None:
    """Without a target, or for a quantity that does not fall with height, the readings stand.

    A soil temperature follows the ground rather than the air, precipitation does not lapse at all,
    and with no elevation for the target there is nothing to correct towards -- a height taken from
    the interpolation itself cancels out of it exactly.
    """
    from wetterdienst.core.util import reduce_to_height  # noqa: PLC0415

    values = pl.Series("00001", [10.0, 12.0])
    assert reduce_to_height(values, 0.0065, 100.0, None).to_list() == [10.0, 12.0]
    # no rate: a quantity that does not fall with height
    assert reduce_to_height(values, None, 100.0, 600.0).to_list() == [10.0, 12.0]


def test_reduce_to_height_leaves_out_a_station_it_cannot_place() -> None:
    """A station with no height of its own cannot answer a question about a height.

    Thirteen providers have such stations -- every one of FMI's, IPMA's and the Environment
    Agency's, and a scattering of ECCC's and met.no's. Letting the readings through uncorrected
    would place them at their own altitude while their neighbours are moved to the caller's, which
    mixes two vertical references in one interpolation.
    """
    from wetterdienst.core.util import reduce_to_height  # noqa: PLC0415

    values = pl.Series("00001", [10.0, 12.0])
    assert reduce_to_height(values, 0.0065, None, 600.0) is None
    # but with no elevation asked for there is nothing to place it against, so it contributes
    assert reduce_to_height(values, 0.0065, None, None).to_list() == [10.0, 12.0]
    # and a quantity that does not fall with height needs no placing either
    assert reduce_to_height(values, None, None, 600.0).to_list() == [10.0, 12.0]


def test_a_parameter_no_station_answered_gives_no_rows() -> None:
    """A parameter with a date grid and no station behind it is no rows, not rows of nulls.

    Concatenating an empty result horizontally pads the grid, and the rows come back with no
    resolution, dataset or parameter either -- noise wearing the shape of an answer. It is
    reachable where every station is turned away for having no height, which is every station a
    few providers have.
    """
    from wetterdienst.core.interpolate import calculate_interpolation  # noqa: PLC0415
    from wetterdienst.core.summarize import calculate_summary  # noqa: PLC0415
    from wetterdienst.core.util import _ParameterData, build_date_grid  # noqa: PLC0415
    from wetterdienst.metadata.resolution import Resolution  # noqa: PLC0415

    grid = build_date_grid(
        Resolution.DAILY,
        dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2022, 1, 3, tzinfo=ZoneInfo("UTC")),
    )
    param_dict = {("daily", "kl", "temperature_air_mean_2m"): _ParameterData(grid)}
    assert calculate_interpolation(0.0, 0.0, {}, param_dict, None).is_empty()
    assert calculate_summary({}, param_dict).is_empty()


def test_extract_station_values_says_whether_it_took_the_column() -> None:
    """A parameter that has what it needs turns a station away, and says so.

    The caller counts the stations an answer draws on from this, and a station counted without a
    column of its own goes into the hull that decides whether four of them surround the point.
    """
    from wetterdienst.core.util import _ParameterData, extract_station_values  # noqa: PLC0415

    param_data = _ParameterData(pl.DataFrame({"date": [1, 2, 3]}))
    taken = extract_station_values(
        param_data,
        pl.Series("00001", [1.0, 2.0, 3.0]),
        min_gain_of_value_pairs=0.1,
        num_additional_stations=3,
        valid_station_groups_exists=True,
    )
    assert taken
    assert "00001" in param_data.values.columns

    # a parameter with its four stations, no gain from a fifth, and no room for another extra
    full = _ParameterData(
        pl.DataFrame({"date": [1, 2, 3], "a": [1.0] * 3, "b": [1.0] * 3, "c": [1.0] * 3, "d": [1.0] * 3}),
        additional_station_counter=3,
    )
    taken = extract_station_values(
        full,
        pl.Series("00002", [None, None, None], dtype=pl.Float64),
        min_gain_of_value_pairs=0.1,
        num_additional_stations=3,
        valid_station_groups_exists=True,
    )
    assert not taken
    assert "00002" not in full.values.columns
    assert full.finished


def test_lapse_rates_are_declared_for_the_air_and_nothing_else() -> None:
    """The rate belongs to quantities measured in the free air, not in or on the ground."""
    for name in ("temperature_air_mean_2m", "temperature_air_max_2m", "temperature_air_min_2m"):
        assert PARAMETERS[name].lapse_rate == 0.0065, name
    # a dew point falls more slowly, the air keeping proportionally more of its moisture as it rises
    assert PARAMETERS["temperature_dew_point_mean_2m"].lapse_rate == 0.002
    for name in ("temperature_soil_mean_0_05m", "temperature_concrete_mean_0m", "temperature_surface_mean"):
        assert PARAMETERS[name].lapse_rate is None, name
    # pressure falls exponentially and wants the barometric formula, so it carries no linear rate
    assert PARAMETERS["pressure_air_site"].lapse_rate is None


def test_has_valid_station_group_agrees_with_enumerating_them() -> None:
    """Whether a covering group exists is the hull of all the stations, without enumerating groups.

    Asked once per station collected, where enumerating C(N,4) groups to find out costs seconds for
    the 40 stations a wide radius reaches. If the point is inside the hull of all of them, three of
    them contain it and any fourth widens that group's hull, so a covering group exists.
    """
    from itertools import combinations  # noqa: PLC0415

    from shapely.geometry import MultiPoint, Point  # noqa: PLC0415

    from wetterdienst.core.interpolate import _covers, has_valid_station_group  # noqa: PLC0415

    rng = random.Random(4)  # noqa: S311
    for _ in range(50):
        stations = {str(index): (rng.uniform(-10, 10), rng.uniform(-10, 10), 1.0) for index in range(rng.randint(3, 8))}
        utm_x, utm_y = rng.uniform(-12, 12), rng.uniform(-12, 12)
        point = Point(utm_x, utm_y)
        enumerated = any(
            _covers(MultiPoint([(stations[s][0], stations[s][1]) for s in group]).convex_hull, point)
            for group in combinations(stations, 4)
        )
        assert has_valid_station_group(stations, utm_x, utm_y) == enumerated


def test_collinear_stations_are_no_valid_group() -> None:
    """Stations on a line are no group, however close the point lies to that line.

    Their hull has no width. It still covers a point lying on it, so `covers` alone called such a
    group valid -- and a valid group stops the collection of further stations, which is how a set
    that cannot be interpolated at all would end a search that might have found one that can.
    """
    from wetterdienst.core.interpolate import has_valid_station_group  # noqa: PLC0415

    on_a_line = {"a": (0.0, 0.0, 1.0), "b": (1.0, 0.0, 2.0), "c": (2.0, 0.0, 3.0), "d": (3.0, 0.0, 4.0)}
    assert get_valid_station_groups(on_a_line, 1.5, 0.0).empty()
    assert not has_valid_station_group(on_a_line, 1.5, 0.0)


def test_apply_interpolation_with_collinear_stations_gives_no_value() -> None:
    """Stations on a line have no triangle to interpolate over, and scipy says so by raising.

    Their hull is a line, which covers a point lying on it, so such a group can reach the
    interpolator -- where it answers with a `QhullError` rather than with NaN.
    """
    stations = {"a": (0.0, 0.0, 1.0), "b": (1.0, 0.0, 2.0), "c": (2.0, 0.0, 3.0), "d": (3.0, 0.0, 4.0)}
    groups = Queue()
    groups.put(("a", "b", "c", "d"))
    row = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
    result = apply_interpolation(row, stations, groups, "daily", "kl", "temperature_air_mean_2m", 1.5, 0.0, [])
    assert result[3] is None
    assert result[5] == []


def test_valid_station_groups_still_reject_a_point_outside_them() -> None:
    """Stations that do not surround the point are no group for it."""
    stations = {"a": (1.0, 1.0, 1.0), "b": (2.0, 1.0, 2.0), "c": (3.0, 2.0, 3.0), "d": (2.0, 3.0, 2.5)}
    assert get_valid_station_groups(stations, -50.0, -50.0).empty()


def test_apply_interpolation_without_an_answer_gives_no_value() -> None:
    """An interpolation with no answer is a gap, not a zero.

    `LinearNDInterpolator` answers NaN for a point outside the stations it was given. Read through
    the occurrence test that suppresses a drizzle nobody recorded, `NaN >= 0.5` is False and the
    NaN came back as a confident zero -- a precipitation of exactly none, at a point the
    interpolation could not answer for at all.
    """
    from queue import Queue  # noqa: PLC0415

    stations = {"a": (1.0, 1.0, 1.0), "b": (2.0, 1.0, 2.0), "c": (3.0, 2.0, 3.0), "d": (2.0, 3.0, 2.5)}
    groups = Queue()
    groups.put(("a", "b", "c", "d"))
    row = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
    # the point lies well outside the four, so the interpolation has nothing to say
    result = apply_interpolation(row, stations, groups, "daily", "kl", "precipitation_height", -50.0, -50.0, [])
    assert PARAMETERS["precipitation_height"].zero_inflated
    assert result[3] is None
    assert result[5] == []


def test_not_interpolatable_parameter(default_settings: Settings, df_interpolated_empty: pl.DataFrame) -> None:
    """Test that a parameter that cannot be interpolated is handled correctly."""
    request = DwdObservationRequest(
        parameters=[("hourly", "wind", "wind_direction")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    assert_frame_equal(
        given_df,
        df_interpolated_empty,
    )


def test_not_interpolatable_dataset(default_settings: Settings, df_interpolated_empty: pl.DataFrame) -> None:
    """Test that a dataset that cannot be interpolated is handled correctly."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "precipitation_form")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    assert_frame_equal(
        given_df,
        df_interpolated_empty,
    )


@pytest.mark.remote
def test_provider_dwd_mosmix(default_settings: Settings) -> None:
    """Test a MOSMIX request with date filter."""
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "temperature_air_mean_2m")],
        start_date=dt.datetime.now(tz=ZoneInfo("UTC")) + dt.timedelta(days=1),
        end_date=dt.datetime.now(tz=ZoneInfo("UTC")) + dt.timedelta(days=8),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.get_column("value").min() >= -40  # equals -40.0°C


def test_interpolation_temperature_air_mean_2m_daily_three_floats(default_settings: Settings) -> None:
    """Test that the interpolation works with three floats."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="too many values to unpack"):
        stations.interpolate(latlon=(0, 1, 2))


def test_interpolation_temperature_air_mean_2m_daily_one_floats(default_settings: Settings) -> None:
    """Test that an error is raised when not enough values are provided."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="not enough values to unpack"):
        stations.interpolate(latlon=(0,))


def test_interpolation_temperature_air_mean_2m_daily_no_station_found(default_settings: Settings) -> None:
    """Test that an error is raised when no station is found."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(StationNotFoundError, match="no station found for 00000"):
        stations.interpolate_by_station_id(station_id="00")


def test_interpolation_increased_station_distance() -> None:
    """Test that the interpolation works with increased station distance."""
    settings = Settings(ts_geo_station_distance={"precipitation_height": 25})
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    )
    values = request.interpolate(latlon=(52.8, 12.9))
    assert values.df.get_column("value").sum() == 21.07


@pytest.mark.remote
def test_interpolation_at_an_elevation(default_settings: Settings) -> None:
    """A point's elevation moves the answer by the lapse rate over the difference in height.

    Around Garmisch the stations within 40 km span 630 m to 2956 m, which is 15 K of air
    temperature interpolated as though it were horizontal structure. Naming the elevation is what
    tells the valley from the summit.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "temperature_air_mean_2m")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    valley = request.interpolate(latlon=(47.48, 11.06), elevation=200.0).df.get_column("value")
    summit = request.interpolate(latlon=(47.48, 11.06), elevation=1500.0).df.get_column("value")
    uncorrected = request.interpolate(latlon=(47.48, 11.06)).df.get_column("value")
    # 1300 m apart at 0.65 K per 100 m is 8.45 K, whatever the readings themselves are
    assert (valley - summit).drop_nulls().to_list() == pytest.approx([8.45] * valley.drop_nulls().len(), abs=0.01)
    # left out, nothing is corrected: the readings sit between the two, at the altitudes the
    # stations themselves stand at
    lower, upper = min(valley.mean(), summit.mean()), max(valley.mean(), summit.mean())
    assert lower < uncorrected.mean() < upper


def _blank_station_heights(monkeypatch: pytest.MonkeyPatch, keeps_its_height: pl.Expr) -> None:
    """Make a DWD request look like a provider that reports heights for only some of its stations.

    FMI, IPMA and the Environment Agency publish no height for any station, and eleven more
    providers for some of theirs. Borrowing DWD's data and taking the heights away exercises the
    same path without a second provider's outages deciding whether this test passes. The frame is
    ranked by distance, so the expression picks by how near the station is.
    """
    original = DwdObservationRequest.filter_by_distance

    def without_heights(self: DwdObservationRequest, *args: object, **kwargs: object) -> object:
        stations_ranked = original(self, *args, **kwargs)
        stations_ranked.df = stations_ranked.df.with_columns(
            pl.when(keeps_its_height).then(pl.col("height")).otherwise(None).alias("height"),
        )
        return stations_ranked

    monkeypatch.setattr(DwdObservationRequest, "filter_by_distance", without_heights)


@pytest.mark.remote
def test_interpolation_at_an_elevation_none_of_the_stations_can_answer(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An elevation that empties the request says so instead of coming back empty.

    A station of unknown height cannot be placed against the height asked about, and where that is
    every station in reach there is nothing left to interpolate. That used to be an empty frame
    with the reason in a server-side log -- the one place the caller cannot look.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "temperature_air_mean_2m")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    _blank_station_heights(monkeypatch, pl.lit(value=False))
    downloads = 0
    original_query = TimeseriesValues.query

    def counting_query(self: TimeseriesValues) -> object:
        nonlocal downloads
        downloads += 1
        return original_query(self)

    monkeypatch.setattr(TimeseriesValues, "query", counting_query)
    with pytest.raises(
        NoStationsWithHeightError,
        match=r"nothing can be brought to 200\.0 m for daily/climate_summary/temperature_air_mean_2m",
    ):
        request.interpolate(latlon=(47.48, 11.06), elevation=200.0)
    # and not one station's values were fetched to arrive at that: the ranking already said no
    # station in reach reports a height, and every quantity asked for needs one
    assert downloads == 0
    # without an elevation the same stations answer as they always did
    monkeypatch.setattr(TimeseriesValues, "query", original_query)
    assert not request.interpolate(latlon=(47.48, 11.06)).df.is_empty()


@pytest.mark.remote
def test_interpolation_at_an_elevation_names_the_parameter_it_lost(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A parameter emptied beside one that answered is named, and the rest of the result stands.

    Precipitation does not fall with height in the sense the correction means, so it keeps every
    station a temperature loses.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "temperature_air_mean_2m"), ("daily", "kl", "precipitation_height")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    _blank_station_heights(monkeypatch, pl.lit(value=False))
    with caplog.at_level(logging.WARNING):
        values = request.interpolate(latlon=(47.48, 11.06), elevation=200.0)
    # of the values that are there, not of the rows: a parameter with a station collected for it
    # gets rows either way, so this is what says the other parameter really was answered
    assert values.df.drop_nulls("value").get_column("parameter").unique().to_list() == ["precipitation_height"]
    assert "daily/climate_summary/temperature_air_mean_2m" in caplog.text


def test_interpolation_error_no_start_date() -> None:
    """Test that an error is raised when start_date is missing."""
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
    )
    with pytest.raises(ValueError, match="start_date and end_date are required for interpolation"):
        request.interpolate(latlon=(52.8, 12.9))


@pytest.mark.remote
def test_interpolation_at_an_elevation_too_few_stations_left_to_interpolate(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stations left over that cannot interpolate are named, the answer being null either way.

    An interpolation wants four that surround the point, so two of known height among neighbours of
    unknown height hold columns and still come back null. Whether keeping the other eight would
    have helped is not something a count can say -- they may not have surrounded the point either
    -- so it is said in the log rather than raised over the caller's result.
    """
    settings = Settings(ts_geo_use_nearby_station_distance=0.0)
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "temperature_air_mean_2m")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 5, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    )
    _blank_station_heights(monkeypatch, pl.int_range(pl.len()) < 2)
    with caplog.at_level(logging.WARNING):
        values = request.interpolate(latlon=(47.48, 11.06), elevation=200.0)
    assert values.df.drop_nulls("value").is_empty()
    assert "daily/climate_summary/temperature_air_mean_2m" in caplog.text
