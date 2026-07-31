# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD SWSMOS (Straßenwetter-MOS) road weather forecast metadata.

SWSMOS is DWD's road weather forecast for its ~1800 road weather stations (SWS). One CSV file is
published per model run (``swsmos_<YYYYMMDDHH0000>_opendata.csv.bz2``) under
https://opendata.dwd.de/weather/local_forecasts/swsmos/, holding an hourly forecast out to +167 h
for every station. Most variables come from a MOS post-processing; road surface temperature and road
condition come from the METRo road model. See
https://www.dwd.de/DE/leistungen/swis_swsmos/swis_swsmos.html.

Only the variables with a clean canonical parameter are mapped. The solid-precipitation *amounts*
(``RRS1c``/``RRS3c``), the 3-hour solid-precipitation *probability* (``WWS3`` -- the enum has 1/6/12
hour windows but no 3 hour one) and the undocumented ``R650`` are intentionally left unmapped.
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

_TEMPERATURE = {"unit_type": "temperature", "unit": "degree_celsius"}
_PRECIPITATION = {"unit_type": "precipitation", "unit": "millimeter"}

DwdSwsmosMetadata = {
    "name_short": "DWD",
    "name_english": "German Weather Service",
    "name_local": "Deutscher Wetterdienst",
    "country": "Germany",
    "copyright": "© Deutscher Wetterdienst (DWD), SWSMOS road weather forecast",
    "url": "https://opendata.dwd.de/weather/local_forecasts/swsmos/",
    "kind": "forecast",
    "timezone": "Europe/Berlin",
    "timezone_data": "UTC",
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["future"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {"name": "temperature_air_mean_2m", "name_original": "TL", **_TEMPERATURE},
                        {"name": "error_absolute_temperature_air_mean_2m", "name_original": "TLSTA", **_TEMPERATURE},
                        {"name": "temperature_dew_point_mean_2m", "name_original": "TD", **_TEMPERATURE},
                        {"name": "temperature_surface_mean", "name_original": "TS", **_TEMPERATURE},
                        {"name": "precipitation_height_liquid", "name_original": "RRL1c", **_PRECIPITATION},
                        {"name": "precipitation_height_last_6h", "name_original": "RR6", **_PRECIPITATION},
                        {
                            "name": "probability_precipitation_liquid_last_6h",
                            "name_original": "WWL6",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "road_surface_condition",
                            "name_original": "RC",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                    ],
                },
            ],
        },
    ],
}
DwdSwsmosMetadata = build_metadata_model(DwdSwsmosMetadata, "DwdSwsmosMetadata")
