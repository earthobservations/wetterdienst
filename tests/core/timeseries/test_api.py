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
@pytest.mark.parametrize(
    "ts_skip_criteria,expected_stations",
    [("min", ["05906", "04928"]), ("mean", ["05426", "04177"]), ("max", ["00377", "05426"])],
)
def test_api_skip_empty_stations(settings_skip_empty_true, ts_skip_criteria, expected_stations):
    # overcharge skip criteria
    settings_skip_empty_true.ts_skip_criteria = ts_skip_criteria
    settings_skip_empty_true.ts_skip_threshold = 0.6
    request = DwdObservationRequest(
        parameter=["kl", "solar"],
        resolution="daily",
        start_date="2021-01-01",
        end_date="2021-12-31",
        settings=settings_skip_empty_true,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=2)
    values = request.values.all()
    assert (
        values.df.get_column("station_id").take(0).to_list() != request.df.get_column("station_id").take(0).to_list()
    )  # not supposed to be the first station of the list
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_stations
    assert values.df_stations.get_column("station_id").to_list() == expected_stations


@pytest.mark.remote
def test_api_skip_empty_stations_equal_on_any_skip_criteria_with_one_parameter(settings_skip_empty_true):
    """If there is only one parameter any skip criteria (min, mean, max) should return the same station"""

    def _get_values(settings):
        return (
            DwdObservationRequest(
                parameter=["sunshine_duration"],
                resolution="daily",
                start_date="1990-01-01",
                end_date="2021-12-31",
                settings=settings,
            )
            .filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=1)
            .values.all()
        )

    settings_skip_empty_true.ts_skip_threshold = 0.9
    expected_station = ["05426"]

    settings_skip_empty_true.ts_skip_criteria = "min"
    values = _get_values(settings_skip_empty_true)
    assert values.df.get_column("station_id").unique().to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station

    settings_skip_empty_true.ts_skip_criteria = "mean"
    values = _get_values(settings_skip_empty_true)
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station

    settings_skip_empty_true.ts_skip_criteria = "max"
    values = _get_values(settings_skip_empty_true)
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station


@pytest.mark.remote
def test_api_dropna(settings_dropna_true):
    request = DwdObservationRequest(
        parameter=[
            "temperature_air",
            "precipitation",
        ],
        resolution="minute_10",
        start_date="2021-01-01",
        end_date="2021-12-31",
        settings=settings_dropna_true,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=20)
    values = next(request.values.query())
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
