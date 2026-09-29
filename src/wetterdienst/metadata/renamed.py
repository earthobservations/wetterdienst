"""Names renamed on the way to 1.0, kept so that the old spelling fails by naming the new one.

None of these is accepted in place of its replacement. A caller still writing the old name gets an
error that says what it is called now, instead of the not-found a name that never existed gets.
"""

from collections.abc import Collection

from wetterdienst.metadata.parameter_table import PARAMETERS

#: frame columns, old name to new
RENAMED_COLUMNS: dict[str, str] = {
    "height": "elevation",  # GH-2024
    "state": "region",  # GH-2026
    "date": "timestamp",  # GH-2028
}


#: canonical parameter names, old name to new
RENAMED_PARAMETERS: dict[str, str] = {
    # GH-2032: misspelt, German or mistranslated names (evaporation targets follow GH-2038 below)
    "chlorid_concentration": "chloride_concentration",
    "cloud_cover_between_2km_to_7km": "cloud_cover_between_2km_and_7km",
    "count_weather_type_ripe": "count_weather_type_hoar_frost",
    "evaporation_height_corn_loamysilt": "evaporation_amount_corn_loamy_silt",
    "evaporation_height_gras_loamysilt": "evaporation_amount_grass_loamy_silt",
    "evaporation_height_gras_sand": "evaporation_amount_grass_sand",
    "evaporation_height_winterwheat_loamysilt": "evaporation_amount_winter_wheat_loamy_silt",
    "evaporation_height_winterwheat_sand": "evaporation_amount_winter_wheat_sand",
    "evapotranspiration_potential_gras_fao_last_24h": "evapotranspiration_potential_grass_fao_last_24h",
    "evapotranspiration_potential_gras_haude_last_24h": "evapotranspiration_potential_grass_haude_last_24h",
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
    "soil_moisture_winterwheat_loamysilt_00cm_60cm": "soil_moisture_winter_wheat_loamy_silt_00cm_60cm",
    "soil_moisture_winterwheat_sand_00cm_60cm": "soil_moisture_winter_wheat_sand_00cm_60cm",
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
    "quality_precipitation_height": "quality_precipitation_amount",
    "quality_precipitation_height_liquid": "quality_precipitation_amount_liquid",
    # GH-2040: the range is what visibility already is
    "visibility_range": "visibility",
    "visibility_range_index": "visibility_index",
    "visibility_range_measurement_method": "visibility_measurement_method",
}


def renamed_column(old: str, columns: Collection[str]) -> str | None:
    """Name the column `old` is called now, where the frame holds it under that name.

    Looked up regardless of case, as DuckDB matches identifiers. And only where the frame has the
    new name: a values frame never had `height`, and pointing its caller at an `elevation` it lacks
    as well would send them the wrong way.
    """
    columns_by_lower = {column.lower(): column for column in columns}
    key = old.lower()
    new = RENAMED_COLUMNS.get(key)
    if new is None:
        new = _renamed_wide_column(key)
    # a name that was not renamed is no hint at all: DuckDB's own error says more (GH-2032)
    return columns_by_lower.get(new) if new and new != key else None


def _renamed_wide_column(key: str) -> str:
    """Rename a wide frame's column after the parameter it is named for.

    A wide frame names a column after its parameter -- prefixed with its dataset where several are
    requested -- and the quality column after that, so each follows its parameter's rename;
    `qn_<parameter>` was the quality column's name before GH-2030.
    """
    base, suffix = key, ""
    if key.startswith("qn_"):
        base, suffix = key.removeprefix("qn_"), "_quality"
    elif key.endswith("_quality"):
        base, suffix = key.removesuffix("_quality"), "_quality"
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
