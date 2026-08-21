# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""SMHI (Sweden) observation metadata.

name_original holds the numeric SMHI parameter id (as a string) used directly in the
request URL, e.g. ".../parameter/1/station/...".
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

SmhiObservationMetadata = {
    "name_short": "SMHI",
    "name_english": "Swedish Meteorological and Hydrological Institute",
    "name_local": "Sveriges meteorologiska och hydrologiska institut",
    "country": "Sweden",
    "copyright": "© SMHI",
    "url": "https://www.smhi.se/data/utforskaren-oppna-data",
    "kind": "observation",
    "timezone": "Europe/Stockholm",
    "resolutions": [
        {
            "name": "1_minute",
            "name_original": "1_minute",
            "periods": ["now"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "45",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "44",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "humidity",
                            "name_original": "43",
                            "unit": "percent",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "52",
                            "unit": "meter",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "51",
                            "unit": "meter",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "47",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "48",
                            "unit": "degree",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "46",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "1",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "39",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "4",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "3",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "21",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "7",
                            "unit": "millimeter",
                        },
                        {
                            "name": "humidity",
                            "name_original": "6",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "9",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "16",
                            "unit": "percent",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "12",
                            "unit": "meter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "2",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "20",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "19",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "5",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "8",
                            "unit": "meter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "monthly",
            "name_original": "monthly",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "22",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "23",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
SmhiObservationMetadata = build_metadata_model(SmhiObservationMetadata, "SmhiObservationMetadata")
