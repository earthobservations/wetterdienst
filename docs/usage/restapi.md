# REST API

Wetterdienst has an integrated REST API which can be started by invoking:

```bash
wetterdienst restapi
```

There's also a hosted version at [wetterdienst.eobs.org](https://wetterdienst.eobs.org).

The REST API is the backend of the [web app](app.md) and of the [MCP server](mcp.md), and the command line renders
through the same functions, so what is said here holds for all four. [Troubleshooting](troubleshooting.md) says what
the failures mean.

## Web App

The [web app](app.md) is a client of this API, with a map-based explorer, forecasts, climate stripes, the providers
and a glossary; its page says what is in it and how to run it.

## What every endpoint shares

The JSON and GeoJSON of the `stations`, `values`, `interpolate`, `summarize` and `history` endpoints
carry a `metadata` block next to the data, always: see [Response metadata](#response-metadata). Add
`with_metadata=true` for its heavier parts, and (for the endpoints of values and `history`)
`with_stations=true` to include the stations' metadata; a listing of `stations` is the
stations, and takes no `with_stations`. In `values` the `stations` block lists the stations that have rows
in the answer, one entry for each resolution and dataset that has rows (a row of nulls is a row, so a
station read with `drop_nulls=false` is listed): the stations that `metadata.request.stations.ids` and
`counts.stations` name, and those of the GeoJSON. Where the wide shape merged several datasets of a resolution
into one row, which names no dataset, the block has an entry for each of the datasets, and the GeoJSON one
feature for the station. A station of the request with no rows is not in
the block, and the block is an empty list where there are no rows. A station named in `stations` that has no
rows while other named stations do is told by a `station-without-rows` warning ([below](#response-metadata)). To find a
requested station that has no rows otherwise, compare the ids the answer names (`metadata.request.stations.ids`, up to 100 stations, padded as the answer pads them: `1048` is `01048`) with yours, or ask `stations` for it without `timestamp`
(with `rank`, `stations` lists the N closest by distance, not the ones the walk took). The `history` block
lists the stations of the request. With `with_metadata=true`, the JSON and GeoJSON of `values`,
`interpolate` and `summarize` also carry a `settings` block next to `metadata`: the settings the result
was got with, named as the endpoint's query parameters are. `interpolate` and `summarize` also report the settings the server sets alone
for them, which no query parameter of theirs changes: `skip_empty`, `skip_threshold`,
`skip_criteria`, `drop_nulls` and `station_distance_resolution_factors`.

For `interpolate` and `summarize`, `with_stations=true` lists the stations (once for each dataset of the request),
each with its `distance` from the point (km) and its `elevation_difference` to it (m); the GeoJSON always lists them.
The rows name their stations by id (`taken_station_ids`, `taken_station_id`) and decide which station gave a value;
this list says where each stands: see
[Interpolation](interpolation.md#which-stations-an-answer-was-made-from). A CSV holds the rows only.

The command line renders through the same function, so the same request gives the same body there:
`wetterdienst values ... --with-metadata=true` writes the `settings` block too, `--pretty` the
indentation `pretty=true` does, and every command that prints JSON prints the `metadata` block.

What the endpoints share about which stations a request names:

- **A name** (`name=Dresden`) is matched fuzzily, without regard to case or diacritics (`Köln`, `Koln`
  and `koeln` are the same name). `stations` lists the best five matches, to choose
  from, and `values` the one best match, as the library's `filter_by_name` does. `rank` sets another
  number of stations, for either; a station is one match however many datasets it has, and two
  stations that share a name are two. A name that holds the whole query as a run of whole words (`Bayern` in
  `Bayern: Mainfranken`, not `Sachsen` in `Niedersachsen`) matches at any threshold below 1 and comes first, then the best
  match; equal scores the closer whole name first, then in the order of their station ids. With a `timestamp`
  the name is matched among the stations that have a record in that window, for `values` as for `stations`, so the best match is not a station that closed before it
  while one of the same name is open; a window no station of that name covers is an empty
  result. The library's `filter_by_name` does the same with the `start` and `end` of its request.
- **A list of station ids** (`stations=01048,99999`) leaves out an id the network has no station for and
  goes on with the others. When none exists the result is empty. The ids left out are named in a
  warning of the response's `metadata`, and in the server's log. The one reference station
  of `interpolate` and `summarize` is a lookup, not a list: unknown, it is a 404 (a 502 for `dwd/observation` and
  `dwd/derived` where a directory of the lookup was skipped, below).
- **A region** (`region=Hamburg`, a comma-separated list for several) selects every station the provider lists under
  it: the `region` column of the stations, which is the source's own (a state, province, canton or département, the
  spelling too: DWD's `Hamburg`, `HH` on `dwd/road`, Hub'Eau's `FINISTERE`), so DWD's `Hamburg` is twelve stations
  of `daily/kl`, nine on land and three at sea, each named with its position in the answer. It is compared as a name
  is, whole and not fuzzily (case, accents and transliteration do not matter, nor does a hyphen against a space), and
  no table of other languages' names is behind it: `Hesse` is no `Hessen`. A region the network does not have is a 400
  of the kind `request-refused` that names it, the closest regions and the regions there are (twenty at most, and how
  many more, with how many stations have no region where some have none); where the stations of the requested
  parameters have no region (the forecast networks of DWD, `smhi/observation`, `imgw`, ...; the list is in
  [the Python API](filter-by-region)) it is a 400 that says so. Neither is an empty result. The exception is a list
  of stations that is empty: it has no region to refuse, and the result is empty. Where the lookup skipped a
  directory of DWD's server (`file-skipped`) that may hold the region, a region that is not found, a list without
  stations and a list without regions are a 502 that names the directory, as a station of `interpolate` is, and not
  the 400 or the empty result. Like the others it is one of the exclusive selections: giving two
  is a 422, and `rank` and `distance` do not go with it. A `values` request is counted against the limit of stations
  as any other, and the refusal for a region tells it to name fewer regions or the stations by their ids.
  `interpolate`, `summarize` and `history` take no `region`.
- **A WMO number, a WIGOS identifier or an ICAO code** (`wmo_id=10381`, `wigos_id=0-20000-0-10381`,
  `icao_id=EDDH`, each a comma-separated list) selects every station that has one of them, which is more than one
  station where an id is on several, as the library's `filter_by_wmo_id`, `filter_by_wigos_id` and `filter_by_icao_id`
  do. They are read in the notation of the station columns of the same names (`1001` is `01001`, `eddh` is `EDDH`,
  `0-056-101-01002` is `0-56-101-01002`); a value that is none of them is a 422 that names the notation. An id no
  station has is left out and named in an `unknown-station` warning, as for `stations`, and a provider that
  publishes no such ids (the columns are null) finds nothing. Like `stations` and `name` they are one of the
  exclusive selections: giving two is a 422. A `stations` listing is cut to the window like any other selection.
- **An empty result** -- a window without readings, a name nothing is called -- is a 200 with an empty
  `values` or `stations`, on the command line exit 0 with the sentence on stderr. A 4xx or a non-zero
  exit means the request failed.
- **A window** (`timestamp`, a date or an interval as for `values`) also narrows `stations`: it lists
  only the stations whose record overlaps it. A station is left out when it started after the window,
  or ended before it by more than a buffer, because the end a source publishes lags a station that is
  still reporting: two days by default up to daily, 62 days for monthly and 732 for annual. The start is
  compared exactly, as an index states the first day with a reading. A station whose start or end is not
  published is kept. `station_window_end_buffer` sets the buffer in days, the same for every resolution
  (0 to 3660): `0` compares the end exactly, and left out it is the buffer by resolution, or the
  server's `WD_TS_STATION_WINDOW_END_BUFFER`. It applies to `stations` and to `values` with a `name`, as
  the library's `filter_by_name` applies the option of the same name, and `values` reports it in the
  `settings` block. With a point and `rank`, the window leaves out stations before the nearest are taken.

Every timestamp in a JSON or GeoJSON body, of values, stations, history and alerts alike,
and the same on the command line and in the MCP tools, is written the one way: ISO 8601 in UTC, to
the microsecond, with its offset, for instance `2026-09-01T00:00:00.000000+00:00`.

## Versioning

The routes are served under `/api/v1/...`, and OpenAPI (`/openapi.json`, `/docs`) documents that
prefix. `/api/...` is an alias of the current version: the same routes with the same handlers, so
`/api/values` and `/api/v1/values` answer alike. The alias is not deprecated, and it follows the
current version, so a client that must not move with the next one asks for `/api/v1`. The
examples on this page and the web app use the alias.

`GET /api/version` reports the version of the contract next to that of the package:

```json
{
  "version": "0.157.0",
  "api_version": "1",
  "mcp_enabled": true,
  "mcp_path": "/mcp/v1",
  "mcp_alias_path": "/mcp",
  "plotting": false,
  "limits": {"max_stations": 100, "max_rows": 500000, "max_stream_rows": 10000000, "max_groups": 50000, "timeout": 60.0, "max_concurrent": 32}
}
```

`limits` are those the instance holds requests to (see [Limits](#limits)), so a client can size its
requests before it is refused; 0 means the instance sets none. `plotting` says whether the instance
draws [charts](#charts), so a client learns it before it asks for one.

`api_version` is raised with a change a client has to follow. A path under a version that does
not exist (`/api/v2/...`) is a 404. What counts as a change a client has to follow, for this API and
for the other surfaces, is on the [Compatibility](compatibility.md) page.

The MCP endpoint is versioned alike, see [MCP endpoint](#mcp-endpoint). The operation ids of the
OpenAPI document (`values_api_values_get`) and the names of the MCP tools (`values`) do not carry
the version, see [The OpenAPI document](#the-openapi-document).

### Deprecation

What is deprecated keeps working for at least two minor releases of wetterdienst before it is removed, and
a removal is announced in the changelog under `Deprecated` when it is deprecated. Meanwhile:

- the OpenAPI document marks the endpoint or the parameter `deprecated`;
- every response to a request that uses it carries a `Deprecation` header ([RFC 9745](https://www.rfc-editor.org/info/rfc9745/)),
  `@` and the unix time of the day it was deprecated, for instance `Deprecation: @1791158400`;
- where a day is set from which it may stop working, `Sunset` ([RFC 8594](https://www.rfc-editor.org/info/rfc8594/))
  says it as an HTTP date, and a `Link` with `rel="deprecation"` points to where the replacement is told;
- for a parameter, the `metadata` block of the answer has a `deprecated-parameter` warning; the old name of a
  renamed canonical parameter, which stays an alias for at least two minor releases, is marked so, without a `Sunset`.

A response that uses several deprecated things says the earliest of each date. A client that logs the
`Deprecation` header of the answers it gets is told before anything is removed.

From 1.0.0 an endpoint or a parameter of `/api/v1` is removed only with the next version of the API: `/api/v1`
is served for at least two minor releases after `/api/v2` appears, and announced by these headers, with `Sunset`
set to the day it stops. Nothing is deprecated today. The code marks one with `ui.deprecation`: `deprecated_route(Deprecation(since=...))` in the decorator of a route
for an endpoint, `mark_deprecated(...)` in the handler that reads a parameter.

## Response metadata

The JSON answer of `stations`, `values`, `interpolate`, `summarize`, `history`, `issues` and `alerts` has a `metadata` member (`station-ids` has one too, with a `providers` list in place of the
one `provider`, as its answer holds several providers' stations, see [Find a station by id](station_ids.md)), and so does the GeoJSON of the first four (next to its
`data`) and of `alerts` (a foreign member of the collection, next to its `snapshot`). It is always there, and
it says where the data comes from and may be used, what was asked for as the library resolved it, and
what the answer is missing:

```json
{
  "metadata": {
    "api_version": "1",
    "schema_version": "1",
    "retrieved_at": "2026-10-16T21:04:37.118220+00:00",
    "data_updated_at": null,
    "provider": {
      "name_local": "Deutscher Wetterdienst",
      "name_english": "German Weather Service",
      "country": "Germany",
      "copyright": "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
      "url": "https://opendata.dwd.de/climate_environment/CDC/",
      "license": {
        "spdx_id": "CC-BY-4.0",
        "name": "Creative Commons Attribution 4.0 International",
        "url": "https://creativecommons.org/licenses/by/4.0/"
      },
      "attribution": "Source: Deutscher Wetterdienst"
    },
    "producer": {
      "name": "wetterdienst",
      "version": "0.156.0",
      "repository": "https://github.com/earthobservations/wetterdienst",
      "documentation": "https://wetterdienst.readthedocs.io",
      "doi": "10.5281/zenodo.3960624"
    },
    "processing_note": "Processed by wetterdienst: the provider's data was reshaped into a uniform table, and its units converted where they differ.",
    "request": {
      "provider": "dwd",
      "network": "observation",
      "parameters": ["daily/climate_summary/temperature_air_mean_2m"],
      "periods": ["historical", "recent"],
      "start": "2026-01-01T00:00:00.000000+00:00",
      "end": "2026-01-01T23:59:59.999999+00:00",
      "stations": {"filter": "by_station_id", "count": 1, "ids": ["01048"]}
    },
    "counts": {"stations": 1, "rows": 1},
    "crs": {
      "code": "EPSG:4326",
      "name": "WGS 84",
      "axis_order": "longitude, latitude",
      "elevation": "metres above mean sea level"
    },
    "warnings": [
      {
        "code": "unknown-station",
        "message": "No station with station_id 99999 for the requested parameters and periods of DwdObservationRequest."
      }
    ]
  },
  "values": [
    {"station_id": "01048", "resolution": "daily", "dataset": "climate_summary", "parameter": "temperature_air_mean_2m", "timestamp": "2026-01-01T00:00:00.000000+00:00", "value": 1.6, "quality_flags": "10"}
  ]
}
```

- **`provider.license`** is the terms the provider publishes its data under: `spdx_id`, the identifier of
  the licence in the [SPDX list](https://spdx.org/licenses/) (or an expression, `CC-BY-4.0 AND NLOD-2.0`,
  where the provider names two that both apply, as MET Norway does), `name` and `url`. `spdx_id` is `null` where the
  terms have none
  (ECCC's data server end-use licence, AEMET's legal notice, IPMA's statement that the
  data may be reused with the source named). `url` is the licence, or the provider's own page that states it. The
  whole of `license` is `null` where the provider states no terms that could be read: no provider does at present,
  and it is then for the user to ask the provider. **`provider.attribution`** is the credit line to give, in the provider's own words where it
  states one (DWD's "Source: Deutscher Wetterdienst") and else its name as the rights holder; `null` where the
  provider states none or asks for none.
  `copyright` stays the free text it was, the rights holder's notice, shown for information: cite `attribution`. All providers are listed with their licence and credit line on
  [licences and credit lines](../data/provider/licenses.md).
- **`processing_note`** says what wetterdienst did to the data, in the same words for every provider and licence:
  "Processed by wetterdienst: the provider's data was reshaped into a uniform table, and its units converted where they differ." Licences such as CC BY ask that changes be indicated. The answers of `interpolate` and `summarize` add
  "The values were selected or calculated from the provider's readings.". It is always there on an answer that holds
  provider data (`issues` and `alerts` too, not `providers` or `coverage`), whatever `with_metadata` says, and it is a
  statement of fact about the processing: it does not replace the credit line, and it is not legal advice about what
  your licence asks of you. Where it does not go is on [licences and credit
  lines](../data/provider/licenses.md#what-wetterdienst-does-to-the-data).
- **`request`** is the request as resolved, not as typed: `daily/kl` is the list of parameters it means,
  `periods` the periods read, `start` and `end` the window applied in UTC (`null` without one), and
  `stations` how they were selected (`filter`: `all`, `by_station_id`, `by_name`, `by_rank`,
  `by_distance`, `by_bbox` or `by_sql`), `count` the stations in the answer and `ids` their `station_id`, for an
  answer of up to 100 stations; for one of more `ids` is `null`, so a listing of a whole network does not carry
  its ids a second time, and `count` is how many there are. To have the ids of a large answer, read the
  `station_id` column of its body.
- **`retrieved_at`** is when the answer was made, in UTC. Whether the data came from the server's cache
  is not told.
- **`data_updated_at`** is when the source last updated the data of the answer, in UTC: the newest such date over the
  files the answer was read from, **a file that failed and one that gave the answer no row not among them** (see
  "Which files count" below). It is not when the data was fetched (that is `retrieved_at`) and it is `null` where
  there is none to give: never `retrieved_at` in its place. What the date is depends on what the source states:

  - **A file the source dates** (the observations of DWD and its derived, phenology, POI and road networks, CHMI, IMGW,
    IPMA, MeteoSwiss, NOAA GHCN and the SYNOP of Météo-France): when the source last wrote the file or files the answer
    was built from, the `Last-Modified` of their download. A file written daily is dated daily, whether or not a value
    in it changed, so the date says how current the copy is and not that the readings in it are new. A response whose
    `Last-Modified` is not earlier than its own `Date` (a server that sends the time of the request), is not a date, or
    is not there gives none, and the date of the request is never taken for it.
  - **`meteofrance/observation`**: the newest `last_modified` that data.gouv.fr gives the files read, the date the
    Etalab Open Licence 2.0 asks to be named with the source. Its listing is cached for 12 hours, so the date may lag a
    file refreshed since by up to that time.
  - **A forecast** (`dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`): the model run the forecast is of, not the file it was
    published in, so it is the same for a run read again later, and `retrieved_at` less `data_updated_at` is how old the
    run is. This is the age of a forecast only: for a file it is not the age of the data. `dwd/pollen` and `dwd/uvi` have
    no run, and their date is when DWD last wrote the one file it serves (its `Last-Modified`).
  - **The warnings of `dwd/alerts`**: the newest `sent` of the warnings of the whole snapshot, which DWD states in each of them,
    also for an answer filtered by a place, which may hold a few warnings or none; a snapshot with no warning has none.

  The date is `null` for the networks whose source states none and whose responses carry no `Last-Modified` that is a
  file's (FMI and SMHI send the time of the request), for those that need credentials and are not examined (AEMET,
  KNMI, MET Norway, Met Office), for every list of stations, and for a streamed answer: NDJSON and CSV answers of
  `values` write their head before the stations are read, so the newest date is not known, they say `null` and the
  header is left out, where a JSON answer of the same request has the exact one. An answer made from the cache has the
  date of the copy it was made from, however long ago it was cached. A copy cached before the library kept dates has
  none until it expires (12 hours at most for the networks of DWD, CHMI, IMGW, IPMA, MeteoSwiss and NOAA) or the cache
  is cleared, and `meteofrance/synop` downloads its finished years once more, once, to date them. For a file
  `retrieved_at` less `data_updated_at` is how long ago the source wrote it, which is not how old the readings in it
  are. The Python results carry it as `data_updated_at`, and the `metadata` of `to_dict`, `to_json` and
  `to_ogc_feature_collection` with `with_metadata=True` has it as a key of its own next to `provider`, `producer` and
  the `processing_note` (`null` for a list of stations). Which networks state a date, and why the others do not, is `DATA_UPDATED_STATED`
  and `DATA_UPDATED_NOT_STATED` in `tests/ui/test_response_metadata.py`.

  For `meteofrance/observation` a copy of a file made before the date the listing gives it is fetched again, and
  replaced only once the new one has arrived: where the host of the files does not answer, an archive file that is
  cached for good (the years before last) is read from the copy from before, and has the date that copy was made and
  not the listing's later one. A file of the current period, cached for 5 minutes, whose copy has expired is not
  served stale: the request fails with the download error. The NDJSON of the command line renders the whole result at
  once and has the exact date. A result cut down by `filtered_by_date` or `filtered_by_sql` keeps the date of the
  result it was cut from, newer files whose rows were cut away included, and has none where no row is left; a
  history has none.

  **Which files count.** A file dates the answer only where rows of it are in the answer: one that failed, one that
  holds no row of the station, one whose rows all lie outside the window asked for, one that holds only parameters
  that were not asked for, and one whose rows another file took the place of (the recent archive of DWD where the
  historical one has the same stamps) are not counted, and where `drop_nulls` is on (the default) a row without a value
  does not make a file count. The provider decides this on the frame it hands to the core, in the order the core cuts it
  (the first row of a reading that has a value is kept, then the requested parameters, the window and the null policy),
  so two things stay out of its sight, and a file that is in the answer for them only still counts: a value that the
  core reads as null although the provider handed it over as a text (a text that is no number), and the stamp of
  `dwd/observation`, which the provider shifts by an hour for an archive that DWD writes in MEZ only afterwards, so a
  window that begins or ends within that hour of the rows of an archive can count it or leave it out wrongly.
  `dwd/observation` and `dwd/derived` decide it for the archives of a period together, which are one file but for the 1
  and 5 minute precipitation of the historical period, and a forecast counts where one of its steps is in the answer.

- **`counts`** is the stations in the answer and its rows: the items of `values` (one per timestamp in
  the wide shape), the stations listed, or the histories.
- **`crs`** is the reference system of every position in the answer: WGS 84, longitude before latitude in
  a GeoJSON position, the elevation in metres above mean sea level.
- **`warnings`** is what the answer is missing but did not fail on, so that a partial answer can be told
  from a whole one. Each has a `code` that stays and a `message` that may be improved. The codes are
  `unknown-station` (an id of `stations`, `wmo_id`, `wigos_id` or `icao_id` the network has no station for), `station-skipped` (a station with too
  few readings, by `skip_empty` and `skip_threshold`, whether `drop_nulls` is on or off), `period-not-published`
  and `period-not-narrowing` (a period that was asked for and does not apply), `elevation-unknown` (the stations of unknown
  elevation that an estimate at an elevation had to leave out), `missing-value-marker` (readings that are
  `null` because the source wrote a marker for a missing value: with `drop_nulls` they are not in the
  answer, and this counts them; without it the `raw:` token of their `quality_flags` keeps the marker; a number
  that a plausibility check rejected is no marker and is told by the next code; a calm wind direction is none
  either, see `calm-wind-direction`),
  `rejected-by-plausibility` (values that are `null` because a hard [plausibility check](../data/plausibility.md)
  rejected the number the source wrote, with the count per check in the message, a value several checks rejected
  counted under each: with `drop_nulls` they are not in the answer, without it `rejected:<check>,raw:<number>` in
  their `quality_flags` keeps them; a soft check keeps the value and raises nothing),
  `calm-wind-direction` (wind directions that are `null` because the source wrote 0 for a calm, which has no
  direction: no reading is missing. Counted apart from the markers, with the same `raw:0` token in `quality_flags`
  and the same `drop_nulls` behaviour; a 0 that is a code for no direction or the direction of a gust that was
  not reported stays a `missing-value-marker`),
  `parameter-ended` (the window reaches years in which the source no longer publishes a parameter, such as
  the hourly `pressure_air_site` of `chmi/observation` after 2024, so it has no values for them),
  `position-unplaced` (a station whose position the source writes where no swap of latitude and
  longitude puts it in the network's country, listed with a null position: `eaufrance/hubeau`; the
  answer has it when the station is in it, selected by `stations`, `name` or `all`, or when a
  search by place, a `rank`, a `distance` or a bounding box, or an estimate by `interpolate` or
  `summarize`, had to leave it out, which is every search by place of a resolution that lists it;
  for a `timestamp`, the whole list and a search by place tell it, in a listing, in the values and in
  an estimate, only if the station has a record in the window),
  `positions-unavailable` (a search by place, a `rank`, a `distance` or a bounding box, or an estimate by
  `interpolate` or `summarize` by a point, on a network whose source gives its stations no position, which is
  `dwd/pollen`, or for a dataset of one that gives them none, `dwd/derived`'s `monthly/climate_correction_factor`: the
  answer is empty by the nature of the data, and the message names the way to find the stations, the `name` and
  `stations` parameters; a search by name or id and the whole list do not have it),
  `source-fallback` (the stations whose file the provider read from its secondary source because the first failed, which
  is `noaa/ghcn` `daily`: NCEI's file could not be read (any failure but a 429: a 404, a 5xx, no connection, a body that is
  no file) and the values are the AWS mirror's, whose files of some stations are older, so the most recent days may be
  missing. One warning for the request, as `file-skipped` is, and for an estimate too: the message gives how many
  stations and names the first ten, which `stations` carries; a station read so is not one `parameter-without-rows` or
  `station-without-rows` says the source holds nothing for. A 429 is never a fallback, it is a `ProviderRateLimitError`),
  `step-without-resolution` (stations left out of the list because the step they report at is one no
  resolution of the network has (seen: 20 and 30 minutes, on some days 180 or 240): `eaufrance/hubeau`.
  The message gives how many, at which steps and names the first ten, which `stations` carries too.
  Every answer that selects stations tells it, whatever the resolution asked for, but one selected by
  `stations`, which is told only of the ids it asked for that were left out, with their steps; none is told
  where no station is left out, see
  [Hub'Eau](../data/provider/eaufrance/hubeau/index.md#stations-at-a-step-no-resolution-has)),
  `deprecated-parameter` (issued when a parameter is deprecated; none is at the moment),
  `network-not-importable` (a network of `providers` that this server cannot import, which is left out),
  `network-failed` (a network `station-ids` asked whose list could not be read, or that cannot be imported: it is left
  out of the search, the others answer, and `searched` of the block names it with the reason; if every network that was
  asked fails the answer is a 502),
  `network-rate-limited` (a network `station-ids` asked whose provider answered 429: it is left out of the search, the
  others answer, and the message and `searched` of the block name it with the wait the provider asks for; if every
  network that was asked failed or was rate-limited, with a 429 among them, the answer is the 503 of a provider's rate
  limit with `Retry-After`),
  `network-not-configured` (a keyed network `station-ids` would ask that needs credentials the server does not hold: it
  is not asked, and never a failure),
  `station-file-unchecked` (a hit of `station-ids` at a network that checks the data file of a station, `noaa/ghcn`,
  whose file could not be checked, or beyond the eight checked: the station stays in the answer),
  `parameter-without-rows` (a requested parameter that the source holds no values for, see below),
  `file-skipped` (the stations whose file the provider let go, see below), `wmo-ids-unavailable` (the stations of
  `dwd/observation` and `dwd/derived` are listed without `wmo_id` because DWD's Stationslexikon could not be read or
  is no longer the table, see [WMO numbers](../data/provider/dwd/observation/index.md#wmo-numbers-of-the-stations)),
  `wigos-ids-unavailable` (the stations of `dwd/observation`, `dwd/derived`, `fmi/observation` and `dmi/observation` are listed
  without the `wigos_id` that WMO's register OSCAR/Surface gives them, because it could not be read or is no longer
  the register of the country, see
  [WIGOS ids](../data/provider/dwd/observation/index.md#wigos-ids-of-the-stations)),
  `station-codes-unavailable` (the stations of `imgw/meteorology` are listed without `short_code` because IMGW's
  `wykaz_stacji.csv` could not be read or is no longer the list; not for `synop`, which it picks the stations of),
  `other-window-left-out` (dates the
  source has values for that the answer leaves out because they are of another series, see below),
  `window-not-closed` (values of a window that had not closed when the request was served, see below),
  `source-data-left-out` (what an estimate by `interpolate` or `summarize` left out at the stations it read, see
  below), `station-without-rows` (ids of `stations` that returned no rows while others did, see below),
  `no-alerts-for-place` (`alerts` asked for a place, a point or a name, that no warning of the snapshot is for: an
  answer, not an error, see [Alerts](../data/provider/dwd/alerts/index.md#a-place)), `no-storm-cells-for-place`
  (`storm_cells` asked for a place or a `min_severity` that leaves no cell of a scan that has some: an answer, not an
  error, see [Storm cells](../data/provider/dwd/storm_cells/index.md#an-empty-answer)), `scan-stale` (the newest scan of
  `storm_cells` is more than 20 minutes older than the time asked for: DWD's run has stopped, and an empty answer is no
  all-clear), `radar-stale` (the newest run of the RV composite listed by `radar/frames` is more than 20 minutes
  old: DWD's feed has stopped, see [Radar](../data/provider/dwd/radar/index.md#radar-frames-on-the-rest-api)) and
  `rows-capped` (`max_rows` cut the answer of [`values`](#choose-the-rows): its message says how many of how many
  matched rows are returned) and
  `answer-truncated` (the answer
  of an [MCP tool](mcp.md#the-size-of-an-answer) was cut to 40,000 characters; its message says how many rows are
  returned, the range kept, and the `timestamp` to ask for next. Only a tool's answer raises it: the
  REST API, the command line and Python answer all of it) and `no-area-matched` (an MCP tool's `alerts` answer for a
  `name` that matches no area of any warning in force, told beside `no-alerts-for-place`: no all-clear for the place,
  see [Alerts](../data/provider/dwd/alerts/index.md#a-place)) and `forecast-from-now` (an MCP tool's `values` answer for a
  forecast network without a `timestamp`, or with one of whole days around now, starts at the current
  hour; its message names the `timestamp` window of the
  hours left out, see [A forecast starts at now](mcp.md#a-forecast-starts-at-now). The REST API, the command line and
  Python answer the whole run). Codes are added as more are told; a client reads the ones it
  knows.

  `source-data-left-out` is how `interpolate` and `summarize` say that source data was left out of the estimate: one
  warning for the answer, with the causes and how many of the stations read, never one for each station. They read the
  stations around a point as candidates, nearest first, and stop when they have enough, so the walk of a values request
  that tells `file-skipped`, `other-window-left-out` and `window-not-closed` at its end does not apply to them, and none
  of them is told of a station by an estimate. It carries `stations` (the stations that were affected, in the order
  they were read, the first ten if there are more), and its message says `at N of the M stations it read`, then each cause that applies,
  with the stations it affected:

  - a file the provider could not use (the cases of `file-skipped`: a refused or failed download, a file withdrawn
    since the listing, a maintenance page, a file that would not parse, a directory found empty). The values of the
    station may be missing from the estimate. The message names the cause and advises by it, in the words of
    `file-skipped` (below): try again later for a failed download, a withdrawn file, a maintenance page or an empty
    directory; for a refused download (too large, too slow) or a file that would not parse, that retrying will not help
    and that it is worth reporting to the provider; both, grouped, where both occurred;
  - dates of another series of the source (the case of `other-window-left-out`, counted in dates for each parameter):
    the source holds values for them, nothing is missing there, and they are not read because a value of another
    window would be wrong under the parameter's name;
  - values of a window that had not closed yet (the case of `window-not-closed`, counted in values for each window:
    today, this month, this year): the day's, month's or year's value is partial and may still change, and the source
    does not mark it. They are not missing at the source and come back once the window has closed. An estimate cannot
    carry the `completeness:Incomplete` mark that `values` puts on a monthly or annual value of an open window, so it
    leaves those out as it leaves a daily one out (`metno/frost`, `dmi/observation`);
  - values a hard [plausibility check](../data/plausibility.md) rejected (the case of `rejected-by-plausibility`,
    counted in values and by check, a value several checks rejected counted under each): the source wrote a number
    there, which the check made null and the estimate does not use. A value a soft check flags `suspect:` is left out
    of an estimate in every mode, whatever is set, and is not counted.

  The causes are told in the one warning, since a caller of an estimate asks one question of it, is it made from all
  that the source holds, and a values request, which asks more, keeps its codes. A station is counted once whatever the
  number of causes. A station that the walk read once it was done and did not use, because it had enough nearer
  ones, is not counted, whether it came back with rows or, as a station whose file was lost does, with none, nor is one
  it never read. Only the providers listed below tell the first three causes to the
  walk, so an estimate without the warning is no proof that every file was read. It is told next to what the lookup of
  the stations says, which `file-skipped` (a directory of `dwd/observation` or `dwd/derived` found empty, below) still
  tells without a station: the two state different facts. In Python it is a log line at level `WARNING`, and
  `recorded_warnings()` gives it after `begin_response()`, as the REST API, the command line and the MCP tools do; the
  result of `interpolate()` and `summarize()` holds no warnings.

  `other-window-left-out` says that the source holds values of a parameter on dates the answer has no row for, because
  the values are of another series than the one the parameter is: `metno/frost` keeps two series of the daily and the
  monthly precipitation sum, 06-06 UTC (the parameter) and 18-18 UTC, and a date that only the 18-18 series has would be
  a sum of another window under the parameter's name; it keeps two of the daily maximum and minimum temperature, 18-18
  UTC (the parameter) and the calendar day, and a date that only the calendar-day series has would be an extreme of
  another window; it keeps two of the daily and monthly mean temperature, the calendar day (the parameter) and 06-06
  UTC, and a date that only the 06-06 series has would be a mean of another window. They are no missing data, so this is not
  `parameter-without-rows`, which is not told of a parameter this one names (a parameter asked for by its name, or any
  parameter of a dataset asked for whole). It carries `parameter` (`resolution/dataset/parameter`) and `stations` (the
  first ten); its message gives the number of dates at each station and says which series was left out. One for each
  parameter and request. The dates beyond the window of the request are not counted.

  `window-not-closed` says that the source served values of a window that had not closed when the request was served,
  and does not mark them: `metno/frost` serves the day's maximum, minimum, sum or mean before the day (or its 06 UTC and
  18 UTC offset) has ended, and the month so far. `dmi/observation` serves the day, the month and the year so far. A
  daily value is left out of the answer, a monthly or annual one is returned with `completeness:Incomplete` as a token
  of its `quality_flags` (an estimate leaves all of them out and tells them as a cause of `source-data-left-out`,
  above); the message says which, how many values at which stations (the first ten) and when the earliest window
  closes (UTC). It carries `parameter`
  (`resolution/dataset/parameter`) and `stations`. The values are not missing at the source: ask again after the
  window has closed, which is no failure and no `parameter-without-rows`. One for each parameter and request.

  `parameter-without-rows` says that the request succeeded and the source has no values of a parameter that was
  asked for, so that it is not taken for a failure and asked again in a loop. It carries `parameter`
  (`resolution/dataset/parameter`, or `resolution/dataset`) and `stations` (the stations it was asked at, the
  first ten if there are more). It is told for a parameter asked for by its name when no station of the answer
  has a row of it, and for a dataset asked for whole only when no station has a row of any of its parameters, so
  that a dataset with a few empty parameters says nothing of them. A parameter that some stations have is not
  told for the ones that lack it. A station that begins after the window is not read and not named, one skipped
  by `skip_empty` had rows (with `drop_nulls` too), and readings that are all null and left out by `drop_nulls` are
  no rows. A dataset that needs a window is refused without one (GH-3562), so it is never told of without one.
  The message gives the window and says `in the periods
  asked for` (for the datasets where `periods` left out a period the window would have read), `in the run issued`
  or `in the lead time asked for` where the request narrowed itself that way; the other `periods`, run or
  `lead_time` is suggested only where it can hold values (the `icon_eu` product has no long run). It says nothing
  of the source being behind for a window that reaches the present, and nothing of what a later request will find:
  a source that is late cannot be told from one that never reports the parameter.

  What it does not say is limited by what the library can see. A provider that gives up on a file it expected and
  answers with the others (a refused download, a file withdrawn since the listing, a timestamp that is not there,
  a maintenance page or an exception report answered with HTTP 200, a file that would not parse) tells the walk, and
  the station whose file was let go is not one of the stations named: the others still are, and where none is left
  nothing is said (a file that serves a whole station group or a whole network is every station's of it). A
  download that failed and was made again with success is no file let go, and what the source answers is told:
  that it has nothing (a 404 for a station that does not report the parameter, Frost's 404 "No data was found for the
  query parameters" and 412 "No available time series for the query parameters", an AEMET `estado` of 404,
  Pegelonline's 404 "Timeseries does not exist.") or a month file of `dwd/derived` that the index never listed.
  This is done for `aemet/observation`, `dwd/derived`, `dwd/observation`, `dwd/poi`, `dwd/pollen`, `dwd/road`,
  `dwd/swsmos`, `dwd/uvi`, `fmi/observation`, `imgw/hydrology`, `imgw/meteorology`, `knmi/observation`,
  `meteofrance/observation`, `meteofrance/synop`, `metno/frost`, `noaa/ghcn`, `smhi/observation` and `wsv/pegel`, each
  at the places where it lets a file go and no other; for any other provider a file it lets go without telling is not
  known, so the warning may name a station whose file was let go.
  The message says nothing of the stations that were let go: `file-skipped` does (below). A parameter
  another warning already names (`parameter-ended`) is not told again, nor is `parameter-without-rows` told for
  `interpolate` and `summarize`, for which a station without a parameter is the ordinary case. In Python it is a log line at level `WARNING`, as the other warnings that say a request returned less
  than it asked for are, and `wetterdienst.util.response_warnings.recorded_warnings` gives it after
  `begin_response()`, as the REST API and the command line do.

  The three counts, `missing-value-marker`, `calm-wind-direction` and `rejected-by-plausibility`, are for the whole
  request and say at which stations: the message gives the total, then the first five stations that have a count, with
  their name where the list has one (cleaned of control characters and cut at 60 characters) and the count at each,
  and `and N more stations` for the rest: `1400 readings ... are null, at 01975 Hamburg-Fuhlsbüttel (18), 01048
  Dresden-Klotzsche (3), 04271 Rostock-Warnemünde (2), 03987 Potsdam (2), 00183 Arkona (1) and 92 more stations;
  ...`. `stations` lists the five. The text is the same in every answer that has a `warnings` block (the library after
  `begin_response()`, the command line's JSON, REST and MCP in `json` and `ndjson`) and on the command line's
  stderr, where a CSV has its line; a REST or MCP CSV carries the code in its header and not the message. A count is of
  what was read, so a station it names may have no row in the answer (a `filter` or `first` cut it, or `drop_nulls`
  emptied it), and in a streamed answer the `metadata` line holds the count of the stations read by then, which the
  `end` line replaces: a head that names one station is not "all at that station".

  `station-without-rows` says that stations the request named by id (`stations=`; `filter_by_station_id` in Python,
  the same on the command line, in REST and in the MCP tool) returned no rows while other named stations returned
  rows, which `values` alone does not say. It carries `stations` (the ids, in the order of the answer, which is the
  catalogue's and not the order they were asked in, the first ten if there are more; the message then gives their
  number). It is told for that selection alone: a point (`rank`, `distance`), a box, a name and `all` have
  empty stations as the ordinary case, a ranked walk stops at the first stations with data, and `interpolate`
  and `summarize` read stations as candidates or one station and do not tell it.

  A station has no rows when the source holds no values of it in the window (a station the index says begins after
  the window included), or, in the long shape with `drop_nulls` (the default), when all its values were null and
  left out: with `drop_nulls=false`, and in the wide shape, which never drops a null row, such a station has rows
  and is not named, and the message does not offer that reason. With `skip_empty` a station with any value in the
  window is `station-skipped`'s, so a station named has none at all and the message does not offer it either. A null
  that carries a `raw:` token is counted by `missing-value-marker`, `calm-wind-direction` or, where a hard check made
  it, `rejected-by-plausibility`; one without is counted by none. The message gives the window and, as
  `parameter-without-rows` does, what narrowed the request (`periods`, a run, a lead time, for any of its datasets,
  the periods of the datasets in one phrase) with what to ask instead, since the values may be in what was left out.
  Without a window it says "there" only when something narrowed the request. It does not say what the other stations
  have: at least one returned rows, and the stations named had none.
  A station with a row of any requested parameter has rows, even if another parameter has none (that is
  `parameter-without-rows`). It is not told when no named station has rows (`parameter-without-rows` is, where it
  can be), for an id the network has no station for (`unknown-station` names it), for a station `file-skipped`
  names (a file that serves every station is every station read's; a station the index says begins after the window
  was not read and is still named), for one `skip_empty` dropped (`station-skipped`), or for one whose dates were
  left out for another series (`other-window-left-out`: the source holds values of it, which that warning says);
  `parameter-ended` names a parameter, not a station, and does not keep a station from being named. It is raised
  once the walk has read every station, so a stream that the client stops, a walk that fails and a rank that ends
  early name none; a limit (`max_rows`, `max_stream_rows`) refuses the request before any station is read. A
  streamed answer (`ndjson`) carries it in the `end` line, and a streamed CSV, which has no place for warnings, not
  at all.

  `file-skipped` says that the answer may be missing values for want of a file the provider let go: the cases just
  listed (a refused download, a file withdrawn since the listing, an error page answered with HTTP 200, a file
  that would not parse), so that a partial answer can be told from a whole one. There is one for the request. It
  carries `stations` (the stations whose file was let go, the first ten if there are more), and its message names the
  datasets the request read at them: a provider says which station, not which of its files. A file that serves every
  station of the request is every station's. A station is named whether its frame came back empty or `skip_empty`
  dropped it below its threshold: it is missing for the failure, not for lack of data, so it may carry
  `station-skipped` as well, for a different cause. The one exception is a rank walk (`rank`, a point) that passed a
  station over for the next candidate and went on to fill its `rank`: the answer holds as many stations as were asked
  for, and the replaced ones are not named. A rank walk that ends short, or empty, after an outage names them all.
  The message gives the cause, and its advice follows it: a failed download (a reset, a timeout, a 5xx, a 408 or
  425), a file withdrawn since the listing, an error page or an empty body (a maintenance page, a server-side exception
  report such as FMI's rate limit) and a directory found empty may be back, so it says to try again later; a refused
  download (too large, too slow, an off-host redirect, or a request the server turns down for good: a 400, 401, 403 or
  410, or an exception report that names a request error such as `InvalidParameterValue`) and a file that would not
  parse mostly stay as they are, so it says that retrying will not help and that it is worth reporting to the
  provider. Where both kinds occurred it groups them as
  `source-data-left-out` does. The code and the members (`stations`) are the same for every cause. What is missing may
  well be there on a retry for the first kind, which is the
  difference to `parameter-without-rows`, whose stations are never among them. It is told for the providers listed
  above, nothing is told when no file was let go (a 404 that is the source's answer of no data, a download made
  again with success), and not of each station for `interpolate` and `summarize`, which read the stations around a
  point as candidates and fall back to the next one, and tell the stations they read whose file was let go in one
  `source-data-left-out` warning (above). The provider logs each file it lets go at level `WARNING` as before. In Python the warning is a log line at that level too.

  A file of `dwd/observation` or `dwd/derived` that the file index listed and the server answers with a 404 is told as
  withdrawn, and the listing of its directory is dropped from the listing cache (kept for 12 hours otherwise; a year
  directory of the 1 and 5 minute precipitation too), so that the retry the message advises lists the directory afresh
  and finds the file under the name DWD gave it at its annual rollover (#3892). It is dropped once for each directory
  in a request, so files that stay a 404 cost one more listing of it for the request, not one for each file.
  `dwd/swsmos` tells the cause of the run it could not read, the newest one the request names: a 404 is a withdrawn
  run, a zero-byte 200 an empty body, a body that would not parse an unreadable one, a directory that lists files and
  no run a file the reader cannot use, and an empty or missing one an empty directory. `dwd/pollen` and `dwd/uvi` tell a
  region or a place of their table that the file does not hold (one DWD has renumbered, renamed or dropped) as a file
  with no forecast of the station,
  which a retry does not change.

  `dwd/observation` and `dwd/derived` tell it too, for a directory of DWD's server that is missing (a 404) or empty
  (an index page with no link) while the stations were looked up, which `stations`, `values` and `history` all do
  first: the lookup goes on without it and the answer is partial, a 200 and not an error (#3819). So does a
  `dwd/observation` directory that lists files and no description of its stations (for the extreme wind, none of its
  FX3 or its FX6), which was skipped with a log line and nothing in the answer: the warning reads `The directory ...
  lists no description of its stations` and the listing of that directory is not kept in the listing cache either, as
  DWD uploads the description after the files (#3834). The warning has no
  `stations`. It names the directory that was listed, the dataset and the periods that were skipped for it (`the
  historical stations of daily/climate_summary were not looked up`): what is certain is that a station that only that
  release lists is not in the answer, and its values or history are not read. What the directory was read for is not
  always the period's own (the 1 minute precipitation reads the daily `more_precip` directory for the region of its
  `historical` stations), so the period named is the one skipped. A dataset whose one directory is empty (the solar
  datasets list the same for every period) answers no station. `values` and `history` say the rest at the stations they
  read: a station found in another period whose `historical` file list is empty is named by `file-skipped` as for any
  file the provider let go (`values`), or by a second warning of the directory that lists the stations whose history was
  not read (`history`); the two state different facts and both are kept. A station that only the skipped release lists
  is not found, and `interpolate` and `summarize` with such a `station` have no
  answer to put a warning in: an error answer has no `warnings`. They answer a 502 of the kind `upstream-failed`
  whose `detail` names the directory and why it was skipped (``No station found for 00044. The lookup of the stations
  went without the directory `climate/monthly/kl/historical/` (its listing came back empty or missing), so a station
  that only it lists is not found, and this may be one. Try again later.``), not the 404 that says the station does
  not exist (#3834). What a skipped directory can say decides which id gets it: an empty or missing directory says
  nothing of the stations it holds, so every id the lookup does not find is the 502; a directory that lists files and
  no description names its stations in its file names, so only an id among them is, and any other id is the usual 404.
  The MCP tools give the same text, the command line exits 1 with it, and Python raises
  `StationListingIncompleteError`, an `UpstreamError`. A station that is not found where every directory was listed
  is still the 404. A history with the warning is not cached (below). Only a listing that is missing, an index page with
  no link or a link to itself only, or a directory with files and no description of its stations is told this way.
  A connection that cannot be made (503), a reset, a timeout or a 5xx of the server (502 or 504) and a 200 page that
  is no index of a directory (a CDN's error page, a JSON error: a `DownloadError`, a 502) are errors as before, never
  a `file-skipped` and never "no data". No empty listing is kept in our listing cache, a year directory of a tree
  included (`5_minutes/precipitation/historical/2022/`), so DWD filling a directory again is seen by the next request; a cache
  written by an older version that holds an empty listing is read as a miss. A directory found empty is listed once
  by a lookup and once by a walk (a walk over a hundred stations asked for it, five GETs at a time, at each station and
  again for the fetch-ahead): a lookup or a walk remembers it for its own length and no longer, in Python as over REST,
  so the next request asks again and nothing is kept in a context between calls. `describe_fields` stays an error. A
  station with no file in a listing that is there (one that only has `recent` data) has no history of it, which is the
  source's answer, and no warning.
- **`api_version`** is the version of the API (`/api/version`), and **`schema_version`** that of this
  block, so that a stored answer can be told from one in a later shape.

Where the answer is not about stations, `request.stations` is `null` and `counts.stations` is `0` (the
warnings of `alerts`), and `counts.rows` counts what it lists: the issues, the alerts. `providers` has a
smaller block, with the `api_version`, `schema_version`, `retrieved_at`, `producer`, `warnings` and the counts of
providers, networks and the different parameters they declare: its answer is about the library, and
the terms are those of each provider it lists.

`with_metadata=true` adds two more members to the block:

- **`parameters`**: for each parameter read its `resolution`, `dataset`, canonical `name`,
  `name_original` (the source's), `description`, `quantity` and the `unit` of its values: the target of the
  quantity, which `unit_targets` sets, where `convert_units` is on, else the unit the source publishes, its
  `aggregation` and its `timestamp_position` (what they mean: [Aggregation and timestamp
  position](../data/parameters.md#aggregation-and-timestamp-position-in-the-answers); `null` is not stated).
- **`quality`**: what the `quality_flags` of a reading holds (its `format`), the `source_flags`, the
  quality flags the datasets read publish, whose code is the first token of `quality_flags`, and the
  `legend`: what each kind of token means for the network read, in the order of the column. An entry has
  its `kind` (`zone` for `zone:mez`; `null` for the source's own flag, which has no prefix and comes
  first), how it is `written` (`zone:<mez|mez-1973-75|mez-local-mean-time|woz>`, `raw:<text>`), its
  `meaning` and, where the source documents a closed set, its `codes` with their meanings (DMI's
  `validity:true` and `validity:false`, IMGW's `8`, `9`, `Z` and `11`, CHMI's quality `0` to `5`, the
  MADIS flags of the NWS). Where the source tells the codes itself (DWD's QN levels, Frost's
  `qualityCode`, GHCN's flags) the `meaning` names whose they are, and `codes` is `null`. The legend is
  empty for a network whose readings carry no flag (LHMT, MeteoSwiss, WSV).

A format with no body to put the block in carries the same in headers, and so does every JSON answer:

| Header | Value |
| --- | --- |
| `X-Wetterdienst-API-Version`, `X-Wetterdienst-Schema-Version` | `api_version` and `schema_version` |
| `X-Wetterdienst-Retrieved-At` | `retrieved_at` |
| `X-Wetterdienst-Data-Updated-At` | `data_updated_at`; left out where it is `null` |
| `X-Wetterdienst-Provider` | the provider's English name |
| `X-Wetterdienst-License` | the SPDX identifier of the licence, else its name; left out without a licence |
| `Link` | `<licence url>; rel="license"`, left out without a licence |
| `X-Wetterdienst-Attribution` | the credit line; left out without one |
| `X-Wetterdienst-Processing` | `processing_note` |
| `X-Wetterdienst-Stations`, `X-Wetterdienst-Rows` | the `counts` |
| `X-Wetterdienst-Warnings` | the `code` of each warning, comma-separated; left out without warnings |
| `X-Wetterdienst-Truncated` | the message of the `answer-truncated` warning of an MCP tool's answer; left out otherwise |
| `X-Wetterdienst-Forecast-From-Now` | the message of the `forecast-from-now` warning of an MCP tool's forecast answer; left out otherwise |

A text with more than ASCII in it (a credit line such as "© Météo-France"), or a character a header cannot
carry, is percent-encoded UTF-8;
`urllib.parse.unquote` reads it back. The CSV and image formats are otherwise the data alone, as they were.
The command line prints the block in its JSON and GeoJSON, as REST does, and nothing of it in CSV; the MCP
tools return the REST answer, and so the block.

## The OpenAPI document

`/openapi.json` (and `/docs`, the interactive reference) is the contract of the API. `tests/ui/openapi.snapshot.json`
is that document as last reviewed, without its `info.version` (the version of the package, which a release
changes and which a test holds to the served one): a test fails when the served document is not it, and
`uv run poe openapi:snapshot` writes it anew, for the diff to be read in the pull request that changes the contract.
A second test holds the served document to `tests/ui/openapi.baseline.json`, the document of the last release: a path, a
parameter, a status, a member or an enum member that release offered must still be there, with its type, and a
request must not be asked more of (a changed default, a tighter bound, a new pattern), so a change that would break a
client written against it fails even where the snapshot was regenerated with it. The baseline is refreshed in the
release commit, with `uv run poe contracts:baseline`.

- **`info`** is the project's: the title, the MIT licence, the issue tracker as the contact, and the `version` of
  wetterdienst that serves the document, and `info.x-api-version` is the version of the API (`1`, the same as
  the `v1` of the paths, `api_version` of `GET /api/version` and of the `metadata` block, and the
  `X-Wetterdienst-API-Version` header). The `servers` are the hosted instance and the address `wetterdienst restapi` listens on.
  There are no terms of service: the data is published under the terms of each provider, which the `metadata` of an
  answer and `providers` state.
- **Tags** group the operations: `Catalogue` (`coverage`, `providers`, `glossary`, `auth`), `Stations` (`stations`,
  `issues`, `history`), `Values` (`values`, `interpolate`, `summarize`), `Alerts`, `Storm cells` and `Server`
  (`version`, `settings`, `health`, `ready`, the index and `robots.txt`).
- **`operationId`** is the name of the handler, then the path without the version, then the method, with every
  non-word character an underscore: `values_api_values_get`, `stations_api_stations_get`. It does not carry the version, so
  a client generated from the document keeps its method names when the version moves, and the MCP tools are found by it (`values`, `stations`, see [MCP endpoint](#mcp-endpoint)). Changing one is a
  break of the API version, as a removed path or parameter is.
- **Answers** have a schema everywhere: the health check (`Health`), the readiness check (`Ready`), the version (`VersionAnswer`) and the data
  routes (the response models above), and a media type of their own for the index (`text/html`) and `robots.txt`
  (`text/plain`).
- **Exclusive parameters** are stated on the operations that have them: `stations` and `values` (`all`, `stations`,
  `name`, a point or a box), `history` (`all` or `stations`), `interpolate` and `summarize` (a `station` or a
  point). The document does not write it as a
  `oneOf`. That is a keyword of one schema, and these are separate query parameters; the only place for it would be one
  object parameter (`style: form`, `explode: true`) in place of them. Then the operation would no longer list `all`,
  `name` and the rest, which the check against the last release counts as removed, and the MCP tool would take one
  argument `selection` instead of them. So the parameters stay as they are, and each operation says it in three ways:
    - the extension `x-wetterdienst-selection` of the operation lists the groups: `exactly_one_of` (for `stations`
      and `values`: `["all"]`, `["stations"]`, `["wmo_id"]`, `["wigos_id"]`, `["icao_id"]`, `["name"]`, `["region"]`,
      `["latitude", "longitude"]`, `["left", "bottom", "right", "top"]`), `then` (with a point, exactly one of `rank` and
      `distance`) and `requires` (a `distance` needs a point, a `rank` a point or a `name`);
    - the `description` of each parameter it names ends with the sentences of the refusal that are about it, such as
      `Exactly one of all, stations, wmo_id, wigos_id, icao_id, name, region, (latitude and longitude) or (left, bottom, right and top) is required.`, and for a point also `Exactly one of rank or distance is required with latitude and longitude.`;
    - its `examples` hold one value the parameter takes, such as `stations=01048,04411` and
      `name=Hamburg Fuhlsbüttel`, or a point of `latitude=53.63`, `longitude=10.0` and `rank=3`. A list is a list
      there, which a client writes comma-separated (`explode: false`). The limits of the server still apply to a
      request made of them: `all=true` on `values` or `history` over a network with more stations than the server
      allows for one request is a 400 (see [Limits](#limits)).

  The model that refuses a request, the extension, the sentences and the examples are written from one definition
  (`Selection` in `ui/core.py`), which the model enforces whole, the `then` and `requires` as well as the groups.
  Tests hold the groups to the rules as written for a client, over every combination of up to three of the
  parameters, and the document to the 422 the server answers with. They hold the examples of each alternative to the
  model and to the schema of the parameter, and run those of `stations` and `values` against a stand-in network of
  eight stations; the other operations' examples are not run. The sentences and examples are on the parameters of the
  operation and not on their schemas, which the MCP tools are built from, so the tools carry no more text than before.

  `x-wetterdienst-selection` is informative. It may change in a minor release, as the descriptions and examples
  may: what is promised is the refusal itself (the 422, its `type` and the alternatives it names), which is held by
  the contract tests, and not this member of the document.
- **Errors** are declared by status where the route can answer them, as references to the `responses` of
  `components`, each listing the kinds of problem that status is (see [Errors](#errors)). Every route under `/api/v1`
  can answer a 400 for a `Host` the server does not answer to, a 500, a 503 when the server is working on as many
  requests as it allows, and a 504 when the request times out; a route with a query also the 422. Beyond those: the
  routes that read from a provider (`stations`, `issues`, `history`, `values`, `interpolate`, `summarize`,
  `alerts`, `storm-cells`, `kostra`, `station-ids`, `radar/frames`, `radar/frame`) the 400 of a refused request, 404, 501 and 502 (and `stations`, `values`, `interpolate` and `summarize` the 403 of a chart
  that the server does not draw); `coverage` a 400, 404 and 501,
  `auth` a 404 and 501, `providers` a 404 and `settings` a 400. A test makes each
  of these routes fail with each exception of the table of [Errors](#errors) and holds the status it answers to
  what the document declares.

## One vocabulary

A request is spelled the same on the REST API, the command line and the MCP tools, so that what is
learnt on one holds on the others:

- **The same name, with a hyphen on the command line.** The query parameters of an endpoint and the
  arguments of its MCP tool are written with underscores, `name_threshold`, and the options of the
  command with hyphens, `--name-threshold`. The mapping is that and nothing else, and a test holds
  every parameter of every request to it: a parameter has an option and an argument of its name and
  type, or is written down with the reason it has none (`--target` writes to a file, which REST does
  not). The underscored spellings of the command line,
  `--convert_units` and the like, are refused with an error naming the hyphenated one.
- **A parameter that takes a list is plural.** `parameters`, `periods`, `stations` and `sections`,
  and `resolutions` and `datasets` of `coverage`, take a list; `station` for `stations` is refused
  with an error naming the plural (`station was renamed to stations`) on the routes that took it in
  0.139.0 (`stations`, `values`, `history`). A name a route never had is no rename there but an
  unknown parameter: `date` of `stations`, which takes a `timestamp` only, `parameter` of `values`.
  A parameter of one value is singular: the one reference
  `station` of `interpolate` and `summarize`, the `station` of `issues`, the
  `parameter` text `glossary` looks for.
- **A request does not set the log level.** `debug` was a parameter of every data endpoint (not `version`,
  `settings` and `health`) that set the level of the logger of the whole server process, for every caller;
  it is refused with a 422 that says it was removed. The operator sets the level: `wetterdienst restapi --debug`
  starts the server with the debug lines of the package (the downloads, the parsing and the dropped columns of
  every provider) in its log, and an app hosted by another server sets it as for any Python logger,
  `logging.getLogger("wetterdienst").setLevel(logging.DEBUG)`. The loggers of other packages stay as they
  are. `--debug` reaches the worker that `--reload` starts as well. The MCP tools, which are these endpoints,
  refuse `debug` the same way; the command line keeps its own `--debug`.
- **A list is comma-separated**, `stations=01048,04411` and `--stations=01048,04411`, which is how
  the OpenAPI document describes it (`explode: false`). The key given more than once,
  `stations=01048&stations=04411`, is read as the same list, and is not documented. The command line
  takes the last of an option given twice.
- **A boolean is `true`, `1`, `yes`, `on`, `t` or `y`, or one of their opposites**, in any case, on
  every surface; nothing else is one. On the command line a boolean option given without a value is
  on (`--pretty`, `--all`), and `--pretty=false` says it outright.
- **A parameter an endpoint ignores is not a parameter of it.** `stations` takes no `lead_time` and `issue`: the
  stations of a forecast network are the same for every run, which is chosen for `values`, `interpolate` and
  `summarize`. `/api/stations` answers either with a 422 like any parameter it does not know, as
  `wetterdienst stations` and the `stations` tool do.
- **The stations are named by exactly one of** `all`, `stations`, `wmo_id`, `wigos_id`, `icao_id`, `name`, `region`, a point
  (`latitude` and `longitude`, with `rank` or `distance`), a bounding box (`left`, `bottom`, `right` and `top`). None, or two, is refused the same way everywhere, a `missing_one_of` or a `mutually_exclusive`
  error that names the alternatives: `Cannot be combined with name, give exactly one of all,
  stations, wmo_id, wigos_id, icao_id, name, region, (latitude and longitude) or (left, bottom, right and top)` as the answer of a
  422, as the message of a tool error and, in the options' names, as the usage error of the
  command. The OpenAPI document states the alternatives and gives an example of each parameter, see
  [The OpenAPI document](#the-openapi-document).

The following examples use [httpie](https://github.com/httpie/cli) to demonstrate the usage of the REST API.

## Examples

### Providers

The overview: which provider has which network, and what each provider is, for a page that lists them or a client
that has to credit the data. The names it goes by (`name_short` for a chip beside a flag, `name_english`,
`name_local`), the country of the agency that runs it (`country_code` is the ISO 3166-1 alpha-2 code, null for a
provider of several countries; it is the operator's country, not the extent of its data: the `extent` of each network
says where its stations are), the terms it publishes its data under (`license`, as in the `metadata` of a data answer),
the credit line (`attribution`, the credit line to cite; the `copyright` of a network is the rights holder's notice,
shown for information), and its networks. The list downloads nothing and reads no credential, so it answers at once.
Each network has

| Field | |
| --- | --- |
| `network` | its name, `observation` |
| `kind` | what the network is, see below |
| `extent` | where its stations are, see [Extent](#extent) |
| `url` | where the provider publishes the data |
| `copyright` | the rights holder's notice |
| `auth` | whether the network needs credentials |
| `configured` | whether the server has them (true for a network that needs none); whether the provider accepts them is not checked here |
| `date_required` | whether a dataset of the network needs the request to name `start` and `end` |
| `parameters` | how many parameters the network has in all of its datasets |

```bash
# Every provider, sorted by name.
http localhost:7890/api/providers

# One provider.
http localhost:7890/api/providers provider==dwd
```

The command line is `wetterdienst providers [--provider dwd]` and the MCP tool is `providers`. They are the one
overview: `coverage` without a provider and network, which listed every provider and network until 1.0.0, is refused
with an error that names `providers` (a 400 problem, a usage error, a tool error), and `datasets` of `providers`, which
listed the resolutions and datasets of each network, is gone: those are `coverage` of one network, below.

`kind` says which endpoints take the network. A **timeseries network** has stations and values, is
`observation`, `forecast` or `derived`, and is what `stations`, `values`, `history`, `interpolate`,
and `summarize` take, and what `coverage` lists the resolutions, datasets and parameters of. Every network is one
but three. The **standalone networks** are `dwd/radar` (`radar`), `dwd/alerts` (`alerts`) and `dwd/storm_cells`
(`storm_cells`): they have their own request
classes and results in Python, no stations or parameters, and every endpoint above answers a request for them with a
404. A new standalone network gets a `kind` of its own.

A network that cannot be imported on the server, such as one whose package is broken, is not in the
list, nor is a provider none of whose networks can be; the answer says why in its `warnings`. Asking for that network
by name, `coverage` or `auth` with its provider and network, answers a 500, or a 501 where an
optional package is missing, never a 404 as for a network that does not exist.

The list leaves out whether the provider accepts the credentials of a network that has them, because
that is a request to the provider. Ask for one network at a time, which gives up after a few seconds
and answers `valid` as `true` or `false`, or `null` when it could not tell (treat `null` as unknown,
not as rejected):

```bash
http localhost:7890/api/auth provider==aemet network==observation
```

The MCP tool `auth` and the command `wetterdienst auth --provider=aemet --network=observation`
ask the same question and give the same answer.

### Coverage

The detail of one network: its resolutions, their datasets and the parameters of each. `provider` and `network` are
required (a request without them is a 400 that names [`providers`](#providers)); narrow the answer with `resolutions`
and `datasets`. Nothing is downloaded, so it answers at once. The answer is keyed by resolution, then `datasets`, then
each dataset's `parameters`, and every one of those three levels carries a `description` saying what the source
means by it. A standalone network (`dwd/radar`, `dwd/alerts`, `dwd/storm_cells`) has none: a 404.

```bash
http localhost:7890/api/coverage provider==dwd network==observation
http localhost:7890/api/coverage provider==dwd network==observation resolutions==daily datasets==climate_summary
```

Each dataset has its [extent](#extent), and each parameter of a dataset a `unit` and, where it differs, a
`unit_source`, and always an `aggregation` and a `timestamp_position`:

| Field | |
| --- | --- |
| `unit` | the unit the `values` of the parameter come back in when the request gives no `unit_targets` or `convert_units`, which is the unit `glossary` gives for its `unit_type`: `degree_celsius` for a temperature, `percent` for a percentage, `hour` for a duration |
| `unit_source` | the unit the provider publishes the parameter in (`degree_kelvin`, `one_eighth`, `minute`), which the values come in with `convert_units=false`. It is there only where it differs from `unit` (189 of 2132 parameters); absent means the same as `unit` |
| `aggregation` | what the value is relative to its interval: `instant`, `mean`, `max`, `min`, `sum`, `count`, `mean_of_max`, `mean_of_min`, `probability`, `occurrence`, `date`, `change`, `uncertainty`, `code` or `at_max`; the name's where it states a statistic, else the provider's declaration. Always there; `null` means the source does not state it |
| `timestamp_position` | where the timestamp sits in the row's interval: `instant` (when the value was observed), `start`, `end` or `middle`; the parameter's own, else its dataset's (see [Time reference](../data/time_reference.md)). Always there; `null` means the source does not state it |

`coverage` takes no options, so a `unit_targets` or `convert_units` a request to `values` gives changes what
`values` return, not `unit`. The settings of the server (`WD_TS_UNIT_TARGETS`, `WD_TS_CONVERT_UNITS`) are what a
request that gives none gets, and `unit` follows them, as `values` does. Only the Python function
`get_glossary(options=...)` takes `unit_targets`: the `glossary` endpoint, tool and command do not. Up to 0.178.0
`unit` was the unit the provider publishes, which is now `unit_source`.

The OpenAPI document describes the answer as one object keyed by resolution, so a client generated from it has one
type for it.

### Extent

The `country` of a provider is the country of the agency that runs it, which says nothing of where its networks have
stations: DWD is German, and the forecast lists of `dwd/mosmix` and `dwd/dmo` have stations on every continent. The
`extent` of each network says where its stations are, in the answer of `providers`, and `coverage` of one network gives the extent of each of its datasets:

| Member | |
| --- | --- |
| `scope` | `global` (stations on at least five continents), `national` (one country, with its territories) or `regional` (everything between: one or several countries or continents) |
| `continents` | the continents the network is meant to serve, in alphabetical order: `africa`, `antarctica`, `asia`, `europe`, `north_america`, `oceania`, `south_america`. **Descriptive**: declared by hand, a few outlying territories may be named or left out, and the `bbox` and the station lists are the exact answer. A territory is named where the network has stations there: the Canary Islands (`africa`) for AEMET and Madeira (`africa`) for IPMA, Greenland and the Caribbean `north_america`, Guam and Hawaii `oceania`, Turkey `europe` and, east of 34 degrees east, `asia` |
| `country_codes` | only for `regional`, where the list is short and exact: the ISO 3166-1 alpha-2 codes of the countries the network is bound to. **Left out** where there are none, and for `national`: the country of a national network is the `country_code` of its provider (an overseas territory counts for its sovereign: Réunion is `FR`) |
| `bbox` | `[west, south, east, north]` in degrees, a whole degree written without its `.0`, around every station of the network, the Earth for `global`. It does not cross the antimeridian: a network with stations on both sides of it (Alaska and Guam) has the wide box |

The extent is declared once, in the metadata of the network, and the tests hold it to the station list where the list can
be read: every station is in the `bbox`, the `bbox` is no more than 5 degrees wider than the stations on any side, each
continent it names has a station near its box, and a global network has stations on five. That is done for every network
whose list is read without a credential (and for `eaufrance/hubeau` by its referential). **Declared from the provider's
documentation, not read:** `aemet/observation`, `knmi/observation`, `metno/frost` and `metoffice/observation` (a
credential is needed) and `dwd/radar`, `dwd/alerts` and `dwd/storm_cells` (no stations), so their boxes are wider than they need be.

A dataset whose stations are fewer than its network's has an `extent` of its own, which lies within the network's: `dwd/dmo`
is global by its `icon` dataset, whose list has stations on every continent, and its `icon_eu` dataset is regional, the
stations of Europe and the edges of Africa and Asia. `coverage` of a network gives every dataset its extent, its own
or, **for a dataset without one of its own, its network's**. A dataset of a national network
is national. The extent does not change what a request answers: `stations` still
lists what the network has.

### Glossary

Coverage says which parameters a provider offers; the glossary says what any of them means and
which unit it comes back in. Each entry has the `aggregation` its name states (`mean`, `max`, `sum`, ...), `null` for a
plain name; it is the canonical value, and `coverage` has the one of each provider and the `timestamp_position`, which
the glossary does not know.

```bash
# Look up every canonical parameter.
http localhost:7890/api/glossary

# Match names containing some text.
http localhost:7890/api/glossary parameter==radiation

# List every parameter of one quantity.
http localhost:7890/api/glossary unit_type==temperature
```

### Settings

A setting a request to `values`, `interpolate` or `summarize` leaves out takes the server's
`WD_TS_*` variable, where it sets one, else wetterdienst's default. The settings endpoint reports
what each of them takes, keyed by endpoint, with `unit_targets` naming the unit of every quantity.

It takes the settings query parameters of the three endpoints, and answers what they resolve to
over the server's, for each endpoint that takes the parameter: `humanize`, `convert_units` and
`unit_targets` apply to all three, `station_window_end_buffer`, `limits` and the `plausibility_<check>` to `values` alone, and
`min_gain_of_value_pairs` and `num_additional_stations` to `interpolate` and `summarize`. A value an endpoint refuses is refused here the same way, and an
unknown parameter too, so a set of settings can be checked before fetching. Nothing is stored on
the server: the parameters apply to that one answer.

```bash
http localhost:7890/api/settings

# What a values request with a soft range check would get.
http localhost:7890/api/settings plausibility_range==soft

# What a values request with shape=wide would get: the wide shape turns drop_nulls off.
http localhost:7890/api/settings shape==wide

# Check unit targets before fetching; an unknown unit is a 400 naming it.
http localhost:7890/api/settings unit_targets=='{"temperature": "degree_fahrenheit"}'
```

### Stations

```bash
# Acquire list of DWD OBS stations.
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent all==true

# Filter stations by name (fuzzy, case-insensitive).
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent name==Darmstadt

# Filter by name with custom threshold (0–1, default 0.8).
http localhost:7890/api/stations provider==dwd network==observation parameters==daily/kl periods==recent name==Darmstatt name_threshold==0.85

# Acquire list of DWD DMO stations.
http localhost:7890/api/stations provider==dwd network==dmo parameters==hourly/icon/temperature_air_2m all==true
```

### Station ids (a WMO, WIGOS or ICAO id at every provider)

```bash
# The station with WMO number 10381 at every provider that lists it (about 9 s the first time).
http localhost:7890/api/station-ids wmo_id==10381

# An aerodrome by its ICAO code: also the stations that list its WMO number only.
http localhost:7890/api/station-ids icao_id==EDDH

# The identifier of WMO's issuer is the WMO number as well; CSV is the table alone.
http localhost:7890/api/station-ids wigos_id==0-20000-0-10381 format==csv
```

At least one of `wmo_id`, `wigos_id` and `icao_id` is required (each one id or several, comma-separated). The answer is
`{"metadata": ..., "stations": [...]}`, one entry for each station of each network that lists it, with `matched_by` (the
id of the station that matched) and `match` (`direct` or `equivalent`). Its `metadata` block names the `searched`
networks and the lists they were read from, and has the licence and credit line of each provider in `providers` instead of
the one `provider` of the other answers; see [Find a station by id](station_ids.md).

### Issues (available model-run datetimes)

```bash
# List available MOSMIX-L run datetimes for a station.
http localhost:7890/api/issues provider==dwd network==mosmix station==10147

# List available MOSMIX-S or MOSMIX-SNOW run datetimes; one run holds every station, so any station lists them.
http localhost:7890/api/issues provider==dwd network==mosmix station==10147 dataset==small
http localhost:7890/api/issues provider==dwd network==mosmix station==Z914 dataset==snow

# List available DMO ICON run datetimes for a station.
http localhost:7890/api/issues provider==dwd network==dmo station==10147

# List available SWSMOS run datetimes; one run holds every road station, so any station lists them.
http localhost:7890/api/issues provider==dwd network==swsmos station==A006
```

### History

The changes of a station (DWD observation only, see [Station history](station_history.md)):

```bash
http localhost:7890/api/history provider==dwd network==observation parameters==daily/kl stations==1048 sections==name,geography
```

### Alerts

The weather warnings of DWD that are active now, or at a time of the last 48 hours (see
[Alerts](../data/provider/dwd/alerts/index.md)):

```bash
http localhost:7890/api/alerts granularity==district language==de format==geojson
```

Without a place that is every warning of Germany, 100 to 370 KB. `latitude` and `longitude` keep the warnings whose
polygons contain the point, and `name` those with an area of that name or warn cell id; a place without a warning is a
200 with no alerts and a `no-alerts-for-place` warning in `metadata`:

```bash
http localhost:7890/api/alerts latitude==54.32 longitude==10.14
http localhost:7890/api/alerts granularity==district name==Kiel
```

### Storm cells

The thunderstorm cells of DWD (KONRAD3D) of the newest radar scan, or of one of the last 48 hours (see
[Storm cells](../data/provider/dwd/storm_cells/index.md)):

```bash
http localhost:7890/api/storm-cells latitude==52.52 longitude==13.40 distance==25 track==false
```

Without a place that is every cell of Germany, which is none in 8 scans of 10 and hundreds on a day of storms. A point
with a `distance` in km, or a box (`left`, `bottom`, `right`, `top`), keeps the cells whose outline is there, and
`min_severity` the severe ones. An empty answer says which scan it is of (`reference_time`), and a scan that is older than
20 minutes a `scan-stale` warning in `metadata`:

```bash
http localhost:7890/api/storm-cells left==8 bottom==47.5 right==13.8 top==50.6 min_severity==2 geometry==centroid
```

### Precipitation radar

DWD's precipitation radar over Germany as map images, a loop of the last hours and DWD's forecast of the next two (the
RV composite, see [Radar](../data/provider/dwd/radar/index.md#radar-frames-on-the-rest-api)). The list says which
frames there are, where the images lie (`bounds` in WGS84, for a Leaflet `ImageOverlay`; the images are Web Mercator)
and what the colours mean in mm/h; each frame is a PNG, transparent where it is dry:

```bash
http localhost:7890/api/radar/frames
# time and run are those of a frame of /radar/frames (DWD keeps about two days)
http localhost:7890/api/radar/frame time==2026-11-19T21:10:00Z run==2026-11-19T21:10:00Z > frame.png
```

The list is `public, max-age=60` with an `ETag` (no `Cache-Control` where it carries a `radar-stale` warning, DWD's
newest run being more than 20 minutes old). A frame asked for with its `run` is the same for as long as DWD keeps the
run, and is `public, max-age=3600` with an `ETag`; without it, a time after the newest run is a forecast frame of the
newest run, `public, max-age=60`. The forecast of a run is served for the newest three runs DWD lists, and a page should load its frames 4 to 6 at a time (the server holds 32 requests at once by default). Neither route is an MCP tool.

### Kostra

The heavy-rainfall statistics of the DWD (KOSTRA-DWD-2020) of the grid cell that holds a point: the depth in mm, the
intensity in l/(s ha) and the uncertainty in percent of a rain by duration and return period (see
[KOSTRA heavy rainfall](../data/provider/dwd/kostra/index.md)):

```bash
http localhost:7890/api/kostra latitude==52.52 longitude==13.40 duration==60 return_period==100
```

`latitude` and `longitude` are required. `duration` (minutes: 5 to 10080, 22 of them) reads one table of DWD; without
it all 22 are read, 2 s the first time. The answer has the `edition`, the `cell` (`index_rc`, its `row` and `column`
and the `latitude` and `longitude` of its centre) and the `values`, one for each duration and return period.
`format=csv` is the table alone. A point outside Germany and its border of about 10 km, or in a cell DWD gives no
values for, is a 400 and no empty table; a table that does not download or read is a 502.

### Values

`timestamp` covers everything it names: `2020-08-01` is that whole day -- all 24 readings of it for
hourly data -- `2020-08` the month and `2020` the year. An interval runs from the start of the
span its first half names to the end of the span its second, so `2020-08/2020-09` ends with
September. A date carrying a time, `2020-08-01T12`, names that one instant.

The Python API reads `start` and `end` the same way: `end="2020-08-05"` is the whole 5th, as
`timestamp==2020-08-01/2020-08-05` is, `start="2020-08"` and `end="2020-09"` are the months as
`timestamp==2020-08/2020-09` is, and the same inputs give the same window on both. The command line's
`--timestamp` and `--start` / `--end` and the `timestamp` of the MCP tools read them alike.

```bash
# Acquire observations.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl periods==recent stations==1048,4411

# Observations for specific date.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==1048,4411 timestamp==2020-08-01

# Observations for a whole month, since a date covers everything it names.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==1048,4411 timestamp==2020-08

# Observations for date range.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==1048,4411 timestamp==2020-08-01/2020-08-05

# Acquire ICON data (the latest forecast run; a past timestamp has none).
http localhost:7890/api/values provider==dwd network==dmo parameters==hourly/icon/temperature_air_2m stations==01001

# Keep a number the range check finds implausible, flagged `suspect:range`, and null a stuck sensor (`rejected:stuck`).
http localhost:7890/api/values provider==dwd network==observation parameters==hourly/moisture/pressure_air_site stations==01048 timestamp==2024-01 plausibility_range==soft plausibility_stuck==hard

# Every check soft but the range: what the source wrote, flagged, and the range rejected.
http localhost:7890/api/values provider==dwd network==observation parameters==hourly/moisture/pressure_air_site stations==01048 timestamp==2024-01 plausibility==soft plausibility_range==hard

# Null a mean temperature outside -30 to 45 degrees (in the unit of the answer) and a rain above 200 mm.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==01048 timestamp==2024-01 limits=='{"temperature_air_mean_2m": [-30, 45], "precipitation_amount": [null, 200]}'
```

`plausibility=soft` (or `hard`) sets the mode of every check at once, and a `plausibility_<check>` given beside it wins:
`plausibility==soft plausibility_range==hard` is every check soft but the range, and everything a source wrote comes back
flagged.

The plausibility checks `range`, `elevation`, `stuck`, `consistency`, `floor`, `limits`, `source`, `step` and `relations` each take a mode,
`hard` or `soft`, as the query parameters `plausibility_range`, `plausibility_elevation`, `plausibility_stuck`,
`plausibility_consistency`, `plausibility_floor`, `plausibility_limits`, `plausibility_source` (soft by default: the
verdict of the source's own quality flag, such as GHCN-Daily `QFLAG` or DMI `validity:false`), `plausibility_step` (soft by default: a jump between consecutive readings) and `plausibility_relations` (soft by default: two readings of one file that contradict each other, or a day of sunshine longer than the day; not `plausibility_consistency`, which is the hard check of a provider's own rules; the environment variable of a server is
`WD_TS_PLAUSIBILITY__RANGE` and so on). A hard check nulls the value and writes `rejected:<check>,raw:<number>` into
`quality_flags`, a soft check keeps the value and writes `suspect:<check>`; a check not named keeps the server's mode. On a forecast network (`dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`, `dwd/pollen`, `dwd/uvi`: `kind` `forecast`) every check but `floor` and `limits` is soft whatever the mode, so `hard` there flags `suspect:<check>` and nulls nothing (`limits` follows its mode).
See [plausibility checks](../data/plausibility.md). `interpolate` and `summarize` take no mode: they leave out a
suspect value in any case.

The check `limits` judges the bounds you set per parameter, which `limits` of `values` takes as a JSON object of a
parameter to `[low, high]` (`null` for no bound at an end): `{"temperature_air_mean_2m": [-30, 45]}`. A key is a
canonical parameter name, which holds in every dataset that serves it, or `resolution/dataset/parameter`, which holds
in that dataset and wins where both name a parameter. The bounds are in the unit of the values the request returns (its
`unit_targets`, or the source's unit with `convert_units` off); a value outside is null with `rejected:limits,raw:<number>`
by default, or kept and flagged `suspect:limits` with `plausibility_limits=soft`, and a forecast network follows the mode too. A name that is no parameter is a 400 naming it; a pair with `low` above `high`, both ends null, a bound that is not
a finite number and text that is no JSON object are a 422. The `limits` of a request are merged into the server's `WD_TS_LIMITS`, the request's entry winning
for a name both give. `/api/settings` reports them in `values`.

A request that asks for more than the [limits](#limits) allow is refused;
[Getting more than the limit](large-requests.md) shows how to get the data anyway.

## Choose the rows

A long series does not fit an answer: a station's daily minimum is megabytes, a tool's answer is 40,000 characters,
and "the lowest temperature in Hamburg" is one number in them. `filter`, `sort`, `first`, `by` and `max_rows` of
`values` have the server choose the rows instead: it reads the whole series, as the same request without them does, and
sends the rows the options name, with a report of what it looked at. They are the same on the REST API, the MCP
`values` tool, the command line (`--filter`, `--sort`, `--first`, `--by`, `--max-rows`) and in Python
([`values().all(filter=...)`](python-api.md#choose-the-rows)).

| Option | Meaning | Example |
| --- | --- | --- |
| `filter` | the rows that meet every condition (joined by `,`): `column`, an operator and a number; a column is `value`, a calendar part or [a parameter's name](#parameters-as-columns) | `value<=-20,month=12\|1\|2`, `temperature_air_min_2m<0,wind_gust_max>=17.2` |
| `sort` | the order of the answer: columns joined by `,`, `-` before one for descending | `-value`, `month,day`, `temperature_air_min_2m` |
| `first` | the first N rows of each group in the `sort` order; the rows that tie with the last one are kept | `1` |
| `by` | the groups `first` counts in, default the station; `none` is all stations together | `station_id,year` |
| `max_rows` | the most rows of the whole answer, the first of its order: the last step, after the others | `20` |

```bash
# The lowest temperature of a station in the window, and the days it was measured on.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==01975 timestamp==1900/2024 sort==value first==1

# The ten hottest days.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_max_2m stations==01975 timestamp==1900/2024 sort==-value first==10

# The coldest day of every year.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==01975 timestamp==1900/2024 sort==value first==1 by==station_id,year

# The days at or below -20 degrees, latest first.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==01975 timestamp==1900/2024 filter=='value<=-20' sort==-timestamp

# The warmest 24 December of all the stations of a list.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_max_2m stations==03987,01975 timestamp==1900/2024 filter==month=12,day=24 sort==-value first==1 by==none

# The driest day: every day without rain ties at 0.0, so keep the first rows of the tie only.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/precipitation_amount stations==03987 timestamp==1900/2024 sort==value first==1 max_rows==20

# The earliest autumn frost by the calendar, whatever the year.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==03987 timestamp==1900/2024 filter=='value<0,month>=7' sort==month,day first==1 by==none
```

### The grammar

The text of each option is read by a small parser of its own and by nothing else: no regular expression, no `eval`, no
SQL, no function, no nesting, no `or`, and a parameter's name only as a column, looked up among the parameters of the
request and nowhere else. What is not in the table below is not read, and a text
that is not in it is refused. The reading is linear in the length of the text, and every text is bounded.

```text
filter = condition { "," condition }
condition = column operator number | column ("=" | "!=") number { "|" number }
column = a column of the option | the name of a requested parameter (letters, digits, underscore)
operator = "=" | "!=" | "<" | "<=" | ">" | ">="
sort = [ "-" ] column { "," [ "-" ] column }
by = "none" | column { "," column }
first = a whole number from 1 to 10000
max_rows = a whole number from 1 to 10000
```

| Rule | What it says |
| --- | --- |
| Columns | `filter`: `value`, `year`, `month`, `day`, `hour`, or the [name of a requested parameter](#parameters-as-columns). `sort`: those, `timestamp` and `station_id`. `by`: `station_id`, `year`, `month`, `day`, `hour`, or `none` (not `timestamp`: a group of one instant is a row; no name). A word that is none of them is refused with the allowed ones listed, so that columns can be added later. |
| Numbers | `-20`, `0.5`, `1e3`, `2e-3`; no plus sign (a `+` in a URL is a space), no `nan`, `inf`, unit or thousands separator. A calendar column takes a whole number in its range: `month` 1 to 12, `day` 1 to 31, `hour` 0 to 23, `year` 1 to 9999; one outside is refused (`month=0`), not an empty answer. |
| Lists | `month=12\|1\|2` is true for any of them; `month!=12\|1` for none of them. Only with `=` and `!=`; a range is two conditions: `value>=-20,value<=-10`. |
| Spaces and case | Spaces and tabs between tokens are ignored; column names and the `e` of an exponent are read in either case. The text is plain ASCII. |
| Quoting | None is needed, and none is read: `<`, `>` and `\|` are plain characters of the text. A URL may write them as `%3C`, `%3E` and `%7C`; `+` must not stand for a sign. On a shell quote the text: `--filter='value<=-20'`. |
| The same column twice | Allowed: `value>=-20,value<=-10` is a range. Conditions that cannot all be true (`month=12,month=1`) give an empty answer, not an error. |
| Caps | The `filter` text 400 characters, 8 conditions, 32 numbers in a list, 24 characters in a number; `sort` and `by` 100 characters; `first` and `max_rows` 10,000. Each option is given once: a second `filter`, `sort` or `by` in a query is a 422 (join conditions with a comma), and on the command line a usage error. |

An error names the option, the position of the character where the text goes wrong, what is found there and what is
allowed, and says what to write instead. It is a 422 located at the option (the `loc` of the error is the option), a
tool error of the MCP tool, a usage error on the command line and a `RowSelectionError` (a `RequestError`) in Python. A
word that can be a parameter's name passes that reading, and is refused once the request is known, as the same 422 located at the option (see below):

```json
{"type": "urn:wetterdienst:problem:invalid-parameters", "title": "Unprocessable Content", "status": 422,
 "detail": "filter: Invalid `filter` at position 8: no number; found 'n', expected a number such as -20, 0.5 or 1e3. Not numbers: nan, inf, names and units. Write the number alone, in the unit of the values.",
 "instance": "urn:wetterdienst:request:4c334dd0c2c447cfbcdd1ccb366c2b16", "request_id": "4c334dd0c2c447cfbcdd1ccb366c2b16",
 "errors": [{"type": "row_selection", "loc": ["query", "filter"], "input": "value<=nan",
             "msg": "Invalid `filter` at position 8: no number; found 'n', expected a number such as -20, 0.5 or 1e3. Not numbers: nan, inf, names and units. Write the number alone, in the unit of the values."}]}
```

Two rules cross the options: `first` needs `sort` (the first rows of which order?) and `by` needs `first`; each refusal says
which option to add. `top` is not an option: it is the northern edge of a bounding box. `limit` and `offset` are not
options either: the 422 (a tool error, a usage error) says that the most rows of an answer are `max_rows`, and that there
is no paging.

### What the options do

The options act on the values as the answer would have them: after the plausibility checks and the conversion of units
(`value` is in the unit the answer is in, and a value a hard check nulled is null), after the humanizing of the names, and
before the shape, the export formats and the cut of a tool's answer. They act on a station when it has been read, so that
the memory of the server holds the rows chosen and not the series read. The stations read are the ones the selection
names: a `rank` is counted with the stations that returned values, and `skip_empty` skips a station by its coverage, both
before the options choose the rows.

- **Missing values never match.** A null `value` meets no condition, `!=` and `value>=-1000` included, and has no place in
  the order of `first`: it is not counted and not kept. A `sort` alone puts a null last, in either direction.
- **The calendar is UTC.** `year`, `month`, `day` and `hour` are those of the timestamp as the answer gives it, which
  is UTC for every provider. For data of a day or coarser the timestamp is a date and the parts are that date's (`hour` is
  0). No time zone is applied: 23:00 of 31 December UTC is `year=2020`, `hour=23`, whatever the time on the clocks of the
  station. A daily value of a source whose day does not start at 00:00 UTC is the date its timestamp gives.
- **Groups.** `first` counts in groups. A group is one parameter of one dataset and resolution, always, and the columns
  of `by`, which is the station unless it says otherwise: `sort=value&first=1` is the lowest value of each parameter at
  each station, `by=none` the lowest of each parameter over all stations, `by=station_id,year` the lowest of each year at
  each station, `by=year` the lowest of each year over the stations. Parameters are never mixed in a group. With a
  [parameter's name](#parameters-as-columns) a row is a timestamp, and a group is the timestamps of a resolution and the
  columns of `by`.
- **Ties.** A row is kept when fewer than `first` rows of its group sort strictly before it, so every row that ties with
  the last one kept is kept too: `first=1` on a record that three days share is three rows. Two rows tie when all the
  columns of `sort` are equal; add `timestamp` to `sort` to have one.
- **`max_rows`** is the last step, after `filter`, `sort` and `first`: the answer is cut to its first rows, in the order
  it has, over all stations and parameters together. No ties are kept, there is no offset and no page. It cuts what is
  returned and nothing that is counted: `metadata.search` still holds what was searched, expected and matched over
  everything, and `returned` beside `matched`, and a `rows-capped` warning says "20 of 25,311 matched rows are
  returned". With sort it keeps the first of the whole order (the lowest, the highest), without it the first rows as
  they are read (by station, by series, by time). It does not raise what may be read (only `first` and `filter` do,
  below), and what the server holds for it is bounded by it: a station is cut to it as it is read. In the wide shape the
  rows are those of the wide frame, a timestamp of a station and resolution, since that is what `counts.rows` counts
  there. A tool's answer may be cut once more to fit its budget: the note of `answer-truncated` then says how many of
  the rows `max_rows` returned are kept, and how many matched.
- **The order of the answer.** Without `sort` the rows are in the order they are read in: by station, by series, by time
  (with [parameters as columns](#parameters-as-columns): by station, by time, by parameter, so that a cut keeps every
  parameter). With `sort` they are ordered by series (resolution, dataset, parameter), then by the keys, then by station and
  timestamp, which fixes the order whatever order the stations arrived in: ties are ordered by station, then
  timestamp. A null is last.
- **`value` and units.** A condition on `value` has one number for every parameter of the request, so it is refused (a
  400) when the parameters are not in one unit, saying to name one, or to name the parameters as columns, which each
  have their own number. `sort=value` is not refused: a group is one parameter.
- **The wide shape.** `year`, `month`, `day` and `hour` work on its rows (a row is one timestamp of one station and
  resolution, and a group is that resolution of the station), and so do the [names of the parameters](#parameters-as-columns),
  which are its columns. `value` is refused in `filter` and `sort`: a row has one column for each parameter and no
  `value`. Use a name, or `shape=long`. A CSV of the rows chosen by `sort` or `first` is one
  frame that was cut, not streamed station by station, so it has the columns the stations delivered.
- **Every format.** `json`, `geojson`, `csv`, `ndjson` and the charts (where the server [draws them](#charts)) hold the rows chosen. `with_stations` lists the
  stations that have a row left, as it does for any cut of the rows. Forecasts with an issue and `lead_time` are chosen
  among the rows the request reads, as the rows are.

### Parameters as columns

A parameter's name is a column of `filter` and `sort`, for conditions on **two parameters of one station at one
time**: frost with strong gusts, or the wind on the coldest days. A row is then a **timestamp** of a station (and a
resolution), not one reading, and the name stands for that parameter's value at it. "One time" is an equal timestamp, not
an equal interval: within one resolution two parameters meet where their stamps are the same, whatever span each value
covers (a mean over a day and a maximum over the same day meet at the stamp both carry):

Read on 2026-11-25 over the record of Potsdam up to 2024:

```bash
# Frost with strong gusts at Potsdam: 319 days, where the frost alone is 11,578 and the gusts alone 2,368.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m,daily/climate_summary/wind_gust_max stations==03987 timestamp==1850/2024 filter=='temperature_air_min_2m<0,wind_gust_max>=17.2'

# The ten coldest days that have a gust, with the wind of them: 20 rows, 10 days.
http localhost:7890/api/values provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m,daily/climate_summary/wind_gust_max stations==03987 timestamp==1850/2024 filter=='wind_gust_max>=0' sort==temperature_air_min_2m first==10
```

| Rule | What it says |
| --- | --- |
| Names | The name the answer gives the parameter (`parameter` of the long shape, the column of the wide one, after `humanize`), in either case, among the parameters **of the request**: `temperature_air_min_2m`. Letters, digits and underscores only. Anything else is refused with the names the request has and the closest of them: a 422 located at the option, as a text that cannot be read is, but known only once the request is. A bare name can become ambiguous when a dataset gains a parameter of that name: the spelling after the dataset guards against it. A provider's own names with a space or a sign (`humanize=false`) cannot be written: ask for the humanised names. |
| The same name twice | A name two requested datasets share (`temperature_air_2m` in `temperature_air` and `dew_point` of the hourly data) is refused, with the spellings that say which; write it after its dataset, as the wide shape does when datasets of several names are requested: `dew_point_temperature_air_2m`. In a request of one dataset a parameter's own name is the one the answer writes and wins (`water_equivalent_snow_depth` is a parameter of `water_equivalent`, and `snow_depth` after its dataset spells the same). Where no spelling tells a parameter apart (`daily/water_equivalent` with `daily/climate_summary`, which has a `snow_depth` too), the refusal says so: request `water_equivalent` alone for its `snow_depth`. |
| A column of the options | `value`, `year`, `month`, `day`, `hour`, `timestamp` and `station_id` are the columns, never a name, and neither are the reserved words (`window`, `aggregate`, `count`, `min`, ...): each is a 422. No parameter of any provider is called like one (a test holds every provider to it). |
| Conditions | All hold at one timestamp of a station. A name that is missing at a timestamp (a gust not measured that day, a station without the parameter) meets no condition, `!=` included, and a timestamp has no place in the order of a `sort` by a parameter it lacks. Conditions of `year`, `month`, `day` and `hour` mix in: `temperature_air_min_2m<0,month=12\|1\|2`. |
| Numbers | In the unit the answer has for each name, after the conversion of units (`temperature_air_min_2m<32` with `unit_targets` of degrees Fahrenheit), so two names have each their own unit. `coverage` lists the unit of a parameter. |
| `value` | Not beside a name (a 400, as `value` over two units is): `value` is the value of one row of one parameter, a name is the value at a timestamp. Name the parameter instead. |
| One resolution | The request holds parameters of one resolution (a 400 otherwise): the timestamps of an hourly and a daily series are not the same instants. Several datasets of one resolution are fine, as in the wide shape, where they share a row. |
| The answer | The rows of **every requested parameter** at the timestamps chosen, in the order of the plain answer of a station by time and then parameter (not by parameter, so that a cut by `max_rows` or a tool's budget keeps every parameter of the timestamps it keeps) or of `sort` (the keys, station, timestamp, then dataset and parameter). A parameter without a value at a chosen timestamp has no row there (with `drop_nulls=false` a null row): the ten coldest days of Potsdam (1929, 1893, ...) have no gust, so `sort=temperature_air_min_2m&first=10` alone returns their temperatures only; add `filter=wind_gust_max>=0` to ask for days that have both. In the wide shape the answer is the rows of the timestamps. |
| `sort` and `first` | `sort=temperature_air_min_2m&first=10` ranks the **timestamps** of each station by that parameter and keeps the ten lowest with the ties of the tenth (11 at Potsdam, where two days share the tenth value): `first` counts timestamps, never rows, and `by` groups them by the station and the calendar as before. A `sort` by a name and calendar columns together is fine; `value` is not. |
| `max_rows` | Counts rows of the answer, as it always did: `max_rows=10` over three parameters is three timestamps and a row of the fourth. The answer is cut exactly, and so are the rows of a station that `query` yields. The rows `all` holds for a later step are never cut inside a timestamp (their sort value is in one of them), so while it reads it may hold up to the number of parameters less one rows more than `max_rows` for a station. |
| `metadata.search` | Unchanged: a series is a station and a parameter, and `matched` is its rows in the answer. For a parameter that a condition names it is the number of timestamps that held (319 for both at Potsdam), for another it is its rows at those timestamps (fewer if it lacks a value there). `searched` and `expected` are of the whole series, as without names. |
| Limits and streaming | As for the same options without names: a name reads what the request reads, under the same limits, and a `filter` alone still streams station by station, read up to `stream_rows` like the others. A station's timestamps are made one row each for the names the options use only (a join of those parameters on the stamps, never the whole request's width), so the memory of a station is its own frame and a column or two a name. |

An unknown name is refused like this (a 422 located at the option over REST, a tool error, a usage error, `RowSelectionError` in Python):

```text
Invalid `filter` at position 1: `temperature_air_min_2` is not a column of this option; found 'temperature_air_min_2',
expected one of value, year, month, day, hour, or a parameter of this request (temperature_air_min_2m, wind_gust_max).
Did you mean temperature_air_min_2m? Example: filter=value<=-20,month=12|1|2 or temperature_air_min_2m<0.
```

### What was searched

An answer to a request with one of the options has `metadata.search`, so that a reader knows from when to when the
search went and whether it was complete, and says when it was not. It is there when nothing matched too. The `series`
come before the `totals`, and in each series the dates (`first`, `last`) before the counts: **read the dates first**. A
series is searched from its own first value to its last, which is not the period of the station, nor the window: a
station whose catalogue says 1883 may have values from 1999, and the lowest of those is the lowest of those.

This is Hamburg-Kirchwerder (`stations==01979`, `timestamp==1951/2006`, `sort==value`, `first==1`, read on 2026-11-24): the
lowest value is -26.0 on 1956-02-16, found among 16,285 daily values, and 4,169 days of the 20,454 the window covers are
missing, which the answer says:

```json
"search": {
  "options": {"filter": null, "sort": "value", "first": 1, "by": null, "max_rows": null},
  "window": {"start": "1951-01-01T00:00:00.000000+00:00", "end": "2006-12-31T23:59:59.999999+00:00"},
  "series": [{"station_id": "01979", "name": "Hamburg-Kirchwerder", "resolution": "daily",
              "dataset": "climate_summary", "parameter": "temperature_air_min_2m",
              "first": "1951-01-01T00:00:00.000000+00:00", "last": "2006-12-31T00:00:00.000000+00:00",
              "searched": 16285, "expected": 20454, "gaps": 4169, "matched": 1, "returned": 1}],
  "series_omitted": 0,
  "totals": {"stations_read": 1, "stations_with_values": 1, "series": 1, "searched": 16285, "expected": 20454,
             "gaps": 4169, "matched": 1, "returned": 1}
}
```

| Member | What it says |
| --- | --- |
| `options` | the options as they were read (`first` and `by` as given, null for one not given) |
| `window` | the window the request read; where it is null, everything the provider holds for the stations. A provider that needs a window (NOAA GHCN, EA) shows the one that was asked for |
| `series[].name` | the name of the station, null where the provider has none |
| `series[].first`, `last` | the timestamps of the first and the last value searched: the period the series was searched over |
| `series[].searched` | the values searched: readings with a value, after the plausibility checks and the conversion of units, within the window |
| `series[].expected` | the values the request covers, by the step of its resolution (calendar months and years for monthly and annual data). With a `timestamp` window, from its start to its end or to the last complete reading (yesterday for daily data, the previous hour, month or year), whichever is earlier, and never narrower than the values found; without one, from `first` to `last`. `expected` minus `searched` is what is missing from the request. Null where the resolution has no fixed step, for a forecast, and where the series is coarser than its resolution: almost none of its steps is as short as the resolution's (a maximum of the last 12 hours in an hourly dataset has a value every 12 hours: no gap; a series that misses half its hours is not coarser, its gaps count) |
| `series[].gaps` | the values the series lacks between its `first` and its `last`, whatever the window says: the holes inside it. Null for a forecast, for a resolution with no fixed step, where the series is coarser than its resolution, and for a series with no value (its `expected` is then the window, all of it missing) |
| `series[].matched` | the rows the options chose from that station and parameter, before `max_rows` |
| `series[].returned` | the rows of the answer from that station and parameter: `matched`, or fewer where `max_rows` cut the answer |
| `totals` | the same summed over all series (`series` is their number); `expected` and `gaps` are null when one series has none. `matched` and `returned` are the rows of the answer as its frame counts them (in the wide shape a row counts once, not once for each parameter). `stations_read` is how many stations the walk read, those with no value in the window included, and `stations_with_values` how many of them have a value searched: a station whose values are all missing is read and has none (with the nulls kept its series is listed, with 0 searched) |
| `series_omitted` | how many series `totals` counts that `series` does not list: the first 100 are listed |

What `expected` says, by case, with a window of the request:

| Case | `expected` |
| --- | --- |
| the window begins before the data (`1880/2026`, a station that starts in 1936) | counted from the window's start: the years before the station are missing from what was asked for, and `first` says where the data begins |
| the window is a year that is not over (`2026`) | up to yesterday, not to 31 December: the future is not missing |
| the station ended before the window does (`2000/2010`, a station that stops in 2005) | counted to the window's end: the years after the station's last value are missing, and `last` says when it stopped |
| a window of the future (a forecast's) | no past to miss: the span of the values |
| no window | from `first` to `last`: only `gaps` can be missing |

So a window that is wider than the data reads as incomplete on purpose: ask for the window you mean. A provider that
requires a window (GHCN, EA) refuses a request without one; to search the whole record give one that spans it, such as
`timestamp==1883/2026`: an end year in the future is fine.

An extreme can be a faulty reading. The lowest daily flow of the Thames at Kingston is -135 m³/s, flagged
`completeness:Incomplete`, and 826 of its daily values (read on 2026-11-24) are negative: read the `quality_flags` of the rows, ask
`first==3` for the next ones, or filter the sign (`filter=='value>=0'`) where a negative number is not possible. The
options do not judge a reading; they find it.

The warnings of the block stay and say the rest: a file that was skipped (`file-skipped`), a source that fell back to
another (`source-fallback`), values that a hard check nulled (`rejected-by-plausibility`), for an answer that `max_rows` cut `rows-capped`,
and, for a tool's answer, one that was cut to its budget (`answer-truncated`). A station that is read and has no values in the window is not a series. `matched` counts
the rows chosen before `max_rows`; a tool's answer that is cut to its budget keeps the first rows of it and says how many of how many matched.

### Limits and streaming

A request with `first` or a `filter` may read up to the limit of a stream (`stream_rows`, 10,000,000 rows estimated; the
larger of `stream_rows` and `rows` where an answer is one body, 0 for either being no limit), whatever its format, so
that a long record can be searched; the estimate counts rows of the frame, a wide row once. The series is read station
by station and only the rows chosen are kept: the readings that do not match a `filter` are let go as each station is
read. The rows it chooses are held until they are sent, so they are held to the limit of one body (`rows`, 500,000) in
every format (a `filter` alone that is streamed, below, is the exception), and the refusal of a walk that holds more
says "N rows so far", where it stopped and not at the start:

- a choice whose groups stay in a station (the default) is the answer as it is read, and the walk is refused the moment
  it holds more, "N rows so far";
- with `max_rows` and `sort`, every station keeps up to `max_rows` rows and the held rows are cut to the first
  `max_rows` of the answer's order whenever they are twice that, so many stations are no refusal;
- groups that span stations (`by=year`, `by=none`) are chosen again over the rows held when these double what the last
  time left (not before a million cells, or the limit where that is lower), and refused, "N rows so far", if what
  remains is above the limit. A tie over many stations (every dry day is 0.0 mm) is such a group: add `timestamp` to
  `sort` to tell the rows apart, or a calendar column to `by`. A later station can still take rows out of such a group,
  so the refusal is of an answer that would be very large, not a proof that it is;
- the rows are checked once more when the answer is whole, as an answer to be sent.

A `filter` alone, or with a `sort`, is a choice that stays in a station, so the first case holds:
`filter=value>=35&sort=-value` over the 682,507 hourly readings of Hamburg-Fuhlsbüttel reads them all and holds the 30
that match. The refusal of a filter that matches more than `rows` says to tighten it, to add `sort` and `first` (the
first rows of each station), to cut the answer with `max_rows` (a smaller one where it is above `rows`), which keeps
what is held to the rows of the answer (a filter that matches everything is then answered with its first rows, and
`metadata.search` still counts all that matched), to ask for a shorter window, and, over REST for a `filter` alone, to
stream it. A filter that matches everything is refused at the station that makes the rows more than `rows`, the walk
stopped there: it holds `rows` rows and the station in hand, where the plain request holds what it reads (at most
`rows`, by its estimate). A forecast has no estimate, so a `filter` over one is held to `rows` where it was not.

A request with `sort` and neither `first` nor `filter` holds every row it reads, and nothing it holds can be let go, so
it is held to `rows` for what it reads, as it was, and a stream does not help it (the refusal says: add `first` or a
`filter`, or drop `sort`). A request with a `filter` alone that is streamed (`format=ndjson`, `format=csv`) is the other
exception: it sends the rows as they are read and holds none, so it may match as many rows as `stream_rows` allows; add
a `sort` and it is held to `rows` like the body of `json`. `max_rows` alone does not raise what may be read: the request
is read as it was. The number of stations and the timeout hold as they do for every request: a request the timeout ends
is a 504 and its walk stops at the station in hand, the rows it held are freed and its place of the cap is free again
(the rows chosen are not made for nobody). The estimate of rows, and the stations, are those of the request without
options.

`max_rows` stops what a stream sends at the cap and goes on counting: the stations after it are read, and the `end` line
has the counts, the `rows-capped` warning and the whole `search`; a CSV has no place for the warning, and its headers
say what is known before the first row, as for any warning raised later. A `filter` alone is applied to each station as it is read, so `format=ndjson` and `format=csv` stream as before; the
first line of the ndjson has no `search` (the search is not done), and its last line, `end`, has: `{"end": {"counts":
{...}, "warnings": [...], "search": {...}}}`. A CSV carries `X-Wetterdienst-Values-Searched`, `-Values-Expected` and
`-Rows-Matched` in its headers when the rows are chosen before it starts. A `sort` or a `first` needs all the rows to
begin the answer (the order is the whole's, and a group may span stations), so the server reads them all, chooses the
rows and then sends them in the format asked, with the whole `search` in the first ndjson line and in the headers of
a CSV; no chunk goes out before the last station is read, so the timeout holds for the whole read.

### What is not evaluated

Nothing else is: the options are no query language. There is no `or`, no nesting, no function, no arithmetic, no
regular expression, no comparison of two columns, no aggregation (a count, a mean) and no chain of steps: one fixed
order, `filter`, then `sort`, then `first`. `window`, `year_start`, `timezone`, `aggregate`, `having`, `per` and
`max_missing` are reserved names: no option or column will be given them for another meaning. Nothing is kept on the
server between requests.

## Statistics

"How many frost days a year does Potsdam have?" and "which winter was the coldest?" are counts and means over
thousands of values, and the values do not fit an answer. `/api/statistics` has the server count, average, add up or
take the extremes of each station's values per year, month, day or hour, and say per group how many values it rests on.
It is the next step after `stations`, as `values` is, and the same on the REST API, the MCP tool `statistics`, the
command line (`wetterdienst statistics`) and in Python
([`values().statistics(...)`](python-api.md#statistics)). It takes the stations and the `timestamp` of `values` (a
name, ids, a region, a point with `rank` or `distance`, or `all`; not the bounding box and the WMO, WIGOS and ICAO
lists), reads each station as `values` does, and reduces it to its groups before it reads the next: what is held is the
groups, never the readings of a hundred stations. The shape is always long, and the values are in the units of
`values`. A series (a station and a parameter) is never merged with another.

| Option | Meaning | Example |
| --- | --- | --- |
| `aggregate` (required) | what to compute per group: one to five of `count`, `mean`, `sum`, `min`, `max`, `earliest`, `latest` | `count`, `mean,max` |
| `by` | the groups, besides the series: any of `year`, `month`, `day`, `hour` (UTC), each once; none is one group per series | `year`, `year,month`, `month` |
| `filter` | the grammar of [`values`](#the-grammar): `year`, `month`, `day`, `hour` say which values are looked at, `value` which of them count | `value<0`, `month=12\|1\|2,value>=25` |
| `year_start` | the month a `year` begins (1 to 12, default 1); the year is named by the year it ends in | `12` |
| `max_missing` | how many values a group may lack and still be `complete`, with a `mean` and a `sum` (0 to 10,000, default 0); with any aggregate | `40` |
| `having` | keep the groups that meet conditions on the results: the aggregates asked for, `searched`, `expected`, `complete` (1 or 0, or `true`, `yes`, `false`, `no`; the word `complete` alone is `complete=1`) | `count>=100`, `searched<360`, `complete` |
| `sort` | the order of the groups: the aggregates asked for, the columns of `by`, `station_id`, `searched`, `expected`, `complete`; `-` for descending | `-mean`, `count,year`, `-complete,-mean` |
| `first` | the first N groups of the `sort` order, exactly N; needs `sort` | `5` |
| `per` | over what `first` counts: `station` (each series, the default) or `none` (the stations of one parameter together: each group gets its `rank`) | `none` |
| `max_rows` | the most groups of the whole answer, the first of its order, the last step | `20` |

The order is fixed, and nothing is chained: `filter` (the time conditions, then the value conditions), the groups of
`by`, the aggregates, completeness (`max_missing`), `having`, `sort`, `first` (per series, or over the stations with
`per=none`), `max_rows`. The statistics over the groups (`over_groups`) are made before `having`, `sort` and `first`,
so `first=5` still gives the mean of all the years.

**What a group is.** A group is one series and one value of each column of `by`. `by=year` is a group a year;
`by=year,month` a group a month; `by=month` puts every January together (the climate normal); `by=hour` the hours of the
day over all days; without `by` the whole window of a series is one group. The groups are those of the window (without a
`timestamp`, from the first value to the last): a period that has no step inside it, the months of a year that the window
leaves out, is no group. A group that lies wholly before the first or after the last value of a
series is no row, but is counted (`groups_not_listed`); a hole inside the record is a row.

### How complete a group is

Every group says how many values it has (`searched`) and how many it should have (`expected`), and the aggregates
follow these twelve rules, each held by a test that works the case out by hand (`tests/model/test_group_statistics_rules.py`):

1. **Present and missing.** A value is present if it is not null in what `values` returns (after the plausibility checks
   and the conversion of units). A null the source wrote and a reading a check made null are missing, as is a step with
   no row.
2. **Cells.** The cells of a group are the steps of its series' resolution (days for daily, hours for hourly, calendar
   months and years for monthly and annual values) that lie in its period and pass the time conditions of `filter`.
   `expected` is the number of cells, counted by the calendar (a leap day, the length of a month). Steps finer than an
   hour count by the hour: a day of 10-minute values has 144 cells. The steps are those of the clock (a 10-minute
   value is dated 00:10, 00:20), so a window from 00:05 begins at 00:10.
3. **The period of a group.** With `year` in `by`, the calendar year (or the season of `year_start`), **whole**: not cut
   by the window, nor by the start of the record, nor by today. A station that began in March has an incomplete first
   year, a year that is not over is incomplete until it is, and so is the first or the last year or season a `timestamp`
   cuts (`timestamp=1941/1969` with `year_start=12` makes the winter 1970 31 of 90 days: incomplete, and no coldest
   winter). Without `year`, from the start of the window (without one, the
   first value) to its end (without one, the last value), and not past the last complete step (yesterday, the previous
   hour): the future is not missing. A period that has not begun is no group (December of the running year). This is
   not the `expected` of `values`, which stops at yesterday for any window: that is why the running year is incomplete
   here.
4. **Searched.** `searched` is the number of present values among the cells (after the time conditions, before the value
   conditions). More values than cells (a source finer than its resolution) makes `expected` null for that group.
5. **Incomplete.** A group is incomplete if `expected - searched` is more than `max_missing` (default 0). Where `expected`
   is null (a forecast, a resolution with no fixed step, a series whose step is coarser than its resolution) completeness
   is not known: the group counts as complete and `completeness-unknown` says so once per series.
6. **What an incomplete group gets.** Its `mean` and `sum` are null. Its `count`, `min`, `max`, `earliest` and `latest`
   are those of the values there are (a count is a lower bound, an extreme can have been missed), with `searched` and
   `expected` beside them, `complete` false, and always the warning `incomplete-groups`, whatever is asked. An
   incomplete group may compete in `sort` and `first` (`having=complete` keeps the complete ones).
7. **No value, and no match.** A group with no present value has `searched` 0 and every aggregate null, `count` too:
   nothing was looked at, it is not 0 frost days. A group with values and none that meets the value conditions has a
   `count` of 0 and a `sum` of 0 (a sum of nothing: the Hellmann number of a winter without frost is 0), and a null
   `mean`, `min`, `max`, `first` and `last`. So the tropical nights of 1961 to 1990 average 0.2333 a year over 30
   years, not 1.1667 over the 6 years that had one.
8. **Which groups are rows.** Every group of the window is a group. Those with no present value that lie wholly before
   the series' first value or after its last are not rows (counted in `groups` and `groups_not_listed`, with the warning
   `no-values-in-groups`); a group inside the record with no value is a row.
9. **The statistics over the groups.** `over_groups.<aggregate>` has `groups` (all of the series, rows or not),
   `usable` (the complete groups with a value) and the `min`, `max` and `mean` over the usable ones: the mean of the
   yearly frost days is over complete years, and a running year's lower bound does not move it.
10. **`max_missing`.** `max_missing=40` accepts a year with 328 of 365 days as complete: it then has its `mean` and
    `sum`, with `searched` and `expected` shown beside it. It counts for every aggregate, since it decides `complete`.
    **Keep it 0 to rank**; raise it only for a gap you accept. A group that `max_missing` lets in with values lacking,
    or a year that is not over, is `complete: true` (the flag says that no more than `max_missing` values lack, not
    that none does) and competes in `sort` and `first` with its `mean` of the values there are; the warning
    `gaps-allowed` counts such groups of the answer and what they lack, and is not told where none is in it. A model
    that sets `max_missing=400` out of habit ranks half-years with whole ones: read `searched` and `expected`. For `count`,
    `min`, `max`, `earliest` and `latest`, `max_missing` changes only `complete`: to rank only groups that have every value
    use `having=complete` with `max_missing` 0.
11. **`year_start` and `year`.** `year` means the year a season ends in, in `by`, `filter` and `sort`: with
    `year_start=12` the winter 2023/24 is 2024 and `filter=year=2024` selects December 2023 to November 2024. A season
    the record or the window covers only in part is incomplete by rule 3.
12. **Sub-daily data and forecasts.** The calendar parts are UTC, as in `filter` of `values`: 24 cells a day for hourly
    data, 144 for 10-minute data, and no daylight saving. A forecast has no `expected` (rule 5).

### Which aggregate for which parameter

It follows the parameter's own metadata (`unit_type` and `aggregation` of the parameter table, those `glossary` and
`coverage` show), and a request the parameter does not allow is a 400 that names the aggregates it does, before any
station is read, whether or not a station has rows.

| Aggregate | Allowed | Refused |
| --- | --- | --- |
| `count`, `earliest`, `latest` | every parameter | none |
| `min`, `max` | every parameter with a magnitude (a zenith angle has one) | directions, weather codes and other codes |
| `mean` | the same, and not estimates of an error | the same |
| `sum` | amounts, durations, energies and counts; a temperature **daily or hourly**, as degree days (`°Cd`) or degree hours (`°Ch`: the Hellmann number, heating degree days) | pressure, humidity, wind speed, cloud cover, probabilities, dates; a total over a window of its own whose rows overlap (`precipitation_amount_last_3h` of hourly values, `_multiday`, `_since_last_routine_report`; `_last_1h` of hourly values is each hour once and is allowed); a temperature at any other resolution |

A column finer than the resolution is refused too (`by=hour` of daily values, a `month` condition of annual ones), and
`year_start` of annual values, which have no seasons. The mean over monthly or yearly values is unweighted: the mean of
twelve monthly means is not the mean of the days. The `min_at`, `max_at` of an extreme is the timestamp of the row that
holds it, the earliest on a tie; `earliest_at` and `latest_at` are the timestamps of the first and the last value that
meets the conditions. A date is written in the shortest ISO form of the series: `2007-03-24` for daily and coarser
values, `2026-11-23T13:00Z` for finer ones. A `value` condition is in the unit of the values and, over parameters of
two units, refused with the hint to name one parameter. The name of the request's one parameter is `value` too
(`filter=temperature_air_min_2m<0` with that parameter alone); with several, a name is no column. `sum` and `mean` are
rounded to 6 decimals where they are made, so that two sums that differ in the last bit of a float tie; `min`, `max`,
`earliest` and `latest` are readings and are not rounded.

**Ties.** `first=N` keeps exactly N groups, which a count needs (most years have 0 days of a frost below -15
degrees, and tie): the ties are ordered by the columns of `by` and then by station, and the warning `ties-not-shown` says
how many more tie with the last group shown. In `values` the ties of the last row are kept.

**Ranking over the stations.** With `per=none` the groups of one parameter compete across the stations, and each
group has its `rank` (1 is the best, in front of the columns of `by`; groups that tie have distinct ranks, in the order
of `by` and then of the station, so the rank is a place in the list and not a competition rank). The series are listed in
the order of their best group; a series that kept no group is not listed (`metadata.search.totals.series` counts all of them), and `max_rows` and
the cut of a tool keep the groups of the first ranks.

### The answer

One object per series; everything that is true of a series is in it.

```json
{"metadata": {"...": "the block of every answer, with search.options, search.window and search.totals",
              "warnings": []},
 "series": [{"station_id": "03987", "name": "Potsdam", "resolution": "daily", "dataset": "climate_summary",
             "parameter": "temperature_air_min_2m", "unit": "°C",
             "first_timestamp": "1961-01-01", "last_timestamp": "1990-12-31", "searched": 10957, "expected": 10957,
             "gaps": 0,
             "over_groups": {"count": {"groups": 30, "usable": 30, "min": 52.0, "max": 123.0, "mean": 89.4}},
             "groups": [{"year": 1961, "count": 70, "searched": 365, "expected": 365, "complete": true},
                        {"year": 1962, "count": 100, "searched": 365, "expected": 365, "complete": true}]}]}
```

(`filter=value<0&aggregate=count&by=year&timestamp=1961/1990`: `over_groups.count.mean` is the 89.4 frost days a year of
the normal period, equal to DWD's own `count_days_frost`.) The members of `series` are the report of the series as
[`metadata.search.series`](#what-was-searched) of `values` has it (`first_timestamp`, `last_timestamp`, `searched`,
`expected`, `gaps`), then the statistics over its groups, then its groups, which are in `series[].groups`: the `rank`
(`per=none`), the columns of `by`, each aggregate (with `min_at`, `max_at`, `earliest_at`, `latest_at` for the four that
have a date), `searched`, `expected` and `complete`; with `year_start` a group's `year` is the year its season ends in. A
`sum` of temperatures says `°Cd` or `°Ch` in the series' `units`. `metadata.search` has the options as read (with their
defaults), the `window` and the `totals`: `stations_read`, `stations_with_values`, `series`, `searched`, `expected`,
`gaps`, and the groups: `groups`, `groups_not_listed`, `groups_incomplete`, `groups_matched` (after `having`) and
`groups_returned`; `stations_read` counts the stations the walk read, those with no value included.

`format=csv` is one row per group with the identity of its series in front (`station_id`, `resolution`, `dataset`,
`parameter`, the `rank`, the columns of `by`, the aggregates and their dates, `searched`, `expected`, `complete`), and
the block in the headers; `format=ndjson` is the block, a line for each group, and an `end` line with the counts, the
warnings and the series without their groups. Both are one body and are not streamed.

| Warning | Meaning |
| --- | --- |
| `incomplete-groups` | how many groups have fewer values than expected, by station, whatever is asked, and how many of them are in the answer: `complete` is false, and their `mean` and `sum` are null |
| `no-values-in-groups` | how many groups lie before the first or after the last value and are not listed |
| `gaps-allowed` | how many groups of the answer lack values and are `complete` only because `max_missing` allows it, the most one lacks and what all lack; not told where there is none |
| `completeness-unknown` | for how many series how many values a group should have is not known |
| `ties-not-shown` | how many more groups tie with the last one `first` shows |
| `rows-capped` | `max_rows` cut the answer: how many of how many groups are returned |
| `answer-truncated` | a tool's answer was cut to the budget (below) |

**The MCP tool** is `statistics`. Its answer is cut to 40,000 characters as `values` is, by dropping groups from the
end in the answer's order (by rank with `per=none`), and says so: "the first 279 of 1,607 groups are returned, in the
answer's order; `metadata.search.totals` and `over_groups` cover all of them. Narrow with `having`, `first` or `filter`."
A tool lists at most 20 series that have a group, and says so in its own note, which is no cut to the budget: the first 20
in the order the stations were read, or with `per=none` those with the best groups over all parameters. The totals count
all, with `groups_returned` the groups shown, and the warning `incomplete-groups` says how many of its groups are in the
answer. REST, the command line and Python are never cut.

**Limits.** The stations and the readings read are held to the limits of `values` as a request with `first` is, but
under `stream_rows` alone (`values` takes the larger of it and `rows`), whatever the format. A request of more than 100
series (stations times parameters) is refused before a
station is read (`series`): "This request has 240 series, more than the 100 an answer reports: name fewer stations or
parameters, or ask in several requests." The groups held, as the stations are read, and the groups of an answer are held
to `max_groups` of the [limits](#limits), 50,000 by default (`WD_RESTAPI_MAX_GROUPS`; a group is about 150 bytes of
JSON): "683,736 groups so far, more than the 50,000 that may be held. Drop a column of `by`, or add `having` or
`first`." A window of more than 1.5 million steps of a resolution (170 years of hours) is refused. The timeout ends the
walk between two stations. A text that cannot be read is a 422 located at the option, a request that is well written
and cannot be applied to a series (a sum of a pressure, `by=hour` of daily values) a 400.

**For later, and kept free.** `longest_run`, `window`, percentiles, `by=decade`, `by=season` and `timezone` are not
options yet and their names are reserved: no column, option or parameter is given another meaning.

### Examples

Ten questions on Potsdam (03987) and DWD's `daily/climate_summary`, each held to the truth worked out a second way
(plain Python over the rows, or DWD's own annual datasets):

```bash
# 1. Frost days per year, and their mean over the years under over_groups: 133 years, equal to DWD's count_days_frost.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==03987 timestamp==1893/2024 filter=='value<0' aggregate==count by==year

# 2. Tropical nights 1961 to 1990: 0.2333 a year (24 of the 30 years have none, which count).
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==03987 timestamp==1961/1990 filter=='value>=20' aggregate==count by==year

# 3. The coldest winters (December to February, a year ends in November): 1940, 1963, 1947.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_mean_2m stations==03987 timestamp==1893/2024 filter=='month=12|1|2' year_start==12 aggregate==mean by==year sort==mean first==3

# 4. The five warmest years: 2024, 2019, 2018, 2023 and 2020 (a year that is not over, such as 2026 now, has no mean).
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_mean_2m stations==03987 timestamp==1893/2024 aggregate==mean by==year sort==-mean first==5

# 5. The Hellmann number of the coldest winters, in degree days.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_mean_2m stations==03987 timestamp==1893/2024 filter=='value<0,month=11|12|1|2|3' year_start==11 aggregate==sum by==year sort==sum first==3

# 6. The statistics of 24 December.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_max_2m stations==03987 timestamp==1893/2024 filter=='month=12,day=24' aggregate==count,min,max,mean

# 7. The wettest months ever: July 1907, July 2011, August 2002.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/precipitation_amount stations==03987 timestamp==1893/2024 aggregate==sum by==year,month sort==-sum first==3

# 8. Summer days per year: 133 years, equal to DWD's count_days_summer.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_max_2m stations==03987 timestamp==1893/2024 filter=='value>=25' aggregate==count by==year

# 9. The first frost of each autumn season (July to June).
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==03987 timestamp==1893/2024 filter=='value<0' year_start==7 aggregate==earliest by==year

# 10. How complete is a station: Hamburg-Kirchwerder lacks 4,169 days, in 13 years (1976 to 1988), whose mean is null.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==01979 timestamp==1951/2006 aggregate==count,mean by==year having=='searched<360'

# The same station with a gap of 40 days allowed: 1976 (31 days short) has a mean now, 1988 (121 short) has none, and
# the warning `gaps-allowed` says which group `max_missing` let in. Keep it 0 to rank.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_min_2m stations==01979 timestamp==1951/2006 aggregate==count,mean by==year having=='searched<360' max_missing==40

# The three warmest years of all the stations of a list together (per=none), each with its rank, as CSV.
http localhost:7890/api/statistics provider==dwd network==observation parameters==daily/climate_summary/temperature_air_mean_2m stations==03987,01975 timestamp==1893/2024 aggregate==mean by==year sort==-mean first==3 per==none format==csv
```

## SQL filters

`sql` and `sql_values` were removed from the REST API and the MCP tools (GHSA-332g-7w2w-4w59): they ran a
caller's text in DuckDB on the server. A request that sends one is a 422 that says so and what to do. On `stations`
and `values` select the stations with the filters of the route (`stations`, `name`, `wmo_id`, `wigos_id`,
`icao_id`, a point with `rank` or `distance`, a bounding box), and on `values` choose the rows with
[`filter`, `sort`, `first` and `by`](#choose-the-rows), or filter the answer yourself; on `values` the rows
of `format=json`, `csv` or `ndjson` are yours to filter, on `interpolate` and `summarize` those of `json` or `csv`.
A route that never took `sql` or `sql_values` (`history`, `glossary`, ...) answers them as it does any parameter
it does not know. The same holds in each MCP tool.

The setting `restapi_sql` (`WD_RESTAPI_SQL`) is removed with them, and `Settings(restapi_sql=...)` in code is
refused. A server that finds `WD_RESTAPI_SQL` set to a true value, in its environment or in `.env`, warns once as
it starts, naming the variable, and runs without SQL: the readiness probe is not affected and nothing is enabled.
Set to `false` or to nothing it is left alone, so a deployment that spelled the default out starts as before. Remove
the variable.

The command line (`--sql`, `--sql-values`) and the library (`filter_by_sql`, `filtered_by_sql`) keep their SQL
filters: there the caller is the host's own user, who could run the SQL on their own DuckDB. See
[Python API](python-api.md#sql). They need DuckDB 1.5.3 or newer (`pip install --upgrade "duckdb>=1.5.3"`); an
older one is refused with an error that says so. These restrictions are defence in depth, not a sandbox: never pass text from someone you do not trust to the filter. The time a condition runs, memory outside DuckDB's limit and the process itself are not protected.

## Charts

A server draws no charts until its operator says so: `WD_RESTAPI_PLOTTING` (`restapi_plotting`) is off by default. A
request for a chart format of `stations`, `values`, `interpolate` or `summarize` (`format=html`, `png`, `jpg`,
`svg` or `pdf`, under `/api` and `/api/v1`) is then refused with a 403 problem of the kind `charts-disabled`, before
anything is read: no station is looked up, nothing is downloaded and no plotting library is loaded. `detail` names the
formats the route answers and says that the operator can switch charts on, and the `errors` entry for `format` has
them in `ctx.formats`. The answer carries `Cache-Control: no-store`, since the operator may switch charts on without a
restart: the variable (or `.env`) is read for every request. A client can check first: `plotting` of
`GET /api/version` (`/api/v1/version`) is `false` for a server that refuses charts, read the same way.

```json
{
  "type": "urn:wetterdienst:problem:charts-disabled",
  "title": "Forbidden",
  "status": 403,
  "detail": "This server draws no charts, so format=png is refused. It answers json, geojson, csv or ndjson. Ask for one of these, or ask whoever runs this instance to switch charts on (WD_RESTAPI_PLOTTING=true).",
  "instance": "urn:wetterdienst:request:4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "request_id": "4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "errors": [
    {"type": "charts_disabled", "loc": ["query", "format"], "input": "png", "ctx": {"formats": ["json", "geojson", "csv", "ndjson"]}, "msg": "..."}
  ]
}
```

Only the chart formats are refused. A request that is also malformed is the 422 first, as ever (a parameter that is
unknown, a `width` that is not positive, a `format` that is none: `PNG` is no format, a row option of
`values` given twice); a chart that is too large, or for
a network that is not served, is told that charts are off, not to lower the `scale` or that the network is unknown. The
`width`, `height` and `scale` of a request in a data format are ignored, as they were. The OpenAPI document is the same
for every server: `format` keeps its chart values, and its description says that a chart needs the setting.

A chart is drawn by vl-convert in the process of the server, one at a time, and a server that draws charts spends
time and memory on them, which is why a public server keeps them off. Measured (2026-11-26): vl-convert 2 draws in a
worker thread of its own and does not hold the interpreter, so the server goes on answering while a chart renders. On
a real `uvicorn` with one worker `/health` was answered in a median 1 ms during renders of a month of values, of the
station map and of a chart of 100,000 points, and waited at most 0.1 s with one chart of 100,000 points rendering, 0.5 s
with four and 1.2 s with sixteen. The charts render one after another in that one worker, so a chart waits for those
before it: about 0.3 s for a month of values, 1.5 s for the station map and 11 s for a chart of 100,000 points (1.3 GB).
Sixteen of the last took more than the default [request timeout](#timeout) of 60 seconds, which answered 11 of them
`504`. A station map made some requests wait up to 0.6 s (four at once) and 3 s (sixteen), which was not traced to a
cause. See [Image size](#image-size) for the limits. With `WD_RESTAPI_PLOTTING=true` the answers are what they were.
The library, the command line (`--format=png`) and the web app, which draws its own charts in the browser, are not
affected, and the MCP tools offer no chart. The index page and the web app link to none.

```shell
WD_RESTAPI_PLOTTING=true wetterdienst restapi --listen 0.0.0.0:7890
docker run --env WD_RESTAPI_PLOTTING=true --publish=7890:7890 ghcr.io/earthobservations/wetterdienst wetterdienst restapi --listen 0.0.0.0:7890
```

## Image size

Where the server [draws charts](#charts), a chart in an image format (`png`, `jpg`, `svg`, `pdf`) is refused with a 400
when a side of the image is longer than 8192 px, `scale` applied. A chart of several parameters is 300 px tall for each,
and is measured as drawn. The limit holds for the REST API; the library and the CLI have none (the MCP tools draw no
chart).

A chart is drawn to an image by vl-convert, in the process of the server: there is no browser to start. The image is
exactly as large as `width` and `height` say, `scale` times as large: a request for 700 x 500 px is an image of
700 x 500 px. A normal image takes 0.1 to 1 second, but the time and the memory grow with the points the chart draws:
a chart of 100,000 points took 11 s and 1.3 GB here, and the one after it waits for it. Hence a chart of more than
100,000 points, an image or the page (`format=html` embeds every point), is refused with a 400 of the kind
`limit-exceeded` (`limit` is `image_points`) once the data is read and before anything is drawn; `detail` says to ask
for fewer stations or parameters, or a shorter `timestamp` window. The Python API and the command line have none: they
draw what they are given, as many rows as there are.

## Limits

A request whose estimate is more than the server allows (what it would return, or for a `filter` or `first` what it
would read) is refused with a 400 before anything is downloaded, as a problem of the kind `limit-exceeded`. A `filter`
or `first` that then holds more than `rows` is refused as the stations are read, as the same problem with "N rows so
far" in its `detail`. It names the limit, its value and what the request comes to (`limit`, `maximum`, `requested`), and
`detail` says how to narrow it:

```json
{
  "type": "urn:wetterdienst:problem:limit-exceeded",
  "title": "Bad Request",
  "status": 400,
  "detail": "This request reads 1284 stations, more than the 100 this server allows for one request. Name fewer stations, or narrow the selection: a smaller `rank`, a smaller `distance` or bounding box. Request the rest in further calls.",
  "instance": "urn:wetterdienst:request:4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "request_id": "4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "limit": "stations",
  "maximum": 100,
  "requested": 1284
}
```

| `limit` | Setting | Default | What it bounds |
| --- | --- | --- | --- |
| `stations` | `WD_RESTAPI_MAX_STATIONS` | 100 | the stations one `values` or `history` request reads; a `rank` counts as that many. For `interpolate` and `summarize`, the stations with a record in the window within the widest radius of the request, which it reads outwards from the point (the radius is bounded as well, see [Interpolation](interpolation.md#rest-api)) |
| `rows` | `WD_RESTAPI_MAX_ROWS` | 500,000 | the rows of an answer sent as one body: `json`, `geojson`, a chart, and the answer of `interpolate`, `summarize` and the listing of `stations`; also the rows a `filter` or `first` of `values` holds |
| `stream_rows` | `WD_RESTAPI_MAX_STREAM_ROWS` | 10,000,000 | the rows of a streamed answer, `format=ndjson` and `format=csv` of `stations` and `values`; what a `filter` or `first` of `values` reads, where it is the larger of this and `rows` |
| `groups` | `WD_RESTAPI_MAX_GROUPS` | 50,000 | the groups of an answer of [`statistics`](#statistics) |
| `series` | none (100) | 100 | the series (stations times parameters) of a `statistics` request, which an answer lists |
| `image_points` | none | 100,000 | the points of a chart, an image (`png`, `jpg`, `svg`, `pdf`) or the page (`format=html`, which embeds them), counted from the rows the chart is drawn from once the data is read. A fixed limit, see [Image size](#image-size) |

The host sets them with the settings of the same names (`restapi_max_stations`, ...; see [Settings](settings.md)),
and `0` switches a limit off. They hold for the REST API and the MCP tools; the library and the command line have
none. The default of 100 stations is the number `request.stations.ids` of the `metadata` block lists.
`GET /api/version` reports the values of the instance as `limits` (`max_stations`, `max_rows`, `max_stream_rows`, `max_groups`,
the `timeout` in seconds and `max_concurrent`), so a client can size its requests before one is refused.

The stations are counted from the selection, which the server holds already. The rows of `values` are an
estimate, and an upper bound: for each station the readings its resolution can hold between the start and the end
of its record, within the `timestamp` of the request, times the parameters asked for (once for each timestamp in the
wide `shape`). Where the provider reads per period (DWD does), `periods=recent` narrows it to what that release
holds, counted as the last two years, rather than the whole record of the station; a dataset whose recent release
reaches back further (the 1 and 5 minute data, the annual data) is counted from further back, and one with no
release of its own (the hourly and daily solar data, the hourly urban data) or one that holds years (the monthly
derived data, the phenology) is counted from its record. A request for `now` alone is counted as the last four days
(10 minute data) or five days (1 and 5 minute data), over the day or two that DWD's `now` files hold.
A station whose record is not published is counted from an assumed start, so that a request without a
`timestamp` is held to the limit as well. That concerns the datasets that need no date and whose station list publishes
no record (the phenology of DWD is one; a network that requires a date has the window of the request). The start is
assumed from the periods of the dataset: 1 January 1950 for one with historical data (or one whose recent data
reaches back years, as the phenology's does), which is before the oldest archive of this kind that the library reads
(IMGW's begins in 1951), two years before the end for recent data and two days for current data. A forecast has no
record to assume and is not counted: its answer is bounded by the horizon of the model. `drop_nulls` or a station
with less data than its record makes the answer smaller. For `interpolate` and
`summarize` it is the readings of the window for each parameter. So the time span of a request is bounded through
the rows: a year of 1-minute readings of one parameter is 525,600 of them, a century of daily ones 36,500.

An answer over `rows` that fits `stream_rows` is told to use `format=ndjson` or `format=csv`; a request that chooses its
rows (`filter`, `first`) reads more than it sends and is told a narrower request. What to do about a
refusal, in the order to try it (a narrower request, a stream, slices, the library, a server of your own), is on
[Getting more than the limit](large-requests.md).

## Streaming

`stations` and `values` answer `format=ndjson` and `format=csv` as the answer is built, station by station,
instead of holding it: the memory of the server does not grow with the answer, and the client reads the first
rows while the later stations are still downloaded. `json` and `geojson` are one body, as before.

```bash
http --stream localhost:7890/api/values provider==dwd network==observation parameters==daily/kl stations==1048,4411 timestamp==2020 format==ndjson
```

Which of the two formats to take, and how to read a stream in Python, with polars or into a file with `curl`, is on
[Getting more than the limit](large-requests.md#stream-it).

**NDJSON** (`application/x-ndjson`) is one JSON object on a line, UTF-8:

1. `{"metadata": {...}}`: the `metadata` block (with `with_metadata`, the `settings` beside it in the same line).
   It is the block as known before the first reading: `counts.stations` is the stations selected (at most `rank`
   of them), `counts.rows` is 0, and `warnings` are those raised so far.
2. One line for each row: an item of the `values` (or `stations`) of the JSON answer.
3. `{"end": {"counts": {"stations": n, "rows": n}, "warnings": [...]}}`: what was sent, and every warning, those of
   the stations read after the first line too.

A stream without its `end` line was cut short. A failure after the response began cannot change its status
(the first station is read before, so a failure on it still has its own status); it is the last line instead,
`{"error": {<problem>}}`, the problem as an error would have been answered, with no `end`. `metadata`, `end` and
`error` are the keys of the lines that are not rows. The command line writes the same lines
(`wetterdienst values --format=ndjson`), all at once.

**CSV** is the CSV of the answer, with the header row once, sent in chunks. A CSV has no place for the block, so
it is in the headers: `X-Wetterdienst-API-Version`, `-Schema-Version`, `-Retrieved-At`, `-Provider`, `-License`,
`-Attribution`, `-Stations` (the stations selected), and `Link: <licence>; rel="license"`. They go out before the
first row, so `X-Wetterdienst-Rows` is left out, and `X-Wetterdienst-Warnings` has only what was raised by then. A
failure after the response began cuts the connection, as CSV cannot say it; the server logs it.

A streamed wide CSV (`shape=wide`) has every column of the request: the header is written with the first station, so
it is the columns of the requested parameters, in the order of the request, and a station that lacks a parameter has
it empty. A parameter that only a later station has is not lost. The CSV of the same request that is not streamed
(the command line, an MCP tool, `to_csv` of the result) has the columns of what the stations delivered, so the two
differ by the columns of parameters no station delivered, and by their order where the first station lacks a parameter. A request
for a dataset has the columns of all its parameters, so a dataset that each station has few of (NOAA GHCN's
`daily/data` has 210 parameters, 420 columns) has many empty columns: name the parameters you want. The NDJSON lines
are as before.

`ndjson` refuses `with_stations` (a 400): it lists the stations of the whole answer, which a stream never holds.

## Caching

Six routes say how long an answer may be reused and how to ask whether it changed: the catalogue (`coverage`,
`providers`, `glossary`), `history` and the radar (`radar/frames`, `radar/frame`). Every other route sends no `Cache-Control`, `ETag` or `Last-Modified`, and
an error never does, so a browser, a proxy or a library keeps none of them: that is a decision for each route,
and where an answer cannot be reasoned about it stays out.

| Route | `Cache-Control` | `ETag` | `Last-Modified` | Why |
| --- | --- | --- | --- | --- |
| `coverage`, `providers`, `glossary` | `public, max-age=300` | yes | yes | Read nothing from a provider: they change with a release, or with the server's settings. A deploy that changes one is seen after five minutes at the latest. |
| `history` | `public, max-age=3600` | yes | no | Changes when the source does (a new sensor, a move), rarely, and the server itself reads its files at most every twelve hours (`CacheExpiry.METAINDEX`). The source says no time it changed, so there is no date to send. Only an answer with rows and no `warnings` is kept: an empty one, or one that left ids out, may be a source that answered nothing for the moment, and carries no cache header. A `dwd/observation` history that met a directory whose listing came back empty or missing, or that lists no description of its stations, in the lookup of its stations or in the history itself, is a `file-skipped` warning on a 200, so that answer is not kept and carries no `ETag`; the empty or missing listing, and the listing of a directory with no description, is not kept in the listing cache either, so the next request lists the directory again (a listing with files is kept for twelve hours; nginx lists an empty directory as itself, which `list_remote_files_fsspec` turns into no file, and no empty listing is kept, a subdirectory's included); a station that has no file in a listing that is there is the source's answer and no warning. A listing that is cut short but not empty cannot be told from a whole one. |
| `radar/frames` | `public, max-age=60` | yes | no | The server holds DWD's list of runs for a minute, and a run comes every 5 minutes. An answer with a `radar-stale` warning is not kept. |
| `radar/frame` | `public, max-age=3600` with a `run`, `public, max-age=60` without | yes | no | The frame of a run never changes while DWD keeps it (about 48 hours). Without a `run` a forecast frame is that of the newest run, which changes every 5 minutes. |
| `stations`, `issues` | none | no | no | A list changes with the provider's catalogue, which the server is not told about. |
| `values`, `interpolate`, `summarize` | none | no | no | A window in the past is not stable by itself: a provider revises data (the DWD `recent` readings are checked and moved to `historical`, others publish corrections), and an estimate is made from them. |
| `ndjson` and `csv` of `stations` and `values` | none | no | no | Streamed station by station, before the answer is known: there is no body to tag when the headers go out. |
| `alerts`, `storm-cells`, `auth`, `version`, `settings` | none | no | no | Alerts and storm cells are live, `auth` probes a provider, and the last two describe the instance. |
| `station-ids` | none | no | no | The lists it reads are cached by the server, but the answer is a search over the networks that declare id columns and is not tagged. |
| `kostra` | none | no | no | DWD's tables are static (December 2022) and the server keeps them in its own cache for a week, but the answer is not tagged: no route is cached by a client without a decision of its own. |
| `/health`, `/ready` | `no-store` (`/ready`) | no | no | A probe is asked every time. |

**The `ETag`** is a weak tag (`W/"..."`) of the body of the answer without the one thing that differs between two
answers to the same question, when it was made: `metadata.retrieved_at`. It is weak because that is what it says: two
bodies that mean the same and are not the same bytes. It covers everything else in the body, including the whole
`metadata` block (licence, attribution, counts, warnings), so an answer that changes in any other way has another
tag. The format and every option are parameters of the query, so a request with another one is another URL with
another tag: the tag of `pretty=false` does not answer `pretty=true`. None of these routes reads another header of the
request, `Accept` included, so the answers have no `Vary`.

**A `304`** answers a `GET` whose `If-None-Match` lists the tag (a list, a strong form of the same value and `*` match
too), or, where there is none, whose `If-Modified-Since` is not before `Last-Modified`. It has no body and carries
`ETag`, `Cache-Control` and `Last-Modified` as the 200 does. It means that **the copy the client holds differs from a
fresh answer at most in its `retrieved_at`**, which is when that copy was made; the `Date` of the 304 is when it was
found to be right. The `X-Wetterdienst-*` headers are not sent again with it, so a cache that updates what it holds
from a 304 keeps the `X-Wetterdienst-Retrieved-At` that matches the body it holds. A client that must have a fresh
`retrieved_at` does not send a condition.

**`Last-Modified`** of the catalogue is when the server last changed: the start of its process, or the change of its
`.env` where that is later (the settings of a request are read from it each time). It only moves forward: an `.env` that
is edited, replaced by an older file or removed moves it on by at least a second, as each changes what `providers` says
(`configured`), so a client holding the earlier answer is not told it is current. The catalogue is a function of the
code and of those settings, so it cannot be older than that. Behind several instances each has its own, and a date
from one is never taken as proof by another that is newer; the worst case is a 200 in full.

**What a 304 saves** is the transfer of the body, not the work of making it: the answer is built to be tagged. Measured
against a server on the loopback interface, a request that sends the tag is answered with 309 bytes where the 200 is
73,835 bytes for `coverage` of `dwd/observation` (8.5 kB gzipped), 135,285 with `pretty=true`, 19,850 for `providers`
and 129,018 for the whole `glossary`, in the same 4 to 6 milliseconds: on a network it is the bytes that count, and
`max-age` saves the request itself. A `history` is read again to be tagged, so for it too the saving is the body.

**Behind the web app** the browser keeps an answer for its `max-age` and then asks the app, whose `/api` proxy passes
the cache headers on but does not send the client's conditions to the backend: the revalidation is answered with the
200 in full, which is right and saves nothing.

Values are not kept by any of this. A client that wants a window it has read before to be cheap keeps it itself, or
asks for a closed window of the `historical` period, and decides how old it may be.

## Timeout

A request has to be answered within a timeout, `WD_RESTAPI_TIMEOUT` (`restapi_timeout`, in seconds), 60 by
default, `0` for none. It holds for the routes under `/api` until the response begins; one that has not by then is a
504 problem of the kind `request-timeout` with `Retry-After`. A stream may run for longer: the timeout holds
between two of its chunks, and a chunk that takes longer ends the stream with an `error` line of that kind (CSV: the
connection is cut).

The work of the request stops with its answer. The thread of a handler cannot be cancelled, so the walk over the
stations is told to stop and ends at the next station it comes to, or at the next file or listing it would begin
(`values`, `stations`, `interpolate`, `summarize`, the tools of the MCP endpoint, the files that are fetched ahead of
the station in hand): the station in hand is finished, a download that was begun arrives and is cached whole, and
nothing more is read for an answer nobody waits for. What the request had downloaded is cached, and the same
request made again after the `Retry-After` is likely to succeed. The request keeps its place in the
[limit on requests served at once](#concurrency) until the station in hand is done, which is soon, where it used to be
until the last station was. A single download (up to the time and the size the library holds a file to), the
parse of one file and the readings of one station are not cut: a station that takes long takes that long. An image
that does not get drawn has its own end, [the time it is given](#image-size). A reverse proxy in front of the server
has a timeout of its own, usually 60 seconds too; set this one below it for the answer to be this problem.

A stream whose client has gone stops in the same way, and so does one that a chunk of ran into the timeout. A server
with `WD_RESTAPI_TIMEOUT=0` holds a stream to no time: it ends when it is read to the end or when its client leaves.
Nothing of this is seen by Python or the command line, which have no timeout, and a request that ends in time is the
answer it was.

### Concurrency

A server works on a limited number of requests at once, `WD_RESTAPI_MAX_CONCURRENT` (`restapi_max_concurrent`), 32 by
default, `0` for no limit. A request under `/api` past it is not started but answered with a 503 problem of the
kind `server-busy` and `Retry-After`, and a client retries it after that time. `/health`, `/ready` and the index page
are not counted. A tool of the MCP endpoint makes its request to the API in process and is counted as one request there.

A request keeps its place until the work of its handler is done, not until its answer is sent: a request that timed
out is told to stop and ends at the station in hand (see [Timeout](#timeout)), so the limit bounds the threads of the
server, which the timeout alone does not. Only a tool call that its MCP client cancels gives its place back at once,
and its thread ends with the station in hand. The default leaves the rest of the 40 threads of the pool to the routes
that are not counted. Set it to what the host can take, and put a rate limit in front of the server; a cap is no
protection against a client that sends requests faster than they are answered, it only keeps them from piling up.

### Allowed hosts

The REST API and the MCP endpoint answer to every `Host` by default, which is what a server behind a proxy or on a
public name wants. `WD_RESTAPI_ALLOWED_HOSTS` (`restapi_allowed_hosts`) is a comma-separated list of the names the
server answers to; a request with another `Host` is a 400 problem of the kind `host-not-allowed`, and so is a
request to the MCP endpoint (`/mcp/v1`, `/mcp`) with an `Origin` that names a host that is not listed
(`origin-not-allowed`; a request without an `Origin`, as a client of an agent makes it, is not checked).

```bash
WD_RESTAPI_ALLOWED_HOSTS=weather.example.org,*.internal.example.org wetterdienst restapi --listen 0.0.0.0:7890
```

An entry is a name without a scheme or a path, compared without regard to case: `localhost` lets `localhost:7890` and
`localhost:3000` in, `localhost:7890` only the first; an IPv6 address is written in brackets (`[::1]`);
`*.example.org` stands for every name below `example.org`, not `example.org` itself. The `Origin` is compared by its
host in the same way. The probes of `/health` and `/ready` are not checked.

`wetterdienst restapi` sets the list for its own process to `localhost,127.0.0.1,[::1]` (and the host it was given)
when `--listen` is a loopback address, which is the default, `127.0.0.1:7890`, and the setting is not given. A page of
another site, whose name a DNS server re-points at `127.0.0.1` (DNS rebinding), reaches a local server with its own
name in `Host`, and is refused. A local server that is reached by another name, through a tunnel, a port mapping
or a container, sets the variable to its names, or listens on `0.0.0.0` and sets it to the names it is served
under. A server started otherwise (`uvicorn wetterdienst.ui.restapi:app`) answers to every host unless the variable is
set.

## Running it for others

The REST API and the MCP endpoint have no authentication, and the server sets no CORS headers. Both are by design,
and what follows is for an instance that others can reach (the
[threat model](https://github.com/earthobservations/wetterdienst/blob/main/.github/SECURITY.md) has the rest):

- **Who may use it.** Anyone who reaches it can use the provider credentials it holds (`WD_AUTH__*`) and spend their
  quotas. `/api/auth` and `/api/providers` say whether a key is configured, never the key. Put a gateway in front that
  authenticates, terminates TLS and limits the requests of each client: the server has a [timeout](#timeout), a
  [cap on requests served at once](#concurrency) and [limits](#limits), no limit per client.
- **CORS.** A page of another origin cannot read the answers. Serve it from the origin of the API, or let the reverse
  proxy add the headers it needs.
- **Hosts.** [Allowed hosts](#allowed-hosts) are open until you set them, in the image too.
- **Response headers.** Every answer, errors and streams included, carries `X-Content-Type-Options: nosniff`, so a
  browser takes a body for the media type it is sent as. A `Content-Security-Policy` is sent with the index page and
  the `svg` answers only, which need no script or request: not with data answers, the `html` chart (a script by
  design), `pdf`, or `/docs` and `/redoc`, which load their own from a CDN. Other headers (HSTS, a
  `Referrer-Policy`, a policy for those answers) are for the reverse proxy to add.
- **Charts.** A chart is drawn by vl-convert in the server's process, one at a time, and takes time and memory (11 s
  and 1.3 GB at 100,000 points), so [charts](#charts) are off until you set `WD_RESTAPI_PLOTTING=true`; a public server
  is better off without them.
- **SQL.** The REST API and the MCP tools take no SQL any more, see [SQL filters](#sql-filters); a server started with
  `WD_RESTAPI_SQL=true` warns once and runs without it.
- **Limits.** The [limits](#limits) are the ones you set. How to set them, and what raising one costs, is on
  [Getting more than the limit](large-requests.md#run-your-own-server), which is also where a client that meets one is
  sent.
- **The cache directory.** `WD_CACHE_DIR` holds the downloaded bodies it caches and the directory listings, as JSON in
  a SQLite file; nothing in it is unpickled or run. Whoever can write there can still replace what the server caches,
  so keep it private to the user the server runs as (a directory wetterdienst makes gets mode 0o700; one that exists
  keeps its mode).

### Health and readiness

`GET /health` is the liveness probe: `{"status": "OK"}` for as long as the process answers. It reads nothing and
cannot fail other than by the process being gone, which is what a restart is for. `GET /ready` is the readiness
probe: it says whether the server can serve a data request, which can stop being true while the process is fine. It
answers `{"status": "ready"}`, or a 503 problem of the kind `not-ready` with `Retry-After` and the `checks` that
failed:

| Check | Fails when |
| --- | --- |
| `settings` | A `WD_*` or `WD_TS_*` setting does not build. They are checked as the server starts, and every request reads them again, so a `.env` edited into something invalid afterwards makes every data request a 500. The server log names the variable, never its value. |
| `cache` | Neither `WD_CACHE_DIR` (a directory the server can write to, or make below one it can write to) nor the temporary directory can be written to, and `WD_CACHE_DISABLE` is not set. A cache directory alone that cannot be used is **not** a failure: the library then caches in a temporary directory, warns once, and serves every request ([Docker](docker.md#upgrading-from-an-image-that-ran-as-root)); what stops a download is that fallback failing too. A full disk is not found: that takes a write. |

Neither probe is held to the host check, the cap on requests served at once or the timeout, so a probe that reaches the
server by an address of its own is answered; neither needs a credential, and neither is an MCP tool. `/ready` asks
no provider: one that is down does not take the server out of the pool, its requests fail with the 5xx that says so
(`upstream-failed`, `upstream-unreachable`, `upstream-timeout`) and the rest are served. It does not look at the
load either: a server working on as many requests as it allows answers those that count with a `server-busy` 503
and stays ready. The answer is `Cache-Control: no-store`.

`HEAD /health` and `HEAD /ready` answer as their `GET` does, with its status and headers (`Content-Length`, and for
`/ready` the `no-store` and the 503 with `Retry-After`) and no body, for a monitor or `wget --spider` that probes with
`HEAD` and reads a 405 as the server being down. They take the same path as the `GET`s: outside the host check, the cap
and the timeout. The routes of the API, the index and `robots.txt` answer `HEAD` with a 405 as before (the pages
FastAPI adds, `/openapi.json`, `/docs` and `/redoc`, answer it already). The document lists a `head` operation on the
two probes alone, and a `POST` to one is a 405 with `Allow: GET, HEAD`.

## Errors

Every error of the `/api/v1` routes and their `/api` alias is an [RFC 9457](https://www.rfc-editor.org/info/rfc9457/)
problem, served as `application/problem+json`, whatever its status: a 400, a 404, a 422, a 500 or
the 404 of a path that does not exist. The MCP endpoint (`/mcp/v1`) answers its own errors as JSON-RPC, but for the `Host` and `Origin` check, which is a problem
as well (see [Allowed hosts](#allowed-hosts)).

```json
{
  "type": "urn:wetterdienst:problem:request-refused",
  "title": "Bad Request",
  "status": 400,
  "detail": "coverage describes one network, so both provider and network are required. To list the providers and their networks, use /api/providers.",
  "instance": "urn:wetterdienst:request:4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "request_id": "4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11"
}
```

`detail` is always text, the whole reason, with one line for each thing wrong where a request is
wrong in several. A request that fails validation (422) also carries `errors`, a list with one
entry for each invalid parameter, where `loc` names it:

```json
{
  "type": "urn:wetterdienst:problem:invalid-parameters",
  "title": "Unprocessable Content",
  "status": 422,
  "detail": "limit: Input should be greater than or equal to 1",
  "instance": "urn:wetterdienst:request:4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "request_id": "4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
  "errors": [
    {"type": "greater_than_equal", "loc": ["query", "limit"], "msg": "Input should be greater than or equal to 1", "input": "0", "ctx": {"ge": 1}}
  ]
}
```

| Status | When |
| --- | --- |
| 400 | the request is understood and cannot be served as phrased: a window that ends before it starts, a parameter the network does not have (the whole request is refused, and `detail` names each unknown one), a point out of range, a `Host` or an MCP `Origin` the server does not answer to ([Allowed hosts](#allowed-hosts)) |
| 403 | a chart (`format` `html`, `png`, `jpg`, `svg` or `pdf`) of `stations`, `values`, `interpolate` or `summarize`, which a server draws only with `WD_RESTAPI_PLOTTING=true` ([Charts](#charts)); `detail` names the formats it answers |
| 404 | what the request names does not exist: a provider, network, a resolution or dataset of `/api/coverage`, station, forecast run, or a path |
| 405 | the method is not allowed for the path |
| 422 | the request is malformed: an unknown or invalid query parameter, a selection that needs exactly one of several; or a map of stations (`format` `html`, `png`, `jpg`, `svg` or `pdf`) none of which has a position (`dwd/derived`'s `monthly/climate_correction_factor`, `dwd/pollen`), where `detail` says to ask for `json`, `csv` or `geojson` and `errors` has the entry for `format` |
| 501 | the server cannot serve it: a credential it lacks or the provider rejects, or an optional package it lacks, which the body does not name |
| 502 | the data provider failed or sent an answer the server cannot read: a download that was refused or cut short, a file in a layout it does not expect; the request was valid and can be retried |
| 503 | the server could not reach the data provider (no network connection), or it is working on as many requests as it allows ([Concurrency](#concurrency)); the request was valid and can be retried, the body says so and does not name the provider's address |
| 504 | the data provider did not answer in time, or the server's own work did not finish in time (the request timeout, an image that was not rendered); the request was valid and can be retried |
| 500 | the server's own error, a defect: the body names the exception's type and nothing else, the cause is in the server log |

Read `type` for what kind of error it is, `status` for what happened and `detail` for a sentence to show; the
wording of `detail` is not part of the contract, the `type` is. A client that read `detail` as the list of a 422
reads `errors` now.

`type` is `urn:wetterdienst:problem:<kind>`: a name for the kind of error, not an address to fetch. The kinds
are these, and a kind keeps its status:

| Type | Status | When |
| --- | --- | --- |
| `urn:wetterdienst:problem:invalid-parameters` | 422 | A query parameter is unknown, malformed or invalid, or a selection that needs exactly one of several does not. `errors` has an entry for each invalid parameter. |
| `urn:wetterdienst:problem:request-refused` | 400 | The request is understood and cannot be served as phrased: a window that ends before it starts, a parameter the network does not have, a point out of range. |
| `urn:wetterdienst:problem:limit-exceeded` | 400 | The request would return more than the server allows. `limit` names the limit (`stations`, `rows`, `stream_rows`, `groups`, `series` or `image_points`), `maximum` its value and `requested` what the request comes to; `detail` says how to narrow it, and [Getting more than the limit](large-requests.md) how to get the data anyway. |
| `urn:wetterdienst:problem:image-too-large` | 400 | A chart would be longer than 8192 px on a side. |
| `urn:wetterdienst:problem:charts-disabled` | 403 | The request asks for a chart (`html`, `png`, `jpg`, `svg` or `pdf`) and this server draws none (`WD_RESTAPI_PLOTTING`, off by default). Nothing was read. Ask for one of the data formats `detail` names, or ask whoever runs the server to switch charts on. |
| `urn:wetterdienst:problem:host-not-allowed` | 400 | The `Host` of the request is not one the server answers to (`WD_RESTAPI_ALLOWED_HOSTS`). Reach the server by a name it lists. |
| `urn:wetterdienst:problem:origin-not-allowed` | 400 | The `Origin` of a request to the MCP endpoint is not a host the server answers to (`WD_RESTAPI_ALLOWED_HOSTS`). A page of another origin cannot use the endpoint. |
| `urn:wetterdienst:problem:not-found` | 404 | What the request names does not exist: a station, a forecast run, a resolution or dataset, or a path. |
| `urn:wetterdienst:problem:unknown-network` | 404 | The provider and network are not served, or have no stations or values to request. |
| `urn:wetterdienst:problem:method-not-allowed` | 405 | The method is not allowed for the path. |
| `urn:wetterdienst:problem:not-implemented` | 501 | The server does not implement what the request asks for, such as the station history of a network. |
| `urn:wetterdienst:problem:dependency-missing` | 501 | The server lacks an optional package the request needs. Whoever runs it has to install it. |
| `urn:wetterdienst:problem:credential-missing` | 501 | The provider needs a credential and the server has none. |
| `urn:wetterdienst:problem:credential-rejected` | 501 | The provider rejected the credential of the server. |
| `urn:wetterdienst:problem:not-configured` | 501 | The server is not configured to serve the request. |
| `urn:wetterdienst:problem:upstream-failed` | 502 | The data provider failed or sent an answer the server cannot read. The request was valid; retry it. |
| `urn:wetterdienst:problem:server-busy` | 503 | The server is working on as many requests as it allows at once (`WD_RESTAPI_MAX_CONCURRENT`). The request was not started; retry it after `Retry-After`. |
| `urn:wetterdienst:problem:not-ready` | 503 | The server is running but cannot serve data: its settings are invalid, or neither its cache directory nor the temporary directory can be written to. Only `GET /ready` answers it; the server still answers `/health`. `checks` names what failed. |
| `urn:wetterdienst:problem:upstream-unreachable` | 503 | The server could not reach the data provider (no connection). The request was valid; retry it. |
| `urn:wetterdienst:problem:upstream-quota-exhausted` | 503 | The data provider refused the request because the quota or the rate limit of the key this server uses is used up for now. The key is accepted and the request was valid; retry it after `Retry-After`. |
| `urn:wetterdienst:problem:upstream-timeout` | 504 | The data provider did not answer in time. The request was valid; retry it. |
| `urn:wetterdienst:problem:request-timeout` | 504 | The server did not answer within its request timeout. Narrow the request, or retry it: what the server had fetched is cached. |
| `urn:wetterdienst:problem:internal-error` | 500 | The server's own error, a defect. The cause is in the server log. |

Every problem has `instance`, `urn:wetterdienst:request:<id>`, and `request_id`, the id of the request. The id
is also the `X-Request-ID` header of every response, error or not: the client's own where it sends one (letters,
digits and `._~-`, up to 128 characters), else one the server makes. Quote it when reporting a failure; the server
logs it with a failure of its own (a 5xx).

The web app's own `/api` proxy passes the backend's answers on as they are, the problem, `X-Request-ID` and
`Retry-After` included, and sends on the `X-Request-ID` of the client. When it cannot reach the backend there is no
answer to pass on, and it answers a problem of its own, a 502 of the kind `urn:wetterdienst:problem:backend-unreachable`
with `instance`, `request_id`, `X-Request-ID` and `Retry-After` as above. The backend cannot answer that kind, so it is not
in the table.

A 502, 503 or 504 carries `Retry-After`, 30 seconds: the request was valid and the same one can succeed once the
provider is back (or, after a timeout, with what the server has cached by then). The exception is
`upstream-quota-exhausted`, whose `Retry-After` is the wait the provider sent (`Retry-After` as seconds or a date,
`RateLimit-Reset`, `X-RateLimit-Reset`; not if it is not positive or is past a day), else 60 seconds for a 429, which
does not say that an hour's quota ran out, and 600 for a quota that is known to be one's. A 429 of any provider is this
kind, no longer a 502 `upstream-failed`. The server limits no rate, so
there is no 429; a proxy in front of it may, and the web app's own server does (a problem of the kind
`urn:wetterdienst:problem:rate-limited` with `Retry-After`, see [Web app](app.md#rate-limit)). The app's problems are
not in the table.

The library's exceptions are answered by their class in the hierarchy of
`wetterdienst.exceptions` (a `RequestError` is a 400, a `NotFoundError` a 404, a
`ConfigurationError` a 501, an `UpstreamError` a 502, 503 or 504), and the command line and the MCP
tools ask the same table. A client may retry a 502, 503 or 504; a 4xx it has to change the request
for, a 501 whoever runs the server has to act on, and a 500 is a defect.

The MCP tools put the same text into the tool error of an error the API answers, as `HTTP error
422: Unprocessable Content - limit: Input should be greater than or equal to 1`, and an exception
that no endpoint handled is the 500 sentence there too, not its own message.

## MCP endpoint

The REST API can serve a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) endpoint at `/mcp/v1`
(`/mcp` is an alias of the current version), so that LLM agents can call the data endpoints as tools. It needs the
`[mcp]` extra; without it the MCP paths are absent and `GET /api/version` says so (`mcp_enabled`). How to use the
hosted endpoint, how to run your own, the tools and the versioning are on the [MCP server](mcp.md) page.
