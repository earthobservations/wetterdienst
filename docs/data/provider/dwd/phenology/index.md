# Phenology

## Overview

The DWD phenological network records the **calendar of plant development**: for one plant at one
station in one reference year, the day of the year on which a developmental phase was reached —
hazel flowering, beech leaf unfolding, winter wheat harvest. Around 1200 volunteer observers
report from roughly 6600 stations, and the series reach back to 1925 for many of the wild plants.

Observations come from two reporter groups, which are kept apart by the dataset name prefix:

- **annual reporters** (*Jahresmelder*, `annual_*`) — the full observation programme, submitted
  once the season is over. ~6600 stations, 76 plants.
- **immediate reporters** (*Sofortmelder*, `immediate_*`) — a smaller set of phases, reported
  within days of the observation. ~1200 stations, 34 plants.

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
- **value** — `Jultag`, the day of the year the phase was reached, dimensionless.
- **date** — the 1st of January of the reference year. The entry date DWD also publishes is that
  date plus `Jultag`, so nothing is lost by not carrying it separately.
- **quality** — `Qualitaetsniveau`: `1` formal check only, `7` checked in routine but uncorrected,
  `10` checked and corrected.

```python
from wetterdienst.provider.dwd.phenology import DwdPhenologyRequest

request = DwdPhenologyRequest(
    parameters=[("annual", "annual_common_hazel", "phenology_flowering_beginning")],
    periods="recent",
)
values = next(request.filter_by_station_id("07521").values.query()).df
```

## Periods

- **historical** — the full archive, re-released about once a year. DWD leaves the previous
  releases in place beside the current one, distinguished only by the end year in the file name;
  only the latest is complete, and that is the one read.
- **recent** — the current year and the three before it.

Not every plant has both. Plants discontinued before the recent files begin (spring wheat, tomato,
white cabbage, the farming activities) are `historical` only, and two added since the last
historical release are `recent` only.

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
