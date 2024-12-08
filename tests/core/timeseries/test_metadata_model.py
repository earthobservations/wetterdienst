import pytest

from wetterdienst.core.timeseries.metadata import ParameterSearch, parse_parameters
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata


@pytest.mark.parametrize(
    "value,expected",
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
def test_parameter_search(value, expected):
    parameter_template = ParameterSearch.parse(value)
    assert parameter_template == expected


@pytest.mark.parametrize(
    "value,expected",
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
def test_parse_parameters(value, expected):
    assert parse_parameters(value, DwdObservationMetadata) == expected
