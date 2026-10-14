# Observation

## Overview

Geosphere Austria (formerly ZAMG) publishes historical observations from its Austrian station
network at 10-minute, hourly, daily and monthly resolution.

Data is served through the Geosphere data hub API (`dataset.api.hub.geosphere.at`) as GeoJSON,
one request per dataset and station over the requested time window. The API is key-less; no
authentication is required. As only historical data is offered, a date range is required when
requesting values.

Each station's `wmo_id` is the WMO station number (five digits, `11021` for Litschau) from the
station list's `Synopstationsnummer`, null for the stations without one. Several series of one
place (a station that moved or was renumbered) can share a number. The list also gives 19
stations a seven-digit number (`8989106`); it is no WMO number and is left out.

```{toctree}
:hidden:

10_minutes.md
hourly.md
daily.md
monthly.md
```