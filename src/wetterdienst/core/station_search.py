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

A network that fails is a warning that names it and the others answer; if every network that was asked fails the
search raises an `UpstreamError` that names them, since an outage is no answer of no station. One that needs
credentials the settings do not hold is a warning too, and is not counted as asked. A 429 is never swallowed: the
search raises the `ProviderRateLimitError`.

The hits of a network whose list names stations that have no data (`noaa/ghcn`, read without its inventory) are
checked one by one for the file of the station, and a station with none is no row. A check that cannot be made keeps
the row and is a warning.
"""

from __future__ import annotations

import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, ParamSpec, TypeVar, cast

import polars as pl

from wetterdienst.api import Wetterdienst
from wetterdienst.exceptions import (
    ConfigurationError,
    CredentialMissingError,
    ProviderRateLimitError,
    RequestError,
    UpstreamError,
)
from wetterdienst.model.station_ids import (
    search_icao_id,
    search_wigos_id,
    search_wmo_id,
    wmo_id_of_wigos_expr,
)
from wetterdienst.util.response_warnings import (
    ResponseWarning,
    begin_response,
    record_response_warning,
    recorded_warnings,
    warn_response,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from concurrent.futures import Future

    from wetterdienst.model.metadata import StationIdColumn, StationIdList
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

#: how many networks are asked at once: more than the cores of a laptop help with, and fewer than the connections a
#: host that serves all of them (DWD answers five of the networks) takes kindly
MAX_WORKERS = 8

#: the code of the warning that names a network whose list could not be read, which the others answer without
NETWORK_FAILED = "network-failed"
#: the code of the warning that names a network that needs credentials the settings do not hold
NETWORK_NOT_CONFIGURED = "network-not-configured"
#: the code of the warning that names the stations of a hit list whose data file could not be checked, which stay in the
#: answer
STATION_FILE_UNCHECKED = "station-file-unchecked"

#: how many hits of one network are checked for a data file: a handful for an id (a WMO number sits on up to four
#: stations of `noaa/ghcn`), and an ICAO code or a list of ids no more than a few more. Hits beyond it stay unchecked
MAX_FILE_CHECKS = 8

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
    #: the resolution and the dataset of the list the network declares for the search; null for a network that could not
    #: be imported, whose declaration is not known
    resolution: str | None
    dataset: str | None
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


def _declared_lists() -> tuple[list[tuple[str, str, StationIdList]], list[SearchedNetwork]]:
    """Give the networks that declare a list for the search (provider, network, the list) and those that cannot be read.

    A network whose module cannot be imported on this server (a dependency is missing) is a failed entry of `searched`:
    its declaration is not known, and it is neither asked nor left out unsaid.
    """
    declared: list[tuple[str, str, StationIdList]] = []
    failed: list[SearchedNetwork] = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            try:
                metadata = Wetterdienst.resolve(provider, network).metadata
            except ImportError as e:
                # the text of an `ImportError` is the library's and may name a path of the server: the log has all of it
                log.warning(f"{provider}/{network} cannot be imported: {e}")
                missing = f": the module '{e.name}' is missing" if isinstance(e, ModuleNotFoundError) and e.name else ""
                failed.append(
                    SearchedNetwork(
                        provider,
                        network,
                        None,
                        None,
                        (),
                        "failed",
                        None,
                        f"it cannot be imported on this server{missing}",
                    )
                )
                continue
            if metadata.station_id_list is not None:
                declared.append((provider, network, metadata.station_id_list))
    return declared, failed


def _reason_of(error: Exception, name: str) -> str:
    """Give why a network failed, for the answer: what an upstream or configuration failure says, else nothing of it.

    A failure of the provider or of the server's configuration has a message that was written to be told. Anything else
    is a defect of ours, whose text may hold what the caller has no business with: it is logged with its traceback, as
    the REST API logs the 500 it answers, and the answer says that it happened.
    """
    if isinstance(error, UpstreamError | ConfigurationError):
        return _one_line(error)
    log.error(f"Failed to read the station list of {name}.", exc_info=error)
    return "an unexpected error occurred; the server's log has it"


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


def _submit(pool: ThreadPoolExecutor, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Future[T]:
    """Start `fn` in the pool, in a copy of the context of the caller."""
    context = contextvars.copy_context()
    return pool.submit(lambda: context.run(fn, *args, **kwargs))


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
                _submit(pool, _read_network, provider, network, lister, settings),
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
                outcomes.append(
                    _Outcome(SearchedNetwork(*where, "failed", None, _reason_of(e, f"{provider}/{network}")))
                )
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


def _equivalents(wmo_ids: list[str], wigos_ids: list[str], wmo_of_icao: list[str]) -> dict[str, list[str]]:
    """Give the ids searched besides the ones asked for, because they are equivalent to them.

    The WMO numbers of the WIGOS identifiers of WMO's issuer that were given and of the stations an ICAO code found,
    and the WIGOS identifiers of WMO's issuer of every WMO number searched. The first two kinds come from the request
    alone, so that what a search says it also looked for does not depend on which list answered.
    """
    wmo_of_wigos = [number for wigos_id in wigos_ids if (number := _wmo_of_issuer_wigos(wigos_id)) is not None]
    wmo_equivalent = _unique([*wmo_of_wigos, *wmo_of_icao])
    wigos_equivalent = _unique(f"{WMO_ISSUER_PREFIX}{number}" for number in _unique([*wmo_ids, *wmo_equivalent]))
    return {
        "wmo_id": [number for number in wmo_equivalent if number not in wmo_ids],
        "wigos_id": [identifier for identifier in wigos_equivalent if identifier not in wigos_ids],
    }


#: the ways a station matches, strongest first: its own id before an equivalent one, and the WMO number before the WIGOS
#: identifier before the ICAO code. The index is the rank a row is told by
_MATCHES = (
    ("wmo_id", "direct"),
    ("wigos_id", "direct"),
    ("icao_id", "direct"),
    ("wmo_id", "equivalent"),
    ("wigos_id", "equivalent"),
)


def _match(
    stations: pl.DataFrame,
    wmo_ids: list[str],
    wigos_ids: list[str],
    icao_ids: list[str],
) -> tuple[pl.DataFrame, dict[str, list[str]]]:
    """Select the stations that carry one of the ids, or an id equivalent to it, and say which matched and how.

    A station a list repeats is one row, told by its strongest match. Returns the matching rows with `matched_by` and
    `match`, and the ids searched by an equivalence.
    """
    # the ICAO codes are searched first, for the WMO numbers of the stations they find
    by_icao = pl.col("icao_id").is_in(icao_ids)
    wmo_of_icao = (
        stations.filter(by_icao)
        .select(_wmo_number_of(pl.col("wmo_id"), pl.col("wigos_id")).alias("wmo"))
        .drop_nulls()
        .get_column("wmo")
        .to_list()
    )
    also = _equivalents(wmo_ids, wigos_ids, wmo_of_icao)
    conditions = [
        pl.col("wmo_id").is_in(wmo_ids),
        pl.col("wigos_id").is_in(wigos_ids),
        by_icao,
        pl.col("wmo_id").is_in(also["wmo_id"]),
        pl.col("wigos_id").is_in(also["wigos_id"]),
    ]
    rank = pl.coalesce(
        *(pl.when(condition).then(pl.lit(index, pl.Int8)) for index, condition in enumerate(conditions)),
    )
    found = (
        stations.with_columns(rank.alias("_rank"))
        .filter(pl.col("_rank").is_not_null())
        # the strongest match of a station first, so that the one row kept of a station a list repeats is that one
        .sort("provider", "network", "station_id", "_rank", maintain_order=True)
        .unique(subset=["provider", "network", "station_id"], keep="first", maintain_order=True)
        .with_columns(
            pl.col("_rank")
            .replace_strict(dict(enumerate(by for by, _ in _MATCHES)), return_dtype=pl.String)
            .alias("matched_by"),
            pl.col("_rank")
            .replace_strict(dict(enumerate(how for _, how in _MATCHES)), return_dtype=pl.String)
            .alias("match"),
        )
        .select(COLUMNS)
    )
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
    one for another id, takes about a second. The hits of `noaa/ghcn`, whose list is read without the inventory and so
    names stations that have no data, are checked for the data file of the station (one download each, held in the
    cache for a read of the values), and a station with none is no row.

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
        UpstreamError: every network that was asked failed, so that the search knows nothing: it names them. A network
            that fails while others answer is a warning of the answer.
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

    declared, import_failures = _declared_lists()
    outcomes = _read_networks(declared, settings)
    # in the order of the registry, the networks that could not be imported where they stand
    order = {
        f"{provider}/{network}": index
        for index, (provider, network) in enumerate(
            (provider, network) for provider, networks in Wetterdienst.registry.items() for network in networks
        )
    }
    outcomes = sorted(
        [*outcomes, *(_Outcome(entry) for entry in import_failures)],
        key=lambda outcome: order[f"{outcome.network.provider}/{outcome.network.network}"],
    )

    warnings: list[ResponseWarning] = []
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

    _raise_if_nothing_was_read(outcomes)

    stations = pl.concat(frames, how="vertical_relaxed") if frames else _empty(with_match=False)
    if stations.is_empty():
        found, also = _empty(with_match=True), _equivalents(wmo_ids, wigos_ids, [])
    else:
        found, also = _match(stations, wmo_ids, wigos_ids, icao_ids)
        found, unchecked = _without_stations_that_have_no_file(found, settings)
        for warning in unchecked:
            log.warning(warning["message"])
            record_response_warning(warning["code"], warning["message"], stations=warning.get("stations"))
        warnings.extend(unchecked)
    return StationIdSearchResult(
        request={"wmo_id": wmo_ids, "wigos_id": wigos_ids, "icao_id": icao_ids},
        also_searched=also,
        df=found,
        searched=[outcome.network for outcome in outcomes],
        warnings=warnings,
    )


def _raise_if_nothing_was_read(outcomes: list[_Outcome]) -> None:
    """Raise the `UpstreamError` of a search in which every network that was asked failed.

    An answer of no station, with a warning for each network, would read as there being no such station: an outage is
    no data. A network that is merely not configured was never asked and does not count; with none asked at all (no key
    is held and nothing else declares a list) there is nothing that failed.
    """
    asked = [outcome.network for outcome in outcomes if outcome.network.status != "not-configured"]
    if asked and all(network.status == "failed" for network in asked):
        named = "; ".join(f"{network.provider}/{network.network} ({network.message})" for network in asked)
        msg = f"None of the {len(asked)} networks that were asked could be read, so nothing is known of the id: {named}"
        raise UpstreamError(msg)


_Hit = tuple[str, str, str]


def _file_checkers(found: pl.DataFrame, settings: Settings) -> dict[tuple[str, str], Any]:
    """Build the request of each network among the hits whose provider checks the data file of a station."""
    requests: dict[tuple[str, str], Any] = {}
    lists = found.select("provider", "network", "resolution", "dataset").unique(maintain_order=True)
    for provider, network, resolution, dataset in lists.iter_rows():
        api = Wetterdienst.resolve(provider, network)
        if api._checks_station_files:  # noqa: SLF001
            requests[(provider, network)] = api(parameters=[(resolution, dataset)], settings=settings)
    return requests


def _bounded_by_network(hits: list[_Hit]) -> tuple[list[_Hit], dict[str, list[str]]]:
    """Keep the first `MAX_FILE_CHECKS` hits of each network, and name the stations of the rest by network."""
    seen: dict[tuple[str, str], int] = {}
    kept: list[_Hit] = []
    beyond: dict[str, list[str]] = {}
    for provider, network, station_id in hits:
        count = seen.get((provider, network), 0)
        seen[(provider, network)] = count + 1
        if count < MAX_FILE_CHECKS:
            kept.append((provider, network, station_id))
        else:
            beyond.setdefault(f"{provider}/{network}", []).append(station_id)
    return kept, beyond


def _check_files(
    requests: dict[tuple[str, str], Any], hits: list[_Hit]
) -> tuple[set[_Hit], dict[str, list[tuple[str, str]]]]:
    """Ask each hit's network whether the station has its file: the hits that have none, and the checks that failed.

    A 429 is raised; any other failure is kept with its reason, by network, for the warning.
    """
    gone: set[_Hit] = set()
    failed: dict[str, list[tuple[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="station-file-check") as pool:
        futures = [
            (hit, _submit(pool, requests[(hit[0], hit[1])]._station_file_exists, hit[2]))  # noqa: SLF001
            for hit in hits
        ]
        for hit, future in futures:
            provider, network, station_id = hit
            try:
                exists = future.result()
            except ProviderRateLimitError:
                for _, other in futures:
                    other.cancel()
                raise
            except Exception as e:  # noqa: BLE001
                reason = _reason_of(e, f"the data file of {station_id} of {provider}/{network}")
                failed.setdefault(f"{provider}/{network}", []).append((station_id, reason))
                continue
            if not exists:
                log.info(f"{provider}/{network} {station_id} has no data file and is left out of the hits.")
                gone.add(hit)
    return gone, failed


def _without_stations_that_have_no_file(
    found: pl.DataFrame, settings: Settings
) -> tuple[pl.DataFrame, list[ResponseWarning]]:
    """Drop the hits of a network that has no data for the station, where the network checks it (`noaa/ghcn`).

    A list that names stations without data (GHCN's, read without the inventory) is checked for the hits only: one
    request each for the file of the station, at most `MAX_FILE_CHECKS` for a network. A check that cannot be made keeps
    the row and is a `station-file-unchecked` warning that names the station, as is a hit beyond the bound. A 429 is
    raised.
    """
    requests = _file_checkers(found, settings)
    if not requests:
        return found, []
    hits = [
        hit for hit in found.select("provider", "network", "station_id").iter_rows() if (hit[0], hit[1]) in requests
    ]
    checked, beyond = _bounded_by_network(hits)
    gone, failed = _check_files(requests, checked)

    warnings: list[ResponseWarning] = [
        {
            "code": STATION_FILE_UNCHECKED,
            "message": f"{name}: only the first {MAX_FILE_CHECKS} hits are checked for a data file; "
            f"{len(stations)} were not, and stay in the answer.",
            "stations": stations,
        }
        for name, stations in beyond.items()
    ]
    warnings += [
        {
            "code": STATION_FILE_UNCHECKED,
            "message": f"{name}: the data file of {', '.join(station for station, _ in entries)} could not be "
            f"checked ({entries[0][1]}); the station stays in the answer, and may have no data.",
            "stations": [station for station, _ in entries],
        }
        for name, entries in failed.items()
    ]
    if gone:
        keys = [
            {"provider": provider, "network": network, "station_id": station_id}
            for provider, network, station_id in gone
        ]
        found = found.filter(~pl.struct("provider", "network", "station_id").is_in(keys))
    return found, warnings
