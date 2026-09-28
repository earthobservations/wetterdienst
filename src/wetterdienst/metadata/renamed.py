"""Names renamed on the way to 1.0, kept so that the old spelling fails by naming the new one.

None of these is accepted in place of its replacement. A caller still writing the old name gets an
error that says what it is called now, instead of the not-found a name that never existed gets.
"""

from collections.abc import Collection

#: frame columns, old name to new
RENAMED_COLUMNS: dict[str, str] = {
    "height": "elevation",  # GH-2024
    "state": "region",  # GH-2026
    "date": "timestamp",  # GH-2028
}


#: canonical parameter names, old name to new
RENAMED_PARAMETERS: dict[str, str] = {
    # GH-2032: misspelt, German or mistranslated names
    "chlorid_concentration": "chloride_concentration",
    "cloud_cover_between_2km_to_7km": "cloud_cover_between_2km_and_7km",
    "count_weather_type_ripe": "count_weather_type_hoar_frost",
    "evaporation_height_corn_loamysilt": "evaporation_height_corn_loamy_silt",
    "evaporation_height_gras_loamysilt": "evaporation_height_grass_loamy_silt",
    "evaporation_height_gras_sand": "evaporation_height_grass_sand",
    "evaporation_height_winterwheat_loamysilt": "evaporation_height_winter_wheat_loamy_silt",
    "evaporation_height_winterwheat_sand": "evaporation_height_winter_wheat_sand",
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
    "thawing_thickness_plantstock": "thawing_thickness_plant_cover",
    "thawing_thickness_plantstock_max_month": "thawing_thickness_plant_cover_max_month",
    "wave_height_sign": "wave_height_significant",
    "wind_movement_24h": "wind_movement",
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
    if new is None and key.startswith("qn_"):
        # a wide frame's quality columns, which follow their parameter rather than a list (GH-2030)
        new = f"{key.removeprefix('qn_')}_quality"
    return columns_by_lower.get(new) if new else None
