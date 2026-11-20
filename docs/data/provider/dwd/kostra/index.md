# KOSTRA heavy rainfall

## Overview

KOSTRA-DWD is the heavy-rainfall statistics of the DWD: for every cell of a 5 km grid over Germany, how much rain falls
in a rain of a given **duration** (5 minutes to 7 days) that comes once in a given **return period** (1 to 100 years).
Engineers size drains and retention basins with it. `wetterdienst` reads the **2020 edition**, KOSTRA-DWD-2020 (made
from the series of about 2,000 rain gauges, published in December 2022), from
[`KOSTRA_DWD_2020/tab/`](https://opendata.dwd.de/climate_environment/CDC/grids_germany/return_periods/precipitation/KOSTRA/KOSTRA_DWD_2020/tab/);
the previous edition, KOSTRA-DWD-2010R, is another grid with depths only and is not read.

KOSTRA has no time axis and no stations, so it is no timeseries network: it is a **point lookup**, as the
[climate stripes](../../../../usage/stripes.md) and [Storm cells](../storm_cells/index.md) are. Give a point, and get the
table of the grid cell that holds it, on every surface: `DwdKostraRequest` in Python, `wetterdienst kostra`, REST
`/api/kostra` and the MCP tool `kostra`.

| | |
| --- | --- |
| Grid | 300 by 300 cells of 5 km, **ETRS89-LAEA (EPSG:3035)**, about 17 % of the cells hold values: Germany and a border of about 10 km |
| Durations | 22: 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 540, 720, 1080, 1440, 2880, 4320, 5760, 7200, 8640 and 10080 minutes |
| Return periods | 9: 1, 2, 3, 5, 10, 20, 30, 50 and 100 years |
| Files | one zipped table of 0.7 MB for each duration, 90,000 rows each, which DWD wrote in December 2022 and has not changed |
| Values | for each duration and return period: the depth, the intensity and the uncertainty |

## What a row holds

The answer is the table of the cell, **one row for each duration and return period** (198 rows, or those of the
`duration` and `return_period` asked for), and the cell it is of:

| Column | Is | Unit | DWD's column |
| --- | --- | --- | --- |
| `duration_minutes` | the duration of the rain | minutes | `D<minutes>` of the file |
| `return_period_years` | how often such a rain comes, on average | years | `T` of `HN_<T>A` |
| `depth_mm` | the depth of the rain (Starkniederschlagshöhe, hN), to 0.1 mm | mm (l/m²) | `HN_<T>A` |
| `intensity_l_s_ha` | the intensity (Regenspende, rN), the depth over the duration, to 0.1 | l/(s ha) | `RN_<T>A` |
| `uncertainty_percent` | DWD's tolerance, plus and minus, to 1 %. It is for the depth **and** for the intensity | % | `UC_<T>A` |

The values are DWD's own numbers: nothing is converted or calculated, the missing-value codes are the only thing
changed. DWD writes `-99,9` (and `-99` for the uncertainty) where it has no value, which is null here (read as
`null_sentinels` reads every provider's). Of the 90,000 cells 74,011 have none, in every table alike: a cell has all of
its values or none, so a cell without values is **refused** and no table of nulls is answered. The uncertainty is not a
safety margin (DWD says so): it is what the method does not know, larger for the rarer rains, and it does not account
for a changing climate.

The **cell** is `index_rc`, which is DWD's name for it (see below), its `row` and `column`, and the `latitude` and
`longitude` of its **centre**, which is not the point asked for: every point of the cell's 25 km² gets the same values.

```python
from wetterdienst.provider.dwd.kostra import DwdKostraRequest

# the 60 minute rain that comes once in 100 years in Berlin
result = DwdKostraRequest(latitude=52.52, longitude=13.40, duration=60, return_period=100).query()
print(result.df)         # depth_mm 48.9, intensity_l_s_ha 135.8, uncertainty_percent 25.0
print(result.cell.index_rc)   # "105190"
print(result.to_json(with_metadata=True))

# every duration and return period of a cell, as a table (22 files the first time, then the cache)
table = DwdKostraRequest(latitude=48.14, longitude=11.58).query().df
```

```bash
wetterdienst kostra --latitude=52.52 --longitude=13.40 --duration=60 --return-period=100
wetterdienst kostra --latitude=48.14 --longitude=11.58 --duration=120 --format=csv
```

```bash
http localhost:7890/api/kostra latitude==52.52 longitude==13.40 duration==60
```

A `duration` that DWD publishes no table for, or a `return_period` it has no column for, is refused and names the ones
there are. A point **outside the area** of the values, off the grid or in a cell without values (the sea, most of
Poland), is a `LocationOutOfRangeError`: a 400 over REST and a usage error (exit 2) on the command line, with the reason.
`format=csv` gives the table alone, and the licence and the credit line in the headers (`X-Wetterdienst-License`,
`X-Wetterdienst-Attribution`).

## How much is read

A lookup with a **`duration` reads that one table** (0.7 MB); one without reads all 22 (15 MB), which are fetched at
once. The files never change, so the cache keeps them for a week. Measured on a laptop, from DWD's server:

| Lookup | First time | From the cache |
| --- | --- | --- |
| one duration | 0.3 s | 0.02 s |
| the 22 durations | 2 s | 0.2 s |

Ask for the duration you need. The first lookup of a duration also serves every other cell: the cache holds the table,
not the cell.

## The grid

DWD describes the grid in its [Anwendungshilfe zu KOSTRA-DWD-2020](https://www.dwd.de/DE/leistungen/kostra_dwd_rasterwerte/kostra_dwd_rasterwerte.html)
(section 4, "Geografischer Bezug") and in `KOSTRA-DWD-2020_geog_Bezug.xlsx` beside the tables:

- the reference system is **ETRS89-LAEA, EPSG:3035** (the Lambert azimuthal equal-area projection on the GRS80
  ellipsoid, centred on 52 N, 10 E), with the lower left corner of the grid at 3,600,000 / 2,300,000 and cells of
  5,000 m (the header of the ASCII grids says the same);
- `INDEX_RC` is `(row * 1000) + column`, in six digits (`zzzsss`: `000001` is row 0, column 1; `105190` is row 105,
  column 190), with the **row counted from the north** and the column from the west.

`wetterdienst` projects the point itself (the projection is written out, no `pyproj` is needed) and finds the cell by
its position in that grid. It was checked against DWD when it was written:

- the **centres of all 90,000 cells** of `KOSTRA-DWD-2020_geog_Bezug.xlsx` are those of the grid, to 5e-9 degrees, and
  its corners too;
- every one of those centres is found in its own cell;
- the projection agrees with `pyproj` to 1e-8 m;
- the value of the 60 minute table at Berlin, Munich, Hamburg, Cologne and the Brocken is the one of DWD's ASCII grid at
  the same point, and the **whole ASCII grid of the 100 year, 60 minute depth equals the table's**, cell for cell;
- the worked example of the Anwendungshilfe, cell `160126` (Frankfurt am Main, 50.089149 N, 8.785514 E in the worksheet
  that goes with it) at 5 minutes: 11.2 mm for 5 years and 20.5 mm for 100 years (373.3 and 683.3 l/(s ha), +-10 % and
  +-12 %), is what is read.

## Licence

The data is the DWD's, under the terms of its open data (GeoNutzV; the same as for the other datasets of the CDC): the
`metadata` block of an answer carries the licence and the credit line, "Source: Deutscher Wetterdienst". It says that
`processing_note` too: the values are DWD's statistics of the grid cell of the point, **not measurements at the point**,
selected for the cell with DWD's missing-value codes read as null. The note does not use the sentence of
`interpolate` and `summarize` (selected or calculated from the provider's readings), because the values are not
readings and nothing is calculated from them. DWD offers tables for a site, for a fee, by e-mail to hydromet@dwd.de.

## What is not here

- **KOSTRA-DWD-2010R**, the previous edition: a different grid (8,453 cells), depths only.
- The GIS files (`gis/`), the parameters of the extreme-value distribution (`Parameter_KOSTRA-DWD-2020`) and the list of
  rain gauges the statistics are made from (`station_list_KOSTRA-DWD-2020.csv`).
- A lookup of a place by name, a range of points, or the statistics of a catchment.
