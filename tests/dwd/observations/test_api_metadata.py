# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json

from wetterdienst.dwd.observations import (
    DwdObservationDataset,
    DwdObservationParameter,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)
from wetterdienst.metadata.resolution import Resolution


def test_dwd_observation_metadata_discover_parameters():
    parameters = DwdObservationRequest.discover(resolution="minute_1", flatten=True)

    assert (
        json.dumps(
            {
                Resolution.MINUTE_1.name: [
                    DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT.name,
                    DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT_DROPLET.name,
                    DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT_ROCKER.name,
                    DwdObservationParameter.MINUTE_1.PRECIPITATION_FORM.name,
                ]
            },
            indent=4,
        )
        in parameters
    )


def test_dwd_observation_metadata_describe_fields_kl_daily_english():
    metadata = DwdObservationRequest.describe_fields(
        dataset=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
    )

    assert list(metadata.keys()) == [
        "parameters",
        "quality_information",
    ]

    assert list(metadata["parameters"].keys()) == [
        "STATIONS_ID",
        "MESS_DATUM",
        "QN_3",
        "FX",
        "FM",
        "QN_4",
        "RSK",
        "RSKF",
        "SDK",
        "SHK_TAG",
        "NM",
        "VPM",
        "PM",
        "TMK",
        "UPM",
        "TXK",
        "TNK",
        "TGK",
    ]


def test_dwd_observation_metadata_describe_fields_kl_daily_german():
    metadata = DwdObservationRequest.describe_fields(
        dataset=DwdObservationDataset.CLIMATE_SUMMARY,
        resolution=DwdObservationResolution.DAILY,
        period=DwdObservationPeriod.RECENT,
    )

    assert list(metadata.keys()) == [
        "parameters",
        "quality_information",
    ]

    assert list(
        DwdObservationRequest.describe_fields(
            dataset=DwdObservationDataset.CLIMATE_SUMMARY,
            resolution=DwdObservationResolution.DAILY,
            period=DwdObservationPeriod.RECENT,
            language="de",
        )["parameters"].keys()
    ) == [
        "STATIONS_ID",
        "MESS_DATUM",
        "QN_3",
        "FX",
        "FM",
        "QN_4",
        "RSK",
        "RSKF",
        "SDK",
        "SHK_TAG",
        "NM",
        "VPM",
        "PM",
        "TMK",
        "UPM",
        "TXK",
        "TNK",
        "TGK",
    ]


def test_dwd_observation_metadata_describe_fields_solar_hourly():

    metadata = DwdObservationRequest.describe_fields(
        dataset=DwdObservationDataset.SOLAR,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        language="en",
    )

    assert list(metadata.keys()) == [
        "parameters",
        "quality_information",
    ]

    assert list(metadata["parameters"].keys()) == [
        "STATIONS_ID",
        "MESS_DATUM",
        "QN_592",
        "ATMO_STRAHL",
        "FD_STRAHL",
        "FG_STRAHL",
        "SD_STRAHL",
        "ZENITH",
    ]


def test_dwd_observation_metadata_describe_fields_temperature_10minutes():

    metadata = DwdObservationRequest.describe_fields(
        dataset=DwdObservationDataset.TEMPERATURE_AIR,
        resolution=DwdObservationResolution.MINUTE_10,
        period=DwdObservationPeriod.RECENT,
    )

    assert list(metadata.keys()) == [
        "parameters",
        "quality_information",
    ]

    assert list(metadata["parameters"].keys()) == [
        "STATIONS_ID",
        "MESS_DATUM",
        "QN",
        "PP_10",
        "TT_10",
        "TM5_10",
        "RF_10",
        "TD_10",
    ]
