from wetterdienst.metadata.metadata_model import MetadataModel

DwdObservationMetadata = [
    {
        "value": "1_minute",
        "periods": ["historical", "recent", "now"],
        "datasets": [
            {
                "name": "precipitation",
                "name_original": "precipitation",
                "parameters": [
                    {"name": "quality", "original": "qn", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "precipitation_height",
                        "original": "rs_01",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                    {
                        "name": "precipitation_height_droplet",
                        "original": "rth_01",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                    {
                        "name": "precipitation_height_rocker",
                        "original": "rwh_01",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                    {
                        "name": "precipitation_index",
                        "original": "rs_ind_01",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                ],
            }
        ],
        "parameters": [
            # precipitation
            {"$ref": "precipitation/precipitation_height"},
            {"$ref": "precipitation/precipitation_height_droplet"},
            {"$ref": "precipitation/precipitation_height_rocker"},
            {"$ref": "precipitation/precipitation_index"},
        ],
    },
    {
        "value": "5_minutes",
        "periods": ["historical", "recent", "now"],
        "datasets": [
            {
                "name": "precipitation",
                "name_original": "precipitation",
                "parameters": [
                    {
                        "name": "quality",
                        "original": "qn_5min",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "precipitation_index",
                        "original": "rs_ind_05",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "precipitation_height",
                        "original": "rs_05",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                    {
                        "name": "precipitation_height_droplet",
                        "original": "rth_05",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                    {
                        "name": "precipitation_height_rocker",
                        "original": "rwh_05",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                ],
            }
        ],
        "parameters": [
            # precipitation
            {"$ref": "precipitation/precipitation_height"},
            {"$ref": "precipitation/precipitation_height_droplet"},
            {"$ref": "precipitation/precipitation_height_rocker"},
            {"$ref": "precipitation/precipitation_index"},
        ],
    },
    {
        "value": "10_minutes",
        "periods": ["historical", "recent", "now"],
        "datasets": [
            {
                "name": "precipitation",
                "name_original": "precipitation",
                "parameters": [
                    {"name": "quality", "original": "qn", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "precipitation_duration",
                        "original": "rws_dau_10",
                        "unit": "second",
                        "unit_original": "minute",
                    },
                    {
                        "name": "precipitation_height",
                        "original": "rws_10",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                    {
                        "name": "precipitation_index",
                        "original": "rws_ind_10",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                ],
            },
            {
                "name": "solar",
                "name_original": "solar",
                "parameters": [
                    {"name": "quality", "original": "qn", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "radiation_sky_short_wave_diffuse",
                        "original": "ds_10",
                        "unit": "joule_per_square_meter",
                        "unit_original": "joule_per_square_centimeter",
                    },
                    {
                        "name": "radiation_global",
                        "original": "gs_10",
                        "unit": "joule_per_square_meter",
                        "unit_original": "joule_per_square_centimeter",
                    },
                    {"name": "sunshine_duration", "original": "sd_10", "unit": "second", "unit_original": "hour"},
                    {
                        "name": "radiation_sky_long_wave",
                        "original": "ls_10",
                        "unit": "joule_per_square_meter",
                        "unit_original": "joule_per_square_centimeter",
                    },
                ],
            },
            {
                "name": "temperature_air",
                "name_original": "air_temperature",
                "parameters": [
                    {"name": "quality", "original": "qn", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "pressure_air_site",
                        "original": "pp_10",
                        "unit": "pascal",
                        "unit_original": "hectopascal",
                    },
                    {
                        "name": "temperature_air_mean_2m",
                        "original": "tt_10",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_air_mean_0_05m",
                        "original": "tm5_10",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {"name": "humidity", "original": "rf_10", "unit": "percent", "unit_original": "percent"},
                    {
                        "name": "temperature_dew_point_mean_2m",
                        "original": "td_10",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                ],
            },
            {
                "name": "temperature_extreme",
                "name_original": "extreme_temperature",
                "parameters": [
                    {"name": "quality", "original": "qn", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "temperature_air_max_2m",
                        "original": "tx_10",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_air_max_0_05m",
                        "original": "tx5_10",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_air_min_2m",
                        "original": "tn_10",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_air_min_0_05m",
                        "original": "tn5_10",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                ],
            },
            {
                "name": "wind",
                "name_original": "wind",
                "parameters": [
                    {"name": "quality", "original": "qn", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "wind_speed",
                        "original": "ff_10",
                        "unit": "meter_per_second",
                        "unit_original": "meter_per_second",
                    },
                    {"name": "wind_direction", "original": "dd_10", "unit": "degree", "unit_original": "degree"},
                ],
            },
            {
                "name": "wind_extreme",
                "name_original": "extreme_wind",
                "parameters": [
                    {"name": "quality", "original": "qn", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "wind_gust_max",
                        "original": "fx_10",
                        "unit": "meter_per_second",
                        "unit_original": "meter_per_second",
                    },
                    {
                        "name": "wind_speed_min",
                        "original": "fnx_10",
                        "unit": "meter_per_second",
                        "unit_original": "meter_per_second",
                    },
                    {
                        "name": "wind_speed_rolling_mean_max",
                        "original": "fmx_10",
                        "unit": "meter_per_second",
                        "unit_original": "meter_per_second",
                    },
                    {
                        "name": "wind_direction_gust_max",
                        "original": "dx_10",
                        "unit": "degree",
                        "unit_original": "degree",
                    },
                ],
            },
        ],
        "parameters": [
            # precipitation
            {"$ref": "precipitation/precipitation_duration"},
            {"$ref": "precipitation/precipitation_height"},
            {"$ref": "precipitation/precipitation_index"},
            # solar
            {"$ref": "solar/radiation_sky_short_wave_diffuse"},
            {"$ref": "solar/radiation_global"},
            {"$ref": "solar/sunshine_duration"},
            {"$ref": "solar/radiation_sky_long_wave"},
            # temperature_air
            {"$ref": "temperature_air/pressure_air_site"},
            {"$ref": "temperature_air/temperature_air_mean_2m"},
            {"$ref": "temperature_air/temperature_air_mean_0_05m"},
            {"$ref": "temperature_air/humidity"},
            {"$ref": "temperature_air/temperature_dew_point_mean_2m"},
            # temperature_extreme
            {"$ref": "temperature_extreme/temperature_air_max_2m"},
            {"$ref": "temperature_extreme/temperature_air_max_0_05m"},
            {"$ref": "temperature_extreme/temperature_air_min_2m"},
            {"$ref": "temperature_extreme/temperature_air_min_0_05m"},
            # wind
            {"$ref": "wind/wind_speed"},
            {"$ref": "wind/wind_direction"},
            # wind_extreme
            {"$ref": "wind_extreme/wind_gust_max"},
            {"$ref": "wind_extreme/wind_speed_min"},
            {"$ref": "wind_extreme/wind_speed_rolling_mean_max"},
            {"$ref": "wind_extreme/wind_direction_gust_max"},
        ],
    },
    {
        "value": "hourly",
        "periods": ["historical", "recent"],
        "datasets": [
            {
                "name": "cloud_type",
                "name_original": "cloud_type",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "cloud_cover_total", "original": "v_n", "unit": "percent", "unit_original": "one_eighth"},
                    {
                        "name": "cloud_cover_total_index",
                        "original": "v_n_i",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "cloud_type_layer1",
                        "original": "v_s1_cs",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "cloud_type_layer1_abbreviation",
                        "original": "v_s1_csa",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {"name": "cloud_height_layer1", "original": "v_s1_hhs", "unit": "meter", "unit_original": "meter"},
                    {
                        "name": "cloud_cover_layer1",
                        "original": "v_s1_ns",
                        "unit": "percent",
                        "unit_original": "one_eighth",
                    },
                    {
                        "name": "cloud_type_layer2",
                        "original": "v_s2_cs",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "cloud_type_layer2_abbreviation",
                        "original": "v_s2_csa",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {"name": "cloud_height_layer2", "original": "v_s2_hhs", "unit": "meter", "unit_original": "meter"},
                    {
                        "name": "cloud_cover_layer2",
                        "original": "v_s2_ns",
                        "unit": "percent",
                        "unit_original": "one_eighth",
                    },
                    {
                        "name": "cloud_type_layer3",
                        "original": "v_s3_cs",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "cloud_type_layer3_abbreviation",
                        "original": "v_s3_csa",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {"name": "cloud_height_layer3", "original": "v_s3_hhs", "unit": "meter", "unit_original": "meter"},
                    {
                        "name": "cloud_cover_layer3",
                        "original": "v_s3_ns",
                        "unit": "percent",
                        "unit_original": "one_eighth",
                    },
                    {
                        "name": "cloud_type_layer4",
                        "original": "v_s4_cs",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "cloud_type_layer4_abbreviation",
                        "original": "v_s4_csa",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {"name": "cloud_height_layer4", "original": "v_s4_hhs", "unit": "meter", "unit_original": "meter"},
                    {
                        "name": "cloud_cover_layer4",
                        "original": "v_s4_ns",
                        "unit": "percent",
                        "unit_original": "one_eighth",
                    },
                ],
            },
            {
                "name": "cloudiness",
                "name_original": "cloudiness",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "cloud_cover_total_index",
                        "original": "v_n_i",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {"name": "cloud_cover_total", "original": "v_n", "unit": "percent", "unit_original": "one_eighth"},
                ],
            },
            {
                "name": "dew_point",
                "name_original": "dew_point",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "temperature_air_mean_2m",
                        "original": "tt",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_dew_point_mean_2m",
                        "original": "td",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                ],
            },
            {
                "name": "moisture",
                "name_original": "moisture",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "humidity_absolute",
                        "original": "absf_std",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {"name": "pressure_vapor", "original": "vp_std", "unit": "pascal", "unit_original": "hectopascal"},
                    {
                        "name": "temperature_wet_mean_2m",
                        "original": "tf_std",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "pressure_air_site",
                        "original": "p_std",
                        "unit": "pascal",
                        "unit_original": "hectopascal",
                    },
                    {
                        "name": "temperature_air_mean_2m",
                        "original": "tt_std",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {"name": "humidity", "original": "rf_std", "unit": "percent", "unit_original": "percent"},
                    {
                        "name": "temperature_dew_point_mean_2m",
                        "original": "td_std",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                ],
            },
            {
                "name": "precipitation",
                "name_original": "precipitation",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "precipitation_height",
                        "original": "r1",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                    {
                        "name": "precipitation_index",
                        "original": "rs_ind",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "precipitation_form",
                        "original": "wrtr",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                ],
            },
            {
                "name": "pressure",
                "name_original": "pressure",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "pressure_air_sea_level",
                        "original": "p",
                        "unit": "pascal",
                        "unit_original": "hectopascal",
                    },
                    {
                        "name": "pressure_air_site",
                        "original": "p0",
                        "unit": "pascal",
                        "unit_original": "hectopascal",
                    },
                ],
            },
            {
                "name": "solar",
                "name_original": "solar",
                "parameters": [
                    {
                        "name": "quality",
                        "original": "qn_592",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "end_of_interval",
                        "original": "end_of_interval",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "radiation_sky_long_wave",
                        "original": "atmo_lberg",
                        "unit": "joule_per_square_meter",
                        "unit_original": "joule_per_square_centimeter",
                    },
                    {
                        "name": "radiation_sky_short_wave_diffuse",
                        "original": "fd_lberg",
                        "unit": "joule_per_square_meter",
                        "unit_original": "joule_per_square_centimeter",
                    },
                    {
                        "name": "radiation_global",
                        "original": "fg_lberg",
                        "unit": "joule_per_square_meter",
                        "unit_original": "joule_per_square_centimeter",
                    },
                    {"name": "sunshine_duration", "original": "sd_lberg", "unit": "second", "unit_original": "hour"},
                    {"name": "sun_zenith_angle", "original": "zenit", "unit": "degree", "unit_original": "degree"},
                    {
                        "name": "true_local_time",
                        "original": "mess_datum_woz",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                ],
            },
            {
                "name": "sun",
                "name_original": "sun",
                "parameters": [
                    {"name": "quality", "original": "qn_7", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "sunshine_duration", "original": "sd_so", "unit": "second", "unit_original": "hour"},
                ],
            },
            {
                "name": "temperature_air",
                "name_original": "air_temperature",
                "parameters": [
                    {"name": "quality", "original": "qn_9", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "temperature_air_mean_2m",
                        "original": "tt_tu",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {"name": "humidity", "original": "rf_tu", "unit": "percent", "unit_original": "percent"},
                ],
            },
            {
                "name": "temperature_soil",
                "name_original": "soil_temperature",
                "parameters": [
                    {"name": "quality", "original": "qn_2", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "temperature_soil_mean_0_02m",
                        "original": "v_te002",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_0_05m",
                        "original": "v_te005",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_0_1m",
                        "original": "v_te010",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_0_2m",
                        "original": "v_te020",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_0_5m",
                        "original": "v_te050",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_1m",
                        "original": "v_te100",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                ],
            },
            {
                "name": "visibility",
                "name_original": "visibility",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "visibility_range_index",
                        "original": "v_vv_i",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {"name": "visibility_range", "original": "v_vv", "unit": "meter", "unit_original": "meter"},
                ],
            },
            {
                "name": "weather_phenomena",
                "name_original": "weather_phenomena",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "weather", "original": "ww", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "weather_text",
                        "original": "ww_text",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                ],
            },
            {
                "name": "wind",
                "name_original": "wind",
                "parameters": [
                    {"name": "quality", "original": "qn_3", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "wind_speed",
                        "original": "f",
                        "unit": "meter_per_second",
                        "unit_original": "meter_per_second",
                    },
                    {"name": "wind_direction", "original": "d", "unit": "degree", "unit_original": "degree"},
                ],
            },
            {
                "name": "wind_extreme",
                "name_original": "extreme_wind",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "wind_gust_max",
                        "original": "fx_911",
                        "unit": "meter_per_second",
                        "unit_original": "meter_per_second",
                    },
                ],
            },
            {
                "name": "wind_synoptic",
                "name_original": "wind_synop",
                "parameters": [
                    {"name": "quality", "original": "qn_8", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "wind_speed",
                        "original": "ff",
                        "unit": "meter_per_second",
                        "unit_original": "meter_per_second",
                    },
                    {"name": "wind_direction", "original": "dd", "unit": "degree", "unit_original": "degree"},
                ],
            },
            # urban datasets
            {
                "name": "urban_precipitation",
                "name_original": "urban_precipitation",
                "parameters": [
                    {
                        "name": "quality",
                        "original": "qualitaets_niveau",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "precipitation_height",
                        "original": "niederschlagshoehe",
                        "unit": "kilogram_per_square_metre",
                        "unit_original": "millimeter",
                    },
                ],
            },
            {
                "name": "urban_pressure",
                "name_original": "urban_pressure",
                "parameters": [
                    {
                        "name": "quality",
                        "original": "qualitaets_niveau",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "pressure_air_sea_level",
                        "original": "luftdruck_nn",
                        "unit": "pascal",
                        "unit_original": "hectopascal",
                    },
                    {
                        "name": "pressure_air_site",
                        "original": "luftdruck_stationshoehe",
                        "unit": "pascal",
                        "unit_original": "hectopascal",
                    },
                ],
            },
            {
                "name": "urban_sun",
                "name_original": "urban_sun",
                "parameters": [
                    {
                        "name": "quality",
                        "original": "qualitaets_niveau",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "sunshine_duration",
                        "original": "sonnenscheindauer",
                        "unit": "second",
                        "unit_original": "hour",
                    },
                ],
            },
            {
                "name": "urban_temperature_air",
                "name_original": "urban_air_temperature",
                "parameters": [
                    {
                        "name": "quality",
                        "original": "qualitaets_niveau",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "temperature_air_mean_2m",
                        "original": "lufttemperatur",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {"name": "humidity", "original": "rel_feuchte", "unit": "percent", "unit_original": "percent"},
                ],
            },
            {
                "name": "urban_temperature_soil",
                "name_original": "urban_soil_temperature",
                "parameters": [
                    {
                        "name": "quality",
                        "original": "qualitaets_niveau",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "temperature_soil_mean_0_05m",
                        "original": "erdbt_005",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_0_1m",
                        "original": "erdbt_010",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_0_2m",
                        "original": "erdbt_020",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_0_5m",
                        "original": "erdbt_050",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_soil_mean_1m",
                        "original": "erdbt_100",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                ],
            },
            {
                "name": "urban_wind",
                "name_original": "urban_wind",
                "parameters": [
                    {
                        "name": "quality",
                        "original": "qualitaets_niveau",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                    {
                        "name": "wind_speed",
                        "original": "windgeschwindigkeit",
                        "unit": "meter_per_second",
                        "unit_original": "meter_per_second",
                    },
                    {"name": "wind_direction", "original": "windrichtung", "unit": "degree", "unit_original": "degree"},
                ],
            },
        ],
        "parameters": [
            # temperature_air
            {"$ref": "temperature_air/temperature_air_mean_2m"},
            {"$ref": "temperature_air/humidity"},
            # cloud_type
            # {"$ref": "cloud_type/cloud_cover_total"},
            # {"$ref": "cloud_type/cloud_cover_total_index"},
            {"$ref": "cloud_type/cloud_type_layer1"},
            # {"$ref": "cloud_type/cloud_type_layer1_abbreviation"},
            {"$ref": "cloud_type/cloud_height_layer1"},
            {"$ref": "cloud_type/cloud_cover_layer1"},
            {"$ref": "cloud_type/cloud_type_layer2"},
            # {"$ref": "cloud_type/cloud_type_layer2_abbreviation"},
            {"$ref": "cloud_type/cloud_height_layer2"},
            {"$ref": "cloud_type/cloud_cover_layer2"},
            {"$ref": "cloud_type/cloud_type_layer3"},
            # {"$ref": "cloud_type/cloud_type_layer3_abbreviation"},
            {"$ref": "cloud_type/cloud_height_layer3"},
            {"$ref": "cloud_type/cloud_cover_layer3"},
            {"$ref": "cloud_type/cloud_type_layer4"},
            # {"$ref": "cloud_type/cloud_type_layer4_abbreviation"},
            {"$ref": "cloud_type/cloud_height_layer4"},
            {"$ref": "cloud_type/cloud_cover_layer4"},
            # cloudiness
            {"$ref": "cloudiness/cloud_cover_total"},
            {"$ref": "cloudiness/cloud_cover_total_index"},
            # dew_point
            # {"$ref": "dew_point/temperature_air_mean_2m"},
            {"$ref": "dew_point/temperature_dew_point_mean_2m"},
            # moisture
            {"$ref": "moisture/humidity_absolute"},
            {"$ref": "moisture/pressure_vapor"},
            {"$ref": "moisture/temperature_wet_mean_2m"},
            # {"$ref": "moisture/pressure_air_site"},
            # {"$ref": "moisture/temperature_air_mean_2m"},
            # {"$ref": "moisture/humidity"},
            # {"$ref": "moisture/temperature_dew_point_mean_2m"},
            # precipitation
            {"$ref": "precipitation/precipitation_height"},
            {"$ref": "precipitation/precipitation_index"},
            {"$ref": "precipitation/precipitation_form"},
            # pressure
            {"$ref": "pressure/pressure_air_sea_level"},
            {"$ref": "pressure/pressure_air_site"},
            # temperature_soil
            {"$ref": "temperature_soil/temperature_soil_mean_0_02m"},
            {"$ref": "temperature_soil/temperature_soil_mean_0_05m"},
            {"$ref": "temperature_soil/temperature_soil_mean_0_1m"},
            {"$ref": "temperature_soil/temperature_soil_mean_0_2m"},
            {"$ref": "temperature_soil/temperature_soil_mean_0_5m"},
            {"$ref": "temperature_soil/temperature_soil_mean_1m"},
            # solar
            {"$ref": "solar/radiation_sky_long_wave"},
            {"$ref": "solar/radiation_sky_short_wave_diffuse"},
            {"$ref": "solar/radiation_global"},
            {"$ref": "solar/sun_zenith_angle"},
            # sun
            {"$ref": "sun/sunshine_duration"},
            # visibility
            {"$ref": "visibility/visibility_range_index"},
            {"$ref": "visibility/visibility_range"},
            # weather_phenomena
            {"$ref": "weather_phenomena/weather"},
            # wind
            {"$ref": "wind/wind_speed"},
            {"$ref": "wind/wind_direction"},
        ]
    },
    {
        "value": "subdaily",
        "periods": ["historical", "recent"],
        "datasets": [
            {
                "name": "cloudiness",
                "name_original": "cloudiness",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "cloud_cover_total", "original": "n_ter", "unit": "percent",
                     "unit_original": "one_eighth"},
                    {
                        "name": "cloud_density",
                        "original": "cd_ter",
                        "unit": "dimensionless",
                        "unit_original": "dimensionless",
                    },
                ],
            },
            {
                "name": "moisture",
                "name_original": "moisture",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "pressure_vapor", "original": "vp_ter", "unit": "pascal", "unit_original": "hectopascal"},
                    {
                        "name": "temperature_air_mean_0_05m",
                        "original": "e_tf_ter",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {
                        "name": "temperature_air_mean_2m",
                        "original": "tf_ter",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {"name": "humidity", "original": "rf_ter", "unit": "percent", "unit_original": "percent"},
                ],
            },
            {
                "name": "pressure",
                "name_original": "pressure",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "pressure_air_site",
                        "original": "pp_ter",
                        "unit": "pascal",
                        "unit_original": "hectopascal",
                    },
                ],
            },
            {
                "name": "soil",
                "name_original": "soil",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "temperature_soil_mean_0_05m",
                        "original": "ek_ter",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    }
                ],
            },
            {
                "name": "temperature_air",
                "name_original": "air_temperature",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {
                        "name": "temperature_air_mean_2m",
                        "original": "tt_ter",
                        "unit": "degree_kelvin",
                        "unit_original": "degree_celsius",
                    },
                    {"name": "humidity", "original": "rf_ter", "unit": "percent", "unit_original": "percent"},
                ],
            },
            {
                "name": "visibility",
                "name_original": "visibility",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "visibility_range", "original": "vk_ter", "unit": "meter", "unit_original": "meter"},
                ],
            },
            {
                "name": "wind",
                "name_original": "wind",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "wind_direction", "original": "dk_ter", "unit": "degree", "unit_original": "degree"},
                    {"name": "wind_force_beaufort", "original": "fk_ter", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                ],
            },
            {
                "name": "wind_extreme",
                "name_original": "extreme_wind",
                "parameters": [
                    {"name": "quality_3", "original": "qn_8_3", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "wind_gust_max_last_3h", "original": "fx_911_3", "unit": "meter_per_second",
                     "unit_original": "meter_per_second"},
                    {"name": "quality_6", "original": "qn_8_6", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "wind_gust_max_last_6h", "original": "fx_911_6", "unit": "meter_per_second",
                     "unit_original": "meter_per_second"},
                ],
            },
        ],
        "parameters": [
            # cloudiness
            {"$ref": "cloudiness/cloud_cover_total"},
            {"$ref": "cloudiness/cloud_density"},
            # moisture
            {"$ref": "moisture/pressure_vapor"},
            {"$ref": "moisture/temperature_air_mean_0_05m"},
            # temperature_air
            {"$ref": "temperature_air/temperature_air_mean_2m"},
            {"$ref": "temperature_air/humidity"},
            # pressure
            {"$ref": "pressure/pressure_air_site"},
            # soil
            {"$ref": "soil/temperature_soil_mean_0_05m"},
            # visibility
            {"$ref": "visibility/visibility_range"},
            # wind
            {"$ref": "wind/wind_direction"},
            {"$ref": "wind/wind_force_beaufort"},
            # wind_extreme
            {"$ref": "wind_extreme/wind_gust_max_last_3h"},
            {"$ref": "wind_extreme/wind_gust_max_last_6h"},
        ],
    },
    {
        "value": "daily",
        "periods": ["historical", "recent"],
        "datasets": [
            {
                "name": "climate_summary",
                "name_original": "kl",
                "parameters": [
                    {"name": "quality_wind", "original": "qn_3", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "wind_gust_max", "original": "fx", "unit": "meter_per_second",
                     "unit_original": "meter_per_second"},
                    {"name": "wind_speed", "original": "fm", "unit": "meter_per_second",
                     "unit_original": "meter_per_second"},
                    {"name": "quality_general", "original": "qn_4", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "precipitation_height", "original": "rsk", "unit": "kilogram_per_square_metre",
                     "unit_original": "millimeter"},
                    {"name": "precipitation_form", "original": "rskf", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "sunshine_duration", "original": "sdk", "unit": "second", "unit_original": "hour"},
                    {"name": "snow_depth", "original": "shk_tag", "unit": "meter", "unit_original": "centimeter"},
                    {"name": "cloud_cover_total", "original": "nm", "unit": "percent", "unit_original": "one_eighth"},
                    {"name": "pressure_vapor", "original": "vpm", "unit": "pascal", "unit_original": "hectopascal"},
                    {"name": "pressure_air_site", "original": "pm", "unit": "pascal", "unit_original": "hectopascal"},
                    {"name": "temperature_air_mean_2m", "original": "tmk", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                    {"name": "humidity", "original": "upm", "unit": "percent", "unit_original": "percent"},
                    {"name": "temperature_air_max_2m", "original": "txk", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                    {"name": "temperature_air_min_2m", "original": "tnk", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                    {"name": "temperature_air_min_0_05m", "original": "tgk", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                ]
            },
            {
                "name": "precipitation_more",
                "name_original": "more_precip",
                "parameters": [
                    {"name": "quality", "original": "qn_6", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "precipitation_height", "original": "rs", "unit": "kilogram_per_square_metre",
                     "unit_original": "millimeter"},
                    {"name": "precipitation_form", "original": "rsf", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "snow_depth", "original": "sh_tag", "unit": "meter", "unit_original": "centimeter"},
                    {"name": "snow_depth_new", "original": "nsh_tag", "unit": "meter", "unit_original": "centimeter"},
                ],
            },
            {
                "name": "solar",
                "name_original": "solar",
                "parameters": [
                    {"name": "quality", "original": "qn_592", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "radiation_sky_long_wave", "original": "atmo_strahl", "unit": "joule_per_square_meter",
                     "unit_original": "joule_per_square_centimeter"},
                    {"name": "radiation_sky_short_wave_diffuse", "original": "fd_strahl",
                     "unit": "joule_per_square_meter", "unit_original": "joule_per_square_centimeter"},
                    {"name": "radiation_global", "original": "fg_strahl", "unit": "joule_per_square_meter",
                     "unit_original": "joule_per_square_centimeter"},
                    {"name": "sunshine_duration", "original": "sd_strahl", "unit": "second", "unit_original": "hour"},
                ],
            },
            {
                "name": "temperature_soil",
                "name_original": "soil_temperature",
                "parameters": [
                    {"name": "quality", "original": "qn_2", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "temperature_soil_mean_0_02m", "original": "v_te002m", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                    {"name": "temperature_soil_mean_0_05m", "original": "v_te005m", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                    {"name": "temperature_soil_mean_0_1m", "original": "v_te010m", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                    {"name": "temperature_soil_mean_0_2m", "original": "v_te020m", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                    {"name": "temperature_soil_mean_0_5m", "original": "v_te050m", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                    {"name": "temperature_soil_mean_1m", "original": "v_te100m", "unit": "degree_kelvin",
                     "unit_original": "degree_celsius"},
                ],
            },
            {
                "name": "water_equivalent",
                "name_original": "water_equiv",
                "parameters": [
                    {"name": "quality", "original": "qn_6", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "snow_depth_excelled", "original": "ash_6", "unit": "meter",
                     "unit_original": "centimeter"},
                    {"name": "snow_depth", "original": "sh_tag", "unit": "meter", "unit_original": "centimeter"},
                    {"name": "water_equivalent_snow_depth", "original": "wash_6", "unit": "kilogram_per_square_metre",
                     "unit_original": "millimeter"},
                    {"name": "water_equivalent_snow_depth_excelled", "original": "waas_6",
                     "unit": "kilogram_per_square_metre", "unit_original": "millimeter"},
                ],
            },
            {
                "name": "weather_phenomena",
                "name_original": "weather_phenomena",
                "parameters": [
                    {"name": "quality", "original": "qn_4", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "count_weather_type_fog", "original": "nebel", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_thunder", "original": "gewitter", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_storm_strong_wind", "original": "sturm_6", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_storm_stormier_wind", "original": "sturm_8", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_dew", "original": "tau", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_glaze", "original": "reif", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_ripe", "original": "reif", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_sleet", "original": "graupel", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_hail", "original": "hagel", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                ],
            },
            {
                "name": "weather_phenomena_more",
                "name_original": "more_weather_phenomena",
                "parameters": [
                    {"name": "quality", "original": "qn_6", "unit": "dimensionless", "unit_original": "dimensionless"},
                    {"name": "count_weather_type_sleet", "original": "rr_graupel", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_hail", "original": "rr_hagel", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_fog", "original": "rr_nebel", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                    {"name": "count_weather_type_thunder", "original": "rr_gewitter", "unit": "dimensionless",
                     "unit_original": "dimensionless"},
                ],
            }
        ],
        "parameters": [
            # climate_summary
            {"$ref": "climate_summary/wind_gust_max"},
            {"$ref": "climate_summary/wind_speed"},
            {"$ref": "climate_summary/precipitation_height"},
            {"$ref": "climate_summary/precipitation_form"},
            {"$ref": "climate_summary/sunshine_duration"},
            {"$ref": "climate_summary/snow_depth"},
            {"$ref": "climate_summary/cloud_cover_total"},
            {"$ref": "climate_summary/pressure_vapor"},
            {"$ref": "climate_summary/pressure_air_site"},
            {"$ref": "climate_summary/temperature_air_mean_2m"},
            {"$ref": "climate_summary/humidity"},
            {"$ref": "climate_summary/temperature_air_max_2m"},
            {"$ref": "climate_summary/temperature_air_min_2m"},
            {"$ref": "climate_summary/temperature_air_min_0_05m"},
            # precipitation_more
            {"$ref": "precipitation_more/precipitation_height"},
            {"$ref": "precipitation_more/precipitation_form"},
            {"$ref": "precipitation_more/snow_depth"},
            {"$ref": "precipitation_more/snow_depth_new"},
            # solar
            {"$ref": "solar/radiation_sky_long_wave"},
            {"$ref": "solar/radiation_sky_short_wave_diffuse"},
            {"$ref": "solar/radiation_global"},
            {"$ref": "solar/sunshine_duration"},
            # temperature_soil
            {"$ref": "temperature_soil/temperature_soil_mean_0_02m"},
            {"$ref": "temperature_soil/temperature_soil_mean_0_05m"},
            {"$ref": "temperature_soil/temperature_soil_mean_0_1m"},
            {"$ref": "temperature_soil/temperature_soil_mean_0_2m"},
            {"$ref": "temperature_soil/temperature_soil_mean_0_5m"},
            {"$ref": "temperature_soil/temperature_soil_mean_1m"},
            # water_equivalent
            {"$ref": "water_equivalent/snow_depth_excelled"},
            {"$ref": "water_equivalent/water_equivalent_snow_depth"},
            {"$ref": "water_equivalent/water_equivalent_snow_depth_excelled"},
        ]
    }
]
DwdObservationMetadata = MetadataModel.model_validate(DwdObservationMetadata)

DWD_URBAN_DATASETS = [
    DwdObservationMetadata.hourly.urban_precipitation,
    DwdObservationMetadata.hourly.urban_pressure,
    DwdObservationMetadata.hourly.urban_sun,
    DwdObservationMetadata.hourly.urban_temperature_air,
    DwdObservationMetadata.hourly.urban_temperature_soil,
    DwdObservationMetadata.hourly.urban_wind,
]