# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Provider(Enum):
    """Source of weather information given as tuple of
    - local name
    - english name
    - country
    - copyright string
    - url to data
    """

    DWD = (
        "Deutscher Wetterdienst",
        "German Weather Service",
        "Germany",
        "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
        "https://opendata.dwd.de/climate_environment/CDC/",
    )
    ECCC = (
        "Environnement et Changement Climatique Canada",
        "Environment and Climate Change Canada",
        "Canada",
        "© Environment and Climate Change Canada (ECCC)",
        "https://climate.weather.gc.ca/climate_data/bulk_data_e.html",
    )
