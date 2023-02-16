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

  # Install wradlib 1.19 only on Python 3.9 or higher.
  if poetry run python -c 'import sys; sys.exit(not sys.version_info >= (3, 9))'; then
    poetry run pip install --verbose --no-input wradlib==1.19.0

  # Install wradlib, preventing installation of GDAL.
  else
    poetry run pip install --verbose --no-input --no-deps wradlib==1.18.0
  fi

  poetry install --verbose --no-interaction \
    --with=test,dev \
    --extras=explorer \
    --extras=export \
    --extras=interpolation \
    --extras=ipython \
    --extras=radar \
    --extras=restapi \
    --extras=sql

elif [ "${flavor}" = "docs" ]; then
  poetry install --verbose --no-interaction --with=docs --extras=interpolation

fi
