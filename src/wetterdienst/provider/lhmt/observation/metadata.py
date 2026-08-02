# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""LHMT (Lithuania) observation metadata.

LHMT (Lietuvos hidrometeorologijos tarnyba) publishes hourly observations from its Lithuanian
station network through a key-less JSON REST API (https://api.meteo.lt/). Unlike a rolling
now-cast feed, the API serves historical data per station and day
(``/v1/stations/{code}/observations/{YYYY-MM-DD}``), reaching back to roughly 2016, so the
``historical`` period is exposed.

Fields are already in canonical SI-ish units (temperature °C, wind m/s, direction degrees, pressure
hPa, humidity/cloud %, precipitation mm, snow cm) and use ``null`` for missing values -- there is no
sentinel to strip. The ``feelsLikeTemperature`` (apparent temperature, no clean canonical parameter)
and ``conditionCode`` (a non-numeric text state) fields are intentionally not mapped.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

LhmtObservationMetadata = {
    "name_short": "LHMT",
    "name_english": "Lithuanian Hydrometeorological Service",
    "name_local": "Lietuvos hidrometeorologijos tarnyba",
    "country": "Lithuania",
    "copyright": "© LHMT (Lietuvos hidrometeorologijos tarnyba)",
    "url": "https://api.meteo.lt/",
    "kind": "observation",
    "timezone": "Europe/Vilnius",
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
                            "name_original": "airTemperature",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "relativeHumidity",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windSpeed",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "windGust",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "windDirection",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "cloudCover",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "seaLevelPressure",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "precipitation",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "snowDepth",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
LhmtObservationMetadata = build_metadata_model(LhmtObservationMetadata, "LhmtObservationMetadata")
