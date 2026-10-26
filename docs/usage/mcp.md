# MCP server

The [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) lets an assistant call wetterdienst as tools:
it finds a station, then reads its measurements, and answers from them instead of from memory. The endpoint is
part of the [REST API](restapi.md): the tools are generated from its routes and run in the same process, so what
the REST API answers (the [`metadata` block](restapi.md#response-metadata) with the licence and the credit line,
the [limits](restapi.md#limits), the [problems](restapi.md#errors)) is what a tool answers.

## Use the hosted endpoint

The hosted instance serves it on its own origin, with no account and no API key:

```text
https://wetterdienst.eobs.org/mcp/v1
```

Any client of the streamable-HTTP transport takes that URL. For an assistant that is configured with a JSON file:

```json
{
  "mcpServers": {
    "wetterdienst": {
      "url": "https://wetterdienst.eobs.org/mcp/v1"
    }
  }
}
```

For Claude Code, one command adds it:

```bash
claude mcp add --transport http wetterdienst https://wetterdienst.eobs.org/mcp/v1
```

Then ask in words: "How warm was it in Kiel on 26 December 2025?" The assistant calls `stations` with the name and
`values` with the station it got.

## Run your own

Install the extra and start the REST API; the endpoint is served next to it:

```bash
pip install "wetterdienst[mcp]"
wetterdienst restapi
```

```text
http://localhost:7890/mcp/v1
```

`GET /api/version` says whether an instance serves it (`mcp_enabled`) and where (`mcp_path`, `mcp_alias_path`; both
`null` without the extra). The [Docker image](docker.md) and the [app](app.md)'s `/mcp/v1` have it.

The server holds the provider credentials (`WD_AUTH__AEMET`, `WD_AUTH__KNMI`, `WD_AUTH__METNO_FROST`,
`WD_AUTH__CEDA`, see [Settings](settings.md)), not the client: a tool for a network that needs one answers a
[problem](troubleshooting.md#credentials) when the server has none, and the tool `auth` says whether the provider
accepts them. The `sql` and `sql_values` arguments are refused unless the server runs with `WD_RESTAPI_SQL=true`.

## The tools

A tool is a route of the REST API, with the same name for each argument (written with underscores, as the query
parameters are, see [one vocabulary](restapi.md#one-vocabulary)) and the same answer.

| Tool | REST route | What it is for |
| --- | --- | --- |
| `stations` | `/api/v1/stations` | find a station by name, id, point, bounding box or rank |
| `values` | `/api/v1/values` | the measurements or forecast of stations; the tool for "what was the weather" |
| `interpolate` | `/api/v1/interpolate` | an estimate for a point between stations; only when asked for |
| `summarize` | `/api/v1/summarize` | the nearest station with data at each timestamp, for a point; only when asked for |
| `history` | `/api/v1/history` | the changes of a station (name, position, instruments), not weather |
| `issues` | `/api/v1/issues` | the model runs of a forecast network |
| `coverage` | `/api/v1/coverage` | which providers, networks, resolutions, datasets and parameters there are |
| `providers` | `/api/v1/providers` | what a provider is: country, licence, credit line, networks |
| `glossary` | `/api/v1/glossary` | what a parameter means and the unit it comes back in |
| `auth` | `/api/v1/auth` | whether the credentials the server holds are accepted by one provider |
| `alerts` | `/api/v1/alerts` | the weather warnings of DWD |
| `stripes_stations`, `stripes_values`, `stripes_image` | `/api/v1/stripes/...` | climate stripes, see [Climate Stripes](stripes.md) |

The endpoints of the server itself (`/api/version`, `/api/settings`, the index and the health check) are not tools.
The server gives the assistant a block of `instructions`: the workflow (find the station, then read its values),
which tool not to reach for first (`interpolate` and `summarize` introduce an error and are for an explicit
request), how a parameter is written (`daily/climate_summary/temperature_air_mean_2m`) and how to read a result.
The instructions and the descriptions of the tools are written for agents and are improved without a new version.

The same two steps serve a network of any `kind` (`observation`, `forecast`, ...), for a place given by coordinates as
well as by name. The `country` of a provider is the country of the agency that runs it, not the extent of its data, and
the instructions tell the assistant not to conclude from it that a network cannot serve a place: it looks at the
network's `kind` and at what `stations` returns near the place.

An error comes back as the text of the REST problem, for instance
`HTTP error 422: Unprocessable Content - limit: Input should be greater than or equal to 1`, and an argument a tool
does not take is refused with the name of the one it takes (`station was renamed to stations`). No tool takes
`debug`: the log level of the server is its operator's, and a call that gives it is refused saying so.

## Text from the providers

A tool answers what the REST route answers, and some of that is text written by the provider: station names, the free
text of DWD warnings (`headline`, `description`, `instruction`), the remarks and instruments of a station's history. The
server does not filter or mark it. To the assistant that reads it, it is untrusted input, as a web page would be: an
assistant that is connected to this endpoint together with tools that act (send, write, run, fetch) should not follow an
instruction that such a field contains. The
[threat model](https://github.com/earthobservations/wetterdienst/blob/main/.github/SECURITY.md)
has the rest.

## Stateless

The endpoint keeps no session. The tools hold no state: each is a request to the REST API, so the server does not
create a session at `initialize`, sends no `mcp-session-id` header and has nothing to expire, and a request needs no
earlier one: `tools/list` and `tools/call` work without an `initialize`. A request that carries an `mcp-session-id`
is served as one without. The two requests that belong to a session are answered with a 405, as the specification
lets a server do: `DELETE` (ending a session; clients that send it on closing carry on) and `GET` (opening a stream
of messages from the server, of which a server of tools has none). A tool's answer is one body and is not streamed:
the long answers are the ones that `format=ndjson` and `csv` stream on the REST API. A tool makes its request to the
API in process, so it is held to the [limits](restapi.md#limits), the [timeout](restapi.md#timeout) and the
[concurrency](restapi.md#concurrency) of the server like any request. A request that a tool is refused for its size is
asked again for a window or fewer stations, or made from the library: see
[Getting more than the limit](large-requests.md#from-an-assistant).

## Versioning

`/mcp/v1` is the endpoint to configure, and it stays what it is: a breaking change of a tool (its name, an
argument, the answer) comes with `/mcp/v2`, and `/mcp/v1` keeps serving the tools as they were for at least two
minor releases, announced in the changelog. `/mcp` is an alias of the current version, the same endpoint with the
same tools, as `/api` is for `/api/v1`: it is not deprecated and it moves with the next version, so a
client that must not move with it is configured with `/mcp/v1`. Until `/mcp/v2` exists, it is a 404. A new tool, an optional argument and a new member of
an answer are not breaking and come to `/mcp/v1` as they come to the REST API. The
[Compatibility](compatibility.md) page has the rules of every surface in one place. The app reads `/api/version` before
offering an MCP client configuration, so an instance without the extra is never advertised as serving an endpoint
it does not.
