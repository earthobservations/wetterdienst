# Docker

Wetterdienst comes in two Docker image flavors. A "standard" variant, including
all dependency packages from the ``export,restapi`` extras, and a "full" variant,
including all dependency packages from the ``export,influxdb,cratedb,postgresql,
radar,bufr,restapi,explorer,radar,radarplus`` extras.


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
