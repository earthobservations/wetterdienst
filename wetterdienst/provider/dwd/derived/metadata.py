# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD derived metadata."""

from wetterdienst.model.metadata import build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA

DwdDerivedMetadata = {
    **_METADATA,
    "kind": "derived",
    "timezone": "Europe/Berlin",
    "timezone_data": "UTC",
    "resolutions": [
        {
            "name": "monthly",
            "name_original": "monthly",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": "heating_degreedays",
                    "name_original": "heating_degreedays",
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "amount_days_per_month",
                            "name_original": "Anzahl Tage",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "heating_degreedays",
                            "name_original": "Monatsgradtage",
                            "unit_type": "degree_day",
                            "unit": "degree_celsius_day",
                        },
                        {
                            "name": "amount_heating_degreedays_per_month",
                            "name_original": "Anzahl Heiztage",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                    ],
                },
            ],
        },
    ],
}
DwdDerivedMetadata = build_metadata_model(DwdDerivedMetadata, "DwdDerivedMetadata")
