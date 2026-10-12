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

This project is a data-fetching library and REST API. Relevant areas include:

- Remote code execution or command injection via user-supplied input
- Dependency vulnerabilities (please check [Dependabot alerts](https://github.com/earthobservations/wetterdienst/security/dependabot) first)
- REST API authentication or data exposure issues

Out of scope: vulnerabilities in upstream data provider services (DWD, NOAA, etc.).

## Threat model of the backend

The backend is the library, the CLI, the REST API (`wetterdienst restapi`) and the MCP endpoint that
the REST API serves at `/mcp`. The REST API and MCP have no authentication; whoever reaches them is
the caller below. The library and the CLI trust their caller, who is the host's own user.

### What it defends against

A caller of the REST API or MCP cannot, with any request:

- read or write a file on the host, or make the server fetch a URL of the caller's choosing. The
  provider and network are looked up in a fixed registry, station ids are joined to the provider's
  own catalogue, parameters are checked against its metadata, and dates are parsed; no caller value
  becomes a URL, a path or code. Archives and XML from the providers are read in memory, with XML
  entities off; nothing is unpickled, evaluated or loaded from YAML that a caller sent.
- run SQL on the host unless the operator sets `WD_RESTAPI_SQL=true`, and then only a filter on a
  DuckDB connection that cannot read files, reach the network or load extensions (the
  [REST API docs](https://wetterdienst.readthedocs.io/en/latest/usage/restapi.html) list its limits).
- read a provider credential. Credentials are `SecretStr`, are left out of the settings the API
  reports, and are scrubbed from retry logs and exceptions. A caller can learn that a key is
  configured and accepted (`/api/auth`, `/api/coverage`), not the key.
- reach an image size that holds a browser for long: a chart is refused above 8192 px on a side.

The dependencies are locked with hashes in `uv.lock` and audited by `uv audit` in CI. The workflows
default to empty permissions, the Docker image runs as an unprivileged user, and PyPI releases are
published with trusted publishing.

### What it leaves to the operator

- **Who may use it.** Anyone who reaches the API can use the provider credentials it is configured
  with and spend their quotas. Put an authenticating gateway in front of a server that holds keys.
- **Limits on the work of one request.** A request can make the server download and compute a lot
  (all stations of a network, a long window at a fine resolution). Few of these are bounded by the
  API; set a timeout, a concurrency limit and a memory limit in a reverse proxy or on the container.
- **Transport.** TLS and CORS: the server speaks plain HTTP and sets no CORS headers.
- **`WD_RESTAPI_SQL=true`.** It lets a caller run DuckDB filters that are bounded per request, not
  for the server as a whole.
- **The cache directory.** `WD_CACHE_DIR` holds files the server reads back, among them pickled
  directory listings (diskcache); whoever can write there can run code as the server. Keep it
  private to the user the server runs as.
- **Export targets and the CLI.** `--target`, `to_target` and the connection strings they take are
  used as given: a table name is put into SQL as written, and a path is written where it says.
