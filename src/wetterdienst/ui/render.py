# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""How a result is written out, shared by the command line, the REST API and MCP (GH-2635).

The command line used to render a result by itself and the REST API by itself, so the same request
was answered differently: with `with_metadata` the REST API reported the settings the values were
got with and the command line did not. Both render through `render` and `render_stations` now. This
module imports no web framework, so the command line can without the `restapi` extra.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.unit import UnitConverter
from wetterdienst.options import SkipThreshold  # noqa: TC001, needed at runtime by pydantic
from wetterdienst.ui.response_metadata import ResponseMetadata, alerts_metadata, metadata_to_dict, response_metadata
from wetterdienst.util.datetime import format_timestamp

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    import polars as pl

    from wetterdienst.model.history import TimeseriesHistory
    from wetterdienst.model.result import (
        InterpolatedValuesResult,
        StationsResult,
        SummarizedValuesResult,
        ValuesResult,
    )
    from wetterdienst.options import Options
    from wetterdienst.provider.dwd.alerts.api import DwdWeatherAlertResult
    from wetterdienst.ui.core import (
        HistoryRequest,
        InterpolationRequest,
        StationsRequest,
        StripesData,
        StripesStationsRequest,
        StripesValuesRequest,
        SummaryRequest,
        ValuesRequest,
    )
    from wetterdienst.util.response_warnings import ResponseWarning

    _Request: TypeAlias = (
        StationsRequest
        | ValuesRequest
        | InterpolationRequest
        | SummaryRequest
        | HistoryRequest
        | StripesStationsRequest
    )


#: a radius, factor or gain, which the settings take as infinite or NaN too, written then as a string
_Unbounded = Annotated[
    float,
    WithJsonSchema(
        {"anyOf": [{"type": "number"}, {"type": "string", "enum": ["Infinity", "NaN"]}]}, mode="serialization"
    ),
]


# The settings a request to `/api/values`, `/api/interpolate` and `/api/summarize` is answered with,
# by the request field that sets each, and with the option of `Options` it sets as its validation alias. The REST
# API's one list of them: an endpoint takes these from its request (GH-2325), reports the ones it
# used with its metadata, and `/api/settings` reports the server's defaults for them (GH-2359), or
# what the query parameters it is given resolve to over those (GH-2383).
# Listed one by one rather than dumped from `Options`: the REST API names them its own way, and reports
# the unit targets and the resolution factors whole.
class _AppliedSettings(BaseModel):
    """The settings every one of the three endpoints is answered with."""

    # by name too, so that a report, which is written by name, reads back. A radius, factor or gain
    # the settings take as infinite is written as the string "Infinity", which JSON has no number for
    model_config = ConfigDict(extra="forbid", populate_by_name=True, ser_json_inf_nan="strings")

    humanize: bool = Field(validation_alias="humanize")
    convert_units: bool = Field(validation_alias="convert_units")
    unit_targets: dict[str, str] = Field(
        validation_alias="unit_targets",
        description="The unit values of each quantity are converted to, for every quantity, where `convert_units` "
        "is on; off, they come in the unit the source publishes.",
    )
    skip_empty: bool = Field(validation_alias="skip_empty")
    skip_threshold: SkipThreshold = Field(validation_alias="skip_threshold")
    skip_criteria: Literal["min", "mean", "max"] = Field(validation_alias="skip_criteria")
    drop_nulls: bool = Field(
        validation_alias="drop_nulls",
        description="Whether rows without a value are dropped. The wide shape, the server's or the request's, "
        "turns it off.",
    )


class ValuesSettings(_AppliedSettings):
    """The settings of `/api/values`."""

    shape: Literal["long", "wide"] = Field(validation_alias="shape")


_STATION_DISTANCE_DESCRIPTION = (
    "The radius (km) set for a parameter by name, which applies at every resolution. A parameter it "
    "leaves out takes the homogeneous or the heterogeneous radius."
)
_STATION_DISTANCE_HETEROGENEOUS_DESCRIPTION = (
    "The radius (km) of a parameter that decorrelates fast, at hourly resolution: at another "
    "resolution it is multiplied by that resolution's factor."
)


class _GeoSettings(_AppliedSettings):
    """The settings `/api/interpolate` and `/api/summarize` share."""

    min_gain_of_value_pairs: _Unbounded = Field(validation_alias="geo_min_gain_of_value_pairs")
    num_additional_stations: int = Field(validation_alias="geo_num_additional_stations")
    # set by the server alone, as are the skipping of sparse stations and the dropping of nulls
    # here: neither request has a field for them, and the stations' values are read with them
    station_distance_resolution_factors: dict[str, _Unbounded] = Field(
        validation_alias="geo_station_distance_resolution_factors",
        description="The factor the heterogeneous radius is multiplied by, for every resolution. Set by the "
        "server alone.",
    )


class InterpolationSettings(_GeoSettings):
    """The settings of `/api/interpolate`."""

    # a summary has no such field: it takes the nearest station with data, so there is nothing for it to decide
    use_nearby_station_distance: _Unbounded | None = Field(validation_alias="geo_use_nearby_station_distance")
    interpolation_station_distance: dict[str, _Unbounded] = Field(
        validation_alias="geo_station_distance",
        description=_STATION_DISTANCE_DESCRIPTION,
    )
    interpolation_station_distance_homogeneous: _Unbounded = Field(validation_alias="geo_station_distance_homogeneous")
    interpolation_station_distance_heterogeneous: _Unbounded = Field(
        validation_alias="geo_station_distance_heterogeneous",
        description=_STATION_DISTANCE_HETEROGENEOUS_DESCRIPTION,
    )


class SummarySettings(_GeoSettings):
    """The settings of `/api/summarize`."""

    summary_station_distance: dict[str, _Unbounded] = Field(
        validation_alias="geo_station_distance",
        description=_STATION_DISTANCE_DESCRIPTION,
    )
    summary_station_distance_homogeneous: _Unbounded = Field(validation_alias="geo_station_distance_homogeneous")
    summary_station_distance_heterogeneous: _Unbounded = Field(
        validation_alias="geo_station_distance_heterogeneous",
        description=_STATION_DISTANCE_HETEROGENEOUS_DESCRIPTION,
    )


_M = TypeVar("_M", bound=_AppliedSettings)


def _applied_settings(model: type[_M], options: Options) -> _M:
    """Report `options` by the fields of `model`.

    The unit targets and the resolution factors hold only the entries that depart from
    wetterdienst's, and are reported whole: the unit of every quantity and the factor of every
    resolution. The per-parameter radii are reported as given, as `Options` dumps them, since a
    parameter they leave out takes one of the two radii reported next to them. `drop_nulls` is
    reported as in effect, which the wide shape turns off.
    """

    def unit_targets() -> dict[str, str]:
        converter = UnitConverter()
        converter.update_targets(options.unit_targets)
        return {quantity: unit.name for quantity, unit in converter.targets.items()}

    reported: dict[str, Callable[[], object]] = {
        "unit_targets": unit_targets,
        "drop_nulls": lambda: options.drop_nulls_effective,
        "geo_station_distance": lambda: options.model_dump(include={"geo_station_distance"})["geo_station_distance"],
        "geo_station_distance_resolution_factors": lambda: {
            resolution.value: options.geo_station_distance_resolution_factor(resolution.value)
            for resolution in Resolution
        },
    }
    return model.model_validate(
        {
            option: reported[option]() if option in reported else getattr(options, option)
            for option in (str(field.validation_alias) for field in model.model_fields.values())
        },
    )


def render_kwargs(
    request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest,
    *,
    max_side: int | None = None,
) -> dict[str, Any]:
    """Give the arguments of a result's `to_format` for what the request asks to have written.

    Not `with_stations`, which a listing of stations has no request field for: a request for values
    adds it (`render`).

    `max_side` is the largest side of a rendered chart that is let through, which the REST API sets
    and the command line, whose caller is at the keyboard, does not.
    """
    kwargs: dict[str, Any] = {"fmt": request.format, "with_metadata": request.with_metadata}
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale
        if max_side is not None:
            kwargs["max_side"] = max_side
    return kwargs


def _json_answer(
    data: dict[str, Any],
    request: _Request,
    metadata: ResponseMetadata,
    settings: _AppliedSettings | None = None,
) -> str:
    """Write the JSON of an answer: its `metadata` block, the `settings` they were got with, then the rest.

    The block is always there; the heavy parts of it, and the settings, are what `with_metadata` adds.
    """
    answer: dict[str, Any] = {"metadata": metadata_to_dict(metadata)}
    if settings is not None:
        answer["settings"] = json.loads(settings.model_dump_json())
    answer.update(data)
    fmt = getattr(request, "format", "json")
    return json.dumps(answer, indent=4 if request.pretty else None, ensure_ascii=fmt == "json")


def ndjson_line(value: Mapping[str, Any]) -> bytes:
    """Write one line of an NDJSON answer: compact JSON, UTF-8, a newline."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def ndjson_head(metadata: ResponseMetadata, settings: _AppliedSettings | None = None) -> dict[str, Any]:
    """Give the first line of an NDJSON answer: the `metadata` block, and the `settings` beside it if there are any."""
    head: dict[str, Any] = {"metadata": metadata_to_dict(metadata)}
    if settings is not None:
        head["settings"] = json.loads(settings.model_dump_json())
    return head


def ndjson_end(stations: int, rows: int, warnings: Sequence[ResponseWarning]) -> dict[str, Any]:
    """Give the content of the last line of an NDJSON answer: what was sent, and every warning raised on the way."""
    return {"counts": {"stations": stations, "rows": rows}, "warnings": list(warnings)}


def ndjson_refusal(request: StationsRequest | ValuesRequest) -> str | None:
    """Say why a request cannot be answered as NDJSON, None where it can.

    `sql_values` filters the whole answer as a frame, which a stream never holds, and `with_stations` lists the
    stations of the whole answer, which a stream does not know before its end.
    """
    if getattr(request, "sql_values", None):
        return (
            "sql_values filters the whole answer, which NDJSON never holds. Use format=json, geojson or csv, or leave "
            "sql_values out and filter the lines."
        )
    if getattr(request, "with_stations", False):
        return (
            "with_stations lists the stations of the whole answer, which NDJSON does not know before its end. Use "
            "format=json or geojson, or ask format=ndjson of stations for them."
        )
    return None


def _render_ndjson(
    rows: Sequence[Mapping[str, Any]],
    frame: pl.DataFrame,
    metadata: ResponseMetadata,
    settings: _AppliedSettings | None,
) -> str:
    """Write a whole answer as NDJSON, as the REST API streams it: the head, a line for each row, the end."""
    stations = frame.get_column("station_id").n_unique() if "station_id" in frame.columns else 0
    lines = [ndjson_line(ndjson_head(metadata, settings)), *(ndjson_line(row) for row in rows)]
    lines.append(ndjson_line({"end": ndjson_end(stations, len(rows), metadata.warnings)}))
    return b"".join(lines).decode()


def render_stations(
    result: StationsResult,
    request: StationsRequest,
    *,
    max_side: int | None = None,
    metadata: ResponseMetadata | None = None,
) -> str | bytes:
    """Write a stations listing in the format the request names, the JSON formats with the `metadata` block.

    `metadata` is the block, where the caller has built it to put the same in the headers.
    """
    if request.format == "ndjson":
        metadata = metadata or response_metadata(result, request)
        return _render_ndjson(result.to_dict()["stations"], result.df, metadata, None)
    if request.format not in ("json", "geojson"):
        return result.to_format(**render_kwargs(request, max_side=max_side))
    metadata = metadata or response_metadata(result, request)
    data = result.to_dict() if request.format == "json" else result.to_ogc_feature_collection()
    return _json_answer(dict(data), request, metadata)


def render(
    result: ValuesResult | InterpolatedValuesResult | SummarizedValuesResult,
    request: ValuesRequest | InterpolationRequest | SummaryRequest,
    applied: type[_AppliedSettings],
    options: Options,
    *,
    max_side: int | None = None,
    metadata: ResponseMetadata | None = None,
) -> str | bytes:
    """Render a result in the format the request names, the JSON formats with the `metadata` block.

    With `with_metadata` the block holds its heavy parts too and the settings `applied` go next to it. The
    rest is written as `to_json` and `to_geojson` write it. `metadata` is the block, where the caller has
    built it to put the same in the headers.
    """
    if request.format == "ndjson":
        metadata = metadata or response_metadata(result, request)
        settings = _applied_settings(applied, options) if request.with_metadata else None
        return _render_ndjson(result.to_dict()["values"], result.df, metadata, settings)
    if request.format not in ("json", "geojson"):
        kwargs: dict[str, Any] = {**render_kwargs(request, max_side=max_side), "with_stations": request.with_stations}
        return result.to_format(**kwargs)
    metadata = metadata or response_metadata(result, request)
    if request.format == "json":
        data: dict[str, Any] = dict(result.to_dict(with_stations=request.with_stations))
    else:
        data = dict(result.to_ogc_feature_collection())
    settings = _applied_settings(applied, options) if request.with_metadata else None
    return _json_answer(data, request, metadata, settings)


def render_history(
    stations: StationsResult,
    history: TimeseriesHistory,
    request: HistoryRequest,
    *,
    metadata: ResponseMetadata | None = None,
) -> tuple[str, ResponseMetadata]:
    """Collect the history of the stations and write it as JSON with the `metadata` block, which is given back too."""
    answer = history.to_dict(with_metadata=False, with_stations=request.with_stations, sections=request.sections)
    metadata = metadata or response_metadata(stations, request, rows=len(answer["histories"]))
    return _json_answer(dict(answer), request, metadata), metadata


def render_issues(issues: list[str], metadata: ResponseMetadata, *, pretty: bool = False) -> str:
    """Write the issue times of a forecast network as JSON: `{"metadata": ..., "issues": [...]}`."""
    answer = {"metadata": metadata_to_dict(metadata), "issues": issues}
    return json.dumps(answer, indent=4 if pretty else None)


def render_alerts(result: DwdWeatherAlertResult, fmt: str, *, pretty: bool = False) -> tuple[str, ResponseMetadata]:
    """Write the warnings in the format asked for, the JSON formats with the `metadata` block, which is given back too.

    A GeoJSON `FeatureCollection` holds the block as a foreign member (RFC 7946 6.1) next to its `snapshot`; CSV has no
    place for it, so a CSV answer carries it in the headers alone (`response_headers`).
    """
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    metadata = alerts_metadata(DwdWeatherAlertRequest, result.df.height)
    if fmt == "csv":
        return result.to_csv(), metadata
    data = result.to_dict() if fmt == "json" else result.to_ogc_feature_collection()
    head = {"type": data.pop("type")} if fmt == "geojson" else {}
    answer = {**head, "metadata": metadata_to_dict(metadata), **data}
    return json.dumps(answer, indent=4 if pretty else None, ensure_ascii=False), metadata


def render_stripes_stations(result: StationsResult, request: StripesStationsRequest, metadata: ResponseMetadata) -> str:
    """Write the stations climate stripes are made for in the format asked for, the JSON formats with the block."""
    if request.format == "csv":
        return result.to_csv()
    data = result.to_dict() if request.format == "json" else result.to_ogc_feature_collection()
    return _json_answer(dict(data), request, metadata)


def render_stripes_values(data: StripesData, request: StripesValuesRequest, metadata: ResponseMetadata) -> str:
    """Write the values of climate stripes as JSON: the `metadata` block, the `series` they are of, and the `values`."""
    values = [
        {
            "timestamp": format_timestamp(row["timestamp"]) if row["timestamp"] else None,
            "value": row["value"],
        }
        for row in data.df.select("timestamp", "value").iter_rows(named=True)
    ]
    answer = {"metadata": metadata_to_dict(metadata), "series": data.series.model_dump(), "values": values}
    return json.dumps(answer, indent=4 if request.pretty else None)
