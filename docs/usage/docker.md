# Docker

The wetterdienst Docker image comes with several extras installed so you can use most of the features out of the box:
- bufr
- cratedb
- duckdb
- explorer
- influxdb
- interpolation
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

A volume or host directory that an earlier run as root filled keeps its owner, and the user cannot
write to it. Hand it over once:

```bash
docker run --rm --user 0 --volume wetterdienst-cache:/c ghcr.io/earthobservations/wetterdienst chown -R 10001:10001 /c
```
