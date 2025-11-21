#!/bin/bash

flavor=$1

if [[ -z "${flavor}" ]]; then
  echo "Missing option 'flavor', use e.g. 'testing' or 'docs'."
  exit 1
fi

echo "Installing package and requirements for ${flavor}"

set -e
set -x

if [ "${flavor}" = "testing" ]; then
  uv sync --active --extra bufr --extra export --extra influxdb --extra interpolation --extra plotting --extra radar --extra radarplus --extra restapi --extra sql

elif [ "${flavor}" = "docs" ]; then
  uv sync --active --extra interpolation --group docs

fi
