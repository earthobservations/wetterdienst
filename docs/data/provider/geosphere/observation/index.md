# Observation

## Overview

Geosphere Austria (formerly ZAMG) publishes historical observations from its Austrian station
network at 10-minute, hourly, daily and monthly resolution.

Data is served through the Geosphere data hub API (`dataset.api.hub.geosphere.at`) as GeoJSON,
one request per dataset and station over the requested time window. The API is key-less; no
authentication is required. As only historical data is offered, a date range is required when
requesting values.

```{toctree}
:hidden:

10_minutes.md
hourly.md
daily.md
monthly.md
```