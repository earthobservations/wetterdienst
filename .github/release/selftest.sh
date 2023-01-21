#!/bin/bash

flavor=$1

echo "Testing wetterdienst"
foobar
wetterdienst --version
wetterdienst dwd about parameters

if [[ ${flavor} = "full" ]]; then
  echo "Checking libraries"
  python -c 'import gdal; print("gdal:", gdal.VersionInfo())'
  python -c 'import wradlib; print("wradlib:", wradlib.__version__)'
fi
