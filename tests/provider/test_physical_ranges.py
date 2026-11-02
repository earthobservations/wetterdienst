# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The physical ranges catch a missing-value sentinel, leave a record alone, and cover every parameter (GH-2615).

The ranges are the one table of the library (GH-3681); the tests here hold the check of the provider tests to it.
"""

import datetime as dt
from io import BytesIO
from typing import get_args

import polars as pl
import pytest

from tests.provider.physical_ranges import bounds_for, out_of_range
from wetterdienst import Options, Settings
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.metadata.unit_type import UnitType
from wetterdienst.model.plausibility_ranges import PARAMETER_RANGES, PREFIX_RANGES, SPAN_HOURS, UNIT_TYPE_RANGES
from wetterdienst.provider.lhmt.observation import LhmtObservationRequest
from wetterdienst.util.network import File


def _frame(parameter: str, *values: float | None) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "parameter": [parameter] * len(values),
            "value": list(values),
            "timestamp": [dt.datetime(2026, 1, 1, tzinfo=dt.UTC) + dt.timedelta(hours=i) for i in range(len(values))],
        },
        schema={"parameter": pl.String, "value": pl.Float64, "timestamp": pl.Datetime(time_zone="UTC")},
    )


@pytest.mark.parametrize(
    ("parameter", "sentinels"),
    [
        ("temperature_air_mean_2m", [-9999.0, -999.0, -99.0, 99.9, 999.0, 9999.0]),
        # -99 is inside the bound of the dew point: ISD holds -98.2 and HadISD -100.0 (GH-3681)
        ("temperature_dew_point_2m", [-9999.0, -999.0, 99.9, 999.0, 9999.0]),
        ("pressure_air_site", [-9999.0, -999.0, -99.0, 9999.0]),
        ("wind_speed", [-9999.0, -999.0, -99.0, -1.0, 999.0, 9999.0]),
        ("wind_direction", [-9999.0, -999.0, -99.0, -1.0, 999.0, 9999.0]),
        ("snow_depth", [-9999.0, -999.0, -99.0, 9999.0]),
        ("sunshine_duration", [-9999.0, -999.0, -99.0, -1.0]),
        ("humidity_relative", [-9999.0, -999.0, -99.0, -1.0, 999.0, 9999.0]),
        ("precipitation_amount", [-9999.0, -999.0, -99.0, -1.0, 99999.0]),
        ("phenology_flowering_beginning", [-9999.0, -999.0, 999.0, 9999.0]),
    ],
)
def test_a_sentinel_is_outside_the_range_of_the_common_parameters(parameter: str, sentinels: list[float]) -> None:
    """The numbers sources use for a missing value are far from what the commonest parameters can be.

    Each parameter names the sentinels its range catches. What it does not name, such as 999 mm of rain in a month or
    99.9 % of relative humidity, looks like a reading, and is the part of #2615 that only the source's own
    documentation can settle.
    """
    for sentinel in sentinels:
        assert not out_of_range(_frame(parameter, sentinel)).is_empty(), sentinel


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("temperature_air_mean_2m", -45.9),  # the German record low, well inside the range
        ("temperature_air_mean_2m", 56.7),  # Death Valley
        ("temperature_dew_point_2m", -80.0),
        ("pressure_air_site", 870.0),  # the lowest sea level pressure, in a typhoon
        ("pressure_air_site", 1084.8),  # the highest
        ("wind_speed", 100.0),
        ("wind_direction", 360.0),
        ("wind_direction", 0.0),
        ("humidity_relative", 1.0),
        ("precipitation_amount", 0.0),
        ("precipitation_amount", 1825.0),  # the most rain in one day
        ("snow_depth", 1182.0),  # the deepest snow pack
        ("snow_depth", -1.0),  # a few centimetres below zero: 11 % of the hours of MeteoSwiss' station PLF, no code
        ("temperature_surface", 85.0),  # a road in the sun
        ("phenology_flowering_beginning", 1.0),  # 1 January of the reference year
        ("phenology_flowering_beginning", 366.0),
        ("phenology_height_growth_beginning", -130.0),  # DWD's Jultag: winter rape, 24 August 2007 of Referenzjahr 2008
        ("phenology_flowering_beginning", -1.0),  # 31 December of the year before: there is no 0
        ("phenology_emergence_beginning", 380.0),  # winter wheat, 15 January 2017 of Referenzjahr 2016
        ("phenology_leaf_fall_autumn", 443.0),  # beech, 20 March 1993 of Referenzjahr 1992
    ],
)
def test_a_record_is_inside_the_range(parameter: str, value: float) -> None:
    """A cold night, a hot road and a storm are no sentinel."""
    assert out_of_range(_frame(parameter, value)).is_empty()


def test_a_value_is_named_by_parameter_and_timestamp() -> None:
    """The rows found keep the parameter, the value and the timestamp, so that a failure says where to look."""
    found = out_of_range(_frame("temperature_air_mean_2m", 4.0, -999.0, None, 99.9, 5.0))
    assert found.get_column("value").to_list() == [-999.0, 99.9]
    assert found.get_column("timestamp").to_list() == [
        dt.datetime(2026, 1, 1, 1, tzinfo=dt.UTC),
        dt.datetime(2026, 1, 1, 3, tzinfo=dt.UTC),
    ]


def test_a_null_is_no_value_outside_the_range() -> None:
    """A missing value mapped to null is what the check wants to see."""
    assert out_of_range(_frame("temperature_air_mean_2m", None, None)).is_empty()


def test_a_source_name_is_read_through_the_mapping() -> None:
    """A frame that is not humanized carries the source's own names, which `names` maps to canonical ones."""
    df = _frame("tmk", 3.0, -999.0)
    assert out_of_range(df, {"tmk": "temperature_air_mean_2m"}).get_column("value").to_list() == [-999.0]


def test_a_parameter_without_a_range_is_left_alone() -> None:
    """A code, a flag and a count are held to nothing but their own ranges."""
    assert PARAMETERS["quality_general"].unit_type == "dimensionless"
    assert bounds_for("quality_general") is None
    assert out_of_range(_frame("quality_general", -999.0)).is_empty()


def test_a_misspelled_parameter_is_an_error_not_the_bound_of_a_family() -> None:
    """The helper reads the library's table, so a name that is no canonical parameter raises (GH-3709)."""
    assert "temperature_air_mean_2n" not in PARAMETERS
    with pytest.raises(KeyError):
        bounds_for("temperature_air_mean_2n")
    with pytest.raises(KeyError):
        out_of_range(_frame("temperature_air_mean_2n", -999.0))
    # a name of the source that `names` does not map is the same defect as a misspelled one
    with pytest.raises(KeyError):
        out_of_range(_frame("tmk", -999.0))


def test_every_unit_type_has_a_range_or_says_it_has_none() -> None:
    """A unit type added to the converter is checked by name, or this test fails and says which."""
    assert set(UNIT_TYPE_RANGES) == set(get_args(UnitType))


def test_a_dissolved_oxygen_reading_passes_and_a_sentinel_does_not() -> None:
    """`concentration` is held to its definition, at least 0, and the parameter has no range of its own (GH-3246)."""
    assert [name for name, parameter in PARAMETERS.items() if parameter.unit_type == "concentration"] == [
        "oxygen_level"
    ]
    assert "oxygen_level" not in PARAMETER_RANGES
    assert bounds_for("oxygen_level") == UNIT_TYPE_RANGES["concentration"]
    # saturation at 0 °C, a summer reading and the supersaturation of an algal bloom
    assert out_of_range(_frame("oxygen_level", 0.0, 8.7, 14.6, 21.0)).is_empty()
    # a quantity with no record is held to its definition alone (GH-3681): a negative number is a sentinel
    sentinels = [-9999.0, -999.0, -99.0, -1.0]
    assert out_of_range(_frame("oxygen_level", *sentinels, 99.9)).get_column("value").to_list() == sentinels


def test_every_canonical_parameter_resolves_to_a_range_or_none() -> None:
    """A parameter is never left unlooked at by a name that falls between the tables, at any resolution."""
    for name in PARAMETERS:
        for resolution in (None, *SPAN_HOURS):
            bounds = bounds_for(name, resolution)
            if bounds is not None:
                assert bounds.low < bounds.high, (name, resolution)


def test_every_special_range_is_used() -> None:
    """A parameter or a prefix in the tables that names nothing is a typo, and left unnoticed holds nothing."""
    assert set(PARAMETER_RANGES) <= set(PARAMETERS)
    for prefix, _ in PREFIX_RANGES:
        assert any(name.startswith(prefix) for name in PARAMETERS), prefix
    resolutions = {resolution.value for resolution in Resolution} | {"*"}
    for range_ in [*PARAMETER_RANGES.values(), *(range_ for _, range_ in PREFIX_RANGES), *UNIT_TYPE_RANGES.values()]:
        if isinstance(range_, dict):
            assert set(range_) <= resolutions, range_


def test_a_prefix_holds_one_unit_type_unless_a_name_is_taken_out() -> None:
    """A prefix that also matches a code of another unit type holds the code to a range of a quantity.

    `cloud_cover_total_measurement_method` is a dimensionless code, and the `cloud_cover_` fraction range of 0 to 1
    called every hour that an instrument measured (the code 2) a sentinel.
    """
    for prefix, range_ in PREFIX_RANGES:
        if range_ is None:
            continue
        matched = {
            name: PARAMETERS[name].unit_type
            for name in PARAMETERS
            if name.startswith(prefix) and name not in PARAMETER_RANGES
        }
        if not matched:
            continue
        family = max(sorted(set(matched.values())), key=list(matched.values()).count)
        odd = {name for name, unit_type in matched.items() if unit_type != family}
        assert odd == set(), f"{prefix} holds {sorted(odd)} to the range of {family}: add them to PARAMETER_RANGES"


def test_a_prefix_does_not_shadow_a_later_one() -> None:
    """The first prefix to match wins, so a prefix that starts another has to come after it."""
    prefixes = [prefix for prefix, _ in PREFIX_RANGES]
    for index, prefix in enumerate(prefixes):
        assert not any(prefix.startswith(earlier) for earlier in prefixes[:index]), prefix


def test_a_sum_over_a_month_or_a_year_may_exceed_the_depth_of_one_reading() -> None:
    """DWD's monthly and annual snow depth are sums of the daily depths, which an Alpine station takes to thousands."""
    assert not out_of_range(_frame("snow_depth_sum", 2194.0), resolution="daily").is_empty()
    assert out_of_range(_frame("snow_depth_sum", 2194.0), resolution="annual").is_empty()
    assert out_of_range(_frame("snow_depth_sum", 2194.0), resolution="monthly").is_empty()
    # a depth is a reading at any resolution, only the sum of the daily depths is no reading
    assert not out_of_range(_frame("snow_depth", 2194.0), resolution="annual").is_empty()
    assert out_of_range(_frame("snow_depth_new", 1500.0), resolution="annual").is_empty()
    assert not out_of_range(_frame("snow_depth_new", 1500.0), resolution="daily").is_empty()
    # a maximum or a reading of the day is no sum, and keeps the range of one reading
    assert not out_of_range(_frame("snow_depth_max", 9999.0), resolution="annual").is_empty()
    assert not out_of_range(_frame("snow_depth", -999.0), resolution="annual").is_empty()


@pytest.mark.parametrize(
    ("parameter", "resolution", "reading", "no_reading"),
    [
        # the most rain in a minute, 15 minutes, an hour and a day on record, and the sentinel of the next span up
        ("precipitation_amount", "1_minute", 31.2, 99.9),
        ("precipitation_amount", "10_minutes", 70.0, 999.0),
        ("precipitation_amount", "hourly", 305.0, 999.0),  # Holt 1947; Shangdi 1975 (401 mm) is not in the WMO table
        ("precipitation_amount", "daily", 1825.0, 2500.0),
        ("precipitation_amount", "monthly", 9300.0, 12_000.0),  # Cherrapunji, July 1861
        # a span of sunshine in seconds
        ("sunshine_duration", "10_minutes", 600.0, 3600.0),
        ("sunshine_duration", "hourly", 3600.0, 86400.0),
        ("sunshine_duration", "daily", 86400.0, 13_850.0 * 60 + 86400.0),
    ],
)
def test_a_reading_of_one_span_is_no_reading_of_a_shorter_one(
    parameter: str, resolution: str, reading: float, no_reading: float
) -> None:
    """A range depends on the span: 99.9 mm is a sentinel in a minute and a reading in a day (GH-2797)."""
    assert out_of_range(_frame(parameter, reading), resolution=resolution).is_empty()
    assert not out_of_range(_frame(parameter, no_reading), resolution=resolution).is_empty()


def test_the_rain_and_the_sunshine_of_a_span_grow_with_it() -> None:
    """The range of a longer span is never narrower than the one of a shorter span."""
    spans = ["1_minute", "5_minutes", "10_minutes", "15_minutes", "hourly", "daily", "monthly", "annual"]
    for name in ("precipitation_amount", "sunshine_duration"):
        bounds = [bounds_for(name, resolution) for resolution in spans]
        highs = [bound.high for bound in bounds if bound is not None]
        assert len(highs) == len(spans), name
        assert highs == sorted(highs), name


def _lhmt_values(
    monkeypatch: pytest.MonkeyPatch, temperature: float, options: Options, pressure: float = 1007.4
) -> pl.DataFrame:
    """Give the values of one LHMT station for a day with one reading, as its reader and the framework make them.

    The core would reject a -999 before the hook of the provider tests sees it, so the test holds it to no bounds:
    the hook is what is under test, not the core.
    """
    monkeypatch.setattr("wetterdienst.model.judge.bounds_for", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("wetterdienst.model.judge._PLANS", {})
    stations = (
        b'[{"code": "vilniaus-ams", "name": "Vilniaus AMS", '
        b'"coordinates": {"latitude": 54.625992, "longitude": 25.107064}}]'
    )
    day = (
        b'{"station": {"code": "vilniaus-ams"}, "observations": ['
        b'{"observationTimeUtc": "2020-07-01 12:00:00", "airTemperature": %f, "seaLevelPressure": %f}]}'
        % (temperature, pressure)
    )

    def download_file(url: str, *_args: object, **_kwargs: object) -> File:
        return File(url=url, content=BytesIO(stations if url.endswith("/stations") else day), status=200)

    monkeypatch.setattr("wetterdienst.provider.lhmt.observation.api.download_file", download_file)
    start = dt.datetime(2020, 7, 1, tzinfo=dt.UTC)
    request = LhmtObservationRequest(
        parameters=[("hourly", "data")],
        start=start,
        end=start + dt.timedelta(days=1),
        settings=Settings(cache_disable=True),
        options=options,
    )
    return request.filter_by_station_id("vilniaus-ams").values().all().df


def test_the_check_sees_a_frame_a_provider_hands_back(
    monkeypatch: pytest.MonkeyPatch,
    physical_range_findings: list[str],
) -> None:
    """The hook the provider tests run under is armed: a value out of range in a returned frame is recorded."""
    # LHMT publishes `null` for a missing reading, so a -999 here is what a sentinel that got through would be
    df = _lhmt_values(monkeypatch, -999.0, Options())

    assert sorted(df.get_column("value").to_list()) == [-999.0, 1007.4]
    assert len(physical_range_findings) == 1
    assert "lhmt.observation.api hourly/data: temperature_air_2m: 1 outside" in physical_range_findings[0]
    physical_range_findings.clear()


def test_a_frame_converted_to_other_units_than_the_default_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
    physical_range_findings: list[str],
) -> None:
    """The ranges are written in the default units, so 72 degrees Fahrenheit is no air temperature out of range."""
    options = Options(unit_targets={"temperature": "degree_fahrenheit"})
    df = _lhmt_values(monkeypatch, 22.3, options)

    assert sorted(df.get_column("value").to_list()) == [pytest.approx(72.14), 1007.4]
    assert physical_range_findings == []


def test_only_the_unit_type_converted_to_other_units_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
    physical_range_findings: list[str],
) -> None:
    """A temperature in degrees Fahrenheit is not checked, the pressure beside it still is."""
    options = Options(unit_targets={"temperature": "degree_fahrenheit"})
    _lhmt_values(monkeypatch, 22.3, options, pressure=-999.0)

    assert len(physical_range_findings) == 1
    assert "pressure_air_sea_level" in physical_range_findings[0]
    assert "temperature" not in physical_range_findings[0]
    physical_range_findings.clear()


def test_a_frame_that_is_not_converted_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
    physical_range_findings: list[str],
) -> None:
    """With the unit conversion off a value is in the source's own unit, which the ranges do not describe."""
    df = _lhmt_values(monkeypatch, -999.0, Options(convert_units=False))

    assert sorted(df.get_column("value").to_list()) == [-999.0, 1007.4]
    assert physical_range_findings == []
