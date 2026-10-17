# Station history

A station changes over its lifetime: it is renamed, changes operator, moves, gets other instruments, and has
periods in which a parameter is missing. The station history is what the provider publishes of that, and it is
the place to look when a series has a jump that the weather does not explain.

## Overview

- **Sections.** A history has five: `name` (the station's and its operator's names, each with the span it was in
  use), `parameter` (what was measured, with unit and source), `device` (instruments, their height and
  measurement method), `geography` (position and elevation over time) and `missing_data` (a summary and the
  periods without a value). Every record of a section gives its span as `valid_from` and `valid_to`.
- **Which providers.** Only DWD observation publishes one (`DwdObservationRequest`); another network answers a
  request for it with a `NotImplementedError` (`History not implemented for ...`), and the REST API with a 501 of
  the kind `not-implemented`.
- **How it comes.** One history for each station and dataset: DWD publishes its station metadata per dataset,
  so a request for several datasets gives up to one history per station and dataset.
- **No snapshots.** The history is what the provider lists today. It cannot be asked for "the station as it was
  on a date"; to find the entry that applies on a date, filter a section by its `valid_from` and `valid_to`.

## Python usage

Example usage via the Python API:

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

settings = Settings()

# the history of station 1048, one history for each dataset the request names
request = DwdObservationRequest(
    parameters=[("daily", "kl")],
    settings=settings
).filter_by_station_id(1048)
history = next(request.history().query())
# the same as JSON, as `/api/history` and `wetterdienst history` return it
print(history.to_json(sections={"name"}))
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
as for `stations`/`values` (via `--stations` or `--all`) and optionally narrow the result to
specific `--sections`:

```bash
# Full history for station 1048 (Dresden-Klotzsche).
wetterdienst history --provider dwd --network observation --parameters daily/kl --stations 1048

# Only the naming and geography sections.
wetterdienst history --provider dwd --network observation --parameters daily/kl \
  --stations 1048 --sections name,geography
```

Available `--sections` are `name`, `parameter`, `device`, `geography` and `missing_data`.
Each record in a section gives its span as `valid_from` and `valid_to`. For a station or operator
name still in use, and for the station's current position in `geography`, `valid_to` is null.
Each history also gives its station's `station_id` and the `resolution` and `dataset` it belongs
to, whichever sections are asked for. DWD observation publishes station metadata per dataset, so a
request for several datasets answers up to one history per station and dataset.
The `valid_from` and `valid_to` of a record are written as the timestamps of every other result,
ISO 8601 in UTC to the microsecond, such as `1926-05-01T00:00:00.000000+00:00`.
The result is returned as JSON; use `--target file://history.json` to write it to a file
(the target must end with `.json`).

## REST API

When the REST API is enabled, station history can be queried via:

GET /api/history?provider={provider}&network={network}&stations={station_ids}&parameters={parameters}&sections={sections}

where sections can be a set of "name", "device", "geography", "parameter", "missing_data".
As on the command line, each history gives its station's `station_id` and the `resolution` and
`dataset` it belongs to, whichever sections are asked for.

The answer is JSON with the `metadata` block of the [REST API](restapi.md#response-metadata) and a list `histories`
with one entry for each station and dataset.

## Notes

- Station history relies on provider-specific metadata; where a provider publishes none the request is refused, see
  above.
- The responses are cached like any other download, see [Settings](settings.md) for the cache.
