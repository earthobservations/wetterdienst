# Meteorology

## Overview

IMGW publishes meteorological observations for the Polish weather-station network at daily and
monthly resolution, as open data from the
[public data portal](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/).
No authentication is required.

Values are downloaded as zipped CSV archives (decoded as `latin-1`), with station metadata
resolved from the accompanying station-code list, which gives no region, so `region` is null; the river
catchment it lists a station under, with its hydrographic code (`Odra (1)`), is `river`. Both daily and
monthly summaries are provided.

A station's `station_id` is IMGW's nine-digit code (`349190600`). `short_code` is the other code IMGW gives it in
`wykaz_stacji.csv`, its list of the stations of the meteorological archives: three digits for a synop station (`600` for
Bielsko-Biała, the number of its per-station files in `dobowe/synop`), four or five for the others (`5409`, `95414`),
which the maps of the archives (`mapa_zawartosci_synop.pdf`, `_klimat.pdf`, `_opad.pdf`) key their stations by. The
list names 573 of the 800 stations of the catalogue (read 2026-11-17); the others have no `short_code`. Three stations
of the list have two codes, a climate and a precipitation one, and it is not told which is the station's: BABIMOST
(`252150270`: `3152` and `93152`), Bydgoszcz-Szwederowo (`253170260`: `2351` and `92367`) and Dąbrówka Stara
(`251200270`: `4611` and `94660`). Their `short_code` is null (two of them are in the catalogue, so 571 stations have one). Find a station by it with `filter_by_sql("short_code = '375'")`. IMGW does not state the code as a WMO number, so it is no `wmo_id` (the three-digit code plus `12` matches the WMO number of the stations compared, but that
is an inference), and `wmo_id`, `wigos_id` and `icao_id` are null.

The code comes from a second list, which the synop stations are picked by. For `synop` a list that cannot be read is
an error. For the other datasets it is an addition: the stations come back with `short_code` null and the warning
`station-codes-unavailable` (see [the warnings of an answer](../../../../usage/restapi.md)).

Five synop stations have daily synop archives and are in no station list that gives a position, so they
are not listed and their history cannot be requested: Zgorzelec (351150405), Gdańsk-Port Północny
(354180140), Bydgoszcz (353170240), Gdańsk-Rębiechowo (354180150) and Żarnowiec (354180131). IMGW's
`wykaz_stacji.csv` names them without a position, and its `mapa_zawartosci_synop.pdf` gives approximate
positions and no elevation. Three of them are listed under newer ids (other station records, which are not
merged by name).

## Status columns

Every measurement in these files is followed by a status column, documented per file in the
`*_format.txt` beside the data. It is read, and carried verbatim into `quality_flags`:

| status  | meaning                                           | value         | `quality_flags` |
|---------|---------------------------------------------------|---------------|-----------------|
| blank   | the value is a measurement                        | as published  | null            |
| `8`     | *brak pomiaru* -- no measurement                  | null          | `8`             |
| `9`     | *brak zjawiska* -- the phenomenon did not occur   | 0             | `9`             |
| `Z`     | *opad zbiorczy* -- a collective total (`o_d` only)| as published  | `Z`             |

Neither code can be taken from the value column, because the files do not write it the same way
twice. Where the status is `8` the value is not left empty but holds a literal zero, which is why
the status has to be read at all -- snow depth at a rain gauge would otherwise read 0 cm for every
day of a Polish January. Where the status is `9` the cell holds a literal zero in some files and
nothing at all in others, for the same parameter months apart, so `9` is returned as the zero it
means rather than passed through.

`8`, `9` and `Z` are IMGW's own codes. An *opad zbiorczy* is a sum over the preceding days that were
not measured, published on the day the reading was taken without saying which days it covers, so the
value is kept -- it is a real measurement -- and the `Z` is what says it is not that day's total
alone. (While the column was numeric, `Z` was reported as 10.)

One code here this library assigns itself: `11`. `o_d_format.txt` adds that *brak zjawiska* covers a day absent from a month that is
itself present ("Brak zjawiska to również brak dnia w istniejącym miesiącu"), and the older `o_d`
files rely on it: `o_d_02_2010` carries 14,229 rows for the 26,796 days in its stations' months,
while `o_d_07_2024` writes every day out, with status `9` on the dry ones. `daily/precipitation`
returns such a day as 0 mm with `quality_flags` `11`, so that a dry day reads the same whichever year IMGW
wrote the file in, and `11` rather than `9` because no status in the file says so. Only
`precipitation_amount` is filled: a day without rain is not a day without snow cover. A month the
station has no row in at all is left empty, and `daily/climate` and `daily/synop` are read as
published, since their format files carry no such sentence.

One thing the status cannot resolve: a `0` in `monthly/climate`'s `snow_depth_max` that is not
qualified by a status means either that there was no snow cover in the month or that the maximum
could not be determined; `k_m_d_format.txt` says so in as many words. It is common -- 96 of the 196
rows of 2024 -- and is returned as 0 cm.

IMGW stopped publishing two files in 2024: `k_d_t` of `daily/climate` with May 2024 and `s_d_t` of
`daily/synop` with July 2024. They carried `cloud_cover_total`, `humidity_relative` and `wind_speed`
(and, in synop, the vapour and air pressures and the day and night precipitation), and no other file
does, so these have rows up to April and June 2024 respectively and none after; the temperatures,
precipitation and snow depth, all in `k_d` and `s_d`, continue.

```{toctree}
:hidden:

daily.md
monthly.md
```