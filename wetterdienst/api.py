# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

from wetterdienst.exceptions import InvalidEnumeration, ProviderError
from wetterdienst.metadata.provider import Provider
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.radar import DwdRadarValues
from wetterdienst.provider.eaufrance.hubeau import HubeauRequest
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.provider.environment_agency.hydrology.api import EaHydrologyRequest
from wetterdienst.provider.noaa.ghcn.api import NoaaGhcnRequest
from wetterdienst.provider.nws.observation.api import NwsObservationRequest
from wetterdienst.provider.wsv.pegel.api import WsvPegelRequest
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.parameter import DatasetTreeCore


class ApiEndpoints(DatasetTreeCore):
    class DWD(Enum):
        OBSERVATION = DwdObservationRequest  # generic name
        MOSMIX = DwdMosmixRequest
        RADAR = DwdRadarValues

    class ECCC(Enum):
        OBSERVATION = EcccObservationRequest  # generic name

    class NOAA(Enum):
        GHCN = NoaaGhcnRequest

    class WSV(Enum):
        PEGEL = WsvPegelRequest

    class EA(Enum):
        HYDROLOGY = EaHydrologyRequest

    class NWS(Enum):
        OBSERVATION = NwsObservationRequest

    class EAUFRANCE(Enum):
        HUBEAU = HubeauRequest


class Wetterdienst:
    """Wetterdienst top-level API with links to the different available APIs"""

    endpoints = ApiEndpoints

    def __new__(cls, provider: str, network: str):
        """

        :param provider: provider of data e.g. DWD
        :param network: data network e.g. NOAAs observation
        """
        # Both provider and network should be fine (if not an exception is raised)
        try:
            provider_ = parse_enumeration_from_template(provider, Provider)

            api = cls.endpoints[provider_.name][network.upper()].value

            if not api:
                raise KeyError

        except (InvalidEnumeration, KeyError):
            raise ProviderError(f"No API available for provider {provider} and network {network}")

        return api

    @classmethod
    def discover(cls) -> dict:
        """Display available API endpoints"""
        api_endpoints = {}
        for provider in cls.endpoints:
            api_endpoints[provider.__name__] = [network.name for network in cls.endpoints[provider.__name__]]

        return api_endpoints
