---
file_format: mystnb
kernelspec:
  name: python3
---

# Getting more than the limit

A how-to for the request that a server refuses for its size: a 400 of the kind `limit-exceeded`, which says, for
instance, "This request would return about 614,866 rows, more than the 500,000 this server sends as one answer", or
"This request reads 1284 stations, more than the 100 this server allows for one request". The REST API and the MCP
tools hold a request to [three limits](restapi.md#limits) so that one request cannot take a server down; the library
and the command line have none. This page lists the ways to the data you want, in the order to try them, and each has
a command or a snippet to start from. What the limits are and how a row is counted is told once, under
[Limits](restapi.md#limits); the settings are in [Settings](settings.md).

| Try | When it fits | The refusal it answers |
| --- | --- | --- |
| [Ask for less](#ask-for-less) | you need less than you asked for: a window, a parameter, a few stations | all of them |
| [Stream it](#stream-it) | one answer of up to the streaming limit, read as it arrives or saved to a file | `rows` |
| [Ask in slices](#ask-in-slices) | more than the streaming limit, a request that runs into the timeout, or a client that cannot stream | `rows`, `stream_rows`, `stations` |
| [Leave the server](#leave-the-server) | a long record, or a whole network, for analysis or a database | `stream_rows`, `stations` |
| [Run your own server](#run-your-own-server) | many people need more than the defaults, and you can pay for it | all of them |

An [assistant](#from-an-assistant) and the [app](#from-the-app) ask the same API and meet the same refusals.

## Ask for less

A request is counted before anything is downloaded, so a refusal costs nothing, and the text of it names the number
that was exceeded. The rows of `values` are an estimate and an upper bound (see [Limits](restapi.md#limits) for how
it is made): the readings each station can hold in the window, times the parameters. A request without a `timestamp`
is counted over the whole record of its stations, which is why the first thing to add to a refused request is a
window.

The defaults, read from the settings, show what one parameter of one station comes to:

```{code-cell}
from wetterdienst import Settings

settings = Settings()
READINGS_PER_DAY = {"1_minute": 1440, "5_minutes": 288, "10_minutes": 144, "hourly": 24, "daily": 1}

print(f"{'':>10} {'as one body':>12} {'streamed':>12}   years of one parameter of one station")
for resolution, per_day in READINGS_PER_DAY.items():
    body = settings.restapi_max_rows / per_day / 365.25
    streamed = settings.restapi_max_stream_rows / per_day / 365.25
    print(f"{resolution:>10} {body:>12,.1f} {streamed:>12,.1f}")

# rows a day are readings of the resolution, times parameters, times stations: hourly, 5 parameters, 20 stations
print(f"\n{settings.restapi_max_rows // (24 * 5 * 20)} days of 24 * 5 * 20 rows fit in one body")
```

So the limits meet 10-minute and finer data (ten years of one 10-minute parameter is about 526,000 rows), and anything with
many stations and parameters; a century of daily readings of one station is 36,500 rows and never meets them. Three
things narrow a request, each by the factor it removes:

- **The window.** `timestamp=2020` is the year, `timestamp=2020-08` the month and `timestamp=2020-08-01/2020-08-05`
  the five days; a date covers everything it names, see [Values](restapi.md#values).
- **The parameters.** `daily/kl` is every parameter of the dataset; `daily/climate_summary/temperature_air_mean_2m` is
  one. In the long shape each parameter adds its rows; in the wide shape a timestamp is one row whatever the number of
  its parameters, so the wide shape counts less.
- **The stations.** A list of ids, or a smaller `rank`, `distance` or bounding box. A `rank` counts as that many
  stations, so `rank=250` of a `values` request is refused where the limit is 100.

`GET /api/version` reports the limits of the instance you are talking to under `limits`, and that is the number to
size a request with: a server sets its own (see [Run your own server](#run-your-own-server)), and the defaults above
are not the hosted instance's.

```bash
http localhost:7890/api/version
```

## Stream it

An answer of `format=ndjson` or `format=csv` is sent as it is built, one station at a time, so the server does not hold
it and the client reads the first rows while the later stations are still downloaded. It is held to the `stream_rows`
limit instead of `rows`, 10,000,000 by default: twenty times as many. A request that is refused for its rows and fits
the streaming limit is told so in its `detail`. The lines and headers of both formats are described under
[Streaming](restapi.md#streaming); which to take is a matter of what reads it:

| | `format=ndjson` | `format=csv` |
| --- | --- | --- |
| Reads well in | a program that checks what it received | a file, a spreadsheet, polars, DuckDB, `curl -o` |
| The metadata | the first line (`metadata`) and the last (`end`: counts and every warning) | the `X-Wetterdienst-*` headers, sent before the first row: no row count, and only the warnings known by then |
| The values | JSON: numbers and `null` as they are | text: a reader guesses the types, see below |
| An answer that is whole | ends with the `end` line | the transfer is complete |
| A failure after the answer began | the last line is `error`, with the problem | the connection is cut, and the server logs it |

Take NDJSON when a program reads it and the answer must be known to be complete: a stream with no `end` line was cut
short. Take CSV for a file. `curl` saves a CSV with `-o`; `--fail-with-body` makes a refusal an error, where without it
the problem is written into the file and the exit code is 0:

```bash
curl --fail-with-body -o dresden.csv "http://localhost:7890/api/values?provider=dwd&network=observation&parameters=daily/climate_summary/temperature_air_mean_2m&stations=01048&timestamp=2020&format=csv"
```

The same line reads ten million rows; it is a year of one station here so that it runs in a second. A CSV has no end
line, so a cut connection is the only sign of a failure after the answer began: `curl` ends a chunked transfer that
stops before its last chunk with exit code 18, and a client of yours has to fail on it too.

Polars reads the file lazily. A CSV is text, and polars guesses: `station_id` is `01048` and becomes the number 1048
unless it is told, and `quality_flags` (`10` here, `G,measurement:T` elsewhere) is a number until a row says
otherwise. Name both as strings:

```python
# needs the dresden.csv of the curl command above
import polars as pl

lazy = pl.scan_csv(
    "dresden.csv",
    schema_overrides={"station_id": pl.String, "quality_flags": pl.String},
    try_parse_dates=True,
)
lazy.select(pl.col("value").mean()).collect()
```

NDJSON is read line by line with the standard library, so that nothing but one line is in memory. The first line is the
`metadata` and the last the `end`, and the rows are saved to a file that polars scans (it takes the lines of a file as
rows, so the two lines that are not rows stay out of it). The `error` line is raised, and a loop that ends without
`end` is a stream that was cut short. The example is a local server (the REST samples of these pages use
`localhost:7890`; the hosted instance is `https://wetterdienst.eobs.org/api`):

```python
# needs a server on localhost:7890
import json
import urllib.parse
import urllib.request

import polars as pl

BASE = "http://localhost:7890/api"
query = urllib.parse.urlencode(
    {
        "provider": "dwd",
        "network": "observation",
        "parameters": "daily/climate_summary/temperature_air_mean_2m",
        "stations": "01048,04411",
        "timestamp": "2020",
        "format": "ndjson",
    }
)

with urllib.request.urlopen(f"{BASE}/values?{query}") as response, open("rows.ndjson", "w") as out:
    for line in response:
        record = json.loads(line)
        if "metadata" in record:
            continue
        if "error" in record:
            raise RuntimeError(record["error"]["detail"])
        if "end" in record:
            end = record["end"]
            break
        out.write(line.decode())
    else:
        raise RuntimeError("the stream was cut short: it has no `end` line")

print(end["counts"])  # {'stations': 2, 'rows': 732}
pl.scan_ndjson("rows.ndjson").group_by("station_id").agg(pl.col("value").mean()).collect()
```

`requests` and `httpx` do the same with `iter_lines()` on a streamed response (`requests.get(url, stream=True)`,
`httpx.stream("GET", url)`). `ndjson` refuses `sql_values` and `with_stations` (a 400), and `csv` with `sql_values` is
one body, held to `rows`. A stream may run longer than the timeout, which holds between two chunks; but the first
station is read before the response begins, so a station that takes longer than the timeout to download is a 504 (ask
again: what was downloaded is cached).

## Ask in slices

A request that is over `stream_rows`, one whose station takes longer than the timeout, or a client that cannot
stream, asks in parts and puts them together. Each part is a request that fits; a part that fails is asked again
alone, and what the server downloaded is cached, so the second try is cheaper. Parts are of two kinds: windows of the
`timestamp`, and batches of stations.

The window comes from the limit: the rows of a day are the readings a day holds at the resolution, times the
parameters, times the stations, and as many whole days as fit under `max_rows` of `GET /api/version` are one call. The
window is whole days written as dates (`2020-01-01/2020-01-31` is all of both days), so that two windows neither
overlap nor leave a gap. A server that answers 429 (the web app limits what a client counts against it, see
[Rate limit](app.md#rate-limit)), 503 or 504 says when to ask again in `Retry-After`; a 400 has to be rephrased, and
its `detail` says how.

```python
# needs a server on localhost:7890
import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import polars as pl

BASE = "http://localhost:7890/api"


def get(path: str, **query: str) -> dict:
    """Ask the API and give the JSON of the answer; wait and ask again when it is busy or ran out of time."""
    url = f"{BASE}/{path}?{urllib.parse.urlencode(query)}"
    for _ in range(5):
        try:
            with urllib.request.urlopen(url) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in {429, 503, 504}:
                # a 400 has to be rephrased: the body is the problem and its `detail` says how
                raise RuntimeError(json.load(error)["detail"]) from error
            time.sleep(int(error.headers.get("Retry-After", 30)))
    raise RuntimeError(f"/{path} was not answered in 5 tries")


limits = get("version")["limits"]

# the readings a day holds at each resolution; a parameter is `resolution/dataset/parameter`
READINGS_PER_DAY = {"1_minute": 1440, "5_minutes": 288, "10_minutes": 144, "hourly": 24, "daily": 1}


def windows(start: dt.date, end: dt.date, parameters: list[str], stations: int):
    """Cut start..end into runs of whole days that the limit for one answer allows."""
    per_day = sum(READINGS_PER_DAY[parameter.split("/")[0]] for parameter in parameters) * stations
    # a server with no limit (0) is asked for ten years at a time
    days = limits["max_rows"] // per_day if limits["max_rows"] else 3660
    if days < 1:
        raise ValueError("a single day is over the limit: ask for fewer parameters or stations")
    while start <= end:
        stop = min(start + dt.timedelta(days=days - 1), end)
        yield start, stop
        start = stop + dt.timedelta(days=1)


# 20 years of 10-minute readings: 1,051,200 rows, three calls with the default limit
parameters = ["10_minutes/temperature_air/temperature_air_2m"]
frames = []
for start, stop in windows(dt.date(2000, 1, 1), dt.date(2019, 12, 31), parameters, stations=1):
    answer = get(
        "values",
        provider="dwd",
        network="observation",
        parameters=",".join(parameters),
        stations="01048",
        timestamp=f"{start}/{stop}",
    )
    frames.append(pl.DataFrame(answer["values"], infer_schema_length=None))
df = pl.concat(frames, how="vertical_relaxed")
```

More stations than a call may read (100 by default) are batches of their ids. A `rank` has no offset (it is the nearest
N, with N at most the limit), so the batches come from a listing: `stations` is held to the rows of the listing and not
to the limit of stations, and with a `timestamp` it names only the stations that have a record in the window. The
`metadata` of each answer carries `request.stations.ids`, the stations the answer holds (for up to 100 of them): one of
the batch that is missing from it had no readings in that window. The window of each batch is cut for the size of the
batch, so the two loops nest and each call fits both limits:

```python
# needs a server on localhost:7890, and the get() and windows() of the example above
parameters = ["daily/climate_summary/temperature_air_mean_2m"]
first, last = dt.date(2024, 1, 1), dt.date(2024, 12, 31)

# the nearest 250 stations with a record in the window
listing = get(
    "stations",
    provider="dwd",
    network="observation",
    parameters=",".join(parameters),
    latitude="51.1",
    longitude="13.7",
    rank="250",
    timestamp=f"{first}/{last}",
)
ids = [station["station_id"] for station in listing["stations"]]

frames = []
size = limits["max_stations"] or len(ids)  # 0 is no limit
for i in range(0, len(ids), size):
    batch = ids[i : i + size]
    for start, stop in windows(first, last, parameters, len(batch)):
        answer = get(
            "values",
            provider="dwd",
            network="observation",
            parameters=",".join(parameters),
            stations=",".join(batch),
            timestamp=f"{start}/{stop}",
        )
        read = answer["metadata"]["request"]["stations"]["ids"]
        print(f"{start} to {stop}: {len(read)} of {len(batch)} stations had readings")
        if answer["values"]:
            frames.append(pl.DataFrame(answer["values"], infer_schema_length=None))
df = pl.concat(frames, how="vertical_relaxed")
```

On a server that sets no limit of stations, `ids` of an answer of more than 100 stations is `null`; read the
`station_id` column of its `values` then.

## Leave the server

The Python library and the command line have no limits: nothing counts rows, and a request is as large as the files of
the provider. What to choose is where the answer goes, not how much of it there is.

`TimeseriesValues.to_target` reads one station at a time and writes each as it is read, so a request holds one
station's frame in memory, not the answer. A database takes the stations one after the other (`replace` for the first,
`append` for the rest), and SQL does the rest. A file takes one frame: `append` is refused for files, so a request of
several stations written to one `file://` target fails at the second station, and a file is written for each station
instead and read together (Parquet, here, which polars and DuckDB read as one). The targets and the `if_exists` modes
are on the [Export](export.md) page.

```{code-cell}
import tempfile
from pathlib import Path

import duckdb
import polars as pl

from wetterdienst.exceptions import ExportRefusedError
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
    start="2019-01-01",
    end="2020-12-31",
)
stations = request.filter_by_station_id(station_id=("01048", "04411"))
directory = Path(tempfile.mkdtemp())

# into a database, a station at a time: the second is appended to the first
database = directory / "weather.duckdb"
stations.values().to_target(f"duckdb:///{database}?table=weather", if_exists="replace")
with duckdb.connect(str(database)) as connection:
    print(connection.sql("SELECT station_id, count(*) AS rows FROM weather GROUP BY station_id ORDER BY 1").pl())

# into files, one for each station, which polars reads as one
for result in stations.values().query():
    station_id = result.df.get_column("station_id")[0]
    result.to_target(f"file://{directory}/{station_id}.parquet")
print(pl.scan_parquet(directory / "*.parquet").group_by("station_id").len().sort("station_id").collect())

# one file for both is refused at the second station
try:
    stations.values().to_target(f"file://{directory}/all.parquet", if_exists="replace")
except ExportRefusedError as error:
    print("refused:", error)
```

The command line takes the same targets with `--target`, and writes the whole answer at once, so its memory is the size
of the answer (the `.all()` of the library); it is the way to a file or a database from a shell or a schedule, see
[Scheduling](scheduling.md):

```bash
wetterdienst values --provider=dwd --network=observation --parameters=daily/climate_summary/temperature_air_mean_2m --stations=01048 --timestamp=2020 --target=file://dresden.parquet
```

For an answer that must not be held at all, use the library's `query()` loop or `to_target` to a database, as above.
The [Python API](python-api.md#values) page has the requests.

## Run your own server

The limits are the settings of the host, so a server of your own sets them for its users:
`WD_RESTAPI_MAX_STATIONS`, `WD_RESTAPI_MAX_ROWS`, `WD_RESTAPI_MAX_STREAM_ROWS` and `WD_RESTAPI_TIMEOUT`, `0` for none,
see the [table of the limits](restapi.md#limits) and [Settings](settings.md). The instance reports what it was started
with at `GET /api/version`, which is where a client such as the loops above reads it.

```bash
WD_RESTAPI_MAX_ROWS=2000000 WD_RESTAPI_MAX_STATIONS=500 WD_RESTAPI_TIMEOUT=300 wetterdienst restapi --listen 0.0.0.0:7890
```

The limits are what keeps a request from taking the server with it: an answer sent as one body is built in memory
(a row of the long JSON is about 200 bytes, so half a million rows is about 100 MB, per request, with 32 at once by
default), a request holds a thread until its work is done, and a reverse proxy in front has a timeout of its own, 60
seconds usually, that a longer `WD_RESTAPI_TIMEOUT` does not move. A server that others reach should raise one limit
at a time and put a gateway in front that limits each client; [Running it for others](restapi.md#running-it-for-others)
says what else to set. In a container, pass them as environment variables of the image (`docker run --env ...`), see
[Docker](docker.md).

## From an assistant

The tools of the [MCP server](mcp.md) are routes of the REST API run in process, so a tool is held to the same limits,
and the refusal comes back to the assistant as the text of the problem: `HTTP error 400: Bad Request - This request
would return about 614,866 rows, more than the 500,000 this server sends as one answer. ...`. A tool answers one body
and cannot stream, so the ways that apply are to ask for less and to ask in slices:

- Ask for a window: a day, a month or a year, "the daily maximum of 2024". The assistant can follow the refusal, which
  says what to shorten, and ask again for the next window.
- Ask for fewer stations (the nearest three) or one parameter, not a dataset.
- For a long series, a whole network or a file to keep, ask the assistant to write a script that uses the
  [library](#leave-the-server) or the loops of this page against the REST API: every row an assistant reads goes through
  its context, which holds a small part of 500,000 rows.

## From the app

The Explorer calls the REST API, so a request it makes is held to the limits of the backend, and when one is exceeded
it shows what the backend answered: the limit, the number the request came to and how to narrow it (see the
[Web app](app.md)). Follow the text in the form: a shorter date range, fewer parameters or fewer stations. For more than
that, leave the app for the data and keep it for finding what to read: the app serves the API of its backend under
`/api`, so the requests of this page work against the address of the app too (`https://wetterdienst.eobs.org/api/...`
for the hosted instance), counted by the [rate limit](app.md#rate-limit) of the app.
