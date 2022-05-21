# 1. Build GDAL-python
FROM python:3.8.8-slim as build-step

# TODO: This currently installs GDAL==2.4.0. For a more recent version, ...
#
# - Maybe use "ubuntu:focal" already?
#   https://github.com/thinkWhere/GDAL-Docker/blob/develop/3.8-ubuntu/Dockerfile
#
# - See also:
#   https://github.com/andrejreznik/docker-python-gdal
#

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Install GDAL.
RUN apt-get update && \
    apt-get --yes --no-install-recommends install build-essential libgdal-dev libmariadb-dev && \
    rm -rf /var/lib/apt/lists/*

# Make sure you have numpy installed before you attempt to install the GDAL Python bindings.
# https://gis.stackexchange.com/a/274328
RUN pip install --no-cache-dir setuptools==57.0.0
RUN pip install --no-cache-dir numpy
RUN pip install --no-cache-dir GDAL==$(gdal-config --version)

# Install wradlib.
RUN pip install --no-cache-dir wradlib --no-deps

# Install database adapters
RUN pip install --no-cache-dir mysqlclient


# 2. Main
FROM python:3.8.8-slim

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Install libgdal.
RUN apt-get update && \
    apt-get --yes --no-install-recommends install libgdal20 && \
    rm -rf /var/lib/apt/lists/*

# Copy build artefacts from first build step.
COPY --from=build-step /usr/local/lib /usr/local/lib

# Install Wetterdienst.

# Use "poetry build --format=wheel" to build wheel packages.
COPY dist/wetterdienst-*.whl /tmp/

# Install latest wheel package.
RUN pip install --no-cache-dir $(ls -c /tmp/wetterdienst-*-py3-none-any.whl)[export,influxdb,cratedb,mysql,postgresql,radar,bufr,restapi,explorer]

# Purge /tmp directory
RUN rm /tmp/*

# Copy selftest.sh to the image
COPY .github/release/selftest.sh /usr/local/bin
