# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
""" tests for file index creation """
import datetime as dt

import polars as pl
import pytest

from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation import DwdObservationDataset
from wetterdienst.provider.dwd.observation.metaindex import (
    create_meta_index_for_climate_observations,
)


@pytest.mark.remote
def test_meta_index_creation_success(default_settings):
    # Existing combination of parameters
    meta_index = create_meta_index_for_climate_observations(
        DwdObservationDataset.CLIMATE_SUMMARY, Resolution.DAILY, Period.HISTORICAL, settings=default_settings
    ).collect()
    assert not meta_index.is_empty()


@pytest.mark.remote
def test_meta_index_creation_failure(default_settings):
    with pytest.raises(FileNotFoundError):
        create_meta_index_for_climate_observations(
            DwdObservationDataset.CLIMATE_SUMMARY, Resolution.MINUTE_1, Period.HISTORICAL, settings=default_settings
        )


@pytest.mark.remote
def test_meta_index_1mph_creation(default_settings):
    meta_index_1mph = create_meta_index_for_climate_observations(
        DwdObservationDataset.PRECIPITATION, Resolution.MINUTE_1, Period.HISTORICAL, settings=default_settings
    ).collect()
    assert meta_index_1mph.filter(pl.col(Columns.STATION_ID.value).eq("00003")).row(0) == (
        (
            "00003",
            dt.datetime(1891, 1, 1, 0, 0),
            dt.datetime(2012, 4, 6, 0, 0),
            202.00,
            50.7827,
            6.0941,
            "Aachen",
            "Nordrhein-Westfalen",
        )
    )
