# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json

from wetterdienst.dwd.forecasts import DwdMosmixRequest
from wetterdienst.dwd.observations import DwdObservationRequest
from wetterdienst.dwd.radar import DwdRadarValues
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.provider import Provider
from wetterdienst.util.enumeration import parse_enumeration_from_template

API_ENDPOINTS = {
    Provider.DWD: {
        Kind.OBSERVATION: DwdObservationRequest,
        Kind.FORECAST: DwdMosmixRequest,
        Kind.RADAR: DwdRadarValues,
    }
}


class Wetterdienst:
    """ Wetterdienst top-level API with links to the different available APIs """

    endpoints = API_ENDPOINTS

    def __init__(self, provider: Provider, kind: Kind) -> None:
        """

        :param provider: provider of data e.g. DWD
        :param kind: kind of the data e.g. observation
        """
        # Both provider and kind should be fine (if not an exception is raised)
        provider = parse_enumeration_from_template(provider, Provider)
        kind = parse_enumeration_from_template(kind, Kind)

        api = API_ENDPOINTS.get(provider).get(kind)

        if not api:
            raise ValueError(
                f"No API available for provider {provider.value} and kind {kind.value}"
            )

        self.api = api

    def __call__(self, *args, **kwargs):
        """ Caller for API """
        return self.api(*args, **kwargs)

    @classmethod
    def discover(cls) -> str:
        """ Display available API endpoints """
        api_endpoints = {}
        for provider, kinds in cls.endpoints.items():
            api_endpoints[provider.name] = [kind.name for kind in kinds]

        return json.dumps(api_endpoints)
