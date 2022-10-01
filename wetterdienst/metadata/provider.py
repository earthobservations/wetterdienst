# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
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
        "Environnement Et Changement Climatique Canada",
        "Environment And Climate Change Canada",
        "Canada",
        "© Environment And Climate Change Canada (ECCC)",
        "https://climate.weather.gc.ca/climate_data/bulk_data_e.html",
    )
    NOAA = (
        "National Oceanic And Atmospheric Administration",
        "National Oceanic And Atmospheric Administration",
        "United States Of America",
        "© National Oceanic And Atmospheric Administration (NOAA), " "Global Historical Climatology Network",
        "ftp://ftp.ncdc.noaa.gov/pub/data/ghcn/daily/",
    )
    WSV = (
        "Wasserstraßen- und Schifffahrtsverwaltung des Bundes",
        "Federal Waterways and Shipping Administration",
        "Germany",
        "© Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV), Pegelonline",
        "https://pegelonline.wsv.de/webservice/ueberblick",
    )
    EA = (
        "Environment Agency",
        "Environment Agency",
        "United Kingdom",
        "© Environment Agency of UK",
        "https://environment.data.gov.uk/hydrology/",
    )
