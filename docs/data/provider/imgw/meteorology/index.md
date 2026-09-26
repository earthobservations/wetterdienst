# Meteorology

## Overview

IMGW publishes meteorological observations for the Polish weather-station network at daily and
monthly resolution, as open data from the
[public data portal](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/).
No authentication is required.

Values are downloaded as zipped CSV archives (decoded as `latin-1`), with station metadata
resolved from the accompanying station-code list. Both daily and monthly summaries are provided.

## Status columns

Every measurement in these files is followed by a status column, documented per file in the
`*_format.txt` beside the data. It is read, and carried into `quality`:

| status  | meaning                                           | value         | `quality` |
|---------|---------------------------------------------------|---------------|-----------|
| blank   | the value is a measurement                        | as published  | null      |
| `8`     | *brak pomiaru* -- no measurement                  | null          | 8         |
| `9`     | *brak zjawiska* -- the phenomenon did not occur   | 0             | 9         |
| `Z`     | *opad zbiorczy* -- a collective total (`o_d` only)| as published  | 10        |

Neither code can be taken from the value column, because the files do not write it the same way
twice. Where the status is `8` the value is not left empty but holds a literal zero, which is why
the status has to be read at all -- snow depth at a rain gauge would otherwise read 0 cm for every
day of a Polish January. Where the status is `9` the cell holds a literal zero in some files and
nothing at all in others, for the same parameter months apart, so `9` is returned as the zero it
means rather than passed through.

`8` and `9` are IMGW's own codes. `quality` is a numeric column and `Z` is a letter, so `Z` is
reported as 10, the one code here this library assigns itself. An *opad zbiorczy* is a sum over the
preceding days that were not measured, published on the day the reading was taken without saying
which days it covers, so the value is kept -- it is a real measurement -- and the 10 is what says it
is not that day's total alone.

Two things the status cannot resolve:

- A `0` in `monthly/climate`'s `snow_depth_max` that is not qualified by a status means either that
  there was no snow cover in the month or that the maximum could not be determined; `k_m_d_format.txt`
  says so in as many words. It is common -- 96 of the 196 rows of 2024 -- and is returned as 0 cm.
- `daily/precipitation` carries a row only for the days a station has something to report, and
  `o_d_format.txt` adds that *brak zjawiska* covers a day absent from a month that is itself present
  ("Brak zjawiska to również brak dnia w istniejącym miesiącu"). Those days are absent from the
  result rather than returned as 0 mm.

```{toctree}
:hidden:

daily.md
monthly.md
```