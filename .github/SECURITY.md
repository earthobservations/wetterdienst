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
- Dependency vulnerabilities (please check [Dependabot alerts](https://github.com/earthobservations/wetterdienst/security/dependabot)
  and the accepted `diskcache` advisory below first)

Out of scope: vulnerabilities in upstream data provider services (DWD, NOAA, etc.); the REST API having no
authentication, TLS or CORS headers, which is [by design](#the-rest-api-and-mcp); a caller of the library or the CLI
doing what the host's user may do; anyone who can already write to the cache directory or set the server's environment.

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
   `NUXT_PUBLIC_API_BASE`; the browser calls its own origin only. It holds no secret.
4. *Upstream providers.* Their addresses are fixed in the provider's code; what they send is data, never trusted.

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
  (`WD_RESTAPI_MAX_*`; `0` switches one off), as a 400 that says how to narrow the request.
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

### Credentials

From `WD_AUTH__*` or `Settings(auth=...)`, held as `SecretStr`. `/api/settings` and the response metadata leave them
out (`test_no_credential_or_cache_setting_is_reported`); `Settings` and its client kwargs render masked, and retry
logs leave them out (`tests/test_settings.py`: `test_credentials_do_not_appear_in_what_settings_render`,
`test_a_retried_listing_does_not_log_the_credentials_in_the_settings`).

### Upstream data

Providers are trusted for their address, not their content. Provider and network come from a fixed registry, parameters
are checked against its metadata, and a station is checked before it becomes part of a URL (GH-3084). XML is parsed
with entities off and no network (`resolve_entities=False`: FMI, DWD alerts, MOSMIX, DMO), archives are read in memory,
and the one file written is the BUFR message, in a private temporary directory removed afterwards (`util/eccodes.py`,
`dwd/road`). Nothing is unpickled, evaluated or loaded from YAML that a caller or provider sent. The native
parsers (eccodes, lxml, polars) are dependencies with advisories of their own. Wrong numbers from a provider are a
data-quality problem, not a vulnerability (`tests/provider/physical_ranges.py` catches the sentinels it can).

### The cache directory

`WD_CACHE_DIR` (default: the user's cache directory, or a per-process temporary one where none resolves) holds the
directory listings, which `diskcache` stores with `pickle`: whoever can write there can run code as the process. Keep it
private to the user the server runs as. The image's cache belongs to its unprivileged user (uid 10001,
`docker/Dockerfile`); the app image runs as `node`.

**Dependabot alert 83 (`diskcache`, GHSA-w8v5-vhqr-4h9v / CVE-2025-69872, `<= 5.6.3`, no patched version).** It applies:
the listings cache is that pickle. Exploiting it takes write access to the cache directory, which the operator controls,
so `pyproject.toml` ignores it in `uv audit` (`ignore-until-fixed`: only until a patched version exists). The
alert stays open until then.

### The app

No secret: the backend URL is public by name (`NUXT_PUBLIC_API_BASE`), and the server forwards neither cookies nor
`Authorization` to the backend (`app/tests/unit/mcp-proxy.test.ts`). The page runs under a Content Security Policy with
a nonce per response, no `'unsafe-inline'` or `'unsafe-eval'` for scripts, and scripts, workers and requests on its own
origin (`app/tests/e2e/csp.spec.ts`, `app/tests/unit/security-headers.test.ts`). Nothing the browser runs comes from a
CDN, so there is no third-party script for subresource integrity to cover; only map tiles, avatars and marker images
come from other hosts. There is no `v-html` or `innerHTML`, so provider text renders as text. The app stores UI settings
(`wd_settings`) in `localStorage` and the language in a cookie, no data. The compose file's app is the dev server, for
development, not exposure (#3096).

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
