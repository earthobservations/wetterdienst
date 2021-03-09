# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
""" tests for file index creation """
import pytest
import requests

from wetterdienst.dwd.observations import DwdObservationDataset
from wetterdienst.dwd.observations.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution


@pytest.mark.remote
def test_meta_index_creation():

    # Existing combination of parameters
    meta_index = create_meta_index_for_climate_observations(
        DwdObservationDataset.CLIMATE_SUMMARY,
        Resolution.DAILY,
        Period.HISTORICAL,
    )

    assert not meta_index.empty

    with pytest.raises(requests.exceptions.HTTPError):
        create_meta_index_for_climate_observations(
            DwdObservationDataset.CLIMATE_SUMMARY,
            Resolution.MINUTE_1,
            Period.HISTORICAL,
        )


@pytest.mark.remote
def test_meta_index_1mph_creation():

    meta_index_1mph = create_meta_index_for_climate_observations(
        DwdObservationDataset.PRECIPITATION,
        Resolution.MINUTE_1,
        Period.HISTORICAL,
    )

    assert meta_index_1mph.loc[
        meta_index_1mph[Columns.STATION_ID.value] == "00003", :
    ].values.tolist() == [
        [
            "00003",
            "18910101",
            "20120406",
            "202.00",
            "50.7827",
            "6.0941",
            "Aachen",
            "Nordrhein-Westfalen",
        ]
    ]
