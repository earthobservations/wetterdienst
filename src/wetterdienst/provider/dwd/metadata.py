# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD metadata."""

from typing import Any

from wetterdienst.model.metadata import CC_BY_4_0

# `Any` values: the fields are of several types, and a network reads them by name
_METADATA: dict[str, Any] = {
    "name_short": "DWD",
    "name_english": "German Weather Service",
    "name_local": "Deutscher Wetterdienst",
    "country": "Germany",
    "country_code": "DE",
    "copyright": "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
    "license": CC_BY_4_0,
    "attribution": "Source: Deutscher Wetterdienst",
    "url": "https://opendata.dwd.de/climate_environment/CDC/",
}

# where the stations of a German network are: the box the station catalogue rules hold them to (`COUNTRY_BBOX` of
# `tests/provider/station_catalogue.py`)
EXTENT_GERMANY: dict[str, Any] = {
    "scope": "national",
    "continents": ["europe"],
    "country_codes": ["DE"],
    "bbox": [5.8, 47.2, 15.1, 55.1],
}
