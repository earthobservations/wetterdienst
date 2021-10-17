# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from typing import Union

from wetterdienst.exceptions import InvalidEnumeration, ProviderError
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.provider import Provider
from wetterdienst.provider.dwd.forecast import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.radar import DwdRadarValues
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.util.enumeration import parse_enumeration_from_template

API_ENDPOINTS = {
    Provider.DWD: {
        Kind.OBSERVATION: DwdObservationRequest,
        Kind.FORECAST: DwdMosmixRequest,
        Kind.RADAR: DwdRadarValues,
    },
    Provider.ECCC: {Kind.OBSERVATION: EcccObservationRequest},
}


class Wetterdienst:
    """ Wetterdienst top-level API with links to the different available APIs """

    endpoints = API_ENDPOINTS

    def __new__(cls, provider: Union[Provider, str], kind: Union[Kind, str]):
        """

        :param provider: provider of data e.g. DWD
        :param kind: kind of the data e.g. observation
        """
        # Both provider and kind should be fine (if not an exception is raised)
        try:
            provider_ = parse_enumeration_from_template(provider, Provider)
            kind_ = parse_enumeration_from_template(kind, Kind)

            api = cls.endpoints.get(provider_, {}).get(kind_)

            if not api:
                raise KeyError

        except (InvalidEnumeration, KeyError):
            raise ProviderError(
                f"No API available for provider {provider} and kind {kind}"
            )

        return api

    @classmethod
    def discover(cls) -> dict:
        """ Display available API endpoints """
        api_endpoints = {}
        for provider, kinds in cls.endpoints.items():
            api_endpoints[provider.name.lower()] = [kind.name.lower() for kind in kinds]

        return api_endpoints  # json.dumps(api_endpoints)
