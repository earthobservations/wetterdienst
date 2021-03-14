# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.metadata import DwdObservationDataset
from wetterdienst.provider.dwd.observation.util.parameter import (
    check_dwd_observations_dataset,
)


def test_check_parameters():
    assert check_dwd_observations_dataset(
        DwdObservationDataset.PRECIPITATION,
        Resolution.MINUTE_10,
        Period.HISTORICAL,
    )
    assert not check_dwd_observations_dataset(
        DwdObservationDataset.CLIMATE_SUMMARY,
        Resolution.MINUTE_1,
        Period.HISTORICAL,
    )
