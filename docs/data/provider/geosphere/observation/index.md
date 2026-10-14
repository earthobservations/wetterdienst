# Observation

## Overview

Geosphere Austria (formerly ZAMG) publishes historical observations from its Austrian station
network at 10-minute, hourly, daily and monthly resolution.

Data is served through the Geosphere data hub API (`dataset.api.hub.geosphere.at`) as GeoJSON,
one request per dataset and station over the requested time window. The API is key-less; no
authentication is required. As only historical data is offered, a date range is required when
requesting values.

Each station's `wmo_id` is the WMO station number (five digits, `11021` for Litschau) from the
station list's `Synopstationsnummer`, null for the stations without one. The list also gives 19
stations a seven-digit number (`8989106`); it is no WMO number and is left out.

The list holds a place's long series twice: as a composite series (`zusammengesetzt` is `ja`, the
low ids such as `1` Aflenz) and as the parts it is chained from (Rohrbach `1415` and `1416`). The
number sits on the parts, which can share it, and never on the composite series, so a lookup by
the composite's id has a null `wmo_id`.

```{toctree}
:hidden:

10_minutes.md
hourly.md
daily.md
monthly.md
```