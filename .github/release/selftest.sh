#!/bin/bash

# Fail on error.
set -e

# Display all commands.
# set -x

flavor=$1

echo "Testing wetterdienst"
wetterdienst version
wetterdienst about coverage

if [ "${flavor}" == "full" ]; then
  echo "Checking libraries"
  python -c 'import gdal; print("gdal:", gdal.VersionInfo())'
  python -c 'import wradlib; print("wradlib:", wradlib.__version__)'
fi
