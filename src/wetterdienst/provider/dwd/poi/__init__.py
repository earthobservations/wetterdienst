# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD POI (current weather reports) provider."""

from wetterdienst.provider.dwd.poi.api import DwdPoiRequest
from wetterdienst.provider.dwd.poi.metadata import DwdPoiMetadata

__all__ = ["DwdPoiMetadata", "DwdPoiRequest"]
