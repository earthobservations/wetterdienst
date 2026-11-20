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
elevation, so `elevation` is always null. A station's `end_timestamp` is null while it is still
active.

A station's `wigos_id` is not in the catalogue. It is read from WMO's register OSCAR/Surface, which lists
`0-246-0-<fmisid>` for the stations that it knows (`0-246-0-101520` is Ahtari Myllymäki, fmisid `101520`; read
2026-11-19, 243 of the 437 stations have one, each within 10 km of the position OSCAR gives it). The id is the
exact one: the `station_id` is the local part of a WIGOS id of Finland's issuer (`246`) with issue number `0`,
nothing is matched by name or position, and a station that has no such id has `wigos_id` null. The WMO's own
`0-20000-0-<WMO number>` of a station is not read as its id, so a station with a `wmo_id` has a `wigos_id` that does
not end in it. The register is kept for a week in the cache and for a day in the process; where it cannot be read the
stations still come back, with `wigos_id` null and the warning `wigos-ids-unavailable` (see
[WIGOS ids of the stations](../../dwd/observation/index.md#wigos-ids-of-the-stations)).

Not every station measures every parameter — a station/parameter combination that FMI
doesn't have simply contributes no rows, the same as a station reporting no data for a
requested date range.

## License

Data is © Finnish Meteorological Institute, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See the
[FMI open data licence](https://en.ilmatieteenlaitos.fi/open-data-licence) for the terms.

```{toctree}
:hidden:

hourly.md
daily.md
```
