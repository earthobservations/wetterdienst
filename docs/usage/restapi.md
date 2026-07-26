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

By default the `stations`, `values`, `interpolate`, `summarize` and `history` endpoints return only
the requested data. Add `with_metadata=true` to include the provider-metadata block, and (for the
value endpoints) `with_stations=true` to include the queried stations' metadata.

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

# Filter stations by name (fuzzy, case-insensitive).
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent name==Darmstadt

# Filter by name with custom threshold (0–1, default 0.8).
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent name==Darmstatt name_threshold==0.85

# Query list of stations with SQL.
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent sql=="lower(name) LIKE lower('%dresden%');"

# Acquire list of DWD DMO stations.
http localhost:7890/api/stations provider==dwd network==dmo parameters==hourly/icon/temperature_air_mean_2m periods==recent all==true
```

### Issues (available model-run datetimes)

```bash
# List available MOSMIX-L run datetimes for a station.
http localhost:7890/api/issues provider==dwd network==mosmix station==10147

# List available DMO ICON run datetimes for a station.
http localhost:7890/api/issues provider==dwd network==dmo station==10147
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

## MCP endpoint

The REST API can optionally expose a [Model Context Protocol](https://modelcontextprotocol.io/)
(MCP) endpoint at `/mcp`, so LLM agents can call the data endpoints (coverage, stations, values,
interpolate, summarize, stripes, alerts, ...) as MCP tools. It is served over the streamable-HTTP
transport by [FastMCP](https://gofastmcp.com/), generated from the REST API's own routes and running
in the same process.

The generated tools are made agent-friendly so even small models use them correctly: a workflow
`instructions` block (find a station, then query its values) is attached to the server, the tools
get clean names (`values` rather than `values_api_values_get`), and the non-data endpoints
(index, health, ...) are hidden.

Install the optional extra to enable it (it is already included in the Docker image, so the hosted
[wetterdienst.eobs.org](https://www.wetterdienst.eobs.org) instance serves `/mcp` as well):

```bash
pip install wetterdienst[mcp]
wetterdienst restapi
```

The endpoint then lives next to the HTTP API:

```
http://localhost:7890/mcp
```

Point any MCP client (streamable HTTP) at that URL — for example:

```json
{
  "mcpServers": {
    "wetterdienst": {
      "url": "https://wetterdienst.eobs.org/mcp"
    }
  }
}
```

Without the `[mcp]` extra installed, the REST API behaves exactly as before and the `/mcp` route is
simply absent.
