# REST API

Wetterdienst has an integrated REST API which can be started by invoking:

```bash
wetterdienst restapi
```

There's also a hosted version at [wetterdienst.eobs.org](https://www.wetterdienst.eobs.org).

## Web Frontend

The REST API is complemented by a modern web frontend built with Nuxt.js, providing an interactive interface for exploring weather data.

### Features

- **Interactive Explorer**: Browse and query weather data with an intuitive UI
  - Map-based station selection with search and filtering
  - Parameter selection across multiple providers and networks
  - Real-time data visualization with tables and charts
  - Date range selection for historical data
- **Comprehensive Settings**: Full access to all backend API parameters
  - General: Humanize parameters, unit conversion, custom unit targets
  - Values mode: Data shape (long/wide), skip empty stations, drop nulls
  - Interpolation mode: Station distances, nearby station distance, gain thresholds
- **Climate Stripes**: Visual representation of temperature trends
- **Customization**: Primary color themes and dark mode support
- **Export**: Download data in CSV, JSON, or GeoJSON formats

### Access

Visit [wetterdienst.eobs.org](https://www.wetterdienst.eobs.org) to use the web interface.

The following examples use [httpie](https://github.com/httpie/cli) to demonstrate the usage of the REST API.

## Examples

### Coverage

```bash
http localhost:7890/api/coverage
```

### Stations

```bash
# Acquire list of DWD OBS stations.
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent all==true

# Query list of stations with SQL.
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent sql=="lower(name) LIKE lower('%dresden%');"

# Acquire list of DWD DMO stations.
http localhost:7890/api/stations provider==dwd network==dmo parameters==hourly/icon/temperature_air_mean_2m periods==recent all==true
```

### Values

```bash
# Acquire observations.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent station==1048,4411

# Observations for specific date.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent station==1048,4411 date==2020-08-01

# Observations for date range.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent station==1048,4411 date==2020-08-01/2020-08-05

# Observations with SQL.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent station==1048,4411 shape=="wide" sql=="temperature_air_max_2m < 2.0;"

# Acquire ICON data.
http localhost:7890/api/values provider==dwd network==dmo parameters==hourly/icon/temperature_air_mean_2m station==01001 date==2024-05-27
```
