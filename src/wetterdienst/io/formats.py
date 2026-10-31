# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The formats of `to_format`, each with the arguments it takes (GH-3449).

One list for `ExportMixin.to_format`, for the `_to_image` of the results and for the surfaces that name the
formats (the command line's choices, the `format` of the REST API and the MCP tools), which
`tests/test_export_formats.py` holds to it. A format a surface offers that is not here, or one here that a surface
and `docs/usage/export.md` leave out, fails that test.

`ndjson` is not a format of `to_format`: the surfaces stream it, and the library writes the same rows as a `.jsonl`
file target.
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


_IMAGE_ARGUMENTS = frozenset({"width", "height", "scale", "max_side"})

#: the formats of `to_format`, in the order the surfaces list them
FORMATS: dict[str, Format] = {
    format_.name: format_
    for format_ in (
        Format("json", "data", "to_json", frozenset({"with_metadata", "with_stations", "indent"})),
        Format("geojson", "data", "to_geojson", frozenset({"with_metadata", "indent"})),
        # `to_csv` passes its keywords to polars, and `to_format` gives it none
        Format("csv", "data", "to_csv", frozenset()),
        *(Format(name, "chart", "to_image", _IMAGE_ARGUMENTS) for name in ("html", "png", "jpg", "webp", "svg", "pdf")),
    )
}

#: every argument some format takes: the ones `to_format` accepts
ARGUMENTS: frozenset[str] = frozenset().union(*(format_.takes for format_ in FORMATS.values()))


def names_of(kind: Literal["data", "chart"]) -> tuple[str, ...]:
    """Give the names of the formats of a kind, in the order they are listed in."""
    return tuple(name for name, format_ in FORMATS.items() if kind == format_.kind)


def find_format(fmt: str, among: Iterable[str] | None = None) -> Format:
    """Find the format a caller names, in any case, among the ones given (all, by default).

    Raises:
        UnknownFormatError: Nothing here renders it, or `among` leaves it out.

    """
    allowed = tuple(FORMATS if among is None else among)
    name = fmt.lower()
    if name not in allowed:
        raise UnknownFormatError(fmt, allowed)
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
        msg = f"to_format() got an unexpected keyword argument {names}; the formats take {', '.join(sorted(ARGUMENTS))}"
        raise TypeError(msg)
