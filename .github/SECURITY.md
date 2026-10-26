# Security Policy

## Supported Versions

Only the latest release receives security fixes. We do not backport patches to older versions.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/earthobservations/wetterdienst/security/advisories/new) or by emailing **benjamin.gutzmann@pm.me**.

Include as much detail as possible:

- Description of the vulnerability and potential impact
- Steps to reproduce or proof-of-concept
- Affected version(s)

We aim to acknowledge reports within **72 hours** and provide a resolution timeline within **7 days**.

## Scope

This project is a data-fetching library, a CLI, a REST API with an MCP endpoint, and a web app. Relevant areas include:

- Remote code execution, file access or command injection via a request to the REST API or MCP, or via data an
  upstream provider sends
- A caller reaching a provider credential, or making the server fetch from a host or read a path of the caller's choice
- The app running a script that is not its own, or passing a client's cookies or credentials to the backend
- Dependency vulnerabilities (please check [Dependabot alerts](https://github.com/earthobservations/wetterdienst/security/dependabot) first)

Out of scope: vulnerabilities in upstream data provider services (DWD, NOAA, etc.); the REST API having no
authentication, TLS or CORS headers, which is [by design](#the-rest-api-and-mcp); a caller of the library or the CLI
doing what the host's user may do; anyone who can already write to the cache directory or set the server's environment.

## Release provenance

What a release publishes to show where it was built, and how to check it. All of it is made by the release
workflows of this repository (`release.yml`, `docker-publish.yml`, `docker-publish-app.yml`); none of it exists for
releases made before it was added.

- **PyPI.** Each wheel and sdist carries a [PEP 740](https://peps.python.org/pep-0740/) publish attestation, signed
  with the identity of the trusted-publisher job of `release.yml` through Sigstore. PyPI shows it on the file's page
  and serves it at `https://pypi.org/integrity/wetterdienst/<version>/<file>/provenance`. To check a file against
  this repository:

  ```bash
  uvx pypi-attestations verify pypi --repository https://github.com/earthobservations/wetterdienst \
      pypi:wetterdienst-<version>-py3-none-any.whl
  ```

  `pip download wetterdienst==<version> --no-deps` followed by the same command with the downloaded path verifies the
  file you hold.
- **Images** (`ghcr.io/earthobservations/wetterdienst` and `ghcr.io/earthobservations/wetterdienst-app`). The manifest
  list of each release has a SLSA build provenance, signed with the GitHub Actions identity of the workflow that
  built it through Sigstore (a certificate of the public-good Sigstore instance, recorded in its transparency log).
  This checks that the image you pulled is the one that workflow pushed:

  ```bash
  gh attestation verify oci://ghcr.io/earthobservations/wetterdienst:<version> --repo earthobservations/wetterdienst
  ```

  BuildKit also attaches, to each platform, an unsigned provenance (`mode=max`) and an SBOM, as extra manifests of
  the image index (they list as `unknown/unknown`). They describe the build and its contents; being unsigned they are
  only as trustworthy as the registry:

  ```bash
  docker buildx imagetools inspect ghcr.io/earthobservations/wetterdienst:<version> --format '{{json .Provenance}}'
  docker buildx imagetools inspect ghcr.io/earthobservations/wetterdienst:<version> --format '{{json .SBOM}}'
  ```

An attestation says which workflow and commit produced an artifact, not that the code is free of defects, and the
dependencies in the image or the wheel are not vetted by it.

## Threat model

What the project defends against and what it leaves to whoever runs it, checked against the code and the tests named.

**Assets:** the provider credentials a host configures (`WD_AUTH__*`) and the quotas behind them; the host's files,
memory, CPU and outbound connections; the cache directory; the browser of an app user.

**Trust boundaries:**

1. *Library and CLI.* The caller is the host's own user and is trusted: no limits, `sql` filters ungated, export targets
   (`--target`, `to_target`) used as given. No REST or MCP parameter reaches one (`extra="forbid"` in `ui/core.py`).
2. *REST API and MCP* (`wetterdienst restapi`; `/mcp` is the same app, stateless, present with the `[mcp]` extra). The
   caller is anonymous and untrusted. Every route of `/api` is a `GET`.
3. *The app* (`app/`). Its Nuxt server proxies `/api`, `/mcp`, `/docs` and `/openapi.json` to the backend at
   `NUXT_API_BASE`; the browser calls its own origin only. It holds no secret.
4. *Upstream providers.* Their addresses are fixed in the provider's code, but for the links a few of them follow and
   the redirects any of them answers with, both held to the provider's own hosts (see [Upstream data](#upstream-data));
   what they send is data, never trusted.

### The REST API and MCP

It is open by design: **there is no authentication**, and none is planned in the server. Whoever reaches it can use
every provider credential it holds and spend its quotas. `/api/auth` and `/api/coverage` say whether a credential is
configured (and accepted), never what it is. A server that holds keys or is reachable beyond its operator's network
belongs behind a gateway that authenticates, terminates TLS and rate-limits per client.

**CORS.** The backend sets no CORS headers and has no setting for them (`ui/restapi.py` adds no CORS middleware), so a
browser page of another origin cannot read its answers: serve such a page from the backend's origin, or have the
reverse proxy add the headers. A setting can come later without breaking anyone. The app's server answers no CORS
header either, unless `NUXT_CORS_ALLOWED_ORIGINS` names the origin (`app/server/utils/cors.ts`).

What the server enforces itself (`docs/usage/restapi.md`, `ui/middleware.py`; `tests/ui/test_operations.py`):

- **Host and Origin.** `WD_RESTAPI_ALLOWED_HOSTS` lists the `Host` names it answers to (any other is a 400) and the
  `Origin` of an MCP request. `wetterdienst restapi` on a loopback address lists the loopback names itself, against
  DNS rebinding; any other address, and the Docker image (`0.0.0.0`), answers to every host until it is set.
- **Limits, refused before any download:** 100 stations, 500,000 rows (10,000,000 streamed), a chart side of 8192 px
  (`WD_RESTAPI_MAX_*`; `0` switches one off), as a 400 that says how to narrow the request. For `interpolate` and
  `summarize` the stations are those with a record in the window within the radius, which is bounded (`ui/core.py`, `tests/ui/test_geo_bounds.py`).
- **Timeout and concurrency:** 60 s (`WD_RESTAPI_TIMEOUT`, a 504), 32 requests at once (`WD_RESTAPI_MAX_CONCURRENT`, a
  503). A timed-out request's thread runs on but keeps its slot, so the cap bounds the threads. There is **no
  per-client rate limit**; that is the proxy's job (the app has one, `docs/usage/app.md`).
- **`sql` and `sql_values`** are a 403 unless `WD_RESTAPI_SQL=true`, on every route and MCP tool that takes them
  (`test_sql_gate_covers_every_route_taking_sql`). Enabled, the clause is one condition on the frame, in DuckDB with
  external access off and the configuration locked, on one thread with 1 GiB (`io/export.py`; `tests/test_io.py`:
  `test_filter_by_sql_cannot_read_files`, `test_filter_by_sql_cannot_reach_the_network`). It can still read DuckDB's
  settings, run long and allocate outside the limit, per request: enable it for clients you trust with that
  (GHSA-rpwr-qmm5-m9wp; those documented limits are settled). The `duckdb` floor is 1.1.0, the first release
  where `sniff_csv` obeys that setting (GHSA-w2gf-jxc9-pf2q; `test_filter_by_sql_cannot_read_files[sniff_csv]`).
- **Errors** are RFC 9457 problems. A 500 is a fixed body with no path, traceback or credential, and a 501 for a missing
  credential does not name the setting (`test_a_500_does_not_name_the_servers_paths_but_the_log_does`).
- **Response headers** (GH-3349; `ui/middleware.py`, `ui/problems.py`; `tests/ui/test_security_headers.py`). Every
  answer carries `X-Content-Type-Options: nosniff`, errors and streams included. A `Content-Security-Policy` goes with
  the index page (`default-src 'none'; style-src 'unsafe-inline'; ...`) and the `svg` answers (`default-src 'none';
  style-src 'unsafe-inline'; img-src data:`), the two whose bodies were read for what they need. It is not sent with
  the data answers, where it has nothing to guard, nor with `pdf` and the other images, nor with `/docs` and `/redoc`,
  which load Swagger UI and ReDoc from a CDN, nor with `format=html`: that is a Plotly figure whose script is in the
  page, so a policy that lets it run guards little and was not checked in a browser. The backend's origin holds no
  cookie or credential, so this is hardening: Plotly escapes `<` in the JSON of a figure, and no free text of the
  caller is drawn into one. HSTS, `Referrer-Policy` and a policy for the rest are for a reverse proxy.

What it does not do:

- **Text from an upstream is not filtered, for an MCP client too.** The tools answer what the REST routes answer:
  station names, the free text of DWD alerts (`headline`, `description`, `instruction`), the remarks and instruments of
  a station's history. That text is the provider's, and to a language model that reads it, it is untrusted input: it may
  contain instructions, and nothing here removes or marks them. Whoever connects an agent to this endpoint along with
  tools that can act (send, write, run, fetch) should not let it follow what such a field says.

### Credentials

From `WD_AUTH__*` or `Settings(auth=...)`, held as `SecretStr`. `/api/settings` and the response metadata leave them
out (`test_no_credential_or_cache_setting_is_reported`); `Settings` and its client kwargs render masked, and retry
logs leave them out (`tests/test_settings.py`: `test_credentials_do_not_appear_in_what_settings_render`,
`test_a_retried_listing_does_not_log_the_credentials_in_the_settings`).

### Upstream data

Providers are trusted for their address, not their content. Provider and network come from a fixed registry, parameters
are checked against its metadata, and a station is checked before it becomes part of a URL (GH-3084). Their address is
not the whole story: seven providers (AEMET, KNMI, NWS, Hub'Eau, MeteoSwiss, Météo-France and EA) fetch a URL that the
upstream's answer names (a `next` page, a `datos`, measure or asset link). Each provider has a list of its own hosts
(`PROVIDER_HOSTS`, `util/provider_hosts.py`: the API and, where the files are served from another host, that host, such
as the S3 bucket of KNMI's pre-signed links and the object store of Météo-France's files). Such a link is fetched only
at a host of the provider that the request started at, over `https` (an `http` link is read as `https`) and on the
default port (`fetchable_link`, `util/network.py`; GH-3339). A redirect is followed only to a host of that provider,
never from `https` down to `http`, whatever the session holds (`_check_redirect`; 0.174.0 let a session without a
credential follow that hop, withdrawn in GH-3400). A credential header, whatever its name, is dropped where it changes
the origin (GH-3338, GH-3339); a refused link or redirect is a `DownloadError` that names the host and the provider. A
request that started at data.gouv.fr and is redirected to `sorry.data.gouv.fr`, its maintenance page, is told before
the host bound and is a `DownloadError` that says the site is in maintenance. A host that no provider lists (a test
server, an address a caller fetches by hand) is held to its
registered domain, told without the public suffix list (`gov.uk`, `data.gouv.fr` and a few more labels are treated as
suffixes, and a name under `amazonaws.com` or `ovh.net` is its own domain). A host name is not resolved, so **an
upstream that is compromised can still make the server fetch from the hosts of its own provider**, and a name of one of
them pointing at an internal address would be fetched. A link in an HTML directory listing is kept only below the
listed directory, on its host, and not where it steps from `https` down to `http`. `file://` and bare paths are refused
by the HTTP client.

XML is parsed with entities off, no network and no DTD, each option passed rather than left to a default
(`util/xml.py`, the one parser of FMI, DWD alerts, MOSMIX and DMO; a test fails for a module that builds its own).
Archives are read in memory. Apart from the cache directory (below) and what the host asks the library or the CLI to
write (`--target`, `to_target`, an output path; no REST or MCP parameter reaches these), the files written are the BUFR
message, in a private temporary directory that is removed afterwards (`util/eccodes.py`, `dwd/road`), and the temporary
directory and browser profile of the headless Chromium that renders a chart to an image (`png`, `jpg`, `webp`, `svg`,
`pdf`; kaleido), which a REST or MCP request can start. Nothing is unpickled, evaluated or loaded from YAML that a
caller or provider sent. The native parsers (eccodes, lxml, polars) are dependencies with advisories of their own. Wrong
numbers from a provider are a data-quality problem, not a vulnerability (`tests/provider/physical_ranges.py` catches the
sentinels it can).

### The cache directory

`WD_CACHE_DIR` (default: the user's cache directory, or a per-process temporary one where none resolves) holds the
downloaded bodies it caches, as files named by the hash of their URLs, and the directory listings, which are JSON in
a SQLite file (`listings-v1.sqlite3`, one per TTL; `util/listing_cache.py`). Nothing in the cache is unpickled,
evaluated or imported (the metadata file of fsspec's download cache is JSON only from fsspec 2026.6.0, the floor
since GH-3326; earlier versions fell back to `pickle` for it): a listing that is read is parsed as JSON and must be
a list of objects, and a row that is anything else is dropped
(`tests/util/test_listing_cache.py::test_a_row_that_is_no_listing_is_dropped_not_returned`,
`tests/util/test_network.py::test_file_dir_cache_never_unpickles_what_diskcache_left`).
Whoever can write there can still fill the cache with listings that are not the provider's, or delete it, but can no
longer run code through a deserializer (the SQLite file is also read from there, with `trusted_schema` off,
`cell_size_check` on and, from Python 3.12, defensive mode); the downloaded bodies are data that is parsed like any
other download. Where the directory cannot be written, a temporary directory of the process takes its place until it
exits (with a warning); the directory in use also gets a write probe, removed at once, and a usage marker.

A directory that wetterdienst makes (the cache directory and the directories above it that are missing) gets mode
`0o700`, the database file `0o600`, on systems that enforce modes; a directory that exists is never changed, so make a
shared one private yourself. Keep it private to the user the server runs as. The image's cache belongs to its
unprivileged user (uid 10001, `docker/Dockerfile`); the app image runs as `node`.

**`diskcache` is no longer a dependency** (GH-3326). It stored the listings with `pickle` and had an advisory with no
fixed version and no maintainer commit since 2024 (Dependabot alert 83, GHSA-w8v5-vhqr-4h9v / CVE-2025-69872, `<=
5.6.3`), which `pyproject.toml` ignored in `uv audit` until now. Its files in an old cache directory are never read as
a cache. The clean-up that removes them, once nothing has written them for an hour, opens `cache.db` read-only and
immutable to look at the names of its tables, and reads nothing else from it.

### The app

No secret: the backend URL is a private key of Nuxt's runtime config (`NUXT_API_BASE`, GH-3096), so no page carries
it (the old public `NUXT_PUBLIC_API_BASE` is read as a deprecated fallback),
and the server forwards neither cookies nor `Authorization` to the backend (`app/tests/unit/mcp-proxy.test.ts`). The page runs under a Content Security Policy with
a nonce per response, no `'unsafe-inline'` or `'unsafe-eval'` for scripts, and scripts, workers and requests on its own
origin (`app/tests/e2e/csp.spec.ts`, `app/tests/unit/security-headers.test.ts`). Nothing the browser runs comes from a
CDN, so there is no third-party script for subresource integrity to cover; only map tiles, avatars and marker images
come from other hosts. There is no `v-html` or `innerHTML`, so provider text renders as text. The app stores UI settings
(`wd_settings`) in `localStorage` and the language in a cookie, no data. The compose file's app is the dev server, for
development, not exposure (#3096).

Who may frame a page: only the app's own origin (`frame-ancestors 'self'` and `X-Frame-Options: SAMEORIGIN`), except
for `/widget`, which any origin may frame because it is meant to sit on other sites. The server decides on the request
line it receives (`/widget` or `/widget/`, with or without a query, nothing decoded), not by a route rule, which
matches the decoded path (`/%77idget`); a plugin sets the two headers after nuxt-security's
(`app/server/plugins/widget-frame.ts`). That is the first layer. A proxy that rewrites the path before it forwards it
(decoding `%77`, collapsing `//`, resolving `..`) presents the server with `/widget` for an address that is not, so it
can still serve the app's shell with the relaxed headers. The second layer is the page, which knows the address it
was loaded at: framed by another origin (any ancestor of another origin counts, not only the top window), it draws
nothing outside the widget's route, not even the text of a 404, and makes no request of the backend while it draws
nothing (`app/app/utils/frame-guard.ts`, `app/app/app.vue`, `app/app/error.vue`; `app/tests/unit/frame-guard.test.ts`,
`app/tests/nuxt/pages/error.test.ts`, `app/tests/e2e/csp.spec.ts`). The widget reads one station's forecast through
three `GET` requests of the app's own origin (the backend's version, the station, its values) and holds nothing a
visitor enters or the app keeps. What can be clicked in it is two links that open in a new tab and, where the chart
could not be drawn, a button that draws it again and one that reloads the frame. Its assets are subresources, not
documents, and keep the headers they had.

The rate limit counts the address of the connection; a header names the client only where the operator sets
`NUXT_RATE_LIMIT_CLIENT_IP_HEADER`, which is right only if the proxy in front writes it and nothing reaches the app
without that proxy (`docs/usage/app.md`, `app/tests/unit/rate-limit.test.ts`).

### Supply chain

`uv.lock` pins every dependency with hashes; a release younger than 3 days is not taken (`exclude-newer`). `uv audit`
runs when the lock changes and weekly (`vulnerable.yml`), `dependency-review.yml` on pull requests, CodeQL and zizmor on
code and workflows; Dependabot proposes uv, npm, Docker and Actions updates weekly. Actions are pinned to a commit SHA
and base images to a digest (`.github/workflows/README.md`); workflows default to `permissions: {}` (read-only at most). A release builds
in a job without `id-token` and publishes to PyPI by trusted publishing in a job that runs no project code (`release.yml`).

### The emSign CA incident (October 2026)

The intermediate certificates under the `emSign ECC Root CA - G3` (eMudhra) have compromised keys, and whoever holds one
can impersonate any HTTPS host to a client that trusts the root
([discussion](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576),
certifi GHSA-6q48-6c7w-9gw2, uv GHSA-hq85-5cpj-mr62). wetterdienst verifies TLS against the trust store of the Python it
runs on, or against the certifi bundle with `use_certifi` (`WD_USE_CERTIFI`, off by default). Affected is therefore a host
whose trust store still holds the root, or that runs `use_certifi` with certifi older than 2026.10.19. From 0.171.0 on,
wetterdienst requires certifi 2026.10.19 and the Docker image is built on a python base image with Debian's
`ca-certificates` update and pip 26.2.2 (GH-3331). An installation from PyPI resolves its own certifi, and the earlier
releases and images keep the old one. To update:

- `pip install --upgrade certifi`; for the system store, the operating system's update (Debian: `ca-certificates`); with
  the python.org installer on macOS, run its `Install Certificates.command` again;
- pip 26.2.2 or later and uv 0.13.4 or later, which carry their own bundle (`uv self update`, or the package manager that
  installed it);
- the Docker image: `docker pull` the new tag, and rebuild an image of your own on top of it with `docker build --pull`.
