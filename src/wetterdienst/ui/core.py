# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core UI utilities for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Annotated, Any, Literal, LiteralString, cast

import polars as pl
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError

# pydantic refuses typing.TypedDict as a response model on Python below 3.12, and GlossaryEntry
# is one; model/result.py imports it from here for the same reason
from typing_extensions import TypedDict

from wetterdienst.exceptions import (
    ApiNotFoundError,
    ConfigurationError,
    DateRequiredError,
    InvalidEnumerationError,
    InvalidTimeIntervalError,
    NoInternetError,
    NoParametersFoundError,
    NotEnoughDataError,
    NotFoundError,
    RequestError,
    StartDateEndDateError,
    StationNotFoundError,
    UpstreamError,
)
from wetterdienst.metadata.aliases import PARAMETER_ALIASES, use_alias
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.unit_type import UnitType  # noqa: TC001, needed at runtime by FastAPI
from wetterdienst.model.metadata import parse_parameters, whole_datasets_kept
from wetterdienst.model.plausibility import CHECKS, Mode
from wetterdienst.model.request import (
    DEFAULT_NAME_RANK,
    DEFAULT_NAME_RANK_LISTING,
    TimeseriesRequest,
    limit_to_window,
    require_window,
)
from wetterdienst.options import Options, SkipThreshold, StationWindowEndBuffer, options_from_mapping
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.util.datetime import format_timestamp, parse_date_window
from wetterdienst.util.extras import import_optional
from wetterdienst.util.logging import get_one_line_logger
from wetterdienst.util.ui import read_list

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable
    from types import ModuleType

    import plotly.graph_objs as go

    from wetterdienst.api import StandaloneRequest
    from wetterdienst.model.result import (
        InterpolatedValuesResult,
        StationsResult,
        SummarizedValuesResult,
        ValuesResult,
    )
    from wetterdienst.settings import Settings

log = get_one_line_logger(__name__)

# Field type aliases with descriptions, shared across the request models below. The descriptions
# surface in the REST API's OpenAPI schema and, via it, in the MCP tool parameters, so a single
# edit here documents both surfaces. Optional fields fold "| None" into the alias so the description
# is attached to the field itself (pydantic drops it from a bare "Alias | None" union).
_ProviderField = Annotated[
    str,
    Field(description="Data provider/organisation, e.g. 'dwd'. List valid provider/network combinations via coverage."),
]
_NetworkField = Annotated[
    str,
    Field(description="Data network of the provider, e.g. 'observation'. List valid combinations via coverage."),
]
_ParametersField = Annotated[
    list[str],
    Field(
        description="Parameters as 'resolution/dataset' (e.g. 'daily/kl') or "
        "'resolution/dataset/parameter' (e.g. 'daily/climate_summary/temperature_air_mean_2m'); "
        "multiple allowed, comma-separated.",
    ),
]
_PeriodsField = Annotated[
    list[str] | None,
    Field(
        description="Dataset periods: 'historical', 'recent', 'now' and/or 'future'. A period the "
        "requested datasets are not published under is rejected. When omitted, inferred from the "
        "timestamp where one is given, else every period those datasets publish.",
    ),
]
# named like the station column the default is read from; `height` in these models is the image option
_ElevationField = Annotated[
    float | None,
    Field(
        description="Elevation of the requested point in metres above sea level. Given, a quantity "
        "that falls with height -- air temperature, dew point -- is brought from each station's "
        "altitude to this one, which is what tells a valley reading from a summit one. "
        "Interpolation and summary only.",
    ),
]
_LeadTimeField = Annotated[
    Literal["short", "long"] | None,
    Field(description="Forecast lead time for DWD DMO ('short' or 'long'); ignored for other networks."),
]
_IssueField = Annotated[
    str | None,
    Field(description="Model-run issue time for DWD MOSMIX/DMO/SWSMOS (ISO 8601); defaults to the latest run."),
]
_AllField = Annotated[bool | None, Field(description="Return all stations, ignoring the stations/name/geo filters.")]
_StationsField = Annotated[
    list[str] | None,
    Field(description="Station ids, comma-separated, e.g. '01048' or '01048,04411'."),
]
_StationIdField = Annotated[str, Field(description="Station id used as the reference location, e.g. '01048'.")]
_StationIdOptField = Annotated[
    str | None,
    Field(description="Station id used as the reference location, e.g. '01048'."),
]
_NameField = Annotated[
    str | None,
    Field(
        description="Filter stations by name using fuzzy matching, e.g. 'Hamburg Fuhlsbüttel'. With a `timestamp` "
        "the name is matched among the stations that have a record in that window. The best match is first, "
        "equal matches ordered by station id."
    ),
]
_NameThresholdField = Annotated[
    float,
    Field(ge=0, le=1, description="Minimum fuzzy-match score for `name` (0 = any match, 1 = exact)."),
]
_LatitudeField = Annotated[
    float | None,
    Field(ge=-90, le=90, description="Latitude of the reference point for geospatial filtering or interpolation."),
]
_LongitudeField = Annotated[
    float | None,
    Field(ge=-180, le=180, description="Longitude of the reference point for geospatial filtering or interpolation."),
]
#: the largest count a request may name (`rank`): more than any network has stations, and far below what a
#: fixed-width integer holds, which a larger number overflows in the conversion (GH-3101)
MAX_COUNT = 1_000_000
#: the largest radius, in km, a request of the REST API or MCP may name for the stations of `interpolate` and
#: `summarize`, as it is given (the heterogeneous radius is scaled by the resolution on top, up to twice): five
#: times the default of a homogeneous parameter (40 km, `Options.geo_station_distance_homogeneous`), ten times that
#: of a heterogeneous one (20 km). The Python API and the command line take any
MAX_STATION_DISTANCE = 200.0
#: the most additional stations a request of the REST API or MCP may ask `interpolate` and `summarize` for, beyond
#: the four an interpolation needs: more than six times the default (3, `Options.geo_num_additional_stations`)
MAX_ADDITIONAL_STATIONS = 20
_RankField = Annotated[
    int | None,
    Field(
        ge=1,
        le=MAX_COUNT,
        description="With latitude/longitude, the N closest stations; with name, at most N stations (default "
        f"{DEFAULT_NAME_RANK_LISTING} for `stations`, which lists candidates, and {DEFAULT_NAME_RANK} for "
        "`values`, the best match, as the library's `filter_by_name`).",
    ),
]
_DistanceField = Annotated[
    float | None,
    Field(ge=0, description="Return stations within this many kilometres of the given latitude/longitude."),
]
_LeftField = Annotated[float | None, Field(ge=-180, le=180, description="Western longitude of the bounding box.")]
_BottomField = Annotated[float | None, Field(ge=-90, le=90, description="Southern latitude of the bounding box.")]
_RightField = Annotated[float | None, Field(ge=-180, le=180, description="Eastern longitude of the bounding box.")]
_TopField = Annotated[float | None, Field(ge=-90, le=90, description="Northern latitude of the bounding box.")]
_SqlField = Annotated[
    str | None,
    Field(
        description="SQL WHERE clause applied to the station metadata, e.g. \"region='Sachsen'\". The REST API "
        "and MCP server refuse it with a 403 unless they run with WD_RESTAPI_SQL=true."
    ),
]
_SqlValuesField = Annotated[
    str | None,
    Field(
        description='SQL WHERE clause applied to the values, e.g. "temperature_air_max_2m < 2.0". The REST API '
        "and MCP server refuse it with a 403 unless they run with WD_RESTAPI_SQL=true."
    ),
]
_WithMetadataField = Annotated[
    bool,
    Field(
        description="Add the unit of every parameter and what `quality_flags` holds to the `metadata` block of the "
        "JSON or GeoJSON, which is always there."
    ),
]
# of the values, interpolate and summarize requests, whose JSON formats report their settings with it
_WithMetadataSettingsField = Annotated[
    bool,
    Field(
        description="Add the unit of every parameter and what `quality_flags` holds to the `metadata` block of the "
        "JSON or GeoJSON, which is always there, and a `settings` block with the settings the result was got with."
    ),
]
_WithStationsField = Annotated[bool, Field(description="Include the queried stations' metadata block in the output.")]
_FormatField = Annotated[
    Literal["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"],
    Field(description="Output format: data (json, geojson, csv) or a rendered chart (html, png, jpg, webp, svg, pdf)."),
]
# of the stations and values requests, whose csv is streamed too, and which have a stream of their own (GH-3065)
_StreamFormatField = Annotated[
    Literal["json", "geojson", "csv", "ndjson", "html", "png", "jpg", "webp", "svg", "pdf"],
    Field(
        description="Output format: data (json, geojson, csv, ndjson) or a rendered chart (html, png, jpg, webp, "
        "svg, pdf). Over the REST API, ndjson and csv are streamed station by station, so they are allowed up to "
        "the higher `stream_rows` limit; an MCP tool gets one body in every format, capped at `rows`: see the "
        "limits of the server."
    ),
]
_PrettyField = Annotated[bool, Field(description="Pretty-print JSON/GeoJSON output.")]
_WidthField = Annotated[int | None, Field(gt=0, description="Width of the rendered chart image in pixels.")]
_HeightField = Annotated[int | None, Field(gt=0, description="Height of the rendered chart image in pixels.")]
_ScaleField = Annotated[float | None, Field(gt=0, description="Scale factor of the rendered chart image.")]
_TIMESTAMP_DESCRIPTION = (
    "Single date or interval in ISO 8601, e.g. '2020-05-01' or '2020-05-01/2020-05-05'. A date "
    "covers everything it names: '2020-05' is the month of May and '2020' the year, and a day is "
    "all of its readings rather than the one at midnight."
)
_TimestampField = Annotated[str, Field(description=_TIMESTAMP_DESCRIPTION)]
_TimestampOptField = Annotated[str | None, Field(description=_TIMESTAMP_DESCRIPTION)]
_StationsTimestampField = Annotated[
    str | None,
    Field(
        description=_TIMESTAMP_DESCRIPTION
        + " Given, only the stations whose record overlaps it are listed, as for `values`: a station is "
        "left out when it started after the window, or ended before it by more than the buffer "
        "(`station_window_end_buffer`), as the end a source publishes lags a station that is still "
        "reporting. A station whose start or end is not published is kept."
    ),
]
_StationWindowEndBufferField = Annotated[
    StationWindowEndBuffer | None,
    Field(
        description="How many days after the end its catalogue publishes a station is still kept for the window "
        "of `timestamp`, for every resolution: 0 compares the end exactly, 7 keeps a station that ended up to a "
        "week before the window. Left out, the buffer is two days up to daily, 62 for monthly and 732 for annual, "
        "as the end a source publishes lags a station that is still reporting. The start is compared exactly. "
        "Applies where stations are matched by `name` and in a listing of `stations`. "
        "Default: the server's WD_TS_STATION_WINDOW_END_BUFFER if set, else the buffer by resolution.",
    ),
]
_ShapeField = Annotated[
    Literal["long", "wide"],
    Field(
        description="Output shape: 'long' (one row per value) or 'wide' (one column per parameter). "
        "Default: the server's WD_TS_SHAPE if set, else long."
    ),
]
_HumanizeField = Annotated[
    bool,
    Field(
        description="Use human-readable parameter names instead of raw dataset codes. "
        "Default: the server's WD_TS_HUMANIZE if set, else true."
    ),
]
_ConvertUnitsField = Annotated[
    bool,
    Field(
        description="Convert values to the unit targets: the defaults, overridden per quantity by unit_targets. "
        "Default: the server's WD_TS_CONVERT_UNITS if set, else true."
    ),
]
_UnitTargetsField = Annotated[
    dict[str, str] | None,
    Field(
        description="Custom unit targets as a mapping of quantity to unit, e.g. {'temperature': 'degree_fahrenheit'}. "
        "A quantity it leaves out keeps the server's WD_TS_UNIT_TARGETS entry, if set."
    ),
]
_SkipEmptyField = Annotated[
    bool,
    Field(
        description="Skip stations whose coverage falls below `skip_threshold`. "
        "Default: the server's WD_TS_SKIP_EMPTY if set, else false."
    ),
]
_SkipThresholdField = Annotated[
    SkipThreshold,
    Field(
        description="Coverage fraction below which a station is skipped (requires `skip_empty`). "
        "Default: the server's WD_TS_SKIP_THRESHOLD if set, else 0.95.",
    ),
]
_SkipCriteriaField = Annotated[
    Literal["min", "mean", "max"],
    Field(
        description="Aggregation over the requested parameters' coverage: min, mean or max. "
        "Default: the server's WD_TS_SKIP_CRITERIA if set, else min."
    ),
]
_DropNullsField = Annotated[
    bool,
    Field(
        description="Drop rows with null values from the output. "
        "Default: the server's WD_TS_DROP_NULLS if set, else true."
    ),
]


def _plausibility_field(check: str, what: str) -> Any:  # noqa: ANN401
    """Make the field of a plausibility check: its mode, `hard` or `soft`, as `plausibility_<check>`."""
    return Annotated[
        Mode,
        Field(
            description=f"What the check `{check}` does to {what}: `hard` nulls the value and keeps the number as "
            f"`rejected:{check},raw:<number>` in `quality_flags`; `soft` keeps the value and flags it "
            f"`suspect:{check}`. Interpolation and summary leave a suspect value out in any case. "
            f"Default: the server's WD_TS_PLAUSIBILITY__{check.upper()} if set, else "
            f"{'soft' if check == 'stuck' else 'hard'}.",
        ),
    ]


_PlausibilityField = Annotated[
    Mode | None,
    Field(
        description="One mode for every plausibility check at once: `soft` keeps every value a check finds "
        "implausible and flags it (`suspect:<check>`), `hard` nulls it and keeps the number "
        "(`rejected:<check>,raw:<number>`). A check given beside it by `plausibility_<check>` wins. "
        "Default: the server's WD_TS_PLAUSIBILITY if set, else the mode of each check.",
    ),
]
_PlausibilityRangeField = _plausibility_field("range", "a reading outside the physical range of its parameter")
_PlausibilityElevationField = _plausibility_field(
    "elevation", "a station pressure the barometric formula does not expect at the station's elevation"
)
_PlausibilityStuckField = _plausibility_field(
    "stuck", "a sensor that held one value over a period it should not have (a verdict that depends on the window)"
)
_PlausibilityConsistencyField = _plausibility_field(
    "consistency", "a reading that another parameter of the same file contradicts (never downloaded for the check)"
)
_PlausibilityFloorField = _plausibility_field(
    "floor", "a model value a little below the floor of its quantity (`hard` sets the floor, not null)"
)
#: the query parameters and command line options that set the mode of a check, by the check they set (GH-3676)
PLAUSIBILITY_OPTIONS = {f"plausibility_{check}": check for check in CHECKS}
_SectionsField = Annotated[
    set[Literal["name", "parameter", "device", "geography", "missing_data"]] | None,
    Field(
        description="History sections to include: name, parameter, device, geography, missing_data. Each history "
        "gives its station_id, resolution and dataset, whichever are included.",
    ),
]
_InterpolationStationDistanceField = Annotated[
    dict[str, Annotated[float, Field(ge=0.0)]] | None,
    Field(
        description="Per-parameter maximum interpolation-station distance in km, keyed by canonical parameter "
        "name, overriding the default radius of that parameter. A parameter it leaves out keeps the server's "
        "WD_TS_GEO_STATION_DISTANCE entry, if set.",
    ),
]
_SummaryStationDistanceField = Annotated[
    dict[str, Annotated[float, Field(ge=0.0)]] | None,
    Field(
        description="Per-parameter maximum summary-station distance in km, keyed by canonical parameter "
        "name, overriding the default radius of that parameter. A parameter it leaves out keeps the server's "
        "WD_TS_GEO_STATION_DISTANCE entry, if set.",
    ),
]
_StationDistanceHomogeneousField = Annotated[
    float | None,
    Field(
        ge=0,
        description="Maximum distance (km) to a station for a parameter that varies slowly across a region, "
        "such as air temperature. Default: the server's WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS if set, else 40.",
    ),
]
_StationDistanceHeterogeneousField = Annotated[
    float | None,
    Field(
        ge=0,
        description="The same for a parameter that decorrelates faster, such as precipitation, at hourly "
        "resolution. Coarser resolutions scale it up and finer ones down -- times 0.75 at the minute "
        "resolutions, times 2 from daily upwards. "
        "Default: the server's WD_TS_GEO_STATION_DISTANCE_HETEROGENEOUS if set, else 20.",
    ),
]
_UseNearbyStationDistanceField = Annotated[
    float,
    Field(
        ge=0,
        description="Use a nearby station's values directly when it is within this distance (km) of the target. "
        "Default: the server's WD_TS_GEO_USE_NEARBY_STATION_DISTANCE if set, else 1.",
    ),
]
_MinGainOfValuePairsField = Annotated[
    float,
    Field(
        ge=0,
        description="Minimum relative gain in value pairs required to add another interpolation station. "
        "Default: the server's WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS if set, else 0.1.",
    ),
]
_NumAdditionalStationsField = Annotated[
    int,
    Field(
        ge=0,
        le=MAX_COUNT,
        description="Number of additional nearby stations to consider for interpolation. "
        "Default: the server's WD_TS_GEO_NUM_ADDITIONAL_STATIONS if set, else 3.",
    ),
]


# what the REST API and MCP take of the above: the same fields, bounded. The Python API and the command line take
# the unbounded ones
_REST_BOUND = (
    f" At most {MAX_STATION_DISTANCE:g} km on the REST API and MCP, which the Python API and the CLI do not hold to."
)
_RestInterpolationStationDistanceField = Annotated[
    dict[str, Annotated[float, Field(ge=0.0, le=MAX_STATION_DISTANCE)]] | None,
    Field(
        description="Per-parameter maximum interpolation-station distance in km, keyed by canonical parameter "
        "name, overriding the default radius of that parameter. A parameter it leaves out keeps the server's "
        f"WD_TS_GEO_STATION_DISTANCE entry, if set.{_REST_BOUND}",
    ),
]
_RestSummaryStationDistanceField = Annotated[
    dict[str, Annotated[float, Field(ge=0.0, le=MAX_STATION_DISTANCE)]] | None,
    Field(
        description="Per-parameter maximum summary-station distance in km, keyed by canonical parameter "
        "name, overriding the default radius of that parameter. A parameter it leaves out keeps the server's "
        f"WD_TS_GEO_STATION_DISTANCE entry, if set.{_REST_BOUND}",
    ),
]
_RestStationDistanceHomogeneousField = Annotated[
    float | None,
    Field(
        ge=0,
        le=MAX_STATION_DISTANCE,
        description="Maximum distance (km) to a station for a parameter that varies slowly across a region, "
        "such as air temperature. Default: the server's WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS if set, else 40."
        + _REST_BOUND,
    ),
]
_RestStationDistanceHeterogeneousField = Annotated[
    float | None,
    Field(
        ge=0,
        le=MAX_STATION_DISTANCE,
        description="The same for a parameter that decorrelates faster, such as precipitation, at hourly "
        "resolution. Coarser resolutions scale it up and finer ones down -- times 0.75 at the minute "
        "resolutions, times 2 from daily upwards. "
        "Default: the server's WD_TS_GEO_STATION_DISTANCE_HETEROGENEOUS if set, else 20." + _REST_BOUND,
    ),
]
_RestMinGainOfValuePairsField = Annotated[
    float,
    Field(
        gt=0,
        description="Minimum relative gain in value pairs required to add another interpolation station, more "
        "than 0 on the REST API and MCP. "
        "Default: the server's WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS if set, else 0.1.",
    ),
]
_RestNumAdditionalStationsField = Annotated[
    int,
    Field(
        ge=0,
        le=MAX_ADDITIONAL_STATIONS,
        description="Number of additional nearby stations to consider for interpolation. At most "
        f"{MAX_ADDITIONAL_STATIONS} on the REST API and MCP, which the Python API and the CLI do not hold to. "
        "Default: the server's WD_TS_GEO_NUM_ADDITIONAL_STATIONS if set, else 3.",
    ),
]


def _read_items(value: str | list | None) -> list[str] | None:
    """Read items, such as station ids, from a comma-separated string or a list of them, None when there are none.

    A blank item selects nothing: FastAPI reads an empty `stations=` as `[""]`, which would count as a
    station selection beside `all` or a point, and be refused as a second one.
    """
    items = [value] if isinstance(value, str) else (value or [])
    ids = [station for item in items for station in read_list(item, separator=",") if station]
    return ids or None


def _load_json(text: str) -> Any:  # noqa: ANN401
    """Read a mapping a query gives as JSON, refusing one nested deeper than Python reads as a plain value error.

    A few thousand opening braces in a query is enough to exhaust the recursion limit, and the `RecursionError` is
    no `ValueError`, so it was the 500 of a request that is only malformed (GH-3085).
    """
    try:
        return json.loads(text)
    except RecursionError:
        msg = "the JSON is nested too deeply"
        raise ValueError(msg) from None


def join_names(names: Sequence[str], last: str = "and") -> str:
    """Join names as prose: `a`, `a and b`, `a, b and c`."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} {last} {names[-1]}"


def describe_fields(groups: Sequence[Sequence[str]], spell: Callable[[str], str] = str) -> str:
    """Name alternative groups of fields as prose: `all, (latitude and longitude) or sql`.

    `spell` names a field; the CLI passes one that names its option instead.
    """
    names = [join_names([spell(field) for field in group]) for group in groups]
    if len(groups) > 1:
        names = [f"({name})" if len(group) > 1 else name for name, group in zip(names, groups, strict=True)]
    return join_names(names, last="or")


# the rules over several fields report the way pydantic reports one field's error: a type, the
# field it is about as `loc` (none for a rule about no field in particular), the value refused as
# `input`, and in `ctx` the other fields involved, which the CLI renders in click's own terms
def _rule_error(
    kind: LiteralString,
    message: str,
    loc: tuple[str, ...] = (),
    value: Any = None,  # noqa: ANN401
    **ctx: Any,  # noqa: ANN401
) -> InitErrorDetails:
    """Build one error of a rule over several fields."""
    # pydantic fills a template's {placeholders} from ctx; the message names fields, which hold none
    template = cast("LiteralString", message)
    return InitErrorDetails(type=PydanticCustomError(kind, template, ctx), loc=loc, input=value)


def _raise_rule_errors(request: BaseModel, errors: list[InitErrorDetails]) -> None:
    """Raise the errors of a model's rules as a ValidationError, which pydantic passes on as it is."""
    if errors:
        raise ValidationError.from_exception_data(type(request).__name__, errors)


#: query parameters renamed on the way to 1.0, old name to new: a parameter that takes a list is
#: plural on every surface (GH-2561). A request model refuses the old name, where the model has
#: the new one and not the old one, with an error naming the new one, rather than one about a
#: parameter it does not know (GH-2438); so does each MCP tool taking the new name, and the command
#: line, which names its option (`--station` was renamed to `--stations`). A model that takes the
#: old name for what it is -- the one reference `station` of an interpolation or a summary, the
#: `dataset` of the issues of a DMO product -- is not refused it
RENAMED_REQUEST_PARAMETERS: dict[str, str] = {
    "date": "timestamp",
    "station": "stations",
    "parameter": "parameters",
    "period": "periods",
    "dataset": "datasets",
    "resolution": "resolutions",
}


#: query parameters removed on the way to 1.0, name to what to do instead. A request that still gives one is
#: refused with that sentence, on REST and in each MCP tool, rather than as a parameter it does not know
#: (GH-3336). `debug` set the logger level of the whole process from an anonymous request, so one caller could
#: switch the server's log to debug for every other; the command line, a process of its own, keeps its `--debug`,
#: which `wetterdienst restapi --debug` gives the operator who starts the server
REMOVED_REQUEST_PARAMETERS: dict[str, str] = {
    "debug": (
        "a request no longer sets the log level of the server, which is the operator's to set: start the server "
        "with `wetterdienst restapi --debug`, or configure the Python logger `wetterdienst` in the process that "
        "hosts it"
    ),
}


def removed_parameter_message(name: str) -> str:
    """Tell a caller that a parameter of `REMOVED_REQUEST_PARAMETERS` is gone, and what to do instead."""
    return f"{name} was removed: {REMOVED_REQUEST_PARAMETERS[name]}"


class _RefusesRenamedParameters(BaseModel):
    """A request model that refuses a parameter given by its old name, naming the new one, or one that is gone."""

    @model_validator(mode="before")
    @classmethod
    def refuse_renamed_parameters(cls, data: Any) -> Any:  # noqa: ANN401
        """Refuse a parameter of `RENAMED_REQUEST_PARAMETERS` by its old name, or of `REMOVED_REQUEST_PARAMETERS`."""
        if isinstance(data, Mapping):
            errors = [
                _rule_error("renamed", f"{old} was renamed to {new}", (old,), data[old], renamed_to=new)
                for old, new in RENAMED_REQUEST_PARAMETERS.items()
                if old in data and old not in cls.model_fields and new in cls.model_fields
            ]
            errors += [
                _rule_error("removed", removed_parameter_message(name), (name,), data[name])
                for name in REMOVED_REQUEST_PARAMETERS
                if name in data and name not in cls.model_fields
            ]
            if errors:
                raise ValidationError.from_exception_data(cls.__name__, errors)
        return data


def _is_set(request: BaseModel, field: str) -> bool:
    """Tell whether a request gives a field: a coordinate of 0 is given, a False flag or an empty list is not."""
    value = getattr(request, field)
    return not (value is None or value is False or (isinstance(value, (str, list)) and not value))


def _check_one_of(request: BaseModel, groups: Sequence[tuple[str, ...]]) -> list[InitErrorDetails]:
    """Check a request gives exactly one of alternative groups of fields, and the whole of it."""
    made = [group for group in groups if any(_is_set(request, field) for field in group)]
    if not made:
        message = f"Exactly one of {describe_fields(groups)} is required"
        return [_rule_error("missing_one_of", message, one_of=[list(group) for group in groups])]
    if len(made) > 1:
        # each group by the first field it gives, the one the error is located at
        firsts = [next(field for field in group if _is_set(request, field)) for group in made]
        errors = []
        one_of = [list(group) for group in groups]
        for field in firsts:
            others = [other for other in firsts if other != field]
            # the alternatives are named with the conflict, as they are with a missing one
            message = f"Cannot be combined with {join_names(others)}, give exactly one of {describe_fields(groups)}"
            errors.append(
                _rule_error(
                    "mutually_exclusive",
                    message,
                    (field,),
                    getattr(request, field),
                    conflicts_with=others,
                    one_of=one_of,
                )
            )
        return errors
    (group,) = made
    given = [field for field in group if _is_set(request, field)]
    return [
        _rule_error("missing_with", f"Field required with {join_names(given)}", (field,), required_with=given)
        for field in group
        if field not in given
    ]


_POINT = ("latitude", "longitude")
_STATION_SELECTIONS = (("all",), ("stations",), ("name",), _POINT, ("left", "bottom", "right", "top"), ("sql",))


def _check_station_selection(request: StationsRequest | ValuesRequest) -> list[InitErrorDetails]:
    """Check the one station selection a stations or values request makes.

    `get_stations` takes the first selection it finds, so a request making two was answered for
    one of them and the other dropped without a word. The CLI's option parser refused that, but the
    REST API and MCP build these models without it and answered. Checked here, all three share one
    rule.

    `rank` goes with `name` as well as with a point: there it caps the fuzzy matches.
    """
    errors = _check_one_of(request, _STATION_SELECTIONS)
    if errors:
        return errors
    if _is_set(request, "latitude"):
        if request.rank is None and request.distance is None:
            message = f"Exactly one of rank or distance is required with {join_names(_POINT)}"
            return [_rule_error("missing_one_of", message, one_of=[["rank"], ["distance"]], required_with=[*_POINT])]
        return _check_one_of(request, (("rank",), ("distance",)))
    if request.distance is not None:
        message = f"Requires {describe_fields([_POINT])}"
        errors.append(_rule_error("requires", message, ("distance",), request.distance, requires=[[*_POINT]]))
    if request.rank is not None and not request.name:
        message = f"Requires {describe_fields([_POINT, ('name',)])}"
        errors.append(_rule_error("requires", message, ("rank",), request.rank, requires=[[*_POINT], ["name"]]))
    return errors


class StationsRequest(_RefusesRenamedParameters):
    """Stations request with validated parameters."""

    model_config = {"extra": "forbid"}

    provider: _ProviderField
    network: _NetworkField
    parameters: _ParametersField

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    periods: _PeriodsField = None

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v: str | list | None) -> list[str] | None:
        """Validate periods."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v, separator=",")
        periods = []
        for item in v:
            if "," in item:
                periods.extend(read_list(item, separator=","))
            else:
                periods.append(item)
        return periods

    # station filter parameters
    all: _AllField = False
    # station ids
    stations: _StationsField = None

    @field_validator("stations", mode="before")
    @classmethod
    def validate_stations(cls, v: str | list | None) -> list[str] | None:
        """Validate stations."""
        return _read_items(v)

    # station name
    name: _NameField = None
    name_threshold: _NameThresholdField = 0.8
    # latlon
    latitude: _LatitudeField = None
    longitude: _LongitudeField = None
    rank: _RankField = None
    distance: _DistanceField = None
    # bbox
    left: _LeftField = None
    bottom: _BottomField = None
    right: _RightField = None
    top: _TopField = None
    # sql
    sql: _SqlField = None

    # the window the stations listed are to have a record in, as for `values` (GH-2635)
    timestamp: _StationsTimestampField = None
    station_window_end_buffer: _StationWindowEndBufferField = None

    with_metadata: _WithMetadataField = False

    format: _StreamFormatField = "json"
    pretty: _PrettyField = False

    # plot settings
    width: _WidthField = None
    height: _HeightField = None
    scale: _ScaleField = None

    @model_validator(mode="after")
    def check_station_selection(self) -> StationsRequest:
        """Check that exactly one station selection is made."""
        _raise_rule_errors(self, _check_station_selection(self))
        return self


class HistoryRequest(_RefusesRenamedParameters):
    """History request with validated parameters.

    Used to get historical station metadata.
    """

    model_config = {"extra": "forbid"}

    provider: _ProviderField
    network: _NetworkField
    parameters: _ParametersField

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    # allow selecting all stations
    all: _AllField = False

    # station filter parameters
    # For history requests we accept one or more station ids (list) or 'all'.
    stations: _StationsField = None

    @field_validator("stations", mode="before")
    @classmethod
    def validate_stations(cls, v: str | list | None) -> list[str] | None:
        """Validate stations."""
        return _read_items(v)

    sections: _SectionsField = None

    @field_validator("sections", mode="before")
    @classmethod
    def validate_sections(cls, v: str | list) -> set[str] | None:
        """Validate sections."""
        if not v:
            return None
        if isinstance(v, str):
            return set(read_list(v))
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return set(parameters)

    with_metadata: _WithMetadataField = False
    with_stations: _WithStationsField = False

    pretty: _PrettyField = False

    @model_validator(mode="after")
    def check_station_selection(self) -> HistoryRequest:
        """Check that exactly one of all or stations is given."""
        _raise_rule_errors(self, _check_one_of(self, (("all",), ("stations",))))
        return self


class ValuesRequest(_RefusesRenamedParameters):
    """Values request with validated parameters."""

    model_config = {"extra": "forbid"}

    # from stations
    provider: _ProviderField
    network: _NetworkField
    parameters: _ParametersField

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    periods: _PeriodsField = None

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v: str | list | None) -> list[str] | None:
        """Validate periods."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v, separator=",")
        periods = []
        for item in v:
            if "," in item:
                periods.extend(read_list(item, separator=","))
            else:
                periods.append(item)
        return periods

    # DWD forecasts: issue for MOSMIX/DMO/SWSMOS, lead_time for DMO
    lead_time: _LeadTimeField = None
    issue: _IssueField = None

    # station filter parameters
    all: _AllField = False
    # station ids
    stations: _StationsField = None

    @field_validator("stations", mode="before")
    @classmethod
    def validate_stations(cls, v: str | list | None) -> list[str] | None:
        """Validate stations."""
        return _read_items(v)

    # station name
    name: _NameField = None
    name_threshold: _NameThresholdField = 0.8
    # latlon
    latitude: _LatitudeField = None
    longitude: _LongitudeField = None
    rank: _RankField = None
    distance: _DistanceField = None
    # bbox
    left: _LeftField = None
    bottom: _BottomField = None
    right: _RightField = None
    top: _TopField = None
    # sql
    sql: _SqlField = None

    with_metadata: _WithMetadataSettingsField = False
    with_stations: _WithStationsField = False

    format: _StreamFormatField = "json"
    pretty: _PrettyField = False

    # plot settings
    width: _WidthField = None
    height: _HeightField = None
    scale: _ScaleField = None

    # values
    timestamp: _TimestampOptField = None
    sql_values: _SqlValuesField = None
    humanize: _HumanizeField = True
    shape: _ShapeField = "long"
    convert_units: _ConvertUnitsField = True
    unit_targets: _UnitTargetsField = None
    skip_empty: _SkipEmptyField = False
    skip_threshold: _SkipThresholdField = 0.95
    skip_criteria: _SkipCriteriaField = "min"
    drop_nulls: _DropNullsField = True
    station_window_end_buffer: _StationWindowEndBufferField = None
    plausibility: _PlausibilityField = None
    plausibility_range: _PlausibilityRangeField = "hard"
    plausibility_elevation: _PlausibilityElevationField = "hard"
    plausibility_stuck: _PlausibilityStuckField = "soft"
    plausibility_consistency: _PlausibilityConsistencyField = "hard"
    plausibility_floor: _PlausibilityFloorField = "hard"

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v: str | dict | None) -> dict[str, str] | None:
        """Validate unit targets."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return _load_json(v)

    @model_validator(mode="after")
    def check_station_selection(self) -> ValuesRequest:
        """Check that exactly one station selection is made."""
        _raise_rule_errors(self, _check_station_selection(self))
        return self


class InterpolationRequest(_RefusesRenamedParameters):
    """Interpolation request with validated parameters."""

    model_config = {"extra": "forbid"}

    provider: _ProviderField
    network: _NetworkField
    parameters: _ParametersField

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    periods: _PeriodsField = None

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v: str | list | None) -> list[str] | None:
        """Validate periods."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v, separator=",")
        periods = []
        for item in v:
            if "," in item:
                periods.extend(read_list(item, separator=","))
            else:
                periods.append(item)
        return periods

    timestamp: _TimestampField

    # DWD forecasts: issue for MOSMIX/DMO/SWSMOS, lead_time for DMO
    lead_time: _LeadTimeField = None
    issue: _IssueField = None

    # station filter parameters
    station: _StationIdOptField = None
    # latlon
    latitude: _LatitudeField = None
    longitude: _LongitudeField = None
    elevation: _ElevationField = None
    # sql
    sql_values: _SqlValuesField = None
    humanize: _HumanizeField = True
    convert_units: _ConvertUnitsField = True
    unit_targets: _UnitTargetsField = None

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v: str | None) -> dict[str, str] | None:
        """Validate unit targets."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return _load_json(v)

    interpolation_station_distance: _InterpolationStationDistanceField = None
    interpolation_station_distance_homogeneous: _StationDistanceHomogeneousField = None
    interpolation_station_distance_heterogeneous: _StationDistanceHeterogeneousField = None

    @field_validator("interpolation_station_distance", mode="before")
    @classmethod
    def validate_interpolation_station_distance(cls, v: str | None) -> dict[str, float] | None:
        """Validate interpolation station distance."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return _load_json(v)

    use_nearby_station_distance: _UseNearbyStationDistanceField = 1.0
    min_gain_of_value_pairs: _MinGainOfValuePairsField = 0.10
    num_additional_stations: _NumAdditionalStationsField = 3
    format: _FormatField = "json"

    with_metadata: _WithMetadataSettingsField = False
    with_stations: _WithStationsField = False

    pretty: _PrettyField = False

    # plot settings
    width: _WidthField = None
    height: _HeightField = None
    scale: _ScaleField = None

    @model_validator(mode="after")
    def check_reference_point(self) -> InterpolationRequest:
        """Check that exactly one of station or latitude/longitude is given."""
        _raise_rule_errors(self, _check_one_of(self, (("station",), _POINT)))
        return self


class SummaryRequest(_RefusesRenamedParameters):
    """Summary request with validated parameters."""

    model_config = {"extra": "forbid"}

    provider: _ProviderField
    network: _NetworkField
    parameters: _ParametersField

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: str | list) -> list[str]:
        """Validate parameters."""
        if isinstance(v, str):
            return read_list(v)
        parameters = []
        for item in v:
            if "," in item:
                parameters.extend(read_list(item, separator=","))
            else:
                parameters.append(item)
        return parameters

    periods: _PeriodsField = None

    @field_validator("periods", mode="before")
    @classmethod
    def validate_periods(cls, v: str | list | None) -> list[str] | None:
        """Validate periods."""
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v, separator=",")
        periods = []
        for item in v:
            if "," in item:
                periods.extend(read_list(item, separator=","))
            else:
                periods.append(item)
        return periods

    timestamp: _TimestampField

    # DWD forecasts: issue for MOSMIX/DMO/SWSMOS, lead_time for DMO
    lead_time: _LeadTimeField = None
    issue: _IssueField = None

    # station filter parameters
    station: _StationIdOptField = None
    # latlon
    latitude: _LatitudeField = None
    longitude: _LongitudeField = None
    elevation: _ElevationField = None
    # sql
    sql_values: _SqlValuesField = None
    humanize: _HumanizeField = True
    convert_units: _ConvertUnitsField = True
    unit_targets: _UnitTargetsField = None

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v: str | None) -> dict[str, str] | None:
        """Validate unit targets."""
        if not v:
            return None
        return _load_json(v)

    summary_station_distance: _SummaryStationDistanceField = None
    summary_station_distance_homogeneous: _StationDistanceHomogeneousField = None
    summary_station_distance_heterogeneous: _StationDistanceHeterogeneousField = None

    @field_validator("summary_station_distance", mode="before")
    @classmethod
    def validate_summary_station_distance(cls, v: str | None) -> dict[str, float] | None:
        """Validate summary station distance."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return _load_json(v)

    min_gain_of_value_pairs: _MinGainOfValuePairsField = 0.10
    num_additional_stations: _NumAdditionalStationsField = 3
    format: _FormatField = "json"

    with_metadata: _WithMetadataSettingsField = False
    with_stations: _WithStationsField = False

    pretty: _PrettyField = False

    # plot settings
    width: _WidthField = None
    height: _HeightField = None
    scale: _ScaleField = None

    @model_validator(mode="after")
    def check_reference_point(self) -> SummaryRequest:
        """Check that exactly one of station or latitude/longitude is given."""
        _raise_rule_errors(self, _check_one_of(self, (("station",), _POINT)))
        return self


class RestInterpolationRequest(InterpolationRequest):
    """The interpolation request of the REST API and MCP: the one of the library, with its work bounded.

    The distances, `num_additional_stations` and `min_gain_of_value_pairs` of a caller who is not the host's own
    user cannot ask for an unbounded amount of work (see `MAX_STATION_DISTANCE` and `MAX_ADDITIONAL_STATIONS`),
    and the stations in reach are counted against the limit of the server (`ui.limits`).
    """

    interpolation_station_distance: _RestInterpolationStationDistanceField = None
    interpolation_station_distance_homogeneous: _RestStationDistanceHomogeneousField = None
    interpolation_station_distance_heterogeneous: _RestStationDistanceHeterogeneousField = None
    min_gain_of_value_pairs: _RestMinGainOfValuePairsField = 0.10
    num_additional_stations: _RestNumAdditionalStationsField = 3


class RestSummaryRequest(SummaryRequest):
    """The summary request of the REST API and MCP: the one of the library, bounded as `RestInterpolationRequest`."""

    summary_station_distance: _RestSummaryStationDistanceField = None
    summary_station_distance_homogeneous: _RestStationDistanceHomogeneousField = None
    summary_station_distance_heterogeneous: _RestStationDistanceHeterogeneousField = None
    min_gain_of_value_pairs: _RestMinGainOfValuePairsField = 0.10
    num_additional_stations: _RestNumAdditionalStationsField = 3


class SettingsRequest(BaseModel):
    """The settings query parameters of the values, interpolation and summary requests (GH-2383).

    Each is the field of the request that takes it, so it is read as that request reads it; one
    the interpolation and the summary request both take is one field here, given to both.
    """

    model_config = {"extra": "forbid"}

    humanize: _HumanizeField = True
    convert_units: _ConvertUnitsField = True
    unit_targets: _UnitTargetsField = None
    # values
    shape: _ShapeField = "long"
    skip_empty: _SkipEmptyField = False
    skip_threshold: _SkipThresholdField = 0.95
    skip_criteria: _SkipCriteriaField = "min"
    drop_nulls: _DropNullsField = True
    station_window_end_buffer: _StationWindowEndBufferField = None
    plausibility: _PlausibilityField = None
    plausibility_range: _PlausibilityRangeField = "hard"
    plausibility_elevation: _PlausibilityElevationField = "hard"
    plausibility_stuck: _PlausibilityStuckField = "soft"
    plausibility_consistency: _PlausibilityConsistencyField = "hard"
    plausibility_floor: _PlausibilityFloorField = "hard"
    # interpolate
    interpolation_station_distance: _RestInterpolationStationDistanceField = None
    interpolation_station_distance_homogeneous: _RestStationDistanceHomogeneousField = None
    interpolation_station_distance_heterogeneous: _RestStationDistanceHeterogeneousField = None
    use_nearby_station_distance: _UseNearbyStationDistanceField = 1.0
    # summarize
    summary_station_distance: _RestSummaryStationDistanceField = None
    summary_station_distance_homogeneous: _RestStationDistanceHomogeneousField = None
    summary_station_distance_heterogeneous: _RestStationDistanceHeterogeneousField = None
    # interpolate and summarize
    min_gain_of_value_pairs: _RestMinGainOfValuePairsField = 0.10
    num_additional_stations: _RestNumAdditionalStationsField = 3

    @field_validator("unit_targets", "interpolation_station_distance", "summary_station_distance", mode="before")
    @classmethod
    def validate_json_mapping(cls, v: str | dict | None) -> dict | None:
        """Read a mapping given as JSON, as the requests read it."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return _load_json(v)


#: what a station id of the MOSMIX, DMO and SWSMOS listings looks like: a path segment, never `.` or `..`
_ISSUE_STATION = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,31}")


class IssuesRequest(_RefusesRenamedParameters):
    """Request model for listing available issue datetimes."""

    model_config = {"extra": "forbid"}

    provider: _ProviderField
    network: _NetworkField
    station: _StationIdField
    dataset: Annotated[
        Literal["icon", "icon_eu"] | None,
        Field(
            description="DWD DMO product to list issues for ('icon' or 'icon_eu'), default 'icon'; "
            "DMO only, refused for MOSMIX and SWSMOS.",
        ),
    ] = None
    # not the shared `_LeadTimeField`: the data requests ignore a lead time outside DMO, but `get_issues`
    # refuses one
    lead_time: Annotated[
        Literal["short", "long"] | None,
        Field(
            description="DWD DMO forecast lead time to list issues for ('short' or 'long'), default 'short'; "
            "DMO only, refused for MOSMIX and SWSMOS.",
        ),
    ] = None

    @field_validator("station")
    @classmethod
    def check_station_is_an_id(cls, v: str) -> str:
        """Refuse a station that is not an id, as it becomes a segment of the path DWD is asked for (GH-3084).

        Unlike the stations of the data requests, which are looked up in the network's list, this one is not
        checked against anything before it is put into the URL of a directory listing: a `/` or `..` in it would
        list another directory of the provider, and a NUL make DWD answer a 400. An id is letters, digits, `_`, `-`
        and, after the first character, `.`. The schema of the parameter is left as it was.
        """
        if not _ISSUE_STATION.fullmatch(v):
            msg = "station is not a station id (letters, digits, '_', '-' and '.', at most 32 characters)"
            raise ValueError(msg)
        return v


# the query parameters of `/api/auth`, `/api/coverage`, `/api/glossary` and `/api/alerts`, and of
# `/api/stripes/stations` below, each a model forbidding others as the other endpoints' requests
# are: taken loose, a parameter the endpoint does not know was passed over, and the request answered
# as if it had not been given it (GH-2479)
class AuthRequest(_RefusesRenamedParameters):
    """Request model for checking the credentials of a provider and network."""

    model_config = {"extra": "forbid"}

    provider: _ProviderField
    network: _NetworkField


class CoverageRequest(_RefusesRenamedParameters):
    """Request model for listing providers and networks, or the resolutions, datasets and parameters of one."""

    model_config = {"extra": "forbid"}

    provider: Annotated[
        str | None,
        Field(
            description="Data provider, e.g. 'dwd'. Give it with network to list that network's resolutions, "
            "datasets and parameters; with neither, every provider and its networks are listed."
        ),
    ] = None
    network: Annotated[
        str | None,
        Field(description="Data network of the provider, e.g. 'observation'. Needs provider."),
    ] = None
    resolutions: Annotated[
        list[str] | None,
        Field(description="Only these resolutions, comma-separated, e.g. 'daily,hourly'. Needs provider and network."),
    ] = None
    datasets: Annotated[
        list[str] | None,
        Field(description="Only these datasets, comma-separated, e.g. 'climate_summary'. Needs provider and network."),
    ] = None
    pretty: _PrettyField = False

    @field_validator("resolutions", "datasets", mode="before")
    @classmethod
    def validate_lists(cls, v: str | list | None) -> list[str] | None:
        """Read a list given comma-separated, or repeated, None where it names nothing."""
        return _read_items(v)


class ProvidersRequest(_RefusesRenamedParameters):
    """Request model for describing the providers."""

    model_config = {"extra": "forbid"}

    provider: Annotated[
        str | None,
        Field(description="Only this provider, e.g. 'dwd'. Without it, every provider."),
    ] = None
    pretty: _PrettyField = False


class GlossaryRequest(_RefusesRenamedParameters):
    """Request model for looking up the canonical parameters."""

    model_config = {"extra": "forbid"}

    parameter: Annotated[
        str | None,
        Field(description="Only the parameters whose name contains this text, e.g. 'radiation'. Not case-sensitive."),
    ] = None
    unit_type: Annotated[
        UnitType | None,
        Field(description="Only the parameters of this quantity, e.g. 'temperature'. Combines with parameter."),
    ] = None
    limit: Annotated[int | None, Field(ge=1, description="Return at most this many entries.")] = None


class AlertsRequest(_RefusesRenamedParameters):
    """Request model for the DWD weather alerts."""

    model_config = {"extra": "forbid"}

    granularity: Annotated[
        Literal["community", "district"],
        Field(
            description="Spatial unit of the warnings: 'community' (per municipality) or 'district' (per Landkreis)."
        ),
    ] = "community"
    language: Annotated[
        Literal["de", "en", "es", "fr", "mul"],
        Field(
            description="Language of the warnings. 'mul' bundles every language in one file, of which only the "
            "first is read: prefer a single language."
        ),
    ] = "en"
    timestamp: Annotated[
        str | None,
        Field(
            description="Instant in ISO 8601 (UTC if no offset) of a snapshot from DWD's rolling window of about "
            "48 hours. Without it, the latest snapshot."
        ),
    ] = None
    format: Annotated[
        Literal["json", "geojson", "csv"],
        Field(description="Output format: json, geojson (a feature collection) or csv."),
    ] = "json"
    pretty: _PrettyField = False


def failure_status(e: BaseException) -> int:
    """Tell the HTTP status a failure is answered with, from its place in the `WetterdienstError` hierarchy.

    The one table every surface reads (REST, the MCP tools through REST, the command line)::

        RequestError, OverflowError          400  the request cannot be served as phrased
        NotFoundError                        404  a provider, network, station or issue that does not exist
        ConfigurationError                   501  a credential or optional dependency this installation lacks
        NotImplementedError                  501  something wetterdienst does not do for a network, e.g. history
        NoInternetError                      503  no connection to the provider could be made
        UpstreamError after a timeout        504  the provider did not answer in time
        any other UpstreamError              502  the provider failed, or sent what the parser does not expect
        anything else                        500  our bug

    A `RequestError` -- a date, period, parameter, bounding box, point or issue that cannot be
    served as given -- is a 400, and a `NotFoundError` a 404. An `OverflowError` is a 400 as well: it
    is a date at the edge of what a datetime holds -- `9999-12-31T23:00Z` once a provider converts it
    to its own zone, an issue a negative offset carries past year 9999 -- and the dates on the way
    that come that close are the request's. A `ConfigurationError`, a credential or an optional
    dependency this installation lacks, is a 501: the request was well formed, and the deployment
    declines it, and so is a `NotImplementedError`, which says what wetterdienst does not do for a network (GH-3065).
    A `NoInternetError` is a 503: nothing is wrong with the request or the server's
    code, and the same request can succeed once the connection is back (GH-2640). Any other
    `UpstreamError` -- a `DownloadError`, a file in a layout the parser does not expect -- is the
    provider's, not the caller's to fix and not a defect of ours: a 502, or a 504 where the failure
    underneath (its `__cause__`) was a timeout. What is left is a 500, an unclassified
    `WetterdienstError` among it, so a class added to the hierarchy without a place here is the
    server's error until it is given one.

    Kept here rather than in the REST API so that `wetterdienst issues` asks the same question
    without importing FastAPI: there a refusal is a usage error, exit 2, a `NoInternetError` one line, exit 1,
    and anything else a logged traceback, exit 1.
    """
    if isinstance(e, NotFoundError):
        return 404
    if isinstance(e, (RequestError, OverflowError)):
        return 400
    if isinstance(e, (ConfigurationError, NotImplementedError)):
        return 501
    if isinstance(e, NoInternetError):
        return 503
    if isinstance(e, UpstreamError):
        return 504 if timed_out(e) else 502
    return 500


def timed_out(e: BaseException) -> bool:
    """Tell whether a failure was a timeout, itself or by the failure it was raised from.

    A download that did not answer in time is a `DownloadError` whose `__cause__` is the timeout
    (`TimeoutError`, which `asyncio`, aiohttp's `ServerTimeoutError` and fsspec's `FSTimeoutError`
    all derive from), so the chain is followed. Its own message is empty, and the class is the only
    thing that tells it from a dropped connection.
    """
    seen: set[int] = set()
    current: BaseException | None = e
    while current is not None and id(current) not in seen:
        if isinstance(current, TimeoutError):
            return True
        seen.add(id(current))
        current = current.__cause__
    return False


def _caller_refusal_status(e: Exception, request: BaseModel) -> int | None:
    """Tell the status of a failure that is the request's own, which the caller can rephrase, else None.

    Beyond the hierarchy (`failure_status`): the caller's own `sql` or `sql_values` is the only SQL
    run on the way, so a DuckDB error about the statement -- its syntax, a column or function it
    names, a value it compares -- is theirs, a 400. So, where the request carries a clause, are the
    refusals of the connection the clause runs on (`wetterdienst.io.sql_filter.filter_by_sql`): a file, URL or
    extension it may not touch (`PermissionException`), more memory than the limit sized to the
    frame lets it build (`OutOfMemoryException`), a construct DuckDB does not implement, such as an
    outer join on a correlated column (`NotSupportedError`), and an extension DuckDB would install
    on the fly, refused with the bare `duckdb.Error`. Every DuckDB error derives from that one, so
    only the exact class counts: an `InternalException` or an `IOException` fails inside DuckDB and
    stays a 500, and so does DuckDB running out of memory for a request without a clause. DuckDB is
    optional, and an error of its can only be raised once it has been imported.
    """
    status = failure_status(e)
    if status in (400, 404):
        return status
    duckdb = sys.modules.get("duckdb")
    if duckdb is None:
        return None
    if isinstance(e, (duckdb.ProgrammingError, duckdb.DataError)):
        return 400
    clause_given = any(getattr(request, name, None) for name in ("sql", "sql_values"))
    if clause_given and (
        isinstance(e, (duckdb.PermissionException, duckdb.OutOfMemoryException, duckdb.NotSupportedError))
        or type(e) is duckdb.Error
    ):
        return 400
    return None


def _is_caller_refusal(e: Exception, request: BaseModel) -> bool:
    """Tell whether a failure is the request's own, which the caller can rephrase, see `_caller_refusal_status`."""
    return _caller_refusal_status(e, request) is not None


class AuthAnswer(TypedDict):
    """Whether the credentials of a provider and network are present and accepted."""

    provider: str
    network: str
    auth: bool
    configured: bool
    # null where the probe could not tell (no network, a timeout, a rate limit, an outage): unknown, not rejected
    valid: bool | None


# how long the answer of a probe is reused, in seconds: the provider is probed at most once in this time per network
_AUTH_PROBE_TTL_SECONDS = 60.0
# the same for an answer that could not be told (`None`): short, so that an outage that ends is not reported for long
_AUTH_PROBE_UNKNOWN_TTL_SECONDS = 5.0


class _ProbeEntry:
    """The last answer of one probe, and until when it holds."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.valid: bool | None = None
        self.expires = float("-inf")


class _ProbeCache:
    """The answers of the credential probes, one per network, each reused for a short time.

    Every caller of `get_auth` (the REST route, the MCP tool, the CLI) would otherwise make the provider
    answer a request of its own. The key is the request class of the network, which every spelling of its
    provider and name resolves to, and which the caller resolves (and so refuses an unknown name) before it
    comes here: the keys are as many as the networks. The answer is the probe's `valid` alone: the credential
    is neither a key nor a value here. Each key has its own lock, held while its probe runs, so callers
    arriving meanwhile wait for that answer and reuse it, and probes of different networks do not wait
    for each other.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._guard = threading.Lock()
        self._entries: dict[Hashable, _ProbeEntry] = {}

    def get(self, key: Hashable, probe: Callable[[], bool | None]) -> bool | None:
        """Return the answer of `probe` for `key`, calling it only where the last answer has expired."""
        with self._guard:
            entry = self._entries.setdefault(key, _ProbeEntry())
        with entry.lock:
            if self._clock() < entry.expires:
                return entry.valid
            valid = probe()
            ttl = _AUTH_PROBE_UNKNOWN_TTL_SECONDS if valid is None else _AUTH_PROBE_TTL_SECONDS
            entry.valid, entry.expires = valid, self._clock() + ttl
            return valid

    def clear(self) -> None:
        """Forget every answer, so that the next call probes."""
        with self._guard:
            self._entries.clear()


_auth_probes = _ProbeCache()


def get_auth(api: type[TimeseriesRequest] | StandaloneRequest, provider: str, network: str) -> AuthAnswer:
    """Check the credentials of one network, probing its provider where they are configured.

    The one place a credential is checked against its provider: `/api/coverage` and `about coverage`
    do not probe (GH-2564), so this answers `valid` for the one network asked about, as a single
    attempt that gives up after `PROBE_TIMEOUT_SECONDS`. A network that needs none is `configured`
    and `valid` without a request; one whose credentials are missing is not `valid`, as a probe
    cannot be performed without them; one that is configured is `valid` as the probe tells, `None`
    when it could not (`Wetterdienst.is_valid`).

    The provider is probed at most once a minute per network and server process: a call within that time
    gets the answer of the one before, whatever the spelling of the provider and network, and simultaneous
    calls share one probe. An answer of `None` is kept for a few seconds only. The credentials are read
    on every probe, so a changed or corrected one is reflected within a minute (a rejection is kept for up
    to 60 s, an unknown answer for 5 s); a revoked one that a provider's own cache (`metno/frost`,
    `aemet/observation`) still reads as accepted, within two minutes.
    """
    from wetterdienst.api import Wetterdienst  # noqa: PLC0415

    metadata = getattr(api, "metadata", None)
    requires_auth = metadata.auth if metadata is not None else False
    configured = Wetterdienst.is_configured(api) if requires_auth else True
    if not requires_auth:
        valid = True
    elif not configured:
        valid = False
    else:
        valid = _auth_probes.get(api, lambda: Wetterdienst.is_valid(api))
    return AuthAnswer(provider=provider, network=network, auth=requires_auth, configured=configured, valid=valid)


class GlossaryEntry(TypedDict):
    """One canonical parameter: what it measures and which unit it is returned in."""

    name: str
    unit_type: UnitType
    unit: str
    unit_symbol: str
    description: str


def get_glossary(
    parameter: str | None = None,
    unit_type: UnitType | None = None,
    limit: int | None = None,
    options: Options | None = None,
) -> list[GlossaryEntry]:
    """Return the canonical parameter vocabulary, optionally filtered.

    `coverage` answers which parameters a given provider offers, with the unit each comes back in for a
    request that passes no options (the environment's targets, as here); this answers what any of them means,
    for every provider, and the unit under the `unit_targets` of the `options` given, which `coverage` takes
    no option for.

    `parameter` matches as a substring, since the useful question over several hundred names is usually
    "everything about radiation" rather than one exact name. An exact name deliberately does *not*
    short-circuit to a single entry: `humidity_relative` is both a parameter and the prefix of
    `humidity_relative_max` and `humidity_relative_min`, and hiding those would be the more
    surprising behaviour. Use `limit` to bound the result instead.

    The unit reported is the one a values request would actually return, so the `unit_targets` option is
    honoured -- reporting the built-in default while `values` hands back Fahrenheit would make this
    worse than saying nothing.
    """
    from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS  # noqa: PLC0415
    from wetterdienst.model.unit import UnitConverter  # noqa: PLC0415

    options = options or Options()
    unit_converter = UnitConverter()
    unit_converter.update_targets(options.unit_targets)
    needle = parameter.strip().lower() if parameter else None
    needles = [needle] if needle else []
    if needle and needle in PARAMETER_ALIASES and needle not in PARAMETERS:
        # the old name of a renamed parameter: it finds the entries of the new name as well as those that hold the
        # old one as a substring
        use_alias(needle, PARAMETER_ALIASES[needle])
        needles.append(PARAMETER_ALIASES[needle].new)
    entries: list[GlossaryEntry] = []
    for canonical in PARAMETER_TABLE:
        if needles and not any(n in canonical.name for n in needles):
            continue
        if unit_type and canonical.unit_type != unit_type:
            continue
        target = unit_converter.targets[canonical.unit_type]
        entries.append(
            GlossaryEntry(
                name=canonical.name,
                unit_type=canonical.unit_type,
                unit=target.name,
                unit_symbol=target.symbol,
                description=canonical.description,
            ),
        )
        if limit is not None and len(entries) >= limit:
            break
    return entries


def get_issues(
    api: type,
    request: IssuesRequest,
    settings: Settings,
) -> list[str]:
    """Return available issue datetimes as UTC ISO strings for provider/network/station.

    Supported: DWD MOSMIX (MOSMIX_L single-station), DWD DMO (ICON single-station) and DWD SWSMOS.
    One SWSMOS run file holds every road station, so its runs are the same whatever the station.

    The DMO product and lead time are passed through rather than left to chance: a run exists for a
    product, and this listed one product's directory whatever the caller went on to ask for, so it
    named issues the values path then rejected (GH-1956). `station_group` is not passed because no
    path here can build anything but a single-station request.
    """
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest  # noqa: PLC0415

    dmo_only = {"dataset": request.dataset, "lead_time": request.lead_time}
    given = sorted(name for name, value in dmo_only.items() if value is not None)
    if given and issubclass(api, (DwdMosmixRequest, DwdSwsmosRequest)):
        # named rather than ignored: silently answering a different question than the one asked is
        # the fault this whole path is being fixed for
        msg = f"{', '.join(given)} applies to DWD DMO only (got {api.__name__})"
        raise InvalidEnumerationError(msg)
    if issubclass(api, DwdMosmixRequest):
        issues = DwdMosmixRequest.available_issues(request.station, settings)
    elif issubclass(api, DwdDmoRequest):
        issues = DwdDmoRequest.available_issues(
            request.station,
            settings,
            **{name: value for name, value in dmo_only.items() if value is not None},
        )
    elif issubclass(api, DwdSwsmosRequest):
        issues = DwdSwsmosRequest.available_issues(settings)
    else:
        msg = f"Issue listing is only supported for DWD MOSMIX, DMO and SWSMOS (got {api.__name__})"
        raise NotImplementedError(msg)

    return [format_timestamp(issue) for issue in issues]


def resolve_network(provider: str, network: str) -> type[TimeseriesRequest] | StandaloneRequest:
    """Resolve the network a UI is asked about, a standalone one (dwd/radar, dwd/alerts) too.

    `Wetterdienst.resolve` is for the timeseries networks and `resolve_standalone` for the other two.
    The surfaces take both kinds by name -- `coverage` lists them, `auth` and `issues` answer for them, and
    the timeseries commands refuse them (`check_timeseries_api`) -- so this picks the one that applies.

    Raises:
        ApiNotFoundError: the provider or network is not in the registry.

    """
    from wetterdienst.api import Wetterdienst  # noqa: PLC0415

    if Wetterdienst.is_standalone(provider, network):
        return Wetterdienst.resolve_standalone(provider, network)
    return Wetterdienst.resolve(provider, network)


def check_timeseries_api(
    api: type[TimeseriesRequest] | StandaloneRequest,
    provider: str,
    network: str,
    *,
    history: bool = False,
) -> type[TimeseriesRequest]:
    """Refuse a network the timeseries commands cannot serve, before any request is built.

    A standalone network (dwd/radar, dwd/alerts) has no metadata model, so there are no parameters to
    resolve: `ApiNotFoundError`, which the callers word with where the networks are listed. With
    `history`, a network without station history is refused with `NotImplementedError` before its
    station catalogue is downloaded to find that out.

    Returns:
        The class, which is a timeseries request now.

    """
    if not issubclass(api, TimeseriesRequest):
        msg = f"Provider '{provider}' and network '{network}' have no stations or values to request."
        raise ApiNotFoundError(msg)
    if history and not getattr(api, "_history", None):
        msg = f"History not implemented for {api.__name__}"
        raise NotImplementedError(msg)
    return api


def overlay_options(base: Options, given: Mapping[str, Any]) -> Options:
    """Lay the options a caller named over `base`, the options the environment sets.

    A mapping the caller gave -- `unit_targets`, the per-parameter radii -- is merged into the
    base's, an entry it gives winning; every other option replaces the base's. That is what the
    REST API and the command line document, and what `Settings(**given)` did by merging the
    environment into the mappings it was given. It is done here in the open: `Options(**given)`
    would merge whatever the environment sets into any mapping, the caller's or not, and the base
    has read the environment already.

    `Options.replace` is not used because it replaces a mapping wholesale, where the surfaces
    document a merge, and because it builds quietly: this goes through `options_from_mapping`, which
    gives the notices a build gives (`drop_nulls` ignored in the wide shape, a radius for a parameter
    never interpolated), as an option given on the command line or in a query always has.

    Raises:
        ValidationError: Where an option is invalid, located by the option's name.

    """
    dumped = base.model_dump()
    # the mode of a check is named by `plausibility_<check>` and laid over the checks the base has, as the mapping of
    # one named `plausibility` is: a check not named keeps its mode (GH-3676)
    checks = {PLAUSIBILITY_OPTIONS[name]: value for name, value in given.items() if name in PLAUSIBILITY_OPTIONS}
    given = {name: value for name, value in given.items() if name not in PLAUSIBILITY_OPTIONS}
    # a bare mode is that mode for every check, and a check named beside it wins
    every = given.get("plausibility")
    if isinstance(every, str):
        given = {**given, "plausibility": dict.fromkeys(CHECKS, every)}
    if checks:
        given = {**given, "plausibility": {**given.get("plausibility", {}), **checks}}
    merged = {name: {**dumped[name], **value} if isinstance(value, Mapping) else value for name, value in given.items()}
    return options_from_mapping(merged, base)


def _get_stations_request(
    api: type[TimeseriesRequest],
    request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest | HistoryRequest,
    timestamp: str | None,
    settings: Settings,
    options: Options | None = None,
) -> TimeseriesRequest:
    """Create a request object for stations, with the host's `settings` and the `options` of the request.

    Options left out are the ones `settings` carries, as a request built without any takes them.
    """
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest  # noqa: PLC0415

    # TODO: move this into Request core
    start_date, end_date = None, None
    if timestamp:
        if "/" in timestamp:
            if timestamp.count("/") >= 2:
                msg = "Invalid ISO 8601 time interval"
                raise InvalidTimeIntervalError(msg)
            start_string, end_string = timestamp.split("/")
            # the window opens with the span the first half names and closes with the second's
            start_date, _ = parse_date_window(start_string)
            _, end_date = parse_date_window(end_string)
        else:
            start_date, end_date = parse_date_window(timestamp)

    parameters = parse_parameters(request.parameters, api.metadata)
    if not parameters:
        # an unknown parameter raised above; this is a request that names none at all, raised here
        # rather than left to the request, which would only see the empty list it resolved to
        msg = f"No valid parameters could be parsed from {request.parameters!r} for {api.__name__}"
        raise NoParametersFoundError(msg)

    # a stations request lists the stations of such a dataset without a window; the others need one
    if not isinstance(request, StationsRequest):
        try:
            require_window(parameters, start_date, end_date)
        except DateRequiredError as e:
            # a history request takes no window at all, so there is no option to tell its caller to pass
            if isinstance(request, HistoryRequest):
                msg = "Start and end date required for single period datasets"
                raise StartDateEndDateError(msg) from e
            raise

    kwargs: dict[str, Any] = {
        # a dataset stays one entry, which the request reads as all its parameters: it then knows that none of them was
        # named, which `parameter-without-rows` is told by
        "parameters": whole_datasets_kept(request.parameters, api.metadata),
        "start": start_date,
        "end": end_date,
        # every request takes periods and validates them against what its datasets publish, so pass
        # them through rather than deciding here which provider is allowed to hear about them
        "periods": getattr(request, "periods", None),
    }

    if (
        issubclass(api, (DwdMosmixRequest, DwdDmoRequest, DwdSwsmosRequest))
        and (issue := getattr(request, "issue", None)) is not None
    ):
        kwargs["issue"] = issue
    if issubclass(api, DwdDmoRequest) and (lead_time := getattr(request, "lead_time", None)) is not None:
        kwargs["lead_time"] = lead_time

    return api(**kwargs, settings=settings, options=options)


def get_stations(
    api: type[TimeseriesRequest],
    request: StationsRequest | ValuesRequest | HistoryRequest,
    timestamp: str | None,
    settings: Settings,
    options: Options | None = None,
) -> StationsResult:
    """Get stations based on request, by the one selection its model lets it make."""
    r = _get_stations_request(api=api, request=request, timestamp=timestamp, settings=settings, options=options)

    if getattr(request, "all", False):
        return r.all()

    if request.stations:
        return r.filter_by_station_id(request.stations)

    name: str | None = getattr(request, "name", None)
    if name:
        # the rank asked for, else the default of what is asked: the best few of a listing, the best
        # match of a fetch, which is the one `filter_by_name` has too (GH-2635)
        default_rank = DEFAULT_NAME_RANK_LISTING if isinstance(request, StationsRequest) else DEFAULT_NAME_RANK
        name_rank: int = getattr(request, "rank", None) or default_rank
        # a request for a window matches the name among the stations that have a record in it, which
        # `filter_by_name` does of its own accord, so that the best match is not one that closed long
        # ago while a current station of the same name has the readings, and the best few of a listing
        # are not ones that closed either (GH-3026)
        return r.filter_by_name(name, rank=name_rank, threshold=getattr(request, "name_threshold", 0.8))

    latitude: float | None = getattr(request, "latitude", None)
    longitude: float | None = getattr(request, "longitude", None)
    rank: int | None = getattr(request, "rank", None)
    distance: float | None = getattr(request, "distance", None)

    if latitude is not None and longitude is not None and rank is not None:
        return r.filter_by_rank(latlon=(latitude, longitude), rank=rank)

    if latitude is not None and longitude is not None and distance is not None:
        return r.filter_by_distance(latlon=(latitude, longitude), distance=distance)

    left: float | None = getattr(request, "left", None)
    bottom: float | None = getattr(request, "bottom", None)
    right: float | None = getattr(request, "right", None)
    top: float | None = getattr(request, "top", None)
    if left is not None and bottom is not None and right is not None and top is not None:
        return r.filter_by_bbox(left=left, bottom=bottom, right=right, top=top)

    sql: str | None = getattr(request, "sql", None)
    if sql:
        return r.filter_by_sql(sql)

    # not reached: the request models refuse a request that selects no stations, and say why
    msg = f"{type(request).__name__} selects no stations"
    raise AssertionError(msg)


def limit_stations_to_window(stations: StationsResult) -> StationsResult:
    """Keep the rows of a stations *listing* whose record overlaps the window the request names.

    `stations` takes a `timestamp` as `values` does, and a window is of no use to a listing unless it
    leaves out the stations that cannot have a reading in it -- a nearest-three listing for a day this
    year included stations that closed a century ago. The rule is the core's (`limit_to_window` of
    `wetterdienst.model.request`, which `filter_by_name` applies as well): a row is left out when its
    `start_timestamp` is after the window, or its `end_timestamp` is before the window by more than
    the buffer: the `station_window_end_buffer` option of the request in days, else the default of its
    resolution (two days, 62 for monthly, 732 for annual). Without a window the listing is returned as it is.

    Applied before `limit_stations_to_rank`, so that the N closest are the N closest of those that
    overlap, and before a `name` is matched, in a listing and in `values` alike (`get_stations`), so that
    the best match is one that can have a reading in the window (GH-3026). A `values` request that names
    stations by id, or by distance, does not use it: it walks the stations and reads what each holds
    inside the window, which is the better judge than an index.
    """
    return replace(
        stations,
        df=limit_to_window(stations.df, stations.start, stations.end, stations.options.station_window_end_buffer),
    )


def limit_stations_to_rank(stations: StationsResult) -> StationsResult:
    """Trim a rank-filtered stations *listing* to the requested ``rank`` stations.

    ``filter_by_rank`` intentionally keeps *all* stations with a position (distance-sorted) in ``df`` because the real
    ``rank`` limit is applied later, during value collection: that walk takes the ``rank`` closest
    stations that actually carry data -- as sparsely as the ``skip_empty`` / ``skip_threshold`` /
    ``skip_criteria`` options allow -- and exposes them via ``ValuesResult.df_stations``.

    A plain stations listing does no value collection, so it cannot apply that data-aware selection --
    but returning every station (e.g. 1284 for DWD) when the caller asked for the N closest is both
    surprising and huge. Here we slice to the ``rank`` closest *by distance* (data availability
    unknown at listing time); leave other filters untouched. The unit is the station, not the row: a
    station has a row for every dataset asked for, so ``rank=2`` with two datasets keeps the rows of
    the two closest stations, not the two rows of the closest one.
    """
    from wetterdienst.model.result import StationsFilter  # noqa: PLC0415

    if stations._stations_filter is StationsFilter.BY_RANK and stations._rank:  # noqa: SLF001
        df = stations.df
        closest = df.get_column("station_id").unique(maintain_order=True).head(stations._rank)  # noqa: SLF001
        return replace(stations, df=df.filter(pl.col("station_id").is_in(closest.to_list())))
    return stations


def get_values(
    api: type[TimeseriesRequest],
    request: ValuesRequest,
    settings: Settings,
    options: Options | None = None,
    check: Callable[[StationsResult], None] | None = None,
) -> ValuesResult:
    """Get values based on request.

    `check` is given the stations selected before any value is downloaded, and refuses the request by raising:
    the limits of the REST API are applied there (GH-3065).
    """
    stations_ = get_stations(
        api=api,
        request=request,
        timestamp=request.timestamp,
        settings=settings,
        options=options,
    )
    if check is not None:
        check(stations_)

    # TODO: Add stream-based processing here.
    # a `ValueError` from the values -- a provider refusing a request it cannot serve as phrased
    # (`ParameterNotCarriedError`), or a parse failure -- propagates: reporting it is the caller's
    values_ = stations_.values().all()

    if values_.df.is_empty():
        # nothing to filter, and nothing more to say about it. An empty window is the caller's
        # news to report: the CLI says so once on stderr and exits 0, the REST API hands the empty result
        # back, and `.all()` has already logged it on the way here. Saying it again here made the
        # CLI print the same sentence twice
        return values_

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_ = values_.filtered_by_sql(request.sql_values)

    return values_


def get_interpolate(
    api: type[TimeseriesRequest],
    request: InterpolationRequest,
    settings: Settings,
    options: Options | None = None,
    check: Callable[[TimeseriesRequest], None] | None = None,
    check_reach: Callable[[int], None] | None = None,
) -> InterpolatedValuesResult:
    """Get interpolated values based on request.

    `check` is given the request before any value is downloaded, and `check_reach` the number of stations within
    the radius of the request, once the stations are ranked against the point and before any value is downloaded.
    """
    r = _get_stations_request(api=api, request=request, timestamp=request.timestamp, settings=settings, options=options)
    r._check_reach = check_reach  # noqa: SLF001
    if check is not None:
        check(r)

    if request.latitude is not None and request.longitude is not None:
        values_ = r.interpolate((request.latitude, request.longitude), elevation=request.elevation)
    elif request.station:
        values_ = r.interpolate_by_station_id(request.station, elevation=request.elevation)
    else:
        # not reached: the request model refuses a request with neither a point nor a station
        msg = f"{type(request).__name__} gives neither a point nor a station"
        raise AssertionError(msg)

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_ = values_.filtered_by_sql(request.sql_values)

    return values_


def get_summarize(
    api: type[TimeseriesRequest],
    request: SummaryRequest,
    settings: Settings,
    options: Options | None = None,
    check: Callable[[TimeseriesRequest], None] | None = None,
    check_reach: Callable[[int], None] | None = None,
) -> SummarizedValuesResult:
    """Get summarized values based on request, with the checks of `get_interpolate`."""
    r = _get_stations_request(api=api, request=request, timestamp=request.timestamp, settings=settings, options=options)
    r._check_reach = check_reach  # noqa: SLF001
    if check is not None:
        check(r)

    if request.latitude is not None and request.longitude is not None:
        values_ = r.summarize((request.latitude, request.longitude), elevation=request.elevation)
    elif request.station:
        values_ = r.summarize_by_station_id(request.station, elevation=request.elevation)
    else:
        # not reached: the request model refuses a request with neither a point nor a station
        msg = f"{type(request).__name__} gives neither a point nor a station"
        raise AssertionError(msg)

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_ = values_.filtered_by_sql(request.sql_values)

    return values_


class StripesSeries(BaseModel):
    """What a series of climate stripes is of: the station, the parameter and the unit of its values."""

    model_config = {"extra": "forbid"}

    station: Mapping[str, Any]
    resolution: str
    dataset: str
    parameter: str
    # the unit `value` comes in, named as `/api/values` names one in its settings' `unit_targets`;
    # the server's `WD_TS_CONVERT_UNITS` and `WD_TS_UNIT_TARGETS` set it (GH-2372)
    unit: str


class StripesData(BaseModel):
    """Climate stripes data: what the series is of, and its values."""

    model_config = {"extra": "forbid", "arbitrary_types_allowed": True}

    series: StripesSeries
    df: pl.DataFrame


# Type definitions for CLIMATE_STRIPES_CONFIG
StripesKind = Literal["temperature", "precipitation"]


class StripesStationsRequest(_RefusesRenamedParameters):
    """Request model for listing the stations climate stripes are made for, forbidding other parameters (GH-2479)."""

    model_config = {"extra": "forbid"}

    kind: Annotated[
        StripesKind,
        Field(description="temperature (annual mean air temperature) or precipitation (annual amount)."),
    ]
    active: Annotated[
        bool, Field(description="Only the stations that still report, i.e. have data in the recent period.")
    ] = True
    format: Annotated[
        Literal["json", "geojson", "csv"],
        Field(description="Output format: json, geojson (a feature collection) or csv."),
    ] = "json"
    pretty: _PrettyField = False


class StripesRequest(_RefusesRenamedParameters):
    """The station and the years climate stripes are made for, shared by their values and their image.

    Like the other request models, it states its rules once for the CLI, the REST API and MCP, which
    each checked them by hand before, and answered a refusal in a shape of their own (GH-2060).
    """

    model_config = {"extra": "forbid"}

    kind: Annotated[
        StripesKind,
        Field(description="temperature (annual mean air temperature) or precipitation (annual amount)."),
    ]
    station: Annotated[str | None, Field(description="Station id, e.g. '01048'; give this or name.")] = None
    name: Annotated[
        str | None,
        Field(description="Station name, matched fuzzily, e.g. 'Hamburg Fuhlsbüttel'; give this or station."),
    ] = None
    # as for stations and values, and the CLI's --name-threshold
    name_threshold: _NameThresholdField = 0.8
    start_year: Annotated[int | None, Field(description="First year. Default: the station's first.")] = None
    end_year: Annotated[
        int | None,
        Field(description="Last year, after start_year. Default: the station's last."),
    ] = None

    @model_validator(mode="after")
    def check_station_and_years(self) -> StripesRequest:
        """Check exactly one of station or name is given, and a year range that ends after it starts."""
        errors = _check_one_of(self, (("station",), ("name",)))
        if self.start_year is not None and self.end_year is not None and self.end_year <= self.start_year:
            message = f"Input should be greater than start_year ({self.start_year})"
            errors.append(
                _rule_error(
                    "greater_than_field",
                    message,
                    ("end_year",),
                    self.end_year,
                    field="start_year",
                    gt=self.start_year,
                ),
            )
        _raise_rule_errors(self, errors)
        return self


class StripesValuesRequest(StripesRequest):
    """A request for the values climate stripes are made of."""

    format: Annotated[Literal["json", "csv"], Field(description="Output format.")] = "json"
    pretty: _PrettyField = False


class StripesImageRequest(StripesRequest):
    """A request for a climate stripes image."""

    show_title: Annotated[bool, Field(description="Show the station name.")] = True
    show_years: Annotated[bool, Field(description="Show the first and last year.")] = True
    show_data_availability: Annotated[bool, Field(description="Mark the years without data.")] = True
    format: Annotated[Literal["png", "jpg", "svg", "pdf"], Field(description="Image format.")] = "png"
    dpi: Annotated[int, Field(gt=0, description="Resolution in dots per inch.")] = 300


class StripesConfigItem(TypedDict):
    """Configuration item for climate stripes."""

    request: Callable[..., DwdObservationRequest]
    color_map: str


class StripesConfig(TypedDict):
    """Configuration for climate stripes by kind."""

    temperature: StripesConfigItem
    precipitation: StripesConfigItem


def _get_stripes_options() -> Options:
    """Give the options the stripes read a station's values with.

    `_get_stripes_data` takes the `value` column of a long frame and draws the gaps in a station's
    record itself. The rest comes from the environment as for any request, but `WD_TS_SHAPE=wide`
    left no `value` column (`ColumnNotFoundError`), and `WD_TS_SKIP_EMPTY=true` dropped a station
    with gaps, leaving no years to draw (GH-2348). Those two are fixed here, as arguments, which
    outrank the environment's variables, a malformed one included.
    """
    return Options(shape="long", skip_empty=False)


def _get_stripes_temperature_request(periods: Period = Period.HISTORICAL) -> DwdObservationRequest:
    """Give the request the temperature stripes list their stations and read their values with."""
    return DwdObservationRequest(
        parameters=[("annual", "climate_summary", "temperature_air_mean_2m")],
        periods=periods,
        options=_get_stripes_options(),
    )


def _get_stripes_precipitation_request(periods: Period = Period.HISTORICAL) -> DwdObservationRequest:
    """Give the request the precipitation stripes list their stations and read their values with."""
    return DwdObservationRequest(
        parameters=[("annual", "precipitation_more", "precipitation_amount")],
        periods=periods,
        options=_get_stripes_options(),
    )


CLIMATE_STRIPES_CONFIG: StripesConfig = {
    "temperature": {
        "request": _get_stripes_temperature_request,
        "color_map": "RdBu",
    },
    "precipitation": {
        "request": _get_stripes_precipitation_request,
        # reversed, as `value_scaled` puts the wettest year at 0: brown for dry, teal for wet (GH-2063)
        "color_map": "BrBG_r",
    },
}


def _get_stripes_stations(kind: StripesKind, *, active: bool = True) -> StationsResult:
    request = CLIMATE_STRIPES_CONFIG[kind]["request"]
    stations = request(Period.HISTORICAL).all()
    if active:
        station_ids_active = request(Period.RECENT).all().df.select("station_id")
        stations = replace(stations, df=stations.df.join(station_ids_active, on="station_id"))
    return stations


def _get_stripes_data(stripes: StripesRequest) -> StripesData:
    """Get stripes data for station in Germany, for a request its model has checked.

    Returns StripesData with metadata and dataframe.
    """
    kind, start_year, end_year = stripes.kind, stripes.start_year, stripes.end_year
    request = CLIMATE_STRIPES_CONFIG[kind]["request"](Period.HISTORICAL)

    if stripes.station:
        stations = request.filter_by_station_id(stripes.station)
    elif stripes.name:
        stations = request.filter_by_name(stripes.name, threshold=stripes.name_threshold)
    else:
        # not reached: the request model refuses a request with neither
        msg = f"{type(stripes).__name__} gives neither a station nor a name"
        raise AssertionError(msg)

    # asked of the list rather than caught from indexing it, so an `IndexError` from building the
    # list is not taken for an unknown station
    found = stations.to_dict()["stations"]
    if not found:
        parameter = "station_id" if stripes.station else "name"
        msg = f"No station with a {parameter} similar to '{stripes.station or stripes.name}' found"
        raise StationNotFoundError(msg)
    station = found[0]

    df = stations.values().all().df.sort("timestamp")
    df = df.set_sorted("timestamp")
    df = df.select("timestamp", "value")
    # a station that returns no rows has no first and last year to upsample between (polars raises
    # `ComputeError`); left empty, it is refused below as having data for no year (GH-2369)
    if not df.is_empty():
        df = df.upsample("timestamp", every="1y")
    recorded = df.filter(pl.col("value").is_not_null()).get_column("timestamp").dt.year()
    if start_year is not None:
        df = df.filter(pl.col("timestamp").dt.year().ge(start_year))
    if end_year is not None:
        df = df.filter(pl.col("timestamp").dt.year().le(end_year))

    # a range holding no year with data drew empty stripes, and one holding a single year stripes of
    # one colour
    years_with_data = df.filter(pl.col("value").is_not_null()).get_column("timestamp")
    if len(years_with_data) < 2:
        record = f"from {recorded.min()} to {recorded.max()}" if len(recorded) else "for no year"
        msg = (
            f"At least two years with data are required to create climate stripes; station "
            f"{station['station_id']} has data {record}"
        )
        raise NotEnoughDataError(msg)
    # from the first year with data to the last: a start or end year falling in a gap of the record
    # would otherwise label the stripes with a year none of them shows
    df = df.filter(pl.col("timestamp").is_between(years_with_data.min(), years_with_data.max()))

    # scaled over the years asked for, so they span the whole colour map rather than the part the
    # station's whole record would leave them; 0 is the highest value, 1 the lowest. Years all of one
    # value take the middle of the map rather than dividing by a range of zero
    value, lowest, highest = pl.col("value"), pl.col("value").min(), pl.col("value").max()
    df = df.with_columns(
        pl.when(value.is_null())
        .then(None)
        .when(highest == lowest)
        .then(0.5)
        .otherwise(1 - (value - lowest) / (highest - lowest))
        .alias("value_scaled"),
        pl.when(value.is_not_null()).then(-0.02).otherwise(None).alias("availability"),
    )

    # named by the one parameter the values were read for, as is their unit: the target of its
    # quantity where they were converted, the unit the source publishes them in where not
    from wetterdienst.core.util import _values_unit  # noqa: PLC0415

    (parameter_model,) = stations.parameters
    series = StripesSeries(
        station=station,
        resolution=parameter_model.dataset.resolution.name,
        dataset=parameter_model.dataset.name,
        parameter=parameter_model.name,
        unit=_values_unit(
            parameter_model,
            stations.values().unit_converter,
            convert_units=stations.options.convert_units,
        ),
    )

    return StripesData(series=series, df=df)


def _require_plotting() -> ModuleType:
    """Give plotly's graph objects, or raise the `MissingDependencyError` that says to install the `plotting` extra.

    Asked before a station's record is downloaded, so that a server without the extra refuses at once (GH-3581).
    """
    return import_optional("plotly.graph_objects", "Plotting warming stripes", extra="plotting")


def _plot_stripes(stripes: StripesImageRequest) -> go.Figure:
    """Create warming stripes for station in Germany, for a request its model has checked."""
    _require_plotting()
    return _draw_stripes(_get_stripes_data(stripes), stripes)


def _draw_stripes(stripes_data: StripesData, stripes: StripesImageRequest) -> go.Figure:
    """Draw the warming stripes of data `_get_stripes_data` has read, so that the caller can tell whose they are.

    Code similar to: https://www.s4f-freiburg.de/temperaturstreifen/
    """
    go = _require_plotting()

    kind = stripes.kind
    show_title, show_years, show_data_availability = (
        stripes.show_title,
        stripes.show_years,
        stripes.show_data_availability,
    )

    df = stripes_data.df
    station_dict = stripes_data.series.station
    cmap = CLIMATE_STRIPES_CONFIG[kind]["color_map"]

    df_without_nulls = df.drop_nulls("value")

    fig = go.Figure()

    # Add bar trace
    fig.add_trace(
        go.Bar(
            x=df_without_nulls.get_column("timestamp").dt.year(),
            y=[1.0] * len(df_without_nulls),
            marker={"color": df_without_nulls.get_column("value_scaled"), "colorscale": cmap, "cmin": 0, "cmax": 1},
            width=1.0,
        ),
    )

    # Add scatter trace for data availability
    if show_data_availability:
        fig.add_trace(
            go.Scatter(
                x=df.get_column("timestamp").dt.year(),
                y=df.get_column("availability"),
                mode="lines",
                marker={"color": "gold", "size": 5},
                line={"color": "gold"},
            ),
        )
        fig.add_annotation(
            x=df.get_column("timestamp").dt.year().min(),
            xanchor="left",
            y=-0.05,
            text="data availability",
            showarrow=False,
            align="right",
            font={"color": "gold"},
        )
    # Add source text
    fig.add_annotation(
        x=0.5,
        y=-0.05,
        text="Source: Deutscher Wetterdienst",
        showarrow=False,
        xref="paper",
        yref="paper",
    )
    if show_title:
        fig.update_layout(
            title=f"Climate stripes ({kind}) for {station_dict['name']}, Germany ({station_dict['station_id']})",
        )
    if show_years:
        fig.add_annotation(
            x=0.05,
            y=-0.05,
            text=str(df.get_column("timestamp").dt.year().min()),
            showarrow=False,
            xref="paper",
            yref="paper",
            xanchor="right",
        )
        fig.add_annotation(
            x=0.95,
            y=-0.05,
            text=str(df.get_column("timestamp").dt.year().max()),
            showarrow=False,
            xref="paper",
            yref="paper",
            xanchor="left",
        )
    fig.update_layout(
        plot_bgcolor="white",
        xaxis={
            "showticklabels": False,
        },
        yaxis={"range": [None, 1], "showticklabels": False},
        showlegend=False,
        margin={"l": 10, "r": 10, "t": 30, "b": 30},
    )
    return fig


def set_logging_level(*, debug: bool) -> None:
    """Set logging level for the wetterdienst package.

    ``debug`` sets the level of the logger ``wetterdienst``, the parent of every logger of the package, to DEBUG, so
    the debug lines of the models and the providers are shown with it and not those of this module alone (GH-3388).
    Without it the level is left as it is: ``setup_logging`` has put the root at INFO, and a level that the host
    configured is not overwritten. The handlers and the loggers of other packages are left alone either way.
    """
    if debug:
        logging.getLogger("wetterdienst").setLevel(logging.DEBUG)
