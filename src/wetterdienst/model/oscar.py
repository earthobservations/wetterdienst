# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The WIGOS ids of stations whose provider's id is the local part of one, read from WMO OSCAR/Surface (GH-4074).

A WIGOS station identifier is ``<series>-<issuer>-<issue number>-<local id>``. The issuer of a country's national
ids (``276`` for Germany, ``246`` for Finland, ``208`` for Denmark) lets the national weather service choose the local
part, and DWD, FMI and DMI chose their own station numbers: OSCAR/Surface, WMO's register of observing stations, has
``0-276-3-73`` for the DWD station ``00073`` (Aldersbach-Kramersepp), ``0-246-0-101520`` for the FMI station
``101520`` (Ahtari Myllymäki) and ``0-208-0-06126`` for the DMI station ``06126`` (Aarslev). None of the three
providers publishes a WIGOS id with its stations list, so the register is where the link is (read 2026-11-19: DWD 372
numeric ids of 374 national ones, FMI 288, DMI 86).

The rule is the exact one and no other. A station of the provider gets a ``wigos_id`` where the register holds a WIGOS
id of the provider's country whose local part *is* the provider's station id (`NationalWigosScheme`):

- no match by name and none by position: a name is written differently by every list (``BAD BERKA`` and ``Berka, Bad``)
  and a position moves by a few hundred metres, where an id is the same id or it is not;
- the issuer is the country's own (``0-276-...``), and the issue numbers are those the scheme names (FMI and DMI: ``0``,
  as ``0-246-3-000101`` of the register is not an fmisid; DWD: ``3`` secondary station, ``6`` city climate and ``2``,
  where all 370 ids are the Stations_ID of a station of DWD of the same name; not ``0`` and ``1``, where the local part
  is a WMO-like number of a radar, a profiler (``0-276-0-10103``) or an observatory, no id of DWD's). The WMO's own
  issuer, ``0-20000-0-<WMO number>``, is no local part of the provider's id even where the tails are alike, so it is
  never read here;
- the one difference of notation is the zeros DWD pads its ids with (``00073``), which the register does not write
  (``0-276-3-73``); it is the scheme's `strip_zeros`. A local part that the register writes with leading zeros does not
  match such an id. DMI's and FMI's ids are written the register's way, and are compared as they are;
- where the register holds more than one WIGOS id of the issuer with that local part (two issue numbers), the provider's
  id is no more one of them than the other: ``wigos_id`` stays null and a warning in the log names them, since which is
  the station's is not for the reader to guess (none at the time of reading);
- a ``wigos_id`` the provider's own list publishes stays, whatever the register says (`with_oscar_wigos_id`).

The register is read with ``GET https://oscar.wmo.int/surface/rest/api/search/station?territoryName=<ISO-3>``, one page
of JSON for a country (Germany 2,495 stations, 1.9 MB, about 3 s; no key). The answer is held to what it says of
itself: a country is one page (``pageCount`` 1) and as many stations as ``totalCount``, with a WIGOS id among them. A
page that is none of it, whatever the status (an HTML waiting page, a JSON error, a page cut short) is no register and
never an empty one: it raises (`OscarRegisterError`, a `DownloadError` for a page that is no JSON at all) and is dropped
from the cache, which holds a 200 for the whole week. The register is kept in the cache for a week, as the WIGOS ids of
a station change a few times a year, and in the process for a day; a failure to read it is remembered for five minutes
so that a register that is down is not asked for by every request, and a rate limit not at all.

The ids are an enrichment of the station list, not the list: when the register cannot be read the stations still come
back, with the column as it would be without OSCAR and the warning `wigos-ids-unavailable` in the log and in the
answer (`with_oscar_wigos_id`), as for `wmo_id` of ``dwd/observation`` (`wmo-ids-unavailable`, GH-4073). A rate limit
(a 429) is raised, as everywhere.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import DownloadError, MetaFileFormatError, NoInternetError, ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.station_ids import wigos_id_or_none
from wetterdienst.util.network import _without_url_secrets, download_file, drop_cached_file
from wetterdienst.util.response_warnings import warn_response

if TYPE_CHECKING:
    from collections.abc import Collection

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: The search of OSCAR/Surface's REST API, which `territoryName` (an ISO 3166-1 alpha-3 code) narrows to a country. A
#: parameter it does not know is ignored and answers the whole register (63,000 stations, 40 MB, two pages), so only
#: `territoryName` is ever sent
OSCAR_SEARCH_URL = "https://oscar.wmo.int/surface/rest/api/search/station"

#: How long a country's register is kept in the cache: the WIGOS ids of a station change a few times a year, and
#: Germany's is 1.9 MB. The longest expiry that is bounded
OSCAR_EXPIRY = CacheExpiry.ONE_WEEK

#: How long the process keeps a register it read, on top of the week of the cache: a register is at most eight days old
OSCAR_MEMORY = 86400.0

#: How long a failure to read a register is remembered by the process, so that a register that is down is asked for once
#: and not by every request, and asked for again soon after it is up
OSCAR_FAILURE_MEMORY = 300.0

#: The code of the warning an answer carries when the register could not be read and the stations have no `wigos_id`
#: from it
WIGOS_IDS_UNAVAILABLE = "wigos-ids-unavailable"


@dataclass(frozen=True)
class NationalWigosScheme:
    """Say how a provider's station id is the local part of the WIGOS ids of a country's own issuer."""

    #: the country as OSCAR's ISO 3166-1 alpha-3 code (``DEU``): the register is asked for by it
    territory: str
    #: the issuer of the country's own ids, as the number (``276``)
    issuer: int
    #: the issue numbers whose local part is the provider's id (``{0}``): an id of another issue number is of another
    #: scheme of the issuer, however it looks
    issue_numbers: frozenset[int]
    #: the provider that is told in a message (``dwd/observation``)
    provider: str
    #: whether the provider writes its ids with the leading zeros the register does not (``00073`` for ``73``)
    strip_zeros: bool = False


class OscarRegisterError(MetaFileFormatError):
    """The answer of OSCAR is not the register of a country: it is another page, or it is cut short."""

    def __init__(self, territory: str, reason: str) -> None:
        """Say what is wrong with the answer, naming the address that was asked."""
        self.territory = territory
        self.reason = reason
        super().__init__(
            f"WMO OSCAR's register of {territory} at {oscar_url(territory)} is not the one that was read: {reason}"
        )

    def __reduce__(self) -> tuple:
        """Rebuild from the parts, so that the error is copied and pickled as it is and not worded twice."""
        return type(self), (self.territory, self.reason)


def oscar_url(territory: str) -> str:
    """Give the address of the register of a country."""
    return f"{OSCAR_SEARCH_URL}?territoryName={territory}"


def parse_wigos_ids(content: bytes, territory: str) -> list[str]:
    """Read the WIGOS ids that the register of a country holds, in the notation of ``wigos_id``, each once.

    Raises:
        DownloadError: the answer is no JSON (an HTML waiting page, a text), which is what a server says in a 200 when
            it is down.
        OscarRegisterError: the answer is JSON that is no complete register of the country: not an object with its
            ``stationSearchResults``, more than one page, fewer stations than ``totalCount`` says, or no WIGOS id.

    """
    try:
        payload = json.loads(content)
    except ValueError as error:
        raise DownloadError(
            _without_url_secrets(oscar_url(territory)), "the answer is not JSON (a waiting or error page?)"
        ) from error
    stations = payload.get("stationSearchResults") if isinstance(payload, dict) else None
    if not isinstance(stations, list):
        raise OscarRegisterError(territory, "it is no object with `stationSearchResults`")
    pages = payload.get("pageCount")
    if pages != 1:
        raise OscarRegisterError(territory, f"it has {pages!r} pages and only the first is asked for, `pageCount` 1")
    total = payload.get("totalCount")
    if total != len(stations):
        raise OscarRegisterError(territory, f"it says {total!r} stations (`totalCount`) and lists {len(stations)}")
    ids: dict[str, None] = {}
    for station in stations:
        listed = station.get("wigosStationIdentifiers") if isinstance(station, dict) else None
        for item in listed if isinstance(listed, list) else ():
            wigos_id = wigos_id_or_none(item.get("wigosStationIdentifier") if isinstance(item, dict) else None)
            if wigos_id is not None:
                ids[wigos_id] = None
    if not ids:
        raise OscarRegisterError(territory, f"none of its {len(stations)} stations has a WIGOS id")
    return list(ids)


def _read(territory: str, settings: Settings) -> list[str]:
    """Download and parse the register of a country, see `read_register`."""
    url = oscar_url(territory)
    file = download_file(
        url=url,
        cache_dir=settings.cache_dir,
        ttl=OSCAR_EXPIRY,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    file.raise_if_exception()
    if isinstance(file.content, Exception):
        # narrows the type; `raise_if_exception` has raised for any failed download
        raise DownloadError(_without_url_secrets(url), "no body")
    try:
        return parse_wigos_ids(file.content.read(), territory)
    except (DownloadError, OscarRegisterError):
        # a 200 that is no register is held by the cache for the whole week: drop it, so that the next call asks again
        drop_cached_file(
            url,
            settings.cache_dir,
            OSCAR_EXPIRY,
            settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        raise


#: what the process remembers, by `_memory_key`: when it is forgotten (`_clock`), and the ids or the error of the read
_MEMORY: dict[tuple, tuple[float, list[str] | Exception]] = {}
_MEMORY_LOCK = threading.Lock()
#: the clock the memory goes by, which a test replaces
_clock = time.monotonic


def _canonical(value: object) -> object:
    """Write a settings value so that equal ones are equal as keys: mappings by sorted key, sequences as tuples."""
    if isinstance(value, dict):
        return tuple(sorted(((str(key), _canonical(item)) for key, item in value.items()), key=lambda pair: pair[0]))
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_canonical(item) for item in value)
    return repr(value)


def _memory_key(territory: str, settings: Settings) -> tuple:
    """Name what a copy of the register depends on: the country, the cache it comes from and how it was asked for."""
    return (
        territory,
        str(settings.cache_dir),
        settings.cache_disable,
        settings.use_certifi,
        _canonical(settings.fsspec_client_kwargs or {}),
    )


def _fresh(error: Exception) -> Exception:
    """Copy an error without the frames it was raised through, so that what is remembered holds none of a request."""
    fresh = copy.copy(error).with_traceback(None)
    fresh.__cause__ = error.__cause__
    return fresh


def _remember(key: tuple, kept_for: float, what: list[str] | Exception) -> None:
    """Keep what was read for `kept_for` seconds, and drop what has run out, so that the memory does not grow."""
    now = _clock()
    with _MEMORY_LOCK:
        for old in [old for old, (until, _) in _MEMORY.items() if until <= now]:
            del _MEMORY[old]
        _MEMORY[key] = (now + kept_for, what)


def forget_registers() -> None:
    """Forget what the process remembers of the registers and of its failures (a test's, a process that must reread)."""
    with _MEMORY_LOCK:
        _MEMORY.clear()


def read_register(territory: str, settings: Settings) -> list[str]:
    """Read the register of a country and give the WIGOS ids it holds (all issuers, all statuses), each once.

    Raises:
        NoInternetError: no connection could be made. DownloadError: the server answered badly, or with a page that is
            no JSON. ProviderRateLimitError: a 429, which is not remembered. OscarRegisterError: what came is no
            complete register. The last two are of a copy that is dropped from the cache, so that the next call asks
            again rather than read the same page for a week; a failure is remembered by the process for five minutes.

    """
    key = _memory_key(territory, settings)
    with _MEMORY_LOCK:
        remembered = _MEMORY.get(key)
        if remembered is not None and _clock() < remembered[0]:
            if isinstance(remembered[1], Exception):
                raise _fresh(remembered[1])
            return remembered[1]
    try:
        ids = _read(territory, settings)
    except ProviderRateLimitError:
        raise
    except (NoInternetError, DownloadError, OscarRegisterError) as error:
        _remember(key, OSCAR_FAILURE_MEMORY, _fresh(error))
        raise
    _remember(key, OSCAR_MEMORY, ids)
    return ids


def wigos_ids_of_scheme(ids: Collection[str], scheme: NationalWigosScheme) -> pl.DataFrame:
    """Pick, of a register's WIGOS ids, the ones that the scheme's providers' station ids are the local part of.

    Returns one row for each local part that has exactly one such id: ``key`` (the local part) and ``wigos_id``. One
    that has more is left out and told in the log, by the rule of the module docstring.
    """
    found: dict[str, set[str]] = {}
    for wigos_id in ids:
        _series, issuer, number, local = wigos_id.split("-", 3)
        if int(issuer) == scheme.issuer and int(number) in scheme.issue_numbers:
            found.setdefault(local, set()).add(wigos_id)
    ambiguous = {local: sorted(item) for local, item in found.items() if len(item) > 1}
    if ambiguous:
        listed = "; ".join(" and ".join(item) for item in list(ambiguous.values())[:10])
        log.warning(
            f"WMO OSCAR holds more than one WIGOS id for the station id of {len(ambiguous)} {scheme.provider} "
            f"stations, which have no wigos_id from it: {listed}{', ...' if len(ambiguous) > 10 else ''}"
        )
    unique = {local: next(iter(item)) for local, item in found.items() if len(item) == 1}
    return pl.DataFrame(
        {"key": list(unique), "wigos_id": list(unique.values())}, schema={"key": pl.String, "wigos_id": pl.String}
    )


def with_oscar_wigos_id(stations: pl.LazyFrame, settings: Settings, scheme: NationalWigosScheme) -> pl.LazyFrame:
    """Give the stations a ``wigos_id`` where OSCAR holds a WIGOS id whose local part is their ``station_id``.

    A station that is none keeps what it has: the ``wigos_id`` its provider's list published, or null. One the provider
    published is never replaced.

    When the register cannot be read (`OscarRegisterError`, a `DownloadError`, a `NoInternetError`) the stations still
    come back, with the column as it would be without OSCAR, and the warning `wigos-ids-unavailable` in the log and in
    the answer; OSCAR is a host other than the provider's, so a name that does not resolve or a proxy that does not let
    it through must not fail every request for the stations. A rate limit (`ProviderRateLimitError`) is raised.
    """
    names = stations.collect_schema().names()
    if "station_id" not in names:
        # no station, no column: the core gives the empty list its columns
        return stations
    keep = pl.col("wigos_id") if "wigos_id" in names else pl.lit(None, dtype=pl.String)
    try:
        ids = read_register(scheme.territory, settings)
    except ProviderRateLimitError:
        raise
    except (NoInternetError, DownloadError, OscarRegisterError) as error:
        warn_response(
            log,
            WIGOS_IDS_UNAVAILABLE,
            f"WMO OSCAR could not be read, so the stations of {scheme.provider} have no wigos_id from it: {error}",
        )
        return stations.with_columns(keep.alias("wigos_id"))
    known = wigos_ids_of_scheme(ids, scheme).lazy().rename({"wigos_id": "oscar_wigos_id"})
    key = pl.col("station_id").str.strip_chars_start("0") if scheme.strip_zeros else pl.col("station_id")
    return (
        stations.with_columns(key.alias("_oscar_key"))
        .join(known, left_on="_oscar_key", right_on="key", how="left", maintain_order="left")
        .with_columns(pl.coalesce(keep, pl.col("oscar_wigos_id")).alias("wigos_id"))
        .drop("_oscar_key", "oscar_wigos_id")
    )
