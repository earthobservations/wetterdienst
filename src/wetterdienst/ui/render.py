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
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.unit import UnitConverter
from wetterdienst.options import SkipThreshold  # noqa: TC001, needed at runtime by pydantic

if TYPE_CHECKING:
    from collections.abc import Callable

    from wetterdienst.model.result import (
        InterpolatedValuesResult,
        StationsResult,
        SummarizedValuesResult,
        ValuesResult,
    )
    from wetterdienst.options import Options
    from wetterdienst.ui.core import InterpolationRequest, StationsRequest, SummaryRequest, ValuesRequest


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

    # not read for a summary, which has nothing for it to decide: its field is only accepted there,
    # and deprecated (GH-2333), so a summary neither passes nor reports it
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
    with_stations: bool,
    max_side: int | None = None,
) -> dict[str, Any]:
    """Give the arguments of a result's `to_format` for what the request asks to have written.

    `max_side` is the largest side of a rendered chart that is let through, which the REST API sets
    and the command line, whose caller is at the keyboard, does not.
    """
    kwargs: dict[str, Any] = {"fmt": request.format, "with_metadata": request.with_metadata}
    if with_stations:
        kwargs["with_stations"] = request.with_stations
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale
        if max_side is not None:
            kwargs["max_side"] = max_side
    return kwargs


def render_stations(
    result: StationsResult,
    request: StationsRequest,
    *,
    max_side: int | None = None,
) -> str | bytes:
    """Write a stations listing in the format the request names."""
    return result.to_format(**render_kwargs(request, with_stations=False, max_side=max_side))


def render(
    result: ValuesResult | InterpolatedValuesResult | SummarizedValuesResult,
    request: ValuesRequest | InterpolationRequest | SummaryRequest,
    applied: type[_AppliedSettings],
    options: Options,
    *,
    max_side: int | None = None,
) -> str | bytes:
    """Render a result in the format the request names, the JSON formats with the settings `applied`.

    The settings go next to the metadata, with `with_metadata` alone, and the rest is written as
    `to_json` and `to_geojson` write it.
    """
    kwargs = render_kwargs(request, with_stations=True, max_side=max_side)
    if not request.with_metadata or request.format not in ("json", "geojson"):
        return result.to_format(**kwargs)
    if request.format == "json":
        data: dict[str, Any] = dict(result.to_dict(with_metadata=True, with_stations=request.with_stations))
    else:
        data = dict(result.to_ogc_feature_collection(with_metadata=True))
    report = json.loads(_applied_settings(applied, options).model_dump_json())
    data = {"metadata": data.pop("metadata"), "settings": report, **data}
    return json.dumps(data, indent=4 if request.pretty else None, ensure_ascii=request.format == "json")
