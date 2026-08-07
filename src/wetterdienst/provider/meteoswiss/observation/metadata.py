# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MeteoSwiss observation metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

MeteoswissObservationMetadata = {
    "name_short": "MeteoSwiss",
    "name_english": "MeteoSwiss",
    "name_local": "MétéoSuisse",
    "country": "Switzerland",
    "copyright": "© MeteoSwiss (Federal Office of Meteorology and Climatology), CC BY 4.0",
    "url": "https://www.meteoswiss.admin.ch/",
    "kind": "observation",
    "timezone": "Europe/Zurich",
    "timezone_data": "UTC",
    "resolutions": [
        {
            "name": "10_minutes",
            "name_original": "t",
            "periods": ["historical", "recent", "now"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "ogd-smn",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "wind_direction",
                            "name_original": "dkl010z0",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "fkl010z0",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fkl010z1",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rre150z0",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "prestas0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pp0qffs0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "pva200s0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity",
                            "name_original": "gre000z0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_short_wave_diffuse_intensity",
                            "name_original": "ods000z0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_long_wave_intensity",
                            "name_original": "oli000z0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sre000z0",
                            "unit": "minute",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "htoauts0",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tre200s0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "tre005s0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "tso005s0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "tso010s0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "tso020s0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "ure200s0",
                            "unit": "percent",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "tde200s0",
                            "unit": "degree_celsius",
                        },
                    ],
                },
            ],
        },
        {
            "name": "hourly",
            "name_original": "h",
            "periods": ["historical", "recent", "now"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "ogd-smn",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "wind_direction",
                            "name_original": "dkl010h0",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "fkl010h0",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fkl010h1",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rre150h0",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "prestah0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pp0qffh0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "pva200h0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity",
                            "name_original": "gre000h0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_short_wave_diffuse_intensity",
                            "name_original": "ods000h0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_long_wave_intensity",
                            "name_original": "oli000h0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sre000h0",
                            "unit": "minute",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "htoauths",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tre200h0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tre200hn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tre200hx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "tre005h0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tre005hn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "tso005hs",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "tso010hs",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "tso020hs",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "ure200h0",
                            "unit": "percent",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "tde200h0",
                            "unit": "degree_celsius",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "d",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "ogd-smn",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "wind_direction",
                            "name_original": "dkl010d0",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "fkl010d0",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fkl010d1",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rre150d0",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "prestad0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pp0qffd0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "pva200d0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity",
                            "name_original": "gre000d0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_short_wave_diffuse_intensity",
                            "name_original": "ods000d0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_long_wave_intensity",
                            "name_original": "oli000d0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sre000d0",
                            "unit": "minute",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "htoautd0",
                            "unit": "centimeter",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tre200d0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tre200dn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tre200dx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "tre005d0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tre005dn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_0_05m",
                            "name_original": "tre005dx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "tso005d0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "tso010d0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "tso020d0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "ure200d0",
                            "unit": "percent",
                        },
                        {
                            "name": "evapotranspiration_potential_gras_fao_last_24h",
                            "name_original": "erefaod0",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "monthly",
            "name_original": "m",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "ogd-smn",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "wind_speed",
                            "name_original": "fkl010m0",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fkl010m1",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rre150m0",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "prestam0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pp0qffm0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "pva200m0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity",
                            "name_original": "gre000m0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_long_wave_intensity",
                            "name_original": "oli000m0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sre000m0",
                            "unit": "minute",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tre200m0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tre200mn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tre200mx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "tre005m0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tre005mn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_0_05m",
                            "name_original": "tre005mx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "tso005m0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "tso010m0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "tso020m0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "ure200m0",
                            "unit": "percent",
                        },
                    ],
                },
            ],
        },
        {
            "name": "annual",
            "name_original": "y",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "ogd-smn",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "wind_speed",
                            "name_original": "fkl010y0",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fkl010y1",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rre150y0",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "prestay0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pp0qffy0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "pva200y0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity",
                            "name_original": "gre000y0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_long_wave_intensity",
                            "name_original": "oli000y0",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sre000y0",
                            "unit": "minute",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tre200y0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tre200yn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tre200yx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "tre005y0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tre005yn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_0_05m",
                            "name_original": "tre005yx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "tso005y0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "tso010y0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "tso020y0",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "ure200y0",
                            "unit": "percent",
                        },
                    ],
                },
            ],
        },
    ],
}
MeteoswissObservationMetadata = build_metadata_model(MeteoswissObservationMetadata, "MeteoswissObservationMetadata")
