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
  uv pip install .[bufr,explorer,export,interpolation,ipython,radar,radarplus,restapi,sql]

elif [ "${flavor}" = "docs" ]; then
  uv pip install .[docs,interpolation]

fi
