# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Météo-France observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

MeteoFranceObservationMetadata = {
    "name_short": "Météo-France",
    "name_english": "Météo-France",
    "name_local": "Météo-France",
    "country": "France",
    "copyright": "© Météo-France, Etalab Open License 2.0",
    "url": "https://meteo.data.gouv.fr/",
    "kind": "observation",
    "timezone": "Europe/Paris",
    "timezone_data": "UTC",
    "resolutions": [
        {
            # "Données climatologiques de base - quotidiennes": per-department daily archives,
            # covering the full climatological station network (much larger than the ~190 SYNOP
            # stations in the sibling "synop" network), split into two file groups per department
            "name": "daily",
            "name_original": "quot",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": "core",
                    "name_original": "RR-T-Vent",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "RR",
                            "unit": "millimeter",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "TN",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "TX",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "TM",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "FFM",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "FXI",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "DXI",
                            "unit": "degree",
                        },
                    ],
                },
                {
                    "name": "others",
                    "name_original": "autres-parametres",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "PMERM",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "TSVM",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "INST",
                            "unit": "minute",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "GLOT",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "humidity",
                            "name_original": "UM",
                            "unit": "percent",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "NEIGETOT06",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "HNEIGEF",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
        {
            # "Données climatologiques de base -  6 minutes": per-department archives of a single
            # parameter (precipitation) at its native 6-minute reporting interval, since 2005
            "name": "6_minutes",
            "name_original": "6 minutes",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "MIN",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "RR",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
        {
            # "Données climatologiques de base - horaires": per-department hourly archives, one
            # (unsplit) file group per department covering all ~100 published parameters
            "name": "hourly",
            "name_original": "horaires",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": "core",
                    "name_original": "core",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "RR1",
                            "unit": "millimeter",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "TN",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "TX",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "T",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "FF",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "DD",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "FXY",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "DXY",
                            "unit": "degree",
                        },
                    ],
                },
                {
                    "name": "others",
                    "name_original": "others",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "TD",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "U",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "PMER",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "PSTAT",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "N",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "VV",
                            "unit": "meter",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "GLO",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "INS",
                            "unit": "minute",
                        },
                    ],
                },
            ],
        },
        {
            # "Données climatologiques de base - mensuelles": per-department monthly archives,
            # aggregated from the daily data, in a single file group per department
            "name": "monthly",
            "name_original": "mens",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "MENSQ",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "RR",
                            "unit": "millimeter",
                        },
                        {
                            "name": "temperature_air_min_2m_mean",
                            "name_original": "TN",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m_mean",
                            "name_original": "TX",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "TMM",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "FFM",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "FXIAB",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity",
                            "name_original": "UMM",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "PMERM",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "TSVM",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "INST",
                            "unit": "minute",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "GLOT",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "HNEIGEFTOT",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
MeteoFranceObservationMetadata = build_metadata_model(MeteoFranceObservationMetadata, "MeteoFranceObservationMetadata")
