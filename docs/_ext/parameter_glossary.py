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
from wetterdienst.settings import Settings

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
        # the default radii, read from the setting itself rather than restated here
        station_distance = Settings().ts_geo_station_distance
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
                sentence = (
                    f"  Interpolatable, using stations up to {station_distance[parameter.name]:g} km from the "
                    f"target point."
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
