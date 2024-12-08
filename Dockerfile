FROM python:3.13-slim-bookworm AS build

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=linux

# Install build prerequisites.
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN \
    --mount=type=cache,id=apt,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,id=apt,sharing=locked,target=/var/lib/apt \
    true \
    && apt-get update \
    && apt-get install --no-install-recommends --no-install-suggests --yes \
      git build-essential python3-dev python3-pip python3-venv python3-wheel \
      python3-h5py ca-certificates pkg-config libhdf5-dev

RUN pip install uv

# Install wradlib.
RUN uv pip install --system wradlib

# Install Wetterdienst.

# Use `poetry build --format=wheel` to build wheel packages into `dist` folder.
COPY dist/wetterdienst-*.whl /tmp/

# Install package.
# Pick latest wheel package from `/tmp` folder.
RUN --mount=type=cache,id=pip,target=/root/.cache/pip \
    true \
    && WHEEL=$(ls -r /tmp/wetterdienst-*-py3-none-any.whl | head -n 1) \
    && uv pip install --system versioningit \
    && uv pip install --system ${WHEEL}[bufr,cratedb,duckdb,explorer,influxdb,interpolation,postgresql,radar,radarplus,restapi]

# TODO: for linux/arm64 we currently cant install zarr as it depends on numcodecs which has no wheels
#   and building it from source takes too long
#   see also: https://github.com/zarr-developers/numcodecs/issues/288
RUN WHEEL=$(ls -r /tmp/wetterdienst-*-py3-none-any.whl | head -n 1) && \
    if [ "$(uname -m)" = "x86_64" ]; then \
        uv pip install --system ${WHEEL}[export]; \
    else \
        uv pip install --system ${WHEEL}[export_without_zarr]; \
    fi


# Final stage
FROM python:3.13-slim-bookworm

# Install h5py
RUN apt-get update \
    && apt-get install --no-install-recommends --no-install-suggests --yes \
      python3-h5py \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy installed pip packages from build stage
COPY --from=build /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
