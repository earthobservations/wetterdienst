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
- file:///path/to/dwd.jsonl (or `.ndjson`)
- file:///path/to/dwd.geojson
- file:///path/to/dwd.xlsx
- file:///path/to/dwd.parquet
- file:///path/to/dwd.feather
- file:///path/to/dwd.zarr
- file:///path/to/dwd.nc

The extension is read in any case: `file:///path/to/dwd.CSV` is a CSV file.

Everything after `file://` is the path, percent-decoded, and the extension is read from the end of that path. A file
target has no query string: `file:///path/to/dwd.csv?a=1` names a file `dwd.csv?a=1`, has no extension and is refused
as an unknown file type (`ExportRefusedError`) rather than written with its query dropped. A `?` that belongs to the
name of a file is written `%3F`; a `#` is part of the name as it stands.

CSV and spreadsheets are written the way ``to_csv`` returns them, with timestamps as ISO strings
and a list of station ids as one comma-separated field. JSON and JSON Lines hold the same records
with the list kept as a list, JSON having arrays of its own, rather than the response envelope
``to_json`` wraps them in; a `.jsonl` or `.ndjson` file is what ``to_ndjson`` returns. A `.geojson` file is what
``to_format("geojson")`` returns. Zarr and NetCDF go through xarray, grouped by the datasets the frame holds;
NetCDF writes its timestamps as CF units, Zarr as the nanoseconds since the epoch it reads back. A gap is `NaN` in
both (`NaT` in a time, and an empty string in a text column, which has no `NaN`); it was `-999` in Zarr, which a reader
took for a measurement.

```python
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

## Formats by surface

Which format each surface takes. `all` is `stations`, `values`, `interpolate` and `summarize`, the four commands,
routes and MCP tools that return a result; `alerts`, `history` and `stripes` have fewer formats and are described
with their own commands. A file target is chosen by its extension, not by a format, so it has its own column.
`tests/test_export_formats.py` holds this table to the code: a format that a surface takes and the table leaves
out, or the other way round, fails it.

| Format | `to_format` | `to_target` file | CLI `--format` | REST `format` | MCP `format` |
| --- | --- | --- | --- | --- | --- |
| `json` | yes | `.json` | all | all | all |
| `geojson` | yes | `.geojson` | all | all | all |
| `csv` | yes | `.csv` | all | all | all |
| `ndjson` | yes | `.jsonl`, `.ndjson` | stations, values | stations, values | stations, values |
| `html` | yes | no | all | all | all |
| `png` | yes | no | all | all | all |
| `jpg` | yes | no | all | all | all |
| `webp` | yes | no | all | all | all |
| `svg` | yes | no | all | all | all |
| `pdf` | yes | no | all | all | all |
| `xlsx` | no | `.xlsx` | no | no | no |
| `parquet` | no | `.parquet` | no | no | no |
| `feather` | no | `.feather` | no | no | no |
| `zarr` | no | `.zarr` | no | no | no |
| `nc` | no | `.nc` | no | no | no |

`to_format` takes one set of arguments for any format and gives each format those it takes: `with_metadata`,
`with_stations` and `indent` for JSON (a stations result has no `with_stations`), `with_metadata` and `indent` for
GeoJSON, `width`, `height`, `scale` and `max_side` for a chart, and none for CSV and NDJSON. A name that is none of
these is a `TypeError` listing them. A format it does not know is an `UnknownFormatError`, which names the format and lists the
supported ones; it is a `KeyError` and a `ValueError` both, so either `except` catches it.

A number that is not finite, `NaN` or an infinity, is written as `null` in every JSON format: `to_json`, `to_geojson`,
the `.json`, `.geojson`, `.jsonl` and `.ndjson` file targets, and the JSON, GeoJSON and NDJSON answers of the command
line, the REST API and MCP. JSON has no such number (RFC 8259), and a strict parser such as JavaScript's `JSON.parse`
refuses the bare `NaN` and `Infinity` that Python writes. `to_dict` returns the float as it is.

A `.json` or `.jsonl` file holds the records of the frame, where `--format=json` and `to_json` write the response
envelope. `ndjson` is those records alone, a JSON object a line: `to_format("ndjson")` and the `.jsonl` file hold
them, and the lines between the `metadata` head and the `end` line that the command line and the REST API stream
hold the same records (they keep those two lines, and the stream, as the transport's; `interpolate` and `summarize`
have none). The records are the same and the text of a number need not be: polars writes `0.00005` where the
stream has `5e-05`.

InfluxDB stores readings at a time, so a frame without a `timestamp`, such as the stations, or without a `station_id`,
`resolution` or `dataset`, such as an interpolated or summarized result, is refused with an `ExportRefusedError` that
names what is missing; write those to a file or to another database.

## Formats and targets not offered

These are left out on purpose, so that none is asked for again without a reason to change it.

- **`to_pandas` and `to_arrow`**: a result's frame is a polars `DataFrame`, `result.df`, which converts itself
  (`result.df.to_pandas()`, `result.df.to_arrow()`). A method on the result would add two dependencies' types to
  its surface for a call that is one attribute away.
- **ClickHouse**: no sink of its own, and none of the tested SQLAlchemy dialects. A ClickHouse table needs an engine
  and a sort key that wetterdienst cannot choose for the caller. Write a Parquet file and load that.
- **S3, GCS and Azure**: no `s3://`, `gs://` or `az://` target. A bucket needs credentials, a client and retries that
  belong to the caller's deployment; write a file and copy it, or open the store yourself with `fsspec` or `boto3`
  and give it `result.df.write_parquet(...)`.
- **Markdown and HTML tables**: a table is a view of a frame rather than a format of data, and every choice (columns,
  rounding, escaping) is a rendering decision. polars prints the frame, and `to_csv` has the data.
- **xarray as a format**: Zarr and NetCDF are written through xarray, but `to_format` returns text or bytes and an
  `xarray.Dataset` is neither. Build one from `result.df` where you need it.
- **Image file targets**: a chart is a `to_format` or `to_image` result (`png`, `svg`, ...), which you write to a file
  yourself; `to_target` takes frames, and `file://chart.png` is refused as an unknown file type.
