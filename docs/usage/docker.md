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

Run Wetterdienst Explorer UI service:

```bash
docker run -it --rm --publish=7891:7891 ghcr.io/earthobservations/wetterdienst wetterdienst explorer --listen 0.0.0.0:7891
```
