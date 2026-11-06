# What wetterdienst does with the data

Wetterdienst does not own the data it hands out. This page says what the project does with it: how it asks the
providers, what it keeps, what it changes, what the hosted instance passes on, what the keys of the providers that
need one allow, and what the repository's own files hold. It is the maintainers' reading of what the providers state
and of what that means for you. **It is not legal advice**: where it says "our reading" it is a reading, and where a
provider's text could be read two ways, the page says which and does not settle it. The terms themselves, which are
on [licences and credit lines](licenses.md) and in the License section of each provider's page, decide what you may do.

Everything below was read at the providers' own pages on 2026-11-06 unless a date says otherwise, with no key and no
personal data sent.

## How it asks the provider

What every request of the library does, whichever provider it goes to:

- **It names itself, and nothing about you.** The `User-Agent` is `wetterdienst/<version> (<system>)`, for example
  `wetterdienst/0.183.0 (Linux)`. It carries no contact and no address. Where a provider asks for a contact (NWS,
  MET Norway's weather API), set one yourself with `fsspec_client_kwargs` (`WD_FSSPEC_CLIENT_KWARGS`, see
  [settings](../../usage/settings.md)): a `User-Agent` you give in its `headers` replaces the default.
- **It sends no `Cache-Control: no-cache` and no `Pragma` header**, which ECCC's usage policy asks callers not to send.
- **It does not hammer.** A download is attempted twice and a listing three times, and only after a reset, a timeout, a
  `5xx` or a handshake the server fumbled; never after a `4xx`, and so never after a `429 Too Many Requests`: the
  answer comes back to you as it is. A certificate that does not verify is not asked again either.
- **It fetches ahead only for five providers**, `dwd/observation`, `dwd/derived`, `chmi`, `imgw/meteorology` and
  `smhi`, where one station is one set of files: while it parses one station it downloads the files of the next four
  (`fetch_ahead`, at most eight, and no more than eight connections to one host for all the reads of a process). 0
  switches it off; `interpolate` and `summarize` do not fetch ahead.
- **It keeps what it downloaded** for a few minutes (below), so the same file is not asked for twice in that time, and
  it does not read the provider's cache or rate-limit headers: the limits are its own.

What it does not do: it does not read a provider's rate-limit headers, count your requests against a provider's
limit, or queue them to stay under it. A request for many stations over a long window is many requests, and nothing in
the library asks whether the provider allows that many. The providers whose terms give a number or a rule about use
are in this table; each row links the License section of the provider, which quotes the terms.

| Provider | What the terms ask of a caller, beyond the licence |
| --- | --- |
| [AEMET](aemet/index.md#license) | cite AEMET, do not distort the data, give the date of the last update where the original has one; a `429` exists, no number is stated |
| [DMI](dmi/index.md#license) | "fair use": filter, do not poll needlessly, cache; may throttle an address that strains the services |
| [DWD](dwd/index.md#license) | credit "immediately next to the information"; a changed warning loses the source line; no guaranteed service level |
| [EA](ea/index.md#license) | one request in flight at a time for bulk downloads; 2,000,000 rows a call at most; may limit concurrency per address |
| [ECCC](eccc/index.md#license) | contact them at 86,400 requests a day or more; no local archive from GeoMet (use Datamart); a meaningful `User-Agent` |
| [Eaufrance](eaufrance/index.md#license) | request a subset with the filters, prefer the bulk exports for whole datasets; no number |
| [FMI](fmi/index.md#license) | 20,000 requests a day, 600 per 5 minutes (Download Service) |
| [GeoSphere Austria](geosphere/index.md#license) | 5 requests a second, 240 an hour; at most 1,000,000 values a request |
| [IMGW](imgw/index.md#license) | credit sentences in Polish, business use needs an agreement (see the page) |
| [IPMA](ipma/index.md#license) | asks for an e-mail to `webmaster@ipma.pt` about your use; no profit-making use stated as allowed |
| [KNMI](knmi/index.md#license) | personal keys, a key is not to be shared; 200 requests a second and 1,000 an hour per registered key; no polling |
| [LHMT](lhmt/index.md#license) | 180 requests a minute and 20,000 a day per IP address; the source must be named or access may end |
| [MET Norway](metno/index.md#license) | a client ID tied to an e-mail address; more than 1 request a second on average is "heavy traffic", contact them |
| [Met Office](metoffice/index.md#license) | CEDA account terms: no letting others use your account, use for the purpose you were given access for |
| [MeteoSwiss](meteoswiss/index.md#license) | no "high-frequency downloading of the same content", use the infrastructure only as needed |
| [NWS](nws/index.md#license) | a `User-Agent` is required; an unpublished rate limit |
| [RMI](rmi/index.md#license) | credit RMI "immediately next to the information", a central list of sources for processed data |
| [SMHI](smhi/index.md#license) | documented APIs only, no needless or mass downloads, use time-limited caching, may block an address |
| [Météo-France](meteofrance/index.md#license), [NOAA](noaa/index.md#license), [CHMI](chmi/index.md#license), [WSV](wsv/index.md#license) | nothing beyond the licence on the pages read (the WSV data is unchecked raw data) |

Where a provider counts "a user" by IP address, a server that answers many callers is one user. The hosted instance and
any instance you run for others share these limits among everyone who asks it (see
[the hosted instance](#the-hosted-instance)).

## What it keeps

The library keeps what it downloaded in a cache directory on the machine it runs on: the files the providers sent,
as they sent them, and the directory listings it read, as JSON in a SQLite file. Nothing is sent anywhere else by the
cache.

- **Where.** The platform's cache directory for `wetterdienst` (`wetterdienst cache` prints it), or `WD_CACHE_DIR`. A
  directory the library makes is private to its user (mode `0o700`). In the Docker image it is
  `/home/wetterdienst/.cache/wetterdienst`. Where none can be written, it keeps a cache in a temporary directory that is
  removed when the process exits. `WD_CACHE_DISABLE=true` keeps nothing.
- **How long.** Each download names its own lifetime. Values: five minutes for the files of the current period and of
  a live feed, so a second question within that time is not a second download. Catalogues (station lists, file
  indexes, metadata): twelve hours. The files of past years that no longer change, where a provider's archive is
  immutable (LHMT's history, Météo-France's finished years): no expiry. A few use a minute or an hour. The
  lifetimes are the library's and are in the provider modules.
- **What goes.** An entry past its lifetime is read again, and removed from the disk by the first download of a
  process that uses the directory, except those with no expiry, which stay until you delete the directory.

Keeping a copy of the files for your own use falls under the licences listed on
[licences and credit lines](licenses.md), all of which let you copy the data; the credit line and the notes of changes
are due when you pass anything on, not when you cache it. That is our reading.

## What it changes

Every answer says so in its `processing_note` (the [wording is on the licences page](licenses.md#what-wetterdienst-does-to-the-data)):
the files are reshaped into one table, parameters get one name whichever provider reports them, values are converted
to common units, and a value the source documents as missing (`-999`, `---`) is null with the text the source wrote in
`quality_flags`. Beyond that:

- **Plausibility checks** set a value that is physically impossible to null by default and keep the number the source
  wrote in `quality_flags` as `rejected:<check>,raw:<number>`; they can be switched to flag it only. See
  [plausibility checks](../plausibility.md). Whichever the mode, the answer shows what was done.
- **`interpolate` and `summarize`** calculate or select values from the readings of several stations; they add a
  sentence to the note.
- **Climate stripes and plots** are drawn from the annual values of DWD stations; the image headers carry a sentence.

The licences that ask for a note of changes (CC BY, Etalab) are met by the note where the answer carries it, which a CSV
or a spreadsheet written without `with_metadata=True` does not (see [licences and credit lines](licenses.md#what-wetterdienst-does-to-the-data)).
A licence that forbids changes or asks for them to be shared is another matter: IMGW (CC BY-NC-ND 4.0) and LHMT
(CC BY-SA 4.0) are the two networks where that applies, and each provider's page says what we know.

## The hosted instance

[wetterdienst.eobs.org](https://wetterdienst.eobs.org) runs the REST API, the MCP endpoint and the web app, for anyone,
without an account. What that means for the data:

- **It passes the data on.** Every answer is the provider's data, reshaped as above, handed to whoever asked. The
  licence or terms of 21 of the 22 providers say the data may be redistributed with the source named (IPMA adds a
  condition against profit-making use, see its page); each answer carries the licence, the credit line
  and the processing note in its `metadata` block and in `X-Wetterdienst-*` headers (the web app does not show them
  yet, see [#3799](https://github.com/earthobservations/wetterdienst/issues/3799)). For IMGW, whose licence
  forbids derivatives and commercial use, see the page of IMGW.
- **It caches for everyone.** One cache serves all callers, so a file is downloaded once per lifetime however many ask.
  The server sends no `Cache-Control` for values and stations; see [Caching](../../usage/restapi.md#caching).
- **It limits what costs something.** The web app counts requests per client (300 in 300 seconds by default, see
  [Rate limit](../../usage/app.md#rate-limit)); there is no limit that follows a provider's own limit. The providers
  that count by address (ECCC, FMI, GeoSphere, LHMT, NWS) see one address.
- **It holds the keys of the four providers that need one.** Read from its public `/api/coverage` on 2026-11-06,
  `aemet`, `knmi`, `metoffice` and `metno` report `configured: true` there. See the next section.
- **Its logs and the data protection of its users** are in the privacy policy of the app, not here.

## Keys and credentials

Four providers need a key or an account: AEMET (API key), KNMI (API key), the Met Office's MIDAS Open (a CEDA account,
from which the library mints a token valid for three days) and MET Norway's Frost (a client ID). What each states about
sharing the key and about serving others with it, quoted at the License section of the provider:

| Provider | What the terms say | Does a server that answers others with one key fit? |
| --- | --- | --- |
| [AEMET](aemet/index.md#license) | The key "identifies" the user; as many may be created as needed; an e-mail address is asked. Nothing on sharing, nothing on serving others. | Not addressed by the pages read. |
| [KNMI](knmi/index.md#license) | "Accounts and keys are personal. They are meant to be used by you or by your organisation for your own applications, and should not be shared with, resold to, or distributed to third parties." And: "If you want to serve KDP data to your own users, proxy the requests through your own backend, keep the key there, and add caching in your backend." | Ambiguous: a backend with a key and a cache is the pattern KNMI names; an open server for anyone may be more than "your own users". Ask KNMI. |
| [Met Office](metoffice/index.md#license) (CEDA) | "Not to use another person's account, nor to let other people use your accounts, except by agreement with us"; "Only to use the service/resource for the purposes for which you were given access". | Ambiguous: others use the server, not the account. Ask CEDA. |
| [MET Norway](metno/index.md#license) (Frost) | "Each client ID must be associated with a valid email address"; "Use a proxy if possible"; "more than 1 requests to the API per second" on average is heavy traffic, "save the information on your own server" and contact them; "trying to circumvent traffic rate limiting measures and/or impersonating traffic from other clients" is abuse (weather API terms). | A proxy with a cache is asked for; the rate on average is the question. Ask MET Norway if the instance is near 1 request a second. |

None of the four says in terms that serving others from one key is allowed or forbidden. We have not used any key to
read what a key's response says, and nothing here has been put to a provider. A question to the provider is the maintainer's to send.

## The repository's own files

The repository holds real provider data of two kinds: excerpts in the tests, and a few images in the docs. The code is
MIT (`LICENSE.md`); the data in it keeps the licence of its provider, which MIT does not replace and which the
repository did not say until this page. This section is the notice.

| Where | What | Provider and terms |
| --- | --- | --- |
| `tests/provider/dwd/radar/files/` | nine radar files of 2026-10-20 to 22 (composites and a volume as HDF5, two `meso` and one `KONRAD3D` XML), 570 kB | DWD, CC BY 4.0, "Source: Deutscher Wetterdienst"; unchanged files |
| `tests/provider/dmi/observation/` | four JSON files of hourly readings and parameter lists, 85 kB | DMI, CC BY 4.0, "© DMI (Danish Meteorological Institute)" |
| `tests/provider/noaa/ghcn/` | two CSV files of GHCN-Daily elements, 1.3 kB | NOAA NCEI, CC0 1.0 |
| `tests/provider/station_catalogue_stubs.py`, `value_stubs.py` and the inline text of the tests of each provider | rows of the real station lists and of real values, a few rows per network, in the provider's own format | the licence and credit line of that provider on [licences and credit lines](licenses.md) |
| `docs/assets/readme-stripes.png`, `summary.png`, `interpolation.png` and the output cells of the docs and the README | charts drawn from, and tables of, DWD values | DWD, CC BY 4.0: "Based on data from Deutscher Wetterdienst" for drawn or processed data |
| `src/wetterdienst/provider/eumetnet/opera/sites.json.gz` (shipped in the package) | the list of the 205 OPERA radar sites of EUMETNET, as it was published | EUMETNET's [OPERA database](https://www.eumetnet.eu/wp-content/themes/aeron-child/observations-programme/current-activities/opera/database/OPERA_Database/index.html) page states no licence |

Our reading:

- Credit and licence are what most of the providers ask for (CC BY, OGL, Etalab, DL-DE-Zero, ECCC's licence, AEMET's
  notice: the source, a note of changes), and the data are facts in a few rows of a list or a series. This notice gives
  the credit; the files themselves cannot carry it.
- **IMGW** is CC BY-NC-ND 4.0 and its terms ask for two Polish sentences on "every work or product made with the data".
  A few dozen rows of IMGW's station lists and daily values are in the tests (`tests/provider/imgw/`,
  `station_catalogue_stubs.py`, `value_stubs.py`): copied, not changed, but in a repository that MIT lets anyone use
  commercially, and without the credit sentences. **LHMT** is CC BY-SA 4.0, whose share-alike would ask for the same
  licence on anything adapted from its rows.
- The OPERA list in the package has no stated licence.

What to do about these is the maintainers' decision and is not made here; the options are to keep the rows and say so
in this table, to replace the IMGW and LHMT rows by invented ones of the same shape, or to ask the provider. A test
(`tests/test_docs_provider_licenses.py`) holds the first table of this page to the registry, so that a provider added
without a row fails it.

## Our reading

- The credit line and the licence of every answer are the providers'. Wetterdienst reports them, and passes them on in
  every answer that holds data; it cannot make a user publish them.
- The data is changed, as above, and every answer says it; a CSV written without `with_metadata=True` does not. Where
  you publish data or a chart of it, give the credit line and say that it was processed.
- Caching a provider's files for your own use needs nothing beyond its licence. Serving them to others is
  redistribution: it needs the credit line, the licence and the note of changes to go with the data, which the hosted
  instance's answers carry, and it needs the provider's terms on use of its service to be kept, which the table above
  lists. For ECCC, FMI, GeoSphere, LHMT and NWS that means staying under limits one address shares, for KNMI, the Met
  Office, MET Norway and AEMET it means a key that is asked about above.
- Where a provider's text can be read two ways, the page says so and leaves it. Nothing on this page was sent to a
  provider, and no provider has confirmed any reading of ours but IMGW's, which is on its page.
