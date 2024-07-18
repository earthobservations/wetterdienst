# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest

from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationParameter,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)


@pytest.fixture
def parameters_reference():
    return [
        (
            DwdObservationParameter.DAILY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MEAN_2M,
            DwdObservationDataset.CLIMATE_SUMMARY,
        ),
        (
            DwdObservationParameter.DAILY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MAX_2M,
            DwdObservationDataset.CLIMATE_SUMMARY,
        ),
        (
            DwdObservationParameter.DAILY.CLIMATE_SUMMARY.TEMPERATURE_AIR_MIN_2M,
            DwdObservationDataset.CLIMATE_SUMMARY,
        ),
        (
            DwdObservationParameter.DAILY.CLIMATE_SUMMARY.PRECIPITATION_HEIGHT,
            DwdObservationDataset.CLIMATE_SUMMARY,
        ),
        (
            DwdObservationParameter.DAILY.CLIMATE_SUMMARY.PRECIPITATION_FORM,
            DwdObservationDataset.CLIMATE_SUMMARY,
        ),
    ]


def test_dwd_observation_parameters_constants(default_settings, parameters_reference):
    request = DwdObservationRequest(
        parameter=[
            DwdObservationParameter.DAILY.TEMPERATURE_AIR_MEAN_2M,  # tmk
            DwdObservationParameter.DAILY.TEMPERATURE_AIR_MAX_2M,  # txk
            DwdObservationParameter.DAILY.TEMPERATURE_AIR_MIN_2M,  # tnk
            DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT,  # rsk
            DwdObservationParameter.DAILY.PRECIPITATION_FORM,  # rskf
        ],
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL,
        settings=default_settings,
    )
    assert request.parameter == parameters_reference


def test_dwd_observation_parameters_strings_lowercase(default_settings, parameters_reference):
    request = DwdObservationRequest(
        parameter=[
            "tmk",
            "txk",
            "tnk",
            "rsk",
            "rskf",
        ],
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL,
        settings=default_settings,
    )
    assert request.parameter == parameters_reference


def test_dwd_observation_parameters_strings_uppercase(default_settings, parameters_reference):
    request = DwdObservationRequest(
        parameter=[
            "TMK",
            "TXK",
            "TNK",
            "RSK",
            "RSKF",
        ],
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.HISTORICAL,
        settings=default_settings,
    )
    assert request.parameter == parameters_reference
