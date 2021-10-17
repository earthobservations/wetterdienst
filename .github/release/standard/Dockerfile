FROM python:3.8.8-slim

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

RUN apt-get update
RUN apt-get --yes install git

# Use "poetry build --format=wheel" to build wheel packages.
COPY dist/wetterdienst-*.whl /tmp/

# Install latest wheel package.
RUN pip install $(ls -c /tmp/wetterdienst-*-py3-none-any.whl)[sql,export,restapi]

# Purge /tmp directory
RUN rm /tmp/*

# Copy selftest.sh to the image
COPY .github/release/selftest.sh /usr/local/bin
