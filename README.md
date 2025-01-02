# Wetterdienst - Open weather data for humans

<p>
  <img src="https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/assets/german_weather_stations.png" alt="German weather stations managed by Deutscher Wetterdienst" width="32%"/>
  <img src="https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/assets/temperature_ts.png" alt="temperature timeseries of Hohenpeissenberg/Germany" width="32%"/>
  <img src="https://raw.githubusercontent.com/earthobservations/wetterdienst/main/docs/assets/hohenpeissenberg_warming_stripes.png" alt="warming stripes of Hohenpeissenberg/Germany" width="32%"/>
</p>


> "What do we want? Climate Justice! When do we want it? Now!" - FFF

> [!WARNING]
> This library is a work in progress!
> Breaking changes should be expected until a 1.0 release, so version pinning is recommended.

### Badges

#### CI

[![CI status](https://github.com/earthobservations/wetterdienst/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/earthobservations/wetterdienst/actions?workflow=Tests)
[![Documentation status](https://readthedocs.org/projects/wetterdienst/badge/?version=latest)](https://wetterdienst.readthedocs.io/en/latest/?badge=latest)
[![Code coverage](https://codecov.io/gh/earthobservations/wetterdienst/branch/main/graph/badge.svg)](https://codecov.io/gh/earthobservations/wetterdienst)

#### Meta

[![PyPI version](https://img.shields.io/pypi/v/wetterdienst.svg)](https://pypi.org/project/wetterdienst/)
[![Conda version](https://img.shields.io/conda/vn/conda-forge/wetterdienst.svg)](https://anaconda.org/conda-forge/wetterdienst)
[![Project license](https://img.shields.io/github/license/earthobservations/wetterdienst)](https://github.com/earthobservations/wetterdienst/blob/main/LICENSE)
[![Project status (alpha, beta, stable)](https://img.shields.io/pypi/status/wetterdienst.svg)](https://pypi.python.org/pypi/wetterdienst/)
[![Python version compatibility](https://img.shields.io/pypi/pyversions/wetterdienst.svg)](https://pypi.python.org/pypi/wetterdienst/)

#### Downloads

[![PyPI downloads](https://static.pepy.tech/personalized-badge/wetterdienst?period=month&units=international_system&left_color=grey&right_color=blue&left_text=PyPI%20downloads/month)](https://pepy.tech/project/wetterdienst)
[![Conda downloads](https://img.shields.io/conda/dn/conda-forge/wetterdienst.svg?label=Conda%20downloads)](https://anaconda.org/conda-forge/wetterdienst)

#### Citation

[![Citation reference](https://zenodo.org/badge/160953150.svg)](https://zenodo.org/badge/latestdoi/160953150)

## Overview

Welcome to Wetterdienst, your friendly weather service library for Python.

We are a group of like-minded people trying to make access to weather data in Python feel like a warm summer breeze,
similar to other projects like [rdwd](https://github.com/brry/rdwd) for the R language, which originally drew our
interest in this project. Our long-term goal is to provide access to multiple weather services as well as other related
agencies such as river measurements. With ``wetterdienst`` we try to use modern Python technologies all over the place.
The library is based on [polars](https://www.pola.rs/) (we <3 [pandas](https://pandas.pydata.org/), it is still part of
some IO processes) across the board, uses [uv](https://github.com/astral-sh/uv) for package administration and GitHub
Actions for all things CI. Our users are an important part of the development as we are not currently using the data we
are providing and only implement what we think would be the best. Therefore, contributions and feedback whether it be
data related or library related are very welcome! Just hand in a PR or Issue if you think we should include a new
feature or data source.

## Data

For an overview of the data we have currently made available and under which license it is published take a look at the
[data](https://wetterdienst.readthedocs.io/en/latest/data/index.html) section. Detailed information on datasets and
parameters is given at the [coverage](https://wetterdienst.readthedocs.io/en/improve-documentation/data/coverage.html)
subsection. Licenses and usage requirements may differ for each provider so check this out before including the data in
your project to be sure that you fulfill copyright requirements!

For a closer look on the DWD data, you can use the [interactive map](https://bookdown.org/brry/rdwd/interactive-map.html)
or the [table](https://bookdown.org/brry/rdwd/available-datasets.html) provided by the `rdwd` package.

## Features

- APIs for stations and values
- Get stations nearby a selected location
- Define your request by arguments such as `parameters`, `periods`, `start date`, `end date`
- Define general settings in Settings context
- Command line interfaced
- Web-API via FastAPI, hosted on [wetterdienst.eobs.org](https://wetterdienst.eobs.org/)
- Rich UI features like [explorer](https://wetterdienst.streamlit.app/), [stripes](https://stripes.streamlit.app/)
- Run SQL queries on the results
- Export results to databases and other data sinks
- Public Docker image
- Interpolation and Summary of station values

## Setup

### Native

Via PyPi (standard):

```bash
pip install wetterdienst
```

Via Github (most recent):

```bash
pip install git+https://github.com/earthobservations/wetterdienst
```

There are some extras available for ``wetterdienst``. Use them like:

```bash
pip install wetterdienst[sql]
```

- docs: Install the Sphinx documentation generator.
- ipython: Install iPython stack.
- export: Install openpyxl for Excel export and pyarrow for writing files in Feather- and Parquet-format.
- sql: Install DuckDB for querying data using SQL.
- duckdb: Install support for DuckDB.
- influxdb: Install support for InfluxDB.
- cratedb: Install support for CrateDB.
- mysql: Install support for MySQL.
- postgresql: Install support for PostgreSQL.
- interpolation: Install support for station interpolation.

In order to check the installation, invoke:

```bash
wetterdienst --help
```

### Docker

Docker images for each stable release will get pushed to GitHub Container Registry.

``wetterdienst`` serves a full environment, including *all* the optional dependencies of Wetterdienst.

Pull the Docker image:

```bash
docker pull ghcr.io/earthobservations/wetterdienst
```

#### Library

Use the latest stable version of ``wetterdienst``:

```bash
$ docker run -ti ghcr.io/earthobservations/wetterdienst
Python 3.8.5 (default, Sep 10 2020, 16:58:22)
[GCC 8.3.0] on linux
```

```python
import wetterdienst
wetterdienst.__version__
```

#### Command line script

The ``wetterdienst`` command is also available:

```bash
# Make an alias to use it conveniently from your shell.
alias wetterdienst='docker run -ti ghcr.io/earthobservations/wetterdienst wetterdienst'

wetterdienst --help
wetterdienst --version
wetterdienst info
```

### Raspberry Pi / LINUX ARM

Running wetterdienst on Raspberry Pi, you need to install **numpy**
and **lxml** prior to installing wetterdienst by running the following
lines:

```bash
# not all installations may be required to get lxml running
sudo apt-get install gfortran
sudo apt-get install libopenblas-base
sudo apt-get install libopenblas-dev
sudo apt-get install libatlas-base-dev
sudo apt-get install python3-lxml
```

Additionally expanding the Swap to 2048 mb may be required and can be done via swap-file:

```bash
sudo nano /etc/dphys-swapfile
```

Thanks [chr-sto](https://github.com/chr-sto) for reporting back to us!

## Example

### Task

Get historical climate summary for two German stations between 1990 and 2020

### Library

```python
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

settings = Settings(  # default
  ts_shape="long",  # tidy data
  ts_humanize=True,  # humanized parameters
  ts_convert_units=True  # convert values to SI units
)

request = DwdObservationRequest(
  parameters=[
    ("daily", "climate_summary", "precipitation_height"),
  ],
  start_date="2002-08-11",  # if not given timezone defaulted to UTC
  end_date="2002-08-13",  # if not given timezone defaulted to UTC
  settings=settings
).filter_by_station_id(station_id=(5779,))

stations = request.df
stations.head()
# ┌────────────┬──────────────┬──────────────┬──────────┬───────────┬────────┬─────────────┬─────────┐
# │ station_id ┆ start_date   ┆ end_date     ┆ latitude ┆ longitude ┆ height ┆ name        ┆ state   │
# │ ---        ┆ ---          ┆ ---          ┆ ---      ┆ ---       ┆ ---    ┆ ---         ┆ ---     │
# │ str        ┆ datetime[μs, ┆ datetime[μs, ┆ f64      ┆ f64       ┆ f64    ┆ str         ┆ str     │
# │            ┆ UTC]         ┆ UTC]         ┆          ┆           ┆        ┆             ┆         │
# ╞════════════╪══════════════╪══════════════╪══════════╪═══════════╪════════╪═════════════╪═════════╡
# │ 05779      ┆ 1971-01-01   ┆ ...          ┆ 50.7313  ┆ 13.7516   ┆ 877.0  ┆ Zinnwald-Ge ┆ Sachsen │
# │            ┆ 00:00:00 UTC ┆ 00:00:00 UTC ┆          ┆           ┆        ┆ orgenfeld   ┆         │
# └────────────┴──────────────┴──────────────┴──────────┴───────────┴────────┴─────────────┴─────────┘

values = request.values.all().df
values.head()
# ┌────────────┬─────────────────┬──────────────────────┬─────────────────────────┬───────┬─────────┐
# │ station_id ┆ dataset         ┆ parameter            ┆ date                    ┆ value ┆ quality │
# │ ---        ┆ ---             ┆ ---                  ┆ ---                     ┆ ---   ┆ ---     │
# │ str        ┆ str             ┆ str                  ┆ datetime[μs, UTC]       ┆ f64   ┆ f64     │
# ╞════════════╪═════════════════╪══════════════════════╪═════════════════════════╪═══════╪═════════╡
# │ 05779      ┆ climate_summary ┆ precipitation_height ┆ 2002-08-11 00:00:00 UTC ┆ 67.9  ┆ 10.0    │
# │ 05779      ┆ climate_summary ┆ precipitation_height ┆ 2002-08-12 00:00:00 UTC ┆ 312.0 ┆ 10.0    │
# │ 05779      ┆ climate_summary ┆ precipitation_height ┆ 2002-08-13 00:00:00 UTC ┆ 26.3  ┆ 10.0    │
# └────────────┴─────────────────┴──────────────────────┴─────────────────────────┴───────┴─────────┘

# to get a pandas DataFrame and e.g. create some matplotlib plots    
values.to_pandas()
```

### Client

```bash
# Get list of all stations for daily climate summary data in JSON format
wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all

# Get daily climate summary data for specific stations
wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --station=1048,4411
```

### Other

Checkout [examples](https://github.com/earthobservations/wetterdienst/tree/main/examples) for more examples.

## Acknowledgements

We want to acknowledge all environmental agencies which provide their data open and free of charge first and foremost
for the sake of endless research possibilities.

We want to acknowledge [Jetbrains](https://www.jetbrains.com/) and the
[Jetbrains OSS Team](https://github.com/JetBrains) for providing us with licenses for Pycharm Pro, which we are using
for the development.

We want to acknowledge all contributors for being part of the improvements to this library that make it better and
better every day.

## Important Links

- Restapi: https://wetterdienst.eobs.org/
- Explorer: https://wetterdienst.streamlit.app/
- Stripes: https://stripes.streamlit.app/
- Documentation: https://wetterdienst.readthedocs.io/

    - Usage: https://wetterdienst.readthedocs.io/en/latest/usage/
    - Contribution: https://wetterdienst.readthedocs.io/en/latest/contribution/
    - Changelog: https://wetterdienst.readthedocs.io/en/latest/changelog.html

- Examples (runnable scripts): https://github.com/earthobservations/wetterdienst/tree/main/examples
- Benchmarks: https://github.com/earthobservations/wetterdienst/tree/main/benchmarks
