# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The 38 places of DWD's UV index forecast, with the positions DWD's file does not give (GH-4089).

``uvi.json`` names each place by its city (``"Frankfurt/Main"``, ``"Großer Arber"``) and gives no id and no position,
so the places are kept here. A place is a station of ``dwd/uvi``.

The id is the name as a slug (`slug`): lower case, ``ä``, ``ö``, ``ü`` and ``ß`` written ``ae``, ``oe``, ``ue`` and
``ss``, every other run of characters that are no letter or digit one ``-``. ``Frankfurt/Main`` is
``frankfurt-main``, ``Großer Arber`` ``grosser-arber``. The id is the name's, not a number of DWD's, because DWD
gives the places no number: it is stable for as long as DWD writes the name the same way, and the name is what the
file is keyed by. A place DWD adds to the file is skipped with a warning naming it (`DwdUviValues`) until it is
added here; the id of a place that is already here never changes.

The position is that of a DWD station of the place, the one `source` names (DWD's id and name of it in the
Stationslexikon as ``dwd/observation`` serves it: latitude and longitude in degrees, height in metres). Many names of
the file are DWD's station names (``List auf Sylt``, ``Marienleuchte``, ``Kahler Asten``, ``Weinbiet``, ``Hahn``,
``Frankfurt/Main``). Where a city has several stations the one that is DWD's reference of the city stands for it:
Berlin-Tempelhof, Hamburg-Fuhlsbüttel, München-Stadt, Stuttgart (Schnarrenberg), Dresden-Hosterwitz, Kiel-Holtenau,
Leipzig-Holzhausen and Rostock-Warnemünde, which is a choice (DWD does not say which station its forecast is of).
Where the station has been closed since (Marienleuchte, Neubrandenburg, Osnabrück, Kassel, Weimar, Ulm), the
Stationslexikon still holds its position, which is the place's. The one exception is Bonn, whose station of that name
was closed and renamed: its position and its height (the SRTM value of the gazetteer) are GeoNames' for the city.

The forecast is of the city and not of a station, so a position that is a few kilometres from the centre (an airport,
a hill above the town) is the position of a place, never a claim that the forecast was made for that station.
"""

from __future__ import annotations

import re
from typing import NamedTuple

_TRANSLITERATION = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def slug(name: str) -> str:
    """Give the station id of a place from the name DWD writes for it: ``Frankfurt/Main`` is ``frankfurt-main``."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower().translate(_TRANSLITERATION)).strip("-")


class UviPlace(NamedTuple):
    """A place of the UV index forecast: the name DWD writes, its position and where the position is from."""

    name: str
    latitude: float
    longitude: float
    #: height in metres
    elevation: float
    #: the DWD station of the Stationslexikon the position is of (`<id> <name>`), or the gazetteer it is from
    source: str

    @property
    def station_id(self) -> str:
        """Give the id of the place, the slug of its name."""
        return slug(self.name)


_GEONAMES = "GeoNames 2946447 Bonn (cities15000, 2026-11-17; the height is the SRTM value of the gazetteer)"

#: the places, in the order of the names in the alphabet
PLACES: tuple[UviPlace, ...] = (
    UviPlace("Arkona", 54.6791, 13.4344, 42.0, "DWD 00183 Arkona"),
    UviPlace("Berlin", 52.4676, 13.4020, 48.0, "DWD 00433 Berlin-Tempelhof"),
    UviPlace("Bonn", 50.73438, 7.09549, 64.0, _GEONAMES),
    UviPlace("Bremen", 53.0451, 8.7981, 4.0, "DWD 00691 Bremen"),
    UviPlace("Cottbus", 51.7759, 14.3168, 69.0, "DWD 00880 Cottbus"),
    UviPlace("Dresden", 51.0221, 13.8470, 112.0, "DWD 01050 Dresden-Hosterwitz"),
    UviPlace("Düsseldorf", 51.2960, 6.7686, 37.0, "DWD 01078 Düsseldorf"),
    UviPlace("Frankfurt/Main", 50.0259, 8.5213, 100.0, "DWD 01420 Frankfurt/Main"),
    UviPlace("Freiburg", 48.0232, 7.8343, 237.0, "DWD 01443 Freiburg"),
    UviPlace("Großer Arber", 49.1129, 13.1338, 1436.0, "DWD 01832 Großer Arber"),
    UviPlace("Hahn", 49.9463, 7.2645, 497.0, "DWD 05871 Hahn"),
    UviPlace("Hamburg", 53.6332, 9.9881, 11.0, "DWD 01975 Hamburg-Fuhlsbüttel"),
    UviPlace("Hannover", 52.4644, 9.6779, 55.0, "DWD 02014 Hannover"),
    UviPlace("Kahler Asten", 51.1803, 8.4891, 839.0, "DWD 02483 Kahler Asten"),
    UviPlace("Kassel", 51.2963, 9.4424, 231.0, "DWD 02532 Kassel (closed 2013-10-31)"),
    UviPlace("Kiel", 54.3776, 10.1424, 28.0, "DWD 02564 Kiel-Holtenau"),
    UviPlace("Konstanz", 47.6952, 9.1307, 428.0, "DWD 02712 Konstanz"),
    UviPlace("Leipzig", 51.3151, 12.4462, 138.0, "DWD 02928 Leipzig-Holzhausen"),
    UviPlace("List auf Sylt", 55.0110, 8.4125, 25.0, "DWD 03032 List auf Sylt"),
    UviPlace("Magdeburg", 52.1029, 11.5827, 79.0, "DWD 03126 Magdeburg"),
    UviPlace("Marienleuchte", 54.4937, 11.2411, 9.0, "DWD 03170 Marienleuchte (closed 2010-04-30)"),
    UviPlace("München", 48.1632, 11.5429, 515.0, "DWD 03379 München-Stadt"),
    UviPlace("Neubrandenburg", 53.5468, 13.1914, 81.0, "DWD 03478 Neubrandenburg (closed 2005-08-16)"),
    UviPlace("Norderney", 53.7123, 7.1519, 12.0, "DWD 03631 Norderney"),
    UviPlace("Nürnberg", 49.5030, 11.0549, 314.0, "DWD 03668 Nürnberg"),
    UviPlace("Osnabrück", 52.2553, 8.0534, 95.0, "DWD 03815 Osnabrück (closed 2010-11-30)"),
    UviPlace("Regensburg", 49.0425, 12.1019, 365.0, "DWD 04104 Regensburg"),
    UviPlace("Rostock", 54.1803, 12.0808, 5.0, "DWD 04271 Rostock-Warnemünde"),
    UviPlace("Sankt Peter-Ording", 54.3279, 8.6031, 5.0, "DWD 04393 Sankt Peter-Ording"),
    UviPlace("Seehausen", 52.8911, 11.7297, 22.0, "DWD 04642 Seehausen"),
    UviPlace("Stuttgart", 48.8281, 9.2000, 314.0, "DWD 04928 Stuttgart (Schnarrenberg)"),
    UviPlace("Ulm", 48.3837, 9.9524, 567.0, "DWD 05155 Ulm (closed 2014-09-01)"),
    UviPlace("Waren", 53.5196, 12.6654, 73.0, "DWD 05349 Waren (Müritz)"),
    UviPlace("Weimar", 50.9751, 11.3076, 264.0, "DWD 05419 Weimar (closed 2007-06-30)"),
    UviPlace("Weinbiet", 49.3758, 8.1212, 553.0, "DWD 05426 Weinbiet"),
    UviPlace("Wernigerode", 51.8454, 10.7686, 233.0, "DWD 05490 Wernigerode"),
    UviPlace("Würzburg", 49.7704, 9.9576, 268.0, "DWD 05705 Würzburg"),
    UviPlace("Zugspitze", 47.4210, 10.9848, 2956.0, "DWD 05792 Zugspitze"),
)

#: the places by the name the file writes
PLACES_BY_NAME: dict[str, UviPlace] = {place.name: place for place in PLACES}
