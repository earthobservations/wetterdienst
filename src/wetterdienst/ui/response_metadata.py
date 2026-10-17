# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `metadata` block of every JSON answer of the data routes, shared by REST, the command line and MCP (GH-2561).

A stations, values, interpolation, summary or history answer says where its data comes from and may be
used (the licence and the credit line of the provider), what was asked as the library resolved it (the
parameters that `daily/kl` meant, the periods, the window, the stations selected), when it was
retrieved, what it is missing but did not fail on (`warnings`), how much of it there is (`counts`), the
reference system of its positions (`crs`), and the versions of the API and of this shape. The block is
always there; `with_metadata` only adds the heavier parts, the unit of every parameter and what
`quality_flags` holds.

Outside JSON the same information goes into headers (`response_headers`): a CSV or an image has no place
in its body for it. This module imports no web framework, so the command line can use it without the
`restapi` extra.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from wetterdienst.metadata.period import Period
from wetterdienst.model.metadata import is_quality_flag
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
from wetterdienst.util.response_warnings import ResponseWarning, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.model.result import _ProviderTerms, _ValuesResult
    from wetterdienst.options import Options
    from wetterdienst.ui.core import (
        HistoryRequest,
        InterpolationRequest,
        IssuesRequest,
        StationsRequest,
        StripesData,
        StripesValuesRequest,
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
    "shifted to UTC, and, always last, `raw:` where a value was a missing-value marker or a number no sensor "
    "can have produced and is returned as null, with the text the source wrote in its place."
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
        "`dwd/alerts`.",
    )


class Counts(BaseModel):
    """How much the answer holds."""

    model_config = ConfigDict(extra="forbid")

    stations: int = Field(description="The stations in the answer; 0 for one that is not about stations.")
    rows: int = Field(
        description="The rows of `values` (one per timestamp in the wide shape, one per value in the long "
        "one), the stations listed, the histories, the issues or the alerts.",
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


class ResponseMetadata(BaseModel):
    """The `metadata` block of an answer."""

    model_config = ConfigDict(extra="forbid")

    api_version: str
    schema_version: str
    retrieved_at: str = Field(description="When this answer was made, in UTC.")
    provider: _Provider = Field(
        description="Who published the data, under which licence (`license`, null where the provider states "
        "none) and with which credit line (`attribution`).",
    )
    producer: _Producer
    request: ResolvedRequest
    counts: Counts
    crs: Crs
    warnings: list[ResponseWarning] = Field(
        description="What the answer is missing but did not fail on, each with a stable `code` and a `message`.",
    )
    parameters: list[ParameterInfo] | None = Field(default=None, description="With `with_metadata` only.")
    quality: Quality | None = Field(default=None, description="With `with_metadata` only.")


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

    The climate stripes are DWD's and their request says which stripes, not where from. `response_metadata` is this
    for the requests that name them.
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
        **_metadata_of(stations),
        request=ResolvedRequest(
            provider=provider.lower(),
            network=network.lower(),
            parameters=_unique(f"{p.dataset.resolution.name}/{p.dataset.name}/{p.name}" for p in parameters),
            periods=[period.value for period in sorted(cast("Iterable[Period]", stations.request.periods or ()))],
            start=format_timestamp(stations.start) if stations.start else None,
            end=format_timestamp(stations.end) if stations.end else None,
            stations=StationsSelected(
                filter=stations.stations_filter.value,
                count=len(ids),
                ids=ids if len(ids) <= MAX_LISTED_STATION_IDS else None,
            ),
        ),
        counts=Counts(stations=len(ids), rows=result.df.height if rows is None else rows),
        crs=Crs(),
        warnings=recorded_warnings(),
    )
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


def catalogue_metadata(*, providers: int, networks: int) -> CatalogueMetadata:
    """Build the block of an answer about the library's providers."""
    return CatalogueMetadata(
        api_version=API_VERSION,
        schema_version=SCHEMA_VERSION,
        retrieved_at=_retrieved_at(),
        producer=describe_producer(),
        counts=CatalogueCounts(providers=providers, networks=networks),
        warnings=recorded_warnings(),
    )


def _provider_terms(api: object) -> _ProviderTerms:
    """Give what a network says of its provider: its metadata model, or the `terms` of a standalone network."""
    metadata = getattr(api, "metadata", None)
    # a standalone network has no `metadata` and declares its `terms`, which the checker cannot know of `object`
    return metadata if metadata is not None else api.terms  # ty: ignore[unresolved-attribute]


def _block_without_result(api: object, request: ResolvedRequest, *, stations: int, rows: int) -> ResponseMetadata:
    """Build the block of an answer that is made from no stations result: the provider's terms and the request."""
    return ResponseMetadata(
        api_version=API_VERSION,
        schema_version=SCHEMA_VERSION,
        retrieved_at=_retrieved_at(),
        **describe_provider(_provider_terms(api)),
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


def stripes_metadata(data: StripesData, request: StripesValuesRequest) -> ResponseMetadata:
    """Build the block of the values of climate stripes (`/api/stripes/values`), which are DWD observation's."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    stripes = data.series
    return _block_without_result(
        DwdObservationRequest,
        ResolvedRequest(
            provider="dwd",
            network="observation",
            parameters=[f"{stripes.resolution}/{stripes.dataset}/{stripes.parameter}"],
            periods=[Period.HISTORICAL.value],
            start=None,
            end=None,
            stations=StationsSelected(
                filter=(StationsFilter.BY_STATION_ID if request.station else StationsFilter.BY_NAME).value,
                count=1,
                ids=[str(stripes.station["station_id"])],
            ),
        ),
        stations=1,
        rows=data.df.height,
    )


def alerts_metadata(api: object, alerts: int) -> ResponseMetadata:
    """Build the block of the warnings of `dwd/alerts` (`/api/alerts`), which are about no stations."""
    return _block_without_result(
        api,
        ResolvedRequest(
            provider="dwd", network="alerts", parameters=[], periods=[], start=None, end=None, stations=None
        ),
        stations=0,
        rows=alerts,
    )


def metadata_to_dict(metadata: ResponseMetadata) -> dict[str, Any]:
    """Write the block as the JSON of an answer has it: the heavy parts only where they were asked for."""
    exclude = {name for name in _HEAVY if getattr(metadata, name) is None}
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
    if (license_ := provider["license"]) is not None:
        headers["X-Wetterdienst-License"] = _header_text(_license_label(license_))
        headers["Link"] = f'<{license_["url"]}>; rel="license"'
    if provider["attribution"]:
        headers["X-Wetterdienst-Attribution"] = _header_text(provider["attribution"])
    if metadata.warnings:
        headers["X-Wetterdienst-Warnings"] = ", ".join(dict.fromkeys(w["code"] for w in metadata.warnings))
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
