# GHCN (Global Historical Climatology Network)

## Overview

NOAA Global Historical Climatology Network is a collection of **hourly** and **daily** weather data put together from multiple weather
services around the world, even those where at this moment no data is publicly offered. Resolution is fixed on daily,
because this is the most common and maintainable resolution with most observations practiced all over the world.

The GHCN-Hourly dataset represents the previously existing ISD (Integrated Surface Database).

Each station's `wmo_id` is the WMO station number the lists give it, null for the many stations that
have none.

## Hourly precipitation

The `precipitation` column of GHCNh holds the amount of a METAR's precipitation group, which is the
amount since the last routine report: the reports of an hour repeat a growing total, and the
file's documentation (section IX) says to take the last report of the hour for the hour's total.
`hourly` returns it as `precipitation_amount_since_last_routine_report` (called
`precipitation_amount` until GH-2841), one report for each UTC clock hour, stamped with the minute
the file gives it (`:53` for the routine METAR at LAX):

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
source, then 2.8 mm in the METAR). The other elements of `hourly` keep every report of the file
(GH-3000).

## License

The NOAA GHCN incorporates data of multiple weather services across the globe. The 
[NOAA GHCN description](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00861) page
includes more information on the usage, references, qualities etc.

```{toctree}
:hidden:

hourly.md
daily.md
```