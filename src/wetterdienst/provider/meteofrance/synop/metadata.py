# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Météo-France SYNOP metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

MeteoFranceSynopMetadata = {
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
            "name": "subdaily",
            "name_original": "synop",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": "synop",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "wind_direction",
                            "name_original": "dd",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "raf10",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "t",
                            "unit_type": "temperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "td",
                            "unit_type": "temperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_min_2m_last_24h",
                            "name_original": "tn24",
                            "unit_type": "temperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_max_2m_last_24h",
                            "name_original": "tx24",
                            "unit_type": "temperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "humidity",
                            "name_original": "u",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "vv",
                            "unit_type": "length_long",
                            "unit": "meter",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "n",
                            # source already publishes the WMO okta code as a percentage
                            # class (0, 10, 25, 40, 50, 60, 75, 90, 100), not raw eighths
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "pres",
                            "unit_type": "pressure",
                            "unit": "pascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pmer",
                            "unit_type": "pressure",
                            "unit": "pascal",
                        },
                        {
                            "name": "precipitation_height_last_1h",
                            "name_original": "rr1",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_3h",
                            "name_original": "rr3",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_6h",
                            "name_original": "rr6",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_12h",
                            "name_original": "rr12",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_24h",
                            "name_original": "rr24",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
MeteoFranceSynopMetadata = build_metadata_model(MeteoFranceSynopMetadata, "MeteoFranceSynopMetadata")
