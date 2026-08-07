# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD observation metadata."""

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import build_metadata_model
from wetterdienst.provider.dwd.metadata import _METADATA

DwdObservationMetadata = {
    **_METADATA,
    "kind": "observation",
    "timezone": "Europe/Berlin",
    "timezone_data": "UTC",
    "resolutions": [
        {
            "name": "1_minute",
            "name_original": "1_minute",
            "periods": ["historical", "recent", "now"],
            "date_required": False,
            "datasets": [
                {
                    "name": "precipitation",
                    "name_original": "precipitation",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rs_01",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_droplet",
                            "name_original": "rth_01",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_rocker",
                            "name_original": "rwh_01",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_index",
                            "name_original": "rs_ind_01",
                            "unit": "dimensionless",
                        },
                    ],
                },
            ],
        },
        {
            "name": "5_minutes",
            "name_original": "5_minutes",
            "periods": ["historical", "recent", "now"],
            "date_required": False,
            "datasets": [
                {
                    "name": "precipitation",
                    "name_original": "precipitation",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_5min",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_index",
                            "name_original": "rs_ind_05",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rs_05",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_droplet",
                            "name_original": "rth_05",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_rocker",
                            "name_original": "rwh_05",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "10_minutes",
            "name_original": "10_minutes",
            "periods": ["historical", "recent", "now"],
            "date_required": False,
            "datasets": [
                {
                    "name": "precipitation",
                    "name_original": "precipitation",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_duration",
                            "name_original": "rws_dau_10",
                            "unit": "minute",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rws_10",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_index",
                            "name_original": "rws_ind_10",
                            "unit": "dimensionless",
                        },
                    ],
                },
                {
                    "name": "solar",
                    "name_original": "solar",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "radiation_sky_short_wave_diffuse",
                            "name_original": "ds_10",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "gs_10",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sd_10",
                            "unit": "hour",
                        },
                        {
                            "name": "radiation_sky_long_wave",
                            "name_original": "ls_10",
                            "unit": "joule_per_square_centimeter",
                        },
                    ],
                },
                {
                    "name": "temperature_air",
                    "name_original": "air_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "pp_10",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tt_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "tm5_10",
                            "unit": "degree_celsius",
                        },
                        {"name": "humidity", "name_original": "rf_10", "unit": "percent"},
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "td_10",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "temperature_extreme",
                    "name_original": "extreme_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tx_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_0_05m",
                            "name_original": "tx5_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tn_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tn5_10",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "wind",
                    "name_original": "wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff_10",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dd_10",
                            "unit": "degree",
                        },
                    ],
                },
                {
                    "name": "wind_extreme",
                    "name_original": "extreme_wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fx_10",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_min",
                            "name_original": "fnx_10",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_rolling_mean_max",
                            "name_original": "fmx_10",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "dx_10",
                            "unit": "degree",
                        },
                    ],
                },
                # urban (Stadtklima) 10-minute datasets -- served from climate_urban/ (recent only);
                # column codes carry the ``_st_`` (Stadt) infix.
                {
                    "name": "urban_temperature_air",
                    "name_original": "urban_air_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tt_st_10",
                            "unit": "degree_celsius",
                        },
                        {"name": "humidity", "name_original": "rf_st_10", "unit": "percent"},
                        {
                            # "Strahlungstemperatur" -- radiant temperature at 2 m
                            "name": "temperature_radiant_mean_2m",
                            "name_original": "strahl_st_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "tt5_st_10",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "urban_temperature_extreme",
                    "name_original": "urban_extreme_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "tx_st_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tn_st_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tn5_st_10",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "urban_wind_extreme",
                    "name_original": "urban_extreme_wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fx_st_10",
                            "unit": "meter_per_second",
                        },
                    ],
                },
                {
                    "name": "urban_precipitation",
                    "name_original": "urban_precipitation",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rr_st_10",
                            "unit": "millimeter",
                        },
                    ],
                },
                {
                    "name": "urban_pressure",
                    "name_original": "urban_pressure",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "pp_st_10",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p0_st_10",
                            "unit": "hectopascal",
                        },
                    ],
                },
                {
                    "name": "urban_temperature_soil",
                    "name_original": "urban_soil_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "te_st_01m_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "te_st_02m_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "te_st_05m_10",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_1m",
                            "name_original": "te_st_10m_10",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "urban_solar",
                    "name_original": "urban_solar",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "fg_st_10",
                            "unit": "joule_per_square_centimeter",
                        },
                        # urban sunshine duration is reported in minutes (the non-urban solar sd_10 is hours)
                        {
                            "name": "sunshine_duration",
                            "name_original": "sd_st_10",
                            "unit": "minute",
                        },
                    ],
                },
                {
                    "name": "urban_wind",
                    "name_original": "urban_wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff_st_10",
                            "unit": "meter_per_second",
                        },
                        {"name": "wind_direction", "name_original": "dd_st_10", "unit": "degree"},
                    ],
                },
            ],
        },
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": "cloud_type",
                    "name_original": "cloud_type",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "v_n",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "cloud_cover_total_index",
                            "name_original": "v_n_i",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_type_layer1",
                            "name_original": "v_s1_cs",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_type_layer1_abbreviation",
                            "name_original": "v_s1_csa",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_height_layer1",
                            "name_original": "v_s1_hhs",
                            "unit": "meter",
                        },
                        {
                            "name": "cloud_cover_layer1",
                            "name_original": "v_s1_ns",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "cloud_type_layer2",
                            "name_original": "v_s2_cs",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_type_layer2_abbreviation",
                            "name_original": "v_s2_csa",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_height_layer2",
                            "name_original": "v_s2_hhs",
                            "unit": "meter",
                        },
                        {
                            "name": "cloud_cover_layer2",
                            "name_original": "v_s2_ns",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "cloud_type_layer3",
                            "name_original": "v_s3_cs",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_type_layer3_abbreviation",
                            "name_original": "v_s3_csa",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_height_layer3",
                            "name_original": "v_s3_hhs",
                            "unit": "meter",
                        },
                        {
                            "name": "cloud_cover_layer3",
                            "name_original": "v_s3_ns",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "cloud_type_layer4",
                            "name_original": "v_s4_cs",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_type_layer4_abbreviation",
                            "name_original": "v_s4_csa",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_height_layer4",
                            "name_original": "v_s4_hhs",
                            "unit": "meter",
                        },
                        {
                            "name": "cloud_cover_layer4",
                            "name_original": "v_s4_ns",
                            "unit": "one_eighth",
                        },
                    ],
                },
                {
                    "name": "cloudiness",
                    "name_original": "cloudiness",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_cover_total_index",
                            "name_original": "v_n_i",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "v_n",
                            "unit": "one_eighth",
                        },
                    ],
                },
                {
                    "name": "dew_point",
                    "name_original": "dew_point",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tt",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "td",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "moisture",
                    "name_original": "moisture",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "humidity_absolute",
                            "name_original": "absf_std",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "vp_std",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "temperature_wet_mean_2m",
                            "name_original": "tf_std",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p_std",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tt_std",
                            "unit": "degree_celsius",
                        },
                        {"name": "humidity", "name_original": "rf_std", "unit": "percent"},
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "td_std",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "precipitation",
                    "name_original": "precipitation",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "r1",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_index",
                            "name_original": "rs_ind",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_form",
                            "name_original": "wrtr",
                            "unit": "dimensionless",
                        },
                    ],
                },
                {
                    "name": "pressure",
                    "name_original": "pressure",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "p",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "p0",
                            "unit": "hectopascal",
                        },
                    ],
                },
                {
                    "name": "solar",
                    "name_original": "solar",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_592",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "end_of_interval",
                            "name_original": "end_of_interval",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "radiation_sky_long_wave",
                            "name_original": "atmo_lberg",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "radiation_sky_short_wave_diffuse",
                            "name_original": "fd_lberg",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "fg_lberg",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sd_lberg",
                            "unit": "minute",
                        },
                        {
                            "name": "sun_zenith_angle",
                            "name_original": "zenit",
                            "unit": "degree",
                        },
                        {
                            "name": "true_local_time",
                            "name_original": "mess_datum_woz",
                            "unit": "dimensionless",
                        },
                    ],
                },
                {
                    "name": "sun",
                    "name_original": "sun",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_7",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sd_so",
                            "unit": "minute",
                        },
                    ],
                },
                {
                    "name": "temperature_air",
                    "name_original": "air_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_9",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tt_tu",
                            "unit": "degree_celsius",
                        },
                        {"name": "humidity", "name_original": "rf_tu", "unit": "percent"},
                    ],
                },
                {
                    "name": "temperature_soil",
                    "name_original": "soil_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_2",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_soil_mean_0_02m",
                            "name_original": "v_te002",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "v_te005",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "v_te010",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "v_te020",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "v_te050",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_1m",
                            "name_original": "v_te100",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "visibility",
                    "name_original": "visibility",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "visibility_range_index",
                            "name_original": "v_vv_i",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "v_vv",
                            "unit": "meter",
                        },
                    ],
                },
                {
                    "name": "weather_phenomena",
                    "name_original": "weather_phenomena",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather",
                            "name_original": "ww",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "weather_text",
                            "name_original": "ww_text",
                            "unit": "dimensionless",
                        },
                    ],
                },
                {
                    "name": "wind",
                    "name_original": "wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_3",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "f",
                            "unit": "meter_per_second",
                        },
                        {"name": "wind_direction", "name_original": "d", "unit": "degree"},
                    ],
                },
                {
                    "name": "wind_extreme",
                    "name_original": "extreme_wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fx_911",
                            "unit": "meter_per_second",
                        },
                    ],
                },
                {
                    "name": "wind_synoptic",
                    "name_original": "wind_synop",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "ff",
                            "unit": "meter_per_second",
                        },
                        {"name": "wind_direction", "name_original": "dd", "unit": "degree"},
                    ],
                },
                # urban datasets
                {
                    "name": "urban_precipitation",
                    "name_original": "urban_precipitation",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qualitaets_niveau",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "niederschlagshoehe",
                            "unit": "millimeter",
                        },
                    ],
                },
                {
                    "name": "urban_pressure",
                    "name_original": "urban_pressure",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qualitaets_niveau",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "luftdruck_nn",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "luftdruck_stationshoehe",
                            "unit": "hectopascal",
                        },
                    ],
                },
                {
                    "name": "urban_sun",
                    "name_original": "urban_sun",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qualitaets_niveau",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sonnenscheindauer",
                            "unit": "minute",
                        },
                    ],
                },
                {
                    "name": "urban_temperature_air",
                    "name_original": "urban_air_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qualitaets_niveau",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "lufttemperatur",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "rel_feuchte",
                            "unit": "percent",
                        },
                    ],
                },
                {
                    "name": "urban_temperature_soil",
                    "name_original": "urban_soil_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qualitaets_niveau",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "erdbt_005",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "erdbt_010",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "erdbt_020",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "erdbt_050",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_1m",
                            "name_original": "erdbt_100",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "urban_wind",
                    "name_original": "urban_wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qualitaets_niveau",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windgeschwindigkeit",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "windrichtung",
                            "unit": "degree",
                        },
                    ],
                },
            ],
        },
        {
            "name": "subdaily",
            "name_original": "subdaily",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": "cloudiness",
                    "name_original": "cloudiness",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "n_ter",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "cloud_density",
                            "name_original": "cd_ter",
                            "unit": "dimensionless",
                        },
                    ],
                },
                {
                    "name": "moisture",
                    "name_original": "moisture",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "vp_ter",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "temperature_air_mean_0_05m",
                            "name_original": "e_tf_ter",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tf_ter",
                            "unit": "degree_celsius",
                        },
                        {"name": "humidity", "name_original": "rf_ter", "unit": "percent"},
                    ],
                },
                {
                    "name": "pressure",
                    "name_original": "pressure",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "pp_ter",
                            "unit": "hectopascal",
                        },
                    ],
                },
                {
                    "name": "soil",
                    "name_original": "soil",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "ek_ter",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "temperature_air",
                    "name_original": "air_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tt_ter",
                            "unit": "degree_celsius",
                        },
                        {"name": "humidity", "name_original": "rf_ter", "unit": "percent"},
                    ],
                },
                {
                    "name": "visibility",
                    "name_original": "visibility",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "vk_ter",
                            "unit": "meter",
                        },
                    ],
                },
                {
                    "name": "wind",
                    "name_original": "wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "dk_ter",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_force_beaufort",
                            "name_original": "fk_ter",
                            "unit": "beaufort",
                        },
                    ],
                },
                {
                    "name": "wind_extreme",
                    "name_original": "extreme_wind",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality_3",
                            "name_original": "qn_8_3",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_gust_max_last_3h",
                            "name_original": "fx_911_3",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "quality_6",
                            "name_original": "qn_8_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_gust_max_last_6h",
                            "name_original": "fx_911_6",
                            "unit": "meter_per_second",
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
                    "name": "climate_summary",
                    "name_original": "kl",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality_wind",
                            "name_original": "qn_3",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "fx",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "fm",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "quality_general",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rsk",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_form",
                            "name_original": "rskf",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sdk",
                            "unit": "hour",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "shk_tag",
                            "unit": "centimeter",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "nm",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "pressure_vapor",
                            "name_original": "vpm",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "pm",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "tmk",
                            "unit": "degree_celsius",
                        },
                        {"name": "humidity", "name_original": "upm", "unit": "percent"},
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "txk",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "tnk",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_0_05m",
                            "name_original": "tgk",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "precipitation_more",
                    "name_original": "more_precip",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "rs",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_form",
                            "name_original": "rsf",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "sh_tag",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "nsh_tag",
                            "unit": "centimeter",
                        },
                    ],
                },
                {
                    "name": "solar",
                    "name_original": "solar",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_592",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "radiation_sky_long_wave",
                            "name_original": "atmo_strahl",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "radiation_sky_short_wave_diffuse",
                            "name_original": "fd_strahl",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "fg_strahl",
                            "unit": "joule_per_square_centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sd_strahl",
                            "unit": "hour",
                        },
                    ],
                },
                {
                    "name": "temperature_soil",
                    "name_original": "soil_temperature",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_2",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_soil_mean_0_02m",
                            "name_original": "v_te002m",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_05m",
                            "name_original": "v_te005m",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_1m",
                            "name_original": "v_te010m",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_2m",
                            "name_original": "v_te020m",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_0_5m",
                            "name_original": "v_te050m",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_soil_mean_1m",
                            "name_original": "v_te100m",
                            "unit": "degree_celsius",
                        },
                    ],
                },
                {
                    "name": "water_equivalent",
                    "name_original": "water_equiv",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "snow_depth_excelled",
                            "name_original": "ash_6",
                            "unit": "centimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "sh_tag",
                            "unit": "centimeter",
                        },
                        {
                            "name": "water_equivalent_snow_depth",
                            "name_original": "wash_6",
                            "unit": "millimeter",
                        },
                        {
                            "name": "water_equivalent_snow_depth_excelled",
                            "name_original": "waas_6",
                            "unit": "millimeter",
                        },
                    ],
                },
                {
                    "name": "weather_phenomena",
                    "name_original": "weather_phenomena",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_fog",
                            "name_original": "nebel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_thunder",
                            "name_original": "gewitter",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_storm_strong_wind",
                            "name_original": "sturm_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_storm_stormier_wind",
                            "name_original": "sturm_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_dew",
                            "name_original": "tau",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_glaze",
                            "name_original": "glatteis",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_ripe",
                            "name_original": "reif",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_sleet",
                            "name_original": "graupel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_hail",
                            "name_original": "hagel",
                            "unit": "dimensionless",
                        },
                    ],
                },
                {
                    "name": "weather_phenomena_more",
                    "name_original": "more_weather_phenomena",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_sleet",
                            "name_original": "rr_graupel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_hail",
                            "name_original": "rr_hagel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_fog",
                            "name_original": "rr_nebel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_thunder",
                            "name_original": "rr_gewitter",
                            "unit": "dimensionless",
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
                    "name": "climate_summary",
                    "name_original": "kl",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality_general",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "mo_n",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mo_tt",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m_mean",
                            "name_original": "mo_tx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_mean",
                            "name_original": "mo_tn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "mo_sd_s",
                            "unit": "hour",
                        },
                        {
                            "name": "wind_force_beaufort",
                            "name_original": "mo_fk",
                            "unit": "beaufort",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "mx_tx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "mx_fx",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "mx_tn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "quality_precipitation",
                            "name_original": "qn_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "mo_rr",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "mx_rs",
                            "unit": "millimeter",
                        },
                    ],
                },
                {
                    "name": "precipitation_more",
                    "name_original": "more_precip",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "mo_nsh",
                            "unit": "centimeter",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "mo_rr",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "mo_sh_s",
                            "unit": "centimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "mx_rs",
                            "unit": "millimeter",
                        },
                    ],
                },
                {
                    "name": "weather_phenomena",
                    "name_original": "weather_phenomena",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_storm_strong_wind",
                            "name_original": "mo_sturm_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_storm_stormier_wind",
                            "name_original": "mo_sturm_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_thunder",
                            "name_original": "mo_gewitter",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_glaze",
                            "name_original": "mo_glatteis",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_sleet",
                            "name_original": "mo_graupel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_hail",
                            "name_original": "mo_hagel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_fog",
                            "name_original": "mo_nebel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_dew",
                            "name_original": "mo_tau",
                            "unit": "dimensionless",
                        },
                    ],
                },
            ],
        },
        {
            "name": "annual",
            "name_original": "annual",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": "climate_summary",
                    "name_original": "kl",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality_general",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "ja_n",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "ja_tt",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m_mean",
                            "name_original": "ja_tx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_mean",
                            "name_original": "ja_tn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "ja_sd_s",
                            "unit": "hour",
                        },
                        {
                            "name": "wind_force_beaufort",
                            "name_original": "ja_fk",
                            "unit": "beaufort",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "ja_mx_tx",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "ja_mx_fx",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "ja_mx_tn",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "quality_precipitation",
                            "name_original": "qn_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "ja_rr",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "ja_mx_rs",
                            "unit": "millimeter",
                        },
                    ],
                },
                {
                    "name": "precipitation_more",
                    "name_original": "more_precip",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "snow_depth_new",
                            "name_original": "ja_nsh",
                            "unit": "centimeter",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "ja_rr",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "ja_sh_s",
                            "unit": "centimeter",
                        },
                        {
                            "name": "precipitation_height_max",
                            "name_original": "ja_mx_rs",
                            "unit": "millimeter",
                        },
                    ],
                },
                {
                    "name": "weather_phenomena",
                    "name_original": "weather_phenomena",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "quality",
                            "name_original": "qn_4",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_storm_strong_wind",
                            "name_original": "ja_sturm_6",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_storm_stormier_wind",
                            "name_original": "ja_sturm_8",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_thunder",
                            "name_original": "ja_gewitter",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_glaze",
                            "name_original": "ja_glatteis",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_sleet",
                            "name_original": "ja_graupel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_hail",
                            "name_original": "ja_hagel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_fog",
                            "name_original": "ja_nebel",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "count_weather_type_dew",
                            "name_original": "ja_tau",
                            "unit": "dimensionless",
                        },
                    ],
                },
            ],
        },
    ],
}
DwdObservationMetadata = build_metadata_model(DwdObservationMetadata, "DwdObservationMetadata")

DWD_URBAN_DATASETS = [
    DwdObservationMetadata.minute_10.urban_temperature_air,
    DwdObservationMetadata.minute_10.urban_temperature_extreme,
    DwdObservationMetadata.minute_10.urban_wind_extreme,
    DwdObservationMetadata.minute_10.urban_precipitation,
    DwdObservationMetadata.minute_10.urban_pressure,
    DwdObservationMetadata.minute_10.urban_temperature_soil,
    DwdObservationMetadata.minute_10.urban_solar,
    DwdObservationMetadata.minute_10.urban_wind,
    DwdObservationMetadata.hourly.urban_precipitation,
    DwdObservationMetadata.hourly.urban_pressure,
    DwdObservationMetadata.hourly.urban_sun,
    DwdObservationMetadata.hourly.urban_temperature_air,
    DwdObservationMetadata.hourly.urban_temperature_soil,
    DwdObservationMetadata.hourly.urban_wind,
]

HIGH_RESOLUTIONS = (
    Resolution.MINUTE_1,
    Resolution.MINUTE_5,
    Resolution.MINUTE_10,
)
