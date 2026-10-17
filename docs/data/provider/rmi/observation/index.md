# Observation

## Overview

RMI's open data service provides observations from its network of automatic weather stations
(AWS) in Belgium, at 10-minute, hourly and daily resolution. Data is served through RMI's
key-less GeoServer WFS endpoint (GeoJSON); no authentication is required.

Each resolution is exposed as its own feature type (`aws_10min`, `aws_1hour`, `aws_1day`). The
provider queries one feature type with a CQL filter (`code = <station> AND timestamp >= <start>
AND timestamp <= <end>`), which returns every parameter for that station in the requested window as one
wide feature per timestamp. Station metadata comes from the `aws_station` feature type.

All timestamps are true UTC instants; daily aggregates are labelled at UTC midnight. The values
therefore need no timezone adjustment.

Each value carries a code in `quality_flags` derived from the source `qc_flags` validation map: `1`
when the parameter is validated, `0` when it is not.

A value outside the physical range of its parameter, which no sensor can have produced, is null and
keeps what the source wrote as the last token of `quality_flags`, `raw:4021` (`0,raw:4021`). The
bounds are generous, so a record is never outside them, and depend on the resolution where the
amount grows with the span: rain is held to 200 mm in 10 minutes, 600 mm in an hour and 2,000 mm in a
day, sunshine to 10, 60 and 1,440 minutes (the span), and a gust to 60 m/s. The daily layer has a `temp_max` of
1003 to 6013 degrees on 48 days (station 6414 on 2003-08-06: 4021), a `temp_avg` of 72 to 342 degrees
on 21, a relative humidity of -6999 % (6494), a radiation of -99999 W/m2 (6484), a sunshine of
3,808 to 13,851 minutes in a day (6459, 6477) and a gust of 81.5 m/s (station 6414 on 2003-10-09);
the hourly layer has gusts of 569.7 and 445.3 m/s, the 81.5 m/s again, and 29 hours of more than 60
minutes of sunshine (63.86, 373 and 1,282 minutes among them). The next highest gust of the daily layer is 51.05 m/s (6434, 2002-12-30), which
stays. The long shape drops the rows without a value by default, so the token shows with
`drop_nulls=False`.

## Sunshine of station 6477 (GH-3031)

The `sun_duration` of station 6477 is null, with the source's value as `raw:<value>` in `quality_flags`
(`0,raw:980`), in three periods of every resolution (10-minute, hourly, daily), because the sensor
was stuck or dead and the values lie inside every range. The source does not say so: its `validated`
flag for sunshine is false on 7,720 of the 8,134 days of the daily layer (2004-06-30 to 2026-10-16,
read 2026-10-17), so `quality_flags` `0` tells nothing here.

- From 2016-04-30 to 2017-05-31 (397 days, 470 to 1,440 minutes) the daily sunshine follows the length
  of the day in steps of ten minutes, whatever the weather: 980 minutes on each day from 2016-06-06 to
  2016-07-05 and again on 2016-12-22, 910 minutes on 2016-05-10 with a mean radiation of 93.6 W/m2.
  Thirteen of these days read exactly 1,440 minutes, a full day of sunshine in December (2016-12-23
  to 2017-01-01, 2017-01-06, 2017-02-18 and 2017-02-19). The 10-minute values of 2016-12-24 are all
  10 (144 of 144) and the hourly ones all 60. The longest day of Belgium is 998 minutes at 51.5 degrees
  north (with refraction), so a range alone would reach the 1,440 minutes and not the 980.
- From 2015-04-25 to 2015-08-19 (117 days) and from 2017-06-02 to 2017-09-19 (110 days) every day
  reads 0 minutes, in summer: the sensor did not measure (all 24 hours of 2015-06-15 and 2017-07-15
  read 0, and so do the 10-minute values of 2017-07-15 from 10:00 to 14:00).

The periods are a list in the reader (`_NO_SUNSHINE`), read off the layers on 2026-10-17; the rest of
the station's series, and the other stations, are not touched. Other sensors of 6477 were not checked.

## License

Data is © RMI (Royal Meteorological Institute of Belgium) and licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
See [geo.be — RMI AWS](https://www.geo.be/catalog/details/RMI_AWS_WFS) for further information
and usage conditions.

```{toctree}
:hidden:

10_minutes.md
hourly.md
daily.md
```
