# Find a station by WMO, WIGOS or ICAO id

One weather station often has more than one provider. Hamburg's airport is DWD's `01975` in the observations, `10147` in
MOSMIX, `GM000010147` at NOAA GHCN and the aerodrome `EDDH`. The three ids that name a station the same way everywhere,
the **WMO number** (`10147`), the **WIGOS station identifier** (`0-20000-0-10147`) and the **ICAO code** (`EDDH`), are
columns of every stations frame (`wmo_id`, `wigos_id` and `icao_id`), where a provider publishes them. This page is
about the question across providers: *the station with WMO 10381, or ICAO EDDH, at every provider that has it*.

It is one function in Python, one command, one REST route and one MCP tool, which all answer the same list.

```bash
wetterdienst station-ids --wmo-id=10381
http localhost:7890/api/v1/station-ids wmo_id==10381
```

```python
from wetterdienst.core.station_search import find_stations_by_id

result = find_stations_by_id(wmo_id="10381")
print(result.df)  # one row for each station
```

## The answer

A list, one row for each station and network, since one WMO number can sit on several stations of one network (NOAA
GHCN lists up to four):

| Column | Meaning |
| --- | --- |
| `provider`, `network` | where the station is listed, as a request names them |
| `resolution`, `dataset` | the station list that was read, see [The lists](#the-lists) |
| `station_id` | the id the provider's own stations and values are asked by: pass it to `stations` or `values` |
| `name`, `latitude`, `longitude`, `elevation` | as the provider lists the station; null where it does not say |
| `wmo_id`, `wigos_id`, `icao_id` | the three ids the provider publishes with the station, null where it publishes none |
| `matched_by` | which of the station's ids matched: `wmo_id`, `wigos_id` or `icao_id` |
| `match` | `direct` where the id asked for is the one the station has, `equivalent` where an id equivalent to it is |

The rows are sorted by provider, network and station id. A station that one list repeats is one row, told by its strongest match. No row
means no listed station has the id, which is an answer and no error.

The REST API, the command line and the MCP tool wrap the rows in the `metadata` block of every answer, which for this
answer says:

- `request`: the ids as given, each in the notation of its column, and `also_searched`, the ids that were searched
  besides because they are equivalent (below);
- `searched`: every network that was asked, with the list it read, the id columns that list fills, the number of
  stations of it that carry an id, and its `status`: `searched`, `failed`, `rate-limited` or `not-configured`;
- `providers`: the licence and the credit line of each provider that has a station in the answer, since the answer holds
  several providers' data (there is no one `provider` as in the answers of `stations`);
- `counts`, `warnings`, the versions, the time and the `processing_note`, as every block has them.

## The ids are equivalent

- **WIGOS `0-20000-0-N` and WMO `N` are one id.** WMO's own issuer, 20000, writes the WMO number as the local part of
  the WIGOS identifier, so a search for either finds a station that has the other. `wigos_id=0-20000-0-10381` finds the
  stations whose `wmo_id` is `10381`, and `wmo_id=10381` finds one that has only the identifier. The leading zeros are
  read as the filters of the stations of one network read them: `1001` is `01001`, `0-056-101-01002` is `0-56-101-01002`.
  A WIGOS identifier of a national issuer (`0-756-0-BIA`) is no WMO number, even where its local part looks like one.
- **An ICAO code also searches the WMO numbers of its hits.** `icao_id=EDDH` finds the stations that list the aerodrome
  by its code (DWD's MOSMIX, DMO and POI), and then the stations that list its WMO number `10147` and no code: DWD's
  observations `01975` and NOAA GHCN `GM000010147`.

`match` tells the two apart for each row, and `also_searched` of the `metadata` block names the ids that were added.

## The lists

Every network that publishes the ids with its stations declares **one station list** to look them up in, in its
metadata (`MetadataModel.station_id_list`: the resolution, the dataset and the id columns that list fills), and every
such network is asked, all at once, with no narrowing by region: a station can be listed by a provider far from where it
stands, and only the lists say.

| Network | List read | Ids it fills |
| --- | --- | --- |
| `dwd/observation` | `daily/climate_summary` | `wmo_id`, `wigos_id` |
| `dwd/derived` | `daily/soil` (the datasets with DWD's station ids, not the grids) | `wmo_id`, `wigos_id` |
| `dwd/mosmix` | `hourly/small` | `wmo_id`, `icao_id` |
| `dwd/dmo` | `hourly/icon` | `wmo_id`, `icao_id` |
| `dwd/poi` | `hourly/data` | `wmo_id`, `icao_id` |
| `chmi/observation` | `daily/data` | `wmo_id`, `wigos_id` |
| `dmi/observation` | `daily/data` | `wmo_id`, `wigos_id` |
| `eccc/observation` | `daily/data` | `wmo_id` |
| `fmi/observation` | `hourly/data` | `wmo_id`, `wigos_id`, `icao_id` |
| `geosphere/observation` | `daily/data` | `wmo_id` |
| `meteofrance/synop` | `subdaily/data` | `wmo_id` |
| `meteoswiss/observation` | `daily/data` | `wmo_id`, `wigos_id` |
| `noaa/ghcn` | `daily/data` | `wmo_id` |
| `nws/observation` | `hourly/data` | `wmo_id` |
| `rmi/observation` | `10_minutes/data` | `wmo_id`, `wigos_id` |
| `aemet/observation` (key) | `daily/data` | `wmo_id` |
| `knmi/observation` (key) | `daily/data` | `wmo_id`, `wigos_id` |
| `metno/frost` (key) | `hourly/data` | `wmo_id`, `wigos_id` |

**Other datasets of a network may hold more stations.** A station that only reports hourly wind is not in
`dwd/observation`'s `daily/climate_summary`, and the row names the list it comes from. A search finds the stations of the
list, and `stations` of the dataset you want to read values from says whether it is there too. The tests hold the
declaration to the station list of the network: the columns it names are the ones the list fills.

`noaa/ghcn` is read without `ghcnd-inventory.txt`, which holds the elements of each station and no id (36 MB beside
the 11 MB of the stations file). The stations file also lists the 147 stations that the inventory has no line for, which
`stations` leaves out, and 146 of them have no data file. So each GHCN hit is checked for the daily file the values are
read from (NCEI's `by_station` file, then the AWS mirror's: one download, held in the cache for a read of the values, for
each hit, at most eight for a search; there is no cheaper request in the library), and a station with no file is no row:
WMO `10628` (Geisenheim, `GMM00010628`) is not an answer. A check that cannot be made (no connection, a 5xx) keeps the
row and is a `station-file-unchecked` warning that names the station, as is a 429 of the file's host (the checks of that
network that have not begun are left unmade).

A network that needs a key (`aemet`, `knmi`, `metno`) is asked only where the settings hold its credentials
(`WD_AUTH__AEMET`, `WD_AUTH__KNMI_EDR`, `WD_AUTH__METNO_FROST`); otherwise it is named in a `network-not-configured`
warning, and never a failure.

## What it costs

The first search reads the station lists of the networks above, about 30 MB, concurrently: about 9 s on a good
connection, longer on a slow one or when a provider is slow. The library's cache keeps each list (twelve hours for most;
the directory listings of DWD a few minutes), so the same search again, or the search for another id, takes about a
second. The MCP tool states the cold latency in its description so that a client does not repeat it.

## Failures

A network whose list cannot be read, or that cannot be imported on the server, is a `network-failed` warning that names it
and says why; the others answer, and the network is in `searched` with its `status` of `failed` (a network that cannot
be imported has a null `resolution` and `dataset`, as its declaration is not known). A failure that is a defect of the
library is logged with its traceback and told as an unexpected error, not by its text. A network that is merely not
configured is not counted as asked.

A network whose provider answers 429 is a `network-rate-limited` warning, not the end of the search: it names the network and
the wait the provider asks for (`retry after 30 s`, or that the provider names none), the others answer, and the network is
in `searched` with its `status` of `rate-limited`. One keyed provider that limits this installation (AEMET's quota is the
usual one) must not take the other seventeen networks down. It is the one rule of the library that differs from a single
request, where a 429 is never swallowed: a search asks many providers, and an answer of the others says what it lacks.

**A search in which every network that was asked failed or was rate-limited is an error, not an empty answer**, since an
outage or a limit must never read as no such station. With no 429 among them it is an `UpstreamError` that names the
networks (a 502 at REST, exit 1 on the command line). With at least one it is the `ProviderRateLimitError`, which names
them too and carries the longest wait asked for (a 503 with `Retry-After` at REST, exit 1 on the command line), since the
same search can succeed once the limit resets.

An MCP tool's answer is cut to 40,000 characters, as that of `stations` is, keeping the first rows, with an
`answer-truncated` warning that tells to ask for fewer ids.

## Python

`find_stations_by_id` takes `wmo_id`, `wigos_id` and `icao_id` (one id or several, at least one of the three), and the
`settings` of the host, and returns a `StationIdSearchResult`: `df` (the rows above), `request`, `also_searched`,
`searched` (a `SearchedNetwork` for each network asked) and `warnings`.

```{autodoc2-object} wetterdienst.core.station_search.find_stations_by_id
render_plugin = "myst"
no_index = true
```
