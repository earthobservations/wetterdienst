# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD SWSMOS (Straßenwetter-MOS) road weather forecast metadata.

SWSMOS is DWD's road weather forecast for its ~1800 road weather stations (SWS). One CSV file is
published per model run (``swsmos_<YYYYMMDDHH0000>_opendata.csv.bz2``) under
https://opendata.dwd.de/weather/local_forecasts/swsmos/, holding an hourly forecast out to +167 h
for every station. Most variables come from a MOS post-processing; road surface temperature and road
condition come from the METRo road model. See
https://www.dwd.de/DE/leistungen/swis_swsmos/swis_swsmos.html.

Only the variables with a clean canonical parameter are mapped. Left unmapped: the
solid-precipitation *amounts* (``RRS1c``/``RRS3c`` -- no solid-precipitation-height parameter), the
3-hour solid-precipitation *probability* (``WWS3`` -- the enum has 1/6/12 hour windows but no 3 hour
one), and ``TLSTA`` (the air-temperature forecast *standard deviation*; the sibling
``error_absolute_temperature_air_mean_2m`` used by dwd/mosmix and dwd/dmo is a different statistic --
DWD's expected absolute error -- so reusing it would be misleading, and there is no standard-deviation
parameter).
"""

from __future__ import annotations

from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, build_metadata_model

_TEMPERATURE = {"unit": "degree_celsius"}
_PRECIPITATION = {"unit": "millimeter"}

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
                        {"name": "temperature_dew_point_mean_2m", "name_original": "TD", **_TEMPERATURE},
                        {"name": "temperature_surface_mean", "name_original": "TS", **_TEMPERATURE},
                        # RR6 is a 6-hour liquid precipitation total; there is no ``*_liquid_last_6h``
                        # parameter, so the (window-bearing) generic 6-hour height is the closest fit
                        {"name": "precipitation_height_liquid", "name_original": "RRL1c", **_PRECIPITATION},
                        {"name": "precipitation_height_last_6h", "name_original": "RR6", **_PRECIPITATION},
                        {
                            "name": "probability_precipitation_liquid_last_6h",
                            "name_original": "WWL6",
                            "unit": "percent",
                        },
                        {
                            # R650: probability of > 5 mm liquid+solid precipitation in the last 6 h
                            "name": "probability_precipitation_height_gt_5mm_last_6h",
                            "name_original": "R650",
                            "unit": "percent",
                        },
                        {
                            "name": "road_surface_condition",
                            "name_original": "RC",
                            "unit": "dimensionless",
                        },
                    ],
                },
            ],
        },
    ],
}
DwdSwsmosMetadata = build_metadata_model(DwdSwsmosMetadata, "DwdSwsmosMetadata")
