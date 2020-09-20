FROM python:3.8.5-slim

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
RUN apt-get update
RUN apt-get --yes install build-essential libgdal-dev

# Make sure you have numpy installed before you attempt to install the GDAL Python bindings.
# https://gis.stackexchange.com/a/274328
RUN pip install numpy
RUN pip install GDAL==$(gdal-config --version)

# Install wradlib.
RUN pip install wradlib

# Install Wetterdienst.
RUN pip install wetterdienst[excel]
