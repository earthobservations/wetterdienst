# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Per-provider descriptions of the fields each source publishes.

What a given provider's ``name_original`` means, in prose -- as against the canonical,
provider-independent sentence in ``wetterdienst.metadata.parameter_table``, which describes the
*quantity* rather than one source's version of it.

Most of these were written for the provider documentation tables and lived only in those markdown
files, where the REST API, MCP and CLI could not reach them and where the two copies drifted apart.
The model is the source now, and ``tests/test_docs.py`` checks the tables still agree with it.

The DWD observation entries are largely transcribed from the English ``DESCRIPTION_*_en.pdf``
sheets DWD publishes beside the data, which are more specific than the text the docs carried. DWD
CDC is Creative Commons BY 4.0
(https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.txt), so its wording is reproduced
with attribution to the Deutscher Wetterdienst. A sheet's cell is used only where it says at least
as much as the curated text: some are terse, a few are truncated (``V_S1_NS`` reads "cloud cover of
1. laye", and ``V_S2_NS`` repeats that for the second layer), and two are left untranslated in an
otherwise English sheet.

Six more providers publish descriptions of their own fields, in machine-readable form, and those
are taken as they come:

- MeteoSwiss: ``ogd-smn_meta_parameters.csv``, published beside the data, English column
- MET Norway: the Frost ``/elements`` endpoint, ``lang=en-US``
- KNMI: the ``long_name`` attribute on each variable of the observation NetCDF files
- FMI: the ``observableProperty`` metadata endpoint, ``language=eng``, composed from its label,
  statistical function and aggregation period ("Air temperature. Mean over 1 minute.")
- AEMET: the ``metadatos`` payload that accompanies every response, translated from Spanish
- SMHI: the parameter listing of the metobs API, translated from Swedish
- LHMT: the field list on api.meteo.lt, translated from Lithuanian
- Météo-France: the `*_descriptif_champs*.csv` published beside each resolution, translated from
  French
- Met Office: the MIDAS table dictionaries CEDA publishes, already in English
- DWD forecast codes: `MetElementDefinition.xml`. It defines the MOSMIX elements, and swsmos reuses
  their names while publishing different units -- MOSMIX `TD` is Kelvin, swsmos `TD` is Celsius -- so
  its wording is used only where it says nothing about the unit

The AEMET, SMHI, LHMT and Météo-France translations are ours. Everything else in this table is the
source's own wording, so a sentence here can be checked against what the provider says.

Keyed by metadata model name, then ``(resolution, dataset, name_original)``. Applied by
``build_metadata_model``.
"""

# Pegelonline serves the same parameters at whatever interval each station records at, so these are
# declared once and expanded over the resolutions below rather than written out five times. The
# resolution names must stay in step with `_EQUIDISTANCE_TO_RESOLUTION` in the provider module; a
# name that drifts out of step leaves its parameters with no description, which
# `test_wsv_every_parameter_is_described` catches.
_WSV_PEGEL_RESOLUTIONS = ("1_minute", "5_minutes", "10_minutes", "15_minutes", "hourly")
_HUBEAU_RESOLUTIONS = ("5_minutes", "6_minutes", "10_minutes", "15_minutes", "hourly")

# Pegelonline names each timeseries in German; the meaning below is the API's own ``longname`` for
# that shortname, e.g. HL is LUFTFEUCHTE and SIGH SIGNIFIKANTEWELLENHÖHE.
_WSV_PEGEL_PARAMETERS = {
    "CL": "average chlorid concentration during time scale",
    "DFH": "average clearance height during time scale",
    "GRU": "average groundwater level during time scale",
    "HL": "average relative humidity of the air during time scale",
    "LF": "average electric conductivity during time scale",
    "LT": "average air temperature during time scale",
    "MAXH": "max wave height during time scale",
    "NIEDERSCHLAG": "average precipitation height during time scale",
    "NIEDERSCHLAGSINTENSITÄT": "average precipitation intensity during time scale",
    "O2": "average oxygen level during time scale",
    "PH": "average pH during time scale",
    "Q": "average discharge during time scale",
    "R": "direction of the water current",
    "SIGH": "average significant wave height during time scale",
    "TP": "average wave period during time scale",
    "TR": "average turbidity during time scale",
    "VA": "average flow speed during time scale",
    "W": "average water level during time scale",
    "WG": "average wind speed during time scale",
    "WR": "average wind direction during time scale",
    "WT": "average water temperature during time scale",
}


SOURCE_DESCRIPTIONS: dict[str, dict[tuple[str, str, str], str]] = {
    "HubeauMetadata": {
        (resolution, "data", name_original): description
        for resolution in _HUBEAU_RESOLUTIONS
        for name_original, description in (("H", "Stage."), ("Q", "Flow."))
    },
    "ChmiObservationMetadata": {
        ("10_minutes", "data", "F"): "Wind speed at 10 m, measured every ten minutes.",
        ("10_minutes", "data", "H"): "Relative humidity at 2 m, measured every ten minutes.",
        ("10_minutes", "data", "P"): "Air pressure at station level, measured every ten minutes.",
        ("10_minutes", "data", "T"): "Air temperature at 2 m, measured every ten minutes.",
        ("annual", "data", "SRA"): "Precipitation, read at 06:00 each day.",
        ("annual", "data", "T"): (
            "Air temperature at 2 m, the daily value being the average of the 06:00, 13:00 and 20:00 observations."
        ),
        ("annual", "data", "TMA"): "Maximum air temperature at 2 m, read at 20:00 each day.",
        ("annual", "data", "TMI"): "Minimum air temperature at 2 m, read at 20:00 each day.",
        ("daily", "data", "F"): (
            "Wind speed at 10 m, the daily value being the average of the 06:00, 13:00 and 20:00 observations."
        ),
        ("daily", "data", "Fmax"): "Maximum wind speed at 10 m.",
        ("daily", "data", "H"): (
            "Relative humidity at 2 m, the daily value being the average of the 06:00, 13:00 and 20:00 observations."
        ),
        ("daily", "data", "P"): (
            "Air pressure at station level, the daily value being the average of the 06:00, 13:00 and "
            "20:00 observations."
        ),
        ("daily", "data", "SCE"): "Snow depth at ground level, read at 06:00.",
        ("daily", "data", "SRA"): "Precipitation, read at 06:00.",
        ("daily", "data", "SSV"): "Sunshine duration, in hours.",
        ("daily", "data", "T"): (
            "Air temperature at 2 m, the daily value being the average of the 06:00, 13:00 and 20:00 observations."
        ),
        ("daily", "data", "TMA"): "Maximum air temperature at 2 m, read at 20:00.",
        ("daily", "data", "TMI"): "Minimum air temperature at 2 m, read at 20:00.",
        ("hourly", "data", "P"): "Air pressure at station level.",
        ("hourly", "data", "SRA1H"): "Precipitation over one hour.",
        ("hourly", "data", "Td"): "Dew point temperature at 2 m.",
        ("monthly", "data", "SRA"): "Precipitation, read at 06:00 each day.",
        ("monthly", "data", "T"): (
            "Air temperature at 2 m, the daily value being the average of the 06:00, 13:00 and 20:00 observations."
        ),
        ("monthly", "data", "TMA"): "Maximum air temperature at 2 m, read at 20:00 each day.",
        ("monthly", "data", "TMI"): "Minimum air temperature at 2 m, read at 20:00 each day.",
    },
    "DwdSwsmosMetadata": {
        ("hourly", "data", "R650"): "Probability of precipitation > 5.0mm during the last 6 hours",
        ("hourly", "data", "RR6"): "Total precipitation during the last 6 hours",
        ("hourly", "data", "RRL1c"): (
            "Total liquid precipitation during the last hour consistent with significant weather"
        ),
        ("hourly", "data", "TD"): "Dew point temperature 2m above surface.",
        ("hourly", "data", "WWL6"): "Probability: Occurrence of liquid precipitation within the last 6 hours",
    },
    "DwdDerivedMetadata": {
        ("hourly", "radiation_global", "qn_952"): "Quality flag.",
        ("hourly", "sunshine_duration", "qn_952"): "Quality flag.",
        ("daily", "soil", "bfgl01_ag"): "soil moisture for meadow on loamy silt 0-10cm",
        ("daily", "soil", "bfgl02_ag"): "soil moisture for meadow on loamy silt 10-20cm",
        ("daily", "soil", "bfgl03_ag"): "soil moisture for meadow on loamy silt 20-30cm",
        ("daily", "soil", "bfgl04_ag"): "soil moisture for meadow on loamy silt 30-40cm",
        ("daily", "soil", "bfgl05_ag"): "soil moisture for meadow on loamy silt 40-50cm",
        ("daily", "soil", "bfgl06_ag"): "soil moisture for meadow on loamy silt 50-60cm",
        ("daily", "soil", "bfgl_ag"): "soil moisture for meadow on loamy silt 0-60cm",
        ("daily", "soil", "bfgs_ag"): "soil moisture for meadow on sand 0-60cm",
        ("daily", "soil", "bfml_ag"): "soil moisture for corn on loamy silt 0-60cm",
        ("daily", "soil", "bfms_ag"): "soil moisture for corn on sand 0-60cm",
        ("daily", "soil", "bfwl_ag"): "soil moisture for winter wheat on loamy silt 0-60cm",
        ("daily", "soil", "bfws_ag"): "soil moisture for winter wheat on sand 0-60cm",
        ("daily", "soil", "ts05"): "mean soil temperature at 0.05m depth",
        ("daily", "soil", "ts10"): "mean soil temperature at 0.1m depth",
        ("daily", "soil", "ts100"): "mean soil temperature at 1m depth",
        ("daily", "soil", "ts20"): "mean soil temperature at 0.2m depth",
        ("daily", "soil", "ts50"): "mean soil temperature at 0.5m depth",
        ("daily", "soil", "tsls05"): "mean soil temperature for loamy sand at 0.05m depth",
        ("daily", "soil", "tssl05"): "mean soil temperature for loamy silt at 0.05m depth",
        ("daily", "soil", "vpgfao"): "potential evapotranspiration for meadow (FAO method)",
        ("daily", "soil", "vpgh"): "potential evapotranspiration for meadow (Haude method)",
        ("daily", "soil", "vrgl_ag"): "evaporation height for meadow on loamy silt",
        ("daily", "soil", "vrgs_ag"): "evaporation height for meadow on sand",
        ("daily", "soil", "vrml_ag"): "evaporation height for corn on loamy silt",
        ("daily", "soil", "vrms_ag"): "evaporation height for corn on sand",
        ("daily", "soil", "vrwl_ag"): "evaporation height for winter wheat on loamy silt",
        ("daily", "soil", "vrws_ag"): "evaporation height for winter wheat on sand",
        ("daily", "soil", "zfumi"): "frozen ground layer thickness",
        ("daily", "soil", "ztkmi"): "thawing thickness under vegetation",
        ("daily", "soil", "ztumi"): "thawing thickness under bare soil",
        ("hourly", "radiation_global", "fg_duett"): "global radiation",
        ("hourly", "radiation_global", "fg_un_duett"): "uncertainty of global radiation",
        ("hourly", "sunshine_duration", "fg_un_duett"): "uncertainty of sunshine duration",
        ("hourly", "sunshine_duration", "sd_duett"): "sunshine duration",
        ("monthly", "climate_correction_factor", "KF"): (
            "quotient of yearly degree days of reference station in Potsdam and postal code"
        ),
        ("monthly", "cooling_degreehours_13", "Anzahl Kuehlstunden"): (
            "number of hours with positive temperature differences between air temperature and reference temperature"
        ),
        ("monthly", "cooling_degreehours_13", "Anzahl Stunden"): "number of hours per month",
        ("monthly", "cooling_degreehours_13", "Kuehlgradstunden"): (
            "accumulated hourly temperature differences between air temperature and reference temperature"
        ),
        ("monthly", "cooling_degreehours_16", "Anzahl Kuehlstunden"): (
            "number of hours with positive temperature differences between air temperature and reference temperature"
        ),
        ("monthly", "cooling_degreehours_16", "Anzahl Stunden"): "number of hours per month",
        ("monthly", "cooling_degreehours_16", "Kuehlgradstunden"): (
            "accumulated hourly temperature differences between air temperature and reference temperature"
        ),
        ("monthly", "cooling_degreehours_18", "Anzahl Kuehlstunden"): (
            "number of hours with positive temperature differences between air temperature and reference temperature"
        ),
        ("monthly", "cooling_degreehours_18", "Anzahl Stunden"): "number of hours per month",
        ("monthly", "cooling_degreehours_18", "Kuehlgradstunden"): (
            "accumulated hourly temperature differences between air temperature and reference temperature"
        ),
        ("monthly", "heating_degreedays", "Anzahl Heiztage"): (
            "number of days with daily mean air temperature less than 15 degree Celsius"
        ),
        ("monthly", "heating_degreedays", "Anzahl Tage"): (
            "number of available values of mean daily air temperatures per month"
        ),
        ("monthly", "heating_degreedays", "Monatsgradtage"): "sum of degree days over a month",
        ("monthly", "soil", "maximum von zfumi"): "maximum frozen ground layer thickness in the month",
        ("monthly", "soil", "maximum von ztkmi"): "maximum thawing thickness under vegetation in the month",
        ("monthly", "soil", "maximum von ztumi"): "maximum thawing thickness under bare soil in the month",
        ("monthly", "soil", "mittel von bfgl01_ag"): "mean soil moisture for meadow on loamy silt 0-10cm",
        ("monthly", "soil", "mittel von bfgl02_ag"): "mean soil moisture for meadow on loamy silt 10-20cm",
        ("monthly", "soil", "mittel von bfgl03_ag"): "mean soil moisture for meadow on loamy silt 20-30cm",
        ("monthly", "soil", "mittel von bfgl04_ag"): "mean soil moisture for meadow on loamy silt 30-40cm",
        ("monthly", "soil", "mittel von bfgl05_ag"): "mean soil moisture for meadow on loamy silt 40-50cm",
        ("monthly", "soil", "mittel von bfgl06_ag"): "mean soil moisture for meadow on loamy silt 50-60cm",
        ("monthly", "soil", "mittel von bfgl_ag"): "mean soil moisture for meadow on loamy silt 0-60cm",
        ("monthly", "soil", "mittel von bfgs_ag"): "mean soil moisture for meadow on sand 0-60cm",
        ("monthly", "soil", "mittel von bfml_ag"): "mean soil moisture for corn on loamy silt 0-60cm",
        ("monthly", "soil", "mittel von bfms_ag"): "mean soil moisture for corn on sand 0-60cm",
        ("monthly", "soil", "mittel von bfwl_ag"): "mean soil moisture for winter wheat on loamy silt 0-60cm",
        ("monthly", "soil", "mittel von bfws_ag"): "mean soil moisture for winter wheat on sand 0-60cm",
        ("monthly", "soil", "mittel von ts05"): "mean soil temperature at 0.05m depth",
        ("monthly", "soil", "mittel von ts10"): "mean soil temperature at 0.1m depth",
        ("monthly", "soil", "mittel von ts100"): "mean soil temperature at 1m depth",
        ("monthly", "soil", "mittel von ts20"): "mean soil temperature at 0.2m depth",
        ("monthly", "soil", "mittel von ts50"): "mean soil temperature at 0.5m depth",
        ("monthly", "soil", "mittel von tsls05"): "mean soil temperature for loamy sand at 0.05m depth",
        ("monthly", "soil", "mittel von tssl05"): "mean soil temperature for loamy silt at 0.05m depth",
        ("monthly", "soil", "summe von vpgfao"): "sum of potential evapotranspiration for meadow (FAO method)",
        ("monthly", "soil", "summe von vpgh"): "sum of potential evapotranspiration for meadow (Haude method)",
        ("monthly", "soil", "summe von vrgl_ag"): "sum of evaporation height for meadow on loamy silt",
        ("monthly", "soil", "summe von vrgs_ag"): "sum of evaporation height for meadow on sand",
        ("monthly", "soil", "summe von vrml_ag"): "sum of evaporation height for corn on loamy silt",
        ("monthly", "soil", "summe von vrms_ag"): "sum of evaporation height for corn on sand",
        ("monthly", "soil", "summe von vrwl_ag"): "sum of evaporation height for winter wheat on loamy silt",
        ("monthly", "soil", "summe von vrws_ag"): "sum of evaporation height for winter wheat on sand",
    },
    "DwdDmoMetadata": {
        ("hourly", "icon", "wwpd"): "Probability: Occurrence of any precipitation within the last 24 hours",
        ("hourly", "icon", "nl"): "Low cloud cover (lower than 2 km).",
        ("hourly", "icon_eu", "nl"): "Low cloud cover (lower than 2 km).",
        ("hourly", "icon", "dd"): "Wind direction",
        ("hourly", "icon", "drr1"): "Duration of precipitation within the last hour",
        ("hourly", "icon", "e_dd"): "Absolute error wind direction",
        ("hourly", "icon", "e_ff"): "Absolute error wind speed 10m above surface",
        ("hourly", "icon", "e_ppp"): "Absolute error surface pressure",
        ("hourly", "icon", "e_td"): "Absolute error dew point 2m above surface",
        ("hourly", "icon", "e_ttt"): "Absolute error temperature 2m above surface",
        ("hourly", "icon", "ff"): "Wind speed",
        ("hourly", "icon", "fx1"): "Maximum wind gust within the last hour",
        ("hourly", "icon", "fx3"): "Maximum wind gust within the last 3 hours",
        ("hourly", "icon", "fx625"): "Probability of wind gusts >= 25kn within the last 6 hours",
        ("hourly", "icon", "fx640"): "Probability of wind gusts >= 40kn within the last 6 hours",
        ("hourly", "icon", "fx655"): "Probability of wind gusts >= 55kn within the last 6 hours",
        ("hourly", "icon", "fxh"): "Maximum wind gust within the last 12 hours",
        ("hourly", "icon", "fxh25"): "Probability of wind gusts >= 25kn within the last 12 hours",
        ("hourly", "icon", "fxh40"): "Probability of wind gusts >= 40kn within the last 12 hours",
        ("hourly", "icon", "fxh55"): "Probability of wind gusts >= 55kn within the last 12 hours",
        ("hourly", "icon", "h_bsc"): "Cloud base of convective clouds",
        ("hourly", "icon", "n"): "Total cloud cover",
        ("hourly", "icon", "n05"): "Cloud cover below 500 ft.",
        ("hourly", "icon", "neff"): "Effective cloud cover",
        ("hourly", "icon", "nh"): "High cloud cover (>7 km)",
        ("hourly", "icon", "nlm"): "Cloud cover low and mid level clouds below 7000 m",
        ("hourly", "icon", "nm"): "Midlevel cloud cover (2-7 km)",
        ("hourly", "icon", "pevap"): "Potential evapotranspiration within the last 24 hours",
        ("hourly", "icon", "pppp"): "Surface pressure, reduced",
        ("hourly", "icon", "psd00"): "Probability: relative sunshine duration > 0 % within 24 hours",
        ("hourly", "icon", "psd30"): "Probability: relative sunshine duration > 30 % within 24 hours",
        ("hourly", "icon", "psd60"): "Probability: relative sunshine duration > 60 % within 24 hours",
        ("hourly", "icon", "r101"): "Probability of precipitation > 0.1 mm during the last hour",
        ("hourly", "icon", "r102"): "Probability of precipitation > 0.2 mm during the last hour",
        ("hourly", "icon", "r103"): "Probability of precipitation > 0.3 mm during the last hour",
        ("hourly", "icon", "r105"): "Probability of precipitation > 0.5 mm during the last hour",
        ("hourly", "icon", "r107"): "Probability of precipitation > 0.7 mm during the last hour",
        ("hourly", "icon", "r110"): "Probability of precipitation > 1.0 mm during the last hour",
        ("hourly", "icon", "r120"): "Probability of precipitation > 2.0mm during the last hour",
        ("hourly", "icon", "r130"): "Probability of precipitation > 3.0 mm during the last hour",
        ("hourly", "icon", "r150"): "Probability of precipitation > 5.0 mm during the last hour",
        ("hourly", "icon", "r600"): "Probability of precipitation > 0.0mm during the last 6 hours",
        ("hourly", "icon", "r602"): "Probability of precipitation > 0.2mm during the last 6 hours",
        ("hourly", "icon", "r610"): "Probability of precipitation > 1.0mm during the last 6 hours",
        ("hourly", "icon", "r650"): "Probability of precipitation > 5.0mm during the last 6 hours",
        ("hourly", "icon", "rad1h"): "Global Irradiance",
        ("hourly", "icon", "radl3"): "Long wave radiation balance during the last 3 hours",
        ("hourly", "icon", "rads3"): "Short wave radiation balance during the last 3 hours",
        ("hourly", "icon", "rd00"): "Probability of precipitation > 0.0mm during the last 24 hours",
        ("hourly", "icon", "rd02"): "Probability of precipitation > 0.2mm during the last 24 hours",
        ("hourly", "icon", "rd10"): "Probability of precipitation > 1.0mm during the last 24 hours",
        ("hourly", "icon", "rd50"): "Probability of precipitation > 5.0mm during the last 24 hours",
        ("hourly", "icon", "rh00"): "Probability of precipitation > 0.0mm during the last 12 hours",
        ("hourly", "icon", "rh02"): "Probability of precipitation > 0.2mm during the last 12 hours",
        ("hourly", "icon", "rh10"): "Probability of precipitation > 1.0mm during the last 12 hours",
        ("hourly", "icon", "rh50"): "Probability of precipitation > 5.0mm during the last 12 hours",
        ("hourly", "icon", "rr1"): "Total precipitation during the last hour",
        ("hourly", "icon", "rr1c"): "Total precipitation during the last hour consistent with significant weather",
        ("hourly", "icon", "rr1o1"): "Probability of precipitation > 10.0 mm during the last hour",
        ("hourly", "icon", "rr1u1"): "Probability of precipitation > 25.0 mm during the last hour",
        ("hourly", "icon", "rr1w1"): "Probability of precipitation > 15.0 mm during the last hour",
        ("hourly", "icon", "rr3"): "Total precipitation during the last 3 hours",
        ("hourly", "icon", "rr3c"): "Total precipitation during the last 3 hours consistent with significant weather",
        ("hourly", "icon", "rr6"): "Total precipitation during the last 6 hours",
        ("hourly", "icon", "rr6c"): "Total precipitation during the last 6 hours consistent with significant weather",
        ("hourly", "icon", "rrad1"): "Global irradiance within the last hour",
        ("hourly", "icon", "rrd"): "Total precipitation during the last 24 hours",
        ("hourly", "icon", "rrdc"): "Total precipitation during the last 24 hours consistent with significant weather",
        ("hourly", "icon", "rrh"): "Total precipitation during the last 12 hours",
        ("hourly", "icon", "rrhc"): "Total precipitation during the last 12 hours consistent with significant weather",
        ("hourly", "icon", "rrl1c"): (
            "Total liquid precipitation during the last hour consistent with significant weather"
        ),
        ("hourly", "icon", "rrs1c"): "Snow-Rain-Equivalent during the last hour",
        ("hourly", "icon", "rrs3c"): "Snow-Rain-Equivalent during the last 3 hours",
        ("hourly", "icon", "rsund"): "Relative sunshine duration within the last 24 hours",
        ("hourly", "icon", "sund"): "Yesterdays total sunshine duration",
        ("hourly", "icon", "sund1"): "Sunshine duration during the last Hour",
        ("hourly", "icon", "sund3"): "Sunshine duration during the last 3 hours",
        ("hourly", "icon", "t5cm"): "Temperature 5cm above surface",
        ("hourly", "icon", "td"): "Dewpoint 2m above surface",
        ("hourly", "icon", "tg"): "Minimum surface temperature at 5cm within the last 12 hours",
        ("hourly", "icon", "tm"): "Mean temperature during the last 24 hours",
        ("hourly", "icon", "tn"): "Minimum temperature - within the last 12 hours",
        ("hourly", "icon", "ttt"): "Temperature 2m above surface",
        ("hourly", "icon", "tx"): "Maximum temperature - within the last 12 hours",
        ("hourly", "icon", "vv"): "Visibility",
        ("hourly", "icon", "vv10"): "Probability: Visibility below 1000m",
        ("hourly", "icon", "w1w2"): "Past weather during the last 6 hours",
        ("hourly", "icon", "wpc11"): "Optional significant weather (highest priority) during the last hour",
        ("hourly", "icon", "wpc31"): "Optional significant weather (highest priority) during the last 3 hours",
        ("hourly", "icon", "wpc61"): "Optional significant weather (highest priority) during the last 6 hours",
        ("hourly", "icon", "wpcd1"): "Optional significant weather (highest priority) during the last 24 hours",
        ("hourly", "icon", "wpch1"): "Optional significant weather (highest priority) during the last 12 hours",
        ("hourly", "icon", "ww"): "Significant Weather",
        ("hourly", "icon", "ww3"): "Significant Weather",
        ("hourly", "icon", "wwc"): "Probability: Occurrence of convective precipitation within the last hour",
        ("hourly", "icon", "wwc6"): "Probability: Occurrence of convective precipitation within the last 6 hours",
        ("hourly", "icon", "wwch"): "Probability: Occurrence of convective precipitation within the last 12 hours",
        ("hourly", "icon", "wwd"): "Probability: Occurrence of stratiform precipitation within the last hour",
        ("hourly", "icon", "wwd6"): "Probability: Occurrence of stratiform precipitation within the last 6 hours",
        ("hourly", "icon", "wwdh"): "Probability: Occurrence of stratiform precipitation within the last 12 hours",
        ("hourly", "icon", "wwf"): "Probability: Occurrence of freezing rain within the last hour",
        ("hourly", "icon", "wwf6"): "Probability: Occurrence of freezing rain within the last 6 hours",
        ("hourly", "icon", "wwfh"): "Probability: Occurrence of freezing rain within the last 12 hours",
        ("hourly", "icon", "wwl"): "Probability: Occurrence of liquid precipitation within the last hour",
        ("hourly", "icon", "wwl6"): "Probability: Occurrence of liquid precipitation within the last 6 hours",
        ("hourly", "icon", "wwlh"): "Probability: Occurrence of liquid precipitation within the last 12 hours",
        ("hourly", "icon", "wwm"): "Probability for fog within the last hour",
        ("hourly", "icon", "wwm6"): "Probability for fog within the last 6 hours",
        ("hourly", "icon", "wwmd"): "Probability for fog within the last 24 hours",
        ("hourly", "icon", "wwmh"): "Probability for fog within the last 12 hours",
        ("hourly", "icon", "wwp"): "Probability: Occurrence of precipitation within the last hour",
        ("hourly", "icon", "wwp6"): "Probability: Occurrence of precipitation within the last 6 hours",
        ("hourly", "icon", "wwph"): "Probability: Occurrence of precipitation within the last 12 hours",
        ("hourly", "icon", "wws"): "Probability: Occurrence of solid precipitation within the last hour",
        ("hourly", "icon", "wws6"): "Probability: Occurrence of solid precipitation within the last 6 hours",
        ("hourly", "icon", "wwsh"): "Probability: Occurrence of solid precipitation within the last 12 hours",
        ("hourly", "icon", "wwt"): "Probability: Occurrence of thunderstorms within the last hour",
        ("hourly", "icon", "wwt6"): "Probability: Occurrence of thunderstorms within the last 6 hours",
        ("hourly", "icon", "wwtd"): "Probability: Occurrence of thunderstorms within the last 24 hours",
        ("hourly", "icon", "wwth"): "Probability: Occurrence of thunderstorms within the last 12 hours",
        ("hourly", "icon", "wwz"): "Probability: Occurrence of drizzle within the last hour",
        ("hourly", "icon", "wwz6"): "Probability: Occurrence of drizzle within the last 6 hours",
        ("hourly", "icon", "wwzh"): "Probability: Occurrence of drizzle within the last 12 hours",
        ("hourly", "icon_eu", "dd"): "Wind direction",
        ("hourly", "icon_eu", "ff"): "Wind speed",
        ("hourly", "icon_eu", "fx1"): "Maximum wind gust within the last hour",
        ("hourly", "icon_eu", "fx3"): "Maximum wind gust within the last 3 hours",
        ("hourly", "icon_eu", "fxh"): "Maximum wind gust within the last 12 hours",
        ("hourly", "icon_eu", "fxh25"): "Probability of wind gusts >= 25kn within the last 12 hours",
        ("hourly", "icon_eu", "fxh40"): "Probability of wind gusts >= 40kn within the last 12 hours",
        ("hourly", "icon_eu", "fxh55"): "Probability of wind gusts >= 55kn within the last 12 hours",
        ("hourly", "icon_eu", "n"): "Total cloud cover",
        ("hourly", "icon_eu", "n05"): "Cloud cover below 500 ft.",
        ("hourly", "icon_eu", "neff"): "Effective cloud cover",
        ("hourly", "icon_eu", "nh"): "High cloud cover (>7 km)",
        ("hourly", "icon_eu", "nm"): "Midlevel cloud cover (2-7 km)",
        ("hourly", "icon_eu", "pppp"): "Surface pressure, reduced",
        ("hourly", "icon_eu", "r602"): "Probability of precipitation > 0.2mm during the last 6 hours",
        ("hourly", "icon_eu", "r650"): "Probability of precipitation > 5.0mm during the last 6 hours",
        ("hourly", "icon_eu", "rad1h"): "Global Irradiance",
        ("hourly", "icon_eu", "rd02"): "Probability of precipitation > 0.2mm during the last 24 hours",
        ("hourly", "icon_eu", "rd50"): "Probability of precipitation > 5.0mm during the last 24 hours",
        ("hourly", "icon_eu", "rh00"): "Probability of precipitation > 0.0mm during the last 12 hours",
        ("hourly", "icon_eu", "rh02"): "Probability of precipitation > 0.2mm during the last 12 hours",
        ("hourly", "icon_eu", "rh10"): "Probability of precipitation > 1.0mm during the last 12 hours",
        ("hourly", "icon_eu", "rh50"): "Probability of precipitation > 5.0mm during the last 12 hours",
        ("hourly", "icon_eu", "rr1c"): "Total precipitation during the last hour consistent with significant weather",
        ("hourly", "icon_eu", "rr3c"): (
            "Total precipitation during the last 3 hours consistent with significant weather"
        ),
        ("hourly", "icon_eu", "rrs1c"): "Snow-Rain-Equivalent during the last hour",
        ("hourly", "icon_eu", "rrs3c"): "Snow-Rain-Equivalent during the last 3 hours",
        ("hourly", "icon_eu", "sund1"): "Sunshine duration during the last Hour",
        ("hourly", "icon_eu", "t5cm"): "Temperature 5cm above surface",
        ("hourly", "icon_eu", "td"): "Dewpoint 2m above surface",
        ("hourly", "icon_eu", "tn"): "Minimum temperature - within the last 12 hours",
        ("hourly", "icon_eu", "ttt"): "Temperature 2m above surface",
        ("hourly", "icon_eu", "tx"): "Maximum temperature - within the last 12 hours",
        ("hourly", "icon_eu", "vv"): "Visibility",
        ("hourly", "icon_eu", "w1w2"): "Past weather during the last 6 hours",
        ("hourly", "icon_eu", "ww"): "Significant Weather",
        ("hourly", "icon_eu", "wwm"): "Probability for fog within the last hour",
        ("hourly", "icon_eu", "wwm6"): "Probability for fog within the last 6 hours",
        ("hourly", "icon_eu", "wwmh"): "Probability for fog within the last 12 hours",
    },
    "DwdMosmixMetadata": {
        ("hourly", "large", "nl"): "Low cloud cover (lower than 2 km)",
        ("hourly", "small", "nl"): "Low cloud cover (lower than 2 km)",
        ("hourly", "large", "wwpd"): "Probability: Occurrence of any precipitation within the last 24 hours",
        ("hourly", "large", "dd"): "Wind direction",
        ("hourly", "large", "drr1"): "Duration of precipitation within the last hour",
        ("hourly", "large", "e_dd"): "Absolute error wind direction",
        ("hourly", "large", "e_ff"): "Absolute error wind speed 10m above surface",
        ("hourly", "large", "e_ppp"): "Absolute error surface pressure",
        ("hourly", "large", "e_td"): "Absolute error dew point 2m above surface",
        ("hourly", "large", "e_ttt"): "Absolute error temperature 2m above surface",
        ("hourly", "large", "ff"): "Wind speed",
        ("hourly", "large", "fx1"): "Maximum wind gust within the last hour",
        ("hourly", "large", "fx3"): "Maximum wind gust within the last 3 hours",
        ("hourly", "large", "fx625"): "Probability of wind gusts >= 25kn within the last 6 hours",
        ("hourly", "large", "fx640"): "Probability of wind gusts >= 40kn within the last 6 hours",
        ("hourly", "large", "fx655"): "Probability of wind gusts >= 55kn within the last 6 hours",
        ("hourly", "large", "fxh"): "Maximum wind gust within the last 12 hours",
        ("hourly", "large", "fxh25"): "Probability of wind gusts >= 25kn within the last 12 hours",
        ("hourly", "large", "fxh40"): "Probability of wind gusts >= 40kn within the last 12 hours",
        ("hourly", "large", "fxh55"): "Probability of wind gusts >= 55kn within the last 12 hours",
        ("hourly", "large", "h_bsc"): "Cloud base of convective clouds",
        ("hourly", "large", "n"): "Total cloud cover",
        ("hourly", "large", "n05"): "Cloud cover below 500 ft.",
        ("hourly", "large", "neff"): "Effective cloud cover",
        ("hourly", "large", "nh"): "High cloud cover (>7 km)",
        ("hourly", "large", "nlm"): "Cloud cover low and mid level clouds below 7000 m",
        ("hourly", "large", "nm"): "Midlevel cloud cover (2-7 km)",
        ("hourly", "large", "pevap"): "Potential evapotranspiration within the last 24 hours",
        ("hourly", "large", "pppp"): "Surface pressure, reduced",
        ("hourly", "large", "psd00"): "Probability: relative sunshine duration > 0 % within 24 hours",
        ("hourly", "large", "psd30"): "Probability: relative sunshine duration > 30 % within 24 hours",
        ("hourly", "large", "psd60"): "Probability: relative sunshine duration > 60 % within 24 hours",
        ("hourly", "large", "r101"): "Probability of precipitation > 0.1 mm during the last hour",
        ("hourly", "large", "r102"): "Probability of precipitation > 0.2 mm during the last hour",
        ("hourly", "large", "r103"): "Probability of precipitation > 0.3 mm during the last hour",
        ("hourly", "large", "r105"): "Probability of precipitation > 0.5 mm during the last hour",
        ("hourly", "large", "r107"): "Probability of precipitation > 0.7 mm during the last hour",
        ("hourly", "large", "r110"): "Probability of precipitation > 1.0 mm during the last hour",
        ("hourly", "large", "r120"): "Probability of precipitation > 2.0mm during the last hour",
        ("hourly", "large", "r130"): "Probability of precipitation > 3.0 mm during the last hour",
        ("hourly", "large", "r150"): "Probability of precipitation > 5.0 mm during the last hour",
        ("hourly", "large", "r600"): "Probability of precipitation > 0.0mm during the last 6 hours",
        ("hourly", "large", "r602"): "Probability of precipitation > 0.2mm during the last 6 hours",
        ("hourly", "large", "r610"): "Probability of precipitation > 1.0mm during the last 6 hours",
        ("hourly", "large", "r650"): "Probability of precipitation > 5.0mm during the last 6 hours",
        ("hourly", "large", "rad1h"): "Global Irradiance",
        ("hourly", "large", "radl3"): "Long wave radiation balance during the last 3 hours",
        ("hourly", "large", "rads3"): "Short wave radiation balance during the last 3 hours",
        ("hourly", "large", "rd00"): "Probability of precipitation > 0.0mm during the last 24 hours",
        ("hourly", "large", "rd02"): "Probability of precipitation > 0.2mm during the last 24 hours",
        ("hourly", "large", "rd10"): "Probability of precipitation > 1.0mm during the last 24 hours",
        ("hourly", "large", "rd50"): "Probability of precipitation > 5.0mm during the last 24 hours",
        ("hourly", "large", "rh00"): "Probability of precipitation > 0.0mm during the last 12 hours",
        ("hourly", "large", "rh02"): "Probability of precipitation > 0.2mm during the last 12 hours",
        ("hourly", "large", "rh10"): "Probability of precipitation > 1.0mm during the last 12 hours",
        ("hourly", "large", "rh50"): "Probability of precipitation > 5.0mm during the last 12 hours",
        ("hourly", "large", "rr1"): "Total precipitation during the last hour",
        ("hourly", "large", "rr1c"): "Total precipitation during the last hour consistent with significant weather",
        ("hourly", "large", "rr1o1"): "Probability of precipitation > 10.0 mm during the last hour",
        ("hourly", "large", "rr1u1"): "Probability of precipitation > 25.0 mm during the last hour",
        ("hourly", "large", "rr1w1"): "Probability of precipitation > 15.0 mm during the last hour",
        ("hourly", "large", "rr3"): "Total precipitation during the last 3 hours",
        ("hourly", "large", "rr3c"): "Total precipitation during the last 3 hours consistent with significant weather",
        ("hourly", "large", "rr6"): "Total precipitation during the last 6 hours",
        ("hourly", "large", "rr6c"): "Total precipitation during the last 6 hours consistent with significant weather",
        ("hourly", "large", "rrad1"): "Global irradiance within the last hour",
        ("hourly", "large", "rrd"): "Total precipitation during the last 24 hours",
        ("hourly", "large", "rrdc"): "Total precipitation during the last 24 hours consistent with significant weather",
        ("hourly", "large", "rrh"): "Total precipitation during the last 12 hours",
        ("hourly", "large", "rrhc"): "Total precipitation during the last 12 hours consistent with significant weather",
        ("hourly", "large", "rrl1c"): (
            "Total liquid precipitation during the last hour consistent with significant weather"
        ),
        ("hourly", "large", "rrs1c"): "Snow-Rain-Equivalent during the last hour",
        ("hourly", "large", "rrs3c"): "Snow-Rain-Equivalent during the last 3 hours",
        ("hourly", "large", "rsund"): "Relative sunshine duration within the last 24 hours",
        ("hourly", "large", "sund"): "Yesterdays total sunshine duration",
        ("hourly", "large", "sund1"): "Sunshine duration during the last Hour",
        ("hourly", "large", "sund3"): "Sunshine duration during the last 3 hours",
        ("hourly", "large", "t5cm"): "Temperature 5cm above surface",
        ("hourly", "large", "td"): "Dewpoint 2m above surface",
        ("hourly", "large", "tg"): "Minimum surface temperature at 5cm within the last 12 hours",
        ("hourly", "large", "tm"): "Mean temperature during the last 24 hours",
        ("hourly", "large", "tn"): "Minimum temperature - within the last 12 hours",
        ("hourly", "large", "ttt"): "Temperature 2m above surface",
        ("hourly", "large", "tx"): "Maximum temperature - within the last 12 hours",
        ("hourly", "large", "vv"): "Visibility",
        ("hourly", "large", "vv10"): "Probability: Visibility below 1000m",
        ("hourly", "large", "w1w2"): "Past weather during the last 6 hours",
        ("hourly", "large", "wpc11"): "Optional significant weather (highest priority) during the last hour",
        ("hourly", "large", "wpc31"): "Optional significant weather (highest priority) during the last 3 hours",
        ("hourly", "large", "wpc61"): "Optional significant weather (highest priority) during the last 6 hours",
        ("hourly", "large", "wpcd1"): "Optional significant weather (highest priority) during the last 24 hours",
        ("hourly", "large", "wpch1"): "Optional significant weather (highest priority) during the last 12 hours",
        ("hourly", "large", "ww"): "Significant Weather",
        ("hourly", "large", "ww3"): "Significant Weather",
        ("hourly", "large", "wwc"): "Probability: Occurrence of convective precipitation within the last hour",
        ("hourly", "large", "wwc6"): "Probability: Occurrence of convective precipitation within the last 6 hours",
        ("hourly", "large", "wwch"): "Probability: Occurrence of convective precipitation within the last 12 hours",
        ("hourly", "large", "wwd"): "Probability: Occurrence of stratiform precipitation within the last hour",
        ("hourly", "large", "wwd6"): "Probability: Occurrence of stratiform precipitation within the last 6 hours",
        ("hourly", "large", "wwdh"): "Probability: Occurrence of stratiform precipitation within the last 12 hours",
        ("hourly", "large", "wwf"): "Probability: Occurrence of freezing rain within the last hour",
        ("hourly", "large", "wwf6"): "Probability: Occurrence of freezing rain within the last 6 hours",
        ("hourly", "large", "wwfh"): "Probability: Occurrence of freezing rain within the last 12 hours",
        ("hourly", "large", "wwl"): "Probability: Occurrence of liquid precipitation within the last hour",
        ("hourly", "large", "wwl6"): "Probability: Occurrence of liquid precipitation within the last 6 hours",
        ("hourly", "large", "wwlh"): "Probability: Occurrence of liquid precipitation within the last 12 hours",
        ("hourly", "large", "wwm"): "Probability for fog within the last hour",
        ("hourly", "large", "wwm6"): "Probability for fog within the last 6 hours",
        ("hourly", "large", "wwmd"): "Probability for fog within the last 24 hours",
        ("hourly", "large", "wwmh"): "Probability for fog within the last 12 hours",
        ("hourly", "large", "wwp"): "Probability: Occurrence of precipitation within the last hour",
        ("hourly", "large", "wwp6"): "Probability: Occurrence of precipitation within the last 6 hours",
        ("hourly", "large", "wwph"): "Probability: Occurrence of precipitation within the last 12 hours",
        ("hourly", "large", "wws"): "Probability: Occurrence of solid precipitation within the last hour",
        ("hourly", "large", "wws6"): "Probability: Occurrence of solid precipitation within the last 6 hours",
        ("hourly", "large", "wwsh"): "Probability: Occurrence of solid precipitation within the last 12 hours",
        ("hourly", "large", "wwt"): "Probability: Occurrence of thunderstorms within the last hour",
        ("hourly", "large", "wwt6"): "Probability: Occurrence of thunderstorms within the last 6 hours",
        ("hourly", "large", "wwtd"): "Probability: Occurrence of thunderstorms within the last 24 hours",
        ("hourly", "large", "wwth"): "Probability: Occurrence of thunderstorms within the last 12 hours",
        ("hourly", "large", "wwz"): "Probability: Occurrence of drizzle within the last hour",
        ("hourly", "large", "wwz6"): "Probability: Occurrence of drizzle within the last 6 hours",
        ("hourly", "large", "wwzh"): "Probability: Occurrence of drizzle within the last 12 hours",
        ("hourly", "small", "dd"): "Wind direction",
        ("hourly", "small", "ff"): "Wind speed",
        ("hourly", "small", "fx1"): "Maximum wind gust within the last hour",
        ("hourly", "small", "fx3"): "Maximum wind gust within the last 3 hours",
        ("hourly", "small", "fxh"): "Maximum wind gust within the last 12 hours",
        ("hourly", "small", "fxh25"): "Probability of wind gusts >= 25kn within the last 12 hours",
        ("hourly", "small", "fxh40"): "Probability of wind gusts >= 40kn within the last 12 hours",
        ("hourly", "small", "fxh55"): "Probability of wind gusts >= 55kn within the last 12 hours",
        ("hourly", "small", "n"): "Total cloud cover",
        ("hourly", "small", "n05"): "Cloud cover below 500 ft.",
        ("hourly", "small", "neff"): "Effective cloud cover",
        ("hourly", "small", "nh"): "High cloud cover (>7 km)",
        ("hourly", "small", "nm"): "Midlevel cloud cover (2-7 km)",
        ("hourly", "small", "pppp"): "Surface pressure, reduced",
        ("hourly", "small", "r602"): "Probability of precipitation > 0.2mm during the last 6 hours",
        ("hourly", "small", "r650"): "Probability of precipitation > 5.0mm during the last 6 hours",
        ("hourly", "small", "rad1h"): "Global Irradiance",
        ("hourly", "small", "rd02"): "Probability of precipitation > 0.2mm during the last 24 hours",
        ("hourly", "small", "rd50"): "Probability of precipitation > 5.0mm during the last 24 hours",
        ("hourly", "small", "rh00"): "Probability of precipitation > 0.0mm during the last 12 hours",
        ("hourly", "small", "rh02"): "Probability of precipitation > 0.2mm during the last 12 hours",
        ("hourly", "small", "rh10"): "Probability of precipitation > 1.0mm during the last 12 hours",
        ("hourly", "small", "rh50"): "Probability of precipitation > 5.0mm during the last 12 hours",
        ("hourly", "small", "rr1c"): "Total precipitation during the last hour consistent with significant weather",
        ("hourly", "small", "rr3c"): "Total precipitation during the last 3 hours consistent with significant weather",
        ("hourly", "small", "rrs1c"): "Snow-Rain-Equivalent during the last hour",
        ("hourly", "small", "rrs3c"): "Snow-Rain-Equivalent during the last 3 hours",
        ("hourly", "small", "sund1"): "Sunshine duration during the last Hour",
        ("hourly", "small", "t5cm"): "Temperature 5cm above surface",
        ("hourly", "small", "td"): "Dewpoint 2m above surface",
        ("hourly", "small", "tn"): "Minimum temperature - within the last 12 hours",
        ("hourly", "small", "ttt"): "Temperature 2m above surface",
        ("hourly", "small", "tx"): "Maximum temperature - within the last 12 hours",
        ("hourly", "small", "vv"): "Visibility",
        ("hourly", "small", "w1w2"): "Past weather during the last 6 hours",
        ("hourly", "small", "ww"): "Significant Weather",
        ("hourly", "small", "wwm"): "Probability for fog within the last hour",
        ("hourly", "small", "wwm6"): "Probability for fog within the last 6 hours",
        ("hourly", "small", "wwmh"): "Probability for fog within the last 12 hours",
    },
    "DwdObservationMetadata": {
        ("hourly", "urban_pressure", "luftdruck_nn"): "Air pressure reduced to sea level.",
        ("10_minutes", "precipitation", "rws_10"): "Sum of the precipitation height of the previous 10 minutes.",
        ("10_minutes", "precipitation", "rws_dau_10"): "Duration of precipitation during the previous 10 minutes.",
        ("10_minutes", "precipitation", "rws_ind_10"): (
            "Indicator of precipitation; if QN = 1 then: 0 = no precipitation, permanent sensor "
            "installed; 1 = precipitation, permanent sensor installed; 2 = no precipitation, heating "
            "in operation, permanent sensor installed; 3 = precipitation, heating in operation, "
            "permanent sensor installed; if QN > 1 then: 0 = no precipitation; 1 = precipitation."
        ),
        ("10_minutes", "solar", "ds_10"): "Sum of diffuse sky radiation during the previous 10 minutes.",
        ("10_minutes", "solar", "gs_10"): "Sum of global radiation during the previous 10 minutes.",
        ("10_minutes", "solar", "ls_10"): "Sum of longwave radiation during the previous 10 minutes.",
        ("10_minutes", "solar", "sd_10"): "Sum of sunshine duration during the previous 10 minutes.",
        ("10_minutes", "temperature_air", "pp_10"): "Air pressure at station altitude.",
        ("10_minutes", "temperature_air", "rf_10"): "Relative humidity 2 m above ground.",
        ("10_minutes", "temperature_air", "td_10"): (
            "Dew point. The dew point temperature is calculated from the air temperature 2 m above "
            "ground and the relative humidity measurement."
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
        ("10_minutes", "urban_precipitation", "rr_st_10"): "Precipitation height of the last 10 minutes.",
        ("10_minutes", "urban_pressure", "p0_st_10"): "Pressure at station height.",
        ("10_minutes", "urban_pressure", "pp_st_10"): "Pressure reduced to sea level.",
        ("10_minutes", "urban_solar", "fg_st_10"): "10min-sum of global (incoming) radiation.",
        ("10_minutes", "urban_solar", "sd_st_10"): "10min-sum of sunshine duration.",
        ("10_minutes", "urban_temperature_air", "rf_st_10"): "Relative humidity at 2m height.",
        ("10_minutes", "urban_temperature_air", "strahl_st_10"): "Radiant temperature at 2m height.",
        ("10_minutes", "urban_temperature_air", "tt5_st_10"): "Air temperature at 5cm height.",
        ("10_minutes", "urban_temperature_air", "tt_st_10"): "Air temperature at 2m height.",
        ("10_minutes", "urban_temperature_extreme", "tn5_st_10"): "Minimum air temperature at 5cm height.",
        ("10_minutes", "urban_temperature_extreme", "tn_st_10"): "Minimum air temperature at 2m height.",
        ("10_minutes", "urban_temperature_extreme", "tx_st_10"): "Maximum air temperature at 2m height.",
        ("10_minutes", "urban_temperature_soil", "te_st_01m_10"): "Soil temperature in 10 cm depth.",
        ("10_minutes", "urban_temperature_soil", "te_st_02m_10"): "Soil temperature in 20 cm depth.",
        ("10_minutes", "urban_temperature_soil", "te_st_05m_10"): "Soil temperature in 50 cm depth.",
        ("10_minutes", "urban_temperature_soil", "te_st_10m_10"): "Soil temperature in 100 cm depth.",
        ("10_minutes", "urban_wind", "dd_st_10"): "Mean wind direction during the last 10 minutes.",
        ("10_minutes", "urban_wind", "ff_st_10"): "Mean wind speed during the last 10 minutes.",
        ("10_minutes", "urban_wind_extreme", "fx_st_10"): "Maximum wind gust of the last 10 minutes.",
        ("10_minutes", "wind", "dd_10"): "Mean wind direction during the previous 10 minutes.",
        ("10_minutes", "wind", "ff_10"): "Mean wind speed during the previous 10 minutes.",
        ("10_minutes", "wind_extreme", "dx_10"): (
            "Wind direction of the maximum wind speed during the previous 10 minutes."
        ),
        ("10_minutes", "wind_extreme", "fmx_10"): (
            "Maximum of the wind speed from the 1 minute mean values of the 3-second maxima of the previous 10 minutes."
        ),
        ("10_minutes", "wind_extreme", "fnx_10"): (
            "Minimum 10-minute mean wind speed. The 10-minute interval is moved in 10 s steps over "
            "the previous 20 minutes."
        ),
        ("10_minutes", "wind_extreme", "fx_10"): (
            "Maximum wind gust during the previous 10 minutes. The instrument samples the "
            "instantaneous wind speed every 0.25 seconds and writes out the maximum of each 3 second "
            "period; the highest occurring within the interval is reported."
        ),
        ("1_minute", "precipitation", "rs_01"): "Sum of the precipitation height.",
        ("1_minute", "precipitation", "rs_ind_01"): (
            "Indicator of precipitation; the codes are those of the 10 minutes dataset."
        ),
        ("1_minute", "precipitation", "rth_01"): (
            "Precipitation height during the previous minute from the tipping bucket rain gauge."
        ),
        ("1_minute", "precipitation", "rwh_01"): (
            "Precipitation height during the previous minute from the electronic rain gauge with tilting scales."
        ),
        ("5_minutes", "precipitation", "rs_05"): "Sum of the precipitation height of the previous 5 minutes.",
        ("5_minutes", "precipitation", "rs_ind_05"): (
            "Indicator of precipitation; if QN = 1 then: 0 = no precipitation, permanent sensor "
            "installed; 1 = precipitation, permanent sensor installed; 2 = no precipitation, heating "
            "in operation, permanent sensor installed; 3 = precipitation, heating in operation, "
            "permanent sensor installed; if QN > 1 then: 0 = no precipitation; 1 = precipitation."
        ),
        ("5_minutes", "precipitation", "rth_05"): "Precipitation height of last 5min measured with droplet.",
        ("5_minutes", "precipitation", "rwh_05"): "Precipitation height of last 5min measured with rocker.",
        ("annual", "climate_indices", "ja_eistage"): "Annual number of ice days.",
        ("annual", "climate_indices", "ja_frosttage"): "Annual number of frost days.",
        ("annual", "climate_indices", "ja_heisse_tage"): "Annual number of hot days.",
        ("annual", "climate_indices", "ja_sommertage"): "Annual number of summer days.",
        (
            "annual",
            "climate_indices",
            "ja_tropennaechte",
        ): "Annual number of tropical nights, counted over the day from 00 to 23 hours.",
        ("annual", "climate_summary", "ja_fk"): "Annual mean of daily wind speed.",
        ("annual", "climate_summary", "ja_mx_fx"): "Annual maximum of daily wind speed.",
        ("annual", "climate_summary", "ja_mx_rs"): "Annual max of daily precipitation height.",
        ("annual", "climate_summary", "ja_mx_tn"): "Annual minimum of daily temperature minima in 2m height.",
        ("annual", "climate_summary", "ja_mx_tx"): "Annual maximum of daily temperature maxima in 2m height.",
        ("annual", "climate_summary", "ja_n"): "Annual mean of cloud cover.",
        ("annual", "climate_summary", "ja_rr"): "Annual sum of daily precipitation height.",
        ("annual", "climate_summary", "ja_sd_s"): "Annual sum of sunshine duration.",
        ("annual", "climate_summary", "ja_tn"): "Annual mean of daily temperature minima in 2m height.",
        ("annual", "climate_summary", "ja_tt"): "Annual mean of daily temperature means in 2m height.",
        ("annual", "climate_summary", "ja_tx"): "Annual mean of daily temperature maxima in 2m height.",
        (
            "annual",
            "precipitation_indices",
            "ja_rr_ge_0_1_mm",
        ): "Annual number of days with a precipitation height of at least 0.1 mm.",
        (
            "annual",
            "precipitation_indices",
            "ja_rr_ge_10_0_mm",
        ): "Annual number of days with a precipitation height of at least 10.0 mm.",
        (
            "annual",
            "precipitation_indices",
            "ja_rr_ge_1_0_mm",
        ): "Annual number of days with a precipitation height of at least 1.0 mm.",
        (
            "annual",
            "precipitation_indices",
            "ja_rr_ge_20_0_mm",
        ): "Annual number of days with a precipitation height of at least 20.0 mm.",
        (
            "annual",
            "precipitation_indices",
            "ja_rr_ge_2_5_mm",
        ): "Annual number of days with a precipitation height of at least 2.5 mm.",
        (
            "annual",
            "precipitation_indices",
            "ja_rr_ge_5_0_mm",
        ): "Annual number of days with a precipitation height of at least 5.0 mm.",
        (
            "annual",
            "precipitation_indices",
            "ja_sh_ge_1_0_cm",
        ): "Annual number of days with a snow depth of at least 1.0 cm.",
        (
            "annual",
            "precipitation_indices",
            "ja_sh_ge_5_0_cm",
        ): "Annual number of days with a snow depth of at least 5.0 cm.",
        ("annual", "precipitation_more", "ja_mx_rs"): "Annual max of daily precipitation height.",
        ("annual", "precipitation_more", "ja_nsh"): "Annual sum of daily fresh snow.",
        ("annual", "precipitation_more", "ja_rr"): "Annual sum of daily precipitation height.",
        ("annual", "precipitation_more", "ja_sh_s"): "Annual sum of daily height of snow pack.",
        ("annual", "weather_phenomena", "ja_gewitter"): "Count of days with thunder of stations in Germany.",
        ("annual", "weather_phenomena", "ja_glatteis"): "Count of days with glaze of stations in Germany.",
        ("annual", "weather_phenomena", "ja_graupel"): "Count of days with sleet of stations in Germany.",
        ("annual", "weather_phenomena", "ja_hagel"): "Count of days with hail of stations in Germany.",
        ("annual", "weather_phenomena", "ja_nebel"): "Count of days with fog of stations in Germany.",
        ("annual", "weather_phenomena", "ja_sturm_6"): "Count of days with storm (strong wind) of stations in Germany.",
        ("annual", "weather_phenomena", "ja_sturm_8"): (
            "Count of days with storm (stormier wind) of stations in Germany."
        ),
        ("annual", "weather_phenomena", "ja_tau"): "Count of days with dew of stations in Germany.",
        ("daily", "climate_summary", "fm"): "Daily mean of wind velocity.",
        ("daily", "climate_summary", "fx"): "Daily maximum of windgust.",
        ("daily", "climate_summary", "nm"): "Daily mean of cloud cover.",
        ("daily", "climate_summary", "pm"): "Daily mean of pressure.",
        ("daily", "climate_summary", "qn_3"): "Quality level of the following columns.",
        ("daily", "climate_summary", "qn_4"): "Quality level of the following columns.",
        ("daily", "climate_summary", "rsk"): "Daily precipitation height.",
        ("daily", "climate_summary", "rskf"): "Precipitation form.",
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
        ("daily", "precipitation_more", "rsf"): "Precipitation form.",
        ("daily", "precipitation_more", "sh_tag"): "Height of snow pack.",
        ("daily", "solar", "atmo_strahl"): "Longwave downward radiation.",
        ("daily", "solar", "fd_strahl"): "Daily sum of diffuse solar radiation.",
        ("daily", "solar", "fg_strahl"): "Daily sum of solar incoming radiation.",
        ("daily", "solar", "sd_strahl"): "Daily sum of sunshine duration.",
        ("daily", "temperature_soil", "v_te002m"): "Daily soil temperature in 2 cm depth.",
        ("daily", "temperature_soil", "v_te005m"): "Daily soil temperature in 5 cm depth.",
        ("daily", "temperature_soil", "v_te010m"): "Daily soil temperature in 10 cm depth.",
        ("daily", "temperature_soil", "v_te020m"): "Daily soil temperature in 20 cm depth.",
        ("daily", "temperature_soil", "v_te050m"): "Daily soil temperature in 50 cm depth.",
        ("daily", "temperature_soil", "v_te100m"): "Daily soil temperature in 100 cm depth.",
        ("daily", "water_equivalent", "ash_6"): "Height of the sampled snow pack.",
        ("daily", "water_equivalent", "sh_tag"): "Height of the snow pack.",
        ("daily", "water_equivalent", "waas_6"): "Water equivalent of the sampled snow pack.",
        ("daily", "water_equivalent", "wash_6"): "Water equivalent of the total snow pack.",
        ("daily", "weather_phenomena", "gewitter"): "Count of days with thunder of stations in Germany.",
        ("daily", "weather_phenomena", "glatteis"): "Count of days with glaze of stations in Germany.",
        ("daily", "weather_phenomena", "graupel"): "Count of days with sleet of stations in Germany.",
        ("daily", "weather_phenomena", "hagel"): "Count of days with hail of stations in Germany.",
        ("daily", "weather_phenomena", "nebel"): "Count of days with fog of stations in Germany.",
        ("daily", "weather_phenomena", "reif"): "Count of days with ripe of stations in Germany.",
        ("daily", "weather_phenomena", "sturm_6"): "Count of days with storm (strong wind) of stations in Germany.",
        ("daily", "weather_phenomena", "sturm_8"): "Count of days with storm (stormier wind) of stations in Germany.",
        ("daily", "weather_phenomena", "tau"): "Count of days with dew of stations in Germany.",
        ("daily", "weather_phenomena_more", "rr_gewitter"): "Count of days with thunder of stations in Germany.",
        ("daily", "weather_phenomena_more", "rr_graupel"): "Count of days with sleet of stations in Germany.",
        ("daily", "weather_phenomena_more", "rr_hagel"): "Count of days with hail of stations in Germany.",
        ("daily", "weather_phenomena_more", "rr_nebel"): "Count of days with fog of stations in Germany.",
        ("hourly", "cloud_type", "v_n"): "Total cloud cover.",
        ("hourly", "cloud_type", "v_n_i"): (
            "Index how measurement is taken, P = by human person,I = by instrument. Returned as 1 for P and 2 for I."
        ),
        ("hourly", "cloud_type", "v_s1_cs"): "Cloud type of 1. layer.",
        ("hourly", "cloud_type", "v_s1_hhs"): "Lower boundary height of 1.layer.",
        ("hourly", "cloud_type", "v_s1_ns"): "Cloud cover in the first layer.",
        ("hourly", "cloud_type", "v_s2_cs"): "Cloud type of 2. layer.",
        ("hourly", "cloud_type", "v_s2_hhs"): "Lower boundary height of 2.layer.",
        ("hourly", "cloud_type", "v_s2_ns"): "Cloud cover in the second layer.",
        ("hourly", "cloud_type", "v_s3_cs"): "Cloud type of 3. layer.",
        ("hourly", "cloud_type", "v_s3_hhs"): "Lower boundary height of 3.layer.",
        ("hourly", "cloud_type", "v_s3_ns"): "Cloud cover in the third layer.",
        ("hourly", "cloud_type", "v_s4_cs"): "Cloud type of 4. layer.",
        ("hourly", "cloud_type", "v_s4_hhs"): "Lower boundary height of 4.layer.",
        ("hourly", "cloud_type", "v_s4_ns"): "Cloud cover in the fourth layer.",
        ("hourly", "cloudiness", "v_n"): "Total cloud cover.",
        ("hourly", "cloudiness", "v_n_i"): (
            "Index how measurement is taken, P = by human person,I = by instrument. Returned as 1 for P and 2 for I."
        ),
        ("hourly", "dew_point", "td"): "Dew point temperature.",
        ("hourly", "dew_point", "tt"): "Air temperature.",
        ("hourly", "moisture", "absf_std"): "Computed hourly value of absolute humidity.",
        ("hourly", "moisture", "p_std"): "Hourly value of barometric pressure.",
        ("hourly", "moisture", "rf_std"): "Relative humidity.",
        ("hourly", "moisture", "td_std"): "Dew point temperature in 2m above ground.",
        ("hourly", "moisture", "tf_std"): "Computed hourly value of wet bulb temperature.",
        ("hourly", "moisture", "tt_std"): "Air temperatur in 2m above ground.",
        ("hourly", "moisture", "vp_std"): "Computed hourly value of vapour pressure.",
        ("hourly", "precipitation", "r1"): "Precipitation height during the previous hour.",
        ("hourly", "precipitation", "rs_ind"): "Precipitation indicator; 0 = no; 1 = yes.",
        ("hourly", "precipitation", "wrtr"): "Precipitation form; 0=No precipitation.",
        ("hourly", "pressure", "p"): "Mean sea level pressure.",
        ("hourly", "pressure", "p0"): "Barometric pressure at station height.",
        ("hourly", "solar", "atmo_lberg"): "Hourly sum of longwave downward radiation.",
        ("hourly", "solar", "fd_lberg"): "Hourly sum of diffuse solar radiation.",
        ("hourly", "solar", "mess_datum_woz"): (
            "Local true solar time, published as a whole timestamp and returned as its distance from "
            "the timestamp of the record: the longitude correction plus the equation of time."
        ),
        ("hourly", "solar", "fg_lberg"): (
            "The solar incoming radiation includes the direct and the diffuse part of the solar "
            "radiation with respect to the horizontal plane. It is sometimes also referred to as "
            "shortwave, including the solar spectrum up to 2.8 micron, as opposed to longwave , which "
            "refers to the thermal radiation of the atmosphere."
        ),
        ("hourly", "solar", "sd_lberg"): "Hourly sum of sunshine duration.",
        ("hourly", "solar", "zenit"): (
            "Solar zenith angle at mid of interval. The solar zenith angle is between 0-180 and is "
            "defined as: ZENIT= 90 - solar_height."
        ),
        ("hourly", "sun", "sd_so"): "Hourly sunshine duration.",
        ("hourly", "temperature_air", "rf_tu"): "Relative humidity.",
        ("hourly", "temperature_air", "tt_tu"): "Air temperature 2 m above ground.",
        ("hourly", "temperature_soil", "v_te002"): "Soil temperature in 2 cm depth.",
        ("hourly", "temperature_soil", "v_te005"): "Soil temperature in 5 cm depth.",
        ("hourly", "temperature_soil", "v_te010"): "Soil temperature in 10 cm depth.",
        ("hourly", "temperature_soil", "v_te020"): "Soil temperature in 20 cm depth.",
        ("hourly", "temperature_soil", "v_te050"): "Soil temperature in 50 cm depth.",
        ("hourly", "temperature_soil", "v_te100"): "Soil temperature in 100 cm depth.",
        ("hourly", "urban_precipitation", "niederschlagshoehe"): "Precipitation height.",
        ("hourly", "urban_pressure", "luftdruck_stationshoehe"): "Pressure at station height.",
        ("hourly", "urban_sun", "sonnenscheindauer"): "Sunshine duration.",
        ("hourly", "urban_temperature_air", "lufttemperatur"): "2m air temperature.",
        ("hourly", "urban_temperature_air", "rel_feuchte"): "2m relative humidity.",
        ("hourly", "urban_temperature_soil", "erdbt_005"): "Soil temperature in 5 cm depth.",
        ("hourly", "urban_temperature_soil", "erdbt_010"): "Soil temperature in 10 cm depth.",
        ("hourly", "urban_temperature_soil", "erdbt_020"): "Soil temperature in 20 cm depth.",
        ("hourly", "urban_temperature_soil", "erdbt_050"): "Soil temperature in 50 cm depth.",
        ("hourly", "urban_temperature_soil", "erdbt_100"): "Soil temperature in 100 cm depth.",
        ("hourly", "urban_wind", "windgeschwindigkeit"): "Mean wind speed.",
        ("hourly", "urban_wind", "windrichtung"): "Mean wind direction.",
        ("hourly", "visibility", "v_vv"): "Visibility range.",
        ("hourly", "visibility", "v_vv_i"): (
            "Visibility index, noting how the measurement is taken,P=by human person,I=by an instrument. "
            "Returned as 1 for P and 2 for I."
        ),
        ("hourly", "weather_phenomena", "ww"): "Weather code of current condition.",
        ("hourly", "wind", "d"): "Mean wind direction.",
        ("hourly", "wind", "f"): "Mean wind speed.",
        ("hourly", "wind_extreme", "fx_911"): "Maximum wind gust 10 m above ground.",
        ("hourly", "wind_synoptic", "dd"): "Mean wind direction.",
        ("hourly", "wind_synoptic", "ff"): "Mean wind speed.",
        ("monthly", "climate_indices", "mo_eistage"): "Monthly number of ice days.",
        ("monthly", "climate_indices", "mo_frosttage"): "Monthly number of frost days.",
        ("monthly", "climate_indices", "mo_heisse_tage"): "Monthly number of hot days.",
        ("monthly", "climate_indices", "mo_sommertage"): "Monthly number of summer days.",
        (
            "monthly",
            "climate_indices",
            "mo_tropennaechte",
        ): "Monthly number of tropical nights, counted over the day from 00 to 23 hours.",
        ("monthly", "climate_summary", "mo_fk"): "Monthly mean of daily wind speed Bft.",
        ("monthly", "climate_summary", "mo_n"): "Monthly mean of cloud cover.",
        ("monthly", "climate_summary", "mo_rr"): "Monthly sum of precipitation height.",
        ("monthly", "climate_summary", "mo_sd_s"): "Monthly sum of sunshine duration.",
        ("monthly", "climate_summary", "mo_tn"): "Monthly mean of daily temperature minima in 2 m above ground.",
        ("monthly", "climate_summary", "mo_tt"): "Monthly mean of the daily mean air temperature 2 m above ground.",
        ("monthly", "climate_summary", "mo_tx"): "Monthly mean of daily temperature maxima at 2 m above ground.",
        ("monthly", "climate_summary", "mx_fx"): "Monthly maximum of daily wind speed.",
        ("monthly", "climate_summary", "mx_rs"): "Monthly maximum of daily precipitation height.",
        ("monthly", "climate_summary", "mx_tn"): "Monthly minimum of daily temperature minima in 2 m above ground.",
        ("monthly", "climate_summary", "mx_tx"): "Monthly maximum of daily temperature maxima in 2 m above ground.",
        ("monthly", "climate_summary", "qn_4"): "Quality level of the data in the following columns.",
        ("monthly", "climate_summary", "qn_6"): "Quality level of the data in the following columns.",
        (
            "monthly",
            "precipitation_indices",
            "mo_rr_ge_0_1_mm",
        ): "Monthly number of days with a precipitation height of at least 0.1 mm.",
        (
            "monthly",
            "precipitation_indices",
            "mo_rr_ge_10_0_mm",
        ): "Monthly number of days with a precipitation height of at least 10.0 mm.",
        (
            "monthly",
            "precipitation_indices",
            "mo_rr_ge_1_0_mm",
        ): "Monthly number of days with a precipitation height of at least 1.0 mm.",
        (
            "monthly",
            "precipitation_indices",
            "mo_rr_ge_20_0_mm",
        ): "Monthly number of days with a precipitation height of at least 20.0 mm.",
        (
            "monthly",
            "precipitation_indices",
            "mo_rr_ge_2_5_mm",
        ): "Monthly number of days with a precipitation height of at least 2.5 mm.",
        (
            "monthly",
            "precipitation_indices",
            "mo_rr_ge_5_0_mm",
        ): "Monthly number of days with a precipitation height of at least 5.0 mm.",
        (
            "monthly",
            "precipitation_indices",
            "mo_sh_ge_1_0_cm",
        ): "Monthly number of days with a snow depth of at least 1.0 cm.",
        (
            "monthly",
            "precipitation_indices",
            "mo_sh_ge_5_0_cm",
        ): "Monthly number of days with a snow depth of at least 5.0 cm.",
        ("monthly", "precipitation_more", "mo_nsh"): "Monthly sum of daily fresh snow.",
        ("monthly", "precipitation_more", "mo_rr"): "Monthly sum of precipitation height.",
        ("monthly", "precipitation_more", "mo_sh_s"): "Monthly sum of daily height of snow pack.",
        ("monthly", "precipitation_more", "mx_rs"): "Monthly maximum of daily precipitation height.",
        ("monthly", "weather_phenomena", "mo_gewitter"): "Count of days with thunder of stations in Germany.",
        ("monthly", "weather_phenomena", "mo_glatteis"): "Count of days with glaze of stations in Germany.",
        ("monthly", "weather_phenomena", "mo_graupel"): "Count of days with sleet of stations in Germany.",
        ("monthly", "weather_phenomena", "mo_hagel"): "Count of days with hail of stations in Germany.",
        ("monthly", "weather_phenomena", "mo_nebel"): "Count of days with fog of stations in Germany.",
        (
            "monthly",
            "weather_phenomena",
            "mo_sturm_6",
        ): "Count of days with storm (strong wind) of stations in Germany.",
        ("monthly", "weather_phenomena", "mo_sturm_8"): (
            "Count of days with storm (stormier wind) of stations in Germany."
        ),
        ("monthly", "weather_phenomena", "mo_tau"): "Count of days with dew of stations in Germany.",
        ("subdaily", "cloudiness", "cd_ter"): "Cloud density.",
        ("subdaily", "cloudiness", "n_ter"): "Total cloud cover.",
        ("subdaily", "moisture", "e_tf_ter"): "Ice on the wet bulb thermometer.",
        ("subdaily", "moisture", "rf_ter"): "2m relative humidity.",
        ("subdaily", "moisture", "tf_ter"): "2m wet bulb temperature.",
        ("subdaily", "moisture", "vp_ter"): "Vapor pressure.",
        ("subdaily", "pressure", "pp_ter"): "Air pressure of site.",
        ("subdaily", "soil", "ek_ter"): "Coded ground state.",
        ("subdaily", "temperature_air", "rf_ter"): "2m relative humidity.",
        ("subdaily", "temperature_air", "tt_ter"): "2m air temperature.",
        ("subdaily", "visibility", "vk_ter"): "Coded visibility class.",
        ("subdaily", "wind", "dk_ter"): "Wind direction.",
        ("subdaily", "wind", "fk_ter"): "Wind force (beaufort).",
        ("subdaily", "wind_extreme", "fx_911_3"): "Wind gust max 3h.",
        ("subdaily", "wind_extreme", "fx_911_6"): "Wind gust max 6h.",
    },
    "DwdRoadMetadata": {
        ("15_minutes", "data", "airTemperature"): "mean air temperature in 2m",
        ("15_minutes", "data", "dewpointTemperature"): "mean dew point temperature in 2m",
        ("15_minutes", "data", "horizontalVisibility"): "visibility range",
        ("15_minutes", "data", "intensityOfPrecipitation"): "precipitation intensity",
        ("15_minutes", "data", "maximumWindGustDirection"): "direction of maximum wind gust",
        ("15_minutes", "data", "maximumWindGustSpeed"): "maximum wind gust",
        ("15_minutes", "data", "precipitationType"): "form of precipitation",
        ("15_minutes", "data", "relativeHumidity"): "mean humidity",
        ("15_minutes", "data", "roadSurfaceCondition"): "road surface condition",
        ("15_minutes", "data", "roadSurfaceTemperature"): "road surface temperature",
        ("15_minutes", "data", "totalPrecipitationOrTotalWaterEquivalent"): "precipitation height",
        ("15_minutes", "data", "waterFilmThickness"): "thickness of water film",
        ("15_minutes", "data", "windDirection"): "mean direction of wind",
        ("15_minutes", "data", "windSpeed"): "mean wind speed",
    },
    "EAHydrologyMetadata": {
        ("15_minutes", "data", "flow-i-900"): "instant flow at timestamp",
        ("15_minutes", "data", "level-i-900"): "instant groundwater level at timestamp",
        ("daily", "data", "flow-m-86400"): "daily mean flow",
        ("daily", "data", "flow-max-86400"): "daily maximum flow",
        ("daily", "data", "flow-min-86400"): "daily min flow",
        ("daily", "data", "level-max-86400"): "daily maximum groundwater level",
        ("daily", "data", "level-min-86400"): "daily minimum groundwater level",
    },
    "EcccObservationMetadata": {
        ("daily", "data", "max_temperature"): "Daily maximum 2m air temperature.",
        ("daily", "data", "mean_temperature"): "Daily mean 2m air temperature.",
        ("daily", "data", "min_temperature"): "Daily minimum 2m air temperature.",
        ("daily", "data", "snow_on_ground"): "Total snow depth.",
        ("daily", "data", "speed_max_gust"): "Maximum wind gust.",
        ("daily", "data", "total_precipitation"): "Total precipitation.",
        ("daily", "data", "total_rain"): "Total liquid precipitation.",
        ("daily", "data", "total_snow"): "New snow depth.",
        ("daily", "data", "cooling_degree_days"): "cooling degree days",
        ("daily", "data", "direction_max_gust"): "wind direction of maximum wind gust",
        ("daily", "data", "heating_degree_days"): "heating degree days",
        ("hourly", "data", "dew_point_temp"): "2m dew point temperature",
        ("hourly", "data", "humidex"): "humidex apparent temperature",
        ("hourly", "data", "precip_amount"): "precipitation height",
        ("hourly", "data", "relative_humidity"): "humidity",
        ("hourly", "data", "station_pressure"): "air pressure at site",
        ("hourly", "data", "temp"): "2m air temperature",
        ("hourly", "data", "visibility"): "visibility range",
        ("hourly", "data", "wind_direction"): "wind direction (source: 10s deg)",
        ("hourly", "data", "wind_speed"): "wind speed",
        ("hourly", "data", "windchill"): "wind chill temperature",
        ("monthly", "data", "bright_sunshine"): "bright sunshine duration",
        ("monthly", "data", "cooling_degree_days"): "cooling degree days",
        ("monthly", "data", "days_with_precip_ge_1mm"): "days with >= 1 mm precipitation",
        ("monthly", "data", "days_with_valid_max_temp"): "days with a valid maximum temperature",
        ("monthly", "data", "days_with_valid_mean_temp"): "days with a valid mean temperature",
        ("monthly", "data", "days_with_valid_min_temp"): "days with a valid minimum temperature",
        ("monthly", "data", "days_with_valid_precip"): "days with a valid precipitation observation",
        ("monthly", "data", "days_with_valid_snowfall"): "days with a valid snowfall observation",
        ("monthly", "data", "days_with_valid_sunshine"): "days with a valid sunshine observation",
        ("monthly", "data", "heating_degree_days"): "heating degree days",
        ("monthly", "data", "max_temperature"): "2m maximum air temperature",
        ("monthly", "data", "mean_temperature"): "2m mean air temperature",
        ("monthly", "data", "min_temperature"): "2m minimum air temperature",
        ("monthly", "data", "normal_mean_temperature"): "normal of the mean air temperature",
        ("monthly", "data", "normal_precipitation"): "normal of the precipitation height",
        ("monthly", "data", "normal_snowfall"): "normal of the snowfall total",
        ("monthly", "data", "normal_sunshine"): "normal of the sunshine duration",
        ("monthly", "data", "snow_on_ground_last_day"): "snow depth on the last day",
        ("monthly", "data", "total_precipitation"): "precipitation height",
        ("monthly", "data", "total_snowfall"): "snowfall total",
    },
    "GeosphereObservationMetadata": {
        ("10_minutes", "data", "cglo"): "global radiation",
        ("10_minutes", "data", "chim"): "sky short wave diffuse radiation",
        ("10_minutes", "data", "dd"): "wind direction",
        ("10_minutes", "data", "ddx"): "wind direction gust max",
        ("10_minutes", "data", "ff"): "wind speed",
        ("10_minutes", "data", "ffam"): "arithmetic mean of wind speed",
        ("10_minutes", "data", "ffx"): "wind gust max",
        ("10_minutes", "data", "p"): "air pressure at site",
        ("10_minutes", "data", "pred"): "air pressure at sea level",
        ("10_minutes", "data", "rf"): "relative humidity",
        ("10_minutes", "data", "rr"): "precipitation height",
        ("10_minutes", "data", "rrm"): "precipitation duration",
        ("10_minutes", "data", "sh"): "snow depth",
        ("10_minutes", "data", "so"): "sunshine duration",
        ("10_minutes", "data", "tb10"): "soil temperature mean at 0.1m",
        ("10_minutes", "data", "tb20"): "soil temperature mean at 0.2m",
        ("10_minutes", "data", "tb50"): "soil temperature mean at 0.5m",
        ("10_minutes", "data", "tl"): "air temperature mean at 2m",
        ("10_minutes", "data", "tlmax"): "air temperature max at 2m",
        ("10_minutes", "data", "tlmin"): "air temperature min at 2m",
        ("10_minutes", "data", "ts"): "air temperature mean at 0.05m",
        ("10_minutes", "data", "tsmax"): "air temperature max at 0.05m",
        ("10_minutes", "data", "tsmin"): "air temperature min at 0.05m",
        ("daily", "data", "bewm_mittel"): "total cloud cover",
        ("daily", "data", "cglo_j"): "global radiation",
        ("daily", "data", "dampf_mittel"): "vapor pressure",
        ("daily", "data", "ffx"): "wind gust max",
        ("daily", "data", "p_mittel"): "air pressure at site",
        ("daily", "data", "rf_mittel"): "relative humidity",
        ("daily", "data", "rr"): "precipitation height",
        ("daily", "data", "sh"): "snow depth",
        ("daily", "data", "sh_manu"): "manually measured snow depth",
        ("daily", "data", "shneu_manu"): "new snow depth",
        ("daily", "data", "so_h"): "sunshine duration",
        ("daily", "data", "tl_mittel"): "air temperature mean at 2m",
        ("daily", "data", "tlmax"): "air temperature max at 2m",
        ("daily", "data", "tlmin"): "air temperature min at 2m",
        ("daily", "data", "tsmin"): "air temperature min at 0.05m",
        ("daily", "data", "vv_mittel"): "wind speed",
        ("hourly", "data", "cglo"): "global radiation",
        ("hourly", "data", "dd"): "wind direction",
        ("hourly", "data", "ddx"): "wind direction gust max",
        ("hourly", "data", "ff"): "wind speed",
        ("hourly", "data", "ffx"): "wind gust max",
        ("hourly", "data", "p"): "air pressure at site",
        ("hourly", "data", "pred"): "air pressure at sea level",
        ("hourly", "data", "rf"): "relative humidity",
        ("hourly", "data", "rr"): "precipitation height",
        ("hourly", "data", "rrm"): "precipitation duration",
        ("hourly", "data", "sh"): "snow depth",
        ("hourly", "data", "so_h"): "sunshine duration",
        ("hourly", "data", "tb10"): "soil temperature mean at 0.1m",
        ("hourly", "data", "tb100"): "soil temperature mean at 1m",
        ("hourly", "data", "tb20"): "soil temperature mean at 0.2m",
        ("hourly", "data", "tb200"): "soil temperature mean at 2m",
        ("hourly", "data", "tb50"): "soil temperature mean at 0.5m",
        ("hourly", "data", "tl"): "air temperature mean at 2m",
        ("hourly", "data", "tsmin"): "air temperature min at 0.05m",
        ("monthly", "data", "bet0"): "concrete temperature mean at 0m",
        ("monthly", "data", "bet0_max"): "concrete temperature max at 0m",
        ("monthly", "data", "bet0_min"): "concrete temperature min at 0m",
        ("monthly", "data", "bewm_mittel"): "cloud cover total",
        ("monthly", "data", "cglo_j"): "global radiation",
        ("monthly", "data", "dampf_mittel"): "vapor pressure",
        ("monthly", "data", "p"): "air pressure at site",
        ("monthly", "data", "pmax"): "air pressure at site max",
        ("monthly", "data", "pmin"): "air pressure at site min",
        ("monthly", "data", "rf_mittel"): "relative humidity",
        ("monthly", "data", "rr"): "precipitation height",
        ("monthly", "data", "rr_max"): "precipitation height max",
        ("monthly", "data", "sh_manu_max"): "snow depth max",
        ("monthly", "data", "shneu_manu"): "snow depth new",
        ("monthly", "data", "shneu_manu_max"): "snow depth new max",
        ("monthly", "data", "so_h"): "sunshine duration",
        ("monthly", "data", "so_r"): "sunshine duration relative",
        ("monthly", "data", "tb100_max"): "soil temperature max at 1m",
        ("monthly", "data", "tb100_min"): "soil temperature min at 1m",
        ("monthly", "data", "tb100_mittel"): "soil temperature mean at 1m",
        ("monthly", "data", "tb10_max"): "soil temperature max at 0.1m",
        ("monthly", "data", "tb10_min"): "soil temperature min at 0.1m",
        ("monthly", "data", "tb10_mittel"): "soil temperature mean at 0.1m",
        ("monthly", "data", "tb200_max"): "soil temperature max at 2m",
        ("monthly", "data", "tb200_min"): "soil temperature min at 2m",
        ("monthly", "data", "tb200_mittel"): "soil temperature mean at 2m",
        ("monthly", "data", "tb20_max"): "soil temperature max at 0.2m",
        ("monthly", "data", "tb20_min"): "soil temperature min at 0.2m",
        ("monthly", "data", "tb20_mittel"): "soil temperature mean at 0.2m",
        ("monthly", "data", "tb50_max"): "soil temperature max at 0.5m",
        ("monthly", "data", "tb50_min"): "soil temperature min at 0.5m",
        ("monthly", "data", "tb50_mittel"): "soil temperature mean at 0.5m",
        ("monthly", "data", "tl_mittel"): "air temperature mean at 2m",
        ("monthly", "data", "tlmax"): "air temperature max at 2m",
        ("monthly", "data", "tlmin"): "air temperature min at 2m",
        ("monthly", "data", "vv_mittel"): "wind speed",
    },
    "ImgwHydrologyMetadata": {
        ("daily", "hydrology", "przepływ"): "discharge",
        ("daily", "hydrology", "stan wody"): "stage",
        ("daily", "hydrology", "temperatura wody"): "temperature water",
        ("monthly", "hydrology", "maksymalna przepływ"): "discharge max",
        ("monthly", "hydrology", "maksymalna stan wody"): "stage max",
        ("monthly", "hydrology", "maksymalna temperatura wody"): "temperature water max",
        ("monthly", "hydrology", "minimalna przepływ"): "discharge min",
        ("monthly", "hydrology", "minimalna stan wody"): "stage min",
        ("monthly", "hydrology", "minimalna temperatura wody"): "temperature water min",
        ("monthly", "hydrology", "średnia przepływ"): "discharge mean",
        ("monthly", "hydrology", "średnia stan wody"): "stage mean",
        ("monthly", "hydrology", "średnia temperatura wody"): "temperature water mean",
    },
    "ImgwMeteorologyMetadata": {
        ("daily", "climate", "średnia dobowa wilgotność względna"): "Humidity.",
        ("daily", "climate", "średnie dobowe zachmurzenie ogólne"): "Cloud cover total.",
        ("daily", "synop", "średnia dobowa wilgotność względna"): "Humidity.",
        ("daily", "synop", "średnia dobowe ciśnienie na poziomie stacji"): "Pressure air site.",
        ("daily", "synop", "średnia dobowe ciśnienie pary wodnej"): "Pressure vapor.",
        ("daily", "synop", "średnie dobowe zachmurzenie ogólne"): "Cloud cover total.",
        ("monthly", "climate", "średnia miesięczna wilgotność względna"): "Humidity.",
        ("monthly", "climate", "średnie miesięczne zachmurzenie ogólne"): "Cloud cover total.",
        ("monthly", "synop", "średnia miesięczna wilgotność względna"): "Humidity.",
        ("monthly", "synop", "średnie miesięczne zachmurzenie ogólne"): "Cloud cover total.",
        ("daily", "climate", "maksymalna temperatura dobowa"): "temperature air max 2m",
        ("daily", "climate", "minimalna temperatura dobowa"): "temperature air min 2m",
        ("daily", "climate", "suma dobowa opadów"): "precipitation height",
        ("daily", "climate", "temperatura minimalna przy gruncie"): "temperature air mean 0 05m",
        ("daily", "climate", "wysokość pokrywy śnieżnej"): "snow depth",
        ("daily", "climate", "średnia dobowa prędkość wiatru"): "wind speed",
        ("daily", "climate", "średnia dobowa temperatura"): "temperature air mean",
        ("daily", "precipitation", "suma dobowa opadów"): "precipitation height",
        ("daily", "precipitation", "wysokość pokrywy śnieżnej"): "snow depth",
        ("daily", "precipitation", "wysokość świeżospałego śniegu"): "snow depth new",
        ("daily", "synop", "średnia dobowa prędkość wiatru"): "wind speed",
        ("daily", "synop", "średnia dobowa temperatura"): "temperature air mean",
        ("monthly", "climate", "absolutna temperatura maksymalna"): "temperature air max 2m",
        ("monthly", "climate", "absolutna temperatura minimalna"): "temperature air min 2m",
        ("monthly", "climate", "maksymalna wysokość pokrywy śnieżnej"): "snow depth max",
        ("monthly", "climate", "miesieczna suma opadów"): "precipitation height",
        ("monthly", "climate", "minimalna temperatura przy gruncie"): "temperature air min 0 05m",
        ("monthly", "climate", "opad maksymalny"): "precipitation height max",
        ("monthly", "climate", "średnia miesięczna prędkość wiatru"): "wind speed",
        ("monthly", "climate", "średnia miesięczna temperatura"): "temperature air mean 2m",
        ("monthly", "climate", "średnia temperatura maksymalna"): "temperature air max 2m mean",
        ("monthly", "climate", "średnia temperatura minimalna"): "temperature air min 2m mean",
        ("monthly", "precipitation", "miesięczna suma opadów"): "precipitation height",
        ("monthly", "precipitation", "opad maksymalny"): "precipitation height max",
        ("monthly", "synop", "absolutna temperatura maksymalna"): "temperature air max 2m",
        ("monthly", "synop", "absolutna temperatura minimalna"): "temperature air min 2m",
        ("monthly", "synop", "maksymalna wysokość pokrywy śnieżnej"): "snow depth max",
        ("monthly", "synop", "miesięczna suma opadów"): "precipitation height",
        ("monthly", "synop", "minimalna temperatura przy gruncie"): "temperature air min 0 05m",
        ("monthly", "synop", "średnia miesięczna prędkość wiatru"): "wind speed",
        ("monthly", "synop", "średnia miesięczna temperatura"): "temperature air mean 2m",
        ("monthly", "synop", "średnia temperatura maksymalna"): "temperature air max 2m mean",
        ("monthly", "synop", "średnia temperatura minimalna"): "temperature air min 2m mean",
        ("monthly", "synop", "średnie miesięczne ciśnienie na pozimie morza"): "pressure air sea level",
        ("monthly", "synop", "średnie miesięczne ciśnienie na poziomie stacji"): "pressure air site",
        ("monthly", "synop", "średnie miesięczne ciśnienie pary wodnej"): "pressure vapor",
    },
    "NoaaGhcnMetadata": {
        ("daily", "data", "tavg"): (
            "Mean temperature calculated from tmean = (temperature_air_max_2m + temperature_air_min_2m) / 2."
        ),
        ("daily", "data", "wdfm"): "Fastest mile wind direction (degrees).",
        ("daily", "data", "acmc"): "Average cloudiness midnight to midnight from 30-second ceilometer data (percent)",
        ("daily", "data", "acmh"): "Average cloudiness midnight to midnight from manual observation (percent)",
        ("daily", "data", "acsc"): "Average cloudiness sunrise to sunset from 30-second ceilometer data (percent)",
        ("daily", "data", "acsh"): "Average cloudiness sunrise to sunset from manual observation (percent)",
        ("daily", "data", "awnd"): (
            "Average daily wind speed (meters per second or miles per hour as per user preference)"
        ),
        ("daily", "data", "daev"): "Number of days included in the multiday evaporation total (MDEV)",
        ("daily", "data", "dapr"): "Number of days included in the multiday precipitation total (MDPR)",
        ("daily", "data", "dasf"): "Number of days included in the multiday snowfall total (MDSF)",
        ("daily", "data", "datn"): "Number of days included in the multiday minimum temperature (MDTN)",
        ("daily", "data", "datx"): "Number of days included in the multiday maximum temperature (MDTX)",
        ("daily", "data", "dawm"): "Number of days included in the multiday wind movement (MDWM)",
        ("daily", "data", "dwpr"): (
            "Number of days with non-zero precipitation included in multiday precipitation total (MDPR)"
        ),
        ("daily", "data", "evap"): (
            "Evaporation of water from evaporation pan (mm or inches as per user preference, or "
            "hundredths of inches on Daily Form pdf file)"
        ),
        ("daily", "data", "frgb"): "Base of frozen ground layer (cm or inches as per user preference)",
        ("daily", "data", "frgt"): "Top of frozen ground layer (cm or inches as per user preference)",
        ("daily", "data", "frth"): "Thickness of frozen ground layer (cm or inches as per user preference)",
        ("daily", "data", "gaht"): "Difference between river and gauge height (cm or inches as per user preference)",
        ("daily", "data", "mdev"): "Multiday evaporation total (mm or inches as per user preference; use with DAEV)",
        ("daily", "data", "mdpr"): (
            "Multiday precipitation total (mm or inches as per user preference; use with DAPR and DWPR, if available)"
        ),
        ("daily", "data", "mdsf"): "Multiday snowfall total (mm or inches as per user preference)",
        ("daily", "data", "mdtn"): (
            "Multiday minimum temperature (Fahrenheit or Celsius as per user preference ; use with DATN)"
        ),
        ("daily", "data", "mdtx"): (
            "Multiday maximum temperature (Fahrenheit or Celsius as per user preference ; use with DATX)"
        ),
        ("daily", "data", "mdwm"): "Multiday wind movement (miles or km as per user preference)",
        ("daily", "data", "mnpn"): (
            "Daily minimum temperature of water in an evaporation pan (Fahrenheit or Celsius as per user preference)"
        ),
        ("daily", "data", "mxpn"): (
            "Daily maximum temperature of water in an evaporation pan  (Fahrenheit or Celsius as per user preference)"
        ),
        ("daily", "data", "prcp"): (
            "Precipitation (mm or inches as per user preference, inches to hundredths on Daily Form pdf file)"
        ),
        ("daily", "data", "psun"): "Daily percent of possible sunshine (percent)",
        ("daily", "data", "sn01"): "Minimum soil temperature of unknown ground at 5cm depth",
        ("daily", "data", "sn02"): "Minimum soil temperature of unknown ground at 10cm depth",
        ("daily", "data", "sn03"): "Minimum soil temperature of unknown ground at 20cm depth",
        ("daily", "data", "sn04"): "Minimum soil temperature of unknown ground at 50cm depth",
        ("daily", "data", "sn05"): "Minimum soil temperature of unknown ground at 100cm depth",
        ("daily", "data", "sn06"): "Minimum soil temperature of unknown ground at 150cm depth",
        ("daily", "data", "sn07"): "Minimum soil temperature of unknown ground at 180cm depth",
        ("daily", "data", "sn11"): "Minimum soil temperature of grass ground at 5cm depth",
        ("daily", "data", "sn12"): "Minimum soil temperature of grass ground at 10cm depth",
        ("daily", "data", "sn13"): "Minimum soil temperature of grass ground at 20cm depth",
        ("daily", "data", "sn14"): "Minimum soil temperature of grass ground at 50cm depth",
        ("daily", "data", "sn15"): "Minimum soil temperature of grass ground at 100cm depth",
        ("daily", "data", "sn16"): "Minimum soil temperature of grass ground at 150cm depth",
        ("daily", "data", "sn17"): "Minimum soil temperature of grass ground at 180cm depth",
        ("daily", "data", "sn21"): "Minimum soil temperature of fallow ground at 5cm depth",
        ("daily", "data", "sn22"): "Minimum soil temperature of fallow ground at 10cm depth",
        ("daily", "data", "sn23"): "Minimum soil temperature of fallow ground at 20cm depth",
        ("daily", "data", "sn24"): "Minimum soil temperature of fallow ground at 50cm depth",
        ("daily", "data", "sn25"): "Minimum soil temperature of fallow ground at 100cm depth",
        ("daily", "data", "sn26"): "Minimum soil temperature of fallow ground at 150cm depth",
        ("daily", "data", "sn27"): "Minimum soil temperature of fallow ground at 180cm depth",
        ("daily", "data", "sn31"): "Minimum soil temperature of bare_ground ground at 5cm depth",
        ("daily", "data", "sn32"): "Minimum soil temperature of bare_ground ground at 10cm depth",
        ("daily", "data", "sn33"): "Minimum soil temperature of bare_ground ground at 20cm depth",
        ("daily", "data", "sn34"): "Minimum soil temperature of bare_ground ground at 50cm depth",
        ("daily", "data", "sn35"): "Minimum soil temperature of bare_ground ground at 100cm depth",
        ("daily", "data", "sn36"): "Minimum soil temperature of bare_ground ground at 150cm depth",
        ("daily", "data", "sn37"): "Minimum soil temperature of bare_ground ground at 180cm depth",
        ("daily", "data", "sn41"): "Minimum soil temperature of brome_grass ground at 5cm depth",
        ("daily", "data", "sn42"): "Minimum soil temperature of brome_grass ground at 10cm depth",
        ("daily", "data", "sn43"): "Minimum soil temperature of brome_grass ground at 20cm depth",
        ("daily", "data", "sn44"): "Minimum soil temperature of brome_grass ground at 50cm depth",
        ("daily", "data", "sn45"): "Minimum soil temperature of brome_grass ground at 100cm depth",
        ("daily", "data", "sn46"): "Minimum soil temperature of brome_grass ground at 150cm depth",
        ("daily", "data", "sn47"): "Minimum soil temperature of brome_grass ground at 180cm depth",
        ("daily", "data", "sn51"): "Minimum soil temperature of sod ground at 5cm depth",
        ("daily", "data", "sn52"): "Minimum soil temperature of sod ground at 10cm depth",
        ("daily", "data", "sn53"): "Minimum soil temperature of sod ground at 20cm depth",
        ("daily", "data", "sn54"): "Minimum soil temperature of sod ground at 50cm depth",
        ("daily", "data", "sn55"): "Minimum soil temperature of sod ground at 100cm depth",
        ("daily", "data", "sn56"): "Minimum soil temperature of sod ground at 150cm depth",
        ("daily", "data", "sn57"): "Minimum soil temperature of sod ground at 180cm depth",
        ("daily", "data", "sn61"): "Minimum soil temperature of straw_mulch ground at 5cm depth",
        ("daily", "data", "sn62"): "Minimum soil temperature of straw_mulch ground at 10cm depth",
        ("daily", "data", "sn63"): "Minimum soil temperature of straw_mulch ground at 20cm depth",
        ("daily", "data", "sn64"): "Minimum soil temperature of straw_mulch ground at 50cm depth",
        ("daily", "data", "sn65"): "Minimum soil temperature of straw_mulch ground at 100cm depth",
        ("daily", "data", "sn66"): "Minimum soil temperature of straw_mulch ground at 150cm depth",
        ("daily", "data", "sn67"): "Minimum soil temperature of straw_mulch ground at 180cm depth",
        ("daily", "data", "sn71"): "Minimum soil temperature of grass_muck ground at 5cm depth",
        ("daily", "data", "sn72"): "Minimum soil temperature of grass_muck ground at 10cm depth",
        ("daily", "data", "sn73"): "Minimum soil temperature of grass_muck ground at 20cm depth",
        ("daily", "data", "sn74"): "Minimum soil temperature of grass_muck ground at 50cm depth",
        ("daily", "data", "sn75"): "Minimum soil temperature of grass_muck ground at 100cm depth",
        ("daily", "data", "sn76"): "Minimum soil temperature of grass_muck ground at 150cm depth",
        ("daily", "data", "sn77"): "Minimum soil temperature of grass_muck ground at 180cm depth",
        ("daily", "data", "sn81"): "Minimum soil temperature of bare_muck ground at 5cm depth",
        ("daily", "data", "sn82"): "Minimum soil temperature of bare_muck ground at 10cm depth",
        ("daily", "data", "sn83"): "Minimum soil temperature of bare_muck ground at 20cm depth",
        ("daily", "data", "sn84"): "Minimum soil temperature of bare_muck ground at 50cm depth",
        ("daily", "data", "sn85"): "Minimum soil temperature of bare_muck ground at 100cm depth",
        ("daily", "data", "sn86"): "Minimum soil temperature of bare_muck ground at 150cm depth",
        ("daily", "data", "sn87"): "Minimum soil temperature of bare_muck ground at 180cm depth",
        ("daily", "data", "snow"): (
            "Snowfall (mm or inches as per user preference, inches to tenths on Daily Form pdf file)"
        ),
        ("daily", "data", "snwd"): "Snow depth (mm or inches as per user preference, inches on Daily Form pdf file)",
        ("daily", "data", "sx01"): "Maximum soil temperature of unknown ground at 5cm depth",
        ("daily", "data", "sx02"): "Maximum soil temperature of unknown ground at 10cm depth",
        ("daily", "data", "sx03"): "Maximum soil temperature of unknown ground at 20cm depth",
        ("daily", "data", "sx04"): "Maximum soil temperature of unknown ground at 50cm depth",
        ("daily", "data", "sx05"): "Maximum soil temperature of unknown ground at 100cm depth",
        ("daily", "data", "sx06"): "Maximum soil temperature of unknown ground at 150cm depth",
        ("daily", "data", "sx07"): "Maximum soil temperature of unknown ground at 180cm depth",
        ("daily", "data", "sx11"): "Maximum soil temperature of grass ground at 5cm depth",
        ("daily", "data", "sx12"): "Maximum soil temperature of grass ground at 10cm depth",
        ("daily", "data", "sx13"): "Maximum soil temperature of grass ground at 20cm depth",
        ("daily", "data", "sx14"): "Maximum soil temperature of grass ground at 50cm depth",
        ("daily", "data", "sx15"): "Maximum soil temperature of grass ground at 100cm depth",
        ("daily", "data", "sx16"): "Maximum soil temperature of grass ground at 150cm depth",
        ("daily", "data", "sx17"): "Maximum soil temperature of grass ground at 180cm depth",
        ("daily", "data", "sx21"): "Maximum soil temperature of fallow ground at 5cm depth",
        ("daily", "data", "sx22"): "Maximum soil temperature of fallow ground at 10cm depth",
        ("daily", "data", "sx23"): "Maximum soil temperature of fallow ground at 20cm depth",
        ("daily", "data", "sx24"): "Maximum soil temperature of fallow ground at 50cm depth",
        ("daily", "data", "sx25"): "Maximum soil temperature of fallow ground at 100cm depth",
        ("daily", "data", "sx26"): "Maximum soil temperature of fallow ground at 150cm depth",
        ("daily", "data", "sx27"): "Maximum soil temperature of fallow ground at 180cm depth",
        ("daily", "data", "sx31"): "Maximum soil temperature of bare_ground ground at 5cm depth",
        ("daily", "data", "sx32"): "Maximum soil temperature of bare_ground ground at 10cm depth",
        ("daily", "data", "sx33"): "Maximum soil temperature of bare_ground ground at 20cm depth",
        ("daily", "data", "sx34"): "Maximum soil temperature of bare_ground ground at 50cm depth",
        ("daily", "data", "sx35"): "Maximum soil temperature of bare_ground ground at 100cm depth",
        ("daily", "data", "sx36"): "Maximum soil temperature of bare_ground ground at 150cm depth",
        ("daily", "data", "sx37"): "Maximum soil temperature of bare_ground ground at 180cm depth",
        ("daily", "data", "sx41"): "Maximum soil temperature of brome_grass ground at 5cm depth",
        ("daily", "data", "sx42"): "Maximum soil temperature of brome_grass ground at 10cm depth",
        ("daily", "data", "sx43"): "Maximum soil temperature of brome_grass ground at 20cm depth",
        ("daily", "data", "sx44"): "Maximum soil temperature of brome_grass ground at 50cm depth",
        ("daily", "data", "sx45"): "Maximum soil temperature of brome_grass ground at 100cm depth",
        ("daily", "data", "sx46"): "Maximum soil temperature of brome_grass ground at 150cm depth",
        ("daily", "data", "sx47"): "Maximum soil temperature of brome_grass ground at 180cm depth",
        ("daily", "data", "sx51"): "Maximum soil temperature of sod ground at 5cm depth",
        ("daily", "data", "sx52"): "Maximum soil temperature of sod ground at 10cm depth",
        ("daily", "data", "sx53"): "Maximum soil temperature of sod ground at 20cm depth",
        ("daily", "data", "sx54"): "Maximum soil temperature of sod ground at 50cm depth",
        ("daily", "data", "sx55"): "Maximum soil temperature of sod ground at 100cm depth",
        ("daily", "data", "sx56"): "Maximum soil temperature of sod ground at 150cm depth",
        ("daily", "data", "sx57"): "Maximum soil temperature of sod ground at 180cm depth",
        ("daily", "data", "sx61"): "Maximum soil temperature of straw_mulch ground at 5cm depth",
        ("daily", "data", "sx62"): "Maximum soil temperature of straw_mulch ground at 10cm depth",
        ("daily", "data", "sx63"): "Maximum soil temperature of straw_mulch ground at 20cm depth",
        ("daily", "data", "sx64"): "Maximum soil temperature of straw_mulch ground at 50cm depth",
        ("daily", "data", "sx65"): "Maximum soil temperature of straw_mulch ground at 100cm depth",
        ("daily", "data", "sx66"): "Maximum soil temperature of straw_mulch ground at 150cm depth",
        ("daily", "data", "sx67"): "Maximum soil temperature of straw_mulch ground at 180cm depth",
        ("daily", "data", "sx71"): "Maximum soil temperature of grass_muck ground at 5cm depth",
        ("daily", "data", "sx72"): "Maximum soil temperature of grass_muck ground at 10cm depth",
        ("daily", "data", "sx73"): "Maximum soil temperature of grass_muck ground at 20cm depth",
        ("daily", "data", "sx74"): "Maximum soil temperature of grass_muck ground at 50cm depth",
        ("daily", "data", "sx75"): "Maximum soil temperature of grass_muck ground at 100cm depth",
        ("daily", "data", "sx76"): "Maximum soil temperature of grass_muck ground at 150cm depth",
        ("daily", "data", "sx77"): "Maximum soil temperature of grass_muck ground at 180cm depth",
        ("daily", "data", "sx81"): "Maximum soil temperature of bare_muck ground at 5cm depth",
        ("daily", "data", "sx82"): "Maximum soil temperature of bare_muck ground at 10cm depth",
        ("daily", "data", "sx83"): "Maximum soil temperature of bare_muck ground at 20cm depth",
        ("daily", "data", "sx84"): "Maximum soil temperature of bare_muck ground at 50cm depth",
        ("daily", "data", "sx85"): "Maximum soil temperature of bare_muck ground at 100cm depth",
        ("daily", "data", "sx86"): "Maximum soil temperature of bare_muck ground at 150cm depth",
        ("daily", "data", "sx87"): "Maximum soil temperature of bare_muck ground at 180cm depth",
        ("daily", "data", "thic"): "Thickness of ice on water (inches or mm as per user preference)",
        ("daily", "data", "tmax"): (
            "Maximum  temperature  (Fahrenheit  or  Celsius  as per  user  preference, Fahrenheit  to "
            "tenths on Daily Form pdf file"
        ),
        ("daily", "data", "tmin"): (
            "Minimum  temperature  (Fahrenheit  or  Celsius  as per  user  preference, Fahrenheit  to "
            "tenths  on Daily Form pdf file"
        ),
        ("daily", "data", "tobs"): (
            "Temperature at the time of observation  (Fahrenheit or Celsius as per user preference)"
        ),
        ("daily", "data", "tsun"): "Daily total sunshine (minutes)",
        ("daily", "data", "wdf1"): "Direction of fastest 1-minute wind (degrees)",
        ("daily", "data", "wdf2"): "Direction of fastest 2-minute wind (degrees)",
        ("daily", "data", "wdf5"): "Direction of fastest 5-second wind (degrees)",
        ("daily", "data", "wdfg"): "Direction of peak wind gust (degrees)",
        ("daily", "data", "wdfi"): "Direction of highest instantaneous wind (degrees)",
        ("daily", "data", "wdmv"): (
            "24-hour wind movement (km or miles as per user preference, miles on Daily Form pdf file)"
        ),
        ("daily", "data", "wesd"): "Water equivalent of snow on the ground (inches or mm as per user preference)",
        ("daily", "data", "wesf"): "Water equivalent of snowfall (inches or mm as per user preference)",
        ("daily", "data", "wsf1"): (
            "Fastest 1-minute wind speed (miles per hour or  meters per second as per user preference)"
        ),
        ("daily", "data", "wsf2"): (
            "Fastest 2-minute wind speed (miles per hour or  meters per second as per user preference)"
        ),
        ("daily", "data", "wsf5"): (
            "Fastest 5-second wind speed (miles per hour or  meters per second as per user preference)"
        ),
        ("daily", "data", "wsfg"): (
            "Peak guest wind speed (miles per hour or  meters per second as per user preference)"
        ),
        ("daily", "data", "wsfi"): (
            "Highest instantaneous wind speed (miles per hour or  meters per second as per user preference)"
        ),
        ("daily", "data", "wsfm"): (
            "Fastest mile wind speed (miles per hour or  meters per second as per user preference)"
        ),
        ("daily", "data", "wt01"): "Fog, ice fog, or freezing fog (may include heavy fog)",
        ("daily", "data", "wt02"): "Heavy fog or heaving freezing fog (not always distinguished from fog)",
        ("daily", "data", "wt03"): "Thunder",
        ("daily", "data", "wt04"): "Ice pellets, sleet, snow pellets, or small hail",
        ("daily", "data", "wt05"): "Hail (may include small hail)",
        ("daily", "data", "wt06"): "Glaze or rime",
        ("daily", "data", "wt07"): "Dust, volcanic ash, blowing dust, blowing sand, or blowing obstruction",
        ("daily", "data", "wt08"): "Smoke or haze",
        ("daily", "data", "wt09"): "Blowing or drifting snow",
        ("daily", "data", "wt10"): "Tornado, waterspout, or funnel cloud",
        ("daily", "data", "wt11"): "High or damaging winds",
        ("daily", "data", "wt12"): "Blowing spray",
        ("daily", "data", "wt13"): "Mist",
        ("daily", "data", "wt14"): "Drizzle",
        ("daily", "data", "wt15"): "Freezing drizzle",
        ("daily", "data", "wt16"): "Rain (may include freezing rain, drizzle, and freezing drizzle)",
        ("daily", "data", "wt17"): "Freezing rain",
        ("daily", "data", "wt18"): "Snow, snow pellets, snow grains, or ice crystals",
        ("daily", "data", "wt19"): "Unknown source of precipitation",
        ("daily", "data", "wt21"): "Ground fog",
        ("daily", "data", "wt22"): "Ice fog or freezing fog",
        ("daily", "data", "wv01"): "Fog, ice fog, or freezing fog (may include heavy fog) in the Vicinity",
        ("daily", "data", "wv03"): "Thunder in the Vicinity",
        ("daily", "data", "wv07"): "Ash, dust, sand, or other blowing obstruction in the Vicinity",
        ("daily", "data", "wv18"): "Snow or ice crystals in the Vicinity",
        ("daily", "data", "wv20"): "Rain or snow shower in the Vicinity",
        ("hourly", "data", "altimeter"): "Reduced pressure (hectopascals)",
        ("hourly", "data", "dew_point_temperature"): "Dew Point Temperature (⁰C to tenths)",
        ("hourly", "data", "precipitation"): (
            "total liquid precipitation (rain or melted snow) for past hour; a “T” in the measurement "
            "code column indicates a trace amount of precipitation (millimeters)"
        ),
        ("hourly", "data", "precipitation_12_hour"): (
            "12-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP "
            "reports; a “T” in the measurement code column indicates a trace amount of precipitation "
            "(millimeters)"
        ),
        ("hourly", "data", "precipitation_15_hour"): (
            "15-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP "
            "reports; a “T” in the measurement code column indicates a trace amount of precipitation "
            "(millimeters)"
        ),
        ("hourly", "data", "precipitation_18_hour"): (
            "18-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP "
            "reports; a “T” in the measurement code column indicates a trace amount of precipitation "
            "(millimeters)"
        ),
        ("hourly", "data", "precipitation_21_hour"): (
            "21-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP "
            "reports; a “T” in the measurement code column indicates a trace amount of precipitation "
            "(millimeters)"
        ),
        ("hourly", "data", "precipitation_24_hour"): (
            "24-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP "
            "reports; a “T” in the measurement code column indicates a trace amount of precipitation "
            "(millimeters)"
        ),
        ("hourly", "data", "precipitation_3_hour"): (
            "3-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP "
            "reports; a “T” in the measurement code column indicates a trace amount of precipitation "
            "(millimeters)"
        ),
        ("hourly", "data", "precipitation_6_hour"): (
            "6-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP "
            "reports; a “T” in the measurement code column indicates a trace amount of precipitation "
            "(millimeters)"
        ),
        ("hourly", "data", "precipitation_9_hour"): (
            "9-hour total liquid precipitation (rain or melted snow) accumulation from FM12/SYNOP "
            "reports; a “T” in the measurement code column indicates a trace amount of precipitation "
            "(millimeters)"
        ),
        ("hourly", "data", "pressure_3hr_change"): "3-hour pressure change (hectopascals)",
        ("hourly", "data", "relative_humidity"): (
            "Relative humidity is calculated from air (dry bulb) temperature and dewpoint temperature (whole percent)"
        ),
        ("hourly", "data", "sea_level_pressure"): "Sea level pressure (hectopascals)",
        ("hourly", "data", "snow_depth"): "depth of snowpack on the ground (centimeters/m)",
        ("hourly", "data", "station_level_pressure"): "Station pressure (hectopascals)",
        ("hourly", "data", "temperature"): (
            "2 meter (circa) Above Ground Level Air (dry bulb) Temperature (⁰C to tenths)"
        ),
        ("hourly", "data", "visibility"): (
            "horizontal distance at which an object can be seen and identified (kilometers)"
        ),
        ("hourly", "data", "wet_bulb_temperature"): "Wet bulb temperature (⁰C to tenths)",
        ("hourly", "data", "wind_direction"): (
            "Wind direction from true north using compass directions (e.g. 360=true north, 180=south, "
            "270=west, etc.). Note: A direction of “000” is given for calm winds. (whole degrees)"
        ),
        ("hourly", "data", "wind_gust"): (
            "Peak short duration (usually < 20 seconds) wind speed (meters per second) that exceeds "
            "the wind_speed average"
        ),
        ("hourly", "data", "wind_speed"): "Wind speed (meters per second)",
    },
    "NwsObservationMetadata": {
        ("hourly", "data", "barometricpressure"): "air pressure at station height",
        ("hourly", "data", "dewpoint"): "Average dew point temperature in 2m",
        ("hourly", "data", "maxtemperaturelast24hours"): "maximum air temperature in the last 24 hours",
        ("hourly", "data", "mintemperaturelast24hours"): "minimum air temperature in the last 24 hours",
        ("hourly", "data", "precipitationlast3hours"): "precipitation height of last three hours",
        ("hourly", "data", "precipitationlast6hours"): "precipitation height of last six hours",
        ("hourly", "data", "precipitationlasthour"): "precipitation height of last hour",
        ("hourly", "data", "relativehumidity"): "relative humidity",
        ("hourly", "data", "sealevelpressure"): "air pressure at sea level",
        ("hourly", "data", "temperature"): "Average air temperature in 2m",
        ("hourly", "data", "visibility"): "visibility range",
        ("hourly", "data", "windchill"): (
            "wind chill temperature calculated by NWS (https://www.weather.gov/gjt/windchill)"
        ),
        ("hourly", "data", "winddirection"): "wind direction",
        ("hourly", "data", "windgust"): "maximum wind gust",
        ("hourly", "data", "windspeed"): "wind speed",
    },
    "WsvPegelMetadata": {
        (resolution, "data", name_original): description
        for resolution in _WSV_PEGEL_RESOLUTIONS
        for name_original, description in _WSV_PEGEL_PARAMETERS.items()
    },
    "AemetObservationMetadata": {
        ("annual", "data", "p_max"): "Greatest daily precipitation of the year, and its date.",
        ("annual", "data", "p_mes"): "Total annual precipitation.",
        ("annual", "data", "ta_max"): "Absolute maximum temperature of the year, and its date.",
        ("annual", "data", "ta_min"): "Absolute minimum temperature of the year, and its date.",
        ("annual", "data", "tm_max"): "Annual mean of the maximum temperatures.",
        ("annual", "data", "tm_mes"): "Annual mean temperature.",
        ("annual", "data", "tm_min"): "Annual mean of the minimum temperatures.",
        ("daily", "data", "dir"): "Direction of the maximum gust.",
        ("daily", "data", "hrmax"): "Daily maximum relative humidity.",
        ("daily", "data", "hrmedia"): "Daily mean relative humidity.",
        ("daily", "data", "hrmin"): "Daily minimum relative humidity.",
        ("daily", "data", "prec"): "Daily precipitation, from 07 to 07.",
        ("daily", "data", "presmax"): "Maximum pressure at the station's reference level.",
        ("daily", "data", "presmin"): "Minimum pressure at the station's reference level.",
        ("daily", "data", "racha"): "Maximum wind gust.",
        ("daily", "data", "tmax"): "Maximum temperature of the day.",
        ("daily", "data", "tmed"): "Daily mean temperature.",
        ("daily", "data", "tmin"): "Minimum temperature of the day.",
        ("daily", "data", "velmedia"): "Mean wind speed.",
        ("hourly", "data", "dmax"): (
            "Direction of the maximum wind recorded in the 60 minutes preceding the time given by 'fint' (degrees)."
        ),
        ("hourly", "data", "dv"): (
            "Mean wind direction over the 10 minutes preceding the time given by 'fint' (degrees)."
        ),
        ("hourly", "data", "hr"): "Instantaneous relative humidity of the air at the time given by 'fint' (%).",
        ("hourly", "data", "prec"): (
            "Accumulated precipitation measured by the rain gauge during the 60 minutes preceding the observation "
            "time 'fint' (mm, equivalent to l/m2)."
        ),
        ("hourly", "data", "pres"): (
            "Instantaneous pressure at the level where the barometer is installed, at the time given by 'fint' (hPa)."
        ),
        ("hourly", "data", "pres_nmar"): (
            "Pressure reduced to sea level, for stations at an altitude of 750 metres or less, at the time given by "
            "'fint' (hPa)."
        ),
        ("hourly", "data", "ta"): "Instantaneous air temperature at the time given by 'fint' (degrees Celsius).",
        ("hourly", "data", "tamax"): (
            "Maximum air temperature, the highest of the 60 instantaneous 'ta' values measured in the 60 minutes "
            "preceding the observation time 'fint' (degrees Celsius)."
        ),
        ("hourly", "data", "tamin"): (
            "Minimum air temperature, the lowest of the 60 instantaneous 'ta' values measured in the 60 minutes "
            "preceding the observation time 'fint' (degrees Celsius)."
        ),
        ("hourly", "data", "tpr"): "Calculated dew point temperature at the time given by 'fint' (degrees Celsius).",
        ("hourly", "data", "vmax"): (
            "Maximum wind speed, the highest wind sustained for 3 seconds recorded in the 60 minutes preceding the "
            "observation time 'fint' (m/s)."
        ),
        ("hourly", "data", "vv"): (
            "Mean wind speed, the scalar mean of the samples taken every 0.25 or 1 second over the 10 minutes "
            "preceding 'fint' (m/s)."
        ),
        ("monthly", "data", "hr"): "Monthly mean relative humidity.",
        ("monthly", "data", "p_max"): "Greatest daily precipitation of the month, and its date.",
        ("monthly", "data", "p_mes"): "Total monthly precipitation.",
        ("monthly", "data", "ta_max"): "Absolute maximum temperature of the month, and its date.",
        ("monthly", "data", "ta_min"): "Absolute minimum temperature of the month, and its date.",
        ("monthly", "data", "tm_max"): "Monthly mean of the maximum temperatures.",
        ("monthly", "data", "tm_mes"): "Monthly mean temperature.",
        ("monthly", "data", "tm_min"): "Monthly mean of the minimum temperatures.",
    },
    "FmiObservationMetadata": {
        ("daily", "data", "rrday"): "Precipitation amount. Sum over 24 hours.",
        ("daily", "data", "snow"): "Snow depth. Instantaneous value over 1 day.",
        ("daily", "data", "tday"): "Air temperature. Mean over 1 day.",
        ("daily", "data", "tmax"): "Maximum temperature. Maximum over 24 hours.",
        ("daily", "data", "tmin"): "Minimum temperature. Minimum over 24 hours.",
        ("hourly", "data", "p_sea"): "Pressure (msl). Mean over 1 minute.",
        ("hourly", "data", "r_1h"): "Precipitation amount. Accumulated over 1 hour.",
        ("hourly", "data", "rh"): "Relative humidity. Mean over 1 minute.",
        ("hourly", "data", "snow_aws"): "Snow depth. Instantaneous value over 1 minute.",
        ("hourly", "data", "t2m"): "Air temperature. Mean over 1 minute.",
        ("hourly", "data", "td"): "Dew-point temperature. Mean over 1 minute.",
        ("hourly", "data", "vis"): "Horizontal visibility. Mean over 1 minute.",
        ("hourly", "data", "wd_10min"): "Wind direction. Mean over 10 minutes.",
        ("hourly", "data", "wg_10min"): "Gust speed. Maximum over 10 minutes.",
        ("hourly", "data", "ws_10min"): "Wind speed. Mean over 10 minutes.",
    },
    "KnmiObservationMetadata": {
        ("10_minutes", "data", "dd"): "Wind Direction Mean with MD",
        ("10_minutes", "data", "dr"): "Precipitation Duration (Rain Gauge)",
        ("10_minutes", "data", "ff"): "Wind Speed at 10 m Mean with MD",
        ("10_minutes", "data", "fx"): "Wind Gust at 10 m Maximum last Interval",
        ("10_minutes", "data", "n"): "Total Cloud Cover",
        ("10_minutes", "data", "p0"): "Air Pressure at Station Level 1 Min Mean",
        ("10_minutes", "data", "pp"): "Air Pressure at Mean Sea Level 1 Min Mean",
        ("10_minutes", "data", "qg"): "Global Solar Radiation Mean",
        ("10_minutes", "data", "rg"): "Precipitation Intensity (Rain Gauge) Mean",
        ("10_minutes", "data", "rh"): "Relative Humidity 1 Min Mean",
        ("10_minutes", "data", "ss"): "Sunshine Duration",
        ("10_minutes", "data", "ta"): "Air Temperature 1 Min Mean",
        ("10_minutes", "data", "tb"): "Wet Bulb Temperature Mean",
        ("10_minutes", "data", "td"): "Dew Point Temperature 1 Min Mean",
        ("10_minutes", "data", "tg"): "Air Temperature 10 cm Mean",
        ("10_minutes", "data", "vv"): "Horizontal Visibility Mean",
        ("daily", "data", "DR"): "Precipitation duration",
        ("daily", "data", "EV24"): "Potential evapotranspiration (Makkink)",
        ("daily", "data", "FG"): "Mean wind speed",
        ("daily", "data", "FXX"): "Maximum wind gust",
        ("daily", "data", "NG"): "Mean cloud cover",
        ("daily", "data", "PG"): "Mean sea level pressure",
        ("daily", "data", "Q"): "Global solar radiation",
        ("daily", "data", "RH"): "Precipitation amount",
        ("daily", "data", "SQ"): "Sunshine duration",
        ("daily", "data", "TG"): "Mean temperature",
        ("daily", "data", "TN"): "Minimum temperature",
        ("daily", "data", "TX"): "Maximum temperature",
        ("daily", "data", "UG"): "Mean relative atmospheric humidity",
        ("hourly", "data", "DD"): "Mean wind direction",
        ("hourly", "data", "DR"): "Precipitation duration",
        ("hourly", "data", "FH"): "Mean wind speed",
        ("hourly", "data", "FX"): "Maximum wind gust",
        ("hourly", "data", "N"): "Cloud cover",
        ("hourly", "data", "P"): "Air pressure",
        ("hourly", "data", "Q"): "Global solar radiation",
        ("hourly", "data", "RH"): "Precipitation amount",
        ("hourly", "data", "SQ"): "Sunshine duration",
        ("hourly", "data", "T"): "Temperature",
        ("hourly", "data", "TD"): "Dew point temperature",
        ("hourly", "data", "U"): "Relative atmospheric humidity",
    },
    "LhmtObservationMetadata": {
        ("hourly", "data", "airTemperature"): "Air temperature, °C.",
        ("hourly", "data", "cloudCover"): (
            "Cloud cover, %. Values: 0 is clear, 100 is overcast. Where the cloud cover cannot be "
            "determined, for example because of fog, null is returned."
        ),
        ("hourly", "data", "precipitation"): "Precipitation amount, mm. The precipitation sum over the hour.",
        ("hourly", "data", "relativeHumidity"): "Relative humidity of the air, %.",
        ("hourly", "data", "seaLevelPressure"): "Pressure at sea level, hPa.",
        ("hourly", "data", "snowDepth"): "Thickness of the snow cover, cm.",
        ("hourly", "data", "windDirection"): (
            "Wind direction, °. Values: 0 is from the north, 180 is from the south, and so on."
        ),
        ("hourly", "data", "windGust"): "Wind gust, m/s. The maximum gust over the hour.",
        ("hourly", "data", "windSpeed"): "Wind speed, m/s.",
    },
    "MetOfficeObservationMetadata": {
        ("daily", "rain", "prcp_amt"): "Precipitation amount, reported to the nearest 0.1 mm.",
        ("daily", "temperature", "max_air_temp"): "Maximum air temperature, to the nearest 0.1 deg C.",
        ("daily", "temperature", "min_air_temp"): "Minimum air temperature, to the nearest 0.1 deg C.",
        ("daily", "temperature", "min_grss_temp"): "Minimum grass temperature, to the nearest 0.1 deg C.",
        ("daily", "weather", "drv_24hr_sun_dur"): (
            "Derived 24 hour sunshine duration, for stations carrying radiation sensors only, which use the global "
            "radiation values to derive it."
        ),
        ("daily", "weather", "frsh_snw_amt"): "Fresh snow amount, cm.",
        ("daily", "weather", "snow_depth"): "Snow depth, cm.",
        ("hourly", "radiation", "difu_irad_amt"): (
            "Diffuse solar irradiation amount, kJ per square metre over the observation period."
        ),
        ("hourly", "radiation", "direct_irad"): (
            "Direct irradiation amount, kJ per square metre over the observation period."
        ),
        ("hourly", "radiation", "glbl_irad_amt"): (
            "Global solar irradiation amount, kJ per square metre over the observation period."
        ),
        ("hourly", "rain", "prcp_amt"): "Precipitation amount, reported to the nearest 0.1 mm.",
        ("hourly", "rain", "prcp_dur"): "Precipitation duration over less than 24 hours, minutes.",
        ("hourly", "soil_temperature", "q100cm_soil_temp"): "100 cm soil temperature, to the nearest 0.1 deg C.",
        ("hourly", "soil_temperature", "q10cm_soil_temp"): "10 cm soil temperature, to the nearest 0.1 deg C.",
        ("hourly", "soil_temperature", "q20cm_soil_temp"): "20 cm soil temperature, to the nearest 0.1 deg C.",
        ("hourly", "soil_temperature", "q50cm_soil_temp"): "50 cm soil temperature, to the nearest 0.1 deg C.",
        ("hourly", "soil_temperature", "q5cm_soil_temp"): "5 cm soil temperature, to the nearest 0.1 deg C.",
        ("hourly", "weather", "air_temperature"): "Air temperature, to the nearest 0.1 deg C.",
        ("hourly", "weather", "cld_ttl_amt_id"): "Total cloud amount code.",
        ("hourly", "weather", "dewpoint"): (
            "Dewpoint temperature: the temperature to which the air must be cooled to produce saturation with respect "
            "to water at its existing pressure and humidity."
        ),
        ("hourly", "weather", "msl_pressure"): "Mean sea level air pressure, to the nearest 0.1 hPa.",
        ("hourly", "weather", "prst_wx_id"): "Present weather code.",
        ("hourly", "weather", "q10mnt_mxgst_spd"): "Maximum gust speed over 10 minutes, knots.",
        ("hourly", "weather", "rltv_hum"): "Calculated relative humidity.",
        ("hourly", "weather", "snow_depth"): "Snow depth, cm.",
        ("hourly", "weather", "stn_pres"): (
            "Station air pressure, as measured at station level. No correction for altitude is applied."
        ),
        ("hourly", "weather", "visibility"): "Visibility, decametres.",
        ("hourly", "weather", "wind_direction"): (
            "Wind direction, that from which the wind blows, in degrees true. An east wind is 090, a south wind 180."
        ),
        ("hourly", "weather", "wind_speed"): "Wind speed, knots.",
        ("hourly", "weather", "wmo_hr_sun_dur"): (
            "Readings from the newer automatic sun sensor, which has replaced the Campbell Stokes recorder."
        ),
        ("hourly", "wind", "max_gust_dir"): "Direction of the maximum gust, degrees true.",
        ("hourly", "wind", "max_gust_speed"): "Speed of the maximum gust, knots.",
        ("hourly", "wind", "mean_wind_dir"): (
            "Mean wind direction, that from which the wind blows, in degrees true. An east wind is 090, a south wind "
            "180."
        ),
        ("hourly", "wind", "mean_wind_speed"): "Mean wind speed, knots.",
    },
    "MeteoFranceObservationMetadata": {
        ("6_minutes", "data", "RR"): "Precipitation amount over 6 minutes.",
        ("daily", "core", "DXI"): "Direction of FXI, on the 360 degree compass.",
        ("daily", "core", "FFM"): "Daily mean of the wind force averaged over 10 minutes, at 10 m.",
        ("daily", "core", "FXI"): "Daily maximum of the hourly maximum instantaneous wind force, at 10 m.",
        ("daily", "core", "RR"): (
            "Precipitation amount over 24 hours, from 06h UTC on day J to 06h UTC on day J+1. The value recorded at "
            "J+1 is attributed to day J."
        ),
        ("daily", "core", "TM"): "Daily mean of the hourly air temperatures under shelter.",
        ("daily", "core", "TN"): "Minimum air temperature under shelter.",
        ("daily", "core", "TX"): "Maximum air temperature under shelter.",
        ("daily", "others", "GLOT"): "Daily global radiation.",
        ("daily", "others", "HNEIGEF"): (
            "Depth of fresh snow fallen over 24 hours, from 06h UTC on day J to 06h UTC on day J+1, that remains on "
            "the ground at 06h UTC."
        ),
        ("daily", "others", "INST"): "Daily sunshine duration.",
        ("daily", "others", "NEIGETOT06"): "Total depth of snow on the ground measured at 06h.",
        ("daily", "others", "PMERM"): "Daily mean of the hourly sea level pressures.",
        ("daily", "others", "TSVM"): "Mean vapour pressure.",
        ("daily", "others", "UM"): "Daily mean of the hourly relative humidities.",
        ("hourly", "core", "DD"): "Direction of FF, on the 360 degree compass.",
        ("hourly", "core", "DXY"): "Direction of FXY, on the 360 degree compass.",
        ("hourly", "core", "FF"): "Wind force averaged over 10 minutes, measured at 10 m.",
        ("hourly", "core", "FXY"): "Maximum value of FF within the hour.",
        ("hourly", "core", "RR1"): "Precipitation amount over 1 hour.",
        ("hourly", "core", "T"): "Instantaneous air temperature under shelter.",
        ("hourly", "core", "TN"): "Minimum air temperature under shelter within the hour.",
        ("hourly", "core", "TX"): "Maximum air temperature under shelter within the hour.",
        ("hourly", "others", "GLO"): "Hourly global radiation, in UTC hours.",
        ("hourly", "others", "INS"): "Hourly sunshine duration, in UTC hours.",
        ("hourly", "others", "N"): (
            "Total cloud amount, in octas. 9 means the sky was invisible through fog or another weather phenomenon."
        ),
        ("hourly", "others", "PMER"): "Sea level pressure, only for stations at an altitude of 750 m or less.",
        ("hourly", "others", "PSTAT"): "Station pressure.",
        ("hourly", "others", "TD"): "Dew point temperature.",
        ("hourly", "others", "U"): "Relative humidity.",
        ("hourly", "others", "VV"): "Visibility.",
        ("monthly", "data", "FFM"): (
            "Monthly mean of the daily mean wind force averaged over 10 minutes (FFM), at 10 m."
        ),
        ("monthly", "data", "FXIAB"): (
            "Monthly absolute maximum of the daily maximum instantaneous wind force, at 10 m."
        ),
        ("monthly", "data", "GLOT"): "Monthly total of the daily global radiation.",
        ("monthly", "data", "HNEIGEFTOT"): (
            "Monthly total of the depth of fresh snow fallen over 24 hours (daily HNEIGEF)."
        ),
        ("monthly", "data", "INST"): "Monthly total of the daily sunshine durations.",
        ("monthly", "data", "PMERM"): "Monthly mean of the daily mean sea level pressures (PMERM).",
        ("monthly", "data", "RR"): "Monthly total of the precipitation depths.",
        ("monthly", "data", "TMM"): "Monthly mean of the daily mean temperatures (TM).",
        ("monthly", "data", "TN"): "Monthly mean of the daily minimum temperatures (TN).",
        ("monthly", "data", "TSVM"): "Monthly mean of the vapour pressure.",
        ("monthly", "data", "TX"): "Monthly mean of the daily maximum temperatures (TX).",
        ("monthly", "data", "UMM"): "Monthly mean of the daily mean humidities (UM).",
    },
    "MeteoswissObservationMetadata": {
        ("10_minutes", "data", "dkl010z0"): "Wind direction; ten minutes mean",
        ("10_minutes", "data", "fkl010z0"): "Wind speed scalar; ten minutes mean in m/s",
        ("10_minutes", "data", "fkl010z1"): "Gust peak (one second); maximum in m/s",
        ("10_minutes", "data", "gre000z0"): "Global radiation; ten minutes mean",
        ("10_minutes", "data", "htoauts0"): "Snow depth (automatic measurement); current value",
        ("10_minutes", "data", "ods000z0"): "Diffuse radiation; ten minutes mean",
        ("10_minutes", "data", "oli000z0"): "Longwave incoming radiation; ten minutes mean",
        ("10_minutes", "data", "pp0qffs0"): "Atmospheric pressure reduced to sea level (QFF); current value",
        ("10_minutes", "data", "prestas0"): "Atmospheric pressure at barometric altitude (QFE); current value",
        ("10_minutes", "data", "pva200s0"): "Vapour pressure 2 m above ground; current value",
        ("10_minutes", "data", "rre150z0"): "Precipitation; ten minutes total",
        ("10_minutes", "data", "sre000z0"): "Sunshine duration; ten minutes total",
        ("10_minutes", "data", "tde200s0"): "Dew point 2 m above ground; current value",
        ("10_minutes", "data", "tre005s0"): "Air temperature at 5 cm above grass; current value",
        ("10_minutes", "data", "tre200s0"): "Air temperature 2 m above ground; current value",
        ("10_minutes", "data", "tso005s0"): "Soil temperature at 5 cm depth; current value",
        ("10_minutes", "data", "tso010s0"): "Soil temperature at 10 cm depth; current value",
        ("10_minutes", "data", "tso020s0"): "Soil temperature at 20 cm depth; current value",
        ("10_minutes", "data", "ure200s0"): "Relative air humidity 2 m above ground; current value",
        ("annual", "data", "fkl010y0"): "Wind speed scalar; annual mean in m/s",
        ("annual", "data", "fkl010y1"): "Gust peak (one second); annual maximum in m/s",
        ("annual", "data", "gre000y0"): "Global radiation; annual mean",
        ("annual", "data", "oli000y0"): "Longwave incoming radiation; annual mean",
        ("annual", "data", "pp0qffy0"): "Atmospheric pressure reduced to sea level (QFF); annual mean",
        ("annual", "data", "prestay0"): "Atmospheric pressure at barometric altitude (QFE); annual mean",
        ("annual", "data", "pva200y0"): "Vapour pressure 2 m above ground; annual mean",
        ("annual", "data", "rre150y0"): "Precipitation; annual total",
        ("annual", "data", "sre000y0"): "Sunshine duration; annual total",
        ("annual", "data", "tre005y0"): "Air temperature at 5 cm above grass; annual mean",
        ("annual", "data", "tre005yn"): "Air temperature at 5 cm above grass; absolute annual minimum",
        ("annual", "data", "tre005yx"): "Air temperature at 5 cm above grass; absolute annual maximum",
        ("annual", "data", "tre200y0"): "Air temperature 2 m above ground; annual mean",
        ("annual", "data", "tre200yn"): "Air temperature 2 m above ground; absolute annual minimum",
        ("annual", "data", "tre200yx"): "Air temperature 2 m above ground; absolute annual maximum",
        ("annual", "data", "tso005y0"): "Soil temperature at 5 cm depth; annual mean",
        ("annual", "data", "tso010y0"): "Soil temperature at 10 cm depth; annual mean",
        ("annual", "data", "tso020y0"): "Soil temperature at 20 cm depth; annual mean",
        ("annual", "data", "ure200y0"): "Relative air humidity 2 m above ground; annual mean",
        ("daily", "data", "dkl010d0"): "Wind direction; daily mean",
        ("daily", "data", "erefaod0"): "Reference evaporation from FAO; daily total",
        ("daily", "data", "fkl010d0"): "Wind speed scalar; daily mean in m/s",
        ("daily", "data", "fkl010d1"): "Gust peak (one second); daily maximum in m/s",
        ("daily", "data", "gre000d0"): "Global radiation; daily mean",
        ("daily", "data", "htoautd0"): "Snow depth (automatic measurement); morning measurement at 6 UTC",
        ("daily", "data", "ods000d0"): "Diffuse radiation; daily mean",
        ("daily", "data", "oli000d0"): "Longwave incoming radiation; daily mean",
        ("daily", "data", "pp0qffd0"): "Atmospheric pressure reduced to sea level (QFF); daily mean",
        ("daily", "data", "prestad0"): "Atmospheric pressure at barometric altitude (QFE); daily mean",
        ("daily", "data", "pva200d0"): "Vapour pressure 2 m above ground; daily mean",
        ("daily", "data", "rre150d0"): "Precipitation; daily total 6 UTC - 6 UTC following day",
        ("daily", "data", "sre000d0"): "Sunshine duration; daily total",
        ("daily", "data", "tre005d0"): "Air temperature at 5 cm above grass; daily mean",
        ("daily", "data", "tre005dn"): "Air temperature at 5 cm above grass; daily minimum",
        ("daily", "data", "tre005dx"): "Air temperature at 5 cm above grass; daily maximum",
        ("daily", "data", "tre200d0"): "Air temperature 2 m above ground; daily mean",
        ("daily", "data", "tre200dn"): "Air temperature 2 m above ground; daily minimum",
        ("daily", "data", "tre200dx"): "Air temperature 2 m above ground; daily maximum",
        ("daily", "data", "tso005d0"): "Soil temperature at 5 cm depth; daily mean",
        ("daily", "data", "tso010d0"): "Soil temperature at 10 cm depth; daily mean",
        ("daily", "data", "tso020d0"): "Soil temperature at 20 cm depth; daily mean",
        ("daily", "data", "ure200d0"): "Relative air humidity 2 m above ground; daily mean",
        ("hourly", "data", "dkl010h0"): "Wind direction; hourly mean",
        ("hourly", "data", "fkl010h0"): "Wind speed scalar; hourly mean in m/s",
        ("hourly", "data", "fkl010h1"): "Gust peak (one second); hourly maximum in m/s",
        ("hourly", "data", "gre000h0"): "Global radiation; hourly mean",
        ("hourly", "data", "htoauths"): "Snow depth (automatic measurement); hourly current value",
        ("hourly", "data", "ods000h0"): "Diffuse radiation; hourly mean",
        ("hourly", "data", "oli000h0"): "Longwave incoming radiation; hourly mean",
        ("hourly", "data", "pp0qffh0"): "Atmospheric pressure reduced to sea level (QFF); hourly mean",
        ("hourly", "data", "prestah0"): "Atmospheric pressure at barometric altitude (QFE); hourly mean",
        ("hourly", "data", "pva200h0"): "Vapour pressure 2 m above ground; hourly mean",
        ("hourly", "data", "rre150h0"): "Precipitation; hourly total",
        ("hourly", "data", "sre000h0"): "Sunshine duration; hourly total",
        ("hourly", "data", "tde200h0"): "Dew point 2 m above ground; hourly mean",
        ("hourly", "data", "tre005h0"): "Air temperature at 5 cm above grass; hourly mean",
        ("hourly", "data", "tre005hn"): "Air temperature at 5 cm above grass; hourly minimum",
        ("hourly", "data", "tre200h0"): "Air temperature 2 m above ground; hourly mean",
        ("hourly", "data", "tre200hn"): "Air temperature 2 m above ground; hourly minimum",
        ("hourly", "data", "tre200hx"): "Air temperature 2 m above ground; hourly maximum",
        ("hourly", "data", "tso005hs"): "Soil temperature at 5 cm depth; hourly current value",
        ("hourly", "data", "tso010hs"): "Soil temperature at 10 cm depth; hourly current value",
        ("hourly", "data", "tso020hs"): "Soil temperature at 20 cm depth; hourly current value",
        ("hourly", "data", "ure200h0"): "Relative air humidity 2 m above ground; hourly mean",
        ("monthly", "data", "fkl010m0"): "Wind speed scalar; monthly mean in m/s",
        ("monthly", "data", "fkl010m1"): "Gust peak (one second); monthly maximum in m/s",
        ("monthly", "data", "gre000m0"): "Global radiation; monthly mean",
        ("monthly", "data", "oli000m0"): "Longwave incoming radiation; monthly mean",
        ("monthly", "data", "pp0qffm0"): "Atmospheric pressure reduced to sea level (QFF); monthly mean",
        ("monthly", "data", "prestam0"): "Atmospheric pressure at barometric altitude (QFE); monthly mean",
        ("monthly", "data", "pva200m0"): "Vapour pressure 2 m above ground; monthly mean",
        ("monthly", "data", "rre150m0"): "Precipitation; monthly total",
        ("monthly", "data", "sre000m0"): "Sunshine duration; monthly total",
        ("monthly", "data", "tre005m0"): "Air temperature at 5 cm above grass; monthly mean",
        ("monthly", "data", "tre005mn"): "Air temperature at 5 cm above grass; absolute monthly minimum",
        ("monthly", "data", "tre005mx"): "Air temperature at 5 cm above grass; absolute monthly maximum",
        ("monthly", "data", "tre200m0"): "Air temperature 2 m above ground; monthly mean",
        ("monthly", "data", "tre200mn"): "Air temperature 2 m above ground; absolute monthly minimum",
        ("monthly", "data", "tre200mx"): "Air temperature 2 m above ground; absolute monthly maximum",
        ("monthly", "data", "tso005m0"): "Soil temperature at 5 cm depth; monthly mean",
        ("monthly", "data", "tso010m0"): "Soil temperature at 10 cm depth; monthly mean",
        ("monthly", "data", "tso020m0"): "Soil temperature at 20 cm depth; monthly mean",
        ("monthly", "data", "ure200m0"): "Relative air humidity 2 m above ground; monthly mean",
    },
    "MetnoFrostMetadata": {
        ("10_minutes", "data", "max(air_temperature PT10M)"): "Highest recorded air temperature per ten minutes",
        ("10_minutes", "data", "max(relative_humidity PT10M)"): "Maximum relative humidity per 10 min",
        ("10_minutes", "data", "max(wind_from_direction_of_gust PT10M)"): (
            "Varying wind direction last 10 minutes. Upper limit"
        ),
        ("10_minutes", "data", "max(wind_speed_of_gust PT10M)"): "Maximum wind gust for the last ten minutes",
        ("10_minutes", "data", "min(air_temperature PT10M)"): "Lowest recorded air temperature per ten minutes",
        ("10_minutes", "data", "min(relative_humidity PT10M)"): "Minimum relative humidity per 10 min",
        ("10_minutes", "data", "sum(precipitation_amount PT10M)"): "Amount of precipitation per 10 minutes",
        ("6_hour", "data", "sum(precipitation_amount PT6H)"): "Amount of precipitation per six hours",
        ("annual", "data", "max(air_temperature P1Y)"): "Highest recorded air temperature per year",
        ("annual", "data", "mean(air_temperature P1Y)"): (
            "Annual mean temperature. The mean is an arithmetic mean of daily values."
        ),
        ("annual", "data", "mean(cloud_area_fraction P1Y)"): (
            "Annual mean cloud cover. The mean is an arithmetic mean of three daily observations (06, 12 and 18 UTC)."
        ),
        ("annual", "data", "min(air_temperature P1Y)"): "Lowest recorded air temperature per year",
        ("annual", "data", "sum(precipitation_amount P1Y)"): "Annual precipitation sum.",
        ("daily", "data", "max(air_temperature P1D)"): "Highest recorded air temperature per 24 hours",
        ("daily", "data", "max(wind_speed P1D)"): (
            "Daily maximum mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do "
            "not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available)."
        ),
        ("daily", "data", "mean(air_pressure_at_sea_level P1D)"): (
            "Mean daily air pressure reduced to sea level. The parameter is usually called QFF in aviation and shows "
            "the measured air pressure reduced to mean sea level by applying actual atmospheric conditions."
        ),
        ("daily", "data", "mean(air_temperature P1D)"): (
            "Daily mean temperature. The mean is an arithmetic mean of 24 hourly values (00-00 UTC), or a formula "
            "based mean value when only a limited number of observations is available (e.g. 06, 12, 18 UTC)."
        ),
        ("daily", "data", "mean(relative_humidity P1D)"): "Daily mean relative humidity.",
        ("daily", "data", "mean(surface_air_pressure P1D)"): (
            "Daily mean air pressure at the station. The parameter is usually called QFE in aviation and shows the "
            "measured air pressure reduced to the reference height of the station."
        ),
        ("daily", "data", "mean(surface_downwelling_shortwave_flux_in_air P1D)"): (
            "Mean global radiation over the last 24 hours. Global radiation is the total downwelling shortwave "
            "radiation from the sun. Shortwave radiation have wavelengths in the area 295-2800 nm and therefore "
            "includes ultraviolet, visible and infrared light. The instrument measures the radiation flux through a "
            "horizontal surface (W/m2)."
        ),
        ("daily", "data", "mean(wind_speed P1D)"): (
            "Daily mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not "
            "exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available)."
        ),
        ("daily", "data", "min(air_temperature P1D)"): "Lowest recorded air temperature per 24 hours",
        ("daily", "data", "sum(duration_of_sunshine P1D)"): "Number of hours of sunshine over the last 24 hours.",
        ("daily", "data", "sum(precipitation_amount P1D)"): "Daily precipitation sum (between 06-06 UTC).",
        ("daily", "data", "surface_snow_thickness"): (
            "The depth of the snow is measured in cm from the ground to the top of the snow cover. Code -1 means no "
            "snow, and is returned as a depth of 0."
        ),
        ("hourly", "data", "air_pressure_at_sea_level"): (
            "Air pressure reduced to mean sea level. The parameter is usually called QFF in aviation and shows the "
            "measured air pressure reduced to mean sea level by applying actual atmospheric conditions."
        ),
        ("hourly", "data", "air_temperature"): "Air temperature (default 2 m above ground), present value",
        ("hourly", "data", "cloud_area_fraction"): (
            "Total cloud cover is registered using a code 0 - 8 describing how many eights of the sky are covered by "
            "clouds (0 = no clouds, 8 = completely overcast). Code -3 or 9 means the cloud cover cannot be estimated "
            "because the sky is obstructed from view by fog, drifting snow and the like; both are returned as null."
        ),
        ("hourly", "data", "dew_point_temperature"): (
            "Dew-point temperature - the temperature at which the air, when cooled, will become saturated (and dew is "
            "formed)"
        ),
        ("hourly", "data", "mean(surface_downwelling_shortwave_flux_in_air PT1H)"): (
            "Hourly mean global radiation. Global radiation is the total downwelling shortwave radiation from the "
            "sun. Shortwave radiation have wavelengths in the area 295-2800 nm and therefore includes ultraviolet, "
            "visible and infrared light. The instrument measures the radiation flux through a horizontal surface "
            "(W/m2)."
        ),
        ("hourly", "data", "relative_humidity"): "Relative humidity",
        ("hourly", "data", "sum(precipitation_amount PT1H)"): "Amount of precipitation per hour",
        ("hourly", "data", "surface_air_pressure"): (
            "Air pressure at the station. The parameter is usually called QFE in aviation and shows the measured air "
            "pressure reduced to the reference height of the station."
        ),
        ("hourly", "data", "surface_snow_thickness"): (
            "The depth of the snow is measured in cm from the ground to the top of the snow cover. Code -1 means no "
            "snow, and is returned as a depth of 0."
        ),
        ("hourly", "data", "wind_from_direction"): (
            "Mean wind direction over the last ten minutes before the observation time. Wind direction is defined as "
            "the direction from which the wind blows and is registered in degrees, where 360 degrees is north and 90 "
            "degrees is east."
        ),
        ("hourly", "data", "wind_speed"): (
            "Mean wind speed is registered as a mean value of the wind speed over the last ten minutes before the "
            "observation time. (default: 10 meters above ground, some stations have measurements at 2 meters)"
        ),
        ("monthly", "data", "max(air_temperature P1M)"): "Highest recorded air temperature per month",
        ("monthly", "data", "max(wind_speed P1M)"): (
            "Monthly maximum mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations "
            "do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available)."
        ),
        ("monthly", "data", "mean(air_pressure_at_sea_level P1M)"): (
            "Monthly mean air pressure reduced to sea level. The parameter is usually called QFF in aviation and "
            "shows the measured air pressure reduced to mean sea level by applying actual atmospheric conditions."
        ),
        ("monthly", "data", "mean(air_temperature P1M)"): (
            "Monthly mean temperature. The mean is an arithmetic mean of daily values."
        ),
        ("monthly", "data", "mean(cloud_area_fraction P1M)"): (
            "Monthly mean cloud cover. The mean is an arithmetic mean of three daily observations (06, 12 and 18 UTC)."
        ),
        ("monthly", "data", "mean(dew_point_temperature P1M)"): (
            "Monthly mean dew-point temperature. Dew-point temperature is the temperature at which the air, when "
            "cooled, will become saturated (and dew is formed)."
        ),
        ("monthly", "data", "mean(relative_humidity P1M)"): "Monthly mean relative humidity.",
        ("monthly", "data", "mean(surface_air_pressure P1M)"): (
            "Monthly mean air pressure at the station. The parameter is usually called QFE in aviation and shows the "
            "measured air pressure reduced to the reference height of the station."
        ),
        ("monthly", "data", "mean(surface_snow_thickness P1M)"): (
            "Monthly mean snow depth. The mean value is an arithmetic mean of daily values."
        ),
        ("monthly", "data", "mean(wind_speed P1M)"): (
            "Monthly mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not "
            "exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available)."
        ),
        ("monthly", "data", "min(air_temperature P1M)"): "Lowest recorded air temperature per month",
        ("monthly", "data", "sum(duration_of_sunshine P1M)"): "Number of hours of sunshine over the last month.",
        ("monthly", "data", "sum(precipitation_amount P1M)"): "Monthly precipitation sum.",
    },
    "SmhiObservationMetadata": {
        ("1_minute", "data", "43"): "Relative humidity. Instantaneous value, every minute.",
        ("1_minute", "data", "44"): "Air pressure reduced to sea level. Instantaneous value, every minute.",
        ("1_minute", "data", "45"): "Air temperature. Instantaneous value, every minute.",
        ("1_minute", "data", "46"): "Precipitation amount. Precipitation during one minute.",
        ("1_minute", "data", "47"): "Wind speed. One minute mean, every minute.",
        ("1_minute", "data", "48"): "Wind direction. One minute mean, every minute.",
        ("1_minute", "data", "51"): "Visibility. One minute mean, every minute.",
        ("1_minute", "data", "52"): "Snow depth. Instantaneous value, every minute.",
        ("daily", "data", "19"): "Air temperature. Minimum, once per day.",
        ("daily", "data", "2"): "Air temperature. Daily mean, once per day at 00.",
        ("daily", "data", "20"): "Air temperature. Maximum, once per day.",
        ("daily", "data", "5"): "Precipitation amount. Daily sum, once per day at 06.",
        ("daily", "data", "8"): "Snow depth. Instantaneous value, once per day at 06.",
        ("hourly", "data", "1"): "Air temperature. Instantaneous value, once per hour.",
        ("hourly", "data", "12"): "Visibility. Instantaneous value, once per hour.",
        ("hourly", "data", "16"): "Total cloud amount. Instantaneous value, once per hour.",
        ("hourly", "data", "21"): "Wind gust. Maximum, once per hour.",
        ("hourly", "data", "3"): "Wind direction. Mean over 10 minutes, once per hour.",
        ("hourly", "data", "39"): "Dew point temperature. Instantaneous value, once per hour.",
        ("hourly", "data", "4"): "Wind speed. Mean over 10 minutes, once per hour.",
        ("hourly", "data", "6"): "Relative humidity. Instantaneous value, once per hour.",
        ("hourly", "data", "7"): "Precipitation amount. Hourly sum, once per hour.",
        ("hourly", "data", "9"): "Air pressure reduced to sea level. At sea level, instantaneous value, once per hour.",
        ("monthly", "data", "22"): "Air temperature. Mean, once per month.",
        ("monthly", "data", "23"): "Precipitation amount. Sum, once per month.",
    },
}


# What a dataset holds, keyed by metadata model name then ``(resolution, dataset)``.
# The docs tables carry a trailing "([details](url))" pointer; that is page formatting and
# is not part of the description here.
DATASET_DESCRIPTIONS: dict[str, dict[tuple[str, str], str]] = {
    "DwdDerivedMetadata": {
        ("daily", "soil"): (
            "Daily soil data including temperature at various depths, soil moisture, and evapotranspiration estimates."
        ),
        ("hourly", "radiation_global"): "Hourly global radiation data with quality flags and uncertainty estimates.",
        ("hourly", "sunshine_duration"): "Hourly sunshine duration data with quality flags and uncertainty estimates.",
        ("monthly", "climate_correction_factor"): (
            "Data on climate correction factors, comparing the degree days between a postal code and "
            "a reference station."
        ),
        ("monthly", "heating_degreedays"): (
            "Data on degree days, comparing the monthly temperatures to the reference temperature of 20 degree Celsius."
        ),
        ("monthly", "soil"): (
            "Monthly aggregated soil data including temperature at various depths, soil moisture, and "
            "evapotranspiration estimates."
        ),
    },
    "DwdDmoMetadata": {
        ("hourly", "icon"): (
            "Local forecast of 115 parameters for worldwide stations, 4 times a day with a lead-time of 240 hours."
        ),
        ("hourly", "icon_eu"): (
            "Local forecast of 40 parameters for worldwide stations, 24 times a day with a lead-time of 240 hours."
        ),
    },
    "DwdObservationMetadata": {
        ("10_minutes", "precipitation"): "10-minute station observations of precipitation for Germany.",
        ("10_minutes", "solar"): "10-minute station observations of solar and sunshine for Germany.",
        ("10_minutes", "temperature_air"): "10-minute station observations of air temperature for Germany.",
        ("10_minutes", "temperature_extreme"): "10-minute station observations of extreme temperatures for Germany.",
        ("10_minutes", "urban_precipitation"): (
            "10-minute precipitation, observed at urban stations for selected urban areas in Germany."
        ),
        ("10_minutes", "urban_pressure"): (
            "10-minute pressure, observed at urban stations for selected urban areas in Germany."
        ),
        ("10_minutes", "urban_solar"): (
            "10-minute solar radiation and sunshine, observed at urban stations for selected urban areas in Germany."
        ),
        ("10_minutes", "urban_temperature_air"): (
            "10-minute air temperature and humidity, observed at urban stations for selected urban areas in Germany."
        ),
        ("10_minutes", "urban_temperature_extreme"): (
            "10-minute extreme air temperatures, observed at urban stations for selected urban areas in Germany."
        ),
        ("10_minutes", "urban_temperature_soil"): (
            "10-minute soil temperature, observed at urban stations for selected urban areas in Germany."
        ),
        ("10_minutes", "urban_wind"): (
            "10-minute wind speed and direction, observed at urban stations for selected urban areas in Germany."
        ),
        ("10_minutes", "urban_wind_extreme"): (
            "10-minute extreme wind, observed at urban stations for selected urban areas in Germany."
        ),
        ("10_minutes", "wind"): "10-minute station observations of wind for Germany.",
        ("10_minutes", "wind_extreme"): "10-minute station observations of extreme wind for Germany.",
        ("1_minute", "precipitation"): "1-minute station observations of precipitation for Germany.",
        ("5_minutes", "precipitation"): "5-minute station observations of precipitation for Germany.",
        ("annual", "climate_indices"): (
            "Historical annual counts of tropical nights and of frost, summer, hot and ice days for "
            "Germany, derived from the daily climate observations."
        ),
        ("annual", "climate_summary"): (
            "Historical annual station observations (temperature, pressure, precipitation, sunshine "
            "duration, etc.) for Germany (details missing, parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("annual", "precipitation_indices"): (
            "Historical annual counts of days reaching precipitation heights of 0.1 to 20 mm and snow "
            "depths of 1 and 5 cm for Germany, derived from the daily precipitation observations."
        ),
        ("annual", "precipitation_more"): (
            "Historical annual precipitation observations for Germany (details missing, parameter "
            "descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("annual", "weather_phenomena"): (
            "Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), "
            "dew, glaze, ripe, sleet and hail for stations of Germany (details missing, parameter "
            "descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("daily", "climate_summary"): (
            "Daily station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany."
        ),
        ("daily", "precipitation_more"): "Daily precipitation observations for Germany.",
        ("daily", "solar"): (
            "Daily station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany."
        ),
        ("daily", "temperature_soil"): "Daily station observations of soil temperature station data for Germany.",
        ("daily", "water_equivalent"): "Daily observations of snow height and water equivalent for Germany.",
        ("daily", "weather_phenomena"): (
            "Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), "
            "dew, glaze, ripe, sleet and hail for stations of Germany (details missing, parameter "
            "descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("daily", "weather_phenomena_more"): (
            "Counts of (additional) weather phenomena sleet, hail, fog and thunder for stations of "
            "Germany (details missing, parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("hourly", "cloud_type"): (
            "Hourly station observations of cloud cover, cloud type and cloud height in up to 4 layers for Germany."
        ),
        ("hourly", "cloudiness"): "Hourly station observations of cloudiness for Germany.",
        ("hourly", "dew_point"): "Hourly station observations of air and dew point temperature for Germany.",
        ("hourly", "moisture"): "Hourly station observations of moisture parameters for Germany.",
        ("hourly", "precipitation"): "Hourly station observations of precipitation for Germany.",
        ("hourly", "pressure"): "Hourly station observations of pressure for Germany.",
        ("hourly", "solar"): (
            "Hourly station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany."
        ),
        ("hourly", "sun"): "Hourly station observations of sunshine duration for Germany.",
        ("hourly", "temperature_air"): "Hourly station observations of 2 m air temperature and humidity for Germany.",
        ("hourly", "temperature_soil"): "Hourly station observations of of soil temperature for Germany.",
        ("hourly", "urban_precipitation"): (
            "Recent hourly precipitation, observed at urban stations for selected urban areas in Germany."
        ),
        ("hourly", "urban_pressure"): (
            "Recent hourly pressure, observed at urban stations for selected urban areas in Germany."
        ),
        ("hourly", "urban_sun"): (
            "Recent hourly sunshine duration, observed at urban stations for selected urban areas in Germany."
        ),
        ("hourly", "urban_temperature_air"): (
            "Recent hourly air temperature and humidity, observed at urban stations for selected "
            "urban areas in Germany."
        ),
        ("hourly", "urban_temperature_soil"): (
            "Recent hourly soil temperature, observed at urban stations for selected urban areas in Germany."
        ),
        ("hourly", "urban_wind"): (
            "Recent hourly wind speed and direction, observed at urban stations for selected urban areas in Germany."
        ),
        ("hourly", "visibility"): "Hourly station observations of visibility for Germany.",
        ("hourly", "weather_phenomena"): "Hourly station observations of weather phenomena for Germany.",
        ("hourly", "wind"): "Hourly mean value from station observations of wind speed and wind direction for Germany.",
        ("hourly", "wind_extreme"): "Hourly maximum value from station observations of windspeed for Germany.",
        ("hourly", "wind_synoptic"): "Hourly station observations of wind speed and wind direction for Germany.",
        ("monthly", "climate_indices"): (
            "Historical monthly counts of tropical nights and of frost, summer, hot and ice days for "
            "Germany, derived from the daily climate observations."
        ),
        ("monthly", "climate_summary"): (
            "Monthly station observations (temperature, precipitation, sunshine duration, wind and "
            "cloud cover) for Germany."
        ),
        ("monthly", "precipitation_indices"): (
            "Historical monthly counts of days reaching precipitation heights of 0.1 to 20 mm and snow "
            "depths of 1 and 5 cm for Germany, derived from the daily precipitation observations."
        ),
        ("monthly", "precipitation_more"): "Monthly precipitation observations for Germany.",
        ("monthly", "weather_phenomena"): (
            "Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), "
            "dew, glaze, ripe, sleet and hail for stations of Germany (details missing, parameter "
            "descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "cloudiness"): (
            "Recent subdaily cloud cover and cloud density of stations in Germany (details missing, "
            "parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "moisture"): (
            "Recent subdaily vapor pressure, mean temperature in 2m height, mean temperature in 5cm "
            "height and humidity of stations in Germany (details missing, parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "pressure"): (
            "Recent air pressure at site of stations in Germany (details missing, parameter "
            "descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "soil"): (
            "Recent soil temperature in 5cm depth of stations in Germany (details missing, parameter "
            "descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "temperature_air"): (
            "Recent subdaily air temperature and humidity of stations in Germany (details missing, "
            "parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "visibility"): (
            "Recent visibility range of stations in Germany (details missing, parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "wind"): (
            "Recent wind direction and wind force (beaufort) of stations in Germany (details missing, "
            "parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "wind_extreme"): (
            "Recent subdaily extreme wind of stations in Germany (details missing, parameter "
            "descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
    },
    "DwdRoadMetadata": {
        ("15_minutes", "data"): "15-minute road weather data of German highway stations.",
    },
    "EAHydrologyMetadata": {
        ("15_minutes", "data"): "Historical 15 minute station observations of flow and groundwater level for the UK.",
        ("daily", "data"): "Historical daily station observations of flow and groundwater level for the UK.",
    },
    "EcccObservationMetadata": {
        ("daily", "data"): "Historical daily station observations for Canada.",
        ("hourly", "data"): (
            "Historical hourly station observations of 2m air temperature, humidity, wind direction, "
            "wind speed, visibility range, air pressure, wind gust and weather for Canada."
        ),
        ("monthly", "data"): "Historical monthly station observations for Canada.",
    },
    "GeosphereObservationMetadata": {
        ("10_minutes", "data"): "historical 10 minute data.",
        ("daily", "data"): "Historical daily station observations of 2m air temperature and humidity for Germany.",
        ("hourly", "data"): "Historical hourly station observations of 2m air temperature and humidity for Germany.",
        ("monthly", "data"): "Historical monthly station observations of 2m air temperature and humidity for Germany.",
    },
    "HubeauMetadata": {(resolution, "data"): "Flow and stage for France." for resolution in _HUBEAU_RESOLUTIONS},
    "ImgwHydrologyMetadata": {
        ("daily", "hydrology"): "historical daily hydrology data.",
        ("monthly", "hydrology"): "historical daily climate data.",
    },
    "ImgwMeteorologyMetadata": {
        ("daily", "climate"): "historical daily climate data.",
        ("daily", "precipitation"): "historical daily precipitation data.",
        ("daily", "synop"): "historical daily synop data.",
        ("monthly", "precipitation"): "historical monthly precipitation data.",
        ("monthly", "synop"): "historical monthly synop data.",
    },
    "NoaaGhcnMetadata": {
        ("daily", "data"): "Historical daily weather data from the Global Historical Climatology Network (GHCN).",
        ("hourly", "data"): "Historical hourly weather data from the Global Historical Climatology Network (GHCN).",
    },
    "NwsObservationMetadata": {
        ("hourly", "data"): (
            "Historical hourly station observations (temperature, pressure, precipitation, etc.) for the US."
        ),
    },
    "WsvPegelMetadata": {
        (resolution, "data"): (
            "Recent data (last 30 days) of German waterways including water level and discharge for "
            "most stations but may also include chemical, meteorologic and other types of values."
        )
        for resolution in _WSV_PEGEL_RESOLUTIONS
    },
}

# What a resolution holds, keyed by metadata model name then resolution name.
RESOLUTION_DESCRIPTIONS: dict[str, dict[str, str]] = {
    # Only where the name underdetermines what arrives. "hourly" and "daily" say everything about
    # themselves, and filling those in would read as information without being any.
    "DwdObservationMetadata": {
        "subdaily": "measurements at 7am, 2pm, 9pm.",
    },
    "MeteoFranceSynopMetadata": {
        "subdaily": "SYNOP reports, made at their native three-hourly interval.",
    },
    "MetnoFrostMetadata": {
        "6_hour": "Synoptic observations reported every six hours.",
    },
}

# Derived rather than sourced: DWD publishes no prose for these fields in either language, so the
# text is taken from the same canonical parameter at the same resolution elsewhere -- same quantity
# over the same interval -- or, failing that, from the canonical sentence in ``parameter_table``.
# Kept apart from SOURCE_DESCRIPTIONS so that a description here is not mistaken for the wording of
# the source itself, and applied only where nothing else supplies one.
DERIVED_DESCRIPTIONS: dict[str, dict[tuple[str, str, str], str]] = {
    "DwdDerivedMetadata": {
        ("monthly", "cooling_degreehours_13", "Kuehltage"): "Number of days on which cooling was required.",
        ("monthly", "cooling_degreehours_16", "Kuehltage"): "Number of days on which cooling was required.",
        ("monthly", "cooling_degreehours_18", "Kuehltage"): "Number of days on which cooling was required.",
    },
    "DwdDmoMetadata": {},
    "DwdMosmixMetadata": {},
    "DwdObservationMetadata": {
        ("10_minutes", "precipitation", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "solar", "qn"): "Quality flag published by the source for the values in the same dataset.",
        ("10_minutes", "temperature_air", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "temperature_extreme", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "urban_precipitation", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "urban_pressure", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "urban_solar", "qn"): "Quality flag published by the source for the values in the same dataset.",
        ("10_minutes", "urban_temperature_air", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "urban_temperature_extreme", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "urban_temperature_soil", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "urban_wind_extreme", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "urban_wind", "qn"): "Quality flag published by the source for the values in the same dataset.",
        ("10_minutes", "wind_extreme", "qn"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("10_minutes", "wind", "qn"): "Quality flag published by the source for the values in the same dataset.",
        ("1_minute", "precipitation", "qn"): "Quality flag published by the source for the values in the same dataset.",
        ("5_minutes", "precipitation", "qn_5min"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("annual", "climate_indices", "qn_4"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("annual", "climate_summary", "qn_4"): (
            "Quality flag published by the source, applying to the dataset as a whole."
        ),
        ("annual", "climate_summary", "qn_6"): (
            "Quality flag published by the source for `precipitation` in the same dataset."
        ),
        ("annual", "precipitation_indices", "qn_6"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("annual", "precipitation_more", "qn_6"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("annual", "weather_phenomena", "qn_4"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("daily", "precipitation_more", "qn_6"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("daily", "solar", "qn_592"): "Quality flag published by the source for the values in the same dataset.",
        ("daily", "temperature_soil", "qn_2"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("daily", "water_equivalent", "qn_6"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("daily", "weather_phenomena_more", "qn_6"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("daily", "weather_phenomena", "qn_4"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("hourly", "cloud_type", "qn_8"): "Quality flag.",
        ("hourly", "cloudiness", "qn_8"): "Quality flag.",
        ("hourly", "dew_point", "qn_8"): "Quality flag.",
        ("hourly", "moisture", "qn_4"): "Quality flag.",
        ("hourly", "precipitation", "qn_8"): "Quality flag.",
        ("hourly", "pressure", "qn_8"): "Quality flag.",
        ("hourly", "solar", "qn_592"): "Quality flag.",
        ("hourly", "sun", "qn_7"): "Quality flag.",
        ("hourly", "temperature_air", "qn_9"): "Quality flag.",
        ("hourly", "temperature_soil", "qn_2"): "Quality flag.",
        ("hourly", "urban_precipitation", "qualitaets_niveau"): "Quality flag.",
        ("hourly", "urban_pressure", "qualitaets_niveau"): "Quality flag.",
        ("hourly", "urban_sun", "qualitaets_niveau"): "Quality flag.",
        ("hourly", "urban_temperature_air", "qualitaets_niveau"): "Quality flag.",
        ("hourly", "urban_temperature_soil", "qualitaets_niveau"): "Quality flag.",
        ("hourly", "urban_wind", "qualitaets_niveau"): "Quality flag.",
        ("hourly", "visibility", "qn_8"): "Quality flag.",
        ("hourly", "weather_phenomena", "qn_8"): "Quality flag.",
        ("hourly", "wind_extreme", "qn_8"): "Quality flag.",
        ("hourly", "wind_synoptic", "qn_8"): "Quality flag.",
        ("hourly", "wind", "qn_3"): "Quality flag.",
        ("monthly", "climate_indices", "qn_4"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("monthly", "precipitation_indices", "qn_6"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("monthly", "precipitation_more", "qn_6"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("monthly", "weather_phenomena", "qn_4"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("subdaily", "cloudiness", "qn_4"): "Quality flag published by the source for the values in the same dataset.",
        ("subdaily", "moisture", "qn_4"): "Quality flag published by the source for the values in the same dataset.",
        ("subdaily", "pressure", "qn_4"): "Quality flag published by the source for the values in the same dataset.",
        ("subdaily", "soil", "qn_4"): "Quality flag published by the source for the values in the same dataset.",
        ("subdaily", "temperature_air", "qn_4"): (
            "Quality flag published by the source for the values in the same dataset."
        ),
        ("subdaily", "visibility", "qn_4"): "Quality flag published by the source for the values in the same dataset.",
        ("subdaily", "wind_extreme", "qn_8_3"): (
            "Quality flag for the 3-hourly maximum wind gust reported in the same dataset."
        ),
        ("subdaily", "wind_extreme", "qn_8_6"): (
            "Quality flag for the 6-hourly maximum wind gust reported in the same dataset."
        ),
        ("subdaily", "wind", "qn_4"): "Quality flag published by the source for the values in the same dataset.",
    },
    "DwdSwsmosMetadata": {
        ("hourly", "data", "RC"): "Coded condition of the road surface, such as dry, wet or icy.",
        ("hourly", "data", "TL"): "Temperature 2m above surface.",
        ("hourly", "data", "TS"): "Mean temperature of the ground surface.",
    },
    "DmiObservationMetadata": {
        ("annual", "data", "acc_heating_degree_days_17"): (
            "Heating degree days, the temperature shortfall below a base value summed over each day."
        ),
        ("annual", "data", "acc_precip"): "Depth of precipitation collected over the period.",
        ("annual", "data", "max_precip_24h"): (
            "Greatest precipitation depth recorded in any single interval of the period."
        ),
        ("annual", "data", "max_temp_w_date"): "Maximum air temperature at 2 m above ground.",
        ("annual", "data", "max_wind_speed_10min"): "Highest rolling mean wind speed over the period.",
        ("annual", "data", "max_wind_speed_3sec"): "Speed of the strongest gust of the period.",
        ("annual", "data", "mean_daily_max_temp"): (
            "Mean of the daily maximum air temperature at 2 m above ground over the period."
        ),
        ("annual", "data", "mean_daily_min_temp"): (
            "Mean of the daily minimum air temperature at 2 m above ground over the period."
        ),
        ("annual", "data", "mean_pressure"): (
            "Air pressure reduced to mean sea level, so that stations at different heights compare."
        ),
        ("annual", "data", "mean_relative_hum"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("annual", "data", "mean_temp"): "Mean air temperature at 2 m above ground.",
        ("annual", "data", "mean_wind_dir"): "Direction the wind is blowing from, clockwise from true north.",
        ("annual", "data", "mean_wind_speed"): "Mean speed of the wind over the period.",
        ("annual", "data", "min_temp"): "Minimum air temperature at 2 m above ground.",
        ("daily", "data", "acc_heating_degree_days_17"): (
            "Heating degree days, the temperature shortfall below a base value summed over each day."
        ),
        ("daily", "data", "acc_precip"): "Depth of precipitation collected over the period.",
        ("daily", "data", "max_precip_30m"): (
            "Greatest precipitation depth recorded in any single interval of the period."
        ),
        ("daily", "data", "max_temp_w_date"): "Maximum air temperature at 2 m above ground.",
        ("daily", "data", "max_wind_speed_10min"): "Highest rolling mean wind speed over the period.",
        ("daily", "data", "max_wind_speed_3sec"): "Speed of the strongest gust of the period.",
        ("daily", "data", "mean_pressure"): (
            "Air pressure reduced to mean sea level, so that stations at different heights compare."
        ),
        ("daily", "data", "mean_relative_hum"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("daily", "data", "mean_temp"): "Mean air temperature at 2 m above ground.",
        ("daily", "data", "mean_wind_dir"): "Direction the wind is blowing from, clockwise from true north.",
        ("daily", "data", "mean_wind_speed"): "Mean speed of the wind over the period.",
        ("daily", "data", "min_temp"): "Minimum air temperature at 2 m above ground.",
        ("hourly", "data", "acc_precip"): "Depth of precipitation collected over the period.",
        ("hourly", "data", "max_temp_w_date"): "Maximum air temperature at 2 m above ground.",
        ("hourly", "data", "max_wind_speed_10min"): "Highest rolling mean wind speed over the period.",
        ("hourly", "data", "max_wind_speed_3sec"): "Speed of the strongest gust of the period.",
        ("hourly", "data", "mean_pressure"): (
            "Air pressure reduced to mean sea level, so that stations at different heights compare."
        ),
        ("hourly", "data", "mean_relative_hum"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("hourly", "data", "mean_temp"): "Mean air temperature at 2 m above ground.",
        ("hourly", "data", "mean_wind_dir"): "Direction the wind is blowing from, clockwise from true north.",
        ("hourly", "data", "mean_wind_speed"): "Mean speed of the wind over the period.",
        ("hourly", "data", "min_temp"): "Minimum air temperature at 2 m above ground.",
        ("monthly", "data", "acc_heating_degree_days_17"): (
            "Heating degree days, the temperature shortfall below a base value summed over each day."
        ),
        ("monthly", "data", "acc_precip"): "Depth of precipitation collected over the period.",
        ("monthly", "data", "max_precip_24h"): (
            "Greatest precipitation depth recorded in any single interval of the period."
        ),
        ("monthly", "data", "max_relative_hum"): "Highest relative humidity over the period.",
        ("monthly", "data", "max_temp_w_date"): "Maximum air temperature at 2 m above ground.",
        ("monthly", "data", "max_wind_speed_10min"): "Highest rolling mean wind speed over the period.",
        ("monthly", "data", "max_wind_speed_3sec"): "Speed of the strongest gust of the period.",
        ("monthly", "data", "mean_daily_max_temp"): (
            "Mean of the daily maximum air temperature at 2 m above ground over the period."
        ),
        ("monthly", "data", "mean_daily_min_temp"): (
            "Mean of the daily minimum air temperature at 2 m above ground over the period."
        ),
        ("monthly", "data", "mean_pressure"): (
            "Air pressure reduced to mean sea level, so that stations at different heights compare."
        ),
        ("monthly", "data", "mean_relative_hum"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("monthly", "data", "mean_temp"): "Mean air temperature at 2 m above ground.",
        ("monthly", "data", "mean_wind_dir"): "Direction the wind is blowing from, clockwise from true north.",
        ("monthly", "data", "mean_wind_speed"): "Mean speed of the wind over the period.",
        ("monthly", "data", "min_relative_hum"): "Lowest relative humidity over the period.",
        ("monthly", "data", "min_temp"): "Minimum air temperature at 2 m above ground.",
    },
    "EcccObservationMetadata": {
        ("daily", "data", "max_rel_humidity"): "Highest relative humidity over the period.",
        ("daily", "data", "min_rel_humidity"): "Lowest relative humidity over the period.",
    },
    "ImgwMeteorologyMetadata": {
        ("daily", "synop", "suma opadu dzień"): "Depth of precipitation collected during the daytime hours.",
        ("daily", "synop", "suma opadu noc"): "Depth of precipitation collected during the night hours.",
        ("daily", "synop", "średnie dobowe ciśnienie na pozimie morza"): (
            "Air pressure reduced to mean sea level, so that stations at different heights compare."
        ),
        ("monthly", "synop", "maksymalna dobowa suma opadów"): "precipitation height max",
        ("monthly", "synop", "suma opadu dzień"): "Depth of precipitation collected during the daytime hours.",
        ("monthly", "synop", "suma opadu noc"): "Depth of precipitation collected during the night hours.",
    },
    "IpmaObservationMetadata": {
        ("hourly", "data", "humidade"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("hourly", "data", "idDireccVento"): "Direction the wind is blowing from, clockwise from true north.",
        ("hourly", "data", "intensidadeVento"): "Mean speed of the wind over the period.",
        ("hourly", "data", "precAcumulada"): "Depth of precipitation collected over the period.",
        ("hourly", "data", "pressao"): (
            "Air pressure reduced to mean sea level, so that stations at different heights compare."
        ),
        ("hourly", "data", "radiacao"): (
            "Global radiation received on a horizontal surface, accumulated as energy over the interval."
        ),
        ("hourly", "data", "temperatura"): "Mean air temperature at 2 m above ground.",
    },
    "MeteoFranceSynopMetadata": {
        ("subdaily", "data", "dd"): "Direction the wind is blowing from, clockwise from true north.",
        ("subdaily", "data", "ff"): "Mean speed of the wind over the period.",
        ("subdaily", "data", "n"): "Fraction of the sky covered by cloud of any kind.",
        ("subdaily", "data", "pmer"): (
            "Air pressure reduced to mean sea level, so that stations at different heights compare."
        ),
        ("subdaily", "data", "pres"): "Air pressure as measured at station height.",
        ("subdaily", "data", "raf10"): "Speed of the strongest gust of the period.",
        ("subdaily", "data", "rr1"): "Depth of precipitation collected over the preceding hour.",
        ("subdaily", "data", "rr12"): "Depth of precipitation collected over the preceding 12 hours.",
        ("subdaily", "data", "rr24"): "Depth of precipitation collected over the preceding 24 hours.",
        ("subdaily", "data", "rr3"): "Depth of precipitation collected over the preceding 3 hours.",
        ("subdaily", "data", "rr6"): "Depth of precipitation collected over the preceding 6 hours.",
        ("subdaily", "data", "t"): "Mean air temperature at 2 m above ground.",
        ("subdaily", "data", "td"): (
            "Dew point at 2 m above ground, the temperature at which the air would become saturated."
        ),
        ("subdaily", "data", "tn24"): "Minimum air temperature at 2 m above ground over the preceding 24 hours.",
        ("subdaily", "data", "tx24"): "Maximum air temperature at 2 m above ground over the preceding 24 hours.",
        ("subdaily", "data", "u"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("subdaily", "data", "vv"): "Horizontal distance at which an object can still be made out.",
    },
    "RmiObservationMetadata": {
        ("10_minutes", "data", "humidity_rel_shelter_avg"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("10_minutes", "data", "precip_quantity"): "Depth of precipitation collected over the period.",
        ("10_minutes", "data", "pressure"): "Air pressure as measured at station height.",
        ("10_minutes", "data", "short_wave_from_sky_avg"): (
            "Global irradiance on a horizontal surface, reported as power rather than energy."
        ),
        ("10_minutes", "data", "sun_duration"): "Length of time the sun shone unobstructed.",
        ("10_minutes", "data", "temp_dry_shelter_avg"): "Mean air temperature at 2 m above ground.",
        ("10_minutes", "data", "temp_grass_pt100_avg"): "Mean air temperature at 0.05 m above ground.",
        ("10_minutes", "data", "temp_soil_avg_10cm"): "Mean soil temperature at 0.1 m depth.",
        ("10_minutes", "data", "temp_soil_avg_20cm"): "Mean soil temperature at 0.2 m depth.",
        ("10_minutes", "data", "temp_soil_avg_50cm"): "Mean soil temperature at 0.5 m depth.",
        ("10_minutes", "data", "temp_soil_avg_5cm"): "Mean soil temperature at 0.05 m depth.",
        ("10_minutes", "data", "wind_direction"): "Direction the wind is blowing from, clockwise from true north.",
        ("10_minutes", "data", "wind_gusts_speed"): "Speed of the strongest gust of the period.",
        ("10_minutes", "data", "wind_speed_10m"): "Mean speed of the wind over the period.",
        ("daily", "data", "humidity_rel_shelter_avg"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("daily", "data", "precip_quantity"): "Depth of precipitation collected over the period.",
        ("daily", "data", "pressure"): "Air pressure as measured at station height.",
        ("daily", "data", "short_wave_from_sky_avg"): (
            "Global irradiance on a horizontal surface, reported as power rather than energy."
        ),
        ("daily", "data", "sun_duration"): "Length of time the sun shone unobstructed.",
        ("daily", "data", "temp_avg"): "Mean air temperature at 2 m above ground.",
        ("daily", "data", "temp_grass_pt100_avg"): "Mean air temperature at 0.05 m above ground.",
        ("daily", "data", "temp_max"): "Maximum air temperature at 2 m above ground.",
        ("daily", "data", "temp_min"): "Minimum air temperature at 2 m above ground.",
        ("daily", "data", "temp_soil_avg_10cm"): "Mean soil temperature at 0.1 m depth.",
        ("daily", "data", "temp_soil_avg_20cm"): "Mean soil temperature at 0.2 m depth.",
        ("daily", "data", "temp_soil_avg_50cm"): "Mean soil temperature at 0.5 m depth.",
        ("daily", "data", "temp_soil_avg_5cm"): "Mean soil temperature at 0.05 m depth.",
        ("daily", "data", "wind_gusts_speed"): "Speed of the strongest gust of the period.",
        ("daily", "data", "wind_speed_10m"): "Mean speed of the wind over the period.",
        ("hourly", "data", "humidity_rel_shelter_avg"): (
            "Relative humidity of the air, the fraction of the moisture it could hold at that temperature."
        ),
        ("hourly", "data", "precip_quantity"): "Depth of precipitation collected over the period.",
        ("hourly", "data", "pressure"): "Air pressure as measured at station height.",
        ("hourly", "data", "short_wave_from_sky_avg"): (
            "Global irradiance on a horizontal surface, reported as power rather than energy."
        ),
        ("hourly", "data", "sun_duration"): "Length of time the sun shone unobstructed.",
        ("hourly", "data", "temp_dry_shelter_avg"): "Mean air temperature at 2 m above ground.",
        ("hourly", "data", "temp_grass_pt100_avg"): "Mean air temperature at 0.05 m above ground.",
        ("hourly", "data", "temp_soil_avg_10cm"): "Mean soil temperature at 0.1 m depth.",
        ("hourly", "data", "temp_soil_avg_20cm"): "Mean soil temperature at 0.2 m depth.",
        ("hourly", "data", "temp_soil_avg_50cm"): "Mean soil temperature at 0.5 m depth.",
        ("hourly", "data", "temp_soil_avg_5cm"): "Mean soil temperature at 0.05 m depth.",
        ("hourly", "data", "wind_gusts_speed"): "Speed of the strongest gust of the period.",
        ("hourly", "data", "wind_speed_10m"): "Mean speed of the wind over the period.",
    },
}
