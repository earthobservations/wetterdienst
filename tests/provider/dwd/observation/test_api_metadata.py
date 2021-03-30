# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationParameter,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)


def test_dwd_observation_metadata_discover_parameters():
    parameters = DwdObservationRequest.discover(filter_="minute_1", flatten=True)

    assert (
        json.dumps(
            {
                Resolution.MINUTE_1.name.lower(): [
                    DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT.name.lower(),
                    DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT_DROPLET.name.lower(),
                    DwdObservationParameter.MINUTE_1.PRECIPITATION_HEIGHT_ROCKER.name.lower(),
                    DwdObservationParameter.MINUTE_1.PRECIPITATION_FORM.name.lower(),
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
        "stations_id",
        "mess_datum",
        "qn_3",
        "fx",
        "fm",
        "qn_4",
        "rsk",
        "rskf",
        "sdk",
        "shk_tag",
        "nm",
        "vpm",
        "pm",
        "tmk",
        "upm",
        "txk",
        "tnk",
        "tgk",
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
        "stations_id",
        "mess_datum",
        "qn_3",
        "fx",
        "fm",
        "qn_4",
        "rsk",
        "rskf",
        "sdk",
        "shk_tag",
        "nm",
        "vpm",
        "pm",
        "tmk",
        "upm",
        "txk",
        "tnk",
        "tgk",
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
        "stations_id",
        "mess_datum",
        "qn_592",
        "atmo_strahl",
        "fd_strahl",
        "fg_strahl",
        "sd_strahl",
        "zenith",
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
        "stations_id",
        "mess_datum",
        "qn",
        "pp_10",
        "tt_10",
        "tm5_10",
        "rf_10",
        "td_10",
    ]
