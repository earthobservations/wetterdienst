# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
# ruff: noqa: E501  (the rows are those of the list, as it wrote them)
"""Rows of the list of KNMI's stations, as the EDR API writes them (GH-3928).

Read 2026-11-11 from `GET /collections/daily-in-situ-meteorological-observations-validated/locations` (77 stations, the
same list for every collection), the rows a test needs, in the order of the list: the name, the type, the height above
sea level, the position (longitude, latitude) and the WIGOS identifier that is the `id`.

- 06201 an offshore platform that is open (the first row), 06206 a platform that closed on 2020-09-01;
- 06209 IJmond;
- 06210 Valkenburg (closed 2016) and 06265 Soesterberg (closed 2008-11-15, its last daily value is of 2008-11-16 and
  its last monthly one of June 2008), the second closing before the 10-minute data starts (2012);
- 06215 Voorschoten, a "Fog station/Meteo site" that has data at every resolution, and 06233 Assendelft, a "Fog station"
  (and a WSI of the issuer 528, as 06392 Horst);
- 06240 Schiphol, which has daily values since 1951 although KNMI's catalogue starts the station in 1990;
- 06260 De Bilt, 06280 Eelde and 06344 Rotterdam Airport (a height below sea level);
- 06275 Deelen and 06370 Eindhoven;
- 78871 and 78990 of the Caribbean Netherlands (block 78).

`ENDS` is what `stations.read_stations` finds for the closed stations: the stamp (the end) of their last day with a value,
as the real API answered on 2026-11-12 (06206 F16-A, 06210 Valkenburg and 06265 Soesterberg, whose last day is
2008-11-16 where its last monthly value is June 2008; the list has two more closed stations, 06212 Hoorn-A and 06311
Hoofdplaat)
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Iterable

#: id -> (the WIGOS identifier, the name, the type, the height, the longitude, the latitude)
LOCATIONS = {
    "06201": ("0-20000-0-06201", "D15-FA-1", "Platform", 42.7, 2.9358, 54.3256),
    "06206": ("0-20000-0-06206", "F16-A", "Platform/AWS", 43.4, 4.0122, 54.1167),
    "06209": ("0-20000-0-06209", "IJmond", "Wind station", 0.0, 4.5175, 52.4636),
    "06210": ("0-20000-0-06210", "VALKENBURG VK", "AWS/Aerodrome", -0.2, 4.4294, 52.1703),
    "06215": ("0-20000-0-06215", "Voorschoten", "Fog station/Meteo site", -1.15, 4.4364, 52.1397),
    "06233": ("0-528-0-06233", "Assendelft", "Fog station", -1.6, 4.7258, 52.4819),
    "06240": ("0-20000-0-06240", "Schiphol Airport", "Aerodrome", -3.87, 4.7897, 52.3172),
    "06260": ("0-20000-0-06260", "De Bilt", "Meteo site", 1.9, 5.1797, 52.0989),
    "06265": ("0-20000-0-06265", "SOESTERBERG", "AWS/Aerodrome", 14.0, 5.2731, 52.1289),
    "06275": ("0-20000-0-06275", "Deelen Airport", "Aerodrome", 44.92, 5.8731, 52.0589),
    "06280": ("0-20000-0-06280", "Groningen Airport Eelde", "Aerodrome", 3.23, 6.5847, 53.1236),
    "06344": ("0-20000-0-06344", "Rotterdam Airport", "Aerodrome", -5.14, 4.4469, 51.9606),
    "06370": ("0-20000-0-06370", "Eindhoven Airport", "Aerodrome", 19.54, 5.3856, 51.4631),
    "06392": ("0-528-0-06392", "Horst", "Meteo site", 21.88, 6.0561, 51.4869),
    "78871": ("0-20000-0-78871", "Saba Airport", "Meteo site", 31.0, -63.2208, 17.6461),
    "78990": ("0-20000-0-78990", "Bonaire Airport", "Aerodrome", 2.11, -68.2758, 12.1300),
}

#: the stations that have closed, and the stamp of their last monthly value (`stations._last_data`)
ENDS = {
    "06206": dt.datetime(2020, 8, 31, tzinfo=dt.UTC),
    "06210": dt.datetime(2016, 5, 3, tzinfo=dt.UTC),
    "06265": dt.datetime(2008, 11, 17, tzinfo=dt.UTC),
}

#: how the list of those that are open now names them: every station but the closed
OPEN = [station for station in LOCATIONS if station not in ENDS]


def feature(station_id: str) -> dict:
    """Write the row of a station as the EDR API's list does."""
    wsi, name, kind, height, longitude, latitude = LOCATIONS[station_id]
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {"name": name, "type": kind, "wmoId": station_id, "height_above_mean_sea_level": height},
        "id": wsi,
    }


def locations_json(station_ids: Iterable[str] | None = None) -> bytes:
    """Write the list of the stations asked for (all of them where none is) as the EDR API's `/locations` does."""
    return json.dumps(
        {"type": "FeatureCollection", "features": [feature(station) for station in (station_ids or LOCATIONS)]}
    ).encode()


def locations_frame(*station_ids: str) -> pl.DataFrame:
    """Give the frame `stations.read_stations` makes of the list: the stations asked for, `end_timestamp` for the closed."""
    ids = station_ids or tuple(LOCATIONS)
    return pl.DataFrame(
        {
            "station_id": list(ids),
            "wigos_id": [LOCATIONS[i][0] for i in ids],
            "name": [LOCATIONS[i][1] for i in ids],
            "latitude": [LOCATIONS[i][5] for i in ids],
            "longitude": [LOCATIONS[i][4] for i in ids],
            "elevation": [LOCATIONS[i][3] for i in ids],
            "type": [LOCATIONS[i][2] for i in ids],
            "end_timestamp": [ENDS.get(i) for i in ids],
        },
        schema={
            "station_id": pl.String,
            "wigos_id": pl.String,
            "name": pl.String,
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "type": pl.String,
            "end_timestamp": pl.Datetime("us", "UTC"),
        },
    )
