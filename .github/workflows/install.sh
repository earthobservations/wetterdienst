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
  poetry install --verbose --no-interaction --extras=sql --extras=export --extras=restapi --extras=explorer --extras=interpolation --extras=radar
  poetry run pip install --verbose --no-input --no-deps wradlib

elif [ "${flavor}" = "docs" ]; then
  poetry install --verbose --no-interaction --extras=docs --extras=interpolation

fi
