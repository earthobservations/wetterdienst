# Storm cells

## Overview

KONRAD3D finds the thunderstorm cells in the volume scans of the radars of the DWD, tracks them from scan to scan and
forecasts the position of their centre for the next hour. The DWD publishes one XML file for every scan, every five
minutes, in [`weather/radar/konrad3d/`](https://opendata.dwd.de/weather/radar/konrad3d/), and keeps about 48 hours of
them. `wetterdienst` reads the newest scan, or the newest at or before a time, into **one row per cell**: how severe it
is, whether it carries hail, heavy rain or gusts, how big, how fast and in which direction it moves, its outline and its
forecast track. It is a "now" product with no stations: a standalone network, as [Alerts](../alerts/index.md) are, on
every surface (`DwdStormCellsRequest` in Python, `wetterdienst storm-cells`, REST `/api/storm-cells` and the MCP tool
`storm_cells`).

The raw files, as the DWD wrote them, are what `DwdRadarValues` gives for `RadarParameter.KONRAD3D_CONVECTIVE_CELLS`
([Radar](../radar/index.md)), which this does not change.

What a scan is:

| | |
| --- | --- |
| Files | `KONRAD3D_YYYYMMDDThhmmss.xml`, in UTC, named for the **reference time**, the start of the radar scan cycle, always on a multiple of five minutes |
| Cadence | one every 5 minutes, and none missing in the 48 hours that were read (576 files) |
| Delay | a file is on the server 5.5 to 10.5 minutes after its reference time (median 5.5, longest 9.4 minutes of the 48 hours read on 2026-11-17), so the newest scan is that old |
| Empty scans | most: 460 of those 576 were a complete file with no cell. DWD's `<cells/>` with no `feature` is the usual answer, not a failure |
| Size | an empty scan is 4 KB of XML, a cell about 17 KB; of JSON a cell with outline and track is 3.5 to 5 KB |
| Latest | there is **no `latest` file**: the newest is found in the directory listing, which is cached for a minute |

The **`cell_id` is not an identifier**: DWD numbers the cells of a scan and reuses a number after a cell has died; `*`
after a number says the cell split off in this scan, `#` that cells merged into it. A cell is told by its **`code`**,
which DWD calls the unique identifier of the cell and which a cell **keeps from scan to scan** (the real files show a
continuing cell with the `code` of its predecessor); a split or a merger gets a new one. So one cell is followed through
the scans by its `code`, and a split is followed to the cell it split off by `predecessor_code`.

## A place

A scan holds every cell of Germany and its surroundings: nothing in 8 scans of 10, and on a day of thunderstorms hundreds
of cells, several hundred KB. Without a place the answer is all of them. Two kinds of place keep the cells for one
spot, on every surface, and `min_severity` the severe ones:

| Argument | Keeps the cells |
| --- | --- |
| `latitude`, `longitude` and `distance` | whose **outline** contains the point (an edge counts) or comes within `distance` km of it. `distance` is 0 by default: the cells that are over the point. It is not given without a point |
| `left`, `bottom`, `right` and `top` | whose outline reaches into the box (the four are given together) |
| `min_severity` | of this severity and above: 0 weak, 1 moderate, 2 severe, 3 extreme |

A point and a box are not given together (a 400, or a usage error). The outline is what counts, and not the centre: a
large cell of 200 km² has its centre 8 km from the rain over your house. The distance is measured on the plane at the
point, within about 1 % of the great-circle distance for the few hundred km a cell can be from it.

```python
from wetterdienst.provider.dwd.storm_cells import DwdStormCellsRequest

# the cells over or within 25 km of Berlin, and how severe they are
berlin = DwdStormCellsRequest(latitude=52.52, longitude=13.40, distance=25).query()
print(berlin.df.select("cell_id", "severity_label", "cell_speed_kmh", "direction_degrees"))

# the severe ones (2 and 3) of southern Germany
south = DwdStormCellsRequest(left=8.0, bottom=47.5, right=13.8, top=50.6, min_severity=2).query()
```

## What a row holds

One row per cell, 26 columns, DWD's attributes in DWD's units with the unit in the name where there is one:

| Column | Is | Unit |
| --- | --- | --- |
| `reference_time` | the scan the cell is of: the start of its radar scan cycle | UTC |
| `cell_id` | the identifier DWD gives the cell, without the `*` or `#`. **Not unique** (it is reused) | |
| `code` | DWD's unique identifier of the cell, 22 digits: `YYYYMMDDhhmm` of the scan that gave the cell this code (its birth, or the split or merger that made it a new cell), the lead time, 0 for measured, the ensemble member, and a number. **The same in every scan while the cell lives** | |
| `predecessor_code` | the `code` of the cell's predecessor in the scan before: its own `code` for a cell that goes on, that of the cell it split off for a split; of a merger, the predecessor DWD is surest of. Null for a new cell | |
| `split_event`, `merge_event` | the cell split off its predecessor in this scan, or cells merged into it (DWD's `split_event` and `merge_event`, which `*` and `#` after the identifier say too) | |
| `first_detection` | when the cell was first detected | UTC |
| `number_detections` | in how many scans it has been found | |
| `severity` | 0 to 3: the weighted mean of the cell's VIL, area above 55 dBZ, maximum reflectivity, heavy rain potential and mass, raised to the highest category of the warning flags | points |
| `severity_label` | `weak` (green), `moderate` (yellow), `severe` (red) or `extreme` (violet) | |
| `severity_decimal` | the severity before it is rounded, 0.00 to 3.00 | points |
| `hail_flag` | 0 no hail, 1 moderate, 2 large hail (DWD has a 3 and never sets it) | |
| `heavy_rain_flag` | 0 below 15 mm in an hour, 1 from 15, 2 from 25, 3 from 40 mm | |
| `gust_flag` | 0 below 65 km/h, 1 from 65, 2 from 104, 3 from 140 km/h. Null where DWD gives none | |
| `centroid_latitude`, `centroid_longitude` | the centre of the cell | degrees |
| `cell_speed_kmh` | how fast the cell moves | km/h |
| `direction_degrees` | the bearing of its motion, degrees clockwise from north (0 north, 90 east). **Calculated**, see below | degrees |
| `covered_area_km2` | the area of the cell's outline | km² |
| `echo_top_msl_m` | the height of the highest radar echo in the cell, above mean sea level | m |
| `max_reflectivity_dbz` | the highest reflectivity in the cell | dBZ |
| `vil_kg_m2` | the vertically integrated liquid of the cell | kg/m² |
| `max_estimated_gust_kmh` | DWD's estimate of the strongest gust of the cell (Stewart's downdraft estimate from the VIL and the echo top, plus the speed of the cell) | km/h |
| `heavy_rain_potential_mm` | the rain the cell would give a place over an hour, for a cell that stays over it (slow cells are more dangerous) | mm |
| `geometry` | the outline as a GeoJSON `Polygon` (longitude, latitude), its ring **closed**; a `MultiPolygon` where the outline is in several parts. With `geometry=centroid` the point of the centre | |
| `track` | the forecast, a list of 12 positions, see below. Left out with `track=false` | |

DWD's missing value (the number `-1000000000`, the text `not-a-date-time`) is null. DWD does not fill the `gust_flag` of
a cell it could not judge, for one.

### The track, and the direction

`track` is DWD's **forecast** of where the centre of the cell will be, in steps of five minutes from 5 to 60 minutes
ahead. It is a forecast and not an observation, and the cell's polygon and intensity are not forecast. Each point has
its `time`, `latitude` and `longitude` and the 1 sigma ellipse of the uncertainty of the position: `uncertainty_major_km`,
`uncertainty_minor_km` and `uncertainty_angle_degrees` (clockwise from north). The ellipse grows from about 3 km at
5 minutes to tens of km at an hour. Where DWD's track is not enough, the files before give the track so far: ask for
the `timestamp` of an earlier scan and find the cell by its `code`.

DWD gives the speed of a cell and no direction. `direction_degrees` is **calculated**: the bearing from the first
to the second forecast position, so it is the direction the cell is going in the next minutes, null where a cell has not
two positions or they are one. The `processing_note` of the answer says so.

### What is left out

About 40 of the roughly 190 attributes of a cell answer "where is it and how bad". The others are research detail and
stay in the XML (which `DwdRadarValues` gives as it is): the group of the mesocyclone in the cell (not the mesocyclone
product of DWD, which is not read either), the environment from the numerical model (CAPE, shear, helicity), the
detail of the hydrometeor classification (hail and large hail), the lightning rate and its history, the areas and volumes
above each threshold of reflectivity, the trends of the intensity, the satellite cloud top, the sweeps that
found the cell and the grid of the run. They are described in DWD's
[format description](https://www.dwd.de/DE/leistungen/radarprodukte/formatbeschreibung_konrad3d.html) (data model 1.7). A
column can be added later; the first list is kept small because removing one is a breaking change.

## An empty answer

Most scans hold no cell, so an empty answer has to be unambiguous, and a feed that has stopped must not look like a quiet
sky. The answer carries the `reference_time` of the scan it is of, and warnings in `metadata.warnings`:

- **no warning**: the scan holds no cell. That is the all-clear, as of `reference_time` (5 to 10 minutes ago).
- `no-storm-cells-for-place`: the scan holds cells, and the place or `min_severity` leaves none of them. The message says
  what was asked and how many cells are elsewhere. An answer, not an error.
- `scan-stale`: the newest scan is more than **20 minutes** older than the time asked for (now, or the `timestamp`):
  DWD's run or its files have stopped, scans are missing, and an empty answer is then **no all-clear**. The longest delay seen
  is 9.4 minutes, so a scan is never this late in the normal course. For a `timestamp` it is told when no scan lies within
  20 minutes before it.

The code of a warning is in the `X-Wetterdienst-Warnings` header of a CSV answer, which has no block.

## A time

Without a `timestamp` the answer is the newest scan. With one, the newest scan at or before it, from the ~48 hours the
DWD keeps (a naive time is UTC). A time before the oldest file is an error (a 400, a usage error on the command line),
naming the oldest. There is no archive.

## Update date

The `data_updated_at` of the [`metadata`](../../../../usage/restapi.md#response-metadata) of an answer is when the DWD
wrote the file of the scan (its `creation-date`), about 5 minutes after the `reference_time`. Both are in UTC.

## Caching

The listing of the directory is cached for **a minute**: with a file every five minutes, the default of five minutes could
show the newest scan up to ten minutes late. A scan is a file named for its time and never changes, so it is cached for
12 hours; a copy that does not parse (read while DWD was writing it) is fetched once more.

## As DataFrame

`DwdStormCellsRequest(...).query()` returns a `DwdStormCellsResult`. Its `.df` is a [polars](https://pola.rs/)
DataFrame with the columns above, one row per cell (`geometry` is GeoJSON text, `track` a list of structs), its
`.reference_time` the time of the scan and `.data_updated_at` that of the file.

```python
from wetterdienst.provider.dwd.storm_cells import DwdStormCellsRequest

result = DwdStormCellsRequest(min_severity=1, track=False).query()
print(result.reference_time, result.df.height)
```

The result is rendered as the other results are:

```python
result.to_dict()                    # {"reference_time": ..., "cells": [...]}, the outline and the track nested
result.to_ogc_feature_collection()  # GeoJSON FeatureCollection, geometry = the outline, + reference_time
result.to_geojson()                 # GeoJSON string
result.to_csv()                     # CSV, a row per cell, the geometry and the track as JSON text
result.to_format("GeoJSON", indent=2, with_metadata=True)  # "json", "geojson" or "csv", in any case
```

`to_json` and `to_geojson` take `indent` and `with_metadata`, which puts the `metadata` block (provider, licence, credit
line, date of the data) first, a foreign member of a feature collection. The result is outside the
[frozen results](../../../../usage/compatibility.md#python-api) of the Python API.

## To a file

`result.to_target("file://cells.geojson")` writes the answer the REST API gives, by the extension of the target: `.json`
(`metadata`, `reference_time`, `cells`), `.geojson` (the feature collection) or `.csv` (bare: `with_metadata=True`
writes the block beside it as `cells.csv.metadata.json`). A scan with no cell is written as it is, so a file that a
schedule rewrites does not keep the cells of the run before. A database target is refused: a cell has an outline and a
track, and there is no table for it. `if_exists` is `replace`, `fail` or `skip`; `pretty=True` indents.

## CLI

```bash
# the cells of the newest scan, as JSON
wetterdienst storm-cells

# over a place or within 25 km of it, without the track: a few KB
wetterdienst storm-cells --latitude=52.52 --longitude=13.40 --distance=25 --track=false

# in a box (left, bottom, right, top), severe cells and above, as the points of their centres
wetterdienst storm-cells --left=8 --bottom=47.5 --right=13.8 --top=50.6 --min-severity=2 --geometry=centroid

# a past scan (UTC, within the last ~48 hours)
wetterdienst storm-cells --timestamp=2026-11-17T20:25

# to a file, the extension names the format
wetterdienst storm-cells --target=file://cells.geojson
```

## REST API

```bash
http localhost:7890/api/storm-cells latitude==52.52 longitude==13.40 distance==25 track==false
http localhost:7890/api/storm-cells left==8 bottom==47.5 right==13.8 top==50.6 min_severity==2 geometry==centroid format==geojson
```

`latitude` without `longitude`, a `distance` without a point, half a box or a point with a box is a 422; a `timestamp` before
the window a 400; a feed that cannot be read a 502 and one that cannot be reached a 503.

## MCP

The tool `storm_cells` is the route. Its answer is **not cut** to the 40,000 characters of an MCP answer
([the size of an answer](../../../../usage/mcp.md#the-size-of-an-answer)): ask for a place, a point with `distance` or a box,
and for a long list `track=false` (1.6 KB a cell) and `geometry=centroid` (a point, not an outline of a few hundred to two
thousand characters), which make 30 cells fit.

## License

The DWD states no terms for this directory; the files are under the same open data terms as the rest of the DWD:
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), "Source: Deutscher Wetterdienst", as
[licences and credit lines](../../licenses.md) lists them, and the answer reports them in its `metadata`. The
`processing_note` says what `wetterdienst` did to the cells: the outlines are closed rings, DWD's missing value is read
as null, `track` is DWD's forecast and not an observation, and `direction_degrees` is calculated.
