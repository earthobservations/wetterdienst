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
bounds are generous, so a record is never outside them: the daily layer has a `temp_max` of 1003 to
6013 degrees on 48 days (station 6414 on 2003-08-06: 4021), a `temp_avg` of 72 to 342 degrees on 21,
a relative humidity of -6999 % (6494) and a radiation of -99999 W/m2 (6484). Merely odd values stay:
the daily gust of 81.5 m/s of station 6414 on 2003-10-09 is below the 115 m/s of the highest gust
measured. The long shape drops the rows without a value by default, so the token shows with
`drop_nulls=False`.

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
