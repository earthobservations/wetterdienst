# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD's own descriptions of its observation parameters.

Transcribed from the English ``DESCRIPTION_*_en.pdf`` sheets DWD publishes beside the data on
its Climate Data Center. Distinct from the canonical descriptions in
``wetterdienst.metadata.parameter_table``: those say what a quantity *is*, provider-independent,
while these say what a given DWD field means in DWD's own words -- measurement method, averaging
interval, code meanings.

Source: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/
Licence: Creative Commons BY 4.0, per
https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.txt -- reproduced with attribution
to the Deutscher Wetterdienst.

Keyed by ``(resolution, dataset, name_original)``. Only the datasets that ship an English
description sheet are covered; the rest document their parameters only inside the data ZIPs, in
German.
"""

DWD_OBSERVATION_DESCRIPTIONS: dict[tuple[str, str, str], str] = {
    ("10_minutes", "precipitation", "rws_10"): "Sum of the precipitation height of the previous 10 minutes.",
    ("10_minutes", "precipitation", "rws_dau_10"): "Duration of precipitation.",
    ("10_minutes", "precipitation", "rws_ind_10"): (
        "Indicator of precipitation; if QN = 1 then:; 0 = no precipitation, permanent sensor installed; 1 = "
        "precipitation, permanent sensor installed; 2 = no precipitation, heating in operation, permanent sensor "
        "installed; 3 = precipitation, heating in operation, permanent sensor installed; if QN > 1 then:; 0 = no "
        "precipitation; 1 = precipitation."
    ),
    ("10_minutes", "solar", "ds_10"): "Sum of diffuse sky radiation during the previous 10 minutes.",
    ("10_minutes", "solar", "gs_10"): "Sum of global radiation during the previous 10 minutes.",
    ("10_minutes", "solar", "ls_10"): "Sum of longwave radiation during the previous 10 minutes.",
    ("10_minutes", "solar", "sd_10"): "Sum of sunshine duration during the previous 10 minutes.",
    ("10_minutes", "temperature_air", "pp_10"): "Air pressure at station altitude.",
    ("10_minutes", "temperature_air", "rf_10"): "Relative humidity.",
    ("10_minutes", "temperature_air", "td_10"): (
        "Dew point,The dew point temperature is calculated from the air temperature 2 m above ground and the relative "
        "humidity measurement."
    ),
    ("10_minutes", "temperature_air", "tm5_10"): "Air temperature 5 cm above ground, instant.",
    ("10_minutes", "temperature_air", "tt_10"): "Air temperature 2 m above ground, instant.",
    ("10_minutes", "temperature_extreme", "tn5_10"): (
        "Minimum of air temperature at 5 cm height during the last 10 minutes."
    ),
    ("10_minutes", "temperature_extreme", "tn_10"): (
        "Minimum of air temperature at 2 m height during the last 10 minutes."
    ),
    ("10_minutes", "temperature_extreme", "tx5_10"): (
        "Maximum of air temperature at 5 cm height during the last 10 minutes."
    ),
    ("10_minutes", "temperature_extreme", "tx_10"): (
        "Maximum of air temperature at 2 m height during the last 10 minutes."
    ),
    ("10_minutes", "wind_extreme", "dx_10"): "Wind direction of the maximum wind speed during the previous 10 minutes.",
    ("10_minutes", "wind_extreme", "fmx_10"): (
        "Maximum of the wind speed from the 1 minute mean values of the 3-second maxima of the previous 10 minutes."
    ),
    ("10_minutes", "wind_extreme", "fnx_10"): "Minimum of wind speed during the previous 10 minutes.",
    ("10_minutes", "wind_extreme", "fx_10"): "Maximum of wind speed during the previous 10 minutes.",
    ("10_minutes", "wind", "dd_10"): "Mean wind direction during the previous 10 minutes.",
    ("10_minutes", "wind", "ff_10"): "Mean wind speed during the previous 10 minutes.",
    ("1_minute", "precipitation", "rs_01"): "Sum of the precipitation height.",
    ("1_minute", "precipitation", "rs_ind_01"): "Indicator of precipitation; if.",
    ("1_minute", "precipitation", "rth_01"): "Value from tipping bucket rain gauge.",
    ("1_minute", "precipitation", "rwh_01"): "Value from electronic rain gauge with tilting scales.",
    ("5_minutes", "precipitation", "rs_05"): "Sum of the precipitation height of the previous 5 minutes.",
    ("5_minutes", "precipitation", "rs_ind_05"): (
        "Indicator of precipitation; if QN = 1 then:; 0 = no precipitation, permanent sensor installed; 1 = "
        "precipitation, permanent sensor installed; 2 = no precipitation, heating in operation, permanent sensor "
        "installed; 3 = precipitation, heating in operation, permanent sensor installed; if QN > 1 then:; 0 = no "
        "precipitation; 1 = precipitation."
    ),
    ("daily", "climate_summary", "fm"): "Daily mean of wind velocity.",
    ("daily", "climate_summary", "fx"): "Daily maximum of windgust.",
    ("daily", "climate_summary", "nm"): "Daily mean of cloud cover.",
    ("daily", "climate_summary", "pm"): "Daily mean of pressure.",
    ("daily", "climate_summary", "qn_3"): "Quality level of the following columns.",
    ("daily", "climate_summary", "qn_4"): "Quality level of the following columns.",
    ("daily", "climate_summary", "rsk"): "Daily precipitation height.",
    ("daily", "climate_summary", "rskf"): "Precipitation form numerical code.",
    ("daily", "climate_summary", "sdk"): "Daily sunshine duration.",
    ("daily", "climate_summary", "shk_tag"): "Daily snow depth.",
    ("daily", "climate_summary", "tgk"): "Daily minimum of air temperature at 5 cm above ground.",
    ("daily", "climate_summary", "tmk"): "Daily mean of temperature.",
    ("daily", "climate_summary", "tnk"): "Daily minimum of temperature at 2m height.",
    ("daily", "climate_summary", "txk"): "Daily maximum of temperature at 2 m height.",
    ("daily", "climate_summary", "upm"): "Daily mean of relative humidity.",
    ("daily", "climate_summary", "vpm"): "Daily mean of vapor pressure.",
    ("daily", "precipitation_more", "nsh_tag"): "Fresh snow depth.",
    ("daily", "precipitation_more", "rs"): "Daily precipitation height.",
    ("daily", "precipitation_more", "rsf"): "Precipitation form numerical code.",
    ("daily", "precipitation_more", "sh_tag"): "Height of snow pack.",
    ("daily", "solar", "atmo_strahl"): "Longwave downward radiation J /cm^2.",
    ("daily", "solar", "fd_strahl"): "Daily sum of diffuse solar radiation J /cm^2.",
    ("daily", "solar", "fg_strahl"): "Daily sum of solar incoming radiation J /cm^2.",
    ("daily", "solar", "sd_strahl"): "Daily sum of sunshine duration.",
    ("daily", "temperature_soil", "v_te002m"): "Daily soil temperature in 2 cm depth.",
    ("daily", "temperature_soil", "v_te005m"): "Daily soil temperature in 5 cm depth.",
    ("daily", "temperature_soil", "v_te010m"): "Daily soil temperature in 10 cm depth.",
    ("daily", "temperature_soil", "v_te020m"): "Daily soil temperature in 20 cm depth.",
    ("daily", "temperature_soil", "v_te050m"): "Daily soil temperature in 50 cm depth.",
    ("daily", "water_equivalent", "ash_6"): "Height of set snow in cm; missing value = -999.",
    ("daily", "water_equivalent", "sh_tag"): "Snow height in cm; missing value = -999.",
    ("daily", "water_equivalent", "waas_6"): "Wasseräquivalent ausgestochene Schneehöhe in mm; missing value = -999.",
    ("daily", "water_equivalent", "wash_6"): "Wasseräquivalent der Gesamtschneehöhe in mm; missing value = -999.",
    ("hourly", "cloud_type", "v_n"): "Total cloud cover.",
    ("hourly", "cloud_type", "v_n_i"): "Index how measurement is taken, P = by human person,I = by instrument.",
    ("hourly", "cloud_type", "v_s1_cs"): "Cloud type of 1. layer.",
    ("hourly", "cloud_type", "v_s1_csa"): "Abbrev. cloud type 1.layer.",
    ("hourly", "cloud_type", "v_s1_hhs"): "Lower boundary height of 1.layer.",
    ("hourly", "cloud_type", "v_s1_ns"): "Cloud cover of 1. laye.",
    ("hourly", "cloud_type", "v_s2_cs"): "Cloud type of 2. layer.",
    ("hourly", "cloud_type", "v_s2_csa"): "Abbrev. cloud type 2.layer.",
    ("hourly", "cloud_type", "v_s2_hhs"): "Lower boundary height of 2.layer.",
    ("hourly", "cloud_type", "v_s2_ns"): "Cloud cover of 1. laye.",
    ("hourly", "cloud_type", "v_s3_cs"): "Cloud type of 3. layer.",
    ("hourly", "cloud_type", "v_s3_csa"): "Abbrev. cloud type 3.layer.",
    ("hourly", "cloud_type", "v_s3_hhs"): "Lower boundary height of 3.layer.",
    ("hourly", "cloud_type", "v_s3_ns"): "Cloud cover of 3. layer.",
    ("hourly", "cloud_type", "v_s4_cs"): "Cloud type of 4. layer.",
    ("hourly", "cloud_type", "v_s4_csa"): "Abbrev. cloud type 4.layer.",
    ("hourly", "cloud_type", "v_s4_hhs"): "Lower boundary height of 4.layer.",
    ("hourly", "cloud_type", "v_s4_ns"): "Cloud cover of 4. layer.",
    ("hourly", "cloudiness", "v_n"): "Total cloud cover.",
    ("hourly", "cloudiness", "v_n_i"): "Index how measurement is taken, P = by human person,I = by instrument.",
    ("hourly", "dew_point", "td"): "Dew point temperature.",
    ("hourly", "dew_point", "tt"): "Air temperature.",
    ("hourly", "moisture", "absf_std"): "Computed hourly value of absolute humidity.",
    ("hourly", "moisture", "p_std"): "Hourly value of barometric pressure.",
    ("hourly", "moisture", "rf_std"): "Relative humidity.",
    ("hourly", "moisture", "td_std"): "Dew point temperature in 2m above ground.",
    ("hourly", "moisture", "tf_std"): "Computed hourly value of wet bulb temperature.",
    ("hourly", "moisture", "tt_std"): "Air temperatur in 2m above ground.",
    ("hourly", "moisture", "vp_std"): "Computed hourly value of vapour pressure.",
    ("hourly", "precipitation", "r1"): "Precipitation.",
    ("hourly", "precipitation", "rs_ind"): (
        "Precipitation indicator; 0 = no; 1 = yes,-999 = missing value numerical code."
    ),
    ("hourly", "precipitation", "wrtr"): (
        "Precipitation form; 0=No precipitation; 9=Missing value, Type of precipitation unascertainable, automatically "
        "ascertainment; 8=Liquid and solid precipitation, automatically ascertainment; 7=Solid precipitation, "
        "automatically ascertainment; 6=Liquid precipitation, automatically ascertainment; 4=Type of precipitation "
        "unascertainable and depositional precipitation, automatically ascertainment; 1=precipitation only "
        "(in historical "
        "Data before 01.01.1979),-999 = missing value numerical code."
    ),
    ("hourly", "pressure", "p0"): "Barometric pressure at station height.",
    ("hourly", "solar", "atmo_lberg"): "Longwave downward radiation.",
    ("hourly", "solar", "fd_lberg"): "Hourly sum of diffuse solar radiation.",
    ("hourly", "solar", "fg_lberg"): (
        "The solar incoming radiation includes the direct and the diffuse part of the solar radiation with "
        "respect to the "
        "horizontal plane. It is sometimes also referred to as shortwave, including the solar spectrum up to "
        "2.8 micron, "
        "as opposed to longwave , which refers to the thermal radiation of the atmosphere."
    ),
    ("hourly", "solar", "mess_datum_woz"): "Local true solar time.",
    ("hourly", "solar", "sd_lberg"): "Hourly sum of sunshine duration.",
    ("hourly", "solar", "zenit"): (
        "Solar zenith angle at mid of interval,The solar zenith angle is between 0-180 and is defined as: ZENIT= 90 - "
        "solar_height."
    ),
    ("hourly", "sun", "sd_so"): "Hourly sunshine duration.",
    ("hourly", "temperature_air", "rf_tu"): "Relative humidity.",
    ("hourly", "temperature_air", "tt_tu"): "Air temperature.",
    ("hourly", "temperature_soil", "v_te002"): "Soil temperature in 2 cm depth.",
    ("hourly", "temperature_soil", "v_te005"): "Soil temperature in 5 cm depth.",
    ("hourly", "temperature_soil", "v_te010"): "Soil temperature in 10 cm depth.",
    ("hourly", "temperature_soil", "v_te020"): "Soil temperature in 20 cm depth.",
    ("hourly", "temperature_soil", "v_te050"): "Soil temperature in 50 cm depth.",
    ("hourly", "temperature_soil", "v_te100"): "Soil temperature in 100 cm depth.",
    ("hourly", "visibility", "v_vv"): "Visibility range.",
    ("hourly", "visibility", "v_vv_i"): (
        "Visibility index, noting how the measurement is taken,P=by human person,I=by an instrument."
    ),
    ("hourly", "weather_phenomena", "ww"): "Weather code numerical code.",
    ("hourly", "weather_phenomena", "ww_text"): "Weather description.",
    ("hourly", "wind_extreme", "fx_911"): "Windspeed, windgust.",
    ("hourly", "wind_synoptic", "dd"): "Winddirection.",
    ("hourly", "wind_synoptic", "ff"): "Windspeed.",
    ("monthly", "climate_summary", "mo_fk"): "Monthly mean of daily wind speed Bft.",
    ("monthly", "climate_summary", "mo_n"): "Monthly mean of cloud cover.",
    ("monthly", "climate_summary", "mo_rr"): "Monthly sum of precipitation height.",
    ("monthly", "climate_summary", "mo_sd_s"): "Monthly sum of sunshine duration.",
    ("monthly", "climate_summary", "mo_tn"): "Monthly mean of daily temperature minima in 2 m above ground.",
    ("monthly", "climate_summary", "mo_tt"): "Monthly mean temperature 2 m above ground.",
    ("monthly", "climate_summary", "mo_tx"): "Monthly mean of daily temperature maxima at 2 m above ground.",
    ("monthly", "climate_summary", "mx_fx"): "Monthly maximum of daily wind speed.",
    ("monthly", "climate_summary", "mx_rs"): "Monthly maximum of daily precipitation height.",
    ("monthly", "climate_summary", "mx_tn"): "Monthly minimum of daily temperature minima in 2 m above ground.",
    ("monthly", "climate_summary", "mx_tx"): "Monthly maximum of daily temperature maxima in 2 m above ground.",
    ("monthly", "climate_summary", "qn_4"): "Quality level of the data in the following columns.",
    ("monthly", "climate_summary", "qn_6"): "Quality level of the data in the following columns.",
    ("monthly", "precipitation_more", "mo_nsh"): "Monthly sum of daily fresh snow.",
    ("monthly", "precipitation_more", "mo_rr"): "Monthly sum of precipitation height.",
    ("monthly", "precipitation_more", "mo_sh_s"): "Monthly sum of daily height of snow pack.",
    ("monthly", "precipitation_more", "mx_rs"): "Monthly maximum of daily precipitation height.",
}
