# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What each provider is: its name, country, terms of use, source and what its networks offer (GH-2565).

This is the overview of who has which network: what a provider *is*, and each network it offers (its kind, extent,
source, whether it needs credentials and has them, how many parameters it has). Every network's metadata model already
holds it (`name_english`, `country`, the licence and the credit line of #3058), and this module reads it out. The
resolutions, datasets and parameters of a network are `/api/coverage`'s, for one network (GH-3996). Nothing is
downloaded and no credential is probed, so the answer is as fast on a cold cache as on a warm one: whether a key is
accepted is `/api/auth`'s question, for one network. This module imports no web framework, so the command line and
MCP use it without the `restapi` extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict, Field

from wetterdienst.api import Wetterdienst
from wetterdienst.model.metadata import (  # noqa: TC001, needed at runtime by pydantic
    Extent,
    LicenseModel,
    NetworkKind,
)
from wetterdienst.ui.response_metadata import CatalogueMetadata, catalogue_metadata
from wetterdienst.util.logging import get_one_line_logger
from wetterdienst.util.response_warnings import warn_response

if TYPE_CHECKING:
    from wetterdienst.model.metadata import MetadataModel

log = get_one_line_logger(__name__)


class ProviderNetwork(BaseModel):
    """A network of a provider: what it is and where, not what it offers (`/api/coverage` lists that)."""

    model_config = ConfigDict(extra="forbid")

    network: str
    kind: NetworkKind = Field(
        description="`observation`, `forecast` or `derived` for a network with stations and values; `radar` and "
        "`alerts` for a standalone one (`dwd/radar`, `dwd/alerts`), which has no resolutions to list.",
    )
    extent: Extent = Field(
        description="Where the stations of the network are, which the `country` of its provider does not say.",
    )
    url: str = Field(description="Where the provider publishes the data of the network.")
    copyright: str = Field(
        description="The rights holder's notice, shown for information. The credit line to cite is `attribution` of "
        "the provider.",
    )
    auth: bool = Field(
        description="Whether the network needs credentials; `/api/auth` tells whether they are accepted.",
    )
    configured: bool = Field(
        description="Whether the credentials the network needs are present on this server, true for a network that "
        "needs none. Whether the provider accepts them is not checked here: `/api/auth` does, for one network.",
    )
    date_required: bool = Field(description="Whether a request for a dataset of the network has to give a date.")
    parameters: int = Field(
        description="How many parameters the network has in all of its datasets, which `/api/coverage` lists for "
        "one network, with its resolutions and datasets."
    )


class Provider(BaseModel):
    """A provider of data, and the networks it offers."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="The name a request calls it by, `dwd`.")
    name_short: str = Field(description="The short name to write beside a flag, `DWD`.")
    name_local: str
    name_english: str
    country: str = Field(
        description="The country of the agency that runs the provider, not the extent of its data: the `extent` of "
        "each of its networks says where its stations are.",
    )
    country_code: str | None = Field(
        description="ISO 3166-1 alpha-2 code of that country, the operator's and not the extent of its data; null for "
        "a provider of several countries.",
    )
    license: LicenseModel | None = Field(
        description="The terms the provider publishes its data under; null where it states none.",
    )
    attribution: str | None = Field(
        description="The credit line to cite when the data is used, in the provider's own words where it states one; "
        "null where the provider states none or asks for none. `copyright` of each network is the rights holder's "
        "notice, shown for information.",
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
                    extent=terms.extent,
                    url=terms.url,
                    copyright=terms.copyright,
                    auth=False,
                    configured=True,
                    date_required=False,
                    parameters=0,
                ),
                None,
            )
        api = Wetterdienst.resolve(provider, network)
        metadata = api.metadata
    except ImportError as e:
        # the text of an `ImportError` is the library's: `cannot import name 'x' from 'y' (/path/to/y/__init__.py)`
        # names a path of the server, which a caller of the API has no use for (GH-3086). The log has all of it, the
        # answer the module that is missing
        log.info(f"{provider}/{network} cannot be imported: {e}")
        missing = f": the module '{e.name}' is missing" if isinstance(e, ModuleNotFoundError) and e.name else ""
        warn_response(
            log,
            "network-not-importable",
            f"{provider}/{network} is left out of the providers, it cannot be imported on this server{missing}",
        )
        return None
    return (
        ProviderNetwork(
            network=network,
            kind=metadata.kind,
            extent=metadata.extent,
            url=metadata.url,
            copyright=metadata.copyright,
            auth=metadata.auth,
            # not probed whether they are accepted: that is a request to the provider (`/api/auth`)
            configured=Wetterdienst.is_configured(api) if metadata.auth else True,
            date_required=any(dataset.date_required for resolution in metadata for dataset in resolution.datasets),
            parameters=sum(len(list(dataset)) for resolution in metadata for dataset in resolution),
        ),
        metadata,
    )


def get_providers(provider: str | None = None) -> ProvidersAnswer:
    """Describe every provider of the registry, sorted by name, or the one named.

    The resolutions, datasets and parameters of a network are not in it: `coverage` of the network lists them
    (GH-3996).

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
    parameters: set[str] = set()
    for name in names:
        networks = [described for network in Wetterdienst.registry[name] if (described := _network(name, network))]
        declared = [metadata for _, metadata in networks if metadata is not None]
        if not declared:
            continue
        first = declared[0]
        providers.append(
            Provider(
                provider=name,
                name_short=first.name_short,
                name_local=first.name_local,
                name_english=first.name_english,
                country=first.country,
                country_code=first.country_code,
                license=first.license,
                attribution=first.attribution,
                networks=[network for network, _ in networks],
            )
        )
        parameters.update(
            parameter.name
            for _, metadata in networks
            if metadata is not None
            for resolution in metadata
            for dataset in resolution
            for parameter in dataset
        )
    providers.sort(key=lambda p: p.name_english.casefold())
    return ProvidersAnswer(
        metadata=catalogue_metadata(
            providers=len(providers),
            networks=sum(len(p.networks) for p in providers),
            parameters=len(parameters),
        ),
        providers=providers,
    )
