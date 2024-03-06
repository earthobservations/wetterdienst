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
    EA = (
        "Environment Agency",
        "Environment Agency",
        "United Kingdom",
        "© Environment Agency of UK",
        "https://environment.data.gov.uk/",
    )
    EAUFRANCE = (
        "Eaufrance",
        "Eaufrance",
        "France",
        "© Eaufrance",
        "https://www.eaufrance.fr/",
    )
    ECCC = (
        "Environnement Et Changement Climatique Canada",
        "Environment And Climate Change Canada",
        "Canada",
        "© Environment And Climate Change Canada (ECCC)",
        "https://climate.weather.gc.ca/climate_data/bulk_data_e.html",
    )
    GEOSPHERE = (
        "Geosphere Österreich",
        "Geosphere Austria",
        "Austria",
        "© ZAMG, Observations",
        "https://www.zamg.ac.at/",
    )
    IMGW = (
        "Instytut Meteorologii i Gospodarki Wodnej",
        "Institute of Meteorology and Water Management",
        "Poland",
        "© IMGW, Observations",
        "https://imgw.pl/",
    )
    NOAA = (
        "National Oceanic And Atmospheric Administration",
        "National Oceanic And Atmospheric Administration",
        "United States Of America",
        "© National Oceanic And Atmospheric Administration (NOAA), Global Historical Climatology Network",
        "http://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/",
    )
    NWS = (
        "NOAA National Weather Service",
        "NOAA National Weather Service",
        "United States Of America",
        "© NOAA NWS (National Weather Service), Observations",
        "https://api.weather.gov/",
    )
    WSV = (
        "Wasserstraßen- und Schifffahrtsverwaltung des Bundes",
        "Federal Waterways and Shipping Administration",
        "Germany",
        "© Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV), Pegelonline",
        "https://pegelonline.wsv.de/webservice/ueberblick",
    )
