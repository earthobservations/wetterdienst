# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Sphinx extension rendering the canonical parameter table as a glossary.

Provides a ``parameter-glossary`` directive so ``docs/data/parameters.md`` builds the glossary from
``wetterdienst.metadata.parameter_table`` at build time. Every canonical name becomes a ``term``
target, which provider metadata tables link to with the MyST term role, {term}`name`.

The directives ``aggregation-definitions`` and ``timestamp-position-definitions`` render the one-line definition of
every member of the two closed sets of the answers (``AGGREGATION_DEFINITIONS``, ``TIMESTAMP_POSITION_DEFINITIONS``) as
the tables of ``docs/data/parameters.md``, so that the page says what the code says. Nothing generated is committed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from sphinx.util.docutils import SphinxDirective

from wetterdienst.metadata.parameter_table import AGGREGATION_DEFINITIONS, PARAMETER_TABLE
from wetterdienst.model.metadata import TIMESTAMP_POSITION_DEFINITIONS
from wetterdienst.model.unit import UnitConverter
from wetterdienst.options import (
    _STATION_DISTANCE_HETEROGENEOUS,
    _STATION_DISTANCE_HOMOGENEOUS,
    _STATION_DISTANCE_RESOLUTION_FACTORS,
    _build_geo_station_distance,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from docutils import nodes
    from sphinx.application import Sphinx


class ParameterGlossaryDirective(SphinxDirective):
    """Render every canonical parameter as a glossary entry."""

    has_content = False
    option_spec: ClassVar[dict] = {}

    def run(self) -> list[nodes.Node]:
        """Build the glossary from the canonical parameter table."""
        unit_converter = UnitConverter()
        # the built-in default radii rather than `Options()`, which would read WD_* env vars and a
        # .env from wherever the docs are built and so document the builder's configuration
        station_distance = _build_geo_station_distance(
            _STATION_DISTANCE_HOMOGENEOUS,
            _STATION_DISTANCE_HETEROGENEOUS,
            {},
        )
        # the radius of a heterogeneous parameter follows the resolution, so the sentence names the
        # span rather than one number that would only be right at hourly resolution
        factors = _STATION_DISTANCE_RESOLUTION_FACTORS.values()
        span = (_STATION_DISTANCE_HETEROGENEOUS * min(factors), _STATION_DISTANCE_HETEROGENEOUS * max(factors))
        lines = ["```{glossary}"]
        for parameter in PARAMETER_TABLE:
            target = unit_converter.targets[parameter.unit_type]
            lines.append(parameter.name)
            lines.append(f"  {parameter.description}")
            lines.append("")
            if parameter.quality_flag:
                # a term for the provider tables to link to, but no parameter: `/api/glossary` leaves it out and
                # a reader of this page is sent to the page that tells what the column holds
                lines.append(
                    "  Not a parameter, and not in the `glossary` of the REST API, the CLI and the MCP server: "
                    "it is the `quality_flags` column of the values. See [Quality flags](quality-flags.md)."
                )
                lines.append("")
                continue
            lines.append(f"  Unit type `{parameter.unit_type}`, returned in `{target.name}` ({target.symbol}).")
            lines.append("")
            if parameter.aggregation:
                # the canonical value, which `glossary` gives; a provider's `coverage` has its own for a plain name
                lines.append(f"  Aggregation `{parameter.aggregation}`.")
                lines.append("")
            if not parameter.interpolation:
                lines.append("  Not interpolatable.")
            else:
                if parameter.interpolation == "heterogeneous":
                    sentence = (
                        f"  Interpolatable, using stations up to {station_distance[parameter.name]:g} km from the "
                        f"target point at hourly resolution, {span[0]:g} km at the finest and {span[1]:g} km at the "
                        f"coarsest -- the radius follows the accumulation period."
                    )
                else:
                    sentence = (
                        f"  Interpolatable, using stations up to {station_distance[parameter.name]:g} km from the "
                        f"target point, at every resolution."
                    )
                if parameter.zero_inflated:
                    sentence += " Interpolated values are thresholded on occurrence."
                if parameter.lapse_rate:
                    sentence += (
                        f" Falls with height at {parameter.lapse_rate * 100:g} per 100 m, which an "
                        f"interpolation or summary corrects for when given an elevation."
                    )
                lines.append(sentence)
            lines.append("")
        lines.append("```")
        return self.parse_text_to_nodes("\n".join(lines))


def definitions_table(header: str, definitions: Mapping[str, str]) -> str:
    """Make a table of a member and its definition, in the order of the set."""
    lines = [f"| `{header}` | meaning |", "| --- | --- |"]
    lines += [f"| `{member}` | {definition} |" for member, definition in definitions.items()]
    return "\n".join(lines)


class AggregationDefinitionsDirective(SphinxDirective):
    """Render the members of `aggregation` with their definitions."""

    has_content = False
    option_spec: ClassVar[dict] = {}

    def run(self) -> list[nodes.Node]:
        """Build the table from `AGGREGATION_DEFINITIONS`."""
        return self.parse_text_to_nodes(definitions_table("aggregation", AGGREGATION_DEFINITIONS))


class TimestampPositionDefinitionsDirective(SphinxDirective):
    """Render the members of `timestamp_position` with their definitions."""

    has_content = False
    option_spec: ClassVar[dict] = {}

    def run(self) -> list[nodes.Node]:
        """Build the table from `TIMESTAMP_POSITION_DEFINITIONS`."""
        return self.parse_text_to_nodes(definitions_table("timestamp_position", TIMESTAMP_POSITION_DEFINITIONS))


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the directive."""
    app.add_directive("parameter-glossary", ParameterGlossaryDirective)
    app.add_directive("aggregation-definitions", AggregationDefinitionsDirective)
    app.add_directive("timestamp-position-definitions", TimestampPositionDefinitionsDirective)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
