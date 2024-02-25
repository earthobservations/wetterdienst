FROM python:3.12-slim-bookworm AS build

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Install build prerequisites.
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN \
    --mount=type=cache,id=apt,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,id=apt,sharing=locked,target=/var/lib/apt \
    true \
    && apt-get update \
    && apt-get install --no-install-recommends --no-install-suggests --yes \
      git build-essential python3-dev python3-pip python3-venv python3-wheel \
      python3-h5py ca-certificates

# Install wradlib.
RUN python -m pip install --prefer-binary wradlib

# Install Wetterdienst.

# Use `poetry build --format=wheel` to build wheel packages into `dist` folder.
COPY dist/wetterdienst-*.whl /tmp/

# Install package.
# Pick latest wheel package from `/tmp` folder.
RUN --mount=type=cache,id=pip,target=/root/.cache/pip \
    true \
    && pip install --prefer-binary versioningit \
    && WHEEL=$(ls -r /tmp/wetterdienst-*-py3-none-any.whl | head -n 1) \
    && pip install --use-pep517 --prefer-binary ${WHEEL}[export,influxdb,cratedb,postgresql,radar,bufr,restapi,explorer,radar,radarplus]

# Final stage
FROM python:3.12-slim-bookworm

# Install h5py
RUN apt-get update \
    && apt-get install --no-install-recommends --no-install-suggests --yes \
      python3-h5py \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# Copy installed pip packages from build stage
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Copy selftest.sh to the image
COPY .github/release/selftest.sh /usr/local/bin
