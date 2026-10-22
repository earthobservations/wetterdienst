"""Names renamed on the way to 1.0, kept so that the old spelling fails by naming the new one.

None of these is accepted in place of its replacement, but for a name that is also an alias of a rename made from 1.0
(`wetterdienst.metadata.aliases`, which these tables take in). A caller still writing the old name gets an
error that says what it is called now, instead of the not-found a name that never existed gets.
"""

from collections.abc import Collection, Mapping

from wetterdienst.metadata.aliases import PARAMETER_ALIASES, PARAMETER_ALIASES_IN_DATASET, ParameterAlias, all_aliases
from wetterdienst.metadata.parameter_table import PARAMETERS

#: frame columns, old name to new
RENAMED_COLUMNS: dict[str, str] = {
    "height": "elevation",  # GH-2024
    "state": "region",  # GH-2026
    "date": "timestamp",  # GH-2028
    "start_date": "start_timestamp",  # GH-2439
    "end_date": "end_timestamp",  # GH-2439
    "quality": "quality_flags",  # GH-2758
    "quality_flag": "quality_flags",  # GH-2758
}


#: canonical parameter names, old name to new
RENAMED_PARAMETERS: dict[str, str] = {
    # GH-2032: misspelt, German or mistranslated names (evaporation targets follow GH-2038 below)
    "cloud_cover_between_2km_to_7km": "cloud_cover_between_2km_and_7km",
    "count_weather_type_ripe": "count_weather_type_hoar_frost",
    "evaporation_height_corn_loamysilt": "evaporation_amount_corn_loamy_silt",
    "evaporation_height_gras_loamysilt": "evaporation_amount_grass_loamy_silt",
    "evaporation_height_gras_sand": "evaporation_amount_grass_sand",
    "evaporation_height_winterwheat_loamysilt": "evaporation_amount_winter_cereals_loamy_silt",
    "evaporation_height_winterwheat_sand": "evaporation_amount_winter_cereals_sand",
    "evapotranspiration_potential_gras_fao_last_24h": "evapotranspiration_potential_grass_fao",
    "evapotranspiration_potential_gras_haude_last_24h": "evapotranspiration_potential_grass_haude",
    "number_of_days_per_month": "count_days_in_month",
    "number_of_hours_per_month": "count_hours_in_month",
    "soil_moisture_corn_loamysilt_00cm_60cm": "soil_moisture_corn_loamy_silt_00cm_60cm",
    "soil_moisture_gras_loamysilt_00cm_10cm": "soil_moisture_grass_loamy_silt_00cm_10cm",
    "soil_moisture_gras_loamysilt_00cm_60cm": "soil_moisture_grass_loamy_silt_00cm_60cm",
    "soil_moisture_gras_loamysilt_10cm_20cm": "soil_moisture_grass_loamy_silt_10cm_20cm",
    "soil_moisture_gras_loamysilt_20cm_30cm": "soil_moisture_grass_loamy_silt_20cm_30cm",
    "soil_moisture_gras_loamysilt_30cm_40cm": "soil_moisture_grass_loamy_silt_30cm_40cm",
    "soil_moisture_gras_loamysilt_40cm_50cm": "soil_moisture_grass_loamy_silt_40cm_50cm",
    "soil_moisture_gras_loamysilt_50cm_60cm": "soil_moisture_grass_loamy_silt_50cm_60cm",
    "soil_moisture_gras_sand_00cm_60cm": "soil_moisture_grass_sand_00cm_60cm",
    "soil_moisture_winterwheat_loamysilt_00cm_60cm": "soil_moisture_winter_cereals_loamy_silt_00cm_60cm",
    "soil_moisture_winterwheat_sand_00cm_60cm": "soil_moisture_winter_cereals_sand_00cm_60cm",
    "temperature_soil_mean_loamysand_0_05m": "temperature_soil_mean_loamy_sand_0_05m",
    "temperature_soil_mean_loamysilt_0_05m": "temperature_soil_mean_loamy_silt_0_05m",
    "thawing_thickness_bare": "thawing_thickness_bare_ground",
    "thawing_thickness_bare_max_month": "thawing_thickness_bare_ground_max_month",
    "thawing_thickness_plantstock": "thawing_thickness_plant_cover",
    "thawing_thickness_plantstock_max_month": "thawing_thickness_plant_cover_max_month",
    "wave_height_sign": "wave_height_significant",
    "wind_movement_24h": "wind_movement",
    # GH-2034: DWD's ausgestochene Schneehöhe, the sampled snow, read as snow beyond a range
    "snow_depth_excelled": "snow_depth_sampled",
    "water_equivalent_snow_depth_excelled": "water_equivalent_snow_depth_sampled",
    # GH-2036: humidity says relative everywhere else, and humidity_absolute stands beside it
    "humidity": "humidity_relative",
    "humidity_max": "humidity_relative_max",
    "humidity_min": "humidity_relative_min",
    # GH-2038: height is DWD's Niederschlagshoehe and Verdunstungshoehe; the quantity is an amount
    "count_days_multiday_precipitation_height_gt_0mm": "count_days_multiday_precipitation_amount_gt_0mm",
    "count_days_precipitation_height_ge_0_1mm": "count_days_precipitation_amount_ge_0_1mm",
    "count_days_precipitation_height_ge_10mm": "count_days_precipitation_amount_ge_10mm",
    "count_days_precipitation_height_ge_1mm": "count_days_precipitation_amount_ge_1mm",
    "count_days_precipitation_height_ge_20mm": "count_days_precipitation_amount_ge_20mm",
    "count_days_precipitation_height_ge_2_5mm": "count_days_precipitation_amount_ge_2_5mm",
    "count_days_precipitation_height_ge_5mm": "count_days_precipitation_amount_ge_5mm",
    "count_days_valid_precipitation_height": "count_days_valid_precipitation_amount",
    "evaporation_height": "evaporation_amount",
    "evaporation_height_corn_sand": "evaporation_amount_corn_sand",
    "evaporation_height_multiday": "evaporation_amount_multiday",
    "precipitation_height": "precipitation_amount",
    "precipitation_height_day": "precipitation_amount_day",
    "precipitation_height_droplet": "precipitation_amount_droplet",
    "precipitation_height_last_12h": "precipitation_amount_last_12h",
    "precipitation_height_last_15h": "precipitation_amount_last_15h",
    "precipitation_height_last_18h": "precipitation_amount_last_18h",
    "precipitation_height_last_1h": "precipitation_amount_last_1h",
    "precipitation_height_last_21h": "precipitation_amount_last_21h",
    "precipitation_height_last_24h": "precipitation_amount_last_24h",
    "precipitation_height_last_3h": "precipitation_amount_last_3h",
    "precipitation_height_last_6h": "precipitation_amount_last_6h",
    "precipitation_height_last_9h": "precipitation_amount_last_9h",
    "precipitation_height_liquid": "precipitation_amount_liquid",
    "precipitation_height_liquid_significant_weather_last_1h": (
        "precipitation_amount_liquid_significant_weather_last_1h"
    ),
    "precipitation_height_max": "precipitation_amount_max",
    "precipitation_height_multiday": "precipitation_amount_multiday",
    "precipitation_height_night": "precipitation_amount_night",
    "precipitation_height_normal": "precipitation_amount_normal",
    "precipitation_height_rocker": "precipitation_amount_rocker",
    "precipitation_height_significant_weather_last_12h": "precipitation_amount_significant_weather_last_12h",
    "precipitation_height_significant_weather_last_1h": "precipitation_amount_significant_weather_last_1h",
    "precipitation_height_significant_weather_last_24h": "precipitation_amount_significant_weather_last_24h",
    "precipitation_height_significant_weather_last_3h": "precipitation_amount_significant_weather_last_3h",
    "precipitation_height_significant_weather_last_6h": "precipitation_amount_significant_weather_last_6h",
    "probability_precipitation_height_gt_0_0mm_last_12h": "probability_precipitation_amount_gt_0_0mm_last_12h",
    "probability_precipitation_height_gt_0_0mm_last_24h": "probability_precipitation_amount_gt_0_0mm_last_24h",
    "probability_precipitation_height_gt_0_0mm_last_6h": "probability_precipitation_amount_gt_0_0mm_last_6h",
    "probability_precipitation_height_gt_0_1mm_last_1h": "probability_precipitation_amount_gt_0_1mm_last_1h",
    "probability_precipitation_height_gt_0_2mm_last_12h": "probability_precipitation_amount_gt_0_2mm_last_12h",
    "probability_precipitation_height_gt_0_2mm_last_1h": "probability_precipitation_amount_gt_0_2mm_last_1h",
    "probability_precipitation_height_gt_0_2mm_last_24h": "probability_precipitation_amount_gt_0_2mm_last_24h",
    "probability_precipitation_height_gt_0_2mm_last_6h": "probability_precipitation_amount_gt_0_2mm_last_6h",
    "probability_precipitation_height_gt_0_3mm_last_1h": "probability_precipitation_amount_gt_0_3mm_last_1h",
    "probability_precipitation_height_gt_0_5mm_last_1h": "probability_precipitation_amount_gt_0_5mm_last_1h",
    "probability_precipitation_height_gt_0_7mm_last_1h": "probability_precipitation_amount_gt_0_7mm_last_1h",
    "probability_precipitation_height_gt_10mm_last_1h": "probability_precipitation_amount_gt_10mm_last_1h",
    "probability_precipitation_height_gt_15mm_last_1h": "probability_precipitation_amount_gt_15mm_last_1h",
    "probability_precipitation_height_gt_1mm_last_12h": "probability_precipitation_amount_gt_1mm_last_12h",
    "probability_precipitation_height_gt_1mm_last_1h": "probability_precipitation_amount_gt_1mm_last_1h",
    "probability_precipitation_height_gt_1mm_last_24h": "probability_precipitation_amount_gt_1mm_last_24h",
    "probability_precipitation_height_gt_1mm_last_6h": "probability_precipitation_amount_gt_1mm_last_6h",
    "probability_precipitation_height_gt_25mm_last_1h": "probability_precipitation_amount_gt_25mm_last_1h",
    "probability_precipitation_height_gt_2mm_last_1h": "probability_precipitation_amount_gt_2mm_last_1h",
    "probability_precipitation_height_gt_3mm_last_1h": "probability_precipitation_amount_gt_3mm_last_1h",
    "probability_precipitation_height_gt_5mm_last_12h": "probability_precipitation_amount_gt_5mm_last_12h",
    "probability_precipitation_height_gt_5mm_last_1h": "probability_precipitation_amount_gt_5mm_last_1h",
    "probability_precipitation_height_gt_5mm_last_24h": "probability_precipitation_amount_gt_5mm_last_24h",
    "probability_precipitation_height_gt_5mm_last_6h": "probability_precipitation_amount_gt_5mm_last_6h",
    # GH-2040: the range is what visibility already is
    "visibility_range": "visibility",
    "visibility_range_index": "visibility_index",
    "visibility_range_measurement_method": "visibility_measurement_method",
    # GH-1977: DWD's NL is low cloud, below 2 km, which the name put at 1000 ft
    "cloud_cover_below_1000ft": "cloud_cover_below_2km",
    # GH-2696: DWD's graupel columns, which were read as sleet; no provider has sleet days
    "count_weather_type_sleet": "count_weather_type_graupel",
    # GH-2659: MOSMIX's error of ttt and td follows them to the spot names
    "error_absolute_temperature_air_mean_2m": "error_absolute_temperature_air_2m",
    "error_absolute_temperature_dew_point_mean_2m": "error_absolute_temperature_dew_point_2m",
    # GH-2843: MOSMIX's RRad1 is a relative global irradiance, no probability
    "probability_radiation_global_last_1h": "radiation_global_relative_last_1h",
    # GH-2844: the window of a synoptic past weather is 6 hours at 00, 06, 12 and 18 UTC and 3 hours at the others
    "weather_last_3h": "weather_past",
    "weather_secondary_last_3h": "weather_secondary_past",
    # GH-2817: DWD POI's "previous day" wind maximum is the maximum of the 6 hours before the report
    "wind_speed_rolling_mean_max_yesterday": "wind_speed_rolling_mean_max_last_6h",
    # GH-3017: the count of the days behind `temperature_air_mean_minmax_2m` and the normal of it, which ECCC builds
    # from the daily (max + min) / 2 too; no other provider had them, so the old names are no table entries any more
    "count_days_valid_temperature_air_mean_2m": "count_days_valid_temperature_air_mean_minmax_2m",
    "temperature_air_mean_2m_normal": "temperature_air_mean_minmax_2m_normal",
    # GH-3151: a mean carries the word, and a mean over a window keeps the window after it
    "wind_direction_last_10min": "wind_direction_mean_last_10min",
    "wind_direction_last_2min": "wind_direction_mean_last_2min",
    "wind_speed_last_10min": "wind_speed_mean_last_10min",
    "wind_speed_last_2min": "wind_speed_mean_last_2min",
    "cloud_cover_total_midnight_to_midnight": "cloud_cover_total_mean_midnight_to_midnight",
    "cloud_cover_total_midnight_to_midnight_manual": "cloud_cover_total_mean_midnight_to_midnight_manual",
    "cloud_cover_total_sunrise_to_sunset": "cloud_cover_total_mean_sunrise_to_sunset",
    "cloud_cover_total_sunrise_to_sunset_manual": "cloud_cover_total_mean_sunrise_to_sunset_manual",
    "radiation_sky_long_wave_intensity": "radiation_sky_long_wave_intensity_mean",
    # GH-2614: DMO's RadS3 and RadL3, the radiation balances of the last 3 hours, which the two old names read as global
    # and sky radiation. No dataset declares either of them, so they are no table entries either
    "radiation_global_last_3h": "radiation_short_wave_net_last_3h",
    "radiation_sky_long_wave_last_3h": "radiation_long_wave_net_last_3h",
    # GH-3263: DWD's derived sheets say "Wintergetreide", winter cereals, no wheat; no other provider has these
    "evaporation_amount_winter_wheat_loamy_silt": "evaporation_amount_winter_cereals_loamy_silt",
    "evaporation_amount_winter_wheat_sand": "evaporation_amount_winter_cereals_sand",
    "soil_moisture_mean_winter_wheat_loamy_silt_00cm_60cm": "soil_moisture_mean_winter_cereals_loamy_silt_00cm_60cm",
    "soil_moisture_mean_winter_wheat_sand_00cm_60cm": "soil_moisture_mean_winter_cereals_sand_00cm_60cm",
}

_WIND_LAST_10MIN = {
    "wind_speed": "wind_speed_mean_last_10min",
    "wind_direction": "wind_direction_mean_last_10min",
}
_GUST_LAST_10MIN = {"wind_gust_max": "wind_gust_max_last_10min"}
_EXTREMES_LAST_12H = {
    "temperature_air_max_2m": "temperature_air_max_2m_last_12h",
    "temperature_air_min_2m": "temperature_air_min_2m_last_12h",
}
# GH-2842: PPPP, "Surface pressure, reduced", is reduced to sea level
_PPPP_SEA_LEVEL = {"pressure_air_site_reduced": "pressure_air_sea_level"}
# GH-2841: the precipitation group of a METAR is the amount since the last routine report, which an hourly dataset of
# reports returned as the hour's precipitation
_PRECIPITATION_SINCE_LAST_ROUTINE_REPORT = {"precipitation_amount": "precipitation_amount_since_last_routine_report"}
_EXTREMES_OF_THE_PERIOD = {
    "temperature_air_max_2m_multiday": "temperature_air_max_2m",
    "temperature_air_min_2m_multiday": "temperature_air_min_2m",
}
_EXTREMES_MEAN_OF_DAILY = {
    "temperature_air_max_2m": "temperature_air_max_2m_mean",
    "temperature_air_min_2m": "temperature_air_min_2m_mean",
}
# GH-2839: a mean computed from the daily extremes, (max + min) / 2, is no mean of the day's readings
_MIDRANGE_MEAN = {"temperature_air_mean_2m": "temperature_air_mean_minmax_2m"}
# GH-3263: DWD's derived sheets say "Wintergetreide", winter cereals. The old names stay a rename per dataset, because
# the daily rows became `soil_moisture_winter_cereals_...` and the monthly ones `soil_moisture_mean_winter_cereals_...`
_WINTER_WHEAT_SOIL_MOISTURE = {
    "soil_moisture_winter_wheat_loamy_silt_00cm_60cm": "soil_moisture_winter_cereals_loamy_silt_00cm_60cm",
    "soil_moisture_winter_wheat_sand_00cm_60cm": "soil_moisture_winter_cereals_sand_00cm_60cm",
}
_POTENTIAL_EVAPOTRANSPIRATION_TOTALS = {
    "evapotranspiration_potential_grass_fao_last_24h": "evapotranspiration_potential_grass_fao",
    "evapotranspiration_potential_grass_haude_last_24h": "evapotranspiration_potential_grass_haude",
}

#: canonical parameter names renamed inside one dataset, for a name that another dataset of the
#: provider still has, so that `RENAMED_PARAMETERS` cannot hold it. Keyed by the name of the
#: provider's metadata declaration (`MetadataModel.name`), then by `(resolution, dataset)`, to
#: `{old name: new name}`. A request for the old name in that dataset is answered with the new one,
#: as the global renames are, instead of a guess at a near spelling. Not every such rename is listed
#: (the sub-daily `_mean_` temperatures follow a rule, `model.metadata._spot_name`), but each one
#: that is has the old name in the table (or in the short list of names that left it) and the new one in the
#: dataset, which `tests/metadata/test_renamed.py` holds it to. The old name stays a canonical parameter where
#: another dataset still declares it, which is why a key of `Options(geo_station_distance=...)` that is one is
#: accepted, and sets the radius of the datasets that still have it; a name that no dataset declares any more is no
#: table entry, and its rename stays here, as the baseline of a release records it and
#: `tests/baselines/parameters.py` reports an entry that is gone. A SQL column of a wide frame that is one is
#: answered with the new name where the frame holds it (`renamed_column`).
RENAMED_PARAMETERS_IN_DATASET: dict[str, dict[tuple[str, str], dict[str, str]]] = {
    # GH-2614, GH-2644
    "AemetObservationMetadata": {
        ("monthly", "data"): _EXTREMES_OF_THE_PERIOD,
        ("annual", "data"): _EXTREMES_OF_THE_PERIOD,
        # GH-2697
        ("hourly", "data"): _WIND_LAST_10MIN,
    },
    "ChmiObservationMetadata": {
        ("monthly", "data"): _EXTREMES_MEAN_OF_DAILY,
        ("annual", "data"): _EXTREMES_MEAN_OF_DAILY,
    },
    "EcccObservationMetadata": {("daily", "data"): _MIDRANGE_MEAN, ("monthly", "data"): _MIDRANGE_MEAN},
    "GeosphereObservationMetadata": {("daily", "data"): _MIDRANGE_MEAN},
    "DwdMosmixMetadata": {
        ("hourly", "small"): {**_EXTREMES_LAST_12H, **_PPPP_SEA_LEVEL},
        ("hourly", "large"): {**_EXTREMES_LAST_12H, **_PPPP_SEA_LEVEL},
    },
    "DwdDmoMetadata": {
        ("hourly", "icon"): {**_EXTREMES_LAST_12H, **_PPPP_SEA_LEVEL},
        ("hourly", "icon_eu"): {**_EXTREMES_LAST_12H, **_PPPP_SEA_LEVEL},
    },
    # GH-2697, GH-2707, GH-2733, GH-2835: the mean of the last 10 minutes, no longer the row's interval
    "DwdObservationMetadata": {("hourly", "wind_synoptic"): {"wind_speed": "wind_speed_mean_last_10min"}},
    "DwdPoiMetadata": {("hourly", "data"): _WIND_LAST_10MIN},
    # GH-2836: WG_10MIN is the strongest gust of the last 10 minutes
    "FmiObservationMetadata": {("hourly", "data"): {**_WIND_LAST_10MIN, **_GUST_LAST_10MIN}},
    "KnmiObservationMetadata": {("hourly", "data"): {"wind_direction": "wind_direction_mean_last_10min"}},
    "MeteoFranceObservationMetadata": {
        # GH-2834: FXY is the hour's highest 10-minute mean wind, no gust
        ("hourly", "core"): {**_WIND_LAST_10MIN, "wind_gust_max": "wind_speed_rolling_mean_max"},
    },
    "MeteoFranceSynopMetadata": {("subdaily", "data"): {**_WIND_LAST_10MIN, **_GUST_LAST_10MIN}},
    # Frost's own element `wind_speed` still selects its row, so only the direction is not found
    "MetnoFrostMetadata": {("hourly", "data"): {"wind_direction": "wind_direction_mean_last_10min"}},
    "SmhiObservationMetadata": {("hourly", "data"): _WIND_LAST_10MIN},
    # GH-2836, GH-2837, GH-2840, GH-2841: NWS's wind is the ASOS's 2-minute average, its gust the peak of the past 10
    # minutes, its barometricPressure the altimeter setting, the pressure at sea level of the standard atmosphere, and
    # its precipitationLastHour the METAR's amount since the last routine report. ECCC's
    # hourly direction, now `wind_direction_mean_last_2min`, is not listed: `wind_direction` is also the source's own
    # field
    # name there, so a request for it still selects the row
    # GH-2838: the wind of the hourly weather table is the SYNOP's and the METAR's mean of the last 10 minutes. Only the
    # gust is listed: `wind_speed` and `wind_direction` are also the source's own field names there, so a request for
    # them still selects the row (answered as `wind_speed_mean_last_10min` and `wind_direction_mean_last_10min`)
    "MetOfficeObservationMetadata": {("hourly", "weather"): _GUST_LAST_10MIN},
    "NwsObservationMetadata": {
        ("hourly", "data"): {
            "wind_speed": "wind_speed_mean_last_2min",
            "wind_direction": "wind_direction_mean_last_2min",
            **_GUST_LAST_10MIN,
            "pressure_air_site": "pressure_air_site_reduced",
            **_PRECIPITATION_SINCE_LAST_ROUTINE_REPORT,
        },
    },
    # GH-2841: the METAR precipitation group is a running total since the last routine report, no hourly amount
    "NoaaGhcnMetadata": {("hourly", "data"): _PRECIPITATION_SINCE_LAST_ROUTINE_REPORT},
    # GH-2845: RR6 is DWD's liquid precipitation of the last 6 hours
    "DwdSwsmosMetadata": {("hourly", "data"): {"precipitation_amount_last_6h": "precipitation_amount_liquid_last_6h"}},
    # GH-2846: RMI's PT100 probe measures the temperature on the grass, a surface temperature
    "RmiObservationMetadata": {
        (resolution, "data"): {"temperature_air_mean_0_05m": "temperature_surface_mean"}
        for resolution in ("10_minutes", "hourly", "daily")
    },
    # GH-2847: a daily total of potential evapotranspiration is the day's, no trailing 24 hours
    "MeteoswissObservationMetadata": {
        ("daily", "data"): {
            "evapotranspiration_potential_grass_fao_last_24h": "evapotranspiration_potential_grass_fao"
        },
    },
    "DwdDerivedMetadata": {
        # GH-3263: the daily names of before the rename to winter cereals (the monthly ones are means, below)
        ("daily", "soil"): {**_POTENTIAL_EVAPOTRANSPIRATION_TOTALS, **_WINTER_WHEAT_SOIL_MOISTURE},
        # GH-3168: the monthly ones were renamed before the daily ones, and the 0.139.0 names went unanswered
        ("monthly", "soil"): _POTENTIAL_EVAPOTRANSPIRATION_TOTALS,
    },
    # GH-2632, GH-3168: the river level the Environment Agency measures was `groundwater_level_max` and `_min`
    "EAHydrologyMetadata": {
        ("daily", "data"): {"groundwater_level_max": "stage_max", "groundwater_level_min": "stage_min"}
    },
}

# GH-3151, wind
_MEAN_WIND_IN_DATASET: dict[str, dict[tuple[str, str], dict[str, str]]] = {
    "AemetObservationMetadata": {
        ("daily", "data"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "ChmiObservationMetadata": {
        ("daily", "data"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "DmiObservationMetadata": {
        ("annual", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("daily", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("hourly", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("monthly", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
    },
    "DwdObservationMetadata": {
        ("10_minutes", "urban_wind"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("10_minutes", "wind"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("daily", "climate_summary"): {
            "wind_speed": "wind_speed_mean",
        },
        ("hourly", "urban_wind"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("hourly", "wind"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
    },
    "GeosphereObservationMetadata": {
        ("daily", "data"): {
            "wind_speed": "wind_speed_mean",
        },
        ("monthly", "data"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "ImgwMeteorologyMetadata": {
        ("daily", "climate"): {
            "wind_speed": "wind_speed_mean",
        },
        ("daily", "synop"): {
            "wind_speed": "wind_speed_mean",
        },
        ("monthly", "climate"): {
            "wind_speed": "wind_speed_mean",
        },
        ("monthly", "synop"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "KnmiObservationMetadata": {
        ("10_minutes", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("daily", "data"): {
            "wind_speed": "wind_speed_mean",
        },
        ("hourly", "data"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "MetOfficeObservationMetadata": {
        ("hourly", "wind"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
    },
    "MeteoFranceObservationMetadata": {
        ("daily", "core"): {
            "wind_speed": "wind_speed_mean",
        },
        ("monthly", "data"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "MeteoswissObservationMetadata": {
        ("10_minutes", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("annual", "data"): {
            "wind_speed": "wind_speed_mean",
        },
        ("daily", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("hourly", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("monthly", "data"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "MetnoFrostMetadata": {
        ("daily", "data"): {
            "wind_speed": "wind_speed_mean",
        },
        ("monthly", "data"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "NoaaGhcnMetadata": {
        ("daily", "data"): {
            "wind_speed": "wind_speed_mean",
        },
    },
    "SmhiObservationMetadata": {
        ("1_minute", "data"): {
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
    },
}


def _merge_in_dataset(*blocks: dict[str, dict[tuple[str, str], dict[str, str]]]) -> None:
    """Add the renames of each block to `RENAMED_PARAMETERS_IN_DATASET`, a name already there being replaced."""
    for block in blocks:
        for metadata_name, datasets in block.items():
            for key, renames in datasets.items():
                # a new dict: the existing ones are shared between datasets
                datasets_of_provider = RENAMED_PARAMETERS_IN_DATASET.setdefault(metadata_name, {})
                datasets_of_provider[key] = {**datasets_of_provider.get(key, {}), **renames}


# GH-3151, humidity
_MEAN_HUMIDITY_IN_DATASET: dict[str, dict[tuple[str, str], dict[str, str]]] = {
    "AemetObservationMetadata": {
        ("daily", "data"): {
            "humidity_relative": "humidity_relative_mean",
        },
        ("monthly", "data"): {
            "humidity_relative": "humidity_relative_mean",
        },
    },
    "ChmiObservationMetadata": {
        ("daily", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_site": "pressure_air_site_mean",
        },
    },
    "DmiObservationMetadata": {
        ("annual", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
        },
        ("daily", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
        },
        ("hourly", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
        },
        ("monthly", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
        },
    },
    "DwdObservationMetadata": {
        ("annual", "climate_summary"): {
            "cloud_cover_total": "cloud_cover_total_mean",
        },
        ("daily", "climate_summary"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_site": "pressure_air_site_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
        ("monthly", "climate_summary"): {
            "cloud_cover_total": "cloud_cover_total_mean",
        },
    },
    "GeosphereObservationMetadata": {
        ("daily", "data"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_site": "pressure_air_site_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
        ("monthly", "data"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
    },
    "ImgwMeteorologyMetadata": {
        ("daily", "climate"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
        },
        ("daily", "synop"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_air_site": "pressure_air_site_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
        ("monthly", "climate"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
        },
        ("monthly", "synop"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_air_site": "pressure_air_site_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
    },
    "KnmiObservationMetadata": {
        ("10_minutes", "data"): {
            "visibility": "visibility_mean",
        },
        ("daily", "data"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
        },
    },
    "MeteoFranceObservationMetadata": {
        ("daily", "others"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
        ("monthly", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
    },
    "MeteoswissObservationMetadata": {
        ("annual", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_air_site": "pressure_air_site_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
        ("daily", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_air_site": "pressure_air_site_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
        ("hourly", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_air_site": "pressure_air_site_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
        ("monthly", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_air_site": "pressure_air_site_mean",
            "pressure_vapor": "pressure_vapor_mean",
        },
    },
    "MetnoFrostMetadata": {
        ("annual", "data"): {
            "cloud_cover_total": "cloud_cover_total_mean",
        },
        ("daily", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_air_site": "pressure_air_site_mean",
        },
        ("monthly", "data"): {
            "cloud_cover_total": "cloud_cover_total_mean",
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
            "pressure_air_site": "pressure_air_site_mean",
        },
    },
    "RmiObservationMetadata": {
        ("10_minutes", "data"): {
            "humidity_relative": "humidity_relative_mean",
        },
        ("daily", "data"): {
            "humidity_relative": "humidity_relative_mean",
        },
        ("hourly", "data"): {
            "humidity_relative": "humidity_relative_mean",
        },
    },
    "SmhiObservationMetadata": {
        ("1_minute", "data"): {
            "visibility": "visibility_mean",
        },
    },
}


# GH-3151, rest
_MEAN_REST_IN_DATASET: dict[str, dict[tuple[str, str], dict[str, str]]] = {
    "DwdDerivedMetadata": {
        ("monthly", "soil"): {
            "soil_moisture_corn_loamy_silt_00cm_60cm": "soil_moisture_mean_corn_loamy_silt_00cm_60cm",
            "soil_moisture_corn_sand_00cm_60cm": "soil_moisture_mean_corn_sand_00cm_60cm",
            "soil_moisture_grass_loamy_silt_00cm_10cm": "soil_moisture_mean_grass_loamy_silt_00cm_10cm",
            "soil_moisture_grass_loamy_silt_00cm_60cm": "soil_moisture_mean_grass_loamy_silt_00cm_60cm",
            "soil_moisture_grass_loamy_silt_10cm_20cm": "soil_moisture_mean_grass_loamy_silt_10cm_20cm",
            "soil_moisture_grass_loamy_silt_20cm_30cm": "soil_moisture_mean_grass_loamy_silt_20cm_30cm",
            "soil_moisture_grass_loamy_silt_30cm_40cm": "soil_moisture_mean_grass_loamy_silt_30cm_40cm",
            "soil_moisture_grass_loamy_silt_40cm_50cm": "soil_moisture_mean_grass_loamy_silt_40cm_50cm",
            "soil_moisture_grass_loamy_silt_50cm_60cm": "soil_moisture_mean_grass_loamy_silt_50cm_60cm",
            "soil_moisture_grass_sand_00cm_60cm": "soil_moisture_mean_grass_sand_00cm_60cm",
            # GH-3263: the names of before the rename to winter cereals
            "soil_moisture_winter_wheat_loamy_silt_00cm_60cm": "soil_moisture_mean_winter_cereals_loamy_silt_00cm_60cm",
            "soil_moisture_winter_wheat_sand_00cm_60cm": "soil_moisture_mean_winter_cereals_sand_00cm_60cm",
        },
    },
    "DwdObservationMetadata": {
        ("annual", "climate_summary"): {
            "wind_force_beaufort": "wind_force_beaufort_mean",
        },
        ("monthly", "climate_summary"): {
            "wind_force_beaufort": "wind_force_beaufort_mean",
        },
    },
    "KnmiObservationMetadata": {
        ("10_minutes", "data"): {
            "precipitation_intensity": "precipitation_intensity_mean",
            "radiation_global_intensity": "radiation_global_intensity_mean",
        },
    },
    "MeteoswissObservationMetadata": {
        ("10_minutes", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
            "radiation_sky_short_wave_diffuse_intensity": "radiation_sky_short_wave_diffuse_intensity_mean",
        },
        ("annual", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
        },
        ("daily", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
            "radiation_sky_short_wave_diffuse_intensity": "radiation_sky_short_wave_diffuse_intensity_mean",
        },
        ("hourly", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
            "radiation_sky_short_wave_diffuse_intensity": "radiation_sky_short_wave_diffuse_intensity_mean",
        },
        ("monthly", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
        },
    },
    "MetnoFrostMetadata": {
        ("daily", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
        },
        ("hourly", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
        },
        ("monthly", "data"): {
            "snow_depth": "snow_depth_mean",
        },
    },
    "RmiObservationMetadata": {
        ("10_minutes", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
        },
        ("daily", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
        },
        ("hourly", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
        },
    },
}


# GH-2614: a name that says what the source's number is, for a name another dataset of the provider keeps
_WHAT_IT_IS_IN_DATASET: dict[str, dict[tuple[str, str], dict[str, str]]] = {
    # the road messages state no statistic for the humidity (BUFR 0 13 003 stands without a time significance), so
    # `humidity_relative_mean` (the name since GH-3151) is a reading again. The air and dew point temperatures
    # (0 12 101, 0 12 103) stand beside a sensor height (0 07 032) of 4.0, 4.05 or 5.0 m in the station groups that
    # state one and of none in the others, never 2 m
    "DwdRoadMetadata": {
        ("15_minutes", "data"): {
            "humidity_relative_mean": "humidity_relative",
            "temperature_air_2m": "temperature_air",
            "temperature_air_mean_2m": "temperature_air",
            "temperature_dew_point_2m": "temperature_dew_point",
            "temperature_dew_point_mean_2m": "temperature_dew_point",
        },
    },
    # PEGELONLINE's `LT` is "LUFTTEMPERATUR" and its documentation and its series state no height, so the 2 m of the old
    # name was an assumption; the name was `temperature_air_mean_2m` in 0.139.0
    "WsvPegelMetadata": {
        (resolution, "data"): {
            "temperature_air_2m": "temperature_air",
            "temperature_air_mean_2m": "temperature_air",
        }
        for resolution in ("1_minute", "5_minutes", "10_minutes", "15_minutes", "hourly")
    },
    # SWSMOS's `TL` and `TD` are "Lufttemperatur" and "Taupunkttemperatur" and its sheet states no height, so the 2 m of
    # the old names was an assumption (as for the road and WSV above); the names were `..._mean_2m` in 0.139.0. `RC`
    # holds the codes of the road model of SWSMOS (1 dry, 2 moist, 3 snow, ...), which are not the BUFR codes of the
    # road stations (0 dry, 1 moist, 2 wet, ...) that `road_surface_condition` keeps
    "DwdSwsmosMetadata": {
        ("hourly", "data"): {
            "road_surface_condition": "road_surface_condition_forecast",
            "temperature_air_2m": "temperature_air",
            "temperature_air_mean_2m": "temperature_air",
            "temperature_dew_point_2m": "temperature_dew_point",
            "temperature_dew_point_mean_2m": "temperature_dew_point",
        },
    },
    # CHMI's `Fmax` is "Max rychlost", the maximum speed, and the source says nothing of a gust
    "ChmiObservationMetadata": {("daily", "data"): {"wind_gust_max": "wind_speed_max"}},
    # IPMA's `humidade` and `pressao` are, as `temperatura` is, the mean of the hour ("media da hora")
    "IpmaObservationMetadata": {
        ("hourly", "data"): {
            "humidity_relative": "humidity_relative_mean",
            "pressure_air_sea_level": "pressure_air_sea_level_mean",
        },
    },
    # `max_precip_30m` is the largest 30 minutes of the day, `max_precip_24h` of the monthly and annual rows the largest
    # day of the month or the year: both were `precipitation_amount_max`
    "DmiObservationMetadata": {("daily", "data"): {"precipitation_amount_max": "precipitation_amount_max_30min"}},
    # `MO_SH_S` and `JA_SH_S` are the monthly and the annual sum of the daily snow depths ("Monatssumme der taegl.
    # Schneehoehe"), no depth of snow
    "DwdObservationMetadata": {
        ("monthly", "precipitation_more"): {"snow_depth": "snow_depth_sum"},
        ("annual", "precipitation_more"): {"snow_depth": "snow_depth_sum"},
    },
    # `tsmin` of the daily file is the night minimum, 18:10 UTC of the previous day to 06:00 UTC; the 10-minute and the
    # hourly ones are readings of their interval
    #
    # GH-2614, GH-3136: nine rows whose description states a mean ("vektorieller 10-Minuten-Mittelwert",
    # "kalibrierter Stunden-Mittelwert", "Monatsmittel der Terminwerte") and which kept the plain name of a reading
    "GeosphereObservationMetadata": {
        ("10_minutes", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
            "radiation_sky_short_wave_diffuse_intensity": "radiation_sky_short_wave_diffuse_intensity_mean",
            "snow_depth": "snow_depth_mean",
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("hourly", "data"): {
            "radiation_global_intensity": "radiation_global_intensity_mean",
            "wind_direction": "wind_direction_mean",
            "wind_speed": "wind_speed_mean",
        },
        ("daily", "data"): {"temperature_air_min_0_05m": "temperature_air_min_0_05m_night"},
        ("monthly", "data"): {"pressure_air_site": "pressure_air_site_mean"},
    },
}

_merge_in_dataset(_MEAN_WIND_IN_DATASET, _MEAN_HUMIDITY_IN_DATASET, _MEAN_REST_IN_DATASET, _WHAT_IT_IS_IN_DATASET)


def _merge_aliases() -> None:
    """Add the renames that keep their old name as an alias (`wetterdienst.metadata.aliases`) to the tables above.

    An alias is a rename here as well: the hint and the baseline know it, and both stay when the alias ends and its
    entry moves from the alias tables into the ones above.
    """
    _merge_in_dataset(
        {
            metadata_name: {
                key: {old: alias.new for old, alias in aliases.items()} for key, aliases in datasets.items()
            }
            for metadata_name, datasets in PARAMETER_ALIASES_IN_DATASET.items()
        }
    )
    RENAMED_PARAMETERS.update({old: alias.new for old, alias in PARAMETER_ALIASES.items()})


_merge_aliases()

#: resolution values, old to new. `Resolution(old)` is no longer accepted; a request or an option that names the old
#: value is refused with the new one named
RENAMED_RESOLUTIONS: dict[str, str] = {
    # GH-2641: the minute resolutions are plural (`10_minutes`), and so is this one
    "6_hour": "6_hours",
}

#: request arguments, old name to new
RENAMED_ARGUMENTS: dict[str, str] = {
    # GH-2437: the window is a pair of UTC timestamps, not of dates
    "start_date": "start",
    "end_date": "end",
}

#: members of the result classes, by the class that had them, old name to what became of it. A result
#: asked for one of these, or built with it as an argument, fails with this text rather than with the
#: bare "no attribute" or "unexpected keyword argument" a name that never existed gets. `ExportMixin`
#: is what every result but the history one derives from.
RENAMED_RESULT_MEMBERS: dict[str, dict[str, str]] = {
    "ExportMixin": {
        # GH-2626: a result does not change under its holder any more, so a filter hands back a new one
        "filter_by_sql": "was renamed to 'filtered_by_sql', which returns a new result and leaves this one as it is",
    },
    "_ValuesResult": {
        "filter_by_date": "was renamed to 'filtered_by_date', which returns a new result and leaves this one as it is",
    },
    "StationsResult": {
        # GH-2626: what the attribute held is the request, and the stations are in `df`
        "stations": "was renamed to 'request': it is the request that made the stations, which are in 'df'",
    },
    "ValuesResult": {
        # GH-2626: the downloader that produced a result is not part of it
        "values": "is gone, as a result no longer holds the downloader that produced it; use 'stations.values()'",
    },
}


def renamed_result_member(owner: type, name: str) -> str | None:
    """Say what became of a member of a result class that was renamed or removed, if it was.

    Looked up on the class and its bases, so that a rename on `ExportMixin` holds for every result.
    """
    for cls in owner.__mro__:
        if (what := RENAMED_RESULT_MEMBERS.get(cls.__name__, {}).get(name)) is not None:
            return f"{owner.__name__}.{name} {what}"
    return None


def refuse_renamed_arguments(owner: str, kwargs: Mapping[str, object]) -> None:
    """Fail on a keyword argument renamed for 1.0, naming the one to write instead.

    Without this the old keyword fails with Python's bare "unexpected keyword argument", which does
    not say what it is called now.
    """
    # all of them at once, so that a caller passing the old pair learns of both in one go
    renamed = [old for old in kwargs if old in RENAMED_ARGUMENTS]
    if len(renamed) == 1:
        msg = f"{owner}() argument '{renamed[0]}' was renamed to '{RENAMED_ARGUMENTS[renamed[0]]}'"
        raise TypeError(msg)
    if renamed:
        olds = " and ".join(f"'{old}'" for old in renamed)
        news = " and ".join(f"'{RENAMED_ARGUMENTS[old]}'" for old in renamed)
        msg = f"{owner}() arguments {olds} were renamed to {news}"
        raise TypeError(msg)


def renamed_column(old: str, columns: Collection[str]) -> str | None:
    """Name the column `old` is called now, where the frame holds it under that name.

    Looked up regardless of case, as DuckDB matches identifiers. And only where the frame has the
    new name: a values frame never had `height`, and pointing its caller at an `elevation` it lacks
    as well would send them the wrong way.

    A rename inside one dataset (`RENAMED_PARAMETERS_IN_DATASET`) is answered the same way, but only
    where the frame holds a name that rename leads to: a column is not tied to a dataset, so the
    frame is what says which one the caller means.
    """
    columns_by_lower = {column.lower(): column for column in columns}
    key = old.lower()
    new = RENAMED_COLUMNS.get(key)
    if new is None:
        new = _renamed_wide_column(key)
    # a name that was not renamed is no hint at all: DuckDB's own error says more (GH-2032)
    if new and new != key and new in columns_by_lower:
        return columns_by_lower[new]
    # a rename inside one dataset, for a name another dataset still has (GH-3008): known only by the frame having
    # the new name, as a frame is of one provider's dataset and its columns do not say which
    for candidate in _renamed_in_dataset_column(key):
        if candidate in columns_by_lower:
            return columns_by_lower[candidate]
    return None


def _in_dataset_successors() -> dict[str, list[str]]:
    """Collect, for each name renamed in some dataset, the names it became in any, sorted."""
    successors: dict[str, set[str]] = {}
    for datasets in RENAMED_PARAMETERS_IN_DATASET.values():
        for renames in datasets.values():
            for old, new in renames.items():
                successors.setdefault(old, set()).add(new)
    return {old: sorted(news) for old, news in successors.items()}


def _renamed_in_dataset_column(key: str) -> list[str]:
    """List the columns a wide frame's column may be called now after a rename inside one dataset.

    The frame's column follows its parameter, its quality flags column follows that, and a dataset prefix
    stays in front, as `_renamed_wide_column` has it; the candidates are every name the parameter became
    in some dataset, of which the caller keeps the one the frame holds.
    """
    base, suffix = _split_quality(key)
    candidates: list[str] = []
    for old, news in _in_dataset_successors().items():
        if base == old:
            prefix = ""
        elif base.endswith(f"_{old}"):
            prefix = base.removesuffix(old)
        else:
            continue
        candidates.extend(f"{prefix}{new}{suffix}" for new in news)
    return candidates


def _split_quality(key: str) -> tuple[str, str]:
    """Split a wide column's name into the parameter's and the quality flags suffix it is now called by, if any."""
    if key.startswith("qn_"):
        return key.removeprefix("qn_"), "_quality_flags"
    for old_suffix in ("_quality_flags", "_quality_flag", "_quality"):
        if key.endswith(old_suffix):
            return key.removesuffix(old_suffix), "_quality_flags"
    return key, ""


def _renamed_wide_column(key: str) -> str:
    """Rename a wide frame's column after the parameter it is named for.

    A wide frame names a column after its parameter -- prefixed with its dataset where several are
    requested -- and the quality flags column after that, so each follows its parameter's rename;
    `qn_<parameter>` was the quality column's name before GH-2030, and `<parameter>_quality` and
    `<parameter>_quality_flag` its names before the two became one `<parameter>_quality_flags`
    (GH-2758).
    """
    base, suffix = _split_quality(key)
    if base in RENAMED_PARAMETERS:
        return f"{RENAMED_PARAMETERS[base]}{suffix}"
    # `<dataset>_<parameter>`: the longest renamed name the column ends in, after an underscore
    for old_name in sorted(RENAMED_PARAMETERS, key=len, reverse=True):
        if base.endswith(f"_{old_name}"):
            new = f"{base.removesuffix(old_name)}{RENAMED_PARAMETERS[old_name]}"
            # a parameter of its own is no dataset prefix: `count_days_multiday_wind_movement` ends
            # in `wind_movement`, but `count_days_multiday_wind_movement_24h` never existed
            if new in PARAMETERS:
                continue
            return f"{new}{suffix}"
    return f"{base}{suffix}"


def aliased_column(old: str, columns: Collection[str]) -> tuple[str, str, ParameterAlias] | None:
    """Find the column a wide frame holds for a name that is an alias (`wetterdienst.metadata.aliases`), if any.

    Returns the column, the old parameter name and its alias. As `renamed_column` does, it follows the parameter into
    the prefixed `<dataset>_<parameter>` column and the `<parameter>_quality_flags` one, regardless of case, and only
    where the frame holds the column the alias leads to: a column is not tied to a dataset, so the frame says which
    one the caller means.
    """
    columns_by_lower = {column.lower(): column for column in columns}
    base, suffix = _split_quality(old.lower())
    for name, alias in all_aliases():
        if base == name:
            prefix = ""
        elif base.endswith(f"_{name}"):
            prefix = base.removesuffix(name)
        else:
            continue
        if (candidate := f"{prefix}{alias.new}{suffix}") in columns_by_lower:
            return columns_by_lower[candidate], name, alias
    return None
