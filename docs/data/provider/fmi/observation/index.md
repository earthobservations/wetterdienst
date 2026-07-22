# Observation

## Overview

FMI's Open Data platform provides access to hourly and daily observation values from the
Finnish Meteorological Institute's station network across Finland. No API key or
registration is required — the WFS service is fully public.

Observations are retrieved per station and date range through FMI's WFS stored queries
(`fmi::observations::weather::simple` for hourly, `fmi::observations::weather::daily::simple`
for daily). FMI caps a single sub-daily request at 168 hours (7 days), so longer hourly
ranges are transparently fetched in consecutive windows and stitched back together.

Station metadata comes from the `fmi::ef::stations` catalogue. It does not expose station
elevation, so `height` is always null. A station's `end_date` is null while it is still
active.

Not every station measures every parameter — a station/parameter combination that FMI
doesn't have simply contributes no rows, the same as a station reporting no data for a
requested date range.

## License

Data is © Finnish Meteorological Institute, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See
[FMI Open Data](https://en.ilmatieteenlaitos.fi/open-data) for further information and
usage conditions.

```{toctree}
:hidden:

hourly.md
daily.md
```
