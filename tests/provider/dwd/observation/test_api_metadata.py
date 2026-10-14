# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation metadata."""

import pytest

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)


def test_dwd_observation_metadata_discover_parameters() -> None:
    """Test DWD observation discover parameters."""
    metadata = DwdObservationRequest.discover()
    expected = {
        "1_minute": {
            "precipitation": [
                {
                    "name": "precipitation_amount",
                    "name_original": "rs_01",
                    "unit_type": "precipitation",
                    "unit": "millimeter",
                },
                {
                    "name": "precipitation_amount_droplet",
                    "name_original": "rth_01",
                    "unit_type": "precipitation",
                    "unit": "millimeter",
                },
                {
                    "name": "precipitation_amount_rocker",
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
            ],
        },
    }
    # compare the fields this test is about rather than a serialised substring, which broke as soon
    # as discover() gained a key
    actual = {
        resolution: {
            dataset: [
                {k: p[k] for k in ("name", "name_original", "unit_type", "unit")} for p in described["parameters"]
            ]
            for dataset, described in entry["datasets"].items()
        }
        for resolution, entry in metadata.items()
        if resolution == "1_minute"
    }
    assert actual == expected
    # descriptions come from the source sheets and are reported alongside, at every level
    precipitation = metadata["1_minute"]["datasets"]["precipitation"]
    assert all(p["description"] for p in precipitation["parameters"])
    assert precipitation["description"]
    assert metadata["subdaily"]["description"] == "measurements at 7am, 2pm, 9pm."


@pytest.mark.remote
def test_dwd_observation_metadata_describe_fields_kl_daily_english() -> None:
    """Test DWD observation describe fields for daily climate data."""
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


@pytest.mark.remote
def test_dwd_observation_metadata_describe_fields_kl_daily_german() -> None:
    """Test metadata for daily climate data."""
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
def test_dwd_observation_metadata_describe_fields_solar_hourly() -> None:
    """Test metadata for hourly solar data."""
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
def test_dwd_observation_metadata_describe_fields_temperature_10minutes() -> None:
    """Test metadata for 10 minute temperature data."""
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


def test_dwd_observation_no_declared_parameter_is_dropped() -> None:
    """Test that nothing is declared as a parameter and dropped from the data at the same time.

    A parameter listed in the metadata is offered everywhere the metadata is read -- `discover()`,
    the REST coverage endpoint, the MCP tools, the docs tables -- so dropping its column means
    advertising a field that answers every request with an empty frame. Seven did exactly that
    before this check existed.
    """
    from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.parser import DROPPABLE_PARAMETERS  # noqa: PLC0415

    declared = {
        (resolution.name, dataset.name, parameter.name_original)
        for resolution in DwdObservationMetadata
        for dataset in resolution
        for parameter in dataset.parameters
    }
    both = sorted(site for site in declared if site[2] in DROPPABLE_PARAMETERS)
    assert not both, f"declared as parameters but dropped from the data: {both}"


@pytest.mark.parametrize(
    ("resolution", "dataset", "original", "until"),
    [
        ("10_minutes", "temperature_extreme", "tx5_10", "2009"),
        ("hourly", "temperature_soil", "v_te002", "2019"),
    ],
)
def test_dwd_observation_a_parameter_of_the_historical_files_says_so(
    resolution: str, dataset: str, original: str, until: str
) -> None:
    """Test that a parameter only the historical files fill says where it ends (GH-2852).

    DWD's `recent` (and `now`) files carry `TX5_10` and `V_TE002` as `-999` at every station, as the
    historical files do from 2010 and 2020 on. The parameters stay declared, since the historical period
    delivers them, so what keeps a request for `recent` from reading as a failure is the description.
    """
    from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata  # noqa: PLC0415

    parameter = next(p for p in DwdObservationMetadata[resolution][dataset].parameters if p.name_original == original)
    assert "Only the historical files carry a value" in parameter.description
    assert f"up to {until}" in parameter.description
