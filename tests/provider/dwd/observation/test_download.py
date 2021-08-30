# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import re
import zipfile

import pytest

from wetterdienst.exceptions import FailedDownload, ProductFileNotFound
from wetterdienst.provider.dwd.observation.download import (
    __download_climate_observations_data,
)


def test_download_climate_observations_data_failure_invalid_url():
    with pytest.raises(FailedDownload) as ex:
        __download_climate_observations_data("foobar.txt")
    assert ex.match(re.escape("Download failed for foobar.txt: InvalidURL(foobar.txt)"))


def test_download_climate_observations_data_failure_invalid_protocol():
    with pytest.raises(FailedDownload) as ex:
        __download_climate_observations_data("foobar://bazqux.txt")
    assert ex.match(
        re.escape("Download failed for foobar://bazqux.txt: AssertionError()")
    )


def test_download_climate_observations_data_failure_invalid_zip():
    with pytest.raises(zipfile.BadZipFile) as ex:
        __download_climate_observations_data("http://example.org")
    assert ex.match(
        re.escape("The Zip archive http://example.org seems to be corrupted")
    )


def test_download_climate_observations_data_failure_broken_zip():
    with pytest.raises(zipfile.BadZipFile) as ex:
        __download_climate_observations_data(
            "https://github.com/earthobservations/testdata/raw/main/opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/broken-zip-archive.zip"
        )
    assert ex.match("The Zip archive .+ seems to be corrupted")


def test_download_climate_observations_data_failure_empty_zip():
    with pytest.raises(ProductFileNotFound) as ex:
        __download_climate_observations_data(
            "https://github.com/earthobservations/testdata/raw/main/opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/empty-zip-archive.zip"
        )
    assert ex.match("The archive .+ does not contain a 'produkt\\*' file")


def test_download_climate_observations_data_valid():
    payload = __download_climate_observations_data(
        "https://github.com/earthobservations/testdata/raw/main/opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/tageswerte_KL_00011_akt.zip"
    )
    assert payload.startswith(
        b"STATIONS_ID;MESS_DATUM;QN_3;  FX;  FM;QN_4; RSK;RSKF; SDK;SHK_TAG;  NM; VPM;"
        b"  PM; TMK; UPM; TXK; TNK; TGK;eor\r\n         11;20200227;   10;  28.5;   "
    )
