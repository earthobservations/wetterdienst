"""Tests for the names renamed on the way to 1.0."""

import pytest

from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.metadata.renamed import RENAMED_PARAMETERS
from wetterdienst.model.metadata import MetadataModel, parse_parameters
from wetterdienst.provider.dwd.dmo.metadata import DwdDmoMetadata
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata


def test_renamed_parameters_point_from_a_retired_name_to_a_canonical_one() -> None:
    """Every rename leads from a name the table no longer has to one it does.

    An old name back in the table would be answered by the table rather than by the rename, and a
    new name missing from it would send the caller to a parameter that does not exist.
    """
    names = {parameter.name for parameter in PARAMETER_TABLE}
    assert sorted(old for old in RENAMED_PARAMETERS if old in names) == []
    assert sorted(new for new in RENAMED_PARAMETERS.values() if new not in names) == []


@pytest.mark.parametrize("metadata", [DwdDmoMetadata, DwdMosmixMetadata], ids=["dmo", "mosmix"])
def test_dwd_low_cloud_cover_is_named_for_2km(metadata: MetadataModel, caplog: pytest.LogCaptureFixture) -> None:
    """DWD's `nl` is low cloud below 2 km, and is named and described so (GH-1977).

    It was `cloud_cover_below_1000ft`, a height off by a factor of 6.5, and that name now answers
    with the one to use instead.
    """
    low_cloud = [
        parameter
        for resolution in metadata
        for dataset in resolution
        for parameter in dataset
        if parameter.name_original == "nl"
    ]
    assert low_cloud
    assert {parameter.name for parameter in low_cloud} == {"cloud_cover_below_2km"}
    assert PARAMETERS["cloud_cover_below_2km"].description == "Fraction of the sky covered by cloud below 2 km."

    dataset = low_cloud[0].dataset
    old = f"{dataset.resolution.name}/{dataset.name}/cloud_cover_below_1000ft"
    assert parse_parameters(old, metadata) == []
    assert "It was renamed to 'cloud_cover_below_2km'." in caplog.text


GRAUPEL_COLUMNS = {
    ("daily", "weather_phenomena"): "graupel",
    ("daily", "weather_phenomena_more"): "rr_graupel",
    ("monthly", "weather_phenomena"): "mo_graupel",
    ("annual", "weather_phenomena"): "ja_graupel",
}


@pytest.mark.parametrize(("resolution", "dataset"), list(GRAUPEL_COLUMNS), ids=str)
def test_dwd_graupel_is_not_named_sleet(resolution: str, dataset: str, caplog: pytest.LogCaptureFixture) -> None:
    """DWD's graupel columns are graupel, not sleet, and the sleet name answers with the one to use (GH-2696).

    `count_weather_type_sleet` stood for them, so that a caller asking for sleet days got days with
    graupel, while DWD publishes no sleet phenomenon in these datasets.
    """
    dataset_model = DwdObservationMetadata[resolution][dataset]
    original = GRAUPEL_COLUMNS[(resolution, dataset)]
    graupel = [parameter for parameter in dataset_model if parameter.name_original == original]
    assert [parameter.name for parameter in graupel] == ["count_weather_type_graupel"]
    assert "count_weather_type_sleet" not in {parameter.name for parameter in dataset_model}
    assert PARAMETERS["count_weather_type_graupel"].description == "Number of days on which graupel was observed."

    assert parse_parameters(f"{resolution}/{dataset}/count_weather_type_sleet", DwdObservationMetadata) == []
    assert "It was renamed to 'count_weather_type_graupel'." in caplog.text
