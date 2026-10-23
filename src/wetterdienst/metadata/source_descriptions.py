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
- KNMI: the ``long_name`` attribute on each variable of the observation NetCDF files, and the longer
  ``description`` attribute where it states the window (hourly ``DD``)
- FMI: the ``observableProperty`` metadata endpoint, ``language=eng``, composed from its label,
  statistical function and aggregation period ("Air temperature. Mean over 1 minute.")
- AEMET: the ``metadatos`` payload that accompanies every response, translated from Spanish
- SMHI: the parameter listing of the metobs API, translated from Swedish
- LHMT: the field list on api.meteo.lt, translated from Lithuanian
- Météo-France: the `*_descriptif_champs*.csv` published beside each resolution, translated from
  French
- Met Office: the MIDAS table dictionaries CEDA publishes, already in English
- DWD POI: the German description line each `<station_id>-BEOB.csv` carries as its third header
  line, translated
- DWD forecast codes: `MetElementDefinition.xml`. It defines the MOSMIX elements, and swsmos reuses
  their names while publishing different units -- MOSMIX `TD` is Kelvin, swsmos `TD` is Celsius -- so
  its wording is used only where it says nothing about the unit: the swsmos rows are the German list of
  variables of its own sheet. Where the catalogue leaves out what a caller needs (`Rad1h` is an energy,
  `RRad1` a share, the codes of `ww`, `ww3`, `WPc*` and `W1W2` are in `mosmix_element_weather_xls.xlsx`),
  or the element is given at a few steps of the day only, the entry says so after the catalogue's words (for the
  elements GH-3136 checked, not for every windowed one)

The AEMET, SMHI, LHMT and Météo-France translations are ours, as are the Geosphere rows
(the German ``description`` of each parameter in ``/v1/station/historical/<resource>/metadata``, with
the window it states: "Maximum der Zehnminutenwerte von 18:10 UTC Vortag - 18:00 UTC aktueller Tag"),
the IMGW rows (the Polish ``*_format.txt`` field lists beside the data in each directory of
``dane_meteorologiczne``, and ``CODZ_publiczne_format.txt`` and ``MIES_publiczne_format.txt`` of
``dane_hydrologiczne``, both under https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/),
IPMA (the field list of the observations section of https://api.ipma.pt/, "temperatura do ar registada a 1.5
metros de altura, média da hora"), the DWD derived rows (the English sheet of each directory of
``derived_germany``, the German one for the daily soil data, which has no English sheet) and the DWD SWSMOS rows
(``swis_swsmos_beschreibung.pdf``). Where a source gives no description of a field, the entry names
what it does give: NWS ``temperature`` and ``dewpoint`` (api.weather.gov documents neither; the
OpenAPI document describes no observation property but ``qualityControl``), the DWD road fields (the
BUFR element they decode from, and the time significance and period the station group writes around
it: DWD publishes no sheet for these files) and WSV (the Pegelonline ``longname`` and unit of the series, which
the documentation does not explain further). Where a
source describes a field in a sentence of its own the entry restates it with a link, and where it
does not but the data does, the entry says what the data shows and the evidence is in a comment
beside it (NWS ``relativehumidity``, which the API computes, and the ASOS wind and gust; IPMA ``radiacao``
is the one the data only suggests). The rest of
this table is meant to be the source's own wording, so that a sentence here can be checked against
what the provider says, but the older entries were written for the docs tables and not every one was
checked against the source; the sub-daily temperature rows listed in GH-2660 were, and so were the
Geosphere, IPMA, NWS, DWD road and WSV ``LT`` rows named above (GH-3136, the first provider group), and
then the rest of the Geosphere rows, the IMGW rows and the Météo-France observation and synop rows (GH-3136,
the second group: the ones translated, or derived from the canonical name, against the source's text), and
the four IPMA rows that read the canonical sentence and the WSV parameters (GH-3136, the third group), and
the DWD POI, MOSMIX, DMO, derived and SWSMOS rows (GH-3136, the fourth group), and the SMHI,
CHMI, LHMT, Environment Agency and Hub'Eau rows (GH-3136, the fifth group). CHMI describes its elements only by
name, unit, height and schedule (``metadata/meta2.csv``) and the Environment Agency by a table of parameter, period,
statistic and unit on its reference page, so what those entries say about a window or a weighting is what the data
show, with the evidence in a comment beside them; SMHI's windows are the ones its own CSV columns give; Hub'Eau
states a unit, an update interval, the instant a value occurred and (for the height) the gauge zero it is relative
to, and the entries say so.
``tests/metadata/test_parameter_statistics.py`` reads a statistic out of an entry only if it is not
in ``DERIVED_DESCRIPTIONS``.

Keyed by metadata model name, then ``(resolution, dataset, name_original)``. Applied by
``build_metadata_model``. A parameter none of the tables here describes reads the canonical sentence
of its quantity, so an entry that repeats that sentence is redundant and
``test_no_description_repeats_the_canonical_one`` fails for it.
"""

# What the IMGW format files leave unsaid about the height of a temperature: the 2 m of the canonical name is the
# shelter convention, and "przy gruncie" is "at the ground", never the 5 cm of `temperature_air_min_0_05m` (GH-3136)
_IMGW_NO_HEIGHT_2M = " The file states no height; the 2 m of the name is the shelter convention."
_IMGW_NO_HEIGHT_GROUND = " The source states no height: the file says at the ground, never 5 cm."

# The hourly soil temperature stamps of the periods whose source is the archive of the eMD (74 stations, up to 1991,
# the terms 01, 04, ..., 22 MEZ) are MEZ, shifted to UTC by the reader (GH-3029)
_SOIL_EMD_ZONE = (
    "The stamps of the periods whose source DWD's Metadaten_Parameter gives as the archive of the eMD (74 East "
    "German stations, up to 1991, the terms 01, 04, ..., 22 MEZ) are MEZ, UTC+1: they are shifted to UTC and their "
    "`quality_flags` carry `zone:mez` (`3,zone:mez`). The other stamps are as written."
)

# Pegelonline serves the same parameters at whatever interval each station records at, so these are
# declared once and expanded over the resolutions below rather than written out five times. The
# resolution names must stay in step with `_EQUIDISTANCE_TO_RESOLUTION` in the provider module; a
# name that drifts out of step leaves its parameters with the canonical sentence in place of the
# source's, which `test_wsv_every_parameter_is_described` catches.
_WSV_PEGEL_RESOLUTIONS = ("1_minute", "5_minutes", "10_minutes", "15_minutes", "hourly")
_HUBEAU_RESOLUTIONS = ("5_minutes", "6_minutes", "10_minutes", "15_minutes", "hourly")

# DMI writes a mean wind direction of 0 where the mean wind speed is 0, at every resolution (GH-2794)
_DMI_MEAN_WIND_DIRECTION = (
    "Direction the wind is blowing from, clockwise from true north. "
    "The source's 0 beside a mean wind speed of 0 (a calm wind) is null."
)

# Pegelonline names each timeseries in German (``longname``), e.g. HL is LUFTFEUCHTE and SIGH
# SIGNIFIKANTEWELLENHÖHE, and says of its measurements: "tagesaktuelle Rohdaten" that "die Wasserstraßen- und
# Schifffahrtsverwaltung des Bundes (WSV) stellt diese ungeprüften Rohdaten bereit"
# (https://www.pegelonline.wsv.de/webservice/ueberblick), one value at every ``equidistance`` minutes of the series
# ("Abstand der Messwerte in Minuten", the REST documentation, which is what the resolution of a request names). It
# explains neither a shortname nor says whether a value is an instant or an aggregate of its interval, so the
# descriptions state the raw data, the interval and the unit the series is published in and no statistic: they were
# "average ... during time scale" and then "a reading" before GH-3136, which the source states of none. The longnames
# and units are those of the stations list of 2026-10-21 (786 stations): a series is named ``X ROHDATEN`` or
# ``X_ROHDATEN`` in most series (not for every shortname: 9 of the 18 served ones have none), and some are named
# ``X``, which the source does not label raw but whose values are the ``measurements.json`` the sentence above
# covers (no station has both for one shortname). The shortnames CL, NIEDERSCHLAG and NIEDERSCHLAGSINTENSITÄT are on
# no station of that list (``stations.json?timeseries=<shortname>`` answers 0 stations for each, as for ``N`` and
# ``NI``), so the three parameters that declared them are gone (GH-3242).
_WSV_PEGEL_RAW = "unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series"
_WSV_PEGEL_PARAMETERS = {
    "DFH": f"Clearance height (DURCHFAHRTSHÖHE), in cm: {_WSV_PEGEL_RAW}.",
    "GRU": f"Groundwater level (GRUNDWASSER ROHDATEN), in m above NHN (the series' unit m+NHN): {_WSV_PEGEL_RAW}.",
    "HL": f"Relative humidity of the air (LUFTFEUCHTE), in %: {_WSV_PEGEL_RAW}.",
    "LF": (
        "Electric conductivity (ELEKTRISCHE_LEITFÄHIGKEIT_ROHDATEN), published in µS/cm or mS/cm and returned in "
        f"µS/cm: {_WSV_PEGEL_RAW}."
    ),
    "LT": (
        "Air temperature (LUFTTEMPERATUR ROHDATEN, or LUFTTEMPERATUR at some stations), in °C; the source states no "
        f"height: {_WSV_PEGEL_RAW}."
    ),
    "MAXH": f"Maximum wave height (MAXIMALEWELLENHÖHE), in cm (the reader also accepts m): {_WSV_PEGEL_RAW}.",
    "O2": (
        f"Oxygen level (SAUERSTOFFGEHALT, or SAUERSTOFFGEHALT ROHDATEN at some stations), in mg/l: {_WSV_PEGEL_RAW}."
    ),
    "PH": f"pH (PH-WERT), a number without unit (the series' unit is --): {_WSV_PEGEL_RAW}.",
    "Q": (f"Discharge (ABFLUSS_ROHDATEN, or ABFLUSS at some stations), in m³/s: {_WSV_PEGEL_RAW}."),
    "R": (
        "Direction of the water current (RICHTUNGSTROM). The series' unit is MGN, which the documentation does not "
        "explain; the value is returned as published, taken as degrees, and may be from magnetic rather than true "
        f"north: {_WSV_PEGEL_RAW}."
    ),
    "SIGH": (f"Significant wave height (SIGNIFIKANTEWELLENHÖHE), in cm (the reader also accepts m): {_WSV_PEGEL_RAW}."),
    "TP": (
        "Wave period (WELLENPERIODE), published in 1/100 s and returned in s (the reader also accepts s): "
        f"{_WSV_PEGEL_RAW}."
    ),
    "TR": (
        "Turbidity (TRÜBUNG, or TRÜBUNG_ROHDATEN at one station), published in FNU, TE/F or NTU, the formazin "
        f"scale, and returned unscaled as NTU: {_WSV_PEGEL_RAW}."
    ),
    "VA": (
        f"Flow speed (FLIESSGESCHWINDIGKEIT_ROHDATEN), published in m/s or cm/s and returned in m/s: {_WSV_PEGEL_RAW}."
    ),
    "W": (
        "Water level (WASSERSTAND ROHDATEN, or WASSERSTAND at two gauges), published in cm or, at some gauges, in m+NN "
        "or m+PNP, and returned in cm. The m+PNP series and the cm series that carry a gauge zero (gaugeZero, the "
        "Pegelnullpunkt) are relative to it, and each gauge zero is that gauge's own. The m+NN series are relative to "
        "NN. 28 cm series (stations list of 2026-10-21) publish no gauge zero and the source states no reference for "
        f"them, so values of different stations do not in general share a reference: {_WSV_PEGEL_RAW}."
    ),
    "WG": f"Wind speed (WINDGESCHWINDIGKEIT), in m/s; the source states no height: {_WSV_PEGEL_RAW}.",
    "WR": f"Wind direction (WINDRICHTUNG), in degrees; the source states no height: {_WSV_PEGEL_RAW}.",
    "WT": (
        f"Water temperature (WASSERTEMPERATUR ROHDATEN, or WASSERTEMPERATUR at some stations), in °C: {_WSV_PEGEL_RAW}."
    ),
}


# The daily temperature file of MIDAS Open mixes the 12 hour rows ending 09:00 (night) and 21:00 (day) with 24 hour rows
# ending 09:00 (2,962 of the 14,334 rows of the daily temperature files of 25 stations, 2022), and the reader stamps
# a row by the date of its `ob_end_time`, the source's 09Z climatological day (GH-3137)
_MO_DAILY_STAMP = (
    "Stamped by the date of ob_end_time (the 09Z climatological day of the source). The file mixes 12 hour rows ending "
    "09:00 and 21:00 with 24 hour rows ending 09:00 (2,962 of 14,334 rows), so a 24 hour 09-09Z row falls on the day "
    "after most of its coverage."
)

# the window of a daily value of the Environment Agency hydrology API (see the comment at its entries)
_EA_DAY = "the 24 hours from 09:00 of the day it is dated to 09:00 of the next (the source gives no zone; read as UTC)"


# The evidence of the DWD claims that the sources do not state (GH-3136, 2026-10-21, key-less):
# - POI: the 974 files of 2026-10-21 for the reporting hours; 25 of the 156 stations that have a DWD 10-minute station
#   within 1.5 km and the previous-day columns at 06 UTC against those 10-minute observations. The previous-day columns
#   equal the temperature extremes (to 0.0), gust (to 0.5 km/h), mean (to 0.11) and sunshine (to 0.04 h, 10 stations) of
#   the previous UTC day, not those of 06 to 06 UTC; the 10-minute stamps are ends of intervals, so the window is
#   23:50 to 23:50 UTC. The hourly columns equal the 10-minute values of the synoptic hour before the stamp, (HH-2):50
#   to (HH-1):50 (precipitation 625 of 625, gust 625 of 625, global and diffuse radiation as J/cm2 * 10000 / 3600 on
#   250 of 250, within 0.89 W/m2, on 10 stations); the clock hour fits worse (precipitation 573, gust 468 of 625).
#   `direct_solar_radiation_last_hour` is sent by 5 French stations and exceeds the global value in 5 of 15 daytime
#   reports; on 2026-10-22 07280 (Dijon) at 09 UTC has 603 against a global 297 W/m2 and 07761 (Ajaccio) 454 against
#   373. With the sun's mean elevation over the hour (20 and 26 degrees at 09 UTC) the direct value times its sine
#   is 209 and 198 there and below the global value in all 6 daytime reports of the two stations, so it is the
#   irradiance perpendicular to the sun's rays (GH-3263, read 2026-10-23, key-less).
#   The reporting hours are those of the files of that day: 12-hour minima at 06, 09 and 18 UTC at most
#   stations, previous-day sunshine at 06 UTC at 123 of 158 stations (all 60 in Germany), at 00 or 03 UTC only at
#   33 stations outside Germany and at every synoptic hour at 2.
# - MOSMIX: the hours that carry an element are those of MOSMIX_L of 8 stations (run of 15 UTC) and MOSMIX_S of 30
#   stations (run of 20 UTC) of 2026-10-21; `RRad1` is `Rad1h` over the extraterrestrial radiation of the hour (6
#   stations, mean difference under 3 points, single hours up to about 20 apart); `W1W2` is two digits (tens never
#   below units) at every station of both runs (MOSMIX_S: all 5648 stations).
# - derived: Monatsgradtage (72.9, 71.6, 62.5), Kuehlgradstunden (2562.3, 2782.8, 2633.5) and the numbers of heating
#   days, cooling hours and days reproduce from DWD's daily and hourly air temperature on stations 00044, 00073, 00078
#   (September 2026); the DUETT hour fits (HH-2):50 to (HH-1):50 best (mean absolute error 4.05 J/cm2, against 15.7
#   for the sheet's other hour and 5.0 for a window 10 minutes off; 4 pseudo-stations, 4799 hours from 2026-09-01).
# - DMO: ICON's `Rad1h`, `RadS3`, `RR1` and `RR3` are not clipped at 0 (2026-10-22, 12 stations of icon and icon-eu
#   and the two latest runs of each: `Rad1h` negative in 411 of 1872 icon-eu values, to -0.15, and 18 of 78 icon
#   steps at 10382, to -0.17; `RadS3` in 273 of 1209, to -0.43; `RR1` in 3 of 1872 icon-eu values, to -0.01; all
#   stations of the icon run of 22 12Z: `Rad1h` to -0.77, `RR1` negative in 2769 of 459,732 values, to -0.10, `RR3`
#   to -0.04, `RadS3` to -0.46); the MOSMIX_L file of station 10382 has no negative `Rad1h` or `RR1c`. The reader
#   returns `RR1` and `RR3` as 0.0 with `raw:` (GH-3263), `Rad1h` and `RadS3` as written.
# - derived: the English sheets in the `cdh_13`, `cdh_16` and `cdh_18` directories of cooling_degreehours (named
#   `..._hdh_..._en.pdf`) are the text of the heating degree days sheet (Monatsgradtage, Heiztage, 15 degree
#   Celsius), so the docs link the English sheet one directory up (`..._cdh_..._en.pdf`), which gives the unit
#   of Kuehlgradstunden as Kelvin * day (the German `hdh` sheet is the cooling one, with the same unit).
SOURCE_DESCRIPTIONS: dict[str, dict[tuple[str, str, str], str]] = {
    # The swagger of the hydrometry API (https://hubeau.eaufrance.fr/api/v2/hydrometrie/api-docs, read 2026-10-22):
    # `date_obs` is the "Date d'observation hydro : date, exprimée en TU, d'occurence de la donnée" and `resultat_obs`
    # the "valeur de la mesure hydrométrique", so a value is dated by the instant it occurred and no mean or interval
    # is stated; the station referential's `altitude_ref_alti_station` is the "altitude du zéro de l'échelle dans le
    # système altimétrique spécifié (en mètres)", of which the swagger says "Cette information permet de convertir
    # des hauteurs relatives en hauteurs absolues sur une échelle", so the height H is relative to the zero of the
    # gauge. 1,478 of the 4,195 stations in service give no such altitude and 215 more name no known system, so the
    # conversion is not possible everywhere (read 2026-10-22). The page of the API
    # (https://hubeau.eaufrance.fr/page/api-hydrometrie, read 2026-10-21 through data.gouv.fr's copy of it) gives the
    # units, "exprimées en mm pour les hauteurs d'eau et en l/s pour les débits", and the update interval, "toutes les
    # 5 à 60 minutes".
    "HubeauMetadata": {
        (resolution, "data", name_original): description
        for resolution in _HUBEAU_RESOLUTIONS
        for name_original, description in (
            (
                "H",
                (
                    "Water height (hauteur d'eau, grandeur H), published in mm and updated by the producer every 5 to "
                    "60 minutes. Each value is dated by the instant it occurred; the source states no mean or "
                    "interval. It is relative to the zero of the station's gauge, so stations share no reference "
                    "level. The station's `gauge_zero` is the altitude of that zero in metres, in the system "
                    "`gauge_zero_datum` names, where the source gives one."
                ),
            ),
            (
                "Q",
                (
                    "Flow (débit, grandeur Q), published in l/s and updated by the producer every 5 to 60 minutes. "
                    "Each value is dated by the instant it occurred; the source states no mean or interval."
                ),
            ),
        )
    },
    # CHMI describes its elements only by name, unit, height and schedule: ``metadata/meta2.csv`` (NAME, UN_DESCRIPTION,
    # HEIGHT, SCHEDULE, in Czech: "Teplota" "°C" 2 "AVG,06:00,13:00,20:00") and, for the monthly and annual files, the
    # TIMEFUNCTION and MDFUNCTION of each row; Klimatologicka_data_popis.pdf says only that the monthly and annual
    # characteristics ("průměr, úhrn, maximum, minimum") are derived from the daily ones. What is more than that was
    # read off the data of 2026-10-21 and is said where the descriptions state it:
    # - the daily mean of the temperature ("AVG") is (T06 + T13 + 2 * T20) / 4 on every one of 75,261 days of five
    #   stations (the plain average of the three also matches on 8,084 of them); the humidity, pressure and wind speed
    #   ("AVG") are the plain average (62,763 of 62,763, 30,487 of 30,487 and 58,765 of 58,765 days). Humidity is whole
    #   percent, so a day counts within 0.5. All 260 active daily T series list the terms 06:00, 13:00 and 20:00, which
    #   is what the descriptions say; 124 older series of 41 stations list other term sets (05:00, 13:00, 21:00 for 30
    #   of them), for which the weighting was not checked;
    # - the monthly and annual temperature "AVG"/"AVG" is the mean of the daily "AVG" (1,191 of 1,191 months, 99 of 99
    #   years of Cheb), TMA "20:00"/"AVG" the mean of the daily values (1,171 of 1,171 months, 97 of 97 years; TMI
    #   was not counted), and SRA "06:00"/"SUM" their sum (780 of 780 months, 65 of 65 years);
    # - the 10 minute wind speed F is not the 10 minute mean, which is the element Fprum (F equals Fprum in 1,311 of
    #   13,248 readings of Cheb, Jun to Aug 2024); P is the pressure at the station: 956.0 hPa at Cheb (483 m) where
    #   the hourly SYNOP P_hm (sea level) is 1012.5 for the same hour;
    # - the daily maximum and minimum temperature (the source stamps them 20:00 and the reader dates them by that
    #   day) are the extremes of the 24 hours up to 20:00 UTC of that day: of the 10 minute TMA/TMI readings of Cheb
    #   (Jun to Jul 2024) that window reproduces the daily value on 54 and 53 of 55 days, the best of the hourly ends
    #   (a window shifted by 10 minutes fits more days, so the end is known to within 10 minutes: the 10 minute
    #   stamp convention is not stated);
    # - the daily precipitation (the source stamps it 06:00) is the sum of the 10 minute SRA10M stamped from 06:10 of
    #   that day to 06:00 of the next, i.e. the 24 hours that begin at the source's stamp, not those that end at it:
    #   39 of 39, 30 of 30 and 19 of 21 wet days at three stations, the best window of all (neighbours within 20
    #   minutes tie); the hourly SRA1H is the sum of the six 10 minute values stamped up to the hour (60 of 60, 76 of
    #   76 and 51 of 51 wet hours);
    # - not settled, and said so: the window of the daily wind maximum (a maximum does not pin the end) and of the
    #   daily sunshine duration (the 10 minute SSV10M sums reproduce it by no window: at best 23, 28 and 33 of 56 days).
    # HEIGHT is exactly 2 at 257 of the 299 active stations' 10 minute temperature (the rest 1.88 to 6.66) and exactly
    # 10 at 161 of 210 for the wind speed (the rest 3 to 26), so the heights in the descriptions are the conventions of
    # the names, not a stated fact for every station
    "ChmiObservationMetadata": {
        ("10_minutes", "data", "F"): (
            "Wind speed at 10 m by convention (the source gives each series its own height: 10 m at most stations), "
            'one value every ten minutes. The source states no statistic; its "Rychlost prům" (prům = průměr) is '
            "the separate element Fprum."
        ),
        ("10_minutes", "data", "H"): (
            "Relative humidity at 2 m, one value every ten minutes. The source states no statistic."
        ),
        ("10_minutes", "data", "P"): (
            "Air pressure at station level (the hourly sea-level pressure is the separate element P_hm), one value "
            "every ten minutes. The source states no statistic."
        ),
        ("10_minutes", "data", "T"): (
            "Air temperature at 2 m, one value every ten minutes. The source states no statistic; it publishes the "
            "10 minute maximum and minimum separately, as TMA and TMI."
        ),
        ("annual", "data", "SRA"): (
            "Precipitation, the total of the year: the sum of the daily values (the source's SRA with the term 06:00)."
        ),
        ("annual", "data", "T"): (
            "Air temperature at 2 m, the mean of the year: the mean of the daily means (T06 + T13 + 2 T20) / 4."
        ),
        ("annual", "data", "TMA"): (
            "Annual mean of the daily maximum air temperature at 2 m, the 24 hours up to 20:00 UTC of each day."
        ),
        ("annual", "data", "TMI"): (
            "Annual mean of the daily minimum air temperature at 2 m, the 24 hours up to 20:00 UTC of each day."
        ),
        ("daily", "data", "F"): (
            "Wind speed at 10 m by convention (the source gives each series its own height: 10 m at most stations), "
            "the daily mean: the plain average of the observations at 06:00, 13:00 and 20:00 UTC."
        ),
        ("daily", "data", "Fmax"): (
            "Maximum wind speed at 10 m by convention (the source gives each series its own height: 10 m at most "
            "stations) of the day it is dated. The source states no window and calls it the maximum speed, not a gust."
        ),
        ("daily", "data", "H"): (
            "Relative humidity at 2 m, the daily mean: the plain average of the observations at 06:00, 13:00 and "
            "20:00 UTC."
        ),
        ("daily", "data", "P"): (
            "Air pressure at station level, the daily mean: the plain average of the observations at 06:00, 13:00 "
            "and 20:00 UTC."
        ),
        ("daily", "data", "SCE"): "Snow depth at ground level, a reading at 06:00 UTC.",
        ("daily", "data", "SRA"): (
            "Precipitation, the source's 06:00 UTC term: the total of the 24 hours from 06:00 UTC of the day it is "
            "dated to 06:00 UTC of the next day. The source states no window."
        ),
        ("daily", "data", "SSV"): (
            "Sunshine duration of the day it is dated, published in hours. The source states no window."
        ),
        ("daily", "data", "T"): (
            "Air temperature at 2 m, the daily mean: the observations at 06:00, 13:00 and 20:00 UTC, the last counted "
            "twice, (T06 + T13 + 2 T20) / 4, not their plain average."
        ),
        ("daily", "data", "TMA"): (
            "Maximum air temperature at 2 m, the source's 20:00 UTC term: the maximum of the 24 hours up to 20:00 UTC "
            "of the day it is dated. The source states no window."
        ),
        ("daily", "data", "TMI"): (
            "Minimum air temperature at 2 m, the source's 20:00 UTC term: the minimum of the 24 hours up to 20:00 UTC "
            "of the day it is dated. The source states no window."
        ),
        ("hourly", "data", "P"): (
            "Air pressure at station level, from the hourly SYNOP report (the sea-level pressure is the separate "
            "element P_hm)."
        ),
        ("hourly", "data", "SRA1H"): (
            "Precipitation total of the hour up to the stamp. The source states no window; the 10 minute "
            "precipitation values stamped up to the hour add up to it (taking those to be stamped at the end of "
            "their interval, which the source does not state)."
        ),
        ("hourly", "data", "Td"): "Dew point temperature at 2 m, from the hourly SYNOP report.",
        ("monthly", "data", "SRA"): (
            "Precipitation, the total of the month: the sum of the daily values (the source's SRA with the term 06:00)."
        ),
        ("monthly", "data", "T"): (
            "Air temperature at 2 m, the mean of the month: the mean of the daily means (T06 + T13 + 2 T20) / 4."
        ),
        ("monthly", "data", "TMA"): (
            "Monthly mean of the daily maximum air temperature at 2 m, the 24 hours up to 20:00 UTC of each day."
        ),
        ("monthly", "data", "TMI"): (
            "Monthly mean of the daily minimum air temperature at 2 m, the 24 hours up to 20:00 UTC of each day."
        ),
    },
    "DwdSwsmosMetadata": {
        ("hourly", "data", "R650"): (
            "Probability of more than 5 mm of liquid and solid precipitation in the last 6 hours, in % (DWD: "
            '"Niederschlag flüssig+fest mehr als 5mm der letzten 6 Stunden Wahrscheinlichkeit"; from DWD\'s MOS).'
        ),
        ("hourly", "data", "RC"): (
            "Condition of the road surface, as a code: 1 dry, 2 moist, 3 snow, 4 hoar frost, 5 freezing wetness, "
            "6 glaze ice, which are not the BUFR codes of the road stations' `road_surface_condition` (0 dry, 1 "
            'moist, 2 wet, ...) (DWD: "Straßenzustand", from the METRo road weather model driven by DWD\'s MOS '
            "values)."
        ),
        ("hourly", "data", "RR6"): (
            'Liquid precipitation of the last 6 hours, accumulated, in mm (DWD: "Niederschlag flüssig der '
            "letzten 6 Stunden akkumuliert\"; from DWD's MOS)."
        ),
        ("hourly", "data", "RRL1c"): (
            'Liquid precipitation of the last hour, in mm (DWD: "Niederschlag flüssig der letzten Stunde", from '
            "DWD's MOS)."
        ),
        ("hourly", "data", "TD"): (
            "Dew point temperature (DWD: \"Taupunkttemperatur\", from DWD's MOS, model output statistics); DWD's "
            "sheet states no height."
        ),
        ("hourly", "data", "TL"): (
            "Air temperature (DWD: \"Lufttemperatur\", from DWD's MOS, model output statistics); DWD's sheet "
            "states no height."
        ),
        ("hourly", "data", "TS"): (
            'Temperature of the road surface (DWD: "Temperatur der Fahrbahnoberfläche"), from the METRo road '
            "weather model driven by DWD's MOS values."
        ),
        ("hourly", "data", "WWL6"): (
            'Probability of liquid precipitation in the last 6 hours, in % (DWD: "Niederschlag flüssig der '
            "letzten 6 Stunden Wahrscheinlichkeit\"; from DWD's MOS)."
        ),
    },
    "DwdPoiMetadata": {
        (
            "hourly",
            "data",
            "daily_mean_of_temperature_previous_day",
        ): "Mean air temperature at 2 m above ground on the previous day (UTC), reported at 06 UTC.",
        ("hourly", "data", "depth_of_new_snow"): (
            'Depth of new snow (DWD: "Neuschneehoehe"). The file states no period; it is reported in the 06 UTC '
            "report only."
        ),
        ("hourly", "data", "dew_point_temperature_at_2_meter_above_ground"): (
            "Dew point temperature at 2 m above ground."
        ),
        ("hourly", "data", "diffuse_solar_radiation_last_hour"): (
            'Diffuse short-wave irradiance of the preceding hour in W/m2 (DWD: "Diffuse Strahlung (letzte '
            'Stunde)"): the energy of that hour divided by 3600 s, not a reading at one moment.'
        ),
        ("hourly", "data", "direct_solar_radiation_last_hour"): (
            'Direct short-wave irradiance of the preceding hour in W/m2 (DWD: "Direkte Strahlung (letzte '
            'Stunde)", no surface stated). It exceeds the global irradiance in some reports, so it is not the '
            "component on a horizontal surface but the irradiance on a plane perpendicular to the sun's rays (direct "
            "normal irradiance, WMO-No. 8 chapter 7.2): multiplied by the cosine of the solar zenith angle it stays "
            "below the global irradiance."
        ),
        ("hourly", "data", "dry_bulb_temperature_at_2_meter_above_ground"): "Air temperature at 2 m above ground.",
        ("hourly", "data", "evaporation/evapotranspiration_last_24_hours"): (
            'Evaporation and evapotranspiration in the preceding 24 hours (DWD: "Evaporation (vergangene 24 '
            'Stunden)"), reported almost only at 06 UTC.'
        ),
        ("hourly", "data", "global_radiation_last_hour"): (
            'Global irradiance of the preceding hour in W/m2 (DWD: "Globalstrahlung (letzte Stunde)"): the '
            "energy of that hour divided by 3600 s, not a reading at one moment."
        ),
        ("hourly", "data", "height_of_base_of_lowest_cloud_above_station"): (
            "Height above the station of the base of the lowest cloud."
        ),
        ("hourly", "data", "maximum_of_10_minutes_mean_of_wind_speed_for_previous_day"): (
            'Highest 10-minute mean wind speed in the 6 hours up to the stamp. DWD names the column "previous day", '
            "but it is carried at 00, 06, 12 and 18 UTC and is the maximum of the 6 hourly values up to the stamp."
        ),
        (
            "hourly",
            "data",
            "maximum_of_temperature_for_previous_day",
        ): "Maximum air temperature at 2 m above ground on the previous day (UTC), reported at 06 UTC.",
        ("hourly", "data", "maximum_temperature_last_12_hours_2_meters_above_ground"): (
            "Maximum air temperature at 2 m above ground in the preceding 12 hours, reported mostly at 06 and 18 UTC."
        ),
        ("hourly", "data", "maximum_wind_speed_as_10_minutes_mean_during_last_hour"): (
            "Highest 10-minute mean wind speed in the preceding hour."
        ),
        (
            "hourly",
            "data",
            "maximum_wind_speed_during_last_6_hours",
        ): "Strongest gust in the preceding 6 hours, reported at 00, 06, 12 and 18 UTC.",
        (
            "hourly",
            "data",
            "maximum_wind_speed_for_previous_day",
        ): "Strongest gust on the previous day (UTC), reported at 06 UTC.",
        ("hourly", "data", "maximum_wind_speed_last_hour"): "Strongest gust in the preceding hour.",
        ("hourly", "data", "mean_wind_direction_during_last_10 min_at_10_meters_above_ground"): (
            "Mean wind direction over the last 10 minutes, at 10 m above ground. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
        ("hourly", "data", "mean_wind_speed_during last_10_min_at_10_meters_above_ground"): (
            "Mean wind speed over the last 10 minutes, at 10 m above ground."
        ),
        (
            "hourly",
            "data",
            "minimum_of_temperature_at_5_cm_above_ground_for_previous_day",
        ): "Minimum air temperature at 5 cm above ground on the previous day (UTC), reported at 06 UTC.",
        (
            "hourly",
            "data",
            "minimum_of_temperature_for_previous_day",
        ): "Minimum air temperature at 2 m above ground on the previous day (UTC), reported at 06 UTC.",
        ("hourly", "data", "minimum_temperature_last_12_hours_2_meters_above_ground"): (
            "Minimum air temperature at 2 m above ground in the preceding 12 hours, reported mostly at 06, 09 "
            "and 18 UTC."
        ),
        ("hourly", "data", "minimum_temperature_last_12_hours_5_cm_above_ground"): (
            "Minimum air temperature at 5 cm above ground in the preceding 12 hours, reported mostly at 06, 09 "
            "and 18 UTC."
        ),
        ("hourly", "data", "past_weather_1"): (
            'Coded past weather of a synoptic report (DWD: "vergangenes Wetter 1"). The values, 0 to 18, fit '
            "BUFR 0 20 004: 0 to 9 of WMO code table 4561 for a manned station, 10 to 19 (WMO code table 4531 "
            "plus 10) for an automatic one. Reported at the eight synoptic hours. DWD states no period; the "
            "WMO's is the 6 hours before the reports of 00, 06, 12 and 18 UTC and the 3 hours before those of "
            "03, 09, 15 and 21 UTC."
        ),
        ("hourly", "data", "past_weather_2"): (
            'Second coded past weather of a synoptic report (DWD: "vergangenes Wetter 2"; BUFR 0 20 005, coded '
            "as `past_weather_1`), reported at the eight synoptic hours. DWD states no period either (the WMO's, "
            "as for `past_weather_1`)."
        ),
        (
            "hourly",
            "data",
            "precipitation_amount_last_24_hours",
        ): "Precipitation collected in the preceding 24 hours, reported mostly at 06 UTC.",
        ("hourly", "data", "precipitation_amount_last_3_hours"): (
            "Precipitation collected in the preceding 3 hours, reported at the eight synoptic hours (00, 03, ... "
            "21 UTC)."
        ),
        (
            "hourly",
            "data",
            "precipitation_amount_last_6_hours",
        ): "Precipitation collected in the preceding 6 hours, reported at 00, 06, 12 and 18 UTC.",
        ("hourly", "data", "precipitation_amount_last_hour"): "Precipitation collected in the preceding hour.",
        (
            "hourly",
            "data",
            "precipitation_last_12_hours",
        ): "Precipitation collected in the preceding 12 hours, reported mostly at 06 and 18 UTC.",
        ("hourly", "data", "present_weather"): (
            "Coded present weather at the time of observation, on DWD's 1..31 scale."
        ),
        ("hourly", "data", "pressure_reduced_to_mean_sea_level"): "Air pressure reduced to mean sea level.",
        ("hourly", "data", "relative_humidity"): "Relative humidity of the air.",
        ("hourly", "data", "sea/water_temperature"): "Temperature of the sea or lake water at the station.",
        ("hourly", "data", "temperature_at_5_cm_above_ground"): "Air temperature at 5 cm above ground.",
        ("hourly", "data", "total_time_of_sunshine_during_last_hour"): (
            "Length of time the sun shone in the preceding hour, in minutes; it agrees with the sum of DWD's "
            "10-minute sunshine duration of that hour."
        ),
        ("hourly", "data", "total_time_of_sunshine_past_day"): (
            "Length of time the sun shone on the previous day (UTC at DWD's stations, checked at 06 UTC), in "
            "hours, reported at 06 UTC at most stations; some stations outside Germany report it at 00 or 03 UTC "
            "instead, with no day stated."
        ),
    },
    "DwdDerivedMetadata": {
        ("hourly", "radiation_global", "qn_952"): "Quality flag.",
        ("hourly", "sunshine_duration", "qn_952"): "Quality flag.",
        ("daily", "soil", "bfgl01_ag"): (
            "Soil moisture under grass on loamy silt at 0 to 10 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfgl02_ag"): (
            "Soil moisture under grass on loamy silt at 10 to 20 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfgl03_ag"): (
            "Soil moisture under grass on loamy silt at 20 to 30 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfgl04_ag"): (
            "Soil moisture under grass on loamy silt at 30 to 40 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfgl05_ag"): (
            "Soil moisture under grass on loamy silt at 40 to 50 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfgl06_ag"): (
            "Soil moisture under grass on loamy silt at 50 to 60 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfgl_ag"): (
            "Soil moisture under grass on loamy silt at 0 to 60 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfgs_ag"): (
            "Soil moisture under grass on sand at 0 to 60 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfml_ag"): (
            "Soil moisture under maize on loamy silt at 0 to 60 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfms_ag"): (
            "Soil moisture under maize on sand at 0 to 60 cm depth, in % nFK (percent of the usable field "
            "capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfwl_ag"): (
            "Soil moisture under winter cereals on loamy silt at 0 to 60 cm depth, in % nFK (percent of the "
            "usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "bfws_ag"): (
            "Soil moisture under winter cereals on sand at 0 to 60 cm depth, in % nFK (percent of the usable "
            "field capacity), calculated with the AMBAV model, not measured."
        ),
        ("daily", "soil", "ts05"): (
            "Mean soil temperature of a typical bare soil at 5 cm depth, calculated with the AMBETI model from "
            "observed weather, not measured."
        ),
        ("daily", "soil", "ts10"): (
            "Mean soil temperature of a typical bare soil at 10 cm depth, calculated with the AMBETI model from "
            "observed weather, not measured."
        ),
        ("daily", "soil", "ts100"): (
            "Mean soil temperature of a typical bare soil at 1 m depth, calculated with the AMBETI model from "
            "observed weather, not measured."
        ),
        ("daily", "soil", "ts20"): (
            "Mean soil temperature of a typical bare soil at 20 cm depth, calculated with the AMBETI model from "
            "observed weather, not measured."
        ),
        ("daily", "soil", "ts50"): (
            "Mean soil temperature of a typical bare soil at 50 cm depth, calculated with the AMBETI model from "
            "observed weather, not measured."
        ),
        ("daily", "soil", "tsls05"): (
            "Mean soil temperature at 5 cm depth in unvegetated loamy sand (BEKLIMA), calculated with the AMBETI "
            "model, not measured."
        ),
        ("daily", "soil", "tssl05"): (
            "Mean soil temperature at 5 cm depth in unvegetated loamy silt (BEKLIMA), calculated with the AMBETI "
            "model, not measured."
        ),
        ("daily", "soil", "vpgfao"): (
            "Potential evapotranspiration over grass (FAO method), in mm, a daily sum (AMBAV model). DWD prefers "
            "it to Haude's method because it takes many more influencing factors into account."
        ),
        (
            "daily",
            "soil",
            "vpgh",
        ): "Potential evapotranspiration over grass (Haude method), in mm, a daily sum (AMBAV model).",
        ("daily", "soil", "vrgl_ag"): (
            "Real (actual) evaporation over grass on loamy silt, in mm, a daily sum calculated with the AMBAV model."
        ),
        ("daily", "soil", "vrgs_ag"): (
            "Real (actual) evaporation over grass on sand, in mm, a daily sum calculated with the AMBAV model."
        ),
        ("daily", "soil", "vrml_ag"): (
            "Real (actual) evaporation over maize on loamy silt, in mm, a daily sum calculated with the AMBAV model."
        ),
        ("daily", "soil", "vrms_ag"): (
            "Real (actual) evaporation over maize on sand, in mm, a daily sum calculated with the AMBAV model."
        ),
        ("daily", "soil", "vrwl_ag"): (
            "Real (actual) evaporation over winter cereals on loamy silt, in mm, a daily sum calculated with the "
            "AMBAV model."
        ),
        ("daily", "soil", "vrws_ag"): (
            "Real (actual) evaporation over winter cereals on sand, in mm, a daily sum calculated with the AMBAV model."
        ),
        ("daily", "soil", "zfumi"): "Frost penetration depth at midday on unvegetated ground, in cm (AMBETI model).",
        (
            "daily",
            "soil",
            "ztkmi",
        ): "Thawing layer at midday under vegetation (the sheet: unter Bestand; BEKLIMA), in cm.",
        ("daily", "soil", "ztumi"): "Thawing layer at midday under unvegetated ground (BEKLIMA), in cm.",
        ("hourly", "radiation_global", "fg_duett"): (
            "Global radiation (the sheet: surface irradiance, hourly mean surface downwelling shortwave "
            "radiation) of a DWD pseudo-station, in J/cm2: derived from gridded satellite and station data "
            "(DUETT) with a topography correction, not measured at the station. The sheet calls the stamp the "
            "end of the synoptic hour and gives that hour as (HH-1):50 to HH:50 in one place and (HH-2):50 to "
            "(HH-1):50 in another; DWD's 10-minute station data fit (HH-2):50 to (HH-1):50 best."
        ),
        ("hourly", "radiation_global", "fg_un_duett"): (
            "Uncertainty of the hourly global radiation of the pseudo-station, in J/cm2 (the sheet: estimated "
            "from the differences between the satellite and station data, the variability around the point and "
            "the geometric uncertainty of the cloud observation)."
        ),
        ("hourly", "sunshine_duration", "sd_un_duett"): (
            "Uncertainty of the hourly sunshine duration of the pseudo-station, in minutes (estimated in the "
            "same way as that of the global radiation)."
        ),
        ("hourly", "sunshine_duration", "sd_duett"): (
            "Sunshine duration of a DWD pseudo-station in the hour, in minutes: derived from gridded satellite "
            "and station data (DUETT), not measured at the station. The sheet calls the stamp the end of the "
            "synoptic hour and gives that hour as (HH-1):50 to HH:50 in one place and (HH-2):50 to (HH-1):50 in "
            "another; DWD's 10-minute station data fit (HH-2):50 to (HH-1):50 best."
        ),
        ("monthly", "climate_correction_factor", "KF"): (
            "Climate factor (KF) of a delivery postal code for the weather adjustment of energy consumption, "
            "relative to the reference location Potsdam (the test reference years TRY 2011), for the 12 months "
            "starting at the timestamp: KF = G(TRY, P) / G, the mean annual degree days of the reference station "
            "Potsdam computed with its test reference years (3666.8) over the annual degree days of the postal "
            "code in those 12 months (DWD's climate-factor page; the sheet states no formula)."
        ),
        ("monthly", "cooling_degreehours_13", "Anzahl Kuehlstunden"): (
            "Number of hours of the month with a positive difference between the hourly air temperature and the "
            "reference temperature of the dataset (13, 16 or 18 degree Celsius)."
        ),
        ("monthly", "cooling_degreehours_13", "Anzahl Stunden"): "number of hours per month",
        ("monthly", "cooling_degreehours_13", "Kuehlgradstunden"): (
            "Cooling degree hours: the sum over the hours of the month of the hourly air temperature minus the "
            "reference temperature of the dataset (13, 16 or 18 degree Celsius), for the hours above it, in K*h. "
            "The sheet gives the unit as Kelvin * day, which the values rule out (for example 2,562.3 for 545 "
            "cooling hours at the reference of 13 degree Celsius, Grossenkneten, September 2026)."
        ),
        ("monthly", "cooling_degreehours_16", "Anzahl Kuehlstunden"): (
            "Number of hours of the month with a positive difference between the hourly air temperature and the "
            "reference temperature of the dataset (13, 16 or 18 degree Celsius)."
        ),
        ("monthly", "cooling_degreehours_16", "Anzahl Stunden"): "number of hours per month",
        ("monthly", "cooling_degreehours_16", "Kuehlgradstunden"): (
            "Cooling degree hours: the sum over the hours of the month of the hourly air temperature minus the "
            "reference temperature of the dataset (13, 16 or 18 degree Celsius), for the hours above it, in K*h. "
            "The sheet gives the unit as Kelvin * day, which the values rule out (for example 2,562.3 for 545 "
            "cooling hours at the reference of 13 degree Celsius, Grossenkneten, September 2026)."
        ),
        ("monthly", "cooling_degreehours_18", "Anzahl Kuehlstunden"): (
            "Number of hours of the month with a positive difference between the hourly air temperature and the "
            "reference temperature of the dataset (13, 16 or 18 degree Celsius)."
        ),
        ("monthly", "cooling_degreehours_18", "Anzahl Stunden"): "number of hours per month",
        ("monthly", "cooling_degreehours_18", "Kuehlgradstunden"): (
            "Cooling degree hours: the sum over the hours of the month of the hourly air temperature minus the "
            "reference temperature of the dataset (13, 16 or 18 degree Celsius), for the hours above it, in K*h. "
            "The sheet gives the unit as Kelvin * day, which the values rule out (for example 2,562.3 for 545 "
            "cooling hours at the reference of 13 degree Celsius, Grossenkneten, September 2026)."
        ),
        ("monthly", "heating_degreedays", "Anzahl Heiztage"): (
            "number of days with daily mean air temperature less than 15 degree Celsius"
        ),
        ("monthly", "heating_degreedays", "Anzahl Tage"): (
            "number of available values of mean daily air temperatures per month"
        ),
        ("monthly", "heating_degreedays", "Monatsgradtage"): (
            "Degree days of the month (VDI 3807 part 1), in K*day: the sum, over the days with a daily mean air "
            "temperature below 15 degree Celsius, of 20 degree Celsius minus the daily mean (20 degree Celsius "
            "is the mean room temperature the file header states). Only given where every daily value of the "
            "month is available."
        ),
        ("monthly", "soil", "maximum von zfumi"): (
            "Maximum in the month of the frost penetration depth at midday on unvegetated ground, in cm (AMBETI model)."
        ),
        ("monthly", "soil", "maximum von ztkmi"): (
            "Maximum in the month of the thawing layer at midday under vegetation (the sheet: unter Bestand; "
            "BEKLIMA), in cm."
        ),
        (
            "monthly",
            "soil",
            "maximum von ztumi",
        ): "Maximum in the month of the thawing layer at midday under unvegetated ground (BEKLIMA), in cm.",
        ("monthly", "soil", "mittel von bfgl01_ag"): (
            "Monthly mean of the daily soil moisture under grass on loamy silt at 0 to 10 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfgl02_ag"): (
            "Monthly mean of the daily soil moisture under grass on loamy silt at 10 to 20 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfgl03_ag"): (
            "Monthly mean of the daily soil moisture under grass on loamy silt at 20 to 30 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfgl04_ag"): (
            "Monthly mean of the daily soil moisture under grass on loamy silt at 30 to 40 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfgl05_ag"): (
            "Monthly mean of the daily soil moisture under grass on loamy silt at 40 to 50 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfgl06_ag"): (
            "Monthly mean of the daily soil moisture under grass on loamy silt at 50 to 60 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfgl_ag"): (
            "Monthly mean of the daily soil moisture under grass on loamy silt at 0 to 60 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfgs_ag"): (
            "Monthly mean of the daily soil moisture under grass on sand at 0 to 60 cm depth, in % nFK (percent "
            "of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfml_ag"): (
            "Monthly mean of the daily soil moisture under maize on loamy silt at 0 to 60 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfms_ag"): (
            "Monthly mean of the daily soil moisture under maize on sand at 0 to 60 cm depth, in % nFK (percent "
            "of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfwl_ag"): (
            "Monthly mean of the daily soil moisture under winter cereals on loamy silt at 0 to 60 cm depth, in "
            "% nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von bfws_ag"): (
            "Monthly mean of the daily soil moisture under winter cereals on sand at 0 to 60 cm depth, in % nFK "
            "(percent of the usable field capacity), calculated with the AMBAV model, not measured."
        ),
        ("monthly", "soil", "mittel von ts05"): (
            "Monthly mean of the daily mean soil temperature of a typical bare soil at 5 cm depth (AMBETI model, "
            "not measured)."
        ),
        ("monthly", "soil", "mittel von ts10"): (
            "Monthly mean of the daily mean soil temperature of a typical bare soil at 10 cm depth (AMBETI "
            "model, not measured)."
        ),
        ("monthly", "soil", "mittel von ts100"): (
            "Monthly mean of the daily mean soil temperature of a typical bare soil at 1 m depth (AMBETI model, "
            "not measured)."
        ),
        ("monthly", "soil", "mittel von ts20"): (
            "Monthly mean of the daily mean soil temperature of a typical bare soil at 20 cm depth (AMBETI "
            "model, not measured)."
        ),
        ("monthly", "soil", "mittel von ts50"): (
            "Monthly mean of the daily mean soil temperature of a typical bare soil at 50 cm depth (AMBETI "
            "model, not measured)."
        ),
        ("monthly", "soil", "mittel von tsls05"): (
            "Monthly mean of the daily mean soil temperature at 5 cm depth in unvegetated loamy sand (BEKLIMA, "
            "AMBETI model, not measured)."
        ),
        ("monthly", "soil", "mittel von tssl05"): (
            "Monthly mean of the daily mean soil temperature at 5 cm depth in unvegetated loamy silt (BEKLIMA, "
            "AMBETI model, not measured)."
        ),
        (
            "monthly",
            "soil",
            "summe von vpgfao",
        ): "Monthly sum of the daily potential evapotranspiration over grass (FAO method), in mm.",
        (
            "monthly",
            "soil",
            "summe von vpgh",
        ): "Monthly sum of the daily potential evapotranspiration over grass (Haude method), in mm.",
        ("monthly", "soil", "summe von vrgl_ag"): (
            "Monthly sum of the daily real (actual) evaporation over grass on loamy silt, in mm (AMBAV model)."
        ),
        (
            "monthly",
            "soil",
            "summe von vrgs_ag",
        ): "Monthly sum of the daily real (actual) evaporation over grass on sand, in mm (AMBAV model).",
        ("monthly", "soil", "summe von vrml_ag"): (
            "Monthly sum of the daily real (actual) evaporation over maize on loamy silt, in mm (AMBAV model)."
        ),
        (
            "monthly",
            "soil",
            "summe von vrms_ag",
        ): "Monthly sum of the daily real (actual) evaporation over maize on sand, in mm (AMBAV model).",
        ("monthly", "soil", "summe von vrwl_ag"): (
            "Monthly sum of the daily real (actual) evaporation over winter cereals on loamy silt, in mm (AMBAV model)."
        ),
        ("monthly", "soil", "summe von vrws_ag"): (
            "Monthly sum of the daily real (actual) evaporation over winter cereals on sand, in mm (AMBAV model)."
        ),
    },
    "DwdDmoMetadata": {
        ("hourly", "icon", "dd"): "Wind direction",
        ("hourly", "icon", "ff"): "Wind speed",
        ("hourly", "icon", "fx3"): "Maximum wind gust within the last 3 hours",
        ("hourly", "icon", "n"): "Total cloud cover",
        ("hourly", "icon", "neff"): "Effective cloud cover",
        ("hourly", "icon", "nh"): "High cloud cover (>7 km)",
        ("hourly", "icon", "nl"): "Low cloud cover (lower than 2 km).",
        ("hourly", "icon", "nm"): "Midlevel cloud cover (2-7 km)",
        ("hourly", "icon", "pppp"): "Surface pressure, reduced",
        ("hourly", "icon", "rad1h"): (
            "Global Irradiance, as the energy of the last hour: the DMO values are in J/cm2 (the file states no "
            "unit; they are about a tenth of the MOSMIX kJ/m2 number for the same hour). Direct model output, "
            "not clipped at 0: in the night hours it is often a little below it (mostly above -0.2 J/cm2, at a "
            "few stations to about -0.8) and is returned as written."
        ),
        ("hourly", "icon", "radl3"): "Long wave radiation balance during the last 3 hours",
        ("hourly", "icon", "rads3"): (
            "Short wave radiation balance during the last 3 hours. Direct model output, not clipped at 0: in the "
            "night hours it is often a little below it (to about -0.4 J/cm2) and is returned as written."
        ),
        ("hourly", "icon", "rr1"): (
            "Total precipitation during the last hour. ICON writes a little below 0 now and then (to about -0.1 mm); "
            "that is returned as 0.0, with the number kept as `raw:` in `quality_flags`."
        ),
        ("hourly", "icon", "rr3"): (
            "Total precipitation during the last 3 hours. ICON writes a little below 0 now and then (to about "
            "-0.04 mm); that is returned as 0.0, with the number kept as `raw:` in `quality_flags`."
        ),
        ("hourly", "icon", "rrs1c"): "Snow-Rain-Equivalent during the last hour",
        ("hourly", "icon", "rrs3c"): "Snow-Rain-Equivalent during the last 3 hours",
        ("hourly", "icon", "t5cm"): "Temperature 5cm above surface",
        ("hourly", "icon", "td"): "Dewpoint 2m above surface",
        ("hourly", "icon", "tn"): "Minimum temperature - within the last 12 hours",
        ("hourly", "icon", "ttt"): "Temperature 2m above surface",
        ("hourly", "icon", "tx"): "Maximum temperature - within the last 12 hours",
        ("hourly", "icon", "w1w2"): (
            "Past weather during the last 6 hours, as a class of DWD's MOSMIX list (the DMO values fit it): 9 "
            "thunderstorm, 8 shower, 7 snow or rain and snow mixed, 6 rain, 5 drizzle, 4 fog, 3 to 0 the "
            "effective cloud cover (at least 7/8, 4.6/8 to 6/8, 1/8 to 4.5/8, below 1/8). DWD says of MOSMIX "
            "that 0 to 3 are not reliable and mean no thunderstorm, no precipitation and no fog. Given at 00, "
            "06, 12 and 18 UTC."
        ),
        ("hourly", "icon", "ww"): (
            "Significant Weather, as a code of DWD's MOSMIX list of codes (DWD publishes it as "
            "mosmix_element_weather_xls.xlsx; the DMO values fit it): 95 (thunderstorm) has the highest "
            "priority, then freezing drizzle and rain, showers, snowfall, rain and snow, drizzle, rain and fog, "
            "down to 3 to 0 (cloud development)."
        ),
        ("hourly", "icon_eu", "dd"): "Wind direction",
        ("hourly", "icon_eu", "ff"): "Wind speed",
        ("hourly", "icon_eu", "fx3"): "Maximum wind gust within the last 3 hours",
        ("hourly", "icon_eu", "n"): "Total cloud cover",
        ("hourly", "icon_eu", "neff"): "Effective cloud cover",
        ("hourly", "icon_eu", "nh"): "High cloud cover (>7 km)",
        ("hourly", "icon_eu", "nl"): "Low cloud cover (lower than 2 km).",
        ("hourly", "icon_eu", "nm"): "Midlevel cloud cover (2-7 km)",
        ("hourly", "icon_eu", "pppp"): "Surface pressure, reduced",
        ("hourly", "icon_eu", "rad1h"): (
            "Global Irradiance, as the energy of the last hour: the DMO values are in J/cm2 (the file states no "
            "unit; they are about a tenth of the MOSMIX kJ/m2 number for the same hour). Direct model output, "
            "not clipped at 0: in the night hours it is often a little below it (mostly above -0.2 J/cm2, at a "
            "few stations to about -0.8) and is returned as written."
        ),
        ("hourly", "icon_eu", "rr1"): (
            "Total precipitation during the last hour. ICON writes a little below 0 now and then (to about -0.1 mm); "
            "that is returned as 0.0, with the number kept as `raw:` in `quality_flags`."
        ),
        ("hourly", "icon_eu", "rrs1c"): "Snow-Rain-Equivalent during the last hour",
        ("hourly", "icon_eu", "t5cm"): "Temperature 5cm above surface",
        ("hourly", "icon_eu", "td"): "Dewpoint 2m above surface",
        ("hourly", "icon_eu", "tn"): "Minimum temperature - within the last 12 hours",
        ("hourly", "icon_eu", "ttt"): "Temperature 2m above surface",
        ("hourly", "icon_eu", "tx"): "Maximum temperature - within the last 12 hours",
        ("hourly", "icon_eu", "w1w2"): (
            "Past weather during the last 6 hours, as a class of DWD's MOSMIX list (the DMO values fit it): 9 "
            "thunderstorm, 8 shower, 7 snow or rain and snow mixed, 6 rain, 5 drizzle, 4 fog, 3 to 0 the "
            "effective cloud cover (at least 7/8, 4.6/8 to 6/8, 1/8 to 4.5/8, below 1/8). DWD says of MOSMIX "
            "that 0 to 3 are not reliable and mean no thunderstorm, no precipitation and no fog. Given at 00, "
            "06, 12 and 18 UTC."
        ),
        ("hourly", "icon_eu", "ww"): (
            "Significant Weather, as a code of DWD's MOSMIX list of codes (DWD publishes it as "
            "mosmix_element_weather_xls.xlsx; the DMO values fit it): 95 (thunderstorm) has the highest "
            "priority, then freezing drizzle and rain, showers, snowfall, rain and snow, drizzle, rain and fog, "
            "down to 3 to 0 (cloud development)."
        ),
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
        ("hourly", "large", "n"): "Total cloud cover",
        ("hourly", "large", "n05"): "Cloud cover below 500 ft.",
        ("hourly", "large", "neff"): "Effective cloud cover",
        ("hourly", "large", "nh"): "High cloud cover (>7 km)",
        ("hourly", "large", "nlm"): "Cloud cover low and mid level clouds below 7000 m",
        ("hourly", "large", "nm"): "Midlevel cloud cover (2-7 km)",
        (
            "hourly",
            "large",
            "pevap",
        ): "Potential evapotranspiration within the last 24 hours, given at the 06 UTC steps",
        ("hourly", "large", "pppp"): "Surface pressure, reduced",
        (
            "hourly",
            "large",
            "psd00",
        ): "Probability: relative sunshine duration > 0 % within 24 hours, given at the 06 UTC steps",
        (
            "hourly",
            "large",
            "psd30",
        ): "Probability: relative sunshine duration > 30 % within 24 hours, given at the 06 UTC steps",
        (
            "hourly",
            "large",
            "psd60",
        ): "Probability: relative sunshine duration > 60 % within 24 hours, given at the 06 UTC steps",
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
        ("hourly", "large", "rad1h"): (
            "Global Irradiance, which the source gives in kJ/m2 and so is the energy of the last hour: the "
            "values follow the daylight (0 at night, largest around noon)."
        ),
        ("hourly", "large", "rd00"): "Probability of precipitation > 0.0mm during the last 24 hours",
        ("hourly", "large", "rd02"): "Probability of precipitation > 0.2mm during the last 24 hours",
        ("hourly", "large", "rd10"): "Probability of precipitation > 1.0mm during the last 24 hours",
        ("hourly", "large", "rd50"): "Probability of precipitation > 5.0mm during the last 24 hours",
        ("hourly", "large", "rh00"): "Probability of precipitation > 0.0mm during the last 12 hours",
        ("hourly", "large", "rh02"): "Probability of precipitation > 0.2mm during the last 12 hours",
        ("hourly", "large", "rh10"): "Probability of precipitation > 1.0mm during the last 12 hours",
        ("hourly", "large", "rh50"): "Probability of precipitation > 5.0mm during the last 12 hours",
        ("hourly", "large", "rr1c"): "Total precipitation during the last hour consistent with significant weather",
        ("hourly", "large", "rr1o1"): "Probability of precipitation > 10.0 mm during the last hour",
        ("hourly", "large", "rr1u1"): "Probability of precipitation > 25.0 mm during the last hour",
        ("hourly", "large", "rr1w1"): "Probability of precipitation > 15.0 mm during the last hour",
        ("hourly", "large", "rr3c"): "Total precipitation during the last 3 hours consistent with significant weather",
        ("hourly", "large", "rr6c"): "Total precipitation during the last 6 hours consistent with significant weather",
        ("hourly", "large", "rrad1"): (
            "Global irradiance within the last hour as a percentage: the source gives % (0..80) and no "
            "reference. Rad1h over the extraterrestrial radiation on a horizontal surface in the same hour "
            "reproduces it roughly (mean difference under 3 points at 6 stations, single hours up to about 20 "
            "points apart), so it is read as a share of that."
        ),
        ("hourly", "large", "rrdc"): "Total precipitation during the last 24 hours consistent with significant weather",
        ("hourly", "large", "rrhc"): "Total precipitation during the last 12 hours consistent with significant weather",
        ("hourly", "large", "rrl1c"): (
            "Total liquid precipitation during the last hour consistent with significant weather"
        ),
        ("hourly", "large", "rrs1c"): "Snow-Rain-Equivalent during the last hour",
        ("hourly", "large", "rrs3c"): "Snow-Rain-Equivalent during the last 3 hours",
        ("hourly", "large", "rsund"): "Relative sunshine duration within the last 24 hours, given at the 06 UTC steps",
        ("hourly", "large", "sund"): "Yesterdays total sunshine duration, given at the 06 UTC steps",
        ("hourly", "large", "sund1"): "Sunshine duration during the last Hour",
        ("hourly", "large", "sund3"): (
            "Sunshine duration during the last 3 hours. Not a sliding 3 hour total: it does not agree with the sum "
            "of the last three sund1, not even at the 3-hourly steps, and appears to be interpolated from "
            "3-hourly values."
        ),
        ("hourly", "large", "t5cm"): "Temperature 5cm above surface",
        ("hourly", "large", "td"): "Dewpoint 2m above surface",
        (
            "hourly",
            "large",
            "tg",
        ): "Minimum surface temperature at 5cm within the last 12 hours, given at the 06 UTC steps",
        ("hourly", "large", "tm"): "Mean temperature during the last 24 hours, given at the 06 UTC steps",
        ("hourly", "large", "tn"): "Minimum temperature - within the last 12 hours, given at the 06 and 18 UTC steps",
        ("hourly", "large", "ttt"): "Temperature 2m above surface",
        ("hourly", "large", "tx"): "Maximum temperature - within the last 12 hours, given at the 06 and 18 UTC steps",
        ("hourly", "large", "vv"): "Visibility",
        ("hourly", "large", "vv10"): "Probability: Visibility below 1000m",
        ("hourly", "large", "w1w2"): (
            "Past weather during the last 6 hours, as two digits W1 and W2 (two-digit values from 0 to 99, such "
            "as 30, 65 or 86; the tens never below the units), each a class of DWD's list: 9 thunderstorm, 8 "
            "shower, 7 snow or rain and snow mixed, 6 rain, 5 drizzle, 4 fog, 3 to 0 the effective cloud cover "
            "(at least 7/8, 4.6/8 to 6/8, 1/8 to 4.5/8, below 1/8). DWD says that 0 to 3 are not reliable and "
            "mean no thunderstorm, no precipitation and no fog. Given at 00, 06, 12 and 18 UTC."
        ),
        ("hourly", "large", "wpc11"): (
            "Optional significant weather (highest priority) during the last hour, as a code of the same list as `ww`."
        ),
        ("hourly", "large", "wpc31"): (
            "Optional significant weather (highest priority) during the last 3 hours, as a code of the same list "
            "as `ww`, given at 00, 03, ... 21 UTC."
        ),
        ("hourly", "large", "wpc61"): (
            "Optional significant weather (highest priority) during the last 6 hours, as a code of the same list "
            "as `ww`, given at 00, 03, ... 21 UTC."
        ),
        ("hourly", "large", "wpcd1"): (
            "Optional significant weather (highest priority) during the last 24 hours, as a code of the same "
            "list as `ww`, given at 00 and 12 UTC."
        ),
        ("hourly", "large", "wpch1"): (
            "Optional significant weather (highest priority) during the last 12 hours, as a code of the same "
            "list as `ww`, given at 00, 06, 12 and 18 UTC."
        ),
        ("hourly", "large", "ww"): (
            "Significant Weather, as a code of DWD's list of the codes used in MOSMIX (DWD publishes it as "
            "mosmix_element_weather_xls.xlsx): 95 (thunderstorm) has the highest priority, then freezing drizzle "
            "and rain, showers, snowfall, rain and snow, drizzle, rain and fog, down to 3 to 0 (cloud "
            "development)."
        ),
        ("hourly", "large", "ww3"): (
            "Significant Weather of the last 3 hours, as a code of the same list as `ww`, given at 00, 03, ... 21 UTC."
        ),
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
        ("hourly", "large", "wwmd"): "Probability: Occurrence of fog within the last 24 hours, given at 00 and 12 UTC",
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
        ("hourly", "small", "rad1h"): (
            "Global Irradiance, which the source gives in kJ/m2 and so is the energy of the last hour: the "
            "values follow the daylight (0 at night, largest around noon)."
        ),
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
        (
            "hourly",
            "small",
            "tn",
        ): "Minimum temperature - within the last 12 hours, given at the 00, 06, 12 and 18 UTC steps",
        ("hourly", "small", "ttt"): "Temperature 2m above surface",
        (
            "hourly",
            "small",
            "tx",
        ): "Maximum temperature - within the last 12 hours, given at the 00, 06, 12 and 18 UTC steps",
        ("hourly", "small", "vv"): "Visibility",
        ("hourly", "small", "w1w2"): (
            "Past weather during the last 6 hours, as two digits W1 and W2 (two-digit values from 0 to 99, such "
            "as 30, 65 or 86; the tens never below the units), each a class of DWD's list: 9 thunderstorm, 8 "
            "shower, 7 snow or rain and snow mixed, 6 rain, 5 drizzle, 4 fog, 3 to 0 the effective cloud cover "
            "(at least 7/8, 4.6/8 to 6/8, 1/8 to 4.5/8, below 1/8). DWD says that 0 to 3 are not reliable and "
            "mean no thunderstorm, no precipitation and no fog. Given at 00, 06, 12 and 18 UTC."
        ),
        ("hourly", "small", "ww"): (
            "Significant Weather, as a code of DWD's list of the codes used in MOSMIX (DWD publishes it as "
            "mosmix_element_weather_xls.xlsx): 95 (thunderstorm) has the highest priority, then freezing drizzle "
            "and rain, showers, snowfall, rain and snow, drizzle, rain and fog, down to 3 to 0 (cloud "
            "development)."
        ),
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
            "Maximum of air temperature at 5 cm height during the last 10 minutes. Only the historical files "
            "carry a value, up to 2009: recent and now hold none."
        ),
        ("10_minutes", "temperature_extreme", "tx_10"): (
            "Maximum of air temperature at 2 m height during the last 10 minutes."
        ),
        (
            "10_minutes",
            "urban_precipitation",
            "rr_st_10",
        ): 'Precipitation per 10-minute interval (DWD: "momentaner Niederschlag").',
        ("10_minutes", "urban_pressure", "p0_st_10"): (
            'Pressure at station height, instantaneous (DWD: "momentaner Luftdruck Stationshoehe").'
        ),
        ("10_minutes", "urban_pressure", "pp_st_10"): (
            'Pressure reduced to sea level (Normal Null), instantaneous (DWD: "momentaner Luftdruck Normal Null").'
        ),
        ("10_minutes", "urban_solar", "fg_st_10"): (
            'Global radiation per 10-minute interval (DWD: "momentane Globalstrahlung").'
        ),
        ("10_minutes", "urban_solar", "sd_st_10"): (
            'Sunshine duration per 10-minute interval (DWD: "momentane Sonnenscheindauer"). The values are hours, '
            'at most 0.17, though the parameter sheet says "Minute".'
        ),
        ("10_minutes", "urban_temperature_air", "rf_st_10"): (
            'Relative humidity at 2 m height, instantaneous (DWD: "momentane rel.Feuchte in 2m Hoehe").'
        ),
        ("10_minutes", "urban_temperature_air", "strahl_st_10"): (
            'Radiant temperature at 2 m height, instantaneous (DWD: "momentane Strahlungstemperatur in 2m Hoehe").'
        ),
        ("10_minutes", "urban_temperature_air", "tt5_st_10"): (
            'Air temperature at 5 cm height, instantaneous (DWD: "momentane Lufttemperatur in 5cm Hoehe").'
        ),
        ("10_minutes", "urban_temperature_air", "tt_st_10"): (
            'Air temperature at 2 m height, instantaneous (DWD: "momentane Lufttemperatur in 2m Hoehe").'
        ),
        ("10_minutes", "urban_temperature_extreme", "tn5_st_10"): (
            'Minimum air temperature at 5 cm height (DWD: "momentane MIN Lufttemperatur in 5cm Hoehe").'
        ),
        ("10_minutes", "urban_temperature_extreme", "tn_st_10"): (
            'Minimum air temperature at 2 m height (DWD: "momentane minimale Lufttemperatur in 2m Hoehe").'
        ),
        ("10_minutes", "urban_temperature_extreme", "tx_st_10"): (
            'Maximum air temperature at 2 m height (DWD: "momentane maximale Lufttemperatur in 2m Hoehe").'
        ),
        ("10_minutes", "urban_temperature_soil", "te_st_01m_10"): (
            'Soil temperature in 10 cm depth, instantaneous (DWD: "momentane Erdbodentemperatur in 10 cm Tiefe").'
        ),
        ("10_minutes", "urban_temperature_soil", "te_st_02m_10"): (
            'Soil temperature in 20 cm depth, instantaneous (DWD: "momentane Erdbodentemp in 20 cm Tiefe").'
        ),
        ("10_minutes", "urban_temperature_soil", "te_st_05m_10"): (
            'Soil temperature in 50 cm depth, instantaneous (DWD: "momentane Erdbodentemp in 50 cm Tiefe").'
        ),
        ("10_minutes", "urban_temperature_soil", "te_st_10m_10"): (
            'Soil temperature in 100 cm depth, instantaneous (DWD: "momentane Erdbodentemperatur in 100 cm Tiefe").'
        ),
        ("10_minutes", "urban_wind", "dd_st_10"): (
            "Mean wind direction over 10 minutes, at the sensor height of the station (368 m at "
            'Berlin-Alexanderplatz) (DWD: "10Minuten Mittel"). '
            "The source's 0 beside a wind speed of 0 (a calm wind) is null."
        ),
        (
            "10_minutes",
            "urban_wind",
            "ff_st_10",
        ): (
            "Mean wind speed over 10 minutes, at the sensor height of the station (368 m at Berlin-Alexanderplatz) "
            '(DWD: "10Minuten Mittel").'
        ),
        (
            "10_minutes",
            "urban_wind_extreme",
            "fx_st_10",
        ): 'Maximum wind per 10-minute interval (DWD: "momentane MaxWind").',
        ("10_minutes", "wind", "dd_10"): (
            "Mean wind direction during the previous 10 minutes. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null."
        ),
        ("10_minutes", "wind", "ff_10"): "Mean wind speed during the previous 10 minutes.",
        ("10_minutes", "wind_extreme", "dx_10"): (
            "Wind direction of the maximum wind speed during the previous 10 minutes. "
            "The source's 0 beside a gust of 0 (a calm wind) is null."
        ),
        ("10_minutes", "wind_extreme", "fmx_10"): (
            "Maximum of the wind speed from the 1 minute mean values of the 3-second maxima of the previous 10 minutes."
        ),
        ("10_minutes", "wind_extreme", "fnx_10"): "Minimum of wind speed during the previous 10 minutes.",
        ("10_minutes", "wind_extreme", "fx_10"): "Maximum of wind speed during the previous 10 minutes.",
        ("1_minute", "precipitation", "rs_01"): "Sum of the precipitation height.",
        ("1_minute", "precipitation", "rs_ind_01"): (
            "Indicator of precipitation; if QN = 1 then: 0 = no precipitation, permanent sensor installed; 1 = "
            "precipitation, permanent sensor installed; 2 = no precipitation, heating in operation, permanent sensor "
            "installed; 3 = precipitation, heating in operation, permanent sensor installed; if QN > 1 then: 0 = no "
            "precipitation; 1 = precipitation."
        ),
        ("1_minute", "precipitation", "rth_01"): (
            'Value of the precipitation gauge with droplet counter (German sheet: "Niederschlagmesser mit '
            'Tröpfchenzähler"; the English sheet says "tipping bucket rain gauge").'
        ),
        ("1_minute", "precipitation", "rwh_01"): (
            'Value of the electronic precipitation gauge with tilting scales (German sheet: "elektronischer '
            'Niederschlagmesser mit Kippwaage").'
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
        ("annual", "climate_summary", "ja_fk"): (
            'Annual mean of the wind force in Beaufort (DWD: "Jahresmittel der Windstaerke"), the arithmetic mean of '
            "the monthly means."
        ),
        (
            "annual",
            "climate_summary",
            "ja_mx_fx",
        ): "Annual maximum of the daily wind peaks (Windspitze).",
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
        ("annual", "weather_phenomena", "ja_graupel"): "Number of days with graupel in the year.",
        ("annual", "weather_phenomena", "ja_hagel"): "Count of days with hail of stations in Germany.",
        ("annual", "weather_phenomena", "ja_nebel"): "Count of days with fog of stations in Germany.",
        ("annual", "weather_phenomena", "ja_sturm_6"): "Count of days with storm (strong wind) of stations in Germany.",
        ("annual", "weather_phenomena", "ja_sturm_8"): (
            "Count of days with storm (stormier wind) of stations in Germany."
        ),
        ("annual", "weather_phenomena", "ja_tau"): "Count of days with dew of stations in Germany.",
        ("daily", "climate_summary", "fm"): "Daily mean of wind velocity.",
        ("daily", "climate_summary", "fx"): "Daily maximum of windgust.",
        ("daily", "climate_summary", "nm"): (
            "Daily mean of cloud cover: the arithmetic mean of at least 21 hourly values, in earlier periods the mean"
            " of the observation terms (3 terms at most stations, 4 or 8 at some)."
        ),
        ("daily", "climate_summary", "pm"): (
            "Daily mean of pressure: the arithmetic mean of at least 21 hourly values, in earlier periods the mean of"
            " the observation terms (3 terms at most stations, 4 or 8 at some)."
        ),
        ("daily", "climate_summary", "qn_3"): "Quality level of the following columns.",
        ("daily", "climate_summary", "qn_4"): "Quality level of the following columns.",
        ("daily", "climate_summary", "rsk"): "Daily precipitation height.",
        ("daily", "climate_summary", "rskf"): "Precipitation form.",
        ("daily", "climate_summary", "sdk"): "Daily sunshine duration.",
        ("daily", "climate_summary", "shk_tag"): "Daily snow depth.",
        ("daily", "climate_summary", "tgk"): "Daily minimum of air temperature at 5 cm above ground.",
        ("daily", "climate_summary", "tmk"): (
            "Daily mean of temperature: the arithmetic mean of at least 21 hourly values, in earlier periods the mean"
            " of the observation terms (3 terms at most stations, TT1 to TT3: TMK=(TT1+TT2+(TT3*2))/4; 4 or 8 at "
            "some)."
        ),
        ("daily", "climate_summary", "tnk"): "Daily minimum of temperature at 2m height.",
        ("daily", "climate_summary", "txk"): "Daily maximum of temperature at 2 m height.",
        ("daily", "climate_summary", "upm"): (
            "Daily mean of relative humidity: the arithmetic mean of at least 21 hourly values, in earlier periods "
            "the mean of the observation terms (3 terms at most stations, 4 or 8 at some)."
        ),
        ("daily", "climate_summary", "vpm"): (
            "Daily mean of vapor pressure: the arithmetic mean of at least 21 hourly values, in earlier periods the "
            "mean of the observation terms (3 terms at most stations, 4 or 8 at some)."
        ),
        ("daily", "precipitation_more", "nsh_tag"): "Fresh snow depth.",
        ("daily", "precipitation_more", "rs"): "Daily precipitation height.",
        ("daily", "precipitation_more", "rsf"): "Precipitation form.",
        ("daily", "precipitation_more", "sh_tag"): "Height of snow pack.",
        ("daily", "solar", "atmo_strahl"): "Daily sum of longwave downward radiation.",
        ("daily", "solar", "fd_strahl"): "Daily sum of diffuse solar radiation.",
        ("daily", "solar", "fg_strahl"): "Daily sum of solar incoming radiation.",
        ("daily", "solar", "sd_strahl"): "Daily sum of sunshine duration.",
        ("daily", "temperature_soil", "v_te002m"): "Daily soil temperature in 2 cm depth.",
        ("daily", "temperature_soil", "v_te005m"): "Daily soil temperature in 5 cm depth.",
        ("daily", "temperature_soil", "v_te010m"): "Daily soil temperature in 10 cm depth.",
        ("daily", "temperature_soil", "v_te020m"): "Daily soil temperature in 20 cm depth.",
        ("daily", "temperature_soil", "v_te050m"): "Daily soil temperature in 50 cm depth.",
        ("daily", "water_equivalent", "ash_6"): "Height of the sampled snow pack.",
        ("daily", "water_equivalent", "sh_tag"): "Height of the snow pack.",
        ("daily", "water_equivalent", "waas_6"): "Water equivalent of the sampled snow pack.",
        ("daily", "water_equivalent", "wash_6"): "Water equivalent of the total snow pack.",
        ("daily", "weather_phenomena", "gewitter"): (
            'Weather event: thunderstorm during the day (DWD: "Wetterereignis: Gewitter im Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena", "glatteis"): (
            'Weather event: glaze ice during the day (DWD: "Wetterereignis: Glatteis im Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena", "graupel"): (
            'Weather event: graupel during the day (DWD: "Wetterereignis: Graupel im Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena", "hagel"): (
            'Weather event: hail during the day (DWD: "Wetterereignis: Hagel im Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena", "nebel"): (
            'Weather event: fog during the day (DWD: "Wetterereignis: Nebel im Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena", "reif"): (
            'Weather event: hoar frost during the day (DWD: "Wetterereignis: Reif im Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena", "sturm_6"): (
            'Weather event: storm of at least 6 Bft during the day (DWD: "Wetterereignis: Sturm>=6 Bft im Verlauf des'
            ' Tages").'
        ),
        ("daily", "weather_phenomena", "sturm_8"): (
            'Weather event: storm of at least 8 Bft during the day (DWD: "Wetterereignis: Sturm>=8 Bft im Verlauf des'
            ' Tages").'
        ),
        ("daily", "weather_phenomena", "tau"): (
            'Weather event: dew during the day (DWD: "Wetterereignis: Tau im Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena_more", "rr_gewitter"): (
            'Weather event of the precipitation network: thunderstorm during the day (DWD: "Wetterereignis_RR: '
            'Gewitter im Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena_more", "rr_graupel"): (
            'Weather event of the precipitation network: graupel during the day (DWD: "Wetterereignis_RR: Graupel im '
            'Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena_more", "rr_hagel"): (
            'Weather event of the precipitation network: hail during the day (DWD: "Wetterereignis_RR: Hagel im '
            'Verlauf des Tages").'
        ),
        ("daily", "weather_phenomena_more", "rr_nebel"): (
            'Weather event of the precipitation network: fog during the day (DWD: "Wetterereignis_RR: Nebel im '
            'Verlauf des Tages").'
        ),
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
        ("hourly", "moisture", "p_std"): (
            "Hourly value of barometric pressure. A station without a barometer carries one station constant in every "
            "row of a file, which is no reading: where a file of at least 500 readings holds at most three distinct "
            "values (a constant that changed once or twice) it is null, and the value stays in quality_flags as the "
            "last token, e.g. raw:997.3."
        ),
        ("hourly", "moisture", "rf_std"): "Relative humidity.",
        ("hourly", "moisture", "td_std"): "Dew point temperature in 2m above ground.",
        ("hourly", "moisture", "tf_std"): "Computed hourly value of wet bulb temperature.",
        ("hourly", "moisture", "tt_std"): "Air temperatur in 2m above ground.",
        ("hourly", "moisture", "vp_std"): "Computed hourly value of vapour pressure.",
        ("hourly", "precipitation", "r1"): "Precipitation height during the previous hour.",
        ("hourly", "precipitation", "rs_ind"): "Precipitation indicator; 0 = no; 1 = yes.",
        ("hourly", "precipitation", "wrtr"): (
            "Precipitation form; 0 = no precipitation; 1 = rain only (in historical data before 01.01.1979); 4 = form"
            " of precipitation unascertainable and depositional precipitation, automatic ascertainment; 6 = liquid "
            "precipitation, automatic ascertainment; 7 = solid precipitation, automatic ascertainment; 8 = liquid and"
            " solid precipitation, automatic ascertainment; 9 = missing value, form of precipitation unascertainable,"
            " automatic ascertainment; returned as null, the 9 stays as the last token of quality_flags, raw:9. The "
            "files also hold 2 and 3, which the current sheet does not define."
        ),
        ("hourly", "pressure", "p"): "Barometric pressure at sea level NN.",
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
        ("hourly", "sun", "sd_so"): (
            "Hourly sunshine duration. The stamps of the periods that DWD's Metadaten_Parameter calls "
            '"Stundenwerte in WOZ" (the older periods of 528 of 636 stations, at some of them to 2006) are the hour '
            "of the station's local true solar time, not UTC: they are returned as written, not shifted, and their "
            "`quality_flags` carry `zone:woz` (`10,zone:woz`). The other stamps are UTC."
        ),
        ("hourly", "temperature_air", "rf_tu"): (
            "Relative humidity. The stamps of the periods that DWD's Metadaten_Parameter calls "
            '"Stundenwerte in MEZ (MD)" (the eMD archive of 76 East German stations, up to 1991) are MEZ, UTC+1: '
            "they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`), "
            "and so are those of Diepholz from 1995-02-01 to 1996-05-31, a period the label calls plain MEZ "
            "that is MEZ in the values from the stamp 1995-02-01 00 to the stamp 1996-05-31 23. "
            "The other stamps are UTC."
        ),
        ("hourly", "temperature_air", "tt_tu"): (
            "Air temperature 2 m above ground. The stamps of the periods that DWD's Metadaten_Parameter calls "
            '"Stundenwerte in MEZ (MD)" (the eMD archive of 80 East German stations, up to 1991) are MEZ, UTC+1: '
            "they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`), "
            "and so are those of Diepholz from 1995-02-01 to 1996-05-31, a period the label calls plain MEZ "
            "that is MEZ in the values from the stamp 1995-02-01 00 to the stamp 1996-05-31 23. "
            "The other stamps are UTC."
        ),
        ("hourly", "temperature_soil", "v_te002"): (
            "Soil temperature in 2 cm depth. Only the historical files carry a value, up to 2019: recent holds none. "
            + _SOIL_EMD_ZONE
        ),
        ("hourly", "temperature_soil", "v_te005"): "Soil temperature in 5 cm depth. " + _SOIL_EMD_ZONE,
        ("hourly", "temperature_soil", "v_te010"): "Soil temperature in 10 cm depth. " + _SOIL_EMD_ZONE,
        ("hourly", "temperature_soil", "v_te020"): "Soil temperature in 20 cm depth. " + _SOIL_EMD_ZONE,
        ("hourly", "temperature_soil", "v_te050"): "Soil temperature in 50 cm depth. " + _SOIL_EMD_ZONE,
        ("hourly", "temperature_soil", "v_te100"): "Soil temperature in 100 cm depth. " + _SOIL_EMD_ZONE,
        ("hourly", "urban_precipitation", "niederschlagshoehe"): (
            "Precipitation height, the sum of the six 10-minute intervals of the previous hour (at UTC 11 the sum of "
            "the precipitation during UTC10-UTC11)."
        ),
        ("hourly", "urban_pressure", "luftdruck_stationshoehe"): (
            "Pressure at station height, following the SYNOP conventions: the hour x corresponds to the measurement "
            "from 10 min before (at UTC 11 the value from UTC 10:50)."
        ),
        ("hourly", "urban_sun", "sonnenscheindauer"): (
            "Sunshine duration, the sum of the six 10-minute intervals of the previous hour (at UTC 11 the sum of the"
            " sunshine during UTC10-UTC11)."
        ),
        ("hourly", "urban_temperature_air", "lufttemperatur"): (
            "2m air temperature, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval "
            "ending UTC 10:50 is given."
        ),
        ("hourly", "urban_temperature_air", "rel_feuchte"): (
            "2m relative humidity, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval"
            " ending UTC 10:50 is given."
        ),
        ("hourly", "urban_temperature_soil", "erdbt_005"): (
            "Soil temperature in 5 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 "
            "minute interval ending UTC 10:50 is given."
        ),
        ("hourly", "urban_temperature_soil", "erdbt_010"): (
            "Soil temperature in 10 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 "
            "minute interval ending UTC 10:50 is given."
        ),
        ("hourly", "urban_temperature_soil", "erdbt_020"): (
            "Soil temperature in 20 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 "
            "minute interval ending UTC 10:50 is given."
        ),
        ("hourly", "urban_temperature_soil", "erdbt_050"): (
            "Soil temperature in 50 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 "
            "minute interval ending UTC 10:50 is given."
        ),
        ("hourly", "urban_temperature_soil", "erdbt_100"): (
            "Soil temperature in 100 cm depth, following the SYNOP conventions: at UTC 11 the mean value of the 1 "
            "minute interval ending UTC 10:50 is given."
        ),
        ("hourly", "urban_wind", "windgeschwindigkeit"): (
            "Mean wind speed, the average of the six 10-minute intervals of the previous hour (at UTC 11 the average "
            "during UTC10-UTC11). DWD's sheet: measured at 368 m on Berlin's television tower (the other urban "
            "stations have their own sensor heights)."
        ),
        ("hourly", "urban_wind", "windrichtung"): (
            "Mean wind direction, the average of the six 10-minute intervals of the previous hour (at UTC 11 the "
            "average during UTC10-UTC11). DWD's sheet: measured at 368 m on Berlin's television tower (the other "
            "urban stations have their own sensor heights). The source's 0 comes with a wind speed above 0 and with "
            "six 10-minute directions spread over the compass, so it is neither a calm nor north (written 360) and "
            "is null."
        ),
        ("hourly", "visibility", "v_vv"): "Visibility range.",
        ("hourly", "visibility", "v_vv_i"): (
            "Visibility index, noting how the measurement is taken,P=by human person,I=by an instrument. "
            "Returned as 1 for P and 2 for I."
        ),
        ("hourly", "weather_phenomena", "ww"): (
            "Present weather code (for 20-29 and 120-126 that of the past hour). One column holds two tables with "
            "disjoint numbers: 0-99 is WMO code table 4677 (ww, manned stations), 100-199 is WMO code table 4680 "
            "(wawa, automatic stations) with 100 added. A station's historical file holds either or both, the "
            "recent file of an automated station only 100-199. The meaning of every code is in DWD's "
            "Wetter_Beschreibung.txt, the text its WW_Text column repeats. The source's -1 (weather not reported) "
            "is null."
        ),
        ("hourly", "wind", "d"): (
            "Mean wind direction. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
        ("hourly", "wind", "f"): "Mean wind speed.",
        ("hourly", "wind_extreme", "fx_911"): "Wind speed, wind gust: the highest wind peak of the last hour.",
        ("hourly", "wind_synoptic", "dd"): (
            'Wind direction (DWD: "Windrichtung uml.,windstill DD=00"). '
            "The source's 0 (a calm or variable wind) is null."
        ),
        ("hourly", "wind_synoptic", "ff"): (
            '10-minute mean of the wind speed (DWD: "10-Min-Mittel der Windgeschwindigkeit").'
        ),
        ("monthly", "climate_indices", "mo_eistage"): "Monthly number of ice days.",
        ("monthly", "climate_indices", "mo_frosttage"): "Monthly number of frost days.",
        ("monthly", "climate_indices", "mo_heisse_tage"): "Monthly number of hot days.",
        ("monthly", "climate_indices", "mo_sommertage"): "Monthly number of summer days.",
        (
            "monthly",
            "climate_indices",
            "mo_tropennaechte",
        ): "Monthly number of tropical nights, counted over the day from 00 to 23 hours.",
        ("monthly", "climate_summary", "mo_fk"): "Monthly mean of the daily wind force in Beaufort.",
        ("monthly", "climate_summary", "mo_n"): "Monthly mean of cloud cover.",
        ("monthly", "climate_summary", "mo_rr"): "Monthly sum of precipitation height.",
        ("monthly", "climate_summary", "mo_sd_s"): "Monthly sum of sunshine duration.",
        ("monthly", "climate_summary", "mo_tn"): "Monthly mean of daily temperature minima in 2 m above ground.",
        ("monthly", "climate_summary", "mo_tt"): "Monthly mean of the daily mean air temperature 2 m above ground.",
        ("monthly", "climate_summary", "mo_tx"): "Monthly mean of daily temperature maxima at 2 m above ground.",
        (
            "monthly",
            "climate_summary",
            "mx_fx",
        ): "Monthly maximum of the daily wind peaks (Windspitze).",
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
        ("monthly", "weather_phenomena", "mo_graupel"): "Number of days with graupel in the month.",
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
        ("subdaily", "wind", "dk_ter"): (
            "Wind direction. The source gives the point of a 32-point wind rose (32 is north), returned in degrees. "
            "The source's 0 beside a wind force of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
        ("subdaily", "wind", "fk_ter"): "Wind force (beaufort).",
        (
            "subdaily",
            "wind_extreme",
            "fx_911_3",
        ): 'Highest wind peak of the last 3 hours; DWD\'s list adds "(>12,5 m/s)".',
        (
            "subdaily",
            "wind_extreme",
            "fx_911_6",
        ): 'Highest wind peak of the last 6 hours; DWD\'s list adds "(>12,5 m/s)".',
    },
    # No sheet describes the fields of the road weather messages, so the entries name the BUFR element each decodes
    # from (ecCodes element.table and the code tables, local table 8 of centre 78) and what the template of the
    # `LATEST` file of each station group states around it (read 2026-10-21): no time significance or period stands
    # before the temperatures, the humidity or the water film, so those are readings at one moment, while the
    # precipitation (0 20 024 to 0 13 011) and the wind (0 08 021, 0 04 025) follow a period the group writes
    "DwdRoadMetadata": {
        (
            "15_minutes",
            "data",
            "airTemperature",
        ): (
            "air temperature (BUFR 0 12 101, no time period or statistic attached); the sensor stands 4 to 5 m above "
            "ground (BUFR 0 07 032 reads 4.0, 4.05 or 5.0 m by station group, none in four of them)"
        ),
        (
            "15_minutes",
            "data",
            "dewpointTemperature",
        ): (
            "dew point temperature (BUFR 0 12 103, no time period or statistic attached); the sensor stands 4 to 5 m "
            "above ground (BUFR 0 07 032 reads 4.0, 4.05 or 5.0 m by station group, none in four of them)"
        ),
        ("15_minutes", "data", "horizontalVisibility"): "visibility range",
        ("15_minutes", "data", "intensityOfPrecipitation"): "precipitation intensity",
        ("15_minutes", "data", "maximumWindGustDirection"): "direction of maximum wind gust",
        ("15_minutes", "data", "maximumWindGustSpeed"): (
            "maximum wind gust over the period the station states (10 or 15 minutes, none stated in some station "
            "groups)"
        ),
        ("15_minutes", "data", "precipitationType"): (
            "type of precipitation, the bit flags of BUFR 0 20 021 (rain is bit 5 of 30, 33554432)"
        ),
        # BUFR 0 13 003 stands with no time significance or period before it in the `LATEST` file of any station group
        # (read 2026-10-21): the source states no mean, so the name is `humidity_relative` since GH-2614
        (
            "15_minutes",
            "data",
            "relativeHumidity",
        ): "relative humidity (BUFR 0 13 003, no time period or statistic attached)",
        ("15_minutes", "data", "roadSurfaceCondition"): (
            "road surface condition, a code: 0 dry, 1 moist, 2 wet, 3 rime, 4 snow, 5 ice, 6 glaze, 7 not dry "
            "(BUFR code table 0 20 241, the same codes as 0 20 138); not the codes of DWD's SWSMOS forecast "
            "(1 dry, 2 moist, 3 snow, ...), which is `road_surface_condition_forecast`"
        ),
        (
            "15_minutes",
            "data",
            "roadSurfaceTemperature",
        ): "road surface temperature (BUFR 0 12 241, no time period or statistic attached)",
        ("15_minutes", "data", "totalPrecipitationOrTotalWaterEquivalent"): (
            "precipitation height over the period the station states (15 minutes in most station groups, 10 at KO, RP "
            "and SD, none stated in some)"
        ),
        ("15_minutes", "data", "waterFilmThickness"): "thickness of water film",
        ("15_minutes", "data", "windDirection"): (
            "mean direction of wind over the period the station states (10 or 15 minutes, none stated in some station "
            "groups)"
        ),
        ("15_minutes", "data", "windSpeed"): (
            "mean wind speed over the period the station states (10 or 15 minutes, none stated in some station groups)"
        ),
    },
    # the "Revised service" table of https://environment.data.gov.uk/hydrology/doc/reference (read 2026-10-21): "Flow
    # 15min instantaneous m3/s", "Flow daily mean, min, max m3/s", "Level 15min instantaneous m", "Level daily min,
    # max m", "GroundwaterLevel sub-daily instantaneous Groundwater Logged mAOD" ("for logged groundwater data the
    # sub-daily values may be a mix of 15min and hourly intervals"), and of the unit "m (for meters with an unspecified
    # datum)", against "mAOD" and "mASD". Every river level measure of the measures listing has the unit m (2,638 each
    # of level-i-900, level-max-86400 and level-min-86400). The daily window is not in the documentation: a daily
    # reading is stamped 09:00 and the mean of a day equals the mean of the 15 minute flows from that 09:00 to the
    # next in 27 of 27, 30 of 30 and 27 of 27 days (Felsted in Feb and Jul 2025, Ulting Sarasota in Feb 2025; no
    # other start hour does), and a maximum or minimum is stamped at the instant of the extreme inside it
    "EAHydrologyMetadata": {
        ("15_minutes", "data", "flow-i-900"): "instant flow at timestamp",
        ("15_minutes", "data", "level-i-900"): (
            "instant river water level at timestamp, in the source's unit m, relative to an unspecified datum (the "
            "unit is not mAOD or mASD)"
        ),
        ("15_minutes", "data", "gw-logged-i-subdaily"): (
            "logged groundwater level at timestamp, in metres above ordnance datum, every 15 minutes to every hour"
        ),
        ("daily", "data", "flow-m-86400"): f"daily mean flow, over {_EA_DAY}",
        ("daily", "data", "flow-max-86400"): f"daily maximum flow, within {_EA_DAY}",
        ("daily", "data", "flow-min-86400"): f"daily minimum flow, within {_EA_DAY}",
        ("daily", "data", "level-max-86400"): (
            f"daily maximum river water level, within {_EA_DAY}, in the source's unit m, relative to an unspecified "
            "datum"
        ),
        ("daily", "data", "level-min-86400"): (
            f"daily minimum river water level, within {_EA_DAY}, in the source's unit m, relative to an unspecified "
            "datum"
        ),
    },
    "EcccObservationMetadata": {
        ("daily", "data", "max_temperature"): "Daily maximum 2m air temperature.",
        ("daily", "data", "mean_temperature"): "Daily mean 2m air temperature, (maximum + minimum) / 2.",
        ("daily", "data", "min_temperature"): "Daily minimum 2m air temperature.",
        ("daily", "data", "snow_on_ground"): "Total snow depth.",
        ("daily", "data", "speed_max_gust"): "Maximum wind gust.",
        ("daily", "data", "total_precipitation"): "Total precipitation.",
        ("daily", "data", "total_rain"): "Total liquid precipitation.",
        ("daily", "data", "total_snow"): "New snow depth.",
        ("daily", "data", "cooling_degree_days"): "cooling degree days",
        ("daily", "data", "direction_max_gust"): (
            "wind direction of maximum wind gust. The source's 0 beside a gust of 0 (none reported) is null."
        ),
        ("daily", "data", "heating_degree_days"): "heating degree days",
        ("hourly", "data", "dew_point_temp"): "2m dew point temperature",
        ("hourly", "data", "humidex"): "humidex apparent temperature",
        ("hourly", "data", "precip_amount"): "precipitation height",
        ("hourly", "data", "relative_humidity"): "humidity",
        ("hourly", "data", "station_pressure"): "air pressure at site",
        ("hourly", "data", "temp"): "2m air temperature",
        ("hourly", "data", "visibility"): "visibility range",
        # the glossary: "the average direction during the two minute period ending at the time of observation"; the
        # speed is the average of "the one-, two- or ten-minute period", the direction is stated for two only
        ("hourly", "data", "wind_direction"): (
            "wind direction (source: 10s deg), the average of the two minutes ending at the time of observation. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null."
        ),
        ("hourly", "data", "wind_speed"): "wind speed",
        ("hourly", "data", "windchill"): "wind chill temperature",
        ("monthly", "data", "bright_sunshine"): "bright sunshine duration",
        ("monthly", "data", "cooling_degree_days"): "cooling degree days",
        ("monthly", "data", "days_with_precip_ge_1mm"): "days with >= 1 mm precipitation",
        ("monthly", "data", "days_with_valid_max_temp"): "days with a valid maximum temperature",
        ("monthly", "data", "days_with_valid_mean_temp"): (
            "days with a valid mean temperature, the daily mean being calculated from the daily extremes"
        ),
        ("monthly", "data", "days_with_valid_min_temp"): "days with a valid minimum temperature",
        ("monthly", "data", "days_with_valid_precip"): "days with a valid precipitation observation",
        ("monthly", "data", "days_with_valid_snowfall"): "days with a valid snowfall observation",
        ("monthly", "data", "days_with_valid_sunshine"): "days with a valid sunshine observation",
        ("monthly", "data", "heating_degree_days"): "heating degree days",
        ("monthly", "data", "max_temperature"): "2m maximum air temperature",
        ("monthly", "data", "mean_temperature"): "2m mean air temperature, the mean of the daily values",
        ("monthly", "data", "min_temperature"): "2m minimum air temperature",
        ("monthly", "data", "normal_mean_temperature"): (
            "normal of the mean air temperature, the daily mean being calculated from the daily extremes"
        ),
        ("monthly", "data", "normal_precipitation"): "normal of the precipitation height",
        ("monthly", "data", "normal_snowfall"): "normal of the snowfall total",
        ("monthly", "data", "normal_sunshine"): "normal of the sunshine duration",
        ("monthly", "data", "snow_on_ground_last_day"): "snow depth on the last day",
        ("monthly", "data", "total_precipitation"): "precipitation height",
        ("monthly", "data", "total_snowfall"): "snowfall total",
    },
    "GeosphereObservationMetadata": {
        ("10_minutes", "data", "cglo"): "Global radiation, calibrated, 10-minute mean value.",
        ("10_minutes", "data", "chim"): "Diffuse radiation, not quality-checked, calibrated, 10-minute mean value.",
        ("10_minutes", "data", "dd"): (
            "Wind direction [360°], vector 10-minute mean value. The source's 0 (a calm wind) is null."
        ),
        ("10_minutes", "data", "ddx"): "Wind direction of the maximum wind speed (peak gust) [360°].",
        ("10_minutes", "data", "ff"): "Wind speed at 10 m height, vector 10-minute mean value.",
        ("10_minutes", "data", "ffam"): "Wind speed at 10 m height, arithmetic 10-minute mean value.",
        ("10_minutes", "data", "ffx"): "Wind speed at 10 m height, 10-minute maximum value (peak gust).",
        ("10_minutes", "data", "p"): "Air pressure, 10-minute measured value.",
        ("10_minutes", "data", "pred"): "Reduced air pressure (reduced to sea level): calculated 10-minute value.",
        ("10_minutes", "data", "rf"): "Relative humidity, 10-minute measured value.",
        ("10_minutes", "data", "rr"): "Precipitation sum, calculated from 1-minute precipitation data.",
        ("10_minutes", "data", "rrm"): "Precipitation duration, calculated from 1-minute precipitation detector data.",
        ("10_minutes", "data", "sh"): (
            "Total snow depth from snow gauge measurement, 10-minute mean value, offset corrected."
        ),
        ("10_minutes", "data", "so"): "Sunshine duration in seconds, 10-minute sum.",
        ("10_minutes", "data", "tb10"): "Soil temperature at 10 cm depth, 10-minute measured value",
        ("10_minutes", "data", "tb20"): "Soil temperature at 20 cm depth, 10-minute measured value",
        ("10_minutes", "data", "tb50"): "Soil temperature at 50 cm depth, 10-minute measured value",
        ("10_minutes", "data", "tl"): "Air temperature at 2 m height, 10-minute measured value",
        ("10_minutes", "data", "tlmax"): "Air temperature at 2 m height, 10-minute maximum value",
        ("10_minutes", "data", "tlmin"): "Air temperature at 2 m height, 10-minute minimum value",
        ("10_minutes", "data", "ts"): "Air temperature at 5 cm height, 10-minute measured value",
        ("10_minutes", "data", "tsmax"): "Air temperature at 5 cm height, 10-minute maximum value",
        ("10_minutes", "data", "tsmin"): "Air temperature at 5 cm height, 10-minute minimum value",
        ("daily", "data", "bewm_mittel"): (
            "Cloud cover, daily mean calculated from the observation times I, II and III (06, 13 and 18 UTC), "
            "multiplied by 10 (the source's unit is 1/100, i.e. percent)."
        ),
        ("daily", "data", "cglo_j"): (
            "Global radiation, calibrated 24-hour sum of the hourly values 0-24 h MOZ (23 UTC of the day before to 23 "
            "UTC of the day)."
        ),
        ("daily", "data", "dampf_mittel"): (
            "Vapor pressure, daily mean calculated from the observation times I, II and III (06, 13 and 18 UTC)."
        ),
        ("daily", "data", "ffx"): (
            "Wind speed (peak gust), daily maximum of the hourly values 0-24 h MOZ (23 UTC of the day before to 23 UTC "
            "of the day)."
        ),
        ("daily", "data", "p_mittel"): (
            "Air pressure, daily mean of the observation times I, II and III (06, 13 and 18 UTC)."
        ),
        ("daily", "data", "rf_mittel"): (
            "Relative humidity, daily mean of the observation times I, II and III (06, 13 and 18 UTC)."
        ),
        ("daily", "data", "rr"): (
            "Precipitation, 24-hour sum of the one-minute values from 06:01 UTC to 06:00 UTC of the following day. The "
            "source's -1 (no precipitation) is 0.0; its 0 (less than 1/10 mm, a trace) stays 0.0."
        ),
        ("daily", "data", "sh"): (
            "Total snow depth from automatic snow gauge measurement, offset corrected, at observation time I (06 UTC). "
            "The source's -1 (no snow) is 0.0."
        ),
        ("daily", "data", "sh_manu"): (
            "Total snow depth, manual measurement at observation time I (06 UTC). The source's -1 (no snow) is 0.0."
        ),
        ("daily", "data", "shneu_manu"): (
            "New snow depth, 24-hour sum, manual measurement at observation time I (06 UTC). The source's -1 (no snow) "
            "is 0.0."
        ),
        ("daily", "data", "so_h"): (
            "Sunshine duration, sum of the hourly values 0-24 h MOZ (23 UTC of the day before to 23 UTC of the day)."
        ),
        ("daily", "data", "tl_mittel"): "air temperature mean at 2m, calculated from (tlmax + tlmin)/2",
        ("daily", "data", "tlmax"): (
            "Air temperature at 2 m height, maximum of the ten-minute values (tlmax) from 18:10 UTC of the day "
            "before to 18:00 UTC of the day"
        ),
        ("daily", "data", "tlmin"): (
            "Air temperature at 2 m height, minimum of the ten-minute values (tlmin) from 18:10 UTC of the day "
            "before to 18:00 UTC of the day"
        ),
        ("daily", "data", "tsmin"): (
            "Air temperature at 5 cm height, minimum in the night from 18:10 UTC of the day before to 06:00 UTC "
            "of the day"
        ),
        ("daily", "data", "vv_mittel"): (
            "Wind speed, daily mean of the observation times I, II and III (06, 13 and 18 UTC)."
        ),
        ("hourly", "data", "cglo"): "Global radiation, calibrated hourly mean value.",
        ("hourly", "data", "dd"): (
            "Wind direction [360°], vector hourly mean value. The source's 0 (a calm wind) is null."
        ),
        ("hourly", "data", "ddx"): "Wind direction of the maximum wind speed (peak gust), hourly value.",
        ("hourly", "data", "ff"): "Wind speed, vector hourly mean value.",
        ("hourly", "data", "ffx"): "Maximum wind speed (peak gust), hourly maximum value.",
        ("hourly", "data", "p"): "Air pressure at station level, hourly measured value.",
        ("hourly", "data", "pred"): "Reduced air pressure (reduced to sea level): calculated hourly value.",
        ("hourly", "data", "rf"): "Relative humidity, hourly measured value.",
        ("hourly", "data", "rr"): "Precipitation, hourly sum.",
        ("hourly", "data", "rrm"): "Precipitation duration, hourly sum.",
        ("hourly", "data", "sh"): "Total snow depth from snow gauge measurement, offset corrected.",
        ("hourly", "data", "so_h"): "Sunshine duration, hourly sum.",
        ("hourly", "data", "tb10"): "Soil temperature at 10 cm depth, hourly measured value",
        ("hourly", "data", "tb100"): "Soil temperature at 100 cm depth, hourly measured value",
        ("hourly", "data", "tb20"): "Soil temperature at 20 cm depth, hourly measured value",
        ("hourly", "data", "tb200"): "Soil temperature at 200 cm depth, hourly measured value",
        ("hourly", "data", "tb50"): "Soil temperature at 50 cm depth, hourly measured value",
        ("hourly", "data", "tl"): "Air temperature at 2 m height, hourly measured value",
        # the source's own sentence reads "Lufttemperatur in 5 cm Höhe, Stunden-Messwert" beside the long name
        # "... Minimalwert"; the data says minimum: of 48 hours of station 1 (2024-07-10/11) the hourly value at H
        # is the smallest of the six 10-minute tsmin stamped H-50 to H in 48, and the 10-minute value at H in 19
        ("hourly", "data", "tsmin"): "Air temperature at 5 cm height, hourly minimum",
        ("monthly", "data", "bet0"): "Concrete temperature at 0 cm depth, monthly mean of the hourly values",
        ("monthly", "data", "bet0_max"): "Concrete temperature at 0 cm depth, monthly maximum of all hourly values",
        ("monthly", "data", "bet0_min"): "Concrete temperature at 0 cm depth, monthly minimum of all hourly values",
        ("monthly", "data", "bewm_mittel"): (
            "Cloud cover, monthly mean calculated from the daily cloud cover means 10*(I+II+III)/3 (the source's unit "
            "is 1/100, i.e. percent)."
        ),
        ("monthly", "data", "cglo_j"): "Global radiation, monthly sum of the calibrated hourly values.",
        ("monthly", "data", "dampf_mittel"): "Vapor pressure, monthly mean of the daily values.",
        ("monthly", "data", "p"): "Air pressure, monthly mean of the observation-time values.",
        ("monthly", "data", "pmax"): "Air pressure, maximum of all observation-time values of the month.",
        ("monthly", "data", "pmin"): "Air pressure, minimum of all observation-time values of the month.",
        ("monthly", "data", "rf_mittel"): "Relative humidity, monthly mean of all daily means.",
        ("monthly", "data", "rr"): "Precipitation, monthly sum of the 24-hour sums at observation time I (06 UTC).",
        ("monthly", "data", "rr_max"): (
            "Precipitation, monthly maximum of the 24-hour sums at observation time I (06 UTC)."
        ),
        ("monthly", "data", "sh_manu_max"): "Total snow depth, monthly maximum of the daily values.",
        ("monthly", "data", "shneu_manu"): (
            "New snow depth, monthly sum of the daily values at observation time I (06 UTC)."
        ),
        ("monthly", "data", "shneu_manu_max"): (
            "New snow depth, monthly maximum of the daily values at observation time I (06 UTC)."
        ),
        ("monthly", "data", "so_h"): "Sunshine duration, monthly sum of the hourly values.",
        ("monthly", "data", "so_r"): (
            "Sunshine duration, share of the monthly sunshine duration in the effectively possible sunshine duration, "
            "in percent."
        ),
        ("monthly", "data", "tb100_max"): "Soil temperature at 100 cm depth, monthly maximum of all hourly values",
        ("monthly", "data", "tb100_min"): "Soil temperature at 100 cm depth, monthly minimum of all hourly values",
        ("monthly", "data", "tb100_mittel"): "Soil temperature at 100 cm depth, monthly mean of all hourly values",
        ("monthly", "data", "tb10_max"): "Soil temperature at 10 cm depth, monthly maximum of all hourly values",
        ("monthly", "data", "tb10_min"): "Soil temperature at 10 cm depth, monthly minimum of all hourly values",
        ("monthly", "data", "tb10_mittel"): "Soil temperature at 10 cm depth, monthly mean of all hourly values",
        ("monthly", "data", "tb200_max"): "Soil temperature at 200 cm depth, monthly maximum of all hourly values",
        ("monthly", "data", "tb200_min"): "Soil temperature at 200 cm depth, monthly minimum of all hourly values",
        ("monthly", "data", "tb200_mittel"): "Soil temperature at 200 cm depth, monthly mean of all hourly values",
        ("monthly", "data", "tb20_max"): "Soil temperature at 20 cm depth, monthly maximum of all hourly values",
        ("monthly", "data", "tb20_min"): "Soil temperature at 20 cm depth, monthly minimum of all hourly values",
        ("monthly", "data", "tb20_mittel"): "Soil temperature at 20 cm depth, monthly mean of all hourly values",
        ("monthly", "data", "tb50_max"): "Soil temperature at 50 cm depth, monthly maximum of all hourly values",
        ("monthly", "data", "tb50_min"): "Soil temperature at 50 cm depth, monthly minimum of all hourly values",
        ("monthly", "data", "tb50_mittel"): "Soil temperature at 50 cm depth, monthly mean of all hourly values",
        # the source says "Monats-Mittelwert aus Termin- und Extremwerten" and nothing of the weights. Fitted on 1,499
        # station-months of klima-v2-1m (stations 105, 106, 107, 112 and 158, 2000-2024, 2026-10-21): tl_mittel is
        # (tl_i_mittel + tl_iii_mittel + tlmax_mittel + tlmin_mittel) / 4 to within the 0.1 K rounding in 1,499 of
        # 1,499 (least squares: 0.249, 0.002, 0.250, 0.249, 0.251 on I, II, III, mean max, mean min; a mean of the
        # daily (tlmax + tlmin) / 2 is 0.45 K off on average and (I + II + III) / 3 is 1.0 K off). The daily
        # tl_mittel is (tlmax + tlmin) / 2 to within 0.05 K in 1,460 of 1,460 days (stations 105 and 106, 2022-2023)
        ("monthly", "data", "tl_mittel"): (
            "Air temperature at 2 m height, monthly mean from observation-time and extreme values (Termin- und "
            "Extremwerte): the mean of the monthly means at 06 and 18 UTC (observation times I and III) and of the "
            "daily maxima and minima, each with a weight of one quarter."
        ),
        ("monthly", "data", "tlmax"): "Air temperature at 2 m height, monthly maximum of the 24-hour maxima",
        ("monthly", "data", "tlmin"): "Air temperature at 2 m height, monthly minimum of the 24-hour minima",
        ("monthly", "data", "vv_mittel"): "Wind speed, monthly mean of the 24-hour means.",
    },
    "ImgwHydrologyMetadata": {
        # CODZ_publiczne_format.txt: "COSTAN - Stan wody [cm]", "COPRZP - Przepływ [m^3/s]", "COPTMP - Temperatura
        # wody [st. C]" and the sentinels "Stan wody 9999 albo NULL oznacza brak danych w bazie", "Przepływ 99999.999
        # albo NULL oznacza, że przepływ w tym dniu nie był opracowywany", "Temperatura 99.9 albo NULL oznacza brak
        # danych"; MIES_publiczne_format.txt: "MCWSKEX - Wskaźnik ekstremum (1 - minimum, 2 - średnia, 3 -
        # maksimum)" over the same three fields, read 2026-10-21
        ("daily", "hydrology", "przepływ"): (
            "Discharge (Przepływ), in m³/s, one value per day. The source's 99999.999 or NULL, a discharge that was "
            "not worked out for the day, is null."
        ),
        ("daily", "hydrology", "stan wody"): (
            "Water level (Stan wody), in cm, one value per day. The source's 9999 or NULL (no data) is null."
        ),
        ("daily", "hydrology", "temperatura wody"): (
            "Water temperature (Temperatura wody), in °C, one value per day. The source's 99.9 or NULL (no data, for "
            "instance at a station that measures no temperature) is null."
        ),
        ("monthly", "hydrology", "maksymalna przepływ"): (
            "Monthly maximum of the discharge (Przepływ), in m³/s (the extremum indicator of the file is 3). The "
            "source's 99999.999 or NULL, no data or gaps in the month's observations, is null."
        ),
        ("monthly", "hydrology", "maksymalna stan wody"): (
            "Monthly maximum of the water level (Stan wody), in cm (the extremum indicator of the file is 3). The "
            "source's 9999 or NULL, no data or gaps in the month's observations, is null."
        ),
        ("monthly", "hydrology", "maksymalna temperatura wody"): (
            "Monthly maximum of the water temperature (Temperatura wody), in °C (the extremum indicator of the file is "
            "3). The source's 99.9 or NULL, no data or gaps in the month's observations, is null."
        ),
        ("monthly", "hydrology", "minimalna przepływ"): (
            "Monthly minimum of the discharge (Przepływ), in m³/s (the extremum indicator of the file is 1). The "
            "source's 99999.999 or NULL, no data or gaps in the month's observations, is null."
        ),
        ("monthly", "hydrology", "minimalna stan wody"): (
            "Monthly minimum of the water level (Stan wody), in cm (the extremum indicator of the file is 1). The "
            "source's 9999 or NULL, no data or gaps in the month's observations, is null."
        ),
        ("monthly", "hydrology", "minimalna temperatura wody"): (
            "Monthly minimum of the water temperature (Temperatura wody), in °C (the extremum indicator of the file is "
            "1). The source's 99.9 or NULL, no data or gaps in the month's observations, is null."
        ),
        ("monthly", "hydrology", "średnia przepływ"): (
            "Monthly mean of the discharge (Przepływ), in m³/s (the extremum indicator of the file is 2). The source's "
            "99999.999 or NULL, no data or gaps in the month's observations, is null."
        ),
        ("monthly", "hydrology", "średnia stan wody"): (
            "Monthly mean of the water level (Stan wody), in cm (the extremum indicator of the file is 2). The "
            "source's 9999 or NULL, no data or gaps in the month's observations, is null."
        ),
        ("monthly", "hydrology", "średnia temperatura wody"): (
            "Monthly mean of the water temperature (Temperatura wody), in °C (the extremum indicator of the file is "
            "2). The source's 99.9 or NULL, no data or gaps in the month's observations, is null."
        ),
    },
    "ImgwMeteorologyMetadata": {
        # the wording is that of the Polish field lists (k_d, k_d_t, o_d, s_d, s_d_t, k_m_d, k_m_t, o_m, s_m_d and
        # s_m_t `_format.txt`, read 2026-10-21): "Średnia dobowa temperatura powietrza [°C]", "Średnie dobowe
        # zachmurzenie ogólne [oktanty]", "Maksymalna dobowa suma opadów w miesiącu [mm]" and so on. The files state
        # no more than that, so that the monthly statistics are those of the daily values is read off the data:
        # June 2020, monthly TMAX, TMIN, TMNG, TMXS, TMNS and STM against the max, min, min, mean, mean and mean of
        # the daily TMAX, TMIN, TMNG, TMAX, TMIN and STD to within 0.06 degC at 63 climate stations and 3 synop
        # stations (all of them), and o_m MAXO against the maximum and SUMM against the sum of the daily SMDB at
        # 596 stations (all of them)
        ("daily", "climate", "średnia dobowa wilgotność względna"): "Average daily relative humidity, in percent.",
        ("daily", "climate", "średnie dobowe zachmurzenie ogólne"): "Average daily total cloud cover, in oktas.",
        ("daily", "synop", "średnia dobowa wilgotność względna"): "Average daily relative humidity, in percent.",
        ("daily", "synop", "średnia dobowe ciśnienie na poziomie stacji"): (
            "Average daily air pressure at station level, in hPa."
        ),
        ("daily", "synop", "średnia dobowe ciśnienie pary wodnej"): "Average daily water vapor pressure, in hPa.",
        ("daily", "synop", "średnie dobowe zachmurzenie ogólne"): "Average daily total cloud cover, in oktas.",
        ("monthly", "climate", "średnia miesięczna wilgotność względna"): (
            "Average monthly relative humidity, in percent."
        ),
        ("monthly", "climate", "średnie miesięczne zachmurzenie ogólne"): (
            "Average monthly total cloud cover, in oktas."
        ),
        ("monthly", "synop", "średnia miesięczna wilgotność względna"): (
            "Average monthly relative humidity, in percent."
        ),
        ("monthly", "synop", "średnie miesięczne zachmurzenie ogólne"): "Average monthly total cloud cover, in oktas.",
        ("daily", "climate", "maksymalna temperatura dobowa"): (
            "Maximum daily air temperature, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("daily", "climate", "minimalna temperatura dobowa"): (
            "Minimum daily air temperature, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("daily", "climate", "suma dobowa opadów"): "Daily precipitation sum, in mm.",
        ("daily", "climate", "temperatura minimalna przy gruncie"): (
            "Minimum daily air temperature at the ground (przy gruncie), in °C." + _IMGW_NO_HEIGHT_GROUND
        ),
        ("daily", "climate", "wysokość pokrywy śnieżnej"): "Height of the snow cover, in cm.",
        ("daily", "climate", "średnia dobowa prędkość wiatru"): "Average daily wind speed, in m/s.",
        ("daily", "climate", "średnia dobowa temperatura"): (
            "Average daily air temperature, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("daily", "precipitation", "suma dobowa opadów"): (
            "Daily precipitation sum, in mm. The status Z marks an opad zbiorczy: the sum of the preceding days "
            "without a measurement, without saying when it fell."
        ),
        ("daily", "precipitation", "wysokość pokrywy śnieżnej"): "Height of the snow cover, in cm.",
        ("daily", "precipitation", "wysokość świeżospałego śniegu"): "Height of the freshly fallen snow, in cm.",
        ("daily", "synop", "maksymalna temperatura dobowa"): (
            "Maximum daily air temperature, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("daily", "synop", "minimalna temperatura dobowa"): (
            "Minimum daily air temperature, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("daily", "synop", "suma dobowa opadów"): "Daily precipitation sum, in mm.",
        ("daily", "synop", "temperatura minimalna przy gruncie"): (
            "Minimum daily air temperature at the ground (przy gruncie), in °C." + _IMGW_NO_HEIGHT_GROUND
        ),
        ("daily", "synop", "wysokość pokrywy śnieżnej"): "Height of the snow cover, in cm.",
        ("daily", "synop", "średnia dobowa prędkość wiatru"): "Average daily wind speed, in m/s.",
        ("daily", "synop", "średnia dobowa temperatura"): "Average daily air temperature, in °C." + _IMGW_NO_HEIGHT_2M,
        ("monthly", "climate", "absolutna temperatura maksymalna"): (
            "Absolute maximum air temperature of the month, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "climate", "absolutna temperatura minimalna"): (
            "Absolute minimum air temperature of the month, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "climate", "maksymalna dobowa suma opadów"): "Maximum daily precipitation sum of the month, in mm.",
        ("monthly", "climate", "maksymalna wysokość pokrywy śnieżnej"): (
            "Maximum height of the snow cover in the month, in cm. A 0 without a status means that there was no snow "
            "cover in the month or that the maximum cannot be determined."
        ),
        ("monthly", "climate", "miesieczna suma opadów"): "Monthly precipitation sum, in mm.",
        ("monthly", "climate", "minimalna temperatura przy gruncie"): (
            "Minimum air temperature of the month at the ground (przy gruncie), in °C." + _IMGW_NO_HEIGHT_GROUND
        ),
        ("monthly", "climate", "średnia miesięczna prędkość wiatru"): "Average monthly wind speed, in m/s.",
        ("monthly", "climate", "średnia miesięczna temperatura"): (
            "Average monthly air temperature (the mean of the daily means), in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "climate", "średnia temperatura maksymalna"): (
            "Average maximum air temperature of the month (the mean of the daily maxima), in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "climate", "średnia temperatura minimalna"): (
            "Average minimum air temperature of the month (the mean of the daily minima), in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "precipitation", "miesięczna suma opadów"): "Monthly precipitation sum, in mm.",
        ("monthly", "precipitation", "opad maksymalny"): (
            "Maximum precipitation of the month, in mm. The file names no period; it is the maximum daily sum of the "
            "month, as the climate and synop files state it."
        ),
        ("monthly", "synop", "absolutna temperatura maksymalna"): (
            "Absolute maximum air temperature of the month, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "synop", "absolutna temperatura minimalna"): (
            "Absolute minimum air temperature of the month, in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "synop", "maksymalna wysokość pokrywy śnieżnej"): (
            "Maximum height of the snow cover in the month, in cm."
        ),
        ("monthly", "synop", "miesięczna suma opadów"): "Monthly precipitation sum, in mm.",
        ("monthly", "synop", "minimalna temperatura przy gruncie"): (
            "Minimum air temperature of the month at the ground (przy gruncie), in °C." + _IMGW_NO_HEIGHT_GROUND
        ),
        ("monthly", "synop", "średnia miesięczna prędkość wiatru"): "Average monthly wind speed, in m/s.",
        ("monthly", "synop", "średnia miesięczna temperatura"): (
            "Average monthly air temperature (the mean of the daily means), in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "synop", "średnia temperatura maksymalna"): (
            "Average maximum air temperature of the month (the mean of the daily maxima), in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "synop", "średnia temperatura minimalna"): (
            "Average minimum air temperature of the month (the mean of the daily minima), in °C." + _IMGW_NO_HEIGHT_2M
        ),
        ("monthly", "synop", "średnie miesięczne ciśnienie na pozimie morza"): (
            "Average monthly air pressure at sea level, in hPa."
        ),
        ("monthly", "synop", "średnie miesięczne ciśnienie na poziomie stacji"): (
            "Average monthly air pressure at station level, in hPa."
        ),
        ("monthly", "synop", "średnie miesięczne ciśnienie pary wodnej"): (
            "Average monthly water vapor pressure, in hPa."
        ),
    },
    "NoaaGhcnMetadata": {
        ("daily", "data", "tavg"): (
            "Average daily temperature. From source 'S' an average of hourly readings for the period ending at 2400 "
            "UTC; from other sources computed in a variety of ways, including traditional fixed hours of the day."
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
            "total liquid precipitation (rain or melted snow), nominally for the hour: a METAR's amount is the "
            "running total since the last routine report, so one report of an hour is returned, the one filed at "
            "the station's routine minute (else the last one that is no SPECI, else the last one) of the UTC hour; "
            "a “T” in the measurement code column indicates a trace amount of precipitation (millimeters)"
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
        ("hourly", "data", "snow_depth"): "depth of snowpack on the ground (millimeters)",
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
            "270=west, etc.). Note: A direction of “000” is given for calm winds. (whole degrees) "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
        ("hourly", "data", "wind_gust"): (
            "Peak short duration (usually < 20 seconds) wind speed (meters per second) that exceeds "
            "the wind_speed average"
        ),
        ("hourly", "data", "wind_speed"): "Wind speed (meters per second)",
    },
    "NwsObservationMetadata": {
        # barometricPressure equals the altimeter setting of the METAR (A#### x 33.86389 Pa) at 9 stations (GH-2840)
        ("hourly", "data", "barometricpressure"): (
            "air pressure reduced to mean sea level with the standard atmosphere, the altimeter setting"
        ),
        ("hourly", "data", "dewpoint"): (
            "dew point temperature, to 0.1 °C in the METAR (the T group) and in whole degrees in the 5-minute rows"
        ),
        # not declared: the endpoint's `maxTemperatureLast24Hours` and `minTemperatureLast24Hours` (the OpenAPI
        # document describes no property) came back null in all 49,688 observations of 108 stations read on
        # 2026-10-21 (the last 500 of each, 2026-10-14 to 21), also where the METAR carries the 24 hour group: 33 of
        # 9,660 reports of 20 airports have it in the remarks (KORD 2026-10-21 05:51 UTC "402060067", maximum 20.6 and
        # minimum 6.7 degC) and none has the field set. A request for them is an unknown parameter
        # the 6RRRR group of the METAR: the 3 hour amount in the reports of 03, 09, 15 and 21 UTC, the 6 hour amount
        # in those of 00, 06, 12 and 18 UTC (KABQ 14:52 "60000" is the 3 hour amount of 15 UTC, KABQ 23:52 "60001"
        # the 6 hour amount of 00 UTC, 2026-10-20), and null in every other row
        ("hourly", "data", "precipitationlast3hours"): (
            "precipitation height of the last three hours, the 6RRRR group of the METAR of 03, 09, 15 and 21 UTC"
        ),
        ("hourly", "data", "precipitationlast6hours"): (
            "precipitation height of the last six hours, the 6RRRR group of the METAR of 00, 06, 12 and 18 UTC"
        ),
        # the endpoint's key is precipitationLastHour, and the amount of the METAR's precipitation group is the
        # running total since the last routine report (GH-2841): at KORD on 2026-10-15 the reports of 22:51 to 23:42
        # read 4.3, 0.8, 8.4, 17.3 and 17.5 mm (a total that restarts after 22:51 and grows), and the METAR of 23:51
        # 17.5 mm (P0069)
        ("hourly", "data", "precipitationlasthour"): (
            "precipitation group of the METAR or SPECI kept for the hour, the amount since the last routine METAR (a "
            "running total, which a routine report holds for the whole hour and a SPECI for the part that had fallen "
            "when it was filed); the endpoint calls it precipitationLastHour"
        ),
        # the API computes it: its values equal the August-Roche-Magnus formula (17.625, 243.04) on the temperature and
        # the dew point of the same row to six digits (10.0 and 8.3 degC: 89.181205 %, 9 and 8: 93.453995 %)
        ("hourly", "data", "relativehumidity"): (
            "relative humidity, calculated by the NWS from the air temperature and the dew point, not measured"
        ),
        # 102590 Pa beside "SLP259" in the METAR of KORD at 04:51 UTC on 2026-10-21; the 5-minute rows carry none
        ("hourly", "data", "sealevelpressure"): (
            "air pressure at sea level, the SLP group of the METAR (the 5-minute rows carry none)"
        ),
        ("hourly", "data", "temperature"): (
            "air temperature, to 0.1 °C in the METAR (the T group) and in whole degrees in the 5-minute rows"
        ),
        ("hourly", "data", "visibility"): "visibility range",
        ("hourly", "data", "windchill"): (
            "wind chill temperature calculated by NWS (https://www.weather.gov/gjt/windchill)"
        ),
        # ASOS User's Guide: "ASOS reports a 2-minute average" of the wind direction, and of the speed, and the
        # reportable gust is "the highest gust stored in memory for the past 10 minutes"
        ("hourly", "data", "winddirection"): (
            "wind direction, the 2-minute average of the ASOS. The source's 0 (a calm wind) is null."
        ),
        # the same guide, 3.2.2.2: "the greatest 5-second average speed observed during the past minute is stored in
        # memory as a gust for 10 minutes", and the highest of them is reported only if it is 3 knots or more above the
        # 2-minute average and exceeds the minimum 5-second wind of the 10 minutes by 10 knots or more
        ("hourly", "data", "windgust"): (
            "maximum wind gust of the past 10 minutes, the highest 5-second average wind speed the ASOS holds as "
            "a gust, reported only when its gust criteria are met"
        ),
        ("hourly", "data", "windspeed"): "wind speed, the 2-minute average of the ASOS",
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
            "Mean wind direction over the 10 minutes preceding the time given by 'fint' (degrees). "
            "The source's 0 beside a mean wind speed of 0 (a calm wind) is null."
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
        ("hourly", "data", "wd_10min"): (
            "Wind direction. Mean over 10 minutes. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
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
        ("hourly", "data", "DD"): "Past 10 minute mean wind direction, representative for 10 meters",
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
    # the observation section of the field list on https://api.meteo.lt/ (Lithuanian, read 2026-10-21), translated
    # sentence by sentence: "airTemperature - oro temperatūra, °C.", "windGust - vėjo gūsis, m/s. Maksimalus gūsis per
    # valandą.", "precipitation - kritulių kiekis, mm. Kritulių suma per valandą." and so on. It states no height for
    # any field, so the 2 m of the temperature's name is the shelter convention
    "LhmtObservationMetadata": {
        ("hourly", "data", "airTemperature"): (
            "Air temperature, °C. The source states no height; the 2 m of the name is the shelter convention."
        ),
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
        (
            "daily",
            "temperature",
            "max_air_temp",
        ): f"Maximum air temperature, to the nearest 0.1 deg C. {_MO_DAILY_STAMP}",
        (
            "daily",
            "temperature",
            "min_air_temp",
        ): f"Minimum air temperature, to the nearest 0.1 deg C. {_MO_DAILY_STAMP}",
        ("daily", "temperature", "min_grss_temp"): (
            f"Minimum grass temperature, to the nearest 0.1 deg C. {_MO_DAILY_STAMP}"
        ),
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
            'Direct irradiation amount, kJ per square metre over the observation period: "the solar radiation coming '
            'directly from the sun but not from the rest of the sky", measured with a pyrheliometer on a sun tracker '
            '"at normal incidence" (MIDAS table RO), so the energy on a plane perpendicular to the sun\'s rays and '
            "no component on a horizontal surface. The documentation says MIDAS holds no direct radiation past "
            "December 1997."
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
        ("hourly", "weather", "cld_ttl_amt_id"): (
            "Total cloud amount code, in oktas. The source's 9, the sky obscured (the tables name no code for it), is "
            "null."
        ),
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
            "Wind direction, that from which the wind blows, in degrees true. An east wind is 090, a south wind 180. "
            'The ten minute wind of a SYNOP or a METAR: the mean wind table is not for "Ten minute winds recorded in '
            'SYNOPs and METARs - they are stored in the UK Hourly Weather table". '
            "The source's 0 beside a wind speed of 0 (a calm wind) is null."
        ),
        ("hourly", "weather", "wind_speed"): (
            'Wind speed, knots. The ten minute wind of a SYNOP or a METAR: the mean wind table is not for "Ten minute '
            'winds recorded in SYNOPs and METARs - they are stored in the UK Hourly Weather table".'
        ),
        ("hourly", "weather", "wmo_hr_sun_dur"): (
            "Readings from the newer automatic sun sensor, which has replaced the Campbell Stokes recorder."
        ),
        ("hourly", "wind", "max_gust_dir"): (
            "Direction of the maximum gust, degrees true. "
            "The source's 0 beside a gust speed of 0 (a calm wind) is null."
        ),
        ("hourly", "wind", "max_gust_speed"): "Speed of the maximum gust, knots.",
        ("hourly", "wind", "mean_wind_dir"): (
            "Mean wind direction, that from which the wind blows, in degrees true. An east wind is 090, a south wind "
            "180. The source's 0 beside a mean wind speed of 0 (a calm wind) is null."
        ),
        ("hourly", "wind", "mean_wind_speed"): "Mean wind speed, knots.",
    },
    "MeteoFranceObservationMetadata": {
        ("6_minutes", "data", "RR"): "Precipitation amount over 6 minutes.",
        ("daily", "core", "DXI"): (
            "Direction of FXI, on the 360 degree compass. The source's 999 (probably variable) is null, and its 0 "
            "beside an FXI of 0 (a calm wind); a 0 beside a wind that blows stays."
        ),
        ("daily", "core", "FFM"): "Daily mean of the wind force averaged over 10 minutes, at 10 m.",
        ("daily", "core", "FXI"): "Daily maximum of the hourly maximum instantaneous wind force, at 10 m.",
        ("daily", "core", "RR"): (
            "Precipitation amount over 24 hours, from 06h FU on day J to 06h FU on day J+1 (the source writes its "
            "hours in UTC for metropolitan France and in FU overseas). The value recorded at J+1 is attributed to day "
            "J."
        ),
        ("daily", "core", "TM"): "Daily mean of the hourly air temperatures under shelter.",
        ("daily", "core", "TN"): "Minimum air temperature under shelter.",
        ("daily", "core", "TX"): "Maximum air temperature under shelter.",
        ("daily", "others", "GLOT"): "Daily global radiation.",
        ("daily", "others", "HNEIGEF"): (
            "Depth of fresh snow fallen over 24 hours, from 06h FU on day J to 06h FU on day J+1, that remains on the "
            "ground at 06h FU (the source writes its hours in UTC for metropolitan France and in FU overseas). The "
            "value recorded at J+1 is attributed to day J."
        ),
        ("daily", "others", "INST"): "Daily sunshine duration.",
        ("daily", "others", "NEIGETOT06"): "Total depth of snow on the ground measured at 06h.",
        ("daily", "others", "PMERM"): "Daily mean of the hourly sea level pressures.",
        ("daily", "others", "TSVM"): "Mean vapour pressure.",
        ("daily", "others", "UM"): "Daily mean of the hourly relative humidities.",
        ("hourly", "core", "DD"): (
            "Direction of FF, the wind force averaged over 10 minutes, on the 360 degree compass. The source's 999 "
            "(probably variable) is null, and its 0 beside an FF of 0 (a calm wind); a 0 beside a wind that blows "
            "stays."
        ),
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
        ("10_minutes", "data", "dkl010z0"): (
            "Wind direction; ten minutes mean. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
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
        ("daily", "data", "dkl010d0"): (
            "Wind direction; daily mean. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
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
        ("hourly", "data", "dkl010h0"): (
            "Wind direction; hourly mean. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
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
        ("6_hours", "data", "sum(precipitation_amount PT6H)"): "Amount of precipitation per six hours",
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
    # The parameter listing of the metobs API ("summary", e.g. "medelvärde 1 dygn, 1 gång/dygn, kl 00"), translated:
    # the first sentence and the statistic. What the listing leaves out comes from the CSV of each station (read
    # 2026-10-21): the "Från Datum Tid (UTC)" and "Till Datum Tid (UTC)" columns of the daily and monthly files give the
    # window of each value, and the station header's "Mäthöjd (meter över marken)" was 2.0 for temperature, dew point,
    # humidity and visibility and 10.0 for wind and gust at all of 25 active stations sampled for each (precipitation:
    # 21 of 25 at 2.0, the others 1.4 to 4.6, which is why it states none). The windows are the same in the corrected
    # archive and in the last months: parameter 2 (mean) 00:00:01 to 00:00:00 UTC, dated by that day; 19 and 20
    # (minimum, maximum) 18:00:01 of the day before to 18:00:00 UTC, dated by the day they end on (hourly 21, the
    # gust, says "Samplingstid = 1 timme" in the footer of its CSV, which is the "over the hour"); 5 (precipitation)
    # 06:00:01 to 06:00:00 UTC of the next day, dated by the day they begin on; 22 (monthly mean) the calendar month;
    # 23 (monthly sum) 06:00:01 of the 1st to 06:00:00 of the 1st of the next month. The monthly temperature is the
    # mean of the daily means (356 of 356 months at Stockholm-Observatoriekullen, 684 of 686 at Göteborg A); the
    # listing does not say so. The monthly precipitation equals the sum of the daily values in 37 of 43 and 532 of 544
    # months, and the others were not traced, so the description says only the window
    "SmhiObservationMetadata": {
        ("1_minute", "data", "43"): "Relative humidity at 2 m. Instantaneous value, every minute.",
        ("1_minute", "data", "44"): "Air pressure reduced to sea level. Instantaneous value, every minute.",
        ("1_minute", "data", "45"): "Air temperature at 2 m. Instantaneous value, every minute.",
        ("1_minute", "data", "46"): "Precipitation amount. Precipitation during one minute.",
        ("1_minute", "data", "47"): "Wind speed at 10 m. One minute mean, every minute.",
        (
            "1_minute",
            "data",
            "48",
        ): (
            "Wind direction at 10 m. One minute mean, every minute. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
        ("1_minute", "data", "51"): "Visibility. One minute mean, every minute.",
        ("1_minute", "data", "52"): "Snow depth. Instantaneous value, every minute.",
        ("daily", "data", "19"): (
            "Air temperature at 2 m. Minimum, once per day, over the 24 hours ending at 18:00 UTC of the day it is "
            "dated."
        ),
        ("daily", "data", "2"): (
            "Air temperature at 2 m. Daily mean, once per day at 00, over the 24 hours from 00:00 UTC of the day it "
            "is dated to 00:00 UTC of the next."
        ),
        ("daily", "data", "20"): (
            "Air temperature at 2 m. Maximum, once per day, over the 24 hours ending at 18:00 UTC of the day it is "
            "dated."
        ),
        ("daily", "data", "5"): (
            "Precipitation amount. Daily sum, once per day at 06, over the 24 hours from 06:00 UTC of the day it is "
            "dated to 06:00 UTC of the next day."
        ),
        ("daily", "data", "8"): "Snow depth. Instantaneous value, once per day at 06 UTC.",
        ("hourly", "data", "1"): "Air temperature at 2 m. Instantaneous value, once per hour.",
        ("hourly", "data", "12"): "Visibility. Instantaneous value, once per hour.",
        ("hourly", "data", "16"): "Total cloud amount. Instantaneous value, once per hour.",
        ("hourly", "data", "21"): "Wind gust at 10 m. Maximum over the hour, once per hour.",
        (
            "hourly",
            "data",
            "3",
        ): (
            "Wind direction at 10 m. Mean over 10 minutes, once per hour. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
        ("hourly", "data", "39"): "Dew point temperature at 2 m. Instantaneous value, once per hour.",
        ("hourly", "data", "4"): "Wind speed at 10 m. Mean over 10 minutes, once per hour.",
        ("hourly", "data", "6"): "Relative humidity at 2 m. Instantaneous value, once per hour.",
        ("hourly", "data", "7"): "Precipitation amount. Hourly sum, once per hour.",
        ("hourly", "data", "9"): "Air pressure reduced to sea level. Instantaneous value, once per hour.",
        ("monthly", "data", "22"): (
            "Air temperature at 2 m. Mean, once per month: the mean of the daily means of the calendar month (UTC)."
        ),
        ("monthly", "data", "23"): (
            "Precipitation amount. Sum, once per month, over the month from 06:00 UTC of its first day to 06:00 UTC "
            "of the first day of the next month."
        ),
    },
    # the field list on api.ipma.pt, translated; it says "média da hora" (the mean of the hour) of temperatura, humidade
    # and pressao ("temperatura do ar registada a 1.5 metros de altura", "humidade relativa do ar registada a 1.5 metros
    # de altura", "pressão atmosférica, reduzida ao nível médio do mar (NMM)"), and of the other four: "intensidade do
    # vento registada a 10 metros de altura (m/s)", "classe do rumo do vento ao rumo predominante do vento registado a
    # 10 metros de altura (0: sem rumo, 1 ou 9: "N", 2: "NE", ...)", "precipitação registada a 1.5 metros de altura,
    # valor acumulado da hora (mm)" and "radiação solar (kJ/m2)", which states no period. The 133 stations of the feed
    # of 2026-10-20/21 that report a radiation: most read 0 at night and, at 13 UTC, the median of the 128 that
    # answer is about 2,200 kJ/m2, which suggests an energy over the hour, but the highest are 3,746 to 3,875 kJ/m2 at
    # 12 to 15 UTC, above the top-of-atmosphere irradiation of the hour around solar noon on 21 October (about 3,000
    # to 3,340 on the mainland, 3,290 at Ponta Delgada, 3,600 on Madeira; the 3,746 is Viana do Castelo at 41.7N, the
    # 3,783 Paredes de Coura - Vascões at 41.9N, the 3,779 to 3,875 Ponta Delgada at 13 to 15 UTC), and the night
    # maximum reaches 1,079 at 02 UTC, so neither the period nor the kind of the value is settled; the source states
    # none of it
    "IpmaObservationMetadata": {
        ("hourly", "data", "humidade"): "Relative humidity of the air recorded at 1.5 m height, hourly mean.",
        ("hourly", "data", "idDireccVento"): (
            'Class of the predominant wind direction recorded at 10 m height ("classe do rumo do vento"): 0 no '
            "direction, 1 or 9 north, 2 north-east, 3 east, 4 south-east, 5 south, 6 south-west, 7 west, 8 north-west, "
            "returned as degrees (0 to 315). The code 0 (sem rumo) is returned as null, whether the wind blows or not. "
            "The source states no period."
        ),
        ("hourly", "data", "intensidadeVento"): (
            "Wind speed recorded at 10 m height. The source states no statistic and no period."
        ),
        ("hourly", "data", "precAcumulada"): (
            "Precipitation recorded at 1.5 m height, accumulated over the hour (the source's valor acumulado da hora)."
        ),
        ("hourly", "data", "pressao"): "Atmospheric pressure reduced to mean sea level (NMM), hourly mean.",
        ("hourly", "data", "radiacao"): (
            "Solar radiation (radiação solar) in kJ/m². The source states neither a period nor that it is global or "
            "on a horizontal surface; the daily course suggests an energy accumulated over the hour, though the "
            "highest values exceed what one hour delivers at the top of the atmosphere."
        ),
        ("hourly", "data", "temperatura"): "Air temperature recorded at 1.5 m height, hourly mean.",
    },
    # `t` is "température" in the technical description of the SYNOP product
    # (OBSERVATIONS_Descriptif_Technique_Données_SYNOP_OMM.pdf), with no window; the 12 and 24 hour
    # extremes are the ones that state one. The same sheet: "dd direction du vent moyen 10 min" (int, degré)
    # and "ff vitesse du vent moyen 10 min" (réel, m/s), though the files hold whole numbers only (2927 of 2927
    # stamps of Orly 2024 equal the hourly FF of the climatological base cut to the integer)
    "MeteoFranceSynopMetadata": {
        # the sheet: "raf10 rafales sur les 10 dernières minutes", beside "rafper rafales sur une période"
        ("subdaily", "data", "raf10"): "Gusts over the last 10 minutes, in m/s.",
        ("subdaily", "data", "dd"): (
            "Direction of the mean wind over 10 minutes, in steps of 10 degrees, north being 360. "
            "The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays."
        ),
        (
            "subdaily",
            "data",
            "ff",
        ): "Speed of the mean wind over 10 minutes, in whole m/s (the mean cut to the integer).",
        ("subdaily", "data", "t"): "Temperature.",
    },
}


# one sentence per dataset, phrased as the `heating_degreedays` sibling is: each of the three covers a
# single reference temperature, so the docs page's shared blurb naming all three would over-claim here,
# where `discover`, the REST API and MCP report it for one dataset at a time
def _cooling_degreehours(reference: int) -> str:
    """Describe the cooling_degreehours dataset taken against one reference temperature."""
    return (
        "Data on cooling degree hours, comparing the hourly temperatures to the reference "
        f"temperature of {reference} degree Celsius."
    )


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
        ("monthly", "cooling_degreehours_13"): _cooling_degreehours(13),
        ("monthly", "cooling_degreehours_16"): _cooling_degreehours(16),
        ("monthly", "cooling_degreehours_18"): _cooling_degreehours(18),
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
            "Direct model output of the global ICON model, extracted at worldwide stations. "
            "Issued twice a day (00 and 12 UTC) as two runs: hourly out to a lead-time of 78 "
            "hours, and 3-hourly from 78 to 168 hours."
        ),
        ("hourly", "icon_eu"): (
            "Direct model output of the regional ICON-EU model, extracted at the stations it is "
            "published for, a smaller set than the global product's though not a subset of it. "
            "Issued twice a day (00 and 12 UTC), hourly out to a lead-time of 78 hours."
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
            "Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, "
            "graupel and hail for stations of Germany (details missing, parameter descriptions "
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
            "Daily weather events fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, hoar frost, "
            "graupel and hail at stations of Germany (details missing, parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("daily", "weather_phenomena_more"): (
            "Daily (additional) weather events graupel, hail, fog and thunder at stations of Germany (details "
            "missing, parameter descriptions "
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
            "Counts of weather phenomena fog, thunder, storm (strong wind), storm (stormier wind), dew, glaze, "
            "graupel and hail for stations of Germany (details missing, parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "cloudiness"): (
            "Recent subdaily cloud cover and cloud density of stations in Germany (details missing, "
            "parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "moisture"): (
            "Recent subdaily vapor pressure, wet bulb temperature, ice on the wet bulb thermometer and relative "
            "humidity of stations in Germany (details missing, parameter descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "pressure"): (
            "Recent air pressure at site of stations in Germany (details missing, parameter "
            "descriptions "
            "[here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx))."
        ),
        ("subdaily", "soil"): (
            "Recent subdaily coded ground state of stations in Germany (details missing, parameter descriptions "
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
    "DwdMosmixMetadata": {
        ("hourly", "small"): (
            "Local forecast of 40 parameters for worldwide stations, 24 times a day with a lead-time of 240 hours."
        ),
        ("hourly", "large"): (
            "Local forecast of 114 parameters for worldwide stations, 4 times a day with a lead-time of 240 hours."
        ),
    },
    "DwdRoadMetadata": {
        ("15_minutes", "data"): "15-minute road weather data of German highway stations.",
    },
    "DwdPoiMetadata": {
        ("hourly", "data"): "Hourly weather reports of the last day, for the stations DWD forecasts for.",
    },
    "EAHydrologyMetadata": {
        ("15_minutes", "data"): (
            "Historical 15 minute station observations of flow, river water level and groundwater level for the UK."
        ),
        ("daily", "data"): "Historical daily station observations of flow and river water level for the UK.",
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
        # the titles of the datasets on the API, "Stationsdaten-v2 (10 min): Stationsdaten für Österreich in
        # zehnminütiger Auflösung mit Qualitätsinformationen" and so on for 1 h, 1 d and 1 m. These said "for Germany"
        # and, for three of them, "of 2m air temperature and humidity", which is a fraction of what they hold
        ("10_minutes", "data"): "Historical 10-minute station observations for Austria, with quality information.",
        ("daily", "data"): "Historical daily station observations for Austria, with quality information.",
        ("hourly", "data"): "Historical hourly station observations for Austria, with quality information.",
        ("monthly", "data"): "Historical monthly station observations for Austria, with quality information.",
    },
    "HubeauMetadata": {(resolution, "data"): "Flow and stage for France." for resolution in _HUBEAU_RESOLUTIONS},
    "ImgwHydrologyMetadata": {
        ("daily", "hydrology"): "historical daily hydrology data.",
        ("monthly", "hydrology"): "historical monthly hydrology data.",
    },
    "ImgwMeteorologyMetadata": {
        ("daily", "climate"): "historical daily climate data.",
        ("daily", "precipitation"): "historical daily precipitation data.",
        ("daily", "synop"): "historical daily synop data.",
        ("monthly", "climate"): "historical monthly climate data.",
        ("monthly", "precipitation"): "historical monthly precipitation data.",
        ("monthly", "synop"): "historical monthly synop data.",
    },
    "NoaaGhcnMetadata": {
        ("daily", "data"): "Historical daily weather data from the Global Historical Climatology Network (GHCN).",
        ("hourly", "data"): "Historical hourly weather data from the Global Historical Climatology Network (GHCN).",
    },
    "NwsObservationMetadata": {
        ("hourly", "data"): (
            "Station observations (temperature, pressure, precipitation, etc.) for the US, one report for each "
            "hour: the METAR or SPECI report nearest to the full hour, else the nearest 5-minute row."
        ),
    },
    "WsvPegelMetadata": {
        (resolution, "data"): (
            "Recent data (last 31 days) of German waterways including water level and discharge for "
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
        "6_hours": "Synoptic observations reported every six hours.",
    },
}

# Derived rather than sourced: DWD publishes no prose for these fields in either language, so the
# text is taken from the same canonical parameter at the same resolution elsewhere -- same quantity
# over the same interval. Where that is just the canonical sentence in ``parameter_table`` there is
# no entry: the model falls back to the canonical sentence itself. Kept apart from
# SOURCE_DESCRIPTIONS so that a description here is not mistaken for the wording of the source itself,
# and applied only where nothing else supplies one.
#
# An entry may also be *narrower* than the canonical sentence where the field is narrower: the three
# ``Kuehltage`` below count days with at least one cooling hour, which is what DWD's Kuehltage is,
# while canonical ``count_days_cooling_degree`` keeps the general "days on which cooling was required"
# because cooling degree days elsewhere are defined against a base temperature. Their
# ``count_days_heating_degree`` sibling is split the same way. So a difference from `parameter_table`
# here is not necessarily drift to be reconciled.
DERIVED_DESCRIPTIONS: dict[str, dict[tuple[str, str, str], str]] = {
    "DwdDerivedMetadata": {
        ("monthly", "cooling_degreehours_13", "Kuehltage"): "Number of days with at least one cooling hour.",
        ("monthly", "cooling_degreehours_16", "Kuehltage"): "Number of days with at least one cooling hour.",
        ("monthly", "cooling_degreehours_18", "Kuehltage"): "Number of days with at least one cooling hour.",
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
        ("subdaily", "wind", "qn_4"): "Quality flag published by the source for the values in the same dataset.",
    },
    "DmiObservationMetadata": {
        # DMI's documentation (https://www.dmi.dk/friedata/dokumentation/climate-data): "Maximum 30 minutes intensity in
        # 24 hours with date", "is found by inspecting the period from 23:31 local time to the previous day to 24.00
        # local time of the respective day"; "Maximum 24-hour precipitation with associated date", "the highest of
        # the underlying daily values of acc_precip" (GH-2614)
        ("daily", "data", "max_precip_30m"): (
            "Largest precipitation depth in any 30 minutes of the day, found from 23:31 local time of the previous "
            "day to 24:00 local time of the day."
        ),
        ("monthly", "data", "max_precip_24h"): (
            "Largest daily precipitation total of the month, the highest of the underlying daily values."
        ),
        ("annual", "data", "max_precip_24h"): (
            "Largest daily precipitation total of the year, the highest of the underlying daily values."
        ),
        ("annual", "data", "mean_wind_dir"): _DMI_MEAN_WIND_DIRECTION,
        ("daily", "data", "mean_wind_dir"): _DMI_MEAN_WIND_DIRECTION,
        ("hourly", "data", "mean_wind_dir"): _DMI_MEAN_WIND_DIRECTION,
        ("monthly", "data", "mean_wind_dir"): _DMI_MEAN_WIND_DIRECTION,
    },
    "ImgwMeteorologyMetadata": {
        ("monthly", "synop", "maksymalna dobowa suma opadów"): "precipitation height max",
    },
    "MeteoFranceSynopMetadata": {
        ("subdaily", "data", "td"): (
            "Dew point at 2 m above ground, the temperature at which the air would become saturated."
        ),
    },
}
