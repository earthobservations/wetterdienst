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
  poetry install --verbose --no-interaction --with=test,dev --extras=sql --extras=export --extras=restapi --extras=explorer --extras=interpolation --extras=ipython --extras=radar --extras=radarplus

elif [ "${flavor}" = "docs" ]; then
  poetry install --verbose --no-interaction --with=docs --extras=interpolation

fi
