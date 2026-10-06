# Station history

This section documents the station history feature implemented in the project.

## Overview

Wetterdienst includes station history retrieval and metadata versioning. The feature provides:

- Historical station snapshots: retrieve station metadata as it was at a given date or over a date range.
- Lifecycle events: query events such as created, updated, decommissioned for stations.
- API and request support: available via the Python API and the REST API (when restapi extras are enabled).
- Caching: history responses are cached to improve repeat query performance.

## Python usage

Example usage via the Python API:

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

settings = Settings()

# Get history snapshots for station 1048 between 2010-01-01 and 2020-01-01
request = DwdObservationRequest(
    parameters=[("daily", "kl")],
    settings=settings
).filter_by_station_id(1048)
history = next(request.history.query())
# access history for climate summary daily station 1048 (Dresden Klotzsche)
# the station it belongs to, "01048" as the stations frame spells it
print(history.history.station_id)
# the resolution and dataset it was read for, "daily" and "climate_summary"
print(history.history.resolution, history.history.dataset)
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

## Command line

The same history is available through the `history` command. Select stations the same way
as for `stations`/`values` (via `--station` or `--all`) and optionally narrow the result to
specific `--sections`:

```bash
# Full history for station 1048 (Dresden-Klotzsche).
wetterdienst history --provider dwd --network observation --parameters daily/kl --station 1048

# Only the naming and geography sections.
wetterdienst history --provider dwd --network observation --parameters daily/kl \
  --station 1048 --sections name,geography
```

Available `--sections` are `name`, `parameter`, `device`, `geography` and `missing_data`.
Each record in a section gives its span as `valid_from` and `valid_to`. For a station or operator
name still in use `valid_to` is null; for the station's current position in `geography` it is the
time the history was read.
Each history also gives its station's `station_id` and the `resolution` and `dataset` it belongs
to, whichever sections are asked for. DWD observation publishes station metadata per dataset, so a
request for several datasets answers up to one history per station and dataset.
The result is returned as JSON; use `--target file://history.json` to write it to a file
(the target must end with `.json`).

## REST API

When the REST API is enabled, station history can be queried via:

GET /api/history?provider={provider}&network={network}&station={station_id}&parameters={parameters}&sections={sections}

where sections can be a set of "name", "device", "geography", "parameter", "missing_data".
As on the command line, each history gives its station's `station_id` and the `resolution` and
`dataset` it belongs to, whichever sections are asked for.

The response returns JSON with station metadata snapshots and lifecycle events.

## Notes

- Station history relies on provider-specific metadata; availability and granularity may vary by provider.
- Use caching cautiously if station metadata is updated frequently; cache invalidation follows the usual cache TTL
  semantics.
