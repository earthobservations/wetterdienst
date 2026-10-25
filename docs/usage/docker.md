# Docker

The wetterdienst Docker image comes with several extras installed so you can use most of the features out of the box:
- bufr
- cratedb
- duckdb
- export
- influxdb
- interpolation
- knmi
- mcp
- plotting
- postgresql
- radar
- radarplus
- restapi

## Acquire image

Get ``wetterdienst``:

```bash
docker pull ghcr.io/earthobservations/wetterdienst
```

## Invoke

Run Wetterdienst command line interface:

```bash
docker run -it --rm ghcr.io/earthobservations/wetterdienst wetterdienst --version
```

Run Wetterdienst HTTP REST API service:

```bash
docker run -it --rm --publish=7890:7890 ghcr.io/earthobservations/wetterdienst wetterdienst restapi --listen 0.0.0.0:7890
```

The image listens on port 7890 when it is started without a command, as `wetterdienst restapi` does
outside Docker, so `docker run --publish=7890:7890 ghcr.io/earthobservations/wetterdienst` serves the API.
Images up to 0.158.0 listened on 3000 instead: a deployment that mapped `3000:3000` has to map
`3000:7890` to keep its host port (or move to `7890:7890`), and a health check or proxy that asks the
container for port 3000 asks for 7890. The [MCP server](mcp.md) is served next to it, at `/mcp/v1`.

The image has a `HEALTHCHECK` that asks `/health` every 30 seconds (every second during the first 60
seconds, on Docker 25 or later), and `docker ps` shows the container as `healthy` or `unhealthy`. The
probe follows the port the server listens on, 7890 by default and 3000 where a start command says so,
for a server listening on all interfaces or on loopback: it looks for the listening TCP sockets of the
container and is healthy when `/health` answers on one of them. A server bound to one container address
is not reached that way, and the probe is meant for a container that runs one server, not one that
shares the network namespace of the host or of another container (`--network host`).

When a platform defines a health check of its own, it replaces the image's. Where it defines none
(Coolify's default), the image's check is what a proxy such as Traefik routes by: it sends traffic only
to containers that are healthy or have no health state. `docker run --no-healthcheck` or, in a Compose
file, `healthcheck: { disable: true }` switches the image's check off.

The app has an image of its own, `ghcr.io/earthobservations/wetterdienst-app`, see [Web app](app.md#run-your-own).

## Docker Compose

`compose.yml` of the repository builds the development images. `docker compose --profile backend up`
serves the API on <http://localhost:7890>, `--profile app up` the app on <http://localhost:4000>, and
`--profile full up` both, the app asking the backend at `http://backend:7890/api` on the compose network
(`NUXT_PUBLIC_API_BASE`). The host ports are the container's own, 7890 and 4000.

Both ports are published on `127.0.0.1` only, so the API and the app (a development server with
Nuxt DevTools) answer on the machine that runs compose and not on its network. To reach them from
another machine, set `WETTERDIENST_BIND_HOST` to the address to listen on, in the shell or in the
`.env` of the repository (`WETTERDIENST_BIND_HOST=0.0.0.0` is every interface; the default is
`127.0.0.1`):

```bash
WETTERDIENST_BIND_HOST=0.0.0.0 docker compose --profile full up
```

The services reach each other by name on the compose network, which this does not change. To publish
one on another host port, give it in a `compose.override.yml`
(`ports: !override ["127.0.0.1:3000:7890"]`, without the address it is published on every interface)
rather than in `compose.yml`.

## User and cache

The image runs as the unprivileged user `wetterdienst` (uid 10001), whose cache is
`/home/wetterdienst/.cache/wetterdienst`. To keep the cache across runs, mount a volume there, or
mount it anywhere and point `WD_CACHE_DIR` to it; it has to be writable by uid 10001.

```bash
docker run -it --rm --publish=7890:7890 --volume wetterdienst-cache:/home/wetterdienst/.cache/wetterdienst ghcr.io/earthobservations/wetterdienst wetterdienst restapi --listen 0.0.0.0:7890
```

### Upgrading from an image that ran as root

A volume or host directory that an earlier run as root filled (any image before 0.148.0) keeps its
owner, and the user cannot write to it. The container cannot repair that itself: a user that is not
root cannot change the owner of a mount. Without the fix below, wetterdienst warns once, naming the
directory and the reason (for the cache database, `attempt to write a readonly database`), and
keeps its cache in a temporary directory instead. Requests then work, but nothing is kept across
runs. Fix the volume once, on the host:

```bash
docker run --rm --user 0 --volume wetterdienst-cache:/c ghcr.io/earthobservations/wetterdienst chown -R 10001:10001 /c
```

or, if the cache is not worth keeping, remove the volume (`docker volume rm wetterdienst-cache`)
and let the next run create it anew. Mounted at `/home/wetterdienst/.cache/wetterdienst`, a new volume
is owned by the user; mounted elsewhere it is owned by root, and needs the `chown` as well.
