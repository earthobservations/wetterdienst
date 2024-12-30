# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.exceptions import NoParametersFoundError
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
    DwdObservationRequest,
)


@pytest.mark.remote
@pytest.mark.parametrize(
    "ts_skip_criteria,expected_stations",
    [("min", ["05906", "04928"]), ("mean", ["05426", "04177"]), ("max", ["00377", "05426"])],
)
def test_api_skip_empty_stations(
    settings_drop_nulls_false_complete_true_skip_empty_true, ts_skip_criteria, expected_stations
):
    # overcharge skip criteria
    settings_drop_nulls_false_complete_true_skip_empty_true.ts_skip_criteria = ts_skip_criteria
    settings_drop_nulls_false_complete_true_skip_empty_true.ts_skip_threshold = 0.6
    request = DwdObservationRequest(
        parameters=[("daily", "kl"), ("daily", "solar")],
        start_date="2021-01-01",
        end_date="2021-12-31",
        settings=settings_drop_nulls_false_complete_true_skip_empty_true,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=2)
    values = request.values.all()
    assert (
        values.df.get_column("station_id").gather(0).to_list()
        != request.df.get_column("station_id").gather(0).to_list()
    )  # not supposed to be the first station of the list
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_stations
    assert values.df_stations.get_column("station_id").to_list() == expected_stations


@pytest.mark.remote
def test_api_skip_empty_stations_equal_on_any_skip_criteria_with_one_parameter(
    settings_drop_nulls_false_complete_true_skip_empty_true,
):
    """If there is only one parameter any skip criteria (min, mean, max) should return the same station"""

    def _get_values(settings):
        return (
            DwdObservationRequest(
                parameters=[("daily", "climate_summary", "sunshine_duration")],
                start_date="1990-01-01",
                end_date="2021-12-31",
                settings=settings,
            )
            .filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=1)
            .values.all()
        )

    settings_drop_nulls_false_complete_true_skip_empty_true.ts_skip_threshold = 0.9
    expected_station = ["05426"]

    settings_drop_nulls_false_complete_true_skip_empty_true.ts_skip_criteria = "min"
    values = _get_values(settings_drop_nulls_false_complete_true_skip_empty_true)
    assert values.df.get_column("station_id").unique().to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station

    settings_drop_nulls_false_complete_true_skip_empty_true.ts_skip_criteria = "mean"
    values = _get_values(settings_drop_nulls_false_complete_true_skip_empty_true)
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station

    settings_drop_nulls_false_complete_true_skip_empty_true.ts_skip_criteria = "max"
    values = _get_values(settings_drop_nulls_false_complete_true_skip_empty_true)
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station


@pytest.mark.remote
def test_api_drop_nulls(default_settings):
    request = DwdObservationRequest(
        parameters=[
            ("minute_10", "temperature_air"),
            ("minute_10", "precipitation"),
        ],
        start_date="2021-01-01",
        end_date="2021-12-31",
        settings=default_settings,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=20)
    values = next(request.values.query())
    assert values.df.shape[0] == 51971


def test_api_no_valid_parameters(default_settings):
    with pytest.raises(NoParametersFoundError):
        DwdObservationRequest(
            parameters=[
                ("daily", "abc"),
            ],
            settings=default_settings,
        )


def test_api_partly_valid_parameters(default_settings, caplog):
    request = DwdObservationRequest(
        parameters=[
            ("daily", "temperature_air"),
            ("daily", "wind"),
            ("daily", "precipitation"),
            ("daily", "solar"),
        ],
        settings=default_settings,
    )
    assert "daily/wind not found in DwdObservationMetadata" in caplog.text
    assert "daily/precipitation not found in DwdObservationMetadata" in caplog.text
    assert request.parameters == [*DwdObservationMetadata.daily.solar]
