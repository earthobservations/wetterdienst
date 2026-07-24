# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""RMI (Royal Meteorological Institute of Belgium) AWS observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

# RMI publishes automatic weather station (AWS) observations through a key-less GeoServer WFS
# (GeoJSON). Each resolution is a single feature type (aws_10min / aws_1hour / aws_1day) whose
# features carry every parameter as its own column, so each resolution is modelled as one
# grouped default dataset. `name_original` is the raw WFS attribute name.
#
# Only attributes with a clean canonical equivalent are mapped. Deliberately left out:
#   - temp_soil_avg      -- soil temperature at an unspecified depth (the profile is already
#                           covered by the explicit -5/-10/-20/-50 cm attributes).
#   - wind_speed_avg_30m -- wind speed at a 30 m mast; there is no canonical wind-at-30m
#                           parameter, and mixing it with the 10 m wind would be wrong.
#   - sun_int_avg        -- direct/beam solar intensity without a clean canonical counterpart.
#   - qc_flags           -- per-parameter validation flags (metadata, not an observation).

# Soil temperature profile shared by every resolution.
_SOIL_TEMPERATURE = [
    {
        "name": "temperature_soil_mean_0_05m",
        "name_original": "temp_soil_avg_5cm",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_soil_mean_0_1m",
        "name_original": "temp_soil_avg_10cm",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_soil_mean_0_2m",
        "name_original": "temp_soil_avg_20cm",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_soil_mean_0_5m",
        "name_original": "temp_soil_avg_50cm",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
]

# Parameters common to every resolution (both sub-daily and daily).
_COMMON = [
    {
        "name": "precipitation_height",
        "name_original": "precip_quantity",
        "unit_type": "precipitation",
        "unit": "millimeter",
    },
    {
        # air temperature just above the grass surface (PT100 sensor at ~5 cm)
        "name": "temperature_air_mean_0_05m",
        "name_original": "temp_grass_pt100_avg",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    *_SOIL_TEMPERATURE,
    {
        "name": "wind_speed",
        "name_original": "wind_speed_10m",
        "unit_type": "speed",
        "unit": "meter_per_second",
    },
    {
        "name": "wind_gust_max",
        "name_original": "wind_gusts_speed",
        "unit_type": "speed",
        "unit": "meter_per_second",
    },
    {
        "name": "humidity",
        "name_original": "humidity_rel_shelter_avg",
        "unit_type": "fraction",
        "unit": "percent",
    },
    {
        "name": "pressure_air_site",
        "name_original": "pressure",
        "unit_type": "pressure",
        "unit": "hectopascal",
    },
    {
        "name": "sunshine_duration",
        "name_original": "sun_duration",
        "unit_type": "time",
        "unit": "minute",
    },
    {
        "name": "radiation_global",
        "name_original": "short_wave_from_sky_avg",
        "unit_type": "power_per_area",
        "unit": "watt_per_square_meter",
    },
]

# The shelter (2 m) air temperature is reported as an interval mean at sub-daily resolution and
# split into mean/max/min at daily resolution.
_SUBDAILY = [
    {
        "name": "temperature_air_mean_2m",
        "name_original": "temp_dry_shelter_avg",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    *_COMMON,
]

# Wind direction is only published at 10-minute resolution.
_MINUTE_10_PARAMETERS = [
    *_SUBDAILY,
    {
        "name": "wind_direction",
        "name_original": "wind_direction",
        "unit_type": "angle",
        "unit": "degree",
    },
]

_HOURLY_PARAMETERS = _SUBDAILY

_DAILY_PARAMETERS = [
    {
        "name": "temperature_air_mean_2m",
        "name_original": "temp_avg",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_max_2m",
        "name_original": "temp_max",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_min_2m",
        "name_original": "temp_min",
        "unit_type": "temperature",
        "unit": "degree_celsius",
    },
    *_COMMON,
]


def _default_dataset(parameters: list[dict]) -> dict:
    return {
        "name": DATASET_NAME_DEFAULT,
        "name_original": DATASET_NAME_DEFAULT,
        "grouped": True,
        "parameters": parameters,
    }


RmiObservationMetadata = {
    "name_short": "RMI",
    "name_english": "Royal Meteorological Institute of Belgium",
    "name_local": "Koninklijk Meteorologisch Instituut / Institut Royal Météorologique",
    "country": "Belgium",
    "copyright": "© RMI (Royal Meteorological Institute of Belgium), CC BY 4.0",
    "url": "https://opendata.meteo.be/",
    "kind": "observation",
    "timezone": "Europe/Brussels",
    # All WFS timestamps are true UTC instants (the payload carries a trailing "Z"), including the
    # daily aggregates which are labelled at UTC midnight. Emitted `date` labels are therefore
    # UTC, so timezone_data (which drives the `ts_complete` base date grid) must be UTC to align.
    "timezone_data": "UTC",
    "auth": False,
    "resolutions": [
        {
            "name": "10_minutes",
            "name_original": "aws_10min",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [_default_dataset(_MINUTE_10_PARAMETERS)],
        },
        {
            "name": "hourly",
            "name_original": "aws_1hour",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [_default_dataset(_HOURLY_PARAMETERS)],
        },
        {
            "name": "daily",
            "name_original": "aws_1day",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [_default_dataset(_DAILY_PARAMETERS)],
        },
    ],
}
RmiObservationMetadata = build_metadata_model(RmiObservationMetadata, "RmiObservationMetadata")
