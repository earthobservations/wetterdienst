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
