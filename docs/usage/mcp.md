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

The server holds the provider credentials (`WD_AUTH__AEMET`, `WD_AUTH__KNMI_EDR`, `WD_AUTH__METNO_FROST`,
`WD_AUTH__CEDA`, see [Settings](settings.md)), not the client: a tool for a network that needs one answers a
[problem](troubleshooting.md#credentials) when the server has none, and the tool `auth` says whether the provider
accepts them. The tools take no `sql` or `sql_values`: they were removed, and a call that gives one is told so, with what to do instead.

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
| `providers` | `/api/v1/providers` | which provider has which network, and what a provider is: country, licence, credit line to cite, the networks with their `kind`, `extent` and whether they are `configured` |
| `coverage` | `/api/v1/coverage` | the resolutions, datasets and parameters of one network (`provider` and `network` are required) |
| `glossary` | `/api/v1/glossary` | what a parameter means and the unit it comes back in |
| `auth` | `/api/v1/auth` | whether the credentials the server holds are accepted by one provider |
| `alerts` | `/api/v1/alerts` | the weather warnings of DWD: all of Germany unless given a place (`latitude` and `longitude`, or `name`), so pass it |
| `storm_cells` | `/api/v1/storm-cells` | the thunderstorm cells of DWD, now or within the last 48 hours: all of Germany unless given a point and `distance` (km) or a box (`left`, `bottom`, `right`, `top`), so pass one; `track=false` and `geometry=centroid` keep a long list short. The answer is not cut |
| `kostra` | `/api/v1/kostra` | the design rainfall of DWD (KOSTRA-DWD-2020: return periods of heavy rain) for a point in Germany: the depth, intensity and uncertainty of a rain by duration and return period. Pass a `duration` (minutes, one of 22) and a `return_period` (years) for the one value you need: without them it reads 22 files and answers 198 rows. A point outside Germany and its border is refused |
| `station_ids` | `/api/v1/station-ids` | one WMO number, WIGOS identifier or ICAO code at every provider that lists stations with it, as a list with the provider, network, `station_id` and which id matched, see [Find a station by id](station_ids.md). It asks the station list of every network that declares id columns at once: about 9 s the first time, longer on a slow day (the tool's description says so), then about a second. A network that cannot be read, or needs a key the server does not hold, is left out and named in a warning; the answer is cut to the budget like `stations`'s |
| `statistics` | `/api/v1/statistics` | how many, how much or the mean per year, month, day or hour (frost days a year, the coldest winter, the rainfall of each July), counted on the server: `aggregate` (`count`, `mean`, `sum`, `min`, `max`, `earliest`, `latest`), `by`, `filter`, `sort` and `first`, see [Statistics](restapi.md#statistics). Every group says how many values it has and should have (`searched`, `expected`), and `complete`: a group with a gap, a year that is not over or a year the window cuts has no `mean` or `sum` and is warned of. A tool lists 20 series at most. It cannot find runs (the longest dry spell), moving windows (the wettest 3-day total), percentiles or medians, and says so instead of estimating them, unless the values of a short window fit in one `values` answer. The answer is cut to the budget like `values`'s, keeping the first groups; `over_groups` and `metadata.search.totals` cover all of them |

The routes of the precipitation radar (`/api/v1/radar/frames` and `/radar/frame`, map images for a page to draw) are no tools.

An argument that is a mapping (`unit_targets`, `limits`, `interpolation_station_distance`,
`summary_station_distance`) is advertised as an object, and an assistant gives it as one:
`unit_targets={"temperature": "degree_fahrenheit"}`. The server sends the REST API its JSON text, which is what the
query parameter takes (`?unit_targets={"temperature": "degree_fahrenheit"}`), so the object and the JSON text of it
are the same argument.

Every tool has a `title` ("Find stations" for `stations`) and says in its annotations that it only reads:
`readOnlyHint` true, `destructiveHint` false and `idempotentHint` true, so a client may run it without asking
first. `openWorldHint` is false for `coverage`, `glossary` and `providers`, which answer from wetterdienst's own
metadata, and true for the others, which fetch from a provider's service (`auth` probes it).

The endpoints of the server itself (`/api/version`, `/api/settings`, the index and the health check) are not tools.
The server gives the assistant a block of `instructions`: the workflow (find the station, then read its values),
which tool not to reach for first (`interpolate` and `summarize` introduce an error and are for an explicit
request), how a parameter is written (`daily/climate_summary/temperature_air_mean_2m`) and how to read a result.
The instructions and the descriptions of the tools are written for agents and are improved without a new version.

The same two steps serve a network of any `kind` (`observation`, `forecast`, ...), for a place given by coordinates as
well as by name. The `country` of a provider is the country of the agency that runs it, not the extent of its data, and
the instructions tell the assistant not to conclude from it that a network cannot serve a place: it looks at the
network's `kind`, its [`extent`](restapi.md#extent) (where its stations are, in `providers`; `coverage` has the extent of each
dataset of one network) and at
what `stations` returns near the place. `providers` is the tool for which networks reach a place, as well as for the
country, licence and credit line of a provider.

An error comes back as the text of the REST problem, for instance
`HTTP error 422: Unprocessable Content - limit: Input should be greater than or equal to 1`, and an argument a tool
does not take is refused with the name of the one it takes where the tool had the old name
(`station was renamed to stations`), and as an unknown argument where it never did. No tool takes
`debug`: the log level of the server is its operator's, and a call that gives it is refused saying so.

Every `format` a tool offers is answered, as one body held to the `rows` limit. `json` and `geojson` are the
structured content of the result. `csv` is a text content block, as the REST API sends it, and so is `ndjson`, which
only `values` and `stations` offer. The structured content that the output schema of the tool
requires is then one sentence about the answer: its media type and size in bytes, and the licence, the attribution,
the note on what wetterdienst did to the data and the warnings that the REST API sends in headers for these formats
(the same in the `_meta` of the result, under `wetterdienst`), followed by the body itself, since a client may hand the
model the structured content alone. The default is `json`, which the assistant reads without further ado, and a long
`csv` goes through the context of the assistant.

### What a tool does not take

A tool is its REST route without the options that only the REST API needs, which a model reading JSON cannot use and
which were part of the tool list of every session: `pretty`, the `width`, `height` and `scale` of an image, and the
formats of a chart (`html`, `png`, `jpg`, `webp`, `svg`, `pdf`). Nothing else is dropped (the `left`, `right`, `top` and
`bottom` of a station box are arguments of the tools as they were). Charts are gone from the tools: a client that needs
a picture calls the REST API, which draws one at `/api/v1/stations`, `/values`, `/interpolate` and `/summarize` with
`format=png` and the like, as do the command line and Python, which are unchanged.

A call that still sends one of the options is answered like this, so that a client written for an earlier release
keeps working where it can. Where the tool's route took the option:

- `pretty` at any value, and `width`, `height` and `scale` as `null` (the default they had), are let go: the call is
  answered as one without them, since they change nothing of an answer in a data format. A client that sends every
  option with its default (`pretty=false`) is not refused for it.
- a `width`, `height` or `scale` with a value is a tool error. The tool draws no image, and a value may mean something
  else to a model: `interpolate` and `summarize` name `elevation` for a `height`, the height of the point above sea
  level, which let go would have been ignored.
- a `format` that the tool does not offer is a tool error that names the formats the tool answers (`format=png is not
  offered by the tool values, which answers json, geojson, csv or ndjson. Charts are drawn by the REST API:
  /api/v1/values takes format=png.`), whether it is a chart format (also in capitals, or with spaces round it) or any
  other, such as `ndjson` for `interpolate`; so is a list of formats with such a one in it. Nothing is requested from
  the provider.
- an object (or a list that holds one) for an argument that takes none, such as `shape={"format": "png"}`, is a tool
  error that names the argument: an object is read as arguments of its own, which would go past the refusal of the
  format. An empty object is refused too; `limits`, `unit_targets` and the station distances take objects. `pretty`
  stays let go, whatever it is given.

The option is an unknown argument, refused as above, for a tool whose route never took it (`pretty` for `glossary`).
All the refusals of a call are one error.

## A forecast starts at now

A forecast is the rows of a model run, and the latest MOSMIX-L or DMO run begins hours before the request: at 14:28 UTC
its first row can be at 10:00 (MOSMIX-S and SWSMOS begin at the current or the next hour). An assistant that reads the
first rows reports an hour that has passed as the forecast. So `values` for a network whose `kind` is `forecast`
(`dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`, `dwd/pollen`, `dwd/uvi`; `coverage` and `providers` give the kind) leaves out the rows stamped before
the current hour, in UTC, and the row stamped at the current hour stays. A `forecast-from-now` warning in
`metadata.warnings` says that the answer starts at now and names the `timestamp` window that asks for the earlier
hours of the run; for `csv` and `ndjson`, whose headers are in the sentence and the `_meta` of the result, it is the
`X-Wetterdienst-Forecast-From-Now` header and the sentence of the tool (an `ndjson` answer also has the block as its
first line). No row is left out, and no note is attached, where the run begins at or after the current
hour. For the daily `dwd/pollen` and `dwd/uvi` the cut is by the day: a value stamped before today is left out and the
one of today stays. The cut is made before the size budget below, so that the characters of the budget go to hours that
are still to come.

Which requests are cut:

- **No `timestamp`:** every row before now.
- **A `timestamp` of whole days that contains now**, as a day or a span (`2026-11-12`, `2026-11-12/2026-11-14`): the
  rows of today before the current hour, as the instructions tell an assistant to give a day. The days of the window
  before today are what the caller named, and stay. Whether a window is of whole days is read from its text: a time
  part (`2026-11-12T00:00`) on either half makes it an exact window, served as asked, as is a month or a year.
- **Left as they are:** a day window wholly in the past or in the future, a run asked for by its `issue` (an older run
  is past by nature), a network that is not a forecast, and `interpolate` and `summarize`, whose `timestamp` is
  required. To read the past hours of today, ask with a time (`2026-11-12T10:00/2026-11-12T14:00`).

The start of now follows the resolution of a row: the current hour for an hourly forecast (the only one a network has
today) and for anything finer or subdaily, the current 6-hour period of a `6_hours` forecast, the current day of a daily
one, the month of a monthly one and the year of an annual one. A frame of several resolutions gets one window for each
in the note, since the window of one can span rows of another that were kept. A run that is over, with every hour
before now, answers no row and says so. The REST API, the command line and Python answer the whole run.

## The size of an answer

An assistant reads the answer of a tool in its context, and Claude Code saves a result of more than 50,000 characters to
a file instead of handing it over (it counts characters, not tokens). So the answer of `values`, `stations`,
`interpolate`, `summarize`, `coverage` and `alerts` is held to **40,000 characters** of what the client receives, in
`json`, `geojson`, `csv` and `ndjson`: for JSON the answer as the client gets it, `metadata` and `with_metadata`
included, and for `csv` and `ndjson` the structured content as JSON: the sentence of the tool, which carries the
licence and the note below, and the body, each newline and quote of it written as the escape it is there. The budget is
a constant of the server and applies to the tools alone: the REST API, the command line and Python answer everything the
[limits](restapi.md#limits) allow, so an app that lists every station of a network is unaffected.

An answer over the budget is cut, not refused, and says so:

- **`values`** keeps whole timestamps, at least one. Without a `timestamp` it keeps the end nearest to now: the start of
  a forecast (which [starts at now](#a-forecast-starts-at-now)), the latest part of a `recent` or `historical` record.
  With a `timestamp` it keeps the start of the window, so the next window continues it. Only where one timestamp alone is more than the budget are its rows cut, and no
  window can split a timestamp: ask for fewer parameters or stations.
- **`values`** with `filter`, `sort`, `first` or `by` (see [Choose the rows](restapi.md#choose-the-rows)) has the rows of
  its own order (`max_rows` has cut it already if it was given, and the `rows-capped` warning says so) and is cut in it: the first rows are kept, so with `sort=-value` the highest, and the
  `answer-truncated` note says how many of how many rows matched and how many values were searched. `metadata.search`
  stays in the answer. To find a record, ask for it (`sort=value&first=1`) instead of reading a window at a time. To meet
  two parameters at one time, name them: `filter=temperature_air_min_2m<0,wind_gust_max>=17.2` over the two requested
  parameters is the days of frost and strong gusts, with the rows of both
  ([Parameters as columns](restapi.md#parameters-as-columns)).
- **`interpolate`** and **`summarize`** answer a series as `values` does and are cut the same way. Their `timestamp` is
  required, so it is always the start of the window that is kept and the next window continues it. They have no
  `shape`, so the note offers `format=csv` (about half the size of the JSON) instead of `shape=wide`.
- **`stations`** with `name` is never cut: it asks for a few stations. Otherwise (`all`, a bounding
  box, ids) it keeps the first stations that fit, in the order of the list, and says how many match and that
  `latitude`, `longitude` with `rank` or `distance`, or `name`, narrow it. A `distance` is cut too, as a wide one lists
  hundreds of stations (983 within 500 km of Berlin): the nearest stations are kept, nearest first, and the note says
  how many lie within the distance and how far the farthest returned is, and suggests a smaller `distance`, or `rank`.
  So is a large `rank` (700 asks for as many): the nearest stations that fit are kept, nearest first, and the note says
  how many the `rank` asked for, how many are returned and how far the farthest of them is, and suggests a smaller
  `rank`. A `rank` that fits is unchanged.
- **`coverage`** is not rows but resolutions, datasets and parameters with a description each, and noaa/ghcn (59,000
  characters), dwd/observation (89,000) and dwd/phenology (139,000) are over the budget. It is cut in steps, each only
  where the one before is still over: the answer as it is; the `description` of every parameter null (everything else
  stays); whole datasets in the order of the network, as many as fit; and, where the first dataset alone is more than
  the budget, its first parameters, the others not being available through the tool. The note names the datasets that
  were left out as `resolution/dataset` and says how to ask for one: `datasets=<name>` with `resolutions=<resolution>`
  gives its full detail. Where a dataset alone is over the budget with its descriptions (noaa/ghcn `daily/data`, 210
  parameters), no request can give them, so the note does not offer one and names `glossary` for what a parameter
  means. The answer keeps its shape. It has no `metadata` block and takes no key beside the resolutions, so the note is
  the start of the `description` of the first resolution; a JSON answer reaches a client as its body alone, so no header
  carries it. `providers` is not cut: it is 20,000 characters for all providers together.

- **`alerts`** is mostly polygons and lists of areas: a warning for a coast is 80,000 characters, and the answer for
  Kiel (three warnings, REST JSON, live on 2026-11-23) was 184,612 and the 34 of Germany 1,290,282, so no warning can
  be kept whole and fit. An answer over the budget is cut in steps, each only where the one before is still over; an
  answer within it is not changed. (1) Every warning without its polygon (`geometry` null) and its lists of areas
  (`area_names` and `warncell_ids` empty, but for a `name`, where the areas that match it are kept), the rest of each
  warning as it is (1,000 to 1,600 characters each: the 34 of Germany are 38,000 and the three for Kiel 4,800). (2) For
  a `name` that matches many areas (1,644 in one warning for a coast), only the first 25 for each warning, which are
  about 1,000 characters; the note names the warnings that have more. (3) As many warnings as fit, the most severe
  first, then the most urgent, then the earliest onset. A request for a place holds only the warnings for it, so none
  goes first for it. The note names the warnings left out as `event (severity)` and how to ask for fewer: a more
  specific `name`, a `name` added to a point (both must hold), or a place where none was given. The polygon and the
  areas are not available through the tool: the REST API, the command line and Python give them. A `name` that matches
  no area of any warning in force is told in a `no-area-matched` warning beside `no-alerts-for-place`: it is no
  all-clear for the place (a place without a warning is in no list, and a name that is not DWD's German one is in none
  either), so ask by point, or, for a request that has a point, ask without the name. The REST API, the command line
  and Python do not add it.

The note (but for `coverage`, above) is a warning, `answer-truncated`, in `metadata.warnings`. A JSON answer reaches a
client as its body alone, so no header carries it (a `csv` answer has no block; for `csv` and `ndjson` the headers are in
the sentence and the `_meta` of the result, and an `ndjson` answer also has the block as its first line). It gives the
rows returned of the total, the range kept, the `timestamp` window to ask for the rest (a value the tool accepts,
ending where the caller's window did) and the ways to ask for less: a narrower `timestamp`, fewer parameters, and
`format=csv` with `shape=wide`, which is five to six times smaller than the long JSON. For `csv`, which has no block, it
is the `X-Wetterdienst-Truncated` header too and a sentence of the tool that tells it in words, never a row of the body.
`metadata.counts.rows` is the number of rows returned, not of those that were cut. The block that `with_metadata` adds
(the units, the quality legend, the settings) can be more than the budget by itself, as for a dataset with many
parameters. It counts toward the budget and is kept: the rows (timestamps, or the stations of a `rank`, a `distance`
or a listing) are cut to make room for it. Only where not even one timestamp or station fits with it, and one fits
without it, is it left out, the always-present `metadata` stays, and the note says how many characters it was and that
`coverage` and `glossary` give the units. A `name` and a single station are not cut, so there the block is left out
where it is what makes the answer over the budget: a block of 60,000 characters (noaa/ghcn with `with_metadata`) is
left out of them, and nothing else is.

The instructions and the description of `values` recommend a `timestamp` window, so an assistant that follows them
asks for a day or a week and is not cut. A forecast of ten days of three parameters in the long JSON is about 100,000
characters, a window of 48 hours about 20,000. An assistant that needs more than a tool gives uses the REST API or the
[library](large-requests.md#from-an-assistant).

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
create a session at `initialize` and has nothing to expire, and a request needs no earlier one: `tools/list` and
`tools/call` work without an `initialize`. The response to `initialize` carries an `mcp-session-id` header, a fresh
random one each time, for the clients that expect one from a streamable-HTTP server; the server neither stores nor
checks it. A request that carries it, another, or none is served alike, and none is unknown (no 404). A client of the
`mcp` package sends the id back with its requests. The id is no credential. The two requests that belong to a session
are answered with a 405, as the specification lets a server do: `DELETE` (ending a session; clients that send it on closing carry on) and `GET` (opening a stream
of messages from the server, of which a server of tools has none; the `mcp` client, which opens one once it has an
id, tries it twice and gives up without an error). A tool's answer is one body and is not streamed
(`format=ndjson` and `csv` are text content of the result, held to the same `rows` limit as every other format of
a tool, not the higher `stream_rows` of the REST API; what a tool with a `filter` or `first` reads is held to the larger
of the two, as over REST, and what it holds to `rows`). A tool makes its request to the
API in process, so it is held to the [limits](restapi.md#limits), the [timeout](restapi.md#timeout) and the
[concurrency](restapi.md#concurrency) of the server like any request. A request that a tool is refused for its size is
asked again for a window or fewer stations (for `interpolate` and `summarize`, which name no stations: a shorter
window or fewer parameters, or a smaller radius when it reaches too many stations), or made from the library: see
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
