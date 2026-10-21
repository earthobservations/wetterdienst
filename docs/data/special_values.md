# Special values

The sources do not write a missing reading, a calm, a trace of rain or an obscured sky the same way: one writes
`-999`, the next `---`, a third a 0 that looks like a reading. `wetterdienst` reads each source's way to one rule per
situation, so that the same situation comes back the same from every provider. This page lists the rules and the
providers that apply them. Where the library maps what the source wrote, the value keeps that text as the last token
of `quality_flags`, `raw:<text>` ([quality flags](quality-flags.md) lists the tokens provider by provider); the long
shape drops the rows without a value by default, so the token shows with `drop_nulls=False` or in the wide shape.

The tests hold the rules to what each source writes: `tests/provider/value_stubs.py` serves a reading and the
special values of every provider through its own reader, and `tests/provider/test_value_stubs.py` checks that no
sentinel reaches the values, that each keeps its `raw:` token, and that no provider returns a wind direction of 0
beside a speed of 0.

## Wind

| situation | rule | providers |
| --- | --- | --- |
| a direction of 0 beside a speed of 0 of the same reading (a calm) | null, `raw:0` (as the source writes it, `raw:0.0`) | every provider whose source writes one: AEMET (hourly), DMI, DWD observation (10 minute and hourly `wind`, 10 minute `wind_extreme` beside the gust, the urban `wind`, subdaily `wind` beside a force of 0), DWD POI, ECCC (hourly; daily beside a gust of 0), FMI, Geosphere, KNMI (hourly), Met Office (hourly), Météo-France observation and synop, MeteoSwiss, NOAA GHCN hourly, NWS, SMHI |
| a direction of 0 beside a speed above 0 | the value 0, as a source may write north as 0 too; most write it 360 | the same providers. Geosphere, KNMI (hourly) and NWS write their 0 beside a speed of 0 only (every 0 of the files read), and null every 0 of the column; KNMI's speed of the direction's 10 minutes (`FF`) is not served |
| a direction of 0 beside a speed the source does not give | the value 0 | the providers that read the speed beside the direction, all of the first row but Geosphere, KNMI and NWS |
| a 0 the source names a code of a variable wind as well | null, `raw:0` | DWD observation hourly `wind_synoptic` ("Windrichtung uml.,windstill DD=00") |
| a code of a variable or indeterminate direction | null, with the code | DWD observation `990`, KNMI `990`, Météo-France observation `999` and daily `400`, Météo-France synop `400`, AEMET daily `99` (calm or variable), NOAA GHCN hourly `999`, NWS `VRB` (null from the source) |
| north | 360, as written; a 0 beside a wind that blows stays 0 | all |
| a direction on a scale of points | read in degrees: DWD subdaily (32 points, 11.25 degrees each), IPMA (8 points, 45 degrees; its code 0, "no direction", is null with `raw:0`) | DWD subdaily, IPMA |
| a direction in tens of degrees | read in degrees | AEMET daily, ECCC |

DWD observation hourly `urban_wind` writes a 0 that is neither a calm nor north (the six 10 minute directions of
the hour are spread over the compass, GH-2809) and never beside a speed of 0; it is null, with `raw:0`, whatever
the speed.

## Precipitation and snow

| situation | rule | providers |
| --- | --- | --- |
| a trace (less than the gauge reads), written as a code in the value | 0.0, `raw:<code>` | AEMET `Ip`, KNMI `-1` (also a trace of sunshine), Météo-France synop `-0.1` |
| a trace written as 0 and flagged | 0.0, the source's flag | CHMI `element:T`, ECCC `T`, NOAA GHCN `measurement:T`, NWS (`P0000`, quality `C`) |
| a trace written as a plain 0 | 0.0 | Geosphere daily ("0=weniger als 1/10 mm"), Météo-France observation |
| no precipitation or no snow written as a code | 0.0, `raw:<code>` | FMI `-1.0`, Geosphere daily `-1.0` and `-1`, MET Norway Frost `-1` (snow depth) |
| no precipitation written as a status | 0, the status as the quality flag | IMGW meteorology `9` |
| a dry hour the source leaves out | null | NWS (no precipitation group in the METAR), NOAA GHCN hourly (an empty cell) |

## Cloud cover

| situation | rule | providers |
| --- | --- | --- |
| the sky obscured or not visible | null, `raw:<code>`, never an amount (9 oktas would read 1.125) | DWD observation `-1`, DWD POI `113` and `126`, KNMI `9`, Met Office `9`, Météo-France observation `9`, Météo-France synop `101`, MET Norway Frost `9` and `-3`, SMHI `113` |
| an obscured sky the source writes as no value | null, without a token | LHMT |
| oktas and percent | a fraction of the sky: oktas are divided by 8, a percent by 100 as the source writes it (Météo-France synop writes 1 okta as 10 %, the others as 12 or 13 %) | all |

## Missing values and texts

| situation | rule | providers |
| --- | --- | --- |
| a missing-value sentinel (`-999`, `-9999`, `-99.0`, `-99.9`, `9999`, `99.9`, `99999.999`, `-None`, `---`, `-`, `NA`, `NaN`) | null, `raw:<sentinel>` | DWD observation and derived, DWD mosmix, dmo, POI and swsmos, FMI, IMGW hydrology, IPMA, KNMI, Met Office, NOAA GHCN hourly |
| an empty field or a JSON null | null, without a token | every other provider |
| a value cell that is a text and no number | null; the core logs one debug line per frame with the count, and a provider that reads text keeps it as `raw:<text>` | all; `raw:` in AEMET, DWD POI, swsmos, mosmix and dmo, FMI, Met Office, Météo-France |
| `nan` or `inf` written as text, and a number padded with blanks | null and counted; the padded number is read | all (the core) |
| a value outside the physical range of its parameter that is no code | null, `raw:<number>` | DMI, RMI |
| a sensor stuck or dead over a period | null, `raw:<value>` | DWD observation (the pressure of a station without a barometer), RMI (sunshine) |
| a value the source flags missing | null, the flag | CHMI `4`, EA `Missing`, ECCC `M`, IMGW meteorology `8` |
| a value the source flags suspect or invalid | the value, with the flag | all that flag (DMI `validity:false`, RMI, GHCN, Met Office, Frost, SMHI `Y`, NWS) |
| a gust the source does not report (below 31 km/h) | null, `raw:0` | ECCC daily |

## As published

These values are returned as the source writes them, with no token:

- visibility at the top of the sensor's range (DWD 75,000 m, SMHI 75,000 and 99,999 m, FMI 50,000 m, NWS and NOAA
  GHCN 16,093 m, ECCC 24.1 km, Météo-France synop 60,000 to 80,000 m): a lower bound, not the visibility;
- a relative humidity of 100 % and above, up to the 130 % above which DMI and RMI null it;
- a radiation of 0 at night; a net radiation that is negative (DWD DMO);
- a snow depth below 0 that no source documents (MeteoSwiss `htoautd0`, -1 to -5 cm on warm days);
- a sunshine duration longer than the day, unless a station's sensor is known to be stuck (RMI).
