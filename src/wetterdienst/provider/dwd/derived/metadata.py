# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD derived metadata."""

from wetterdienst.model.metadata import build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA

cooling_degree_hours_common_parameters = [
    {
        "name": "number_of_hours_per_month",
        "name_original": "Anzahl Stunden",
        "unit_type": "dimensionless",
        "unit": "dimensionless",
    },
    {
        "name": "count_hours_cooling_degree",
        "name_original": "Anzahl Kuehlstunden",
        "unit_type": "dimensionless",
        "unit": "dimensionless",
    },
    {
        "name": "cooling_degree_hour",
        "name_original": "Kuehlgradstunden",
        "unit_type": "degree_day",
        "unit": "degree_celsius_day",
    },
    {
        "name": "count_days_cooling_degree",
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
                            "name": "radiation_global",
                            "name_original": "fg_duett",
                            "unit_type": "energy_per_area",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "radiation_global_uncertainty",
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
                            "name": "sunshine_duration",
                            "name_original": "sd_duett",
                            "unit_type": "time",
                            "unit": "minute",
                        },
                        {
                            "name": "sunshine_duration_uncertainty",
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
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "ts05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "ts10",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "ts20",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "ts50",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_1m",
                            "name_original": "ts100",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_loamysand_0_05m",
                            "name_original": "tsls05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_loamysilt_0_05m",
                            "name_original": "tssl05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "frozen_ground_layer_thickness",
                            "name_original": "zfumi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "thawing_thickness_plantstock",  # Auftauschicht am Mittag unter Bestand (BEKLIMA)
                            "name_original": "ztkmi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "thawing_thickness_bare",  # Auftauschicht am Mittag unter unbewachsenem Boden
                            "name_original": "ztumi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_00cm_10cm",  # _silt_loam
                            "name_original": "bfgl01_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_10cm_20cm",
                            "name_original": "bfgl02_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_20cm_30cm",
                            "name_original": "bfgl03_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_30cm_40cm",
                            "name_original": "bfgl04_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_40cm_50cm",
                            "name_original": "bfgl05_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_50cm_60cm",
                            "name_original": "bfgl06_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_sand_00cm_60cm",
                            "name_original": "bfgs_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_00cm_60cm",
                            "name_original": "bfgl_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_winterwheat_sand_00cm_60cm",
                            "name_original": "bfws_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_winterwheat_loamysilt_00cm_60cm",
                            "name_original": "bfwl_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_corn_sand_00cm_60cm",
                            "name_original": "bfms_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_corn_loamysilt_00cm_60cm",
                            "name_original": "bfml_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "evapotranspiration_potential_gras_fao_last_24h",
                            "name_original": "vpgfao",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evapotranspiration_potential_gras_haude_last_24h",
                            "name_original": "vpgh",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_gras_sand",
                            "name_original": "vrgs_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_gras_loamysilt",
                            "name_original": "vrgl_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_winterwheat_sand",
                            "name_original": "vrws_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_winterwheat_loamysilt",
                            "name_original": "vrwl_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_corn_sand",
                            "name_original": "vrms_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_corn_loamysilt",
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
                            "name": "number_of_days_per_month",
                            "name_original": "Anzahl Tage",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "heating_degree_day",
                            "name_original": "Monatsgradtage",
                            "unit_type": "degree_day",
                            "unit": "degree_celsius_day",
                        },
                        {
                            "name": "count_days_heating_degree",
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
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "mittel von ts05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "mittel von ts10",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "mittel von ts20",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "mittel von ts50",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_1m",
                            "name_original": "mittel von ts100",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_loamysand_0_05m",
                            "name_original": "mittel von tsls05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_loamysilt_0_05m",
                            "name_original": "mittel von tssl05",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "frozen_ground_layer_thickness_max_month",
                            "name_original": "maximum von zfumi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "thawing_thickness_plantstock_max_month",
                            "name_original": "maximum von ztkmi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "thawing_thickness_bare_max_month",
                            "name_original": "maximum von ztumi",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_00cm_10cm",
                            "name_original": "mittel von bfgl01_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_10cm_20cm",
                            "name_original": "mittel von bfgl02_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_20cm_30cm",
                            "name_original": "mittel von bfgl03_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_30cm_40cm",
                            "name_original": "mittel von bfgl04_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_40cm_50cm",
                            "name_original": "mittel von bfgl05_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_50cm_60cm",
                            "name_original": "mittel von bfgl06_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_sand_00cm_60cm",
                            "name_original": "mittel von bfgs_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_gras_loamysilt_00cm_60cm",
                            "name_original": "mittel von bfgl_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_winterwheat_sand_00cm_60cm",
                            "name_original": "mittel von bfws_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_winterwheat_loamysilt_00cm_60cm",
                            "name_original": "mittel von bfwl_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_corn_sand_00cm_60cm",
                            "name_original": "mittel von bfms_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "soil_moisture_corn_loamysilt_00cm_60cm",
                            "name_original": "mittel von bfml_ag",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "evapotranspiration_potential_gras_fao_last_24h",
                            "name_original": "summe von vpgfao",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evapotranspiration_potential_gras_haude_last_24h",
                            "name_original": "summe von vpgh",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_gras_sand",
                            "name_original": "summe von vrgs_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_gras_loamysilt",
                            "name_original": "summe von vrgl_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_winterwheat_sand",
                            "name_original": "summe von vrws_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_winterwheat_loamysilt",
                            "name_original": "summe von vrwl_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_corn_sand",
                            "name_original": "summe von vrms_ag",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "evaporation_height_corn_loamysilt",
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
