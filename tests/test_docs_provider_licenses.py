# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The page of licences and credit lines, built by `docs/_ext/provider_licenses.py` from the provider metadata.

The rows are collected offline from the registry, so a provider that is added is on the page, and one that cannot be
imported fails the build rather than leaving it out. The glue to Sphinx runs on a minimal project (the extension and the
markdown of MyST); these need the `docs` group and are skipped without it (`docs.yml` runs the file with it).
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from html import unescape
from pathlib import Path

import pytest

from wetterdienst.api import Wetterdienst

_EXT = Path(__file__).resolve().parents[1] / "docs" / "_ext"
_SPEC = importlib.util.spec_from_file_location("provider_licenses", _EXT / "provider_licenses.py")
assert _SPEC is not None
assert _SPEC.loader is not None
provider_licenses = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = provider_licenses  # a dataclass looks its module up, and so does Sphinx
_SPEC.loader.exec_module(provider_licenses)


def _networks() -> list[tuple[str, str]]:
    return [(provider, network) for provider, networks in Wetterdienst.registry.items() for network in networks]


def _terms(provider: str, network: str) -> object:
    if Wetterdienst.is_standalone(provider, network):
        return Wetterdienst.resolve_standalone(provider, network).terms
    return Wetterdienst.resolve(provider, network).metadata


# --- the rows ------------------------------------------------------------------------------------------------------


def test_every_network_of_every_provider_is_on_the_page_once() -> None:
    """Each network of the registry, the standalone ones of DWD (radar, alerts) included, is in exactly one row."""
    rows = provider_licenses.license_rows()

    listed = [(row.provider, network) for row in rows for network in row.networks]

    assert sorted(listed) == sorted(_networks())
    assert {("dwd", "radar"), ("dwd", "alerts")} <= set(listed)
    assert {row.provider for row in rows} == set(Wetterdienst.registry)


def test_the_networks_of_a_provider_share_a_row_while_they_agree() -> None:
    """They do agree (`tests/ui/test_providers.py` holds them to it), so a provider is one row."""
    rows = provider_licenses.license_rows()

    assert len(rows) == len(Wetterdienst.registry)
    dwd = next(row for row in rows if row.provider == "dwd")
    assert set(dwd.networks) == set(Wetterdienst.registry["dwd"])


@pytest.mark.parametrize(("provider", "network"), _networks())
def test_a_row_has_the_terms_the_network_declares(provider: str, network: str) -> None:
    """Licence, credit line and notice are read from the declaration: the page is not a second copy of them."""
    terms = _terms(provider, network)
    row = next(row for row in provider_licenses.license_rows() if row.provider == provider and network in row.networks)

    assert row.license == terms.license  # ty: ignore[unresolved-attribute]
    assert row.attribution == terms.attribution  # ty: ignore[unresolved-attribute]
    assert row.notice == terms.notice  # ty: ignore[unresolved-attribute]
    assert row.name_english == terms.name_english  # ty: ignore[unresolved-attribute]


def test_the_rows_are_in_the_order_of_the_providers_list() -> None:
    """Sorted by the English name, as `/api/providers` lists them."""
    names = [row.name_english.casefold() for row in provider_licenses.license_rows()]

    assert names == sorted(names)


def test_eccc_is_the_row_with_a_notice() -> None:
    """The one restriction beyond a licence is shown on the page."""
    noticed = {row.provider: row.notice for row in provider_licenses.license_rows() if row.notice}

    assert set(noticed) == {"eccc"}
    assert "same restrictions" in noticed["eccc"]


def test_a_network_that_differs_gets_a_row_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """The page cannot hide a disagreement between the networks of a provider."""
    mosmix = Wetterdienst.resolve("dwd", "mosmix").metadata
    monkeypatch.setattr(mosmix, "attribution", "Another credit line")

    rows = [row for row in provider_licenses.license_rows() if row.provider == "dwd"]

    assert len(rows) == 2
    assert {row.attribution for row in rows} == {"Another credit line", "Source: Deutscher Wetterdienst"}
    assert [row.networks for row in rows if row.attribution == "Another credit line"] == [("mosmix",)]


def test_a_network_that_cannot_be_imported_fails_the_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider left out of the page quietly would be worse than no page: the error names the network."""
    from sphinx.errors import ExtensionError  # noqa: PLC0415

    def refuse(provider: str, network: str) -> object:
        msg = f"No module named 'wradlib' ({provider}/{network})"
        raise ImportError(msg)

    monkeypatch.setattr(Wetterdienst, "resolve", staticmethod(refuse))

    with pytest.raises(ExtensionError, match=r"aemet/observation cannot be imported"):
        provider_licenses.license_rows()


def test_the_licence_label_is_the_spdx_identifier_or_else_the_name() -> None:
    """As an answer's `X-Wetterdienst-License` header names it."""
    rows = {row.provider: row for row in provider_licenses.license_rows()}

    assert rows["dwd"].licence_label == "CC-BY-4.0"
    assert rows["eccc"].licence_label == rows["eccc"].license.name  # ty: ignore[unresolved-attribute]


# --- the glue to Sphinx --------------------------------------------------------------------------------------------


def _build(root: Path) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Build a project of the page and a stub for each provider's own page, warnings being errors.

    In a process of its own: Sphinx keeps node classes and parsers in the module state of the process, so a second
    build in the one that ran `test_docs_notebook_errors.py` warns of what the first registered.
    """
    pytest.importorskip("myst_parser")
    src = root / "src"
    (src / "data" / "provider").mkdir(parents=True)
    (src / "conf.py").write_text(
        f"import sys\nsys.path.insert(0, {str(_EXT)!r})\n"
        "extensions = ['myst_parser', 'provider_licenses']\nroot_doc = 'index'\n",
        encoding="utf8",
    )
    providers = sorted(Wetterdienst.registry)
    pages = [f"data/provider/{provider}/index" for provider in providers]
    for provider in providers:
        (src / "data" / "provider" / provider).mkdir()
        (src / "data" / "provider" / provider / "index.md").write_text(f"# {provider}\n", encoding="utf8")
    (src / "index.md").write_text("# Scratch\n\n```{toctree}\ndata/provider/licenses\n" + "\n".join(pages) + "\n```\n")
    (src / "data" / "provider" / "licenses.md").write_text(
        "# Licences\n\n```{provider-licenses}\n```\n", encoding="utf8"
    )
    out = root / "_build"
    process = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "sphinx", "-b", "html", "-W", "--keep-going", "-q", str(src), str(out)],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    return process, out / "data" / "provider" / "licenses.html"


def test_the_directive_builds_a_table_with_every_licence_link_and_the_notice(tmp_path: Path) -> None:
    """The licence URLs are links of the page, so the link check reaches them; notice and credit lines are text."""
    process, page = _build(tmp_path)

    # -W: any warning of the build is an error
    assert process.returncode == 0, process.stderr
    html = page.read_text(encoding="utf8")
    table = html[html.index("<table") : html.index("</table>")]
    text = unescape(re.sub(r"<[^>]+>", " ", table))
    hrefs = {unescape(href) for href in re.findall(r'href="([^"]+)"', table)}
    for provider, network in _networks():
        terms = _terms(provider, network)
        assert terms.license is None or terms.license.url in hrefs  # ty: ignore[unresolved-attribute]
        assert network in text
        if terms.attribution:  # ty: ignore[unresolved-attribute]
            assert terms.attribution in text  # ty: ignore[unresolved-attribute]
    # the notice of ECCC, and the link of each provider to its own page
    assert "ECCC data may be passed on only if every recipient agrees to the same restrictions" in text
    assert {f"{provider}/index.html" for provider in Wetterdienst.registry} <= hrefs
