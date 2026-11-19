# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Sphinx extension rendering the window and the steps of every MOSMIX element as one table (GH-4176).

Provides a ``mosmix-elements`` directive so ``docs/data/provider/dwd/mosmix/elements/index.md`` builds its table at docs build
time from ``mosmix_cadence.ELEMENTS`` (the measured steps) and the metadata of ``dwd/mosmix`` (the parameter an element
is read as, and which of the products declares it), so a parameter that is added or renamed is on the page and one that
the table does not know fails the build. Nothing generated is committed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from docutils import nodes
from mosmix_cadence import ALL, ELEMENTS, EVERY_3, RUN_HOUR_UTC, Cadence
from sphinx.errors import ExtensionError
from sphinx.util.docutils import SphinxDirective

from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata

if TYPE_CHECKING:
    from sphinx.application import Sphinx

_COLUMNS = (
    "Element",
    "Parameter",
    "Window",
    "Steps (UTC)",
    "Product",
    f"First to last step, run of {RUN_HOUR_UTC:02d} UTC",
    "Note",
)
_WIDTHS = (8, 26, 8, 14, 8, 16, 30)


@dataclass(frozen=True)
class ElementRow:
    """One element: what DWD calls it, what it is read as, and when its steps fall."""

    element: str
    parameter: str
    large: bool
    small: bool
    cadence: Cadence


def element_rows() -> list[ElementRow]:
    """Join the measured steps to the metadata: one row for each element that either product declares.

    An element that a product declares and the table does not know, or the table knows and neither product declares,
    fails the build: a page that quietly left it out would be worse than none.
    """
    declared: dict[str, dict[str, Any]] = {}
    for dataset in ("large", "small"):
        for parameter in getattr(DwdMosmixMetadata.hourly, dataset).parameters:
            entry = declared.setdefault(parameter.name_original, {"parameter": parameter.name})
            entry[dataset] = True

    by_lower = {element.lower(): element for element in ELEMENTS}
    unknown = sorted(set(declared) - set(by_lower))
    absent = sorted(set(by_lower) - set(declared))
    if unknown or absent:
        msg = (
            f"mosmix-elements: elements the metadata declares and mosmix_cadence.py does not know: {unknown}; "
            f"elements it knows and no dataset declares: {absent}"
        )
        raise ExtensionError(msg)
    return [
        ElementRow(
            element=element,
            parameter=declared[element.lower()]["parameter"],
            large=declared[element.lower()].get("large", False),
            small=declared[element.lower()].get("small", False),
            cadence=cadence,
        )
        for element, cadence in ELEMENTS.items()
    ]


def window_text(cadence: Cadence) -> str:
    """Write the window of an element: the hours it covers, or that it is the state at the step."""
    return "at the step" if cadence.window is None else f"{cadence.window} h"


def steps_text(cadence: Cadence) -> str:
    """Write the UTC hours at which the steps of an element fall."""
    if cadence.hours == ALL:
        text = "every hour"
    elif cadence.hours == EVERY_3:
        text = "00, 03, ..., 21"
    else:
        text = ", ".join(f"{hour:02d}" for hour in cadence.hours)
    if cadence.extra:
        text += f" (and {', '.join(f'{hour:02d}' for hour in cadence.extra)} at some stations)"
    return text


def product_text(row: ElementRow) -> str:
    """Name the products that carry an element."""
    return " and ".join(name for name, carried in (("L", row.large), ("S", row.small)) if carried)


def range_lines(row: ElementRow) -> list[str]:
    """Write the first and the last step, in hours after the issue, for each product that carries the element."""
    lines = [f"L: +{row.cadence.l_range[0]} to +{row.cadence.l_range[1]} h"]
    if row.cadence.s_range is not None:
        lines.append(f"S: +{row.cadence.s_range[0]} to +{row.cadence.s_range[1]} h")
    return lines


def _text(value: str) -> nodes.paragraph:
    paragraph = nodes.paragraph()
    paragraph += nodes.Text(value)
    return paragraph


def _entry(*children: nodes.Node) -> nodes.entry:
    entry = nodes.entry()
    for child in children:
        entry += child
    return entry


class MosmixElementsDirective(SphinxDirective):
    """Render the window and the steps of every element as a table."""

    has_content = False
    option_spec: ClassVar[dict[str, Any]] = {}

    def run(self) -> list[nodes.Node]:
        """Build the table from the cadence of the elements and the metadata."""
        table = nodes.table()
        tgroup = nodes.tgroup(cols=len(_COLUMNS))
        table += tgroup
        for width in _WIDTHS:
            tgroup += nodes.colspec(colwidth=width)
        head = nodes.thead()
        tgroup += head
        head_row = nodes.row()
        head += head_row
        for title in _COLUMNS:
            head_row += _entry(_text(title))
        body = nodes.tbody()
        tgroup += body
        for row in _ROWS if _ROWS is not None else element_rows():
            line = nodes.row()
            line += _entry(_text(row.element))
            line += _entry(*self.parse_text_to_nodes(f"{{term}}`{row.parameter}`"))
            line += _entry(_text(window_text(row.cadence)))
            line += _entry(_text(steps_text(row.cadence)))
            line += _entry(_text(product_text(row)))
            line += _entry(*(_text(text) for text in range_lines(row)))
            line += _entry(_text(row.cadence.note))
            body += line
        return [table]


#: the rows, collected once before Sphinx forks the workers that read the pages in parallel (`-j`), as
#: `provider_licenses` does: a worker that imported the providers itself died on macOS
_ROWS: list[ElementRow] | None = None


def _collect_rows(app: Sphinx) -> None:  # noqa: ARG001
    """Read the metadata, once, when the builder is made and nothing has been forked yet."""
    global _ROWS  # noqa: PLW0603
    _ROWS = element_rows()


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the directive, and the collection of the rows before the pages are read."""
    app.connect("builder-inited", _collect_rows)
    app.add_directive("mosmix-elements", MosmixElementsDirective)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
