# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DMI (Danish Meteorological Institute) climate data observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import CC_BY_4_0, DATASET_NAME_DEFAULT, LicenseModel, build_metadata_model

# DMI's climateData `stationValue` collection returns every available parameter for a
# station/resolution/date-range in a single request, so each resolution is modelled as one
# grouped default dataset. `name_original` is the raw DMI parameterId.
#
# Only the parameters with a canonical equivalent are mapped here (GH-3622). Left out, for want of a canonical name that
# fits exactly: `snow_cover` (the share of the ground covered by snow, in percent; would be `snow_cover`),
# `leaf_moisture` (the minutes of the hour or day with a wet leaf; `leaf_wetness_duration`), `temp_grass` (the air
# temperature at grass height, 5 to 20 cm over the terrain, which is neither `temperature_air_mean_0_05m` nor
# `temperature_air_mean_0_1m`; `temperature_air_mean_grass_height`), `temp_soil_30` (the soil temperature at 30 cm;
# `temperature_soil_mean_0_3m`) and `vapour_pressure_deficit_mean` (in kPa; `vapor_pressure_deficit_mean`).

# Parameters available at every resolution (hour, day, month, year).
_BASE_PARAMETERS = [
    {
        "name": "temperature_air_mean_2m",
        "name_original": "mean_temp",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_max_2m",
        "name_original": "max_temp_w_date",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_min_2m",
        "name_original": "min_temp",
        "unit": "degree_celsius",
    },
    {
        "name": "humidity_relative_mean",
        "name_original": "mean_relative_hum",
        "unit": "percent",
    },
    {
        # DMI's mean_pressure is reduced to mean sea level (observed parameter "pressure_at_sea").
        "name": "pressure_air_sea_level_mean",
        "name_original": "mean_pressure",
        "unit": "hectopascal",
    },
    {
        "name": "precipitation_amount",
        "name_original": "acc_precip",
        "unit": "millimeter",
    },
    {
        "name": "wind_speed_mean",
        "name_original": "mean_wind_speed",
        "unit": "meter_per_second",
    },
    {
        # maximum of the 10-minute mean wind speed
        "name": "wind_speed_rolling_mean_max",
        "name_original": "max_wind_speed_10min",
        "unit": "meter_per_second",
    },
    {
        # maximum 3-second (gust) wind speed
        "name": "wind_gust_max",
        "name_original": "max_wind_speed_3sec",
        "unit": "meter_per_second",
    },
    {
        "name": "wind_direction_mean",
        "name_original": "mean_wind_dir",
        "unit": "degree",
    },
]

# Heating degree days are aggregated from day resolution upwards. DMI publishes them as two fields, by country:
# `acc_heating_degree_days_17` (17 degrees Celsius minus the daily mean temperature; "graddage - Danmark") and
# `acc_heating_degree_days_19` (19 degrees; "graddage - Grønland"). A station has one of the two: the stations of the
# 17 (06019 to 06197, Denmark) and of the 19 (04203 to 04416, Greenland) do not overlap in the days of 2024-01-10 to
# 2024-01-12 nor in the months and years of 2022 and 2023 (read 2026-10-31). So the reader reads the 19 as the 17
# (`_FIELD_SERVED_AS` of `api.py`) and both are the one parameter, whose base is that of the station's country
# (GH-3622).
_HEATING_DEGREE_DAY = {
    "name": "heating_degree_day",
    "name_original": "acc_heating_degree_days_17",
    "unit": "degree_celsius_day",
}
# The highest and lowest of the hourly means of the pressure reduced to mean sea level of the day (DMI: "highest hourly
# value of mean_pressure within a day"), of the month and of the year (the highest and lowest of the underlying daily
# values). Not published at the hour. Published for 45 stations, 38 in Greenland (04xxx) and 7 of 06007 to 06014, none
# of the 06019 to 06197 of Denmark (day, month and year of 2022 to 2024, read 2026-10-31).
_PRESSURE_EXTREMES = [
    {
        "name": "pressure_air_sea_level_max",
        "name_original": "max_pressure",
        "unit": "hectopascal",
    },
    {
        "name": "pressure_air_sea_level_min",
        "name_original": "min_pressure",
        "unit": "hectopascal",
    },
]

# Sunshine, radiation and cloud cover are published for a part of the stations only (the cloud cover of the hours for
# 15 stations, all in Greenland, the sunshine of the hours for 28, read 2026-10-30).
_SUNSHINE_HOURLY = {
    # the minutes of the hour with sunshine ("sun_last1h_glob" of metObs)
    "name": "sunshine_duration",
    "name_original": "bright_sunshine",
    "unit": "minute",
}
_SUNSHINE = {
    # the sum of the hours of the underlying hourly values, in hours
    "name": "sunshine_duration",
    "name_original": "bright_sunshine",
    "unit": "hour",
}
_HUMIDITY_RELATIVE_EXTREMES = [
    {
        "name": "humidity_relative_max",
        "name_original": "max_relative_hum",
        "unit": "percent",
    },
    {
        "name": "humidity_relative_min",
        "name_original": "min_relative_hum",
        "unit": "percent",
    },
]
_CLOUD_COVER_MEAN = {
    "name": "cloud_cover_total_mean",
    "name_original": "mean_cloud_cover",
    "unit": "percent",
}
# Counts of the days of a month or a year on which a threshold was passed. DMI counts the precipitation days at "greater
# than or equal to" 0.1, 1 and 10 mm, the ice days at a maximum below 0 and the frost days at a minimum below 0 degrees
# Celsius, as the canonical names do. The summer days ("maximum temperature > 25 °C") and the tropical nights ("minimum
# temperature > 20 °C") are counted past the threshold, where `count_days_summer` and `count_days_tropical_night` count
# from it (GH-3622): DMI's monthly counts equal the days of its daily values above the threshold in all 157 months it
# published for 2010 to 2023 (of 168) at each of 06180, 06070 and 06041, and fall short of the days at it or above in
# 5, 13 and 1 of them for the summer days (06180, 06070, 06041) and in 0, 1 and 1 for the tropical nights.
_DAY_COUNTS = [
    {
        "name": "count_days_ice",
        "name_original": "no_ice_days",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_frost",
        "name_original": "no_frost_days",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_summer",
        "name_original": "no_summer_days",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_tropical_night",
        "name_original": "no_tropical_nights",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_precipitation_amount_ge_0_1mm",
        "name_original": "no_days_acc_precip_01",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_precipitation_amount_ge_1mm",
        "name_original": "no_days_acc_precip_1",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_precipitation_amount_ge_10mm",
        "name_original": "no_days_acc_precip_10",
        "unit": "dimensionless",
    },
]

# The global radiation of a day, a month and a year (the sum of the underlying hourly values), which DMI publishes in
# MJ/m2: "for hourly time resolution the unit is W/m^2, for all other time resolutions the unit is MJ/m^2"
# (https://www.dmi.dk/friedata/dokumentation/climate-data, parameter table, read 2026-10-31). The library has no MJ/m2,
# so the reader multiplies the value by 1000 (`_TO_DECLARED_UNIT` of `api.py`) and the metadata declares kJ/m2.
_RADIATION_SUM = {
    "name": "radiation_global",
    "name_original": "mean_radiation",
    "unit": "kilojoule_per_square_meter",
}
# The mean vapour pressure, from the hourly values of the mean temperature and the mean relative humidity
# (DMI: "calculation method of mean_vapour_pressure"), published from the day on.
_VAPOUR_PRESSURE = {
    "name": "pressure_vapor_mean",
    "name_original": "mean_vapour_pressure",
    "unit": "hectopascal",
}
# Counts of the days on which DMI's own threshold was passed (DMI's calculation table, read 2026-10-31). Each is
# `>=` or `>` or `<` as DMI writes it, and each was held to the daily values DMI publishes (GH-3622):
# - `no_cold_days`: the days with `min_temp` "less than -10 °C" (`<` fits the monthly counts of 04339, 04250 and 04320
#   of 2011 to 2025 in 152 of 153, 176 of 177 and 180 of 180 months, `<=` in 135, 157 and 172);
# - `no_windy_days`, `no_stormy_days`, `no_days_w_storm`, `no_days_w_hurricane`: the days with `max_wind_speed_10min`
#   (the highest 10-minute mean of the day, `wind_speed_rolling_mean_max`) "greater or equal to" 10.8, 20.8, 24.5 and
#   28.5 m/s; the parameter table calls it "mean wind speed" but the daily mean does not fit the counts (2 of 60 months
#   at 06180 for the windy days against 59 for the maximum), `>` does not either (121 of 145 months at 04339);
# - `no_clear_days` and `no_cloudy_days`: the days with `mean_cloud_cover` "less than 20%" and "greater than 80%",
#   published for every day as 1 or 0 and summed for months and years (every one of 5,404, 5,142 and 5,245 days of
#   04220, 04250 and 04270 is as `<` 20 and `>` 80 say, 63, 74 and 84 days have exactly 80);
# - `no_days_snow_cover`: the days with `snow_depth` "greater than 0" and `snow_cover` "greater than 50" (percent), in
#   the months of 2011 to 2015 at five stations (all 35 months of 06180).
_COUNTS_OF_DAYS_PAST_A_THRESHOLD = [
    {
        "name": "count_days_cold",
        "name_original": "no_cold_days",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_wind_speed_rolling_mean_max_ge_10_8mps",
        "name_original": "no_windy_days",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_wind_speed_rolling_mean_max_ge_20_8mps",
        "name_original": "no_stormy_days",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_wind_speed_rolling_mean_max_ge_24_5mps",
        "name_original": "no_days_w_storm",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_wind_speed_rolling_mean_max_ge_28_5mps",
        "name_original": "no_days_w_hurricane",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_snow_cover_gt_50pct",
        "name_original": "no_days_snow_cover",
        "unit": "dimensionless",
    },
]
_CLEAR_AND_CLOUDY_DAYS = [
    {
        "name": "count_days_cloud_cover_total_mean_lt_20pct",
        "name_original": "no_clear_days",
        "unit": "dimensionless",
    },
    {
        "name": "count_days_cloud_cover_total_mean_gt_80pct",
        "name_original": "no_cloudy_days",
        "unit": "dimensionless",
    },
]
# The greatest depth of snow of a month and of a year (the highest of the daily `snow_depth`), published for 115
# stations, with the date it was reached.
_SNOW_DEPTH_MAX = {
    "name": "snow_depth_max",
    "name_original": "max_snow_depth",
    "unit": "centimeter",
}
# The soil temperature at 10 cm: the mean of the hour, and of the day the average of the hourly values.
_SOIL_TEMPERATURE = {
    "name": "temperature_soil_mean_0_1m",
    "name_original": "temp_soil_10",
    "unit": "degree_celsius",
}

_HOURLY_PARAMETERS = [
    *_BASE_PARAMETERS,
    _SUNSHINE_HOURLY,
    {
        # the mean intensity of the hour (`radia_glob_past1h` of metObs), in W/m2
        "name": "radiation_global_intensity_mean",
        "name_original": "mean_radiation",
        "unit": "watt_per_square_meter",
    },
    {
        # the reading at minute 0 of the hour (`cloud_cover` of metObs), no mean
        "name": "cloud_cover_total",
        "name_original": "mean_cloud_cover",
        "unit": "percent",
    },
    # the extremes and the sums of the 12 and 24 hours up to the end of the hour, reported at 06 and 18 UTC (12 hours)
    # and at 00, 06, 12 and 18 UTC (24 hours) by part of the stations. The temperatures are the highest and lowest of
    # the 12 hourly values that end with their hour (75 of 75 values of 04339, June 2025, for both); the precipitation
    # is the gauge's own reading and within a few tenths of a millimetre of the sum of the hourly values (33 of 39
    # 12 hour and 38 of 44 24 hour values of the month are the sum to a tenth)
    {
        "name": "temperature_air_max_2m_last_12h",
        "name_original": "max_temp_12h",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_min_2m_last_12h",
        "name_original": "min_temperature_12h",
        "unit": "degree_celsius",
    },
    {
        "name": "precipitation_amount_last_12h",
        "name_original": "acc_precip_past12h",
        "unit": "millimeter",
    },
    {
        "name": "precipitation_amount_last_24h",
        "name_original": "acc_precip_past24h",
        "unit": "millimeter",
    },
    _SOIL_TEMPERATURE,
]

_DAILY_PARAMETERS = [
    *_BASE_PARAMETERS,
    *_PRESSURE_EXTREMES,
    *_HUMIDITY_RELATIVE_EXTREMES,
    _SUNSHINE,
    _CLOUD_COVER_MEAN,
    _RADIATION_SUM,
    _VAPOUR_PRESSURE,
    _SOIL_TEMPERATURE,
    *_CLEAR_AND_CLOUDY_DAYS,
    {
        # measured by hand once a day, at 07:00 UTC (`snow_depth_man` of metObs), and so a reading of the day of 06:00
        # to 06:00 UTC that it falls in the start of. DMI turns the codes of the source into numbers: -1 ("less than
        # 0.5 cm") is 0.5 and -2 is 0
        "name": "snow_depth_manual",
        "name_original": "snow_depth",
        "unit": "centimeter",
    },
    {
        # maximum 30-minute precipitation within the day, from 23:31 local time of the previous day (GH-2614)
        "name": "precipitation_amount_max_30min",
        "name_original": "max_precip_30m",
        "unit": "millimeter",
    },
    _HEATING_DEGREE_DAY,
]

# Monthly aggregates add mean daily extremes, relative-humidity extremes, the
# maximum 24-hour precipitation total and the counts of days.
_MONTHLY_PARAMETERS = [
    *_BASE_PARAMETERS,
    *_PRESSURE_EXTREMES,
    _HEATING_DEGREE_DAY,
    _SUNSHINE,
    _CLOUD_COVER_MEAN,
    _RADIATION_SUM,
    _VAPOUR_PRESSURE,
    _SNOW_DEPTH_MAX,
    *_DAY_COUNTS,
    *_COUNTS_OF_DAYS_PAST_A_THRESHOLD,
    *_CLEAR_AND_CLOUDY_DAYS,
    {
        "name": "temperature_air_max_2m_mean",
        "name_original": "mean_daily_max_temp",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_min_2m_mean",
        "name_original": "mean_daily_min_temp",
        "unit": "degree_celsius",
    },
    *_HUMIDITY_RELATIVE_EXTREMES,
    {
        "name": "precipitation_amount_max",
        "name_original": "max_precip_24h",
        "unit": "millimeter",
    },
]

# Yearly aggregates are the monthly ones, the relative-humidity extremes included.
_ANNUAL_PARAMETERS = list(_MONTHLY_PARAMETERS)


def _default_dataset(parameters: list[dict]) -> dict:
    return {
        "name": DATASET_NAME_DEFAULT,
        "name_original": DATASET_NAME_DEFAULT,
        "grouped": True,
        "parameters": parameters,
    }


_DmiObservationMetadataSpec = {
    "name_short": "DMI",
    "name_english": "Danish Meteorological Institute",
    "name_local": "Danmarks Meteorologiske Institut",
    "country": "Denmark",
    "country_code": "DK",
    "copyright": "© DMI (Danish Meteorological Institute), CC BY 4.0",
    # "DMI's Open Data are distributed under the Creative Commons License CC BY 4.0", on DMI's terms of use
    "license": LicenseModel(
        spdx_id=CC_BY_4_0.spdx_id,
        name=CC_BY_4_0.name,
        url="https://www.dmi.dk/friedata/dokumentation/terms-of-use",
    ),
    "attribution": "© DMI (Danish Meteorological Institute)",
    "url": "https://www.dmi.dk/friedata/",
    "kind": "observation",
    "extent": {
        "scope": "national",
        "continents": ["europe", "north_america"],
        "country_codes": ["DK"],
        "bbox": [-75.0, 54.0, 16.0, 84.0],
    },
    "timezone": "Europe/Copenhagen",
    "auth": False,
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hour",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [_default_dataset(_HOURLY_PARAMETERS)],
        },
        {
            "name": "daily",
            "name_original": "day",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [_default_dataset(_DAILY_PARAMETERS)],
        },
        {
            "name": "monthly",
            "name_original": "month",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [_default_dataset(_MONTHLY_PARAMETERS)],
        },
        {
            "name": "annual",
            "name_original": "year",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [_default_dataset(_ANNUAL_PARAMETERS)],
        },
    ],
}
DmiObservationMetadata = build_metadata_model(_DmiObservationMetadataSpec, "DmiObservationMetadata")
