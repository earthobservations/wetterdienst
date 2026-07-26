# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Metadata and enums for DWD CAP weather alerts.

The alert products are published as zipped Common Alerting Protocol (CAP) v1.2 documents at
https://opendata.dwd.de/weather/alerts/cap/ . We only expose the DWD full-snapshot ("_DWD_STAT")
products, which contain one CAP XML file per currently active warning, on either community
(Gemeinde / ``COMMUNEUNION``) or district (Landkreis / ``DISTRICT``) basis. See the official
"CAP DWD Profile" documentation for the full schema.
"""

from __future__ import annotations

from enum import Enum

DWD_ALERTS_BASE_URL = "https://opendata.dwd.de/weather/alerts/cap"


class DwdWeatherAlertGranularity(Enum):
    """Spatial granularity of the DWD CAP alert products.

    - ``community`` maps to the ``COMMUNEUNION`` products (per Gemeinde).
    - ``district`` maps to the ``DISTRICT`` products (per Landkreis).
    """

    COMMUNITY = "community"
    DISTRICT = "district"

    @property
    def product(self) -> str:
        """Return the DWD full-snapshot product directory for this granularity."""
        return {
            DwdWeatherAlertGranularity.COMMUNITY: "COMMUNEUNION_DWD_STAT",
            DwdWeatherAlertGranularity.DISTRICT: "DISTRICT_DWD_STAT",
        }[self]

    @property
    def token(self) -> str:
        """Return the granularity token used in the CAP zip filename."""
        return {
            DwdWeatherAlertGranularity.COMMUNITY: "COMMUNEUNION",
            DwdWeatherAlertGranularity.DISTRICT: "DISTRICT",
        }[self]


class DwdWeatherAlertLanguage(Enum):
    """Language of the DWD CAP alert products.

    ``multi`` (``MUL``) bundles every language into one file; only its first ``<info>`` block per
    alert is honoured by the parser, so prefer a single language for one-row-per-alert output.
    """

    GERMAN = "de"
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    MULTI = "mul"

    @property
    def suffix(self) -> str:
        """Return the language suffix used in the CAP zip filename (e.g. ``EN``)."""
        return self.value.upper()
