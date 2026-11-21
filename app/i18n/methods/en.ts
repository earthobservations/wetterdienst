/**
 * "How the answers of Ask the weather are worked out" in English (GH-3764, steps 1b and 1c).
 *
 * The English text is the one a reader of a language that has no text of its own sees (the page says so, as it does for
 * "How weather is measured"). `de.ts` says the same, key for key (`tests/unit/ask-methods.test.ts` holds the two to each
 * other, to the definitions of the chips, and to the numbers in them).
 *
 * Every statement about a source says what the document says, and the place in it is in the definition of the chip
 * (`utils/ask/chips/`); a choice that no published source makes is said to be wetterdienst's own, with the reasoning.
 * `{name}` is a number or a name that the code fills in: the values of the rules of the chip, or the numbers of the answer.
 */

import type { MethodTexts } from './types'

const WMO = 'The World Meteorological Organization (WMO) is the United Nations agency in which the national weather services agree how weather is measured and compared.'
const DWD = 'The Deutscher Wetterdienst (DWD) is Germany\'s national weather service.'

export const methods: MethodTexts = {
  chips: {
    rain: {
      title: 'Will it rain tomorrow?',
      summary: 'A forecast for tomorrow at the forecast point of DWD nearest to the place: how much rain, in which hour, and how likely it is.',
      data: 'DWD\'s MOSMIX forecast, the set called MOSMIX_L (dataset hourly/large): the amount of rain of each hour and its totals for 6, 12 and 24 hours, and the chance of more than 0.1 mm in the hour, for the forecast point nearest to the place.',
      steps: {
        point: 'The forecast point nearest to the place is looked up. A forecast is made for places, not for every spot, so the answer is the one of that point, and it says which and how far away.',
        day: 'Tomorrow is the calendar day after today in the time zone of the place, from midnight to midnight. The forecast has one value for every hour.',
        sum: 'The amounts of the 24 hours of tomorrow are added up to the rain of the day. The hours are read from the forecast\'s hourly amounts; where they do not account for one of its longer totals (6, 12 or 24 hours), the longer total is used.',
        verdict: 'The verdict is "yes" if the day has {yesMm} mm or more, or an hour has a chance of {yesChance} % or more; "maybe" from {maybeMm} mm or a chance of {maybeChance} %; otherwise "probably not". If the forecast does not reach {hours} of the 24 hours there is no answer.',
      },
      formulas: {
        total: 'rain of the day = amount of hour 1 + amount of hour 2 + … + amount of hour 24',
      },
      rules: {
        'forecast': {
          text: 'The forecast is DWD\'s MOSMIX_L, hourly: the amount of rain of an hour (and its totals for 6, 12 and 24 hours) and the chance of more than 0.1 mm in the hour.',
          says: 'DWD describes MOSMIX as a forecast for places that corrects the output of weather models statistically with what weather stations have measured. Its list of the elements of MOSMIX names the amounts of rain (RR1c, RR6c, RRhc, RRdc, "consistent with significant weather", in kg/m², which is millimetres) and R101, the probability of more than 0.1 mm of precipitation during the last hour, in per cent.',
        },
        'nearest-point': {
          text: 'The forecast point nearest to the place is used as it is. Two points are not mixed.',
          reason: 'A forecast is made for points. The nearest one is the simplest rule and needs no assumption about how rain varies between points; the answer says which point it is and how far away. No source says it is the right rule.',
        },
        'day': {
          text: 'Tomorrow is the calendar day of the place\'s time zone, from midnight to midnight.',
          reason: 'A reader\'s tomorrow is the day on the clock where the place is. The forecast is stamped in UTC, so the day is cut at the local midnight. This is a choice of the app, not a rule of a guide.',
        },
        'min-hours': {
          text: 'The answer needs a forecast value for at least {hours} of the 24 hours of tomorrow. With fewer, the chip says the forecast does not reach tomorrow yet.',
          reason: 'A total of a few hours would read as the rain of the day. {hours} hours, three quarters of the day, is a round line chosen by wetterdienst; no source gives one.',
        },
        'day-total': {
          text: 'The rain of the day is the sum of the hourly amounts; where they do not account for a longer total of the forecast, the longer total is used.',
          says: 'DWD\'s list gives the amount of rain of one hour and its totals for 6, 12 and 24 hours, each "consistent with significant weather", in kg/m².',
          reason: 'Adding the hours is plain arithmetic. Which of the forecast\'s amounts to add, so that the sum of the day agrees with DWD\'s own totals, is wetterdienst\'s decision.',
        },
        'wet-hour': {
          text: 'An hour with at least {wetMm} mm counts as a wet hour.',
          says: 'WMO\'s guide says that amounts of less than 0.1 mm are generally called trace amounts. DWD\'s chance of rain (R101) is the chance of more than 0.1 mm in the hour.',
        },
        'yes-amount': {
          text: 'A day with {yesMm} mm or more is "yes, rain is likely".',
          says: 'WMO\'s guidelines on climate normals list the number of days with precipitation of 1 mm or more among the principal climate parameters of its normals (the counts at 5, 10, 50 mm and more are secondary ones), so 1 mm is the line WMO uses to count a day as a day with precipitation.',
        },
        'maybe-amount': {
          text: 'A day with {maybeMm} mm or more, and less than the line for "yes", is "maybe, a little".',
          says: 'WMO\'s guide asks that daily amounts read by hand are read to the nearest 0.2 mm and, if feasible, to the nearest 0.1 mm.',
          reason: '0.2 mm is the coarsest reading step the guide allows for a daily amount (the nearest 0.2 mm, and if feasible 0.1 mm), and wetterdienst takes it as the line for "a little". No source gives a line for "maybe".',
        },
        'chance-bands': {
          text: 'A chance of {yesChance} % or more in any one hour is "yes"; {maybeChance} % or more is "maybe".',
          says: 'DWD\'s list defines R101 as the probability of more than 0.1 mm of precipitation during the last hour, in per cent.',
          reason: 'The chance comes from DWD; the two lines that turn it into a word do not. 7 in 10 for "likely" and 3 in 10 for "maybe" are round numbers chosen by wetterdienst. No source gives them.',
        },
        'highest-chance': {
          text: 'The chance that is shown is the highest chance of any one hour of the day.',
          reason: 'DWD gives a chance for each hour, and the highest is the simplest summary of them. It understates the chance that it rains at some time of the day, which is at least as high as the highest hour. No source prescribes it.',
        },
      },
      limits: {
        forecast: 'This is a forecast, not a measurement: it says what DWD\'s models and statistics expect, and the next forecast can differ. What fell is told by the measurements of a weather station afterwards.',
        point: 'A forecast point can be some kilometres from the place, in a valley or on a coast where the weather is not the same. The answer names the point and its distance.',
        chance: 'The amount and the chance are two things: a high chance can come with a small amount, a low one with a heavy shower. The verdict is "yes" if either of them is above its line.',
        day: 'The hours are stamped in UTC, and the value at a full hour is the rain of the hour before it, so the first hour of a local day is the value stamped one hour after midnight.',
        hours: 'Where the forecast does not reach at least three quarters of the hours of tomorrow, there is no answer, and the chip says so rather than making one up.',
      },
      numbers: {
        point: 'Forecast point: {name} ({id}), {distance} km from {place}.',
        pointNoDistance: 'Forecast point: {name} ({id}), the one nearest to {place}.',
        day: 'The day: {day}, as the calendar day in the time zone {zone}.',
        hours: 'The forecast has a value for {given} of the {hours} hours of the day.',
        total: 'Rain of the day: {amount} {unit}, with {wetHours} wet hours (at least {wet} mm).',
        chance: 'Highest chance of more than 0.1 mm in any one hour: {chance}.',
        bands: 'The lines of the verdict, in millimetres whatever the unit of the settings: yes from {yes} mm in the day or a chance of {yesChance} in an hour; maybe from {maybe} mm or a chance of {maybeChance}.',
      },
    },

    season: {
      title: 'Was the last season warmer than usual?',
      summary: 'The mean temperature of the three months of a season (spring, summer, autumn or winter) at the place\'s station, set against the mean of the seasons of a WMO normal: 1961 to 1990, or any later normal that is complete.',
      data: 'DWD\'s monthly station observations (dataset monthly/climate_summary): the monthly mean of the air temperature at 2 m height of the place\'s station, its whole record.',
      steps: {
        seasons: 'For every year in which DWD has the monthly means of all three months of the season, the season is the mean of those three: spring is March to May, summer June to August, autumn September to November, and winter December to February, with the December of the year before. A season counts once it is over: from 1 June, 1 September, 1 December and 1 March. The last one that is over is the one asked about.',
        reference: 'The reference is the mean of the seasons of the normal chosen: 30 years that end in a year ending in 0, from {firstFrom} to {firstTo} on, each one once it is complete. The newest one is the one that opens. A normal is offered only if the station has at least {minSeasons} of its {ofSeasons} seasons of that kind. If the station has fewer of the newest normal, the seasons before the one asked about are used instead, if there are at least {fallbackMin}; with fewer there is no answer.',
        compare: 'The anomaly is the season\'s mean minus the reference. The same difference is drawn as a bar for every season of that kind at the station.',
        verdict: 'The season is "warmer" if its anomaly is {band} °C or more, "cooler" if it is {band} °C or less below, and "as usual" in between. The question about a winter asks for "colder", and its answer says yes where the winter was cooler. The rank counts the seasons that were warmer.',
      },
      formulas: {
        season: 'season(year) = (mean of month 1 + mean of month 2 + mean of month 3) / 3; for a winter, month 1 is the December of the year before',
        anomaly: 'anomaly = season(asked year) − mean of season(year) over the reference years',
      },
      rules: {
        'season': {
          text: 'A season is three whole months: spring is March, April and May; summer is June, July and August; autumn is September, October and November; winter is December, January and February.',
          says: 'DWD says that meteorologists divide the year into seasons of three whole months, each beginning on the first of the month in which the astronomical season begins: spring from 1 March to 31 May, summer from 1 June to 31 August, autumn from 1 September to 30 November and winter from 1 December to the end of February. It says this is done because climate statistics are made from data of single months.',
        },
        'winter-year': {
          text: 'A winter takes the December of the year before: December 2025 with January and February 2026 is the winter 2025/26, which counts as the winter of 2026, the year of its January and February. It is over on 1 March.',
          says: 'WMO\'s guidelines say that a seasonal normal is the mean of the monthly normals of its months, each taken over the same years of the period. They do not say which December a winter takes.',
          reason: 'Neither DWD\'s definition of the seasons nor WMO\'s guidelines say which year a winter that spans the turn of the year is named for. wetterdienst names it for the year of its January and February and takes the December before them, so that its three months follow one another, as they do in the weather. WMO\'s normal for December, January and February would average the December of the same years as the January and the February; the two differ only by the December at the ends of the period (for the normal 1991 to 2020, December 1990 against December 2020). This is wetterdienst\'s own choice, and the maintainers have to accept it.',
        },
        'complete-months': {
          text: 'A season counts only if the station has the mean of all three months. DWD calculates a monthly mean from the daily values of the month, and only where they are complete (for some stations it has monthly values and no daily ones).',
          says: 'WMO\'s guidelines say that if the normal of one of the months of a season is missing, the normal of the season is missing as well. DWD\'s description says its monthly means are calculated from the daily values, and only if the daily values are complete, and that for some stations monthly values exist where no daily values are available.',
        },
        'only-over': {
          text: 'A season counts once it is over: spring from 1 June, summer from 1 September, autumn from 1 December and winter from 1 March. The season that is still running is not compared.',
          reason: 'A running season has only some of its weeks, and its mean would be compared with whole seasons. The maintainers decided that only complete seasons are compared. No source is needed for that.',
        },
        'season-mean': {
          text: 'The mean of a season is the plain mean of the three monthly means, each month counting the same, whatever its number of days.',
          says: 'WMO\'s guidelines say that a seasonal normal is the mean of the monthly normals of its months. Some weather services weight the months by their number of days; WMO says that is not recommended for products that are exchanged between countries.',
        },
        'default-season': {
          text: 'The question opens on the summer, and a link that names no season asks about it.',
          reason: 'No source says which season a question should open on. The summer is the one this question always asked about, so that an old link and a habit keep their meaning; the choice above the answer changes it.',
        },
        'reference-choices': {
          text: 'The reference can be any WMO normal of 30 years that ends in a year ending in 0 and is complete: from {firstFrom} to {firstTo} on, with a new one added on 1 January after its last year. The whole record of the station and a sliding 30 years are not offered.',
          says: 'WMO defines the climatological standard normal as the average over 30 years that ends in a year ending in 0: 1981 to 2010, 1991 to 2020 and so on. The period 1961 to 1990 is kept as the reference normal for assessing long-term climate change, but it is not a standard normal. A normal in WMO\'s sense is a period average over at least three consecutive ten-year periods that start on 1 January of a year ending in 1, which every period offered here is.',
        },
        'reference-default': {
          text: 'The question opens on the newest normal that is complete. It ends in the year floor((year − 1) / 10) × 10, so it is 1991 to 2020 until the end of 2030, and from 1 January 2031 it is 2001 to 2030.',
          says: 'WMO says that the climatological standard normal is the most recent 30-year period that finishes in a year ending in 0, and that it is calculated again every ten years.',
        },
        'normal-mean': {
          text: 'The reference is the mean of the complete seasons of its years, each season counting the same. A year in which a month is missing is left out whole.',
          says: 'WMO\'s guidelines build a seasonal normal as the mean of the three monthly normals of its months, and not from the values of single years. If the normal of one month is missing, the seasonal normal is missing.',
          reason: 'The chip averages whole seasons, so a year with one month missing drops out of the reference entirely, where WMO would still use that year in the other two monthly normals. The two give the same where no month is missing. The way the chip averages is wetterdienst\'s own choice.',
        },
        'min-seasons': {
          text: 'A normal is offered only if the station has at least {minSeasons} of its {ofSeasons} seasons of the kind. Another one is shown in the choice, disabled, with how many the station has; the newest one uses the fallback below.',
          says: 'WMO asks, for each month, for valid monthly values in at least 80 % of the years of the period for a normal, which is 24 or more of 30 years.',
          reason: 'The chip counts complete seasons (all three months in the same year), not the years of each month, so the line is not WMO\'s and cannot be compared with it one to one. {minSeasons} of {ofSeasons} is wetterdienst\'s own line, set so that stations with gaps still get an answer against a WMO period, and the maintainers have to accept it; the reference of such a station is then not a WMO normal in the strict sense.',
        },
        'fallback-period': {
          text: 'Where the station has too few seasons of the newest normal, the reference is all the seasons of the station before the one asked about. No other normal is replaced like this: one that is picked is the one used, or is not offered.',
          says: 'WMO calls the mean of monthly values over any specified period an "average", and says that some sources call it a "provisional normal".',
          reason: 'Taking all earlier seasons, and not a period that starts in a year ending in 1 as WMO\'s definition of a period average has it, is wetterdienst\'s own choice. So is leaving the substitute to the newest normal: an answer against other years than the ones the reader picked would not answer the question asked.',
        },
        'fallback-minimum': {
          text: 'The fallback needs at least {fallbackMin} seasons.',
          says: 'WMO says that for most mean and sum parameters, 10 to 12 years of data gave a predictive skill similar to that of a standard 30-year period.',
          reason: 'Ten is the lower end of that range, and WMO sets no hard minimum. WMO\'s own definition of a period average, at least ten years starting on 1 January of a year ending in 1, does not fit a fallback of all earlier seasons. The line of {fallbackMin} seasons is wetterdienst\'s own, and the maintainers have to accept it.',
        },
        'anomaly': {
          text: 'The anomaly is the season\'s mean minus the reference, in degrees.',
          says: 'WMO says that a normal is the benchmark against which recent observations are compared, and that many anomaly-based climate datasets are built on it. An anomaly is that difference.',
        },
        'usual-band': {
          text: 'A difference of less than {band} °C either way counts as "as usual".',
          reason: 'A band is needed to say "as usual", and half a degree is a round figure chosen by wetterdienst. No source gives a width for the word, and the maintainers have to accept this one.',
        },
        'rank': {
          text: 'The rank is the number of seasons of that kind at the station that were warmer, plus one.',
          reason: 'A plain count needs no assumption about the distribution of seasons; it is not a method from a source.',
        },
      },
      limits: {
        station: 'The answer is the reading of one station that stands in one place. A town or a region can have had another season; the stations of DWD differ in height, surroundings and instruments.',
        moved: 'A station that was moved, or that changed its instruments or its times of observation, is not corrected for it: the answer is the station\'s series as DWD publishes it. DWD asks that changes in the station height and in the observation times are kept in mind when trends are read.',
        gaps: 'One missing day takes the month, and so the season, out of the comparison, because DWD calculates a monthly mean only from complete daily values (WMO allows up to 10 missing days in a month, and fewer than 5 in a row). A station with gaps has fewer seasons, and a station that began later than a normal has few or none of its seasons: that normal is then not offered.',
        reference: 'The same season set against another normal has another anomaly and can have another verdict. The normal 1961 to 1990 is WMO\'s reference for climate change, the newest one is the current standard, and a new one comes every ten years. How a normal is made is explained on the page "How weather is measured".',
        band: 'The width of "as usual" is wetterdienst\'s own: a difference of just under and just over the band are nearly the same, but have different words.',
      },
      numbers: {
        station: 'Station: {name} ({id}). The answer is the station\'s, not the town\'s.',
        season: 'In {season} {year} ({months}) the mean was {mean} {unit}.',
        reference: 'Compared with the {seasons} of {from} to {to}: the mean of {count} {seasons}, {normal} {unit}.',
        referenceFallback: 'The station has too few {seasons} of the newest WMO normal ({askedFrom} to {askedTo}), so the {count} {seasons} from {from} to {to} are used instead: their mean is {normal} {unit}. That is an average of the station\'s earlier record, not a WMO normal.',
        anomaly: 'Difference: {anomaly} {unit} (the {season} minus the reference).',
        band: 'Within {band} {unit} either way counts as usual.',
        rank: 'Rank {rank} of {count} complete seasons of this kind (rank 1 is the warmest); the record starts in {first}.',
      },
      terms: {
        season: { spring: 'spring', summer: 'summer', autumn: 'autumn', winter: 'winter' },
        seasons: { spring: 'springs', summer: 'summers', autumn: 'autumns', winter: 'winters' },
        months: { spring: 'March to May', summer: 'June to August', autumn: 'September to November', winter: 'December to February' },
      },
    },

    wind: {
      title: 'How windy was it on a day?',
      summary: 'The strongest gust and the mean wind of a day at the place\'s station, turned into a Beaufort force and a word, and set beside the days around it.',
      data: 'DWD\'s daily station observations (dataset daily/climate_summary): the daily highest wind gust (wind_gust_max) and the daily mean wind speed (wind_speed_mean) of the place\'s station, for the {days} days either side of the day.',
      steps: {
        station: 'The values of the day, and of the {days} days before and after it (none after yesterday), are fetched for the place\'s station: the day\'s strongest gust and its mean wind speed.',
        forces: 'Each speed is turned into a force of the Beaufort scale, from 0 to 12, by the table of WMO. The force is the number of lower edges of the table that the speed has reached.',
        verdict: 'Where the station has a gust for the day, the word comes from its force: calm below force {gustBreezy}, breezy from {gustBreezy}, windy from {gustWindy}, stormy from {gustStormy}. Without a gust the mean is used, one force lower: from {meanBreezy}, {meanWindy} and {meanStormy}.',
        around: 'The day is set beside the days around it: how many of them had a stronger value than the day.',
      },
      formulas: {
        force: 'force = the number of lower edges of the Beaufort table (0.3, 1.6, 3.4 … 32.7 m/s) that the speed is at or above',
      },
      rules: {
        'daily-values': {
          text: 'The values are the daily highest wind gust and the daily mean wind speed of the station, in the unit chosen in the settings.',
          says: 'DWD\'s description of its daily data lists the daily maximum of the wind gust and the daily mean of the wind velocity, both in m/s. WMO asks that the wind speed of reports is an average over 10 minutes.',
        },
        'default-day': {
          text: 'A link with no day asks about the last 26 December whose readings can be in: this year\'s from 28 December on, otherwise last year\'s. The reader can pick any day up to yesterday.',
          reason: 'The day is an example the project chose to show what the answer looks like; it has no meaning for the method. No source applies.',
        },
        'beaufort': {
          text: 'A speed becomes a force by the table of WMO: the lower edges of force 1 to 12 are {edges} m/s.',
          says: 'WMO\'s guide gives, for each force of the Beaufort scale from 0 (calm) to 12 (hurricane), the wind speed at a standard height of 10 m above open flat ground that it equals. Force 7, a near gale, is 13.9 to 17.1 m/s; force 9, a strong gale, 20.8 to 24.4 m/s.',
        },
        'gust-first': {
          text: 'Where the station has a gust for the day, the verdict is read from the gust, otherwise from the mean.',
          says: 'WMO says that the wind speed of reports is an average over 10 minutes (§5.1.2), and that many applications, among them the climatology of wind loads, need the gusts (§5.1.3); the 3 second peak gust is one of the two variables it names for routine reading. Its Table 5.1 gives the Beaufort forces as wind speed equivalents at a height of 10 m, for estimating wind.',
          reason: 'A gust says more about a rough day than the mean does. Reported wind is a 10-minute mean and Table 5.1 gives the equivalents of speeds in that sense, so reading a gust of seconds by it is an inference of wetterdienst\'s, not a statement of WMO\'s.',
        },
        'gust-words': {
          text: 'By the gust: calm below force {gustBreezy}, breezy from {gustBreezy}, windy from {gustWindy}, stormy from {gustStormy}.',
          says: 'WMO\'s table names force 5 a fresh breeze, force 7 a near gale and force 9 a strong gale. DWD\'s warning criteria start the first level of wind warnings at gusts over 50 km/h, which is force 7, and call gusts of 65 to 89 km/h (force 8 to 9) storm gusts; DWD says the scale is modelled on the Beaufort scale.',
          reason: 'The four words are wetterdienst\'s grouping of the twelve forces. Its edges follow the names of WMO\'s table. "Windy" starts where DWD\'s first warning level starts, and "stormy" one force above where DWD\'s storm gusts start. No source gives these four words.',
        },
        'mean-words': {
          text: 'By the mean, where there is no gust: calm below force {meanBreezy}, breezy from {meanBreezy}, windy from {meanWindy}, stormy from {meanStormy}.',
          says: 'WMO\'s table names force 4 a moderate breeze, force 6 a strong breeze and force 8 a gale.',
          reason: 'A mean is lower than the gust of the same hour, so the lines are one force lower than those for a gust. No source gives them.',
        },
        'around-window': {
          text: 'The day is set beside the {days} days before it and the {days} days after it, none of them after yesterday.',
          reason: 'A week either side is enough to show whether the day was unusual for that spell of weather, and short enough that the season hardly changes. No source gives a window.',
        },
        'stronger-count': {
          text: 'How many of the days around were stronger is a plain count of the days with a larger value.',
          reason: 'A count needs no assumption about the distribution of wind and is easy to check against the chart. It is not a method from a source.',
        },
      },
      limits: {
        station: 'The wind of one station is not the wind of a town or a region. WMO says it is nearly impossible to find a place where the wind speed is representative of a large area, and that the exposure of the anemometer is the most difficult aspect of wind measurement.',
        gust: 'A Beaufort force of a gust is not the force of the wind: reported wind is averaged over 10 minutes, the table gives the equivalents of such speeds, and a gust lasts seconds. "Stormy" here means a strong gust, not a "storm" (force 10 of WMO\'s table) in the sense of a mean wind.',
        missing: 'A day for which the station has neither a gust nor a mean has no answer. Without a gust the word comes from the mean, on the scale that is one force lower.',
        height: 'The Beaufort table is for a height of 10 m above open ground. DWD\'s stations differ in the height of the sensor, and a sensor at another height reads another speed; the page "How weather is measured" gives an example.',
        window: 'The days around the day do not reach beyond yesterday, because later days are not in the data yet.',
      },
      numbers: {
        station: 'Station: {name} ({id}).',
        day: 'The day: {day}.',
        mean: 'Daily mean wind: {speed} {unit}, Beaufort force {force}.',
        gust: 'Strongest gust: {speed} {unit}, Beaufort force {force}.',
        scaleGust: 'Scale used, by the gust: calm below force {breezy}, breezy from {breezy}, windy from {windy}, stormy from {stormy}.',
        scaleMean: 'The station has no gust for this day, so the mean is used: calm below force {breezy}, breezy from {breezy}, windy from {windy}, stormy from {stormy}.',
        around: 'In the days around it (up to {days} either side), {around} have a value and {stronger} of them had a stronger one.',
      },
    },

    download: {
      title: 'Where can I download hourly temperatures?',
      summary: 'The weather services whose measurements wetterdienst can read at an hourly step with the air temperature in them.',
      data: 'No weather data is read for this answer: it is the list of the providers of wetterdienst and the coverage that each measurement network states for the hourly resolution.',
      steps: {
        providers: 'The list of providers is read from the backend of wetterdienst, and only their measurement networks (kind "observation") are looked at.',
        coverage: 'For each of them the coverage of the hourly resolution is asked, a few at a time. A network is listed if it has an hourly dataset with the air temperature at 2 m, the dataset named temperature_air first. A network with no hourly data answers that it has none, and is left out.',
        order: 'DWD, the service of the place\'s own country, comes first, then the others by name in the language of the page. Each links to the Explorer on that data.',
      },
      formulas: {},
      rules: {
        'networks': {
          text: 'Only measurement networks are looked at, not forecasts, radar, alerts or derived data.',
          reason: 'The question is about temperatures that were measured. This is a choice of the app.',
        },
        'hourly-temperature': {
          text: 'A network counts if its hourly coverage has a parameter named temperature_air_mean_2m or temperature_air_2m.',
          says: 'WMO\'s guide says that the observed air temperature should be representative of the free air at a height of between 1.25 and 2 m above ground.',
          reason: 'These are the names that providers give the hourly air temperature at 2 m, as wetterdienst lists them; the list is the app\'s, and what the names mean is checked against the coverage, not against a source.',
        },
        'order': {
          text: 'DWD comes first, the others follow in the order of their names.',
          reason: 'The places of the app are DWD stations, so DWD\'s service is the one of the place; the rest is in alphabetical order so that the list ranks no provider.',
        },
      },
      limits: {
        coverage: 'A network is listed if the backend says it has the parameter at an hourly step; that is no promise that every station or every year has values.',
        definitions: 'The hourly temperatures of the providers are not all the same kind of number: some are a reading at the hour, others the mean of the hour. Look at the provider\'s description before you compare them.',
        licences: 'Each provider publishes its data under its own terms. The Providers page and the credit under an answer say which.',
      },
      numbers: {
        count: '{count} services were found.',
        parameters: 'The coverage was searched for the parameters {names}.',
      },
    },
  },

  works: {
    'wmo-8-i': {
      plain: `${WMO} Volume I of its Guide to Instruments and Methods of Observation is the handbook for measuring temperature, wind, precipitation and the other variables. Here it gives the Beaufort scale of wind force, what an average of the wind is, why gusts matter, and what is called a trace of rain.`,
    },
    'wmo-1203': {
      plain: `${WMO} Its Guidelines on the Calculation of Climate Normals say what a climate normal is, which periods count, how a normal is made from monthly values and how much missing data is allowed. A normal is the average of a long, fixed period that recent weather is compared with. The thirty years became the standard mainly because only thirty years of data were available when it was first recommended. Here it gives the normals that can be chosen (the reference normal 1961 to 1990 and the later ones), the way a season is calculated and the rules for a station that has too few years.`,
    },
    'dwd-seasons': {
      plain: `${DWD} Its weather lexicon says how meteorologists divide the year: each season is three whole months, because the statistics of the climate are made from the data of single months.`,
    },
    'dwd-summer': {
      plain: `${DWD} In an article of 20 June 2018 it explains why June, July and August are the summer of the meteorologists, and that the reason is statistical: whole months are easier to evaluate.`,
    },
    'dwd-monthly-kl': {
      plain: `${DWD} The description of its monthly station dataset says where the monthly values come from: they are calculated from the daily values, and only if the daily values of the month are complete. It also asks readers to note changes of the station height and of the observation times.`,
    },
    'dwd-daily-kl': {
      plain: `${DWD} The description of its daily station dataset names the parameters and their units. Here it says that FX is the daily maximum of the wind gust and FM the daily mean of the wind velocity, both in m/s.`,
    },
    'dwd-warnings': {
      plain: `${DWD} It publishes the criteria of its weather warnings. For the wind they give a gust speed in km/h and the matching force of the Beaufort scale for each level of warning, at about 10 m above open ground.`,
    },
    'dwd-mosmix': {
      plain: `${DWD} MOSMIX is its forecast for places: it takes the forecasts of weather models and corrects them statistically with what weather stations have measured, because every model simplifies the ground and has systematic errors.`,
    },
    'dwd-mosmix-elements': {
      plain: `${DWD} This is its list of the elements of MOSMIX, with their meaning and unit. It says, for example, that RR1c is the total precipitation during the last hour and R101 the probability of more than 0.1 mm of precipitation during the last hour.`,
    },
  },
}
