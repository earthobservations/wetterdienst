# Concepts

The words the rest of the documentation uses, and how a request becomes a result. They mean the same in Python, on
the command line, in the REST API, in the MCP tools and in the app.

## The words

| Word | What it is | Example |
| --- | --- | --- |
| **Provider** | a national service that publishes data | `dwd`, `noaa`, `eccc` |
| **Network** | one kind of data of a provider, with its own request class | `dwd/observation`, `dwd/mosmix`, `wsv/pegel` |
| **Station** | a place where the data is measured or forecast, with an id, a name, a position and the span of its record | `01048`, Dresden-Klotzsche |
| **Resolution** | the time step of the values, from `1_minute` to `annual` | `daily`, `hourly` |
| **Dataset** | a group of parameters a provider publishes together, at one resolution | `climate_summary` |
| **Parameter** | one quantity | `temperature_air_mean_2m` |
| **Period** | the release the data is read from, where a provider splits its record into releases | `historical`, `recent`, `now` |
| **Canonical parameter** | the name of a quantity that means the same whoever reports it, with a unit | `precipitation_amount`, in millimetres |
| **Original name** | the provider's own name for a parameter, accepted wherever the canonical one is | `rsk` for `precipitation_amount` of DWD's daily `kl` |

A parameter is written `resolution/dataset/parameter` (`daily/climate_summary/temperature_air_mean_2m`), or
`resolution/dataset` for every parameter of a dataset (`daily/climate_summary`, or `daily/kl` with the original name
of the dataset). Which there are, per provider, is under [Data](../data/index.md); what a canonical name means and its
unit is in the [glossary](../data/parameters.md), and `coverage` lists them for a network. Every provider is reached
the same way, and a parameter has one unit whichever provider reports it, see [Units](units.md).

## From a request to values

```text
request  ->  stations result  ->  values result
```

1. A **request** says what you want: the `parameters` and, optionally, `periods`, `start` and `end`. Nothing is
   downloaded yet. Python: `DwdObservationRequest(parameters=..., start=..., end=...)`.
2. You **select the stations**: by id, by name (a fuzzy match), by distance from a point, by rank (the nearest
   ones), by a bounding box, with an SQL condition, or all. The answer is a **stations result** whose frame lists the
   stations with the span of their record. Python: `request.filter_by_station_id(...)`, `request.filter_by_name(...)`,
   `request.filter_by_distance(...)`, `request.filter_by_rank(...)`, `request.filter_by_bbox(...)`, `request.all()`.
3. You read the **values** of the selected stations, one frame in the long shape (a row per station, parameter and
   timestamp) or the wide one. Python: `stations.values().all()` for all at once or `stations.values().query()`
   station by station. Each row has a `quality_flags` column with what the source says about the reading.

`interpolate` and `summarize` skip step 2: they take a point and derive a series for it from the stations around, see
[Interpolation & Summary](interpolation.md). `history` is the station's metadata over time, not weather, see
[Station history](station_history.md).

Every result renders itself (a dictionary, JSON, GeoJSON, CSV, a chart) and writes itself to a file or a database, see
[Python API](python-api.md#format) and [Export](export.md). The command line and the REST API are the same steps in
one call: `stations` selects, `values` selects and reads. How the classes behind these steps fit together is in the
[Architecture](../contribution/architecture.md).

## Settings and options

Two kinds of configuration are kept apart, see [Settings and options](settings.md):

- **Options** belong to a request: how its values come back (the shape, whether parameter names are humanized and
  units converted, which unit) and how far a station may be to be interpolated from. Two requests of one process can
  differ in them.
- **Settings** belong to the host: the cache, the network client, the credentials of the providers that need them,
  and what a server allows.

## One vocabulary

A request is spelled alike everywhere, so that what is learned on one surface holds on the others: the REST API takes
`name_threshold`, the MCP tool takes `name_threshold` and the command line `--name-threshold`; a list is plural and
comma-separated (`stations=01048,04411`). See [one vocabulary](restapi.md#one-vocabulary). The failures are alike too,
see [Troubleshooting](troubleshooting.md).

## Where the data comes from

The library downloads from the providers' own open-data servers when you ask, and keeps what it downloaded in a
[cache](python-api.md#caching). It holds no data of its own. The terms the data is published under differ per provider
and are part of every answer of the REST API (`metadata.provider.license` and `attribution`); the
[provider pages](../data/index.md) give them.
