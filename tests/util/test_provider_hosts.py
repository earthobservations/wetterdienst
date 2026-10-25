# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The hosts of each provider, to which its redirects and the links of its answers are held (GH-3339)."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import wetterdienst
from wetterdienst.exceptions import DownloadError
from wetterdienst.util.network import RedirectRefusedError, _check_redirect, fetchable_link
from wetterdienst.util.provider_hosts import PROVIDER_HOSTS, clean_host, hosts_of_provider, provider_of


def _redirect(url: str, location: str) -> SimpleNamespace:
    """Give the part of an aiohttp response that a redirect check reads."""
    return SimpleNamespace(url=url, headers={"Location": location})


PROVIDER_ROOT = Path(wetterdienst.__file__).parent / "provider"

#: The hosts that the code of the providers names without fetching from them: the terms of a licence, the home page
#: of a provider, documentation that a message or a comment points to. A host that a provider fetches from is in
#: `PROVIDER_HOSTS`, whose entries are the only hosts a redirect or a link of an answer may lead to.
NOT_FETCHED = {
    "api.met.no": "the licence of met.no",
    "catalogue.ceda.ac.uk": "the catalogue page of the Met Office dataset, in its metadata",
    "climate.weather.gc.ca": "the glossary of ECCC, in its metadata",
    "creativecommons.org": "the licence of LHMT",
    "dataplatform.knmi.nl": "the home page of KNMI's data platform, in its metadata",
    "developer.dataplatform.knmi.nl": "the documentation of KNMI's API",
    "en.ilmatieteenlaitos.fi": "the home page of FMI",
    "imgw.pl": "the home page of IMGW",
    "meteo.data.gouv.fr": "the catalogue page of Météo-France, in its metadata",
    "www.aemet.es": "the home page of AEMET",
    "www.dmi.dk": "the documentation of DMI",
    "www.eaufrance.fr": "the home page of Eaufrance",
    "www.govdata.de": "the licence of the WSV",
    "www.ipma.pt": "the home page of IPMA",
    "www.meteoswiss.admin.ch": "the home page of MeteoSwiss",
    "www.smhi.se": "the home page of SMHI",
    "www.weather.gov": "the documentation of NWS",
    "www.zamg.ac.at": "the home page of GeoSphere Austria",
}


def _hosts_named_by_the_providers() -> dict[str, set[str]]:
    """Give each host that a string of the providers' code writes as an http(s) address, with the files that do."""
    found: dict[str, set[str]] = {}
    for path in sorted(PROVIDER_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                for match in re.finditer(r"https?://([A-Za-z0-9._-]+)", node.value):
                    found.setdefault(match.group(1).lower(), set()).add(path.relative_to(PROVIDER_ROOT).as_posix())
    return found


def test_the_hosts_are_names_of_known_providers_each_listed_once() -> None:
    """A provider is a directory of `provider/`; a host is a lower case name, with no scheme, port or wildcard."""
    directories = {path.name for path in PROVIDER_ROOT.iterdir() if path.is_dir() and path.name != "__pycache__"}
    assert set(PROVIDER_HOSTS) <= directories
    listed = [host for hosts in PROVIDER_HOSTS.values() for host in hosts]
    assert len(listed) == len(set(listed)), "a host is one provider's"
    for host in listed:
        assert re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host), host


def test_every_host_the_providers_fetch_from_is_listed() -> None:
    """A new provider, or a new address of one, is a host to list here: or to name in `NOT_FETCHED`, with its reason."""
    listed = {host for hosts in PROVIDER_HOSTS.values() for host in hosts}
    named = _hosts_named_by_the_providers()
    unlisted = {host: sorted(files) for host, files in named.items() if host not in listed | set(NOT_FETCHED)}
    assert unlisted == {}


def test_a_host_is_not_both_fetched_from_and_named_as_not_fetched() -> None:
    """`NOT_FETCHED` names only what the code writes and does not fetch from, so an entry cannot linger."""
    listed = {host for hosts in PROVIDER_HOSTS.values() for host in hosts}
    named = _hosts_named_by_the_providers()
    assert not listed & set(NOT_FETCHED)
    assert set(NOT_FETCHED) <= set(named)


_HOSTS = [(provider, host) for provider, hosts in PROVIDER_HOSTS.items() for host in hosts]


@pytest.mark.parametrize(("provider", "host"), _HOSTS, ids=[f"{provider}-{host}" for provider, host in _HOSTS])
def test_a_provider_follows_a_link_and_a_redirect_to_each_of_its_hosts_and_to_no_other(
    provider: str, host: str
) -> None:
    """From any host of a provider, a link or a redirect leads to its other hosts, and the others are refused."""
    base = f"https://{host}/start"
    assert provider_of(host) == provider
    assert hosts_of_provider(host) == PROVIDER_HOSTS[provider]
    for own in PROVIDER_HOSTS[provider]:
        link = f"https://{own}/next?page=2"
        assert fetchable_link(link, base) == link
        _check_redirect(_redirect(base, link), {}, base)  # ty: ignore[invalid-argument-type]
    others = [name for other, hosts in PROVIDER_HOSTS.items() if other != provider for name in hosts]
    foreign = [
        "example.net",
        "169.254.169.254",
        "localhost",
        f"www.{host}",
        f"evil.{host}",
        f"{host}.evil.example",
        host.split(".", 1)[1],
        "www." + host.split(".", 1)[1],
        *others,
    ]
    for name in foreign:
        if name in PROVIDER_HOSTS[provider]:
            continue
        with pytest.raises(
            DownloadError, match=rf"leads to {re.escape(name)}, which is none of the hosts of {provider}"
        ):
            fetchable_link(f"https://{name}/x", base)
        with pytest.raises(
            RedirectRefusedError, match=rf"another host \({re.escape(name)}\) than the hosts of {provider}"
        ):
            _check_redirect(_redirect(base, f"https://{name}/x"), {}, base)  # ty: ignore[invalid-argument-type]


def test_a_host_is_read_in_the_form_it_is_compared_in() -> None:
    """The case and the root dot of a name do not make another host."""
    assert clean_host("API.Weather.GOV.") == "api.weather.gov"
    assert provider_of("API.Weather.GOV.") == "nws"
    assert provider_of("example.net") is None
    assert provider_of(None) is None
    assert hosts_of_provider("example.net") is None
