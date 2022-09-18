#!/usr/bin/env bash

flavor=$1

if [[ -z "${flavor}" ]]; then
  echo "Missing option 'flavor', use e.g. 'testing' or 'docs'."
  exit 1
fi

echo "Installing package and requirements for ${flavor}"

if [[ "${flavor}" = "testing" ]]; then
  poetry install --no-interaction --extras=sql --extras=export --extras=restapi --extras=explorer --extras=interpolation
  poetry run pip install wradlib --no-deps
elif [[ "${flavor}" = "docs" ]]; then
  poetry install --no-interaction --extras=docs --extras=interpolation
fi
