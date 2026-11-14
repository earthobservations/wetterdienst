# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The identifiers a station may carry besides its ``station_id``: ``wmo_id``, ``wigos_id`` and ``icao_id`` (GH-4070).

They are three columns of every stations frame (`wetterdienst.model.schema.STATIONS_SCHEMA`), ``String``, null where the
provider has none, so that the one station is found by the same id whichever provider lists it. Each has one notation,
which a provider's source rarely writes: the WMO number loses its leading zero as an integer, DWD writes ``----`` for no
ICAO code, WIGOS issuers come padded or not. The notation is fixed here, and the core holds every provider to it
(`shape_stations_frame` applies `STATION_ID_COLUMNS` to what a provider hands over):

- ``wmo_id``: five digits, zero-padded (``01001``, ``10381``). A value that is not that (a junk text, the seven-digit
  ``8989xxx`` of Geosphere, a number of another length) is null.
- ``wigos_id``: ``<series>-<issuer>-<issue number>-<local id>``, the three numbers written without leading zeros
  (``0-56-101-01002``, not ``0-056-101-01002``), the local id as the provider publishes it.
- ``icao_id``: four letters, upper case (``EDDH``).

A search by one of them (`TimeseriesRequest.filter_by_wmo_id` and the two others, the ``wmo_id``, ``wigos_id`` and
``icao_id`` parameters of the command line, the REST API and MCP) normalises what it is given the same way before it
compares. It is lenient where the person typing is: ``1001`` and ``1001`` as a number find ``01001``, ``eddh`` finds
``EDDH``, ``0-056-101-01002`` finds ``0-56-101-01002``. A text that cannot be an id of the column is refused
with a `ValueError` that names the notation, as a latitude beyond 90 is, and not answered as no station.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

#: the width of a WMO number: block number (two digits) and station number (three)
WMO_ID_LENGTH = 5

_WMO_ID = re.compile(r"^[0-9]{5}$")
_WIGOS_ID = re.compile(r"^([0-9]+)-([0-9]+)-([0-9]+)-(\S+)$")
_ICAO_ID = re.compile(r"^[A-Z]{4}$")

#: the notation of each column, as the text a refusal gives
WMO_ID_NOTATION = "five digits with leading zeros, e.g. 01001 or 10381"
WIGOS_ID_NOTATION = "<series>-<issuer>-<issue number>-<local id>, e.g. 0-20000-0-10381 or 0-56-101-01002"
ICAO_ID_NOTATION = "four letters, e.g. EDDH"


def wmo_id_or_none(value: object) -> str | None:
    """Read a WMO number as the five-digit text it is written as, or None where it is none.

    Strict: a text of another shape is no WMO number (a source's junk, an id of another scheme), and padding it would
    make one up. A provider whose source drops the leading zero (an integer) pads it with `zfill(5)` before it hands
    it over; the search pads what it is given (`search_wmo_id`).
    """
    if value is None:
        return None
    text = str(value).strip()
    return text if _WMO_ID.fullmatch(text) else None


def wigos_id_or_none(value: object) -> str | None:
    """Read a WIGOS station identifier in the notation of `wigos_id`, or None where it is not one.

    The series, the issuer and the issue number lose their leading zeros, the local identifier is kept as it is.
    """
    if value is None:
        return None
    found = _WIGOS_ID.fullmatch(str(value).strip())
    if found is None:
        return None
    series, issuer, number, local = found.groups()
    return f"{int(series)}-{int(issuer)}-{int(number)}-{local}"


def icao_id_or_none(value: object) -> str | None:
    """Read an ICAO location indicator as four upper-case letters, or None where it is none (``----`` is none)."""
    if value is None:
        return None
    text = str(value).strip().upper()
    return text if _ICAO_ID.fullmatch(text) else None


def _search_ids(
    column: str,
    ids: str | int | Sequence[str | int],
    read: Callable[[str | int], str | None],
    notation: str,
) -> list[str]:
    """Read the ids of a search, each in the notation of its column, refusing one that cannot be an id of it."""
    items = [ids] if isinstance(ids, str | int) else ids
    found: list[str] = []
    for item in items:
        if isinstance(item, bool) or not isinstance(item, str | int):
            msg = f"{column} has to be a text or a number, got {type(item).__name__} {item!r}; use {notation}"
            raise TypeError(msg)
        normalised = read(item)
        if normalised is None:
            msg = f"{item!r} is no {column}; use {notation}"
            raise ValueError(msg)
        found.append(normalised)
    if not found:
        msg = f"{column} names no id; use {notation}"
        raise ValueError(msg)
    return list(dict.fromkeys(found))


def search_wmo_id(ids: str | int | Sequence[str | int]) -> list[str]:
    """Read the WMO numbers of a search: a number or a text of one to five digits is padded to five, as `01001`.

    Raises:
        ValueError: an id is no WMO number (not digits, or more than five).
        TypeError: an id is neither a text nor a number.

    """

    def read(item: str | int) -> str | None:
        text = str(item).strip()
        return wmo_id_or_none(text.zfill(WMO_ID_LENGTH)) if re.fullmatch(r"[0-9]+", text) else None

    return _search_ids("wmo_id", ids, read, WMO_ID_NOTATION)


def search_wigos_id(ids: str | int | Sequence[str | int]) -> list[str]:
    """Read the WIGOS identifiers of a search in the notation of the column (issuer zeros dropped).

    Raises:
        ValueError: an id is no WIGOS station identifier.
        TypeError: an id is neither a text nor a number.

    """
    return _search_ids("wigos_id", ids, wigos_id_or_none, WIGOS_ID_NOTATION)


def search_icao_id(ids: str | int | Sequence[str | int]) -> list[str]:
    """Read the ICAO codes of a search in upper case, whatever case they were typed in.

    Raises:
        ValueError: an id is no ICAO code.
        TypeError: an id is neither a text nor a number.

    """
    return _search_ids("icao_id", ids, icao_id_or_none, ICAO_ID_NOTATION)


def wmo_id_expr(column: str | pl.Expr) -> pl.Expr:
    """Give the expression that reads a column of text as `wmo_id`: five digits, else null."""
    expr = pl.col(column) if isinstance(column, str) else column
    text = expr.cast(pl.String).str.strip_chars()
    return pl.when(text.str.contains(_WMO_ID.pattern)).then(text)


def icao_id_expr(column: str | pl.Expr) -> pl.Expr:
    """Give the expression that reads a column of text as `icao_id`: four letters in upper case, else null."""
    expr = pl.col(column) if isinstance(column, str) else column
    text = expr.cast(pl.String).str.strip_chars().str.to_uppercase()
    return pl.when(text.str.contains(_ICAO_ID.pattern)).then(text)


def wigos_id_expr(column: str | pl.Expr) -> pl.Expr:
    """Give the expression that reads a column of text as `wigos_id`: the issuer's zeros dropped, else null."""
    expr = pl.col(column) if isinstance(column, str) else column
    text = expr.cast(pl.String).str.strip_chars()
    parts = text.str.extract_groups(_WIGOS_ID.pattern)
    numbers = [parts.struct.field(str(index)).cast(pl.Int64, strict=False) for index in (1, 2, 3)]
    local = parts.struct.field("4")
    return pl.when(local.is_not_null() & pl.all_horizontal(number.is_not_null() for number in numbers)).then(
        pl.format("{}-{}-{}-{}", *numbers, local)
    )


#: the expression that reads a column of `STATION_ID_COLUMNS` in its notation; `shape_stations_frame` applies it
STATION_ID_COLUMNS = {"wmo_id": wmo_id_expr, "wigos_id": wigos_id_expr, "icao_id": icao_id_expr}
