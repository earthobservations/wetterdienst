# Special values

The sources do not write a missing reading, a calm, a trace of rain or an obscured sky the same way: one writes
`-999`, the next `---`, a third a 0 that looks like a reading. `wetterdienst` reads each source's way to one rule per
situation, so that the same situation comes back the same from every provider. This page lists the rules and the
providers that apply them. Where the library maps what the source wrote, the value keeps that text as the last token
of `quality_flags`, `raw:<text>` ([quality flags](quality-flags.md) lists the tokens provider by provider); the long
shape drops the rows without a value by default, so the token shows with `drop_nulls=False` or in the wide shape.

What the library finds implausible, rather than what the source writes as a code, is a [plausibility check](plausibility.md)
with a mode of its own: the rows of the table "Missing values and texts" that name a range, an elevation, a stuck
sensor, a reading another contradicts or a floor are such checks, and write `rejected:<check>,raw:<number>` (hard, the
default but for `stuck`) or keep the value as `suspect:<check>` (soft). The codes of a source (`-999`, a calm, a trace)
are no check and have no mode.

The tests hold the rules to what each source writes: `tests/provider/value_stubs.py` serves a reading and the
special values of every provider through its own reader, and `tests/provider/test_value_stubs.py` checks that no
sentinel reaches the values, that each keeps its `raw:` token, and that every wind direction follows one of the two
rules below: the calm, or the no-direction code.

## Wind

Two rules decide a wind direction of 0. The **calm**: a 0 beside a speed of 0 of the same reading is null, and a 0
beside a wind that blows stays, as a source may write north as 0. The **no-direction code**: a direction the source
writes as a code of a variable wind or of no direction, or a 0 that its data shows is neither a calm nor north, is
null whatever the speed. The second is the one exception to the first, and applies only where the source names the
value a code or its data rules out a bearing; a 0 that may be north is always the business of the calm.

| situation | rule | providers |
| --- | --- | --- |
| a direction of 0 beside a speed of 0 of the same reading (a calm) | null, `raw:0` (as the source writes it, `raw:0.0`) | every provider whose source writes one: AEMET (hourly), DMI, DWD observation (10 minute and hourly `wind`, 10 minute `wind_extreme` beside the gust, the urban 10 minute `wind`, subdaily `wind` beside a force of 0), DWD POI, ECCC (hourly; daily beside a gust of 0), FMI, Geosphere, KNMI (hourly), Met Office (hourly), Météo-France observation and synop, MeteoSwiss, NOAA GHCN hourly, NWS, SMHI |
| a direction of 0 beside a speed above 0 | the value 0, as a source may write north as 0 too; most write it 360 | the same providers. Geosphere and NWS write their 0 beside a speed of 0 only (every 0 of the files read), and null every 0 of the column; for KNMI see below |
| a direction of 0 beside a speed the source does not give | the value 0 | the providers that read the speed beside the direction, all of the first row but Geosphere, KNMI and NWS |
| a no-direction code: a code of a variable or indeterminate direction | null, with the code | DWD observation `990`, KNMI `990`, Météo-France observation `999` and daily `400`, Météo-France synop `400`, AEMET daily `99` (calm or variable), NOAA GHCN hourly `999`, NWS `VRB` (null from the source) |
| a no-direction code: a 0 the source names a code | null, `raw:0`, whatever the speed | DWD observation hourly `wind_synoptic` (the sheet's "Windrichtung uml.,windstill DD=00", a variable or calm wind), IPMA (the point 0 of eight, "no direction", where north is 1 or 9) |
| a no-direction code: a 0 that is neither a calm nor north | null, `raw:0`, whatever the speed | DWD observation hourly `urban_wind`: 1,288 zeros in 295,005 hours, never beside a speed of 0, and the six 10 minute directions of such an hour are spread over the compass (GH-2809); north is written 360 |
| north | 360, as written; a 0 beside a wind that blows stays 0 | all; IPMA's codes 1 and 9 for north are read as 360 |
| a direction on a scale of points | read in degrees: DWD subdaily (32 points, 11.25 degrees each), IPMA (8 points, 45 degrees, north 360) | DWD subdaily, IPMA |
| a direction in tens of degrees | read in degrees | AEMET daily, ECCC |

KNMI's hourly direction `DD` is the mean of the last 10 minutes of the hour ("0=windstil"), and the speed of those
10 minutes (`FF`) is no parameter of the library, which serves the hourly mean `FH`. Every 0 of `DD` is null: in
KNMI's hourly files of 2023 at stations 260, 240, 344 and 270 all 354 zeros are beside an `FF` of 0, which is the
rule of a calm with the speed it needs, and 223 of them beside an `FH` of 1 to 2 m/s, so `FH` cannot stand in for it.

## Not measured

A 0 the source writes for a quantity it did not measure is no reading, and is null with `raw:0`. ECCC's daily
`wind_gust_max` is 0 below the 31 km/h the stations report gusts from, and `wind_direction_gust_max` beside it is
null too. So is NOAA GHCN daily's `wind_gust_max` of 0 with source flag C (Environment Canada); a 0 of any other
source is a gust of 0.

## Precipitation and snow

A trace (less than the gauge reads) comes back as 0.0 in one of two shapes, as the source writes it. Where the source
writes 0 and a flag, the flag says it, as for any other reading; where it writes a code in place of the value, the
library maps the code to 0.0 and keeps it as `raw:<code>`.

| situation | rule | providers |
| --- | --- | --- |
| a trace written as a code in the value | 0.0, `raw:<code>` | AEMET `Ip`, KNMI `-1` (also a trace of sunshine), Météo-France synop `-0.1` |
| a trace written as 0 and flagged | 0.0, the source's flag | CHMI `element:T`, ECCC `T`, NOAA GHCN `measurement:T`, NWS (`P0000`, quality `C`) |
| a precipitation or radiation a model writes a little below 0 (check `floor`) | hard: 0.0, `rejected:floor,raw:<number>`; soft: the value, `suspect:floor` | DWD DMO `rr1` and `rr3` (ICON, to -0.10 mm), `rad1h` and `rads3` (to -0.77 and -0.46 J/cm2) |
| a trace written as a plain 0 | 0.0 | Geosphere daily ("0=weniger als 1/10 mm"), Météo-France observation |
| no precipitation or no snow written as a code | 0.0, `raw:<code>` | FMI `-1.0`, Geosphere daily `-1.0` and `-1`, MET Norway Frost `-1` (snow depth) |
| no precipitation written as a status | 0, the status as the quality flag | IMGW meteorology `9` |
| a dry hour the source leaves out | null: a METAR without a precipitation group, or an empty cell, cannot be told from a station without a gauge | NWS, NOAA GHCN hourly |

## Cloud cover

| situation | rule | providers |
| --- | --- | --- |
| the sky obscured or not visible | null, `raw:<code>`, never an amount (9 oktas would read 1.125) | DWD observation `-1`, DWD POI `113` and `126`, KNMI `9`, Met Office `9`, Météo-France observation `9`, Météo-France synop `101`, MET Norway Frost `9` and `-3`, SMHI `113` |
| an obscured sky the source writes as no value | null, without a token | LHMT |
| oktas and percent | a fraction of the sky: oktas are divided by 8, a percent by 100 as the source writes it (Météo-France synop writes 1 okta as 10 %, the others as 12 or 13 %) | all |

## Missing values and texts

The core reads every value as a number. A value cell that is a text and no number (`nan` and `inf` among them) is
null there, and one debug line per frame says how many: that count is the floor every provider gets. A `raw:<text>`
token goes only with a text the source documents (`---`, `-`, `NA`, `Ip`, a sentinel number), where the reader maps
it itself.

| situation | rule | providers |
| --- | --- | --- |
| a missing-value sentinel (`-999`, `-9999`, `-99.0`, `-99.9`, `9999`, `99.9`, `99999.999`, `-None`, `---`, `-`, `NA`, `NaN`) | null, `raw:<sentinel>` | DWD observation and derived, DWD mosmix, dmo, POI and swsmos, FMI, IMGW hydrology, IPMA, KNMI, Met Office, NOAA GHCN hourly |
| the 198.15 K (-75.00 °C) a stopped sensor writes, exactly (GH-3681) | null, `raw:198.15` (kelvin, as DWD writes it) | DWD road (air and road surface temperature, seen in station group KM) |
| an empty field or a JSON null | null, without a token | every other provider |
| a value cell that is a text and no number, or a JSON `NaN` | null and counted by the core; a reader that knows the text keeps it as `raw:<text>` | all; `raw:` in AEMET, DWD POI, swsmos, mosmix and dmo, FMI, Met Office, Météo-France |
| a number padded with blanks | read | all (the core) |
| a value outside the physical range of its parameter that is no code (check `range`) | hard: null, `rejected:range,raw:<number>` as the source wrote it, in its unit; soft: the value, `suspect:range` | every network that has a quantity in the one table of ranges (`wetterdienst.model.plausibility_ranges`, the same for every provider), such as DMI and RMI (4021 °C, a rain beyond the records), DWD road (a humidity below 1 % too), DWD observation (a wind speed below 0 or above 115 m/s; `pressure_air_site` outside 300 to 1100 hPa, `pressure_air_sea_level` outside 850 to 1100 hPa), Météo-France synop (`pres`, `pmer`, the temperatures and the dew point, and `rr1` to `rr24` beyond the records) and Geosphere (a `-1` of rain outside the daily code) |
| a station pressure that the standard atmosphere does not allow at the elevation of the station in the station list (143 hPa below it at sea level, 75 hPa above it): a reading inside the bounds of the world that is mistyped (1093.3 hPa at 48 m) or is the pressure of another height (968.6 hPa at the Zugspitze, 2,956 m) (check `elevation`) | hard: null, `rejected:elevation,raw:<number>` as the source wrote it; soft: the value, `suspect:elevation` | every network that serves `pressure_air_site`, `_mean`, `_min` or `_max` (DWD observation, Météo-France observation and synop, MeteoSwiss, Geosphere, ...); a station without an elevation in the list is held to the bounds of the world only, and so is a `noaa/ghcn` station listed at 0.0 m (its lists write 0.0 for an unknown height) |
| a temperature below 0 C where there is no frost: air at 2 m, its extremes and the dew point of Guadeloupe (971), Martinique (972), Guyane (973), Mayotte (985), Wallis-et-Futuna (986), French Polynesia (987) and the Îles Éparses (984: Glorieuses, Juan de Nova, Europa, Tromelin) (check `range`; the humidity beside such a dew point is `consistency`) | hard: null, `rejected:range,raw:<number>` as the source wrote it (`rejected:consistency,raw:<number>` for the humidity); soft: the value, `suspect:range` or `suspect:consistency` | Météo-France observation and synop (the 24 synop stations are named in `synop/api.py`), the relative humidity of the row whose dew point is nulled included (the same hygrometer failed, `raw:<number>`; no floor on the humidity itself); not La Réunion, where frost occurs at altitude, nor Saint-Pierre-et-Miquelon, the southern territories (Kerguelen, Crozet, Nouvelle-Amsterdam, Dumont d'Urville) or New Caledonia |
| a sensor stuck or dead over a period (check `stuck`, soft by default) | soft: the value, `suspect:stuck`; hard: null, `rejected:stuck,raw:<value>` | DWD observation (a run of 72 hourly readings, 5 daily, 36 at 10 minutes of one station pressure: the pressure of a station without a barometer), RMI (sunshine of station 6477) |
| a value inside every range that is no reading, alone (check `range`) or beside another of its minute (check `consistency`) | hard: null, `rejected:range,raw:<value>` or `rejected:consistency,raw:<value>`; soft: the value, `suspect:<check>` | DWD road (a relative humidity below 1 %; a road surface temperature more than 20 K above the air temperature of its minute with the sun more than 6 degrees below the horizon) |
| a sensor that holds one value for six hours (check `stuck`) | soft: the value, `suspect:stuck`; hard: null, `rejected:stuck,raw:<value>` | DWD road (air, dew point and road surface temperature) |
| a value the source flags missing | null, the flag | CHMI `4`, EA `Missing`, ECCC `M`, IMGW meteorology `8` |
| a value the source flags suspect or invalid | the value, with the flag | all that flag (DMI `validity:false`, RMI, GHCN, Met Office, Frost, SMHI `Y`, NWS, DWD road) |

## As published

These values are returned as the source writes them, with no token:

- visibility at the top of the sensor's range (DWD 75,000 m, SMHI 75,000, 99,999 and, at one 1 minute station, 50,000 m,
  FMI 50,000 m, NWS and NOAA GHCN 16,093 m, ECCC 24.1 km, Météo-France synop 60,000 to 80,000 m): a lower bound, not
  the visibility. A visibility at that value says only that it was at least that far;
- a radiation of 0 at night; a long wave radiation balance that is negative (DWD DMO `radl3`);
- a snow depth below 0 that no source documents: MeteoSwiss' automatic gauge `htoautd0` reads -1 to -5 cm on warm
  days (11 % of the hours at PLF), a spread around a bare ground and not a code;
- a sunshine duration longer than the daylight but within its span plus 5 % (above that `range` rejects it; a station's sensor known to be stuck, RMI, is `stuck`'s).
