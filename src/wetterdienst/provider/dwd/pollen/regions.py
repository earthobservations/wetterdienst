# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The 27 regions of DWD's pollen forecast, which are the stations of ``dwd/pollen`` (GH-4088).

``s31fg.json`` gives a forecast for each *part-region* (``partregion_id``) of a region (``region_id``) of the
Pollenflugbereiche of DWD's medical meteorology, and for a region that has no parts, the region itself, written with
``"partregion_id": -1`` and an empty ``partregion_name`` (Mecklenburg-Vorpommern, Brandenburg und Berlin). DWD ships no
shapes and no position of any of them (``Beschreibung_pollen_s31fg.pdf``), so the stations have no latitude and no
longitude: they are found by their name and their id, never by a distance, a rank or a box.

The id of a station is the number DWD gives the area, as the text of it: the ``partregion_id``, and where there is none
(``-1``) the ``region_id``. DWD numbers the regions in tens (10, 20, ... 120) and the parts of a region in ones (11 and
12 of region 10), so the two never meet and the id is unique: ``11`` is Schleswig-Holstein und Hamburg, Inseln und
Marschen, ``20`` is Mecklenburg-Vorpommern, ``124`` is Bayern, Mainfranken. It is DWD's own number, so it is as stable
as DWD's numbering. The name is ``<region>: <part-region>`` (the region alone where there is no part) and the ``region``
column is the region (the state or states of it, as DWD writes it).

A region that DWD adds to the file is skipped with a warning that names it until it is added here (`DwdPollenValues`);
the id of a region that is here never changes.
"""

from __future__ import annotations

from typing import NamedTuple


class PollenRegion(NamedTuple):
    """A region of the pollen forecast, with the numbers and the names DWD writes for it."""

    region_id: int
    #: ``-1`` where DWD gives the region no parts
    partregion_id: int
    region_name: str
    #: empty where DWD gives the region no parts
    partregion_name: str

    @property
    def station_id(self) -> str:
        """Give the id of the station: the part-region's number, the region's where it has no parts."""
        return str(self.region_id if self.partregion_id == -1 else self.partregion_id)

    @property
    def name(self) -> str:
        """Give the name of the station: the region and its part-region, the region alone where it has none."""
        return f"{self.region_name}: {self.partregion_name}" if self.partregion_name else self.region_name


#: the regions in the order of their numbers, the part-regions as ``s31fg.json`` of 2026-11-17 writes their names
REGIONS: tuple[PollenRegion, ...] = (
    PollenRegion(10, 11, "Schleswig-Holstein und Hamburg", "Inseln und Marschen"),
    PollenRegion(10, 12, "Schleswig-Holstein und Hamburg", "Geest,Schleswig-Holstein und Hamburg"),
    PollenRegion(20, -1, "Mecklenburg-Vorpommern", ""),
    PollenRegion(30, 31, "Niedersachsen und Bremen", "Westl. Niedersachsen/Bremen"),
    PollenRegion(30, 32, "Niedersachsen und Bremen", "Östl. Niedersachsen"),
    PollenRegion(40, 41, "Nordrhein-Westfalen", "Rhein.-Westfäl. Tiefland"),
    PollenRegion(40, 42, "Nordrhein-Westfalen", "Ostwestfalen"),
    PollenRegion(40, 43, "Nordrhein-Westfalen", "Mittelgebirge NRW"),
    PollenRegion(50, -1, "Brandenburg und Berlin", ""),
    PollenRegion(60, 61, "Sachsen-Anhalt", "Tiefland Sachsen-Anhalt"),
    PollenRegion(60, 62, "Sachsen-Anhalt", "Harz"),
    PollenRegion(70, 71, "Thüringen", "Tiefland Thüringen"),
    PollenRegion(70, 72, "Thüringen", "Mittelgebirge Thüringen"),
    PollenRegion(80, 81, "Sachsen", "Tiefland Sachsen"),
    PollenRegion(80, 82, "Sachsen", "Mittelgebirge Sachsen"),
    PollenRegion(90, 91, "Hessen", "Nordhessen und hess. Mittelgebirge"),
    PollenRegion(90, 92, "Hessen", "Rhein-Main"),
    PollenRegion(100, 101, "Rheinland-Pfalz und Saarland", "Rhein, Pfalz, Nahe und Mosel"),
    PollenRegion(100, 102, "Rheinland-Pfalz und Saarland", "Mittelgebirgsbereich Rheinland-Pfalz"),
    PollenRegion(100, 103, "Rheinland-Pfalz und Saarland", "Saarland"),
    PollenRegion(110, 111, "Baden-Württemberg", "Oberrhein und unteres Neckartal"),
    PollenRegion(110, 112, "Baden-Württemberg", "Hohenlohe/mittlerer Neckar/Oberschwaben"),
    PollenRegion(110, 113, "Baden-Württemberg", "Mittelgebirge Baden-Württemberg"),
    PollenRegion(120, 121, "Bayern", "Allgäu/Oberbayern/Bay. Wald"),
    PollenRegion(120, 122, "Bayern", "Donauniederungen"),
    PollenRegion(120, 123, "Bayern", "Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken"),
    PollenRegion(120, 124, "Bayern", "Mainfranken"),
)

#: the regions by the pair of numbers the file keys them by
REGIONS_BY_KEY: dict[tuple[int, int], PollenRegion] = {(r.region_id, r.partregion_id): r for r in REGIONS}
#: the regions by station id
REGIONS_BY_ID: dict[str, PollenRegion] = {region.station_id: region for region in REGIONS}
