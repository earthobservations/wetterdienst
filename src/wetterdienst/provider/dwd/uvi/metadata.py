# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD UV index forecast metadata (GH-4089).

DWD's medical meteorology publishes the forecast of the UV index (``UV-Gefahrenindex``) for 38 places in Germany as
one JSON file, https://opendata.dwd.de/climate_environment/health/alerts/uvi.json, described in
``Beschreibung_uvi.pdf`` beside it: for each place the highest UV index expected for today, tomorrow and the day after
tomorrow, as a whole number. The file is rewritten once a day in the morning and holds no earlier day, so the network
has the ``future`` period only and the three days of the latest file.

The file names a place by its city and gives no position, so the places are kept in ``places.py``.

DWD describes the number as "the maximum UV radiation to be expected" for the day (``maximal zu erwartete
UV-Strahlung``) and the file as the ``UV-Gefahrenindex``, which is the WHO's UV index (a dimensionless number, 0 to 2
low, 3 to 5 moderate, 6 to 7 high, 8 to 10 very high, 11 and above extreme). DWD states neither a time zone nor the
hours of the day; the day is the German calendar date of ``forecast_day``, and the timestamp is that date at 00:00 UTC
as for every daily value of the library.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA, EXTENT_GERMANY

_DwdUviMetadataSpec = {
    "name_short": "DWD",
    "name_english": "German Weather Service",
    "name_local": "Deutscher Wetterdienst",
    "country": "Germany",
    "country_code": "DE",
    "copyright": "© Deutscher Wetterdienst (DWD), UV index forecast",
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
                        {
                            "name": "uv_index_max",
                            # the keys of `forecast` in the file are the days; the one name is the parameter
                            "name_original": "uv_index",
                            "unit": "dimensionless",
                        },
                    ],
                },
            ],
        },
    ],
}

DwdUviMetadata = build_metadata_model(_DwdUviMetadataSpec, "DwdUviMetadata")
