# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""CHMI (Czechia) observation metadata.

The Czech Hydrometeorological Institute publishes historical climate observations as key-less
CSV files through its open-data portal (https://opendata.chmi.cz/). Station metadata comes from
``metadata/meta1.csv``; observations are addressed per ``(station, element)``.

Five resolutions are exposed. The ``daily``, ``monthly`` and ``annual`` resolutions store one flat
CSV per ``(station, element)``; ``10_minutes`` and ``hourly`` are partitioned into one CSV per
``(station, element, month)`` under a year sub-directory (so they require a date range). Every
parameter maps to one CHMI element code (its ``name_original``); the element's storage
sub-directory, the value-selection rule and the file layout are resolved in ``api.py``.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

_TEMPERATURE = {"unit_type": "temperature", "unit": "degree_celsius"}
_PRECIPITATION = {"unit_type": "precipitation", "unit": "millimeter"}
_PRESSURE = {"unit_type": "pressure", "unit": "hectopascal"}
_HUMIDITY = {"unit_type": "fraction", "unit": "percent"}
_WIND_SPEED = {"unit_type": "speed", "unit": "meter_per_second"}

# daily/monthly/annual share the same climatological element codes and value-selection scheme;
# only the file layout and date granularity differ (handled in api.py).
_CLIMATE_PARAMETERS = [
    {"name": "temperature_air_mean_2m", "name_original": "T", **_TEMPERATURE},
    {"name": "temperature_air_max_2m", "name_original": "TMA", **_TEMPERATURE},
    {"name": "temperature_air_min_2m", "name_original": "TMI", **_TEMPERATURE},
    {"name": "precipitation_height", "name_original": "SRA", **_PRECIPITATION},
]

_DAILY_PARAMETERS = [
    *_CLIMATE_PARAMETERS,
    {"name": "humidity", "name_original": "H", **_HUMIDITY},
    {"name": "pressure_air_site", "name_original": "P", **_PRESSURE},
    {"name": "wind_speed", "name_original": "F", **_WIND_SPEED},
    {"name": "wind_gust_max", "name_original": "Fmax", **_WIND_SPEED},
    {"name": "snow_depth", "name_original": "SCE", "unit_type": "length_short", "unit": "centimeter"},
    {"name": "sunshine_duration", "name_original": "SSV", "unit_type": "time", "unit": "hour"},
]

_MINUTE_10_PARAMETERS = [
    {"name": "temperature_air_mean_2m", "name_original": "T", **_TEMPERATURE},
    {"name": "humidity", "name_original": "H", **_HUMIDITY},
    {"name": "pressure_air_site", "name_original": "P", **_PRESSURE},
    {"name": "wind_speed", "name_original": "F", **_WIND_SPEED},
]

_HOURLY_PARAMETERS = [
    {"name": "temperature_dew_point_mean_2m", "name_original": "Td", **_TEMPERATURE},
    {"name": "precipitation_height", "name_original": "SRA1H", **_PRECIPITATION},
    {"name": "pressure_air_site", "name_original": "P", **_PRESSURE},
]


def _resolution(name: str, parameters: list[dict], *, date_required: bool) -> dict:
    return {
        "name": name,
        "name_original": name,
        "periods": ["historical"],
        "date_required": date_required,
        "datasets": [
            {
                "name": DATASET_NAME_DEFAULT,
                "name_original": DATASET_NAME_DEFAULT,
                "grouped": True,
                "parameters": parameters,
            },
        ],
    }


ChmiObservationMetadata = {
    "name_short": "CHMI",
    "name_english": "Czech Hydrometeorological Institute",
    "name_local": "Český hydrometeorologický ústav",
    "country": "Czechia",
    "copyright": "© Czech Hydrometeorological Institute (CHMI)",
    "url": "https://opendata.chmi.cz/",
    "kind": "observation",
    "timezone": "Europe/Prague",
    "timezone_data": "UTC",
    "resolutions": [
        _resolution("10_minutes", _MINUTE_10_PARAMETERS, date_required=True),
        _resolution("hourly", _HOURLY_PARAMETERS, date_required=True),
        _resolution("daily", _DAILY_PARAMETERS, date_required=False),
        _resolution("monthly", _CLIMATE_PARAMETERS, date_required=False),
        _resolution("annual", _CLIMATE_PARAMETERS, date_required=False),
    ],
}
ChmiObservationMetadata = build_metadata_model(ChmiObservationMetadata, "ChmiObservationMetadata")
