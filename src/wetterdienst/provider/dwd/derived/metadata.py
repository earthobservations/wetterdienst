# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD derived metadata."""

from wetterdienst.model.metadata import build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA

cooling_degree_hours_common_parameters = [
    {
        "name": "amount_hours",
        "name_original": "Anzahl Stunden",
        "unit_type": "dimensionless",
        "unit": "dimensionless",
    },
    {
        "name": "amount_cooling_hours",
        "name_original": "Anzahl Kuehlstunden",
        "unit_type": "dimensionless",
        "unit": "dimensionless",
    },
    {
        "name": "cooling_degreehours",
        "name_original": "Kuehlgradstunden",
        "unit_type": "degree_day",
        "unit": "degree_celsius_day",
    },
    {
        "name": "cooling_days",
        "name_original": "Kuehltage",
        "unit_type": "dimensionless",
        "unit": "dimensionless",
    },
]

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
                {
                    "name": "cooling_degreehours_13",
                    "name_original": "cooling_degreehours_13",
                    "grouped": False,
                    "parameters": cooling_degree_hours_common_parameters,
                },
                {
                    "name": "cooling_degreehours_16",
                    "name_original": "cooling_degreehours_16",
                    "grouped": False,
                    "parameters": cooling_degree_hours_common_parameters,
                },
                {
                    "name": "cooling_degreehours_18",
                    "name_original": "cooling_degreehours_18",
                    "grouped": False,
                    "parameters": cooling_degree_hours_common_parameters,
                },
                {
                    "name": "climate_correction_factor",
                    "name_original": "climate_correction_factor",
                    "grouped": False,
                    "periods": ["recent"],
                    "parameters": [
                        {
                            "name": "climate_correction_factor",
                            "name_original": "KF",
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
