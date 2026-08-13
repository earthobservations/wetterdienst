# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""AEMET OpenData observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

# Monthly and annual values come from the same AEMET endpoint (mensualesanuales) and share
# the same field names — the response is split by resolution based on the "fecha" suffix
# ("YYYY-01".."YYYY-12" for months, "YYYY-13" for the year total).
_MONTHLY_ANNUAL_PARAMETERS = [
    {
        "name": "temperature_air_mean_2m",
        "name_original": "tm_mes",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_max_2m_mean",
        "name_original": "tm_max",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_min_2m_mean",
        "name_original": "tm_min",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_max_2m_multiday",
        "name_original": "ta_max",
        "unit": "degree_celsius",
    },
    {
        "name": "temperature_air_min_2m_multiday",
        "name_original": "ta_min",
        "unit": "degree_celsius",
    },
    {
        "name": "precipitation_height",
        "name_original": "p_mes",
        "unit": "millimeter",
    },
    {
        "name": "precipitation_height_max",
        "name_original": "p_max",
        "unit": "millimeter",
    },
    {
        "name": "humidity",
        "name_original": "hr",
        "unit": "percent",
    },
]

# AEMET's annual aggregate doesn't include a humidity field at all (unlike monthly).
_ANNUAL_PARAMETERS = [parameter for parameter in _MONTHLY_ANNUAL_PARAMETERS if parameter["name"] != "humidity"]

AemetObservationMetadata = {
    "name_short": "AEMET",
    "name_english": "State Meteorological Agency of Spain",
    "name_local": "Agencia Estatal de Meteorología",
    "country": "Spain",
    "copyright": "© AEMET",
    "url": "https://opendata.aemet.es/",
    "kind": "observation",
    "timezone": "Europe/Madrid",
    "timezone_data": "Europe/Madrid",
    "auth": True,
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "convencional",
            "periods": ["now"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "ta",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tamax",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tamin",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "tpr",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "prec",
                            "unit": "millimeter",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dv",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "dmax",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "vv",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "vmax",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "pres",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pres_nmar",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "humidity",
                            "name_original": "hr",
                            "unit": "percent",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "diarios",
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
                            "name_original": "tmed",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tmax",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tmin",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "prec",
                            "unit": "millimeter",
                        },
                        {
                            # AEMET documents `dir` as the direction of the maximum gust, not the
                            # mean wind direction -- its hourly block names those `dmax` and `dv`
                            "name": "wind_direction_gust_max",
                            "name_original": "dir",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "velmedia",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "racha",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "pressure_air_site_max",
                            "name_original": "presmax",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site_min",
                            "name_original": "presmin",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "humidity",
                            "name_original": "hrmedia",
                            "unit": "percent",
                        },
                        {
                            "name": "humidity_max",
                            "name_original": "hrmax",
                            "unit": "percent",
                        },
                        {
                            "name": "humidity_min",
                            "name_original": "hrmin",
                            "unit": "percent",
                        },
                    ],
                },
            ],
        },
        {
            "name": "monthly",
            "name_original": "mensuales",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": _MONTHLY_ANNUAL_PARAMETERS,
                },
            ],
        },
        {
            "name": "annual",
            "name_original": "anuales",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": _ANNUAL_PARAMETERS,
                },
            ],
        },
    ],
}
AemetObservationMetadata = build_metadata_model(AemetObservationMetadata, "AemetObservationMetadata")
