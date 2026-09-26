# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD DMO metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA

DwdDmoMetadata = {
    **_METADATA,
    "kind": "forecast",
    "timezone": "Europe/Berlin",
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["future"],
            "date_required": False,
            "datasets": [
                {
                    "name": "icon_eu",
                    "name_original": "icon_eu",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_cover_above_7km",
                            "name_original": "nh",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_below_1000ft",
                            "name_original": "nl",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_between_2km_to_7km",
                            "name_original": "nm",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_effective",
                            "name_original": "neff",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "n",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height_last_1h",
                            "name_original": "rr1",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site_reduced",
                            "name_original": "pppp",
                            "unit": "pascal",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "rad1h",
                            "unit": "kilojoule_per_square_meter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tx",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "t5cm",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "ttt",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tn",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "td",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "water_equivalent_snow_depth_new_last_1h",
                            "name_original": "rrs1c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "weather_last_6h",
                            "name_original": "w1w2",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_significant",
                            "name_original": "ww",
                            "unit": "significant_weather",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dd",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max_last_3h",
                            "name_original": "fx3",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff",
                            "unit": "meter_per_second",
                        },
                    ],
                },
                {
                    "name": "icon",
                    "name_original": "icon",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_cover_above_7km",
                            "name_original": "nh",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_below_1000ft",
                            "name_original": "nl",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_between_2km_to_7km",
                            "name_original": "nm",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_effective",
                            "name_original": "neff",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "n",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_height_last_1h",
                            "name_original": "rr1",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_3h",
                            "name_original": "rr3",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site_reduced",
                            "name_original": "pppp",
                            "unit": "pascal",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "rad1h",
                            "unit": "kilojoule_per_square_meter",
                        },
                        {
                            "name": "radiation_global_last_3h",
                            "name_original": "rads3",
                            "unit": "kilojoule_per_square_meter",
                        },
                        {
                            "name": "radiation_sky_long_wave_last_3h",
                            "name_original": "radl3",
                            "unit": "kilojoule_per_square_meter",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tx",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "t5cm",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "ttt",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tn",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "td",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "water_equivalent_snow_depth_new_last_1h",
                            "name_original": "rrs1c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "water_equivalent_snow_depth_new_last_3h",
                            "name_original": "rrs3c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "weather_last_6h",
                            "name_original": "w1w2",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_significant",
                            "name_original": "ww",
                            "unit": "significant_weather",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dd",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max_last_3h",
                            "name_original": "fx3",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff",
                            "unit": "meter_per_second",
                        },
                    ],
                },
            ],
        },
    ],
}
DwdDmoMetadata = build_metadata_model(DwdDmoMetadata, "DwdDmoMetadata")
