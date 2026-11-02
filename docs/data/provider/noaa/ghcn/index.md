# GHCN (Global Historical Climatology Network)

## Overview

NOAA Global Historical Climatology Network is a collection of **hourly** and **daily** weather data put together from multiple weather
services around the world, even those where at this moment no data is publicly offered. Resolution is fixed on daily,
because this is the most common and maintainable resolution with most observations practiced all over the world.

The GHCN-Hourly dataset represents the previously existing ISD (Integrated Surface Database).

Each station's `wmo_id` is the WMO station number the lists give it, null for the many stations that
have none.

## Elevation 0.0 is no elevation

GHCN writes `elevation` 0.0 for a station of which it knows no elevation: 54 of the 271 stations
at 0.0 in the hourly list stand between 150 and 4,329 m (CHM00052940 reads 500.2 to 998 hPa), and
BRM00083566 of the daily list is inland at about 827 m. The stations frame keeps the 0.0 as GHCN
writes it, so that a station on a coast at 0.0 m is not lost. Where the elevation is used, 0.0 is
read as unknown (`ELEVATION_ZERO_IS_UNKNOWN`): the plausibility check `elevation` of the station
pressure does not judge a station at 0.0, and `interpolate` and `summarize` asked about an elevation
leave such a station out, as they do a station with no elevation, instead of bringing its readings
from a height of 0 m ([interpolation at an elevation](../../../usage/interpolation.md#elevation),
GH-3708). A station at 12.0 m is a height and is corrected.

## One reading an hour

The hourly files hold every report of a station, and `hourly` returns one reading for each parameter
and full hour, stamped with the hour (GH-3000). The temperature of Denver in 2026 (read
2026-10-17) has 9,146 rows in 6,854 hours, one to seven in an hour: the routine METAR at :53
(source 413), the SPECI and further `FM15` reports filed between, and at the synoptic hours a SYNOP
at :00 (source 412). The 5-minute rows of the file (source 343) hold `precipitation_5_minute` and
none of the elements `hourly` reads. For each parameter:

1. a reading belongs to the full hour it is nearest to: 14:53 to 15:00, 14:20 to 14:00, and 14:30
   to 15:00 (a half hour goes to the later hour);
2. of the readings of an hour the one kept is the one the file gives a value for, so that a
   parameter a SPECI does not carry (a SPECI has no sea level pressure) is read from the report that
   has it;
3. then the one nearest to the full hour, which is the routine METAR at :51 to :54 unless a report
   was filed closer, a SYNOP at :00 included; then the earlier of two at the same distance.

The kept reading is stamped with the full hour (15:00 for the METAR of 14:53), as DWD and ECCC stamp
their hourly readings, so that `interpolate`, `summarize` and `skip_empty`, which count the readings
of an hour on the full-hour grid, find them. The parameters of an hour may come from different
reports (temperature from the SPECI of 22:59, sea level pressure from the METAR of 22:53), and the
`source:` token of `quality_flags` says which source a reading is from. The minute of the report is
no longer returned; read the file for it. An hour in which a parameter has no value in any report
has one null for it, which only `drop_nulls=False` shows.

## Hourly precipitation

The `precipitation` column of GHCNh holds the amount of a METAR's precipitation group, which is the
amount since the last routine report: the reports of an hour repeat a growing total, and the
file's documentation (section IX) says to take the last report of the hour for the hour's total.
`hourly` returns it as `precipitation_amount_since_last_routine_report` (called
`precipitation_amount` until GH-2841), one report for each UTC clock hour, stamped with the full
hour that report is nearest to like every other parameter (15:00 for the routine METAR of 14:53 at
LAX, which closes the clock hour 14):

1. the last report of the hour that holds a precipitation and was filed at the station's routine
   minute, the most common minute of its reports that are no SPECI in that month (`:53` at LAX and
   Denver; of two equally common minutes the later one; the documentation: "the most common minute
   closest to the end of the hour"). A station changes its minute: LAX in 1996 reports at :00 (SAO)
   until June and at :50 to :54 (METAR) from July;
2. else the last report that is no SPECI (`FM16`, `SAOSP`), for an hour whose routine report is
   missing or late;
3. else the last report.

What is filed after the routine report is passed over, because its amount is what fell since that
report, which the routine report of the next hour holds again. At LAX in 2022, 4 of the 98 hours
with several reports end in a SPECI: 17:00 UTC on 2022-03-28 reads 12.4 mm at :53 and 0.2 mm at
:57. From source 413 `FM15` reports at other minutes follow too: Denver 2026-09-18 23:00 UTC reads
21.6 mm at :53 and 0.0 mm at :59. A missing value (`-9999`) of the report kept is the hour's, and
the amount of an earlier report of the hour does not stand in for it.

This still is the total of a closing report, as the source gives it: at LAX the amounts of one
hour are not always monotonic (2022-03-28 18:00 UTC reads 2.5, 3.3 and 3.5 mm in SPECI of another
source, then 2.8 mm in the METAR).

### Precipitation of source 412 (GH-3016)

At Denver, since April 2026, the `precipitation` of the METAR rows at the hours 02, 05, 08, 11, 14,
17, 20 and 23 UTC (:53, one hour before the 3-hourly synoptic terms) comes from source 412,
"SYNOP/FM12 or BUFR Surface Land Observations decoded by NOAA/NCEI" (`precipitation_Report_Type`
`FM94_1`, the station as `WMO-72565`), not from the METAR (source 413, `ICAO-KDEN`) as before and as
in the other hours. Of the 1,418 precipitation values of Denver in 2026 (read 2026-10-17) 672 are
source 412, at those hours and six at 00:00. Chicago O'Hare and Boston have source 412 too, from the
same month. The documentation names no period for them, and they do not agree with the station's own
gauge: the GHCN-daily PRCP of Denver is 0.0 for 2026-04-02 to 2026-04-04, while source 412 reads 2.0
mm at 05:53 and 13.0 mm at 11:53 of 2026-04-02, and 52.0 mm at 14:53 on 2026-06-22, when the daily
total is 0.0. Of the 95 non-zero amounts at Denver 46 lie in a window of three days of which the
daily total is 0.0 on each (Chicago O'Hare 25 of 63, Boston 4 of 33). The largest amount a day of
source 413 reads is close to the daily total (Denver 2026-09-20: 3.0 mm and 3.0 mm), and the 24-hour
total that source 412 files too is (`precipitation_amount_last_24h`: 2.8 mm at 11:53 on 2026-06-22, the
2.8 mm of the METARs of 03:38 to 03:53 that day).

`hourly` returns the source 412 amounts as they are, with `source:412` as the mark, because what
they are is not known. A caller that needs the precipitation of an hour should leave out the
readings with `source:412` (`quality_flags` containing `source:412`) and take the `daily`
resolution for longer spans.

## The source's own verdict (`source`)

The check `source` reads the quality flag NCEI returns with the value and flags the codes its documentation words as a
failed check, an erroneous or a suspect value.

**Daily.** The first token of `quality_flags` is `QFLAG`, blank (left out) for a value that "did not fail any quality
assurance check". The [GHCN-Daily readme](https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt) says: "QFLAG1 is the
quality flag for the first day of the month. There are fourteen possible values: Blank = did not fail any quality
assurance check", and words the others as follows. All of them are read: `D` failed duplicate check; `G` failed gap check;
`I` failed internal consistency check; `K` failed streak/frequent-value check; `L` failed check on length of multiday
period; `M` failed megaconsistency check; `N` failed naught check; `O` failed climatological outlier check; `R` failed
lagged range check; `S` failed spatial consistency check; `T` failed temporal consistency check; `W` temperature too warm
for snow; `X` failed bounds check; `Z` flagged as a result of an official Datzilla investigation. The CSV returns such a
value (the `TMAX` of Central Park of 1869-06-22 is 172, tenths of a degree, with `QFLAG` `I`; read 2026-11-02), and so does
the reader: `I,source:Z,suspect:source`. (The token `source:Z` is the data source of the value, the SFLAG, and has nothing to
do with the check of that name, whose token is `suspect:source` or `rejected:source`.)

**Hourly.** The first token is `<element>_Quality_Code`, whose meaning depends on the source of the element (the `source:`
token), as Table 3 of the [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf)
lists it. The codes read are the ones it words as a verdict:

| `source:` | codes read, as the documentation words them |
| --- | --- |
| 313, 314, 315, 322, 335, 343, 344, 346 ("Legacy Codes for Sources 313, 314, 315, 322, 335, 343, 344, 346 include") | `2` "Suspect"; `3` "Erroneous"; `6` "Suspect, data originate from an NCEI data source"; `7` "Erroneous, data originate from an NCEI data source" |
| 220, 221, 222, 223, 347, 348 ("Legacy Codes for Sources: 220, 221, 222, 223, 347, 348 include") | `2` "Suspect"; `3` "Erroneous" |

Not read: the `0`, `1`, `4`, `5` and `9` of those lists (not checked, good, calculated, removed, passed), the letters of the
integration's own checks (`c` climatological outlier, `s` spike, ... of Table 3: no verdict is worded for them), the
letters `A`, `P`, `U`, `I`, `M`, `R` that say a value was edited, and the lists of sources 345 and 382, which Table 3
words on their own.

With `plausibility={"source": "hard"}` the value is null and the token is `rejected:source,raw:<text>`; the
default is `soft`, which keeps the value and writes `suspect:source`, so interpolation, summaries and climate stripes leave it
out. See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

## License

The NOAA GHCN incorporates data of multiple weather services across the globe. The 
[NOAA GHCN description](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00861) page
includes more information on the usage, references, qualities etc.

NOAA waives its rights in the data under the
[Creative Commons Zero 1.0 Universal Public Domain Dedication (CC0-1.0)](https://creativecommons.org/publicdomain/zero/1.0/):
the [GHCNh record](https://data.noaa.gov/onestop/collections/details/76ca9a6c-a4d4-45a8-b4a9-a336d474ba55) says so,
and [NOAA's Open Data Dissemination program](https://registry.opendata.aws/noaa-ghcn/) says it of GHCN-Daily (NCEI's
own record of GHCN-Daily states a citation and no licence). Attribution is requested, not required; do not state or
imply that NOAA endorses you, or that modified data is NOAA's original. Cite the product as its record asks.

```{toctree}
:hidden:

hourly.md
daily.md
```