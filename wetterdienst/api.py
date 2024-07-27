# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.exceptions import InvalidEnumerationError, ProviderNotFoundError
from wetterdienst.metadata.provider import Provider
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.parameter import DatasetTreeCore


class RequestRegistry(DatasetTreeCore):
    """
    Manage all weather data providers.

    Provide their main API request factories lazily on request.
    """

    class DWD(DatasetTreeCore):
        class OBSERVATION(DatasetTreeCore):
            @staticmethod
            def load() -> "DwdObservationRequest":  # noqa: F821
                from wetterdienst.provider.dwd.observation import DwdObservationRequest

                return DwdObservationRequest

        class MOSMIX(DatasetTreeCore):
            @staticmethod
            def load() -> "DwdMosmixRequest":  # noqa: F821
                from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

                return DwdMosmixRequest

        class DMO(DatasetTreeCore):
            @staticmethod
            def load() -> "DwdMosmixRequest":  # noqa: F821
                from wetterdienst.provider.dwd.dmo import DwdDmoRequest

                return DwdDmoRequest

        class ROAD(DatasetTreeCore):
            @staticmethod
            def load() -> "DwdRoadRequest":  # noqa: F821
                from wetterdienst.provider.dwd.road import DwdRoadRequest

                return DwdRoadRequest

        class RADAR(DatasetTreeCore):
            @staticmethod
            def load() -> "DwdRadarValues":  # noqa: F821
                from wetterdienst.provider.dwd.radar import DwdRadarValues

                return DwdRadarValues

    class ECCC(DatasetTreeCore):
        class OBSERVATION(DatasetTreeCore):
            @staticmethod
            def load() -> "EcccObservationRequest":  # noqa: F821
                from wetterdienst.provider.eccc.observation import (
                    EcccObservationRequest,
                )

                return EcccObservationRequest

    class IMGW(DatasetTreeCore):
        class HYDROLOGY(DatasetTreeCore):
            @staticmethod
            def load() -> "ImgwHydrologyRequest":  # noqa: F821
                from wetterdienst.provider.imgw.hydrology import (
                    ImgwHydrologyRequest,
                )

                return ImgwHydrologyRequest

        class METEOROLOGY(DatasetTreeCore):
            @staticmethod
            def load() -> "ImgwMeteorologyRequest":  # noqa: F821
                from wetterdienst.provider.imgw.meteorology import (
                    ImgwMeteorologyRequest,
                )

                return ImgwMeteorologyRequest

    class NOAA(DatasetTreeCore):
        class GHCN(DatasetTreeCore):
            @staticmethod
            def load() -> "NoaaGhcnRequest":  # noqa: F821
                from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest

                return NoaaGhcnRequest

    class WSV(DatasetTreeCore):
        class PEGEL(DatasetTreeCore):
            @staticmethod
            def load() -> "WsvPegelRequest":  # noqa: F821
                from wetterdienst.provider.wsv.pegel import WsvPegelRequest

                return WsvPegelRequest

    class EA(DatasetTreeCore):
        class HYDROLOGY(DatasetTreeCore):
            @staticmethod
            def load() -> "EAHydrologyRequest":  # noqa: F821
                from wetterdienst.provider.ea.hydrology import (
                    EAHydrologyRequest,
                )

                return EAHydrologyRequest

    class NWS(DatasetTreeCore):
        class OBSERVATION(DatasetTreeCore):
            @staticmethod
            def load() -> "NwsObservationRequest":  # noqa: F821
                from wetterdienst.provider.nws.observation import NwsObservationRequest

                return NwsObservationRequest

    class EAUFRANCE(DatasetTreeCore):
        class HUBEAU(DatasetTreeCore):
            @staticmethod
            def load() -> "HubeauRequest":  # noqa: F821
                from wetterdienst.provider.eaufrance.hubeau import HubeauRequest

                return HubeauRequest

    class GEOSPHERE(DatasetTreeCore):
        class OBSERVATION(DatasetTreeCore):
            @staticmethod
            def load() -> "GeosphereObservationRequest":  # noqa: F821
                from wetterdienst.provider.geosphere.observation import (
                    GeosphereObservationRequest,
                )

                return GeosphereObservationRequest

    @classmethod
    def discover(cls):
        return {provider.name: [network.name for network in cls[provider.name]] for provider in cls}

    @classmethod
    def resolve(cls, provider: str, network: str):
        try:
            return cls[provider][network.upper()].load()
        except AttributeError as e:
            raise KeyError(e) from e

    @classmethod
    def get_provider_names(cls):
        return [provider.name for provider in cls]

    @classmethod
    def get_network_names(cls, provider):
        return [network.name for network in cls[provider]]


class Wetterdienst:
    """Wetterdienst top-level API with links to the different available APIs"""

    endpoints = RequestRegistry

    def __new__(cls, provider: str, network: str):
        """

        :param provider: provider of data e.g. DWD
        :param network: data network e.g. NOAAs observation
        """
        # Both provider and network should be fine (if not an exception is raised)
        try:
            provider_ = parse_enumeration_from_template(provider, Provider)

            api = cls.endpoints.resolve(provider_.name, network)

            if not api:
                raise KeyError

        except (InvalidEnumerationError, KeyError) as e:
            raise ProviderNotFoundError(f"No API available for provider {provider} and network {network}") from e

        return api

    @classmethod
    def discover(cls) -> dict:
        """Display available API endpoints"""
        return cls.endpoints.discover()
