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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wetterdienst.metadata.unit_type import UnitType


@dataclass(frozen=True, slots=True)
class CanonicalParameter:
    """Properties of a measured quantity, shared by every provider that reports it."""

    name: str
    unit_type: UnitType
    # required rather than defaulted: every parameter has one, and a new entry without a
    # description should not be constructible in the first place
    description: str


PARAMETER_TABLE: tuple[CanonicalParameter, ...] = (
    CanonicalParameter("chlorid_concentration", "concentration", "Concentration of chloride dissolved in the water."),
    CanonicalParameter(
        "clearance_height", "length_short", "Vertical clearance between the water surface and the structure above it."
    ),
    CanonicalParameter(
        "climate_correction_factor", "dimensionless", "Factor correcting a degree-day total for the local climate."
    ),
    CanonicalParameter(
        "cloud_base_convective", "length_medium", "Height above ground of the base of convective cloud."
    ),
    CanonicalParameter("cloud_cover_above_7km", "fraction", "Fraction of the sky covered by cloud above 7 km."),
    CanonicalParameter("cloud_cover_below_1000ft", "fraction", "Fraction of the sky covered by cloud below 1000 ft."),
    CanonicalParameter("cloud_cover_below_500ft", "fraction", "Fraction of the sky covered by cloud below 500 ft."),
    CanonicalParameter("cloud_cover_below_7km", "fraction", "Fraction of the sky covered by cloud below 7 km."),
    CanonicalParameter(
        "cloud_cover_between_2km_to_7km", "fraction", "Fraction of the sky covered by cloud between 2 km and 7 km."
    ),
    CanonicalParameter(
        "cloud_cover_effective",
        "fraction",
        "Effective cloud cover, weighting each layer by how much it attenuates radiation.",
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
    CanonicalParameter("cloud_cover_total", "fraction", "Fraction of the sky covered by cloud of any kind."),
    CanonicalParameter(
        "cloud_cover_total_index",
        "dimensionless",
        "Coded index describing total cloud cover, as published by the source.",
    ),
    CanonicalParameter(
        "cloud_cover_total_midnight_to_midnight",
        "fraction",
        "Mean total cloud cover over the calendar day, midnight to midnight.",
    ),
    CanonicalParameter(
        "cloud_cover_total_midnight_to_midnight_manual",
        "fraction",
        "Mean total cloud cover over the calendar day, midnight to midnight, from manual observation.",
    ),
    CanonicalParameter(
        "cloud_cover_total_sunrise_to_sunset",
        "fraction",
        "Mean total cloud cover over the daylight hours, sunrise to sunset.",
    ),
    CanonicalParameter(
        "cloud_cover_total_sunrise_to_sunset_manual",
        "fraction",
        "Mean total cloud cover over the daylight hours, sunrise to sunset, from manual observation.",
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
    CanonicalParameter(
        "cloud_type_layer1_abbreviation", "dimensionless", "Abbreviated cloud genus of the lowest reported cloud layer."
    ),
    CanonicalParameter("cloud_type_layer2", "dimensionless", "Coded cloud genus of the second reported cloud layer."),
    CanonicalParameter(
        "cloud_type_layer2_abbreviation", "dimensionless", "Abbreviated cloud genus of the second reported cloud layer."
    ),
    CanonicalParameter("cloud_type_layer3", "dimensionless", "Coded cloud genus of the third reported cloud layer."),
    CanonicalParameter(
        "cloud_type_layer3_abbreviation", "dimensionless", "Abbreviated cloud genus of the third reported cloud layer."
    ),
    CanonicalParameter("cloud_type_layer4", "dimensionless", "Coded cloud genus of the fourth reported cloud layer."),
    CanonicalParameter(
        "cloud_type_layer4_abbreviation", "dimensionless", "Abbreviated cloud genus of the fourth reported cloud layer."
    ),
    CanonicalParameter(
        "cooling_degree_hour",
        "degree_day",
        "Cooling degree hours, the temperature excess above a base value summed over each hour.",
    ),
    CanonicalParameter("count_days_cooling_degree", "dimensionless", "Number of days on which cooling was required."),
    CanonicalParameter("count_days_heating_degree", "dimensionless", "Number of days on which heating was required."),
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
        "end_of_interval",
        "dimensionless",
        "Marker showing that the timestamp denotes the end of the measuring interval.",
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
    CanonicalParameter("evaporation_height", "precipitation", "Depth of water evaporated from the surface."),
    CanonicalParameter(
        "evaporation_height_corn_loamysilt", "precipitation", "Depth of water evaporated from loamy silt under corn."
    ),
    CanonicalParameter(
        "evaporation_height_corn_sand", "precipitation", "Depth of water evaporated from sand under corn."
    ),
    CanonicalParameter(
        "evaporation_height_gras_loamysilt", "precipitation", "Depth of water evaporated from loamy silt under grass."
    ),
    CanonicalParameter(
        "evaporation_height_gras_sand", "precipitation", "Depth of water evaporated from sand under grass."
    ),
    CanonicalParameter(
        "evaporation_height_multiday",
        "precipitation",
        "Depth of water evaporated over several days, reported as one total.",
    ),
    CanonicalParameter(
        "evaporation_height_winterwheat_loamysilt",
        "precipitation",
        "Depth of water evaporated from loamy silt under winter wheat.",
    ),
    CanonicalParameter(
        "evaporation_height_winterwheat_sand",
        "precipitation",
        "Depth of water evaporated from sand under winter wheat.",
    ),
    CanonicalParameter(
        "evapotranspiration_potential_gras_fao_last_24h",
        "precipitation",
        "Potential evapotranspiration over grass in the preceding 24 hours, after the FAO reference method.",
    ),
    CanonicalParameter(
        "evapotranspiration_potential_gras_haude_last_24h",
        "precipitation",
        "Potential evapotranspiration over grass in the preceding 24 hours, after the Haude method.",
    ),
    CanonicalParameter(
        "evapotranspiration_potential_last_24h",
        "precipitation",
        "Potential evapotranspiration in the preceding 24 hours.",
    ),
    CanonicalParameter(
        "flow_direction",
        "angle",
        "Direction the water current is flowing towards, clockwise from magnetic north.",
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
    ),
    CanonicalParameter(
        "humidity",
        "fraction",
        "Relative humidity of the air, the fraction of the moisture it could hold at that temperature.",
    ),
    CanonicalParameter(
        "humidity_absolute", "dimensionless", "Absolute humidity, the mass of water vapour per volume of air."
    ),
    CanonicalParameter("humidity_max", "fraction", "Highest relative humidity over the period."),
    CanonicalParameter("humidity_min", "fraction", "Lowest relative humidity over the period."),
    CanonicalParameter("ice_on_water_thickness", "length_short", "Thickness of the ice covering the water surface."),
    CanonicalParameter("number_of_days_per_month", "dimensionless", "Number of days in the month the record covers."),
    CanonicalParameter("number_of_hours_per_month", "dimensionless", "Number of hours in the month the record covers."),
    CanonicalParameter("oxygen_level", "concentration", "Concentration of oxygen dissolved in the water."),
    CanonicalParameter("ph_value", "dimensionless", "Acidity of the water on the pH scale."),
    CanonicalParameter("precipitation_duration", "time", "Length of time during which precipitation fell."),
    CanonicalParameter(
        "precipitation_form", "dimensionless", "Coded form of the precipitation, such as rain, snow or freezing rain."
    ),
    CanonicalParameter("precipitation_height", "precipitation", "Depth of precipitation collected over the period."),
    CanonicalParameter(
        "precipitation_height_day", "precipitation", "Depth of precipitation collected during the daytime hours."
    ),
    CanonicalParameter(
        "precipitation_height_droplet",
        "precipitation",
        "Depth of precipitation measured by the droplet sensor of the gauge.",
    ),
    CanonicalParameter(
        "precipitation_height_last_12h",
        "precipitation",
        "Depth of precipitation collected over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "precipitation_height_last_15h",
        "precipitation",
        "Depth of precipitation collected over the preceding 15 hours.",
    ),
    CanonicalParameter(
        "precipitation_height_last_18h",
        "precipitation",
        "Depth of precipitation collected over the preceding 18 hours.",
    ),
    CanonicalParameter(
        "precipitation_height_last_1h", "precipitation", "Depth of precipitation collected over the preceding hour."
    ),
    CanonicalParameter(
        "precipitation_height_last_21h",
        "precipitation",
        "Depth of precipitation collected over the preceding 21 hours.",
    ),
    CanonicalParameter(
        "precipitation_height_last_24h",
        "precipitation",
        "Depth of precipitation collected over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "precipitation_height_last_3h", "precipitation", "Depth of precipitation collected over the preceding 3 hours."
    ),
    CanonicalParameter(
        "precipitation_height_last_6h", "precipitation", "Depth of precipitation collected over the preceding 6 hours."
    ),
    CanonicalParameter(
        "precipitation_height_last_9h", "precipitation", "Depth of precipitation collected over the preceding 9 hours."
    ),
    CanonicalParameter(
        "precipitation_height_liquid", "precipitation", "Depth of the liquid part of the precipitation."
    ),
    CanonicalParameter(
        "precipitation_height_liquid_significant_weather_last_1h",
        "precipitation",
        "Depth of liquid precipitation from significant weather in the preceding hour.",
    ),
    CanonicalParameter(
        "precipitation_height_max",
        "precipitation",
        "Greatest precipitation depth recorded in any single interval of the period.",
    ),
    CanonicalParameter(
        "precipitation_height_multiday",
        "precipitation",
        "Depth of precipitation over several days, reported as one total.",
    ),
    CanonicalParameter(
        "precipitation_height_night", "precipitation", "Depth of precipitation collected during the night hours."
    ),
    CanonicalParameter(
        "precipitation_height_rocker",
        "precipitation",
        "Depth of precipitation measured by the tipping-bucket sensor of the gauge.",
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_12h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_1h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding hour.",
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_24h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_3h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding 3 hours.",
    ),
    CanonicalParameter(
        "precipitation_height_significant_weather_last_6h",
        "precipitation",
        "Depth of precipitation from significant weather over the preceding 6 hours.",
    ),
    CanonicalParameter("precipitation_index", "dimensionless", "Coded indicator of whether precipitation occurred."),
    CanonicalParameter("precipitation_intensity", "precipitation_intensity", "Rate at which precipitation is falling."),
    CanonicalParameter(
        "pressure_air_sea_level",
        "pressure",
        "Air pressure reduced to mean sea level, so that stations at different heights compare.",
    ),
    CanonicalParameter("pressure_air_site", "pressure", "Air pressure as measured at station height."),
    CanonicalParameter(
        "pressure_air_site_delta_last_3h",
        "pressure",
        "Change in air pressure at station height over the preceding 3 hours.",
    ),
    CanonicalParameter("pressure_air_site_max", "pressure", "Highest air pressure at station height over the period."),
    CanonicalParameter("pressure_air_site_min", "pressure", "Lowest air pressure at station height over the period."),
    CanonicalParameter(
        "pressure_air_site_reduced", "pressure", "Air pressure at station height reduced to a reference level."
    ),
    CanonicalParameter("pressure_vapor", "pressure", "Partial pressure of water vapour in the air."),
    CanonicalParameter(
        "probability_drizzle_last_12h", "fraction", "Probability of drizzle over the preceding 12 hours."
    ),
    CanonicalParameter("probability_drizzle_last_1h", "fraction", "Probability of drizzle over the preceding hour."),
    CanonicalParameter("probability_drizzle_last_6h", "fraction", "Probability of drizzle over the preceding 6 hours."),
    CanonicalParameter("probability_fog_last_12h", "fraction", "Probability of fog over the preceding 12 hours."),
    CanonicalParameter("probability_fog_last_1h", "fraction", "Probability of fog over the preceding hour."),
    CanonicalParameter("probability_fog_last_24h", "fraction", "Probability of fog over the preceding 24 hours."),
    CanonicalParameter("probability_fog_last_6h", "fraction", "Probability of fog over the preceding 6 hours."),
    CanonicalParameter(
        "probability_precipitation_convective_last_12h",
        "fraction",
        "Probability of convective precipitation over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_convective_last_1h",
        "fraction",
        "Probability of convective precipitation over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_convective_last_6h",
        "fraction",
        "Probability of convective precipitation over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_freezing_last_12h",
        "fraction",
        "Probability of freezing precipitation over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_freezing_last_1h",
        "fraction",
        "Probability of freezing precipitation over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_freezing_last_6h",
        "fraction",
        "Probability of freezing precipitation over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_0mm_last_12h",
        "fraction",
        "Probability that more than 0.0 mm of precipitation fell over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_0mm_last_24h",
        "fraction",
        "Probability that more than 0.0 mm of precipitation fell over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_0mm_last_6h",
        "fraction",
        "Probability that more than 0.0 mm of precipitation fell over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_1mm_last_1h",
        "fraction",
        "Probability that more than 0.1 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_2mm_last_12h",
        "fraction",
        "Probability that more than 0.2 mm of precipitation fell over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_2mm_last_1h",
        "fraction",
        "Probability that more than 0.2 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_2mm_last_24h",
        "fraction",
        "Probability that more than 0.2 mm of precipitation fell over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_2mm_last_6h",
        "fraction",
        "Probability that more than 0.2 mm of precipitation fell over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_3mm_last_1h",
        "fraction",
        "Probability that more than 0.3 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_5mm_last_1h",
        "fraction",
        "Probability that more than 0.5 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_0_7mm_last_1h",
        "fraction",
        "Probability that more than 0.7 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_10mm_last_1h",
        "fraction",
        "Probability that more than 10 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_15mm_last_1h",
        "fraction",
        "Probability that more than 15 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_1mm_last_12h",
        "fraction",
        "Probability that more than 1 mm of precipitation fell over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_1mm_last_1h",
        "fraction",
        "Probability that more than 1 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_1mm_last_24h",
        "fraction",
        "Probability that more than 1 mm of precipitation fell over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_1mm_last_6h",
        "fraction",
        "Probability that more than 1 mm of precipitation fell over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_25mm_last_1h",
        "fraction",
        "Probability that more than 25 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_2mm_last_1h",
        "fraction",
        "Probability that more than 2 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_3mm_last_1h",
        "fraction",
        "Probability that more than 3 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_5mm_last_12h",
        "fraction",
        "Probability that more than 5 mm of precipitation fell over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_5mm_last_1h",
        "fraction",
        "Probability that more than 5 mm of precipitation fell over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_5mm_last_24h",
        "fraction",
        "Probability that more than 5 mm of precipitation fell over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_height_gt_5mm_last_6h",
        "fraction",
        "Probability that more than 5 mm of precipitation fell over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_last_12h",
        "fraction",
        "Probability of precipitation of any kind over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_last_1h",
        "fraction",
        "Probability of precipitation of any kind over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_last_24h",
        "fraction",
        "Probability of precipitation of any kind over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_last_6h",
        "fraction",
        "Probability of precipitation of any kind over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_liquid_last_12h",
        "fraction",
        "Probability of liquid precipitation over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_liquid_last_1h",
        "fraction",
        "Probability of liquid precipitation over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_liquid_last_6h",
        "fraction",
        "Probability of liquid precipitation over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_solid_last_12h",
        "fraction",
        "Probability of solid precipitation over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_solid_last_1h",
        "fraction",
        "Probability of solid precipitation over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_solid_last_6h",
        "fraction",
        "Probability of solid precipitation over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_stratiform_last_12h",
        "fraction",
        "Probability of stratiform precipitation over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_precipitation_stratiform_last_1h",
        "fraction",
        "Probability of stratiform precipitation over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_precipitation_stratiform_last_6h",
        "fraction",
        "Probability of stratiform precipitation over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_radiation_global_last_1h",
        "fraction",
        "Probability of measurable global radiation over the preceding hour.",
    ),
    CanonicalParameter(
        "probability_sunshine_duration_relative_gt_0pct_last_24h",
        "fraction",
        "Probability that sunshine lasted more than 0 % of the possible duration over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "probability_sunshine_duration_relative_gt_30pct_last_24h",
        "fraction",
        "Probability that sunshine lasted more than 30 % of the possible duration over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "probability_sunshine_duration_relative_gt_60pct_last_24h",
        "fraction",
        "Probability that sunshine lasted more than 60 % of the possible duration over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "probability_thunder_last_12h", "fraction", "Probability of thunderstorm over the preceding 12 hours."
    ),
    CanonicalParameter(
        "probability_thunder_last_1h", "fraction", "Probability of thunderstorm over the preceding hour."
    ),
    CanonicalParameter(
        "probability_thunder_last_24h", "fraction", "Probability of thunderstorm over the preceding 24 hours."
    ),
    CanonicalParameter(
        "probability_thunder_last_6h", "fraction", "Probability of thunderstorm over the preceding 6 hours."
    ),
    CanonicalParameter(
        "probability_visibility_below_1000m", "fraction", "Probability that visibility falls below 1000 m."
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_25kn_last_12h",
        "fraction",
        "Probability of a wind gust reaching 25 kn or more over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_25kn_last_6h",
        "fraction",
        "Probability of a wind gust reaching 25 kn or more over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_40kn_last_12h",
        "fraction",
        "Probability of a wind gust reaching 40 kn or more over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_40kn_last_6h",
        "fraction",
        "Probability of a wind gust reaching 40 kn or more over the preceding 6 hours.",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_55kn_last_12h",
        "fraction",
        "Probability of a wind gust reaching 55 kn or more over the preceding 12 hours.",
    ),
    CanonicalParameter(
        "probability_wind_gust_ge_55kn_last_6h",
        "fraction",
        "Probability of a wind gust reaching 55 kn or more over the preceding 6 hours.",
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
    ),
    CanonicalParameter(
        "radiation_global_intensity",
        "power_per_area",
        "Global irradiance on a horizontal surface, reported as power rather than energy.",
    ),
    CanonicalParameter(
        "radiation_global_last_3h", "energy_per_area", "Global radiation accumulated over the preceding 3 hours."
    ),
    CanonicalParameter(
        "radiation_global_uncertainty", "energy_per_area", "Uncertainty attached to the reported global radiation."
    ),
    CanonicalParameter(
        "radiation_sky_long_wave",
        "energy_per_area",
        "Downward long-wave radiation from the sky, accumulated as energy over the interval.",
    ),
    CanonicalParameter(
        "radiation_sky_long_wave_intensity",
        "power_per_area",
        "Downward long-wave irradiance from the sky, reported as power.",
    ),
    CanonicalParameter(
        "radiation_sky_long_wave_last_3h",
        "energy_per_area",
        "Downward long-wave radiation from the sky over the preceding 3 hours.",
    ),
    CanonicalParameter(
        "radiation_sky_short_wave_diffuse",
        "energy_per_area",
        "Diffuse short-wave radiation from the sky, accumulated as energy over the interval.",
    ),
    CanonicalParameter(
        "radiation_sky_short_wave_diffuse_intensity",
        "power_per_area",
        "Diffuse short-wave irradiance from the sky, reported as power.",
    ),
    CanonicalParameter(
        "radiation_sky_short_wave_direct",
        "energy_per_area",
        "Direct short-wave radiation from the sun, accumulated as energy over the interval.",
    ),
    CanonicalParameter(
        "road_surface_condition", "dimensionless", "Coded condition of the road surface, such as dry, wet or icy."
    ),
    CanonicalParameter("snow_depth", "length_short", "Depth of the snow lying on the ground."),
    CanonicalParameter(
        "snow_depth_excelled", "length_short", "Depth of the snow cover where it exceeded the measuring range."
    ),
    CanonicalParameter(
        "snow_depth_manual", "length_short", "Depth of the snow lying on the ground, from manual observation."
    ),
    CanonicalParameter("snow_depth_max", "length_short", "Greatest snow depth over the period."),
    CanonicalParameter("snow_depth_new", "length_short", "Depth of snow that fell during the period."),
    CanonicalParameter("snow_depth_new_max", "length_short", "Greatest depth of fresh snow recorded over the period."),
    CanonicalParameter(
        "snow_depth_new_multiday", "length_short", "Depth of fresh snow over several days, reported as one total."
    ),
    CanonicalParameter(
        "soil_moisture_corn_loamysilt_00cm_60cm",
        "fraction",
        "Soil moisture in loamy silt under corn, between the surface and 60 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_corn_sand_00cm_60cm",
        "fraction",
        "Soil moisture in sand under corn, between the surface and 60 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_00cm_10cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between the surface and 10 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_00cm_60cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between the surface and 60 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_10cm_20cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 10 cm and 20 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_20cm_30cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 20 cm and 30 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_30cm_40cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 30 cm and 40 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_40cm_50cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 40 cm and 50 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_gras_loamysilt_50cm_60cm",
        "fraction",
        "Soil moisture in loamy silt under grass, between 50 cm and 60 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_gras_sand_00cm_60cm",
        "fraction",
        "Soil moisture in sand under grass, between the surface and 60 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_winterwheat_loamysilt_00cm_60cm",
        "fraction",
        "Soil moisture in loamy silt under winter wheat, between the surface and 60 cm.",
    ),
    CanonicalParameter(
        "soil_moisture_winterwheat_sand_00cm_60cm",
        "fraction",
        "Soil moisture in sand under winter wheat, between the surface and 60 cm.",
    ),
    CanonicalParameter("stage", "length_short", "Water level at the gauge, measured against the gauge datum."),
    CanonicalParameter("stage_max", "length_short", "Highest water level at the gauge over the period."),
    CanonicalParameter("stage_mean", "length_short", "Mean water level at the gauge over the period."),
    CanonicalParameter("stage_min", "length_short", "Lowest water level at the gauge over the period."),
    CanonicalParameter("sun_zenith_angle", "angle", "Angle between the sun and the vertical."),
    CanonicalParameter("sunshine_duration", "time", "Length of time the sun shone unobstructed."),
    CanonicalParameter(
        "sunshine_duration_last_3h", "time", "Length of time the sun shone unobstructed in the preceding 3 hours."
    ),
    CanonicalParameter(
        "sunshine_duration_relative",
        "fraction",
        "Sunshine duration as a fraction of the longest possible for the location and date.",
    ),
    CanonicalParameter(
        "sunshine_duration_relative_last_24h", "fraction", "Relative sunshine duration over the preceding 24 hours."
    ),
    CanonicalParameter(
        "sunshine_duration_uncertainty", "time", "Uncertainty attached to the reported sunshine duration."
    ),
    CanonicalParameter(
        "sunshine_duration_yesterday", "time", "Length of time the sun shone unobstructed on the previous day."
    ),
    CanonicalParameter(
        "temperature_air_2m", "temperature", "Air temperature at 2 m above ground, the standard screen height."
    ),
    CanonicalParameter("temperature_air_max_0_05m", "temperature", "Maximum air temperature at 0.05 m above ground."),
    CanonicalParameter("temperature_air_max_2m", "temperature", "Maximum air temperature at 2 m above ground."),
    CanonicalParameter(
        "temperature_air_max_2m_last_24h",
        "temperature",
        "Maximum air temperature at 2 m above ground over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "temperature_air_max_2m_mean",
        "temperature",
        "Mean of the daily maximum air temperature at 2 m above ground over the period.",
    ),
    CanonicalParameter(
        "temperature_air_max_2m_multiday",
        "temperature",
        "Maximum air temperature at 2 m above ground, covering several days where a station did not report daily.",
    ),
    CanonicalParameter("temperature_air_mean_0_05m", "temperature", "Mean air temperature at 0.05 m above ground."),
    CanonicalParameter("temperature_air_mean_0_1m", "temperature", "Mean air temperature at 0.1 m above ground."),
    CanonicalParameter("temperature_air_mean_2m", "temperature", "Mean air temperature at 2 m above ground."),
    CanonicalParameter(
        "temperature_air_mean_2m_last_24h",
        "temperature",
        "Mean air temperature at 2 m above ground over the preceding 24 hours.",
    ),
    CanonicalParameter("temperature_air_min_0_05m", "temperature", "Minimum air temperature at 0.05 m above ground."),
    CanonicalParameter(
        "temperature_air_min_0_05m_last_12h",
        "temperature",
        "Minimum air temperature at 0.05 m above ground over the preceding 12 hours.",
    ),
    CanonicalParameter("temperature_air_min_2m", "temperature", "Minimum air temperature at 2 m above ground."),
    CanonicalParameter(
        "temperature_air_min_2m_last_24h",
        "temperature",
        "Minimum air temperature at 2 m above ground over the preceding 24 hours.",
    ),
    CanonicalParameter(
        "temperature_air_min_2m_mean",
        "temperature",
        "Mean of the daily minimum air temperature at 2 m above ground over the period.",
    ),
    CanonicalParameter(
        "temperature_air_min_2m_multiday",
        "temperature",
        "Minimum air temperature at 2 m above ground, covering several days where a station did not report daily.",
    ),
    CanonicalParameter(
        "temperature_concrete_max_0m", "temperature", "Maximum temperature at the surface of a concrete slab."
    ),
    CanonicalParameter(
        "temperature_concrete_mean_0m", "temperature", "Mean temperature at the surface of a concrete slab."
    ),
    CanonicalParameter(
        "temperature_concrete_min_0m", "temperature", "Minimum temperature at the surface of a concrete slab."
    ),
    CanonicalParameter(
        "temperature_dew_point_mean_2m",
        "temperature",
        "Dew point at 2 m above ground, the temperature at which the air would become saturated.",
    ),
    CanonicalParameter(
        "temperature_radiant_mean_2m",
        "temperature",
        "Mean radiant temperature, the temperature a body feels from surrounding surfaces.",
    ),
    CanonicalParameter("temperature_soil_max_0_1m", "temperature", "Maximum soil temperature at 0.1 m depth."),
    CanonicalParameter("temperature_soil_max_0_2m", "temperature", "Maximum soil temperature at 0.2 m depth."),
    CanonicalParameter("temperature_soil_max_0_5m", "temperature", "Maximum soil temperature at 0.5 m depth."),
    CanonicalParameter("temperature_soil_max_1m", "temperature", "Maximum soil temperature at 1 m depth."),
    CanonicalParameter("temperature_soil_max_2m", "temperature", "Maximum soil temperature at 2 m depth."),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_ground_1m", "temperature", "Maximum soil temperature at 1 m depth under bare ground."
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_bare_muck_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_max_brome_grass_1m", "temperature", "Maximum soil temperature at 1 m depth under brome grass."
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_max_fallow_1m", "temperature", "Maximum soil temperature at 1 m depth under fallow ground."
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_0_05m", "temperature", "Maximum soil temperature at 0.05 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_0_1m", "temperature", "Maximum soil temperature at 0.1 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_0_2m", "temperature", "Maximum soil temperature at 0.2 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_0_5m", "temperature", "Maximum soil temperature at 0.5 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_1_5m", "temperature", "Maximum soil temperature at 1.5 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_1_8m", "temperature", "Maximum soil temperature at 1.8 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_1m", "temperature", "Maximum soil temperature at 1 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_grass_muck_1m",
        "temperature",
        "Maximum soil temperature at 1 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_0_05m", "temperature", "Maximum soil temperature at 0.05 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_0_1m", "temperature", "Maximum soil temperature at 0.1 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_0_2m", "temperature", "Maximum soil temperature at 0.2 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_0_5m", "temperature", "Maximum soil temperature at 0.5 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_1_5m", "temperature", "Maximum soil temperature at 1.5 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_1_8m", "temperature", "Maximum soil temperature at 1.8 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_max_sod_1m", "temperature", "Maximum soil temperature at 1 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_0_05m",
        "temperature",
        "Maximum soil temperature at 0.05 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_0_1m",
        "temperature",
        "Maximum soil temperature at 0.1 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_0_2m",
        "temperature",
        "Maximum soil temperature at 0.2 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_0_5m",
        "temperature",
        "Maximum soil temperature at 0.5 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_1_5m",
        "temperature",
        "Maximum soil temperature at 1.5 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_1_8m",
        "temperature",
        "Maximum soil temperature at 1.8 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_max_straw_mulch_1m", "temperature", "Maximum soil temperature at 1 m depth under straw mulch."
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
    CanonicalParameter("temperature_soil_mean_0_02m", "temperature", "Mean soil temperature at 0.02 m depth."),
    CanonicalParameter("temperature_soil_mean_0_05m", "temperature", "Mean soil temperature at 0.05 m depth."),
    CanonicalParameter("temperature_soil_mean_0_1m", "temperature", "Mean soil temperature at 0.1 m depth."),
    CanonicalParameter("temperature_soil_mean_0_2m", "temperature", "Mean soil temperature at 0.2 m depth."),
    CanonicalParameter("temperature_soil_mean_0_5m", "temperature", "Mean soil temperature at 0.5 m depth."),
    CanonicalParameter("temperature_soil_mean_1m", "temperature", "Mean soil temperature at 1 m depth."),
    CanonicalParameter("temperature_soil_mean_2m", "temperature", "Mean soil temperature at 2 m depth."),
    CanonicalParameter(
        "temperature_soil_mean_loamysand_0_05m",
        "temperature",
        "Mean soil temperature at 0.05 m depth under loamy sand.",
    ),
    CanonicalParameter(
        "temperature_soil_mean_loamysilt_0_05m",
        "temperature",
        "Mean soil temperature at 0.05 m depth under loamy silt.",
    ),
    CanonicalParameter("temperature_soil_min_0_1m", "temperature", "Minimum soil temperature at 0.1 m depth."),
    CanonicalParameter("temperature_soil_min_0_2m", "temperature", "Minimum soil temperature at 0.2 m depth."),
    CanonicalParameter("temperature_soil_min_0_5m", "temperature", "Minimum soil temperature at 0.5 m depth."),
    CanonicalParameter("temperature_soil_min_1m", "temperature", "Minimum soil temperature at 1 m depth."),
    CanonicalParameter("temperature_soil_min_2m", "temperature", "Minimum soil temperature at 2 m depth."),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under bare ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_ground_1m", "temperature", "Minimum soil temperature at 1 m depth under bare ground."
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_bare_muck_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under bare muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under brome grass.",
    ),
    CanonicalParameter(
        "temperature_soil_min_brome_grass_1m", "temperature", "Minimum soil temperature at 1 m depth under brome grass."
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under fallow ground.",
    ),
    CanonicalParameter(
        "temperature_soil_min_fallow_1m", "temperature", "Minimum soil temperature at 1 m depth under fallow ground."
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_0_05m", "temperature", "Minimum soil temperature at 0.05 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_0_1m", "temperature", "Minimum soil temperature at 0.1 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_0_2m", "temperature", "Minimum soil temperature at 0.2 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_0_5m", "temperature", "Minimum soil temperature at 0.5 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_1_5m", "temperature", "Minimum soil temperature at 1.5 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_1_8m", "temperature", "Minimum soil temperature at 1.8 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_1m", "temperature", "Minimum soil temperature at 1 m depth under grass."
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_grass_muck_1m",
        "temperature",
        "Minimum soil temperature at 1 m depth under grass over muck soil.",
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_0_05m", "temperature", "Minimum soil temperature at 0.05 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_0_1m", "temperature", "Minimum soil temperature at 0.1 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_0_2m", "temperature", "Minimum soil temperature at 0.2 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_0_5m", "temperature", "Minimum soil temperature at 0.5 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_1_5m", "temperature", "Minimum soil temperature at 1.5 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_1_8m", "temperature", "Minimum soil temperature at 1.8 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_min_sod_1m", "temperature", "Minimum soil temperature at 1 m depth under sod."
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_0_05m",
        "temperature",
        "Minimum soil temperature at 0.05 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_0_1m",
        "temperature",
        "Minimum soil temperature at 0.1 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_0_2m",
        "temperature",
        "Minimum soil temperature at 0.2 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_0_5m",
        "temperature",
        "Minimum soil temperature at 0.5 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_1_5m",
        "temperature",
        "Minimum soil temperature at 1.5 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_1_8m",
        "temperature",
        "Minimum soil temperature at 1.8 m depth under straw mulch.",
    ),
    CanonicalParameter(
        "temperature_soil_min_straw_mulch_1m", "temperature", "Minimum soil temperature at 1 m depth under straw mulch."
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
    CanonicalParameter("temperature_surface_mean", "temperature", "Mean temperature of the ground surface."),
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
    CanonicalParameter("temperature_wet_mean_2m", "temperature", "Wet-bulb temperature at 2 m above ground."),
    CanonicalParameter(
        "temperature_wind_chill",
        "temperature",
        "Wind chill, the temperature the air feels like once wind is accounted for.",
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
        "true_local_time", "dimensionless", "True local solar time at the station, as opposed to zone time."
    ),
    CanonicalParameter("turbidity", "turbidity", "Cloudiness of the water caused by suspended particles."),
    CanonicalParameter(
        "visibility_range", "length_medium", "Horizontal distance at which an object can still be made out."
    ),
    CanonicalParameter("visibility_range_index", "dimensionless", "Coded indicator of the visibility range."),
    CanonicalParameter(
        "water_equivalent_snow_depth",
        "precipitation",
        "Depth of water that would result from melting the snow on the ground.",
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth_excelled",
        "precipitation",
        "Water equivalent of the snow cover where it exceeded the gauge range.",
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth_new",
        "precipitation",
        "Depth of water that would result from melting the freshly fallen snow.",
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth_new_last_1h",
        "precipitation",
        "Water equivalent of the snow that fell in the preceding hour.",
    ),
    CanonicalParameter(
        "water_equivalent_snow_depth_new_last_3h",
        "precipitation",
        "Water equivalent of the snow that fell in the preceding 3 hours.",
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
    CanonicalParameter("weather_last_6h", "dimensionless", "Coded weather observed over the preceding 6 hours."),
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
    CanonicalParameter("weather_text", "dimensionless", "Plain-language description of the present weather."),
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
    CanonicalParameter("wind_force_beaufort", "wind_scale", "Wind strength on the Beaufort scale."),
    CanonicalParameter("wind_gust_max", "speed", "Speed of the strongest gust of the period."),
    CanonicalParameter("wind_gust_max_1mile", "speed", "Strongest gust measured over a one-mile passage of air."),
    CanonicalParameter("wind_gust_max_1min", "speed", "Strongest gust averaged over one minute."),
    CanonicalParameter("wind_gust_max_2min", "speed", "Strongest gust averaged over two minutes."),
    CanonicalParameter("wind_gust_max_5sec", "speed", "Strongest gust averaged over five seconds."),
    CanonicalParameter("wind_gust_max_instant", "speed", "Strongest instantaneous gust."),
    CanonicalParameter("wind_gust_max_last_12h", "speed", "Strongest gust over the preceding 12 hours."),
    CanonicalParameter("wind_gust_max_last_1h", "speed", "Strongest gust over the preceding hour."),
    CanonicalParameter("wind_gust_max_last_3h", "speed", "Strongest gust over the preceding 3 hours."),
    CanonicalParameter("wind_gust_max_last_6h", "speed", "Strongest gust over the preceding 6 hours."),
    CanonicalParameter(
        "wind_movement_24h",
        "length_long",
        "Wind run, the distance a parcel of air travelled past the station in 24 hours.",
    ),
    CanonicalParameter("wind_movement_multiday", "length_long", "Wind run over several days, reported as one total."),
    CanonicalParameter("wind_speed", "speed", "Mean speed of the wind over the period."),
    CanonicalParameter("wind_speed_arithmetic", "speed", "Arithmetic mean of the wind speed, unweighted by direction."),
    CanonicalParameter("wind_speed_min", "speed", "Lowest wind speed over the period."),
    CanonicalParameter("wind_speed_rolling_mean_max", "speed", "Highest rolling mean wind speed over the period."),
)

PARAMETERS: dict[str, CanonicalParameter] = {parameter.name: parameter for parameter in PARAMETER_TABLE}
