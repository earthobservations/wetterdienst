# Pollen

## Overview

Pollen is the DWD's **forecast of the pollen load** (the "Pollenflug-Gefahrenindex") for 27 regions of Germany, made by
its medical meteorology. For each region and each of eight pollen types it gives the load expected for today, tomorrow
and the day after tomorrow, as one of seven steps of a scale from none to high.

The data is one small JSON file,
[s31fg.json](https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json), written once a day in the morning
(`last_update` is 11:00 local time) and described in
[Beschreibung_pollen_s31fg.pdf](https://opendata.dwd.de/climate_environment/health/alerts/Beschreibung_pollen_s31fg.pdf)
beside it. It holds no earlier day and no other run, so there is no `issue`: the network is the latest forecast, with
one daily value for each of the three days. No authentication is required.

## Stations

The 27 regions are the stations. DWD's areas are regions (`region_id`, such as Bayern) and the part-regions of some of
them (`partregion_id`, such as Mainfranken); a region that has no parts is a station itself (the file writes its
`partregion_id` as `-1`).

- **The id** is DWD's number of the area, as text: the `partregion_id`, and where there is none the `region_id`.
  DWD numbers regions in tens and part-regions in ones, so the ids never meet: `11` is Schleswig-Holstein und Hamburg,
  Inseln und Marschen, `20` is Mecklenburg-Vorpommern, `50` is Brandenburg und Berlin, `124` is Bayern, Mainfranken.
- **The name** is the region and the part-region, `Bayern: Mainfranken`, the region alone where there is no part
  (`Mecklenburg-Vorpommern`). The `region` column is the region (`Bayern`).
- **There is no position.** DWD ships no shape and no coordinates of the regions, and the library invents none:
  `latitude`, `longitude` and `elevation` are null. A region is found by its name (`name`, a fuzzy match, the best
  `rank` of them) or its id (`stations`), or by `sql`; a search by `latitude` and `longitude` with `rank` or `distance`,
  or by a bounding box, finds none of them and answers an empty list with the warning `positions-unavailable`, which
  names the way to find them (`name` and `stations`).
  A region has no point to estimate at, so `interpolate` and `summarize` refuse it. In a GeoJSON answer the feature of
  a region has a null `geometry`. The table of the regions, with the numbers and names as the file writes them, is
  `provider/dwd/pollen/regions.py`.

A region that DWD adds to the file is skipped, with a warning that names it, until it is added to the table; a region of
the table that is not in the file has no values and is named in the `file-skipped` warning of the answer. A file that is
not the one described is a `DownloadError`, and a 429 is a `ProviderRateLimitError`.

## The load

A level is one of seven steps, which the `legend` of the file names, and which the library serves as a number from 0 to 3
in steps of 0.5 (dimensionless; the half steps are the ranges between two classes). The number is the step's own, no
concentration: DWD gives no grains per cubic metre.

| step in the file | value | DWD's text (`legend`)         | meaning                           |
|------------------|-------|-------------------------------|-----------------------------------|
| `0`              | 0     | keine Belastung               | no load                           |
| `0-1`            | 0.5   | keine bis geringe Belastung   | none to low load                  |
| `1`              | 1     | geringe Belastung             | low load                          |
| `1-2`            | 1.5   | geringe bis mittlere Belastung | low to medium load               |
| `2`              | 2     | mittlere Belastung            | medium load                       |
| `2-3`            | 2.5   | mittlere bis hohe Belastung   | medium to high load               |
| `3`              | 3     | hohe Belastung                | high load                         |

A day without a value is written `-1` ("Fehlende Werte werden mit einer -1 gekennzeichnet"). It is null here, as is any
other text that is none of the seven steps, and the text stays as the last token of `quality_flags`, `raw:-1`.

The eight pollen types are Hasel (hazel), Erle (alder), Esche (ash), Birke (birch), Gräser (grass), Roggen (rye),
Beifuß (mugwort) and Ambrosia (ragweed), the parameters `pollen_load_hazel`, `pollen_load_alder`, `pollen_load_ash`,
`pollen_load_birch`, `pollen_load_grass`, `pollen_load_rye`, `pollen_load_mugwort` and `pollen_load_ragweed`. The file
keys them by the German name without an umlaut (`Graeser`, `Beifuss`), which is the original name.

The timestamp of a value is the date of its day at 00:00 UTC. The file names no day but its own: `today` is the
German date of `last_update`, `tomorrow` the next and `dayafter_to` the one after.

## Update date

There is no model run: the `data_updated_at` of the
[`metadata`](../../../../usage/restapi.md#response-metadata) of an answer is when DWD last wrote the file (its
`Last-Modified`), the date DWD states in `last_update` having no time zone.

```{toctree}
:hidden:

daily.md
```
