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

RUN apt-get update


# Install GDAL.
RUN apt-get --yes install build-essential libgdal-dev libmariadbclient-dev git

# Make sure you have numpy installed before you attempt to install the GDAL Python bindings.
# https://gis.stackexchange.com/a/274328
RUN pip install numpy
RUN pip install GDAL==$(gdal-config --version)

# Install wradlib.
RUN pip install wradlib

# Install database adapters
RUN pip install mysqlclient


# 2. Main
FROM python:3.8.8-slim

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Install libgdal.
RUN apt-get update
RUN apt-get --yes install libgdal20 git

# Copy build artefacts from first build step.
COPY --from=build-step /usr/local/lib /usr/local/lib

# Install Wetterdienst.

# Use "poetry build --format=wheel" to build wheel packages.
COPY dist/wetterdienst-*.whl /tmp/

# Install latest wheel package.
RUN pip install $(ls -c /tmp/wetterdienst-*-py3-none-any.whl)[sql,export,duckdb,influxdb,cratedb,mysql,postgresql,radar,bufr,restapi,explorer]

# Purge /tmp directory
RUN rm /tmp/*

# Copy selftest.sh to the image
COPY .github/release/selftest.sh /usr/local/bin
