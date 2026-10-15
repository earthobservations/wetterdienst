"""Tests for the names renamed on the way to 1.0."""

import pytest
from pydantic import ValidationError

from tests.test_api import ALL_METADATA
from wetterdienst import Options
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.metadata.renamed import RENAMED_PARAMETERS, RENAMED_PARAMETERS_IN_DATASET, RENAMED_RESOLUTIONS
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, MetadataModel, _find, _not_found, _spot_name, parse_parameters
from wetterdienst.provider.aemet.observation import AemetObservationMetadata
from wetterdienst.provider.chmi.observation import ChmiObservationMetadata
from wetterdienst.provider.dwd.dmo.metadata import DwdDmoMetadata
from wetterdienst.provider.dwd.mosmix.metadata import DwdMosmixMetadata
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.provider.dwd.swsmos.metadata import DwdSwsmosMetadata
from wetterdienst.provider.geosphere.observation import GeosphereObservationMetadata
from wetterdienst.provider.knmi.observation import KnmiObservationMetadata
from wetterdienst.provider.metno.frost.api import MetnoFrostMetadata


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


@pytest.mark.parametrize(
    ("resolution", "dataset", "original"),
    [(*key, original) for key, original in GRAUPEL_COLUMNS.items()],
    ids=[f"{resolution}/{dataset}" for resolution, dataset in GRAUPEL_COLUMNS],
)
def test_dwd_graupel_is_not_named_sleet(
    resolution: str, dataset: str, original: str, caplog: pytest.LogCaptureFixture
) -> None:
    """DWD's graupel columns are graupel, not sleet, and the sleet name answers with the one to use (GH-2696).

    `count_weather_type_sleet` stood for them, so that a caller asking for sleet days got days with
    graupel, while DWD publishes no sleet phenomenon in these datasets.
    """
    dataset_model = DwdObservationMetadata[resolution][dataset]
    graupel = [parameter for parameter in dataset_model if parameter.name_original == original]
    assert [parameter.name for parameter in graupel] == ["count_weather_type_graupel"]
    assert "count_weather_type_sleet" not in {parameter.name for parameter in dataset_model}

    assert parse_parameters(f"{resolution}/{dataset}/count_weather_type_sleet", DwdObservationMetadata) == []
    assert "It was renamed to 'count_weather_type_graupel'." in caplog.text


def test_sleet_as_a_station_distance_key_names_graupel() -> None:
    """The retired sleet name in `geo_station_distance` is refused with the name to use (GH-2696)."""
    with pytest.raises(ValidationError, match=r"'count_weather_type_sleet' is now 'count_weather_type_graupel'"):
        Options(geo_station_distance={"count_weather_type_sleet": 10.0})


def _find_dataset(metadata_name: str, resolution: str, dataset: str) -> DatasetModel:
    """Find the dataset a rename is declared for, by the metadata declaration's name."""
    metadata = next(metadata for metadata in ALL_METADATA if metadata.name == metadata_name)
    return metadata[resolution][dataset]


_RENAMES_IN_DATASET = [
    (metadata_name, resolution, dataset, old, new)
    for metadata_name, datasets in RENAMED_PARAMETERS_IN_DATASET.items()
    for (resolution, dataset), renames in datasets.items()
    for old, new in renames.items()
]


@pytest.mark.parametrize(
    ("metadata_name", "resolution", "dataset", "old", "new"),
    _RENAMES_IN_DATASET,
    ids=[f"{metadata}/{resolution}/{dataset}/{old}" for metadata, resolution, dataset, old, _ in _RENAMES_IN_DATASET],
)
def test_a_rename_in_a_dataset_leads_from_a_name_it_lacks_to_one_it_has(
    metadata_name: str, resolution: str, dataset: str, old: str, new: str
) -> None:
    """A rename in one dataset names a canonical parameter the dataset does not answer to, and one it holds.

    An old name that the dataset still answers to (as a canonical or as the source's own name)
    would never reach the hint, a new one it does not have would send the caller to a parameter
    that is not there, and an old name that is no canonical name at all is a misspelling that no
    caller wrote.
    """
    dataset_model = _find_dataset(metadata_name, resolution, dataset)
    assert old in PARAMETERS
    assert new in PARAMETERS
    assert _find(dataset_model.parameters, old) is None
    assert _find(dataset_model.parameters, new) is not None
    # one that holds in every dataset belongs in RENAMED_PARAMETERS
    assert old not in RENAMED_PARAMETERS


def test_a_rename_in_a_dataset_is_declared_for_a_dataset_of_the_provider() -> None:
    """The keys name a metadata declaration, a resolution and a dataset that exist."""
    names = {metadata.name for metadata in ALL_METADATA}
    assert sorted(set(RENAMED_PARAMETERS_IN_DATASET) - names) == []
    for metadata_name, datasets in RENAMED_PARAMETERS_IN_DATASET.items():
        for resolution, dataset in datasets:
            # raises a KeyError naming what is missing
            _find_dataset(metadata_name, resolution, dataset)


@pytest.mark.parametrize(
    ("metadata", "value", "message"),
    [
        # GH-2644: the old name stays valid elsewhere (NOAA's multiday maximum, the 12 h maximum of DWD's
        # other datasets), so the answer is the rename in this dataset and not the closest spelling, which
        # was `temperature_air_max_2m_mean` (the mean of the daily maxima: 10.4 for 15.7)
        (
            AemetObservationMetadata,
            "monthly/data/temperature_air_max_2m_multiday",
            "It was renamed to 'temperature_air_max_2m' in this dataset.",
        ),
        (
            AemetObservationMetadata,
            "annual/data/temperature_air_min_2m_multiday",
            "It was renamed to 'temperature_air_min_2m' in this dataset.",
        ),
        (
            DwdMosmixMetadata,
            "hourly/large/temperature_air_max_2m",
            "It was renamed to 'temperature_air_max_2m_last_12h' in this dataset.",
        ),
        (
            DwdDmoMetadata,
            "hourly/icon_eu/temperature_air_min_2m",
            "It was renamed to 'temperature_air_min_2m_last_12h' in this dataset.",
        ),
        (
            ChmiObservationMetadata,
            "monthly/data/temperature_air_max_2m",
            "It was renamed to 'temperature_air_max_2m_mean' in this dataset.",
        ),
        (
            KnmiObservationMetadata,
            "hourly/data/wind_direction",
            "It was renamed to 'wind_direction_last_10min' in this dataset.",
        ),
        # GH-2673: a `_mean_` temperature that moved to the spot name, which difflib took for another
        # quantity: the minimum, the 20 cm soil and the 10 cm grass temperature
        (
            GeosphereObservationMetadata,
            "10_minutes/data/temperature_air_mean_2m",
            "It is named 'temperature_air_2m' here, a reading at one moment, not a mean.",
        ),
        (
            GeosphereObservationMetadata,
            "hourly/data/temperature_soil_mean_2m",
            "It is named 'temperature_soil_2m' here, a reading at one moment, not a mean.",
        ),
        (
            KnmiObservationMetadata,
            "10_minutes/data/temperature_air_mean_2m",
            "It is named 'temperature_air_2m' here, a reading at one moment, not a mean.",
        ),
        (
            DwdObservationMetadata,
            "hourly/temperature_air/temperature_air_mean_2m",
            "It is named 'temperature_air_2m' here, a reading at one moment, not a mean.",
        ),
        (
            DwdSwsmosMetadata,
            "hourly/data/temperature_surface_mean",
            "It is named 'temperature_surface' here, a reading at one moment, not a mean.",
        ),
        # a name the dataset never had and no rule maps keeps the closest spelling
        (
            DwdObservationMetadata,
            "daily/kl/temperature_air_mean_200",
            "Did you mean 'temperature_air_mean_2m'?",
        ),
    ],
)
def test_a_name_a_dataset_lacks_is_answered_with_the_name_it_has(
    metadata: MetadataModel, value: str, message: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The warning for a parameter a dataset does not have names the one it has under another name."""
    assert parse_parameters(value, metadata) == []
    assert message in caplog.text
    # not a guess besides the answer
    assert caplog.text.count("Did you mean") == int("Did you mean" in message)


@pytest.mark.parametrize(
    ("metadata", "value"),
    [
        # GH-2924: the closest spelling was the air temperature, which is no dew point
        (DwdObservationMetadata, "daily/kl/temperature_dew_point_mean_2m"),
        # only `hourly/large` holds the error, `temperature_air_2m` is the temperature
        (DwdMosmixMetadata, "hourly/small/error_absolute_temperature_air_mean_2m"),
        # `error_absolute_` is the error of a quantity, not the quantity: the wind speed is no wind gust
        (DwdMosmixMetadata, "hourly/large/error_absolute_wind_gust_max"),
    ],
)
def test_a_name_of_another_quantity_is_not_guessed_at(
    metadata: MetadataModel, value: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A dataset without the quantity names none, and the list of what it has is the answer."""
    assert parse_parameters(value, metadata) == []
    assert "Did you mean" not in caplog.text
    assert "Available parameters:" in caplog.text


@pytest.mark.parametrize(
    ("value", "guess"),
    [
        ("daily/kl/temperature_air_mean_200", "temperature_air_mean_2m"),
        # a misspelled token in the part that names the quantity is still a typo of it
        ("daily/kl/temperatur_air_mean_2m", "temperature_air_mean_2m"),
        ("daily/kl/wind_sped", "wind_speed"),
        ("daily/kl/humidity_realtive", "humidity_relative"),
        # the source's own name is a candidate too, and a code has no quantity to compare
        ("daily/kl/tmkk", "tmk"),
        ("daily/kl/rsx", "rsk"),
        # a missing underscore is a typo of the whole name
        ("daily/kl/windspeed", "wind_speed"),
        ("daily/kl/wind_gustmax", "wind_gust_max"),
        ("daily/kl/temperatureair_mean_2m", "temperature_air_mean_2m"),
    ],
)
def test_a_typo_of_a_quantity_the_dataset_has_is_still_guessed_at(
    value: str, guess: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The guess is kept where it is the same quantity spelled differently."""
    assert parse_parameters(value, DwdObservationMetadata) == []
    assert f"Did you mean '{guess}'?" in caplog.text


@pytest.mark.parametrize("value", ["hourly/large/eror_absolute_wind_speed", "hourly/large/error_absolut_wind_speed"])
def test_a_misspelled_error_prefix_is_still_guessed_at(value: str, caplog: pytest.LogCaptureFixture) -> None:
    """`error_absolute_` is part of the name, so a typo in it is a typo of the quantity, not another one."""
    assert parse_parameters(value, DwdMosmixMetadata) == []
    assert "Did you mean 'error_absolute_wind_speed'?" in caplog.text


def test_a_rename_in_a_dataset_answers_attribute_and_item_access_too() -> None:
    """`dataset.<old>` and `dataset["<old>"]` name the new parameter, as a request for the old one does."""
    dataset = AemetObservationMetadata["monthly"]["data"]
    with pytest.raises(AttributeError, match=r"It was renamed to 'temperature_air_max_2m' in this dataset"):
        _ = dataset.temperature_air_max_2m_multiday
    with pytest.raises(KeyError, match=r"It was renamed to 'temperature_air_max_2m' in this dataset"):
        _ = dataset["temperature_air_max_2m_multiday"]


def test_a_rename_in_a_dataset_leaves_the_name_alone_in_a_dataset_that_has_it() -> None:
    """The old name still resolves where it is the parameter's own, which is why it is a rename per dataset."""
    assert [p.name for p in parse_parameters("daily/data/wind_speed", AemetObservationMetadata)] == ["wind_speed"]
    assert [p.name for p in parse_parameters("daily/data/wind_speed", KnmiObservationMetadata)] == ["wind_speed"]
    assert parse_parameters("hourly/data/wind_speed", AemetObservationMetadata) == []


def test_a_request_for_several_parameters_names_the_renamed_one_and_keeps_the_rest(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The old name is dropped with a hint that says what it is called, and the others are returned."""
    found = parse_parameters(
        ["hourly/large/temperature_air_max_2m", "hourly/large/temperature_air_2m"], DwdMosmixMetadata
    )
    assert [parameter.name for parameter in found] == ["temperature_air_2m"]
    assert "It was renamed to 'temperature_air_max_2m_last_12h' in this dataset." in caplog.text


@pytest.mark.parametrize(
    ("name", "spot"),
    [
        ("temperature_air_mean_2m", "temperature_air_2m"),
        ("temperature_dew_point_mean_2m", "temperature_dew_point_2m"),
        ("temperature_soil_mean_0_05m", "temperature_soil_0_05m"),
        ("temperature_soil_mean_2m", "temperature_soil_2m"),
        ("temperature_surface_mean", "temperature_surface"),
        ("error_absolute_temperature_air_mean_2m", "error_absolute_temperature_air_2m"),
        # the mean of an extreme, or of a window, is no reading's mean: nothing succeeded it
        ("temperature_air_max_2m_mean", None),
        ("temperature_air_min_2m_mean", None),
        ("temperature_air_mean_2m_last_24h", None),
        ("temperature_soil_mean_loamy_sand_0_05m", None),
        ("humidity_relative_mean", None),
        ("temperature_air_2m", None),
    ],
)
def test_the_spot_name_of_a_mean_temperature(name: str, spot: str | None) -> None:
    """A sub-daily `_mean_` temperature of a reading maps to its spot name, any other name to none."""
    assert _spot_name(name) == spot


def test_the_hint_never_names_a_parameter_the_dataset_lacks() -> None:
    """A dataset without the name a rule produces is not answered with it.

    `daily/kl` has neither `temperature_dew_point_2m` (the spot name of the mean below) nor
    `visibility` (the rename of `visibility_range`), so neither is offered.
    """
    dataset = DwdObservationMetadata["daily"]["kl"]
    assert _spot_name("temperature_dew_point_mean_2m") == "temperature_dew_point_2m"
    assert _find(dataset.parameters, "temperature_dew_point_2m") is None
    assert RENAMED_PARAMETERS["visibility_range"] == "visibility"
    assert _find(dataset.parameters, "visibility") is None
    for item in ("temperature_dew_point_mean_2m", "visibility_range"):
        message = _not_found("parameters", item, dataset.parameters, dataset)
        assert "It is named" not in message
        assert "renamed" not in message


def test_the_spot_name_is_offered_for_a_sub_daily_dataset_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """A daily or coarser `_mean_` is the source's mean or one it keeps, not a rename to a reading.

    A coarse dataset that holds a spot name beside the mean it is asked for would otherwise be
    said to have renamed it to a reading at one moment, which the source does not state there.
    """
    daily = DwdObservationMetadata["daily"]["kl"]
    hourly = DwdObservationMetadata["hourly"]["temperature_air"]
    assert _find(hourly.parameters, "temperature_air_2m") is not None
    message = _not_found("parameters", "temperature_air_mean_2m", hourly.parameters, hourly)
    assert "It is named 'temperature_air_2m' here" in message
    # the same dataset taken for a daily one has its spot name, which is not answered for a mean
    monkeypatch.setattr(hourly, "resolution", daily.resolution)
    assert "It is named" not in _not_found("parameters", "temperature_air_mean_2m", hourly.parameters, hourly)


@pytest.mark.parametrize("metadata", ALL_METADATA, ids=lambda metadata: metadata.name)
def test_every_resolution_knows_the_declaration_it_belongs_to(metadata: MetadataModel) -> None:
    """The rename of a dataset is looked up by its declaration, so each resolution must carry the name."""
    assert metadata.name
    assert {resolution.metadata_name for resolution in metadata} == {metadata.name}


def test_mosmix_names_the_error_of_a_temperature_after_the_temperature(caplog: pytest.LogCaptureFixture) -> None:
    """The error of `ttt` and `td` is named after `temperature_air_2m` and `temperature_dew_point_2m` (GH-2659).

    A caller pairs a value with its error by name, which `error_absolute_temperature_air_mean_2m`
    did not allow once `ttt` was no mean. The old names answer with the new ones, also as a key of
    `geo_station_distance`.
    """
    # only `large` holds the errors, `small` has `ttt` and `td` alone
    names = {parameter.name_original: parameter.name for parameter in DwdMosmixMetadata["hourly"]["large"]}
    assert names["ttt"] == "temperature_air_2m"
    assert names["e_ttt"] == "error_absolute_temperature_air_2m"
    assert names["td"] == "temperature_dew_point_2m"
    assert names["e_td"] == "error_absolute_temperature_dew_point_2m"
    assert PARAMETERS["error_absolute_temperature_air_2m"].unit_type == PARAMETERS["temperature_air_2m"].unit_type
    assert (
        PARAMETERS["error_absolute_temperature_dew_point_2m"].unit_type
        == PARAMETERS["temperature_dew_point_2m"].unit_type
    )
    for old in ("error_absolute_temperature_air_mean_2m", "error_absolute_temperature_dew_point_mean_2m"):
        assert old not in PARAMETERS
        assert parse_parameters(f"hourly/large/{old}", DwdMosmixMetadata) == []
        assert f"It was renamed to '{old.replace('_mean', '')}'." in caplog.text
    with pytest.raises(ValidationError, match=r"'error_absolute_temperature_air_mean_2m' is now 'error_absolute"):
        Options(geo_station_distance={"error_absolute_temperature_air_mean_2m": 10.0})


def test_a_renamed_resolution_is_refused_with_the_new_value_named(caplog: pytest.LogCaptureFixture) -> None:
    """`6_hour` is `6_hours` (GH-2641): not accepted, and the refusal says what it is called now.

    Every rename leads from a value `Resolution` no longer has to one it does, which keeps the old one refused.
    """
    values = {resolution.value for resolution in Resolution}
    assert sorted(old for old in RENAMED_RESOLUTIONS if old in values) == []
    assert sorted(new for new in RENAMED_RESOLUTIONS.values() if new not in values) == []
    assert RENAMED_RESOLUTIONS == {"6_hour": "6_hours"}
    assert Resolution.HOUR_6.value == "6_hours"
    with pytest.raises(ValueError, match="'6_hour' is not a valid Resolution"):
        Resolution("6_hour")

    assert parse_parameters("6_hour/data/precipitation_amount", MetnoFrostMetadata) == []
    assert "'6_hour'. It was renamed to '6_hours'. Available resolutions:" in caplog.text
    assert [parameter.name for parameter in parse_parameters("6_hours/data", MetnoFrostMetadata)] == [
        "precipitation_amount"
    ]
    with pytest.raises(KeyError, match="It was renamed to '6_hours'"):
        MetnoFrostMetadata["6_hour"]
    with pytest.raises(ValidationError, match=r"\['6_hour'\] not in .*\('6_hour' is now '6_hours'\)"):
        Options(geo_station_distance_resolution_factors={"6_hour": 1.0})
    options = Options(geo_station_distance_resolution_factors={"6_hours": 1.0})
    assert options.geo_station_distance_resolution_factors == {"6_hours": 1.0}
