#!/usr/bin/env bash

flavor=$1

if [[ -z "${flavor}" ]]; then
  echo "Missing option 'flavor', use e.g. 'testing' or 'docs'."
  exit 1
fi

echo "Installing package and requirements for ${flavor}"

if [[ "${flavor}" = "testing" ]]; then
  poetry install --no-interaction --extras=http --extras=sql --extras=export --extras=ui

elif [[ "${flavor}" = "docs" ]]; then
  poetry install --no-interaction --extras=docs
fi
