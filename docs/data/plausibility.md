# Plausibility checks

Some numbers a source publishes are no readings, though they are no code: 4021 °C for a daily maximum, 909.5 hPa at a
station at sea level, a sensor that held one value for a month, a road surface 30 K above the air at night. A check
that finds one judges it, and what happens to the value is yours to choose, **per kind of check**. The judging is the
core's, not the reader's: a reader decodes what its source writes as a code and hands the numbers over in the source's
unit, and the library judges them all in one place, in one unit per quantity ([how](#how-the-core-judges)):

- **hard**: the value is null (for `floor`, the floor of its quantity) and the number the source wrote stays in
  `quality_flags` as `rejected:<check>,raw:<number>`;
- **soft**: the value is kept and `quality_flags` says `suspect:<check>`.

There is no mode that skips a check. A soft check already keeps the value, and the flag keeps the judgement visible.

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
   beside a road surface, the dew point beside a humidity, the air of the road's run rule): a verdict on a parameter
   that is cut afterwards would never be seen, so the others are not merged, converted or judged.
3. Those parameters are converted to the canonical unit of their unit type (°C, hPa, m/s, mm, J/cm², a fraction as a
   decimal, seconds), without rounding. The bounds are therefore written once per quantity and not once per source
   and unit, and a bound does not depend on the unit you ask for.
4. The five checks judge the frame in canonical units. A check that compares two parameters (a road surface and the air
   of its minute) reads both from the frame of the station at the same timestamp, so such a dataset is collected whole.
5. The frame is cut to the parameters you asked for and converted to the unit you asked for, rounded once.

The bounds are one table, by canonical name and by resolution where the quantity grows with the span
(`wetterdienst.model.plausibility_ranges`), with the sources of the narrower ones noted beside them. What only a provider
knows it hands the core as data, through one hook: the stations without frost, the periods in which one sensor of one
station did not work, the relation of a road surface to the air at night, and the bounds a network holds narrower than the
table ([contributing a provider](../contribution/services.md)).

A judged value's `raw:` is the text the source wrote for it (`raw:-0.80`), in the unit of the source: the reader hands
the text over beside the value and the core writes it. Where a source gives the core only a number, the number is
written as short as it goes (`4021.0` as `4021`).

## The checks

| check | judges | default | rule and bounds |
| --- | --- | --- | --- |
| `range` | a reading outside the physical range of its parameter | hard | One table of bounds by canonical parameter and resolution (the rain of a minute and of a day differ), in the canonical unit, and generous: each rests on a record with room above it, so that a value that is only odd stays. A network holds a quantity narrower where it knows its source better; the table says why beside the bound. See each provider's page, e.g. [DMI](provider/dmi/observation/index.md), [RMI](provider/rmi/observation/index.md), [DWD road](provider/dwd/road/15_minutes.md). DWD road holds a relative humidity below 1 % to this check as well: a failed hygrometer writes a value inside every range, and 1 % is far below any humidity the air of Germany reaches |
| `elevation` | a station pressure the barometric formula does not expect at the station's elevation | hard | The pressure of the international standard atmosphere at the elevation of the station in the station list, 75 hPa either way (about 650 m of height). The world-wide bounds (500 to 1090 hPa) let through a P0 mistyped by a digit at a station near sea level (909.5 hPa at 48 m) or the pressure of another height (968.6 hPa at the Zugspitze, 2,956 m, where 705 are expected). A station without an elevation, or one outside -500 to 9,000 m, is not judged. 75 hPa is wide enough for the deep lows of Dumont d'Urville (938 hPa at 43 m, where 1,008 are expected) |
| `stuck` | a sensor that held one value over a period it should not have | **soft** | DWD observation: a run of consecutive readings of one value of the station pressure (`pressure_air_site`, `pressure_air_site_mean`): 72 hourly readings, 5 days, 36 readings at 10 minutes (HadISD and ECA&D, see [the limits](#the-limit-of-a-run)); a station without a barometer writes its constant in every row. DWD road: 24 readings or more (6 h) of one value of the air, the dew point or the road surface temperature, a gap longer than four times the station's usual one ending the run, melting ice excepted. RMI: the sunshine of station 6477 in the periods its sensor was stuck or dead |
| `consistency` | a reading that another parameter of the same file contradicts | hard | DWD road: a road surface more than 20 K above the air of the same minute with the sun more than 6 degrees below the horizon. Météo-France: the humidity of an hour whose dew point lies below 0 °C at a station without frost (the same hygrometer), and a `tn12` that is the text of the `tx12` beside it (a copy, no minimum) |
| `floor` | a model value a little below the floor of its quantity | hard | DWD DMO: ICON writes -0.02 mm for the precipitation of an hour, down to -0.10, and the radiation of a night below 0. **hard sets the floor**, 0.0, and keeps the number; soft keeps the number as the value |

`stuck` is soft by default because it judges a series and not a value: identical readings are a sign of a stuck sensor
and no proof, and what is found depends on what was read, which differs by network (see the caveats). Every other check
is hard, which reproduces what the library did before the modes existed.

### The limit of a run

A barometer that writes one pressure for hours reflects the station and not the weather. The limit is the number of
consecutive readings of one value that is taken for it, per resolution, from the research for
[GH-3681](https://github.com/earthobservations/wetterdienst/issues/3681) (section 4.1, persistence of station and sea
level pressure):

| resolution | readings | source |
| --- | --- | --- |
| hourly | 72 | HadISD (Dunn et al. 2012, Climate of the Past 8, 1649-1679, table 4): a straight repeat of 72 values of the sea level pressure at a resolution of 0.1 hPa, which DWD's pressures have |
| daily | 5 | ECA&D (KNMI, Algorithm Theoretical Basis Document v11, 2021, section 3): the daily pressure may not be exactly the same 5 days in a row |
| 10 minutes | 36 (6 hours) | **derived, not published**: no source publishes a count at 10 minutes; the research derives 36 readings (6 hours) from the hourly one and marks it as its own derivation |

Sub-daily, monthly and annual values have no source and are not judged. The run is judged in the series the core is
handed, after the periods are merged, so a station whose historical file is constant and whose recent file is not is
flagged for the stretch that is.

A reading that is missing does not break a run: a null inside a short stretch is skipped, and the equal values on both
sides are one run. A **gap** does: where two readings are more than four times the interval of the resolution apart
(more than 4 hours at hourly, 40 minutes at 10 minutes, 4 days at daily), the run ends there, as the road rule's does. A
month of `-999` between two readings of 997.3 hPa is two stretches and not one.

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

Options(plausibility="soft")  # all five checks soft, the same as listing them
Options(plausibility={"range": "hard", "elevation": "soft", "stuck": "soft", "consistency": "soft", "floor": "soft"})
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
`plausibility_consistency` and `plausibility_floor` on `values`; `/api/settings` reports the modes in effect. A value
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

- One token per kind, the checks joined with `+` in alphabetical order. A value that a hard check rejected carries the
  hard checks alone: it is null, and `rejected:` says why. A value that only soft checks found is `suspect:` of all of
  them.
- A soft verdict has no `raw:`: the value is the number the source wrote, after the unit conversion as any other.
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

The table is what the core is told to judge: a network that is in no row judges no value, and extending the checks to the
networks that have none is a follow-up. A dataset is `resolution/dataset`.

<!-- coverage:start -->

| check | network | datasets |
| --- | --- | --- |
| `range` | `dmi/observation` | `hourly/data`, `daily/data`, `monthly/data`, `annual/data` |
| `range` | `dwd/observation` | `10_minutes/temperature_air`, `10_minutes/urban_pressure`, `10_minutes/urban_wind`, `10_minutes/urban_wind_extreme`, `10_minutes/wind`, `10_minutes/wind_extreme`, `hourly/moisture`, `hourly/pressure`, `hourly/urban_pressure`, `hourly/urban_wind`, `hourly/wind`, `hourly/wind_extreme`, `hourly/wind_synoptic`, `subdaily/pressure`, `subdaily/wind_extreme`, `daily/climate_summary`, `monthly/climate_summary`, `annual/climate_summary` |
| `range` | `dwd/road` | `15_minutes/data` |
| `range` | `meteofrance/observation` | `hourly/core`, `hourly/others`, `daily/core`, `monthly/data` |
| `range` | `meteofrance/synop` | `subdaily/data` |
| `range` | `rmi/observation` | `10_minutes/data`, `hourly/data`, `daily/data` |
| `elevation` | `dwd/observation` | `10_minutes/temperature_air`, `10_minutes/urban_pressure`, `hourly/moisture`, `hourly/pressure`, `hourly/urban_pressure`, `subdaily/pressure`, `daily/climate_summary` |
| `elevation` | `meteofrance/synop` | `subdaily/data` |
| `stuck` | `dwd/observation` | `10_minutes/temperature_air`, `10_minutes/urban_pressure`, `hourly/moisture`, `hourly/pressure`, `hourly/urban_pressure`, `daily/climate_summary` |
| `stuck` | `dwd/road` | `15_minutes/data` |
| `stuck` | `rmi/observation` | `10_minutes/data`, `hourly/data`, `daily/data` |
| `consistency` | `dwd/road` | `15_minutes/data` |
| `consistency` | `meteofrance/observation` | `hourly/others` |
| `consistency` | `meteofrance/synop` | `subdaily/data` |
| `floor` | `dwd/dmo` | `hourly/icon`, `hourly/icon_eu` |

<!-- coverage:end -->

Within a dataset a check covers the parameters its rule names, not every parameter: `range` of DWD observation the wind
speeds and the pressures, `elevation` the `pressure_air_site` and `pressure_air_site_mean`, `stuck` the
`pressure_air_site` and `pressure_air_site_mean`. The provider pages and [special values](special_values.md) list them.

What no check covers, and why:

- **A second parameter in another dataset.** A check never triggers a download. A consistency check reads its second
  parameter from the frame of the station and the same timestamp: the dataset is collected whole, and the neighbour of a
  relation is kept for the check even where nobody asked for it, and dropped after judging. Where the second parameter
  lives in another dataset, the check does not run. DWD observation holds its hourly `temperature_air` and `moisture` in
  two datasets, so the humidity of one is not held to the dew point of the other.
- **Networks with no check yet.** Most networks judge nothing: a number outside every range stays as the source wrote
  it. The sources' own "erroneous" flags (GHCN `QFLAG`, Frost `7`, GHCNh `3`, ...) are the source's and are returned as
  its flags, not as a check.

## Caveats

- **What `stuck` finds depends on what was read, which differs by network.** The check judges a series and not a value,
  which is why it is soft by default: the value stays and you decide.
  - *DWD road*: the verdict depends on the window of the request, because the reader cuts to the window. A run of
    identical values that crosses the start of the request is only found when the window covers enough of it, and a
    request for an hour has fewer readings than the 24 that mark a run: the same day can answer differently for a
    different window. For this reason the road surface rule of `consistency` does not use the stuck verdict.
  - *DWD observation*: the verdict depends on the periods and files read (historical, recent, now), not on the window:
    the core judges the merged series before the window is cut, so the same file answers the same for any window inside
    it. A request for the recent period alone sees the runs of the recent file alone. A constant stretch below the limit
    of a run (71 hourly readings, 4 days) is not flagged, where the earlier rule on a whole file of at most three values
    flagged it whatever its length.
  - *RMI*: the periods are fixed dates of one station (6477), so the verdict depends on neither.
- **`elevation` uses the station list's current elevation for every period.** A station that was moved by 500 m or more
  keeps the readings of its other site only while they lie within the range. DWD's historical outliers were checked
  against the station list and are bad readings, not station moves.
- **A check stands aside where the second value is missing.** A consistency check that finds no second value for a row
  (null, not a number, outside its own range, or marked suspect by the source's own flag) returns the value unflagged.
- **Every check judges the same number.** A pressure of 1093.3 hPa at 100 m is outside the range and outside the
  elevation: `rejected:elevation+range,raw:1093.3` with both hard, and `suspect:elevation+range` with both soft.
- **A hard check can only judge a number it can read.** A text that is no number (`mq`, `---`) and a NaN or an infinity
  are no judgement: they are null with their text, as a code is, in both modes.

## Soft mode and the rest of the request

- **Interpolation, summary and climate stripes** always leave out a `suspect` value, whatever the mode: a number a check
  finds implausible has no place in a weighted mean, a nearest station's answer or a year of stripes (which shows as a
  year without data). The mode changes only what a station's own values show. The values stay rows with no value, as a
  rejected one does.
- **`skip_empty`** judges a station by its unflagged values alone: a value flagged `suspect` is no coverage, so a station
  with only such values is skipped. For the checks that used to null (`range`, `elevation`, `consistency`, `floor`, and
  `stuck` of DWD observation and RMI) this is as before. For `stuck` of DWD road, which used to keep the value with
  the flag `1` and count it, it is a change: a road station with long stuck runs can be skipped where it was kept.
- **A rejected value carries only the hard verdict.** Where a hard check rejects a value and a soft one also finds it
  suspect, the value is null and the token is `rejected:<hard checks>,raw:<number>`; the soft check is not listed.
- **`drop_nulls=True`** keeps dropping the rows of hard-rejected values, as it drops any null. A soft row has a value and
  stays. `drop_nulls=False`, or the wide shape, shows the rejected rows with their flags.
- **Unit conversion** acts on a soft value as on any other: the number is converted, and the flag stays. The `raw:` of a
  hard verdict is the text the source wrote, in the unit of the source (DMI's radiation is the megajoules it wrote).
- **The wide shape** has the flag beside each value, in `<parameter>_quality_flags`, with the same tokens.
- **Physical ranges in tests.** A value outside its range that carries `suspect:` is kept on purpose, so the range check
  of the provider tests accepts it.
