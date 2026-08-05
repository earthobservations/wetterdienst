# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Sphinx extension rendering the canonical parameter table as a glossary.

Provides a ``parameter-glossary`` directive so ``docs/data/parameters.md`` builds the glossary from
``wetterdienst.metadata.parameter_table`` at build time. Every canonical name becomes a ``term``
target, which provider metadata tables link to with ``{term}`name```.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from sphinx.util.docutils import SphinxDirective

from wetterdienst.metadata.parameter_table import PARAMETER_TABLE
from wetterdienst.model.unit import UnitConverter

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
        lines = ["```{glossary}"]
        for parameter in PARAMETER_TABLE:
            target = unit_converter.targets[parameter.unit_type]
            lines.append(parameter.name)
            if parameter.description:
                lines.append(f"  {parameter.description}")
                lines.append("")
            lines.append(f"  Unit type `{parameter.unit_type}`, returned in `{target.name}` ({target.symbol}).")
            lines.append("")
        lines.append("```")
        return self.parse_text_to_nodes("\n".join(lines))


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the directive."""
    app.add_directive("parameter-glossary", ParameterGlossaryDirective)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
