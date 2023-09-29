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
  poetry install --verbose --no-interaction \
    --with=test,dev \
    --extras=bufr \
    --extras=explorer \
    --extras=export \
    --extras=interpolation \
    --extras=ipython \
    --extras=radar \
    --extras=radarplus \
    --extras=restapi \
    --extras=sql

  # FIXME: Remove this again.
  # Fix dependency woes about percy: AttributeError: module 'percy' has no attribute 'Runner'.
  # https://github.com/earthobservations/wetterdienst/pull/1017#issuecomment-1741240635
  # pytest tests/ui/explorer/test_explorer.py -k test_app_layout
  poetry run poe fix-percy

elif [ "${flavor}" = "docs" ]; then
  poetry install --verbose --no-interaction --with=docs --extras=interpolation

fi
