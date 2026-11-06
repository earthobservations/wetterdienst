# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The terms of every provider are declared and written down (GH-2567).

Every network names the page its data comes from and the credit it asks for, or says that it asks for none. The
standalone networks of DWD, which `tests/ui/test_response_metadata.py` does not look at, declare a licence too. The
provider's page of the docs has a License section that links the terms the network declares, and the page on what the
project does with the data names every provider, every provider that needs a key, and every directory of the tests that
holds data files. Nothing here reads the network: what a provider's terms say is read by a person and quoted on those
pages, these tests hold the pages to the registry, the code and the files.
"""

from __future__ import annotations

import platform
import re
from pathlib import Path

import pytest

import wetterdienst
from tests.ui.test_response_metadata import LICENSE_NOT_STATED
from wetterdienst.api import Wetterdienst
from wetterdienst.settings import Settings

_ROOT = Path(__file__).resolve().parents[1]
_PROVIDER_DOCS = _ROOT / "docs" / "data" / "provider"
_DATA_USE = _PROVIDER_DOCS / "data-use.md"

#: the networks whose provider asks for no credit, with the words of its terms. A network is named here, or declares
#: an `attribution`; it is never left empty by forgetting.
ATTRIBUTION_NOT_ASKED: dict[tuple[str, str], str] = {
    ("wsv", "pegel"): (
        "PEGELONLINE puts the data under the licence DL-DE->Zero-2.0 ('Dies geschieht auf der Grundlage der Lizenz "
        "DL-DE->Zero-2.0', https://pegelonline.wsv.de/gast/nutzungsbedingungen, read 2026-11-06), which asks for none"
    ),
    ("nws", "observation"): (
        "'All of the information presented via the API is intended to be open data, free to use for any purpose' "
        "(https://www.weather.gov/documentation/services-web-api, read 2026-11-06); it names no credit"
    ),
}


def _networks() -> list[tuple[str, str]]:
    return [(provider, network) for provider, networks in Wetterdienst.registry.items() for network in networks]


def _terms(provider: str, network: str) -> object:
    if Wetterdienst.is_standalone(provider, network):
        return Wetterdienst.resolve_standalone(provider, network).terms
    return Wetterdienst.resolve(provider, network).metadata


def _section(text: str, heading: str) -> str:
    """Return the text of a `## ` section, up to the next one."""
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, flags=re.DOTALL | re.MULTILINE)
    assert match, f"no section '{heading}'"
    return match.group(1)


@pytest.mark.parametrize(("provider", "network"), _networks())
def test_every_network_names_its_source_page_and_its_credit_or_says_it_asks_for_none(
    provider: str, network: str
) -> None:
    """A source page is declared, and a credit line, or the reason for none."""
    terms = _terms(provider, network)

    assert terms.url.startswith(("https://", "http://")), f"{provider}/{network} names no page"  # ty: ignore[unresolved-attribute]
    if (provider, network) in ATTRIBUTION_NOT_ASKED:
        assert not terms.attribution, f"{provider}/{network} declares a credit now: drop it from ATTRIBUTION_NOT_ASKED"  # ty: ignore[unresolved-attribute]
    else:
        assert terms.attribution, f"{provider}/{network} declares no credit line"  # ty: ignore[unresolved-attribute]


@pytest.mark.parametrize(
    ("provider", "network"), [network for network in _networks() if Wetterdienst.is_standalone(*network)]
)
def test_a_standalone_network_declares_its_licence_or_says_why_not(provider: str, network: str) -> None:
    """The other networks are held to it by `test_response_metadata.py`; the radar and the alerts of DWD are not."""
    terms = _terms(provider, network)

    if (provider, network) in LICENSE_NOT_STATED:
        assert terms.license is None, f"{provider}/{network} states a licence now: drop it from LICENSE_NOT_STATED"  # ty: ignore[unresolved-attribute]
        return
    assert terms.license is not None, f"{provider}/{network} declares no licence"  # ty: ignore[unresolved-attribute]
    assert terms.license.name  # ty: ignore[unresolved-attribute]
    assert terms.license.url.startswith("https://")  # ty: ignore[unresolved-attribute]


def test_no_network_is_named_that_does_not_exist() -> None:
    """A network that goes is dropped from the registry of credits that are not asked for."""
    assert set(ATTRIBUTION_NOT_ASKED) <= set(_networks())


@pytest.mark.parametrize("provider", sorted(Wetterdienst.registry))
def test_the_license_section_of_a_provider_links_the_terms_its_networks_declare(provider: str) -> None:
    """A reader finds, in the License section, the licence that an answer of each network names."""
    section = _section((_PROVIDER_DOCS / provider / "index.md").read_text(encoding="utf8"), "License")

    for network in Wetterdienst.registry[provider]:
        terms = _terms(provider, network)
        if terms.license is None:  # ty: ignore[unresolved-attribute]
            continue
        link = terms.license.url.rstrip("/")  # ty: ignore[unresolved-attribute]
        assert link in section, f"{provider}/{network}: the License section does not link {link}"


def test_the_licence_page_and_the_provider_index_name_the_page_on_what_the_project_does_with_the_data() -> None:
    """Linked from the table of licences and in the toctree of the providers, so that it is found and built."""
    licences = (_PROVIDER_DOCS / "licenses.md").read_text(encoding="utf8")
    index = (_PROVIDER_DOCS / "index.md").read_text(encoding="utf8")

    assert "](data-use.md)" in licences
    assert re.search(r"^data-use\.md$", index, flags=re.MULTILINE)


@pytest.mark.parametrize("provider", sorted(Wetterdienst.registry))
def test_the_page_on_the_data_names_every_provider(provider: str) -> None:
    """Each provider has a row in the table of what its terms ask of a caller."""
    section = _section(_DATA_USE.read_text(encoding="utf8"), "How it asks the provider")

    assert f"]({provider}/index.md#license)" in section, f"{provider} has no row in 'How it asks the provider'"


def test_every_provider_that_needs_a_key_is_in_the_table_of_keys() -> None:
    """A network that needs a key or an account is read for what its terms say of sharing it, by name."""
    section = _section(_DATA_USE.read_text(encoding="utf8"), "Keys and credentials")
    keyed = sorted({provider for provider, network in _networks() if getattr(_terms(provider, network), "auth", False)})

    assert keyed == ["aemet", "knmi", "metno", "metoffice"]
    for provider in keyed:
        assert f"]({provider}/index.md#license)" in section, f"{provider} needs a key and is not in the table of keys"


def test_the_section_on_the_files_names_every_directory_of_the_tests_that_holds_data_files() -> None:
    """A real file added to the tests is named, with its terms, where the repository says what it holds."""
    section = _section(_DATA_USE.read_text(encoding="utf8"), "The repository's own files")
    provider_tests = _ROOT / "tests" / "provider"
    directories = {
        path.parent.relative_to(_ROOT).as_posix()
        for path in provider_tests.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not path.name.startswith(".")
        and path.suffix not in {".py", ".pyc"}
        # the hashes of the frames the core produced hold no provider data
        and path.name != "frames.snapshot.json"
    }

    assert directories, "no data file found in tests/provider"
    for directory in sorted(directories):
        assert f"`{directory}/`" in section, f"{directory}/ holds data files and the page does not name it"


def test_the_paths_the_section_on_the_files_names_exist() -> None:
    """A path that moves or goes is not left in the notice."""
    section = _section(_DATA_USE.read_text(encoding="utf8"), "The repository's own files")
    paths = re.findall(r"`((?:tests|docs|src)/[^`\s]+?)`", section)

    assert paths
    for path in paths:
        assert (_ROOT / path).exists(), f"the notice names {path}, which is not there"


def test_the_credit_sentences_of_imgw_are_beside_its_rows_in_the_notice_and_in_the_code() -> None:
    """IMGW's two Polish sentences, the `attribution` it declares, stand in the notice and beside its rows."""
    attribution = Wetterdienst.resolve("imgw", "meteorology").metadata.attribution
    assert attribution
    source, processed = (sentence.strip() for sentence in attribution.rstrip(".").split(". ", 1))
    section = _section(_DATA_USE.read_text(encoding="utf8"), "The repository's own files")

    assert source in section
    assert processed in section
    # in the code the sentences are broken after the dash, to keep a line short
    for path in (
        "tests/provider/imgw/meteorology/test_api.py",
        "tests/provider/imgw/hydrology/test_api.py",
        "tests/provider/station_catalogue_stubs.py",
        "tests/provider/value_stubs.py",
    ):
        text = (_ROOT / path).read_text(encoding="utf8")
        for sentence in (source, processed):
            head, tail = sentence.split(" \u2013 ", 1)
            assert head in text, f"{path}: the credit of IMGW is not beside its rows"
            assert tail in text, f"{path}: the credit of IMGW is not beside its rows"


def test_the_user_agent_is_the_one_the_page_says_and_no_header_asks_a_provider_not_to_cache() -> None:
    """The page tells the format of the default User-Agent and that no cache header is sent, as the library does."""
    page = _DATA_USE.read_text(encoding="utf8")
    headers = {name.lower(): value for name, value in Settings().fsspec_client_kwargs["headers"].items()}

    assert "`wetterdienst/<version> (<system>)`" in page
    assert headers["user-agent"] == f"wetterdienst/{wetterdienst.__version__} ({platform.system()})"
    assert "`Cache-Control: no-cache` and no `Pragma` header" in page
    assert "cache-control" not in headers
    assert "pragma" not in headers
