# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core UI utilities for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Any, Literal

import polars as pl
from pydantic import BaseModel, Field, field_validator

# pydantic refuses typing.TypedDict as a response model on Python below 3.12, and GlossaryEntry
# is one; model/result.py imports it from here for the same reason
from typing_extensions import TypedDict

from wetterdienst.exceptions import InvalidTimeIntervalError, NoParametersFoundError, StartDateEndDateError
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.unit_type import UnitType  # noqa: TC001, needed at runtime by FastAPI
from wetterdienst.model.metadata import parse_parameters
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.util.datetime import parse_date
from wetterdienst.util.ui import read_list

if TYPE_CHECKING:
    from collections.abc import Callable

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
    Field(description="Dataset periods: 'historical', 'recent' and/or 'now'. Inferred from the date when omitted."),
]
_LeadTimeField = Annotated[
    Literal["short", "long"] | None,
    Field(description="Forecast lead time for DWD DMO ('short' or 'long'); ignored for other networks."),
]
_IssueField = Annotated[
    str | None,
    Field(description="Model-run issue time for DWD MOSMIX/DMO (ISO 8601); defaults to the latest run."),
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
    Field(ge=1, description="Return the N closest stations to the given latitude/longitude."),
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
    Field(description="SQL WHERE clause applied to the station metadata, e.g. \"state='Sachsen'\"."),
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
_DateField = Annotated[
    str,
    Field(description="Single date or interval in ISO 8601, e.g. '2020-05-01' or '2020-05-01/2020-05-05'."),
]
_DateOptField = Annotated[
    str | None,
    Field(description="Single date or interval in ISO 8601, e.g. '2020-05-01' or '2020-05-01/2020-05-05'."),
]
_ShapeField = Annotated[
    Literal["long", "wide"],
    Field(description="Output shape: 'long' (one row per value) or 'wide' (one column per parameter)."),
]
_HumanizeField = Annotated[bool, Field(description="Use human-readable parameter names instead of raw dataset codes.")]
_ConvertUnitsField = Annotated[bool, Field(description="Convert values to SI units.")]
_UnitTargetsField = Annotated[
    dict[str, str] | None,
    Field(
        description="Custom unit targets as a mapping of quantity to unit, e.g. {'temperature': 'degree_fahrenheit'}."
    ),
]
_SkipEmptyField = Annotated[bool, Field(description="Skip stations whose coverage falls below `skip_threshold`.")]
_SkipThresholdField = Annotated[
    float,
    Field(ge=0, le=1, description="Coverage fraction below which a station is skipped (requires `skip_empty`)."),
]
_SkipCriteriaField = Annotated[
    Literal["min", "mean", "max"],
    Field(description="Aggregation over the requested parameters' coverage: min, mean or max."),
]
_DropNullsField = Annotated[bool, Field(description="Drop rows with null values from the output.")]
_SectionsField = Annotated[
    set[Literal["name", "parameter", "device", "geography", "missing_data"]] | None,
    Field(description="History sections to include: name, parameter, device, geography, missing_data."),
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

    A radius that was not given is left out rather than passed as the library default, so that a
    CLI user or a server configured through `WD_TS_GEO_STATION_DISTANCE_*` keeps its own.
    """
    radii: dict[str, Any] = {}
    if homogeneous is not None:
        radii["ts_geo_station_distance_homogeneous"] = homogeneous
    if heterogeneous is not None:
        radii["ts_geo_station_distance_heterogeneous"] = heterogeneous
    return radii


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

    # Mosmix/DMO
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
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v)
        stations = []
        for item in v:
            if "," in item:
                stations.extend(read_list(item, separator=","))
            else:
                stations.append(item)
        return stations

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
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v)
        stations = []
        for item in v:
            if "," in item:
                stations.extend(read_list(item, separator=","))
            else:
                stations.append(item)
        return stations

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

    # Mosmix/DMO
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
        if not v:
            return None
        if isinstance(v, str):
            return read_list(v)
        stations = []
        for item in v:
            if "," in item:
                stations.extend(read_list(item, separator=","))
            else:
                stations.append(item)
        return stations

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

    # Mosmix/DMO
    lead_time: _LeadTimeField = None
    issue: _IssueField = None

    # station filter parameters
    station: _StationIdOptField = None
    # latlon
    latitude: _LatitudeField = None
    longitude: _LongitudeField = None
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

    # Mosmix/DMO
    lead_time: _LeadTimeField = None
    issue: _IssueField = None

    # station filter parameters
    station: _StationIdOptField = None
    # latlon
    latitude: _LatitudeField = None
    longitude: _LongitudeField = None
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


class IssuesRequest(BaseModel):
    """Request model for listing available issue datetimes."""

    model_config = {"extra": "forbid"}

    provider: _ProviderField
    network: _NetworkField
    station: _StationIdField
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

    `parameter` matches as a substring, since the useful question over 504 names is usually
    "everything about radiation" rather than one exact name. An exact name deliberately does *not*
    short-circuit to a single entry: `humidity` is both a parameter and the prefix of
    `humidity_max`, `humidity_min` and `humidity_absolute`, and hiding those would be the more
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

    Supported: DWD MOSMIX (MOSMIX_L single-station) and DWD DMO (ICON single-station).
    """
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest  # noqa: PLC0415

    if issubclass(api, DwdMosmixRequest):
        issues = DwdMosmixRequest.available_issues(request.station, settings)
    elif issubclass(api, DwdDmoRequest):
        issues = DwdDmoRequest.available_issues(request.station, settings)
    else:
        msg = f"Issue listing is only supported for DWD MOSMIX and DMO (got {api.__name__})"
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

    # TODO: move this into Request core
    start_date, end_date = None, None
    if date:
        if "/" in date:
            if date.count("/") >= 2:
                msg = "Invalid ISO 8601 time interval"
                raise InvalidTimeIntervalError(msg)
            start_date, end_date = date.split("/")
            start_date = parse_date(start_date)
            end_date = parse_date(end_date)
        else:
            start_date = parse_date(date)

    parameters = parse_parameters(request.parameters, api.metadata)
    if not parameters:
        # raised here rather than left to the request, which would only see the empty list this
        # resolved to and could not name what was asked for
        msg = f"No valid parameters could be parsed from {request.parameters!r} for {api.metadata.__name__}"
        raise NoParametersFoundError(msg)

    any_date_required = any(parameter.dataset.date_required for parameter in parameters)
    if any_date_required and (not start_date or not end_date) and not isinstance(request, StationsRequest):
        msg = "Start and end date required for single period datasets"
        raise StartDateEndDateError(msg)

    any_multiple_period_dataset = any(len(parameter.dataset.periods) > 1 for parameter in parameters)

    kwargs: dict[str, Any] = {
        "parameters": parameters,
        "start_date": start_date,
        "end_date": end_date,
    }
    if any_multiple_period_dataset and "periods" in getattr(api, "__dataclass_fields__", {}):
        kwargs["periods"] = getattr(request, "periods", None)

    if issubclass(api, (DwdMosmixRequest, DwdDmoRequest)) and (issue := getattr(request, "issue", None)) is not None:
        kwargs["issue"] = issue
    if issubclass(api, DwdDmoRequest) and (lead_time := getattr(request, "lead_time", None)) is not None:
        kwargs["lead_time"] = lead_time

    return api(**kwargs, settings=settings)


def get_stations(
    api: type[TimeseriesRequest],
    request: StationsRequest | ValuesRequest | InterpolationRequest | HistoryRequest,
    date: str | None,
    settings: Settings,
) -> StationsResult:
    """Get stations based on request."""
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

    # Use coordinates twice in main if-elif to get same KeyError
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

    param_options = [
        "all (boolean)",
        "station (string)",
        "name (string)",
        "latitude (float), longitude (float) and rank (integer)",
        "latitude (float), longitude (float) and distance (float)",
        "left (float), bottom (float), right (float), top (float)",
    ]
    msg = f"Give one of the parameters: {', '.join(param_options)}"
    raise KeyError(msg)


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

    try:
        # TODO: Add stream-based processing here.
        values_ = stations_.values.all()
    except ValueError:
        log.exception("Error while fetching values")
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
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

    if request.latitude and request.longitude:
        values_ = r.interpolate((request.latitude, request.longitude))
    elif request.station:
        values_ = r.interpolate_by_station_id(request.station)
    else:
        msg = "Either latitude and longitude or station must be provided"
        raise ValueError(msg)

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

    if request.latitude and request.longitude:
        values_ = r.summarize((request.latitude, request.longitude))
    elif request.station:
        values_ = r.summarize_by_station_id(request.station)
    else:
        msg = "Either latitude and longitude or station must be provided"
        raise ValueError(msg)

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
        parameters=[("annual", "precipitation_more", "precipitation_height")],
        periods=periods,
    )


CLIMATE_STRIPES_CONFIG: StripesConfig = {
    "temperature": {
        "request": _get_stripes_temperature_request,
        "color_map": "RdBu",
    },
    "precipitation": {
        "request": _get_stripes_precipitation_request,
        "color_map": "BrBG",
    },
}


def _get_stripes_stations(kind: StripesKind, *, active: bool = True) -> StationsResult:
    request = CLIMATE_STRIPES_CONFIG[kind]["request"]
    stations = request(Period.HISTORICAL).all()
    if active:
        station_ids_active = request(Period.RECENT).all().df.select("station_id")
        stations.df = stations.df.join(station_ids_active, on="station_id")
    return stations


def _get_stripes_data(  # noqa: C901
    kind: StripesKind,
    station_id: str | None = None,
    name: _NameField = None,
    start_year: int | None = None,
    end_year: int | None = None,
    name_threshold: float = 0.8,
) -> StripesData:
    """Get stripes data for station in Germany.

    Returns StripesData with metadata and dataframe.
    """
    if kind not in ["temperature", "precipitation"]:
        msg = "kind must be either 'temperature' or 'precipitation'"
        raise ValueError(msg)
    if start_year and end_year and start_year >= end_year:
        msg = "start_year must be less than end_year"
        raise ValueError(msg)
    if name_threshold < 0 or name_threshold > 1:
        msg = "name_threshold must be between 0.0 and 1.0"
        raise ValueError(msg)

    request = CLIMATE_STRIPES_CONFIG[kind]["request"](Period.HISTORICAL)

    if station_id:
        stations = request.filter_by_station_id(station_id)
    elif name:
        stations = request.filter_by_name(name, threshold=name_threshold)
    else:
        param_options = [
            "station (string)",
            "name (string)",
        ]
        msg = f"Give one of the parameters: {', '.join(param_options)}"
        raise KeyError(msg)

    try:
        station = stations.to_dict()["stations"][0]
    except IndexError as e:
        parameter = "station_id" if station_id else "name"
        msg = f"No station with a {parameter} similar to '{station_id or name}' found"
        raise ValueError(msg) from e

    df = stations.values.all().df.sort("date")
    df = df.set_sorted("date")
    df = df.select("date", "value")
    df = df.upsample("date", every="1y")
    df = df.with_columns(
        (1 - (pl.col("value") - pl.col("value").min()) / (pl.col("value").max() - pl.col("value").min())).alias(
            "value_scaled",
        ),
        pl.when(pl.col("value").is_not_null()).then(-0.02).otherwise(None).alias("availability"),
    )

    if start_year:
        df = df.filter(pl.col("date").dt.year().ge(start_year))
    if end_year:
        df = df.filter(pl.col("date").dt.year().le(end_year))

    if len(df) == 1:
        msg = "At least two years are required to create warming stripes."
        raise ValueError(msg)

    resolution = "annual"
    if kind == "temperature":
        dataset = "climate_summary"
        parameter = "temperature_air_mean_2m"
    else:
        dataset = "precipitation_more"
        parameter = "precipitation_height"

    metadata = StripesMetadata(
        station=station,
        resolution=resolution,
        dataset=dataset,
        parameter=parameter,
    )

    return StripesData(metadata=metadata, df=df)


def _plot_stripes(
    kind: StripesKind,
    station_id: str | None = None,
    name: _NameField = None,
    start_year: int | None = None,
    end_year: int | None = None,
    name_threshold: float = 0.8,
    *,
    show_title: bool = True,
    show_years: bool = True,
    show_data_availability: bool = True,
) -> go.Figure:
    """Create warming stripes for station in Germany.

    Code similar to: https://www.s4f-freiburg.de/temperaturstreifen/
    """
    import plotly.graph_objects as go  # noqa: PLC0415

    stripes_data = _get_stripes_data(
        kind=kind,
        station_id=station_id,
        name=name,
        start_year=start_year,
        end_year=end_year,
        name_threshold=name_threshold,
    )

    df = stripes_data.df
    station_dict = stripes_data.metadata.station
    cmap = CLIMATE_STRIPES_CONFIG[kind]["color_map"]

    df_without_nulls = df.drop_nulls("value")

    fig = go.Figure()

    # Add bar trace
    fig.add_trace(
        go.Bar(
            x=df_without_nulls.get_column("date").dt.year(),
            y=[1.0] * len(df_without_nulls),
            marker={"color": df_without_nulls.get_column("value_scaled"), "colorscale": cmap, "cmin": 0, "cmax": 1},
            width=1.0,
        ),
    )

    # Add scatter trace for data availability
    if show_data_availability:
        fig.add_trace(
            go.Scatter(
                x=df.get_column("date").dt.year(),
                y=df.get_column("availability"),
                mode="lines",
                marker={"color": "gold", "size": 5},
                line={"color": "gold"},
            ),
        )
        fig.add_annotation(
            x=df.get_column("date").dt.year().min(),
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
            text=str(df.get_column("date").min().year),  # ty: ignore[unresolved-attribute]
            showarrow=False,
            xref="paper",
            yref="paper",
            xanchor="right",
        )
        fig.add_annotation(
            x=0.95,
            y=-0.05,
            text=str(df.get_column("date").max().year),  # ty: ignore[unresolved-attribute]
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
