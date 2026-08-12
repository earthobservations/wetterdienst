# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geosphere observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

GeosphereObservationMetadata = {
    "name_short": "Geosphere",
    "name_english": "Geosphere Austria",
    "name_local": "Geosphere Österreich",
    "country": "Austria",
    "copyright": "© ZAMG, Observations",
    "url": "https://www.zamg.ac.at/",
    "kind": "observation",
    "timezone": "Europe/Vienna",
    "timezone_data": "UTC",
    "resolutions": [
        {
            "name": "10_minutes",
            "name_original": "10_minutes",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "klima-v2-10min",
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "humidity",
                            "name_original": "rf",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "rrm",
                            "unit": "minute",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rr",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pred",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity",
                            "name_original": "cglo",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_short_wave_diffuse_intensity",
                            "name_original": "chim",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "sh",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "so",
                            "unit": "second",
                        },
                        {
                            "name": "temperature_air_max_0_05m",
                            "name_original": "tsmax",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tlmax",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "ts",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tl",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tsmin",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tlmin",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "tb10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "tb20",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "tb50",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dd",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "ddx",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "ffx",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_arithmetic",
                            "name_original": "ffam",
                            "unit": "meter_per_second",
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
                    "name_original": "klima-v2-1h",
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "humidity",
                            "name_original": "rf",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "rrm",
                            "unit": "minute",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rr",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pred",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity",
                            "name_original": "cglo",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "sh",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "so_h",
                            "unit": "hour",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tl",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tsmin",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "tb10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "tb20",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "tb50",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_1m",
                            "name_original": "tb100",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_2m",
                            "name_original": "tb200",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dd",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "ddx",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "ffx",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff",
                            "unit": "meter_per_second",
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
                    "name_original": "klima-v2-1d",
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "cloud_cover_total",
                            "name_original": "bewm_mittel",
                            # Geosphere documents bewm_mittel as "1/100", i.e. percent
                            "unit": "percent",
                        },
                        {
                            "name": "humidity",
                            "name_original": "rf_mittel",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rr",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p_mittel",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "dampf_mittel",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "cglo_j",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "sh",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_manual",
                            "name_original": "sh_manu",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "shneu_manu",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "so_h",
                            "unit": "hour",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tlmax",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tl_mittel",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tlmin",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tsmin",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "ffx",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "vv_mittel",
                            "unit": "meter_per_second",
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
                    "name_original": "klima-v2-1m",
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "cloud_cover_total",
                            "name_original": "bewm_mittel",
                            # Geosphere documents bewm_mittel as "1/100", i.e. percent
                            "unit": "percent",
                        },
                        {
                            "name": "humidity",
                            "name_original": "rf_mittel",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rr",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "rr_max",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site_max",
                            "name_original": "pmax",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site_min",
                            "name_original": "pmin",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "dampf_mittel",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "cglo_j",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "shneu_manu",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new_max",
                            "name_original": "shneu_manu_max",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_max",
                            "name_original": "sh_manu_max",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "so_h",
                            "unit": "hour",
                        },
                        {
                            "name": "sunshine_duration_relative",
                            "name_original": "so_r",
                            "unit": "percent",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tlmax",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_concrete_max_0m",
                            "name_original": "bet0_max",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tl_mittel",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_concrete_mean_0m",
                            "name_original": "bet0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tlmin",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_concrete_min_0m",
                            "name_original": "bet0_min",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_0_1m",
                            "name_original": "tb10_max",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_0_2m",
                            "name_original": "tb20_max",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_0_5m",
                            "name_original": "tb50_max",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_1m",
                            "name_original": "tb100_max",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_max_2m",
                            "name_original": "tb200_max",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "tb10_mittel",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "tb20_mittel",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "tb50_mittel",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_1m",
                            "name_original": "tb100_mittel",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_2m",
                            "name_original": "tb200_mittel",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_0_1m",
                            "name_original": "tb10_min",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_0_2m",
                            "name_original": "tb20_min",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_0_5m",
                            "name_original": "tb50_min",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_1m",
                            "name_original": "tb100_min",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_min_2m",
                            "name_original": "tb200_min",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "vv_mittel",
                            "unit": "meter_per_second",
                        },
                    ],
                },
            ],
        },
    ],
}
GeosphereObservationMetadata = build_metadata_model(GeosphereObservationMetadata, "GeosphereObservationMetadata")
