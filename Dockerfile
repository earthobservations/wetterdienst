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
      python3-h5py ca-certificates pkg-config libhdf5-dev curl libxml2 libxslt1-dev cmake


# linux/arm/v7
# install rust, required to build fastexcel
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN pip install uv

# Install Wetterdienst.
# Use previously built wheel package.
COPY dist/wetterdienst-*.whl /tmp/

# Install package.
# Pick latest wheel package from `/tmp` folder.
RUN --mount=type=cache,id=pip,target=/root/.cache/pip \
    true \
    && WHEEL=$(ls -r /tmp/wetterdienst-*-py3-none-any.whl | head -n 1) \
    && if [ "$(uname -m)" = "x86_64" ]; then \
        uv pip install --system ${WHEEL}[bufr,cratedb,duckdb,explorer,export,influxdb,interpolation,postgresql,radar,radarplus,restapi]; \
    elif [ "$(uname -m)" = "aarch64" ]; then \
        uv pip install --system ${WHEEL}[bufr,cratedb,duckdb,explorer,export_without_zarr,influxdb,interpolation,postgresql,radar,radarplus,restapi]; \
    elif [ "$(uname -m)" = "armv7l" ]; then \
        uv pip install --system ${WHEEL}; \
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

# by default start restapi, also need this for sliplane atm
CMD [ "wetterdienst", "restapi", "--listen=0.0.0.0:10000"]