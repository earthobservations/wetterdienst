# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DMI (Danish Meteorological Institute) climate data observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

# DMI's climateData `stationValue` collection returns every available parameter for a
# station/resolution/date-range in a single request, so each resolution is modelled as one
# grouped default dataset. `name_original` is the raw DMI parameterId.
#
# Only the physical parameters with a clean canonical equivalent are mapped here. DMI also
# exposes a set of derived day-count statistics (no_frost_days, no_summer_days,
# no_tropical_nights, no_days_acc_precip_*, ...) at the coarser resolutions; those have no
# canonical Parameter counterpart and are intentionally left out.

# Parameters available at every resolution (hour, day, month, year).
_BASE_PARAMETERS = [
    {
        "name": "temperature_air_mean_2m",
        "name_original": "mean_temp",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_max_2m",
        "name_original": "max_temp_w_date",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_min_2m",
        "name_original": "min_temp",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "humidity",
        "name_original": "mean_relative_hum",
        "unit_type": "fraction",
        "unit": "percent",
    },
    {
        # DMI's mean_pressure is reduced to mean sea level (observed parameter "pressure_at_sea").
        "name": "pressure_air_sea_level",
        "name_original": "mean_pressure",
        "unit_type": "pressure",
        "unit": "hectopascal",
    },
    {
        "name": "precipitation_height",
        "name_original": "acc_precip",
        "unit_type": "precipitation",
        "unit": "millimeter",
    },
    {
        "name": "wind_speed",
        "name_original": "mean_wind_speed",
        "unit_type": "speed",
        "unit": "meter_per_second",
    },
    {
        # maximum of the 10-minute mean wind speed
        "name": "wind_speed_rolling_mean_max",
        "name_original": "max_wind_speed_10min",
        "unit_type": "speed",
        "unit": "meter_per_second",
    },
    {
        # maximum 3-second (gust) wind speed
        "name": "wind_gust_max",
        "name_original": "max_wind_speed_3sec",
        "unit_type": "speed",
        "unit": "meter_per_second",
    },
    {
        "name": "wind_direction",
        "name_original": "mean_wind_dir",
        "unit_type": "angle",
        "unit": "degree",
    },
]

# Heating degree days (base 17 °C) are aggregated from day resolution upwards.
_HEATING_DEGREE_DAY = {
    "name": "heating_degree_day",
    "name_original": "acc_heating_degree_days_17",
    "unit_type": "degree_day",
    "unit": "degree_celsius_day",
}

_DAILY_PARAMETERS = [
    *_BASE_PARAMETERS,
    {
        # maximum 30-minute precipitation within the day
        "name": "precipitation_height_max",
        "name_original": "max_precip_30m",
        "unit_type": "precipitation",
        "unit": "millimeter",
    },
    _HEATING_DEGREE_DAY,
]

# Monthly aggregates add mean daily extremes, relative-humidity extremes and the
# maximum 24-hour precipitation total.
_MONTHLY_PARAMETERS = [
    *_BASE_PARAMETERS,
    _HEATING_DEGREE_DAY,
    {
        "name": "temperature_air_max_2m_mean",
        "name_original": "mean_daily_max_temp",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_min_2m_mean",
        "name_original": "mean_daily_min_temp",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "humidity_max",
        "name_original": "max_relative_hum",
        "unit_type": "fraction",
        "unit": "percent",
    },
    {
        "name": "humidity_min",
        "name_original": "min_relative_hum",
        "unit_type": "fraction",
        "unit": "percent",
    },
    {
        "name": "precipitation_height_max",
        "name_original": "max_precip_24h",
        "unit_type": "precipitation",
        "unit": "millimeter",
    },
]

# Yearly aggregates match monthly minus the relative-humidity extremes (not published at
# year resolution).
_ANNUAL_PARAMETERS = [
    parameter for parameter in _MONTHLY_PARAMETERS if parameter["name"] not in ("humidity_max", "humidity_min")
]


def _default_dataset(parameters: list[dict]) -> dict:
    return {
        "name": DATASET_NAME_DEFAULT,
        "name_original": DATASET_NAME_DEFAULT,
        "grouped": True,
        "parameters": parameters,
    }


DmiObservationMetadata = {
    "name_short": "DMI",
    "name_english": "Danish Meteorological Institute",
    "name_local": "Danmarks Meteorologiske Institut",
    "country": "Denmark",
    "copyright": "© DMI (Danish Meteorological Institute), CC BY 4.0",
    "url": "https://opendatadocs.dmi.govcloud.dk/",
    "kind": "observation",
    "timezone": "Europe/Copenhagen",
    "timezone_data": "Europe/Copenhagen",
    "auth": False,
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hour",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [_default_dataset(_BASE_PARAMETERS)],
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
DmiObservationMetadata = build_metadata_model(DmiObservationMetadata, "DmiObservationMetadata")
