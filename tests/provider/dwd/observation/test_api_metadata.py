# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json

import pytest

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)


def test_dwd_observation_metadata_discover_parameters():
    metadata = DwdObservationRequest.discover()
    expected = {
        "1_minute": {
            "precipitation": [
                {
                    "name": "precipitation_height",
                    "name_original": "rs_01",
                    "unit_type": "precipitation",
                    "unit": "millimeter",
                },
                {
                    "name": "precipitation_height_droplet",
                    "name_original": "rth_01",
                    "unit_type": "precipitation",
                    "unit": "millimeter",
                },
                {
                    "name": "precipitation_height_rocker",
                    "name_original": "rwh_01",
                    "unit_type": "precipitation",
                    "unit": "millimeter",
                },
                {
                    "name": "precipitation_index",
                    "name_original": "rs_ind_01",
                    "unit_type": "dimensionless",
                    "unit": "dimensionless",
                },
            ]
        },
    }
    assert json.dumps(expected)[:-1] in json.dumps(metadata)


@pytest.mark.xfail
@pytest.mark.remote
def test_dwd_observation_metadata_describe_fields_kl_daily_english():
    metadata = DwdObservationRequest.describe_fields(
        dataset=("daily", "climate_summary"),
        period="recent",
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


@pytest.mark.xfail
@pytest.mark.remote
def test_dwd_observation_metadata_describe_fields_kl_daily_german():
    metadata = DwdObservationRequest.describe_fields(
        dataset=("daily", "climate_summary"),
        period="recent",
        language="de",
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


@pytest.mark.xfail
@pytest.mark.remote
def test_dwd_observation_metadata_describe_fields_solar_hourly():
    metadata = DwdObservationRequest.describe_fields(
        dataset=("hourly", "solar"),
        period="recent",
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


@pytest.mark.xfail
@pytest.mark.remote
def test_dwd_observation_metadata_describe_fields_temperature_10minutes():
    metadata = DwdObservationRequest.describe_fields(
        dataset=("minute_10", "temperature_air"),
        period="recent",
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
