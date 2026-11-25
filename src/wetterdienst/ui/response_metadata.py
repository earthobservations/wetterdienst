# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `metadata` block of every JSON answer of the data routes, shared by REST, the command line and MCP (GH-2561).

A stations, values, interpolation, summary or history answer says where its data comes from and may be
used (the licence and the credit line of the provider), what was asked as the library resolved it (the
parameters that `daily/kl` meant, the periods, the window, the stations selected), when it was
retrieved, what it is missing but did not fail on (`warnings`), how much of it there is (`counts`), the
reference system of its positions (`crs`), and the versions of the API and of this shape. The block is
always there; `with_metadata` only adds the heavier parts, the unit, the `aggregation` and the
`timestamp_position` of every parameter and what `quality_flags` holds.

Outside JSON the same information goes into headers (`response_headers`): a CSV or an image has no place
in its body for it. This module imports no web framework, so the command line can use it without the
`restapi` extra.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from wetterdienst.metadata.parameter_table import Aggregation  # noqa: TC001, needed at runtime by pydantic
from wetterdienst.model.metadata import TimestampPosition, is_quality_flag
from wetterdienst.model.processing_note import STATION_IDS_NOTE, processing_note
from wetterdienst.model.quality_legend import QualityKind, quality_legend
from wetterdienst.model.result import (
    StationsFilter,
    StationsResult,
    _License,
    _metadata_of,
    _Producer,
    _Provider,
    describe_producer,
    describe_provider,
)
from wetterdienst.model.unit import UnitConverter
from wetterdienst.util.datetime import format_timestamp
from wetterdienst.util.response_warnings import (
    ANSWER_TRUNCATED,
    FORECAST_FROM_NOW,
    ResponseWarning,
    recorded_warnings,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from wetterdienst.core.station_search import StationIdSearchResult
    from wetterdienst.metadata.period import Period
    from wetterdienst.model.group_statistics import StatisticsResult
    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.model.result import _ProviderTerms, _ValuesResult
    from wetterdienst.options import Options
    from wetterdienst.ui.core import (
        HistoryRequest,
        InterpolationRequest,
        IssuesRequest,
        StationsRequest,
        SummaryRequest,
        ValuesRequest,
    )

#: the version of the REST API contract, reported by `/api/version` and by every answer as `api_version`
API_VERSION = "1"
#: the version of the shape of the `metadata` block, which a stored answer is told apart from a later one by
SCHEMA_VERSION = "1"

#: the most stations whose `station_id` the block lists: an answer of more says how many there are instead
#: (`ids` null, `count` set), so that a listing of a whole network does not carry its ids a second time
MAX_LISTED_STATION_IDS = 100

_QUALITY_FLAGS_DESCRIPTION = (
    "One nullable string per reading, comma-separated. The first token without a `kind:` prefix is the "
    "source's own quality flag as the source writes it. Every further token is `kind:code`: the kinds a "
    "provider publishes beside it (for instance `measurement:T`), `zone:` where the source's timestamps were "
    "shifted to UTC, `suspect:<check>` where a plausibility check in the mode `soft` found the value implausible "
    "and left it (the suspect level of `source` is flagged in either mode), and, always last, `raw:` where a value "
    "was a missing-value marker or a number no sensor can "
    "have produced and is returned as null, with the text the source wrote in its place; a number a check in the "
    "mode `hard` rejected (the bounds you set included) has `rejected:<check>` before it."
)


class StationsSelected(BaseModel):
    """The stations an answer is about."""

    model_config = ConfigDict(extra="forbid")

    filter: StationsFilter = Field(description="How the stations were selected from the network's.")
    count: int = Field(description="How many stations the answer has.")
    ids: list[str] | None = Field(
        description="The `station_id` of every station in the answer, in its order, for an answer of "
        f"{MAX_LISTED_STATION_IDS} stations or fewer; null for one of more, which `count` gives.",
    )


class ResolvedRequest(BaseModel):
    """What was asked for, as the library resolved it rather than as it was typed."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    network: str
    parameters: list[str] = Field(
        description="Every parameter read, as `resolution/dataset/parameter`: `daily/kl` is the list it means.",
    )
    periods: list[str] = Field(description="The periods read, oldest first.")
    start: str | None = Field(description="Start of the window applied, in UTC; null for no window.")
    end: str | None = Field(description="End of the window applied, in UTC; null for no window.")
    stations: StationsSelected | None = Field(
        description="The stations the answer is about; null for one that is not about stations, the warnings of "
        "`dwd/alerts` and the cells of `dwd/storm_cells`.",
    )


class Counts(BaseModel):
    """How much the answer holds."""

    model_config = ConfigDict(extra="forbid")

    stations: int = Field(description="The stations in the answer; 0 for one that is not about stations.")
    rows: int = Field(
        description="The rows of `values` (one per timestamp in the wide shape, one per value in the long "
        "one), the stations listed, the histories, the issues, the alerts or the storm cells.",
    )


class Crs(BaseModel):
    """The reference system of the positions in the answer."""

    model_config = ConfigDict(extra="forbid")

    code: Literal["EPSG:4326"] = "EPSG:4326"
    name: Literal["WGS 84"] = "WGS 84"
    axis_order: Literal["longitude, latitude"] = Field(
        default="longitude, latitude", description="The order of a GeoJSON position, which RFC 7946 fixes."
    )
    elevation: Literal["metres above mean sea level"] = "metres above mean sea level"


class ParameterInfo(BaseModel):
    """One parameter of the answer, with the unit its values are in."""

    model_config = ConfigDict(extra="forbid")

    resolution: str
    dataset: str
    name: str = Field(description="The canonical name.")
    name_original: str = Field(description="The name the source gives it.")
    description: str | None
    quantity: str = Field(description="What is measured, which `unit_targets` chooses a unit for.")
    unit: str = Field(
        description="The symbol of the unit of the values: the target of the quantity where `convert_units` is "
        "on, else the unit the source publishes.",
    )
    aggregation: Aggregation | None = Field(
        description="What the value is relative to its interval: the name's, else the provider's declaration "
        "where the source states it (`mean`, `max`, `sum`, ...; `instant` is a single reading). Null: not "
        "stated, which is not a reading.",
    )
    timestamp_position: TimestampPosition | None = Field(
        description="Where the timestamp sits in the row's interval: `instant` (when the value was observed), "
        "`start`, `end` or `middle` of it. Null: not stated.",
    )


class SourceQualityFlag(BaseModel):
    """A quality flag the source publishes beside the values of a dataset."""

    model_config = ConfigDict(extra="forbid")

    resolution: str
    dataset: str
    name_original: str
    description: str | None


class Quality(BaseModel):
    """What the `quality_flags` of a reading holds."""

    model_config = ConfigDict(extra="forbid")

    column: Literal["quality_flags"] = "quality_flags"
    format: str = _QUALITY_FLAGS_DESCRIPTION
    source_flags: list[SourceQualityFlag] = Field(
        description="The quality flags the datasets read publish, which the first token of `quality_flags` is "
        "the code of.",
    )
    legend: list[QualityKind] = Field(
        description="What the tokens of `quality_flags` mean for this network, in the order of the column: the "
        "source's own flag, its further kinds, and `raw` last. Empty for a network whose readings carry no flag.",
    )


class CatalogueCounts(BaseModel):
    """How much a catalogue of the library holds."""

    model_config = ConfigDict(extra="forbid")

    providers: int
    networks: int
    parameters: int = Field(
        description="How many different parameters (canonical names) the networks listed declare, counted once "
        "however many networks, resolutions and datasets carry one.",
    )


class CatalogueMetadata(BaseModel):
    """The `metadata` block of an answer that is about the library and no provider's data (`/api/providers`).

    The members the block of every answer has that need no provider or request: the versions, the time, the producer
    and the warnings. The terms of each provider are in the answer, one for every provider it lists.
    """

    model_config = ConfigDict(extra="forbid")

    api_version: str
    schema_version: str
    retrieved_at: str = Field(description="When this answer was made, in UTC.")
    producer: _Producer
    counts: CatalogueCounts
    warnings: list[ResponseWarning] = Field(
        description="What the answer is missing but did not fail on, each with a stable `code` and a `message`: a "
        "network that cannot be imported on this server is left out and told here.",
    )


class StationIdsSearched(BaseModel):
    """A network the search for a WMO, WIGOS or ICAO id asked, the list it read and what came of it."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    network: str
    resolution: str | None = Field(
        description="The resolution of the station list read: another one may list other stations. Null for a network "
        "that cannot be imported on this server, whose declaration is not known.",
    )
    dataset: str | None = Field(
        description="The dataset of the station list read: another one may list other stations; null as `resolution`.",
    )
    ids: list[str] = Field(description="The id columns the list fills: `wmo_id`, `wigos_id` and `icao_id`.")
    status: Literal["searched", "failed", "not-configured", "rate-limited"] = Field(
        description="`searched` for a list that was read; `failed` for one that could not be, which a warning names; "
        "`not-configured` for a network that needs credentials the server does not hold, which a warning names; "
        "`rate-limited` for a network whose provider answered 429, which a warning names with the wait it asks for.",
    )
    stations_with_ids: int | None = Field(
        description="How many stations of the list carry at least one id; null for a list that was not read.",
    )
    message: str | None = Field(description="Why a list that was not read was not; null for one that was.")


class StationIdsAlsoSearched(BaseModel):
    """The ids searched besides the ones given, because they are equivalent to them."""

    model_config = ConfigDict(extra="forbid")

    wmo_id: list[str] = Field(
        description="WMO numbers: those of a WIGOS identifier of WMO's issuer (`0-20000-0-<number>`) that was given, "
        "and of the stations an ICAO code found.",
    )
    wigos_id: list[str] = Field(
        description="WIGOS identifiers of WMO's issuer (`0-20000-0-<number>`) of every WMO number searched.",
    )


class StationIdsRequestInfo(BaseModel):
    """What was asked: the ids given, each in the notation of its column, and the ones searched besides."""

    model_config = ConfigDict(extra="forbid")

    wmo_id: list[str]
    wigos_id: list[str]
    icao_id: list[str]
    also_searched: StationIdsAlsoSearched


class StationIdsProvider(BaseModel):
    """A provider that has a station in the answer: who published its list, and under which terms."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="The name a request calls it by, `dwd`.")
    name_local: str
    name_english: str
    country: str
    copyright: str
    url: str
    license: _License | None = Field(
        description="The terms the provider publishes its data under; null where it states none.",
    )
    attribution: str | None = Field(description="The credit line to cite; null where the provider states none.")


class StationIdsCounts(BaseModel):
    """How much a search for an id found, and how many of the networks answered."""

    model_config = ConfigDict(extra="forbid")

    stations: int = Field(description="How many stations (rows) the answer has.")
    providers: int = Field(description="How many providers have a station in it.")
    networks_searched: int = Field(description="How many networks were asked.")
    networks_answered: int = Field(description="How many of them read their list.")


class StationIdsMetadata(BaseModel):
    """The `metadata` block of the answer of a search for a WMO, WIGOS or ICAO id (`/api/station-ids`).

    The answer holds the stations of several providers, so the block has no one `provider`: `providers` gives the
    licence and the credit line of each provider that has a station in the answer, and `searched` tells every network
    that was asked, with its list. The versions, the time, the producer, the processing note and the warnings are the
    members every block has.
    """

    model_config = ConfigDict(extra="forbid")

    api_version: str
    schema_version: str
    retrieved_at: str = Field(description="When this answer was made, in UTC.")
    producer: _Producer
    processing_note: str = Field(
        description="What wetterdienst did to the data: the stations were taken from each provider's station list, "
        "reshaped into a uniform table, and selected by the id, and by the ids equivalent to it.",
    )
    request: StationIdsRequestInfo
    counts: StationIdsCounts
    searched: list[StationIdsSearched] = Field(
        description="Every network the search asked, each with the list it read and what came of it.",
    )
    providers: list[StationIdsProvider] = Field(
        description="The providers that have a station in the answer, with their licence and credit line.",
    )
    warnings: list[ResponseWarning] = Field(
        description="What the answer is missing but did not fail on, each with a stable `code` and a `message`: a "
        "network whose list could not be read (`network-failed`), that needs credentials the server does not "
        "hold (`network-not-configured`) or whose provider answered 429 (`network-rate-limited`) is left out of the "
        "search and told here.",
    )


class SearchOptions(BaseModel):
    """The row options of the request as they were read, null for one that was not given."""

    model_config = ConfigDict(extra="forbid")

    filter: str | None = Field(description="The conditions, as read: `value<=-20,month=12|1|2`.")
    sort: str | None = Field(description="The sort keys, as read: `-value`, `month,day`.")
    first: int | None = Field(description="How many rows of each group were kept, the ties of the last included.")
    by: str | None = Field(
        description="The groups `first` counted in as read: `station_id` or `none` or a list; null for the default, "
        "the station.",
    )
    max_rows: int | None = Field(description="The most rows the answer was cut to, as the last step; null for no cap.")


class SearchWindow(BaseModel):
    """The window the request read, in UTC."""

    model_config = ConfigDict(extra="forbid")

    start: str | None = Field(description="Start of the window; null where the request has none.")
    end: str | None = Field(description="End of the window; null where the request has none.")


class SearchTotals(BaseModel):
    """What the whole answer searched, summed over its series."""

    model_config = ConfigDict(extra="forbid")

    stations_read: int | None = Field(
        description="How many stations the walk read, those with no value in the window included; null for a result "
        "that did not walk (`selected_rows`). `stations_with_values` of them have a series.",
    )
    stations_with_values: int = Field(description="How many stations have at least one value searched.")
    series: int = Field(description="How many stations and parameters were searched (also those that are not listed).")
    searched: int = Field(description="The values searched in all.")
    expected: int | None = Field(
        description="The values the request covers, in all (see `series[].expected`); null where one series has none "
        "to give.",
    )
    gaps: int | None = Field(
        description="The values the series lack inside their own span, in all; null where one series has none to give.",
    )
    matched: int = Field(
        description="The rows the options chose of the values searched, before `max_rows` cut them: the rows of the "
        "frame, so in the wide shape a row counts once, not once for each parameter.",
    )
    returned: int = Field(
        description="The rows of the answer, as `counts.rows` has them: `matched`, or fewer where `max_rows` cut the "
        "answer.",
    )


class SearchedSeries(BaseModel):
    """What was searched of one parameter of one station, from when to when, and what of it is in the answer."""

    model_config = ConfigDict(extra="forbid")

    station_id: str
    name: str | None = Field(description="The name of the station, null where the provider has none.")
    resolution: str
    dataset: str
    parameter: str = Field(description="The name the answer's rows have.")
    first: str | None = Field(
        description="The timestamp of the first value searched, in UTC; null where none. The series is searched from "
        "here, whatever the station's record or the window say.",
    )
    last: str | None = Field(description="The timestamp of the last value searched, in UTC; null where none.")
    searched: int = Field(
        description="The values searched: readings with a value, after the plausibility rules and the conversion of "
        "units, within the window.",
    )
    expected: int | None = Field(
        description="The values the request covers, in the steps of the resolution (calendar months and years for the "
        "monthly and annual): with a `timestamp` window from its start to its end or to the last complete reading, "
        "whichever is earlier, so that a window that begins before `first`, a series that ended before the window "
        "does and a year that is not over are incomplete; without one from `first` to `last`. `expected` minus "
        "`searched` is what is missing. Null where the resolution has no fixed step, for a forecast, and where the "
        "series is coarser than its resolution (a value every 12 hours in an hourly dataset: almost none of its steps "
        "is as short as the resolution's).",
    )
    gaps: int | None = Field(
        description="The values the series lacks between `first` and `last`, whatever the window says: null where the "
        "resolution has no fixed step, for a forecast, where the series is coarser than its resolution, and for a "
        "series with no value (its `expected` is then the window, all of it missing).",
    )
    matched: int = Field(
        description="The rows the options chose from this station and parameter (in the wide shape the rows of its "
        "station and resolution, which hold every parameter).",
    )
    returned: int = Field(
        description="The rows of the answer from this station and parameter: `matched`, or fewer where `max_rows` "
        "cut the answer, which keeps its first rows over all stations and parameters.",
    )


class Search(BaseModel):
    """What the row options looked at, so that a reader knows whether the search was complete.

    The options are `filter`, `sort`, `first`, `by` and `max_rows`; given where the request has one of them. Counted
    before the options choose: per station and parameter from when
    to when (`first`, `last`) it was searched, how many `searched` values that is, of the `expected`, the `matched` rows
    the options chose and the `returned` rows that are in the answer (`max_rows` may return fewer than matched). The
    `warnings` of the block say what else was left out (a file skipped, a source that fell back to another, rows cut by
    `max_rows` as `rows-capped`, an answer cut to fit a tool); an empty answer reports as well.
    """

    model_config = ConfigDict(extra="forbid")

    options: SearchOptions
    window: SearchWindow = Field(
        description="The window the request read: a provider that needs one names it here, and where there is none "
        "everything the provider holds for the stations was searched.",
    )
    series: list[SearchedSeries] = Field(
        description="One entry per station and parameter, at most 100; `totals.series` counts them all. A series is "
        "searched from its `first` to its `last` value, which need not be the period of the station or the window.",
    )
    series_omitted: int = Field(description="How many series `totals` counts that `series` does not list.")
    totals: SearchTotals


class StatisticsOptions(BaseModel):
    """The options of a `statistics` request as they were read, with their defaults."""

    model_config = ConfigDict(extra="forbid")

    aggregate: list[str] = Field(description="What was computed per group, in the order asked.")
    filter: str | None = Field(description="The conditions, as read: `value<0,month=12|1|2`.")
    by: list[str] = Field(description="The columns the groups are made of besides the series, in calendar order.")
    per: str = Field(description="Over what `first` counted: `station` or `none`.")
    having: str | None = Field(description="The conditions on the results, as read.")
    sort: str | None = Field(description="The sort keys, as read.")
    first: int | None = Field(description="How many groups were kept, exactly, in the `sort` order.")
    year_start: int = Field(description="The month a `year` began: 1 is the calendar year.")
    max_missing: int = Field(description="How many values a group could lack and still get a `mean` and a `sum`.")
    max_rows: int | None = Field(description="The most groups the answer was cut to, as the last step.")


class StatisticsTotals(BaseModel):
    """What the whole answer searched and made, summed over its series."""

    model_config = ConfigDict(extra="forbid")

    stations_read: int | None = Field(
        description="How many stations the walk read, those with no value in the window included; null for a result "
        "that did not walk. `stations_with_values` of them have a series.",
    )
    stations_with_values: int = Field(description="How many stations have at least one value searched.")
    series: int = Field(description="How many stations and parameters were searched (also those that are not listed).")
    searched: int = Field(description="The values searched in all, before any condition of `filter`.")
    expected: int | None = Field(
        description="The values the request covers, in all (see `series[].expected`); null where one series has none "
        "to give.",
    )
    gaps: int | None = Field(
        description="The values the series lack inside their own span, in all; null where one series has none to give.",
    )
    groups: int = Field(
        description="All the groups of the series: those that are rows and those that are not (`groups_not_listed`).",
    )
    groups_not_listed: int = Field(
        description="The groups wholly before the first or after the last value of their series that have none: "
        "counted, no rows. A hole inside the record is a row.",
    )
    groups_incomplete: int = Field(description="The rows that lack more values than `max_missing` allows.")
    groups_matched: int = Field(description="The rows left after `having`, before `sort`, `first` and `max_rows`.")
    groups_returned: int = Field(description="The groups of the answer, as `counts.rows` has them.")


class StatisticsSearch(BaseModel):
    """What `statistics` looked at: the options as read, the window and the totals."""

    model_config = ConfigDict(extra="forbid")

    options: StatisticsOptions
    window: SearchWindow = Field(
        description="The window the request read; where there is none every value of the stations was searched.",
    )
    totals: StatisticsTotals


class ResponseMetadata(BaseModel):
    """The `metadata` block of an answer."""

    model_config = ConfigDict(extra="forbid")

    api_version: str
    schema_version: str
    retrieved_at: str = Field(description="When this answer was made, in UTC.")
    data_updated_at: str | None = Field(
        description="When the source says the data of this answer was last updated, in UTC: the newest such date "
        "over what the answer was read from (a file without a date adds none), as the source states it, and "
        "not the time the answer was made (`retrieved_at`). Null where the source states none or the library does not "
        "read it for the network, as for a list of stations and a streamed answer (NDJSON, CSV), whose head goes out "
        "before the newest date is known. It is the date the source reported when the answer was made, with the copy "
        "of the listing or file it was read from: it may lag a file refreshed since by up to the time the listing is "
        "cached.",
    )
    provider: _Provider = Field(
        description="Who published the data, under which licence (`license`, null where the provider states "
        "none) and with which credit line: `attribution` is the credit line to cite, `copyright` the rights holder's "
        "notice, shown for information.",
    )
    producer: _Producer
    processing_note: str = Field(
        description="What wetterdienst did to the data: it was reshaped into a uniform table and its units "
        "converted where they differ. The answers of `interpolate` and `summarize` add that the values were selected "
        "or calculated from the provider's readings, those of `storm_cells` that the "
        "direction of a cell is calculated from its forecast track, and those of `kostra` that the values are DWD's "
        "statistics of the grid cell of the point. The same "
        "text for every provider and licence, so that a licence that asks for changes to be indicated has them said; "
        "no legal advice.",
    )
    request: ResolvedRequest
    counts: Counts
    crs: Crs
    warnings: list[ResponseWarning] = Field(
        description="What the answer is missing but did not fail on, each with a stable `code` and a `message`.",
    )
    search: Search | None = Field(
        default=None,
        description="What `filter`, `sort`, `first`, `by` and `max_rows` searched, per station and parameter: present "
        "with one of them, also where no row matched. A streamed answer that chooses its rows station by station "
        "(a `filter` alone) has it in the `end` line of NDJSON and not in the first, which goes out before the "
        "search is done; one that chooses before it begins (`sort`, `first`) has it in the first line. A CSV has the "
        "totals of `searched`, `expected` and `matched` in headers where the rows were chosen before it began.",
    )
    parameters: list[ParameterInfo] | None = Field(default=None, description="With `with_metadata` only.")
    quality: Quality | None = Field(default=None, description="With `with_metadata` only.")


class StatisticsMetadata(ResponseMetadata):
    """The `metadata` block of the answer of `statistics`: that of `values`, with the search of the groups."""

    search: StatisticsSearch | None = Field(
        default=None,
        description="What the options looked at and made: the options as read (with their defaults), the window, and "
        "the totals of the values searched and the groups made, found and returned. The series themselves, with "
        "what was searched of each and the statistics over their groups, are the `series` of the answer.",
    )


# the parts that only `with_metadata` asks for
_HEAVY = {"parameters", "quality"}


def _unit_symbol(parameter: ParameterModel, options: Options, converter: UnitConverter) -> str:
    """Give the symbol the values of a parameter are in: the target unit, or the source's where nothing is converted."""
    if options.convert_units:
        return converter.targets[parameter.unit_type].symbol
    return converter.get_unit(parameter.unit, parameter.unit_type).symbol


def _retrieved_at() -> str:
    """Write the time an answer is made at."""
    return format_timestamp(dt.datetime.now(dt.UTC))


def _unique(values: Any) -> list[str]:  # noqa: ANN401
    """Keep the first occurrence of each value, in order."""
    return list(dict.fromkeys(str(value) for value in values))


def response_metadata(
    result: StationsResult | _ValuesResult[Any, Any],
    request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest | HistoryRequest,
    *,
    heavy: bool | None = None,
    rows: int | None = None,
) -> ResponseMetadata:
    """Build the block of the answer to `request`, which `result` is the result of.

    `heavy` adds the units and the quality legend, and is what `with_metadata` of the request asks for
    by default. `rows` is given where the answer holds something other than the rows of the result's frame.
    """
    return result_metadata(
        result,
        provider=request.provider,
        network=request.network,
        heavy=request.with_metadata if heavy is None else heavy,
        rows=rows,
    )


def result_metadata(
    result: StationsResult | _ValuesResult[Any, Any],
    *,
    provider: str,
    network: str,
    heavy: bool,
    rows: int | None = None,
) -> ResponseMetadata:
    """Build the block of an answer made from `result` when the request does not name the provider and network.

    `response_metadata` is this for the requests that name them.
    """
    stations = result if isinstance(result, StationsResult) else result.stations
    frame = result.df if isinstance(result, StationsResult) else result.df_stations
    ids = _unique(frame.get_column("station_id")) if "station_id" in frame.columns else []
    options = stations.options
    parameters = stations.parameters
    block = ResponseMetadata(
        api_version=API_VERSION,
        schema_version=SCHEMA_VERSION,
        retrieved_at=_retrieved_at(),
        **_metadata_of(
            stations,
            None if isinstance(result, StationsResult) else result.data_updated_at,
            derived=not isinstance(result, StationsResult) and result._derived,  # noqa: SLF001
        ),
        request=ResolvedRequest(
            provider=provider.lower(),
            network=network.lower(),
            parameters=_unique(f"{p.dataset.resolution.name}/{p.dataset.name}/{p.name}" for p in parameters),
            periods=[period.value for period in sorted(cast("Iterable[Period]", stations.request.periods or ()))],
            start=format_timestamp(stations.start) if stations.start else None,
            end=format_timestamp(stations.end) if stations.end else None,
            stations=StationsSelected(
                filter=stations._stations_filter.value,  # noqa: SLF001
                count=len(ids),
                ids=ids if len(ids) <= MAX_LISTED_STATION_IDS else None,
            ),
        ),
        counts=Counts(stations=len(ids), rows=result.df.height if rows is None else rows),
        crs=Crs(),
        warnings=recorded_warnings(),
    )
    searched = None if isinstance(result, StationsResult) else getattr(result, "search", None)
    if searched is not None:
        block.search = Search.model_validate(searched.to_dict())
    if heavy:
        converter = UnitConverter()
        converter.update_targets(options.unit_targets)
        block.parameters = [
            ParameterInfo(
                resolution=p.dataset.resolution.name,
                dataset=p.dataset.name,
                name=p.name,
                name_original=p.name_original,
                description=p.description,
                quantity=p.unit_type,
                unit=_unit_symbol(p, options, converter),
                aggregation=p.effective_aggregation,
                timestamp_position=p.effective_timestamp_position,
            )
            for p in parameters
        ]
        block.quality = Quality(
            legend=quality_legend(provider, network),
            source_flags=[
                SourceQualityFlag(
                    resolution=dataset.resolution.name,
                    dataset=dataset.name,
                    name_original=flag.name_original,
                    description=flag.description,
                )
                for dataset in {id(p.dataset): p.dataset for p in parameters}.values()
                for flag in dataset.parameters
                if is_quality_flag(flag)
            ],
        )
    return block


def statistics_metadata(result: StatisticsResult, *, provider: str, network: str) -> StatisticsMetadata:
    """Build the block of the answer of `statistics` (`/api/statistics`): that of `values` and the groups' search."""
    from wetterdienst.model.processing_note import STATISTICS_NOTE  # noqa: PLC0415

    stations = result.stations
    ids = _unique(series.station_id for series in result.series)
    # the stations searched, those whose series kept no group under `per=none` included
    searched = _unique(series.station_id for series in [*result.series, *result.left_out])
    search = StatisticsSearch.model_validate(result.search())
    return StatisticsMetadata(
        api_version=API_VERSION,
        schema_version=SCHEMA_VERSION,
        retrieved_at=_retrieved_at(),
        **describe_provider(stations.request.metadata, result.data_updated_at, calculated=STATISTICS_NOTE),
        request=ResolvedRequest(
            provider=provider.lower(),
            network=network.lower(),
            parameters=_unique(f"{p.dataset.resolution.name}/{p.dataset.name}/{p.name}" for p in stations.parameters),
            periods=[period.value for period in sorted(cast("Iterable[Period]", stations.request.periods or ()))],
            start=format_timestamp(stations.start) if stations.start else None,
            end=format_timestamp(stations.end) if stations.end else None,
            stations=StationsSelected(
                filter=stations._stations_filter.value,  # noqa: SLF001
                count=len(searched),
                ids=searched if len(searched) <= MAX_LISTED_STATION_IDS else None,
            ),
        ),
        counts=Counts(stations=len(ids), rows=search.totals.groups_returned),
        crs=Crs(),
        warnings=recorded_warnings(),
        search=search,
    )


def catalogue_metadata(*, providers: int, networks: int, parameters: int) -> CatalogueMetadata:
    """Build the block of an answer about the library's providers."""
    return CatalogueMetadata(
        api_version=API_VERSION,
        schema_version=SCHEMA_VERSION,
        retrieved_at=_retrieved_at(),
        producer=describe_producer(),
        counts=CatalogueCounts(providers=providers, networks=networks, parameters=parameters),
        warnings=recorded_warnings(),
    )


def _provider_terms(api: object) -> _ProviderTerms:
    """Give what a network says of its provider: its metadata model, or the `terms` of a standalone network."""
    metadata = getattr(api, "metadata", None)
    # a standalone network has no `metadata` and declares its `terms`, which the checker cannot know of `object`
    return metadata if metadata is not None else api.terms  # ty: ignore[unresolved-attribute]


def _block_without_result(
    api: object,
    request: ResolvedRequest,
    *,
    stations: int,
    rows: int,
    data_updated_at: dt.datetime | None = None,
    calculated: str | None = None,
    image_note: str | None = None,
) -> ResponseMetadata:
    """Build the block of an answer that is made from no stations result: the provider's terms and the request.

    The date the source states for the data is the caller's to give, for an answer that has one (the warnings), and
    so are the `calculated` sentence of numbers calculated from the readings and the `image_note` of an image drawn
    from them.
    """
    return ResponseMetadata(
        api_version=API_VERSION,
        schema_version=SCHEMA_VERSION,
        retrieved_at=_retrieved_at(),
        **describe_provider(_provider_terms(api), data_updated_at, calculated=calculated, image_note=image_note),
        request=request,
        counts=Counts(stations=stations, rows=rows),
        crs=Crs(),
        warnings=recorded_warnings(),
    )


def issues_metadata(api: object, request: IssuesRequest, issues: Sequence[str]) -> ResponseMetadata:
    """Build the block of a list of the issue times of one station's forecast runs (`/api/issues`)."""
    return _block_without_result(
        api,
        ResolvedRequest(
            provider=request.provider.lower(),
            network=request.network.lower(),
            parameters=[],
            periods=[],
            start=None,
            end=None,
            stations=StationsSelected(filter=StationsFilter.BY_STATION_ID.value, count=1, ids=[request.station]),
        ),
        stations=1,
        rows=len(issues),
    )


def alerts_metadata(api: object, alerts: int, data_updated_at: dt.datetime | None = None) -> ResponseMetadata:
    """Build the block of the warnings of `dwd/alerts` (`/api/alerts`), which are about no stations.

    `data_updated_at` is the newest `sent` of the warnings of the whole snapshot, those for a place or not
    (`DwdWeatherAlertResult.data_updated_at`).
    """
    return _block_without_result(
        api,
        ResolvedRequest(
            provider="dwd", network="alerts", parameters=[], periods=[], start=None, end=None, stations=None
        ),
        stations=0,
        rows=alerts,
        data_updated_at=data_updated_at,
    )


def storm_cells_metadata(api: object, cells: int, data_updated_at: dt.datetime | None = None) -> ResponseMetadata:
    """Build the block of the thunderstorm cells of `dwd/storm_cells` (`/api/storm-cells`), which are about no stations.

    `data_updated_at` is when DWD wrote the file of the scan (`DwdStormCellsResult.data_updated_at`). The processing
    note names what is calculated and what is DWD's forecast.
    """
    from wetterdienst.provider.dwd.storm_cells.metadata import STORM_CELLS_NOTE  # noqa: PLC0415

    return _block_without_result(
        api,
        ResolvedRequest(
            provider="dwd", network="storm_cells", parameters=[], periods=[], start=None, end=None, stations=None
        ),
        stations=0,
        rows=cells,
        data_updated_at=data_updated_at,
        calculated=STORM_CELLS_NOTE,
    )


def kostra_metadata(api: object, rows: int, data_updated_at: dt.datetime | None = None) -> ResponseMetadata:
    """Build the block of the KOSTRA-DWD-2020 statistics of a point (`/api/kostra`), which are about no stations.

    `rows` is the rows of the table (a duration and a return period each), `data_updated_at` when DWD wrote the newest
    file read (`DwdKostraResult.data_updated_at`). The processing note says that the values are DWD's statistics of
    a grid cell, not readings.
    """
    from wetterdienst.provider.dwd.kostra.metadata import KOSTRA_NOTE  # noqa: PLC0415

    return _block_without_result(
        api,
        ResolvedRequest(
            provider="dwd", network="kostra", parameters=[], periods=[], start=None, end=None, stations=None
        ),
        stations=0,
        rows=rows,
        data_updated_at=data_updated_at,
        calculated=KOSTRA_NOTE,
    )


def radar_metadata(frames: int, *, image: bool, data_updated_at: dt.datetime | None = None) -> ResponseMetadata:
    """Build the block of the frames of DWD's precipitation radar (`/api/radar/frames` and `/api/radar/frame`).

    The frames are about no stations: `frames` is the number of them in the list, one for an image. The note says what
    wetterdienst did to the composite, and `image` adds that the image is drawn from it.
    """
    from wetterdienst.provider.dwd.radar import DwdRadarValues  # noqa: PLC0415
    from wetterdienst.provider.dwd.radar.frames import RADAR_FRAMES_NOTE, RADAR_IMAGE_NOTE  # noqa: PLC0415

    return _block_without_result(
        DwdRadarValues,
        ResolvedRequest(
            provider="dwd", network="radar", parameters=["rv"], periods=[], start=None, end=None, stations=None
        ),
        stations=0,
        rows=frames,
        data_updated_at=data_updated_at,
        calculated=RADAR_FRAMES_NOTE,
        image_note=RADAR_IMAGE_NOTE if image else None,
    )


def station_ids_metadata(result: StationIdSearchResult) -> StationIdsMetadata:
    """Build the block of the search for a WMO, WIGOS or ICAO id (`/api/station-ids`), which holds several providers.

    Each provider with a station in the answer is named with its terms, and every network asked with the list it read.
    The warnings are the search's own (`result.warnings`: the networks it left out, and what the lists said of
    themselves) and those recorded for the response being served, which are the same where it began a record
    (`begin_response`), told once.
    """
    from wetterdienst.api import Wetterdienst  # noqa: PLC0415

    in_answer = list(dict.fromkeys(result.df.get_column("provider")))
    # a provider is what its networks say of it, and they agree (`tests/ui/test_providers.py` holds the registry to it)
    first_network = {name: next(iter(Wetterdienst.registry[name])) for name in in_answer}
    providers = []
    for name in in_answer:
        terms = Wetterdienst.resolve(name, first_network[name]).metadata
        providers.append(
            StationIdsProvider(
                provider=name,
                name_local=terms.name_local,
                name_english=terms.name_english,
                country=terms.country,
                copyright=terms.copyright,
                url=terms.url,
                license=cast("_License", terms.license.model_dump()) if terms.license else None,
                attribution=terms.attribution,
            )
        )
    searched = [
        StationIdsSearched(
            provider=network.provider,
            network=network.network,
            resolution=network.resolution,
            dataset=network.dataset,
            ids=list(network.ids),
            status=network.status,
            stations_with_ids=network.stations_with_ids,
            message=network.message,
        )
        for network in result.searched
    ]
    return StationIdsMetadata(
        api_version=API_VERSION,
        schema_version=SCHEMA_VERSION,
        retrieved_at=_retrieved_at(),
        producer=describe_producer(),
        processing_note=processing_note(calculated=STATION_IDS_NOTE),
        request=StationIdsRequestInfo(
            wmo_id=result.request["wmo_id"],
            wigos_id=result.request["wigos_id"],
            icao_id=result.request["icao_id"],
            also_searched=StationIdsAlsoSearched(
                wmo_id=result.also_searched["wmo_id"], wigos_id=result.also_searched["wigos_id"]
            ),
        ),
        counts=StationIdsCounts(
            stations=result.df.height,
            providers=len(providers),
            networks_searched=len(searched),
            networks_answered=sum(network.status == "searched" for network in searched),
        ),
        searched=searched,
        providers=providers,
        warnings=[*result.warnings, *(w for w in recorded_warnings() if w not in result.warnings)],
    )


def station_ids_headers(metadata: StationIdsMetadata) -> Mapping[str, str]:
    """Give the headers that say what the block of a search for an id says, for the CSV, which has no place for it."""
    headers = {
        "X-Wetterdienst-API-Version": metadata.api_version,
        "X-Wetterdienst-Schema-Version": metadata.schema_version,
        "X-Wetterdienst-Retrieved-At": metadata.retrieved_at,
        "X-Wetterdienst-Stations": str(metadata.counts.stations),
    }
    if metadata.providers:
        headers["X-Wetterdienst-Provider"] = _header_text(", ".join(p.name_english for p in metadata.providers))
        # as the headers of every other answer write them (the licence by its identifier or name, the credit line as the
        # provider states it), one entry for each provider in the order of `X-Wetterdienst-Provider`, an entry once
        licences = list(
            dict.fromkeys(_license_label(provider.license) for provider in metadata.providers if provider.license)
        )
        if licences:
            headers["X-Wetterdienst-License"] = _header_text(", ".join(licences))
            urls = dict.fromkeys(p.license["url"] for p in metadata.providers if p.license is not None)
            headers["Link"] = ", ".join(f'<{url}>; rel="license"' for url in urls)
        credits_ = list(dict.fromkeys(p.attribution for p in metadata.providers if p.attribution))
        if credits_:
            headers["X-Wetterdienst-Attribution"] = _header_text("; ".join(credits_))
    headers["X-Wetterdienst-Processing"] = _header_text(metadata.processing_note)
    if metadata.warnings:
        headers["X-Wetterdienst-Warnings"] = ", ".join(dict.fromkeys(w["code"] for w in metadata.warnings))
    # the note of a tool's answer that was cut (GH-4022): a CSV has no block to carry it
    if truncated := next((w["message"] for w in metadata.warnings if w["code"] == ANSWER_TRUNCATED), None):
        headers["X-Wetterdienst-Truncated"] = _header_text(truncated)
    return headers


def metadata_to_dict(metadata: ResponseMetadata) -> dict[str, Any]:
    """Write the block as the JSON of an answer has it: the heavy parts only where they were asked for."""
    exclude = {name for name in (*_HEAVY, "search") if getattr(metadata, name) is None}
    return metadata.model_dump(mode="json", exclude=exclude)


def _header_text(value: str) -> str:
    """Write a header value that may carry more than ASCII (an attribution) as percent-encoded UTF-8."""
    return quote(value, safe=" ,.:;/()-_@=+'!*&")


def response_headers(metadata: ResponseMetadata) -> Mapping[str, str]:
    """Give the headers that say the same as the block, for the formats that have no body to put it in.

    Text that may carry more than ASCII is percent-encoded UTF-8, which a client reads back with
    `urllib.parse.unquote`. `Link` points at the licence, as RFC 8288's `license` relation does.
    """
    provider = metadata.provider
    headers = {
        "X-Wetterdienst-API-Version": metadata.api_version,
        "X-Wetterdienst-Schema-Version": metadata.schema_version,
        "X-Wetterdienst-Retrieved-At": metadata.retrieved_at,
        "X-Wetterdienst-Provider": _header_text(provider["name_english"]),
        "X-Wetterdienst-Stations": str(metadata.counts.stations),
        "X-Wetterdienst-Rows": str(metadata.counts.rows),
    }
    if metadata.data_updated_at is not None:
        headers["X-Wetterdienst-Data-Updated-At"] = metadata.data_updated_at
    if metadata.search is not None:
        # a CSV has no block: what the row options searched goes into three headers, its series stay in JSON
        totals = metadata.search.totals
        headers["X-Wetterdienst-Values-Searched"] = str(totals.searched)
        if totals.expected is not None:
            headers["X-Wetterdienst-Values-Expected"] = str(totals.expected)
        if isinstance(totals, StatisticsTotals):
            headers["X-Wetterdienst-Groups-Matched"] = str(totals.groups_matched)
        else:
            headers["X-Wetterdienst-Rows-Matched"] = str(totals.matched)
    if (license_ := provider["license"]) is not None:
        headers["X-Wetterdienst-License"] = _header_text(_license_label(license_))
        headers["Link"] = f'<{license_["url"]}>; rel="license"'
    if provider["attribution"]:
        headers["X-Wetterdienst-Attribution"] = _header_text(provider["attribution"])
    headers["X-Wetterdienst-Processing"] = _header_text(metadata.processing_note)
    if metadata.warnings:
        headers["X-Wetterdienst-Warnings"] = ", ".join(dict.fromkeys(w["code"] for w in metadata.warnings))
    # the note of a tool's answer that was cut (GH-4022): a CSV has no block to carry it, and a client that reads
    # none of the body finds it here
    if truncated := next((w["message"] for w in metadata.warnings if w["code"] == ANSWER_TRUNCATED), None):
        headers["X-Wetterdienst-Truncated"] = _header_text(truncated)
    # the same for a forecast answer that starts at now (GH-4025)
    if started := next((w["message"] for w in metadata.warnings if w["code"] == FORECAST_FROM_NOW), None):
        headers["X-Wetterdienst-Forecast-From-Now"] = _header_text(started)
    return headers


def catalogue_headers(metadata: CatalogueMetadata) -> Mapping[str, str]:
    """Give the headers that say the same as the block of an answer about the library, for a client that reads none."""
    headers = {
        "X-Wetterdienst-API-Version": metadata.api_version,
        "X-Wetterdienst-Schema-Version": metadata.schema_version,
        "X-Wetterdienst-Retrieved-At": metadata.retrieved_at,
    }
    if metadata.warnings:
        headers["X-Wetterdienst-Warnings"] = ", ".join(dict.fromkeys(w["code"] for w in metadata.warnings))
    return headers


def _license_label(license_: _License) -> str:
    """Name a licence by its SPDX identifier where it has one, else by its name."""
    return license_["spdx_id"] or license_["name"]
