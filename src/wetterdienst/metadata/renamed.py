"""Names renamed on the way to 1.0, kept so that the old spelling fails by naming the new one.

None of these is accepted in place of its replacement. A caller still writing the old name gets an
error that says what it is called now, instead of the not-found a name that never existed gets.
"""

from collections.abc import Collection, Mapping

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
    # GH-1977: DWD's NL is low cloud, below 2 km, which the name put at 1000 ft
    "cloud_cover_below_1000ft": "cloud_cover_below_2km",
    # GH-2696: DWD's graupel columns, which were read as sleet; no provider has sleet days
    "count_weather_type_sleet": "count_weather_type_graupel",
    # GH-2659: MOSMIX's error of ttt and td follows them to the spot names
    "error_absolute_temperature_air_mean_2m": "error_absolute_temperature_air_2m",
    "error_absolute_temperature_dew_point_mean_2m": "error_absolute_temperature_dew_point_2m",
    # GH-2817: DWD POI's "previous day" wind maximum is the maximum of the 6 hours before the report
    "wind_speed_rolling_mean_max_yesterday": "wind_speed_rolling_mean_max_last_6h",
}

_WIND_LAST_10MIN = {
    "wind_speed": "wind_speed_last_10min",
    "wind_direction": "wind_direction_last_10min",
}
_EXTREMES_LAST_12H = {
    "temperature_air_max_2m": "temperature_air_max_2m_last_12h",
    "temperature_air_min_2m": "temperature_air_min_2m_last_12h",
}
_EXTREMES_OF_THE_PERIOD = {
    "temperature_air_max_2m_multiday": "temperature_air_max_2m",
    "temperature_air_min_2m_multiday": "temperature_air_min_2m",
}
_EXTREMES_MEAN_OF_DAILY = {
    "temperature_air_max_2m": "temperature_air_max_2m_mean",
    "temperature_air_min_2m": "temperature_air_min_2m_mean",
}

#: canonical parameter names renamed inside one dataset, for a name that another dataset of the
#: provider still has, so that `RENAMED_PARAMETERS` cannot hold it. Keyed by the name of the
#: provider's metadata declaration (`MetadataModel.name`), then by `(resolution, dataset)`, to
#: `{old name: new name}`. A request for the old name in that dataset is answered with the new one,
#: as the global renames are, instead of a guess at a near spelling. Not every such rename is listed
#: (the sub-daily `_mean_` temperatures follow a rule, `model.metadata._spot_name`), but each one
#: that is has the old name in the table and the new one in the dataset, which
#: `tests/metadata/test_renamed.py` holds it to.
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
    "DwdMosmixMetadata": {
        ("hourly", "small"): _EXTREMES_LAST_12H,
        ("hourly", "large"): _EXTREMES_LAST_12H,
    },
    "DwdDmoMetadata": {
        ("hourly", "icon"): _EXTREMES_LAST_12H,
        ("hourly", "icon_eu"): _EXTREMES_LAST_12H,
    },
    # GH-2697, GH-2707, GH-2733, GH-2835: the mean of the last 10 minutes, no longer the row's interval
    "DwdObservationMetadata": {("hourly", "wind_synoptic"): {"wind_speed": "wind_speed_last_10min"}},
    "DwdPoiMetadata": {("hourly", "data"): _WIND_LAST_10MIN},
    "FmiObservationMetadata": {("hourly", "data"): _WIND_LAST_10MIN},
    "KnmiObservationMetadata": {("hourly", "data"): {"wind_direction": "wind_direction_last_10min"}},
    "MeteoFranceObservationMetadata": {
        # GH-2834: FXY is the hour's highest 10-minute mean wind, no gust
        ("hourly", "core"): {**_WIND_LAST_10MIN, "wind_gust_max": "wind_speed_rolling_mean_max"},
    },
    "MeteoFranceSynopMetadata": {("subdaily", "data"): _WIND_LAST_10MIN},
    # Frost's own element `wind_speed` still selects its row, so only the direction is not found
    "MetnoFrostMetadata": {("hourly", "data"): {"wind_direction": "wind_direction_last_10min"}},
    "SmhiObservationMetadata": {("hourly", "data"): _WIND_LAST_10MIN},
}

#: request arguments, old name to new
RENAMED_ARGUMENTS: dict[str, str] = {
    # GH-2437: the window is a pair of UTC timestamps, not of dates
    "start_date": "start",
    "end_date": "end",
}


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
    requested -- and the quality flags column after that, so each follows its parameter's rename;
    `qn_<parameter>` was the quality column's name before GH-2030, and `<parameter>_quality` and
    `<parameter>_quality_flag` its names before the two became one `<parameter>_quality_flags`
    (GH-2758).
    """
    base, suffix = key, ""
    if key.startswith("qn_"):
        base, suffix = key.removeprefix("qn_"), "_quality_flags"
    else:
        for old_suffix in ("_quality_flags", "_quality_flag", "_quality"):
            if key.endswith(old_suffix):
                base, suffix = key.removesuffix(old_suffix), "_quality_flags"
                break
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
