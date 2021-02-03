# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.dwd.index import (
    _create_file_index_for_dwd_server,
    build_path_to_parameter,
)
from wetterdienst.dwd.metadata.constants import DWDCDCBase
from wetterdienst.dwd.observations import (
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
)
from wetterdienst.util.network import list_remote_files


def test_build_index_path():
    path = build_path_to_parameter(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        DWDObservationResolution.DAILY,
        DWDObservationPeriod.HISTORICAL,
    )
    assert path == "daily/kl/historical/"


@pytest.mark.remote
def test_list_files_of_climate_observations():
    files_server = list_remote_files(
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "annual/kl/recent",
        recursive=False,
    )

    assert (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "annual/kl/recent/jahreswerte_KL_01048_akt.zip" in files_server
    )


def test_fileindex():

    file_index = _create_file_index_for_dwd_server(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        DWDObservationResolution.DAILY,
        DWDObservationPeriod.RECENT,
        DWDCDCBase.CLIMATE_OBSERVATIONS,
    )

    assert "daily/kl/recent" in file_index.iloc[0]["FILENAME"]
