# Troubleshooting

What a failure means and what to do about it, by what you see. The same failure has one name on every surface:
the exception class in Python, the exit code on the command line, the status and the `type` of the problem in the
REST API and the MCP tools (see [Errors](python-api.md#errors) and [REST API](restapi.md#errors) for the full
tables). Problems of one machine (a proxy, a certificate, an old Raspberry Pi) are in [Known issues](../known_issues.md).

| You see | It means | What to do |
| --- | --- | --- |
| `InvalidParameterError`, exit 2, 400 `request-refused` | the request is understood and cannot be served as phrased | read the message, it names the entry and the close match |
| 422 `invalid-parameters` | a query parameter is unknown or malformed | `errors` names each; check the spelling and the [vocabulary](restapi.md#one-vocabulary) |
| `NotFoundError`, 404 | a provider, network, resolution, dataset, station or run that does not exist | look it up with `coverage` or `about coverage` |
| `MissingDependencyError`, 501 `dependency-missing` | an extra is not installed | install the extra the message names, see [Installation](quickstart.md#installation) |
| `CredentialMissingError` or `CredentialRejectedError`, 501 | a provider needs a key and there is none, or it is refused | see [Credentials](#credentials) |
| `NoInternetError`, exit 1, 503 `upstream-unreachable` | the provider could not be reached | see [Upstream outages](#upstream-outages) |
| `DownloadError`, 502 `upstream-failed`, 504 `upstream-timeout` | the provider answered badly or too late | the same |
| 400 `limit-exceeded`, 504 `request-timeout` | the REST API or MCP server holds a request to its limits | see [Limits](#limits-and-timeouts) |
| 503 `server-busy` | the server works on as many requests as it is set to | wait the `Retry-After` and ask again, see [Limits](#limits-and-timeouts) |
| 400 `host-not-allowed` or `origin-not-allowed` | the server answers only to the `Host` names it lists (`WD_RESTAPI_ALLOWED_HOSTS`) | reach it by a name it lists, or add yours, see [Allowed hosts](restapi.md#allowed-hosts) |
| 429 `rate-limited` | the web app limits what a client may count against it | wait the `Retry-After`, see [Web app](app.md#rate-limit) |
| an empty `values` or `stations` | nothing in the window, or no such station: an answer, not an error | see [An empty answer](#an-empty-answer) |

## An empty answer

An empty result is not a failure. In Python it is an empty frame, on the command line exit 0 with
`No data available for given constraints` on stderr, and in the REST API a 200 with an empty `values` or `stations`.
The usual reasons:

- **The window has no readings.** A station's record has a start and an end (`start_timestamp`, `end_timestamp` of
  `stations`); a day that is not published yet, or before the station began, is empty. `periods` that the dataset
  does not publish under are refused rather than empty; an `end` without a `start` is the one day of `end`, not
  everything up to it.
- **The station has no data for the parameters.** A station id that has none of the requested parameters is left
  out with a warning (`unknown-station` in the `metadata` of the REST answer, a log line in Python), and when none
  is left the result is empty. Ask `stations` with the same `parameters` first: it lists only the stations that have
  them.
- **A name matched nothing.** A name is matched fuzzily with a threshold (`name_threshold`, 0.8 by default); lower it
  or look at the best matches (`rank`).
- **Nulls were dropped.** The long shape drops rows without a value by default (`drop_nulls`); a reading the source
  marks as missing is null with the source's text in `quality_flags` (`raw:-999`). `drop_nulls=False` shows them.
- **A station was skipped** for having too little data, if `skip_empty` is on (`station-skipped` warning).

The `warnings` of the `metadata` block say what a partial answer is missing, see
[response metadata](restapi.md#response-metadata).

## Credentials

AEMET, KNMI, MET Norway Frost and the Met Office (CEDA) need a key or an account, which you ask the provider for
(the provider pages say where) and give to wetterdienst as a setting:

| Provider and network | Variable | Python |
| --- | --- | --- |
| `aemet/observation` | `WD_AUTH__AEMET=<api_key>` | `Settings(auth={"aemet": "<api_key>"})` |
| `knmi/observation` | `WD_AUTH__KNMI=<api_key>` | `Settings(auth={"knmi": "<api_key>"})` |
| `metno/frost` | `WD_AUTH__METNO_FROST=<client_id>` | `Settings(auth={"metno_frost": "<client_id>"})` |
| `metoffice/observation` | `WD_AUTH__CEDA=<username>:<password>` | `Settings(auth={"ceda": "<username>:<password>"})` |

`CredentialMissingError` says the setting to change. `CredentialRejectedError` says the provider answered 401 or 403
to the one you gave: it has expired (the Met Office token lives three days), was mistyped, or was revoked. Whether a
network accepts the credentials the process holds is one call: `wetterdienst about auth --provider=aemet
--network=observation`, `GET /api/auth`, the MCP tool `auth`, or `Wetterdienst.is_valid(...)`; `coverage` says only
whether they are `configured`. `valid` is `null` where the provider could not be asked in time: treat it as unknown.

Against the REST API or the MCP server the credentials are the server's, not yours: a 501 `credential-missing` or
`credential-rejected` is for whoever runs the server, who sets the variable in its environment. The hosted instance
serves the networks that need no key; for the others, run your own.

## Upstream outages

wetterdienst reads files and APIs of national services, and they are sometimes down, slow or changed. The failures
say which:

- **`NoInternetError`** (command line: exit 1 with `No internet connection: could not reach <url>`; REST 503): the
  connection could not be made. The message names the URL without its query or credentials, and the connection error
  is the exception's `__cause__`. Check the network, the proxy (`Settings(fsspec_client_kwargs={"trust_env": True})`,
  see [Settings](settings.md#python)) and, on the server, its own connection. Nothing was written to a `--target`.
- **`DownloadError`** (REST 502, 504 when it timed out): the provider answered with an error status, cut the answer
  short, or sent a file in a layout the parser does not know. The request was valid; try again later. If a provider has
  changed its files, that is a [bug to report](#reporting-a-problem).
- **A provider that throttles.** A burst of downloads can make a provider refuse your address for a
  while (DWD has been seen to); the failures then differ from run to run and pass later. Request less (one
  parameter, a shorter window, fewer stations) or wait; the [cache](python-api.md#caching) keeps what was downloaded.

A 502, 503 or 504 of the REST API carries `Retry-After` (30 seconds): the request was valid and can be repeated.
Every one of these is safe to retry; a 4xx has to be changed first.

## Limits and timeouts

The library and the command line have no limits. The REST API and the MCP tools hold a request to three, so that one
request cannot take the server down; the answer names the limit and its value:

| `limit` | Default | What to do |
| --- | --- | --- |
| `stations` | 100 stations of a `values` or `history` request | name fewer stations, a smaller `rank`, `distance` or bounding box, and ask again for the rest |
| `rows` | 500,000 rows of an answer sent as one body | narrow the `timestamp` or the parameters, or use `format=ndjson` or `format=csv`, which stream |
| `stream_rows` | 10,000,000 rows of a streamed answer | narrow it, or run the library or the CLI, which have no limit |

`GET /api/version` reports the limits of an instance (`limits`), and a client can size its request before it is
refused. A request has to be answered within `WD_RESTAPI_TIMEOUT` (60 seconds): a 504 `request-timeout` has
downloaded what it could, so the same request again is likely to succeed. For a long series, ask in pieces (a year at
a time) or from Python. See [Limits](restapi.md#limits) and [Timeout](restapi.md#timeout), and
[Getting more than the limit](large-requests.md) for the ways to the data, in the order to try them.

A server also works on only so many requests at once (`WD_RESTAPI_MAX_CONCURRENT`, 32 by default, `limits.max_concurrent`
in `/api/version`): one past it is a 503 `server-busy` with `Retry-After`, and asking again after that time is
the answer, see [Concurrency](restapi.md#concurrency).

## Other things that go wrong

- **`403 sql-disabled`**: the server does not enable the `sql` and `sql_values` filters (`WD_RESTAPI_SQL=true` does).
  In the library and the command line they work.
- **`400 image-too-large`**: a chart longer than 8192 px on a side; lower `width`, `height` or `scale`.
- **Stale or odd results from the cache.** `wetterdienst cache` prints the cache directory; delete it, or set
  `WD_CACHE_DISABLE=true` to run without it. A cache directory that cannot be written (a Docker volume that root
  filled) does not fail a request: wetterdienst warns once and keeps a cache in a temporary directory, see
  [Docker](docker.md#upgrading-from-an-image-that-ran-as-root).
- **`SSLError: CERTIFICATE_VERIFY_FAILED`**: `Settings(use_certifi=True)`, see [Known issues](../known_issues.md).
- **A parameter you expect is not there.** The names are canonical (`temperature_air_mean_2m`), and the provider's own
  are accepted too (`tmk`); `coverage`, the [glossary](../data/parameters.md) and the provider page list them. A
  value that came back in other units than the source's is converted, see [Units](units.md).
- **An old option or name is refused with a message naming the new one** (`station was renamed to stations`,
  `--convert_units was renamed to --convert-units`, `values.filter_by_sql` in Python): follow the message; the
  [changelog](../changelog.md) lists the renames.

## Reporting a problem

An [issue](https://github.com/earthobservations/wetterdienst/issues) with the output of `wetterdienst info` (the
version and the cache directory), the call that failed with its whole message, and, for a REST or MCP failure, the
`request_id` of the problem (the `X-Request-ID` header of every response, which the server logs with its own
failures). A provider that is down is that provider's to fix, but a change in its files is ours: say which URL.
