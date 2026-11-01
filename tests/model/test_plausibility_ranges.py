# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The one table of ranges, the same for every provider, and the elevation rule that goes with it (GH-3681, GH-3670)."""

from __future__ import annotations

import datetime as dt
import math

import polars as pl
import pytest

from tests.provider import value_stubs
from tests.provider.judging import judged
from wetterdienst import Wetterdienst
from wetterdienst.model import plausibility_ranges
from wetterdienst.model.judge import ELEVATION_PRESSURE, plan_for, standard_station_pressure, station_pressure_bounds
from wetterdienst.model.plausibility import Plausibility
from wetterdienst.model.plausibility_ranges import bounds_for

UTC = dt.UTC
INF = math.inf


def _networks() -> list[str]:
    return [
        f"{provider}/{network}"
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if not Wetterdienst.is_standalone(provider, network)
    ]


def _datasets(network: str) -> list:
    provider, name = network.split("/")
    return [dataset for resolution in Wetterdienst.resolve(provider, name).metadata for dataset in resolution]


@pytest.mark.parametrize(
    ("name", "resolution", "expected"),
    [
        # the records of the WMO table of 31 July 2025, rounded outward
        ("temperature_air_mean_2m", "daily", (-90.0, 60.0)),
        ("temperature_air_max_2m_last_24h", "subdaily", (-90.0, 60.0)),
        ("pressure_air_sea_level", "hourly", (850.0, 1100.0)),
        ("pressure_air_site_reduced", "hourly", (850.0, 1100.0)),
        ("wind_gust_max", "hourly", (0.0, 115.0)),
        ("wind_speed_mean", "daily", (0.0, 115.0)),
        ("precipitation_amount", "1_minute", (0.0, 40.0)),
        ("precipitation_amount", "5_minutes", (0.0, 350.0)),
        ("precipitation_amount", "hourly", (0.0, 350.0)),
        ("precipitation_amount_last_1h", "subdaily", (0.0, 350.0)),
        ("precipitation_amount_last_12h", "subdaily", (0.0, 1150.0)),
        ("precipitation_amount_last_24h", "subdaily", (0.0, 1850.0)),
        ("precipitation_amount", "daily", (0.0, 1850.0)),
        ("precipitation_amount", "monthly", (0.0, 10000.0)),
        ("precipitation_amount", "annual", (0.0, 30000.0)),
        # a definition
        ("humidity_relative", "hourly", (0.0, 1.0)),
        ("humidity_relative_mean", "daily", (0.0, 1.0)),
        ("cloud_cover_total", "hourly", (0.0, 1.0)),
        ("sunshine_duration", "10_minutes", (0.0, 630.0)),
        ("sunshine_duration", "hourly", (0.0, 3780.0)),
        ("sunshine_duration", "daily", (0.0, 90720.0)),
        ("precipitation_duration", "hourly", (0.0, 3780.0)),
        ("count_days_frost", "monthly", (0.0, 31.0)),
        ("count_days_frost", "annual", (0.0, 366.0)),
        ("snow_cover", "daily", (0.0, 1.0)),
        ("leaf_wetness_duration", "hourly", (0.0, 3780.0)),
        ("leaf_wetness_duration", "daily", (0.0, 90720.0)),  # DMI's sum of the minutes of a day, 1,440 at most
        # a month of ECCC's normal snowfall is the day's 200 cm times 31, as the sums of the daily depths are
        ("snow_depth_new_normal", "monthly", (0.0, 6200.0)),
        ("snow_depth_new", "monthly", (0.0, 6200.0)),
        ("precipitation_amount_normal", "monthly", (0.0, 10000.0)),
        ("sunshine_duration_normal", "monthly", (0.0, 2678400.0)),
        # a named source
        ("pressure_air_site", "hourly", (300.0, 1100.0)),
        ("pressure_vapor_mean", "daily", (0.0, 60.0)),
        # a deficit is no pressure of the air: its upper end is the saturation at 60 °C, ~199 hPa; the lower end leaves
        # DMI's slightly negative days (-0.3 kPa at 06193 on 2025-07-25)
        ("vapor_pressure_deficit_mean", "hourly", (-10.0, 200.0)),
        ("temperature_dew_point_2m", "hourly", (-100.0, 60.0)),
        ("radiation_global_intensity_mean", "hourly", (0.0, 2000.0)),
        # a family without a record is held to its definition: at least 0, no upper end
        ("oxygen_level", "hourly", (0.0, INF)),
        ("soil_moisture_grass_sand_00cm_60cm", "daily", (0.0, INF)),
        ("radiation_sky_long_wave", "daily", (0.0, INF)),
        ("volume_reservoir", "daily", (0.0, INF)),
    ],
)
def test_the_bounds_the_maintainer_decided(name: str, resolution: str, expected: tuple[float, float]) -> None:
    """The bounds of the decisions D1 to D7 of GH-3681, at the resolution they depend on."""
    assert tuple(bounds_for(name, resolution)) == expected


@pytest.mark.parametrize(
    "name",
    [
        # hydrology gauges have a datum of their own, and a tidal river runs backwards (D7)
        "stage",
        "stage_max",
        "discharge",
        "discharge_mean",
        "groundwater_level",
        "distance_river_gauge_height",
        "flow_speed",
        "flow_direction",
        # derived quantities follow from checked inputs (D8)
        "temperature_wind_chill",
        "temperature_humidex",
        "evaporation_amount",
        "evapotranspiration_potential_last_24h",
        "radiation_long_wave_net_last_3h",
        "radiation_short_wave_net_last_3h",
        # forecast errors: signed, and in kelvin for the temperatures, which must stay out of every temperature rule
        "error_absolute_temperature_air_2m",
        "error_absolute_temperature_dew_point_2m",
        "error_absolute_pressure_air_site",
        "error_absolute_wind_speed",
        "error_absolute_wind_direction",
        # codes
        "weather_significant",
        "cloud_cover_total_measurement_method",
        "temperature_wet_ice_formation",
        "visibility_index",
    ],
)
def test_what_has_no_range(name: str) -> None:
    """A quantity that is derived, a code, or has a datum of its own is held to nothing, at any resolution."""
    for resolution in (None, "hourly", "daily", "monthly"):
        assert bounds_for(name, resolution) is None, (name, resolution)


#: the families a quantity may be held to nothing in, and why (D7, D8): a code, a flag or an index has no range, a
#: derived quantity follows from checked inputs, a hydrology gauge has a datum of its own
_HELD_TO_NOTHING = (
    "weather",
    "cloud_type_",
    "cloud_density",
    "cloud_cover_total_measurement_method",
    "climate_correction_factor",
    "precipitation_form",
    "precipitation_type_flags",
    "precipitation_index",
    "road_surface_condition",
    "soil_state_index",
    "visibility_index",
    "visibility_measurement_method",
    "temperature_wet_ice_formation",
    "quality",
    "error_absolute_",
    "evaporation_",
    "evapotranspiration",
    "temperature_wind_chill",
    "temperature_humidex",
    "radiation_global_uncertainty",
    "radiation_long_wave_net_last_3h",
    "radiation_short_wave_net_last_3h",
    "stage",
    "discharge",
    "groundwater_level",
    "distance_river_gauge",
    "flow_",
)


def test_every_canonical_parameter_is_bounded_or_deliberately_held_to_nothing() -> None:
    """A new canonical name that no row of the table reaches is a gap in the check, not a pass."""
    from wetterdienst.metadata.parameter_table import PARAMETERS  # noqa: PLC0415

    unbounded = [name for name in PARAMETERS if bounds_for(name) is None]
    assert [name for name in unbounded if not name.startswith(_HELD_TO_NOTHING)] == []
    # the quantities of the DMI additions (GH-3622) are bounded, not in a family held to nothing
    dmi = ("snow_cover", "leaf_wetness_duration", "vapor_pressure_deficit_mean", "temperature_air_mean_grass_height")
    assert [name for name in dmi if bounds_for(name) is None] == []


@pytest.mark.parametrize("unit_type", [None, "temperature", "temperature_difference"])
@pytest.mark.parametrize("name", ["error_absolute_temperature_air_2m", "error_absolute_temperature_dew_point_2m"])
def test_the_error_of_a_forecast_temperature_is_in_no_temperature_rule(name: str, unit_type: str | None) -> None:
    """These are errors in kelvin, not readings (GH-3688): by name and by family they stay out of the air and dew rules.

    Whatever unit type the lookup is given, the family `error_absolute_` holds them to nothing, before any
    `temperature_` family could, so the move to the unit type `temperature_difference` changes no bound.
    """
    for resolution in (None, "hourly", "daily"):
        assert bounds_for(name, resolution, unit_type) is None
    assert not any(
        name.startswith(prefix) for prefix, _ in plausibility_ranges.PREFIX_RANGES if prefix != "error_absolute_"
    )


def test_the_unit_type_temperature_difference_is_held_to_nothing() -> None:
    """A difference in kelvin is signed and no reading: the unit type has no range of its own (GH-3688)."""
    assert plausibility_ranges.UNIT_TYPE_RANGES["temperature_difference"] is None
    assert bounds_for("a_difference_no_table_names", None, "temperature_difference") is None


def test_a_bound_is_not_a_record() -> None:
    """Every extreme the module cites lies inside its bound; the one documented exceedance lies outside."""
    records = [
        ("temperature_air_max_2m", "daily", 56.7),  # Furnace Creek, 1913-07-10
        ("temperature_air_min_2m", "daily", -89.2),  # Vostok, 1983-07-21
        ("pressure_air_sea_level", "hourly", 1089.1),  # Tosontsengel, 2004-12-30
        ("pressure_air_sea_level", "hourly", 870.0),  # Typhoon Tip, 1979-10-12
        ("wind_gust_max", "hourly", 113.2),  # Barrow Island, 1996-04-10
        ("precipitation_amount", "1_minute", 31.2),  # Unionville MD, 1956-07-04
        ("precipitation_amount", "hourly", 305.0),  # Holt MO, 1947-06-22
        ("precipitation_amount_last_12h", "subdaily", 1144.0),  # Foc-Foc, 1966-01-07/08
        ("precipitation_amount", "daily", 1825.0),  # Foc-Foc, 1966-01-07/08
        ("precipitation_amount", "monthly", 9300.0),  # Cherrapunji, July 1861
        ("precipitation_amount", "annual", 26470.0),  # Cherrapunji, 1860/61
    ]
    for name, resolution, value in records:
        low, high = bounds_for(name, resolution)
        assert low <= value <= high, (name, resolution, value)
    # Shangdi (Inner Mongolia, 1975-08-01): 401 mm in 60 minutes, not in the WMO table, and the one exceedance
    assert bounds_for("precipitation_amount", "hourly").high < 401.0


def test_the_bound_of_a_quantity_is_that_of_the_quantity_and_not_of_the_network() -> None:
    """Every network is judged against the one table: the plan of a dataset holds `bounds_for` of each parameter."""
    assert not hasattr(plausibility_ranges, "SCOPE")
    assert not hasattr(plausibility_ranges, "OVERRIDES")
    checked = 0
    for network in _networks():
        for dataset in _datasets(network):
            plan = plan_for(network, dataset)
            for parameter in dataset:
                bounds = bounds_for(parameter.name, dataset.resolution.name, parameter.unit_type)
                found = plan.ranges.get(parameter.name_original)
                assert found == (None if bounds is None else tuple(bounds)), (network, dataset.name, parameter.name)
                checked += 1
    assert checked > 2000


def test_rain_and_sunshine_grow_with_the_span() -> None:
    """The bound of a longer span is never narrower than that of a shorter one."""
    spans = ["1_minute", "5_minutes", "10_minutes", "15_minutes", "hourly", "6_hours", "daily", "monthly", "annual"]
    for name in ("precipitation_amount", "sunshine_duration"):
        highs = [bounds_for(name, resolution).high for resolution in spans]
        assert highs == sorted(highs), name


# --- the elevation rule, for every network -----------------------------------------------------------------------


def test_the_station_pressure_is_held_to_the_elevation_in_every_network_that_serves_one() -> None:
    """Every dataset with a `pressure_air_site`, `_mean`, `_min` or `_max` has it in the plan of the elevation check."""
    served = {}
    for network in _networks():
        for dataset in _datasets(network):
            names = {parameter.name for parameter in dataset} & set(ELEVATION_PRESSURE)
            if names:
                plan = plan_for(network, dataset)
                assert {plan.parameters[original].name for original in plan.pressure} == names, (network, dataset.name)
                served.setdefault(network, set()).update(names)
    assert {"dwd/observation", "meteofrance/observation", "meteofrance/synop", "geosphere/observation"} <= set(served)
    assert len(served) >= 14
    assert {"pressure_air_site_min", "pressure_air_site_max"} <= served["geosphere/observation"]


def test_the_bounds_of_the_station_pressure_at_an_elevation() -> None:
    """From the lowest pressure on record as a share of the standard atmosphere, to 75 hPa above it."""
    low, high = station_pressure_bounds(0.0)
    assert low == pytest.approx(870.0)
    assert high == pytest.approx(1013.25 + 75.0)
    low, high = station_pressure_bounds(2956.0)
    assert (low, high) == pytest.approx((standard_station_pressure(2956.0) * 870.0 / 1013.25, 705.0 + 75.0), abs=1.0)
    assert station_pressure_bounds(None) is None
    assert station_pressure_bounds(9500.0) is None
    assert station_pressure_bounds(-600.0) is None


@pytest.mark.parametrize(
    ("elevation", "value", "kept", "case"),
    [
        (3.0, 917.4, True, "Hurricane Irma, St-Barthelemy 97123005, 2017-09-06 10 UTC, quality code 1 (GH-3670)"),
        (3.0, 936.0, True, "Hurricane Irma, one hour earlier"),
        (0.0, 870.0, True, "Typhoon Tip: the lowest sea level pressure on record"),
        (43.0, 938.0, True, "the deep lows of Dumont d'Urville"),
        (48.0, 1093.3, False, "Berlin-Tempelhof 1994-03-18, a digit slip 85.8 hPa above the standard atmosphere"),
        (25.0, 1098.2, False, "List auf Sylt 1991-06-21"),
        (25.0, 1099.3, False, "List auf Sylt 1995-11-15"),
        (25.0, 795.0, False, "List auf Sylt 1993-12-16, 215 hPa below the standard atmosphere"),
        (2956.0, 968.6, False, "the Zugspitze reading a sea level pressure"),
        (2956.0, 908.6, False, "the Zugspitze, 1990-05-31"),
        (7.0, 1097.3, False, "Tromelin, 2000-07-17"),
        # the known gap, for the step check of GH-3681 to close: a slip that lies between the margins
        (48.0, 909.5, True, "Berlin-Tempelhof 1994-08-29: 98 hPa below, as far as Irma's eye is"),
        (25.0, 910.1, True, "List auf Sylt 1990-09-18"),
        (25.0, 908.5, True, "List auf Sylt 1992-10-22"),
    ],
)
def test_irma_stays_and_the_digit_slips_go(elevation: float, value: float, kept: bool, case: str) -> None:  # noqa: FBT001
    """The margins keep a real hurricane and reject the slips of DWD that lie beyond them (GH-3670, GH-3681)."""
    low, high = station_pressure_bounds(elevation)
    assert (low <= value <= high) is kept, case


def test_irma_is_kept_by_the_elevation_check_of_meteofrance_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hourly `PSTAT` of St-Barthelemy is judged, through the reader, and nothing of the hurricane is rejected."""
    df = value_stubs._meteofrance_observation_hourly_irma(monkeypatch, drop_nulls=False)  # noqa: SLF001
    kept = df.filter(pl.col("value").is_not_null()).sort("timestamp")
    assert kept.get_column("value").to_list() == [990.9, 977.1, 936.0, 917.4, 960.4]
    assert kept.get_column("quality_flags").to_list() == ["1"] * 5
    rejected = df.filter(pl.col("value").is_null())
    assert rejected.get_column("quality_flags").to_list() == ["1,rejected:elevation,raw:1093.3"]


def test_a_station_without_an_elevation_is_not_judged() -> None:
    """The elevation check stands aside for a station the list gives no elevation."""
    dataset = next(
        d for d in _datasets("meteofrance/observation") if d.name == "others" and d.resolution.name == "hourly"
    )
    plan = plan_for("meteofrance/observation", dataset)
    name = next(original for original, c in plan.parameters.items() if c.name == "pressure_air_site")
    stamps = [dt.datetime(2024, 1, 1, tzinfo=UTC) + dt.timedelta(hours=hour) for hour in range(2)]
    df = pl.DataFrame(
        {"parameter": [name] * 2, "timestamp": stamps, "value": [1093.3, 800.0], "quality_flags": [None, None]},
        schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
    )
    out = judged(df, network="meteofrance/observation", dataset=dataset, elevation=None)
    assert out.get_column("quality_flags").to_list() == [None, None]
    out = judged(df, network="meteofrance/observation", dataset=dataset, elevation=48.0)
    assert out.get_column("quality_flags").to_list() == ["rejected:elevation,raw:1093.3", "rejected:elevation,raw:800"]


def test_an_elevation_of_zero_is_none_where_the_list_writes_it_for_an_unknown_one() -> None:
    """GHCN hourly lists CHM00052940 (4,329 m) at 0.0 and it reads 500.2 hPa: no elevation, so no judgement."""
    dataset = next(d for d in _datasets("noaa/ghcn") if d.resolution.name == "hourly")
    plan = plan_for("noaa/ghcn", dataset)
    name = next(original for original, c in plan.parameters.items() if c.name == "pressure_air_site")
    stamps = [dt.datetime(2024, 1, 1, tzinfo=UTC) + dt.timedelta(hours=hour) for hour in range(2)]
    df = pl.DataFrame(
        {"parameter": [name] * 2, "timestamp": stamps, "value": [500.2, 998.0], "quality_flags": [None, None]},
        schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
    )
    assert judged(df, network="noaa/ghcn", dataset=dataset, elevation=0.0).get_column("quality_flags").to_list() == [
        None,
        None,
    ]
    # the same list at 4,329 m would hold the 500.2 and a station at 5 m would not: only the zero is set aside
    assert judged(df, network="noaa/ghcn", dataset=dataset, elevation=5.0).get_column("quality_flags").to_list()[0] == (
        "rejected:elevation,raw:500.2"
    )
    # the 0.0 of the DWD list is a height, a coast
    dwd = next(d for d in _datasets("dwd/observation") if d.name == "pressure" and d.resolution.name == "hourly")
    dwd_plan = plan_for("dwd/observation", dwd)
    dwd_name = next(original for original, c in dwd_plan.parameters.items() if c.name == "pressure_air_site")
    dwd_df = df.with_columns(pl.lit(dwd_name).alias("parameter"))
    out = judged(dwd_df, network="dwd/observation", dataset=dwd, elevation=0.0)
    assert out.get_column("quality_flags").to_list()[0] == "rejected:elevation,raw:500.2"


def test_the_known_dwd_slip_between_the_margins_is_kept_until_the_step_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """909.5 hPa at 48 m (GH-3627) is 98 hPa under the standard atmosphere, as far as the eye of Irma was: kept."""
    df = value_stubs._dwd_hourly_pressure_off_the_elevation(monkeypatch, drop_nulls=False)  # noqa: SLF001
    site = df.filter(pl.col("parameter") == "pressure_air_site").sort("timestamp")
    assert site.get_column("value").to_list() == [1038.9, 909.5, 1009.6]


def test_the_checks_judge_one_pressure_with_both_modes() -> None:
    """The range and the elevation both name a pressure outside the two; soft keeps it."""
    dataset = next(d for d in _datasets("dwd/observation") if d.name == "pressure" and d.resolution.name == "hourly")
    plan = plan_for("dwd/observation", dataset)
    p0 = next(original for original, c in plan.parameters.items() if c.name == "pressure_air_site")
    stamps = [dt.datetime(2024, 1, 1, tzinfo=UTC) + dt.timedelta(hours=hour) for hour in range(2)]
    df = pl.DataFrame(
        {"parameter": [p0] * 2, "timestamp": stamps, "value": [1150.0, 1000.0], "quality_flags": [None, None]},
        schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
    )
    out = judged(
        df, network="dwd/observation", dataset=dataset, elevation=48.0, modes=Plausibility.model_validate("soft")
    )
    assert out.get_column("quality_flags").to_list() == ["suspect:elevation+range", None]
