# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The formats of `to_format`, each with the arguments it takes (GH-3449).

One list for `ExportMixin.to_format`, for the `_to_image` of the results and for the surfaces that name the
formats (the command line's choices, the `format` of the REST API and the MCP tools), which
`tests/test_export_formats.py` holds to it. A format a surface offers that is not here, or one here that a surface
and `docs/usage/export.md` leave out, fails that test.

`ndjson` is the rows of a result, one JSON object a line. The REST API and the command line put a `metadata` head and an
`end` line round it and stream it, which stays theirs and is no part of this format.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from wetterdienst.exceptions import UnknownFormatError

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class Format:
    """A format `to_format` renders: its name, what renders it and the arguments that render takes."""

    name: str
    #: `data` is text of the data, `chart` a rendered figure (`to_image`)
    kind: Literal["data", "chart"]
    #: the method of the result that renders it, `to_image` for a chart
    method: str
    #: the arguments some result's method takes, which `to_format` gives it where the one it is called on takes them:
    #: `to_json` takes `with_stations` of a values result and not of a stations result
    takes: frozenset[str]
    #: rendered to an image by Kaleido, which is every chart but `html`: the size of what it renders is checked, and the
    #: browser it starts is needed
    kaleido: bool = False


_IMAGE_ARGUMENTS = frozenset({"width", "height", "scale", "max_side"})

#: the formats of `to_format`, in the order the surfaces list them
FORMATS: dict[str, Format] = {
    format_.name: format_
    for format_ in (
        Format("json", "data", "to_json", frozenset({"with_metadata", "with_stations", "indent"})),
        Format("geojson", "data", "to_geojson", frozenset({"with_metadata", "indent"})),
        # `to_csv` passes its keywords to polars, and `to_format` gives it none
        Format("csv", "data", "to_csv", frozenset()),
        # the rows and nothing else: the head and end lines of a stream are the surface's
        Format("ndjson", "data", "to_ndjson", frozenset()),
        Format("html", "chart", "to_image", _IMAGE_ARGUMENTS),
        *(
            Format(name, "chart", "to_image", _IMAGE_ARGUMENTS, kaleido=True)
            for name in ("png", "jpg", "webp", "svg", "pdf")
        ),
    )
}

#: every argument some format takes: the ones `to_format` accepts
ARGUMENTS: frozenset[str] = frozenset().union(*(format_.takes for format_ in FORMATS.values()))


def names_of(kind: Literal["data", "chart"]) -> tuple[str, ...]:
    """Give the names of the formats of a kind, in the order they are listed in."""
    return tuple(name for name, format_ in FORMATS.items() if kind == format_.kind)


def renders_with_kaleido(fmt: str) -> bool:
    """Tell whether a chart format is rendered to an image by Kaleido: the registry says, not a list of names."""
    format_ = FORMATS.get(fmt)
    return format_ is not None and format_.kaleido


def find_format(fmt: str) -> Format:
    """Find the format a caller names, in any case.

    Raises:
        UnknownFormatError: Nothing here renders it.

    """
    name = fmt.lower()
    if name not in FORMATS:
        raise UnknownFormatError(fmt, tuple(FORMATS))
    return FORMATS[name]


def refuse_unknown_arguments(kwargs: Iterable[str]) -> None:
    """Refuse an argument that no format takes, listing the ones that are.

    An argument that some other format takes is not refused: `to_format` takes one set of arguments for every format
    and gives each the ones it takes.

    Raises:
        TypeError: An argument that is the name of none.

    """
    unknown = sorted(set(kwargs) - ARGUMENTS)
    if unknown:
        names = ", ".join(repr(name) for name in unknown)
        noun = "arguments" if len(unknown) > 1 else "argument"
        msg = f"to_format() got an unexpected keyword {noun} {names}; the formats take {', '.join(sorted(ARGUMENTS))}"
        raise TypeError(msg)
