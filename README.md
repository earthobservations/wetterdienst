# Wetterdienst - Open weather data for humans

<p align="center">
  <img src="https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/assets/hohenpeissenberg_warming_stripes.png" alt="Warming stripes of Hohenpeissenberg, Germany, drawn from data fetched with wetterdienst" width="100%"/>
</p>

> **Global warming is not an opinion.** — Erderwärmung ist keine Meinung.

[![CI status](https://github.com/earthobservations/wetterdienst/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/earthobservations/wetterdienst/actions?workflow=Tests)
[![Documentation status](https://readthedocs.org/projects/wetterdienst/badge/?version=latest)](https://wetterdienst.readthedocs.io/en/latest/?badge=latest)
[![Code coverage](https://codecov.io/gh/earthobservations/wetterdienst/branch/main/graph/badge.svg)](https://codecov.io/gh/earthobservations/wetterdienst)
[![PyPI version](https://img.shields.io/pypi/v/wetterdienst.svg)](https://pypi.org/project/wetterdienst/)
[![Conda version](https://img.shields.io/conda/vn/conda-forge/wetterdienst.svg)](https://anaconda.org/conda-forge/wetterdienst)
[![Python version compatibility](https://img.shields.io/pypi/pyversions/wetterdienst.svg)](https://pypi.python.org/pypi/wetterdienst/)
[![Project license](https://img.shields.io/github/license/earthobservations/wetterdienst)](https://github.com/earthobservations/wetterdienst/blob/main/LICENSE)
[![PyPI downloads](https://static.pepy.tech/personalized-badge/wetterdienst?period=month&units=international_system&left_color=grey&right_color=blue&left_text=PyPI%20downloads/month)](https://pepy.tech/project/wetterdienst)
[![Citation reference](https://zenodo.org/badge/160953150.svg)](https://zenodo.org/badge/latestdoi/160953150)

> [!WARNING]
> This library is a work in progress!
> Breaking changes should be expected until a 1.0 release, so version pinning is recommended.

Wetterdienst gives you weather, climate and hydrology data from 22 national services through one
interface: one way to find a station, one way to ask for values, one shape of result. It is a
[polars](https://www.pola.rs/)-based Python library, a command line client, a REST API, an MCP
endpoint and a web app, all serving the same data.

Contributions and feedback are very welcome — we do not use most of this data ourselves, so what
you need is what tells us what to build next. Hand in an issue or a PR.

## What we support

| Provider                                                                                       | Country       | What you get                                                          |
|------------------------------------------------------------------------------------------------|---------------|-----------------------------------------------------------------------|
| [DWD](https://www.dwd.de/)                                                                     | 🇩🇪 Germany     | observations, MOSMIX/DMO forecasts, radar, warnings, road weather, derived indices |
| [AEMET](https://www.aemet.es/)                                                                 | 🇪🇸 Spain       | observations (API key)                                                |
| [CHMI](https://www.chmi.cz/)                                                                   | 🇨🇿 Czechia     | observations                                                          |
| [DMI](https://www.dmi.dk/)                                                                     | 🇩🇰 Denmark     | observations, incl. Greenland and the Faroe Islands (API key)         |
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
| [WSV](https://www.pegelonline.wsv.de/)                                                         | 🇩🇪 Germany     | hydrology (Pegelonline)                                               |

Across those: **514 canonical parameters**, resolutions from **1 minute to annual**, and archives
reaching back centuries where the service keeps them. Every provider is reached the same way, and a
parameter means the same thing whichever service reports it — `temperature_air_mean_2m` is the mean
air temperature at 2 m, converted to the same unit, everywhere.

Licenses and usage requirements differ per provider, so check the
[data](https://wetterdienst.readthedocs.io/en/latest/data/index.html) chapter before you publish
anything built on them. It also lists every dataset and parameter per provider.

## Features

- Stations, values and station history (metadata changes) through one request model
- Find stations by name, id, distance from a point, bounding box or rank
- Request by `parameters`, `periods`, `start_date`, `end_date`; tune the rest through `Settings`
- Unit conversion, interpolation and summarization for a point between stations
- DWD weather alerts (CAP warnings) with GeoJSON geometry, by community or district
- SQL queries over results, export to CSV/JSON/Excel/Parquet/Zarr and to SQLite, PostgreSQL,
  CrateDB, InfluxDB and DuckDB
- Command line client, REST API and a public Docker image
- MCP (Model Context Protocol) endpoint, so LLM agents can query the data as tools
- Web app with map-based explorer, forecasts, climate stripes and a glossary, at
  [wetterdienst.eobs.org](https://wetterdienst.eobs.org/)

## Setup

```bash
pip install wetterdienst           # from PyPI
pip install wetterdienst[export]   # with an extra
pip install git+https://github.com/earthobservations/wetterdienst  # most recent
```

Extras: `bufr`, `cratedb`, `duckdb`, `eccodes`, `excel`, `export`, `influxdb`, `interpolation`,
`knmi`, `mcp`, `mysql`, `pdf`, `plotting`, `postgresql`, `radar`, `radarplus`, `restapi`, `sql`.
Check the installation with `wetterdienst --help`.

Prefer Docker? The image ships with the optional dependencies included:

```bash
docker pull ghcr.io/earthobservations/wetterdienst
docker run -ti ghcr.io/earthobservations/wetterdienst wetterdienst --version
```

See the [Docker](https://wetterdienst.readthedocs.io/en/latest/usage/docker.html) chapter for
running the REST API and the app from the image.

## Example

Daily precipitation for Zinnwald-Georgenfeld, August 2002 — the flood:

```python
from wetterdienst.provider.dwd.observation import DwdObservationRequest

request = DwdObservationRequest(
    parameters=[("daily", "climate_summary", "precipitation_height")],
    start_date="2002-08-11",
    end_date="2002-08-13",
).filter_by_station_id(station_id=(5779,))

stations = request.df
stations.head()
# ┌────────────┬─────────────────┬────────────┬─────────────────────────┬───┬───────────┬────────┬──────────────────────┬─────────┐
# │ resolution ┆ dataset         ┆ station_id ┆ start_date              ┆ … ┆ longitude ┆ height ┆ name                 ┆ state   │
# │ ---        ┆ ---             ┆ ---        ┆ ---                     ┆   ┆ ---       ┆ ---    ┆ ---                  ┆ ---     │
# │ str        ┆ str             ┆ str        ┆ datetime[μs, UTC]       ┆   ┆ f64       ┆ f64    ┆ str                  ┆ str     │
# ╞════════════╪═════════════════╪════════════╪═════════════════════════╪═══╪═══════════╪════════╪══════════════════════╪═════════╡
# │ daily      ┆ climate_summary ┆ 05779      ┆ 1971-01-01 00:00:00 UTC ┆ … ┆ 13.7516   ┆ 877.0  ┆ Zinnwald-Georgenfeld ┆ Sachsen │
# └────────────┴─────────────────┴────────────┴─────────────────────────┴───┴───────────┴────────┴──────────────────────┴─────────┘

values = request.values.all().df
values.head()
# ┌────────────┬────────────┬─────────────────┬──────────────────────┬─────────────────────────┬───────┬─────────┐
# │ station_id ┆ resolution ┆ dataset         ┆ parameter            ┆ date                    ┆ value ┆ quality │
# ╞════════════╪════════════╪═════════════════╪══════════════════════╪═════════════════════════╪═══════╪═════════╡
# │ 05779      ┆ daily      ┆ climate_summary ┆ precipitation_height ┆ 2002-08-11 00:00:00 UTC ┆ 67.9  ┆ 10.0    │
# │ 05779      ┆ daily      ┆ climate_summary ┆ precipitation_height ┆ 2002-08-12 00:00:00 UTC ┆ 312.0 ┆ 10.0    │
# │ 05779      ┆ daily      ┆ climate_summary ┆ precipitation_height ┆ 2002-08-13 00:00:00 UTC ┆ 26.3  ┆ 10.0    │
# └────────────┴────────────┴─────────────────┴──────────────────────┴─────────────────────────┴───────┴─────────┘

values.to_pandas()  # if you would rather have pandas
```

The same thing from the command line:

```bash
wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all
wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --station=1048,4411
```

More in [examples](https://github.com/earthobservations/wetterdienst/tree/main/examples) and in the
[usage](https://wetterdienst.readthedocs.io/en/latest/usage/) chapter.

## Links

- App: [wetterdienst.eobs.org](https://wetterdienst.eobs.org/)
- Documentation: [wetterdienst.readthedocs.io](https://wetterdienst.readthedocs.io/)
  ([usage](https://wetterdienst.readthedocs.io/en/latest/usage/),
  [contribution](https://wetterdienst.readthedocs.io/en/latest/contribution/),
  [changelog](https://wetterdienst.readthedocs.io/en/latest/changelog.html))
- [Examples](https://github.com/earthobservations/wetterdienst/tree/main/examples) and
  [benchmarks](https://github.com/earthobservations/wetterdienst/tree/main/benchmarks)

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

[![JetBrains logo.](https://resources.jetbrains.com/storage/products/company/brand/logos/jetbrains.svg)](https://jb.gg/OpenSourceSupport)
&nbsp;&nbsp;
[![Anthropic logo.](https://cdn.simpleicons.org/anthropic/181818/ffffff)](https://www.anthropic.com/)

Special thanks to the kind people at [JetBrains] s.r.o. for a PyCharm licence through their
open-source support programme, and to [Anthropic] for a Claude Max subscription for open-source
maintainers.

[JetBrains]: https://www.jetbrains.com/
[Anthropic]: https://www.anthropic.com/
