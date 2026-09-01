# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Canonical parameter table.

Holds what is true of a measured *quantity*, independent of any provider: its canonical
snake_case name and the unit type that selects the output unit via ``UnitConverter.targets``.

Provider metadata declares only what the provider itself knows -- the canonical ``name`` as a
foreign key into this table, the source's own ``name_original`` and the source's ``unit``.
A provider cannot declare a ``unit_type`` of its own: ``ParameterModel.unit_type`` reads it from
here, and ``ParameterModel`` forbids the key outright, so an override cannot creep back in.
That the name is a key of this table at all is checked by
``tests/test_api.py::test_metadata_parameter_table`` rather than at import time, so no user pays
for validating declarations that only a contributor can get wrong.

A name maps to exactly one ``unit_type``. Where a source reports a different physical quantity it
gets its own name, not a different unit type for the same one -- see the ``radiation_*`` /
``radiation_*_intensity`` pairs, which are irradiation (energy per area accumulated over the
interval) and irradiance (power per area), and are not convertible without the interval.

``description`` is one sentence saying what the quantity is, written once here rather than once per
provider. It is provider- and resolution-independent on purpose: it describes the quantity, not a
particular source's version of it, so it says "mean air temperature at 2 m above ground" and not
"daily mean of air temperature". What a given source calls the parameter, and any caveats specific
to that source, belong in the provider metadata instead.

The descriptions feed the docs glossary, the REST API and the MCP tools, all of which previously
exposed parameter names with no explanation of what they measure.

``interpolation`` and ``zero_inflated`` say how the quantity behaves in space, which is the other
thing that is true of a quantity rather than of a provider. They used to be spelled out as three
hand-maintained name lists -- ``TimeseriesRequest.interpolatable_parameters``, the
``ts_geo_station_distance`` defaults in ``settings`` and ``_OCCURRENCE_BASED_PARAMETERS`` in
``core.interpolate`` -- which had to agree about the same names and could only be kept in step by a
test. All three are derived from these two fields now.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from wetterdienst.metadata.unit_type import UnitType

# How far a quantity stays correlated in space, which sets the default search radius for
# interpolation and summarization (``Settings.ts_geo_station_distance``):
#
# - "homogeneous": a smooth regional field -- temperature, pressure, humidity, wind, radiation,
#   lying snow, model probabilities. Meaningful out to the wide default radius.
# - "heterogeneous": a field that decorrelates over a much shorter distance -- precipitation and
#   fresh snow, which are convectively driven, and visibility, which is made and unmade by fog
#   banks a few kilometres across. Half the radius at hourly resolution, and the radius follows the
#   accumulation period from there -- see `Settings.ts_geo_station_distance_for`.
# - ``None``: not interpolated at all. Coded observations (weather type, cloud genus, road surface
#   condition), quality flags, counts and bookkeeping have no meaningful value between two
#   stations, and neither do quantities tied to a particular body of water (discharge, stage,
#   water temperature) or to a station's own instrument (measurement errors, uncertainties).
#   Directions are excluded too: interpolating 350 deg and 10 deg linearly gives south. So are the
#   soil temperatures whose surface cover is recorded as "unknown": the rest of that family is
#   interpolatable because the cover is part of the name, and that is exactly what does not hold
#   when the cover was never recorded and two stations may be measuring under different surfaces.
#
# A ``Literal`` rather than an enum, for the same reason as ``UnitType``: a typo in a table entry
# is then a type error under ``ty`` rather than something only a test can catch.
Interpolation = Literal["homogeneous", "heterogeneous"]


@dataclass(frozen=True, slots=True)
class CanonicalParameter:
    """Properties of a measured quantity, shared by every provider that reports it."""

    name: str
    unit_type: UnitType
    # required rather than defaulted: every parameter has one, and a new entry without a
    # description should not be constructible in the first place
    description: str
    # defaulted, unlike the fields above: not being interpolated is the safe answer for a quantity
    # nobody has classified, and it is what the majority of the table is
    interpolation: Interpolation | None = None
    # whether zero is a normal, frequent value meaning "the event did not happen here" -- true of
    # rainfall and fresh snow, false of a temperature or a climatological normal. Interpolation
    # thresholds these on occurrence, so that a station that recorded rain and one that recorded
    # none do not average out into a drizzle that fell nowhere. Independent of ``interpolation``:
    # visibility decorrelates quickly without being zero-inflated, and a precipitation normal is
    # heterogeneous without ever being zero.
    zero_inflated: bool = False


PARAMETER_TABLE: tuple[CanonicalParameter, ...] = (
    CanonicalParameter("chlorid_concentration", "concentration", "Concentration of chloride dissolved in the water."),
    CanonicalParameter(
        "clearance_height", "length_short", "Vertical clearance between the water surface and the structure above it."
    ),
    CanonicalParameter(
        "climate_correction_factor", "dimensionless", "Factor correcting a degree-day total for the local climate."
    ),
    CanonicalParameter(
        "cloud_base_convective",
        "length_medium",
        "Height above ground of the base of convective cloud.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_above_7km",
        "fraction",
        "Fraction of the sky covered by cloud above 7 km.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_below_1000ft",
        "fraction",
        "Fraction of the sky covered by cloud below 1000 ft.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_below_500ft",
        "fraction",
        "Fraction of the sky covered by cloud below 500 ft.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_below_7km",
        "fraction",
        "Fraction of the sky covered by cloud below 7 km.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_between_2km_to_7km",
        "fraction",
        "Fraction of the sky covered by cloud between 2 km and 7 km.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_effective",
        "fraction",
        "Effective cloud cover, weighting each layer by how much it attenuates radiation.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_layer1", "fraction", "Fraction of the sky covered by cloud in the lowest reported layer."
    ),
    CanonicalParameter(
        "cloud_cover_layer2", "fraction", "Fraction of the sky covered by cloud in the second reported layer."
    ),
    CanonicalParameter(
        "cloud_cover_layer3", "fraction", "Fraction of the sky covered by cloud in the third reported layer."
    ),
    CanonicalParameter(
        "cloud_cover_layer4", "fraction", "Fraction of the sky covered by cloud in the fourth reported layer."
    ),
    CanonicalParameter(
        "cloud_cover_total",
        "fraction",
        "Fraction of the sky covered by cloud of any kind.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_total_measurement_method",
        "dimensionless",
        "Coded indicator of how the total cloud cover was determined, such as by a person or an instrument.",
    ),
    CanonicalParameter(
        "cloud_cover_total_midnight_to_midnight",
        "fraction",
        "Mean total cloud cover over the calendar day, midnight to midnight.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_total_midnight_to_midnight_manual",
        "fraction",
        "Mean total cloud cover over the calendar day, midnight to midnight, from manual observation.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_total_sunrise_to_sunset",
        "fraction",
        "Mean total cloud cover over the daylight hours, sunrise to sunset.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cloud_cover_total_sunrise_to_sunset_manual",
        "fraction",
        "Mean total cloud cover over the daylight hours, sunrise to sunset, from manual observation.",
        interpolation="homogeneous",
    ),
    CanonicalParameter("cloud_density", "dimensionless", "Optical density of the cloud."),
    CanonicalParameter(
        "cloud_height_layer1", "length_medium", "Height above ground of the base of the lowest reported cloud layer."
    ),
    CanonicalParameter(
        "cloud_height_layer2", "length_medium", "Height above ground of the base of the second reported cloud layer."
    ),
    CanonicalParameter(
        "cloud_height_layer3", "length_medium", "Height above ground of the base of the third reported cloud layer."
    ),
    CanonicalParameter(
        "cloud_height_layer4", "length_medium", "Height above ground of the base of the fourth reported cloud layer."
    ),
    CanonicalParameter("cloud_type_layer1", "dimensionless", "Coded cloud genus of the lowest reported cloud layer."),
    CanonicalParameter("cloud_type_layer2", "dimensionless", "Coded cloud genus of the second reported cloud layer."),
    CanonicalParameter("cloud_type_layer3", "dimensionless", "Coded cloud genus of the third reported cloud layer."),
    CanonicalParameter("cloud_type_layer4", "dimensionless", "Coded cloud genus of the fourth reported cloud layer."),
    CanonicalParameter(
        "cooling_degree_day",
        "degree_day",
        "Cooling degree days, the temperature excess above a base value summed over each day.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "cooling_degree_hour",
        "degree_hour",
        "Cooling degree hours, the temperature excess above a base value summed over each hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter("count_days_cooling_degree", "dimensionless", "Number of days on which cooling was required."),
    CanonicalParameter(
        "count_days_frost",
        "dimensionless",
        "Number of days on which the minimum air temperature fell below 0 degrees Celsius.",
    ),
    CanonicalParameter("count_days_heating_degree", "dimensionless", "Number of days on which heating was required."),
    CanonicalParameter(
        "count_days_hot",
        "dimensionless",
        "Number of days on which the maximum air temperature reached at least 30 degrees Celsius.",
    ),
    CanonicalParameter(
        "count_days_ice",
        "dimensionless",
        "Number of days on which the maximum air temperature stayed below 0 degrees Celsius.",
    ),
    CanonicalParameter(
        "count_days_multiday_evaporation", "dimensionless", "Number of days covered by a multi-day evaporation total."
    ),
    CanonicalParameter(
        "count_days_multiday_precipitation",
        "dimensionless",
        "Number of days covered by a multi-day precipitation total.",
    ),
    CanonicalParameter(
        "count_days_multiday_precipitation_height_gt_0mm",
        "dimensionless",
        "Number of days with measurable precipitation within a multi-day total.",
    ),
    CanonicalParameter(
        "count_days_multiday_snow_depth_new", "dimensionless", "Number of days covered by a multi-day fresh snow total."
    ),
    CanonicalParameter(
        "count_days_multiday_temperature_air_max_2m",
        "dimensionless",
        "Number of days covered by a multi-day maximum air temperature.",
    ),
    CanonicalParameter(
        "count_days_multiday_temperature_air_min_2m",
        "dimensionless",
        "Number of days covered by a multi-day minimum air temperature.",
    ),
    CanonicalParameter(
        "count_days_multiday_wind_movement", "dimensionless", "Number of days covered by a multi-day wind run total."
    ),
    CanonicalParameter(
        "count_days_precipitation_height_ge_0_1mm",
        "dimensionless",
        "Number of days on which at least 0.1 mm of precipitation fell.",
    ),
    CanonicalParameter(
        "count_days_precipitation_height_ge_10mm",
        "dimensionless",
        "Number of days on which at least 10 mm of precipitation fell.",
    ),
    CanonicalParameter(
        "count_days_precipitation_height_ge_1mm",
        "dimensionless",
        "Number of days on which at least 1 mm of precipitation fell.",
    ),
    CanonicalParameter(
        "count_days_precipitation_height_ge_20mm",
        "dimensionless",
        "Number of days on which at least 20 mm of precipitation fell.",
    ),
    CanonicalParameter(
        "count_days_precipitation_height_ge_2_5mm",
        "dimensionless",
        "Number of days on which at least 2.5 mm of precipitation fell.",
    ),
    CanonicalParameter(
        "count_days_precipitation_height_ge_5mm",
        "dimensionless",
        "Number of days on which at least 5 mm of precipitation fell.",
    ),
    CanonicalParameter(
        "count_days_snow_depth_ge_1cm",
        "dimensionless",
        "Number of days on which the snow depth reached at least 1 cm.",
    ),
    CanonicalParameter(
        "count_days_snow_depth_ge_5cm",
        "dimensionless",
        "Number of days on which the snow depth reached at least 5 cm.",
    ),
    CanonicalParameter(
        "count_days_summer",
        "dimensionless",
        "Number of days on which the maximum air temperature reached at least 25 degrees Celsius.",
    ),
    CanonicalParameter(
        "count_days_tropical_night",
        "dimensionless",
        "Number of nights on which the minimum air temperature stayed at or above 20 degrees Celsius.",
    ),
    CanonicalParameter(
        "count_days_valid_precipitation_height",
        "dimensionless",
        "Number of days in the period carrying a valid precipitation observation.",
    ),
    CanonicalParameter(
        "count_days_valid_snow_depth_new",
        "dimensionless",
        "Number of days in the period carrying a valid fresh snow observation.",
    ),
    CanonicalParameter(
        "count_days_valid_sunshine_duration",
        "dimensionless",
        "Number of days in the period carrying a valid sunshine duration observation.",
    ),
    CanonicalParameter(
        "count_days_valid_temperature_air_max_2m",
        "dimensionless",
        "Number of days in the period carrying a valid maximum air temperature observation.",
    ),
    CanonicalParameter(
        "count_days_valid_temperature_air_mean_2m",
        "dimensionless",
        "Number of days in the period carrying a valid mean air temperature observation.",
    ),
    CanonicalParameter(
        "count_days_valid_temperature_air_min_2m",
        "dimensionless",
        "Number of days in the period carrying a valid minimum air temperature observation.",
    ),
    CanonicalParameter(
        "count_hours_cooling_degree", "dimensionless", "Number of hours during which cooling was required."
    ),
    CanonicalParameter("count_weather_type_dew", "dimensionless", "Number of days on which dew was observed."),
    CanonicalParameter("count_weather_type_fog", "dimensionless", "Number of days on which fog was observed."),
    CanonicalParameter("count_weather_type_glaze", "dimensionless", "Number of days on which glaze ice was observed."),
    CanonicalParameter("count_weather_type_hail", "dimensionless", "Number of days on which hail was observed."),
    CanonicalParameter("count_weather_type_ripe", "dimensionless", "Number of days on which hoar frost was observed."),
    CanonicalParameter("count_weather_type_sleet", "dimensionless", "Number of days on which sleet was observed."),
    CanonicalParameter(
        "count_weather_type_storm_stormier_wind",
        "dimensionless",
        "Number of days with wind reaching at least Beaufort 8.",
    ),
    CanonicalParameter(
        "count_weather_type_storm_strong_wind",
        "dimensionless",
        "Number of days with wind reaching at least Beaufort 6.",
    ),
    CanonicalParameter("count_weather_type_thunder", "dimensionless", "Number of days on which thunder was heard."),
    CanonicalParameter("discharge", "volume_per_time", "Volume of water passing the gauge per unit of time."),
    CanonicalParameter("discharge_max", "volume_per_time", "Highest discharge observed over the period."),
    CanonicalParameter("discharge_mean", "volume_per_time", "Mean discharge over the period."),
    CanonicalParameter("discharge_min", "volume_per_time", "Lowest discharge observed over the period."),
    CanonicalParameter(
        "distance_river_gauge_height", "length_short", "Height of the gauge zero point above the reference datum."
    ),
    CanonicalParameter(
        "electric_conductivity",
        "conductivity",
        "Electrical conductivity of the water, a proxy for its dissolved salt content.",
    ),
    CanonicalParameter(
        "error_absolute_pressure_air_site", "pressure", "Absolute error attached to the reported air pressure."
    ),
    CanonicalParameter(
        "error_absolute_temperature_air_mean_2m",
        "temperature",
        "Absolute error attached to the reported air temperature.",
    ),
    CanonicalParameter(
        "error_absolute_temperature_dew_point_mean_2m",
        "temperature",
        "Absolute error attached to the reported dew point.",
    ),
    CanonicalParameter(
        "error_absolute_wind_direction", "angle", "Absolute error attached to the reported wind direction."
    ),
    CanonicalParameter("error_absolute_wind_speed", "speed", "Absolute error attached to the reported wind speed."),
    CanonicalParameter(
        "evaporation_height",
        "precipitation",
        "Depth of water evaporated from the surface.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evaporation_height_corn_loamysilt",
        "precipitation",
        "Depth of water evaporated from loamy silt under corn.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evaporation_height_corn_sand",
        "precipitation",
        "Depth of water evaporated from sand under corn.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evaporation_height_gras_loamysilt",
        "precipitation",
        "Depth of water evaporated from loamy silt under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evaporation_height_gras_sand",
        "precipitation",
        "Depth of water evaporated from sand under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evaporation_height_multiday",
        "precipitation",
        "Depth of water evaporated over several days, reported as one total.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evaporation_height_winterwheat_loamysilt",
        "precipitation",
        "Depth of water evaporated from loamy silt under winter wheat.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evaporation_height_winterwheat_sand",
        "precipitation",
        "Depth of water evaporated from sand under winter wheat.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evapotranspiration_last_24h",
        "precipitation",
        "Water evaporated and transpired in the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evapotranspiration_potential_gras_fao_last_24h",
        "precipitation",
        "Potential evapotranspiration over grass in the preceding 24 hours, after the FAO reference method.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evapotranspiration_potential_gras_haude_last_24h",
        "precipitation",
        "Potential evapotranspiration over grass in the preceding 24 hours, after the Haude method.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "evapotranspiration_potential_last_24h",
        "precipitation",
        "Potential evapotranspiration in the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "flow_direction", "angle", "Direction the water current is flowing towards, clockwise from magnetic north."
    ),
    CanonicalParameter("flow_speed", "speed", "Speed at which the water is flowing past the gauge."),
    CanonicalParameter(
        "frozen_ground_layer_base", "length_short", "Depth below the surface at which the frozen layer ends."
    ),
    CanonicalParameter("frozen_ground_layer_thickness", "length_short", "Thickness of the frozen ground layer."),
    CanonicalParameter(
        "frozen_ground_layer_thickness_max_month",
        "length_short",
        "Greatest thickness the frozen ground layer reached during the month.",
    ),
    CanonicalParameter(
        "frozen_ground_layer_top", "length_short", "Depth below the surface at which the frozen layer begins."
    ),
    CanonicalParameter("groundwater_level", "length_medium", "Level of the groundwater table."),
    CanonicalParameter("groundwater_level_max", "length_medium", "Highest groundwater level over the period."),
    CanonicalParameter("groundwater_level_min", "length_medium", "Lowest groundwater level over the period."),
    CanonicalParameter(
        "heating_degree_day",
        "degree_day",
        "Heating degree days, the temperature shortfall below a base value summed over each day.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "humidity",
        "fraction",
        "Relative humidity of the air, the fraction of the moisture it could hold at that temperature.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "humidity_absolute",
        "mass_per_volume",
        "Absolute humidity, the mass of water vapour per volume of air.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "humidity_max", "fraction", "Highest relative humidity over the period.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "humidity_min", "fraction", "Lowest relative humidity over the period.", interpolation="homogeneous"
    ),
    CanonicalParameter("ice_on_water_thickness", "length_short", "Thickness of the ice covering the water surface."),
    CanonicalParameter("number_of_days_per_month", "dimensionless", "Number of days in the month the record covers."),
    CanonicalParameter("number_of_hours_per_month", "dimensionless", "Number of hours in the month the record covers."),
    CanonicalParameter("oxygen_level", "concentration", "Concentration of oxygen dissolved in the water."),
    CanonicalParameter("ph_value", "dimensionless", "Acidity of the water on the pH scale."),
    # The phenological phases of the DWD phenology network. A value is the day of the year on
    # which the phase was observed, so these are dimensionless and are left unclassified for
    # interpolation: an onset date is an event at one plant at one station, and the library has
    # no notion of averaging two of them into a date that happened at neither.
    CanonicalParameter(
        "phenology_activity_beginning", "dimensionless", "Day of the year on which the recorded farming activity began."
    ),
    CanonicalParameter(
        "phenology_activity_end", "dimensionless", "Day of the year on which the recorded farming activity ended."
    ),
    CanonicalParameter(
        "phenology_bleeding_first", "dimensionless", "Day of the year on which sap first bled from the pruned vine."
    ),
    CanonicalParameter(
        "phenology_bud_formation_beginning", "dimensionless", "Day of the year on which flower bud formation began."
    ),
    CanonicalParameter(
        "phenology_bud_swelling", "dimensionless", "Day of the year on which the buds first swelled noticeably."
    ),
    CanonicalParameter(
        "phenology_dough_ripeness_beginning",
        "dimensionless",
        "Day of the year on which the grain reached dough (wax-ripe) stage.",
    ),
    CanonicalParameter(
        "phenology_emergence_beginning", "dimensionless", "Day of the year on which the first seedlings emerged."
    ),
    CanonicalParameter(
        "phenology_flowering_beginning", "dimensionless", "Day of the year on which the first flowers opened."
    ),
    CanonicalParameter(
        "phenology_flowering_end", "dimensionless", "Day of the year on which the last flowers had faded."
    ),
    CanonicalParameter(
        "phenology_flowering_end_observation_area",
        "dimensionless",
        "Day of the year on which flowering ended across the whole observation area.",
    ),
    CanonicalParameter(
        "phenology_flowering_general", "dimensionless", "Day of the year on which about half of the flowers were open."
    ),
    CanonicalParameter(
        "phenology_fruit_ripe_first", "dimensionless", "Day of the year on which the first fruits were fully ripe."
    ),
    CanonicalParameter(
        "phenology_full_ripeness_beginning", "dimensionless", "Day of the year on which the crop reached full ripeness."
    ),
    CanonicalParameter(
        "phenology_grain_harvest_beginning", "dimensionless", "Day of the year on which the grain harvest began."
    ),
    CanonicalParameter(
        "phenology_grape_harvest", "dimensionless", "Day of the year on which the grapes were harvested."
    ),
    CanonicalParameter(
        "phenology_grape_picking_ripeness",
        "dimensionless",
        "Day of the year on which the grapes were ripe for picking.",
    ),
    CanonicalParameter(
        "phenology_grape_ripeness_beginning",
        "dimensionless",
        "Day of the year on which the grapes began to ripen (veraison).",
    ),
    CanonicalParameter("phenology_harvest", "dimensionless", "Day of the year on which the crop was harvested."),
    CanonicalParameter(
        "phenology_harvest_by_hand", "dimensionless", "Day of the year on which the crop was harvested by hand."
    ),
    CanonicalParameter(
        "phenology_hay_cut_first", "dimensionless", "Day of the year of the first cut of the grassland for hay."
    ),
    CanonicalParameter(
        "phenology_hay_cut_second", "dimensionless", "Day of the year of the second cut of the grassland for hay."
    ),
    CanonicalParameter(
        "phenology_hay_or_silage_cut_first",
        "dimensionless",
        "Day of the year of the first cut of the grassland for hay or silage.",
    ),
    CanonicalParameter(
        "phenology_hay_or_silage_cut_second",
        "dimensionless",
        "Day of the year of the second cut of the grassland for hay or silage.",
    ),
    CanonicalParameter(
        "phenology_heading_beginning",
        "dimensionless",
        "Day of the year on which the first ears emerged from the flag leaf.",
    ),
    CanonicalParameter(
        "phenology_height_growth_beginning", "dimensionless", "Day of the year on which growth in height began."
    ),
    CanonicalParameter(
        "phenology_leaf_colouring_autumn",
        "dimensionless",
        "Day of the year on which about half of the leaves had taken on their autumn colour.",
    ),
    CanonicalParameter(
        "phenology_leaf_fall_autumn", "dimensionless", "Day of the year on which about half of the leaves had fallen."
    ),
    CanonicalParameter(
        "phenology_leaf_formation_beginning", "dimensionless", "Day of the year on which leaf formation began."
    ),
    CanonicalParameter(
        "phenology_leaf_unfolding_beginning",
        "dimensionless",
        "Day of the year on which the first leaves had fully unfolded.",
    ),
    CanonicalParameter(
        "phenology_may_sprouting",
        "dimensionless",
        "Day of the year on which the May shoots of the conifer broke from the buds.",
    ),
    CanonicalParameter(
        "phenology_milk_ripeness_beginning",
        "dimensionless",
        "Day of the year on which the grain reached milk ripeness.",
    ),
    CanonicalParameter(
        "phenology_needle_colouring_autumn",
        "dimensionless",
        "Day of the year on which about half of the needles had taken on their autumn colour.",
    ),
    CanonicalParameter(
        "phenology_needle_fall_autumn",
        "dimensionless",
        "Day of the year on which about half of the needles had fallen.",
    ),
    CanonicalParameter(
        "phenology_needle_unfolding_beginning",
        "dimensionless",
        "Day of the year on which the first needle bundles unfolded.",
    ),
    CanonicalParameter(
        "phenology_panicle_emergence_beginning", "dimensionless", "Day of the year on which the panicle first emerged."
    ),
    CanonicalParameter(
        "phenology_picking_ripeness_beginning",
        "dimensionless",
        "Day of the year on which the fruit was first ripe for picking.",
    ),
    CanonicalParameter(
        "phenology_planting_beginning", "dimensionless", "Day of the year on which planting out of the crop began."
    ),
    CanonicalParameter(
        "phenology_rosette_formation_beginning", "dimensionless", "Day of the year on which rosette formation began."
    ),
    CanonicalParameter(
        "phenology_shooting_beginning", "dimensionless", "Day of the year on which stem elongation (shooting) began."
    ),
    CanonicalParameter(
        "phenology_silage_cut_first", "dimensionless", "Day of the year of the first cut of the grassland for silage."
    ),
    CanonicalParameter(
        "phenology_silage_cut_second", "dimensionless", "Day of the year of the second cut of the grassland for silage."
    ),
    CanonicalParameter(
        "phenology_silage_harvest_beginning", "dimensionless", "Day of the year on which the silage harvest began."
    ),
    CanonicalParameter(
        "phenology_silk_emergence_beginning",
        "dimensionless",
        "Day of the year on which the silks of the maize first emerged.",
    ),
    CanonicalParameter(
        "phenology_sowing_beginning", "dimensionless", "Day of the year on which sowing or drilling of the crop began."
    ),
    CanonicalParameter(
        "phenology_sprouting_beginning",
        "dimensionless",
        "Day of the year on which the first buds broke and leaf green became visible.",
    ),
    CanonicalParameter(
        "phenology_st_johns_sprouting",
        "dimensionless",
        "Day of the year on which the midsummer (St. John's) shoot appeared.",
    ),
    CanonicalParameter(
        "phenology_stand_closed", "dimensionless", "Day of the year on which the crop stand had closed over the rows."
    ),
    CanonicalParameter(
        "phenology_tassel_tip_visible",
        "dimensionless",
        "Day of the year on which the tip of the maize tassel first became visible.",
    ),
    CanonicalParameter(
        "phenology_turning_green_beginning", "dimensionless", "Day of the year on which the plant began to turn green."
    ),
    CanonicalParameter(
        "phenology_yellow_ripeness_beginning",
        "dimensionless",
        "Day of the year on which the crop reached yellow ripeness.",
    ),
    CanonicalParameter(
        "precipitation_duration",
        "time",
        "Length of time during which precipitation fell.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_form", "dimensionless", "Coded form of the precipitation, such as rain, snow or freezing rain."
    ),
    CanonicalParameter(
        "precipitation_height",
        "precipitation",
        "Depth of precipitation collected over the period.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_day",
        "precipitation",
        "Depth of precipitation collected during the daytime hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_droplet",
        "precipitation",
        "Depth of precipitation measured by the droplet sensor of the gauge.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_12h",
        "precipitation",
        "Depth of precipitation collected over the preceding 12 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_15h",
        "precipitation",
        "Depth of precipitation collected over the preceding 15 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_18h",
        "precipitation",
        "Depth of precipitation collected over the preceding 18 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_1h",
        "precipitation",
        "Depth of precipitation collected over the preceding hour.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_21h",
        "precipitation",
        "Depth of precipitation collected over the preceding 21 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_24h",
        "precipitation",
        "Depth of precipitation collected over the preceding 24 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_3h",
        "precipitation",
        "Depth of precipitation collected over the preceding 3 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_6h",
        "precipitation",
        "Depth of precipitation collected over the preceding 6 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_last_9h",
        "precipitation",
        "Depth of precipitation collected over the preceding 9 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_liquid",
        "precipitation",
        "Depth of the liquid part of the precipitation.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_liquid_significant_weather_last_1h",
        "precipitation",
        "Depth of liquid precipitation from significant weather in the preceding hour.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_max",
        "precipitation",
        "Greatest precipitation depth recorded in any single interval of the period.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_multiday",
        "precipitation",
        "Depth of precipitation over several days, reported as one total.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_night",
        "precipitation",
        "Depth of precipitation collected during the night hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_normal",
        "precipitation",
        "Climatological normal of the precipitation height for the period.",
        interpolation="heterogeneous",
    ),
    CanonicalParameter(
        "precipitation_height_rocker",
        "precipitation",
        "Depth of precipitation measured by the tipping-bucket sensor of the gauge.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_12h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding 12 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_1h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding hour.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_24h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding 24 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_3h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding 3 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_6h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding 6 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter("precipitation_index", "dimensionless", "Coded indicator of whether precipitation occurred."),
    CanonicalParameter(
        "precipitation_intensity",
        "precipitation_intensity",
        "Rate at which precipitation is falling.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "pressure_air_sea_level",
        "pressure",
        "Air pressure reduced to mean sea level, so that stations at different heights compare.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "pressure_air_site", "pressure", "Air pressure as measured at station height.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "pressure_air_site_delta_last_3h",
        "pressure",
        "Change in air pressure at station height over the preceding 3 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "pressure_air_site_max",
        "pressure",
        "Highest air pressure at station height over the period.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "pressure_air_site_min",
        "pressure",
        "Lowest air pressure at station height over the period.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "pressure_air_site_reduced",
        "pressure",
        "Air pressure at station height reduced to a reference level.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "pressure_vapor", "pressure", "Partial pressure of water vapour in the air.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "probability_drizzle_last_12h",
        "fraction",
        "Probability of drizzle over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_drizzle_last_1h",
        "fraction",
        "Probability of drizzle over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_drizzle_last_6h",
        "fraction",
        "Probability of drizzle over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_fog_last_12h",
        "fraction",
        "Probability of fog over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_fog_last_1h",
        "fraction",
        "Probability of fog over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_fog_last_24h",
        "fraction",
        "Probability of fog over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_fog_last_6h",
        "fraction",
        "Probability of fog over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_convective_last_12h",
        "fraction",
        "Probability of convective precipitation over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_convective_last_1h",
        "fraction",
        "Probability of convective precipitation over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_convective_last_6h",
        "fraction",
        "Probability of convective precipitation over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_freezing_last_12h",
        "fraction",
        "Probability of freezing precipitation over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_freezing_last_1h",
        "fraction",
        "Probability of freezing precipitation over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_freezing_last_6h",
        "fraction",
        "Probability of freezing precipitation over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_0mm_last_12h",
        "fraction",
        "Probability that more than 0.0 mm of precipitation fell over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_0mm_last_24h",
        "fraction",
        "Probability that more than 0.0 mm of precipitation fell over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_0mm_last_6h",
        "fraction",
        "Probability that more than 0.0 mm of precipitation fell over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_1mm_last_1h",
        "fraction",
        "Probability that more than 0.1 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_2mm_last_12h",
        "fraction",
        "Probability that more than 0.2 mm of precipitation fell over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_2mm_last_1h",
        "fraction",
        "Probability that more than 0.2 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_2mm_last_24h",
        "fraction",
        "Probability that more than 0.2 mm of precipitation fell over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_2mm_last_6h",
        "fraction",
        "Probability that more than 0.2 mm of precipitation fell over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_3mm_last_1h",
        "fraction",
        "Probability that more than 0.3 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_5mm_last_1h",
        "fraction",
        "Probability that more than 0.5 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_7mm_last_1h",
        "fraction",
        "Probability that more than 0.7 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_10mm_last_1h",
        "fraction",
        "Probability that more than 10 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_15mm_last_1h",
        "fraction",
        "Probability that more than 15 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_1mm_last_12h",
        "fraction",
        "Probability that more than 1 mm of precipitation fell over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_1mm_last_1h",
        "fraction",
        "Probability that more than 1 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_1mm_last_24h",
        "fraction",
        "Probability that more than 1 mm of precipitation fell over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_1mm_last_6h",
        "fraction",
        "Probability that more than 1 mm of precipitation fell over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_25mm_last_1h",
        "fraction",
        "Probability that more than 25 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_2mm_last_1h",
        "fraction",
        "Probability that more than 2 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_3mm_last_1h",
        "fraction",
        "Probability that more than 3 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_5mm_last_12h",
        "fraction",
        "Probability that more than 5 mm of precipitation fell over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_5mm_last_1h",
        "fraction",
        "Probability that more than 5 mm of precipitation fell over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_5mm_last_24h",
        "fraction",
        "Probability that more than 5 mm of precipitation fell over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_5mm_last_6h",
        "fraction",
        "Probability that more than 5 mm of precipitation fell over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_last_12h",
        "fraction",
        "Probability of precipitation of any kind over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_last_1h",
        "fraction",
        "Probability of precipitation of any kind over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_last_24h",
        "fraction",
        "Probability of precipitation of any kind over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_last_6h",
        "fraction",
        "Probability of precipitation of any kind over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_liquid_last_12h",
        "fraction",
        "Probability of liquid precipitation over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_liquid_last_1h",
        "fraction",
        "Probability of liquid precipitation over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_liquid_last_6h",
        "fraction",
        "Probability of liquid precipitation over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_solid_last_12h",
        "fraction",
        "Probability of solid precipitation over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_solid_last_1h",
        "fraction",
        "Probability of solid precipitation over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_solid_last_6h",
        "fraction",
        "Probability of solid precipitation over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_stratiform_last_12h",
        "fraction",
        "Probability of stratiform precipitation over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_stratiform_last_1h",
        "fraction",
        "Probability of stratiform precipitation over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_precipitation_stratiform_last_6h",
        "fraction",
        "Probability of stratiform precipitation over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_radiation_global_last_1h",
        "fraction",
        "Probability of measurable global radiation over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_sunshine_duration_relative_gt_0pct_last_24h",
        "fraction",
        "Probability that sunshine lasted more than 0 % of the possible duration over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_sunshine_duration_relative_gt_30pct_last_24h",
        "fraction",
        "Probability that sunshine lasted more than 30 % of the possible duration over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_sunshine_duration_relative_gt_60pct_last_24h",
        "fraction",
        "Probability that sunshine lasted more than 60 % of the possible duration over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_thunder_last_12h",
        "fraction",
        "Probability of thunderstorm over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_thunder_last_1h",
        "fraction",
        "Probability of thunderstorm over the preceding hour.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_thunder_last_24h",
        "fraction",
        "Probability of thunderstorm over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_thunder_last_6h",
        "fraction",
        "Probability of thunderstorm over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_visibility_below_1000m",
        "fraction",
        "Probability that visibility falls below 1000 m.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_25kn_last_12h",
        "fraction",
        "Probability of a wind gust reaching 25 kn or more over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_25kn_last_6h",
        "fraction",
        "Probability of a wind gust reaching 25 kn or more over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_40kn_last_12h",
        "fraction",
        "Probability of a wind gust reaching 40 kn or more over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_40kn_last_6h",
        "fraction",
        "Probability of a wind gust reaching 40 kn or more over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_55kn_last_12h",
        "fraction",
        "Probability of a wind gust reaching 55 kn or more over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_55kn_last_6h",
        "fraction",
        "Probability of a wind gust reaching 55 kn or more over the preceding 6 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "quality", "dimensionless", "Quality flag published by the source for the values in the same dataset."
    ),
    CanonicalParameter(
        "quality_3", "dimensionless", "Quality flag for the 3-hourly maximum wind gust reported in the same dataset."
    ),
    CanonicalParameter(
        "quality_6", "dimensionless", "Quality flag for the 6-hourly maximum wind gust reported in the same dataset."
    ),
    CanonicalParameter(
        "quality_general", "dimensionless", "Quality flag published by the source, applying to the dataset as a whole."
    ),
    CanonicalParameter(
        "quality_precipitation",
        "dimensionless",
        "Quality flag published by the source for `precipitation` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_precipitation_height",
        "dimensionless",
        "Quality flag published by the source for `precipitation_height` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_precipitation_height_liquid",
        "dimensionless",
        "Quality flag published by the source for `precipitation_height_liquid` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_snow_depth",
        "dimensionless",
        "Quality flag published by the source for `snow_depth` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_snow_depth_new",
        "dimensionless",
        "Quality flag published by the source for `snow_depth_new` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_temperature_air_max_2m",
        "dimensionless",
        "Quality flag published by the source for `temperature_air_max_2m` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_temperature_air_max_2m_mean",
        "dimensionless",
        "Quality flag published by the source for `temperature_air_max_2m_mean` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_temperature_air_mean_2m",
        "dimensionless",
        "Quality flag published by the source for `temperature_air_mean_2m` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_temperature_air_min_2m",
        "dimensionless",
        "Quality flag published by the source for `temperature_air_min_2m` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_temperature_air_min_2m_mean",
        "dimensionless",
        "Quality flag published by the source for `temperature_air_min_2m_mean` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_wind", "dimensionless", "Quality flag published by the source for `wind` in the same dataset."
    ),
    CanonicalParameter(
        "quality_wind_direction_gust_max",
        "dimensionless",
        "Quality flag published by the source for `wind_direction_gust_max` in the same dataset.",
    ),
    CanonicalParameter(
        "quality_wind_gust_max",
        "dimensionless",
        "Quality flag published by the source for `wind_gust_max` in the same dataset.",
    ),
    CanonicalParameter(
        "radiation_global",
        "energy_per_area",
        "Global radiation received on a horizontal surface, accumulated as energy over the interval.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_global_intensity",
        "power_per_area",
        "Global irradiance on a horizontal surface, reported as power rather than energy.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_global_last_3h",
        "energy_per_area",
        "Global radiation accumulated over the preceding 3 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_global_uncertainty", "energy_per_area", "Uncertainty attached to the reported global radiation."
    ),
    CanonicalParameter(
        "radiation_sky_long_wave",
        "energy_per_area",
        "Downward long-wave radiation from the sky, accumulated as energy over the interval.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_sky_long_wave_intensity",
        "power_per_area",
        "Downward long-wave irradiance from the sky, reported as power.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_sky_long_wave_last_3h",
        "energy_per_area",
        "Downward long-wave radiation from the sky over the preceding 3 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_sky_short_wave_diffuse",
        "energy_per_area",
        "Diffuse short-wave radiation from the sky, accumulated as energy over the interval.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_sky_short_wave_diffuse_intensity",
        "power_per_area",
        "Diffuse short-wave irradiance from the sky, reported as power.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_sky_short_wave_direct",
        "energy_per_area",
        "Direct short-wave radiation from the sun, accumulated as energy over the interval.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "radiation_sky_short_wave_direct_intensity",
        "power_per_area",
        "Direct short-wave irradiance from the sun, reported as power.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "road_surface_condition", "dimensionless", "Coded condition of the road surface, such as dry, wet or icy."
    ),
    CanonicalParameter(
        "snow_depth", "length_short", "Depth of the snow lying on the ground.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "snow_depth_excelled",
        "length_short",
        "Depth of the snow cover where it exceeded the measuring range.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "snow_depth_manual",
        "length_short",
        "Depth of the snow lying on the ground, from manual observation.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "snow_depth_max", "length_short", "Greatest snow depth over the period.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "snow_depth_new",
        "length_short",
        "Depth of snow that fell during the period.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "snow_depth_new_max",
        "length_short",
        "Greatest depth of fresh snow recorded over the period.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "snow_depth_new_multiday",
        "length_short",
        "Depth of fresh snow over several days, reported as one total.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "snow_depth_new_normal",
        "length_short",
        "Climatological normal of the fresh snow total for the period.",
        interpolation="heterogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_corn_loamysilt_00cm_60cm",
        "fraction",
        "Soil moisture in loamy silt under corn, between the surface and 60 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_corn_sand_00cm_60cm",
        "fraction",
        "Soil moisture in sand under corn, between the surface and 60 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_00cm_10cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between the surface and 10 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_00cm_60cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between the surface and 60 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_10cm_20cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 10 cm and 20 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_20cm_30cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 20 cm and 30 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_30cm_40cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 30 cm and 40 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_40cm_50cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 40 cm and 50 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_50cm_60cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 50 cm and 60 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_gras_sand_00cm_60cm",
        "fraction",
        "Soil moisture in sand under grass, between the surface and 60 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_winterwheat_loamysilt_00cm_60cm",
        "fraction",
        "Soil moisture in loamy silt under winter wheat, between the surface and 60 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_moisture_winterwheat_sand_00cm_60cm",
        "fraction",
        "Soil moisture in sand under winter wheat, between the surface and 60 cm.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "soil_state_index",
        "dimensionless",
        "Coded state of the ground surface, such as dry, moist, frozen or snow-covered.",
    ),
    CanonicalParameter("stage", "length_short", "Water level at the gauge, measured against the gauge datum."),
    CanonicalParameter("stage_max", "length_short", "Highest water level at the gauge over the period."),
    CanonicalParameter("stage_mean", "length_short", "Mean water level at the gauge over the period."),
    CanonicalParameter("stage_min", "length_short", "Lowest water level at the gauge over the period."),
    CanonicalParameter("sun_zenith_angle", "angle", "Angle between the sun and the vertical."),
    CanonicalParameter(
        "sunshine_duration", "time", "Length of time the sun shone unobstructed.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "sunshine_duration_last_3h",
        "time",
        "Length of time the sun shone unobstructed in the preceding 3 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "sunshine_duration_normal",
        "time",
        "Climatological normal of the sunshine duration for the period.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "sunshine_duration_relative",
        "fraction",
        "Sunshine duration as a fraction of the longest possible for the location and date.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "sunshine_duration_relative_last_24h",
        "fraction",
        "Relative sunshine duration over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "sunshine_duration_uncertainty", "time", "Uncertainty attached to the reported sunshine duration."
    ),
    CanonicalParameter(
        "sunshine_duration_yesterday",
        "time",
        "Length of time the sun shone unobstructed on the previous day.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_2m",
        "temperature",
        "Air temperature at 2 m above ground, the standard screen height.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_max_0_05m",
        "temperature",
        "Maximum air temperature at 0.05 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_max_2m",
        "temperature",
        "Maximum air temperature at 2 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_max_2m_last_12h",
        "temperature",
        "Maximum air temperature at 2 m above ground over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_max_2m_last_24h",
        "temperature",
        "Maximum air temperature at 2 m above ground over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_max_2m_mean",
        "temperature",
        "Mean of the daily maximum air temperature at 2 m above ground over the period.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_max_2m_multiday",
        "temperature",
        "Maximum air temperature at 2 m above ground, covering several days where a station did not report daily.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_max_2m_yesterday",
        "temperature",
        "Maximum air temperature at 2 m above ground on the previous day.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_mean_0_05m",
        "temperature",
        "Mean air temperature at 0.05 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_mean_0_1m",
        "temperature",
        "Mean air temperature at 0.1 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_mean_2m",
        "temperature",
        "Mean air temperature at 2 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_mean_2m_last_24h",
        "temperature",
        "Mean air temperature at 2 m above ground over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_mean_2m_normal",
        "temperature",
        "Climatological normal of the mean air temperature at 2 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_mean_2m_yesterday",
        "temperature",
        "Mean air temperature at 2 m above ground on the previous day.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_0_05m",
        "temperature",
        "Minimum air temperature at 0.05 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_0_05m_last_12h",
        "temperature",
        "Minimum air temperature at 0.05 m above ground over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_0_05m_yesterday",
        "temperature",
        "Minimum air temperature at 0.05 m above ground on the previous day.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_2m",
        "temperature",
        "Minimum air temperature at 2 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_2m_last_12h",
        "temperature",
        "Minimum air temperature at 2 m above ground over the preceding 12 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_2m_last_24h",
        "temperature",
        "Minimum air temperature at 2 m above ground over the preceding 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_2m_mean",
        "temperature",
        "Mean of the daily minimum air temperature at 2 m above ground over the period.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_2m_multiday",
        "temperature",
        "Minimum air temperature at 2 m above ground, covering several days where a station did not report daily.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_air_min_2m_yesterday",
        "temperature",
        "Minimum air temperature at 2 m above ground on the previous day.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_concrete_max_0m",
        "temperature",
        "Maximum temperature at the surface of a concrete slab.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_concrete_mean_0m",
        "temperature",
        "Mean temperature at the surface of a concrete slab.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_concrete_min_0m",
        "temperature",
        "Minimum temperature at the surface of a concrete slab.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_dew_point_mean_2m",
        "temperature",
        "Dew point at 2 m above ground, the temperature at which the air would become saturated.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_humidex",
        "temperature",
        "Humidex, the apparent temperature combining air temperature and humidity.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_radiant_mean_2m",
        "temperature",
        "Mean radiant temperature, the temperature a body feels from surrounding surfaces.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_1m", "temperature", "Maximum soil temperature at 1 m depth.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "temperature_soil_max_2m", "temperature", "Maximum soil temperature at 2 m depth.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_max_unknown_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_max_unknown_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_max_unknown_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_max_unknown_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_max_unknown_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_max_unknown_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_max_unknown_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_mean_0_02m",
        "temperature",
        "Mean soil temperature at 0.02 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_mean_0_05m",
        "temperature",
        "Mean soil temperature at 0.05 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_mean_0_1m",
        "temperature",
        "Mean soil temperature at 0.1 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_mean_0_2m",
        "temperature",
        "Mean soil temperature at 0.2 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_mean_0_5m",
        "temperature",
        "Mean soil temperature at 0.5 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_mean_1m", "temperature", "Mean soil temperature at 1 m depth.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "temperature_soil_mean_2m", "temperature", "Mean soil temperature at 2 m depth.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "temperature_soil_mean_loamysand_0_05m",
        "temperature",
        "Mean soil temperature at 0.05 m depth under loamy sand.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_mean_loamysilt_0_05m",
        "temperature",
        "Mean soil temperature at 0.05 m depth under loamy silt.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_1m", "temperature", "Minimum soil temperature at 1 m depth.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "temperature_soil_min_2m", "temperature", "Minimum soil temperature at 2 m depth.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under bare ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under bare muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under brome grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under fallow ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under grass.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under grass over muck soil.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under sod.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under straw mulch.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_soil_min_unknown_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_min_unknown_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_min_unknown_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_min_unknown_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_min_unknown_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_min_unknown_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_soil_min_unknown_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under an unrecorded surface cover.",
    ),
    CanonicalParameter(
        "temperature_surface_mean",
        "temperature",
        "Mean temperature of the ground surface.",
        interpolation="homogeneous",
    ),
    CanonicalParameter("temperature_water", "temperature", "Temperature of the water."),
    CanonicalParameter(
        "temperature_water_evaporation_pan_max",
        "temperature",
        "Highest water temperature in the evaporation pan over the period.",
    ),
    CanonicalParameter(
        "temperature_water_evaporation_pan_min",
        "temperature",
        "Lowest water temperature in the evaporation pan over the period.",
    ),
    CanonicalParameter("temperature_water_max", "temperature", "Highest water temperature over the period."),
    CanonicalParameter("temperature_water_mean", "temperature", "Mean water temperature over the period."),
    CanonicalParameter("temperature_water_min", "temperature", "Lowest water temperature over the period."),
    CanonicalParameter(
        "temperature_wet_ice_formation",
        "dimensionless",
        "Whether ice had formed on the thermometer during the wet bulb measurement.",
    ),
    CanonicalParameter(
        "temperature_wet_mean_2m",
        "temperature",
        "Wet-bulb temperature at 2 m above ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "temperature_wind_chill",
        "temperature",
        "Wind chill, the temperature the air feels like once wind is accounted for.",
        interpolation="homogeneous",
    ),
    CanonicalParameter("thawing_thickness_bare", "length_short", "Depth to which bare ground has thawed."),
    CanonicalParameter(
        "thawing_thickness_bare_max_month",
        "length_short",
        "Greatest depth to which bare ground thawed during the month.",
    ),
    CanonicalParameter(
        "thawing_thickness_plantstock", "length_short", "Depth to which ground under plant cover has thawed."
    ),
    CanonicalParameter(
        "thawing_thickness_plantstock_max_month",
        "length_short",
        "Greatest depth to which ground under plant cover thawed in the month.",
    ),
    CanonicalParameter(
        "true_local_time_offset",
        "time",
        "How far true local solar time runs ahead of the timestamp of the record, being the "
        "longitude correction plus the equation of time.",
    ),
    CanonicalParameter("turbidity", "turbidity", "Cloudiness of the water caused by suspended particles."),
    CanonicalParameter(
        "visibility_range",
        "length_medium",
        "Horizontal distance at which an object can still be made out.",
        interpolation="heterogeneous",
    ),
    CanonicalParameter(
        "visibility_range_index",
        "dimensionless",
        "Coded class the visibility range falls into, rather than a measured distance.",
    ),
    CanonicalParameter(
        "visibility_range_measurement_method",
        "dimensionless",
        "Coded indicator of how the visibility range was determined, such as by a person or an instrument.",
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth",
        "precipitation",
        "Depth of water that would result from melting the snow on the ground.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth_excelled",
        "precipitation",
        "Water equivalent of the snow cover where it exceeded the gauge range.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth_new",
        "precipitation",
        "Depth of water that would result from melting the freshly fallen snow.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth_new_last_1h",
        "precipitation",
        "Water equivalent of the snow that fell in the preceding hour.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth_new_last_3h",
        "precipitation",
        "Water equivalent of the snow that fell in the preceding 3 hours.",
        interpolation="heterogeneous",
        zero_inflated=True,
    ),
    CanonicalParameter(
        "water_film_thickness", "length_short", "Thickness of the film of water lying on the road surface."
    ),
    CanonicalParameter(
        "wave_height_max", "length_short", "Height of the highest single wave observed over the period."
    ),
    CanonicalParameter(
        "wave_height_sign",
        "length_short",
        "Significant wave height, the mean height of the highest third of the waves.",
    ),
    CanonicalParameter("wave_period", "time", "Mean time between successive wave crests."),
    CanonicalParameter("weather", "dimensionless", "Coded present weather at the time of observation."),
    CanonicalParameter(
        "weather_last_3h",
        "dimensionless",
        "Coded weather observed over the preceding 3 hours.",
    ),
    CanonicalParameter("weather_last_6h", "dimensionless", "Coded weather observed over the preceding 6 hours."),
    CanonicalParameter(
        "weather_secondary_last_3h",
        "dimensionless",
        "Second coded weather observed over the preceding 3 hours, where two kinds of weather occurred.",
    ),
    CanonicalParameter(
        "weather_significant", "significant_weather", "Coded significant weather at the time of observation."
    ),
    CanonicalParameter(
        "weather_significant_last_3h", "significant_weather", "Coded significant weather over the preceding 3 hours."
    ),
    CanonicalParameter(
        "weather_significant_optional_last_12h",
        "significant_weather",
        "Coded significant weather over the preceding 12 hours, where reported.",
    ),
    CanonicalParameter(
        "weather_significant_optional_last_1h",
        "significant_weather",
        "Coded significant weather over the preceding hour, where reported.",
    ),
    CanonicalParameter(
        "weather_significant_optional_last_24h",
        "significant_weather",
        "Coded significant weather over the preceding 24 hours, where reported.",
    ),
    CanonicalParameter(
        "weather_significant_optional_last_3h",
        "significant_weather",
        "Coded significant weather over the preceding 3 hours, where reported.",
    ),
    CanonicalParameter(
        "weather_significant_optional_last_6h",
        "significant_weather",
        "Coded significant weather over the preceding 6 hours, where reported.",
    ),
    CanonicalParameter(
        "weather_type_blowing_drifting_snow", "dimensionless", "Whether blowing or drifting snow was observed."
    ),
    CanonicalParameter("weather_type_blowing_spray", "dimensionless", "Whether blowing spray was observed."),
    CanonicalParameter("weather_type_drizzle", "dimensionless", "Whether drizzle was observed."),
    CanonicalParameter(
        "weather_type_dust_ash_sand", "dimensionless", "Whether dust, volcanic ash or blowing sand was observed."
    ),
    CanonicalParameter("weather_type_fog", "dimensionless", "Whether fog was observed."),
    CanonicalParameter("weather_type_freezing_drizzle", "dimensionless", "Whether freezing drizzle was observed."),
    CanonicalParameter("weather_type_freezing_rain", "dimensionless", "Whether freezing rain was observed."),
    CanonicalParameter("weather_type_glaze_rime", "dimensionless", "Whether glaze or rime was observed."),
    CanonicalParameter("weather_type_ground_fog", "dimensionless", "Whether ground fog was observed."),
    CanonicalParameter("weather_type_hail", "dimensionless", "Whether hail was observed."),
    CanonicalParameter("weather_type_heavy_fog", "dimensionless", "Whether heavy or freezing fog was observed."),
    CanonicalParameter(
        "weather_type_high_damaging_winds", "dimensionless", "Whether high, damaging winds was observed."
    ),
    CanonicalParameter(
        "weather_type_ice_fog_freezing_fog", "dimensionless", "Whether ice fog or freezing fog was observed."
    ),
    CanonicalParameter(
        "weather_type_ice_sleet_snow_hail", "dimensionless", "Whether ice pellets, sleet, snow or hail was observed."
    ),
    CanonicalParameter("weather_type_mist", "dimensionless", "Whether mist was observed."),
    CanonicalParameter(
        "weather_type_precipitation_unknown_source",
        "dimensionless",
        "Whether precipitation of unknown type was observed.",
    ),
    CanonicalParameter("weather_type_rain", "dimensionless", "Whether rain was observed."),
    CanonicalParameter("weather_type_smoke_haze", "dimensionless", "Whether smoke or haze was observed."),
    CanonicalParameter(
        "weather_type_snow_pellets_snow_grains_ice_crystals",
        "dimensionless",
        "Whether snow pellets, snow grains or ice crystals was observed.",
    ),
    CanonicalParameter("weather_type_thunder", "dimensionless", "Whether thunder was observed."),
    CanonicalParameter(
        "weather_type_tornado_waterspout",
        "dimensionless",
        "Whether a tornado, waterspout or funnel cloud was observed.",
    ),
    CanonicalParameter(
        "weather_type_vicinity_dust_ash_sand",
        "dimensionless",
        "Whether dust, volcanic ash or blowing sand was observed in the vicinity of the station.",
    ),
    CanonicalParameter(
        "weather_type_vicinity_fog_any",
        "dimensionless",
        "Whether fog of any kind was observed in the vicinity of the station.",
    ),
    CanonicalParameter(
        "weather_type_vicinity_rain_snow_shower",
        "dimensionless",
        "Whether a rain or snow shower was observed in the vicinity of the station.",
    ),
    CanonicalParameter(
        "weather_type_vicinity_snow_ice_crystals",
        "dimensionless",
        "Whether snow or ice crystals was observed in the vicinity of the station.",
    ),
    CanonicalParameter(
        "weather_type_vicinity_thunder", "dimensionless", "Whether thunder was observed in the vicinity of the station."
    ),
    CanonicalParameter("wind_direction", "angle", "Direction the wind is blowing from, clockwise from true north."),
    CanonicalParameter("wind_direction_gust_max", "angle", "Direction the strongest gust of the period blew from."),
    CanonicalParameter(
        "wind_direction_gust_max_1mile",
        "angle",
        "Direction of the strongest gust measured over a one-mile passage of air.",
    ),
    CanonicalParameter(
        "wind_direction_gust_max_1min", "angle", "Direction of the strongest gust averaged over one minute."
    ),
    CanonicalParameter(
        "wind_direction_gust_max_2min", "angle", "Direction of the strongest gust averaged over two minutes."
    ),
    CanonicalParameter(
        "wind_direction_gust_max_5sec", "angle", "Direction of the strongest gust averaged over five seconds."
    ),
    CanonicalParameter("wind_direction_gust_max_instant", "angle", "Direction of the strongest instantaneous gust."),
    CanonicalParameter(
        "wind_force_beaufort", "wind_scale", "Wind strength on the Beaufort scale.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "wind_gust_max", "speed", "Speed of the strongest gust of the period.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "wind_gust_max_1mile",
        "speed",
        "Strongest gust measured over a one-mile passage of air.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "wind_gust_max_1min", "speed", "Strongest gust averaged over one minute.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "wind_gust_max_2min", "speed", "Strongest gust averaged over two minutes.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "wind_gust_max_5sec", "speed", "Strongest gust averaged over five seconds.", interpolation="homogeneous"
    ),
    CanonicalParameter("wind_gust_max_instant", "speed", "Strongest instantaneous gust.", interpolation="homogeneous"),
    CanonicalParameter(
        "wind_gust_max_last_12h", "speed", "Strongest gust over the preceding 12 hours.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "wind_gust_max_last_1h", "speed", "Strongest gust over the preceding hour.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "wind_gust_max_last_3h", "speed", "Strongest gust over the preceding 3 hours.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "wind_gust_max_last_6h", "speed", "Strongest gust over the preceding 6 hours.", interpolation="homogeneous"
    ),
    CanonicalParameter(
        "wind_gust_max_yesterday",
        "speed",
        "Strongest gust on the previous day.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "wind_movement_24h",
        "length_long",
        "Wind run, the distance a parcel of air travelled past the station in 24 hours.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "wind_movement_multiday",
        "length_long",
        "Wind run over several days, reported as one total.",
        interpolation="homogeneous",
    ),
    CanonicalParameter("wind_speed", "speed", "Mean speed of the wind over the period.", interpolation="homogeneous"),
    CanonicalParameter(
        "wind_speed_arithmetic",
        "speed",
        "Arithmetic mean of the wind speed, unweighted by direction.",
        interpolation="homogeneous",
    ),
    CanonicalParameter("wind_speed_min", "speed", "Lowest wind speed over the period.", interpolation="homogeneous"),
    CanonicalParameter(
        "wind_speed_rolling_mean_max",
        "speed",
        "Highest rolling mean wind speed over the period.",
        interpolation="homogeneous",
    ),
    CanonicalParameter(
        "wind_speed_rolling_mean_max_yesterday",
        "speed",
        "Highest rolling mean wind speed on the previous day.",
        interpolation="homogeneous",
    ),
)

PARAMETERS: dict[str, CanonicalParameter] = {parameter.name: parameter for parameter in PARAMETER_TABLE}

# the names a request may interpolate or summarize over, i.e. everything the table classifies at
# all. A frozenset rather than the list this used to be: membership is what every caller tests.
INTERPOLATABLE_PARAMETERS: frozenset[str] = frozenset(
    parameter.name for parameter in PARAMETER_TABLE if parameter.interpolation
)
