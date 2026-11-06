# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The terms of every provider are declared and written down (GH-2567).

Every network names the page its data comes from, the licence or terms it is published under, and the credit it asks
for, or says that it asks for none. The provider's page of the docs has a License section, and the page on what the
project does with the data names every provider and every provider that needs a key. Nothing here reads the network:
what a provider's terms say is read by a person and quoted on those pages, these tests hold the pages to the registry.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wetterdienst.api import Wetterdienst
from wetterdienst.settings import Settings

_PROVIDER_DOCS = Path(__file__).resolve().parents[1] / "docs" / "data" / "provider"
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
def test_every_network_has_a_source_page_a_licence_and_a_credit(provider: str, network: str) -> None:
    """URL, licence (name and a link) and attribution are declared, or the missing credit is named with its reason."""
    terms = _terms(provider, network)

    assert terms.url.startswith(("https://", "http://")), f"{provider}/{network} names no page"  # ty: ignore[unresolved-attribute]
    assert terms.license is not None, f"{provider}/{network} declares no licence"  # ty: ignore[unresolved-attribute]
    assert terms.license.name  # ty: ignore[unresolved-attribute]
    assert terms.license.url.startswith("https://")  # ty: ignore[unresolved-attribute]
    if (provider, network) in ATTRIBUTION_NOT_ASKED:
        assert not terms.attribution, f"{provider}/{network} declares a credit now: drop it from ATTRIBUTION_NOT_ASKED"  # ty: ignore[unresolved-attribute]
    else:
        assert terms.attribution, f"{provider}/{network} declares no credit line"  # ty: ignore[unresolved-attribute]


def test_no_network_is_named_that_does_not_exist() -> None:
    """A network that goes is dropped from the registry of credits that are not asked for."""
    assert set(ATTRIBUTION_NOT_ASKED) <= set(_networks())


def test_a_credit_not_asked_has_its_reason_quoted() -> None:
    """The reason is the provider's words and the page they were read at, with the day."""
    for reason in ATTRIBUTION_NOT_ASKED.values():
        assert "https://" in reason
        assert "read 20" in reason


@pytest.mark.parametrize("provider", sorted(Wetterdienst.registry))
def test_every_provider_page_has_a_license_section_that_names_its_terms(provider: str) -> None:
    """The section links the terms and is no longer a sentence that sends the reader off to look."""
    text = (_PROVIDER_DOCS / provider / "index.md").read_text(encoding="utf8")

    section = _section(text, "License")

    assert "](http" in section, f"{provider}: the License section links no terms"
    assert "check the portal" not in section.lower()


def test_the_licence_page_names_the_page_on_what_the_project_does_with_the_data() -> None:
    """Linked from the table of licences and from the provider index, so that it is found."""
    licences = (_PROVIDER_DOCS / "licenses.md").read_text(encoding="utf8")
    index = (_PROVIDER_DOCS / "index.md").read_text(encoding="utf8")

    assert "(data-use.md)" in licences
    assert "data-use.md" in index


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


def test_the_section_on_the_files_names_the_terms_that_stand_in_the_way() -> None:
    """The IMGW and LHMT licences and the OPERA list, which no licence covers, are named where the fixtures are."""
    section = _section(_DATA_USE.read_text(encoding="utf8"), "The repository's own files")

    for needle in ("IMGW", "CC BY-NC-ND 4.0", "LHMT", "CC BY-SA 4.0", "OPERA"):
        assert needle in section


def test_what_the_page_says_the_library_sends_to_a_provider() -> None:
    """`User-Agent` names the library and no person, and no header asks the provider not to cache."""
    headers = {name.lower(): value for name, value in Settings().fsspec_client_kwargs["headers"].items()}

    assert re.fullmatch(r"wetterdienst/\S+ \(\S+\)", headers["user-agent"])
    assert "cache-control" not in headers
    assert "pragma" not in headers
