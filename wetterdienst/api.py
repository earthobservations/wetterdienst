# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import importlib

from wetterdienst.core.timeseries.request import TimeseriesRequest


class Wetterdienst:
    """
    Manage all weather data providers.

    Provide their main API request factories lazily on request.
    """

    registry = {
        "dwd": {
            "observation": "wetterdienst.provider.dwd.observation.DwdObservationRequest",
            "mosmix": "wetterdienst.provider.dwd.mosmix.DwdMosmixRequest",
            "dmo": "wetterdienst.provider.dwd.dmo.DwdDmoRequest",
            "road": "wetterdienst.provider.dwd.road.DwdRoadRequest",
            "radar": "wetterdienst.provider.dwd.radar.DwdRadarValues",
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
    }

    @classmethod
    def resolve(cls, provider: str, network: str):
        provider = provider.strip().lower()
        network = network.strip().lower()

        try:
            module_path, class_name = cls.registry[provider][network].rsplit(".", 1)
        except KeyError as e:
            raise KeyError(f"No API available for provider {provider} and network {network}") from e

        try:
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except ModuleNotFoundError as e:
            raise ImportError(f"Module {module_path} not found") from e
        except AttributeError as e:
            raise AttributeError(f"Class {class_name} not found in module {module_path}") from e

    def __new__(cls, provider: str, network: str) -> type[TimeseriesRequest]:
        """

        :param provider: provider of data e.g. DWD
        :param network: data network e.g. NOAAs observation
        """
        # Both provider and network should be fine (if not an exception is raised)
        return cls.resolve(provider, network)

    @classmethod
    def discover(cls):
        return {provider: list(networks.keys()) for provider, networks in cls.registry.items()}

    @classmethod
    def get_provider_names(cls):
        return list(cls.registry.keys())

    @classmethod
    def get_network_names(cls, provider: str):
        provider = provider.strip().lower()
        return list(cls.registry[provider].keys())
