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
