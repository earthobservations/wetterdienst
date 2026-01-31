# Station history

This section documents the station history feature implemented in the project.

## Overview

Wetterdienst now includes station history retrieval and metadata versioning. The feature provides:

- Historical station snapshots: retrieve station metadata as it was at a given date or over a date range.
- Lifecycle events: query events such as created, updated, decommissioned for stations.
- API and request support: available via the Python API and the REST API (when restapi extras are enabled).
- Caching: history responses are cached to improve repeat query performance.

## Python usage

Example usage via the Python API:

```python
from src.wetterdienst import Settings
from src.wetterdienst.provider.dwd.observation import DwdObservationRequest

settings = Settings()

# Get history snapshots for station 1048 between 2010-01-01 and 2020-01-01
request = DwdObservationRequest(
    parameters=[("daily", "kl")],
    settings=settings
).filter_by_station_id(1048)
history = next(request.history.query())
# access history for climate summary daily station 1048 (Dresden Klotzsche)
# naming
for station_name_change in history.history.name.station:
    print(station_name_change)
for operator_name_change in history.history.name.operator:
    print(operator_name_change)
# device changes
for device_change in history.history.device:
    print(device_change)
# geography changes
print(history.history.geography)
# parameter (measurement) changes
print(history.history.parameter)
# missing data periods
print(history.history.missing_data)
```

## REST API

When the REST API is enabled, station history can be queried via:

GET /api/history?provider={provider}&network={network}&station={station_id}&parameters={parameters}&sections={sections}

where sections can be a set of "name", "device", "geography", "parameter", "missing_data".

The response returns JSON with station metadata snapshots and lifecycle events.

## Notes

- Station history relies on provider-specific metadata; availability and granularity may vary by provider.
- Use caching cautiously if station metadata is updated frequently; cache invalidation follows the usual cache TTL
  semantics.
