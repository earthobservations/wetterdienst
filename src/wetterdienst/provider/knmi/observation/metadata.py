# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KNMI (Netherlands) observation metadata.

name_original holds the raw KNMI NetCDF variable name (e.g. "T", "RH"), used directly
to select the variable within each downloaded file.
"""

from __future__ import annotations

from wetterdienst.model.metadata import CC_BY_4_0, DATASET_NAME_DEFAULT, build_metadata_model

_KnmiObservationMetadataSpec = {
    "name_short": "KNMI",
    "name_english": "Royal Netherlands Meteorological Institute",
    "name_local": "Koninklijk Nederlands Meteorologisch Instituut",
    "country": "Netherlands",
    "country_code": "NL",
    "copyright": "© KNMI",
    "license": CC_BY_4_0,
    "attribution": "© KNMI",
    "url": "https://dataplatform.knmi.nl/",
    "kind": "observation",
    "extent": {
        "scope": "national",
        "continents": ["europe", "north_america"],
        "country_codes": ["NL"],
        # declared from the documentation of KNMI, no list was read (a key is needed): the 10-minute stations include
        # the Caribbean Netherlands (WMO block 78) and the platforms of the North Sea, north to F3-FB-1 (54.85 N) and
        # A12 (55.4 N), so the box reaches 56, and west to 70.5 so that Aruba (70.0 W) is in it whether or not the
        # dataset lists it: the parser (`public_station_id`) names the Caribbean stations of block 78, and the list was
        # not read
        "bbox": [-70.5, 12.0, 8.0, 56.0],
    },
    "timezone": "Europe/Amsterdam",
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
                            "name": "temperature_air_2m",
                            "name_original": "ta",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_1m",
                            "name_original": "tg",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_2m",
                            "name_original": "td",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_wet_mean_2m",
                            "name_original": "tb",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity_relative",
                            "name_original": "rh",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed_mean",
                            "name_original": "ff",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_mean",
                            "name_original": "dd",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fx",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p0",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pp",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity_mean",
                            "name_original": "qg",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "ss",
                            "unit": "minute",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "n",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "visibility_mean",
                            "name_original": "vv",
                            "unit": "meter",
                        },
                        {
                            "name": "precipitation_intensity_mean",
                            "name_original": "rg",
                            "unit": "millimeter_per_hour",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "dr",
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
                            "name": "temperature_air_2m",
                            "name_original": "T",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_2m",
                            "name_original": "TD",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity_relative",
                            "name_original": "U",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed_mean",
                            "name_original": "FH",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_mean_last_10min",
                            "name_original": "DD",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "FX",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "RH",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "DR",
                            "unit": "hour",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "P",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "SQ",
                            "unit": "hour",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "Q",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "N",
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
                            "unit": "degree_celsius",
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
                            "name": "humidity_relative_mean",
                            "name_original": "UG",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed_mean",
                            "name_original": "FG",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "FXX",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "RH",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "DR",
                            "unit": "hour",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "PG",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "SQ",
                            "unit": "hour",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "Q",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "cloud_cover_total_mean",
                            "name_original": "NG",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "evapotranspiration_potential_last_24h",
                            "name_original": "EV24",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
KnmiObservationMetadata = build_metadata_model(_KnmiObservationMetadataSpec, "KnmiObservationMetadata")
