# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IPMA (Portugal) observation provider."""

from wetterdienst.provider.ipma.observation.api import IpmaObservationRequest
from wetterdienst.provider.ipma.observation.metadata import IpmaObservationMetadata

__all__ = ["IpmaObservationMetadata", "IpmaObservationRequest"]
