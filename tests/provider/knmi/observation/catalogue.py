# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
# ruff: noqa: E501  (the rows are those of the file, as it wrote them)
"""Rows of KNMI's catalogue of the stations, as the real file wrote them (GH-4008).

Read 2026-11-11 from `csv_knmi_nl_20260615.csv` of the dataset `waarneemstations_csv` 1.0 (77 stations), which the
Open Data API serves with the key of the observations. The rows are the ones a test needs, in the order of the file:

- 06201 an offshore platform that is open (the first row), 06206 a platform that closed on 2020-09-01;
- 06209 IJmond, which the files named "IJMOND WP" until late 2024;
- 06210 Valkenburg (closed 2016) and 06265 Soesterberg (closed 2008-11-15), whose history is in the files and that no
  latest file lists, 06265 closing before the 10-minute files start (2012);
- 06215 Voorschoten, a "Fog station/Meteo site" that the hourly files hold, and 06233 Assendelft, a "Fog station" that
  only the 10-minute files hold (and a WSI of the issuer 528, as 06392 Horst);
- 06240 Schiphol, whose `STARTT` of 1990 is later than its data (1951);
- 06260 De Bilt, 06280 Eelde and 06344 Rotterdam Airport (a height below sea level);
- 06275 Deelen and 06370 Eindhoven, which were moved: the files carry the old position (52.0547, 5.8722 and 51.4497,
  5.3769) until June 2026, the catalogue and the file of 2026-11-10 the new one;
- 78871 and 78990 of the Caribbean Netherlands (block 78).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wetterdienst.provider.knmi.observation.api import _read_station_catalogue

if TYPE_CHECKING:
    import polars as pl

CATALOGUE_HEADER = "STN,WSI,STARTT,STOPT,LOCATIE,TYPE,HOOGTE,POS_X,POS_Y,POS_NB,POS_OL"

CATALOGUE_ROWS = {
    "06201": "201,0-20000-0-06201,2009-02-10,9999-12-31,D15-FA-1,Platform,42.7,-4.51,707.29,54.3256,2.9358",
    "06206": "206,0-20000-0-06206,1979-12-25,2020-09-01,F16-A,Platform/AWS,43.4,65.07,682.16,54.1167,4.0122",
    "06209": "209,0-20000-0-06209,2001-01-29,9999-12-31,IJmond,Wind station,0.0,95.90,497.67,52.4636,4.5175",
    "06210": "210,0-20000-0-06210,1951-01-01,2016-05-03,VALKENBURG VK,AWS/Aerodrome,-0.2,89.48,465.11,52.1703,4.4294",
    "06215": "215,0-20000-0-06215,2014-07-15,9999-12-31,Voorschoten,Fog station/Meteo site,-1.15,89.91,461.71,52.1397,4.4364",
    "06233": "233,0-528-0-06233,2009-07-08,9999-12-31,Assendelft,Fog station,-1.6,110.07,499.56,52.4819,4.7258",
    "06240": "240,0-20000-0-06240,1990-07-01,9999-12-31,Schiphol Airport,Aerodrome,-3.87,114.26,481.20,52.3172,4.7897",
    "06260": "260,0-20000-0-06260,1896-04-01,9999-12-31,De Bilt,Meteo site,1.9,140.78,456.76,52.0989,5.1797",
    "06265": "265,0-20000-0-06265,1951-09-10,2008-11-15,SOESTERBERG,AWS/Aerodrome,14.0,147.18,460.08,52.1289,5.2731",
    "06275": "275,0-20000-0-06275,1949-10-01,9999-12-31,Deelen Airport,Aerodrome,44.92,188.32,452.40,52.0589,5.8731",
    "06280": "280,0-20000-0-06280,1948-08-01,9999-12-31,Groningen Airport Eelde,Aerodrome,3.23,235.16,571.43,53.1236,6.5847",
    "06344": "344,0-20000-0-06344,1956-10-01,9999-12-31,Rotterdam Airport,Aerodrome,-5.14,90.38,441.77,51.9606,4.4469",
    "06370": "370,0-20000-0-06370,1951-01-01,9999-12-31,Eindhoven Airport,Aerodrome,19.54,154.89,386.00,51.4631,5.3856",
    "06392": "392,0-528-0-06392,2024-11-20,9999-12-31,Horst,Meteo site,21.88,201.46,388.87,51.4869,6.0561",
    "78871": "871,0-20000-0-78871,2016-01-01,9999-12-31,Saba Airport,Meteo site,31.0,-7634.49,-297.45,17.6461,-63.2208",
    "78990": "990,0-20000-0-78990,2013-01-01,9999-12-31,Bonaire Airport,Aerodrome,2.11,-8805.61,-358.74,12.1300,-68.2758",
}


def catalogue_csv(*station_ids: str) -> bytes:
    """Write the catalogue file of the stations asked for, in that order (all of them where none is)."""
    rows = [CATALOGUE_ROWS[station_id] for station_id in (station_ids or CATALOGUE_ROWS)]
    return ("\n".join([CATALOGUE_HEADER, *rows]) + "\n").encode()


def catalogue_frame(*station_ids: str) -> pl.DataFrame:
    """Read the catalogue file of the stations asked for as the provider does."""
    return _read_station_catalogue(catalogue_csv(*station_ids))
