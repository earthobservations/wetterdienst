# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""ECCC observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

EcccObservationMetadata = {
    "name_short": "ECCC",
    "name_english": "Environment And Climate Change Canada",
    "name_local": "Environnement Et Changement Climatique Canada",
    "country": "Canada",
    "copyright": "© Environment And Climate Change Canada (ECCC)",
    "url": "https://climate.weather.gc.ca/climate_data/bulk_data_e.html",
    "kind": "observation",
    "timezone": "UTC",
    "timezone_data": "UTC",
    "resolutions": [
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
                            "name": "count_days_cooling_degree",
                            "name_original": "cooling_degree_days",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_days_heating_degree",
                            "name_original": "heating_degree_days",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "humidity_max",
                            "name_original": "max_rel_humidity",
                            "unit": "percent",
                        },
                        {
                            "name": "humidity_min",
                            "name_original": "min_rel_humidity",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "total_precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_liquid",
                            "name_original": "total_rain",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "snow_on_ground",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "total_snow",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "direction_max_gust",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "speed_max_gust",
                            "unit": "kilometer_per_hour",
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
                            "name": "count_days_cooling_degree",
                            "name_original": "cooling_degree_days",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_days_heating_degree",
                            "name_original": "heating_degree_days",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "humidity_max",
                            "name_original": "max_rel_humidity",
                            "unit": "percent",
                        },
                        {
                            "name": "humidity_min",
                            "name_original": "min_rel_humidity",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "total_precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_liquid",
                            "name_original": "total_rain",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "snow_on_ground",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "total_snow",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "direction_max_gust",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "speed_max_gust",
                            "unit": "kilometer_per_hour",
                        },
                    ],
                },
            ],
        },
        {
            "name": "monthly",
            "name_original": "monthly",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "total precip (mm)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "quality_precipitation_height",
                            "name_original": "total precip flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height_liquid",
                            "name_original": "total rain (mm)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "quality_precipitation_height_liquid",
                            "name_original": "total rain flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "snow grnd last day (cm)",
                            "unit": "centimeter",
                        },
                        {
                            "name": "quality_snow_depth",
                            "name_original": "snow grnd last day flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "total snow (cm)",
                            "unit": "centimeter",
                        },
                        {
                            "name": "quality_snow_depth_new",
                            "name_original": "total snow flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "extr max temp (°c)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "quality_temperature_air_max_2m",
                            "name_original": "extr max temp flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_max_2m_mean",
                            "name_original": "mean max temp (°c)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "quality_temperature_air_max_2m_mean",
                            "name_original": "mean max temp flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean temp (°c)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "quality_temperature_air_mean_2m",
                            "name_original": "mean temp flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "extr min temp (°c)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "quality_temperature_air_min_2m",
                            "name_original": "extr min temp flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_min_2m_mean",
                            "name_original": "mean min temp (°c)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "quality_temperature_air_min_2m_mean",
                            "name_original": "mean min temp flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "dir of max gust (10s deg)",
                            "unit": "degree",
                        },
                        {
                            "name": "quality_wind_direction_gust_max",
                            "name_original": "dir of max gust flag",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "spd of max gust(km/h)",
                            "unit": "kilometer_per_hour",
                        },
                        {
                            "name": "quality_wind_gust_max",
                            "name_original": "spd of max gust flag",
                            "unit": "dimensionless",
                        },
                    ],
                },
            ],
        },
    ],
}
EcccObservationMetadata = build_metadata_model(EcccObservationMetadata, "EcccObservationMetadata")
