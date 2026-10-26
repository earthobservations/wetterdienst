# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API request factory."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NoReturn, TypeAlias, cast, overload

from pydantic import ValidationError
from pydantic_settings import SettingsError

from wetterdienst.exceptions import ApiNotFoundError, MissingDependencyError
from wetterdienst.settings import Settings, check_settings
from wetterdienst.util.extras import missing_dependency_message

if TYPE_CHECKING:
    from wetterdienst.model.metadata import CoverageNetwork
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest
    from wetterdienst.provider.dwd.radar import DwdRadarValues

    #: the request class of a standalone network, which is no `TimeseriesRequest`
    StandaloneRequest: TypeAlias = type[DwdRadarValues | DwdWeatherAlertRequest]

log = logging.getLogger(__name__)

#: the members of a network in the list of every network, in the order the answer gives them
_LISTED_ORDER = ("name_short", "country", "kind", "scope", "url", "auth", "configured", "date_required")

#: the problems with the settings already logged, so a listing asked for again does not repeat them
_REPORTED_SETTINGS_PROBLEMS: set[tuple[str, ...]] = set()


class Wetterdienst:
    """Manage all weather data providers.

    Provide their main API request factories lazily on request.
    """

    registry: ClassVar = {
        "aemet": {
            "observation": "wetterdienst.provider.aemet.observation.AemetObservationRequest",
        },
        "chmi": {
            "observation": "wetterdienst.provider.chmi.observation.ChmiObservationRequest",
        },
        "dmi": {
            "observation": "wetterdienst.provider.dmi.observation.DmiObservationRequest",
        },
        "dwd": {
            "observation": "wetterdienst.provider.dwd.observation.DwdObservationRequest",
            "mosmix": "wetterdienst.provider.dwd.mosmix.DwdMosmixRequest",
            "dmo": "wetterdienst.provider.dwd.dmo.DwdDmoRequest",
            "road": "wetterdienst.provider.dwd.road.DwdRoadRequest",
            "swsmos": "wetterdienst.provider.dwd.swsmos.DwdSwsmosRequest",
            "poi": "wetterdienst.provider.dwd.poi.DwdPoiRequest",
            "phenology": "wetterdienst.provider.dwd.phenology.DwdPhenologyRequest",
            "radar": "wetterdienst.provider.dwd.radar.DwdRadarValues",
            "alerts": "wetterdienst.provider.dwd.alerts.DwdWeatherAlertRequest",
            "derived": "wetterdienst.provider.dwd.derived.DwdDerivedRequest",
        },
        "eccc": {
            "observation": "wetterdienst.provider.eccc.observation.EcccObservationRequest",
        },
        "fmi": {
            "observation": "wetterdienst.provider.fmi.observation.FmiObservationRequest",
        },
        "imgw": {
            "hydrology": "wetterdienst.provider.imgw.hydrology.ImgwHydrologyRequest",
            "meteorology": "wetterdienst.provider.imgw.meteorology.ImgwMeteorologyRequest",
        },
        "ipma": {
            "observation": "wetterdienst.provider.ipma.observation.IpmaObservationRequest",
        },
        "knmi": {
            "observation": "wetterdienst.provider.knmi.observation.KnmiObservationRequest",
        },
        "lhmt": {
            "observation": "wetterdienst.provider.lhmt.observation.LhmtObservationRequest",
        },
        "noaa": {
            "ghcn": "wetterdienst.provider.noaa.ghcn.NoaaGhcnRequest",
        },
        "rmi": {
            "observation": "wetterdienst.provider.rmi.observation.RmiObservationRequest",
        },
        "wsv": {
            "pegel": "wetterdienst.provider.wsv.pegel.WsvPegelRequest",
        },
        "ea": {
            "hydrology": "wetterdienst.provider.ea.hydrology.EAHydrologyRequest",
        },
        "nws": {
            "observation": "wetterdienst.provider.nws.observation.NwsObservationRequest",
        },
        "eaufrance": {
            "hubeau": "wetterdienst.provider.eaufrance.hubeau.HubeauRequest",
        },
        "geosphere": {
            "observation": "wetterdienst.provider.geosphere.observation.GeosphereObservationRequest",
        },
        "meteofrance": {
            "synop": "wetterdienst.provider.meteofrance.synop.MeteoFranceSynopRequest",
            "observation": "wetterdienst.provider.meteofrance.observation.MeteoFranceObservationRequest",
        },
        "meteoswiss": {
            "observation": "wetterdienst.provider.meteoswiss.observation.MeteoswissObservationRequest",
        },
        "metno": {
            "frost": "wetterdienst.provider.metno.frost.MetnoFrostRequest",
        },
        "metoffice": {
            "observation": "wetterdienst.provider.metoffice.observation.MetOfficeObservationRequest",
        },
        "smhi": {
            "observation": "wetterdienst.provider.smhi.observation.SmhiObservationRequest",
        },
    }

    #: the networks of the registry that are no timeseries networks: they have their own request class and
    #: result, no stations or values and no metadata model. `resolve_standalone` resolves them, and `resolve`
    #: refuses them
    standalone: ClassVar[frozenset[tuple[str, str]]] = frozenset({("dwd", "radar"), ("dwd", "alerts")})

    @staticmethod
    def _normalize(provider: str, network: str) -> tuple[str, str]:
        return provider.strip().lower(), network.strip().lower()

    @classmethod
    def is_standalone(cls, provider: str, network: str) -> bool:
        """Tell whether a network is a standalone one (`dwd/radar`, `dwd/alerts`) and not a timeseries network.

        Args:
            provider: Provider name
            network: Network name

        Returns:
            Whether `resolve_standalone` and not `resolve` resolves it

        """
        return cls._normalize(provider, network) in cls.standalone

    @classmethod
    def _path(cls, provider: str, network: str) -> str:
        """Tell the dotted path of the request class the registry names for a provider and network."""
        try:
            return cls.registry[provider][network]
        except KeyError as e:
            msg = f"No API available for provider {provider} and network {network}."
            raise ApiNotFoundError(msg) from e

    @classmethod
    def _import(cls, provider: str, network: str) -> type[Any]:
        """Import the request class the registry names for a provider and network."""
        module_path, class_name = cls._path(provider, network).rsplit(".", 1)
        try:
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except ModuleNotFoundError as e:
            # a dependency of the provider module raises this just as readily as the module itself
            # being absent, and the two want different advice. The name says which happened, and
            # the provider modules all ship with the package -- so in practice it is the former
            # (a module of ours that does not exist is a defect, and is not an instruction to install)
            if e.name and "." not in e.name:
                msg = missing_dependency_message(f"Module {module_path}", e.name)
                raise MissingDependencyError(msg) from e
            if e.name and e.name != module_path:
                msg = f"Module {module_path} failed to import: {e.name} not found."
            else:
                msg = f"Module {module_path} not found."
            raise ImportError(msg) from e
        except AttributeError as e:
            msg = f"Class {class_name} not found in module {module_path}."
            raise AttributeError(msg) from e

    @classmethod
    def resolve(cls, provider: str, network: str) -> type[TimeseriesRequest]:
        """Resolve provider and network to the request class of a timeseries network.

        A timeseries network has stations and values. The two networks that have not, `dwd/radar` and
        `dwd/alerts` (`Wetterdienst.standalone`), are resolved by `resolve_standalone`, and refused here
        because their classes are no `TimeseriesRequest` and take other arguments (GH-3045).

        Args:
            provider: Provider name
            network: Network name

        Returns:
            API request class

        Raises:
            ApiNotFoundError: the provider or network is not in the registry, or the network is a
                standalone one.

        """
        provider, network = cls._normalize(provider, network)
        if (provider, network) in cls.standalone:
            msg = (
                f"Provider '{provider}' and network '{network}' have no stations or values to request: it is a "
                f"standalone network, resolve it with Wetterdienst.resolve_standalone('{provider}', '{network}')."
            )
            raise ApiNotFoundError(msg)
        return cls._import(provider, network)

    @overload
    @classmethod
    def resolve_standalone(cls, provider: Literal["dwd"], network: Literal["radar"]) -> type[DwdRadarValues]: ...

    @overload
    @classmethod
    def resolve_standalone(
        cls, provider: Literal["dwd"], network: Literal["alerts"]
    ) -> type[DwdWeatherAlertRequest]: ...

    @overload
    @classmethod
    def resolve_standalone(cls, provider: str, network: str) -> StandaloneRequest: ...

    @classmethod
    def resolve_standalone(cls, provider: str, network: str) -> StandaloneRequest:
        """Resolve provider and network to the request class of a standalone network.

        A standalone network (`dwd/radar`, `dwd/alerts`) has its own request class, which takes its own
        arguments, and its own result. Neither has stations, values or a metadata model, so none of
        `stations`, `values`, `history`, `interpolate` and `summarize` takes one. The class is the one
        to import from `wetterdienst.provider.dwd.radar` or `wetterdienst.provider.dwd.alerts`, as the
        examples do; this resolves it by name, as `resolve` does a timeseries network.

        Args:
            provider: Provider name
            network: Network name

        Returns:
            API request class

        Raises:
            ApiNotFoundError: the provider or network is not in the registry, or the network is a
                timeseries network, which `resolve` resolves.

        """
        provider, network = cls._normalize(provider, network)
        # a network that is not in the registry is told first, as `resolve` tells it
        cls._path(provider, network)
        if (provider, network) not in cls.standalone:
            msg = (
                f"{provider}/{network} is a timeseries network, not a standalone one: "
                f"resolve it with Wetterdienst.resolve('{provider}', '{network}')."
            )
            raise ApiNotFoundError(msg)
        return cls._import(provider, network)

    def __new__(cls, *args: object, **kwargs: object) -> NoReturn:  # noqa: ARG004
        """Refuse the constructor form `Wetterdienst(provider, network)`, which returned a class until 0.172.0.

        A class constructed is no instance of it, and the return type could not say which kind of class came
        back (GH-3045). It is refused by naming what to write instead, rather than as the arguments of a class
        that takes none (GH-3128).

        Raises:
            TypeError: always

        """
        msg = (
            "Wetterdienst(provider, network) was removed, and Wetterdienst is not instantiated: "
            "use Wetterdienst.resolve(provider, network) for the request class of a timeseries network, "
            "or Wetterdienst.resolve_standalone(provider, network) for dwd/radar and dwd/alerts"
        )
        raise TypeError(msg)

    @staticmethod
    def is_configured(api: object) -> bool:
        """Tell whether the credentials of an auth-requiring provider are present.

        A `WD_*` variable that is invalid makes the settings unbuildable, and so every provider's
        credentials unreadable. That is told as the provider not being configured, and logged once,
        rather than raised: one malformed credential would otherwise take down a listing of all
        providers (GH-2580). The REST API refuses to start with such settings, and the CLI's
        `coverage` of all providers builds them before listing, so it tells them and exits 1.

        Args:
            api: Request class of the provider and network

        Returns:
            Whether the credentials are present

        """
        is_configured = getattr(api, "is_configured", lambda: True)
        try:
            return is_configured()
        except (ValidationError, SettingsError) as e:
            # another model's error is not the settings'
            if isinstance(e, ValidationError) and e.title != Settings.__name__:
                raise
            problems = tuple(check_settings())
            if not problems:
                raise
            if problems not in _REPORTED_SETTINGS_PROBLEMS:
                _REPORTED_SETTINGS_PROBLEMS.add(problems)
                log.warning("The settings are invalid, so no credential is read: %s", "; ".join(problems))
            return False

    @staticmethod
    def is_valid(api: object) -> bool | None:
        """Tell whether the provider accepts the credentials it is configured with.

        Only for a provider that is configured: it probes the provider.

        Args:
            api: Request class of the provider and network

        Returns:
            True if the provider accepted the credentials, False if it rejected them, None if that
            could not be told (the probe failed for another reason, or raised): a failure to check
            is not a rejection, so it is not told as one

        """
        is_valid = getattr(api, "is_valid", lambda: True)
        try:
            return is_valid()
        except Exception:
            log.warning("Could not check the credentials of %s", getattr(api, "__name__", api), exc_info=True)
            return None

    @classmethod
    def discover(cls) -> dict[str, dict[str, CoverageNetwork]]:
        """Discover all available providers and networks with what they are.

        Nothing is downloaded, so this is as fast on a cold cache as on a warm one (GH-2564). Whether
        a provider accepts the credentials it is configured with takes a request to the provider, which
        a listing of every provider must not wait for, so it is not told here: `Wetterdienst.is_valid(api)`
        checks one network, as `/api/auth` and `wetterdienst about auth` do (GH-2641).

        Per network: `name_short`, the provider's short name; `country`, the operator's; `url`, where the
        provider publishes the data; `kind`; `scope`, how far the network reaches (`global`, `national` or
        `regional`, which the country does not say; the full `extent`, with the continents and the box, is in
        `/api/providers` and in the coverage of one network, so that this list stays short); `auth` whether it
        needs credentials, `configured` whether they are present; `date_required`.

        `kind` is what the network is. A timeseries network has stations and values, and is `observation`,
        `forecast` or `derived`; those are the networks `stations`, `values`, `history`, `interpolate` and
        `summarize` take. A standalone network has its own request class and result, is `radar`
        or `alerts` (`dwd/radar` and `dwd/alerts`), and is refused by all of them with a 404 or a usage
        error. A standalone network has no metadata model, so its name, country and url are its request class's
        `listing`, which names the provider's short name and country and the url of its own products.

        A network that cannot be imported (a dependency is missing, or the install is broken) is left out,
        and so is a provider none of whose networks can: nothing is known of it, and a listing of what
        it needs credentials for or what it is would be a guess. The reason is logged as a warning. Asking
        for the network itself still tells why, as `resolve` raises the import error (GH-2801).
        """
        result: dict[str, dict[str, CoverageNetwork]] = {}
        for provider, networks in cls.registry.items():
            listed: dict[str, CoverageNetwork] = {}
            for network in networks:
                try:
                    if cls.is_standalone(provider, network):
                        standalone = cls.resolve_standalone(provider, network)
                        # no metadata model, so what the network is comes from its request class; and no credentials
                        entry = {
                            **standalone.listing,
                            "scope": standalone.terms.extent.scope,
                            "auth": False,
                            "configured": True,
                            "date_required": False,
                        }
                        # in the order of a timeseries network's entry below: name, country, kind, scope, url, ...
                        listed[network] = cast("CoverageNetwork", {key: entry[key] for key in _LISTED_ORDER})
                        continue
                    api = cls.resolve(provider, network)
                except ImportError as e:
                    # left out of the listing, so the log is where it is told (GH-2801)
                    log.warning("Left %s/%s out of the listing, it cannot be imported: %s", provider, network, e)
                    continue
                metadata = api.metadata
                date_required = any(dataset.date_required for resolution in metadata for dataset in resolution.datasets)
                listed[network] = {
                    "name_short": metadata.name_short,
                    "country": metadata.country,
                    "kind": metadata.kind,
                    "scope": metadata.extent.scope,
                    "url": metadata.url,
                    "auth": metadata.auth,
                    # not probed whether the credentials are accepted: that is a request to the provider per
                    # network, and a listing of all of them waited for each in turn (GH-2564)
                    "configured": cls.is_configured(api) if metadata.auth else True,
                    "date_required": date_required,
                }
            if listed:
                result[provider] = listed
        return result

    @classmethod
    def get_provider_names(cls) -> list[str]:
        """Get all providers."""
        return list(cls.registry.keys())

    @classmethod
    def get_network_names(cls, provider: str) -> list[str]:
        """Get all networks for a provider.

        Raises:
            ApiNotFoundError: the provider is not in the registry, as `resolve` raises it.

        """
        provider = provider.strip().lower()
        try:
            return list(cls.registry[provider].keys())
        except KeyError as e:
            msg = f"No API available for provider {provider}. Available providers: {', '.join(cls.registry)}"
            raise ApiNotFoundError(msg) from e
