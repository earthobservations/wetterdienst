# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
""" tests for file index creation """
import pytest
import requests

from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.dwd.observations import (
    DWDObservationParameterSet,
    DWDObservationPeriod,
    DWDObservationResolution,
)
from wetterdienst.dwd.observations.fileindex import (
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
)
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


@pytest.mark.remote
def test_file_index_creation():

    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        DWDObservationResolution.DAILY,
        DWDObservationPeriod.RECENT,
    )

    assert not file_index.empty

    assert file_index.loc[
        file_index[DWDMetaColumns.STATION_ID.value] == "01048",
        DWDMetaColumns.FILENAME.value,
    ].values.tolist() == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/recent/tageswerte_KL_01048_akt.zip"
    ]

    with pytest.raises(requests.exceptions.HTTPError):
        create_file_index_for_climate_observations(
            DWDObservationParameterSet.CLIMATE_SUMMARY,
            DWDObservationResolution.MINUTE_1,
            DWDObservationPeriod.HISTORICAL,
        )


def test_create_file_list_for_dwd_server():
    remote_file_path = create_file_list_for_climate_observations(
        station_id="01048",
        parameter_set=DWDObservationParameterSet.CLIMATE_SUMMARY,
        resolution=DWDObservationResolution.DAILY,
        period=DWDObservationPeriod.RECENT,
    )
    assert remote_file_path == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "daily/kl/recent/tageswerte_KL_01048_akt.zip"
    ]

    # with date range
    remote_file_path = create_file_list_for_climate_observations(
        station_id="00003",
        parameter_set=DWDObservationParameterSet.TEMPERATURE_AIR,
        resolution=Resolution.MINUTE_10,
        period=Period.HISTORICAL,
        date_range="19930428_19991231",
    )

    assert remote_file_path == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "10_minutes/air_temperature/historical/"
        "10minutenwerte_TU_00003_19930428_19991231_hist.zip"
    ]
