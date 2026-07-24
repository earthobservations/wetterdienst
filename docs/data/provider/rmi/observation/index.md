# Observation

## Overview

RMI's open data service provides observations from its network of automatic weather stations
(AWS) in Belgium, at 10-minute, hourly and daily resolution. Data is served through RMI's
key-less GeoServer WFS endpoint (GeoJSON); no authentication is required.

Each resolution is exposed as its own feature type (`aws_10min`, `aws_1hour`, `aws_1day`). The
provider queries one feature type with a CQL filter (`code = <station> AND timestamp DURING
<start>/<end>`), which returns every parameter for that station in the requested window as one
wide feature per timestamp. Station metadata comes from the `aws_station` feature type.

All timestamps are true UTC instants; daily aggregates are labelled at UTC midnight. The values
therefore need no timezone adjustment.

Each value carries a quality code derived from the source `qc_flags` validation map: `1.0` when
the parameter is validated, `0.0` when it is not.

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
