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
                    # The fields the climate-hourly collection actually publishes. This block used
                    # to carry the daily field list -- max_temperature, snow_on_ground, the degree
                    # days -- none of which exists here, so the whole resolution returned nothing.
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "temp",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dew_point_temp",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "relative_humidity",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "precip_amount",
                            "unit": "millimeter",
                        },
                        {
                            # ECCC publishes hourly station pressure in kPa, not hPa
                            "name": "pressure_air_site",
                            "name_original": "station_pressure",
                            "unit": "kilopascal",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "visibility",
                            "unit": "kilometer",
                        },
                        {
                            # published in tens of degrees, decoded in the parser like the daily
                            # gust direction
                            "name": "wind_direction",
                            "name_original": "wind_direction",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "wind_speed",
                            "unit": "kilometer_per_hour",
                        },
                        {
                            "name": "temperature_wind_chill",
                            "name_original": "windchill",
                            "unit": "degree_celsius",
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
                            "name": "cooling_degree_day",
                            "name_original": "cooling_degree_days",
                            "unit": "degree_celsius_day",
                        },
                        {
                            "name": "heating_degree_day",
                            "name_original": "heating_degree_days",
                            "unit": "degree_celsius_day",
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
                    # The fields the climate-monthly collection actually publishes. This block used
                    # to carry bulk-CSV column headers ("total precip (mm)", "spd of max gust(km/h)")
                    # that the OGC API never returns, along with quality parameters -- quality
                    # arrives in the `quality` column via the *_FLAG join, as it does for daily.
                    # The DAYS_WITH_* counts and NORMAL_* fields are deliberately left out: they
                    # have no canonical name yet, and adding vocabulary belongs in its own change
                    # rather than a repair.
                    "parameters": [
                        {
                            "name": "sunshine_duration",
                            "name_original": "bright_sunshine",
                            "unit": "hour",
                        },
                        {
                            "name": "cooling_degree_day",
                            "name_original": "cooling_degree_days",
                            "unit": "degree_celsius_day",
                        },
                        {
                            "name": "heating_degree_day",
                            "name_original": "heating_degree_days",
                            "unit": "degree_celsius_day",
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
                            "name": "snow_depth",
                            "name_original": "snow_on_ground_last_day",
                            "unit": "centimeter",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "total_precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "total_snowfall",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
EcccObservationMetadata = build_metadata_model(EcccObservationMetadata, "EcccObservationMetadata")
