FROM python:3.8.5-slim

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Use "poetry build --format=wheel" to build wheel packages.
COPY dist/*.whl /tmp/

# Install latest wheel package.
RUN pip install $(ls -c /tmp/wetterdienst-*-py3-none-any.whl)[http,sql,excel]
