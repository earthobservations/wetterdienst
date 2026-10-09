# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API request factory."""

import importlib
import logging
from typing import ClassVar

from pydantic import ValidationError
from pydantic_settings import SettingsError

from wetterdienst.exceptions import ApiNotFoundError
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.settings import Settings, check_settings
from wetterdienst.util.extras import missing_dependency_message

log = logging.getLogger(__name__)

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

    @classmethod
    def resolve(cls, provider: str, network: str) -> type[TimeseriesRequest]:
        """Resolve provider and network to API request class.

        Args:
            provider: Provider name
            network: Network name

        Returns:
            API request class

        """
        provider = provider.strip().lower()
        network = network.strip().lower()

        try:
            module_path, class_name = cls.registry[provider][network].rsplit(".", 1)
        except KeyError as e:
            msg = f"No API available for provider {provider} and network {network}."
            raise ApiNotFoundError(msg) from e

        try:
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except ModuleNotFoundError as e:
            # a dependency of the provider module raises this just as readily as the module itself
            # being absent, and the two want different advice. The name says which happened, and
            # the provider modules all ship with the package -- so in practice it is the former
            if e.name and module_path != e.name and not module_path.startswith(f"{e.name}."):
                msg = missing_dependency_message(f"Module {module_path}", e.name)
            else:
                msg = f"Module {module_path} not found."
            raise ImportError(msg) from e
        except AttributeError as e:
            msg = f"Class {class_name} not found in module {module_path}."
            raise AttributeError(msg) from e

    def __new__(cls, provider: str, network: str) -> type[TimeseriesRequest]:
        """Resolve provider and network to API request class.

        Args:
            provider: Provider name
            network: Network name

        Returns:
            API request class

        """
        # Both provider and network should be fine (if not an exception is raised)
        return cls.resolve(provider, network)

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

    @classmethod
    def discover(cls) -> dict:
        """Discover all available providers and networks with their metadata."""
        result = {}
        for provider, networks in cls.registry.items():
            result[provider] = {}
            for network in networks:
                try:
                    api = cls(provider, network)
                except ImportError:
                    result[provider][network] = {
                        "auth": False,
                        "configured": True,
                        "valid": True,
                        "date_required": False,
                    }
                    continue
                metadata = getattr(api, "metadata", None)
                auth = metadata.auth if metadata is not None else False
                is_valid = getattr(api, "is_valid", lambda: True)
                configured = cls.is_configured(api) if auth else True
                if not auth:
                    valid = True
                elif not configured:
                    valid = False
                else:
                    try:
                        valid = is_valid()
                    except Exception:  # noqa: BLE001
                        valid = False
                date_required = (
                    any(dataset.date_required for resolution in metadata for dataset in resolution.datasets)
                    if metadata is not None
                    else False
                )
                result[provider][network] = {
                    "auth": auth,
                    "configured": configured,
                    "valid": valid,
                    "date_required": date_required,
                }
        return result

    @classmethod
    def get_provider_names(cls) -> list[str]:
        """Get all providers."""
        return list(cls.registry.keys())

    @classmethod
    def get_network_names(cls, provider: str) -> list[str]:
        """Get all networks for a provider."""
        provider = provider.strip().lower()
        return list(cls.registry[provider].keys())
