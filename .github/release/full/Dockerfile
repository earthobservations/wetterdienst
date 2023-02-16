# 1. Build GDAL-python
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Install GDAL and HDF5 bindings for Python, and a few other dependencies.
RUN apt-get update && \
    apt-get --yes --no-install-recommends --no-install-suggests install \
      ca-certificates python-is-python3 python3-gdal python3-h5py python3-pip python3-wheel && \
    rm -rf /var/lib/apt/lists/* && rm -rf /var/cache/apt

# Use Python 3.11.
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 0

# Install wradlib, preventing installation of GDAL.
RUN python -m pip install --prefer-binary xradar
RUN python -m pip install --prefer-binary --no-deps wradlib==1.19.0

# Install Wetterdienst.

# Use `poetry build --format=wheel` to build wheel packages into `dist` folder.
COPY dist/wetterdienst-*.whl /tmp/

# Install latest wheel package.
RUN python -m pip install --no-cache-dir --prefer-binary $(ls -r /tmp/wetterdienst-*-py3-none-any.whl | head -n 1)[export,influxdb,cratedb,postgresql,radar,bufr,restapi,explorer]

# Purge /tmp directory
RUN rm /tmp/*

# Copy selftest.sh to the image
COPY .github/release/selftest.sh /usr/local/bin
