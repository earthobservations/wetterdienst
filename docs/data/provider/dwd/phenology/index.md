# Phenology

## Overview

The DWD phenological network records the **calendar of plant development**: for one plant at one
station in one reference year, the day of the year on which a developmental phase was reached —
hazel flowering, beech leaf unfolding, winter wheat harvest. Around 1200 volunteer observers
report from roughly 6600 stations, and the series reach back to 1925 for many of the wild plants.

Observations come from two reporter groups, which are kept apart by the dataset name prefix:

- **annual reporters** (*Jahresmelder*, `annual_*`) — the full observation programme, submitted
  once the season is over. ~6600 stations, 72 plant datasets.
- **immediate reporters** (*Sofortmelder*, `immediate_*`) — a smaller set of phases, reported
  within days of the observation. ~1200 stations, 38 plant datasets.

Data is published at
[observations_germany/phenology](https://opendata.dwd.de/climate_environment/CDC/observations_germany/phenology/),
one semicolon-separated text file per plant, reporter group and period, with the station
catalogues in [CDC/help](https://opendata.dwd.de/climate_environment/CDC/help/). No authentication
is required. See the DWD's
[phenology pages](https://www.dwd.de/DE/klimaumwelt/klimaueberwachung/phaenologie/phaenologie_node.html)
for the observation guidelines behind the phase definitions.

## Data model

Phenology carries one dimension the rest of the library does not — the plant. It maps onto the
file layout:

- **resolution** — `annual`, one observation per phase and reference year.
- **dataset** — one **plant**, as observed by one reporter group, which is exactly one source
  file: `annual_common_hazel`, `immediate_winter_wheat`, `annual_grapevine_late_ripening`.
- **parameter** — one **phenological phase**: `phenology_flowering_beginning`,
  `phenology_leaf_unfolding_beginning`, `phenology_harvest`. The `original name` is DWD's numeric
  `Phase_id`, which is the only name the data files themselves use.
- **value** — `Jultag`, which DWD describes as the day of the year the phase was reached, dimensionless.
  It is returned as DWD writes it, and it is the day of the year only for a date in the reference year of a
  year that is not a leap year (1 January is 1); see *Reading `Jultag`* below.
- **timestamp** — the 1st of January of the reference year, not the date of the phase. The entry date
  (`Eintrittsdatum`) that DWD also publishes is not carried, and it cannot be recovered from the stamp and
  `Jultag` alone.
- **quality_flags** — `Qualitaetsniveau`, as DWD writes it: `1` formal check only, `7` checked in routine
  but uncorrected, `10` checked and corrected.

```python
from wetterdienst.provider.dwd.phenology import DwdPhenologyRequest

request = DwdPhenologyRequest(
    parameters=[("annual", "annual_common_hazel", "phenology_flowering_beginning")],
    periods="recent",
)
values = next(request.filter_by_station_id("07521").values.query()).df
```

## Reading `Jultag`

DWD's description files call `Jultag` the "day of the year" (`DDD`) and say nothing more about how it is
counted. The data show that it is the day of the year only for a date in the reference year of a year that is not
a leap year, and the library returns it as DWD writes it. Checked on the current and historical files of winter
wheat (annual reporters) and hazel (immediate reporters), 2026-10-13:

- **Leap years.** From about 1952 the count is of a 365-day year: 29 February is 59, as 28 February is, and
  1 March is 60, so from 1 March `Jultag` is one below the real day of the year. Winter wheat, historical: 175,633
  of 176,470 March-to-December rows of the leap years since 1952 (the rest, mostly 1952 to 1968, carry the real day
  of the year). Hazel, historical and recent: every March-to-December row of a leap year (1,243 and 169). Before
  1952 the leap years carry the real day of the year (154 of 159 winter wheat rows).
- **A date before the reference year.** A phase can fall before 1 January of the `Referenzjahr`: the sowing of a winter
  crop is reported for the year of its harvest, and a hazel can flower in December. The immediate reporters write that as a negative
  number of days before 1 January: 31 December is -1 and there is no 0 (`20231229` of `Referenzjahr` 2024 is -3;
  243 of 243 hazel rows of the historical file, 63 of 63 of the recent one). The annual reporters write the
  positive day of the year of the earlier year (`19621010` of `Referenzjahr` 1963 is 283; 39 of the 42 winter wheat
  rows of the historical file that are dated outside the reference year, 2 of 2 in the recent one), which looks
  like a day of the reference year. The other 3 are dated in the year after and carry a number above 365
  (`20170115` of 2016 is 380).
- **What follows.** The timestamp is the 1st of January of the `Referenzjahr` and the entry date is not carried, so
  adding `Jultag - 1` days to the timestamp gives the entry date for a date in the reference year of a year that is
  not a leap year, and only there. In a leap year add `Jultag` days from 1 March on; a negative `Jultag` is added
  as it is (`-3` gives 29 December of the year before). Two cases cannot be told apart from the
  value: 28 and 29 February, and an annual reporter's date in the year before from a date in the reference year.

## Periods

- **historical** — the full archive, re-released about once a year. DWD leaves the previous
  releases in place beside the current one, distinguished only by the end year in the file name;
  only the latest is complete, and that is the one read.
- **recent** — the current year and the three before it.

Not every plant has both. Fifteen datasets are `historical` only — those discontinued before the
recent files begin, among them spring wheat, tomato, white cabbage, the two farming activities,
three of the five annual-reporter grapevine varieties and all three immediate-reporter ones. Two are `recent` only, `annual_beet` and
`annual_currant_all_varieties`, having been added since the last historical release; their whole
record lives in the recent file, so a date range reaching back before the recent window still
reads them.

```{warning}
The files are per plant, not per station: asking for one station's `historical` series downloads
the file holding every station, which for the larger crop and tree series is 50–160 MB. A request
parses each file once and keeps the stations it asked for, so a many-station request costs no more
than a one-station request — but a one-station request is not cheap.
```

## License

The German Weather Service specified their data as being open though they ask you to
reference them as copyright owner. Take a look at the
[Open Data Strategy at the DWD](https://www.dwd.de/EN/ourservices/opendata/opendata.html)
and the [Official Copyright](https://www.dwd.de/EN/service/copyright/copyright_artikel.html?nn=495490&lsbId=627548)
statements before using the data.

```{toctree}
:hidden:

annual.md
```
