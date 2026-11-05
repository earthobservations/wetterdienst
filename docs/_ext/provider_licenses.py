# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Sphinx extension rendering the licence, credit line and notice of every provider as one table (GH-2567).

Provides a ``provider-licenses`` directive so ``docs/data/provider/licenses.md`` builds its table from the provider
metadata at build time: what the answers of the library report as ``metadata.provider.license``, ``attribution`` and
``notice`` is what the page says, because it is read from the same declarations. Nothing generated is committed.

The table has a row for every provider and the terms its networks declare: the networks of a provider that agree
(they all do, which ``tests/ui/test_providers.py`` holds them to) share a row, and a network that did not would get a
row of its own, so that the page cannot hide a disagreement. The standalone networks of DWD (radar, alerts), which
have no metadata model, are read from their ``ProviderTerms``. A network that cannot be imported fails the build: a
provider left out of the page quietly would be a worse page than none.

The licence column links the page of the licence, or of the provider's own terms where it has no licence of its own,
so the link check of the docs (``uv run poe "docs:linkcheck"``) reaches each of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from docutils import nodes
from sphinx.errors import ExtensionError
from sphinx.util.docutils import SphinxDirective

from wetterdienst.api import Wetterdienst

if TYPE_CHECKING:
    from sphinx.application import Sphinx

    from wetterdienst.model.metadata import LicenseModel, MetadataModel, ProviderTerms

_COLUMNS = ("Provider", "Networks", "Licence", "Credit line", "Notice")
_WIDTHS = (16, 12, 24, 28, 20)


@dataclass(frozen=True)
class LicenseRow:
    """The terms of one provider, for the networks that declare these."""

    provider: str
    name_english: str
    networks: tuple[str, ...]
    license: LicenseModel | None
    attribution: str | None
    notice: str | None

    @property
    def licence_label(self) -> str:
        """Name the licence as an answer does: its SPDX identifier where it has one, else its name."""
        if self.license is None:
            return ""
        return self.license.spdx_id or self.license.name


def _terms(provider: str, network: str) -> MetadataModel | ProviderTerms:
    """Read what a network says of its provider: its metadata model, or the terms of a standalone network."""
    try:
        if Wetterdienst.is_standalone(provider, network):
            return Wetterdienst.resolve_standalone(provider, network).terms
        return Wetterdienst.resolve(provider, network).metadata
    except ImportError as e:
        msg = (
            f"provider-licenses: {provider}/{network} cannot be imported, so its terms cannot be listed ({e}); "
            "the docs are built with the extras of the `docs` flavour of .github/workflows/install.sh"
        )
        raise ExtensionError(msg) from e


def license_rows() -> list[LicenseRow]:
    """Collect the terms of every network of the registry, one row for each provider and each set of terms.

    Sorted by the English name of the provider, as `/api/providers` is. The networks of a row are in the order of the
    registry.
    """
    grouped: dict[tuple[str, str | None, str | None, str | None], list[str]] = {}
    declared: dict[tuple[str, str | None, str | None, str | None], LicenseRow] = {}
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            terms = _terms(provider, network)
            key = (
                provider,
                terms.license.model_dump_json() if terms.license else None,
                terms.attribution,
                terms.notice,
            )
            grouped.setdefault(key, []).append(network)
            declared.setdefault(
                key,
                LicenseRow(
                    provider=provider,
                    name_english=terms.name_english,
                    networks=(),
                    license=terms.license,
                    attribution=terms.attribution,
                    notice=terms.notice,
                ),
            )
    rows = [
        LicenseRow(
            provider=row.provider,
            name_english=row.name_english,
            networks=tuple(grouped[key]),
            license=row.license,
            attribution=row.attribution,
            notice=row.notice,
        )
        for key, row in declared.items()
    ]
    return sorted(rows, key=lambda row: row.name_english.casefold())


def _text(value: str | None, *, missing: str) -> nodes.paragraph:
    """Write a cell of plain text, which is never read as markup; `missing` stands for a null."""
    paragraph = nodes.paragraph()
    paragraph += nodes.Text(value if value else missing)
    return paragraph


def _entry(*children: nodes.Node) -> nodes.entry:
    entry = nodes.entry()
    for child in children:
        entry += child
    return entry


class ProviderLicensesDirective(SphinxDirective):
    """Render the licence, the credit line and the notice of every provider as a table."""

    has_content = False
    option_spec: ClassVar[dict[str, Any]] = {}

    def _licence_cell(self, row: LicenseRow) -> nodes.entry:
        if row.license is None:
            return _entry(_text(None, missing="None stated by the provider"))
        link = nodes.paragraph()
        reference = nodes.reference("", "", internal=False, refuri=row.license.url)
        reference += nodes.Text(row.licence_label)
        link += reference
        cell = _entry(link)
        # the name beside an identifier that stands for it, which the identifier alone does not tell
        if row.license.spdx_id:
            cell += _text(row.license.name, missing="")
        return cell

    def _provider_cell(self, row: LicenseRow) -> nodes.entry:
        # the provider's own page, which keeps its clauses: a link of the markdown, resolved from this page's folder
        return _entry(*self.parse_text_to_nodes(f"[{row.name_english}]({row.provider}/index.md)"))

    def run(self) -> list[nodes.Node]:
        """Build the table from the metadata of every network."""
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
            head_row += _entry(_text(title, missing=""))
        body = nodes.tbody()
        tgroup += body
        for row in license_rows():
            line = nodes.row()
            line += self._provider_cell(row)
            line += _entry(_text(", ".join(row.networks), missing=""))
            line += self._licence_cell(row)
            line += _entry(_text(row.attribution, missing="None stated"))
            line += _entry(_text(row.notice, missing="None"))
            body += line
        return [table]


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the directive."""
    app.add_directive("provider-licenses", ProviderLicensesDirective)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
