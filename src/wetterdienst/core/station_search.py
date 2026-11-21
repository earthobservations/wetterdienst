# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Find one WMO number, WIGOS identifier or ICAO code at every provider that has it (GH-4075).

`find_stations_by_id` asks the networks whose metadata declares the id columns their station list fills
(`MetadataModel.station_id_list`) for the stations that carry an id, all at once, and answers one row per station.
Nothing is narrowed by region: a station can be listed by a provider far from where it stands, and only the lists say.

The ids are taken as equivalent where the standards say they are:

- the WIGOS identifier ``0-20000-0-N`` of WMO's own issuer and the WMO number ``N`` are one id, so a search for either
  finds a station that has the other;
- an ICAO code is searched, and so are the WMO numbers of the stations it finds: ``EDDH`` finds Hamburg's station at
  every provider whose list has the aerodrome's code, and then those that list its WMO number, which most do not
  write the ICAO code beside.

A row says which of its ids matched (``matched_by``) and whether the id searched for was the station's own
(``direct``) or came by an equivalence (``equivalent``). The lists are one for each network, named in the row
(``resolution`` and ``dataset``): another dataset of a network may list stations this one does not.

A network that fails is a warning that names it and the others answer. One that needs credentials the settings do not
hold is a warning too. A 429 is never swallowed: the search raises the `ProviderRateLimitError`.
"""

from __future__ import annotations

import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, cast

import polars as pl

from wetterdienst.api import Wetterdienst
from wetterdienst.exceptions import CredentialMissingError, ProviderRateLimitError, RequestError
from wetterdienst.model.station_ids import (
    search_icao_id,
    search_wigos_id,
    search_wmo_id,
    wmo_id_of_wigos_expr,
)
from wetterdienst.util.response_warnings import ResponseWarning, begin_response, recorded_warnings, warn_response

if TYPE_CHECKING:
    from collections.abc import Sequence
    from concurrent.futures import Future

    from wetterdienst.model.metadata import StationIdColumn, StationIdList
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: how many networks are asked at once: more than the cores of a laptop help with, and fewer than the connections a
#: host that serves all of them (DWD answers five of the networks) takes kindly
MAX_WORKERS = 8

#: the code of the warning that names a network whose list could not be read, which the others answer without
NETWORK_FAILED = "network-failed"
#: the code of the warning that names a network that needs credentials the settings do not hold
NETWORK_NOT_CONFIGURED = "network-not-configured"

WMO_ISSUER_PREFIX = "0-20000-0-"

#: the columns of the answer, in order
COLUMNS = [
    "provider",
    "network",
    "resolution",
    "dataset",
    "station_id",
    "name",
    "latitude",
    "longitude",
    "elevation",
    "wmo_id",
    "wigos_id",
    "icao_id",
    "matched_by",
    "match",
]

_ID_COLUMNS: tuple[StationIdColumn, ...] = ("wmo_id", "wigos_id", "icao_id")

Status = Literal["searched", "failed", "not-configured"]


@dataclass(frozen=True)
class SearchedNetwork:
    """A network the search asked, the list it read and what came of it."""

    provider: str
    network: str
    #: the resolution and the dataset of the list the network declares for the search
    resolution: str
    dataset: str
    #: the id columns that list fills
    ids: tuple[str, ...]
    status: Status
    #: the stations of the list that carry at least one id; null for a network that was not read
    stations_with_ids: int | None = None
    #: why a network that was not read was not
    message: str | None = None


@dataclass(frozen=True)
class StationIdSearchResult:
    """The answer of `find_stations_by_id`: the stations, and what was asked and how it went.

    `df` has one row per station and network (`COLUMNS`), sorted by provider, network and station id. `searched` names
    each network that was asked, whether it answered, failed or was not configured.
    """

    #: the ids as given, each in the notation of its column
    request: dict[str, list[str]]
    #: the ids searched besides, by an equivalence: the WMO numbers of a WIGOS identifier of WMO's issuer and of the
    #: stations an ICAO code found, and the WIGOS identifiers of WMO's issuer of every WMO number searched
    also_searched: dict[str, list[str]]
    df: pl.DataFrame
    searched: list[SearchedNetwork]
    warnings: list[ResponseWarning] = field(default_factory=list)

    def to_dict(self) -> list[dict[str, object]]:
        """Give the stations as a list of dictionaries, one for each row of `df`."""
        return self.df.to_dicts()


def _declared_lists() -> tuple[list[tuple[str, str, StationIdList]], list[ResponseWarning]]:
    """Give the networks that declare a list for the search (provider, network, the list) and the ones left out."""
    declared: list[tuple[str, str, StationIdList]] = []
    problems: list[ResponseWarning] = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            try:
                metadata = Wetterdienst.resolve(provider, network).metadata
            except ImportError as e:
                problems.append(
                    {
                        "code": NETWORK_FAILED,
                        "message": f"{provider}/{network} cannot be imported on this server and is not searched: {e}",
                    }
                )
                continue
            if metadata.station_id_list is not None:
                declared.append((provider, network, metadata.station_id_list))
    return declared, problems


def _one_line(error: BaseException) -> str:
    """Give an error as one line of text that names its kind, for the warning of a network that failed."""
    text = " ".join(str(error).split())
    return f"{type(error).__name__}: {text}" if text else type(error).__name__


#: what the read of one network gives: its stations that carry an id, and what it warned of
_Read = tuple[pl.DataFrame, list[ResponseWarning]]


def _read_network(
    provider: str,
    network: str,
    declared: StationIdList,
    settings: Settings,
) -> _Read:
    """Read the station list a network declares, down to the stations that carry an id, and what it warned of."""
    begin_response()
    api = Wetterdienst.resolve(provider, network)
    request = api(parameters=[(declared.resolution, declared.dataset)], settings=settings)
    stations = request._stations_for_id_search()  # noqa: SLF001
    # the id columns the list may not have (a network that declares one it does not fill is a defect the tests find)
    # are read as null rather than failing the search
    ids = [
        pl.col(column) if column in stations.columns else pl.lit(None, pl.String).alias(column)
        for column in _ID_COLUMNS
    ]
    frame = stations.select(
        pl.lit(provider).alias("provider"),
        pl.lit(network).alias("network"),
        pl.lit(declared.resolution).alias("resolution"),
        pl.lit(declared.dataset).alias("dataset"),
        "station_id",
        "name",
        "latitude",
        "longitude",
        "elevation",
        *ids,
    ).filter(pl.any_horizontal(pl.col(column).is_not_null() for column in _ID_COLUMNS))
    return frame, recorded_warnings()


@dataclass(frozen=True)
class _Outcome:
    """What the read of one network came to: its entry of `searched`, its stations, and what it warned of."""

    network: SearchedNetwork
    frame: pl.DataFrame | None = None
    warnings: list[ResponseWarning] = field(default_factory=list)


def _submit(
    pool: ThreadPoolExecutor, provider: str, network: str, declared: StationIdList, settings: Settings
) -> Future[_Read]:
    """Start the read of one network in the pool, in a copy of the context of the caller."""
    context = contextvars.copy_context()

    def read() -> _Read:
        return context.run(_read_network, provider, network, declared, settings)

    return pool.submit(read)


def _read_networks(declared: list[tuple[str, str, StationIdList]], settings: Settings) -> list[_Outcome]:
    """Read the declared list of every network at once, in the order they are declared.

    A network that fails, or needs credentials the settings do not hold, is an outcome that says so, and the others
    are read all the same. A 429 is the one failure that ends the search: it is raised (`ProviderRateLimitError`) once
    the reads that are running are done.
    """
    outcomes: list[_Outcome] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="station-id-search") as pool:
        # each network is read in a copy of this context, so that what it warns of is its own: the record of a
        # response is a context variable, which `_read_network` begins anew in the copy
        futures: list[tuple[str, str, StationIdList, Future[_Read]]] = [
            (
                provider,
                network,
                lister,
                _submit(pool, provider, network, lister, settings),
            )
            for provider, network, lister in declared
        ]
        for provider, network, lister, future in futures:
            where = (provider, network, lister.resolution, lister.dataset, lister.ids)
            try:
                frame, recorded = future.result()
            except ProviderRateLimitError:
                for *_, other in futures:
                    other.cancel()
                raise
            except CredentialMissingError as e:
                outcomes.append(_Outcome(SearchedNetwork(*where, "not-configured", None, str(e))))
            except Exception as e:  # noqa: BLE001
                outcomes.append(_Outcome(SearchedNetwork(*where, "failed", None, _one_line(e))))
            else:
                outcomes.append(_Outcome(SearchedNetwork(*where, "searched", frame.height), frame, recorded))
    return outcomes


def _empty(*, with_match: bool) -> pl.DataFrame:
    """Give the frame of no station: the columns of a list's stations, and with `with_match` those of the answer."""
    floats = {"latitude", "longitude", "elevation"}
    columns = COLUMNS if with_match else COLUMNS[:-2]
    return pl.DataFrame(schema={column: pl.Float64 if column in floats else pl.String for column in columns})


def _wmo_number_of(wmo_id: pl.Expr, wigos_id: pl.Expr) -> pl.Expr:
    """Give the WMO number of a station: its `wmo_id`, else the one its WIGOS identifier of WMO's issuer holds."""
    return pl.coalesce(wmo_id, wmo_id_of_wigos_expr(wigos_id))


def _match(
    stations: pl.DataFrame,
    wmo_ids: list[str],
    wigos_ids: list[str],
    icao_ids: list[str],
) -> tuple[pl.DataFrame, dict[str, list[str]]]:
    """Select the stations that carry one of the ids, or an id equivalent to it, and say which matched and how.

    Returns the matching rows with `matched_by` and `match`, and the ids searched by an equivalence.
    """
    wmo_of_wigos = [number for wigos_id in wigos_ids if (number := _wmo_of_issuer_wigos(wigos_id)) is not None]
    # the ICAO codes are searched first, for the WMO numbers of the stations they find
    by_icao = pl.col("icao_id").is_in(icao_ids)
    wmo_of_icao = (
        stations.filter(by_icao)
        .select(_wmo_number_of(pl.col("wmo_id"), pl.col("wigos_id")).alias("wmo"))
        .drop_nulls()
        .get_column("wmo")
        .to_list()
    )
    wmo_equivalent = _unique([*wmo_of_wigos, *wmo_of_icao])
    wmo_searched = _unique([*wmo_ids, *wmo_equivalent])
    wigos_equivalent = _unique(f"{WMO_ISSUER_PREFIX}{number}" for number in wmo_searched)

    direct_wmo = pl.col("wmo_id").is_in(wmo_ids)
    direct_wigos = pl.col("wigos_id").is_in(wigos_ids)
    equivalent_wmo = pl.col("wmo_id").is_in(wmo_equivalent)
    equivalent_wigos = pl.col("wigos_id").is_in(wigos_equivalent)
    found = (
        stations.with_columns(
            pl.when(direct_wmo)
            .then(pl.lit("wmo_id"))
            .when(direct_wigos)
            .then(pl.lit("wigos_id"))
            .when(by_icao)
            .then(pl.lit("icao_id"))
            .when(equivalent_wmo)
            .then(pl.lit("wmo_id"))
            .when(equivalent_wigos)
            .then(pl.lit("wigos_id"))
            .alias("matched_by"),
            pl.when(direct_wmo | direct_wigos | by_icao)
            .then(pl.lit("direct"))
            .when(equivalent_wmo | equivalent_wigos)
            .then(pl.lit("equivalent"))
            .alias("match"),
        )
        .filter(pl.col("matched_by").is_not_null())
        # one row for each station of a network, whatever the list repeats
        .unique(subset=["provider", "network", "station_id"], keep="first", maintain_order=True)
        .sort("provider", "network", "station_id")
        .select(COLUMNS)
    )
    also = {
        "wmo_id": [number for number in wmo_equivalent if number not in wmo_ids],
        "wigos_id": [identifier for identifier in wigos_equivalent if identifier not in wigos_ids],
    }
    return found, also


def _wmo_of_issuer_wigos(wigos_id: str) -> str | None:
    """Give the WMO number a WIGOS identifier of WMO's issuer (``0-20000-0-10381``) holds, else None."""
    if not wigos_id.startswith(WMO_ISSUER_PREFIX):
        return None
    local = wigos_id.removeprefix(WMO_ISSUER_PREFIX)
    return local if len(local) == 5 and local.isdigit() else None


def _unique(values: Sequence[str] | object) -> list[str]:
    """Give the values once each, in the order they come in."""
    return list(dict.fromkeys(cast("Sequence[str]", values)))


def find_stations_by_id(
    *,
    wmo_id: str | int | Sequence[str | int] | None = None,
    wigos_id: str | Sequence[str] | None = None,
    icao_id: str | Sequence[str] | None = None,
    settings: Settings | None = None,
) -> StationIdSearchResult:
    """Find the stations that carry a WMO number, WIGOS identifier or ICAO code, at every provider that lists them.

    Asks every network that declares the id columns its station list fills (`MetadataModel.station_id_list`), all at
    once and whatever the region, and answers one row for each station that has one of the ids searched for, or an
    equivalent one. A WMO number sits on one station of most providers and on up to four of `noaa/ghcn`, so the
    answer is a list, and a station that two providers list is a row of each.

    The list of a network is the one it declares, named in each row by `resolution` and `dataset`: the other datasets
    of the network may list stations it does not. A cold search downloads the lists, about 30 MB, in about 9 s on a
    good connection and longer on a slow one; the cache of the library holds each list, so the same search again, or
    one for another id, takes about a second.

    Args:
        wmo_id: One WMO number or several, as text or as numbers. One to five digits are read as the number with its
            leading zeros: ``1001`` is ``01001``.
        wigos_id: One WIGOS station identifier or several, ``<series>-<issuer>-<issue number>-<local id>``. One of WMO's
            own issuer, ``0-20000-0-10381``, is the WMO number ``10381`` as well.
        icao_id: One ICAO code or several, in any case. The WMO numbers of the stations it finds are searched too.
        settings: The settings of the host, which the networks read their cache directory, network client and
            credentials from; the process-wide ones where left out.

    Returns:
        StationIdSearchResult: The stations (`df`, with `matched_by` and `match`), the networks that were asked and
            the warnings.

    Raises:
        ValueError: no id is given, or one is not in the notation of its kind.
        TypeError: an id is neither a text nor a number.
        ProviderRateLimitError: a provider refused for asking too often (a 429), which is never swallowed.

    """
    if wmo_id is None and wigos_id is None and icao_id is None:
        msg = "give at least one of wmo_id, wigos_id and icao_id to search for"
        raise RequestError(msg)
    wmo_ids = search_wmo_id(wmo_id) if wmo_id is not None else []
    wigos_ids = search_wigos_id(wigos_id) if wigos_id is not None else []
    icao_ids = search_icao_id(icao_id) if icao_id is not None else []

    if settings is None:
        from wetterdienst.settings import Settings  # noqa: PLC0415

        settings = Settings()

    declared, warnings = _declared_lists()
    for warning in warnings:
        log.warning(warning["message"])
    outcomes = _read_networks(declared, settings)

    frames: list[pl.DataFrame] = []
    for outcome in outcomes:
        network = outcome.network
        name = f"{network.provider}/{network.network}"
        if network.status == "not-configured":
            message = f"{name} needs credentials the settings do not hold, so it is not searched: {network.message}"
            warnings.append({"code": NETWORK_NOT_CONFIGURED, "message": message})
            warn_response(log, NETWORK_NOT_CONFIGURED, message)
        elif network.status == "failed":
            message = f"{name} could not be read and is not searched: {network.message}"
            warnings.append({"code": NETWORK_FAILED, "message": message})
            warn_response(log, NETWORK_FAILED, message)
        if outcome.frame is not None:
            frames.append(outcome.frame)
        warnings.extend(w for w in outcome.warnings if w not in warnings)

    stations = pl.concat(frames, how="vertical_relaxed") if frames else _empty(with_match=False)
    if stations.is_empty():
        found, also = _empty(with_match=True), {"wmo_id": [], "wigos_id": []}
    else:
        found, also = _match(stations, wmo_ids, wigos_ids, icao_ids)
    return StationIdSearchResult(
        request={"wmo_id": wmo_ids, "wigos_id": wigos_ids, "icao_id": icao_ids},
        also_searched=also,
        df=found,
        searched=[outcome.network for outcome in outcomes],
        warnings=warnings,
    )
