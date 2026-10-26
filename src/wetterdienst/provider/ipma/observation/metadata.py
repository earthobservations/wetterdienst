# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IPMA (Portugal) observation metadata.

IPMA (Instituto Português do Mar e da Atmosfera) publishes near-real-time hourly observations from
its automatic station network as a single key-less JSON feed
(https://api.ipma.pt/open-data/observation/meteorology/stations/observations.json). The feed is a
rolling window of roughly the last day, so only the ``recent`` period is available -- there is no
historical archive here.

Field semantics and units follow the IPMA open-data documentation (https://api.ipma.pt/): pressure
is reduced to mean sea level, radiation is "radiação solar (kJ/m2)" (the source says neither global
nor a period, see the description of ``radiacao``), and wind direction is published as an 8-point
*code* (``idDireccVento``) that ``parser.py`` converts to degrees (north, the codes 1 and 9, is 360). The
``intensidadeVentoKM`` field (the same wind speed in km/h) is intentionally not mapped -- it
duplicates ``intensidadeVento`` (m/s). ``-99.0`` is the missing-value sentinel and becomes null.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, LicenseModel, build_metadata_model

_IpmaObservationMetadataSpec = {
    "name_short": "IPMA",
    "name_english": "Portuguese Institute for Sea and Atmosphere",
    "name_local": "Instituto Português do Mar e da Atmosfera",
    "country": "Portugal",
    "country_code": "PT",
    "copyright": "© IPMA (Instituto Português do Mar e da Atmosfera)",
    # no licence is named. IPMA's news item of 2020-02-06 on its API says "Estes dados podem ser usados, reutilizados e
    # redistribuídos livremente - sendo exigido sempre a indicação da fonte dos mesmos", and the conditions of use
    # on api.ipma.pt allow free use "desde que dessa utilização não decorram finalidades lucrativas ou ofensivas"
    "license": LicenseModel(
        spdx_id=None,
        name="IPMA open data: free use, reuse and redistribution with the source named",
        url="https://www.ipma.pt/pt/media/noticias/news.detail.jsp?y=2020&f=api-2020.html",
    ),
    "attribution": "Source: IPMA (Instituto Português do Mar e da Atmosfera)",
    "url": "https://api.ipma.pt/",
    "kind": "observation",
    "extent": {
        "scope": "national",
        "continents": ["europe"],
        "countries": ["PT"],
        "bbox": [-31.5, 30.0, -6.1, 42.2],
    },
    "timezone": "Europe/Lisbon",
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
                            "name": "humidity_relative_mean",
                            "name_original": "humidade",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level_mean",
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
                            "name": "precipitation_amount",
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
IpmaObservationMetadata = build_metadata_model(_IpmaObservationMetadataSpec, "IpmaObservationMetadata")
