# Plausibility checks

Some numbers a source publishes are no readings, though they are no code: 4021 °C for a daily maximum, 1093.3 hPa at a
station at sea level, a sensor that held one value for a month, a road surface 30 K above the air at night. A check
that finds one judges it, and what happens to the value is yours to choose, **per kind of check**. The judging is the
core's, not the reader's: a reader decodes what its source writes as a code and hands the numbers over in the source's
unit, and the library judges them all in one place, in one unit per quantity ([how](#how-the-core-judges)):

- **hard**: the value is null (for `floor`, the floor of its quantity) and the number the source wrote stays in
  `quality_flags` as `rejected:<check>,raw:<number>`;
- **soft**: the value is kept and `quality_flags` says `suspect:<check>`.

There is no mode that skips a check. A soft check already keeps the value, and the flag keeps the judgement visible.

**A forecast is judged soft, but for two checks.** A network whose metadata `kind` is `forecast` (what `coverage` reports: `dwd/mosmix`,
`dwd/dmo`, `dwd/swsmos`, and any provider that declares one) has every check soft but two, **whatever mode is set**: the default,
`hard` given by `Options`, `--plausibility-range=hard`, `plausibility_range=hard` of the REST API or `WD_TS_PLAUSIBILITY`
in the environment. A forecast is the output of a model and no reading, so a value that a check finds (ICON's 394.92 mm of rain
in an hour at 83827 Foz do Iguaçu, above the 350 mm of the table) is kept and flagged `suspect:range`, and never nulled; a
caller who sets `hard` on a forecast and finds nothing nulled sees this rule at work, and the answer is not a missing check.
There are two exceptions, which keep the mode they were given, hard by default. `floor` does not reject: it sets the
model's small negative to the floor of its quantity (0.0) and keeps the number as `rejected:floor,raw:<number>`.
[`limits`](#bounds-of-your-own-limits) are bounds you wrote for a parameter, so you have said what is to go: a forecast
value outside them is null as `rejected:limits,raw:<number>`, or flagged `suspect:limits` where you set the mode soft. The
networks are told by their `kind`, not by a list, so a new forecast network is judged so from its metadata. An
observation or derived network in `hard` mode still nulls.

A check judges. What a source **documents** is no judgement and has no mode: `-999`, `---`, `NaN`, AEMET's `Ip` trace,
FMI's `-1.0` for no snow, a direction of 0 beside a speed of 0 (a calm), the `-0.1` trace of DMI. These are the source's
meanings, not ours, and a soft `-999` would return -999 as a number. They are decoded as before, with `raw:` alone, in
both modes ([special values](special_values.md)).

The tests hold this page to the code: `tests/test_docs_plausibility.py` compares the table below with what the core is
told to judge (its tables and the rules the providers hand it), and `tests/provider/test_plausibility_modes.py` runs
every stubbed source with every check soft.

## How the core judges

For a dataset that a check applies to, the core does this for each station, after the reader has handed over its rows:

1. The rows of the periods the reader read (the historical archive, the recent file, the current one) are made one
   series, the first reading that has a value winning (for DWD the historical archive before the recent one), so that
   no check sees a reading twice.
2. The frame of a grouped dataset is cut to the parameters you asked for and the ones a rule reads beside them (the air
   beside a road surface, the dew point beside a humidity, the air of the road's run rule, the partner of a
   [relation](#the-relations-of-one-row-relations): asking for the daily maximum reads the mean and the minimum too): a verdict on a parameter
   that is cut afterwards would never be seen, so the others are not merged, converted or judged.
3. Those parameters are converted to the canonical unit of their unit type (°C, hPa, m/s, mm, MJ/m², a fraction in
   percent, a duration in hours, a wave period in seconds), without rounding. The bounds of the table are therefore written once per quantity and not once
   per source and unit, and do not depend on the unit you ask for. (The bounds you set yourself,
   [`limits`](#bounds-of-your-own-limits), are in the unit you ask for, and the core converts them.)
4. The checks judge the frame in canonical units. A check that compares two parameters (a road surface and the air
   of its minute) reads both from the frame of the station at the same timestamp, so such a dataset is collected whole.
5. The frame is cut to the parameters you asked for and converted to the unit you asked for, rounded once.

The bounds are one table for every provider, by canonical name and by resolution where the quantity grows with the
span (`wetterdienst.model.plausibility_ranges`, [below](#the-table-of-ranges)). What only a provider knows it hands the
core as data, through one hook: the stations without frost, the periods in which one sensor of one station did not work,
the relation of a road surface to the air at night
([contributing a provider](../contribution/services.md)).

A judged value's `raw:` is the text the source wrote for it (`raw:-0.80`), in the unit of the source: the reader hands
the text over beside the value and the core writes it. Where a source gives the core only a number, the number is
written as short as it goes (`4021.0` as `4021`).

## The checks

| check | judges | default | rule and bounds |
| --- | --- | --- | --- |
| `range` | a reading outside the physical range of its parameter | hard | One table of bounds for every network, by canonical parameter and resolution (the rain of a minute and of a day differ), in the canonical unit, and generous: each rests on a record with room above it (the relative humidity's 1 % floor, which is no record, is the one exception), so that a value that is only odd stays ([the table](#the-table-of-ranges)). No network has bounds of its own in the table; a provider's `Bound` rule can only narrow it (Météo-France: no air below 0 °C at a station without frost). A relative humidity is held to 1 to 100 %, not 0 to 100: a failed hygrometer and a dropout write 0.0 (or 0.1, 0.4), which is inside every range of 0 up, and 1 % is far below any humidity the air of Germany reaches ([why 1](#relative-humidity-under-one-percent)) |
| `elevation` | a station pressure the standard atmosphere does not allow at the station's elevation | hard | In every network that serves a station pressure (`pressure_air_site`, `_mean`, `_min`, `_max`), for each station of the list that has an elevation. Against the pressure of the international standard atmosphere at that elevation, from **870/1013.25 of it** (143 hPa below at sea level: the lowest pressure on record, 870 hPa in Typhoon Tip, as a share of the standard atmosphere) to **75 hPa above it** (the 1,083.8 hPa of Agata, 261 m, the highest sea level pressure of a low station, reduced to the station with the cold column of that day lies 59 to 64 hPa above the standard atmosphere there, the 1,089.1 hPa of Tosontsengel, 1,725 m, 14 to 40: a derivation of GH-3681). The world-wide bounds (300 to 1100 hPa) let through the pressure of another height (968.6 hPa at the Zugspitze, 2,956 m, where 705 are expected) and a P0 mistyped by a digit above the standard atmosphere (1093.3 hPa at 48 m, 85.8 above). A station without an elevation, or one outside -500 to 9,000 m, is not judged. So is a `noaa/ghcn` station at 0.0 m: its lists write 0.0 for stations they know no elevation of (the daily one BRM00083566, inland at about 827 m), and 54 of the 271 at 0.0 in the hourly one stand between 150 and 4,329 m (CHM00052940 reads 500.2 to 998 hPa), while the 0.0 of the lists read (DWD, ECCC, IMGW, Météo-France) is a coast. The margin below keeps Hurricane Irma (917.4 hPa at 10:00 UTC and 936.0 hPa an hour earlier at St-Barthélemy, 3 m, 2017-09-06, quality code 1) and the deep lows of Dumont d'Urville (938 hPa at 43 m, where 1,008 are expected); it lets 3 of the 19 readings of DWD's hourly station pressure beyond 75 hPa of the standard atmosphere (the research of GH-3681, over Berlin-Tempelhof, List auf Sylt and the Zugspitze) pass: 909.5, 910.1 and 908.5 hPa, 98 to 102 hPa below, which the check [`step`](#the-limits-of-a-jump-step) finds as spikes of about 100 hPa |
| `stuck` | a sensor that held one value over a period it should not have | **soft** | **Every observation network**: a run of consecutive readings of one value of one station and parameter, as long as the table of [the limit of a run](#the-limit-of-a-run) says for the parameter, the resolution (10 minutes, hourly, daily) and the step the series is written at. The air temperature (an hour: 24 readings at tenths of a degree, 30 at halves, 40 at whole degrees; a day: 5), the dew point (twice that, hourly and at 10 minutes, not daily), the pressure (72 hourly readings, 36 at 10 minutes, 5 days; a station without a barometer writes its constant in every row), the mean wind speed (a calm is exempt) and, of a day, the rain above 1 mm, the gust, the snow depth and the new snow above 0: the limits of HadISD, ECA&D and GHCN-Daily, and this library's own derivation where none is published (10 minutes, a coarser daily step), each cited in the table. Not judged: where no source gives a limit ([the list](#what-stuck-does-not-judge)). DWD road: 24 readings or more (6 h) of one value of the air, the dew point or the road surface temperature, a gap longer than four times the station's usual one ending the run, melting ice excepted; and 24 readings or more of one value **above zero** of the precipitation intensity, a run of zeros being a dry spell and no fault (55 of the 575 stations that report one write 21.6 or 20.16 mm/h in every reading; the longest run of one non-zero intensity at the others is 13 readings, and 10 for the 10-minute precipitation of 148 stations of DWD observation over 400 days). RMI: the sunshine of station 6477 in the periods its sensor was stuck or dead |
| `step` | a reading that differs from the one before it by more than the weather does in that time, or that jumps away from both neighbours and back | **soft** | **Every observation network**: of one station and parameter, a **step** (the change from the reading one step of the resolution before it is larger than the limit; the later reading is flagged) and a **spike** (a reading that departs from both neighbours by more than the limit, in opposite directions; the middle reading is flagged), as the table of [the limits of a jump](#the-limits-of-a-jump-step) says for the parameter and the resolution (10 minutes, hourly, daily): the air temperature and the dew point (an hour: a spike of 8 K, a step of 20 K; a day: a spike of 25 K), the pressure (60 hPa), the mean wind speed (a spike of 10 m/s, a step of 15 m/s): the limits of ISD, DMI, MADIS and GHCN-Daily, and this library's own data and derivation where none is published, each cited in the table. A reading further than one step from its neighbour (a null or a gap between) is not judged, nor is the first reading of a series. Not judged: where no source gives a limit, or the limit flags good readings ([the list](#what-step-does-not-judge)) |
| `relations` | two readings of one row that contradict each other (a maximum below the mean, a dew point above the air temperature, a gust below the mean wind), or a day of sunshine longer than the day | **soft** | **Every observation network**, for the parameters of one file (a dataset the provider collects whole), as [the table of relations](#the-relations-of-one-row-relations) says: the maximum is not below the mean and the mean not below the minimum (temperature, humidity, pressure, wind), the dew point is at most 0.2 K above the air temperature, a gust is not below the mean wind of its interval, and the sunshine of a day is at most the longest day length of its date at the station, and 5 % more. **Both readings of a broken pair are flagged**, since nothing says which is wrong; the check never downloads the other parameter and stands aside where it is missing. Not `consistency`, which is the hard check of a provider's own rules ([how they differ](#how-relations-differs-from-consistency)) |
| `consistency` | a reading that another parameter of the same file contradicts | hard | DWD road: a road surface more than 20 K above the air of the same minute with the sun more than 6 degrees below the horizon, the air counting only where it passed `range` and is not marked suspect by DWD's own flag. Météo-France: the humidity of an hour whose dew point lies below 0 °C at a station without frost (the same hygrometer), and a `tn12` that is the text of the `tx12` beside it (a copy, no minimum) |
| `floor` | a model value a little below the floor of its quantity | hard | DWD DMO (a forecast, soft in every other built-in check, but `floor` corrects and does not reject, so it keeps its mode): ICON writes -0.02 mm for the precipitation of an hour, down to -0.10, and the radiation of a night below 0. **hard sets the floor**, 0.0, and keeps the number; soft keeps the number as the value |
| `limits` | a reading outside the bounds **you** set for its parameter ([below](#bounds-of-your-own-limits)) | hard | Judges nothing until you set a bound (`Options(limits=...)`, `WD_TS_LIMITS`, `--limits`, `limits` of REST and MCP), and then only the parameters you name. The bounds are in the unit the values come back in, and are a check of their own beside `range`, whose bounds they neither narrow nor widen: a value outside both carries both verdicts, as far as both are in one mode ([the tokens](#the-tokens)) |
| `source` | a value the source itself marks as erroneous or doubtful in its own quality flag and returns | **soft** | The codes the provider's documentation words as a failed check, erroneous, suspect, doubtful or poor, per provider ([below](#the-sources-own-verdict-source)): GHCN-Daily `QFLAG`, GHCNh `Suspect`/`Erroneous`, the letters of its source 382, source 345's `3` and `o`/`f` of a derived humidity, Frost `qualityCode` 7, CHMI `Suspect` and `Poor`, Environment Agency `Suspect`, Météo-France `Q` 2, DMI `validity:false`, NWS/MADIS `X`, `Q` and `B`, Hub'Eau `12`, DWD road `1`, Met Office MIDAS status `1`. Soft keeps the value and writes `suspect:source`; hard nulls it and writes `rejected:source,raw:<text>`, except the suspect level of a source that has two (GHCNh `Suspect` and source 382 `R`, CHMI `Suspect`, MADIS `Questioned`, GHCNh `f`), which stays `suspect:source` |

`stuck` is soft by default because it judges a series and not a value: identical readings are a sign of a stuck sensor
and no proof, and what is found depends on what was read, which differs by network (see the caveats). `step` is soft
for the same reason, and because a front is a real step. `source` is soft by default because its verdict is the source's
and not ours. `relations` is soft because it cannot tell which of two readings is wrong and flags both, so a false alarm
puts a good reading beside the bad one. Every other check is hard, which is what the library did for the networks it
judged before the modes existed; since GH-3681 `range`, `elevation`, `stuck`, `step` and `relations` judge every network.

### The limit of a run

A sensor that holds one value for as long as the weather cannot has stopped: a thermometer that reads the same tenth of a
degree for a day, a barometer that writes its station constant, an anemometer that is jammed. The check flags **every
reading of a run**, consecutive readings of one station and one parameter that hold one value, once the run is as long
as the table below says. The table is **one for every observation network**
([GH-3681](https://github.com/earthobservations/wetterdienst/issues/3681)), by canonical parameter, resolution and the
step the series is written at, and it holds what a published quality control gives a limit for and nothing else
([what is not judged](#what-stuck-does-not-judge)). `wetterdienst.model.persistence` holds it with the same sources in
its docstring; a test holds this table to it.

**Where a limit comes from.** A limit is the level at which a service calls a value *certainly wrong*, not the
strictest tolerance, so that a `suspect:stuck` rarely falls on a good value. Zahumenský's tolerance (60 minutes of
1-minute data, 6 readings at 10 minutes) is not used. Where ECA&D and GHCN-Daily disagree on a daily series in tenths,
the shorter count of ECA&D is taken (5 days for a temperature and a pressure, 10 and 5 for the rain), as the maintainer
decided on 2026-11-01, and not the 20 identical values that GHCN-Daily takes for a temperature or a rain. The sources:

- **HadISD** (Dunn et al. 2012, *Climate of the Past* 8, 1649-1679, table 4; Dunn et al. 2016, *Geoscientific
  Instrumentation, Methods and Data Systems* 5, 473-491), the streak test the GHCN hourly archive (GHCNh) has adopted. A
  limit depends on the resolution a station reports at: a temperature 40 values at 1 K, 30 at 0.5 K and 24 at 0.1 K,
  the dew point twice that, the sea level pressure 120, 100 and 72 values at 1, 0.5 and 0.1 hPa (or 28, 21 and 14 days),
  the wind speed 40, 30 and 24 values at 1, 0.5 and 0.1 m/s, where "all values below 0.5 m/s (or 1 m/s for coarse
  resolution) are also discounted in the streak search".
- **ECA&D** (KNMI, Algorithm Theoretical Basis Document v11, 2021, section 3): a daily value is flagged suspect that is
  "not exactly the same value n days in a row", n being 5 for TX, TN, TG and PP, 10 for RR if more than 1.0 mm and 5 if
  more than 5.0 mm, 6 for FG if at least 2.0 m/s and 5 for FX if at least 4.0 m/s.
- **Durre et al.** (2010, *Journal of Applied Meteorology and Climatology* 49, 1615-1633, table 1), GHCN-Daily: 20
  identical values of TMAX or TMIN, 20 of PRCP (zeros skipped), 90 identical nonzero snow depths (a depth is not tested for duplication, because the
  same depth can last more than a month) and 10 identical nonzero new snows.
- **Zahumenský** (2004, WMO CBS/OPAG-IOS/ET AWS-3/Doc. 4(1)) has a test too, under 0.1 K over 60 minutes of 1-minute
  data. It is the strictest tolerance, written for the firmware of a station, and it is not the level at which a value
  is certainly wrong; it is not used.

A limit that **no source publishes** is this library's own derivation and says so in the table. There are four: the
10-minute counts of the temperature, the dew point and the wind speed are the **span of the hourly limit** in readings
(24 hours are 144 readings), and the 36 readings (6 hours) of a pressure at 10 minutes were derived in the research for
GH-3681 and are kept from GH-3680; and two limits of a coarser step: the 21 and 28 days of a daily pressure (HadISD's
span in days for a streak of hourly values, read as a count of daily values) and the 20 identical values of a daily
temperature (Durre's rule for TMAX and TMIN, applied to every daily temperature). The 10-minute counts rest on measured runs, read on 2026-11-03 in 91 million 10-minute readings (all
parameters; 52.8 million of the four judged ones) of 8 DWD stations: the longest run of one non-zero air temperature is 78 readings and of one pressure 31, so
the 18 readings (3 hours) that the research derived by tripling Zahumenský's 60 minutes would flag 1,163 runs of the
temperature that are weather, where 144
flags five runs in all the readings (two of 0.0 °C at the Zugspitze, 171 and 147 readings, the melting point, and three
of 51.7 m/s at Helgoland, 180 to 308 readings, an anemometer that stopped in a storm).

<!-- persistence:start -->

| parameters | resolution | fine | half | whole | readings that count | source |
| --- | --- | --- | --- | --- | --- | --- |
| `pressure_air_sea_level`, `pressure_air_sea_level_mean`, `pressure_air_site`, `pressure_air_site_mean` | hourly | 72 | 100 | 120 | all | HadISD (Dunn et al. 2012, table 4): sea level pressure, straight repeat of values |
| `temperature_air`, `temperature_air_2m`, `temperature_air_mean_2m` | hourly | 24 | 30 | 40 | all | HadISD (Dunn et al. 2012, table 4): temperature, straight repeat of values |
| `temperature_dew_point`, `temperature_dew_point_2m`, `temperature_dew_point_mean_2m` | hourly | 48 | 60 | 80 | all | HadISD (Dunn et al. 2012, table 4): dew point, twice the straight repeat of a temperature |
| `wind_speed`, `wind_speed_mean`, `wind_speed_mean_last_10min`, `wind_speed_mean_last_2min` | hourly | 24 | 30 | 40 | from 0.5 m/s (1 at a whole step) | HadISD (Dunn et al. 2012, table 4): wind speed, straight repeat of values; values below 0.5 m/s (1 m/s at a whole step) discounted |
| `pressure_air_sea_level`, `pressure_air_sea_level_mean`, `pressure_air_site`, `pressure_air_site_mean` | 10_minutes | 36 | 36 | 36 | all | own derivation: 6 hours, from the research for GH-3681 and kept from GH-3680 (the longest run of one pressure in 13.3 million readings of 8 DWD stations is 31) |
| `temperature_air`, `temperature_air_2m`, `temperature_air_mean_2m` | 10_minutes | 144 | 180 | 240 | all | own derivation: the span of HadISD's hourly limit in readings of 10 minutes (Zahumenský's 60 minutes of 1-minute data, 6 readings, or 18 as the research tripled them, are inside what working sensors do) |
| `temperature_dew_point`, `temperature_dew_point_2m`, `temperature_dew_point_mean_2m` | 10_minutes | 288 | 360 | 480 | all | own derivation: the span of HadISD's hourly limit in readings of 10 minutes (Zahumenský's 60 minutes of 1-minute data, 6 readings, or 18 as the research tripled them, are inside what working sensors do) |
| `wind_speed`, `wind_speed_mean`, `wind_speed_mean_last_10min`, `wind_speed_mean_last_2min` | 10_minutes | 144 | 180 | 240 | from 0.5 m/s (1 at a whole step) | own derivation: the span of HadISD's hourly limit in readings of 10 minutes (Zahumenský's 60 minutes of 1-minute data, 6 readings, or 18 as the research tripled them, are inside what working sensors do) |
| `precipitation_amount` | daily | 10 | 10 | 10 | above 1 mm | ECA&D (ATBD v11, section 3): RR not the same value 10 days in a row if more than 1.0 mm, 5 days if more than 5.0 mm |
| `precipitation_amount` | daily | 5 | 5 | 5 | above 5 mm | ECA&D (ATBD v11, section 3): RR not the same value 10 days in a row if more than 1.0 mm, 5 days if more than 5.0 mm |
| `pressure_air_sea_level`, `pressure_air_sea_level_mean`, `pressure_air_site`, `pressure_air_site_mean` | daily | 5 | 21 | 28 | all | ECA&D (ATBD v11, section 3): PP not the same value 5 days in a row; own derivation for a coarser step: HadISD's 21 and 28 days at 0.5 and 1 hPa (table 4), read as counts of daily values |
| `snow_depth` | daily | 90 | 90 | 90 | above 0 cm | Durre et al. 2010 (table 1): SNWD, 90 consecutive identical nonzero values |
| `snow_depth_new` | daily | 10 | 10 | 10 | above 0 cm | Durre et al. 2010 (table 1): SNOW, 10 consecutive identical nonzero values |
| `temperature_air_2m`, `temperature_air_max_2m`, `temperature_air_mean_2m`, `temperature_air_min_2m` | daily | 5 | 20 | 20 | all | ECA&D (ATBD v11, section 3): TX, TN, TG not the same value 5 days in a row; own derivation for a coarser step: the 20 identical values of Durre et al. 2010 (table 1) for TMAX and TMIN, applied to every daily temperature |
| `wind_gust_max` | daily | 5 | - | - | from 4 m/s | ECA&D (ATBD v11, section 3): FX not the same value 5 days in a row if at least 4.0 m/s |
| `wind_speed`, `wind_speed_mean` | daily | 6 | - | - | from 2 m/s | ECA&D (ATBD v11, section 3): FG not the same value 6 days in a row if at least 2.0 m/s |

<!-- persistence:end -->

Counts are consecutive readings (days at a daily resolution). `-` means that no source gives a limit for a series at
that step and none is judged: ECA&D's daily wind rules are for series in tenths of a metre per second, and a daily
wind written in whole metres per second or in knots holds one value for days.

**The step a series is written at.** A source that writes whole degrees holds one value for longer than one that writes
tenths, so a limit has three counts. A series is **whole** where at least 80 % of its values are whole numbers of the
canonical unit (a series in tenths has about a tenth of them) and **half** where that many are multiples of 0.5; else
the typical gap between its different values tells (**fine** below 0.25, half below 0.75, else whole: a Fahrenheit
degree is 0.56 K, a knot 0.51 m/s). The step is read **per calendar year** of the parameter, because a source changes it
(DWD's hourly temperature of `hourly/moisture` is in whole degrees until 1981 and in tenths after, which a station-wide
reading would take for tenths and flag the whole-degree years by the limit of 24), and the values are counted where
they change, so a stretch of one value for hours does not decide the step of the rest. A year with fewer than 10 changes of value
(the start of a run at a year boundary) tells nothing of the step, and the step of all the readings is taken instead. A
year, or a series, that holds one value in 500 readings or more (a barometer that writes 1012.0 for decades) is
**fine**, the strictest limit, whatever number it writes: a stopped sensor. One value in fewer readings (a short
window) is read by what it is: a whole number may be whole degrees, anything else is fine.

**Readings that do not count.** A reading below the floor in the column "readings that count" is exempt (a calm wind, a
dry day, no snow): it never counts and **ends a run**, so a dry day between two falls of 7.0 mm is no run of 7.0 mm.
A reading that is missing does not break a run: a null inside a short stretch is skipped, and the equal values on both
sides are one run. A **gap** does: where two readings are more than four times the interval of the resolution apart
(more than 4 hours at hourly, 40 minutes at 10 minutes, 4 days at daily), the run ends there, as the road rule's does. A
month of `-999` between two readings of 997.3 hPa is two stretches and not one. The run is judged in the series the core
is handed, after the periods are merged, so a station whose historical file is constant and whose recent file is not is
flagged for the stretch that is.

### What `stuck` does not judge

Where no source gives a limit the check stands aside, however long the run: it does not invent one.

- **Relative humidity.** The only source is Zahumenský's 1 % over 60 minutes of 1-minute data. DWD's hourly humidity, in
  whole percents, holds one value for long stretches that are weather: 97 to 99 % for 41 to 160 hours, 100 % for up to
  243 (Zugspitze, Feldberg, Straubing), so an exemption of 100 % would not be enough and a derived limit would flag them.
- **Wind direction.** The only source is ECA&D's daily mean direction. DWD's hourly direction, in steps of 10 degrees,
  holds one value for 30 to 206 hours (206 hours of 80 degrees at Potsdam in March 1969).
- **A calm wind, no rain, no snow, no sunshine, no radiation** are the normal state and exempt where the parameter is
  judged at all; sunshine, radiation, cloud cover (0 or 8 oktas), soil temperature and the sub-daily rain have no source
  for a run and are not judged.
- **The extremes of an interval shorter than a day** (the maximum temperature of an hour), **gusts** at any resolution
  but the daily one, and the **amounts of an interval** (the rain of an hour).
- **Any resolution but 10 minutes, hourly and daily** (1, 5, 6 and 15 minutes, 6 hours, subdaily reports, months,
  years), **forecasts** (a model holds one value without a sensor failing) and **derived quantities**.

#### How it relates to the rules that were there

- **The barometer of DWD observation** (72 hourly readings, 5 days, 36 at 10 minutes of a station pressure, GH-2699) is
  **merged**: those are the limits of the pressure rows above, now for every network and for the sea level pressure.
  Nothing changes for DWD in practice: the hourly `moisture` pressure of the ten stations read flags 1,054,736 readings
  (635 runs) where the earlier rule, written out, flags 1,054,738.
- **DWD road** (24 readings at 15 minutes of the air, the dew point and the road surface temperature, melting ice
  excepted, and of a precipitation intensity above zero) **stays a provider rule**: 15 minutes is not a resolution the
  table has a source for, and the rule rests on the measured runs of 700 road stations and on the melting-ice exception
  that only the road knows.
- **RMI's dated periods** of the sunshine sensor of station 6477 stay a provider rule as well (a dated fact, not a run).

#### What it found in real data

Read on 2026-11-03 from DWD's open data (historical and recent files merged, whole histories, 10 stations for hourly
and daily, 8 for 10 minutes: Dresden-Klotzsche, Hamburg, Potsdam, Zugspitze, Helgoland, Arkona, Feldberg,
Berlin-Tempelhof, and for hourly and daily Straubing and Trier as well):

| resolution | parameter (dataset) | readings | runs flagged | readings flagged | what they are |
| --- | --- | --- | --- | --- | --- |
| hourly | air temperature (`temperature_air`) | 6,298,984 | 2 | 67 | 0.0 °C for 43 hours (Straubing, 1999-11) and 24 (Trier, 2001-03) |
| hourly | air temperature (`moisture`) | 4,505,460 | 3 | 125 | 40 to 43 hours of 1.0 to 4.0 °C in 1979 to 1981, when DWD wrote whole degrees (Helgoland, Potsdam) |
| hourly | dew point (`moisture`) | 4,501,287 | 3 | 354 | 0.0 °C for 184, 75 and 95 hours (Berlin-Tempelhof 2019-05 and 2014-03, Potsdam 2022-10) |
| hourly | station pressure (`moisture`) | 4,505,396 | 635 | 1,054,736 | the constants of stations without a barometer; the earlier rule, written out, flags 1,054,738 |
| hourly | mean wind speed (`wind`, `wind_synoptic`), pressure (`pressure`) | 17,370,526 | 0 | 0 | |
| 10 minutes | air temperature, dew point, pressure, mean wind speed (`temperature_air`, `wind`) | 52,770,020 | 5 | 987 | 0.0 °C for 171 and 147 readings at the Zugspitze (the melting point), 51.7 m/s for 308, 181 and 180 readings at Helgoland (an anemometer that stopped in a storm) |
| daily | air temperature, pressure, mean wind, gust, rain, snow depth, new snow (`climate_summary`, `precipitation_more`, `water_equivalent`) | 2,700,000 | 2 | 11 | 5 days of 10.1 °C as a minimum (Arkona, 2019-05), 6 days of 13.0 m/s as a gust (Dresden-Klotzsche, 1992-06) |

The hourly humidity and wind direction and the 10-minute ones, which are not judged, hold runs of 97 to 100 % for up to
243 hours and of 10 degrees for up to 206 hours. Other key-less networks, one year (2023) and two stations each: CHMI (hourly
17,520 readings, daily 3,650), IMGW (daily, 5,601), SMHI (hourly 35,740, daily 2,921) and RMI (hourly 218,848, daily
10,571) have no run flagged.

### The limits of a jump (`step`)

The air does not change by 20 K in an hour, and a barometer that reads 100 hPa too low for one hour and the right value
the next has made a mistake, however plausible each number is by itself. The check judges two things in every
observation network, for one station and one parameter
([GH-3681](https://github.com/earthobservations/wetterdienst/issues/3681)):

- a **step**: a reading that differs from the one before it by more than the limit for the time between two readings.
  The **later** reading is flagged, the one that arrives with the jump: nothing says which of the two is wrong;
- a **spike**: a reading that departs from the one before it by more than the limit and from the one after it by more
  than the limit, in the opposite direction, so that it comes back within one step. Only the **middle** reading is
  flagged. A spike is judged first. The reading after it is judged against the last reading **before it that is no spike**
  (before the spike, or before several in a row), not against the spike, which is the mistake: a jump back to where the series was is no step, and a jump somewhere else
  (10, 10, 19, -20: a spike of 19 and a step of 30 K from the 10) is one.

A change has to *exceed* the limit: 8.0 K is no spike of 8 K. The limits are per parameter and resolution, in the
canonical unit, and `wetterdienst.model.rate_of_change` holds them with the same sources in its docstring; a test holds
this table to it.

**Where a limit comes from.** As for `stuck`, a limit is the level at which a service calls a value *certainly wrong*,
not the strictest tolerance (the maintainer's decision of 2026-11-01), so that a `suspect:step` rarely falls on a good
reading: an hourly air temperature of 8 K as a spike (ISD, DMI's "certain error" of 6 to 8 K) and not the 4 K an hour of
WMO-No. 305 (1993, withdrawn), or Zahumenský's 3 K a minute, written for the firmware of a station. The sources:

- **ISD** (Lott 2004, "The quality control of the Integrated Surface Hourly database", AMS 84th Annual Meeting,
  section 4): a rise of 8 °C in one hour triggers a look at the next report, and if the temperature falls back by 8 °C
  or more the value in the middle is "an improbable spike". The paper applies the same continuity test to the dew
  point, the wind speed and the pressure and **gives no limit for them**. It writes "or more"; the code flags a change
  of *more than* the limit, so a change of exactly 8.0 K is no spike.
- **DMI** (Vejen et al. 2002, *Quality control of meteorological observations. Automatic methods used in the Nordic
  countries*, NORDKLIM / MET Report 8/2002, table 3.1): the step limits per month, flag 3 being a "certain error": for one
  hour 6 K (October to March) to 8 K (May to August) of the air temperature, 5 to 8 hPa of the pressure and 15 m/s of
  the wind speed.
- **MADIS** (NOAA / NWS, *MADIS surface data QC*, temporal consistency): 35 F (19.4 K) an hour of the air and the dew
  point temperature, 50 % of the relative humidity, 15 hPa of the sea level pressure, 20 kt (10.3 m/s) of the wind speed
  and 5 F (2.8 K) of the soil temperature. A reading that fails is questioned, not rejected.
- **Durre et al.** (2010, *Journal of Applied Meteorology and Climatology* 49, 1615-1633, table 3), GHCN-Daily: a daily
  TMAX or TMIN at least 25 K above or below both the day before and the day after is a spike or dip. The code flags
  *more than* 25 K, so a change of exactly 25.0 K is no spike.
- **WMO-No. 100** (2018, 3.3.6) says that a drop of 10 K in an hour "may be suspect, but could be quite realistic if
  associated with the passage of a cold front or onset of a sea breeze": the reason for two limits, a low one for a
  spike and a high one for a step.
- **Own data**: the pressure, below.

Where no source publishes a limit, the table says "own derivation" and why: the limits at **10 minutes** are those of the
hour (a change in 10 minutes cannot be larger than the weather's in an hour, so the hourly limit is the more lenient
there); the hourly dew point is judged like the air (ISD applies its test to both but gives no limit for the dew point, MADIS has one limit for both); a daily mean is judged
like the daily extremes it lies between; and the **pressure** is 60 hPa an hour for the step and for the spike, which
lies between the 43 hPa an hour of Hurricane Irma at Saint-Barthélemy (2017-09-06: 936.0, 917.4, 960.4 hPa in three
hours, a good reading, which `elevation` keeps too) and the 64 hPa an hour of the smallest of the 19 keying slips found in
DWD's hourly station pressure. DMI's 5 to 8 hPa and MADIS's 15 hPa would flag that hurricane
([below](#what-step-does-not-judge)).

<!-- rate-of-change:start -->

| parameters | resolution | spike | step | unit | source |
| --- | --- | --- | --- | --- | --- |
| `pressure_air_sea_level`, `pressure_air_sea_level_mean`, `pressure_air_site`, `pressure_air_site_mean` | 10_minutes | 60 | 60 | hPa | own derivation: the limits of the hour, which a change in 10 minutes cannot exceed by the weather (Zahumenský's step limits are for 1-minute data and the strictest tolerance, and are not used) |
| `pressure_air_sea_level`, `pressure_air_sea_level_mean`, `pressure_air_site`, `pressure_air_site_mean` | hourly | 60 | 60 | hPa | own derivation from data: 60 hPa, between 43 hPa an hour of Hurricane Irma at Saint-Barthélemy (2017-09-06; the minimum of 917.4 hPa is 18.6 hPa below the hour before) and 64 hPa an hour of the smallest of the 19 keying slips found in DWD's hourly station pressure; the limits of the sources would flag that hurricane (DMI: a change of 5 hPa (May to August) to 8 hPa (October to March) in an hour is a certain error; MADIS: 15 hPa questioned) |
| `temperature_air_2m`, `temperature_air_max_2m`, `temperature_air_mean_2m`, `temperature_air_min_2m` | daily | 25 | - | °C | Durre et al. 2010 (table 3): a daily TMAX or TMIN at least 25 K above or below both the day before and the day after (here: more than 25 K); own derivation for the daily mean, which is smoother than an extreme: the same limit |
| `temperature_air`, `temperature_air_2m`, `temperature_air_mean_2m` | hourly | 8 | 20 | °C | ISD (Lott 2004, section 4): a rise of 8 K in an hour that falls back by 8 K is a spike (here: more than 8 K); MADIS (temporal consistency): 35 F (19.4 K) in an hour |
| `temperature_air`, `temperature_air_2m`, `temperature_air_mean_2m`, `temperature_dew_point`, `temperature_dew_point_2m`, `temperature_dew_point_mean_2m` | 10_minutes | 8 | 20 | °C | own derivation: the limits of the hour, which a change in 10 minutes cannot exceed by the weather (Zahumenský's step limits are for 1-minute data and the strictest tolerance, and are not used) |
| `temperature_dew_point`, `temperature_dew_point_2m`, `temperature_dew_point_mean_2m` | hourly | 8 | 20 | °C | own derivation for the spike: the temperature's 8 K (ISD applies its continuity test to the dew point as well but gives no limit for it); MADIS (temporal consistency) for the step: 35 F (19.4 K) in an hour, for the dew point as for the air |
| `temperature_dew_point`, `temperature_dew_point_2m`, `temperature_dew_point_mean_2m` | daily | 25 | - | °C | own derivation: the spike of Durre et al. 2010 (table 3), 25 K for a daily TMAX or TMIN, applied to the daily dew point |
| `wind_speed`, `wind_speed_mean`, `wind_speed_mean_last_10min`, `wind_speed_mean_last_2min` | 10_minutes | 10 | 15 | m/s | own derivation: the limits of the hour, which a change in 10 minutes cannot exceed by the weather (Zahumenský's step limits are for 1-minute data and the strictest tolerance, and are not used) |
| `wind_speed`, `wind_speed_mean`, `wind_speed_mean_last_10min`, `wind_speed_mean_last_2min` | hourly | 10 | 15 | m/s | MADIS (temporal consistency): 20 kt (10.3 m/s) of the wind speed in an hour; DMI (Vejen et al. 2002, table 3.1): a change of 15 m/s in an hour is a certain error |

<!-- rate-of-change:end -->

`-` means that the source gives no limit for that kind of jump and none is judged: no source gives a step for the daily
temperature (a front is a real step of a day), and a spike of 25 K between two days is what GHCN-Daily flags.

**The time between readings.** A limit is for the time between two consecutive readings of the resolution of the dataset
(10 minutes, an hour, a day). A pair or a triple of readings is judged when each interval between them is **no longer
than that step**, which is the case in a series of the resolution. A null or a missing row between two readings leaves
them two steps apart, and the check **stands aside**, as ISD's and DNMI's checks do where the series has no good
coverage; the limit is not scaled up for the longer time. A reading that is *closer* to its neighbour than one step (an
irregular series: a METAR between two hourly ones) is judged with the limit of the step, which is the more lenient for
it.

**What a neighbour is.** A reading that **any other check judged bad, soft or hard** (`range`, `elevation`, `limits`,
`source`, `stuck`, `consistency`: the verdicts are made first and `step` runs last, whatever their modes) or that the
source wrote as a code (`raw:-999`) is no neighbour and is not judged: it would flag the good reading beside it. A
thermometer stuck at -40 °C for 30 hours is `stuck`'s, and the 5.0 that follows it is no step of 45 K; GHCN hourly 5, 5,
40, 41, 5, 5 with 40 and 41 flagged erroneous by the source is the same. The reading next to such a one has no
neighbour on that side, and is judged against the one on the other side only (the first reading of a stuck run is
`stuck`'s too, so the jump into the run is not told as a step).

**The first and the last reading.** The first reading of a series has no predecessor: it is never flagged, and the second
is flagged for a step if the jump is there (a bad first reading flags the good second one). The last reading has no
successor, so it can be a step but not a spike. This is the window-edge caveat of `stuck`, and the series is the one
the reader hands the core, **before** the window of the request is cut ([the caveats](#caveats)).

### What `step` does not judge

Where no source gives a limit, or the limit that a source gives flags good readings, the check stands aside. The numbers
are what the check would flag with the limit, in the whole histories of the 10 DWD stations of
[below](#what-step-found-in-real-data) (read on 2026-11-05, no other check applied to them):

| parameter | limit measured | readings flagged | of | what they are |
| --- | --- | --- | --- | --- |
| relative humidity | spike 30 %, step 50 % (DNMI, MADIS), hourly | 1,463 | 6.3 million | 1,319 at the Zugspitze and the Feldberg: fog and cloud take the humidity from 100 to 40 % and back in an hour |
| gusts | step 15 m/s (the research's own derivation), hourly | 376 | 2.3 million | thunderstorm gusts: 3.0, 27.0, 20.0, 10.0 m/s in four hours (Dresden, 2001-07-07) |
| soil temperature at 5 cm | step 3 K (MADIS 2.8 K), hourly | 17,690 | 2.1 million | the sun on bare soil |
| air temperature | one-sided step 8 K instead of the spike, hourly | 300 | 6.3 million | fronts: 33.8 to 24.3 °C at Berlin-Tempelhof, 2022-07-25 (the table's 7 are spikes) |
| pressure | spike 5 hPa, step 60 hPa (DMI), hourly | 811 | 6.8 million | 52 are the table's; the rest are single readings 5 to 60 hPa off their neighbours (1018.9, 1008.0, 1019.3 hPa), and a hurricane's minimum |

- **Relative humidity.** The limits that exist are DNMI's dip test of 30 % (not in operation, it flags nothing) and
  MADIS's 50 % an hour. Measured, they flag 1,463 of 6.3 million hourly readings of these stations, 1,319 of them at
  the two summits, where a station is in cloud one hour and out of it the next. That rate of false alarms is the
  reason it is not judged, and the only one.
- **Gusts.** Nothing publishes a limit for them; the research derived 15 m/s, and a thunderstorm gust is a real step.
- **Soil temperature.** The limit that exists is MADIS's 2.8 K an hour (Zahumenský's 1 K is for 1-minute data).
  Measured, a step of 3 K flags 17,690 of 2.1 million hourly readings at 5 cm, which is bare soil in the sun: the false
  alarms are the reason it is not judged.
- **The pressure is the one parameter where a source's limit is not taken.** DMI calls a change of 5 hPa (May to August)
  to 8 hPa (October to March) in an hour a certain error, and MADIS questions 15 hPa. Hurricane Irma at Saint-Barthélemy
  (2017-09-06, quality code 1) read 977.1, 936.0, 917.4, 960.4 hPa in four hours: its minimum is 18.6 hPa below the hour
  before and 43.0 below the one after, a good reading that any of those limits flags, and which `elevation` keeps for the
  same reason. The table takes 60 hPa for the spike and for the step: above the 43 hPa an hour of the hurricane, below the
  64 hPa an hour of the smallest of the 19 keying slips in DWD's hourly pressure, which it finds ([below](#how-step-relates-to-elevation-and-range)).
  What 60 hPa leaves are single readings 5 to 60 hPa off their neighbours: 759 of the 811 that 5 hPa
  flags, in 6.8 million readings, which look like typing slips. Choosing 5 hPa is a one-line change of the table, and
  would flag a tropical cyclone's eye at hourly resolution.
- **A jump of the extremes of an interval, amounts, directions.** The extremes of an interval (the highest air
  temperature of an hour) are not what the limits are for. The amounts and the sums of an interval (rain, sunshine, new
  snow, a radiation sum) jump from 0 and back, and no Nordic service tests them for a step; **radiation** has no source
  for a limit either. **Wind direction** is circular (350 degrees to 10 is a change of 20). Cloud cover and weather codes
  are steps of a scale.
- **Any resolution but 10 minutes, hourly and daily** (1, 5, 6 and 15 minutes, 6 hours, subdaily reports, months, years):
  no source gives a limit for them, and the road's 15 minutes are a provider's. **Forecasts** (a model writes no
  readings) and **derived quantities**.

### How `step` relates to `elevation` and `range`

`range` and `elevation` judge a reading by itself and stay as they are; `step` judges it beside its neighbours, and
treats a reading either of them (or any other check) has found as no neighbour. The 19 readings of DWD's hourly station pressure that lie
beyond 75 hPa of the standard atmosphere were the research's start of this check: `elevation` rejects 16 of them, and the
other three (909.5 hPa at Berlin-Tempelhof, 1994-08-29, and 910.1 and 908.5 hPa at List auf Sylt, 1990-09-18 and
1992-10-22, 98 to 102 hPa below the standard atmosphere) are spikes of about 100 hPa, which `step` flags
(`suspect:step`).

### What `step` found in real data

Read on 2026-11-05 from DWD's open data (historical and recent files merged, whole histories, 10 stations for each
resolution: Dresden-Klotzsche, Hamburg, Potsdam, Zugspitze, Helgoland, Arkona, Feldberg, Berlin-Tempelhof, Straubing,
Trier-Petrisberg), with the check as it ships, soft. The readings that are looked at are those that have a value; the
check needs a neighbour one step away, which nearly all have (the hourly `moisture` of the earlier decades is 3-hourly,
and 88 % of it is judged).

| resolution | parameter (dataset) | readings | flagged | what they are |
| --- | --- | --- | --- | --- |
| hourly | air temperature (`temperature_air`) | 6,299,464 | 7 | 2.8 °C between 20.6 and 22.0 (Hamburg, 1950), 8.0 between 17.1 and 19.4 (1960), 15.4 between 5.6 and 4.8 (1975), 0.0 between 11.9 and 12.2 (1997), a sign: 6.5 between -6.6 and -5.7 (Feldberg, 1995), 5.5 between -5.0 and -6.3 (Potsdam, 1936), 5.4 between -5.4 and -5.6 (Zugspitze, 1957) |
| hourly | air temperature (`moisture`) | 4,505,940 | 380 | 184 are 0.0 between other values, 351 are before 1995, 110 at the Zugspitze and the Feldberg: the old whole-degree decades |
| hourly | dew point (`moisture`) | 4,501,767 | 1,120 | 316 are 0.0 between other values, 612 at the Zugspitze and the Feldberg (the dubious ones) |
| hourly | station pressure (`moisture`, `pressure`) | 4,505,876 | 38 | single readings about 100 hPa off their neighbours (33), 1989 to 2001; the three that `elevation` lets through are among them |
| hourly | sea level pressure (`pressure`) | 3,539,284 | 14 | the same: 10 of 14 differ by a multiple of 10 hPa, 8 at Trier-Petrisberg |
| hourly | mean wind speed (`wind`) | 5,841,991 | 167 | 141 at the Zugspitze (the dubious ones), 159 before 1995 |
| 10 minutes | air temperature (`temperature_air`) | 16,287,927 | 220 | the Zugspitze's thermometer alternating between -20.2 and 15.1 °C on 2001-05-31 and 06-01 (89), Arkona down to -85.2 °C in September 1993 (26), 52 are 0.0 |
| 10 minutes | dew point (`temperature_air`) | 15,470,459 | 510 | 359 at the Zugspitze and the Feldberg (the dubious ones), 97 in 2001 |
| 10 minutes | station pressure (`temperature_air`) | 16,263,915 | 8 | 100 hPa off their neighbours (7), 1991 to 1997 |
| 10 minutes | mean wind speed (`wind`) | 16,183,841 | 37 | 14 at the summits, 17 at Helgoland |
| daily | air temperature mean, minimum, maximum (`climate_summary`) | 964,596 | 0 | |

The daily temperature has no reading flagged: GHCN-Daily's 25 K is a spike no station of these ten has made. The
readings flagged are, by what they look like: a **0.0** between other values, which DWD wrote for a missing value in the
whole-degree decades of the hourly `moisture` (184 of the 380 temperatures, 316 of the 1,120 dew points); a **sign or a
digit** that is wrong (5.5 °C between -5.0 and -6.3, 15.4 between 5.6 and 4.8; 33 of the 38 site pressures differ from
their neighbours by a multiple of 10 hPa, within 1.5); a **sensor that fails**: the Zugspitze's thermometer alternated between -20.2 and 15.1 °C for 89 readings on
2001-05-31 and 06-01, and Arkona's wrote values down to -85.2 °C in September 1993 (26 readings). Neither `range` (-90 to
60 °C) nor `stuck` finds them. The cases that are **probably good**, the known false positives, are two: the hourly mean
**wind speed of the Zugspitze** (141 of the 167, in storms, 38.5 m/s one hour and 7.8 the next in November 1983), and the
**dew point of the two summit stations** (612 of the 1,120, a value derived from the temperature and the humidity in cold
dry air that swings 8 K and back); the rest of the wind and dew point flags are at lowland stations and are mostly
errors (a dew point of 0.0 or -59 between values of 10).

## The relations of one row (`relations`)

Two readings of one station at one timestamp can contradict each other though each is plausible alone: a daily mean
wind of 4.9 m/s beside a gust of 4.8 m/s, a dew point 40 K above the air. The check `relations` holds the
readings of **one row** (the same station, the same timestamp, the same file: a dataset the provider collects whole) to
the relations of the table below, and the sunshine of a day to the length of the day at the station (the
sources are in the table). It judges every observation network that has two parameters of
the table in one dataset, in both modes: **soft** by default, **hard** nulls both readings of a broken pair.

**Both readings of a broken pair are flagged** (Durre et al. flag every value of an inconsistency, and MADIS flags both
of a dew point above the air): nothing says which of the two is wrong. For a
triple of a maximum, a mean and a minimum the flagged readings are those of the **broken pair** and no more: a maximum
below the mean flags the maximum and the mean, and not the minimum. Where the mean is no reading to judge (null, a
code, or judged bad by another check) the maximum and the minimum are held to each other. The sunshine of a day has no
partner reading, and that one reading is flagged.

<!-- relations:start -->

| quantity | parameters, highest first (the first of a rung that the dataset has) | tolerance | source |
| --- | --- | --- | --- |
| air temperature (2 m) | `temperature_air_max_2m`, `temperature_air_mean_2m` or `temperature_air_mean_minmax_2m`, `temperature_air_min_2m` | none | WMO-No. 100 (3.3.6), Durre et al. 2010, ECA&D, Vejen et al. 2002 (3.2.1 to 3.2.3): a maximum is not below the mean, nor the mean below the minimum (not for the daily temperatures of Météo-France, nor the daily mean of FMI: [below](#what-relations-does-not-judge)) |
| air temperature (5 cm) | `temperature_air_max_0_05m`, `temperature_air_mean_0_05m`, `temperature_air_min_0_05m` | none | the same, for the thermometer at 5 cm |
| relative humidity | `humidity_relative_max`, `humidity_relative_mean`, `humidity_relative_min` | none | WMO-No. 100 (3.3.6): a maximum is not below a minimum, and the mean of the same period lies between |
| pressure (site) | `pressure_air_site_max`, `pressure_air_site_mean`, `pressure_air_site_min` | none | the same |
| pressure (sea level) | `pressure_air_sea_level_max`, `pressure_air_sea_level_mean`, `pressure_air_sea_level_min` | none | the same |
| wind speed (interval) | `wind_gust_max`, `wind_speed_mean` | none | Zahumenský 2004 (II.c): a gust is not below the wind speed, of the same period (the gust of the resolution's interval beside its mean) |
| wind speed (10 minutes) | `wind_gust_max_last_10min`, `wind_speed_mean_last_10min` | none | the same, where the names say that both are of the last ten minutes |
| wind speed (highest rolling mean) | `wind_speed_rolling_mean_max`, `wind_speed_mean` | none | own derivation: the highest mean of ten minutes in an interval is not below the mean of the interval |
| wind speed (lowest rolling mean) | `wind_speed_rolling_mean_max`, `wind_speed_min` | none | own derivation: the highest mean of ten minutes in an interval is not below the lowest |
| dew point | `temperature_air_2m` and `temperature_dew_point_2m`; `temperature_air_mean_2m` and `temperature_dew_point_mean_2m`; `temperature_air` and `temperature_dew_point` | 0.2 K | WMO-No. 8 (Vol. V, real-time quality control), Zahumenský 2004 (II.c), HadISD (Dunn et al. 2012, test 11) and MADIS: the dew point is not above the air temperature; Vejen et al. 2002 (3.2.1): a tolerance of gamma = 0.2 K recommended, which the table takes |
| sunshine | `sunshine_duration`: at most the longest day length of the date (the day, the day before and the day after) at the station's position and elevation | the day length +5 % | WMO-No. 100 (3.3.6): sunshine is limited by the length of the day; ECA&D: below the maximum day length for the day of the year and the latitude, plus 5 % (the margin of the table of ranges, D5) |

<!-- relations:end -->

Every relation holds with **no tolerance** but two: the dew point may exceed the air by 0.2 K, and the sunshine of a
day may exceed the day length by 5 %. Numbers are compared after rounding to six decimals, so that 8.0 K is not
8.000000000000002. Rounding in the source cannot break an order: a rounding is monotone, so a mean that is not above the
maximum before rounding is not above it after, whatever step the source writes in (whole degrees, tenths).

**The day length** is the time the centre of the sun is higher than -0.833 degrees (the disc and the refraction),
lowered at a station above sea level by the dip of its horizon (1.76 minutes of arc times the root of its elevation in
metres: 1.6 degrees at the Zugspitze, 2,962 m, which makes a December day about 20 minutes longer than at its foot).
The sun is the one of the road rule of `consistency` (the low-precision formulas of the Astronomical Almanac, within
0.01 degrees: `wetterdienst.model.sun`). It is the **longest of three days**, the date of the reading and the day before
and after, because the date of a source's clock is not always UTC's and, near the polar circles, the day grows or
shrinks by an hour or more in a day: 0 in the polar night, 24 in the polar day, and a reading is never held to a day
that the date, read one day off, made too short. A station with no position, or the 0, 0 of a list that has none, has
no day length, and its sunshine is not judged.

### How `relations` differs from `consistency`

Both hold two readings of one file to each other, and they are two checks with two modes, so that a reader can choose:

| | `consistency` | `relations` |
| --- | --- | --- |
| rules | **a provider's own**, for its source: DWD road (a road surface far above the air at night), Météo-France (a humidity beside a dew point below frost at a station without frost, a `tn12` that copies `tx12`) | **one table for every provider** ([above](#the-relations-of-one-row-relations)): orders that hold by definition (maximum, mean, minimum), the dew point, the gust, the day |
| flagged | the one reading the rule names (the surface, the humidity) | **both** readings of the pair (the one sunshine of a day) |
| default | **hard** (what the library did before the modes existed): the value is null, `rejected:consistency,raw:<text>` | **soft**: the value is kept, `suspect:relations` |
| set with | `plausibility_consistency`, `--plausibility-consistency`, `WD_TS_PLAUSIBILITY__CONSISTENCY`, `Options(plausibility={"consistency": ...})` | `plausibility_relations`, `--plausibility-relations`, `WD_TS_PLAUSIBILITY__RELATIONS`, `Options(plausibility={"relations": ...})` |

To null the road surface a rule of `consistency` rejects, set `consistency`; to null both readings of a maximum below the
mean, set `relations`. The bare `plausibility="hard"` (or `"soft"`) sets both, as it sets every check, and a check named
beside it wins. Neither check changes what the other does: `plausibility_relations=hard` leaves `consistency` hard and
`plausibility_consistency=soft` leaves `relations` soft, and each writes its own token. A reading that `consistency`
has judged bad, soft or hard, is no partner of a relation (as is none that `range`, `elevation`, `stuck`, `source` or
`limits` judged bad, or that the source wrote as a code): the relation stands aside for it.

### What `relations` does not judge

Where a relation does not hold by the source's own definition, or no relation of the table has both parameters in one
file, the check stands aside. The numbers are from the whole histories of 10 DWD stations (below).

- **A total equal to the sum of its parts** (an hourly or daily amount against its parts in one file) is not built: it
  is the optional relation of the research, and only where a source documents it.
- **A relation across two files.** A check never triggers a download. DWD observation holds the hourly air temperature
  and moisture, wind and wind extremes in different datasets: the hourly gust of `wind_extreme` is not held to the mean
  of `wind`, nor the 10-minute extremes of `temperature_extreme` to the mean of `temperature_air`. A dataset that a
  provider collects a parameter at a time (**SMHI, WSV, the Environment Agency, Hub'Eau, IMGW's hydrology**) has no
  second parameter in the frame, and nothing is judged there.
- **A gust held to the highest rolling mean of ten minutes**, though the gust of an interval is above every mean in it.
  DWD's 10-minute `wind_extreme` has both (`FX_10` and `FMX_10`), and the order fails in **137,356 of 9.8 million**
  readings (1.4 %): by more than 0.1 m/s in 81,308, 0.5 in 11,709, 1 in 2,371, 2 in 348 and 5 m/s in 8 (a gust of 0.0 at the
  Zugspitze beside a mean of 11.5). The rolling mean is a window that begins before the interval does, so by the
  source's own definition the two are not of one period. That is the false alarm of the relation, and it is not built.
  The same dataset's highest and lowest rolling mean are held to each other (5 broken of 9.8 million).
- **A gust and a mean of different windows**: an hourly gust (`wind_gust_max`) beside a mean of ten minutes
  (`wind_speed_mean_last_10min`, AEMET), a gust of ten minutes beside a mean of two (NWS), or `wind_speed`, which no source
  says is a mean. The table pairs only what the names pair.
- **The instantaneous air temperature** (`temperature_air_2m` of an hour) beside an hourly maximum and minimum: a
  thermometer read at the end of the hour is a sample, not an average, and the sensor's own maximum need not reach it.
  The extremes of `_last_12h`, `_last_24h` and `_yesterday` (DWD POI, DMI, Météo-France SYNOP) are of another window than
  the report beside them.
- **The daily mean against the extremes where the source's windows differ.** Météo-France's `TM` is the "moyenne
  quotidienne des températures horaires" and the description of the fields gives no window for `TN` and `TX` (it gives
  one for the rain only, 06h to 06h), so nothing says that they are the hours of the mean's day: at Bordeaux-Mérignac
  (33281001) on 2023-12-01 `TX` is 9.3, `TM` 8.3 and `TN` 8.5, all three good (`TN` is the lowest value from 18 UTC of the
  evening before to 18 UTC; the hourly series falls to 5.8 °C by 23 UTC). In the 36 stations still reporting, 2019 to
  2025: `TM` below `TN` on 6 of 17,565 days, above `TX` on 2 of 17,563 (a reviewer counted 9 of 32,646 at 7 stations),
  and `TX` against `TN` holds on 20,312 days but no window is given that makes it hold, so the whole daily temperature
  ladder of `meteofrance/observation daily` is left out (its hourly `TX` and `TN` are "within the hour" and stay, its
  gust against the mean wind stays: 0 of 5,555). FMI's `tday` is "mean over 1 day" (aggregation period P1D) and
  `tmax`, `tmin` are over "24 hours" (PT24H): the mean is left out (3 days of 65,316 have it above the minimum) and the
  maximum against the minimum, both PT24H, stays. DMI defines the mean and the minimum over the same hours, and keeps its
  pair (14 broken days of 7,138, one station). `NOT_ONE_WINDOW` in `wetterdienst.model.relations` lists the exceptions.
- **A month and a year**, whose extremes and means are made from the days by the source's own rule; **1, 5 and 15 minutes
  and the other resolutions** have a pair only where a dataset holds one: the check judges the resolutions up to a day
  (`1_minute` to `daily`, and `subdaily` reports). **Forecasts and derived quantities** (a model writes no readings).
- **Sunshine under a cloudless sky** (radiation against sunshine), which Zahumenský's draft judges for periods of up to 10
  minutes only, and cloud cover against precipitation or sunshine: no source gives a limit that holds at the resolutions
  of the networks.

### What `relations` found in real data

Read on 2026-11-05 from DWD's open data (historical and recent files merged, whole histories, 10 stations for each
resolution: Dresden-Klotzsche, Hamburg, Potsdam, Zugspitze, Helgoland, Arkona, Feldberg, Berlin-Tempelhof, Straubing,
Trier-Petrisberg), with the check as it ships. "Judged" are the pairs (or sunshine readings) that have both values and
that no other check found bad; "broken" are the pairs the check flags (twice that many readings).

| resolution | relation (dataset) | judged | broken | what they are |
| --- | --- | --- | --- | --- |
| daily | maximum, mean, minimum of the air temperature (`climate_summary`) | 321,379 / 321,375 | 0 / 0 | DWD's daily extremes and mean are made from one day's readings, whichever window each uses: no order is broken, in tenths or in whole degrees |
| daily | gust, mean wind (`climate_summary`) | 208,959 | 2 | the Zugspitze, 1994-08-10 (a mean of 10.3 m/s beside a gust of 8.7) and Dresden-Klotzsche, 1994-05-01 (4.9 beside 4.8), both with quality level 3: real inconsistencies of the daily wind, which `range` cannot see |
| daily | sunshine, the day (`climate_summary`, `solar`) | 306,534; 94,005 | 1; 0 | the Zugspitze, 1919-11-04: 11.0 hours of sunshine on a day of 10.28 hours at the summit (limit 10.8). **Without the dip of the horizon** the day lengths of the plain would put 638 readings above the day, 85 above it by 2 % and 6 by 5 % (5 at the Zugspitze, 1 at the Feldberg), which the summits' lower horizon explains; with it 27, 5 and 1 |
| hourly | dew point, air (`dew_point`) | 4,513,204 | 398 | 354 at the Zugspitze (143), the Feldberg (153) and Trier-Petrisberg (58), 1940s to 2000; 116 by more than 5 K (an air of -30.0 beside a dew point of 32.0, Trier 1964; -23.0 and 25.0, the Zugspitze 1970: a sign or a digit), 80 by 1 to 5 K, 174 by 0.5 to 1 K (169 by exactly 1.0 K, 166 of them before 1981, in whole degrees: an air of 1 beside a dew point of 2), 28 by 0.2 to 0.5 K |
| hourly | dew point, air (`moisture`) | 4,501,288 | 0 | the dew point there is derived from the temperature and the humidity |
| hourly | sunshine, the day (`sun`) | 4,905,458 | 0 | (hourly sunshine is held to the day, which only the polar night can break) |
| 10 minutes | dew point, air (`temperature_air`) | 15,470,302 | 925 | **912 of the 928 broken by more than 0.2 K are at a relative humidity of 100 %** (Arkona 727 in 1991 to 2005, Potsdam 190 in 1993): the dew point of a saturated hygrometer, which reads 0.2 to 1.0 K above the thermometer beside it; 617 are by 0.2 to 0.5 K, 243 by 0.5 to 1 K, 59 by 1 to 5 K, 9 by more than 5 (a dew point of 72.8 °C beside 24.4 at Dresden, 1992-05-21, with the humidity missing) |
| 10 minutes | maximum, minimum of the air at 2 m (`temperature_extreme`) | 16,286,918 | 42 | the Helgoland maximum below its minimum for 26 readings on 2008-12-01 (4.2 below 5.0, up to 0.8 K), Straubing 14 on 2010-11-17 (0.2 K), one each at Trier and the Zugspitze |
| 10 minutes | maximum, minimum at 5 cm (`temperature_extreme`) | 5,388,500 | 1 | Arkona |
| 10 minutes | highest and lowest rolling mean wind (`wind_extreme`) | 9,821,075 | 5 | Berlin-Tempelhof 2, Helgoland 3 |
| 10 minutes | sunshine, the day (`solar`) | 15,906,485 | 0 | |

The false alarms the data show are one class: **the dew point of a saturated reading.** At a relative humidity of 100 %
the dew point is the temperature of the hygrometer, and a thermometer beside it that reads 0.3 K lower is no mistake
of either: 617 pairs of 15.5 million at 10 minutes, all by less than 0.5 K, flagged at a tolerance of 0.2 K and not at
0.5 K. The tolerance of 0.2 K is Vejen et al.'s (the Nordic report recommends it), the sources that name none take 0;
raising it to 0.5 K would leave 311 of the 928 pairs, a choice of the table that this page states and a test pins. In
the whole-degree decades of the hourly `dew_point` a dew point cannot exceed the air by a rounding, because a rounding is
monotone: the 166 readings 1.0 K above before 1981 are two instruments that differ, and **flagging both** costs a good
air temperature its `suspect:relations` and its place in an interpolation.

Other key-less networks (a random sample of up to 40 stations that are still reporting, daily 2019 to 2023 unless
stated; each pair is judged at the days that have both values):

| network, resolution | relation | judged | broken | what they are |
| --- | --- | --- | --- | --- |
| Météo-France `daily/core`, 36 stations, 2019 to 2025 | TX against TM; TM against TN; TX against TN (where TM is null); gust against mean wind | 17,563; 17,565; 2,749; 5,555 | 2; 6; 0; 0 | **not judged** since the windows differ (below): at Bordeaux-Mérignac (33281001), 2023-12-01, TX 9.3, TM 8.3, TN 8.5 (a reviewer found 9 days in 32,646 at 7 stations) |
| Météo-France `hourly/core`, 30 stations, September 2025 | TX against TN of the hour | 10,454 | 0 | |
| Météo-France SYNOP, 40 stations, 2023 to October 2025 | dew point against air; gust against mean of ten minutes | 126,344; 87,708 | 0; 0 | |
| NWS, 40 stations, one week | dew point against air | 3,841 | 0 | |
| FMI `daily/data`, 40 stations, 2010 to 2023 | TX against TM; TM against TN | 65,317; 65,316 | 0; 3 | **not judged** (the mean is of P1D, the extremes of PT24H, below): 3 days of 0.1 K |
| DMI `daily/data`, 40 stations | TX against TM; **TM against TN**; humidity and sea level pressure triples; gust and highest rolling mean against mean wind | 7,138; 7,138; 3,523 and 3,556; 6,647 and 6,651 | 0; **14**; 0; 0 | the 14 are one station, Vestervig (06051): a mean up to 2.2 K below the lowest hourly value of the day, which the source defines as the mean and the minimum of the same hours (kept, a real inconsistency) |
| MeteoSwiss `daily/data`, 40 stations | triple at 2 m and 5 cm; gust against mean; sunshine | 67,438; 36,443; 69,170; 51,333 | 0 | |
| Geosphere `daily/data`, 18 stations | max, (max + min) / 2, min; gust against mean; sunshine | 18,161; 18,140; 15,209 | 0; **13**; 0 | the 13 are one station (15300): a gust 0.2 to 0.3 m/s below the daily mean wind |
| CHMI, RMI, IMGW `synop` daily | triple; sunshine | 3,652 and 3,651; 23,712 and 21,305; 5,478 | 0 | |

Also 0 broken in the first look at 2023 (two stations each): Geosphere hourly (17,474 of the gust and the mean, and of the
sunshine) and 10 minutes (8,354), RMI hourly (17,466 of the sunshine), FMI at Sodankylä hourly (8,734 of the gust and the
mean of ten minutes, 8,737 of the dew point), MeteoSwiss hourly (8,737 of the extremes and the mean, at 2 m and 5 cm, of the
gust, of the dew point; 17,474 of the sunshine), ECCC hourly (8,731 dew points), DMI hourly (697), GHCN-Daily 2018 to 2023
(62,144 days of TMAX against TMIN at six ASOS stations, 40 cooperative stations whose observers read at different hours
and three European ones; 13,101 days of the humidity extremes and the mean at the ASOS stations), DWD POI (100 dew points,
25 sunshine readings of one day), and DWD road, one day (3,750 dew points against the air, 7 of them broken: station O329
holds a dew point of 2.3 beside an air of 1.6). **Not measured**: the keyed providers (KNMI, MET Norway, Met Office, AEMET),
IMGW `climate` (no rows came back for the stations asked), GHCN-Daily's mean air against mean dew point (no station of
the sample reports both: it is in the table and unmeasured there), and a sunshine duration at a polar station (no
key-less one reports it), for which the tests of the polar night and day stand (Tromsø).

### How `relations` relates to `step`

`relations` runs **before** `step`, which treats a reading any other check found bad as no neighbour. A reading
`relations` flagged is therefore no neighbour of a jump either, whatever mode it is in: the check does not judge it, and it
can hide a real spike beside it and **move the flag to a good reading**. A good air temperature flagged beside a wrong
maximum, then a real jump of 35 K, then the old level (an hourly series 10, 10, 10, 45, 10 with a maximum of 5 beside the
third): the third mean is flagged `suspect:relations`, the 45 has no neighbour one step before it and is not judged, and
the 10 after it is flagged `suspect:step` as the step from the 45. This follows from the rule, is kept (it is the same
rule that `stuck`, `source` and the others follow) and is pinned by a test.

### The effect on `step`

`relations` runs before `step`, so the readings it flags leave the series `step` judges (above). On the DWD data of the
table, with the code as it ships and as it was before: the hourly `dew_point` has 991 flags of `step` before and **944
after** (47 lost, every one at a reading that is now `suspect:relations`, 796 of them: 398 pairs), the 10-minute
`temperature_air` 738 before and **732** after (6 lost: 4 at readings that are now `relations`, and the air and the dew
point of Arkona, 1993-09-11 11:50, whose neighbour was flagged by the relation); the daily and the hourly `moisture`
data are unchanged. **No flag of `step` was gained**: no spike was hidden so that its flag moved to the good reading
after it, in the 10 stations' histories. Where a *good* reading is flagged by a relation (a sound air temperature
beside a wrong dew point) a spike beside it can move its flag, as the line above says, and the test pins it.

## The table of ranges

The `range` check has **one table for every provider**. A quantity has the bound of the quantity and not of the network
that serves it: DMI's rain, DWD's station pressure and RMI's gusts and sunshine were once held to bounds of their own, and
are held to the table now. Every network is judged against it, wherever its parameters have a bound. A bound is the first
of these that exists, rounded outward to a round number (31.2 is 40, 1,144 is 1,150, 1,825 is 1,850, 26,470 is 30,000; the irradiance of
2,000 W/m² lies between the 1,600 of WMO-No. 488 and the 2,141 of BSRN), so that it finds a value that is a defect of the source and never a
record:

1. the extreme the WMO World Weather and Climate Extremes Archive lists
   ([table of 31 July 2025](https://public.wmo.int/sites/default/files/2025-07/Table_Records_25Jul2025.pdf));
2. a limit that follows from the definition of the quantity (a share is 0 to 100 %, a duration is not longer than its
   span, a count of days is not more than the days there are);
3. a named source, cited beside the bound.

A quantity that has neither a record nor a definition that bounds it above is held to its definition alone: at least 0,
and no upper end. The module `wetterdienst.model.plausibility_ranges` holds every bound with its source in its docstring;
the main ones are:

| quantity | bound | source |
| --- | --- | --- |
| air temperature | -90 to 60 °C | WMO: 56.7 °C (Furnace Creek, 1913), -89.2 °C (Vostok, 1983) |
| dew point | -100 to 60 °C | HadISD minimum -100.0 °C, ISD -98.2 °C; the upper end is the air's |
| pressure at sea level | 850 to 1100 hPa | WMO: 1,089.1 hPa (Tosontsengel, 2004), 870 hPa (Typhoon Tip, 1979) |
| pressure at the station | 300 to 1100 hPa | Everest 330 hPa; WMO-No. 305 (1993, withdrawn) erroneous below 300 or above 1100 hPa; the elevation check is the sharper one |
| vapour pressure | 0 to 60 hPa | the saturation pressure at 35 °C, the highest dew point on record (Dhahran, 2003) |
| wind gust and mean wind speed | 0 to 115 m/s | WMO: 113.2 m/s (Barrow Island, 1996); a mean cannot exceed the gust of its interval |
| wind direction, direction of the current | 0 to 360 degrees | definition of a bearing |
| rain in 1 minute | 0 to 40 mm | WMO: 31.2 mm (Unionville, 1956) |
| rain in 5 to 60 minutes | 0 to 350 mm | WMO: 305 mm in 60 minutes (Holt, 1947) |
| rain in up to 12 hours | 0 to 1,150 mm | WMO: 1,144 mm in 12 hours (Foc-Foc, 1966) |
| rain in up to 24 hours | 0 to 1,850 mm | WMO: 1,825 mm in 24 hours (Foc-Foc, 1966) |
| rain in a month | 0 to 10,000 mm | 9,300 mm in July 1861 (Cherrapunji; Bureau of Meteorology, a secondary source) |
| rain in a year | 0 to 30,000 mm | WMO: 26,470 mm in 12 months (Cherrapunji, 1860/61) |
| relative humidity | 1 to 100 % | 100 % by definition; 1 % is the floor of what a hygrometer reports, see [below](#relative-humidity-under-one-percent) |
| snow cover | 0 to 100 % | definition |
| vapour pressure deficit | -10 to 200 hPa | the saturation pressure at the 60 °C of the air bound, 199 hPa by Magnus; DMI writes some hours and days a little below 0 (-3 hPa at 06193, 2025-07-25), so the lower end leaves them |
| new snow in a day, in a month | 0 to 200 cm, 0 to 6,200 cm | Durre et al. 192.5 cm; a month (the sums of the daily depths, ECCC's normal snowfall) is that times 31 |
| sunshine, precipitation and leaf wetness duration | 0 to the span + 5 % (1.05 h in an hour, 25.2 h in a day) | definition, with the margin of ECA&D for the length of the day |
| short-wave irradiance | 0 to 2,000 W/m² | WMO-No. 488 holds 0 to 1,600, BSRN 2,141 at the zenith |
| a sum of short-wave radiation | 0 to 1 MJ/m² in 10 minutes, 5 in an hour, 60 in a day | the solar constant times the span, rounded outward; a day is at most 60 (the top of the atmosphere at 82 degrees north in midsummer is about 45), a month and a year are that times their days (1,860 and 22,000) |
| snow depth | -10 to 1,200 cm | ISD 1,200 cm, Durre et al. 1,146 cm; a gauge reads a few centimetres below 0 |
| water temperature | -5 to 50 °C | MADIS holds the sea surface to -2 to 40 °C |
| everything else with no record | at least 0 | definition |

Quantities that are **derived** from others (wind chill, humidex, evaporation, the net radiation of DMO and the forecast
errors `error_absolute_*`), codes and flags, and the **hydrology gauges** (stage, discharge, groundwater level, distance
to the gauge and flow speed: a datum of their own, and a tidal river runs backwards) have no bound. The direction of the current is a bearing, held to 0 to 360 degrees like the direction of the wind.

**Shangdi.** The one documented exceedance is Shangdi (Inner Mongolia, 1975-07-03): 401 mm in 60 minutes, which is in
the lists of the Bureau of Meteorology and the NWS but not in the WMO table, so the bound of an hour is 350 mm and the
reading would be null.

**The WMO guides give no fixed table.** WMO-No. 488 (Guide to the Global Observing System, Appendix VI.2) sets limits for
the 1-minute values of an automatic weather station only, and some of them cut records of the Archive (a wind speed of
75 m/s against the 95 m/s of Typhoon Nancy); the tests of WMO-No. 1269 (Guidelines on Surface Station Data Quality
Control and Quality Assurance for Climate Applications, 2021) are relative to the station (percentiles of its own last 30
years, or its climatological extremes); and the current WMO-No. 305 (Guide to the WMO Integrated Processing and
Prediction System) has no chapter on quality control, the gross limits quoted from it come from the withdrawn edition of
1993. The table is compared with these, not taken from them.

### Relative humidity under one percent

The table holds a relative humidity to **1 to 100 %**. An exact 0.0 % is what a dropout writes (DWD's urban
`10_minutes` `humidity_relative` has five of 1,837,972 readings, each a dropout between normal ones with quality level
3: 72.3 % before and null after at Dresden-Neustadt, 32.0 and 33.1 % at Berlin-Alexanderplatz, 48.0 and 48.8 % at
Regensburg-Mitte; GH-3773), a failed hygrometer writes 0.0, 0.1 or 0.4 % (DWD road, GH-3624), and the
air of Germany is never that dry; the minima of the other DWD humidity columns are 7 to 12 %. Every relative humidity is
held to it (`humidity_relative` and its `_mean`, `_max` and `_min`), at every resolution, and no other humidity: not
the absolute humidity, the vapour pressure or the dew point.

Why 1 and not the smallest number above 0, or 0.5:

- GHCNh derives its humidity from air and dew point temperature in whole percents and calls a value under 1 "out of
  range" itself ([documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf),
  Table 3, `o`). Read on 2026-11-03 (2023, the two nearest stations of Death Valley, Phoenix, Yuma, Las Vegas, Aswan,
  Tamanrasset, Alice Springs, Riyadh, Kuwait, Concordia, Atacama, Bechar, Ouargla and Turpan, 14 places): the hourly
  readings of 0 are three, two at Death Valley (USW00053139) and one at Tamanrasset (AGM00060679), of which GHCNh marks
  two itself (`o` out of range, and the legacy code `3` of source 345). There are 103 hours of exactly 1 % (Death Valley
  23, Tamanrasset 73, Atacama 5, Turpan 2), between neighbours of 0 to 4 %: a whole percent of 1 is a reading and stays.
- The lowest values the literature reports are derived from a temperature and a dew point, not read from a hygrometer:
  0.36 % at Safi-Abad Dezful (Iran, 2017-06-20, 46.5 °C and a dew point of -33.2 °C) and 0.33 % at Needles
  (California, 2014-05-04, 38.9 °C and -38 °C), per [Weather Underground](https://www.wunderground.com/cat6/world-record-low-humidity-116f-036-humidity-iran),
  which notes that humidity cannot be measured to hundredths of a percent. **A floor of 1 % would null such an hour**
  if a source wrote it as a decimal; the cost is a handful of hours the world has seen, against the dropouts of
  every network, and the readings of whole percents that GHCNh rounds to 0 are the same hours.
- The WMO World Weather and Climate Extremes Archive lists no humidity record, so this bound rests on the sources above
  (N), not on a record.

The monthly mean of a station that reads 6 % (Météo-France, Crozet, 1997-07, validated) is not a dropout of a
hygrometer and is not found by any floor that leaves the deserts alone; it stays a value, as the source published it
([special values](special_values.md)).

### What a table for the world cannot catch

A bound that holds for every provider cannot see a defect that lies inside it. These stay, as the source wrote them, or are told by another check:

- **Totals that are wrong and plausible.** DMI marks `validity:false` on a daily rain of 989 mm (04339, 2011-07-25), a
  monthly 3,229.9 mm (2012-10), a yearly 9,574.3 and 6,026.5 mm (2014, 2015) and a yearly 3,253.4 mm, all inside the
  ranges: no range separates the last from the 3,291.3 mm of a year that DMI validated at 04390. They are the business
  of [`source`](#the-sources-own-verdict-source), which reads the source's own verdict: each is kept and flagged
  `suspect:source`, and is null with `rejected:source` where you set the check hard. DMI's 1,978 mm of a day and 17,802
  mm of a month are above the bounds and are null by `range`.
- **A gust of 81.5 m/s in Belgium** (RMI, station 6414, 2003-10-09, `validated: false`): inside the 115 m/s of the
  world, and not a reading. **No check finds it**: `step` does not judge gusts ([why](#what-step-does-not-judge)), so
  it is returned as RMI writes it, and a caller who wants it gone sets a bound of their own (`limits`); the 445.3 and 569.7 m/s of the hourly layer are above the bound and are null.
- **A station pressure keyed in by a digit, between the margins of `elevation`**: 909.5, 910.1 and 908.5 hPa at DWD's
  Berlin-Tempelhof and List auf Sylt, 98 to 102 hPa under the standard atmosphere, as far as the eye of a hurricane
  (917.4 hPa at 3 m). Steps of 90 to 129 hPa in an hour, against the 43 of Irma, tell them; that is the step check, too.
- **The stopped sensors of DWD road at -75.00 °C** (station group KM): inside the -90 °C of the air record, so no
  bound finds them. They are a code of the source and the reader of DWD road maps them to null, keeping `raw:198.15`.
  The `-30.00` and `-25.00` of other stopped sensors are readings a German winter reaches, and stay with the check `stuck`.
- **A sensor stuck at a plausible value, a sunshine of 1,440 minutes on a day of December** (RMI, 6477) and other
  quantities that look like data: `stuck` and the rules of a provider, not the table.

## Bounds of your own (`limits`)

The table of ranges is generous on purpose: it finds a value that is a defect of the source and never a record (the one
exception is the 1 % floor of a relative humidity, [above](#relative-humidity-under-one-percent)). Where
you know more (a station in a valley that never reads 45 °C, a rain gauge that cannot have caught 200 mm in an hour), you
set the bounds yourself, per parameter, and the check `limits` judges every reading against them. It is a separate check
from `range`: the physical ranges are not changed, and a value outside both carries both verdicts, joined with `+` as with
any two checks (`rejected:limits+range,raw:4021`) where both are hard or both soft. Where one is hard and nulls the
value, it is the hard verdict alone (`range` hard and `limits` soft: `rejected:range,raw:4021`).

| | |
| --- | --- |
| **bounds** | `(low, high)`, both ends included in what is plausible. Either may be `None` (`null`) for no bound at that end, but not both. `low` may not exceed `high`, and a bound is a finite number: NaN and infinity are refused |
| **names** | a canonical parameter name (`temperature_air_mean_2m`), which holds in every dataset that serves it, or `resolution/dataset/parameter` (`daily/climate_summary/temperature_air_mean_2m`), which holds in that dataset only. The dataset is named as a request names it: `daily/kl/...`, the source's own names and any casing work. Where both name a parameter, the one with the dataset wins **as a whole**: its pair is used and the other pair is not combined with it |
| **unit** | the unit of the values the request returns: `unit_targets` if you ask for one (`(-22, 113)` for degrees Fahrenheit), the default unit of the quantity otherwise (a humidity is a percent, `(0, 90)`), and the unit of the source with `convert_units` off. The core converts the bounds to the canonical unit and judges the reading there, as it does for the table, before it is rounded for the answer |
| **mode** | `plausibility={"limits": ...}`: **hard** by default (`rejected:limits,raw:<number>`, the value null), **soft** keeps the value and flags it `suspect:limits`. A bare `plausibility="soft"` covers it like every check |
| **a name that is none** | an error, never ignored: a typo would be indistinguishable from having set no bound. A name that is a parameter but that your request does not read does nothing, so one set of bounds can serve requests for any network |

```python
from wetterdienst import Options
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "temperature_air_mean_2m"), ("daily", "climate_summary", "precipitation_amount")],
    start="2024-01-01",
    end="2024-01-31",
    options=Options(
        limits={"temperature_air_mean_2m": (-30, 45), "precipitation_amount": (None, 200)},
        plausibility={"limits": "soft"},  # keep what is outside, flagged `suspect:limits` (hard is the default)
    ),
)
values = request.filter_by_station_id("01048").values().all()
```

A bound in another unit, and one for a single dataset (bounds for `temperature_air_mean_2m` in the daily climate summary
alone, in degrees Fahrenheit):

```python
Options(unit_targets={"temperature": "degree_fahrenheit"}, limits={"daily/climate_summary/temperature_air_mean_2m": (-22, 113)})
```

The same on the other surfaces. A pair is `[low, high]` in JSON, with `null` for an end that is not set:

```bash
export WD_TS_LIMITS='{"temperature_air_mean_2m": [-30, 45], "precipitation_amount": [null, 200]}'
export WD_TS_PLAUSIBILITY__LIMITS=soft

wetterdienst values --provider dwd --network observation --parameters daily/kl --stations 01048 --timestamp 2024-01 \
    --limits temperature_air_mean_2m=-30:45 --limits precipitation_amount=:200 --plausibility-limits soft

curl -G "http://localhost:7890/api/v1/values" --data-urlencode "provider=dwd" --data-urlencode "network=observation" \
    --data-urlencode "parameters=daily/kl" --data-urlencode "stations=01048" --data-urlencode "timestamp=2024-01" \
    --data-urlencode 'limits={"temperature_air_mean_2m": [-30, 45], "precipitation_amount": [null, 200]}' \
    --data-urlencode "plausibility_limits=soft"
```

`--limits` is repeated for more parameters and takes either `name=low:high` (an end left empty is no bound) or a JSON
object. The bounds that a command or a request gives are merged into the ones the environment sets, the entry of the
request winning for a name both give (as the unit targets are); `WD_TS_LIMITS__<NAME>='[low, high]'` sets one name from
the environment, and a name with a dataset (it has slashes) can only be set in the JSON of `WD_TS_LIMITS`. The REST API
and the MCP tools take `limits` (JSON) and `plausibility_limits` on `values`, and `/api/settings` reports both as set.
`interpolate` and `summarize` take neither as a parameter, but read `WD_TS_LIMITS` of the server like any option, and,
like the stripes, leave out a value that is `suspect:limits`.

**A forecast follows the mode.** Unlike `range` and the other built-in checks but `floor`, `limits` is not made soft on a network whose `kind` is
`forecast` (`dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`): the bounds are yours, so a forecast value outside them is null with
`rejected:limits,raw:<number>` by default and kept, flagged `suspect:limits`, where you set `plausibility_limits` soft,
as for an observation. The `range` of the same value stays soft there and flags it `suspect:range`, and the token of a
value both find is `rejected:limits,raw:<number>` (a rejected value carries the hard checks alone).

**A value is judged as it was read.** A reading that is exactly on a bound stays, in whatever unit the bound is written
(the converted bound is given a margin of a part in a billion, the noise of a conversion). The bound is compared with
the number before it is rounded for the answer, so a 45.00004 °C beside a bound of 45 is outside it although the answer,
rounded to the decimals of its unit, may read 45.0. A reading that carries a code of the source (`raw:-999`) is the
source's meaning and is judged by nobody, as for every check. A bound that is no value of the unit it is in (a negative
Beaufort number as a speed) is the request's error, a 400 for REST, before any station's values are read.

A key is kept in one spelling where that does not change what it names: `daily/kl/tmk` is
`daily/climate_summary/temperature_air_mean_2m`, so that a bound a request gives replaces the host's for the same
parameter however either is written; of two spellings of one key the later pair wins. A key of one network's own names
(`hourly/ogd-smn/rre150h0`) stays as it is, and where it and a wider key (`hourly/data/precipitation_amount`, which
names that parameter in thirteen networks) both name a parameter, the one that names fewer wins, whatever the order
they are given in. A name that is the old name of a renamed parameter is read as the new one, with a warning.

## The source's own verdict (`source`)

Many sources mark a value as wrong in a quality flag of their own and return it all the same: a GHCN-Daily value that
failed a check, a Frost value of quality code 7, an Environment Agency reading that is `Suspect`. The check `source`
reads that verdict from `quality_flags`, where the reader has put the source's flag as the source wrote it, and applies
the mode you chose:

- **soft** (the default): the value is kept and `quality_flags` gains `suspect:source`
  (`X,measurement:T,source:0,suspect:source`). Nothing is nulled, so a default request returns the same values as
  before, with one more token on the readings the source doubts. An interpolation, a summary, climate stripes and
  `skip_empty` leave a `suspect:` value out, as they do for every soft check, so only the flagged values are left out of them, and a station can be skipped
  where it was counted. A bare `plausibility="hard"` (`WD_TS_PLAUSIBILITY=hard`,
  `plausibility=hard` of REST) sets `source` too, and nulls those values: name `source` beside it to keep them.
- **hard**: the value is null and the text the source wrote stays as `rejected:source,raw:<text>`
  (`Suspect,rejected:source,raw:0.359`), except for the milder level of a source that has two (see *Which codes count*, below):
  that stays `suspect:source` (`2,source:343,suspect:source`) and is never nulled.

It is soft by default, and the only check but `stuck` that is, because the verdict is the source's and not the
library's: it is no number outside what a sensor can produce, and a source's own scale (a code that says a value was
corrected, a value not controlled) is not for the library to read as a rejection: it is never in the map, and nulling what the source flagged is for you to ask. A forecast network is
judged soft in `source` as in every check but `floor` and `limits`; none of the forecast networks (DWD MOSMIX, DMO and
SWSMOS) has a flag of its own that marks a value, so the check judges nothing there.

**Which codes count.** One rule for every provider, and every code is the provider's own, taken from its documentation
and cited in the table below with the wording and the page: *a code is in the map where the documentation words it as
the verdict that the value failed a check, is erroneous, suspect, doubtful or of poor quality.* What the documentation
words as a degree of uncertainty (Frost's "slightly uncertain" and "very uncertain", codes 2, 4 and 5), as a treatment
(estimated, corrected, interpolated), as a missing value, or as no control at all (`Unchecked`, DMI's `qcStatus`
`none`) is no verdict and is not read. Where a source has two levels of verdict (GHCNh `Suspect` and `Erroneous`, CHMI
`Suspect` and `Poor`, MADIS `Questioned` and `Rejected/erroneous`), both are in the map, each as a *suspect level* or an *erroneous level* code in the table: `soft`
flags both as `suspect:source`, and `hard` nulls only the erroneous level, the code the source words as erroneous,
failed or poor (GHCNh `Erroneous`, CHMI `Poor`, MADIS `Rejected/erroneous`), while the suspect level (GHCNh `Suspect` and source 382 `R`, CHMI `Suspect`, MADIS `Questioned`, GHCNh `f`) stays
`suspect:source` and is never nulled. A source that has one level only (GHCN-Daily `QFLAG`, Frost 7, EA `Suspect`,
Météo-France 2, DMI `validity:false`, Hub'Eau 12, DWD road 1, MIDAS status 1) has it as the erroneous level, so `hard` nulls it. The source's own word stays in
`quality_flags` beside the token, so a code is told from the other by the flag (`3,suspect:source` against
`2,suspect:source`). A source that has no such wording is not in the map; a network has the check only where its reader
returns the flag.

The token of the check is `suspect:source` or `rejected:source`; GHCN's `source:Z` is another thing, the data source of the
value (the `SFLAG`), and sits among the source's own flags. A value that carries a `raw:` token already is a code of the source (a missing value) and is not judged. A flag that
holds a code the map does not list (a letter the documentation does not word as a verdict) is not judged either.

<!-- source:start -->

| network | datasets | flag in `quality_flags` | codes that count, as the provider words them | documentation |
| --- | --- | --- | --- | --- |
| `noaa/ghcn` | `daily/data` | the plain first token (`QFLAG`) | `D` failed duplicate check; `G` failed gap check; `I` failed internal consistency check; `K` failed streak/frequent-value check; `L` failed check on length of multiday period; `M` failed megaconsistency check; `N` failed naught check; `O` failed climatological outlier check; `R` failed lagged range check; `S` failed spatial consistency check; `T` failed temporal consistency check; `W` temperature too warm for snow; `X` failed bounds check; `Z` flagged as a result of an official Datzilla investigation | [GHCN-Daily readme.txt](https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt): "QFLAG1 is the quality flag for the first day of the month. There are fourteen possible values: Blank = did not fail any quality assurance check" |
| `noaa/ghcn` | `hourly/data` | the plain first token (`<element>_Quality_Code`), where `source:` is 313, 314, 315, 322, 335, 343, 344 or 346 | suspect level: `2` Suspect; `6` Suspect, data originate from an NCEI data source; erroneous level: `3` Erroneous; `7` Erroneous, data originate from an NCEI data source | [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf), Table 3: "Legacy Codes for Sources 313, 314, 315, 322, 335, 343, 344, 346 include: ... 2 = Suspect 3 = Erroneous ... 6 = Suspect, data originate from an NCEI data source 7 = Erroneous, data originate from an NCEI data source" |
| `noaa/ghcn` | `hourly/data` | the plain first token, where `source:` is 220, 221, 222, 223, 347 or 348 | suspect level: `2` Suspect; erroneous level: `3` Erroneous | [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf), Table 3: "Legacy Codes for Sources: 220, 221, 222, 223, 347, 348 include 0 Not Checked 1 Good 2 Suspect 3 Erroneous 4 Calculated 5 Removed" |
| `noaa/ghcn` | `hourly/data` | the plain first token, where `source:` is 382 (the precipitation of C-HPD) | suspect level: `R` Indicates data values are suspect with regard to the times or period of occurrence; erroneous level: `X` failed global extreme exceedance check; `N` failed negative precipitation check; `Y` failed state extreme exceedance check (performed on daily totals); `K` failed streak/frequent-value check; `G` failed gap check; `O` failed climatological outlier check; `Z` flagged as a result of an official Datzilla investigation; `Q` Indicates value failed an extreme value test (value will be present) | [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf), Table 3: "Legacy Codes for Source 382 for precipitation (as given in C-HPD documentation) Blank = did not fail any quality assurance check X = failed global extreme exceedance check ..." |
| `noaa/ghcn` | `hourly/data` | the plain first token, where `source:` is 345, for `humidity_relative` and `wind_speed` only | `3` Error (erroneous data) | [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf), Table 3: "Legacy Codes for Source 345 (for relative humidity and wind speed only): 0 = Good 1 = Issue (field-length overflow) 3 = Error (erroneous data)" |
| `noaa/ghcn` | `hourly/data` | the plain first token, where `source:` is 220, 221, 222, 223, 313, 314, 315, 322, 335, 343, 344, 346, 347 or 348 (the sources that derive humidity), for `humidity_relative` only | suspect level: `f` Suspect or Error flags for 1 or more of the input measurements; erroneous level: `o` Out of range (relative humidity only - with values < 1 or > 100) | [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf), Table 3: "Sources: 220, 221, 222, 223, 313, 314, 315, 322, 335, 343, 344, 346, 347, 348 For these sources, relative humidity and wet-bulb temperature are not directly measured, but rather derived from other measured variables. These can have the following QC flags: o - Out of range (relative humidity only - with values < 1 or > 100) f - Suspect or Error flags for 1 or more of the input measurements" |
| `noaa/ghcn` | `hourly/data` | the same sources, for `temperature_wet_2m` only | suspect level: `f` Suspect or Error flags for 1 or more of the input measurements | the same table of the [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf) |
| `metno/frost` | `10_minutes/data`, `hourly/data`, `6_hours/data`, `daily/data`, `monthly/data`, `annual/data` | the plain first token (`qualityCode`) | `7` Erroneous, value is not corrected | [Frost data clarifications, Quality code](https://frost.met.no/dataclarifications.html#quality-code): "Frost tries to give the user a single value to represent the general quality of the observation. This value is set in the field qualityCode." `7 Erroneous, value is not corrected` |
| `chmi/observation` | `10_minutes/data`, `hourly/data`, `daily/data` | the plain first token (`QUALITY`) | suspect level: `1` Suspect/Podezřelá hodnota; erroneous level: `2` Poor/Hodnota s nízkou kvalitou, podezřelá, zatím nepoužívat | [meta4.csv](https://opendata.chmi.cz/meteorology/climate/historical_csv/metadata/meta4.csv): `1,Suspect/Podezřelá hodnota`, `2,Poor/Hodnota s nízkou kvalitou, podezřelá, zatím nepoužívat` |
| `ea/hydrology` | `15_minutes/data`, `daily/data` | the plain first token (`quality`) | `Suspect` | [Hydrology API reference, Readings](https://environment.data.gov.uk/hydrology/doc/reference#readings-section): "quality: The quality of this reading: Good, Estimated, Suspect, Unchecked, Missing" |
| `meteofrance/observation` | `6_minutes/data`, `hourly/core`, `hourly/others`, `daily/core`, `daily/others`, `monthly/data` | the plain first token (`Q<parameter>`) | `2` donnée douteuse en cours de vérification (la donnée a été mise en doute par contrôle automatique) | the "descriptif" of each of the four products ([quotidiennes](https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-quotidiennes/20260603-085232/climatologie-donnees-quotidiennes-descriptif-20260603.pdf), [horaires](https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-horaires/20260603-085646/climatologie-donnees-horaires-descriptif-20260603.pdf), [mensuelles](https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-mensuelles/20260603-085345/climatologie-donnees-mensuelles-descriptif-20260603.pdf), [6 minutes](https://static.data.gouv.fr/resources/donnees-climatologiques-de-base-6-minutes/20260401-151040/climatologie-donnees-6-minutes-descriptif-20250604.pdf)): "un code qualité est associé à la mesure (noté Qparamètre). Il qualifie l’état de validation de la donnée : ... 2 : donnée douteuse en cours de vérification (la donnée a été mise en doute par contrôle automatique)" |
| `dmi/observation` | `hourly/data`, `daily/data`, `monthly/data`, `annual/data` | the token `validity:` | `false`: "Whether or not the value is considered valid by the climatologists. Invalid data is generally not correct" | [DMI climate data API, `stationValue`](https://www.dmi.dk/friedata/dokumentation/apis/climate-data-api-1): `properties.validity`. Its `qcStatus` (`manual`, `none`) says whether the value was controlled and is no verdict |
| `nws/observation` | `hourly/data` | the plain first token (`qualityControl` of the quantity, MADIS's QC data descriptor) | suspect level: `Q` Questioned, passed level 1, failed 2 or 3; erroneous level: `X` Rejected/erroneous, failed level 1; `B` Subjective bad | [NWS API reference, `QuantitativeValue.qualityControl`](https://api.weather.gov/openapi.json): "For values in observation records, the quality control flag from the MADIS system. The definitions of these flags can be found at https://madis.ncep.noaa.gov/madis_sfc_qc_notes.shtml"; [MADIS surface QC notes](https://madis.ncep.noaa.gov/madis_sfc_qc_notes.shtml), "QC Data Descriptor Values": "X - Rejected/erroneous, failed level 1 Q - Questioned, passed level 1, failed 2 or 3 where level 1 = validity level 2 = internal consistency, temporal consistency, statistical spatial consistency checks level 3 = spatial consistency check ... G - Subjective good B - Subjective bad" |
| `eaufrance/hubeau` | `5_minutes/data`, `6_minutes/data`, `10_minutes/data`, `15_minutes/data`, `hourly/data` | the plain first token (`code_qualification_obs`) | `12` Douteuse | [Hub'Eau hydrométrie API](https://hubeau.eaufrance.fr/api/v2/hydrometrie/api-docs), `code_qualification_obs`: "Qualification de la donnée d'observation hydrométrique. 7 valeurs possibles : 0, 4, 8, 12, 16, 20, 30 (Neutre, Faible, Forte, Douteuse, Non qualifiée, Bonne, Estimée)"; the Sandre nomenclature 515 it points to words `12` as "Valeur douteuse" |
| `dwd/road` | `15_minutes/data` | the plain first token, the station's own verdict on the sensor of the reading (`qualityInformationAwsData`, BUFR 0 33 005, read as `1` or `0`), for the wind, `temperature_air`, `humidity_relative`, `visibility` and the precipitation (not `temperature_surface` and `temperature_dew_point`, which the table names no bit for) | `1` Wind data suspect, Air temperature data suspect, Humidity data suspect, Ground temperature data suspect, Visibility data suspect, Precipitation data suspect | [WMO flag table 0 33 005, "Quality information (AWS data)"](https://github.com/wmo-im/BUFR4/blob/master/BUFRCREX_CodeFlag_en_33.csv): "2 Pressure data suspect; 3 Wind data suspect; 4 Air temperature data suspect; 5 Wet-bulb temperature data suspect; 6 Humidity data suspect; 7 Ground temperature data suspect; ... 14 Visibility data suspect; ... 18 Precipitation data suspect" |
| `metoffice/observation` | `daily/rain`, `daily/temperature`, `daily/weather`, `hourly/rain`, `hourly/weather`, `hourly/wind`, `hourly/radiation`, `hourly/soil_temperature` | the third digit from the right of the plain first token (`MESQL`, `_q`): the status, `qc_status`, as the file writes it without leading zeros (`2176` is `02176`) | `1` Observed and suspect (i.e. has failed the latest QC check), or there are strong grounds for suspecting the accuracy of the observation | [MIDAS QC flags](https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html): "This _q attribute is a five digit number (of the form MESQL), where each digit describes one aspect of the quality of a meteorological element. ... qc_status (code_id 8023) indicates the status of the data value. 0 Observed and not suspect 1 Observed and suspect (i.e. has failed the latest QC check), or there are strong grounds for suspecting the accuracy of the observation" |

<!-- source:end -->

The tests hold this table to the map of the code (`wetterdienst.model.source_flags.SOURCE_FLAGS`) and to the pages of
the providers, and a test of each provider's reader pins its codes on a row of the source. What is **not** read, and why:

- **GHCNh letters of the integration's own checks**: `c` climatological outlier, `s` spike, `l` failed logistical
  consistency, ... name the check of the dataset's own processing that flagged one of six elements (temperature, dew
  point, both pressures, wind direction, wind speed). The same letters `o` ("Out of range") and `f` ("Suspect or Error
  flags for 1 or more of the input measurements") are read only for the `humidity_relative` and the `temperature_wet_2m`
  (`f` alone) of the legacy sources that derive them, where Table 3 words them as verdicts. No other letter is read
  outside the list of source 382, where the documentation words each as a failed check or as suspect. The codes `0`,
  `1`, `4`, `5` and `9` of the legacy lists say the value was not checked, passed, was calculated or was removed, `D`,
  `M`, `A` and `q` of source 382 that it was deleted, missing, an accumulation or leaves out 15 minute periods, and `A`,
  `P`, `U`, `I`, `M`, `R` of the legacy lists that a value was accepted, replaced or inserted. Source 345's `1`, "Issue
  (field-length overflow)", is a fault of the record and not a verdict on the value, and `0` is "Good".
- **Frost 2, 4, 5 and 6**: "slightly uncertain" and "very uncertain" are a degree of confidence, and `6` is model data.
  Frost's own word for a verdict is `7`, "Erroneous": "very uncertain" (`5`) says how sure the control was, not that
  the value failed, where Météo-France's "douteuse" and CHMI's "Suspect" say the control doubted the value itself.
- **CHMI 3 to 5, EA `Estimated`, `Unchecked` and `Missing`**: an estimate, a value nobody checked and a missing value.
- **DMI `qcStatus`**: `manual` and `none` say whether a climatologist controlled the value.
- **NWS/MADIS `Z`, `C`, `S`, `V`, `G` and `T`**: how far a value got through the checks ("Preliminary, no QC", "Coarse
  pass", "Screened", "Verified"), "Subjective good", and a temperature returned for a virtual temperature that could
  not be calculated: none says the value failed.
- **Hub'Eau `0`, `4`, `8`, `16`, `20` and `30`**: "Neutre", "Faible" and "Forte" are the sandre's unknown values ("Valeur
  inconnue"), `16` "Non qualifiée" is no control, `20` "Bonne" passed and `30` "Valeur estimée" is an estimate.
- **DWD road `0` and null**: the station checked the quantity and did not find it suspect, or said nothing (the station
  ran no automated checks).
- **Met Office MIDAS, the other digits**: `qc_estimate` (an estimate or correction), the status codes `2` to `7` (an
  estimate, "An unreliable estimate (used in radiation QC)", "A correction (a reported value is assumed to be in
  error)", "Value reverted to original", "Original value verified by observer"), `qc_query` ("Failed MIDAS validation",
  "Failed climate QC range check", ... "gives information about the original (as reported) value", which a correction
  or a verification may have replaced, so the value returned is not the one that failed) and `qc_level`. A value of the
  qc-version 1 files may be a corrected one, with its original in qc-version 0
  ([MIDAS Open user guide](https://help.ceda.ac.uk/article/4982-midas-open-user-guide)).
- **SMHI `Kvalitet` `Y`**: not read. SMHI's [questions and answers](https://www.smhi.se/data/om-smhis-data/fragor-och-svar)
  do not word the codes `G` and `Y`; they say that values before 2010, which the earlier system could not check, got
  "en väldigt enkel kontroll för att få bort helt felaktiga värden" and that "de data som passerat kontrollen utan
  anmärkning har gulmarkerats, då vi inte kan garantera att de verkligen är korrekta" (the data that passed without
  remark are marked yellow because SMHI cannot guarantee them), and that daily precipitation stays `G` ("godkända")
  once the automatic checks find nothing wrong. The page does not say that `Y` is that yellow, and the library's own
  description of `Y` as "suspect or aggregated" has two meanings in one code: neither reading is a verdict on a value.
- **RMI `qc_flags` `validated`**: RMI words `validated` as a flag and no verdict: `false` is "not validated", the state
  of most of the series (the sunshine of station 6477 is `false` on 7,720 of 8,134 days), and its documentation says
  nothing of a value that failed.
- **Providers whose flag the reader does not return**, or whose documentation words no verdict, are in
  [GH-3745](https://github.com/earthobservations/wetterdienst/issues/3745).

## Setting the modes

One mode per check. A check that is not named keeps its mode, from the environment or its default.

```python
from wetterdienst import Options
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("hourly", "moisture", "pressure_air_site")],
    start="2024-01-01",
    end="2024-01-31",
    options=Options(plausibility={"range": "soft", "stuck": "hard"}),  # a dict of options works as well
)
values = request.filter_by_station_id("01048").values().all()
```

The same in the environment of a host, on the command line and as REST query parameters:

```bash
export WD_TS_PLAUSIBILITY__RANGE=soft
export WD_TS_PLAUSIBILITY__STUCK=hard

wetterdienst values --provider dwd --network observation --parameters hourly/moisture/pressure_air_site \
    --stations 01048 --timestamp 2024-01 --plausibility-range soft --plausibility-stuck hard

curl "http://localhost:7890/api/v1/values?provider=dwd&network=observation&parameters=hourly/moisture/pressure_air_site&stations=01048&timestamp=2024-01&plausibility_range=soft&plausibility_stuck=hard"
```

A bare mode sets every check at once: everything the source wrote, flagged and none of it nulled, is `soft`. A check
given beside it wins, so `soft` for all but the range is `soft` with `range` hard:

```python
from wetterdienst import Options

Options(plausibility="soft")  # all nine checks soft, the same as listing them
Options(
    plausibility={
        "range": "hard",
        "elevation": "soft",
        "stuck": "soft",
        "consistency": "soft",
        "floor": "soft",
        "limits": "soft",
        "source": "soft",
        "step": "soft",
        "relations": "soft",
    }
)
```

```bash
export WD_TS_PLAUSIBILITY=soft                  # every check soft ...
export WD_TS_PLAUSIBILITY__RANGE=hard           # ... but the range, which a check named beside it wins

wetterdienst values --provider dwd --network observation --parameters hourly/moisture/pressure_air_site \
    --stations 01048 --timestamp 2024-01 --plausibility soft --plausibility-range hard

curl "http://localhost:7890/api/v1/values?provider=dwd&network=observation&parameters=hourly/moisture/pressure_air_site&stations=01048&timestamp=2024-01&plausibility=soft&plausibility_range=hard"
```

In a Python mapping the checks are listed, so the shorthand there is the bare string; the environment, the command line
and REST have both the shorthand and the checks, and the checks win whatever the order. A value other than `soft` or
`hard` is refused.

The REST API and the MCP tools take `plausibility` and `plausibility_range`, `plausibility_elevation`, `plausibility_stuck`,
`plausibility_consistency`, `plausibility_floor`, `plausibility_limits`, `plausibility_source`, `plausibility_step` and `plausibility_relations` on `values`; `/api/settings` reports the modes as set (a forecast network is soft in every check but `floor` and `limits` whatever they are). A value
other than `soft` or `hard` is refused.

## The tokens

The two kinds sit after the source's own flags and before `raw:`, which stays the last token.

| case | `quality_flags` | value |
| --- | --- | --- |
| soft | `3,suspect:range` | kept |
| hard | `3,rejected:range,raw:4021` | null (the floor for `floor`) |
| a missing-value code of the source | `3,raw:-999` | null, or the documented meaning |
| several checks, soft | `suspect:range+stuck` | kept |
| several checks, hard | `rejected:range+stuck,raw:4021` | null |
| a relation, soft (both readings of the pair) | `10,suspect:relations` | kept |
| a relation, hard (both readings of the pair) | `3,rejected:relations,raw:4.9` | null |
| the source's own verdict, soft | `X,measurement:T,source:0,suspect:source` | kept |
| the source's own verdict, hard | `Suspect,rejected:source,raw:0.359` | null |

- One token per kind, the checks joined with `+` in alphabetical order. A value that a hard check nulled carries the
  hard checks alone: it is null, and `rejected:` says why. A value that only soft checks found is `suspect:` of all of
  them. The one exception is a hard `floor`, which keeps the value (as 0.0): a soft check that also finds it comes
  first, `suspect:limits,rejected:floor,raw:-0.02`.
- A soft verdict has no `raw:` of its own: the value is the number the source wrote, after the unit conversion as any
  other (beside a hard `floor` it is the floor, 0.0).
- The outcome is in the token and not only in the options, because an exported file does not carry the options it was
  made with. `raw:` alone is the source's own code; `rejected:` before it is our judgement.

A REST answer tells the two apart in its `warnings` ([REST API](../usage/restapi.md)): `missing-value-marker` counts the
nulls that carry a code the source wrote (`raw:` alone; a calm wind direction is told by `calm-wind-direction`),
`rejected-by-plausibility` the nulls a hard check made (`rejected:` before `raw:`), with the count per check in its
message. A value that two checks rejected is one value,
told under both. A soft check keeps the value and raises no warning, and neither does the `floor` check, whose value is
the floor and not null.

```python
import polars as pl

flags = pl.col("quality_flags")

# the numbers a hard check rejected (the value is null: use `drop_nulls=False`, or the wide shape)
rejected = values.df.filter(flags.str.contains(r"(^|,)rejected:"))
# the check that rejected each, and the number the source wrote
rejected.select(
    flags.str.extract(r"rejected:([a-z+]+)", 1).alias("checks"),
    flags.str.extract(r"raw:([^,]*)$", 1).alias("number"),
)

# the values a soft check kept, and those of one check
suspect = values.df.filter(flags.str.contains(r"(^|,)suspect:"))
stuck = values.df.filter(flags.str.contains(r"(^|,)suspect:([a-z+]*\+)?stuck"))

# the codes the source documents, which no check judged: `raw:` with no `rejected:` before it
codes = values.df.filter(flags.str.contains(r"(^|,)raw:") & ~flags.str.contains(r"(^|,)rejected:"))

# only the values no check doubts
clean = values.df.filter(~flags.str.contains(r"(^|,)(suspect|rejected):").fill_null(value=False))
```

## Where each check runs

The table is what the core is told to judge by the library's own tables: a network that is in no row judges no value
unless you set [bounds of your own](#bounds-of-your-own-limits), which any network is judged by. A dataset is
`resolution/dataset`; `*` stands for every dataset of the network that has a parameter the check judges, which is how
`range`, `elevation`, `stuck`, `step` and `relations` run on every network that has one.

<!-- coverage:start -->

| check | network | datasets |
| --- | --- | --- |
| `range` | `aemet/observation` | `*` |
| `range` | `chmi/observation` | `*` |
| `range` | `dmi/observation` | `*` |
| `range` | `dwd/derived` | `*` |
| `range` | `dwd/dmo` | `*` |
| `range` | `dwd/mosmix` | `*` |
| `range` | `dwd/observation` | `*` |
| `range` | `dwd/phenology` | `*` |
| `range` | `dwd/poi` | `*` |
| `range` | `dwd/road` | `*` |
| `range` | `dwd/swsmos` | `*` |
| `range` | `eccc/observation` | `*` |
| `range` | `fmi/observation` | `*` |
| `range` | `geosphere/observation` | `*` |
| `range` | `imgw/hydrology` | `*` |
| `range` | `imgw/meteorology` | `*` |
| `range` | `ipma/observation` | `*` |
| `range` | `knmi/observation` | `*` |
| `range` | `lhmt/observation` | `*` |
| `range` | `meteofrance/observation` | `*` |
| `range` | `meteofrance/synop` | `*` |
| `range` | `meteoswiss/observation` | `*` |
| `range` | `metno/frost` | `*` |
| `range` | `metoffice/observation` | `*` |
| `range` | `noaa/ghcn` | `*` |
| `range` | `nws/observation` | `*` |
| `range` | `rmi/observation` | `*` |
| `range` | `smhi/observation` | `*` |
| `range` | `wsv/pegel` | `*` |
| `elevation` | `aemet/observation` | `*` |
| `elevation` | `chmi/observation` | `*` |
| `elevation` | `dwd/observation` | `*` |
| `elevation` | `eccc/observation` | `*` |
| `elevation` | `geosphere/observation` | `*` |
| `elevation` | `imgw/meteorology` | `*` |
| `elevation` | `knmi/observation` | `*` |
| `elevation` | `meteofrance/observation` | `*` |
| `elevation` | `meteofrance/synop` | `*` |
| `elevation` | `meteoswiss/observation` | `*` |
| `elevation` | `metno/frost` | `*` |
| `elevation` | `metoffice/observation` | `*` |
| `elevation` | `noaa/ghcn` | `*` |
| `elevation` | `rmi/observation` | `*` |
| `stuck` | `aemet/observation` | `*` |
| `stuck` | `chmi/observation` | `*` |
| `stuck` | `dmi/observation` | `*` |
| `stuck` | `dwd/observation` | `*` |
| `stuck` | `dwd/poi` | `*` |
| `stuck` | `dwd/road` | `*` |
| `stuck` | `eccc/observation` | `*` |
| `stuck` | `fmi/observation` | `*` |
| `stuck` | `geosphere/observation` | `*` |
| `stuck` | `imgw/meteorology` | `*` |
| `stuck` | `ipma/observation` | `*` |
| `stuck` | `knmi/observation` | `*` |
| `stuck` | `lhmt/observation` | `*` |
| `stuck` | `meteofrance/observation` | `*` |
| `stuck` | `meteoswiss/observation` | `*` |
| `stuck` | `metno/frost` | `*` |
| `stuck` | `metoffice/observation` | `*` |
| `stuck` | `noaa/ghcn` | `*` |
| `stuck` | `nws/observation` | `*` |
| `stuck` | `rmi/observation` | `*` |
| `stuck` | `smhi/observation` | `*` |
| `stuck` | `wsv/pegel` | `*` |
| `step` | `aemet/observation` | `*` |
| `step` | `chmi/observation` | `*` |
| `step` | `dmi/observation` | `*` |
| `step` | `dwd/observation` | `*` |
| `step` | `dwd/poi` | `*` |
| `step` | `eccc/observation` | `*` |
| `step` | `fmi/observation` | `*` |
| `step` | `geosphere/observation` | `*` |
| `step` | `imgw/meteorology` | `*` |
| `step` | `ipma/observation` | `*` |
| `step` | `knmi/observation` | `*` |
| `step` | `lhmt/observation` | `*` |
| `step` | `meteofrance/observation` | `*` |
| `step` | `meteoswiss/observation` | `*` |
| `step` | `metno/frost` | `*` |
| `step` | `metoffice/observation` | `*` |
| `step` | `noaa/ghcn` | `*` |
| `step` | `nws/observation` | `*` |
| `step` | `rmi/observation` | `*` |
| `step` | `smhi/observation` | `*` |
| `step` | `wsv/pegel` | `*` |
| `relations` | `aemet/observation` | `*` |
| `relations` | `chmi/observation` | `*` |
| `relations` | `dmi/observation` | `*` |
| `relations` | `dwd/observation` | `*` |
| `relations` | `dwd/poi` | `*` |
| `relations` | `dwd/road` | `*` |
| `relations` | `eccc/observation` | `*` |
| `relations` | `fmi/observation` | `*` |
| `relations` | `geosphere/observation` | `*` |
| `relations` | `imgw/meteorology` | `*` |
| `relations` | `knmi/observation` | `*` |
| `relations` | `meteofrance/observation` | `*` |
| `relations` | `meteofrance/synop` | `*` |
| `relations` | `meteoswiss/observation` | `*` |
| `relations` | `metno/frost` | `*` |
| `relations` | `metoffice/observation` | `*` |
| `relations` | `noaa/ghcn` | `*` |
| `relations` | `nws/observation` | `*` |
| `relations` | `rmi/observation` | `*` |
| `consistency` | `dwd/road` | `15_minutes/data` |
| `consistency` | `meteofrance/observation` | `hourly/others` |
| `consistency` | `meteofrance/synop` | `subdaily/data` |
| `floor` | `dwd/dmo` | `hourly/icon`, `hourly/icon_eu` |
| `source` | `chmi/observation` | `10_minutes/data`, `hourly/data`, `daily/data` |
| `source` | `dmi/observation` | `hourly/data`, `daily/data`, `monthly/data`, `annual/data` |
| `source` | `dwd/road` | `15_minutes/data` |
| `source` | `ea/hydrology` | `15_minutes/data`, `daily/data` |
| `source` | `eaufrance/hubeau` | `5_minutes/data`, `6_minutes/data`, `10_minutes/data`, `15_minutes/data`, `hourly/data` |
| `source` | `meteofrance/observation` | `daily/core`, `daily/others`, `hourly/core`, `hourly/others`, `monthly/data`, `6_minutes/data` |
| `source` | `metno/frost` | `10_minutes/data`, `hourly/data`, `6_hours/data`, `daily/data`, `monthly/data`, `annual/data` |
| `source` | `metoffice/observation` | `daily/rain`, `daily/temperature`, `daily/weather`, `hourly/rain`, `hourly/weather`, `hourly/wind`, `hourly/radiation`, `hourly/soil_temperature` |
| `source` | `noaa/ghcn` | `daily/data`, `hourly/data` |
| `source` | `nws/observation` | `hourly/data` |
<!-- coverage:end -->

`range`, `elevation`, `stuck`, `step` and `relations` run on every network that serves a quantity of their tables (`*`:
every dataset of the network that has one; for `stuck` also the road and RMI datasets of their own rules; for `relations`
every dataset that holds two parameters of [its table](#the-relations-of-one-row-relations) in one file, or a sunshine
duration, which is every dataset whose provider collects it whole). `source` runs where a provider's flag is mapped ([the codes](#the-sources-own-verdict-source)). `limits` is in no row: it runs on any network, for the parameters you set a bound for. Within a dataset a check covers the parameters its rule names, not every parameter: `range` the
parameters that have a bound in the table, `elevation` the `pressure_air_site`, `pressure_air_site_mean`,
`pressure_air_site_min` and `pressure_air_site_max`, `stuck` the parameters of [its table](#the-limit-of-a-run), at the
resolutions it names, `step` those of [its table](#the-limits-of-a-jump-step) and `relations` the pairs of [its table](#the-relations-of-one-row-relations). The provider pages and [special values](special_values.md) list them.

What no check covers, and why:

- **A second parameter in another dataset.** A check never triggers a download. A consistency check reads its second
  parameter from the frame of the station and the same timestamp: the dataset is collected whole, and the neighbour of a
  relation is kept for the check even where nobody asked for it, and dropped after judging. Where the second parameter
  lives in another dataset, the check does not run. DWD observation holds its hourly `temperature_air` and `moisture` in
  two datasets, so the humidity of one is not held to the dew point of the other.
- **Quantities with no bound.** The hydrology of Hub'Eau and the Environment Agency (apart from their `Douteuse` and `Suspect` readings, which `source` flags) judges nothing without bounds of your own, and no network
  judges its codes, the derived quantities and the gauges listed above: a number there stays as the source wrote it. The
  sources' own "erroneous" flags are judged by [`source`](#the-sources-own-verdict-source) where a provider is mapped,
  and are the source's own, returned as its flags, where it is not.

## Caveats

- **What `stuck` finds depends on what was read, which differs by network.** The check judges a series and not a value,
  which is why it is soft by default: the value stays and you decide. It judges the series the reader hands the core,
  merged over the periods it read, **before** the window of the request is cut, and it never reads more than the reader
  did (a check never downloads): the earlier values of a run that crosses the start of the window are in the verdict
  where the reader read them anyway, and are not where it did not. So:
  - *A reader that reads whole files* (DWD observation: the historical, recent and now files of a station) judges the
    merged series of the files: the same file answers the same for any window inside it, and a run that crosses the start
    of the window is found. A request for the recent period alone sees the runs of the recent file alone.
  - *A reader that asks its source for the window only* (DWD road, FMI, DMI) has nothing before the start of the window,
    so a run that crosses it is found only when the window covers enough of it, and a request for an hour has fewer
    readings than any limit: the same day can answer differently for a different window. For this reason the road
    surface rule of `consistency` does not use the stuck verdict. Extending such a read by the length of a run would be a
    larger download, which the check does not trigger, and is not done.
  - *A short series reads as a coarser one.* The step a series is written at is read off its own values
    ([above](#the-limit-of-a-run)), and a window of a few days has few different values, so a series in tenths can read
    as halves or wholes there, where the limit is the more lenient one (30 or 40 hourly readings instead of 24, a daily
    wind rule not judged). The exception is a window in which the sensor never changed: that series reads as the finest
    step, whatever the file it was cut from.
  - *A constant stretch below the limit of a run* (71 hourly readings of a pressure, 4 days) is not flagged, where the
    earlier rule on a whole file of at most three values flagged it whatever its length.
  - *RMI's sunshine*: the periods are fixed dates of one station (6477), so the verdict depends on neither.
- **What `step` finds depends on what was read, as `stuck` does.** It judges the series the reader hands the core,
  merged over the periods and **before** the window of the request is cut, and never reads more than the reader did, so
  a reader that reads whole files (DWD observation) finds a jump across the start of the window, and one that asks its
  source for the window only (DWD road, FMI, DMI) does not. The first reading of the series that is read has no
  predecessor and is never flagged; if it is the wrong one, the reading after it is flagged for the change, and a
  bad first reading of a short window costs that. A spike needs both neighbours, so the last reading of a series is no
  spike.
- **A front is a real step, and the check judges a series and not a value.** A cold front or a thunderstorm can lower an
  hourly air temperature by 10 K, which is why the spike limit (8 K) is the lower and the step limit (20 K) the higher. A one-sided
  limit of 8 K an hour would flag 300 hourly steps of 6.3 million in the DWD data read, nearly all of them weather
  (33.8 to 24.3 °C at Berlin-Tempelhof, 2022-07-25), and is not used.
- **A false alarm of another check can hide a spike and move the flag to the good reading.** A reading any other
  check flagged is no neighbour, soft or hard, so a flag that is wrong takes its reading out of the series: 50 hours
  pinned at 0.0 (`suspect:stuck`, a melting point), then 30.0, 0.2, 0.3 leaves the 30.0 without a neighbour and
  unflagged, and flags the good 0.2 after it as the step from the 30.0. This follows from the rule and is kept. In the
  hourly DWD data read the rule lost no flag and added 4.
- **A step flags the later reading of the pair.** Nothing says which of two readings is wrong. A level shift (a sensor
  that jumped by 25 K and stays) flags the first reading after the jump; a bad value that is held for two readings or
  more is a spike of two, which is no spike, so its first reading is flagged as a step, and the first good reading after
  it as another. The jump out of a single spike is the spike's: the good reading after it is judged against the reading
  before the spike, and is not flagged where it is back within the limit.
- **A hurricane's pressure.** The limit of 60 hPa an hour keeps the readings of Hurricane Irma at Saint-Barthélemy
  (936.0, 917.4, 960.4 hPa in three hours); the limits of the sources (DMI 5 to 8 hPa, MADIS 15 hPa) would flag its
  minimum, and also 759 more readings of DWD's hourly pressure, typing slips of 5 to 60 hPa, which 60 does not ([what step does not judge](#what-step-does-not-judge)).
- **Melting point and the whole-degree years.** A temperature pinned at 0.0 °C (snow or ice melting, a mountain in cloud)
  can hold one value for a day, and the limits do not exempt it: seven runs of 0.0 °C of the air temperature or the dew
  point in the readings read are flagged, the Zugspitze's 171 readings of 0.0 °C among them. And three runs of 40 to 43
  hours at 1.0 to 4.0 °C in 1979 to 1981 (Helgoland, Potsdam), when DWD wrote whole degrees and the limit is HadISD's
  40, are weather by all appearances and flagged. Both are `suspect:stuck`, soft, and left out of an interpolation.
- **`elevation` uses the station list's current elevation for every period.** A station that was moved by 500 m or more
  keeps the readings of its other site only while they lie within the margins. DWD's historical outliers were checked
  against the station list and are bad readings, not station moves.
- **`relations` flags a good reading beside a bad one, by design.** A broken pair has one wrong reading at most (or
  two), and nothing says which; both are flagged, so each false alarm costs two readings and not one, and an
  interpolation, a summary and `skip_empty` leave both out. That is why the check is soft by default. The false alarms
  measured are one class, the dew point of a saturated hygrometer ([above](#what-relations-found-in-real-data)); a
  tolerance of 0.2 K is the table's, and a different one is a change of the table.
- **A relation reads its partner whether or not you asked for it.** Asking for the daily maximum alone reads the mean
  and the minimum of the file as well (the dataset is collected whole), judges the pairs, and returns the maximum with
  its flag: the verdict does not depend on what you asked for. The partner is dropped after the judging, as the air beside a
  road surface is.
- **The sunshine reads the station list.** The day length uses the latitude and the elevation the list holds, so a
  position that is wrong but on Earth is not seen: a degree of latitude moves the December day by 0.13 to 0.22 h at 45 to
  55 degrees north (the margin is 5 %, 0.4 to 0.9 h) and the June day of 65 degrees by 2 h. A 0, 0, a missing position
  and a number off the globe are stood aside for. A polar station is judged by the same formulas (the day is 0 in the
  polar night and 24 in the polar day), which no key-less network reading sunshine lets the page measure: the tests
  hold it to the day lengths of Tromsø.
- **A check stands aside where the second value is missing.** A consistency check that finds no second value for a row
  (null, not a number, outside its own range, or marked suspect by the source's own flag) returns the value unflagged.
- **Every check judges the same number.** A pressure of 1150 hPa at 100 m is outside the range and outside the
  elevation: `rejected:elevation+range,raw:1150` with both hard, and `suspect:elevation+range` with both soft. One of
  1093.3 hPa at 100 m is inside the range and outside the elevation: `rejected:elevation,raw:1093.3`.
- **Where a `floor` covers a value, the range stands aside.** DMO's rain of -0.02 mm is below the 0 of the table and is
  the floor's, so it becomes 0 as before (`rejected:floor,raw:-0.02`) and not null. Where `floor` is hard, `limits`
  judge such a value as the floor, 0.0, which is what the answer holds, so a bound of 0 for the rain does not take it away
  again; where `floor` is soft, the value is kept as the model wrote it and is judged as it is. A soft check that also finds a
  value the hard floor has set to 0.0 is told as well (`suspect:limits,rejected:floor,raw:-0.02`), since the value stays.
- **A hard check can only judge a number it can read.** A text that is no number (`mq`, `---`) and a NaN or an infinity
  are no judgement: they are null with their text, as a code is, in both modes.

## Soft mode and the rest of the request

- **Interpolation, summary and climate stripes** always leave out a `suspect` value, whatever the mode: a number a check
  finds implausible has no place in a weighted mean, a nearest station's answer or a year of stripes (which shows as a
  year without data). The mode changes only what a station's own values show. The values stay rows with no value, as a
  rejected one does.
- **`skip_empty`** judges a station by its unflagged values alone: a value flagged `suspect` is no coverage, so a station
  with only such values is skipped. For the checks that used to null (`range`, `elevation`, `consistency`, `floor`, and
  `stuck` of the DWD observation barometer and RMI) this is as before. For `stuck` of DWD road, which used to keep the
  value with the flag `1` and count it, it is a change: a road station with long stuck runs can be skipped where it was
  kept. So it is for the run rule of every other network and parameter (GH-3681), where a stuck run is left out of an
  interpolation and a summary, and a station that has only stuck readings in the window is skipped, as before it was
  not: in the DWD data read, about 1,500 of 93 million judged readings, apart from the barometer constants. So it is for `step`: a reading flagged `suspect:step` is left out of an interpolation and a summary (a spike of 100 hPa in the pressure of a station is no pressure to interpolate), and a window whose readings are all flagged skips the station, which the readings read (a few hundred in millions) do not make. So it is for `relations`, with a cost the others do not have: **both** readings of a broken pair are left out, so a good air temperature beside a wrong dew point is no air to interpolate either (in the DWD data read, 796 hourly, 1,850 10-minute and 5 daily readings, of 93 million judged). So it is for `source`: a station of `noaa/ghcn`, `metno/frost`, `chmi/observation`, `ea/hydrology`,
  `meteofrance/observation` or `dmi/observation` whose values the source flagged can be skipped where it was kept.
- **A rejected value carries only the hard verdict.** Where a hard check nulls a value and a soft one also finds it
  suspect, the value is null and the token is `rejected:<hard checks>,raw:<number>`; the soft check is not listed. A
  hard `floor` keeps the value, so a soft check that also finds it is listed before it.
- **`drop_nulls=True`** keeps dropping the rows of hard-rejected values, as it drops any null. A soft row has a value and
  stays. `drop_nulls=False`, or the wide shape, shows the rejected rows with their flags.
- **Unit conversion** acts on a soft value as on any other: the number is converted, and the flag stays. The `raw:` of a
  hard verdict is the text the source wrote, in the unit of the source (DMI's radiation is the megajoules it wrote).
- **The wide shape** has the flag beside each value, in `<parameter>_quality_flags`, with the same tokens.
- **Physical ranges in tests.** A value outside its range that carries `suspect:` is kept on purpose, so the range check
  of the provider tests accepts it.
