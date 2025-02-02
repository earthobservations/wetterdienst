# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst.ui.core import unpack_parameters


def test_unpack_parameters_parameters_only() -> None:
    parameters = "precipitation_height,temperature_air_2m"
    expected = ["precipitation_height", "temperature_air_2m"]
    assert unpack_parameters(parameters) == expected


def test_unpack_parameters_parameter_dataset_pair() -> None:
    parameters = "precipitation_height/precipitation_more,temperature_air_2m/kl"
    expected = [
        ("precipitation_height", "precipitation_more"),
        ("temperature_air_2m", "kl"),
    ]
    assert unpack_parameters(parameters) == expected
