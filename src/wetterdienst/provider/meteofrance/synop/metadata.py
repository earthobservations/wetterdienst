# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Météo-France SYNOP metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, ETALAB_2_0, build_metadata_model

_MeteoFranceSynopMetadataSpec = {
    "name_short": "Météo-France",
    "name_english": "Météo-France",
    "name_local": "Météo-France",
    "country": "France",
    "country_code": "FR",
    "copyright": "© Météo-France, Etalab Open License 2.0",
    "license": ETALAB_2_0,
    "attribution": "© Météo-France",
    "url": "https://meteo.data.gouv.fr/",
    "kind": "observation",
    "extent": {
        "scope": "national",
        "continents": ["africa", "antarctica", "europe", "north_america", "oceania", "south_america"],
        "country_codes": ["FR"],
        "bbox": [-179.0, -67.0, 167.0, 52.0],
    },
    "timezone": "Europe/Paris",
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
                            "name": "wind_direction_mean_last_10min",
                            "name_original": "dd",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed_mean_last_10min",
                            "name_original": "ff",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max_last_10min",
                            "name_original": "raf10",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "temperature_air_2m",
                            "name_original": "t",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_dew_point_2m",
                            "name_original": "td",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_min_2m_last_24h",
                            "name_original": "tn24",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_max_2m_last_24h",
                            "name_original": "tx24",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "humidity_relative",
                            "name_original": "u",
                            "unit": "percent",
                        },
                        {
                            "name": "visibility",
                            "name_original": "vv",
                            "unit": "meter",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "n",
                            # source already publishes the WMO okta code as a percentage
                            # class (0, 10, 25, 40, 50, 60, 75, 90, 100), not raw eighths
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "pres",
                            "unit": "pascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pmer",
                            "unit": "pascal",
                        },
                        {
                            "name": "precipitation_amount_last_1h",
                            "name_original": "rr1",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_amount_last_3h",
                            "name_original": "rr3",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_amount_last_6h",
                            "name_original": "rr6",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_amount_last_12h",
                            "name_original": "rr12",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_amount_last_24h",
                            "name_original": "rr24",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
MeteoFranceSynopMetadata = build_metadata_model(_MeteoFranceSynopMetadataSpec, "MeteoFranceSynopMetadata")
