# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KNMI (Netherlands) observation metadata.

name_original holds the raw KNMI NetCDF variable name (e.g. "T", "RH"), used directly
to select the variable within each downloaded file.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

KnmiObservationMetadata = {
    "name_short": "KNMI",
    "name_english": "Royal Netherlands Meteorological Institute",
    "name_local": "Koninklijk Nederlands Meteorologisch Instituut",
    "country": "Netherlands",
    "copyright": "© KNMI",
    "url": "https://dataplatform.knmi.nl/",
    "kind": "observation",
    "timezone": "Europe/Amsterdam",
    "timezone_data": "UTC",
    "auth": True,
    "resolutions": [
        {
            "name": "10_minutes",
            "name_original": "10_minutes",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "ta",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_1m",
                            "name_original": "tg",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "td",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_wet_mean_2m",
                            "name_original": "tb",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "rh",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dd",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fx",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p0",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pp",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "qg",
                            "unit_type": "power_per_area",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "ss",
                            "unit_type": "time",
                            "unit": "minute",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "n",
                            "unit_type": "fraction",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "vv",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                        {
                            "name": "precipitation_intensity",
                            "name_original": "rg",
                            "unit_type": "precipitation_intensity",
                            "unit": "millimeter_per_hour",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "dr",
                            "unit_type": "time",
                            "unit": "second",
                        },
                    ],
                },
            ],
        },
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "T",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "TD",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "U",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "FH",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "DD",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "FX",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "RH",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "DR",
                            "unit_type": "time",
                            "unit": "hour",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "P",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "SQ",
                            "unit_type": "time",
                            "unit": "hour",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "Q",
                            "unit_type": "energy_per_area",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "N",
                            "unit_type": "fraction",
                            "unit": "one_eighth",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "TG",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "TN",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "TX",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "UG",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "FG",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "FXX",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "RH",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "DR",
                            "unit_type": "time",
                            "unit": "hour",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "PG",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "SQ",
                            "unit_type": "time",
                            "unit": "hour",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "Q",
                            "unit_type": "energy_per_area",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "NG",
                            "unit_type": "fraction",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "evapotranspiration_potential_last_24h",
                            "name_original": "EV24",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
KnmiObservationMetadata = build_metadata_model(KnmiObservationMetadata, "KnmiObservationMetadata")
