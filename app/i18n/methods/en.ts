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
        reference: 'The reference is the mean of the seasons of the normal chosen: 30 years that end in a year ending in 0, from {firstFrom} to {firstTo} on, each one once it is complete. The question opens on the newest one that the station has enough seasons of. A normal can be compared only if the station has at least {minSeasons} of its {ofSeasons} seasons of that kind; one that has fewer is greyed out in the choice, and an answer for it says so. If the station has fewer of the newest normal, the seasons before the one asked about are used instead, if there are at least {fallbackMin}; with fewer there is no answer.',
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
          text: 'A winter takes the December of the year before: December 2025 with January and February 2026 is the winter 2025/26, which counts as the winter of 2026, the year of its January and February. It is over on 1 March. A winter normal is written with the years of its winters: the normal 1961 to 1990 is the winters 1960/61 to 1989/90.',
          says: 'WMO\'s guidelines say that a seasonal normal is the mean of the monthly normals of its months. They do not say which December a winter takes.',
          reason: 'Neither DWD\'s definition of the seasons nor WMO\'s guidelines say which year a winter that spans the turn of the year is named for. wetterdienst names it for the year of its January and February and takes the December before them, so that its three months follow one another, as they do in the weather. As wetterdienst reads it, WMO\'s normal for December, January and February would average the December of the same years as the January and the February; the two differ only by the December at the ends of the period (for the normal 1991 to 2020, December 1990 against December 2020). This is wetterdienst\'s own choice, and the maintainers have to accept it.',
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
          text: 'The question opens on the season that was completed most recently and that the station has enough data for: the autumn from 1 December, the winter from 1 March, the spring from 1 June and the summer from 1 September. A season has enough data where the station has at least {minSeasons} of the {ofSeasons} seasons of some normal, or where the seasons before the last can stand in for the newest normal (see below). Where the latest has too little, it opens on the next most recent. A link or a choice of the reader that names a season keeps it, and the link ?ask=summer names the summer; a season with too little data is greyed out, and a link that names one gets the season the question opens on, with a line that says so.',
          reason: 'No source says which season a question should open on. The one completed most recently is the one people ask about, and the data decides where the latest has too little of it. This replaces the earlier choice (always the summer), which the maintainers had accepted, so it needs accepting again.',
        },
        'reference-choices': {
          text: 'The reference can be any WMO normal of 30 years that ends in a year ending in 0 and is complete: from {firstFrom} to {firstTo} on, with a new one added on 1 January after its last year. The whole record of the station and a sliding 30 years are not offered.',
          says: 'WMO defines the climatological standard normal as the average over 30 years that ends in a year ending in 0: 1981 to 2010, 1991 to 2020 and so on. The period 1961 to 1990 is kept as the reference normal for assessing long-term climate change, but it is not a standard normal. A normal in WMO\'s sense is a period average over at least three consecutive ten-year periods that start on 1 January of a year ending in 1, which every period offered here is.',
        },
        'reference-default': {
          text: 'The question opens on the newest normal that is complete. It ends in the year floor((year − 1) / 10) × 10, so it is 1991 to 2020 until the end of 2030, and from 1 January 2031 it is 2001 to 2030.',
          says: 'WMO says that the climatological standard normal is the most recent 30-year period that finishes in a year ending in 0, and that it is calculated again every ten years.',
        },
        'default-normal': {
          text: 'The question opens on the newest of the normals that the station has enough seasons of for the chosen season: at least {minSeasons} of its {ofSeasons}, or, for the newest normal, enough seasons before the last for the fallback below. A normal that the reader or a link names is kept; where it is greyed out for the season, the normal the question opens on is used instead, and a line says so.',
          reason: 'No source says which of the normals to open on. The newest is the current standard, and the question passes to an older one only where the station cannot be compared with a newer. The maintainers have to accept it.',
        },
        'normal-mean': {
          text: 'The reference is the mean of the complete seasons of its years, each season counting the same. A season in which a month is missing is left out whole.',
          says: 'WMO\'s guidelines build a seasonal normal as the mean of the three monthly normals of its months, and not from the values of single years. If the normal of one month is missing, the seasonal normal is missing.',
          reason: 'The chip averages whole seasons, so a year with one month missing drops out of the reference entirely, where WMO would still use that year in the other two monthly normals. The two give the same where no month is missing. The way the chip averages is wetterdienst\'s own choice.',
        },
        'min-seasons': {
          text: 'A normal can be compared only if the station has at least {minSeasons} of its {ofSeasons} seasons of the kind. Another one is greyed out in the choice, with how many the station has, and an answer for it says so; the newest one uses the fallback below.',
          says: 'WMO asks, for each month, for valid monthly values in at least 80 % of the years of the period for a normal, which is 24 or more of 30 years.',
          reason: 'The chip counts complete seasons (all three months of the season, for a winter with the December before it), not the years of each month, so the line is not WMO\'s and cannot be compared with it one to one. {minSeasons} of {ofSeasons} is wetterdienst\'s own line, set so that stations with gaps still get an answer against a WMO period, and the maintainers have to accept it; the reference of such a station is then not a WMO normal in the strict sense.',
        },
        'fallback-period': {
          text: 'Where the station has too few seasons of the newest normal, the reference is all the seasons of the station before the one asked about. No other normal is replaced like this: one that is picked is the one used, or is greyed out.',
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
        gaps: 'One missing day takes the month, and so the season, out of the comparison, because DWD calculates a monthly mean only from complete daily values (WMO allows up to 10 missing days in a month, and fewer than 5 in a row). A station with gaps has fewer seasons, and a station that began later than a normal has few or none of its seasons: that normal is then greyed out.',
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

    day: {
      title: 'What was a day like?',
      summary: 'How windy, sunny, wet, hot or cold, or snowy a day was at the place\'s station, put into a word by a scale that a published source gives where there is one, and set beside the days around it.',
      data: 'DWD\'s daily station observations (dataset daily/climate_summary): the highest wind gust (wind_gust_max) and the mean wind speed (wind_speed_mean), the sunshine duration (sunshine_duration), the precipitation (precipitation_amount), the highest and lowest air temperature at 2 m (temperature_air_max_2m, temperature_air_min_2m) and the snow depth (snow_depth) of the place\'s station, and its fresh snow (snow_depth_new, from the daily precipitation dataset daily/precipitation_more) where it has any, for the {days} days either side of the day.',
      steps: {
        station: 'The values of the day, and of the {days} days before and after it (none after yesterday), are fetched for the place\'s station, all measures in one request: the wind gust and mean, the sunshine duration, the precipitation, the highest and lowest temperature, the snow depth and the fresh snow. Choosing another measure asks for nothing new.',
        wind: 'Wind: each speed is turned into a force of the Beaufort scale, from 0 to 12, by the table of WMO. Where the station has a gust for the day, the word comes from its force: calm below force {gustBreezy}, breezy from {gustBreezy}, windy from {gustWindy}, stormy from {gustStormy}. Without a gust the mean is used, one force lower: from {meanBreezy}, {meanWindy} and {meanStormy}.',
        sun: 'Sun: the sunshine duration of the day is divided by the sunshine that was possible at the station\'s latitude that day, the time the Sun\'s centre is above a flat horizon, which follows from the Sun\'s declination (about a quarter of an hour shorter than the sunrise to sunset of the tables, which count refraction and the Sun\'s disc). Below {dullBelow} % of it the day is dull, from {sunnyFrom} % it is sunny, and between the two it is mixed.',
        rain: 'Rain: the precipitation of the day, in millimetres, is dry below {dryMm} mm, a little rain from there, wet from {wetMm} mm and very wet from {veryWetMm} mm.',
        temperature: 'Heat and cold: the highest and the lowest temperature of the day are held against the days that DWD names: a hot day (highest temperature {hotDay} °C or more), a summer day (from {summerDay} °C), a tropical night (lowest temperature {tropicalFrom} °C or more), an ice day (highest below {iceBelow} °C) and a frost day (lowest below {frostBelow} °C). The first of them in this order names the day, and the others it belongs to are listed with it.',
        snow: 'Snow: snow lies where the snow depth of the day is above {snowAboveCm} cm. The depth is given, and the fresh snow where the station reports it.',
        around: 'The day is set beside the days around it, as a chart of them. For the wind it is also counted how many of them had a stronger value than the day.',
      },
      formulas: {
        force: 'force = the number of lower edges of the Beaufort table (0.3, 1.6, 3.4 … 32.7 m/s) that the speed is at or above',
        daylength: 'sin δ = sin ε · sin λ (δ: the Sun\'s declination, ε: the obliquity of the ecliptic, 23.439°, λ: the Sun\'s ecliptic longitude); cos t = −tan φ · tan δ (t: the hour angle of sunrise, φ: the latitude); possible sunshine = 2 · t ÷ 15° per hour',
        share: 'share = sunshine duration ÷ possible sunshine, not above 100 %',
      },
      rules: {
        'daily-values': {
          text: 'The values are the station\'s daily values: the highest wind gust and the mean wind speed, the sunshine duration, the precipitation, the highest and lowest air temperature at 2 m, the snow depth, and the fresh snow where the station has it. They are in the unit chosen in the settings, except the sunshine, which is always in hours.',
          says: 'DWD\'s description of its daily data lists FX, the daily maximum of the wind gust, and FM, the daily mean of the wind velocity (m/s), SDK, the daily sunshine duration (h), RSK, the daily precipitation height (mm), TXK and TNK, the daily maximum and minimum of the temperature at 2 m height (°C), and SHK_TAG, the daily snow depth (cm). The description of its daily precipitation data lists SH_TAG, the height of the snow pack, and NSH_TAG, the fresh snow depth (cm).',
        },
        'default-day': {
          text: 'A link with no day asks about the same date last year. A 29 February, which the year before did not have, asks about 28 February. The reader can pick any day up to yesterday.',
          reason: 'The day is an example the project chose to show what the answer looks like: the same date a year ago has its readings in the data, and it is in the same season as today. It has no meaning for the method. No source applies. It replaces the last 26 December that the question opened on before.',
        },
        'default-measure': {
          text: 'A link with no measure asks about the wind, the question this chip always was. Where the station has no wind reading for the day, it opens on the first measure that it has a reading of: sun, rain, heat and cold, snow.',
          reason: 'The wind is what the question asked about before it had a choice, so that links and habits keep their meaning, and falling back to a measure with data shows an answer rather than an empty one. No source applies.',
        },
        'measure-reading': {
          text: 'A measure is offered only if the station has a reading of it for the day. The others are greyed out with that said, and a link that names one gets the default, with a line that says so. Heat and cold need both the highest and the lowest temperature, the wind either the gust or the mean.',
          reason: 'A verdict made from a reading that is not there would be made up. Both temperatures are needed because a frost day cannot be ruled out without the lowest one. No source applies.',
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
        'sun-share': {
          text: 'The sunshine duration of the day is compared with the sunshine that was possible at the station\'s latitude that day, as a share from 0 to 100 %.',
          says: 'WMO defines sunshine duration as the time for which the direct solar irradiance exceeds 120 W per square metre (§8.1.1), and says that for climatological purposes a "relative daily sunshine duration" is used, which relates the sunshine duration to the extra-terrestrial possible one, written SD0 (§8.1.2).',
        },
        'day-length': {
          text: 'The possible sunshine is the length of the day at the station\'s latitude: the Sun\'s declination on that day gives the hour angle of sunrise, and the day is twice that angle at 15 degrees to the hour, on a flat horizon (the Sun\'s centre at the horizon, with no refraction: about a quarter of an hour shorter than the sunrise to sunset of the tables). A day on which the Sun does not rise has no answer.',
          says: 'WMO gives the approximate formulae of the Astronomical Almanac for the position of the Sun, from which the declination follows (Annex 7.F), and, for a mathematical horizon, the hour angle of sunrise and sunset as cos t = −tan(latitude) · tan(declination) (Annex 7.G).',
        },
        'sun-bands': {
          text: 'By the share of the possible sunshine: dull below {dullBelow} %, mixed from {dullBelow} %, sunny from {sunnyFrom} %.',
          says: 'WMO describes three ranges of the relative daily sunshine duration: "cloudy sky" from 0 up to 0.3, "scattered clouds" from 0.3 up to 0.7 and "fair weather" from 0.7 to 1.0. It uses them to say how much the requirements on a sunshine recorder depend on the cloudiness of the place.',
          reason: 'The edges are WMO\'s. Calling the three ranges "dull", "mixed" and "sunny" is wetterdienst\'s own use of them: WMO uses them to describe the cloudiness a recorder has to cope with, not the weather of a day, and no source names a verdict for a day.',
        },
        'rain-trace': {
          text: 'A day with less than {dryMm} mm of precipitation is dry.',
          says: 'WMO says that daily amounts of precipitation should be read to the nearest 0.2 mm and, if feasible, to the nearest 0.1 mm, and that amounts less than 0.1 mm are generally referred to as trace amounts.',
          reason: 'The edge is WMO\'s. The word "dry" for a day below it is wetterdienst\'s own: WMO calls such amounts traces and names no class of day.',
        },
        'rain-wet-day': {
          text: 'From {wetMm} mm the day is wet. The days between {dryMm} mm and {wetMm} mm have a little rain.',
          says: 'WMO\'s guidelines list the number of days with precipitation of 1 mm or more among the principal climatological parameters of a station\'s normals.',
          reason: 'WMO\'s table counts the days of 1 mm or more and names no class: calling such a day "wet", and one between the two edges "a little rain", is wetterdienst\'s own wording. No source names a day.',
        },
        'rain-very-wet': {
          text: 'From {veryWetMm} mm the day is very wet.',
          says: 'The same table lists the number of days with a daily precipitation of 5, 10, 50, 100 and 150 mm or more among the secondary parameters; 10 mm is one of those thresholds.',
          reason: 'WMO lists thresholds to count days by, not words for them. The word "very wet" for the days from 10 mm, and leaving out the thresholds of 5 mm and of 50 mm and more, are wetterdienst\'s own: four words are enough to describe a day, and the amount is always given with it.',
        },
        'heat-days': {
          text: 'A summer day has a highest temperature of {summerDay} °C or more, a hot day {hotDay} °C or more.',
          says: 'DWD defines the Sommertag as a day with a highest air temperature of at least 25.0 °C and the Heiße Tag as one with at least 30.0 °C. WMO\'s guidelines list the number of days with a maximum temperature of 25, 30, 35 and 40 °C or more among the secondary parameters of normals.',
        },
        'cold-days': {
          text: 'A frost day has a lowest temperature below {frostBelow} °C, an ice day a highest temperature below {iceBelow} °C. An ice day is a frost day too.',
          says: 'DWD defines the Frosttag as a day whose lowest air temperature is below 0.0 °C and the Eistag as one whose highest is below 0.0 °C. WMO\'s guidelines list the number of days with a maximum temperature below 0 °C and with a minimum below 0 °C among the secondary parameters of normals.',
        },
        'tropical-night': {
          text: 'A tropical night has a lowest temperature of {tropicalFrom} °C or more.',
          says: 'DWD defines the Tropennacht as a night in which the lowest air temperature is 20 °C or more, measured from 18 UTC to 06 UTC.',
        },
        'tropical-daily-minimum': {
          text: 'The lowest temperature of the station\'s day stands in for the lowest temperature of the night: a day whose lowest temperature is {tropicalFrom} °C or more counts as a tropical night.',
          says: 'DWD measures the night from 18 UTC to 06 UTC.',
          reason: 'The station\'s daily data has no minimum of the night alone. The daily minimum is that of the day, and a night lies over two days, so this is an approximation: where the day never fell below 20 °C, the hours of two nights that lie in it (00 to 06 and 18 to 24 UTC) did not either, but the other half of each night belongs to the next or the previous day and is not looked at.',
        },
        'class-order': {
          text: 'A day is named by the first class that it belongs to, in this order: hot day, summer day, tropical night, ice day, frost day. The other classes it belongs to are listed with the word. A day with none is called "neither frost nor a summer day".',
          says: 'DWD calls the days on which a threshold of a meteorological parameter is reached or passed "Kenntage" (days that characterise a time of the year), and names the Sommertag, the Heiße Tag, the Frosttag and the Eistag among them.',
          reason: 'Every hot day is a summer day and every ice day is a frost day, so the stronger class says more. The heat comes before the cold because hardly any day is both (it would need a range of more than 25 K within the day); where one is, both are listed. The order is wetterdienst\'s, and no source gives one.',
        },
        'snow-lies': {
          text: 'Snow lies where the snow depth of the day is above {snowAboveCm} cm. Otherwise there is no snow on the ground.',
          says: 'WMO\'s guidelines list the number of days with a snow depth above 0, 1, 10 and 50 cm among the secondary parameters of normals; above 0 cm is the first of them.',
        },
        'fresh-snow': {
          text: 'The fresh snow of the day is added where the station reports it. It comes from DWD\'s daily precipitation dataset, as the climate summary has none.',
          says: 'DWD\'s description of its daily precipitation data lists SH_TAG, the height of the snow pack, and NSH_TAG, the fresh snow depth, both in cm.',
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
        'station': 'The readings of one station are not the weather of a town or a region: sun, rain, wind and frost differ over a few kilometres. WMO says it is nearly impossible to find a place where the wind speed is representative of a large area, and that the exposure of the anemometer is the most difficult aspect of wind measurement.',
        'missing': 'A measure that the station has no reading of for the day has no answer, and its option is greyed out. Without a gust the wind\'s word comes from the mean, on the scale that is one force lower.',
        'window': 'The days around the day do not reach beyond yesterday, because later days are not in the data yet.',
        'time': 'A day is not the same 24 hours in every column of DWD\'s daily data. From April 2001, at the stations checked, the precipitation covers 06:00 UTC to 06:00 UTC of the next day, the highest and lowest temperature and the sunshine duration cover 00:00 to 24:00 UTC, and the snow depth is the reading of 06 UTC. The page "How weather is measured" explains it.',
        'gust': 'A Beaufort force of a gust is not the force of the wind: reported wind is averaged over 10 minutes, the table gives the equivalents of such speeds, and a gust lasts seconds. "Stormy" here means a strong gust, not a "storm" (force 10 of WMO\'s table) in the sense of a mean wind.',
        'height': 'The Beaufort table is for a height of 10 m above open ground. DWD\'s stations differ in the height of the sensor, and a sensor at another height reads another speed; the page "How weather is measured" gives an example.',
        'horizon': 'The possible sunshine is the day on a flat horizon, counted to the Sun\'s centre and with no refraction, as WMO\'s SD0 is: about a quarter of an hour shorter than the sunrise to sunset of the tables. A sunshine recorder needs the Sun some degrees above the horizon (WMO asks for a free view of it wherever it is more than 3° up), and hills, buildings and trees at the station take more, so even a cloudless day usually stays a little under 100 %.',
        'recorder': 'Sunshine duration is measured to about a tenth of an hour at best (WMO asks for ±0.1 h). WMO says the highest precision is needed where high cloud layers dim the direct sunlight to around 120 W per square metre, and that a dominantly clouded sky shows the highest percentage of deviations from the reference: a dull day is the least certain one.',
        'gauge': 'A rain gauge measures at one point, and the wind makes it catch less than falls: WMO calls the wind the greatest source of disturbance in precipitation measurements and says the undercatch of rain in a standard gauge can be as high as 10 %.',
        'night': 'A tropical night is a night from 18 UTC to 06 UTC, and the answer looks at the station\'s day from 00:00 to 24:00 UTC. In Germany local time is one or two hours ahead of UTC.',
        'snow-reading': 'DWD\'s snow depth is the reading of 06 UTC at the stations checked: snow that fell and melted during the day is not in it, and a day with fresh snow can show a depth of 0 cm. The fresh snow is a value of its own that not every station reports; where it has none, the answer says so. The link into the Explorer opens the snow depth; the fresh snow is in the dataset daily/precipitation_more.',
      },
      numbers: {
        station: 'Station: {name} ({id}).',
        day: 'The day: {day}.',
        mean: 'Daily mean wind: {speed} {unit}, Beaufort force {force}.',
        gust: 'Strongest gust: {speed} {unit}, Beaufort force {force}.',
        scaleGust: 'Scale used, by the gust: calm below force {breezy}, breezy from {breezy}, windy from {windy}, stormy from {stormy}.',
        scaleMean: 'The station has no gust for this day, so the mean is used: calm below force {breezy}, breezy from {breezy}, windy from {windy}, stormy from {stormy}.',
        around: 'In the days around it (up to {days} either side), {around} have a value and {stronger} of them had a stronger one.',
        sunHours: 'Sunshine: {hours} h. At {latitude}° N the Sun could shine {possible} h that day, so the day had {share} of the possible sunshine.',
        sunScale: 'Scale used: dull below {dull}, mixed from {dull}, sunny from {sunny} of the possible sunshine.',
        rainAmount: 'Precipitation of the day: {amount} {unit}.',
        rainScale: 'Scale used: dry below {dry} {unit}, a little rain from {dry}, wet from {wet}, very wet from {veryWet} {unit}.',
        tempRange: 'Highest temperature {max} {unit}, lowest {min} {unit}.',
        tempClass: 'The day counts as: {kind}.',
        tempScale: 'Days counted: a summer day has a highest temperature from {summer} {unit}, a hot day from {hot} {unit}, an ice day below {ice} {unit}; a frost day has a lowest temperature below {frost} {unit}, a tropical night from {tropical} {unit}.',
        snowDepth: 'Snow depth: {depth} {unit}.',
        snowFresh: 'Fresh snow: {fresh} {unit}.',
        snowNoFresh: 'The station has no reading of fresh snow for this day.',
        snowScale: 'Snow counts as lying where the depth is above {above} {unit}.',
        window: 'The chart shows up to {days} days either side of the day; {given} of its days have a reading.',
      },
      terms: {
        kind: { hot: 'hot day', summer: 'summer day', tropical: 'tropical night', ice: 'ice day', frost: 'frost day' },
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

    monthrain: {
      title: 'Was this month wetter than the same month last year?',
      summary: 'The rain of the days of this month so far at the place\'s station, set against the rain of the same days of the same month a year before.',
      data: 'DWD\'s daily station observations (dataset daily/climate_summary): the daily precipitation height of the place\'s station, from the month before this one a year ago up to yesterday.',
      steps: {
        days: 'The days of this month from the 1st up to the newest day with a reading are paired with the same days of the month a year before: the 1st with the 1st, the 2nd with the 2nd, and so on. A day counts only if the station has a reading in both years. If fewer than {minDays} days can be paired, the last complete month is compared with the same month a year before it, and the answer says so.',
        sums: 'The daily amounts of the paired days are added up, once for this year and once for last year. Both sums are over exactly the same days of the month.',
        verdict: 'The month is "wetter" if its sum is above last year\'s by more than the band, "drier" if it is below by more than the band, and "about as wet" within it. The band is {similarMm} mm or {similarShare} % of the larger sum, whichever is more.',
      },
      formulas: {
        sums: 'sum(year) = amount of day 1 + amount of day 2 + … over the days that both years have a reading for; difference = sum(this year) − sum(last year)',
      },
      rules: {
        'daily-precipitation': {
          text: 'The rain of a day is DWD\'s daily precipitation height of the place\'s station.',
          says: 'DWD\'s description of its daily station observations lists the column RSK as the "daily precipitation height", in mm, and names the daily sum among the ways the data are processed.',
        },
        'month-so-far': {
          text: 'This month is compared as far as it has gone: from the 1st to the newest day with a reading, which is yesterday at the latest.',
          reason: 'The question says "this month", which is not over. Comparing it with a whole month a year ago would make it look dry, so only the days that have happened are compared. No source says how to compare a running month.',
        },
        'same-days': {
          text: 'The days are paired by their number in the month: the 5th with the 5th. Only days with a reading in both years are added up. A 29 February has no partner and is left out.',
          reason: 'The same days of the month are the fair comparison of a month that is not over. A day that is missing in one year is left out of both sums, so that a gap is never counted as a dry day. This is a choice of the app.',
        },
        'min-days': {
          text: 'At least {minDays} days must be paired. With fewer (the first days of a month) the last complete month is compared with the same month a year before it.',
          reason: 'A sum over two or three days is mostly luck, and the first days of every month would be a poor answer. A week is a round line chosen by wetterdienst; no source gives one.',
        },
        'month-sum': {
          text: 'The rain of a month is the sum of the daily amounts of the paired days.',
          reason: 'Adding the days is plain arithmetic, and the monthly total is by definition the sum of the daily ones. Which days are added is the rule above.',
        },
        'similar-band': {
          text: 'The two sums are "about the same" if they differ by no more than {similarMm} mm or {similarShare} % of the larger one, whichever is more.',
          reason: 'A millimetre is within what a rain gauge resolves, and a tenth of a wet month is within what chance moves from one year to the next. Both numbers are round ones chosen by wetterdienst; no source gives a line for "about as wet".',
        },
      },
      limits: {
        station: 'The answer is about one station. Rain falls unevenly, and a shower can wet one place and miss another a few kilometres away.',
        recent: 'The newest days come from DWD\'s directory of recent data, for which DWD says quality control has not been completed, so there may always be changes in the values.',
        gauge: 'A sum of rain says how much fell, not how it fell: a month can be as wet as another with one storm or with many days of drizzle.',
        band: 'The words "wetter", "drier" and "about as wet" depend on the band, which is wetterdienst\'s own. The sums and their difference are given in the answer.',
      },
      numbers: {
        station: 'Station: {name} ({id}).',
        month: 'Compared: {month} and {lastMonth}, {days} days with a reading in both.',
        sums: 'Rain of those days: {sum} {unit} in {month}, {lastSum} {unit} in {lastMonth}.',
        difference: 'This year minus last year: {difference} {unit}.',
        band: 'Band of "about as wet": {similarMm} mm or {similarShare} % of the larger sum, whichever is more.',
        fallback: 'Only {count} days of the running month could be paired, fewer than the {min} needed, so the last complete month is compared.',
      },
    },

    nearby: {
      title: 'Is it warmer here than at a station nearby?',
      summary: 'The mean temperature of the last month at the place\'s station, set against that of the nearest other station that reports now.',
      data: 'DWD\'s daily station observations (dataset daily/climate_summary): the daily mean of the air temperature of the place\'s station and of the other station, for the last {windowDays} days up to yesterday.',
      steps: {
        station: 'The stations nearest to the place are looked through, nearest first, for one that is not the place\'s own, lies within {maxKm} km and has readings from the last {reportsDays} days. The first one is used. If there is none, there is no answer.',
        days: 'The last {windowDays} days up to yesterday are taken. A day counts only if both stations have a daily mean for it. If fewer than {minDays} days can be paired there is no answer.',
        means: 'The daily means of the paired days are averaged for each station, and the mean of the other station is subtracted from the mean of the place.',
        verdict: 'The place is "warmer" if its mean is above the other station\'s by more than {band} °C, "cooler" if it is below by more than {band} °C, and "about the same" within it. The chart shows the difference of each day.',
      },
      formulas: {
        means: 'difference = mean over the paired days of (temperature here) − mean over the same days of (temperature at the other station)',
      },
      rules: {
        'daily-mean': {
          text: 'The temperature of a day is DWD\'s daily mean of the air temperature of the station.',
          says: 'DWD\'s description of its daily station observations lists the column TMK as the "daily mean of temperature", in °C.',
        },
        'nearest-station': {
          text: 'The other station is the nearest one that is not the place\'s own, lies within {maxKm} km, and has readings from the last {reportsDays} days.',
          reason: 'Within some tens of kilometres the weather is mostly the same weather, which is what "nearby" asks for; further off the two are not comparable. A station that stopped reporting has no recent days to compare. Both lines are chosen by wetterdienst; no source gives them.',
        },
        'window': {
          text: 'The last {windowDays} days up to yesterday are compared.',
          reason: 'A month is what "lately" means, long enough that one warm night does not decide and short enough to be about now. It is a choice of the app; yesterday is the newest day that is published.',
        },
        'common-days': {
          text: 'At least {minDays} of the {windowDays} days must have a mean at both stations, else there is no answer. Days that only one station has are left out of both means.',
          reason: 'Averaging different days at the two stations would compare the weather of those days, not the stations. Two thirds of the window is a line chosen by wetterdienst; no source gives one.',
        },
        'mean-difference': {
          text: 'The difference is the mean of the place\'s daily means minus the mean of the other station\'s, over the paired days.',
          reason: 'The plain mean of the daily means is the simplest summary of a month and uses no assumption. It is a choice of the app.',
        },
        'same-band': {
          text: 'The means are "about the same" if they differ by no more than {band} °C.',
          reason: 'Half a degree is the band the app also uses for "as usual" in the question about the season, and is within what the height or the site of two stations changes. It is chosen by wetterdienst; no source gives it.',
        },
      },
      limits: {
        height: 'Air is usually cooler the higher a station lies, and a station in a town is usually warmer than one in a field. A difference between the two stations can come from where they are and not from the weather. The answer gives both heights where the list has them.',
        recent: 'The newest days come from DWD\'s directory of recent data, for which DWD says quality control has not been completed, so there may always be changes in the values.',
        station: 'The other station is chosen by the rules above, not for being the most alike. Another one nearby can give another answer.',
        days: 'Where days are missing, the means are of the days both have, which is fewer than {windowDays}; the answer says how many.',
        band: 'The words "warmer", "cooler" and "about the same" depend on the band, which is wetterdienst\'s own. The means and their difference are given in the answer.',
      },
      numbers: {
        station: 'Station: {name} ({id}).',
        other: 'The other station: {name} ({id}), {distance} km away.',
        days: '{days} of the last {window} days, {from} to {to}, have a mean at both stations.',
        means: 'Mean of those days: {here} {unit} here, {there} {unit} at the other station.',
        difference: 'Here minus there: {difference} {unit}.',
        band: 'Band of "about the same": {band} °C.',
      },
    },
  },

  works: {
    'wmo-8-i': {
      plain: `${WMO} Volume I of its Guide to Instruments and Methods of Observation is the handbook for measuring temperature, wind, precipitation and the other variables. Here it gives the Beaufort scale of wind force, what an average of the wind is, why gusts matter, what is called a trace of rain, how sunshine duration is defined and how its relative form is read, and the formulae for the position of the Sun, from which the length of a day follows.`,
    },
    'wmo-1203': {
      plain: `${WMO} Its Guidelines on the Calculation of Climate Normals say what a climate normal is, which periods count, how a normal is made from monthly values and how much missing data is allowed. A normal is the average of a long, fixed period that recent weather is compared with. The thirty years became the standard mainly because only thirty years of data were available when it was first recommended. Here it gives the normals that can be chosen (the reference normal 1961 to 1990 and the later ones), the way a season is calculated, the rules for a station that has too few years, and its list of the days that a station's normals count: days with a given amount of precipitation, with a maximum or minimum temperature above or below a line, and with snow on the ground.`,
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
      plain: `${DWD} The description of its daily station dataset names the parameters and their units. Here it says that FX is the daily maximum of the wind gust and FM the daily mean of the wind velocity, both in m/s, and names the sunshine duration (SDK), the precipitation height (RSK), the highest and lowest temperature at 2 m (TXK, TNK) and the snow depth (SHK_TAG).`,
    },
    'dwd-daily-more-precip': {
      plain: `${DWD} The description of its daily precipitation dataset names the parameters and their units. Here it says that SH_TAG is the height of the snow pack and NSH_TAG the fresh snow depth, both in cm.`,
    },
    'dwd-kenntage': {
      plain: `${DWD} In an article of 13 August 2025 it explains its "Kenntage", the days on which a threshold of a meteorological parameter is reached or passed, as a second way, besides the average temperature, to judge a season. It names the Sommertag (a highest temperature of at least 25.0 °C), the Heiße Tag (30.0 °C), the Frosttag (a lowest temperature below 0.0 °C) and the Eistag (a highest temperature below 0.0 °C).`,
    },
    'dwd-tropennacht': {
      plain: `${DWD} Its weather lexicon defines the Tropennacht as a night in which the lowest air temperature is 20 °C or more, measured from 18 UTC to 06 UTC, and says that at most of its stations there is, on average, less than one a year.`,
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
