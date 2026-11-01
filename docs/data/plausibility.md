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

The bounds are one table for every provider, by canonical name and by resolution where the quantity grows with the
span (`wetterdienst.model.plausibility_ranges`, [below](#the-table-of-ranges)). What only a provider knows it hands the
core as data, through one hook: the stations without frost, the periods in which one sensor of one station did not work,
the relation of a road surface to the air at night, and DWD road's humidity floor
([contributing a provider](../contribution/services.md)).

A judged value's `raw:` is the text the source wrote for it (`raw:-0.80`), in the unit of the source: the reader hands
the text over beside the value and the core writes it. Where a source gives the core only a number, the number is
written as short as it goes (`4021.0` as `4021`).

## The checks

| check | judges | default | rule and bounds |
| --- | --- | --- | --- |
| `range` | a reading outside the physical range of its parameter | hard | One table of bounds for every network, by canonical parameter and resolution (the rain of a minute and of a day differ), in the canonical unit, and generous: each rests on a record with room above it, so that a value that is only odd stays ([the table](#the-table-of-ranges)). No network has bounds of its own in the table; a provider's `Bound` rule can only narrow it (Météo-France: no air below 0 °C at a station without frost). DWD road holds a relative humidity below 1 % to this check as well: a failed hygrometer writes a value inside every range, and 1 % is far below any humidity the air of Germany reaches |
| `elevation` | a station pressure the standard atmosphere does not allow at the station's elevation | hard | In every network that serves a station pressure (`pressure_air_site`, `_mean`, `_min`, `_max`), for each station of the list that has an elevation. Against the pressure of the international standard atmosphere at that elevation, from **870/1013.25 of it** (143 hPa below at sea level: the lowest pressure on record, 870 hPa in Typhoon Tip, as a share of the standard atmosphere) to **75 hPa above it** (the 1,083.8 hPa of Agata, 261 m, the highest sea level pressure of a low station, reduced to the station with the cold column of that day lies 59 to 64 hPa above the standard atmosphere there, the 1,089.1 hPa of Tosontsengel, 1,725 m, 14 to 40: a derivation of GH-3681). The world-wide bounds (300 to 1100 hPa) let through the pressure of another height (968.6 hPa at the Zugspitze, 2,956 m, where 705 are expected) and a P0 mistyped by a digit above the standard atmosphere (1093.3 hPa at 48 m, 85.8 above). A station without an elevation, or one outside -500 to 9,000 m, is not judged. So is a `noaa/ghcn` station at 0.0 m: its lists write 0.0 for stations they know no elevation of (the daily one BRM00083566, inland at about 827 m), and 54 of the 271 at 0.0 in the hourly one stand between 150 and 4,329 m (CHM00052940 reads 500.2 to 998 hPa), while the 0.0 of the lists read (DWD, ECCC, IMGW, Météo-France) is a coast. The margin below keeps Hurricane Irma (917.4 hPa at 10:00 and 936.0 hPa an hour earlier at St-Barthélemy, 3 m, 2017-09-06, quality code 1) and the deep lows of Dumont d'Urville (938 hPa at 43 m, where 1,008 are expected); it lets 3 of the 19 readings of DWD's hourly station pressure beyond 75 hPa of the standard atmosphere (the research of GH-3681, over Berlin-Tempelhof, List auf Sylt and the Zugspitze) pass: 909.5, 910.1 and 908.5 hPa, 98 to 102 hPa below, which the step check planned in [GH-3681](https://github.com/earthobservations/wetterdienst/issues/3681) is to catch |
| `stuck` | a sensor that held one value over a period it should not have | **soft** | DWD observation: a run of consecutive readings of one value of the station pressure (`pressure_air_site`, `pressure_air_site_mean`): 72 hourly readings, 5 days, 36 readings at 10 minutes (HadISD and ECA&D, see [the limits](#the-limit-of-a-run)); a station without a barometer writes its constant in every row. DWD road: 24 readings or more (6 h) of one value of the air, the dew point or the road surface temperature, a gap longer than four times the station's usual one ending the run, melting ice excepted. RMI: the sunshine of station 6477 in the periods its sensor was stuck or dead |
| `consistency` | a reading that another parameter of the same file contradicts | hard | DWD road: a road surface more than 20 K above the air of the same minute with the sun more than 6 degrees below the horizon, the air counting only where it passed `range` and is not marked suspect by DWD's own flag. Météo-France: the humidity of an hour whose dew point lies below 0 °C at a station without frost (the same hygrometer), and a `tn12` that is the text of the `tx12` beside it (a copy, no minimum) |
| `floor` | a model value a little below the floor of its quantity | hard | DWD DMO: ICON writes -0.02 mm for the precipitation of an hour, down to -0.10, and the radiation of a night below 0. **hard sets the floor**, 0.0, and keeps the number; soft keeps the number as the value |

`stuck` is soft by default because it judges a series and not a value: identical readings are a sign of a stuck sensor
and no proof, and what is found depends on what was read, which differs by network (see the caveats). Every other check
is hard, which is what the library did for the networks it judged before the modes existed; since GH-3681 `range` and
`elevation` judge every network.

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
| rain in 1 minute | 0 to 40 mm | WMO: 31.2 mm (Unionville, 1956) |
| rain in 5 to 60 minutes | 0 to 350 mm | WMO: 305 mm in 60 minutes (Holt, 1947) |
| rain in up to 12 hours | 0 to 1,150 mm | WMO: 1,144 mm in 12 hours (Foc-Foc, 1966) |
| rain in up to 24 hours | 0 to 1,850 mm | WMO: 1,825 mm in 24 hours (Foc-Foc, 1966) |
| rain in a month | 0 to 10,000 mm | 9,300 mm in July 1861 (Cherrapunji; Bureau of Meteorology, a secondary source) |
| rain in a year | 0 to 30,000 mm | WMO: 26,470 mm in 12 months (Cherrapunji, 1860/61) |
| relative humidity | 0 to 100 % | definition |
| snow cover | 0 to 100 % | definition |
| vapour pressure deficit | -10 to 200 hPa | the saturation pressure at the 60 °C of the air bound, 199 hPa by Magnus; DMI writes some hours and days a little below 0 (-3 hPa at 06193, 2025-07-25), so the lower end leaves them |
| new snow in a day, in a month | 0 to 200 cm, 0 to 6,200 cm | Durre et al. 192.5 cm; a month (the sums of the daily depths, ECCC's normal snowfall) is that times 31 |
| sunshine, precipitation and leaf wetness duration | 0 to the span + 5 % | definition, with the margin of ECA&D for the length of the day |
| short-wave irradiance | 0 to 2,000 W/m² | WMO-No. 488 holds 0 to 1,600, BSRN 2,141 at the zenith |
| snow depth | -10 to 1,200 cm | ISD 1,200 cm, Durre et al. 1,146 cm; a gauge reads a few centimetres below 0 |
| water temperature | -5 to 50 °C | MADIS holds the sea surface to -2 to 40 °C |
| everything else with no record | at least 0 | definition |

Quantities that are **derived** from others (wind chill, humidex, evaporation, the net radiation of DMO and the forecast
errors `error_absolute_*`), codes and flags, and the **hydrology gauges** (stage, discharge, groundwater level, distance
to the gauge, flow speed and the direction of the current, whose unit the source does not explain: a datum of their own, and a tidal river runs backwards) have no bound.

**Shangdi.** The one documented exceedance is Shangdi (Inner Mongolia, 1975-08-01): 401 mm in 60 minutes, which is in
the lists of the Bureau of Meteorology and the NWS but not in the WMO table, so the bound of an hour is 350 mm and the
reading would be null.

**The WMO guides give no fixed table.** WMO-No. 488 (Guide to the Global Observing System, Appendix VI.2) sets limits for
the 1-minute values of an automatic weather station only, and some of them cut records of the Archive (a wind speed of
75 m/s against the 95 m/s of Typhoon Nancy); the tests of WMO-No. 1269 (Guidelines on Surface Station Data Quality
Control and Quality Assurance for Climate Applications, 2021) are relative to the station (percentiles of its own last 30
years, or its climatological extremes); and the current WMO-No. 305 (Guide to the WMO Integrated Processing and
Prediction System) has no chapter on quality control, the gross limits quoted from it come from the withdrawn edition of
1993. The table is compared with these, not taken from them.

### What a table for the world cannot catch

A bound that holds for every provider cannot see a defect that lies inside it. These stay, as the source wrote them:

- **Totals that are wrong and plausible.** DMI marks `validity:false` on a daily rain of 989 mm (04339, 2011-07-25), a
  monthly 3,229.9 mm (2012-10), a yearly 9,574.3 and 6,026.5 mm (2014, 2015) and a yearly 3,253.4 mm, all inside the
  ranges: no range separates the last from the 3,291.3 mm of a year that DMI validated at 04390. They are for the planned
  `source` check, which will use the source's own verdict ([GH-3677](https://github.com/earthobservations/wetterdienst/issues/3677)).
  DMI's 1,978 mm of a day and 17,802 mm of a month are above the bounds and are null.
- **A gust of 81.5 m/s in Belgium** (RMI, station 6414, 2003-10-09, `validated: false`): inside the 115 m/s of the
  world, and not a reading. It is for the step check of [GH-3681](https://github.com/earthobservations/wetterdienst/issues/3681);
  the 445.3 and 569.7 m/s of the hourly layer are above the bound and are null.
- **A station pressure keyed in by a digit, between the margins of `elevation`**: 909.5, 910.1 and 908.5 hPa at DWD's
  Berlin-Tempelhof and List auf Sylt, 98 to 102 hPa under the standard atmosphere, as far as the eye of a hurricane
  (917.4 hPa at 3 m). Steps of 90 to 129 hPa in an hour, against the 43 of Irma, tell them; that is the step check, too.
- **The stopped sensors of DWD road at -75.00 °C** (station group KM): inside the -90 °C of the air record, so no
  bound finds them. They are a code of the source and the reader of DWD road maps them to null, keeping `raw:198.15`.
  DWD road keeps one narrow rule of its own beside it: a humidity below 1 % is no reading (a `Bound`). The `-30.00` and
  `-25.00` of other stopped sensors are readings a German winter reaches, and stay with the check `stuck`.
- **A sensor stuck at a plausible value, a sunshine of 1,440 minutes on a day of December** (RMI, 6477) and other
  quantities that look like data: `stuck` and the rules of a provider, not the table.

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
nulls that carry a code the source wrote (`raw:` alone), `rejected-by-plausibility` the nulls a hard check made
(`rejected:` before `raw:`), with the count per check in its message. A value that two checks rejected is one value,
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

The table is what the core is told to judge: a network that is in no row judges no value. A dataset is
`resolution/dataset`; `*` stands for every dataset of the network that has a parameter the check judges, which is how
`range` and `elevation` run on every network that has one.

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
| `stuck` | `dwd/observation` | `10_minutes/temperature_air`, `10_minutes/urban_pressure`, `hourly/moisture`, `hourly/pressure`, `hourly/urban_pressure`, `daily/climate_summary` |
| `stuck` | `dwd/road` | `15_minutes/data` |
| `stuck` | `rmi/observation` | `10_minutes/data`, `hourly/data`, `daily/data` |
| `consistency` | `dwd/road` | `15_minutes/data` |
| `consistency` | `meteofrance/observation` | `hourly/others` |
| `consistency` | `meteofrance/synop` | `subdaily/data` |
| `floor` | `dwd/dmo` | `hourly/icon`, `hourly/icon_eu` |

<!-- coverage:end -->

`range` and `elevation` run on every network that serves a quantity of their tables (`*`: every dataset of the network
that has one). Within a dataset a check covers the parameters its rule names, not every parameter: `range` the
parameters that have a bound in the table, `elevation` the `pressure_air_site`, `pressure_air_site_mean`,
`pressure_air_site_min` and `pressure_air_site_max`, `stuck` the `pressure_air_site` and `pressure_air_site_mean` of DWD
observation. The provider pages and [special values](special_values.md) list them.

What no check covers, and why:

- **A second parameter in another dataset.** A check never triggers a download. A consistency check reads its second
  parameter from the frame of the station and the same timestamp: the dataset is collected whole, and the neighbour of a
  relation is kept for the check even where nobody asked for it, and dropped after judging. Where the second parameter
  lives in another dataset, the check does not run. DWD observation holds its hourly `temperature_air` and `moisture` in
  two datasets, so the humidity of one is not held to the dew point of the other.
- **Quantities with no bound.** The hydrology of the Environment Agency and Hub'Eau judges nothing, and no network
  judges its codes, the derived quantities and the gauges listed above: a number there stays as the source wrote it. The
  sources' own "erroneous" flags (GHCN `QFLAG`, Frost `7`, GHCNh `3`, ...) are the source's and are returned as its
  flags, not as a check.

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
  keeps the readings of its other site only while they lie within the margins. DWD's historical outliers were checked
  against the station list and are bad readings, not station moves.
- **A check stands aside where the second value is missing.** A consistency check that finds no second value for a row
  (null, not a number, outside its own range, or marked suspect by the source's own flag) returns the value unflagged.
- **Every check judges the same number.** A pressure of 1150 hPa at 100 m is outside the range and outside the
  elevation: `rejected:elevation+range,raw:1150` with both hard, and `suspect:elevation+range` with both soft. One of
  1093.3 hPa at 100 m is inside the range and outside the elevation: `rejected:elevation,raw:1093.3`.
- **Where a `floor` covers a value, the range stands aside.** DMO's rain of -0.02 mm is below the 0 of the table and is
  the floor's, so it becomes 0 as before (`rejected:floor,raw:-0.02`) and not null.
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
