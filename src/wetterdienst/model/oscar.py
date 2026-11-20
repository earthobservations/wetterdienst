# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The WIGOS ids of stations whose provider's id is the local part of one, read from WMO OSCAR/Surface (GH-4074).

A WIGOS station identifier is ``<series>-<issuer>-<issue number>-<local id>``. The issuer of a country's national
ids (``276`` for Germany, ``246`` for Finland, ``208`` for Denmark) lets the national weather service choose the local
part, and DWD, FMI and DMI chose their own station numbers: OSCAR/Surface, WMO's register of observing stations, has
``0-276-3-73`` for the DWD station ``00073`` (Aldersbach-Kramersepp), ``0-246-0-101520`` for the FMI station
``101520`` (Ahtari Myllymäki) and ``0-208-0-06126`` for the DMI station ``06126`` (Aarslev). None of the three
providers publishes a WIGOS id with its stations list, so the register is where the link is (read 2026-11-19: DWD 372
numeric ids of 374 national ones, FMI 288, DMI 170 of two territories).

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
  id is no more one of them than the other: ``wigos_id`` stays null and a warning in the log names them, once for
  each time the register is read, since which is the station's is not for the reader to guess (none at the time of
  reading);
- a scheme may name more than one territory, as OSCAR files the stations of Greenland under ``GRL`` and those of
  Denmark and the Faroe Islands under ``DNK``, both with the issuer 208 (DMI: ``0-208-0-04202`` is Pituffik, in
  ``GRL``). The registers are joined before the rule is applied, and one that cannot be read is the whole register
  that cannot: the stations of the other territory would be a list that is partly right;
- a ``wigos_id`` the provider's own list publishes stays, whatever the register says (`with_oscar_wigos_id`).

The register is read with ``GET https://oscar.wmo.int/surface/rest/api/search/station?territoryName=<ISO-3>``, one page
of JSON for a country (Germany 2,495 stations, 1.9 MB, about 3 s; no key). The answer is held to what it says of
itself: a country is one page (``pageCount`` 1) and as many stations as ``totalCount``, with a WIGOS id among them. A
page that is none of it, whatever the status (an HTML waiting page, a JSON error, a page cut short) is no register and
never an empty one: it raises (`OscarRegisterError`, a `DownloadError` for a page that is no JSON at all) and is dropped
from the cache, which holds a 200 for the whole week. The register is kept in the cache for a week, as the WIGOS ids of
a station change a few times a year, and in the process for a day; a failure to read it is remembered for five minutes
so that a register that is down is not asked for by every request, and a rate limit not at all. A host that drops
connections is waited for ten seconds, once (`OSCAR_TIMEOUT`, one attempt), and the threads that ask at the same
time share one read (`util/read_memory.py`).

The ids are an enrichment of the station list, not the list: when the register cannot be read the stations still come
back, with the column as it would be without OSCAR and the warning `wigos-ids-unavailable` in the log and in the
answer (`with_oscar_wigos_id`), as for `wmo_id` of ``dwd/observation`` (`wmo-ids-unavailable`, GH-4073). A rate limit
(a 429) is raised, as everywhere, worded as OSCAR's and not "the provider's" (the provider of the stations is not
the one that limits).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import DownloadError, MetaFileFormatError, NoInternetError, ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.station_ids import wigos_id_or_none
from wetterdienst.util.network import _without_url_secrets, download_file, drop_cached_file
from wetterdienst.util.read_memory import ReadMemory, settings_key
from wetterdienst.util.response_warnings import warn_response

if TYPE_CHECKING:
    from collections.abc import Collection

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: The search of OSCAR/Surface's REST API, which `territoryName` (an ISO 3166-1 alpha-3 code) narrows to a country. A
#: parameter it does not know is ignored and answers the whole register (63,000 stations, about 50 MB, two pages), so
#: only `territoryName` is ever sent
OSCAR_SEARCH_URL = "https://oscar.wmo.int/surface/rest/api/search/station"

#: How long a country's register is kept in the cache: the WIGOS ids of a station change a few times a year, and
#: Germany's is 1.9 MB. The longest expiry that is bounded
OSCAR_EXPIRY = CacheExpiry.ONE_WEEK

#: How long the process keeps a register it read, on top of the week of the cache: a register is at most eight days old
OSCAR_MEMORY = 86400.0

#: How long a failure to read a register is remembered by the process, so that a register that is down is asked for once
#: and not by every request, and asked for again soon after it is up
OSCAR_FAILURE_MEMORY = 300.0

#: How long the server is waited for in silence (connecting, and between two reads of the page) and how often it is
#: asked: a host that drops connections costs a request ten seconds once, and not the sixty of the client's default
#: timeout and its second attempt
OSCAR_TIMEOUT = 10

#: The code of the warning an answer carries when the register could not be read and the stations have no `wigos_id`
#: from it
WIGOS_IDS_UNAVAILABLE = "wigos-ids-unavailable"


@dataclass(frozen=True)
class NationalWigosScheme:
    """Say how a provider's station id is the local part of the WIGOS ids of a country's own issuer."""

    #: the territories as OSCAR's ISO 3166-1 alpha-3 codes (``("DEU",)``): the register is asked for by each
    territories: tuple[str, ...]
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
    # the client's default is 30 s of silence and a second attempt: a host that drops connections would stall a request
    # for a minute. The copy is cached and dropped with the arguments it was downloaded with
    client_kwargs = {**settings.fsspec_client_kwargs, "timeout": OSCAR_TIMEOUT}
    file = download_file(
        url=url,
        cache_dir=settings.cache_dir,
        ttl=OSCAR_EXPIRY,
        client_kwargs=client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
        attempts=1,
    )
    try:
        file.raise_if_exception()
    except ProviderRateLimitError as error:
        # the one that limits is OSCAR, not the provider of the stations that are being listed
        raise ProviderRateLimitError(
            _without_url_secrets(url),
            "WMO OSCAR, the register that the WIGOS ids of the stations come from, limits how fast this installation "
            "may ask; the stations can be listed again once the limit has reset",
            error.retry_after,
        ) from error
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
            client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        raise


#: the clock the memory goes by, which a test replaces
_clock = time.monotonic
#: the failures that are the register's: what a failure of the read of one is told by, and remembered
_FAILURES = (NoInternetError, DownloadError, OscarRegisterError)
#: what the process remembers of each country's register, and of its failures (`util/read_memory.py`): the clock is
#: looked up by name at each use, so that a test replaces `_clock`
_REGISTERS: ReadMemory[list[str]] = ReadMemory(
    kept_for=OSCAR_MEMORY,
    failure_kept_for=OSCAR_FAILURE_MEMORY,
    failures=_FAILURES,
    clock=lambda: _clock(),  # noqa: PLW0108
)
#: what the process remembers of the ids of each scheme, which are the registers of its territories joined and picked:
#: the join and the warning about an id that is listed twice are made once for each time they are read
_SCHEMES: ReadMemory[pl.DataFrame] = ReadMemory(
    kept_for=OSCAR_MEMORY,
    failure_kept_for=OSCAR_FAILURE_MEMORY,
    failures=_FAILURES,
    clock=lambda: _clock(),  # noqa: PLW0108
)


def forget_registers() -> None:
    """Forget what the process remembers of the registers and of its failures (a test's, a process that must reread)."""
    _REGISTERS.forget()
    _SCHEMES.forget()


def read_register(territory: str, settings: Settings) -> list[str]:
    """Read the register of a country and give the WIGOS ids it holds (all issuers, all statuses), each once.

    Raises:
        NoInternetError: no connection could be made. DownloadError: the server answered badly, or with a page that is
            no JSON. ProviderRateLimitError: a 429, which is not remembered. OscarRegisterError: what came is no
            complete register. The last two are of a copy that is dropped from the cache, so that the next call asks
            again rather than read the same page for a week; a failure is remembered by the process for five minutes.

    """
    return _REGISTERS.get((territory, *settings_key(settings)), lambda: _read(territory, settings))


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


def read_scheme_ids(scheme: NationalWigosScheme, settings: Settings) -> pl.DataFrame:
    """Read the registers of the territories of a scheme and give `wigos_ids_of_scheme` of them joined.

    One territory that cannot be read is the whole register that cannot: it raises what `read_register` raises, and
    no id is given from the registers that could be. The registers are joined before the rule is applied, so that an id
    that two of them list is one id, and two ids for one local part are found wherever they are listed. Kept by the
    process like a register, so that the warning of an id listed twice is made once for each time it is read.
    """

    def read() -> pl.DataFrame:
        ids: dict[str, None] = {}
        for territory in scheme.territories:
            ids.update(dict.fromkeys(read_register(territory, settings)))
        return wigos_ids_of_scheme(list(ids), scheme)

    return _SCHEMES.get((scheme, *settings_key(settings)), read)


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
        known = read_scheme_ids(scheme, settings)
    except ProviderRateLimitError:
        raise
    except _FAILURES as error:
        warn_response(
            log,
            WIGOS_IDS_UNAVAILABLE,
            f"WMO OSCAR could not be read, so the stations of {scheme.provider} have no wigos_id from it: {error}",
        )
        return stations.with_columns(keep.alias("wigos_id"))
    known_lazy = known.lazy().rename({"wigos_id": "oscar_wigos_id"})
    key = pl.col("station_id").str.strip_chars_start("0") if scheme.strip_zeros else pl.col("station_id")
    return (
        stations.with_columns(key.alias("_oscar_key"))
        .join(known_lazy, left_on="_oscar_key", right_on="key", how="left", maintain_order="left")
        .with_columns(pl.coalesce(keep, pl.col("oscar_wigos_id")).alias("wigos_id"))
        .drop("_oscar_key", "oscar_wigos_id")
    )
