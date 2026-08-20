# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Sphinx extension rendering the canonical parameter table as a glossary.

Provides a ``parameter-glossary`` directive so ``docs/data/parameters.md`` builds the glossary from
``wetterdienst.metadata.parameter_table`` at build time. Every canonical name becomes a ``term``
target, which provider metadata tables link to with the MyST term role, {term}`name`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from sphinx.util.docutils import SphinxDirective

from wetterdienst.metadata.parameter_table import PARAMETER_TABLE
from wetterdienst.model.unit import UnitConverter
from wetterdienst.settings import (
    _STATION_DISTANCE_HETEROGENEOUS,
    _STATION_DISTANCE_HOMOGENEOUS,
    _STATION_DISTANCE_RESOLUTION_FACTORS,
    _build_geo_station_distance,
)

if TYPE_CHECKING:
    from docutils import nodes
    from sphinx.application import Sphinx


class ParameterGlossaryDirective(SphinxDirective):
    """Render every canonical parameter as a glossary entry."""

    has_content = False
    option_spec: ClassVar[dict] = {}

    def run(self) -> list[nodes.Node]:
        """Build the glossary from the canonical parameter table."""
        unit_converter = UnitConverter()
        # the built-in default radii rather than `Settings()`, which would read WD_* env vars and a
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
            lines.append(f"  Unit type `{parameter.unit_type}`, returned in `{target.name}` ({target.symbol}).")
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
                lines.append(sentence)
            lines.append("")
        lines.append("```")
        return self.parse_text_to_nodes("\n".join(lines))


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the directive."""
    app.add_directive("parameter-glossary", ParameterGlossaryDirective)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
