FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

RUN apt-get update && apt-get --yes --no-install-recommends install build-essential

# Use "poetry build --format=wheel" to build wheel packages.
COPY dist/wetterdienst-*.whl /tmp/

# Install latest wheel package.
RUN pip install --no-cache-dir $(ls -r /tmp/wetterdienst-*-py3-none-any.whl | head -n 1)[export,restapi]

# Purge /tmp directory
RUN rm /tmp/*

# Copy selftest.sh to the image
COPY .github/release/selftest.sh /usr/local/bin
