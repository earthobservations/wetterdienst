# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A stub of WMO OSCAR/Surface's register, for the tests of the stations that get a ``wigos_id`` from it (GH-4074).

`oscar_stub_rows/<ISO-3>.json` hold real stations of ``GET .../search/station?territoryName=<ISO-3>``, read 2026-11-19
(each is the whole object OSCAR answered, in the order of its name), picked for what the reader has to tell:

- Germany: stations that DWD numbers with its ``Stations_ID`` (``0-276-3-73`` is Aldersbach-Kramersepp, the DWD station
  ``00073``: the id OSCAR writes without the zeros), the secondary stations (issue number 3), a city climate station
  (6, ``0-276-6-399``) and Neuruppin (2), the ids of issue number 0 and 1 (Helgoland, the radar of Borkum
  ``0-276-0-10103``, the Taunus Observatory), which are no DWD station ids, and Hamburg-Fuhlsbüttel, which has only the
  WMO's own id (``0-20000-0-10147``);
- Finland: ``0-246-0-<fmisid>`` beside ``0-20000-0-<WMO number>`` on Ahtari, Helsinki Kaisaniemi and Jomala, on Helsinki
  Malmi alone, and the station whose id has issue number 3 (``0-246-3-000101``, no fmisid);
- Denmark: ``0-208-0-<stationId>`` beside ``0-20000-0-<WMO number>`` (Copenhagen Airport ``06180`` and Skagen Fyr
  ``06041`` are stations of the stub of DMI's list), and Tranebjerg Syd, which has two ids of the
  issuer (``0-208-0-06134`` and ``0-208-0-06132``) and one of the WMO's;
- Greenland (``GRL``, which OSCAR files apart from Denmark under the same issuer 208): Pituffik ``0-208-0-04202``,
  Qaanaaq ``04205`` and Nuuk ``04250``.

The stub is a cut of the register: its ``totalCount`` is the number of its rows (the register's are 2,495, 362 and 125).
`register` gives the body of a country's answer, `served` the file that serves it from the address of the search.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from wetterdienst.model.oscar import OSCAR_SEARCH_URL
from wetterdienst.util.network import File

_ROWS = Path(__file__).parent / "oscar_stub_rows"

#: the countries that have a stub
TERRITORIES = ("DEU", "FIN", "DNK", "GRL")


def rows(territory: str) -> list[dict]:
    """Give the stations of the stub of a country, as OSCAR answered them."""
    return json.loads((_ROWS / f"{territory}.json").read_text(encoding="utf-8"))


def register(territory: str, stations: list[dict] | None = None, **page: object) -> bytes:
    """Give the body of OSCAR's answer for a country: its stub rows (or `stations`) as one complete page.

    `page` overrides what the page says of itself (``pageCount``, ``totalCount``), for the tests of a page that is not
    the whole register.
    """
    listed = rows(territory) if stations is None else stations
    body = {
        "totalCount": len(listed),
        "pageCount": 1,
        "pageNumber": 1,
        "itemsPerPage": 50000,
        "stationSearchResults": listed,
        **page,
    }
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def served(url: str) -> File | None:
    """Give the file that the stub answers a url of the search with, or None for any other address or country."""
    prefix = f"{OSCAR_SEARCH_URL}?territoryName="
    if not url.startswith(prefix):
        return None
    territory = url.removeprefix(prefix)
    if territory not in TERRITORIES:
        return None
    return File(url=url, content=BytesIO(register(territory)), status=200)
