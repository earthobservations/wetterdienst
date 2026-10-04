# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core UI utilities for the wetterdienst package."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

import polars as pl
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError

# pydantic refuses typing.TypedDict as a response model on Python below 3.12, and GlossaryEntry
# is one; model/result.py imports it from here for the same reason
from typing_extensions import LiteralString, TypedDict

from wetterdienst.exceptions import (
    InvalidEnumerationError,
    InvalidTimeIntervalError,
    NoParametersFoundError,
    NotEnoughDataError,
    StartDateEndDateError,
    StationNotFoundError,
)
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.unit_type import UnitType  # noqa: TC001, needed at runtime by FastAPI
from wetterdienst.model.metadata import parse_parameters
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.settings import SkipThreshold
from wetterdienst.util.datetime import parse_date_window
from wetterdienst.util.ui import read_list

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Set as AbstractSet

    import plotly.graph_objs as go

    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import (
        InterpolatedValuesResult,
        StationsResult,
        SummarizedValuesResult,
        ValuesResult,
    )
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

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
        "requested datasets are not published under is rejected. Inferred from the date when "
        "omitted, else every period those datasets publish.",
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
_AllField = Annotated[bool | None, Field(description="Return all stations, ignoring the station/name/geo filters.")]
_StationIdsField = Annotated[
    list[str] | None,
    Field(description="One or more station ids to query, e.g. '01048' or '01048,04411'."),
]
_StationIdField = Annotated[str, Field(description="Station id used as the reference location, e.g. '01048'.")]
_StationIdOptField = Annotated[
    str | None,
    Field(description="Station id used as the reference location, e.g. '01048'."),
]
_NameField = Annotated[
    str | None,
    Field(description="Filter stations by name using fuzzy matching, e.g. 'Hamburg Fuhlsbüttel'."),
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
_RankField = Annotated[
    int | None,
    Field(
        ge=1,
        description="With latitude/longitude, the N closest stations; with name, at most N matches (default 5).",
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
    Field(description="SQL WHERE clause applied to the station metadata, e.g. \"region='Sachsen'\"."),
]
_SqlValuesField = Annotated[
    str | None,
    Field(description='SQL WHERE clause applied to the values, e.g. "temperature_air_max_2m < 2.0".'),
]
_WithMetadataField = Annotated[bool, Field(description="Include the provider-metadata block in the output.")]
_WithStationsField = Annotated[bool, Field(description="Include the queried stations' metadata block in the output.")]
_FormatField = Annotated[
    Literal["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"],
    Field(description="Output format: data (json, geojson, csv) or a rendered chart (html, png, jpg, webp, svg, pdf)."),
]
_PrettyField = Annotated[bool, Field(description="Pretty-print JSON/GeoJSON output.")]
_DebugField = Annotated[bool, Field(description="Enable debug logging.")]
_WidthField = Annotated[int | None, Field(gt=0, description="Width of the rendered chart image in pixels.")]
_HeightField = Annotated[int | None, Field(gt=0, description="Height of the rendered chart image in pixels.")]
_ScaleField = Annotated[float | None, Field(gt=0, description="Scale factor of the rendered chart image.")]
_DATE_DESCRIPTION = (
    "Single date or interval in ISO 8601, e.g. '2020-05-01' or '2020-05-01/2020-05-05'. A date "
    "covers everything it names: '2020-05' is the month of May and '2020' the year, and a day is "
    "all of its readings rather than the one at midnight."
)
_DateField = Annotated[str, Field(description=_DATE_DESCRIPTION)]
_DateOptField = Annotated[str | None, Field(description=_DATE_DESCRIPTION)]
_ShapeField = Annotated[
    Literal["long", "wide"],
    Field(description="Output shape: 'long' (one row per value) or 'wide' (one column per parameter)."),
]
_HumanizeField = Annotated[bool, Field(description="Use human-readable parameter names instead of raw dataset codes.")]
_ConvertUnitsField = Annotated[
    bool,
    Field(description="Convert values to the unit targets: the defaults, overridden per quantity by unit_targets."),
]
_UnitTargetsField = Annotated[
    dict[str, str] | None,
    Field(
        description="Custom unit targets as a mapping of quantity to unit, e.g. {'temperature': 'degree_fahrenheit'}."
    ),
]
_SkipEmptyField = Annotated[bool, Field(description="Skip stations whose coverage falls below `skip_threshold`.")]
_SkipThresholdField = Annotated[
    SkipThreshold,
    Field(description="Coverage fraction below which a station is skipped (requires `skip_empty`)."),
]
_SkipCriteriaField = Annotated[
    Literal["min", "mean", "max"],
    Field(description="Aggregation over the requested parameters' coverage: min, mean or max."),
]
_DropNullsField = Annotated[bool, Field(description="Drop rows with null values from the output.")]
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
        "name, overriding the default radius of that parameter.",
    ),
]
_SummaryStationDistanceField = Annotated[
    dict[str, Annotated[float, Field(ge=0.0)]] | None,
    Field(
        description="Per-parameter maximum summary-station distance in km, keyed by canonical parameter "
        "name, overriding the default radius of that parameter.",
    ),
]
_StationDistanceHomogeneousField = Annotated[
    float | None,
    Field(
        ge=0,
        description="Maximum distance (km) to a station for a parameter that varies slowly across a region, "
        "such as air temperature. Defaults to the configured radius of 40 km.",
    ),
]
_StationDistanceHeterogeneousField = Annotated[
    float | None,
    Field(
        ge=0,
        description="The same for a parameter that decorrelates faster, such as precipitation, at hourly "
        "resolution. Coarser resolutions scale it up and finer ones down -- times 0.75 at the minute "
        "resolutions, times 2 from daily upwards. Defaults to the configured radius of 20 km.",
    ),
]
_UseNearbyStationDistanceField = Annotated[
    float,
    Field(
        ge=0, description="Use a nearby station's values directly when it is within this distance (km) of the target."
    ),
]
_MinGainOfValuePairsField = Annotated[
    float,
    Field(ge=0, description="Minimum relative gain in value pairs required to add another interpolation station."),
]
_NumAdditionalStationsField = Annotated[
    int,
    Field(ge=0, description="Number of additional nearby stations to consider for interpolation."),
]


def station_distance_radii(homogeneous: float | None, heterogeneous: float | None) -> dict[str, Any]:
    """Collect the radii that were given, as keyword arguments for `Settings`.

    A radius the request did not give is left out rather than passed as the library default, so that
    a server configured through `WD_TS_GEO_STATION_DISTANCE_*` keeps its own.
    """
    radii: dict[str, Any] = {}
    if homogeneous is not None:
        radii["ts_geo_station_distance_homogeneous"] = homogeneous
    if heterogeneous is not None:
        radii["ts_geo_station_distance_heterogeneous"] = heterogeneous
    return radii


def _read_station_ids(value: str | list | None) -> list[str] | None:
    """Read station ids from a comma-separated string or a list of them, None when there are none.

    A blank id selects nothing: FastAPI reads an empty `station=` as `[""]`, which would count as a
    station selection beside `all` or a point, and be refused as a second one.
    """
    items = [value] if isinstance(value, str) else (value or [])
    ids = [station for item in items for station in read_list(item, separator=",") if station]
    return ids or None


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
        for field in firsts:
            others = [other for other in firsts if other != field]
            message = f"Cannot be combined with {join_names(others)}"
            errors.append(
                _rule_error("mutually_exclusive", message, (field,), getattr(request, field), conflicts_with=others)
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
_STATION_SELECTIONS = (("all",), ("station",), ("name",), _POINT, ("left", "bottom", "right", "top"), ("sql",))


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


class StationsRequest(BaseModel):
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

    # DWD forecasts: issue for MOSMIX/DMO/SWSMOS, lead_time for DMO
    lead_time: _LeadTimeField = None
    issue: _IssueField = None

    # station filter parameters
    all: _AllField = False
    # station ids
    station: _StationIdsField = None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v: str | list | None) -> list[str] | None:
        """Validate station."""
        return _read_station_ids(v)

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

    with_metadata: _WithMetadataField = False
    with_stations: _WithStationsField = False

    format: _FormatField = "json"
    pretty: _PrettyField = False
    debug: _DebugField = False

    # plot settings
    width: _WidthField = None
    height: _HeightField = None
    scale: _ScaleField = None

    @model_validator(mode="after")
    def check_station_selection(self) -> StationsRequest:
        """Check that exactly one station selection is made."""
        _raise_rule_errors(self, _check_station_selection(self))
        return self


class HistoryRequest(BaseModel):
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
    station: _StationIdsField = None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v: str | list | None) -> list[str] | None:
        """Validate station."""
        return _read_station_ids(v)

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
    debug: _DebugField = False

    @model_validator(mode="after")
    def check_station_selection(self) -> HistoryRequest:
        """Check that exactly one of all or station is given."""
        _raise_rule_errors(self, _check_one_of(self, (("all",), ("station",))))
        return self


class ValuesRequest(BaseModel):
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
    station: _StationIdsField = None

    @field_validator("station", mode="before")
    @classmethod
    def validate_station(cls, v: str | list | None) -> list[str] | None:
        """Validate station."""
        return _read_station_ids(v)

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

    with_metadata: _WithMetadataField = False
    with_stations: _WithStationsField = False

    format: _FormatField = "json"
    pretty: _PrettyField = False
    debug: _DebugField = False

    # plot settings
    width: _WidthField = None
    height: _HeightField = None
    scale: _ScaleField = None

    # values
    date: _DateOptField = None
    sql_values: _SqlValuesField = None
    humanize: _HumanizeField = True
    shape: _ShapeField = "long"
    convert_units: _ConvertUnitsField = True
    unit_targets: _UnitTargetsField = None
    skip_empty: _SkipEmptyField = False
    skip_threshold: _SkipThresholdField = 0.95
    skip_criteria: _SkipCriteriaField = "min"
    drop_nulls: _DropNullsField = True

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets(cls, v: str | dict | None) -> dict[str, str] | None:
        """Validate unit targets."""
        if not v:
            return None
        if isinstance(v, dict):
            return v
        return json.loads(v)

    @model_validator(mode="after")
    def check_station_selection(self) -> ValuesRequest:
        """Check that exactly one station selection is made."""
        _raise_rule_errors(self, _check_station_selection(self))
        return self


class InterpolationRequest(BaseModel):
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

    date: _DateField

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
        return json.loads(v)

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
        return json.loads(v)

    use_nearby_station_distance: _UseNearbyStationDistanceField = 1.0
    min_gain_of_value_pairs: _MinGainOfValuePairsField = 0.10
    num_additional_stations: _NumAdditionalStationsField = 3
    format: _FormatField = "json"

    with_metadata: _WithMetadataField = False
    with_stations: _WithStationsField = False

    pretty: _PrettyField = False
    debug: _DebugField = False

    # plot settings
    width: _WidthField = None
    height: _HeightField = None
    scale: _ScaleField = None

    @model_validator(mode="after")
    def check_reference_point(self) -> InterpolationRequest:
        """Check that exactly one of station or latitude/longitude is given."""
        _raise_rule_errors(self, _check_one_of(self, (("station",), _POINT)))
        return self


class SummaryRequest(BaseModel):
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

    date: _DateField

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
        return json.loads(v)

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
        return json.loads(v)

    use_nearby_station_distance: _UseNearbyStationDistanceField = 1.0
    min_gain_of_value_pairs: _MinGainOfValuePairsField = 0.10
    num_additional_stations: _NumAdditionalStationsField = 3
    format: _FormatField = "json"

    with_metadata: _WithMetadataField = False
    with_stations: _WithStationsField = False

    pretty: _PrettyField = False
    debug: _DebugField = False

    # plot settings
    width: _WidthField = None
    height: _HeightField = None
    scale: _ScaleField = None

    @model_validator(mode="after")
    def check_reference_point(self) -> SummaryRequest:
        """Check that exactly one of station or latitude/longitude is given."""
        _raise_rule_errors(self, _check_one_of(self, (("station",), _POINT)))
        return self


class IssuesRequest(BaseModel):
    """Request model for listing available issue datetimes."""

    model_config = {"extra": "forbid"}

    provider: _ProviderField
    network: _NetworkField
    station: _StationIdField
    dataset: Annotated[
        Literal["icon", "icon_eu"] | None,
        Field(
            description="DWD DMO product to list issues for ('icon' or 'icon_eu'); "
            "DMO only, refused for MOSMIX and SWSMOS.",
        ),
    ] = None
    # not the shared `_LeadTimeField`: the data requests ignore a lead time outside DMO, but `get_issues`
    # refuses one
    lead_time: Annotated[
        Literal["short", "long"] | None,
        Field(
            description="DWD DMO forecast lead time to list issues for ('short' or 'long'); "
            "DMO only, refused for MOSMIX and SWSMOS.",
        ),
    ] = None
    debug: _DebugField = False


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
    settings: Settings | None = None,
) -> list[GlossaryEntry]:
    """Return the canonical parameter vocabulary, optionally filtered.

    `coverage` answers which parameters a given provider offers; this answers what any of them
    means and which unit it comes back in, neither of which coverage reports.

    `parameter` matches as a substring, since the useful question over several hundred names is usually
    "everything about radiation" rather than one exact name. An exact name deliberately does *not*
    short-circuit to a single entry: `humidity_relative` is both a parameter and the prefix of
    `humidity_relative_max` and `humidity_relative_min`, and hiding those would be the more
    surprising behaviour. Use `limit` to bound the result instead.

    The unit reported is the one a values request would actually return, so `ts_unit_targets` is
    honoured -- reporting the built-in default while `values` hands back Fahrenheit would make this
    worse than saying nothing.
    """
    from wetterdienst.metadata.parameter_table import PARAMETER_TABLE  # noqa: PLC0415
    from wetterdienst.model.unit import UnitConverter  # noqa: PLC0415
    from wetterdienst.settings import Settings as _Settings  # noqa: PLC0415

    settings = settings or _Settings()
    unit_converter = UnitConverter()
    unit_converter.update_targets(settings.ts_unit_targets)
    needle = parameter.strip().lower() if parameter else None
    entries: list[GlossaryEntry] = []
    for canonical in PARAMETER_TABLE:
        if needle and needle not in canonical.name:
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
    api: type[TimeseriesRequest],
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

    return [issue.isoformat() for issue in issues]


def _get_stations_request(
    api: type[TimeseriesRequest],
    request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest | HistoryRequest,
    date: str | None,
    settings: Settings,
) -> TimeseriesRequest:
    """Create a request object for stations."""
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest  # noqa: PLC0415

    # TODO: move this into Request core
    start_date, end_date = None, None
    if date:
        if "/" in date:
            if date.count("/") >= 2:
                msg = "Invalid ISO 8601 time interval"
                raise InvalidTimeIntervalError(msg)
            start_string, end_string = date.split("/")
            # the window opens with the span the first half names and closes with the second's
            start_date, _ = parse_date_window(start_string)
            _, end_date = parse_date_window(end_string)
        else:
            start_date, end_date = parse_date_window(date)

    parameters = parse_parameters(request.parameters, api.metadata)
    if not parameters:
        # raised here rather than left to the request, which would only see the empty list this
        # resolved to and could not name what was asked for
        msg = f"No valid parameters could be parsed from {request.parameters!r} for {api.__name__}"
        raise NoParametersFoundError(msg)

    any_date_required = any(parameter.dataset.date_required for parameter in parameters)
    if any_date_required and (not start_date or not end_date) and not isinstance(request, StationsRequest):
        msg = "Start and end date required for single period datasets"
        raise StartDateEndDateError(msg)

    kwargs: dict[str, Any] = {
        "parameters": parameters,
        "start_date": start_date,
        "end_date": end_date,
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

    return api(**kwargs, settings=settings)


def get_stations(
    api: type[TimeseriesRequest],
    request: StationsRequest | ValuesRequest | HistoryRequest,
    date: str | None,
    settings: Settings,
) -> StationsResult:
    """Get stations based on request, by the one selection its model lets it make."""
    r = _get_stations_request(api=api, request=request, date=date, settings=settings)

    if getattr(request, "all", False):
        return r.all()

    if request.station:
        return r.filter_by_station_id(request.station)

    name: str | None = getattr(request, "name", None)
    if name:
        # filter_by_name defaults to a single best match; for a listing default to several
        # candidates so a place query offers options, honoring an explicit rank when given
        # (e.g. the REST/MCP `rank` param).
        name_rank: int = getattr(request, "rank", None) or 5
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


_HISTORY_IDENTIFIERS = frozenset({"station_id", "resolution", "dataset"})


def select_history_sections(history: dict[str, Any], sections: AbstractSet[str] | None) -> dict[str, Any]:
    """Keep the requested sections of a dumped station history, all of them when none are requested.

    In the history's own field order rather than the order of `sections`, which is a set, so the
    same request always answers the same document. `station_id`, `resolution` and `dataset` say
    which station and dataset the history belongs to, are not sections and are always kept.
    """
    if not sections:
        return history
    return {key: value for key, value in history.items() if key in _HISTORY_IDENTIFIERS or key in sections}


def limit_stations_to_rank(stations: StationsResult) -> StationsResult:
    """Trim a rank-filtered stations *listing* to the requested ``rank`` rows.

    ``filter_by_rank`` intentionally keeps *all* stations (distance-sorted) in ``df`` because the real
    ``rank`` limit is applied later, during value collection: that walk takes the ``rank`` closest
    stations that actually carry data -- as sparsely as ``ts_skip_empty`` / ``ts_skip_threshold`` /
    ``ts_skip_criteria`` allow -- and exposes them via ``ValuesResult.df_stations``.

    A plain stations listing does no value collection, so it cannot apply that data-aware selection --
    but returning every station (e.g. 1284 for DWD) when the caller asked for the N closest is both
    surprising and huge. Here we slice to the ``rank`` closest *by distance* (data availability
    unknown at listing time); leave other filters untouched.
    """
    from wetterdienst.model.result import StationsFilter  # noqa: PLC0415

    if stations.stations_filter is StationsFilter.BY_RANK and stations.rank:
        stations.df = stations.df.head(stations.rank)
    return stations


def get_values(
    api: type[TimeseriesRequest],
    request: ValuesRequest,
    settings: Settings,
) -> ValuesResult:
    """Get values based on request."""
    stations_ = get_stations(
        api=api,
        request=request,
        date=request.date,
        settings=settings,
    )

    # TODO: Add stream-based processing here.
    # a `ValueError` from the values -- a provider refusing a request it cannot serve as phrased
    # (`ParameterNotCarriedError`), or a parse failure -- propagates: reporting it is the caller's
    values_ = stations_.values.all()

    if values_.df.is_empty():
        # nothing to filter, and nothing more to say about it. An empty window is the caller's
        # news to report: the CLI says so once and exits, the REST API hands the empty result
        # back, and `.all()` has already logged it on the way here. Saying it again here made the
        # CLI print the same sentence twice
        return values_

    if request.sql_values:
        log.info(f"Filtering with SQL: {request.sql_values}")
        values_.filter_by_sql(request.sql_values)

    return values_


def get_interpolate(
    api: type[TimeseriesRequest],
    request: InterpolationRequest,
    settings: Settings,
) -> InterpolatedValuesResult:
    """Get interpolated values based on request."""
    r = _get_stations_request(api=api, request=request, date=request.date, settings=settings)

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
        values_.filter_by_sql(request.sql_values)

    return values_


def get_summarize(
    api: type[TimeseriesRequest],
    request: SummaryRequest,
    settings: Settings,
) -> SummarizedValuesResult:
    """Get summarized values based on request."""
    r = _get_stations_request(api=api, request=request, date=request.date, settings=settings)

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
        values_.filter_by_sql(request.sql_values)

    return values_


class StripesMetadata(BaseModel):
    """Metadata for climate stripes data."""

    model_config = {"extra": "forbid"}

    station: Mapping[str, Any]
    resolution: str
    dataset: str
    parameter: str


class StripesData(BaseModel):
    """Climate stripes data with metadata and values."""

    model_config = {"extra": "forbid", "arbitrary_types_allowed": True}

    metadata: StripesMetadata
    df: pl.DataFrame


# Type definitions for CLIMATE_STRIPES_CONFIG
StripesKind = Literal["temperature", "precipitation"]


class StripesRequest(BaseModel):
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
    # as for stations and values, and the CLI's --name_threshold
    name_threshold: _NameThresholdField = 0.8
    start_year: Annotated[int | None, Field(description="First year. Default: the station's first.")] = None
    end_year: Annotated[
        int | None,
        Field(description="Last year, after start_year. Default: the station's last."),
    ] = None
    debug: _DebugField = False

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


def _get_stripes_temperature_request(periods: Period = Period.HISTORICAL) -> DwdObservationRequest:
    """Need this for displaying stations in the interactive app."""
    return DwdObservationRequest(
        parameters=[("annual", "climate_summary", "temperature_air_mean_2m")],
        periods=periods,
    )


def _get_stripes_precipitation_request(periods: Period = Period.HISTORICAL) -> DwdObservationRequest:
    """Need this for displaying stations in the interactive app."""
    return DwdObservationRequest(
        parameters=[("annual", "precipitation_more", "precipitation_amount")],
        periods=periods,
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
        stations.df = stations.df.join(station_ids_active, on="station_id")
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

    df = stations.values.all().df.sort("timestamp")
    df = df.set_sorted("timestamp")
    df = df.select("timestamp", "value")
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

    resolution = "annual"
    if kind == "temperature":
        dataset = "climate_summary"
        parameter = "temperature_air_mean_2m"
    else:
        dataset = "precipitation_more"
        parameter = "precipitation_amount"

    metadata = StripesMetadata(
        station=station,
        resolution=resolution,
        dataset=dataset,
        parameter=parameter,
    )

    return StripesData(metadata=metadata, df=df)


def _plot_stripes(stripes: StripesImageRequest) -> go.Figure:
    """Create warming stripes for station in Germany, for a request its model has checked.

    Code similar to: https://www.s4f-freiburg.de/temperaturstreifen/
    """
    import plotly.graph_objects as go  # noqa: PLC0415

    kind = stripes.kind
    show_title, show_years, show_data_availability = (
        stripes.show_title,
        stripes.show_years,
        stripes.show_data_availability,
    )
    stripes_data = _get_stripes_data(stripes)

    df = stripes_data.df
    station_dict = stripes_data.metadata.station
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
            text=str(df.get_column("timestamp").min().year),  # ty: ignore[unresolved-attribute]
            showarrow=False,
            xref="paper",
            yref="paper",
            xanchor="right",
        )
        fig.add_annotation(
            x=0.95,
            y=-0.05,
            text=str(df.get_column("timestamp").max().year),  # ty: ignore[unresolved-attribute]
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
    """Set logging level for the wetterdienst package."""
    log_level = logging.INFO

    if debug:
        log_level = logging.DEBUG

    log.setLevel(log_level)
