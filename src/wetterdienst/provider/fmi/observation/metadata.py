# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""FMI (Finland) observation metadata.

The Finnish Meteorological Institute publishes open weather-observation data through a
key-less WFS service (https://opendata.fmi.fi/wfs). Observations are retrieved per station
and date range via the ``fmi::observations::weather::simple`` (sub-daily) and
``fmi::observations::weather::daily::simple`` (daily) stored queries, both of which return
every requested parameter in one response -- so each resolution is modelled as a single
grouped default dataset (mirroring DMI).

``name_original`` holds the raw FMI parameter code used directly in the ``parameters=`` query
argument, e.g. ``t2m``, ``ws_10min``, ``rrday``.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

FmiObservationMetadata = {
    "name_short": "FMI",
    "name_english": "Finnish Meteorological Institute",
    "name_local": "Ilmatieteen laitos",
    "country": "Finland",
    "copyright": "© Finnish Meteorological Institute",
    "url": "https://en.ilmatieteenlaitos.fi/open-data",
    "kind": "observation",
    "timezone": "Europe/Helsinki",
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
                            "name": "temperature_air_mean_2m",
                            "name_original": "t2m",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "td",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "rh",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ws_10min",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "wg_10min",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "wd_10min",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "r_1h",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "snow_aws",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "p_sea",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "vis",
                            "unit_type": "length_medium",
                            "unit": "meter",
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
                            "name_original": "tday",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tmax",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tmin",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rrday",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "snow",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
FmiObservationMetadata = build_metadata_model(FmiObservationMetadata, "FmiObservationMetadata")
