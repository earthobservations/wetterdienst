# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The hosts of each provider: where a redirect or a link of an answer may lead a request of it (GH-3339).

A provider's addresses are fixed in its code, but a redirect of its upstream, or a link in an answer (the next page of
a result, the address of the data, an asset), names another. `PROVIDER_HOSTS` lists, for each provider, the hosts
that its requests are served from. A request that starts at one of them is led to another of the same provider and
to no other host (`util/network.py`: `fetchable_link` for a link, `_check_redirect` for a redirect), so that an
upstream cannot make the client fetch from a host of its choosing, an internal one among them.

A host is a name, spelled out: no wildcard, no scheme or port. The name of a bucket of a shared domain (S3, an object
store) is listed whole, as another tenant can register a name that starts alike. It is the host as the provider's code
or the upstream's answer writes it, found by reading the code and, for the stores that pre-signed and asset links lead
to, by reading the answers of the upstream's public catalogue (the comments say which).
"""

from __future__ import annotations

#: The hosts that the requests of each provider (the first part of its `provider/` directory) are served from.
PROVIDER_HOSTS: dict[str, tuple[str, ...]] = {
    "aemet": (
        "opendata.aemet.es",  # the API and the `datos` links of its answers (`/opendata/sh/<id>`)
    ),
    "chmi": ("opendata.chmi.cz",),
    "dmi": ("opendataapi.dmi.dk",),
    "dwd": (
        "opendata.dwd.de",
        "www.dwd.de",  # the station catalogues that are no open data files
    ),
    "ea": ("environment.data.gov.uk",),
    "eaufrance": ("hubeau.eaufrance.fr",),
    "eccc": ("api.weather.gc.ca",),
    "eumetnet": ("www.eumetnet.eu",),
    "fmi": ("opendata.fmi.fi",),
    "geosphere": ("dataset.api.hub.geosphere.at",),
    "imgw": ("danepubliczne.imgw.pl", "dane.imgw.pl"),
    "ipma": ("api.ipma.pt",),
    "knmi": (
        "api.dataplatform.knmi.nl",
        # the store that the pre-signed link of a file leads to (`X-Amz-Signature`); read from an answer of the
        # API (2026-10-24, host only). The name of the bucket is global to S3, so it is listed whole
        "knmi-kdp-datasets-eu-west-1.s3.eu-west-1.amazonaws.com",
    ),
    "lhmt": ("api.meteo.lt",),
    "meteofrance": (
        "www.data.gouv.fr",  # the API of the catalogue, whose "latest resource" links redirect to the next
        "static.data.gouv.fr",  # the files that data.gouv.fr hosts itself
        # the store of the period files of the climate datasets and of SYNOP: 2,824 of the 2,830 resources of the four
        # datasets are named at it, the other six at static.data.gouv.fr (read from the catalogue, 2026-10-25)
        "meteofrance.s3.sbg.io.cloud.ovh.net",
    ),
    "meteoswiss": (
        "data.geo.admin.ch",  # the STAC catalogue, and the files its assets name (all 16 of an item, 2026-10-25)
    ),
    "metno": ("frost.met.no",),
    "metoffice": (
        "data.ceda.ac.uk",  # the anonymous listing
        "dap.ceda.ac.uk",  # the download, which answers with a redirect to its own login without a token
        "services.ceda.ac.uk",  # the token
    ),
    "noaa": (
        "www.ncei.noaa.gov",
        "noaa-ghcn-pds.s3.amazonaws.com",
    ),
    "nws": (
        "api.weather.gov",
        "madis-data.ncep.noaa.gov",
    ),
    "rmi": ("opendata.meteo.be",),
    "smhi": ("opendata-download-metobs.smhi.se",),
    "wsv": ("pegelonline.wsv.de",),
}


def clean_host(host: str | None) -> str:
    """Give a host name in the form it is compared in: lower case, without the root dot."""
    return (host or "").lower().rstrip(".")


def provider_of(host: str | None) -> str | None:
    """Give the provider that a host is one of, or `None` for a host that no provider lists."""
    host = clean_host(host)
    for provider, hosts in PROVIDER_HOSTS.items():
        if host in hosts:
            return provider
    return None


def hosts_of_provider(host: str | None) -> tuple[str, ...] | None:
    """Give the hosts of the provider that a host is one of, or `None` for a host that no provider lists."""
    provider = provider_of(host)
    return None if provider is None else PROVIDER_HOSTS[provider]
