# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The WMO numbers of the stations of ``dwd/observation``, read from DWD's Stationslexikon (GH-4073).

The station descriptions the climate data come with (``*_Beschreibung_Stationen.txt``) carry no WMO number. DWD's
Stationslexikon does: an HTML table with a row for every station and product (read 2026-11-16: 21,111 rows of 13,779
stations), where the column ``Stationskennung`` is the id the station has in the network of its product. For the
products ``SY`` (synoptic station) and ``MN`` (the automatic network that took over the synoptic stations) it is the
WMO number, five digits (Berlin-Dahlem ``00403`` is ``10381``, Hamburg-Fuhlsbüttel ``01975`` is ``10147``); for the
others it is the id of that network (the ``03319`` of the Berlin-Dahlem climate station, the ``46552`` of its rain
gauge), and for most ``SY`` and ``MN`` rows it is an id of DWD's own that looks like none (``H808``, ``Q334``). Only a
number of five digits of ``SY`` or ``MN`` is a WMO number.

One station may list its number in more than one row (``SY`` and ``MN``, and ``SY`` twice). The numbers of a station
are read together, and the rule is:

- one distinct number among them: it is the station's ``wmo_id`` (read 2026-11-16: 314 stations, 194 of them with the
  same number for ``SY`` and ``MN`` and 120 with ``SY`` alone; no station had two);
- two or more distinct numbers: no ``wmo_id`` and a warning in the log, since which of the numbers is the station's is
  not for the reader to guess;
- none: no ``wmo_id``.

A WMO number may belong to more than one station id, where the station moved and kept its number (10427 is Altastenberg
``00098`` until 1954 and Kahler Asten ``02483`` from then on, 8 numbers of 306 are shared so). Each id keeps the number
of its own rows, so a search by that number finds both.

A page is no data format: the address, the columns and the notation of the table are DWD's to change. The columns are
found by the name of their header (spelling and hyphenation of the header do not count) and not by position, and a page
that has no header with the three names, no row, or no WMO number at all raises `StationslexikonLayoutError`, which
names the address, rather than leave the column empty. What `with_wmo_id` does with that is its docstring's.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import DownloadError, MetaFileFormatError, NoInternetError, ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.station_ids import wmo_id_or_none
from wetterdienst.util.network import download_file, drop_cached_file
from wetterdienst.util.response_warnings import warn_response
from wetterdienst.util.xml import parse_html

if TYPE_CHECKING:
    from lxml.etree import _Element

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: The page of the Stationslexikon, which a person reads: without the view below it is the introduction (46 KB), the
#: table (5.9 MB) is the same address with this view
STATIONSLEXIKON_PAGE_URL = "https://www.dwd.de/DE/leistungen/klimadatendeutschland/statliste/statlex_html.html"
STATIONSLEXIKON_URL = f"{STATIONSLEXIKON_PAGE_URL}?view=nasPublication"

#: How long the table is kept: the WMO number of a station is a fact that changes when a station is opened, moved or
#: renumbered, a few times a year, and the table is 5.9 MB. The longest expiry that is bounded
STATIONSLEXIKON_EXPIRY = CacheExpiry.ONE_WEEK

#: The code of the warning an answer carries when the table could not be read and the stations have no `wmo_id`
WMO_IDS_UNAVAILABLE = "wmo-ids-unavailable"

#: The products whose `Stationskennung` is the WMO number
WMO_PRODUCTS = frozenset({"SY", "MN"})

#: The encoding of the page (its `<meta>` says so, and the server sends `text/html;charset=utf-8` for the shell only)
_ENCODING = "iso-8859-1"

# the columns that are read, by the name of the header that is looked for: `Stations_ID`, `Kennung`, and
# `Stations-<br>kennung`, which is the one this module calls the number
_ID_HEADER, _PRODUCT_HEADER, _NUMBER_HEADER = "stationsid", "kennung", "stationskennung"
_HEADER_NAMES = {_ID_HEADER: "Stations_ID", _PRODUCT_HEADER: "Kennung", _NUMBER_HEADER: "Stations-kennung"}

_SCHEMA = {"station_id": pl.String, "wmo_id": pl.String}


class StationslexikonLayoutError(MetaFileFormatError):
    """The page of the Stationslexikon is not the table this module reads: its layout has changed or it is no table."""

    def __init__(self, reason: str) -> None:
        """Say what is wrong with the page, naming its address."""
        self.url = STATIONSLEXIKON_URL
        super().__init__(f"DWD's Stationslexikon at {STATIONSLEXIKON_URL} is not the table that was read: {reason}")


def _key(text: str) -> str:
    """Read a header as the letters and digits it is written with: `Stations-kennung` and `stations_kennung` are one."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _text(element: _Element) -> str:
    return "".join(element.itertext()).strip()


def _header_of(root: _Element) -> list[str]:
    """Find the header row: the row of `th` cells that names the three columns, as their keys in order."""
    seen: list[str] = []
    for row in root.iter("tr"):
        keys = [_key(_text(cell)) for cell in row if cell.tag == "th"]
        if {_ID_HEADER, _PRODUCT_HEADER, _NUMBER_HEADER} <= set(keys):
            return keys
        if len(keys) > len(seen):
            seen = keys
    missing = ", ".join(name for key, name in _HEADER_NAMES.items() if key not in seen)
    msg = f"no header row names {missing}" + (f" (the widest header row has {len(seen)} columns)" if seen else "")
    raise StationslexikonLayoutError(msg)


def parse_wmo_ids(content: bytes) -> pl.DataFrame:
    """Read the WMO number of each station out of the page of the Stationslexikon, by the rule of the module docstring.

    Returns one row for each station that has a number: ``station_id`` (``Stations_ID`` padded to five digits) and
    ``wmo_id`` (five digits).

    Raises:
        StationslexikonLayoutError: the page is no HTML, names no header with `Stations_ID`, `Kennung` and
            `Stations-kennung`, has no row under it, or has no five-digit number for `SY` or `MN` at all.

    """
    try:
        root = parse_html(content, _ENCODING)
    except ValueError as error:
        raise StationslexikonLayoutError(str(error)) from error
    header = _header_of(root)
    at_id, at_product, at_number = (header.index(key) for key in (_ID_HEADER, _PRODUCT_HEADER, _NUMBER_HEADER))
    rows = 0
    numbers: dict[str, set[str]] = {}
    for row in root.iter("tr"):
        cells = [cell for cell in row if cell.tag == "td"]
        if len(cells) != len(header):
            continue
        rows += 1
        if _text(cells[at_product]) not in WMO_PRODUCTS:
            continue
        station_id, number = _text(cells[at_id]), wmo_id_or_none(_text(cells[at_number]))
        if number is None or not station_id.isascii() or not station_id.isdigit() or len(station_id) > 5:
            continue
        numbers.setdefault(station_id.zfill(5), set()).add(number)
    if not rows:
        msg = f"the header is there ({', '.join(header)}) and no row of {len(header)} cells under it"
        raise StationslexikonLayoutError(msg)
    if not numbers:
        msg = f"none of its {rows} rows is a product {' or '.join(sorted(WMO_PRODUCTS))} with a number of five digits"
        raise StationslexikonLayoutError(msg)
    conflicting = sorted(station_id for station_id, found in numbers.items() if len(found) > 1)
    if conflicting:
        listed = ", ".join(f"{station_id} ({'/'.join(sorted(numbers[station_id]))})" for station_id in conflicting[:10])
        log.warning(
            f"DWD's Stationslexikon lists more than one WMO number for {len(conflicting)} stations, which have no "
            f"wmo_id: {listed}{', ...' if len(conflicting) > 10 else ''}",
        )
    unique = {station_id: next(iter(found)) for station_id, found in numbers.items() if len(found) == 1}
    return pl.DataFrame({"station_id": list(unique), "wmo_id": list(unique.values())}, schema=_SCHEMA)


def read_wmo_ids(settings: Settings) -> pl.DataFrame:
    """Read the Stationslexikon, kept for a week, and give the WMO number of each station that has one.

    Raises:
        NoInternetError: no connection could be made. DownloadError: the server answered badly (a 429 is the
            `ProviderRateLimitError`). StationslexikonLayoutError: what came is not the table; the copy of it is
            dropped from the cache, so that the next call asks again rather than read the same page for a week.

    """
    file = download_file(
        url=STATIONSLEXIKON_URL,
        cache_dir=settings.cache_dir,
        ttl=STATIONSLEXIKON_EXPIRY,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    file.raise_if_exception()
    if isinstance(file.content, Exception):
        # narrows the type; `raise_if_exception` has raised for any failed download
        raise DownloadError(STATIONSLEXIKON_URL, "no body")
    try:
        return parse_wmo_ids(file.content.read())
    except StationslexikonLayoutError:
        drop_cached_file(
            STATIONSLEXIKON_URL,
            settings.cache_dir,
            STATIONSLEXIKON_EXPIRY,
            settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        raise


def with_wmo_id(stations: pl.LazyFrame, settings: Settings) -> pl.LazyFrame:
    """Add ``wmo_id`` to the stations of ``dwd/observation``, from the Stationslexikon, null for a station without one.

    The number is an enrichment of the station list, not the list: when the Stationslexikon cannot be read the stations
    still come back, with `wmo_id` null and a warning (`wmo-ids-unavailable`) in the log and in the answer, as
    `dwd/dmo` answers with the catalogue shared by both of its products when it cannot read which stations a product
    covers. That is a page that is not the table (`StationslexikonLayoutError`) and a server that answers badly
    (`DownloadError`). A connection that cannot be made (`NoInternetError`) and a rate limit
    (`ProviderRateLimitError`) are raised, as `dwd/dmo` raises them: they are no property of this page, and the next
    request meets them too.
    """
    try:
        wmo_ids = read_wmo_ids(settings)
    except (NoInternetError, ProviderRateLimitError):
        raise
    except (DownloadError, StationslexikonLayoutError) as error:
        warn_response(
            log,
            WMO_IDS_UNAVAILABLE,
            f"DWD's Stationslexikon could not be read, so the stations have no wmo_id: {error}",
        )
        return stations.with_columns(pl.lit(None, dtype=pl.String).alias("wmo_id"))
    return stations.join(wmo_ids.lazy(), on="station_id", how="left", maintain_order="left")
