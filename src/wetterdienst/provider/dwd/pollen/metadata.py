# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD pollen forecast metadata (GH-4088).

DWD's medical meteorology publishes the forecast of the pollen load (``Pollenflug-Gefahrenindex``) for 27 regions of
Germany as one JSON file, https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json, described in
``Beschreibung_pollen_s31fg.pdf`` beside it: for each region and each of eight pollen types the level of the load
expected for today, tomorrow and the day after tomorrow. The file is rewritten once a day in the morning
(``last_update`` is 11:00 local time) and holds no earlier day, so the network has the ``future`` period only and the
three days of the latest file.

The level is one of seven steps, which the file's ``legend`` names (``id1`` to ``id7`` with their ``_desc``), and which
the library serves as a number, 0 to 3 in steps of 0.5: ``0`` is 0 (keine Belastung), ``0-1`` 0.5 (keine bis geringe
Belastung), ``1`` 1 (geringe Belastung), ``1-2`` 1.5 (geringe bis mittlere Belastung), ``2`` 2 (mittlere Belastung),
``2-3`` 2.5 (mittlere bis hohe Belastung) and ``3`` 3 (hohe Belastung). The number is the step's own (the middle of a
range such as ``0-1``) and no concentration: DWD gives no grains per cubic metre, only the load class. A day with no
value is ``-1`` in the file ("Fehlende Werte werden mit einer -1 gekennzeichnet"), which is null here, as is any other
text that is none of the seven steps; the text stays as ``raw:`` in ``quality_flags``.

The file keys a pollen type by its German name without an umlaut (``Graeser``, ``Beifuss``), which is ``name_original``.
The regions are the stations, kept in ``regions.py``: DWD gives them no position.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA, EXTENT_GERMANY

#: the pollen types of the file, with the English name of the canonical parameter: the German name in the file
#: (``Hasel``, ``Erle``, ``Esche``, ``Birke``, ``Graeser``, ``Roggen``, ``Beifuss``, ``Ambrosia``) first
POLLEN_TYPES: dict[str, str] = {
    "Hasel": "pollen_load_hazel",
    "Erle": "pollen_load_alder",
    "Esche": "pollen_load_ash",
    "Birke": "pollen_load_birch",
    "Graeser": "pollen_load_grass",
    "Roggen": "pollen_load_rye",
    "Beifuss": "pollen_load_mugwort",
    "Ambrosia": "pollen_load_ragweed",
}

_DwdPollenMetadataSpec = {
    "name_short": "DWD",
    "name_english": "German Weather Service",
    "name_local": "Deutscher Wetterdienst",
    "country": "Germany",
    "country_code": "DE",
    "copyright": "© Deutscher Wetterdienst (DWD), pollen forecast",
    "license": _METADATA["license"],
    "attribution": _METADATA["attribution"],
    "url": "https://opendata.dwd.de/climate_environment/health/alerts/",
    "kind": "forecast",
    "extent": EXTENT_GERMANY,
    "timezone": "Europe/Berlin",
    "resolutions": [
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["future"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "timestamp_position": "start",
                    "parameters": [
                        {"name": name, "name_original": name_original, "unit": "dimensionless"}
                        for name_original, name in POLLEN_TYPES.items()
                    ],
                },
            ],
        },
    ],
}

DwdPollenMetadata = build_metadata_model(_DwdPollenMetadataSpec, "DwdPollenMetadata")
