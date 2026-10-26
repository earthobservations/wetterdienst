# Usage

Wetterdienst is one library, one command line, one REST API, one MCP server and one app over the same data.
Start with the [Quickstart](quickstart.md) and [Concepts](concepts.md); this page says where to go by what you want
to do.

## From Python

| Page | What it is for |
| --- | --- |
| [Python API](python-api.md) | requests, stations, values, formats, errors: the reference of the library |
| [Python Examples](python-examples.md) | ready-to-run snippets per provider and network |
| [Interpolation & Summary](interpolation.md) | a series for a point between stations |
| [Station history](station_history.md) | the changes of a station: names, instruments, position |
| [Climate Stripes](stripes.md) | warming stripes of a DWD station, from the command line and the REST API |
| [Units](units.md) | the unit every quantity comes back in, and how to change it |
| [Export](export.md) | writing a result to a file or a database |
| [Settings and options](settings.md) | the host's settings and a request's options |

## From the command line, the REST API, an assistant or the app

| Page | What it is for |
| --- | --- |
| [Command line interface](cli.md) | every command and its options, as the help prints them |
| [REST API](restapi.md) | the endpoints, the response metadata, limits, streaming and errors |
| [Getting more than the limit](large-requests.md) | what to do about a request refused for its size: narrow it, stream it, ask in slices, leave the server |
| [MCP server](mcp.md) | the same data as tools for an assistant |
| [Web app](app.md) | the explorer, forecasts, stripes, providers and glossary, and how to run your own |

## Upgrading and compatibility

| Page | What it is for |
| --- | --- |
| [Compatibility](compatibility.md) | what is stable on every surface, what counts as breaking, how a deprecation and a break are announced |
| [Migrating from 0.139.0](migrating.md) | what to change in your code, scripts and deployment to move to the current release |

## Running it

| Page | What it is for |
| --- | --- |
| [Docker](docker.md) | the image, the REST API in a container, the cache volume |
| [Scheduling](scheduling.md) | a recurring acquisition with systemd, launchd or cron |
| [Troubleshooting](troubleshooting.md) | what a failure means and what to do |
| [Known issues](../known_issues.md) | problems of one machine: a proxy, a certificate, ecCodes on Linux, a Raspberry Pi |

The data itself, every provider and parameter, is under [Data](../data/index.md).

```{toctree}
:hidden:

python-api.md
python-examples.md
interpolation.md
station_history.md
stripes.md
units.md
export.md
settings.md
cli.md
restapi.md
large-requests.md
mcp.md
app.md
docker.md
scheduling.md
compatibility.md
migrating.md
```
