# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""API request factory."""

import importlib
from typing import ClassVar

from wetterdienst.exceptions import ApiNotFoundError
from wetterdienst.model.request import TimeseriesRequest


class Wetterdienst:
    """Manage all weather data providers.

    Provide their main API request factories lazily on request.
    """

    registry: ClassVar = {
        "aemet": {
            "observation": "wetterdienst.provider.aemet.observation.AemetObservationRequest",
        },
        "dwd": {
            "observation": "wetterdienst.provider.dwd.observation.DwdObservationRequest",
            "mosmix": "wetterdienst.provider.dwd.mosmix.DwdMosmixRequest",
            "dmo": "wetterdienst.provider.dwd.dmo.DwdDmoRequest",
            "road": "wetterdienst.provider.dwd.road.DwdRoadRequest",
            "radar": "wetterdienst.provider.dwd.radar.DwdRadarValues",
            "derived": "wetterdienst.provider.dwd.derived.DwdDerivedRequest",
        },
        "eccc": {
            "observation": "wetterdienst.provider.eccc.observation.EcccObservationRequest",
        },
        "imgw": {
            "hydrology": "wetterdienst.provider.imgw.hydrology.ImgwHydrologyRequest",
            "meteorology": "wetterdienst.provider.imgw.meteorology.ImgwMeteorologyRequest",
        },
        "noaa": {
            "ghcn": "wetterdienst.provider.noaa.ghcn.NoaaGhcnRequest",
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
                is_configured = getattr(api, "is_configured", lambda: True)
                is_valid = getattr(api, "is_valid", lambda: True)
                configured = is_configured() if auth else True
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
