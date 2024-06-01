# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst import Period, Resolution
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
)
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
