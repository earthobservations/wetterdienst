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

  # Install wradlib and gdal only on ubuntu and latest python version
  if [ "${OS}" = "ubuntu-latest" ] && [ "${PYTHON}" = "3.11" ]; then
    sudo add-apt-repository ppa:ubuntugis/ppa
    sudo apt-get update
    sudo apt-get install gdal-bin
    sudo apt-get install libgdal-dev
    poetry run pip install GDAL=="$(gdal-config --version)"
    poetry run pip install --verbose --no-input --force-reinstall wradlib
  fi

  poetry install --verbose --no-interaction \
    --with=test,dev \
    --extras=explorer \
    --extras=export \
    --extras=interpolation \
    --extras=ipython \
    --extras=radar \
    --extras=radarplus \
    --extras=restapi \
    --extras=sql

elif [ "${flavor}" = "docs" ]; then
  poetry install --verbose --no-interaction --with=docs --extras=interpolation

fi
