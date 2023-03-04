# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
""" tests for file index creation """
import pytest

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
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
def test_file_index_creation_success(default_settings):
    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.RECENT,
        settings=default_settings,
    )
    assert not file_index.empty
    assert file_index.loc[file_index["station_id"] == "01048", "filename",].values.tolist() == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/recent/tageswerte_KL_01048_akt.zip"
    ]


@pytest.mark.remote
def test_file_index_creation_failure(default_settings):
    with pytest.raises(FileNotFoundError):
        create_file_index_for_climate_observations(
            DwdObservationDataset.CLIMATE_SUMMARY, Resolution.MINUTE_1, Period.HISTORICAL, settings=default_settings
        )


@pytest.mark.remote
def test_create_file_list_for_dwd_server(default_settings):
    remote_file_path = create_file_list_for_climate_observations(
        station_id="01048",
        dataset=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
        settings=default_settings,
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
        settings=default_settings,
    )
    assert remote_file_path == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "10_minutes/air_temperature/historical/"
        "10minutenwerte_TU_00003_19930428_19991231_hist.zip"
    ]
