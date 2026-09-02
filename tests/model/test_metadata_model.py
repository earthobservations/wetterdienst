# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for metadata models."""

import re

import pytest

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import (
    ParameterModel,
    ParameterSearch,
    group_parameters_by_dataset,
    parse_parameters,
)
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("daily/climate_summary", ParameterSearch("daily", "climate_summary")),
        (
            "daily/climate_summary/temperature_air_mean_2m",
            ParameterSearch("daily", "climate_summary", "temperature_air_mean_2m"),
        ),
        (("daily", "climate_summary"), ParameterSearch("daily", "climate_summary")),
        (
            ("daily", "climate_summary", "temperature_air_mean_2m"),
            ParameterSearch("daily", "climate_summary", "temperature_air_mean_2m"),
        ),
        (DwdObservationMetadata.daily.climate_summary, ParameterSearch("daily", "climate_summary")),
        (
            DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m,
            ParameterSearch("daily", "climate_summary", "temperature_air_mean_2m"),
        ),
        # other separators
        ("daily.climate_summary", ParameterSearch("daily", "climate_summary")),
        ("daily:climate_summary", ParameterSearch("daily", "climate_summary")),
    ],
)
def test_parameter_search(value: str | ParameterModel, expected: ParameterModel) -> None:
    """Test parsing of parameters into a search object."""
    parameter_template = ParameterSearch.parse(value)
    assert parameter_template == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("daily/climate_summary", [*DwdObservationMetadata.daily.climate_summary]),
        (
            "daily/climate_summary/temperature_air_mean_2m",
            [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m],
        ),
        (("daily/climate_summary",), [*DwdObservationMetadata.daily.climate_summary]),
        (
            ("daily/climate_summary/temperature_air_mean_2m",),
            [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m],
        ),
        (("daily", "climate_summary"), [*DwdObservationMetadata.daily.climate_summary]),
        (
            ("daily", "climate_summary", "temperature_air_mean_2m"),
            [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m],
        ),
        ([("daily", "climate_summary")], [*DwdObservationMetadata.daily.climate_summary]),
        (
            [("daily", "climate_summary", "temperature_air_mean_2m")],
            [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m],
        ),
        # other
        # lowercase/uppercase
        ("DAILY/CLIMATE_SUMMARY", [*DwdObservationMetadata.daily.climate_summary]),
        ("DAILY/climate_summary", [*DwdObservationMetadata.daily.climate_summary]),
        ("daily/CLIMATE_SUMMARY", [*DwdObservationMetadata.daily.climate_summary]),
        # original names
        ("1_minute/precipitation", [*DwdObservationMetadata.minute_1.precipitation]),
        ("daily/kl", [*DwdObservationMetadata.daily.climate_summary]),
        ("daily/kl/rsk", [DwdObservationMetadata.daily.climate_summary.precipitation_height]),
        # models
        (DwdObservationMetadata.daily.climate_summary, [*DwdObservationMetadata.daily.climate_summary]),
        (
            DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m,
            [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m],
        ),
        ((DwdObservationMetadata.daily.climate_summary,), [*DwdObservationMetadata.daily.climate_summary]),
        (
            (DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m,),
            [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m],
        ),
        # other separators
        ("daily.climate_summary", [*DwdObservationMetadata.daily.climate_summary]),
        ("daily:climate_summary", [*DwdObservationMetadata.daily.climate_summary]),
        (("daily.climate_summary",), [*DwdObservationMetadata.daily.climate_summary]),
        (
            ("daily.climate_summary.temperature_air_mean_2m",),
            [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m],
        ),
        (("daily:climate_summary",), [*DwdObservationMetadata.daily.climate_summary]),
        (
            ("daily:climate_summary:temperature_air_mean_2m",),
            [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m],
        ),
    ],
)
def test_parse_parameters(value: str | ParameterModel, expected: ParameterModel) -> None:
    """Test parsing of parameters."""
    assert parse_parameters(value, DwdObservationMetadata) == expected


@pytest.mark.parametrize(
    ("value", "error", "message"),
    [
        # too few, too many or empty parts
        ("daily", ValueError, "expected 'resolution/dataset'"),
        ("a/b/c/d", ValueError, "expected 'resolution/dataset'"),
        (("daily",), ValueError, "expected 'resolution/dataset'"),
        ("daily/", ValueError, "expected 'resolution/dataset'"),
        # parts that are not names
        (("daily", 1), TypeError, "expected the parts as strings, got int '1'"),
        ((Resolution.DAILY, "climate_summary"), TypeError, "expected the parts as strings, got Resolution"),
        (Resolution.DAILY, TypeError, "got Resolution"),
    ],
)
def test_parameter_search_invalid(value: str | tuple, error: type[Exception], message: str) -> None:
    """Test that a malformed parameter says what shape was expected instead of failing to unpack."""
    with pytest.raises(error, match=re.escape(message)):
        ParameterSearch.parse(value)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("dayly/kl", "'dayly'. Did you mean 'daily'? Available resolutions:"),
        ("daily/klx", "'klx'. Did you mean 'kl'? Available datasets:"),
        (
            "daily/kl/temperature_air_mean_200",
            "'temperature_air_mean_200'. Did you mean 'temperature_air_mean_2m'? Available parameters:",
        ),
        ("daily/kl/quality_wind", "'quality_wind' is a quality flag."),
    ],
)
def test_parse_parameters_not_found(value: str, message: str, caplog: pytest.LogCaptureFixture) -> None:
    """Test that a parameter that cannot be resolved is warned about with the reason."""
    assert parse_parameters(value, DwdObservationMetadata) == []
    assert message in caplog.text
    assert caplog.records[0].levelname == "WARNING"


def test_parse_parameters_deduplicated() -> None:
    """Test that a parameter requested twice, directly and via its dataset, is only returned once."""
    parameters = parse_parameters(
        ["daily/climate_summary", "daily/kl", "daily/kl/temperature_air_mean_2m"],
        DwdObservationMetadata,
    )
    assert parameters == [*DwdObservationMetadata.daily.climate_summary]


def test_parse_parameters_iterator() -> None:
    """Test that an iterator is not exhausted by the checks that classify the argument."""
    parameters = parse_parameters(iter(["daily/kl/temperature_air_mean_2m"]), DwdObservationMetadata)
    assert parameters == [DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m]


def test_parse_parameters_wrong_type() -> None:
    """Test that a parameter of an unsupported type is named as such."""
    with pytest.raises(TypeError, match="got int"):
        parse_parameters(1, DwdObservationMetadata)
    with pytest.raises(TypeError, match="expected the parts as strings, got Resolution"):
        parse_parameters([(Resolution.DAILY, "climate_summary")], DwdObservationMetadata)


@pytest.mark.parametrize(
    "item",
    ["climate_summary", "CLIMATE_SUMMARY", "kl", "KL", " kl "],
)
def test_lookup_case_insensitive(item: str) -> None:
    """Test that item and attribute lookup accept either name in any case."""
    assert DwdObservationMetadata.daily[item] == DwdObservationMetadata.daily.climate_summary
    assert getattr(DwdObservationMetadata.daily, item) == DwdObservationMetadata.daily.climate_summary


@pytest.mark.parametrize(
    "lookup", [lambda: DwdObservationMetadata.daily["klx"], lambda: DwdObservationMetadata.daily.klx]
)
def test_lookup_suggests(lookup: object) -> None:
    """Test that a failed lookup suggests the closest name."""
    with pytest.raises((KeyError, AttributeError), match="Did you mean 'kl'"):
        lookup()


def test_parse_parameters_malformed_is_skipped(caplog: pytest.LogCaptureFixture) -> None:
    """Test that a malformed parameter is skipped like an unknown one, not raised to the caller.

    A trailing separator is easy to produce from CLI or REST input and used to be answered with
    the whole dataset; taking the parameters listed next to it down with it would be worse than
    either.
    """
    parameters = parse_parameters(["daily/kl/", "daily/solar"], DwdObservationMetadata)
    assert parameters == [*DwdObservationMetadata.daily.solar]
    assert "'daily/kl/' could not be parsed as a parameter" in caplog.text


def test_group_parameters_by_dataset_groups_a_dataset_asked_for_twice() -> None:
    """A dataset interleaved with another must form one group, not one per run.

    ``parse_parameters`` keeps the order the caller asked in, so ``itertools.groupby`` -- which
    only groups consecutive items -- split ``climate_summary`` into two groups here. Downstream
    that fetched and parsed it twice, and put a duplicate station row in the frames built from it.
    """
    parameters = parse_parameters(
        [
            "daily/kl/temperature_air_mean_2m",
            "daily/more_precip/precipitation_height",
            "daily/kl/precipitation_height",
        ],
        DwdObservationMetadata,
    )

    groups = group_parameters_by_dataset(parameters)

    assert [(dataset.name, [parameter.name for parameter in grouped]) for dataset, grouped in groups] == [
        ("climate_summary", ["temperature_air_mean_2m", "precipitation_height"]),
        ("precipitation_more", ["precipitation_height"]),
    ]
