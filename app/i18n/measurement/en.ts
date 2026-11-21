/**
 * "How weather is measured" in English (GH-3787).
 *
 * The English text is the one a reader of a language that has no text of its own sees (the page says so). Every
 * statement rests on a source of the entry's `sources`, by volume, chapter and section, or on the provider's own file,
 * which the entry names; a statement that no source supports is not here. `de.ts` says the same, entry for entry
 * (`tests/unit/measurement.test.ts` holds the two to each other).
 *
 * The editions of the WMO Guide are the current ones of each volume: the 2024 edition of Volumes I and II (checked
 * against the official PDFs, whose chapters 2, 5 and 8 of Volume I and chapter 2 of Volume II are the text of the 2023
 * edition) and the 2023 edition of Volume V. The provisional 2026 edition is not used.
 */

import type { MeasurementSource, MeasurementTexts } from './types'

const WMO_I = 'https://library.wmo.int/records/item/68695-guide-to-instruments-and-methods-of-observation'
const WMO_II = 'https://library.wmo.int/records/item/68660-guide-to-instruments-and-methods-of-observation'
const WMO_V = 'https://library.wmo.int/records/item/68663-guide-to-instruments-and-methods-of-observation'
const DWD_DAILY = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/DESCRIPTION_obsgermany-climate-daily-kl_en.pdf'

/** Where the station files of the daily data are: they have no address of their own, they are inside the archive of each station */
const DWD_KL = 'opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/'
const STATION_FILES = `DWD Climate Data Center, files inside the station archives of ${DWD_KL}recent/ (tageswerte_KL_03987_akt.zip, tageswerte_KL_01420_akt.zip) and ${DWD_KL}historical/ (tageswerte_KL_01048_19340101_20251231_hist.zip), read on 20 November 2026 for Potsdam (03987), Dresden-Klotzsche (01048) and Frankfurt/Main (01420):`

/** The hourly datasets of the DWD: the station files of the entries on pressure, humidity, radiation and visibility are inside the archives of these folders */
const DWD_HOURLY = 'opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/'
const DWD_HOURLY_PRESSURE = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/DESCRIPTION_obsgermany_climate_hourly_pressure_en.pdf'
const DWD_HOURLY_HUMIDITY = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/DESCRIPTION_obsgermany_climate_hourly_air_temperature_en.pdf'
const DWD_HOURLY_SOLAR = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/DESCRIPTION_obsgermany_climate_hourly_solar_en.pdf'
const DWD_HOURLY_VISIBILITY = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/DESCRIPTION_obsgermany_climate_hourly_visibility_en.pdf'
const NOAA_GHCNH = 'https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf'

const DWD_HOURLY_CLOUDINESS = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloudiness/DESCRIPTION_obsgermany_climate_hourly_cloudiness_en.pdf'
const DWD_HOURLY_WEATHER = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/DESCRIPTION_obsgermany_climate_hourly_weather_phenomena_en.pdf'
/** The derived soil dataset of the DWD: evaporation and soil moisture are calculated by a model (the English description is the monthly one) */
const DWD_SOIL_MONTHLY = 'https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/monthly/recent/DESCRIPTION_derived_germany-soil-monthly-v2_en.pdf'
const KNMI_DAILY = 'https://www.knmi.nl/nederland-nu/klimatologie/daggegevens'
const NOAA_GHCN_DAILY = 'https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt'

/** KNMI's daily data, which the entries on evaporation and clouds name where providers differ */
function knmi(plain: string, citation: string): MeasurementSource {
  return {
    plain: `The Royal Netherlands Meteorological Institute (KNMI) is the national weather service of the Netherlands. ${plain}`,
    citation,
    href: KNMI_DAILY,
  }
}

/** NOAA's daily dataset, which the entries on evaporation, present weather and clouds name where providers differ */
function ghcnDaily(plain: string, citation: string): MeasurementSource {
  return {
    plain: `The National Centers for Environmental Information (NCEI) of the United States' NOAA publish GHCN-Daily, the daily observations of weather stations. ${plain}`,
    citation,
    href: NOAA_GHCN_DAILY,
  }
}

/** NOAA's hourly dataset, which the entries on pressure, humidity and visibility name where providers differ */
function ghcnh(plain: string, citation: string): MeasurementSource {
  return {
    plain: `The National Centers for Environmental Information (NCEI) of the United States' NOAA publish GHCNh, the hourly observations of weather stations from all over the world. ${plain}`,
    citation: `NOAA NCEI. Global Historical Climatology Network hourly (GHCNh), documentation, version 1.1.0 (10 March 2026). ${citation}`,
    href: NOAA_GHCNH,
  }
}

/** What the WMO is, once, for every entry that cites its Guide */
const WMO_PLAIN = 'The World Meteorological Organization (WMO) is the United Nations agency in which the national weather services agree on how weather is measured and compared. Its Guide to Instruments and Methods of Observation is the handbook for it.'

/** Volumes I and II: the 2024 edition, the current one */
function wmoGuide(plain: string, citation: string, href: string): MeasurementSource {
  return { plain: `${WMO_PLAIN} ${plain}`, citation: `WMO (2024). Guide to Instruments and Methods of Observation (WMO-No. 8), 2024 edition. ${citation}`, href }
}

/** Volume V: its 2023 edition is the current one */
function wmoGuideV(plain: string, citation: string): MeasurementSource {
  return { plain: `${WMO_PLAIN} ${plain}`, citation: `WMO (2023). Guide to Instruments and Methods of Observation (WMO-No. 8), 2023 edition. ${citation}`, href: WMO_V }
}

function dwdFiles(plain: string, citation: string, href: string): MeasurementSource {
  return { plain: `The Deutscher Wetterdienst (DWD) is Germany's national weather service. ${plain}`, citation, href }
}

export const measurement: MeasurementTexts = {
  'temperature': {
    title: 'Air and soil temperature',
    summary: 'Why the air temperature is read about two metres above the ground in a shaded, ventilated housing, and what that means for the number.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'A weather station measures air temperature with an electrical thermometer, most often a platinum resistance thermometer: a wire or film of platinum whose electrical resistance changes with the temperature (the usual format is called Pt100). WMO names electrical thermometers as the recommended instruments.',
          'By WMO\'s definition, air temperature is what a thermometer shows when it is exposed to the air in a place sheltered from direct sunshine. Sunshine, clouds and the ground send out radiation that passes through air without warming it much, but a thermometer in the open absorbs it. With ordinary instruments the reading can then be wrong by as much as 25 K under extremely unfavourable conditions. So the thermometer sits in a screen, which shields it from the radiation and from rain and still lets the air flow through.',
          'The standard height is between 1.25 and 2 m above the ground, over natural ground, preferably grass, on level ground in the open and not close to trees or buildings. The height is fixed because the lowest layer of the air can have large vertical temperature differences.',
          'Soil temperature is measured at the standard depths of 5, 10, 20, 50 and 100 cm, on a level plot of bare ground. The grass minimum temperature, the lowest temperature of a night, is measured 5 cm above short grass.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'The air temperature changes by a degree or two within seconds, so a single reading says little. The thermometer is meant to be slow enough to smooth this out (WMO recommends a time constant of about 20 seconds). For international exchange and for many operational applications, a reported measurement is an average and stands, by convention, for the previous 1 to 10 minutes (for wind, 2 or 10 minutes).',
          'The highest and the lowest temperature of a period come from the record itself: when an electrical thermometer is recorded continuously and often enough, the extremes are found in the measured data and no separate maximum or minimum thermometer is needed.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'On a day of strong sunshine and light wind, the air in a naturally ventilated louvred screen can be warmer than the true air temperature, and on a clear, calm night slightly cooler; WMO gives errors of up to about 2.5 K and -0.5 K in extreme cases. Too little air flow through the screen (wind below 1 m/s), above all in strong sunshine, and a wet screen or sensor after rain, which is cooled by evaporation, are other sources of error.',
          'One station is not the whole area. The reading should represent the free air around the station, but in towns local differences are larger, and readings on a roof are of doubtful use. A change of the screen, of the vegetation or of the buildings around a station changes what it reads, which matters when years are compared.',
          'A soil temperature describes a patch of bare ground of about 2 m by 2 m. It depends on the soil, its cover and the slope, which is why WMO asks for these to be recorded.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'There is no single screen for the whole world. WMO notes that it is difficult to recommend one design for worldwide measurements, because applications, the degree of automation and the climate differ, and very different screens are in use.',
          'DWD lists, for every station, the instrument and its height above the ground in the files that come with the data. At Potsdam, for example, the air temperature has been measured with a Pt100 thermometer at 2 m since 1978, and the minimum temperature at 5 cm above the ground with a Pt100 since 1986.',
          'The stretch of time a daily maximum or minimum covers is the provider\'s choice. In DWD\'s daily data it is 00:00 to 24:00 UTC from April 2001, at the stations checked, and the daily mean is the arithmetic mean of at least 21 hourly values. See "Time" for the day other providers use.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 2 on temperature is where this entry takes the definition, the height, the screen and the typical errors from.',
        'Volume I, Chapter 2 (Measurement of temperature), sections 2.1.1, 2.1.3.3, 2.1.4, 2.1.4.1, 2.1.4.2, 2.1.4.3, 2.2.1.1, 2.2.3, 2.5, 2.5.1.',
        WMO_I,
      ),
      wmoGuideV(
        'Volume V, Chapter 3 on data reduction is where this entry takes the rule that a reported value stands for the previous 1 to 10 minutes.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), section 3.5.',
      ),
      dwdFiles(
        'The files that come with each station\'s data say which instrument it used, at which height, and what a daily value covers.',
        `${STATION_FILES} Metadaten_Geraete_Lufttemperatur_*, Metadaten_Geraete_Lufttemp_Am_Erdb_Minimum_* and Metadaten_Parameter_klima_tag_*; dataset description "Daily station observations (temperature, pressure, precipitation, sunshine duration, etc.) for Germany", version v24.3 (2024).`,
        DWD_DAILY,
      ),
    ],
  },

  'pressure': {
    title: 'Pressure, and its reduction to sea level',
    summary: 'Air pressure is the weight of the air above the station. To compare stations at different heights it is calculated to sea level, and that number is a calculation, not a reading.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'Atmospheric pressure is the force that the weight of the air above a surface exerts on each unit of its area. The unit is the pascal; in meteorology it is the hectopascal (hPa), which is 100 Pa and the same as the older millibar.',
          'Pressure is measured most often with electronic or aneroid barometers. In an aneroid barometer, a sealed, partly emptied metal capsule is pressed in by the air, a spring keeps it from collapsing, and the deformation is read mechanically or electrically. Electronic barometers turn the pressure into an electrical signal, for example by measuring how far a thin diaphragm of silicon, ceramic or metal bends, how a quartz element is squeezed, or how the vibration frequency of a thin cylinder changes. Mercury barometers are still in use, but WMO no longer recommends them.',
          'The barometer needs a place without draughts and a solid mounting that does not vibrate. Wind is a common source of error: a strong, gusty wind changes the pressure in the room where the barometer stands, and these fluctuations are superimposed on the static pressure and may amount to up to 2 or 3 hPa. Air conditioning can create a pressure difference between a room and the outside. A static head, an inlet that couples the barometer to the air outside, avoids most of this.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'A barometer is normally set to read the pressure at its own height, the station pressure. Like other readings it is averaged: WMO\'s table of requirements gives 1 minute for the output of a pressure measurement, and a reported value stands, by convention, for the previous 1 to 10 minutes.',
          'Since pressure is the weight of the air above, readings of stations at different heights cannot be compared as they are. WMO says they must be reduced to the same level, and recommends mean sea level for every station where this can be done with reasonable accuracy. The reduction is calculated from the station pressure, the height of the station, the temperature at the station and the water vapour pressure there, for an imagined column of air between the station and sea level, in which the temperature is assumed to fall by 0.0065 K for each metre of height. WMO gives this formula for stations below 750 m, and a simpler one for stations below 50 m, which adds a constant to the station pressure.',
          'The pressure tendency is how the pressure changed over the last three hours: the difference between the reading at the end and the one at the start. The error of a single reading is mainly random, so in a difference the random errors can add up. WMO notes, though, that errors are partly systematic and likely to have the same sign within three hours, and that this part is diminished by the subtraction.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'WMO asks for an uncertainty of 0.1 hPa and lists 0.15 hPa as what is achievable in operation; a well-made aneroid barometer can reach 0.3 hPa. Barometers drift between calibrations, above all when they are new, which WMO calls one of the key sources of error, and it suggests checking them often, at first about once a year.',
          'Even these figures need protection from the wind: WMO notes that the uncertainty is seriously affected by the dynamic pressure of the wind if no precautions are taken, and that a sensor whose temperature is not compensated well enough can be affected significantly.',
          'The pressure at sea level is not measured at sea level. It is a calculation of what the pressure would be at the point below the station, so it carries the errors of everything that goes into it: the station pressure, the height of the station and the temperature assumed for the imagined column of air. Where a reduction to sea level cannot be done with reasonable accuracy, WMO asks a station to report something else instead: the height of an agreed pressure level, or the pressure reduced to an agreed level for that station.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'Providers publish different pressures, and the names matter. NOAA\'s hourly dataset GHCNh has three: the station-level pressure, observed at the station; the sea-level pressure, calculated with the temperatures that actually exist at the station; and the altimeter setting, calculated with the temperature profile of a "standard" atmosphere that stands for average conditions over the United States at 40 degrees north. The last two are both reduced to sea level, and they are not the same number. Wetterdienst keeps them apart: pressure_air_site is the pressure at station height, pressure_air_sea_level the pressure reduced to mean sea level, and pressure_air_site_reduced the altimeter setting, reduced with the standard atmosphere.',
          'DWD\'s hourly pressure data has two values for each station, the pressure reduced to sea level ("NN") and the pressure at station height. Its station files say that both come from the SYNOP weather reports of the station, the internationally coded observations, and that the times are in UTC.',
          'The instrument is in the station files too. At Potsdam, which stands 80.86 m above sea level, DWD lists a digital barometer of the type PTB 330 since 20 November 2015, a digital barometer of the type AIR-DB from 1992 to 2015 and a conventional station barometer before; from 1986 to 1992 an electronic absolute-pressure transducer (ADMW) ran beside the station barometer.',
          'Wetterdienst returns the pressure in hectopascal by default, whichever unit the provider uses.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 3 on atmospheric pressure is where this entry takes the definition, the barometers, the effect of the wind, the typical errors and the reduction to sea level from. Chapter 1 of the same volume holds the table of the uncertainties WMO asks for.',
        'Volume I, Chapter 3 (Measurement of atmospheric pressure), sections 3.1.1, 3.1.2, 3.1.4.1, 3.1.4.2, 3.1.4.3.2, 3.1.4.3.3, 3.2.1, 3.2.2, 3.2.3, 3.2.6, 3.2.7.1, 3.3.1, 3.3.2, 3.5.1, 3.5.2, 3.7, 3.7.1, 3.7.2, 3.7.3; Volume I, Chapter 1 (General), Annex 1.A, row 3.1.',
        WMO_I,
      ),
      wmoGuideV(
        'Volume V, Chapter 3 on data reduction is where this entry takes the rule that a reported value stands for the previous 1 to 10 minutes.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), section 3.5.',
      ),
      ghcnh(
        'Its documentation says what each element is, among them the three kinds of pressure this entry names.',
        'Section IV (List of Elements/Variables), Table 1: station_level_pressure, sea_level_pressure, altimeter.',
      ),
      dwdFiles(
        'The files that come with each station\'s data say which instrument it used, at which height, and where the values come from.',
        `DWD Climate Data Center, files inside the station archive stundenwerte_P0_03987_akt.zip in ${DWD_HOURLY}pressure/recent/, read on 21 November 2026 for Potsdam (03987): Metadaten_Geraete_Luftdruck_Reduziert_*, Metadaten_Geraete_Luftdruck_Stationshoehe_*, Metadaten_Parameter_p0_stunde_* and Metadaten_Geographie_*; dataset description "Hourly station observations of pressure for Germany" (version v24.03, 2024).`,
        DWD_HOURLY_PRESSURE,
      ),
    ],
  },

  'humidity': {
    title: 'Humidity and dew point',
    summary: 'Humidity is said in several ways. Relative humidity is a percentage that depends on the temperature, and the dew point is usually calculated, not measured.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'Humidity is how much water vapour the air holds, and it is said in several ways. The relative humidity is the share, in per cent, of the water vapour pressure that is present compared with the highest it could be at that temperature and pressure, when the air is saturated. The dew point is the temperature at which the air would be saturated with water vapour; if the air is cooled to it, dew or frost can form. The vapour pressure is the part of the air pressure that the water vapour makes up. The absolute humidity is the mass of water vapour in a volume of air.',
          'Any instrument that measures humidity is a hygrometer. The leading technology today is the electronic, capacitive hygrometer: a thin polymer film between two electrodes takes up water vapour from the air, which changes its electrical properties, and the change is read as a relative humidity. A psychrometer has two thermometers side by side, one of them with a wet sleeve; the water that evaporates cools it, and the drier the air, the larger the difference between the two. Psychrometers are still in use, though more and more replaced by electronic sensors. Below freezing the wet sleeve is covered with a thin layer of ice, and the calculation differs for a bulb coated with ice and one coated with supercooled water. A chilled-mirror hygrometer cools a small mirror until dew or frost forms on it and measures the temperature of the mirror, which is the dew point; it is mostly used as a reference.',
          'The sensor sits in a screen like the one of the thermometer, protected from direct sunshine, dirt, rain and wind, and its housing must not make a small climate of its own around it. A temperature measurement is always needed alongside, because the relative humidity depends strongly on the temperature and because other quantities, such as the dew point, are calculated from the two.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'What a hygrometer gives is a relative humidity. The dew point is calculated from it and from the air temperature, with formulae that WMO adopted in 1990, unless it is measured directly with a chilled mirror.',
          'A humidity value, like the other values, is an average that stands for the previous 1 to 10 minutes. WMO says that a time constant of about 1 minute suits most purposes, and its table of requirements lists 40 seconds for solid-state sensors and 20 seconds for the dew point.',
          'WMO notes that averaging a variable that does not change in proportion is difficult when it changes during the averaging period. For the dew point, its table names the absolute humidity as the quantity to average, and says that dew point, relative humidity and air temperature are linked, and so are their uncertainties.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'WMO asks for an uncertainty of 1 % relative humidity and 0.1 K for the dew point, and lists what is achievable in operation: 3 % for solid-state sensors and 0.25 K for the dew point. It adds that these uncertainties are not easy to reach in practice, even with good instruments that are well kept, and that a psychrometer in a screen without forced ventilation may be significantly worse.',
          'Electronic sensors age. Dirt, sea spray or chemicals on the sensor can make it read too high at low humidity and too low at high humidity, or in some other pattern. In damp air, with dew or fog, a sensor drifts, most often upwards, so that it can show 100 % at 95 %. A sensor warmed above the air temperature, for example in a screen heated by the sun, reads falsely low. For electronic sensors in weather stations in damp climates, WMO gives a lifetime that is commonly between six months and two or more years.',
          'A temperature error carries into everything that is calculated with it: when the dew point is calculated from the relative humidity, an error of 0.1 °C near 20 °C has the same effect as an error of 0.6 % relative humidity. For a psychrometer, an error of 0.5 K in the wet-bulb temperature means an error of 4 % relative humidity at 20 °C and of 27 % at -20 °C, for a true relative humidity of 50 %, and WMO says that psychrometers are less accurate at low humidity.',
          'Below 0 °C, WMO says, the relative humidity is to be evaluated with respect to water, not ice: most hygrometers show it that way, most clouds below 0 °C consist of water or mainly of water, values above 100 % would in general not be observed, and most older records are on this basis.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'DWD\'s station files say where the hourly values come from. At Frankfurt/Main, the relative humidity comes from the paper records of a thermohygrograph until October 1993, in MEZ, from automatic stations until 1 April 2001, and from SYNOP weather reports, the internationally coded observations, since; the hourly dew point comes from SYNOP reports in all periods. The times are in UTC, except for the records until 1993.',
          'The files name the sensor and its height too. At Frankfurt/Main the relative humidity has been measured 2 m above the ground with an electronic sensor of the type EE33 since 5 December 2015, before that with a probe of the type HMP45D from February 2012; a conventional recording thermohygrograph was in use until August 2022.',
          'Providers also differ in what they call humidity. NOAA\'s GHCNh says that, depending on the source, its relative humidity is either measured directly or calculated from the air temperature and the dew point, and says the same of its wet-bulb temperature. Wetterdienst gives the relative humidity in per cent and the dew point in °C by default.',
          'Whether a provider\'s daily or monthly mean of the relative humidity or the dew point is formed from the values as they are, or from the absolute humidity as WMO advises for averaging, is for the provider\'s own documentation to say; this entry does not assume either.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 4 on humidity is where this entry takes the definitions, the instruments, the typical errors and the rule for below 0 °C from. Chapter 1 of the same volume holds the table of the uncertainties WMO asks for.',
        'Volume I, Chapter 4 (Measurement of humidity), sections 4.1.1, 4.1.3, 4.1.4.1.1, 4.1.4.1.2, 4.1.4.1.3, 4.1.4.2, 4.2.2, 4.2.3, 4.2.5, 4.2.7, 4.3.1.4, 4.3.1.8, Table 4.1, Annex 4.A (paragraphs 3 and 17); Volume I, Chapter 1 (General), Annex 1.A, rows 2.1 and 2.2 and note 11.',
        WMO_I,
      ),
      wmoGuideV(
        'Volume V, Chapter 3 on data reduction is where this entry takes the rule that a reported value stands for the previous 1 to 10 minutes, and the quantity to average for a dew point.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), sections 3.5, 3.6.',
      ),
      ghcnh(
        'Its documentation says what each element is, and how the relative humidity and the wet-bulb temperature were found.',
        'Section IV (List of Elements/Variables), Table 1: relative_humidity, wet_bulb_temperature.',
      ),
      dwdFiles(
        'The files that come with each station\'s data say which sensor it used, at which height, and where the values come from.',
        `DWD Climate Data Center, files inside the station archives stundenwerte_TU_01420_akt.zip (${DWD_HOURLY}air_temperature/recent/) and stundenwerte_TD_01420_akt.zip (${DWD_HOURLY}dew_point/recent/), read on 21 November 2026 for Frankfurt/Main (01420): Metadaten_Geraete_Rel_Feuchte_*, Metadaten_Parameter_tu_stunde_* and Metadaten_Parameter_td_stunde_*; dataset descriptions "Hourly station observations of 2 m air temperature and humidity for Germany" and "Hourly station observations of air and dew point temperature for Germany" (version v24.03, 2024).`,
        DWD_HOURLY_HUMIDITY,
      ),
    ],
  },

  'wind': {
    title: 'Wind: mean speed and gusts',
    summary: 'A mean wind is an average over ten minutes, a gust is the highest short peak, and both depend on where the anemometer stands.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'Surface wind is measured with a cup or propeller anemometer for the speed and a wind vane for the direction. Sonic anemometers, which time an ultrasonic pulse over a fixed distance, are in use too; having no moving parts, they are durable. The standard height is 10 m above open, level ground, because the wind speed increases considerably with height. Open means that the nearest obstacle is at least ten times as far away as it is high. The direction is the direction the wind blows from, in degrees clockwise from true north.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'The speed and the direction of a weather report are an average over 10 minutes. Climate statistics usually use averages over each whole hour, day and night.',
          'A peak gust is the highest wind speed observed in a stated interval; in an hourly report it is the highest in the last full hour. WMO recommends measuring a gust over about 3 seconds, which suits most users, and says that a 1-minute "average" is a long gust, not a mean wind.',
          'How sharp a gust is depends on how fast the instrument reacts: a slow one smears out the extremes, a fast one records high, narrow peaks. For gusts of different stations to be comparable, WMO says, the response of the whole measuring chain has to be specified with care; it recommends a gust duration of about 3 seconds.',
          'The Beaufort scale from 0 to 12 turns a wind speed at 10 m into a description. Force 7, a near gale, is 13.9 to 17.1 m/s, for example.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'WMO calls the exposure of the anemometer the most difficult aspect of wind measurement, and finds it nearly impossible to find a place where the wind is representative of a large area. A mast in the wake of trees or buildings tells little about the undisturbed wind. Closer than 20 times the height of an obstacle, the value can be wrong by up to 25 % before it is corrected.',
          'Cup and propeller sensors speed up faster than they slow down, and vertical gusts add to this, so their average reads too high in a gusty wind; WMO gives a total overspeeding of up to 10 % for some designs in turbulent wind over very rough terrain.',
          'Because the wind is stronger higher up, a sensor at another height than 10 m reads a different speed.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'DWD\'s station files give the type and the height of each wind sensor, and the height is not always 10 m: at Potsdam the ultrasonic anemometer is 37.7 m above the ground.',
          'DWD\'s 10-minute wind is a 10-minute mean. Its station files describe the daily mean wind as the arithmetic mean of at least 21 hourly means, made from 10-minute means, and the daily maximum gust as the highest one from 23:51 to 23:50 UTC; this is so since September 2003 at the stations checked.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 5 on surface wind is where this entry takes the definitions of the mean wind and the gust, the standard height and the typical errors from.',
        'Volume I, Chapter 5 (Measurement of surface wind), sections 5.1.1, 5.1.2, 5.1.3, 5.1.4, 5.4, 5.6, 5.8.2, 5.9.1, 5.9.2 and Table 5.1.',
        WMO_I,
      ),
      dwdFiles(
        'The files that come with each station\'s data say which instrument it used, at which height, and what a daily value covers.',
        `${STATION_FILES} Metadaten_Geraete_Windgeschwindigkeit_* and Metadaten_Parameter_klima_tag_*; dataset description "10-minute station observations of wind for Germany" (version v24.03, 2024).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/DESCRIPTION_obsgermany_climate_10min_wind_en.pdf',
      ),
    ],
  },

  'precipitation': {
    title: 'Precipitation',
    summary: 'Rain and snow are caught in a gauge and measured as a depth. What the gauge catches is not exactly what falls, and snow in wind is the hardest case.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'Precipitation is the liquid or solid water that falls from clouds as rain, drizzle, snow, snow grains, snow pellets, hail or ice pellets, or falls from clear air as diamond dust. It is measured as the vertical depth of water that would cover a flat patch of ground, with snow counted as the water it melts to. One millimetre is one litre on every square metre.',
          'A gauge is an open receptacle with vertical sides, usually a cylinder, with a funnel if it is meant mainly for rain; the volume or the weight of the catch is measured. A manual gauge stores the water in a container that is read at fixed times, a weighing gauge weighs it, and a tipping-bucket gauge counts how often a small bucket tips when it has filled with a fixed amount of water (0.1 to 0.5 mm in the gauges of an international survey). Instruments that catch nothing and measure with light or radar are in use as well.',
          'If significant amounts of snow are expected, the opening of the gauge has to be at least 200 cm²; openings of 200 to 500 cm² are the most common. WMO recommends shielding the gauge where wind is expected to take a significant part of the catch, naturally, in a clearing in a forest, or artificially, with a windshield, above all for snow. It also asks that obstacles stand no closer than twice their height above the opening, and that gauges are not put on a slope or a roof.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'The amount of a period is the total that reached the ground in that period, in millimetres. An amount below 0.1 mm is called a trace. The intensity is the amount per unit of time, usually in millimetres per hour; WMO recommends at least one minute as the interval to derive it from, because it varies so much from minute to minute.',
          'A manual gauge is read at fixed times that are the same for the whole network, to the nearest 0.2 mm and, if possible, 0.1 mm. That is why the "day" of a precipitation measurement runs from one reading to the next, which need not be midnight (see "Time"). A weighing gauge gives the amount of an interval as the difference of the weight of its bucket between the start and the end of the interval.',
          'A measured amount can be adjusted to come closer to the true amount, with a transfer function that uses the wind speed and the air temperature of the station. WMO asks archives to keep both the adjusted and the unadjusted amount and to document the adjustment, so that the unadjusted amount can be recovered if the adjustment is revised.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'Wind bends the air around a gauge, and some of what would have fallen into it is carried past the opening. For rain this is typically 2 to 10 % (up to 10 % against a gauge in a pit). For snow it is typically 10 to 50 % or more, and the bias of gauges for solid or mixed precipitation is typically 30 % or higher, depending on the exposure, the wind at the height of the gauge and the crystals; snow is less dense than rain and is carried past more easily. Shielding reduces this but generally does not remove it.',
          'Water that wets the inner walls of a manual gauge stays behind: an average of up to 0.2 mm per observation, typically 2 to 15 % of the measured values in summer and 1 to 8 % in winter, and more when the gauge is read often. Water also evaporates from the container: losses of over 0.8 mm a day have been reported in late spring at mid-latitudes in gauges without a funnel, and 0.1 to 0.2 mm a day in winter. Splashing into and out of the gauge changes the catch by 1 to 2 %. Wetting is small for weighing gauges.',
          'A tipping-bucket gauge that is not corrected can report up to 20 % too little in heavy rain in some gauges, because water is lost while the bucket tips (a dynamic calibration and a correction reduce this), and it records in steps: a bucket of 0.2 mm gives an intensity per minute in steps of 12 mm/h.',
          'A gauge measures one spot. Even the best measurement represents only a limited area, and obstacles, topography and wind around it add or take away precipitation locally.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'Gauge heights, sizes and shapes of the opening differ between countries, and WMO says that measurements are therefore not strictly comparable; in more than 100 countries, the most common height of the opening lies between 0.5 and 1.5 m. The type of the gauge differs too: manual, weighing, tipping bucket, or instruments that catch nothing.',
          'DWD lists every gauge of a station and its height in the files that come with the data. At Potsdam, for example, a PLUVIO gauge stood 1 m above the ground from 2009, and since 2017 a rain[e]H3 gauge that weighs the water stands at the same height.',
          'DWD\'s 10-minute value is the sum of the previous 10 minutes; for the PLUVIO gauge, since November 2008, a value stamped 11:50 UTC is the interval that ended at 11:45 UTC. Its hourly value is an hourly sum, and its daily value covers 06:00 to 06:00 UTC of the next day (see "Time").',
          'Whether a provider adjusts its amounts for the losses above is for the provider\'s own documentation to say; this entry does not assume either.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 6 on precipitation is where this entry takes the definition, the gauges, the typical errors, the shielding and the transfer functions from.',
        'Volume I, Chapter 6 (Measurement of precipitation), sections 6.1.1, 6.1.2, 6.1.3, 6.2.1, 6.2.1.2, 6.2.2, 6.2.3, 6.2.3.1, 6.2.5, 6.3.1.1, 6.3.2.1, 6.3.2.2, 6.3.2.4, 6.4.2, 6.5, 6.5.2, 6.6.',
        WMO_I,
      ),
      dwdFiles(
        'The files that come with each station\'s data say which gauge it used, at which height, and what a value covers.',
        `${STATION_FILES} Metadaten_Geraete_Niederschlagshoehe_* and Metadaten_Parameter_klima_tag_*; dataset description "10-minute station observations of precipitation for Germany" (version v24.03, 2024).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/DESCRIPTION_obsgermany-climate-10min-precipitation_en.pdf',
      ),
    ],
  },

  'radiation': {
    title: 'Radiation',
    summary: 'Radiation is energy from the sun and the sky that falls on a horizontal surface. It is stated as a power at a moment or as an energy added up over an hour or a day, and the two are easily confused.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'WMO distinguishes two kinds. Solar radiation comes from the sun; 97 % of the energy of the sun\'s radiation outside the atmosphere lies between 290 and 3000 nm in wavelength, which is why solar radiation is also called short-wave radiation. Part of it reaches the ground, and part is scattered or absorbed on the way by gas molecules, particles and cloud droplets. Terrestrial radiation is the long-wave radiation of the Earth\'s surface and of the gases, particles and clouds of the atmosphere, with wavelengths from 3000 to 100000 nm.',
          'Global radiation is the solar radiation that arrives on a horizontal surface from the whole sky: the direct beam from the sun\'s disc plus the diffuse sky radiation, the sunlight that has been scattered in the atmosphere. It is measured with a pyranometer, which looks at the whole sky and measures wavelengths from 300 to 3000 nm. To measure the diffuse radiation alone, a small disc or a shadow band keeps the direct sunlight off the pyranometer.',
          'The direct beam is measured with a pyrheliometer, which looks only at the sun and a narrow ring of sky around it and is kept pointed at the sun by a sun tracker. A pyrgeometer measures the long-wave radiation that comes down from the sky, and a pair of instruments, one looking up and one looking down, gives the net radiation, the difference between what comes down and what goes up. Sunshine duration, which is derived from the direct beam, has its own entry: see "Sunshine duration".',
          'A pyranometer needs a site with no obstruction above the level of the sensor, no light-coloured wall nearby that could reflect the sun onto it, and, in the directions where the sun rises and sets over the year, nothing higher than 5 degrees above the horizon. It has to be level, and WMO asks for it to be inspected at least daily: the glass dome is wiped clean and dry, and any frost or snow on it is removed.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'Two kinds of number are in use. The irradiance is a power per area, in watts per square metre (W/m²), at a moment or averaged over a short time. The radiant exposure is an energy per area, in joules per square metre (J/m²), over a stated period, such as an hour or a day. A mean irradiance of 100 W/m² over an hour is a radiant exposure of 0.36 MJ/m². WMO notes that these are the quantities most commonly recorded, with averages and totals of over 1 hour, and that daily totals are frequently used, but expressed as a mean daily irradiance.',
          'A reading is made often and added up. WMO asks for samples taken more often than the time constant of the instrument, even when only the total of an hour or more is kept in the end.',
          'WMO asks for radiation measurements to be referred to true solar time, the time of the sun\'s own position, which differs from the clock time of a place. Universal time (UTC) is accepted for automatic systems if the data are sampled and stored often enough that converting them to true solar time loses no significant information. So the "hour" of a radiation value can be in either, and a provider may publish both (see "Time").',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'How exact the number is depends on the instrument. WMO sorts pyranometers into high, good and moderate quality and lists what they can achieve with good facilities, well-trained staff and quality control, at a 95 % confidence level, under clear skies and not counting calibration errors: hourly totals within 3 %, 8 % or 20 %, and daily totals within 2 %, 5 % or 10 %. Moderate-quality pyranometers are not suitable for hourly or daily totals, though they may do for monthly and yearly ones. For a daily total from one pyranometer without other measurements, WMO calls an uncertainty better than 5 % the result of good and careful work.',
          'Several things add errors: a pyranometer that is not level, dirt or dew on its dome, and a response that depends on the angle of the sun and on the temperature of the instrument. For the diffuse radiation, WMO names the signal that the sensor shows even when no light arrives, the zero irradiance signal, as a significant error source: in clear sky it is the equivalent of 5 to 10 W/m² and could approach 15 % of the diffuse radiation. The diffuse radiation from a cloudless sky may be less than a tenth of the global radiation.',
          'A building, a tree or a hill that hides the sun or part of the sky, or a light wall that reflects sunlight onto the sensor, changes the reading, which is why WMO asks for the horizon around the station and the height of the sensor to be described.',
          'The long-wave radiation is more difficult still: WMO writes that its measurement is still more difficult and less understood than that of solar irradiance. A net radiation can be negative, since more energy can leave the ground than arrives.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'DWD\'s hourly radiation data are sums over the hour, in J/cm², of the global radiation, the diffuse radiation and the long-wave radiation from the sky, with the sunshine duration in minutes; its 10-minute data are sums of the previous 10 minutes. The hourly files have two time stamps, one in UTC and one in local true solar time (WOZ).',
          'Wetterdienst returns the energy in MJ/m² by default (1 J/cm² is 0.01 MJ/m²) and a mean power, which some providers publish instead, in W/m². Energy and power are different quantities and are not interchangeable: radiation_global is an energy summed over the interval, radiation_global_intensity_mean a power.',
          'The instruments are in the station files. At Potsdam, DWD lists a CM11 pyranometer for the global radiation from 2009 to 2020 and a CMP22 since 29 July 2021, both 33 m above the ground, and for the radiation from the sky a CG4 pyrgeometer until 2021 and a CGR4 since.',
          'Some providers publish the direct radiation as it falls on a plane that faces the sun (wetterdienst: radiation_sky_short_wave_direct_perpendicular), which is what a pyrheliometer measures. It is not a part of the global radiation on a horizontal surface, which is the direct radiation multiplied by the cosine of the sun\'s zenith angle, the angle from straight overhead, plus the diffuse radiation, and it can exceed it.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 7 on radiation is where this entry takes the definitions, the instruments, the sites and the typical errors from.',
        'Volume I, Chapter 7 (Measurement of radiation), sections 7.1.1, 7.1.3.1, 7.1.3.3, 7.1.3.4, 7.2, 7.3, 7.3.2, 7.3.2.5, 7.3.3, 7.3.3.3, 7.3.3.5, 7.4, 7.4.1, 7.4.5, Table 7.4, Annex 7.B.',
        WMO_I,
      ),
      dwdFiles(
        'The files that come with each station\'s data say which instrument it used, at which height, and what a value covers.',
        `DWD Climate Data Center, files inside the station archive stundenwerte_ST_03987_row.zip in ${DWD_HOURLY}solar/, read on 21 November 2026 for Potsdam (03987): Metadaten_Geraete_Global_Kw_J_*, Metadaten_Geraete_Atmosphaere_Lw_J_* and Metadaten_Parameter_st_stunde_*; dataset descriptions "Hourly station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany" and "10-minute station observations of solar and sunshine for Germany" (version v24.03, 2024).`,
        DWD_HOURLY_SOLAR,
      ),
    ],
  },

  'sunshine': {
    title: 'Sunshine duration',
    summary: 'The hours of sunshine are the time the direct beam of the sun is strong enough, not the time without clouds.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'WMO defines the sunshine duration of a period as the sum of the time during which the direct solar irradiance exceeds 120 W per square metre. The threshold was chosen to match the point at which the sun burns the card of the Campbell-Stokes recorder, the simple instrument that has been in use at weather stations since 1880.',
          'More and more, sensors measure it instead of paper: a pyrheliometer that measures the direct beam, pyranometers that measure global and diffuse radiation from which the direct beam is calculated, or devices with several sensors. WMO no longer recommends the burn method, because it does not record the duration of bright sunshine consistently enough.',
          'The detector needs an uninterrupted view of the sun whenever the sun is more than 3 degrees above the horizon.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'Sunshine duration is a time, in seconds or hours, for a stated period such as a day, a month or a year; the period is part of the unit. It is also given as a share of the sunshine that was possible.',
          'From a single pyranometer, the sunshine of each 10 minutes or each minute is estimated from the measured irradiance with a calculation (WMO describes two, the Slob and Monna method and the Carpentras method), and the daily value is the sum of these.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'WMO asks for an uncertainty of 0.1 h and a resolution of 0.1 h. A daily total calculated from one pyranometer is less certain: for the Slob and Monna method WMO gives about 0.6 h and notes that later work found the expanded uncertainty of daily totals can exceed 1 h, and for the Carpentras method an expanded uncertainty of about 0.7 h.',
          'Instruments and methods give different values. Even the first recorders, built without international rules, gave different durations. Thin, high cloud that weakens the beam to around the threshold is the hardest case, because a small error of the threshold then changes the result a lot.',
          'Sunshine duration and cloud cover are related only on average: the relation does not hold for high, thin cloud or for clouds that do not cover the sun.',
          'A hill or a building that hides the sun at a low angle shortens the measured duration. In mountain valleys WMO accepts natural obstructions as part of the local climate, if they are documented.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'The instrument differs between stations and changes over time. At Potsdam, DWD lists a Campbell-Stokes recorder until March 2005, a SONIe sensor from August 1992 to January 2025 and a CMP22 pyranometer since then.',
          'DWD\'s daily sunshine duration is in hours for 00:00 to 24:00 UTC at the stations checked, and its hourly value is in minutes.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 8 on sunshine duration is where this entry takes the definition, the instruments and the typical errors from.',
        'Volume I, Chapter 8 (Measurement of sunshine duration), sections 8.1, 8.1.1, 8.1.2, 8.1.3, 8.1.3.2, 8.1.3.3, 8.1.4, 8.2.2.1, 8.3.',
        WMO_I,
      ),
      dwdFiles(
        'The files that come with each station\'s data say which instrument it used and what a daily value covers.',
        `${STATION_FILES} Metadaten_Geraete_Sonnenscheindauer_* and Metadaten_Parameter_klima_tag_*; dataset description "Hourly station observations of sunshine duration for Germany" (version v24.03, 2024).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/DESCRIPTION_obsgermany_climate_hourly_sun_en.pdf',
      ),
    ],
  },

  'visibility': {
    title: 'Visibility',
    summary: 'Visibility is how far one can see. An instrument cannot look: it measures how strongly the air weakens light, and the distance is calculated from that.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'WMO defines visibility by day as the greatest distance at which a black object of suitable size on the ground can be seen and recognised against the sky at the horizon. What a person sees depends on the person, so WMO uses a measure that instruments can find too, the meteorological optical range (MOR): the length of path in the air that reduces the light of a narrow beam from a lamp to 5 % of its original value. It is given in metres or kilometres.',
          'By eye, an observer judges the distance to objects that are known: by day dark objects against the sky, such as groups of trees, towers or masts, at night lights of known strength. Each station prepares a plan of these objects with their distances and directions, and the observer looks from about 1.5 m above the ground, not from a tall building. At night the eyes need 5 to 15 minutes to get used to the dark.',
          'Instruments measure how strongly the air weakens light, the extinction coefficient. A transmissometer sends a beam of light over a known distance, from a few metres up to 150 m (or even 300 m), and measures how much of it arrives. A forward-scatter meter shines light into a small volume of air and measures how much is scattered towards a receiver; it needs little space and is used in more and more automatic stations. WMO says the volume of air measured should normally be at the height of an observer\'s eyes, about 1.5 m above the ground, and that the sun must never be in the receiver\'s field of view.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'From the extinction coefficient the instrument calculates the MOR: it is about 3 divided by the extinction coefficient. This assumes that the air along the whole path is like the air in the small volume that the instrument looks at.',
          'The extinction coefficient of a small volume of air fluctuates quickly and irregularly, so many samples are averaged. WMO\'s first international intercomparison of visibility measurements found no gain from averaging over more than 1 minute for most instruments, and 2 minutes for the noisiest ones. WMO\'s table lists output averaging times of 1 and 10 minutes, and advises that, when averaging, the extinction coefficient is the quantity to average, not the visibility.',
          'Reported visibilities come in steps that get coarser as the distance grows: in the code of the synoptic report, 100 m steps from 100 to 5000 m, 1 km steps from 6 to 30 km and 5 km steps from 35 to 70 km. This is because the errors of visibility measurements grow in proportion to the visibility.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'A person and an instrument do not see the same. WMO calls any visual estimate subjective. In its first international intercomparison, observers estimated about 15 % more than the instruments by day and about 30 % more in the dark. At night the estimate depends on the lights that are there and on the adaptation of the observer\'s eyes, and WMO calls it particularly problematic.',
          'An instrument reads one small volume of air. It gives a good MOR only if that volume is like the air around the station out to a distance of the MOR; with patchy fog or a local shower of rain or snow it can mislead, and WMO says that instrumental measurements of MOR must be interpreted with caution. The step from the extinction coefficient to the distance holds for fog droplets; when rain, snow or blowing sand reduce the visibility, WMO says that the values should be treated with more care.',
          'WMO asks for an uncertainty of 50 m up to 600 m, 10 % between 600 and 1500 m, and 20 % above 1500 m, and lists the larger of 20 m or 20 % as what is achievable. Instruments differ: the best forward-scatter meters reached a standard deviation of about 10 % over a range from about 100 m to 50 km, but forward-scatter meters were generally less accurate than transmissometers at low visibility and more affected by precipitation, and cobwebs or flying insects in the measuring volume can make one read too low.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'DWD\'s hourly visibility is in metres, with an indicator that says whether a value was observed by a person (P) or measured by an instrument (I). In the recent files of the three stations checked, every value is marked I. Of the values from 19 May 2025 on, 87 to 93 % at these stations are not on the steps of the synoptic code (for example 32280 m), and DWD\'s description says why: with automatic measurements the range of values depends on the instrument, and the frequency distribution of the visibility is station-dependent and not necessarily constant over time. The station files name SYNOP weather reports, the internationally coded observations, as the source of the values, and the times are in UTC.',
          'The station files name the instrument and its height. DWD lists a visibility sensor of the type FS11, 2.5 m above the ground, since 30 October 2018 at Potsdam (a DF20+, 2.3 m above the ground, before it from 2009), since 14 October 2019 at Dresden-Klotzsche and since 6 August 2021 at Frankfurt/Main. WMO says that the volume of air measured should normally be at about 1.5 m.',
          'Providers differ in the unit too: NOAA\'s GHCNh gives the visibility in kilometres, DWD in metres, and wetterdienst returns metres by default. Some provide only the mean over a period (visibility_mean) or a class of the visibility (visibility_index), a code and not a distance. A forecast of the visibility is not a measurement either: see "Observation, forecast and derived data".',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 9 on visibility is where this entry takes the definitions, the observation by eye, the instruments, the averaging and the typical errors from. Chapter 1 of the same volume holds the table of the uncertainties WMO asks for.',
        'Volume I, Chapter 9 (Measurement of visibility), sections 9.1.1, 9.1.2, 9.1.4, 9.2.1, 9.2.2, 9.2.3, 9.2.5, 9.3.2, 9.3.3, 9.3.4, 9.3.5.1, 9.3.6.1, 9.3.6.3; Volume I, Chapter 1 (General), Annex 1.A, row 8.1.',
        WMO_I,
      ),
      wmoGuideV(
        'Volume V, Chapter 3 on data reduction is where this entry takes the quantity to average for a visibility.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), section 3.6.',
      ),
      ghcnh(
        'Its documentation says what each element is, and in which unit.',
        'Section IV (List of Elements/Variables), Table 1: visibility.',
      ),
      dwdFiles(
        'The files that come with each station\'s data say which instrument it used, at which height, and where the values come from.',
        `DWD Climate Data Center, files inside the station archives stundenwerte_VV_03987_akt.zip, stundenwerte_VV_01048_akt.zip and stundenwerte_VV_01420_akt.zip in ${DWD_HOURLY}visibility/recent/, read on 21 November 2026 for Potsdam (03987), Dresden-Klotzsche (01048) and Frankfurt/Main (01420): Metadaten_Geraete_Sichtweite_*, Metadaten_Parameter_vv_stunde_* and the column V_VV_I of the data file; dataset description "Hourly station observations of visibility for Germany" (version v24.03, 2024, section "Uncertainties").`,
        DWD_HOURLY_VISIBILITY,
      ),
    ],
  },

  'evaporation': {
    title: 'Evaporation',
    summary: 'WMO says that measuring the evaporation of a whole field or lake directly is not practicable at present. Pans and lysimeters measure the water they lose; the rest is estimated or calculated.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'WMO keeps several quantities apart. Evaporation is the water that leaves an open water surface or the ground as vapour. Transpiration is the water that plants give off. Evapotranspiration is the sum from soil and plants when the ground has its natural moisture. Potential evapotranspiration is the most that could evaporate from a continuous cover of vegetation that is well supplied with water. WMO says that when "potential evapotranspiration" is used, the kind of evaporation and transpiration it contains must be stated clearly.',
          'WMO says that measuring the evaporation of a large natural water or land surface directly is not practicable at present. WMO says that the methods are generally indirect: a point measurement with an instrument, or a calculation from other measured quantities of the weather. Evaporation is given as a depth of water in millimetres, normally per day.',
          'Evaporation pans are frequently used in networks: an open tank of water whose level is read, and the loss of level, with the rain that fell taken into account, is the evaporation. The United States Class A pan, for example, is 25.4 cm deep and 120.7 cm across, and its water level is read with a hook gauge. A lysimeter is a vessel sunk into the ground, filled with soil and planted. It is a water budget: the evapotranspiration is the precipitation (and irrigation) minus the water that drains through the bottom minus the change in the water stored in the soil. WMO says that weighable lysimeters give reliable and precise short-term values if the necessary precautions in design, operation and siting are taken.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'The rate of evaporation is the amount of water that leaves a unit of area in a unit of time, written as the depth of liquid water that this amount would make. The unit of time is normally a day. For daily totals WMO asks for an uncertainty of 0.1 mm for amounts under 5 mm and 2 % for larger ones (at the 95 % confidence level), and it says that in principle the usual instruments could meet this but that difficulties with exposure and practical operation cause much larger errors. WMO mentions 1 mm as a figure proposed as achievable.',
          'Because direct measurement is not practicable, evaporation from natural surfaces is often calculated. WMO gives as an example the procedure of the Royal Netherlands Meteorological Institute (KNMI), after G. F. Makkink, which calculates the daily reference vegetation evaporation from the mean air temperature of the day and the day\'s amount of global radiation. WMO also says that the potential or reference evapotranspiration of vegetated land can be found with the methods used for lakes, adapted to vegetation, and that some methods add coefficients that depend on the growth stage of each crop.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'The water lost from a pan is not the water lost from a lake or a field. WMO says that the evaporation rate of a natural surface necessarily differs from that of an evaporimeter exposed to the same weather, because the two surfaces are physically different, and that the values of an evaporimeter cannot be used without adjustment as evaporation from a lake or as actual or potential evapotranspiration. Different evaporimeters and lysimeters measure physically different things, so the instrument and its exposure should be described precisely.',
          'The exposure matters. A pan above the ground evaporates more than a sunken one, mainly because its sides take up additional radiant energy; a sunken pan has smaller boundary effects but collects more dirt, its leaks are harder to find, and it exchanges heat with the soil. Heavy rain and very high winds are likely to splash water out of a pan and may invalidate the measurement. If a pan is too full, as much as 10 % or more of the rain that falls can splash out, which makes evaporation read too high; if the water is too low, the rim shades the water and evaporation falls by about 2.5 % for each centimetre below the reference level (in temperate regions).',
          'A lysimeter changes the ground it measures. WMO lists among the sources of error a restricted growth of the roots, a discontinuity between the plant cover inside the vessel and the surroundings, thermal differences from the surroundings, and a water budget that differs from the surroundings, for example through restricted drainage or because surface runoff and the lateral movement of soil water are prevented. There is no universal international standard lysimeter.',
          'The rate of evaporation depends on the weather and on the surface. WMO groups the meteorological factors as energy (supplied largely by solar and terrestrial radiation) and the transport of the vapour away (wind speed at the surface, and the difference in vapour pressure between the surface and the lower air), and the surface factors as the amount and state of the water, the roughness, and for plants their own characteristics and the availability of soil moisture. Either group can limit the rate.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'The evaporation that wetterdienst offers from DWD, in the derived dataset for soil, is calculated and not measured. DWD\'s description says that the values of evaporation, soil moisture and soil temperature were calculated for various places in Germany and are usually not measured. The values of evaporation and soil moisture come from the agrometeorological model AMBAV. The model\'s documentation names the Penman-Monteith equation as its core, and says that it takes routine weather reports as input, calculates in hourly or three-hourly steps and evaluates daily totals. DWD gives the "real" evaporation (reale Verdunstung) for grass, winter cereals and maize, each on a sand and on a loamy silt soil, and two potential evaporations over grass, one after the FAO method and one after Haude. DWD says that the FAO one is preferable to the one after Haude because many more influencing quantities are taken into account.',
          'The name of a parameter does not tell a forecast from a calculation. evapotranspiration_potential_last_24h is a forecast of DWD\'s MOSMIX (see "Observation, forecast and derived data"), and it is also the name of KNMI\'s EV24, which KNMI\'s file header names the potential evapotranspiration after Makkink, the procedure that WMO describes as a calculation from the mean air temperature and the global radiation of the day. evapotranspiration_potential_grass_fao is DWD\'s, from its model, and also MeteoSwiss\'s, whose documentation was not read, so nothing is said about how it is formed. NOAA\'s GHCN-Daily has a measured quantity: EVAP, the evaporation of water from an evaporation pan, with MDEV for a total over several days and DAEV for the number of days it covers, and the minimum and maximum temperature of the water in the pan. This page says nothing about the evaporation of other providers.',
          'So the names matter: wetterdienst\'s evaporation_amount_* from a pan or from a model, evapotranspiration_potential_* and evapotranspiration_last_24h are different quantities, and only quantities of the same kind can be compared. By default wetterdienst returns millimetres.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 10 on evaporation is where this entry takes the definitions, the instruments, the sources of error and the example of a calculation from.',
        'Volume I, Chapter 10 (Measurement of evaporation), sections 10.1.1, 10.1.2, 10.1.3, 10.1.4, 10.3, 10.3.1, 10.3.4, 10.3.6, 10.4, 10.4.1, 10.4.3, 10.5.',
        WMO_I,
      ),
      dwdFiles(
        'The description of its derived dataset says that evaporation, soil moisture and soil temperature are calculated, and from which model. The documentation of the model says how it works.',
        'DWD Climate Data Center. Calculated recent monthly values for different characteristic elements of soil and crops, version v2 (2024; revised 2026-05-28), sections "Abstract", "Data origin" and "Additional information"; German daily description "Berechnete aktuelle Tageswerte von charakteristischen Elementen aus dem Boden und dem Pflanzenbestand", version v2 (2024). Löpmeier, F.-J., "Agrarmeteorologisches Modell zur Berechnung der aktuellen Verdunstung (AMBAV)", sections 1 and 2.1 and 2.2 (opendata.dwd.de/climate_environment/CDC/grids_germany/daily/evapo_r/AMBAV.pdf). Both read on 21 November 2026.',
        DWD_SOIL_MONTHLY,
      ),
      knmi(
        'The header of its daily data file names each element and its unit.',
        'KNMI, daily data of the weather in the Netherlands (daggegevens), file header for station 260 (De Bilt), element EV24, read on 21 November 2026.',
      ),
      ghcnDaily(
        'Its readme names each element and its unit.',
        'NOAA NCEI. Readme of the Global Historical Climatology Network daily (GHCN-Daily), version 3.35, section III: the elements EVAP, MDEV, DAEV, MNPN and MXPN.',
      ),
    ],
  },

  'soil-moisture': {
    title: 'Soil moisture',
    summary: 'Soil moisture is how much water is in the ground. It can be given as a share of mass, a share of volume or as the energy with which the soil holds the water (the water potential), and what a number means depends on the soil.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'WMO says that soil moisture determinations measure either the soil water content or the soil water potential. The content is the mass or volume of water in the soil. The potential describes the energy state of the soil water: water tends to flow from a place of higher potential to one of lower potential, and as soil dries the potential becomes more negative and plants find it harder to take water up. The relation between content and potential is not universal; it depends on the local soil.',
          'The basic technique is gravimetric. A soil sample of about 50 g is taken, weighed, dried in an oven at 105 °C until its mass stays constant, which usually takes 16 to 24 hours, and weighed again; the difference is the water. This is a direct measurement, so WMO calls it the standard against which all other methods are compared. But the sampling destroys the sample, so the measurement cannot be repeated on it.',
          'Indirect methods leave the soil in place. A neutron probe is lowered into a tube in the ground: hydrogen, most of it in water, slows the neutrons, which gives the water content. Dielectric methods, such as time-domain reflectometry, use the fact that liquid water has about 20 times the permittivity of average dry soil; WMO says that these can be fully automated. The soil water potential is measured with tensiometers, resistance blocks and soil psychrometers. WMO also describes the measurement of soil moisture by satellites, which looks at the surface.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'The gravimetric water content is the mass of water divided by the mass of dry soil. The volumetric water content is the volume of water divided by the volume of the whole sample (dry soil, air and water). Both are usually given in per cent, although many research communities now use cubic metres of water per cubic metre of soil for the volume. To turn one into the other the density of the dry soil is needed. The soil water potential is given as energy per mass, as a pressure or as the height of a column of water.',
          'Soil moisture changes with depth, and what is needed depends on the use. WMO says that models of evapotranspiration mostly concern a shallow depth of tens of centimetres, agriculture needs the moisture at the depth of the roots, of the order of a metre, and models of the atmosphere use layers down to a few metres. WMO says that there is no standard depth or measuring interval; the stations of the International Soil Moisture Network mostly measure at several depths between 0.05 m and 0.50 m or 1 m.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'A reading is for one place. WMO says that soil varies a lot, horizontally and vertically, in structure, cover and relief, and that a single observation location cannot give absolute knowledge of the soil moisture of a region, only relative knowledge of how it changes. Measurements by sampling or with an instrument in the ground are reliable only at the point of measurement, so describing a site takes many samples.',
          'The same percentage means different things in different soils. WMO describes the field capacity, the state in which the soil holds all the moisture it can hold against gravity after a heavy wetting, and the wilting point, at which the roots can no longer overcome the forces that hold the water to the soil particles. The water available to plants is commonly taken as the quantity between the two, and it varies a lot between soils: in sandy soils it may be less than 10 volume per cent, in soils with much organic matter over 40 volume per cent. Water contents of stony or gravelly soils can be grossly misleading.',
          'Each method has limits. The neutron method cannot be used effectively in the top 20 cm of soil. Resistance blocks read a wetter soil than there is if the soil is saline, although gypsum blocks are less sensitive to this. Tensiometers work well only in wet soil, and their practical limit is about -85 kPa.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'The soil moisture in wetterdienst is that of DWD\'s derived dataset for soil, and it is calculated, not measured. DWD says that all calculated values of soil moisture and evapotranspiration come from the agrometeorological model AMBAV, and that the values are usually not measured. As the reason it gives that the measurement of soil moisture is very costly and prone to error. The model needs hourly weather: temperature, humidity, wind, precipitation and also global and long-wave radiation. DWD says that the radiation is not measured at every station and is often derived from the sunshine duration and the cloud cover. For the check of the moisture DWD says that it was compared with measurements only at single points, in special campaigns, and agreed well.',
          'The unit is not the volume fraction of WMO. DWD gives soil moisture in per cent of the usable field capacity (% nFK). 100 % is the span between the wilting point and the field capacity of the soil that the model uses, so 0 % is the wilting point and 100 % the field capacity. DWD says that values above 100 % are correct and occur when the water content is above the field capacity; in light soils, at the rarely observed saturation of the soil, up to 300 % are possible, but only with impermeable layers or frozen ground. By default wetterdienst returns the number in per cent as DWD gives it, so for these parameters "per cent" means per cent of the usable field capacity and not per cent of the volume.',
          'DWD calculates for two soils, a loamy silt with a wilting point of 13 volume per cent and a field capacity of 37 volume per cent, and a loamy sand with 3 and 17 volume per cent, under grass, winter cereals and maize. Under grass on the loamy silt it gives the layers 0 to 10 cm, 10 to 20 cm and so on to 50 to 60 cm, and for each combination the layer from 0 to 60 cm. The daily values are in the daily dataset and the monthly means in the monthly dataset (soil_moisture_mean_*). At the time of writing no other provider in wetterdienst offers soil moisture, so there is no other source to compare it with.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 11 on soil moisture is where this entry takes the definitions, the methods, their limits and the remarks on depth and representativeness from.',
        'Volume I, Chapter 11 (Measurement of soil moisture), sections 11.1.1, 11.1.2, 11.1.3, 11.1.4, 11.2, 11.3.1.1, 11.3.2, 11.4, 11.4.1, 11.4.2, 11.5, 11.6.',
        WMO_I,
      ),
      dwdFiles(
        'The description of its derived dataset says that soil moisture is calculated, from which model, with which input, and in which soils. Its documentation of soil moisture defines the unit.',
        'DWD Climate Data Center. Calculated recent monthly values for different characteristic elements of soil and crops, version v2 (2024; revised 2026-05-28), sections "Abstract", "Data origin", "Validation and uncertainty estimate", "Uncertainties" and "Additional information"; German daily description "Berechnete aktuelle Tageswerte von charakteristischen Elementen aus dem Boden und dem Pflanzenbestand", version v2 (2024), section "Unsicherheiten". DWD, "Bodenfeuchte" (Dokumentation, status March 2024), sections 1 and 2 (dwd.de/DE/fachnutzer/landwirtschaft/dokumentationen/allgemein/bf_erlaeuterungen.pdf). Both read on 21 November 2026.',
        DWD_SOIL_MONTHLY,
      ),
    ],
  },

  'present-weather': {
    title: 'Present weather and state of the ground',
    summary: 'Present weather is a description, not a number: a code that says what was happening at the time of the observation, such as rain, fog or thunder. WMO says that at present only a trained observer can observe all of it.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'WMO calls "weather" the qualitative descriptions of the phenomena in the atmosphere or on the Earth\'s surface that were at first not meant to be measured. Present weather describes the weather phenomena present at the time of the observation. Past weather describes the significant weather events of the previous hour that were not occurring at the time of the observation. State of the ground is a related item: the condition of the Earth\'s surface that results from recent weather, in terms of its moisture or of any layers of solid, watery or other particles that cover it.',
          'WMO lists what is observed: precipitation (rain, drizzle, snow, ice pellets, snow grains, diamond dust and hail), obscurity and suspended particles (haze, dust, smoke, mist, fog, drifting and blowing snow, dust and sand storms, dust devils), funnel clouds, squalls and lightning. WMO says that the only current ability to observe all the forms of weather is the seeing and hearing of a trained human observer. An event can be defined by what a person perceives: it is a thunderstorm when thunder is heard, even if no lightning is seen.',
          'Instruments cover part of it. WMO says that no single sensor classifies all present weather. Automatic systems combine data from several sensors, such as visibility, temperature, dew point, wind speed and the distinction between rain and snow, with algorithms. The type of precipitation is detected by scatter sensors, optical disdrometers, Doppler radars and impact detectors, among others. Thunderstorms are mainly detected with lightning counters. WMO\'s example for haze: if a station has instruments, it is fairly safe to take an obscurity as haze if the relative humidity is below a certain value, for example 80 %, and the visibility is within certain limits, for example greater than 1 km horizontally and greater than 2 km vertically; mist is reported at high humidity and a visibility of 1 km or more.',
          'The state of the ground is reported by observers with the codes of WMO\'s Manual on Codes (WMO-No. 306). WMO says that measuring it automatically is still relatively new and not widely used. WMO says that research has shown that the main states can be told apart by the way the surface reflects and scatters light: dry, humid, wet, snow-covered, rimed or iced. Scatter sensors use this; a capacitive sensor, which WMO says is still being developed, would use the different dielectric constants of dry and wet earth.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'Present weather, past weather and the state of the ground are reported as codes. The observer chooses a term from a large number of descriptions laid down in the Manual on Codes (WMO-No. 306), and at staffed stations the code is reported together with quantitative data. WMO says that the data of sophisticated present weather systems should be reported as quantities in a binary code format such as BUFR, because the alphanumeric code has many restrictions. In a synoptic report, if there is no precipitation at the time of the observation, the conditions of the last hour are taken into account when choosing the code figure.',
          'Intensity has classes. Observers, or the instruments that replace them, classify precipitation as slight, moderate or heavy. WMO\'s annex gives criteria by the rate of fall, based on a measurement period of 3 minutes: for rain slight is below 2.5 mm per hour, moderate from 2.5 up to 10 mm per hour, heavy from 10 up to 50 mm per hour and violent 50 mm per hour or more; for snow, in water equivalent, slight is below 1.0 mm per hour, moderate from 1.0 up to 5.0 mm per hour and heavy 5.0 mm per hour or more. WMO says that a present weather event may be well defined by a period of 3 minutes, and that the highest running 3-minute average within the 10-minute period should be reported.',
          'A word can mean something different in reports and in climate summaries. In synoptic reports "fog" means water or ice fog that generally reduces the horizontal visibility at the surface to less than 1 km, and WMO says that wherever the term occurs in the present weather and past weather codes it should be read in this sense. In climatological summaries, all occasions of visibility of less than 1 km are regarded as fog.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'Present weather, past weather and the state of the ground are, WMO says, primarily meant as a qualitative description of weather events. The amount of precipitation is a different measurement (see "Precipitation"), and the clouds too (see "Clouds"). A code says what kind of weather there was, and not how much.',
          'With current technology, WMO says, instruments for present and past weather, cloud amount and height, and snow cover are not able to observe the whole range of phenomena, whereas human observers are. What the instruments detect is also not the same for every type of instrument. WMO reports field tests in which sensors for the type of precipitation detected the major types, except the very lightest snow or drizzle, in over 90 % of the cases compared with a trained observer, with a much lower share for very slight precipitation. Scatter sensors were reported at 70 to 90 % for the common types, rain and snow, depending on the test and the instrument. Mixed precipitation of rain and snow and hail are observed less well, and wet or melting snow is difficult to tell from rain. WMO also says that these sensors do not give the quality or the uncertainty of their report.',
          'An intensity from such a sensor is rougher than one from a gauge. WMO says that the intensity from a scatter sensor is usually less accurate than that from conventional methods such as weighing or tipping-bucket rain gauges, and that for a coarse indication such as slight or heavy it is usable.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'DWD\'s hourly weather phenomena are a code, with a text beside it, and the station files name SYNOP weather reports as the source, with the times in UTC. DWD\'s list of codes has two ranges: 0 to 99, and 100 to 199 with meanings of their own, for example 100 "with cloud cover (more than 0/8) at the time of observation: no significant weather phenomena observed", 123 "rain, not freezing (not at the time of observation): at the station in the last hour" and 161 "rain, not freezing: light". In the recent files of the three stations checked, every code is in the range 100 to 199 or is -1; for -1 the file says "weather was not reported", and that is the case in 70 to 72 % of the hours at these stations (for example 9124 of 13118 hours at Potsdam). So -1 does not say what the weather was, fine or not, and wetterdienst returns no value for these hours. The codes of the two ranges are not converted into each other.',
          'DWD\'s data for fixed observation times contain a coded state of the ground ("Terminwerte des Erdbodenzustand", EK_TER, parameter soil_state_index in wetterdienst), which the station file says is generated from SYNOP reports at the fixed observation times, since 2001. In the recent folder it exists for 30 stations. At the one station read (Altenstadt, 00125) more than half of the entries are missing (1169 of 1835). The file calls it a code and does not say which one; the code tables are in WMO\'s Manual on Codes, which is not one of the sources of this page.',
          'NOAA\'s GHCN-Daily records which kinds of weather occurred on a day as weather types, one element for each kind (WT01 fog, ice fog or freezing fog; WT03 thunder; WT05 hail; WT06 glaze or rime; WT16 rain; WT18 snow, and others) and a second set for weather in the vicinity of the station. Wetterdienst names them weather_type_*. DWD\'s forecasts MOSMIX and DMO give forecast codes under weather_significant* and weather_last_6h, which are not observations: see "Observation, forecast and derived data".',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 14 on present and past weather and the state of the ground is where this entry takes the definitions, the methods, the criteria for intensity and the results of the tests of sensors from. Chapter 1 of the same volume says what instruments cannot yet observe.',
        'Volume I, Chapter 14 (Observation of present and past weather; state of the ground), sections 14.1.1, 14.1.2, 14.1.3, 14.1.4, 14.2, 14.2.1.2, 14.2.1.3, 14.2.1.4, 14.2.2.1, 14.2.3.1, 14.2.3.2, 14.3.1, 14.3.2 and the Annex (criteria for slight, moderate and heavy precipitation intensity); Volume I, Chapter 1 (General), section 1.3.',
        WMO_I,
      ),
      dwdFiles(
        'The description of the dataset, the list of the weather codes and the files that come with each station say what DWD publishes as present weather, where the values come from, and what -1 stands for.',
        `DWD Climate Data Center, files inside the station archives stundenwerte_WW_03987_akt.zip, stundenwerte_WW_01048_akt.zip and stundenwerte_WW_01420_akt.zip in ${DWD_HOURLY}weather_phenomena/recent/, read on 21 November 2026 for Potsdam (03987), Dresden-Klotzsche (01048) and Frankfurt/Main (01420): Metadaten_Parameter_ww_stunde_* and the column WW of the data file; Wetter_Beschreibung.txt in the same folder; dataset description "Hourly station observations of weather phenomena for Germany" (version v24.03, 2024). For the state of the ground: terminwerte_EK_00125_akt.zip in opendata.dwd.de/climate_environment/CDC/observations_germany/climate/subdaily/soil/recent/ (Metadaten_Parameter_ek_termin_00125 and the column EK_TER of the data file) and the list EK_Terminwerte_Beschreibung_Stationen.txt in the same folder, read on 21 November 2026.`,
        DWD_HOURLY_WEATHER,
      ),
      ghcnDaily(
        'Its readme names each element and what it stands for.',
        'NOAA NCEI. Readme of the Global Historical Climatology Network daily (GHCN-Daily), version 3.35, section III: the elements WT** (weather type) and WV** (weather in the vicinity).',
      ),
    ],
  },

  'clouds': {
    title: 'Clouds',
    summary: 'The amount of cloud, the height of its base and its kind are three different observations. An observer sees the whole sky; a ceilometer looks straight up at one small part of it.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'WMO defines a cloud as a collection of very small water droplets, ice crystals or a mixture of both, whose base is above the ground and which can be seen from the place of observation. Three things are observed: how much of the sky is covered (cloud amount), how high the lowest part of the cloud is above the ground (cloud-base height) and what kind of cloud it is (cloud type). WMO says that cloud amount was traditionally observed by eye, and that instrumental methods are now widely accepted and used.',
          'An observer estimates the part of the sky that is covered to the nearest okta, an eighth of the sky. The observer should give equal weight to the area overhead and to the lower parts of the sky; if the clouds are very unevenly spread, the sky can be divided into quadrants and the estimates added. The code figure 9 is reported when the sky cannot be seen because of fog, falling snow and the like, or when the observer cannot estimate the amount because of darkness or other lighting. At night the observer must let the eyes get used to the dark. Where there is no instrument, the height of a cloud base can only be estimated, in mountainous areas for example by comparing it with the heights of known landmarks. WMO adds that because of perspective a cloud can seem to rest on distant hills, and that for tropical cumulus clouds with a high base, surface observers have frequently underestimated the height very seriously.',
          'The height of the cloud base is measured with a ceilometer. WMO says that the laser ceilometer is the method most used now and should be considered the most appropriate. It sends pulses of near-infrared light upwards and measures how long the light scattered by the cloud takes to come back. Cloud amount can be found from the series of a ceilometer\'s readings, from infrared sensors that measure the thermal emission of the sky in many directions, and from cameras that look at the whole sky. WMO says that for most cloud types the only method is still visual, and that cloud type is still generally observed by people; one automatic method exists, for the aviation weather reports, which combines precipitation radar and lightning detection to tell cumulonimbus and towering cumulus.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'Cloud amount is reported on a scale of oktas, from 0 for a clear sky to 8 for a completely covered one. 1 stands for one okta or less but not zero, and 7 for seven oktas or more but not eight, so that 0 and 8 are kept for a sky that is completely clear or completely covered. WMO\'s table also gives the same scale in tenths. In the BUFR code, the total cloud cover is given in per cent.',
          'WMO tells the total cloud amount from the partial one. The total is the part of the sky dome covered by all the clouds that can be seen. The partial amount is the part covered by a type or layer of cloud as if it were the only cloud in the sky, so partial amounts can add up to more than the total and to more than eight oktas.',
          'A ceilometer has no view of the whole sky, so it builds an amount from many readings. WMO says that the amount of cloud within the range of a ceilometer can be estimated from the share of the time that well-identified layers occupy, assuming that this time average stands for the sky around the station. As an example WMO describes the American system ASOS: the ceilometer takes a sample every 30 seconds; every minute the last 30 minutes are processed, the last 10 minutes with double weight; the cloud heights are grouped into layers, and the amount of a layer comes from the share of the samples that found cloud, converted to be equivalent to a human observation. For cloud type, WMO describes classes: ten genera in the International Cloud Atlas (WMO-No. 407), and for synoptic reports codes for low, middle and high clouds, whose purpose is to report characteristic states of the sky rather than individual cloud types.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'A ceilometer looks straight up at a small piece of sky. WMO says that most differences from the amount estimated by an observer can be attributed to this limited spatial representativeness, and that the method relies on the clouds moving over the instrument and being representative of the whole sky. In a comparison at coastal stations at mid-latitudes, the ceilometer method agreed within 2 oktas with the observer\'s total cloud amount typically in 85 to 90 % of the cases, and WMO says that this result is affected by the many overcast situations (7 or 8 oktas about 55 % of the time). A ceilometer reports 8 oktas much more often than 7 oktas, while an observer can see gaps anywhere in the cloud cover and reports 7 and 8 about equally often.',
          'The height of a cloud base is not as sharp as it sounds. WMO says that studies found systematic differences of 30 to 50 m in the cloud-base heights of ceilometers of different manufacturers, which seem to come from the algorithms that place the base, and that for instruments there is no clear definition of a cloud base. In fog and during precipitation serious errors can occur. The laser may not detect high cirrus, and moist layers, aerosol, aircraft, birds, vegetation overhead or snow on the instrument can give a base that is not there. WMO\'s table of requirements asks for an uncertainty of 1/8 for the cloud amount, and says that 2/8 is achievable; for the height of the base it asks for 10 m up to 100 m and 10 % above, and puts what is achievable at about 10 m against a hard target (not a cloud), with a significant bias during precipitation.',
          'WMO says that there are occasions when it is very difficult to estimate cloud amount, especially at night, and that the observer needs time for the eyes to adjust; on moonless nights the total can usually be estimated from the part of the sky in which the stars are dimmed or hidden by cloud, although haze alone can hide stars near the horizon. WMO says that scanning infrared detectors and infrared cameras can observe at night and that cameras which use daylight cannot; each method has disadvantages of its own, for example a scanning infrared detector finds it hard to classify partly transparent cloud.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'DWD\'s hourly cloud cover is in eighths, with an indicator that says whether a person (P) or an instrument (I) made the observation. In the recent files of the three stations checked, almost every value is marked I; Potsdam and Dresden-Klotzsche have 47 values marked P, Frankfurt/Main none. The station files name SYNOP weather reports as the source, with times in UTC. They list as the instrument for the total cloud cover a ceilometer of the type CHM 15k "Nimbus" since 21 July 2015 at Potsdam (before it an LD 40 from 2009 and a cloud-height meter of the type IVO until 1997), since 19 September 2019 at Dresden-Klotzsche and since 6 August 2021 at Frankfurt/Main. The files and the dataset description that were read do not say how the readings of the ceilometer become the cover. DWD says that many of its stations changed from manual to automatic observation between the end of the nineties and 2009, and names changes of instruments and of the observing personnel among the sources of uncertainty for long time series.',
          'The cloud-type dataset has up to four layers, each with a type, the height of its base and its cover. In the recent files of the three stations checked there are heights and covers for up to three layers, no type for any layer and no fourth layer. DWD writes -1 in some hours; its description names only -999 as a missing value. Wetterdienst reads -1 as a sky that could not be seen and returns no value for it; that is wetterdienst\'s reading, not a statement of DWD. By default wetterdienst returns the cover in per cent of the sky and the height in metres.',
          'DWD\'s daily mean cloud cover (NM) is an arithmetic mean: for the stations checked, since 1 April 2001 of at least 21 hourly values from SYNOP reports, and before that of the observations at three times of day (in 1967 to 1990 at Potsdam of four or eight). KNMI gives the mean cloud cover of the day (NG) in oktas and writes 9 for a sky that cannot be seen, which wetterdienst returns as no value. NOAA\'s GHCN-Daily gives the average cloudiness as a percentage and keeps the sources apart: ACMC and ACSC are from ceilometer data at 30-second intervals, ACMH and ACSH from manual observations, each for midnight to midnight or for sunrise to sunset. DWD\'s forecasts MOSMIX and DMO give cloud cover by layer of height (for example cloud_cover_below_2km) and an effective cloud cover. These are forecasts, not measurements: see "Observation, forecast and derived data".',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume I, Chapter 15 on clouds is where this entry takes the definitions, the observation by eye, the instruments and their errors from. Chapter 1 of the same volume holds the table of the uncertainties WMO asks for.',
        'Volume I, Chapter 15 (Observation and measurement of clouds), sections 15.1.1, 15.1.2, 15.1.3, 15.1.4.1, 15.1.4.2, 15.1.4.3, 15.2.1, 15.2.2, 15.2.3, 15.3, 15.3.1, 15.3.2, 15.3.3, 15.4, 15.4.1.1, 15.4.1.3, 15.5; Volume I, Chapter 1 (General), Annex 1.A, rows 4.1 and 4.2.',
        WMO_I,
      ),
      dwdFiles(
        'The files that come with each station say which instrument it used and where the values come from. The descriptions of the datasets say what the numbers are.',
        `DWD Climate Data Center, files inside the station archives stundenwerte_N_*_akt.zip and stundenwerte_CS_*_akt.zip in ${DWD_HOURLY}cloudiness/recent/ and ${DWD_HOURLY}cloud_type/recent/ and tageswerte_KL_*_akt.zip in ${DWD_KL}recent/, read on 21 November 2026 for Potsdam (03987), Dresden-Klotzsche (01048) and Frankfurt/Main (01420): Metadaten_Geraete_Gesamt_Bedeckungsgrad_*, Metadaten_Parameter_n_stunde_*, Metadaten_Parameter_klima_tag_* (parameter NM) and the columns V_N, V_N_I and V_S1_CS to V_S4_NS of the data files; dataset descriptions "Hourly station observations of cloudiness for Germany" and "Hourly station observations of cloud cover, cloud type and cloud height in up to 4 layers for Germany" (version v24.03, 2024).`,
        DWD_HOURLY_CLOUDINESS,
      ),
      knmi(
        'The header of its daily data file names each element and its unit.',
        'KNMI, daily data of the weather in the Netherlands (daggegevens), file header for station 260 (De Bilt), element NG, read on 21 November 2026.',
      ),
      ghcnDaily(
        'Its readme names each element and its unit.',
        'NOAA NCEI. Readme of the Global Historical Climatology Network daily (GHCN-Daily), version 3.35, section III: the elements ACMC, ACMH, ACSC and ACSH.',
      ),
    ],
  },

  'snow': {
    title: 'Snow',
    summary: 'Snow depth, fresh snow, the water in the snow and the presence of snow are four different measurements.',
    parts: [
      {
        title: 'How it is measured',
        paragraphs: [
          'WMO distinguishes four things. The snow depth is the vertical distance from the snow surface to the ground, in whole centimetres. The depth of snowfall, or fresh snow, is the depth of the snow that fell and piled up in a period, usually 24 hours. The water equivalent is the depth of water that would be left if the snow cover melted, which is the depth of the snow times its average density. The presence of snow is a yes or no: whether more than half of the measuring site is covered.',
          'By hand, snow depth is read from a stake or rod with centimetre marks. Automatic stations use a sensor above the snow, sonic or laser, which measures the distance to the snow surface; the depth is the distance to the bare ground minus the distance to the snow.',
          'Fresh snow is measured on a white board of plywood, 40 to 60 cm on a side, which is read at the same time every day to the nearest 0.5 cm and then swept clear. There is no accepted automatic technique for it.',
        ],
      },
      {
        title: 'How a reading becomes a value',
        paragraphs: [
          'A snow depth is a reading at one place at one time, unless stated otherwise. If more than half of the measuring site is bare, a depth of 0 cm is entered, even if some snow is left at the stake.',
          'Fresh snow cannot be found by subtracting two snow depths: snow that lies settles and melts, so the difference would be too small. A fresh snow of less than 0.5 cm is recorded as a trace.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'One stake is one point. A stake in a drift or in a spot that the wind has swept bare can be wrong by as much as the mean snow depth or more, so WMO asks for level, sheltered sites that represent their surroundings. Automatic sensors should be specified to a data uncertainty of not more than 2 cm, preferably 1 cm.',
          'Wind and melt make fresh snow uncertain: the observer has to estimate what would have fallen, and WMO says the error can be as much as 100 %. In a warm spell an hour earlier or later can make a difference of several centimetres.',
          'Snow also falls into a rain gauge, which catches much less of it in wind: the bias of gauges for snow is typically 30 % or higher (see "Precipitation").',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'DWD\'s daily snow depth is the reading of 06 UTC at the stations checked; the fresh snow depth is a separate daily value. Where a Canadian site reports twice a day, Environment and Climate Change Canada bases the "snow on the ground" of a day on the morning observation of that day.',
          'The instrument changes: at Dresden-Klotzsche, DWD lists a manual snow stake (Schneepegel) until July 2022 next to an automatic snow depth sensor that has been in use since September 2019.',
        ],
      },
    ],
    sources: [
      wmoGuide(
        'Volume II, Chapter 2 on snow is where this entry takes the definitions, the instruments and the typical errors from. Volume I, Chapter 6 is where it takes the bias of gauges for snow from.',
        'Volume II (Measurement of cryospheric variables), Chapter 2 (Measurement of snow), sections 2.1.1, 2.2, 2.3.1.2, 2.3.1.3, 2.3.2.1, 2.3.2.2, 2.6, 2.7; Volume I, Chapter 6 (Measurement of precipitation), sections 6.2.1.2, 6.5.2.',
        WMO_II,
      ),
      dwdFiles(
        'The files that come with each station\'s data say which instrument it used and when a value was read.',
        `${STATION_FILES} Metadaten_Geraete_Schneehoehe_* and Metadaten_Parameter_klima_tag_*; dataset description "Daily precipitation observations for Germany" (more_precip, version v24.3, 2024). Environment and Climate Change Canada, Climate glossary, "Climatological Day" (climate.weather.gc.ca/glossary_e.html).`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/more_precip/DESCRIPTION_obsgermany-climate-daily-more_precip_en.pdf',
      ),
    ],
  },

  'normals': {
    title: 'Climate normals: the 30-year reference period',
    summary: 'A normal is an average over thirty years that today\'s weather is compared with, and which thirty years it is makes a difference.',
    parts: [
      {
        title: 'What a normal is',
        paragraphs: [
          'A climate normal is the average of weather observations over a long, fixed period. It does two jobs: it is the benchmark that recent observations are compared with, and it is used as a guess of the conditions most likely to occur at a place.',
          'WMO defines the climatological standard normal as the average over a period of 30 years that ends in a year ending in 0: 1981 to 2010, 1991 to 2020, and so on. It is calculated anew every ten years. Thirty years became the standard mainly because only thirty years of data were available when it was first recommended.',
          'The period 1961 to 1990 has been kept as the reference for assessments of long-term climate change; WMO\'s guidelines call the averages of this period reference normals.',
        ],
      },
      {
        title: 'How it is calculated',
        paragraphs: [
          'A monthly normal is the mean of all valid values of that month in the period. An annual or a seasonal normal is calculated from the monthly normals, not from the single years, and if the normal of one month is missing, the seasonal or annual one is missing as well.',
          'A monthly mean is not calculated if observations are missing on 11 or more days of the month or on 5 or more days in a row. A normal is calculated only if valid months exist in at least 80 % of the years: 24 of 30. A monthly total, such as monthly precipitation, generally needs complete data for the month.',
        ],
      },
      {
        title: 'What the number can and cannot tell',
        paragraphs: [
          'A normal is a reference, not a forecast of any particular year and not a limit. The same year compared with the 1961 to 1990 normal and with the 1991 to 2020 normal gives different answers. WMO keeps the fixed 1961 to 1990 benchmark so that an "above average" year does not turn into a "below average" one because the reference period changed, while for some elements with a clear and consistent trend, most notably temperature, the newest normal says most about the conditions to expect.',
          'Extreme values and rare percentiles taken from only thirty years can be much less stable than means, for some elements such as precipitation. WMO says that a calculation that departs from its rules should say so.',
        ],
      },
      {
        title: 'Where providers differ',
        paragraphs: [
          'Providers publish normals for different periods. DWD lists stations for the periods 1961 to 1990, 1971 to 2000, 1981 to 2010 and 1991 to 2020; 1971 to 2000 is neither a standard nor a reference period of WMO.',
          'A parameter of the glossary whose name ends in "normal", such as sunshine_duration_normal, is a normal "for the period" the provider uses. Check which period that is before you compare with it.',
        ],
      },
    ],
    sources: [
      {
        plain: `${WMO_PLAIN} Its Guidelines on the Calculation of Climate Normals say what a normal is, which periods count, and how many missing values are allowed. This entry takes all of that from them.`,
        citation: 'WMO (2017). WMO Guidelines on the Calculation of Climate Normals (WMO-No. 1203), 2017 edition. Chapters 2 (Background), 3 (Definitions), 4.3 and 4.4 (Calculation of normal values, Data completeness), 5.1 and 5.2.2 (Application aspects).',
        href: 'https://library.wmo.int/records/item/55797-wmo-guidelines-on-the-calculation-of-climate-normals',
      },
      dwdFiles(
        'It publishes lists of the stations for which it calculates normals.',
        'DWD Climate Data Center, directory help: lists of stations by period, such as Temperatur_1991-2020_Stationsliste_festerStandort.txt, read on 20 November 2026.',
        'https://opendata.dwd.de/climate_environment/CDC/help/',
      ),
    ],
  },

  'time': {
    title: 'Time: what an hour and a day are in the data',
    summary: 'Timestamps are in UTC, a stamp can mean the start or the end of an interval, and a day is not always midnight to midnight.',
    parts: [
      {
        title: 'Which clock',
        paragraphs: [
          'The library wetterdienst returns every timestamp in UTC, whichever clock the provider writes. Providers use UTC, local time or a fixed offset such as DWD\'s MEZ, the time of central Europe without summer time (UTC+1). A mistake of the clock is an hour off and never raises an error, so the library follows what each provider\'s documentation says about its clock.',
          'DWD states the clock of each period of each station in its files. Its 10-minute data are in UTC since the year 2000, and in MEZ before; its hourly air temperature and precipitation of recent years are in UTC.',
        ],
      },
      {
        title: 'The start or the end of an interval',
        paragraphs: [
          'A value that covers an interval, such as a 10-minute sum, is stamped at the start, at the end or, more rarely, in the middle of it. DWD stamps its 10-minute precipitation at the end of the interval for the rain[e]H3 gauge; a PLUVIO value is delayed by about 5 minutes. For the hourly sunshine duration and radiation estimates of DWD\'s DUETT project, a stamp of 11:00 UTC covers the hour from 09:50 to 10:50, so the stamp is neither the start nor the end of the hour it stands for.',
        ],
      },
      {
        title: 'The climate day',
        paragraphs: [
          'A daily value follows a "climate day" that the provider has chosen. Environment and Climate Change Canada explains why: a calendar day cannot capture the maximum and the minimum that truly belong to a day, because the coldest time is just before sunrise and the warmest shortly after the sun is at its highest. Its climatological day therefore starts and ends at the same hour of two days, for example from the 0601 UTC observations of one day to the 0600 UTC observation of the next. WMO asks for daily precipitation to be read at fixed times that are the same for the whole network.',
          'In DWD\'s daily data, from April 2001 and at the stations checked, daily precipitation covers 06:00 UTC to 06:00 UTC of the next day, and the daily maximum and minimum temperature, the minimum 5 cm above the ground and the sunshine duration cover 00:00 to 24:00 UTC. The snow depth is the reading of 06 UTC, and the daily maximum gust covers 23:51 to 23:50 UTC. So "a day" is not the same 24 hours in every column of one DWD file. DWD writes a window like "06:00 - 06:00 FT. UTC", where FT stands for Folgetag, the following day.',
          'Before 2001 the windows were different. At Dresden-Klotzsche, for example, daily precipitation covered 07:30 MEZ to 07:30 MEZ of the next day from 1991 to 2001, so a long series can mix two windows.',
        ],
      },
    ],
    sources: [
      dwdFiles(
        'The descriptions of its datasets and the files of each station say which clock a value uses and which stretch of time it covers.',
        `${STATION_FILES} Metadaten_Parameter_klima_tag_*; hourly archives stundenwerte_TU_01048_akt.zip and stundenwerte_RR_01048_akt.zip in opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/recent/ and .../hourly/precipitation/recent/ (Metadaten_Parameter_tu_stunde_*, Metadaten_Parameter_rr_stunde_*); dataset descriptions "10-minute station observations of precipitation for Germany" (version v24.03, 2024) and "Pseudo station data of gridded hourly near-realtime data of surface irradiance and sunshine duration based on surface measurements and satellite observations - DUETT Project" (version 006, 2024, "Considerations for applications").`,
        'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/precipitation/DESCRIPTION_obsgermany-climate-10min-precipitation_en.pdf',
      ),
      {
        plain: 'Environment and Climate Change Canada (ECCC) is the national weather service of Canada. Its climate glossary explains the climatological day its daily values follow.',
        citation: 'Environment and Climate Change Canada. Climate glossary, "Climatological Day". climate.weather.gc.ca/glossary_e.html',
        href: 'https://climate.weather.gc.ca/glossary_e.html',
      },
      {
        plain: 'The documentation of the library wetterdienst lists, for every provider, which clock it uses, which part of an interval its stamp marks, and where the provider says so.',
        citation: 'Wetterdienst documentation, "Time zones and reference times".',
        href: 'https://wetterdienst.readthedocs.io/en/latest/data/time_reference.html',
      },
      wmoGuide(
        'Volume I, Chapter 6 on precipitation is where this entry takes the rule that daily precipitation is read at fixed times that are the same for the whole network.',
        'Volume I, Chapter 6 (Measurement of precipitation), section 6.1.2.',
        WMO_I,
      ),
    ],
  },

  'observation-forecast-derived': {
    title: 'Observation, forecast and derived data',
    summary: 'A measurement was read at a station, a forecast is calculated for a place and a time to come, and a derived value is calculated from measurements.',
    parts: [
      {
        title: 'Observation',
        paragraphs: [
          'An observation is what an instrument at a station read. Even then the number has been through steps: WMO lists, among others, sampling, applying the calibration, averaging, and the calculation of related quantities. A sensor cannot measure the visibility, for example, but only how much light the air extinguishes, from which the visibility is calculated; the dew point and the pressure at sea level are calculated too.',
        ],
      },
      {
        title: 'Forecast',
        paragraphs: [
          'DWD\'s MOSMIX is a forecast for places. It takes the forecasts of two weather models, ICON of DWD and IFS of the European Centre for Medium-Range Weather Forecasts, and corrects them statistically with what weather stations have measured, because every model simplifies the ground and has systematic errors. It gives forecasts for about 5400 places for the next ten days, in steps of one hour.',
          'At about 2800 of these places MOSMIX has its own statistics, built from the history of the station. The other 2600 or so are calculated from neighbouring places, so a MOSMIX value there is an estimate between stations. MOSMIX also gives quantities that the models do not calculate, such as the visibility, through statistical rules.',
          'A forecast is issued at a time and is valid for a time to come. MOSMIX comes in two sets: MOSMIX_S, 24 times a day with 40 parameters, and MOSMIX_L, four times a day with 115 parameters, both up to +240 hours. In MOSMIX_S, the first 24 hours are updated every hour with the latest observations, the hours from +25 to +240 four times a day, at 04, 10, 16 and 22 UTC. A forecast is not a record of what the weather was.',
        ],
      },
      {
        title: 'Derived data',
        paragraphs: [
          'A derived value is calculated from measurements or from a model, and was not read at an instrument. An example is the DUETT project of DWD: it combines satellite images with the measurements of 42 DWD stations into hourly maps of the radiation and of the sunshine duration, and then takes the values at 576 stations from the map, from the nearest grid point with a correction for the shading of the mountains around. The file gives an uncertainty with each value, and its quality level says whether stations, the satellite or both went into it.',
        ],
      },
      {
        title: 'Where the kinds are told apart',
        paragraphs: [
          'Wetterdienst tells the kinds apart by the network of a provider: a network is, for example, an observation, a forecast, derived data, radar, alerts or storm cells (the Providers page names the kind of each network). The glossary and the parameters are the same for all of them, so a temperature of a forecast and a temperature of an observation can have the same name and are not the same kind of number.',
        ],
      },
    ],
    sources: [
      dwdFiles(
        'It describes its forecast product MOSMIX and its derived datasets on its website and with each dataset.',
        'DWD. Model Output Statistics-MIX (MOSMIX), dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html. DWD Climate Data Center: dataset description "Pseudo station data of gridded hourly near-realtime data of surface irradiance and sunshine duration based on surface measurements and satellite observations - DUETT Project", version 006 (2024).',
        'https://www.dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html',
      ),
      wmoGuideV(
        'Volume V, Chapter 3 on data reduction describes how the signal of an instrument becomes a meteorological variable.',
        'Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction), sections 3.1.1, 3.1.3, 3.5, 3.6.',
      ),
    ],
  },
}
