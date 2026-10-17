# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What each provider is: its name, country, terms of use, source and what its networks offer (GH-2565).

`/api/coverage` lists the networks and, for one, its parameters; nothing said what a provider *is*. Every network's
metadata model already holds it (`name_english`, `country`, the licence and the credit line of #3058), and this
module reads it out, with the resolutions and datasets each network offers. Nothing is downloaded, no credential is
read or probed, so the answer is as fast on a cold cache as on a warm one: whether a key is accepted is
`/api/auth`'s question, for one network. This module imports no web framework, so the command line and MCP use it
without the `restapi` extra.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict, Field

from wetterdienst.api import Wetterdienst
from wetterdienst.model.metadata import LicenseModel, NetworkKind  # noqa: TC001, needed at runtime by pydantic
from wetterdienst.ui.response_metadata import CatalogueMetadata, catalogue_metadata
from wetterdienst.util.response_warnings import warn_response

if TYPE_CHECKING:
    from wetterdienst.model.metadata import MetadataModel

log = logging.getLogger(__name__)


class ProviderDataset(BaseModel):
    """A dataset of a resolution."""

    model_config = ConfigDict(extra="forbid")

    name: str
    parameters: int = Field(description="How many parameters the dataset has, which `/api/coverage` lists.")


class ProviderResolution(BaseModel):
    """A resolution of a network."""

    model_config = ConfigDict(extra="forbid")

    name: str
    datasets: list[ProviderDataset]


class ProviderNetwork(BaseModel):
    """A network of a provider, with what it offers."""

    model_config = ConfigDict(extra="forbid")

    network: str
    kind: NetworkKind = Field(
        description="`observation`, `forecast` or `derived` for a network with stations and values; `radar` and "
        "`alerts` for a standalone one (`dwd/radar`, `dwd/alerts`), which has no resolutions to list.",
    )
    url: str = Field(description="Where the provider publishes the data of the network.")
    copyright: str
    auth: bool = Field(
        description="Whether the network needs credentials; `/api/auth` tells whether they are accepted.",
    )
    date_required: bool = Field(description="Whether a request for a dataset of the network has to give a date.")
    parameters: int = Field(description="How many parameters the network has in all of its datasets.")
    resolutions: list[ProviderResolution]


class Provider(BaseModel):
    """A provider of data, and the networks it offers."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="The name a request calls it by, `dwd`.")
    name_local: str
    name_english: str
    country: str
    country_code: str = Field(description="ISO 3166-1 alpha-2 code of the country, or `ZZ` for a multinational one.")
    license: LicenseModel | None = Field(
        description="The terms the provider publishes its data under; null where it states none.",
    )
    attribution: str | None = Field(
        description="The credit line a user of the data has to give; null where the provider states none or asks for "
        "none.",
    )
    networks: list[ProviderNetwork]


class ProvidersAnswer(BaseModel):
    """The answer of `/api/providers`."""

    model_config = ConfigDict(extra="forbid")

    metadata: CatalogueMetadata
    providers: list[Provider]


def _network(provider: str, network: str) -> tuple[ProviderNetwork, MetadataModel | None] | None:
    """Describe a network, or None where it cannot be imported on this server: it is left out, and told as a warning."""
    try:
        if Wetterdienst.is_standalone(provider, network):
            standalone = Wetterdienst.resolve_standalone(provider, network)
            terms = standalone.terms
            return (
                ProviderNetwork(
                    network=network,
                    kind=cast("NetworkKind", standalone.listing["kind"]),
                    url=terms.url,
                    copyright=terms.copyright,
                    auth=False,
                    date_required=False,
                    parameters=0,
                    resolutions=[],
                ),
                None,
            )
        metadata = Wetterdienst.resolve(provider, network).metadata
    except ImportError as e:
        warn_response(
            log,
            "network-not-importable",
            f"{provider}/{network} is left out of the providers, it cannot be imported on this server: {e}",
        )
        return None
    resolutions = [
        ProviderResolution(
            name=resolution.name,
            datasets=[ProviderDataset(name=dataset.name, parameters=len(dataset.parameters)) for dataset in resolution],
        )
        for resolution in metadata
    ]
    return (
        ProviderNetwork(
            network=network,
            kind=metadata.kind,
            url=metadata.url,
            copyright=metadata.copyright,
            auth=metadata.auth,
            date_required=any(dataset.date_required for resolution in metadata for dataset in resolution.datasets),
            parameters=sum(dataset.parameters for resolution in resolutions for dataset in resolution.datasets),
            resolutions=resolutions,
        ),
        metadata,
    )


def get_providers(provider: str | None = None) -> ProvidersAnswer:
    """Describe every provider of the registry, sorted by name, or the one named.

    A provider is what its networks say of it; they agree (`tests/ui/test_providers.py` holds the registry to it), so
    the first network's declaration speaks for the provider. The standalone networks of `dwd` say the same by their
    `terms`, and are listed after the networks that have a metadata model.

    Raises:
        ApiNotFoundError: `provider` is not in the registry.

    """
    if provider:
        # raises for a provider that is not in the registry
        Wetterdienst.get_network_names(provider)
        names = [provider.strip().lower()]
    else:
        names = list(Wetterdienst.registry)
    providers: list[Provider] = []
    for name in names:
        networks = [described for network in Wetterdienst.registry[name] if (described := _network(name, network))]
        declared = [metadata for _, metadata in networks if metadata is not None]
        if not declared:
            continue
        first = declared[0]
        providers.append(
            Provider(
                provider=name,
                name_local=first.name_local,
                name_english=first.name_english,
                country=first.country,
                country_code=first.country_code,
                license=first.license,
                attribution=first.attribution,
                networks=[network for network, _ in networks],
            )
        )
    providers.sort(key=lambda p: p.name_english.casefold())
    return ProvidersAnswer(
        metadata=catalogue_metadata(providers=len(providers), networks=sum(len(p.networks) for p in providers)),
        providers=providers,
    )
