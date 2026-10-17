# Export

Data can be exported to [SQLite](https://www.sqlite.org/), [DuckDB](https://duckdb.org/docs/sql/introduction),
[InfluxDB](https://github.com/influxdata/influxdb), [CrateDB](https://github.com/crate/crate) and more targets.
A target is identified by a connection string.

Examples:

- sqlite:///dwd.sqlite?table=weather
- duckdb:///dwd.duckdb?table=weather
- influxdb://localhost/?database=dwd&table=weather
- crate://localhost/?database=dwd&table=weather

File targets are identified by their extension:

- file:///path/to/dwd.csv
- file:///path/to/dwd.json
- file:///path/to/dwd.jsonl
- file:///path/to/dwd.xlsx
- file:///path/to/dwd.parquet
- file:///path/to/dwd.feather
- file:///path/to/dwd.zarr
- file:///path/to/dwd.nc

CSV and spreadsheets are written the way ``to_csv`` returns them, with timestamps as ISO strings
and a list of station ids as one comma-separated field. JSON and JSON Lines hold the same records
with the list kept as a list, JSON having arrays of its own, rather than the response envelope
``to_json`` wraps them in. Zarr and NetCDF go through xarray, grouped by the datasets the frame holds;
NetCDF writes its timestamps as CF units, Zarr as the nanoseconds since the epoch it reads back.

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start="2019-01-01",
    end="2020-01-01",
)
stations = request.filter_by_station_id(station_id=[1048, 1050])
stations.values().to_target("influxdb://localhost/?database=dwd&table=weather", if_exists="append")
```

The previous example uses a batch approach meaning each station is written one by one. The first station is written
with the `if_exists` given and every station after it with `append`, so the sink has to accept `append` — which is why
this form passes it explicitly rather than taking the `fail` that `TimeseriesValues.to_target` defaults to.

You could also first collect all data and then write it at once:

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start="2019-01-01",
    end="2020-01-01",
)
stations = request.filter_by_station_id(station_id=[1048, 1050])
stations.values().all().to_target("influxdb://localhost/?database=dwd&table=weather")
```

You could also iterate over the stations and write them one by one:

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=("hourly", "temperature_air"),
    start="2019-01-01",
    end="2020-01-01",
)
stations = request.filter_by_station_id(station_id=[1048, 1050])
for station in stations.values().query():
    station.to_target("influxdb://localhost/?database=dwd&table=weather", if_exists="append")
```

The argument `if_exists` supports the following modes:

- `fail`: Raise an error if the table/file already exists.
- `replace`: Drop the table/file before inserting new values.
- `append`: Insert new values to the existing table (not supported by files).
- `skip`: Do nothing if the table/file already exists.

`replace` is the default on a result — `StationsResult`, `ValuesResult`, anything carrying a frame.
`TimeseriesValues.to_target`, the batch form above, defaults to `fail` instead and then writes
every station after the first with `append`, because there it is one table being filled station by
station rather than one frame being written.

InfluxDB takes `replace` and `append`, which do the same thing there: every write is points, and a
point carrying the timestamp and tags another already has replaces that one, so `replace` does not
clear what is already in the measurement. `fail` and `skip` are refused, because both turn on
whether the measurement exists and this sink never asks.

An append into a database matches columns by name rather than by position, so a frame carrying a
column the table does not have is refused instead of being filed under whatever heading sat in that
position. A frame that is a *subset* of the table's columns is accepted, with nulls for the rest.

Every refusal — a mode the sink does not do, a target that already holds data under `fail`, or a
format or protocol nothing here writes — raises `ExportRefusedError` (from `wetterdienst.exceptions`),
whose message is the whole of what there is to know. A package a sink needs that is not installed
(DuckDB, SQLAlchemy, xarray) raises `MissingDependencyError`, an `ImportError` naming the extra
that installs it. Anything else out of `to_target` is a defect or an environment problem and keeps
its own class and traceback.

The CLI takes the same argument as `--if-exists`, which is what a scheduled acquisition needs —
see [Scheduling](scheduling.md):

```bash
wetterdienst values --provider=dwd --network=observation \
    --parameters=daily/kl/temperature_air_mean_2m --periods=recent --stations=01048 \
    --target="duckdb:////var/lib/wetterdienst/obs.duckdb?table=weather" --if-exists=append
```
