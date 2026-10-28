<h1 align="center">
  <img src="https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/assets/icon.svg" alt="" width="56" height="56" align="absmiddle"/>
  Wetterdienst
</h1>

<p align="center"><strong>Open weather data for humans</strong></p>

<!-- docs-start -->

<p align="center">
  <a href="https://github.com/earthobservations/wetterdienst/actions?workflow=Tests"><img src="https://github.com/earthobservations/wetterdienst/actions/workflows/tests.yml/badge.svg?branch=main" alt="CI status"/></a>
  <a href="https://wetterdienst.readthedocs.io/en/latest/?badge=latest"><img src="https://readthedocs.org/projects/wetterdienst/badge/?version=latest" alt="Documentation status"/></a>
  <a href="https://app.codecov.io/gh/earthobservations/wetterdienst"><img src="https://codecov.io/gh/earthobservations/wetterdienst/branch/main/graph/badge.svg" alt="Code coverage"/></a>
  <br/>
  <a href="https://pypi.org/project/wetterdienst/"><img src="https://img.shields.io/pypi/v/wetterdienst.svg" alt="PyPI version"/></a>
  <a href="https://anaconda.org/conda-forge/wetterdienst"><img src="https://img.shields.io/conda/vn/conda-forge/wetterdienst.svg" alt="Conda version"/></a>
  <a href="https://pypi.org/project/wetterdienst/"><img src="https://img.shields.io/pypi/pyversions/wetterdienst.svg" alt="Python version compatibility"/></a>
  <a href="https://github.com/earthobservations/wetterdienst/blob/main/LICENSE.md"><img src="https://img.shields.io/github/license/earthobservations/wetterdienst" alt="Project license"/></a>
  <a href="https://pepy.tech/projects/wetterdienst"><img src="https://static.pepy.tech/personalized-badge/wetterdienst?period=month&amp;units=international_system&amp;left_color=grey&amp;right_color=blue&amp;left_text=PyPI%20downloads/month" alt="PyPI downloads"/></a>
  <a href="https://doi.org/10.5281/zenodo.3960624"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.3960624.svg" alt="Citation reference"/></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/assets/readme-stripes.png" alt="Warming stripes for Hohenpeißenberg, Germany: one stripe per year from 1781 to 2025, blue for cold years and red for warm ones" width="640" height="80"/>
  <br/>
  <sub>Hohenpeißenberg, Germany, 1781 to 2025: the mean air temperature of each year, fetched and drawn with wetterdienst.</sub>
  <br/>
  <strong>Global warming is not an opinion.</strong> <em>Erderwärmung ist keine Meinung.</em>
</p>

> [!WARNING]
> This library is a work in progress!
> Breaking changes should be expected until a 1.0 release, so version pinning is recommended.
> What 1.0 promises, and what to change to upgrade, is in
> [Compatibility](https://wetterdienst.readthedocs.io/en/latest/usage/compatibility.html) and
> [Migrating from 0.139.0](https://wetterdienst.readthedocs.io/en/latest/usage/migrating.html).

Wetterdienst gives you weather, climate and hydrology data from 22 national services through one
interface: one way to find a station, one way to ask for values, one shape of result. It is a
[polars](https://pola.rs/)-based Python library, a command line client, a REST API, an MCP
endpoint and a web app, all serving the same data.

Contributions and feedback are very welcome. We do not use most of this data ourselves, so what
you need is what tells us what to build next. Hand in an issue or a PR.

## Features

- Stations, values and station history (metadata changes) through one request model, with stations found
  by name, id, distance from a point, bounding box or rank
- Unit conversion, and interpolation and summarization for a point between stations
- DWD weather alerts (CAP warnings) with GeoJSON geometry, by community or district
- SQL queries over results, and export to CSV, JSON, Excel, Parquet and Zarr files and to SQLite,
  PostgreSQL, CrateDB, InfluxDB and DuckDB
- A command line client, a REST API with a public Docker image, and an MCP (Model Context Protocol)
  endpoint, so LLM agents can query the data as tools
- A web app with a map-based explorer, forecasts, climate stripes, a glossary and an overview of the
  providers, at [wetterdienst.eobs.org](https://wetterdienst.eobs.org/)

## Setup

```bash
pip install wetterdienst           # from PyPI
pip install "wetterdienst[export]" # with an extra
pip install git+https://github.com/earthobservations/wetterdienst  # most recent
```

Extras: `bufr`, `cratedb`, `duckdb`, `eccodes`, `excel`, `export`, `influxdb`, `interpolation`,
`knmi`, `mcp`, `mysql`, `pdf`, `plotting`, `postgresql`, `radar`, `radarplus`, `restapi`, `sql`.
Check the installation with `wetterdienst --help`.

On Linux, a process that imports ecCodes (`bufr` or `eccodes` extra) itself, before wetterdienst
does, and then imports `pyproj` (which `radarplus` brings) can crash at exit
([ecmwf/eckit#354](https://github.com/ecmwf/eckit/issues/354)). See
[known issues](https://wetterdienst.readthedocs.io/en/latest/known_issues.html#crash-at-exit-with-eccodes-and-pyproj-on-linux)
for the workaround.

Prefer Docker? The image ships with most of the extras:

```bash
docker run -ti ghcr.io/earthobservations/wetterdienst wetterdienst --version
```

See the [Docker](https://wetterdienst.readthedocs.io/en/latest/usage/docker.html) chapter for
running the REST API and the app from the image.

## Examples

Every example runs as it is and needs no account or key: DWD is open. A provider that needs one says
so in the table below. The same request, the flood of August 2002 at Zinnwald-Georgenfeld, comes
three ways, from Python, the command line and the REST API.

### Your first request, with every setting and option

`Settings` are the host's: the cache, the network client, the credentials. They are one value for the
whole process and are also read from `WD_*` variables. `Options` are a request's: how its values come
back, and how far a station may be to be interpolated from. They are also read from `WD_TS_*`
variables. Each is written out here at its default, so you see what can be turned; leave out what you
do not need. [Settings and options](https://wetterdienst.readthedocs.io/en/latest/usage/settings.html)
lists all of them.

```python
from wetterdienst import Options, Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

# The host, one value for the whole process. cache_disable is WD_CACHE_DISABLE, and so on.
settings = Settings(
    cache_disable=False,  # default: downloads are kept in the cache
    fetch_ahead=4,  # default: stations whose files are fetched while one is parsed, 0 is off
    use_certifi=False,  # default: the system's certificates
    fsspec_client_kwargs={"timeout": 30},  # default: a User-Agent header and 30 s, merged with yours
)
# Also cache_dir (default: your platform's cache directory) and auth, the keys of the providers
# that need one (WD_AUTH__*, see the provider pages). DWD needs none.

# One request. shape is WD_TS_SHAPE, and so on.
options = Options(
    humanize=True,  # default: canonical parameter names, not the provider's own codes
    shape="long",  # default: one row per value, "wide" has a column per parameter
    convert_units=True,  # default: one unit per quantity, whichever provider reports it
    unit_targets={},  # default: none, {"temperature": "degree_fahrenheit"} changes one quantity
    drop_nulls=True,  # default: leave out rows without a value (long shape only)
    skip_empty=False,  # default: keep every station; True skips one that covers too few readings:
    skip_threshold=0.95,  # less than this share of what its window can hold,
    skip_criteria="min",  # judged by its "min", "mean" or "max" parameter
    station_window_end_buffer=None,  # default: days a station may have ended before the window, by resolution
)

request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "precipitation_amount")],  # or "daily/kl" for a whole dataset
    start="2002-08-11",  # default: the start of the station's record
    end="2002-08-13",  # default: its end
    periods=None,  # default: chosen from the window; "recent", "historical" or "now" pins one
    settings=settings,
    options=options,
)

# Choose the stations by id, or instead filter_by_name("Zinnwald-Georgenfeld"),
# filter_by_rank(latlon=(50.73, 13.75), rank=3), filter_by_distance(latlon=(50.73, 13.75), distance=25),
# filter_by_bbox(left=13, bottom=50, right=15, top=51), filter_by_sql("region = 'Sachsen'") or all()
stations = request.filter_by_station_id(station_id=("05779",))
stations.df
# ┌────────────┬─────────────────┬────────────┬─────────────────────────┬───┬───────────┬───────────┬──────────────────────┬─────────┐
# │ resolution ┆ dataset         ┆ station_id ┆ start_timestamp         ┆ … ┆ longitude ┆ elevation ┆ name                 ┆ region  │
# │ ---        ┆ ---             ┆ ---        ┆ ---                     ┆   ┆ ---       ┆ ---       ┆ ---                  ┆ ---     │
# │ str        ┆ str             ┆ str        ┆ datetime[μs, UTC]       ┆   ┆ f64       ┆ f64       ┆ str                  ┆ str     │
# ╞════════════╪═════════════════╪════════════╪═════════════════════════╪═══╪═══════════╪═══════════╪══════════════════════╪═════════╡
# │ daily      ┆ climate_summary ┆ 05779      ┆ 1971-01-01 00:00:00 UTC ┆ … ┆ 13.7516   ┆ 877.0     ┆ Zinnwald-Georgenfeld ┆ Sachsen │
# └────────────┴─────────────────┴────────────┴─────────────────────────┴───┴───────────┴───────────┴──────────────────────┴─────────┘

result = stations.values().all()
values = result.df
values
# ┌────────────┬────────────┬─────────────────┬──────────────────────┬─────────────────────────┬───────┬───────────────┐
# │ station_id ┆ resolution ┆ dataset         ┆ parameter            ┆ timestamp               ┆ value ┆ quality_flags │
# │ ---        ┆ ---        ┆ ---             ┆ ---                  ┆ ---                     ┆ ---   ┆ ---           │
# │ str        ┆ str        ┆ str             ┆ str                  ┆ datetime[μs, UTC]       ┆ f64   ┆ str           │
# ╞════════════╪════════════╪═════════════════╪══════════════════════╪═════════════════════════╪═══════╪═══════════════╡
# │ 05779      ┆ daily      ┆ climate_summary ┆ precipitation_amount ┆ 2002-08-11 00:00:00 UTC ┆ 67.9  ┆ 10            │
# │ 05779      ┆ daily      ┆ climate_summary ┆ precipitation_amount ┆ 2002-08-12 00:00:00 UTC ┆ 312.0 ┆ 10            │
# │ 05779      ┆ daily      ┆ climate_summary ┆ precipitation_amount ┆ 2002-08-13 00:00:00 UTC ┆ 26.3  ┆ 10            │
# └────────────┴────────────┴─────────────────┴──────────────────────┴─────────────────────────┴───────┴───────────────┘

values.to_pandas()  # the frame is polars, pandas if you prefer
csv = result.to_csv()  # also to_dict(), to_json() and to_ogc_feature_collection()
# result.to_target("duckdb:///dwd.duckdb?table=weather")  # or SQLite, PostgreSQL, ... (extras)
```

### Command line

The same request with every option of `values` written out at its default (without `--start` and
`--end` you get the whole record, without `--target` the answer goes to stdout):

```bash
wetterdienst values \
  --provider=dwd --network=observation \
  --parameters=daily/climate_summary/precipitation_amount \
  --stations=05779 --start=2002-08-11 --end=2002-08-13 \
  --shape=long --humanize=true --convert-units=true --drop-nulls=true \
  --skip-empty=false --skip-threshold=0.95 --skip-criteria=min \
  --format=json --pretty=false --with-metadata=false --with-stations=false
```

With options you change: a second parameter, wide, the temperature in Fahrenheit, as a CSV file.

```bash
wetterdienst values --provider=dwd --network=observation \
  --parameters=daily/climate_summary/precipitation_amount,daily/climate_summary/temperature_air_mean_2m \
  --stations=05779 --start=2002-08-11 --end=2002-08-13 \
  --shape=wide --unit-targets='{"temperature":"degree_fahrenheit"}' \
  --format=csv --target=file://zinnwald.csv
```

`wetterdienst stations` takes the same selections (`--stations`, `--name`, `--latitude` and `--longitude`
with `--rank` or `--distance`, `--left` `--bottom` `--right` `--top`, `--sql`) and `--format`. The
settings are `WD_*` variables here, the options `WD_TS_*` ones as in Python. `wetterdienst values --help`
lists every option with its default.

### REST API

Start the server (the `restapi` extra, or the Docker image: `docker run --publish=7890:7890
ghcr.io/earthobservations/wetterdienst`). The limits it holds you to are settings, here at their
defaults, where 0 switches one off:

```bash
WD_RESTAPI_MAX_STATIONS=100 WD_RESTAPI_MAX_ROWS=500000 WD_RESTAPI_MAX_STREAM_ROWS=10000000 \
WD_RESTAPI_TIMEOUT=60 WD_RESTAPI_MAX_CONCURRENT=32 WD_RESTAPI_SQL=false \
wetterdienst restapi --listen 127.0.0.1:7890
```

Then ask it for the same request:

```bash
curl -G "http://localhost:7890/api/v1/values" \
  -d provider=dwd -d network=observation \
  -d parameters=daily/climate_summary/precipitation_amount \
  -d stations=05779 -d timestamp=2002-08-11/2002-08-13 \
  -d shape=long -d humanize=true -d convert_units=true -d drop_nulls=true \
  -d skip_empty=false -d skip_threshold=0.95 -d skip_criteria=min \
  -d format=json -d pretty=false -d with_metadata=false -d with_stations=false
```

The query takes the names of the command line with underscores, and `timestamp` for a window (a day, a
month, a year or `2002-08-11/2002-08-13`). The answer carries a `metadata` block with the provider's
licence and credit line. The interactive reference is at `http://localhost:7890/docs`, and a hosted
instance is at [wetterdienst.eobs.org](https://wetterdienst.eobs.org/).

### MCP

The same data as tools for an assistant: `stations`, `values`, `coverage`, `providers` and more. Add the
hosted endpoint, no account needed, or serve your own next to the REST API (the `mcp` extra) at
`http://localhost:7890/mcp/v1`:

```bash
claude mcp add --transport http wetterdienst https://wetterdienst.eobs.org/mcp/v1
```

Then ask in words: "How much did it rain at Zinnwald-Georgenfeld on 12 August 2002?" Other clients take
the URL as a streamable-HTTP server, see the
[MCP server](https://wetterdienst.readthedocs.io/en/latest/usage/mcp.html) chapter.

### Between stations

`interpolate` estimates a point between stations and `summarize` takes the nearest station with a value
at each timestamp, here for a point a few kilometres from Zinnwald. `interpolate` needs the
`interpolation` extra. The options that steer the search are written out at their defaults:

```python
from wetterdienst import Options
from wetterdienst.provider.dwd.observation import DwdObservationRequest

options = Options(
    geo_station_distance_homogeneous=40.0,  # default: km a station may be away, for a slowly varying quantity
    geo_station_distance_heterogeneous=20.0,  # default: the same for precipitation and the like
    geo_station_distance={},  # default: no override per parameter, e.g. {"precipitation_amount": 25.0}
    geo_station_distance_resolution_factors={},  # default: no change to how the radius scales with the resolution
    geo_use_nearby_station_distance=1.0,  # default: a station within this many km is used as it is
    geo_min_gain_of_value_pairs=0.10,  # default: stop adding stations below this gain
    geo_num_additional_stations=3,  # default: and add at least this many regardless
)
request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "precipitation_amount")],
    start="2002-08-11",
    end="2002-08-13",
    options=options,
)
interpolated = request.interpolate(latlon=(50.79, 13.79), elevation=700)  # elevation is optional
summarized = request.summarize(latlon=(50.79, 13.79), elevation=700)
```

On the command line these are `wetterdienst interpolate` and `wetterdienst summarize`, with `--latitude`
and `--longitude` (or `--station`), `--elevation`, and the options above as flags, such as
`--interpolation-station-distance-homogeneous`, `--min-gain-of-value-pairs` and
`--num-additional-stations`.

More in [examples](https://github.com/earthobservations/wetterdienst/tree/main/examples) and in the
[quickstart](https://wetterdienst.readthedocs.io/en/latest/usage/quickstart.html).

## What we support

| Provider                                                                                       | Country       | What you get                                                          |
|------------------------------------------------------------------------------------------------|---------------|-----------------------------------------------------------------------|
| [DWD](https://www.dwd.de/)                                                                     | 🇩🇪 Germany     | observations, MOSMIX/DMO forecasts, radar, warnings, road weather, derived indices |
| [AEMET](https://www.aemet.es/)                                                                 | 🇪🇸 Spain       | observations (API key)                                                |
| [CHMI](https://www.chmi.cz/)                                                                   | 🇨🇿 Czechia     | observations                                                          |
| [DMI](https://www.dmi.dk/)                                                                     | 🇩🇰 Denmark     | observations, incl. Greenland and the Faroe Islands                   |
| [EA](https://environment.data.gov.uk/)                                                         | 🇬🇧 England     | hydrology                                                             |
| [Eaufrance](https://hubeau.eaufrance.fr/)                                                      | 🇫🇷 France      | hydrology                                                             |
| [ECCC](https://climate.weather.gc.ca/)                                                         | 🇨🇦 Canada      | observations                                                          |
| [FMI](https://en.ilmatieteenlaitos.fi/)                                                        | 🇫🇮 Finland     | observations                                                          |
| [GeoSphere](https://www.geosphere.at/)                                                         | 🇦🇹 Austria     | observations                                                          |
| [IMGW](https://www.imgw.pl/)                                                                   | 🇵🇱 Poland      | meteorology, hydrology                                                |
| [IPMA](https://www.ipma.pt/)                                                                   | 🇵🇹 Portugal    | observations                                                          |
| [KNMI](https://www.knmi.nl/)                                                                   | 🇳🇱 Netherlands | observations (API key)                                                |
| [LHMT](https://www.meteo.lt/)                                                                  | 🇱🇹 Lithuania   | observations                                                          |
| [Met Office](https://www.metoffice.gov.uk/)                                                    | 🇬🇧 UK          | MIDAS Open observations (CEDA account)                                |
| [Météo-France](https://meteofrance.com/)                                                       | 🇫🇷 France      | observations, SYNOP                                                   |
| [MeteoSwiss](https://www.meteoswiss.admin.ch/)                                                 | 🇨🇭 Switzerland | observations                                                          |
| [met.no](https://www.met.no/)                                                                  | 🇳🇴 Norway      | Frost observations (API key)                                          |
| [NOAA](https://www.ncei.noaa.gov/)                                                             | 🌍 worldwide   | GHCN daily and hourly, stations across the globe                      |
| [NWS](https://www.weather.gov/)                                                                | 🇺🇸 USA         | observations                                                          |
| [RMI](https://www.meteo.be/)                                                                   | 🇧🇪 Belgium     | observations                                                          |
| [SMHI](https://www.smhi.se/)                                                                   | 🇸🇪 Sweden      | observations                                                          |
| [WSV](https://pegelonline.wsv.de/)                                                             | 🇩🇪 Germany     | hydrology (Pegelonline)                                               |

Across those: **over 600 canonical parameters**, resolutions from **1 minute to annual**, and archives
reaching back centuries where the service keeps them. Every provider is reached the same way, and a
parameter means the same thing whichever service reports it: `temperature_air_mean_2m` is the mean
air temperature at 2 m, converted to the same unit, everywhere.

Licenses and usage requirements differ per provider, so check the
[data](https://wetterdienst.readthedocs.io/en/latest/data/index.html) chapter before you publish
anything built on them. It also lists every dataset and parameter per provider.


## Where to start

Documentation: [wetterdienst.readthedocs.io](https://wetterdienst.readthedocs.io/en/latest/)

- **Install and make a first call** (Python, command line, REST API, assistant, app):
  [Quickstart](https://wetterdienst.readthedocs.io/en/latest/usage/quickstart.html), and
  [Concepts](https://wetterdienst.readthedocs.io/en/latest/usage/concepts.html) for the words.
- **Python**: [Python API](https://wetterdienst.readthedocs.io/en/latest/usage/python-api.html),
  [examples](https://github.com/earthobservations/wetterdienst/tree/main/examples) and
  [benchmarks](https://github.com/earthobservations/wetterdienst/tree/main/benchmarks).
- **Command line**: [command line interface](https://wetterdienst.readthedocs.io/en/latest/usage/cli.html).
- **REST API and MCP**: [REST API](https://wetterdienst.readthedocs.io/en/latest/usage/restapi.html),
  [MCP server](https://wetterdienst.readthedocs.io/en/latest/usage/mcp.html).
- **App**: [wetterdienst.eobs.org](https://wetterdienst.eobs.org/), and
  [how to run your own](https://wetterdienst.readthedocs.io/en/latest/usage/app.html).
- **The data**: [providers, parameters and licences](https://wetterdienst.readthedocs.io/en/latest/data/index.html),
  [DWD weather alerts](https://wetterdienst.readthedocs.io/en/latest/data/provider/dwd/alerts/index.html).
- **Upgrade**: [compatibility](https://wetterdienst.readthedocs.io/en/latest/usage/compatibility.html), what
  is stable and how a break is announced, and the
  [migration note from 0.139.0](https://wetterdienst.readthedocs.io/en/latest/usage/migrating.html).
- **Something fails**: [troubleshooting](https://wetterdienst.readthedocs.io/en/latest/usage/troubleshooting.html)
  and [known issues](https://wetterdienst.readthedocs.io/en/latest/known_issues.html).
- **Contribute**: [contribution guide](https://wetterdienst.readthedocs.io/en/latest/contribution/),
  [changelog](https://wetterdienst.readthedocs.io/en/latest/changelog.html).

## What we stand for

- 🏳️‍🌈🏳️‍⚧️ We stand with the LGBTQI+ community.
- ✊ No place for Nazis. FCKNZS.
- 🌡️ Global warming is not an opinion.
- 🔓 Weather data belongs to everyone.

## Acknowledgements

We want to acknowledge all environmental agencies which provide their data open and free of charge
first and foremost for the sake of endless research possibilities.

We want to acknowledge all contributors for being part of the improvements to this library that make
it better and better every day.

## Supported by

<p>
  <!-- same height, each at its own aspect ratio: the JetBrains file is a 298x64 wordmark and the
       Anthropic one a 24x24 glyph, so equal width and height would squash the first. -->
  <a href="https://jb.gg/OpenSourceSupport"><img src="https://resources.jetbrains.com/storage/products/company/brand/logos/jetbrains.svg" alt="JetBrains logo" width="224" height="48"/></a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://www.anthropic.com/"><img src="https://cdn.simpleicons.org/anthropic/181818/ffffff" alt="Anthropic logo" width="48" height="48"/></a>
</p>

Special thanks to the kind people at [JetBrains] s.r.o. for a PyCharm licence through their
open-source support programme, and to [Anthropic] for a Claude Max subscription for open-source
maintainers.

[JetBrains]: https://www.jetbrains.com/
[Anthropic]: https://www.anthropic.com/
