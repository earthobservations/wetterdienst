# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""tests for file index creation"""

import polars as pl
import pytest

from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
)
from wetterdienst.provider.dwd.observation.fileindex import (
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
)


@pytest.mark.remote
def test_file_index_creation_success(default_settings):
    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.RECENT,
        settings=default_settings,
    ).collect()
    assert not file_index.is_empty()
    assert file_index.filter(pl.col("station_id").eq("01048")).get_column("url").to_list() == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
        "climate/daily/kl/recent/tageswerte_KL_01048_akt.zip",
    ]


@pytest.mark.remote
def test_file_index_creation_precipitation_minute_1(default_settings):
    # Existing combination of parameters
    file_index = create_file_index_for_climate_observations(
        dataset=DwdObservationMetadata.minute_1.precipitation,
        period=Period.HISTORICAL,
        settings=default_settings,
    ).collect()
    assert not file_index.is_empty()
    assert "00000" not in file_index.get_column("station_id")


@pytest.mark.remote
def test_create_file_list_for_dwd_server(default_settings):
    remote_file_path = create_file_list_for_climate_observations(
        station_id="01048",
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.RECENT,
        settings=default_settings,
    ).to_list()
    assert remote_file_path == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "daily/kl/recent/tageswerte_KL_01048_akt.zip",
    ]
    # with date range
    remote_file_path = create_file_list_for_climate_observations(
        station_id="00003",
        dataset=DwdObservationMetadata.minute_10.temperature_air,
        period=Period.HISTORICAL,
        date_ranges=["19930428_19991231"],
        settings=default_settings,
    ).to_list()
    assert remote_file_path == [
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
        "10_minutes/air_temperature/historical/"
        "10minutenwerte_TU_00003_19930428_19991231_hist.zip",
    ]
