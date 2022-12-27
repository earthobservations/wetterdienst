# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.exceptions import NoParametersFound
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationRequest,
    DwdObservationResolution,
)


@pytest.mark.remote
def test_api_skip_empty_stations(settings_skip_empty_true):
    start_date = "2021-01-01"
    end_date = "2021-12-31"

    stations = DwdObservationRequest(
        parameter=[
            DwdObservationDataset.TEMPERATURE_AIR,
            DwdObservationDataset.PRECIPITATION,
        ],
        resolution=DwdObservationResolution.MINUTE_10,
        start_date=start_date,
        end_date=end_date,
        settings=settings_skip_empty_true,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=20)

    values = next(stations.values.query())

    assert (
        values.df.station_id.iloc[0] != stations.df.station_id.iloc[0]
    )  # not supposed to be the first station of the list
    assert values.df.station_id.iloc[0] == "05426"


@pytest.mark.remote
def test_api_dropna(settings_dropna_true):
    start_date = "2021-01-01"
    end_date = "2021-12-31"

    stations = DwdObservationRequest(
        parameter=[
            DwdObservationDataset.TEMPERATURE_AIR,
            DwdObservationDataset.PRECIPITATION,
        ],
        resolution=DwdObservationResolution.MINUTE_10,
        start_date=start_date,
        end_date=end_date,
        settings=settings_dropna_true,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=20)

    values = next(stations.values.query())

    assert values.df.shape[0] == 51971


def test_api_no_valid_parameters(default_settings):
    with pytest.raises(NoParametersFound):
        DwdObservationRequest(
            parameter=[
                DwdObservationDataset.TEMPERATURE_AIR,
            ],
            resolution=DwdObservationResolution.DAILY,
            settings=default_settings,
        )


def test_api_partly_valid_parameters(default_settings, caplog):
    request = DwdObservationRequest(
        parameter=[
            DwdObservationDataset.TEMPERATURE_AIR,
            DwdObservationDataset.WIND,
            DwdObservationDataset.PRECIPITATION,
            DwdObservationDataset.SOLAR,
        ],
        resolution=DwdObservationResolution.DAILY,
        settings=default_settings,
    )

    assert "dataset WIND is not a valid dataset for resolution DAILY" in caplog.text
    assert "dataset PRECIPITATION is not a valid dataset for resolution DAILY" in caplog.text

    assert request.parameter == [
        (
            DwdObservationDataset.SOLAR,
            DwdObservationDataset.SOLAR,
        )
    ]
