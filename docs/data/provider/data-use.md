# What wetterdienst does with the data

Wetterdienst does not own the data it hands out. This page says what the project does with it: how it asks the
providers, what it keeps, what it changes, what the hosted instance passes on, what the terms of the providers that need
a key say about sharing it, and what the repository's own files hold. It is the maintainers' reading of what the
providers state and of what that means for you. **It is not legal advice**: where it says "our reading" it is a reading,
and where a provider's text could be read two ways, the page says which and does not settle it. The terms themselves,
which are on [licences and credit lines](licenses.md) and in the License section of each provider's page, decide what
you may do.

Everything below was read at the providers' own pages on 2026-11-06 unless a date says otherwise, with no key and no
personal data sent.

## How it asks the provider

What the requests of the library do, whichever provider they go to:

- **It names itself, and nothing about you.** The `User-Agent` is `wetterdienst/<version> (<system>)`, the version of
  the library and the name of the operating system. It names the application and carries no contact and no address.
  KNMI asks for a descriptive `User-Agent` "that identifies your application, and, if possible, how to reach you", ECCC
  for "a meaningful HTTP User-Agent", NWS requires one and invites a contact in it, and MET Norway's weather API (not
  read by the library) wants a contact too. To add a contact, give a `User-Agent` in the `headers` of `fsspec_client_kwargs`
  (`WD_FSSPEC_CLIENT_KWARGS`, see [settings](../../usage/settings.md)); it replaces the default.
- **It sends no `Cache-Control: no-cache` and no `Pragma` header**, which ECCC's usage policy asks callers not to send.
- **It retries a failure that may pass, and not an answer.** For every provider a download is attempted twice and a
  listing three times, after a reset, a timeout, a `5xx` or a handshake the server fumbled, and a download also once
  more after a `404` (a file index can be read before the file it names is published). A certificate that does not
  verify and a `429 Too Many Requests` are not asked again, and the answer comes back to you as it is. Two providers
  add a loop of their own: AEMET and KNMI ask up to three times in all, waiting 2 seconds to start with and 15 at most. AEMET retries a
  `429` (and any status but `400`, `401`, `403` and `404`); KNMI's EDR API is asked once for a `404` (no data, a request of
  its quota) and retries a reset or a `5xx`, not a `400`, `401`, `403`, `404`, `413`, `422` or `429`.
- **It fetches ahead for five networks**, `dwd/observation`, `dwd/derived`, `chmi`, `imgw/meteorology` and `smhi`
  (of four providers), where one station is one set of files: while it parses one station it downloads the files of the
  next four (`fetch_ahead`, at most eight, and no more than eight connections to one host for all the reads of a
  process). 0 switches it off; `interpolate` and `summarize` do not fetch ahead.
- **It keeps what it downloaded** for a lifetime of its own (below), and it does not read the provider's cache headers.
  It does not read a provider's rate-limit headers, count your requests against a limit, or queue them to stay under
  it. A request for many stations over a long window is many requests, and nothing in the library asks whether the
  provider allows that many.

The providers whose terms give a number or a rule about use are in this table; each row links the License section of
the provider, which quotes the terms.

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
| [IPMA](ipma/index.md#license) | asks for an e-mail to `webmaster@ipma.pt` about your use; its conditions allow copying and use where no profit-making or offensive purpose results |
| [KNMI](knmi/index.md#license) | personal keys, a key is not to be shared; 200 requests a second and 1,000 an hour per registered key; no polling |
| [LHMT](lhmt/index.md#license) | 180 requests a minute and 20,000 a day per IP address; the source must be named or access may end |
| [MET Norway](metno/index.md#license) | a client ID tied to an e-mail address; more than 1 request a second on average is "heavy traffic": contact them if the requests cannot be reduced by their guidelines |
| [Met Office](metoffice/index.md#license) | CEDA account terms: no letting others use your account, use for the purpose you were given access for |
| [MeteoSwiss](meteoswiss/index.md#license) | no "high-frequency downloading of the same content", use the infrastructure only as needed |
| [NWS](nws/index.md#license) | a `User-Agent` is required; an unpublished rate limit |
| [RMI](rmi/index.md#license) | credit RMI "immediately next to the information", a central list of sources for processed data |
| [SMHI](smhi/index.md#license) | documented APIs only, no needless or mass downloads, use time-limited caching, may block an address |
| [Météo-France](meteofrance/index.md#license), [NOAA](noaa/index.md#license), [CHMI](chmi/index.md#license), [WSV](wsv/index.md#license) | nothing beyond the licence on the pages read |

Whether a limit counts callers or addresses is mostly not said. LHMT counts "from one IP address". ECCC speaks of "you
or your application", FMI of "user specific request limitations", GeoSphere of "A users requests", and NWS only says
that "Proxies are more likely to reach the limit". Our reading is that a server that answers many callers is one user
to each of them, so the hosted instance and any instance you run for others share these limits among everyone who asks
it (see [the hosted instance](#the-hosted-instance)).

## What it keeps

The library keeps what it downloaded in a cache directory on the machine it runs on: the files the providers sent,
as they sent them, and the directory listings it read, as JSON in a SQLite file. Nothing is sent anywhere else by the
cache.

- **Where.** The platform's cache directory for `wetterdienst` (`wetterdienst cache` prints it), or `WD_CACHE_DIR`. A
  directory the library makes is private to its user (mode `0o700`). In the Docker image it is
  `/home/wetterdienst/.cache/wetterdienst`. Where none can be written, it keeps a cache in a temporary directory that is
  removed when the process exits. `WD_CACHE_DISABLE=true` keeps nothing.
- **How long.** Each download names its own lifetime, in the provider's module. The values of most networks are kept
  five minutes, so a second question within that time is not a second download. Exceptions:
  - twelve hours: the files of CHMI and of the Met Office, DWD's road, phenology and RADOLAN radar files, and the runs
    of a DWD forecast that no longer change;
  - no expiry for a period that no longer changes (the days before today of LHMT, the years before last of
    Météo-France's observations, the years before this one of its synop), five minutes for the current one;
  - not kept at all: the values of WSV and the station lookups of EA (its readings are kept five minutes);
  - catalogues (station lists, file indexes, metadata) are kept twelve hours, a few listings a minute or an hour.
- **What goes.** An entry past its lifetime is read again, and removed from the disk by the first download of a
  process that uses the directory, except those with no expiry, which stay until you delete the directory.

Keeping a copy of the files for your own use falls under the licences listed on
[licences and credit lines](licenses.md), which let you copy the data (IMGW's for non-commercial use only). Where they ask for a credit or a note of changes, it is due when you pass something on, not when you cache it.
That is our reading.

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

What the licences ask about changes differs. CC BY asks to "indicate if changes were made"; the note in the answer says
what was done, and a CSV or a spreadsheet written without `with_metadata=True` does not carry it (see
[licences and credit lines](licenses.md#what-wetterdienst-does-to-the-data)). Whether the note is enough for a licence is
for you and the licence to say; our reading is that it says what the licence asks to be said, where the answer carries
it. Etalab 2.0 (Météo-France, Eaufrance) asks for the source and the date of the last update of the information, and that
the reuse does not mislead about them; the answers carry the date as `data_updated_at` where the provider states one
(Eaufrance states none). IMGW (CC BY-NC-ND 4.0) and LHMT (CC BY-SA 4.0) are the two networks whose licence also
concerns derivatives, which each provider's page says what we know of.

## The hosted instance

[wetterdienst.eobs.org](https://wetterdienst.eobs.org) runs the REST API, the MCP endpoint and the web app, for anyone,
without an account. What that means for the data:

- **It passes the data on.** Every answer is the provider's data, reshaped as above, handed to whoever asked. Most
  providers' terms let the data be copied or reused with the source named. Three need a look: IMGW (CC BY-NC-ND 4.0, see
  its page), LHMT (CC BY-SA 4.0, share-alike) and IPMA, whose conditions cover copying and use and not passing on, and
  exclude profit-making ends. Each answer carries the licence, the credit line and the processing note in its `metadata`
  block and in `X-Wetterdienst-*` headers (the web app does not show them yet, see
  [#3799](https://github.com/earthobservations/wetterdienst/issues/3799)).
- **It caches for everyone.** One cache serves all callers, so where a network keeps its values (above), a file is
  downloaded once per lifetime however many ask; WSV's values and EA's station lookups are downloaded for each question.
  The server sends no `Cache-Control` for values and stations; see [Caching](../../usage/restapi.md#caching).
- **It limits what costs something.** The web app counts requests per client (300 in 300 seconds by default, see
  [Rate limit](../../usage/app.md#rate-limit)); there is no limit that follows a provider's own limit.
- **It holds the keys of the four providers that need one**, and keeps serving them. Read from its public
  `/api/coverage` on 2026-11-06 (that list is `/api/providers` now), `aemet`, `knmi`, `metoffice` and `metno` report `configured: true` there. Whether that
  is within their terms is not settled; the question was put to KNMI and CEDA in November 2026 and no answer has come
  yet (see the next section).
- **Its logs and the data protection of its users** are in the privacy policy of the app, not here.

## Keys and credentials

Four providers need a key or an account: AEMET (API key), KNMI (EDR API key), the Met Office's MIDAS Open (a CEDA account,
from which the library mints a token valid for three days) and MET Norway's Frost (a client ID). What each states about
sharing the key and about serving others with it, quoted at the License section of the provider:

| Provider | What the terms say | Does a server that answers others with one key fit? |
| --- | --- | --- |
| [AEMET](aemet/index.md#license) | The key "identifies" the user; as many may be created as needed; an e-mail address is asked. Nothing on sharing, nothing on serving others. | Not addressed by the pages read. |
| [KNMI](knmi/index.md#license) | "Accounts and keys are personal. They are meant to be used by you or by your organisation for your own applications, and should not be shared with, resold to, or distributed to third parties." And: "If you want to serve KDP data to your own users, proxy the requests through your own backend, keep the key there, and add caching in your backend." | Not settled: the question was put to KNMI in November 2026 and no answer has come yet. Our reading: a backend with a key and a cache is the pattern KNMI names; an open server for anyone may be more than "your own users". |
| [Met Office](metoffice/index.md#license) (CEDA) | "Not to use another person's account, nor to let other people use your accounts, except by agreement with us"; "Only to use the service/resource for the purposes for which you were given access". | Not settled: the question was put to CEDA in November 2026 and no answer has come yet. Our reading: others use the server, not the account. |
| [MET Norway](metno/index.md#license) (Frost) | "Each client ID must be associated with a valid email address"; "Use a proxy if possible"; "Heavy traffic means on average more than 1 requests to the API per second": then "save the information on your own server", and contact them if you "have not been able to reduced the amount of requests by taking into account our guidelines". The weather API's terms (a different service) call "trying to circumvent traffic rate limiting measures and/or impersonating traffic from other clients" abuse. | A proxy with a cache is asked for; what counts is the rate on average, which is not measured here. |

None of the four says in terms that serving others from one key is allowed or forbidden. We have not used any key to
read what a key's response says.

## The repository's own files

The repository holds real provider data of two kinds: excerpts in the tests, and a few images in the docs. **The MIT
licence (`LICENSE.md`) covers the code and what the project wrote, and does not cover this data.** The data keeps the
licence and the credit line of its provider, which MIT neither replaces nor lifts, and which the repository did not say
until this page. This section is the notice. Anyone who takes the repository, or a package built from it, takes the data
with the terms of its provider.

| Where | What | Provider, terms and credit |
| --- | --- | --- |
| `tests/provider/dwd/radar/files/` | nine real radar files of 2026-10-20 to 22, the smallest of their product (composites and a volume scan as HDF5, two `meso` and one `KONRAD3D` XML), 550,338 bytes | DWD, CC BY 4.0, "Source: Deutscher Wetterdienst" |
| `tests/provider/dwd/alerts/files/` | one DWD warning in CAP form (a fog warning for Kreis Wittenberg, 2026-11-05, in eight languages) with the polygon of its one area cut to 5 of its 124 points, 16 kB | DWD, CC BY 4.0, "Source: Deutscher Wetterdienst"; the wording is DWD's |
| `tests/provider/dmi/observation/` | four JSON files of DMI readings and parameter lists (hourly, daily, monthly and annual values), 85 kB | DMI, CC BY 4.0, "© DMI (Danish Meteorological Institute)" |
| `tests/provider/knmi/observation/files/` | five real answers of KNMI's EDR API (De Bilt and Schiphol, a day to a year of each resolution) cut to the variables the provider maps, and the rows the Open Data files route made of them before GH-3928, 10 CSV files, 247 kB | KNMI, CC BY 4.0, "© KNMI" |
| `tests/provider/noaa/ghcn/` | two CSV files of GHCN-Daily elements, 1.3 kB | NOAA NCEI, CC0 1.0 |
| `tests/provider/station_catalogue_stubs.py`, `tests/provider/value_stubs.py` and the inline text of the tests of each provider | rows of the real station lists and of real values, a few per network, in the provider's own format; some rows are edited (below) | the licence and credit line of that provider on [licences and credit lines](licenses.md) |
| IMGW rows of the same files and of `tests/provider/imgw/` | a few dozen rows of station lists and daily values, some of them edited | IMGW, CC BY-NC-ND 4.0; credit: „Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy” and „Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone” |
| LHMT rows of `tests/provider/lhmt/` | a few rows of observations, some of them edited | LHMT, CC BY-SA 4.0, credit "Lietuvos hidrometeorologijos tarnyba (LHMT)" |
| `docs/assets/readme-stripes.png`, `summary.png`, `interpolation.png` and the output cells of the docs and the README | charts drawn from, and tables of, DWD values | DWD, CC BY 4.0, "Based on data from Deutscher Wetterdienst" |
| `src/wetterdienst/provider/eumetnet/opera/sites.json.gz` (shipped in the package) | the 205 OPERA radar sites of EUMETNET's database, those with a location and a position, with their numbers converted from text | EUMETNET's [OPERA database](https://www.eumetnet.eu/wp-content/themes/aeron-child/observations-programme/current-activities/opera/database/OPERA_Database/index.html) page states no licence |

The two IMGW sentences are IMGW's own (§ 5 ust. 3 and 4 of its terms, in Polish); the first names the source, the second
says the data were processed, which they are. The same two sentences stand beside the IMGW rows in the code.

Our reading:

- **Edited rows.** Most rows are real ones copied as they are; some are not. A test of `imgw/meteorology` serves a real
  station-list row with the river left blank, an elevation written `brak` or `1 987`, to see what the reader makes of
  them; `value_stubs.py` says that the sentinels of an IMGW daily row are "worded after the reader" and are not those of
  the file's own rows; an LHMT row (vilniaus-ams, 2020-07-01 12:00, compared with the feed on 2026-11-06) has
  `precipitation` `null` where the feed has 0, and `cloudy` where it has `cloudy-with-sunny-intervals`. These are adaptations, which bears on the NoDerivatives condition of IMGW's
  licence and the share-alike one of LHMT's: we do not claim that they are within either. The tests need the edits.
- **Credit and licence** are what most providers ask for (CC BY, OGL, ECCC's licence, AEMET's notice: the source, a note
  of changes; DL-DE-Zero and CC0 ask for neither), and the data are facts in a few rows of a list or a series. This
  section gives the credit; the files themselves cannot carry it.
- **The DWD warning** is a real message with the polygon of its area cut. DWD's rule is that "If any of the official
  weather warnings issued by the DWD is changed, the source details provided with the data/services have to be
  deleted" ([rules](https://www.dwd.de/EN/service/legal_notice/templates_dwd_as_source.html)); a test file that is
  published as no warning is not what the rule is about, in our reading, which is not DWD's.
- The OPERA list has no stated licence.

The rows stay, named and credited here; replacing the IMGW and LHMT ones with invented rows of the same shape would be
the other way. The OPERA list is not settled: EUMETNET's page states no licence, the question was put to EUMETNET in November 2026
and no answer has come yet. A test
(`tests/test_provider_terms.py`) holds the first table of this page to the registry, so that a provider added without a
row fails it, and this section to the data files that are in the tests.

## Our reading

- The credit line and the licence of every answer are the providers'. Wetterdienst reports them, and passes them on in
  every answer that holds data; it cannot make a user publish them.
- The data is changed, as above, and every answer says it; a CSV written without `with_metadata=True` does not. Where
  you publish data or a chart of it, give the credit line and say that it was processed.
- Caching a provider's files for your own use needs nothing beyond its licence. Serving them to others is
  redistribution: it needs the credit line, the licence and the note of changes to go with the data, which the hosted
  instance's answers carry, and the provider's terms on use of its service to be kept, which the table above lists. Where
  a limit is shared by everyone a server answers (LHMT's, at least), that is a limit on the server. For KNMI, the Met
  Office, MET Norway and AEMET it is a key whose sharing is not settled above.
- Where a provider's text can be read two ways, the page says so and leaves it. Of the providers' own confirmations
  there is one: IMGW-PIB told the maintainers in November 2026 that the data it classes as high-value are free for any
  use under CC BY 4.0 and that all its other data are public-sector information under CC BY-NC-ND 4.0. It did not say
  which of the two the files read here are, nor how the licence's NoDerivatives condition applies to wetterdienst's
  reshaping; the page of IMGW has what follows from that. ECCC's API names its licence, which is a statement of ECCC's
  and no confirmation of our reading of it.
