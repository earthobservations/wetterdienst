# Plausibility checks

Some numbers a source publishes are no readings, though they are no code: 4021 °C for a daily maximum, 909.5 hPa at a
station at sea level, a sensor that held one value for a month, a road surface 30 K above the air at night. A reader
that finds one judges it, and what happens to the value is yours to choose, **per kind of check**:

- **hard**: the value is null (for `floor`, the floor of its quantity) and the number the source wrote stays in
  `quality_flags` as `rejected:<check>,raw:<number>`;
- **soft**: the value is kept and `quality_flags` says `suspect:<check>`.

There is no mode that skips a check. A soft check already keeps the value, and the flag keeps the judgement visible.

A check judges. What a source **documents** is no judgement and has no mode: `-999`, `---`, `NaN`, AEMET's `Ip` trace,
FMI's `-1.0` for no snow, a direction of 0 beside a speed of 0 (a calm), the `-0.1` trace of DMI. These are the source's
meanings, not ours, and a soft `-999` would return -999 as a number. They are decoded as before, with `raw:` alone, in
both modes ([special values](special_values.md)).

The tests hold this page to the readers: `tests/test_docs_plausibility.py` compares the table below with the rules the
providers declare, and `tests/provider/test_plausibility_modes.py` runs every stubbed source with every check soft.

## The checks

| check | judges | default | rule and bounds |
| --- | --- | --- | --- |
| `range` | a reading outside the physical range of its parameter | hard | The bounds are the reader's, per resolution where the quantity grows with the span (the rain of a minute and of a day), in the unit of the source, and generous: each rests on a record with room above it, so that a value that is only odd stays. See each provider's page, e.g. [DMI](provider/dmi/observation/index.md), [RMI](provider/rmi/observation/index.md), [DWD road](provider/dwd/road/15_minutes.md). DWD road holds a relative humidity below 1 % to this check as well: a failed hygrometer writes a value inside every range, and 1 % is far below any humidity the air of Germany reaches |
| `elevation` | a station pressure the barometric formula does not expect at the station's elevation | hard | The pressure of the international standard atmosphere at the elevation of the station in the station list, 75 hPa either way (about 650 m of height). The world-wide bounds (500 to 1090 hPa) let through a P0 mistyped by a digit at a station near sea level (909.5 hPa at 48 m) or the pressure of another height (968.6 hPa at the Zugspitze, 2,956 m, where 705 are expected). A station without an elevation, or one outside -500 to 9,000 m, is not judged. 75 hPa is wide enough for the deep lows of Dumont d'Urville (938 hPa at 43 m, where 1,008 are expected) |
| `stuck` | a sensor that held one value over a period it should not have | **soft** | DWD observation: a file of the hourly `moisture` dataset with 500 readings or more and at most three distinct values in `pressure_air_site` (a station without a barometer writes its constant in every row). DWD road: 24 readings or more (6 h) of one value of the air, the dew point or the road surface temperature, a gap longer than four times the station's usual one ending the run, melting ice excepted. RMI: the sunshine of station 6477 in the periods its sensor was stuck or dead |
| `consistency` | a reading that another parameter of the same file contradicts | hard | DWD road: a road surface more than 20 K above the air of the same minute with the sun more than 6 degrees below the horizon. Météo-France: the humidity of an hour whose dew point lies below 0 °C at a station without frost (the same hygrometer), and a `tn12` that is the text of the `tx12` beside it (a copy, no minimum) |
| `floor` | a model value a little below the floor of its quantity | hard | DWD DMO: ICON writes -0.02 mm for the precipitation of an hour, down to -0.10, and the radiation of a night below 0. **hard sets the floor**, 0.0, and keeps the number; soft keeps the number as the value |

`stuck` is soft by default because its verdict depends on the window of the request (see the caveats). Every other
check is hard, which reproduces what the library did before the modes existed.

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

The table is what the readers declare: a network that is in no row judges no value, and extending the checks to the
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
| `stuck` | `dwd/observation` | `hourly/moisture` |
| `stuck` | `dwd/road` | `15_minutes/data` |
| `stuck` | `rmi/observation` | `10_minutes/data`, `hourly/data`, `daily/data` |
| `consistency` | `dwd/road` | `15_minutes/data` |
| `consistency` | `meteofrance/observation` | `hourly/others` |
| `consistency` | `meteofrance/synop` | `subdaily/data` |
| `floor` | `dwd/dmo` | `hourly/icon`, `hourly/icon_eu` |

<!-- coverage:end -->

Within a dataset a check covers the parameters its rule names, not every parameter: `range` of DWD observation the wind
speeds and the pressures, `elevation` the `pressure_air_site` and `pressure_air_site_mean`, `stuck` the
`pressure_air_site` of `hourly/moisture`. The provider pages and [special values](special_values.md) list them.

What no check covers, and why:

- **A second parameter in another file or dataset.** A check never triggers a download. A consistency check reads its
  second parameter only from the file already being read: where that parameter is not requested it is parsed from the
  bytes already downloaded, used and dropped before the result is built (Météo-France reads `TD` for the humidity this
  way; a DWD road dataset is one file). Where the second parameter lives in another file, the check does not run. DWD
  observation holds its hourly `temperature_air` and `moisture` in two files, so the humidity of one is not held to the
  dew point of the other.
- **Networks with no check yet.** Most networks judge nothing: a number outside every range stays as the source wrote
  it. The sources' own "erroneous" flags (GHCN `QFLAG`, Frost `7`, GHCNh `3`, ...) are the source's and are returned as
  its flags, not as a check.

## Caveats

- **`stuck` depends on the window of the request.** A run of identical values that crosses the start of the request is
  only found when the window covers enough of it, and a request for an hour of the road network has fewer readings than
  the 24 that mark a run. The same day can answer differently for a different window. For this reason the road surface
  rule of `consistency` does not use the stuck verdict, and `stuck` is soft by default: the value stays and you decide.
  DWD observation judges a file as it is, so its verdict follows the files of the periods read.
- **`elevation` uses the station list's current elevation for every period.** A station that was moved by 500 m or more
  keeps the readings of its other site only while they lie within the range. DWD's historical outliers were checked
  against the station list and are bad readings, not station moves.
- **A check stands aside where the second value is missing.** A consistency check that finds no second value for a row
  (null, not a number, outside its own range, or marked suspect by the source's own flag) returns the value unflagged.
- **A reader that judges in steps does not show a value an earlier step rejected to the next.** DWD observation checks
  the range while it parses and the elevation after: a pressure of 1093.3 hPa at 100 m is `rejected:range,raw:1093.3`
  with both hard, and `suspect:elevation+range` with both soft, as nothing was rejected before the second check.
- **A hard check can only judge a number it can read.** A text that is no number (`mq`, `---`) and a NaN or an infinity
  are no judgement: they are null with their text, as a code is, in both modes.

## Soft mode and the rest of the request

- **Interpolation and summary** always leave out a `suspect` value, whatever the mode: a number a check finds
  implausible has no place in a weighted mean or a nearest station's answer. The mode changes only what a station's own
  values show. The values stay rows with no value, as a rejected one does.
- **`drop_nulls=True`** keeps dropping the rows of hard-rejected values, as it drops any null. A soft row has a value and
  stays. `drop_nulls=False`, or the wide shape, shows the rejected rows with their flags.
- **Unit conversion** acts on a soft value as on any other: the number is converted, and the flag stays. The `raw:` of a
  hard verdict is the number as the source wrote it, in the unit of the source.
- **The wide shape** has the flag beside each value, in `<parameter>_quality_flags`, with the same tokens.
- **Physical ranges in tests.** A value outside its range that carries `suspect:` is kept on purpose, so the range check
  of the provider tests accepts it.
