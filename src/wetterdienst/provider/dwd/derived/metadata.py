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
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": "radiation_global",
                    "name_original": "radiation_global",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_952",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "surface_irradiance",
                            "name_original": "fg_duett",
                            "unit_type": "energy_per_area",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "hourly_global_radiation_uncertainty",
                            "name_original": "fg_un_duett",
                            "unit_type": "energy_per_area",
                            "unit": "joule_per_square_centimeter",
                        },
                    ],
                },
                {
                    "name": "sunshine_duration",
                    "name_original": "sunshine_duration",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_952",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "hourly_sunshine_duration",
                            "name_original": "sd_duett",
                            "unit_type": "time",
                            "unit": "minute",
                        },
                        {
                            "name": "hourly_sunshine_duration_uncertainty",
                            "name_original": "fg_un_duett",
                            "unit_type": "time",
                            "unit": "minute",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": "soil",
                    "name_original": "soil",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "ts05",
                            "name_original": "ts05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "ts10",
                            "name_original": "ts10",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "ts20",
                            "name_original": "ts20",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "ts50",
                            "name_original": "ts50",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "ts100",
                            "name_original": "ts100",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "tsls05",
                            "name_original": "tsls05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "tssl05",
                            "name_original": "tssl05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "zfumi",
                            "name_original": "zfumi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "ztkmi",
                            "name_original": "ztkmi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "ztumi",
                            "name_original": "ztumi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "bfgl01_ag",
                            "name_original": "bfgl01_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl02_ag",
                            "name_original": "bfgl02_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl03_ag",
                            "name_original": "bfgl03_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl04_ag",
                            "name_original": "bfgl04_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl05_ag",
                            "name_original": "bfgl05_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl06_ag",
                            "name_original": "bfgl06_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgs_ag",
                            "name_original": "bfgs_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl_ag",
                            "name_original": "bfgl_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfws_ag",
                            "name_original": "bfws_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfwl_ag",
                            "name_original": "bfwl_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfms_ag",
                            "name_original": "bfms_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfml_ag",
                            "name_original": "bfml_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "vpgfao",
                            "name_original": "vpgfao",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vpgh",
                            "name_original": "vpgh",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrgs_ag",
                            "name_original": "vrgs_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrgl_ag",
                            "name_original": "vrgl_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrws_ag",
                            "name_original": "vrws_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrwl_ag",
                            "name_original": "vrwl_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrms_ag",
                            "name_original": "vrms_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrml_ag",
                            "name_original": "vrml_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
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
                {
                    "name": "soil",
                    "name_original": "soil",
                    "grouped": True,
                    "periods": ["historical", "recent"],
                    "parameters": [
                        {
                            "name": "ts05",
                            "name_original": "mittel von ts05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "ts10",
                            "name_original": "mittel von ts10",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "ts20",
                            "name_original": "mittel von ts20",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "ts50",
                            "name_original": "mittel von ts50",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "ts100",
                            "name_original": "mittel von ts100",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "tsls05",
                            "name_original": "mittel von tsls05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "tssl05",
                            "name_original": "mittel von tssl05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "zfumi",
                            "name_original": "maximum von zfumi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "ztkmi",
                            "name_original": "maximum von ztkmi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "ztumi",
                            "name_original": "maximum von ztumi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "bfgl01_ag",
                            "name_original": "mittel von bfgl01_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl02_ag",
                            "name_original": "mittel von bfgl02_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl03_ag",
                            "name_original": "mittel von bfgl03_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl04_ag",
                            "name_original": "mittel von bfgl04_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl05_ag",
                            "name_original": "mittel von bfgl05_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl06_ag",
                            "name_original": "mittel von bfgl06_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgs_ag",
                            "name_original": "mittel von bfgs_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfgl_ag",
                            "name_original": "mittel von bfgl_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfws_ag",
                            "name_original": "mittel von bfws_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfwl_ag",
                            "name_original": "mittel von bfwl_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfms_ag",
                            "name_original": "mittel von bfms_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "bfml_ag",
                            "name_original": "mittel von bfml_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "vpgfao",
                            "name_original": "summe von vpgfao",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vpgh",
                            "name_original": "summe von vpgh",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrgs_ag",
                            "name_original": "summe von vrgs_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrgl_ag",
                            "name_original": "summe von vrgl_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrws_ag",
                            "name_original": "summe von vrws_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrwl_ag",
                            "name_original": "summe von vrwl_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrms_ag",
                            "name_original": "summe von vrms_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "vrml_ag",
                            "name_original": "summe von vrml_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
DwdDerivedMetadata = build_metadata_model(DwdDerivedMetadata, "DwdDerivedMetadata")

TECHNICAL_DATASETS = [
    DwdDerivedMetadata.monthly.heating_degreedays,
    DwdDerivedMetadata.monthly.cooling_degreehours_13,
    DwdDerivedMetadata.monthly.cooling_degreehours_16,
    DwdDerivedMetadata.monthly.cooling_degreehours_18,
    DwdDerivedMetadata.monthly.climate_correction_factor,
]

RADIATION_DATASETS = [
    DwdDerivedMetadata.hourly.radiation_global,
    DwdDerivedMetadata.hourly.sunshine_duration,
]

SUNSHINE_DURATION_DATASETS = [
    DwdDerivedMetadata.hourly.sunshine_duration,
]

SOIL_DATASETS = [
    DwdDerivedMetadata.daily.soil,
    DwdDerivedMetadata.monthly.soil,
]
