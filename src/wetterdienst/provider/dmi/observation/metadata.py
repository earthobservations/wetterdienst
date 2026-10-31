# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DMI (Danish Meteorological Institute) climate data observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import CC_BY_4_0, DATASET_NAME_DEFAULT, LicenseModel, build_metadata_model

# DMI's climateData `stationValue` collection returns every available parameter for a
# station/resolution/date-range in a single request, so each resolution is modelled as one
# grouped default dataset. `name_original` is the raw DMI parameterId.
#
# Only the parameters with a clean canonical equivalent are mapped here (GH-3622). Left out, for want of
# a canonical name or of a unit, or because the statistic differs: the maximum and minimum pressure
# (`max_pressure`, `min_pressure`; sea level, which `pressure_air_site_max` is not), the radiation of a day, month
# and year (`mean_radiation` in MJ/m2, which `energy_per_area` has no unit for), the counts of days that
# have no canonical name (`no_cold_days`, `no_windy_days`, `no_stormy_days`, `no_days_w_storm`,
# `no_days_w_hurricane`, `no_clear_days`, `no_cloudy_days`, `no_days_snow_cover`), the counts `no_summer_days` (DMI:
# "more than 25", counted as > 25 in 121 of 121 months of 06180, against 116 for >= 25) and `no_tropical_nights` ("more
# than 20"), whose canonical names count from the threshold itself, and the heating degree days of Greenland
# (`acc_heating_degree_days_19`, base 19 against the base 17 of Denmark).

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

# Heating degree days (base 17 °C) are aggregated from day resolution upwards.
_HEATING_DEGREE_DAY = {
    "name": "heating_degree_day",
    "name_original": "acc_heating_degree_days_17",
    "unit": "degree_celsius_day",
}

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
# Celsius, as the canonical names do.
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
]

_DAILY_PARAMETERS = [
    *_BASE_PARAMETERS,
    *_HUMIDITY_RELATIVE_EXTREMES,
    _SUNSHINE,
    _CLOUD_COVER_MEAN,
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
    _HEATING_DEGREE_DAY,
    _SUNSHINE,
    _CLOUD_COVER_MEAN,
    *_DAY_COUNTS,
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
