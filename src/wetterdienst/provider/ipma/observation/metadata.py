# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IPMA (Portugal) observation metadata.

IPMA (Instituto Português do Mar e da Atmosfera) publishes near-real-time hourly observations from
its automatic station network as a single key-less JSON feed
(https://api.ipma.pt/open-data/observation/meteorology/stations/observations.json). The feed is a
rolling window of roughly the last day, so only the ``recent`` period is available -- there is no
historical archive here.

Field semantics and units follow the IPMA open-data documentation (https://api.ipma.pt/): pressure
is reduced to mean sea level, radiation is global solar radiation in kJ/m², and wind direction is
published as an 8-point *code* (``idDireccVento``) that ``parser.py`` converts to degrees. The
``intensidadeVentoKM`` field (the same wind speed in km/h) is intentionally not mapped -- it
duplicates ``intensidadeVento`` (m/s). ``-99.0`` is the missing-value sentinel and becomes null.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

IpmaObservationMetadata = {
    "name_short": "IPMA",
    "name_english": "Portuguese Institute for Sea and Atmosphere",
    "name_local": "Instituto Português do Mar e da Atmosfera",
    "country": "Portugal",
    "copyright": "© IPMA (Instituto Português do Mar e da Atmosfera)",
    "url": "https://api.ipma.pt/",
    "kind": "observation",
    "timezone": "Europe/Lisbon",
    "timezone_data": "UTC",
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "temperatura",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "humidade",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pressao",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "intensidadeVento",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "idDireccVento",
                            "unit": "degree",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "precAcumulada",
                            "unit": "millimeter",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "radiacao",
                            "unit": "kilojoule_per_square_meter",
                        },
                    ],
                },
            ],
        },
    ],
}
IpmaObservationMetadata = build_metadata_model(IpmaObservationMetadata, "IpmaObservationMetadata")
