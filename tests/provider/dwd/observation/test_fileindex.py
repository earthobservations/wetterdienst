# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
""" tests for file index creation """
import aiohttp
import pytest
import requests

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.fileindex import (
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
)


@pytest.mark.remote
def test_file_index_creation():

    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.RECENT,
    )

    assert not file_index.empty

    assert file_index.loc[
        file_index[DwdColumns.STATION_ID.value] == "01048",
        DwdColumns.FILENAME.value,
    ].values.tolist() == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/recent/tageswerte_KL_01048_akt.zip"
    ]

    with pytest.raises(
        (requests.exceptions.HTTPError, aiohttp.client_exceptions.ClientResponseError)
    ):
        create_file_index_for_climate_observations(
            DwdObservationDataset.CLIMATE_SUMMARY,
            DwdObservationResolution.MINUTE_1,
            DwdObservationPeriod.HISTORICAL,
        )


@pytest.mark.remote
def test_create_file_list_for_dwd_server():
    remote_file_path = create_file_list_for_climate_observations(
        station_id="01048",
        dataset=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
    )
    assert remote_file_path == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "daily/kl/recent/tageswerte_KL_01048_akt.zip"
    ]

    # with date range
    remote_file_path = create_file_list_for_climate_observations(
        station_id="00003",
        dataset=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=Resolution.MINUTE_10,
        period=Period.HISTORICAL,
        date_range="19930428_19991231",
    )

    assert remote_file_path == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "10_minutes/air_temperature/historical/"
        "10minutenwerte_TU_00003_19930428_19991231_hist.zip"
    ]
