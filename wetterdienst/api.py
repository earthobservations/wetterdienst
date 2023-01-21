# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.exceptions import InvalidEnumeration, ProviderError
from wetterdienst.metadata.provider import Provider
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.parameter import DatasetTreeCore


class RequestRegistry(DatasetTreeCore):
    class DWD(DatasetTreeCore):
        @staticmethod
        @property
        def OBSERVATION():
            from wetterdienst.provider.dwd.observation import DwdObservationRequest

            return DwdObservationRequest

        @staticmethod
        @property
        def MOSMIX():
            from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

            return DwdMosmixRequest

        @staticmethod
        @property
        def RADAR():
            from wetterdienst.provider.dwd.radar import DwdRadarValues

            return DwdRadarValues

    class ECCC(DatasetTreeCore):
        @staticmethod
        @property
        def OBSERVATION():
            from wetterdienst.provider.eccc.observation import EcccObservationRequest

            return EcccObservationRequest

    class NOAA(DatasetTreeCore):
        @staticmethod
        @property
        def GHCN():
            from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest

            return NoaaGhcnRequest

    class WSV(DatasetTreeCore):
        @staticmethod
        @property
        def PEGEL():
            from wetterdienst.provider.wsv.pegel import WsvPegelRequest

            return WsvPegelRequest

    class EA(DatasetTreeCore):
        @staticmethod
        @property
        def HYDROLOGY():
            from wetterdienst.provider.environment_agency.hydrology import (
                EaHydrologyRequest,
            )

            return EaHydrologyRequest

    class NWS(DatasetTreeCore):
        @staticmethod
        @property
        def OBSERVATION():
            from wetterdienst.provider.nws.observation import NwsObservationRequest

            return NwsObservationRequest

    class EAUFRANCE(DatasetTreeCore):
        @staticmethod
        @property
        def HUBEAU():
            from wetterdienst.provider.eaufrance.hubeau import HubeauRequest

            return HubeauRequest

    class GEOSPHERE(DatasetTreeCore):
        @staticmethod
        @property
        def OBSERVATION():
            from wetterdienst.provider.geosphere.observation import (
                GeosphereObservationRequest,
            )

            return GeosphereObservationRequest

    @classmethod
    def discover(cls):
        api_endpoints = {}
        for provider in cls:
            api_endpoints[provider.__name__] = [network.fget.__name__ for network in cls[provider.__name__]]
        return api_endpoints

    @classmethod
    def resolve(cls, provider: str, network: str):
        try:
            # `.fget()` is needed to access the <property> instance.
            return cls[provider][network.upper()].fget()
        except AttributeError as ex:
            raise KeyError(ex)

    @classmethod
    def get_provider_names(cls):
        return [provider.__name__ for provider in cls]

    @classmethod
    def get_network_names(cls, provider):
        return [network.fget.__name__ for network in cls[provider]]


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

        except (InvalidEnumeration, KeyError):
            raise ProviderError(f"No API available for provider {provider} and network {network}")

        return api

    @classmethod
    def discover(cls) -> dict:
        """Display available API endpoints"""
        return cls.endpoints.discover()
