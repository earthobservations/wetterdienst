# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst import Period, Resolution
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.util.parameter import check_dwd_observations_dataset
from wetterdienst.provider.dwd.util import build_parameter_set_identifier


def test_build_parameter_identifier():
    parameter_identifier = build_parameter_set_identifier(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL,
        "00001",
    )

    assert parameter_identifier == "kl/daily/historical/00001"


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
