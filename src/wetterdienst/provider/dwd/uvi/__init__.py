# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD UV index forecast provider."""

from wetterdienst.provider.dwd.uvi.api import DwdUviRequest
from wetterdienst.provider.dwd.uvi.metadata import DwdUviMetadata

__all__ = ["DwdUviMetadata", "DwdUviRequest"]
