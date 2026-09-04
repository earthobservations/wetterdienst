# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for interpolation."""

import datetime as dt
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
from wetterdienst.exceptions import StationNotFoundError
from wetterdienst.metadata.parameter_table import PARAMETERS
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
    for result in (
        request.interpolate(latlon=(48.2156, 8.9784)),
        request.interpolate_by_station_id(station_id="00071"),
    ):
        given_df = result.df
        assert given_df.shape[0] == 2
        assert given_df.drop_nulls().shape[0] == 2
        assert_frame_equal(given_df, expected_df)


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
    """
    # in distance order from the point at the origin, which makes a bowtie of the four
    stations = {
        "near": (0.0, -3.2, 3.2),
        "mid": (3.84, -2.86, 4.8),
        "west": (-6.03, 1.11, 6.1),
        "far": (8.76, -1.34, 8.9),
    }
    groups = get_valid_station_groups(stations, 0.0, 0.0)
    assert list(groups.queue) == [("near", "mid", "west", "far")]
    row = {"near": 1.0, "mid": 3.0, "west": 4.0, "far": 2.0}
    _, _, _, value, _, taken = apply_interpolation(
        row, stations, groups, "daily", "kl", "temperature_air_mean_2m", 0.0, 0.0, []
    )
    assert value is not None
    assert sorted(taken) == ["far", "mid", "near", "west"]


def test_has_valid_station_group_agrees_with_enumerating_them() -> None:
    """Whether a covering group exists is the hull of all the stations, without enumerating groups.

    Asked once per station collected, where enumerating C(N,4) groups to find out costs seconds for
    the 40 stations a wide radius reaches. If the point is inside the hull of all of them, three of
    them contain it and any fourth widens that group's hull, so a covering group exists.
    """
    from itertools import combinations  # noqa: PLC0415

    from shapely.geometry import MultiPoint, Point  # noqa: PLC0415

    from wetterdienst.core.interpolate import has_valid_station_group  # noqa: PLC0415

    rng = random.Random(4)  # noqa: S311
    for _ in range(50):
        stations = {str(index): (rng.uniform(-10, 10), rng.uniform(-10, 10), 1.0) for index in range(rng.randint(3, 8))}
        utm_x, utm_y = rng.uniform(-12, 12), rng.uniform(-12, 12)
        point = Point(utm_x, utm_y)
        enumerated = any(
            MultiPoint([(stations[s][0], stations[s][1]) for s in group]).convex_hull.covers(point)
            for group in combinations(stations, 4)
        )
        assert has_valid_station_group(stations, utm_x, utm_y) == enumerated


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


def test_interpolation_error_no_start_date() -> None:
    """Test that an error is raised when start_date is missing."""
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
    )
    with pytest.raises(ValueError, match="start_date and end_date are required for interpolation"):
        request.interpolate(latlon=(52.8, 12.9))
