# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD MOSMIX metadata."""

from __future__ import annotations

from wetterdienst.model.metadata import build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA

DwdMosmixMetadata = {
    **_METADATA,
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
                    "name": "small",
                    "name_original": "small",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_cover_above_7km",
                            "name_original": "nh",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_below_500ft",
                            "name_original": "n05",
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
                            "name": "precipitation_height_significant_weather_last_1h",
                            "name_original": "rr1c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_significant_weather_last_3h",
                            "name_original": "rr3c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site_reduced",
                            "name_original": "pppp",
                            "unit": "pascal",
                        },
                        {
                            "name": "probability_fog_last_1h",
                            "name_original": "wwm",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_fog_last_6h",
                            "name_original": "wwm6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_fog_last_12h",
                            "name_original": "wwmh",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_0mm_last_12h",
                            "name_original": "rh00",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_2mm_last_6h",
                            "name_original": "r602",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_2mm_last_12h",
                            "name_original": "rh02",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_2mm_last_24h",
                            "name_original": "rd02",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_1mm_last_12h",
                            "name_original": "rh10",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_5mm_last_6h",
                            "name_original": "r650",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_5mm_last_12h",
                            "name_original": "rh50",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_5mm_last_24h",
                            "name_original": "rd50",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_25kn_last_12h",
                            "name_original": "fxh25",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_40kn_last_12h",
                            "name_original": "fxh40",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_55kn_last_12h",
                            "name_original": "fxh55",
                            "unit": "percent",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "rad1h",
                            "unit": "kilojoule_per_square_meter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sund1",
                            "unit": "second",
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
                            "name": "visibility_range",
                            "name_original": "vv",
                            "unit": "meter",
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
                            "name": "wind_gust_max_last_1h",
                            "name_original": "fx1",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max_last_3h",
                            "name_original": "fx3",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max_last_12h",
                            "name_original": "fxh",
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
                    "name": "large",
                    "name_original": "large",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "cloud_base_convective",
                            "name_original": "h_bsc",
                            "unit": "meter",
                        },
                        {
                            "name": "cloud_cover_above_7km",
                            "name_original": "nh",
                            "unit": "percent",
                        },
                        {
                            "name": "cloud_cover_below_500ft",
                            "name_original": "n05",
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
                            "name": "cloud_cover_below_7km",
                            "name_original": "nlm",
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
                            "name": "error_absolute_pressure_air_site",
                            "name_original": "e_ppp",
                            "unit": "pascal",
                        },
                        {
                            "name": "error_absolute_temperature_air_mean_2m",
                            "name_original": "e_ttt",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "error_absolute_temperature_dew_point_mean_2m",
                            "name_original": "e_td",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "error_absolute_wind_direction",
                            "name_original": "e_dd",
                            "unit": "degree",
                        },
                        {
                            "name": "error_absolute_wind_speed",
                            "name_original": "e_ff",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "evapotranspiration_potential_last_24h",
                            "name_original": "pevap",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "drr1",
                            "unit": "second",
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
                            "name": "precipitation_height_last_6h",
                            "name_original": "rr6",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_12h",
                            "name_original": "rrh",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_24h",
                            "name_original": "rrd",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_liquid_significant_weather_last_1h",
                            "name_original": "rrl1c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_significant_weather_last_1h",
                            "name_original": "rr1c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_significant_weather_last_3h",
                            "name_original": "rr3c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_significant_weather_last_6h",
                            "name_original": "rr6c",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_significant_weather_last_12h",
                            "name_original": "rrhc",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_significant_weather_last_24h",
                            "name_original": "rrdc",
                            "unit": "millimeter",
                        },
                        {
                            "name": "pressure_air_site_reduced",
                            "name_original": "pppp",
                            "unit": "pascal",
                        },
                        {
                            "name": "probability_drizzle_last_1h",
                            "name_original": "wwz",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_drizzle_last_6h",
                            "name_original": "wwz6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_drizzle_last_12h",
                            "name_original": "wwzh",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_fog_last_1h",
                            "name_original": "wwm",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_fog_last_6h",
                            "name_original": "wwm6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_fog_last_12h",
                            "name_original": "wwmh",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_fog_last_24h",
                            "name_original": "wwmd",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_convective_last_1h",
                            "name_original": "wwc",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_convective_last_6h",
                            "name_original": "wwc6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_convective_last_12h",
                            "name_original": "wwch",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_freezing_last_1h",
                            "name_original": "wwf",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_freezing_last_6h",
                            "name_original": "wwf6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_freezing_last_12h",
                            "name_original": "wwfh",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_0mm_last_6h",
                            "name_original": "r600",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_0mm_last_12h",
                            "name_original": "rh00",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_0mm_last_24h",
                            "name_original": "rd00",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_1mm_last_1h",
                            "name_original": "r101",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_2mm_last_1h",
                            "name_original": "r102",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_2mm_last_6h",
                            "name_original": "r602",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_2mm_last_12h",
                            "name_original": "rh02",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_2mm_last_24h",
                            "name_original": "rd02",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_3mm_last_1h",
                            "name_original": "r103",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_5mm_last_1h",
                            "name_original": "r105",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_0_7mm_last_1h",
                            "name_original": "r107",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_1mm_last_1h",
                            "name_original": "r110",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_1mm_last_6h",
                            "name_original": "r610",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_1mm_last_12h",
                            "name_original": "rh10",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_1mm_last_24h",
                            "name_original": "rd10",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_2mm_last_1h",
                            "name_original": "r120",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_3mm_last_1h",
                            "name_original": "r130",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_5mm_last_1h",
                            "name_original": "r150",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_5mm_last_6h",
                            "name_original": "r650",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_5mm_last_12h",
                            "name_original": "rh50",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_5mm_last_24h",
                            "name_original": "rd50",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_10mm_last_1h",
                            "name_original": "rr1o1",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_15mm_last_1h",
                            "name_original": "rr1w1",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_height_gt_25mm_last_1h",
                            "name_original": "rr1u1",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_last_1h",
                            "name_original": "wwp",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_last_6h",
                            "name_original": "wwp6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_last_12h",
                            "name_original": "wwph",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_last_24h",
                            "name_original": "wwpd",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_liquid_last_1h",
                            "name_original": "wwl",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_liquid_last_6h",
                            "name_original": "wwl6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_liquid_last_12h",
                            "name_original": "wwlh",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_solid_last_1h",
                            "name_original": "wws",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_solid_last_6h",
                            "name_original": "wws6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_solid_last_12h",
                            "name_original": "wwsh",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_stratiform_last_1h",
                            "name_original": "wwd",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_stratiform_last_6h",
                            "name_original": "wwd6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_precipitation_stratiform_last_12h",
                            "name_original": "wwdh",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_radiation_global_last_1h",
                            "name_original": "rrad1",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_sunshine_duration_relative_gt_0pct_last_24h",
                            "name_original": "psd00",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_sunshine_duration_relative_gt_30pct_last_24h",
                            "name_original": "psd30",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_sunshine_duration_relative_gt_60pct_last_24h",
                            "name_original": "psd60",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_thunder_last_1h",
                            "name_original": "wwt",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_thunder_last_6h",
                            "name_original": "wwt6",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_thunder_last_12h",
                            "name_original": "wwth",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_thunder_last_24h",
                            "name_original": "wwtd",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_visibility_below_1000m",
                            "name_original": "vv10",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_25kn_last_6h",
                            "name_original": "fx625",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_25kn_last_12h",
                            "name_original": "fxh25",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_40kn_last_6h",
                            "name_original": "fx640",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_40kn_last_12h",
                            "name_original": "fxh40",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_55kn_last_6h",
                            "name_original": "fx655",
                            "unit": "percent",
                        },
                        {
                            "name": "probability_wind_gust_ge_55kn_last_12h",
                            "name_original": "fxh55",
                            "unit": "percent",
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
                            "name": "sunshine_duration",
                            "name_original": "sund1",
                            "unit": "second",
                        },
                        {
                            "name": "sunshine_duration_last_3h",
                            "name_original": "sund3",
                            "unit": "second",
                        },
                        {
                            "name": "sunshine_duration_relative_last_24h",
                            "name_original": "rsund",
                            "unit": "percent",
                        },
                        {
                            "name": "sunshine_duration_yesterday",
                            "name_original": "sund",
                            "unit": "second",
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
                            "name": "temperature_air_mean_2m_last_24h",
                            "name_original": "tm",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_air_min_0_05m_last_12h",
                            "name_original": "tg",
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
                            "name": "visibility_range",
                            "name_original": "vv",
                            "unit": "meter",
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
                            "name": "weather_significant_last_3h",
                            "name_original": "ww3",
                            "unit": "significant_weather",
                        },
                        {
                            "name": "weather_significant_optional_last_1h",
                            "name_original": "wpc11",
                            "unit": "significant_weather",
                        },
                        {
                            "name": "weather_significant_optional_last_3h",
                            "name_original": "wpc31",
                            "unit": "significant_weather",
                        },
                        {
                            "name": "weather_significant_optional_last_6h",
                            "name_original": "wpc61",
                            "unit": "significant_weather",
                        },
                        {
                            "name": "weather_significant_optional_last_12h",
                            "name_original": "wpch1",
                            "unit": "significant_weather",
                        },
                        {
                            "name": "weather_significant_optional_last_24h",
                            "name_original": "wpcd1",
                            "unit": "significant_weather",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dd",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max_last_1h",
                            "name_original": "fx1",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max_last_3h",
                            "name_original": "fx3",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_gust_max_last_12h",
                            "name_original": "fxh",
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
DwdMosmixMetadata = build_metadata_model(DwdMosmixMetadata, "DwdMosmixMetadata")
