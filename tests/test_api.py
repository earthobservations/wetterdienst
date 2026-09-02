# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the API."""

import collections
import zoneinfo
from datetime import datetime
from typing import get_args

import polars as pl
import pytest
from fsspec.exceptions import FSTimeoutError
from pydantic import ValidationError

from tests.conftest import IS_CI, IS_WINDOWS
from wetterdienst import Settings
from wetterdienst.api import Wetterdienst
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.metadata.unit_type import UnitType
from wetterdienst.model.metadata import ParameterModel, build_metadata_model
from wetterdienst.model.unit import UnitConverter
from wetterdienst.provider.aemet.observation import AemetObservationMetadata, AemetObservationRequest
from wetterdienst.provider.chmi.observation import ChmiObservationMetadata, ChmiObservationRequest
from wetterdienst.provider.dmi.observation import DmiObservationMetadata, DmiObservationRequest
from wetterdienst.provider.dwd.derived.metadata import DwdDerivedMetadata
from wetterdienst.provider.dwd.dmo import DwdDmoMetadata, DwdDmoRequest
from wetterdienst.provider.dwd.mosmix import DwdMosmixMetadata, DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationMetadata, DwdObservationRequest
from wetterdienst.provider.dwd.phenology import DwdPhenologyMetadata
from wetterdienst.provider.dwd.poi import DwdPoiMetadata
from wetterdienst.provider.dwd.road import DwdRoadMetadata, DwdRoadRequest
from wetterdienst.provider.dwd.swsmos import DwdSwsmosMetadata
from wetterdienst.provider.ea.hydrology import EAHydrologyMetadata, EAHydrologyRequest
from wetterdienst.provider.eaufrance.hubeau import HubeauMetadata, HubeauRequest
from wetterdienst.provider.eccc.observation import EcccObservationMetadata, EcccObservationRequest
from wetterdienst.provider.fmi.observation import FmiObservationMetadata, FmiObservationRequest
from wetterdienst.provider.geosphere.observation import GeosphereObservationMetadata, GeosphereObservationRequest
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyMetadata, ImgwHydrologyRequest
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyMetadata, ImgwMeteorologyRequest
from wetterdienst.provider.ipma.observation import IpmaObservationMetadata
from wetterdienst.provider.knmi.observation import KnmiObservationMetadata, KnmiObservationRequest
from wetterdienst.provider.lhmt.observation import LhmtObservationMetadata
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationMetadata, MeteoFranceObservationRequest
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopMetadata, MeteoFranceSynopRequest
from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationMetadata, MeteoswissObservationRequest
from wetterdienst.provider.metno.frost.api import MetnoFrostMetadata, MetnoFrostRequest
from wetterdienst.provider.metoffice.observation import MetOfficeObservationMetadata
from wetterdienst.provider.noaa.ghcn import NoaaGhcnMetadata, NoaaGhcnRequest
from wetterdienst.provider.nws.observation import NwsObservationMetadata, NwsObservationRequest
from wetterdienst.provider.rmi.observation import RmiObservationMetadata, RmiObservationRequest
from wetterdienst.provider.smhi.observation import SmhiObservationMetadata, SmhiObservationRequest
from wetterdienst.provider.wsv.pegel import WsvPegelMetadata, WsvPegelRequest
from wetterdienst.util.eccodes import ensure_eccodes, ensure_pdbufr

# every provider/network that exposes a metadata model (dwd/radar and dwd/alerts have none)
ALL_METADATA = [
    AemetObservationMetadata,
    ChmiObservationMetadata,
    DmiObservationMetadata,
    DwdDerivedMetadata,
    DwdDmoMetadata,
    DwdMosmixMetadata,
    DwdObservationMetadata,
    DwdPhenologyMetadata,
    DwdPoiMetadata,
    DwdRoadMetadata,
    DwdSwsmosMetadata,
    EAHydrologyMetadata,
    EcccObservationMetadata,
    FmiObservationMetadata,
    GeosphereObservationMetadata,
    HubeauMetadata,
    ImgwHydrologyMetadata,
    ImgwMeteorologyMetadata,
    IpmaObservationMetadata,
    KnmiObservationMetadata,
    LhmtObservationMetadata,
    MeteoFranceObservationMetadata,
    MeteoFranceSynopMetadata,
    MeteoswissObservationMetadata,
    MetnoFrostMetadata,
    MetOfficeObservationMetadata,
    NoaaGhcnMetadata,
    NwsObservationMetadata,
    RmiObservationMetadata,
    SmhiObservationMetadata,
    WsvPegelMetadata,
]

DF_STATIONS_MINIMUM_COLUMNS = {
    "resolution",
    "dataset",
    "station_id",
    "start_date",
    "end_date",
    "latitude",
    "longitude",
    "height",
    "name",
    "state",
}
DF_VALUES_MINIMUM_COLUMNS = {"resolution", "dataset", "station_id", "parameter", "date", "value", "quality"}


def _is_complete_stations_df(
    df: pl.DataFrame,
    exclude_columns: set[str] | None = None,
) -> bool:
    columns = DF_STATIONS_MINIMUM_COLUMNS
    exclude_columns = exclude_columns or set()
    columns = columns - exclude_columns
    return df.select(columns).select(pl.all_horizontal(pl.all().is_not_null().all())).to_series().all()


def _is_complete_values_df(
    df: pl.DataFrame,
) -> bool:
    columns = DF_VALUES_MINIMUM_COLUMNS - {"value", "quality"}
    return df.select(columns).select(pl.all_horizontal(pl.all().is_not_null().all())).to_series().all()


@pytest.fixture
def unit_converter() -> UnitConverter:
    """Provide unit converter."""
    return UnitConverter()


@pytest.fixture
def unit_converter_unit_type_units(unit_converter: UnitConverter) -> dict:
    """Provide dictionary of unit types and their units."""
    return {unit_type: [unit.name for unit in units] for unit_type, units in unit_converter.units.items()}


@pytest.mark.parametrize(
    ("provider", "network"),
    [(provider, network) for provider in Wetterdienst.registry for network in Wetterdienst.registry[provider]],
)
def test_wetterdienst_api(provider: str, network: str) -> None:
    """Test wetterdienst API."""
    request = Wetterdienst.resolve(provider, network)
    assert request


@pytest.mark.parametrize(
    "metadata",
    ALL_METADATA,
)
def test_metadata_units(unit_converter: UnitConverter, unit_converter_unit_type_units: dict, metadata: dict) -> None:
    """Test metadata units."""
    for resolution in metadata:
        for dataset in resolution:
            for parameter in dataset:
                assert parameter.unit_type in unit_converter.targets
                assert parameter.unit in unit_converter_unit_type_units[parameter.unit_type]


def test_unit_type_matches_unit_converter(unit_converter: UnitConverter) -> None:
    """Test that the `UnitType` literal and the unit converter describe the same vocabulary.

    `UnitType` has to restate the keys of `UnitConverter.units`, which are built as a dict literal
    at runtime and so cannot be turned into a static type. That makes it a second place the same
    vocabulary is written down, which is only safe while the two are pinned together. Checked in
    both directions: a unit type added to the converter but not the literal cannot be named by a
    parameter, and one added to the literal but not the converter has no target unit to convert to.
    """
    assert set(get_args(UnitType)) == set(unit_converter.units)
    assert set(get_args(UnitType)) == set(unit_converter.targets)


def test_every_resolution_and_period_is_served_by_a_provider() -> None:
    """Test that neither vocabulary carries a member no provider declares.

    Both are closed vocabularies rather than free labels: `Resolution` validates the keys of
    `ts_geo_station_distance_resolution_factors`, is looked up by name in `Frequency`, and is
    restated in the app's types. A member nothing serves is therefore a setting that can be
    written and never read, and a value the app can offer that no request answers. That is what
    `undefined` and `dynamic` became once the providers resolving to them started reporting the
    interval each station records at.

    dwd/radar and dwd/alerts declare no metadata model and so are not counted here; radar's own
    resolutions are `5_minutes`, `hourly` and `daily`, all of which other networks declare too.
    """
    resolutions = set()
    periods = set()
    for metadata in ALL_METADATA:
        for resolution in metadata:
            resolutions.add(resolution.value)
            for dataset in resolution:
                periods.update(dataset.periods)
    assert resolutions == set(Resolution)
    assert periods == set(Period)


def test_parameter_table_unit_types(unit_converter: UnitConverter) -> None:
    """Test that every canonical unit type is one the unit converter can convert to.

    `UnitType` makes this a type error too, but only for code the type checker sees. The table is
    data, and a wrong-but-valid unit type -- `pressure` where `temperature` was meant -- is not a
    typo the literal can catch.
    """
    for parameter in PARAMETER_TABLE:
        assert parameter.unit_type in unit_converter.targets, parameter.name


def test_parameter_table_descriptions() -> None:
    """Test that every canonical parameter says what it is, in one well-formed sentence.

    The description is what the docs glossary, the REST API and the MCP tools show a user who does
    not already know what a parameter measures. `CanonicalParameter.description` is a required
    field, so omitting one is a type error; what remains for this test is that it is not empty,
    that it reads as a sentence, and that it is distinct. That last check is the one with teeth: a
    description repeated across two parameters means at least one is not describing itself.
    """
    missing = sorted(p.name for p in PARAMETER_TABLE if not p.description)
    assert not missing, f"canonical parameters with an empty description: {missing}"
    malformed = sorted(
        p.name for p in PARAMETER_TABLE if not p.description[0].isupper() or not p.description.endswith(".")
    )
    assert not malformed, f"descriptions must be a capitalised sentence ending in a period: {malformed}"
    seen = collections.Counter(p.description for p in PARAMETER_TABLE)
    duplicated = sorted(description for description, count in seen.items() if count > 1)
    assert not duplicated, f"descriptions shared by more than one parameter: {duplicated}"


def test_interpolation_behaviour_derives_from_parameter_table() -> None:
    """Test that nothing keeps its own copy of which parameters may be interpolated.

    Which parameters may be interpolated, which get the shorter search radius and which get
    occurrence thresholding used to be three hand-written name lists in three modules, kept in step
    by a test that they were at least spelled correctly. They are views of
    `CanonicalParameter.interpolation` and `.zero_inflated` now, and this asserts they still are --
    a list written out again by hand would drift from the table exactly as before.
    """
    from wetterdienst.model.request import TimeseriesRequest  # noqa: PLC0415
    from wetterdienst.settings import (  # noqa: PLC0415
        _STATION_DISTANCE_HETEROGENEOUS,
        _STATION_DISTANCE_HOMOGENEOUS,
        _build_geo_station_distance,
    )

    assert set(TimeseriesRequest.interpolatable_parameters) == {p.name for p in PARAMETER_TABLE if p.interpolation}
    default_distances = _build_geo_station_distance(
        _STATION_DISTANCE_HOMOGENEOUS,
        _STATION_DISTANCE_HETEROGENEOUS,
        {},
    )
    shorter_radius = {
        name for name, distance in default_distances.items() if distance == _STATION_DISTANCE_HETEROGENEOUS
    }
    assert shorter_radius == {p.name for p in PARAMETER_TABLE if p.interpolation == "heterogeneous"}


def test_parameter_table_zero_inflated_parameters_are_interpolated() -> None:
    """Test that no parameter asks for occurrence thresholding it will never receive.

    `zero_inflated` is only ever read while interpolating, so marking a parameter that is not
    interpolated at all says something about it that nothing acts on -- a declaration that reads as
    intent but has no effect.
    """
    unreachable = sorted(p.name for p in PARAMETER_TABLE if p.zero_inflated and not p.interpolation)
    assert not unreachable, f"zero_inflated but never interpolated: {unreachable}"


def test_parameter_table_names_unique() -> None:
    """Test that no canonical name is declared twice.

    `PARAMETERS` is built by dict comprehension, so a duplicate is silently collapsed and the last
    entry wins -- a conflicting `unit_type` would take effect with no error anywhere. It would also
    emit a duplicate-term warning when the docs glossary is built.
    """
    duplicates = sorted({p.name for p in PARAMETER_TABLE if [q.name for q in PARAMETER_TABLE].count(p.name) > 1})
    assert not duplicates, f"duplicate canonical names: {duplicates}"


def test_parameter_model_rejects_declared_unit_type() -> None:
    """Test that a provider cannot declare a `unit_type` of its own.

    The table owns the unit type, and letting a declaration override it is exactly the drift the
    table exists to prevent -- one name meaning two unit types, and so two output units. Providers
    used to declare it 1575 times; `extra="forbid"` is what stops one creeping back in.
    """
    with pytest.raises(ValidationError):
        ParameterModel(
            name="temperature_air_mean_2m",
            name_original="tt_10",
            unit="degree_celsius",
            unit_type="temperature",
        )


def test_parameter_model_unit_type_unknown_name() -> None:
    """Test that an uncanonical name fails when its unit type is read, naming the parameter.

    The lookup is deliberately not done at import: a name that is not in the table is a
    contributor error, caught by `test_metadata_parameter_table`, and validating 1692 declarations
    on every interpreter start would make every user pay for it.
    """
    parameter = ParameterModel(name="not_a_real_parameter", name_original="x", unit="meter")
    with pytest.raises(KeyError, match="not_a_real_parameter"):
        _ = parameter.unit_type


def _minimal_metadata() -> dict:
    """Build the smallest metadata declaration that validates, for the model tests below."""
    return {
        "name_short": "Example",
        "name_english": "Example Weather Service",
        "name_local": "Beispiel",
        "country": "Germany",
        "copyright": "© Example",
        "url": "https://example.com",
        "kind": "observation",
        "timezone": "Europe/Berlin",
        "resolutions": [
            {
                "name": "daily",
                "name_original": "daily",
                "periods": ["historical"],
                "date_required": False,
                "datasets": [
                    {
                        "name": "data",
                        "name_original": "data",
                        "grouped": True,
                        "parameters": [
                            {
                                "name": "temperature_air_mean_2m",
                                "name_original": "tt",
                                "unit": "degree_celsius",
                            },
                        ],
                    },
                ],
            },
        ],
    }


@pytest.mark.parametrize(
    ("level", "key"),
    [
        ("metadata", "kindd"),
        ("resolution", "date_requiered"),
        ("dataset", "grupped"),
    ],
)
def test_metadata_model_rejects_unknown_keys(level: str, key: str) -> None:
    """Test that a misspelled key is rejected rather than dropped, at every level of the model.

    Only `ParameterModel` used to forbid extra keys. Everywhere else a typo was silently ignored
    and the declaration then fell back to a default -- a `date_requiered` dataset quietly inherits
    the resolution's `date_required`, which is the sort of drift no test would catch.
    """
    metadata = _minimal_metadata()
    resolution = metadata["resolutions"][0]
    target = {"metadata": metadata, "resolution": resolution, "dataset": resolution["datasets"][0]}[level]
    target[key] = True
    with pytest.raises(ValidationError, match=key):
        build_metadata_model(metadata, "ExampleMetadata")


def test_metadata_model_reports_the_invalid_period() -> None:
    """Test that an unknown period is reported as such, rather than as a missing field.

    `validate_datasets` cascades the resolution's `periods` down to its datasets. Reading that
    field by index used to turn any error in it into `KeyError('periods')`, because pydantic drops
    a field that failed validation from the data the next validator sees.

    The datasets that would have inherited it are left out of the report rather than each adding a
    `Field required` of its own, which for a resolution the size of `DwdPhenologyMetadata`'s would
    bury the real error under 110 misleading ones.
    """
    metadata = _minimal_metadata()
    resolution = metadata["resolutions"][0]
    resolution["periods"] = ["histerical"]
    resolution["datasets"].append({**resolution["datasets"][0], "name": "other", "name_original": "other"})
    with pytest.raises(ValidationError, match="histerical") as excinfo:
        build_metadata_model(metadata, "ExampleMetadata")

    assert excinfo.value.error_count() == 1


def test_metadata_model_rejects_a_declared_name() -> None:
    """Test that a declaration cannot set the name the model is built with.

    `build_metadata_model` injects it, so a declaration setting it would have it silently
    overwritten -- the one top-level key `extra="forbid"` cannot catch, and a plausible one to
    write next to `name_short`, `name_english` and `name_local`.
    """
    metadata = _minimal_metadata()
    metadata["name"] = "example"
    with pytest.raises(ValueError, match="cannot be declared"):
        build_metadata_model(metadata, "ExampleMetadata")


def test_metadata_model_name() -> None:
    """Test that the name a metadata model is built with is readable and stays out of the dump.

    It names the provider in messages about parameters that could not be resolved against it. It
    is the name of the declaration rather than one of the provider's own names, so it is excluded
    from the serialized metadata.
    """
    metadata = build_metadata_model(_minimal_metadata(), "ExampleMetadata")
    assert metadata.name == "ExampleMetadata"
    assert "name" not in metadata.model_dump()


@pytest.mark.parametrize(
    "metadata",
    ALL_METADATA,
)
def test_metadata_parameter_table(unit_converter_unit_type_units: dict, metadata: dict) -> None:
    """Test provider parameter declarations against the canonical parameter table.

    Providers no longer declare a `unit_type` -- `ParameterModel.unit_type` reads it from the table
    -- so there is no longer a disagreement to detect. What is left to check is that the name is a
    key of the table at all, since an unknown name only raises once something reads `unit_type`,
    and that the source's unit really is a unit of the quantity that name denotes.
    """
    for resolution in metadata:
        for dataset in resolution:
            # iterate dataset.parameters rather than dataset, to cover quality parameters too
            for parameter in dataset.parameters:
                site = f"{metadata.name} {resolution.name}/{dataset.name}/{parameter.name}"
                canonical = PARAMETERS.get(parameter.name)
                assert canonical, f"{site}: not a canonical parameter name"
                # the source's unit must be a unit of the quantity this parameter measures
                assert parameter.unit in unit_converter_unit_type_units[canonical.unit_type], (
                    f"{site}: unit {parameter.unit!r} is not a unit of unit_type {canonical.unit_type!r}"
                )


def test_api_dwd_observation(default_settings: Settings) -> None:
    """Test dwd observation API."""
    request = DwdObservationRequest(parameters=[("daily", "kl")], periods="recent", settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df)
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_dwd_observation_hourly_weather_phenomena(default_settings: Settings) -> None:
    """Test dwd observation API for hourly weather phenomena.

    The data contains invalid utf8 sequence which would cause an error if not transformed from latin1 to utf8.
    """
    request = DwdObservationRequest(
        parameters=[("hourly", "weather_phenomena")], settings=default_settings
    ).filter_by_station_id("00003")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df)
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_dwd_mosmix(default_settings: Settings) -> None:
    """Test dwd mosmix API."""
    request = DwdMosmixRequest(parameters=[("hourly", "large")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_dwd_dmo_icon_single_stations(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(
        parameters=[("hourly", "icon")], station_group="single_stations", settings=default_settings
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_dwd_dmo_icon_all_stations(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(
        parameters=[("hourly", "icon")], station_group="all_stations", settings=default_settings
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_dwd_dmo_icon_eu_single_stations(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(
        parameters=[("hourly", "icon_eu")], station_group="single_stations", settings=default_settings
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_dwd_dmo_icon_eu_all_stations(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(
        parameters=[("hourly", "icon_eu")], station_group="all_stations", settings=default_settings
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.skipif(IS_CI and IS_WINDOWS, reason="permission with storage in CI on Windows")
@pytest.mark.skipif(not ensure_eccodes(), reason="eccodes not installed")
@pytest.mark.skipif(not ensure_eccodes() and not ensure_pdbufr(), reason="pdbufr not installed")
def test_api_dwd_road(default_settings: Settings) -> None:
    """Test dwd road API."""
    request = DwdRoadRequest(
        parameters=[("15_minutes", "data", "temperature_air_mean_2m")],
        settings=default_settings,
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(
        request.df,
        exclude_columns={
            "start_date",
            "end_date",
        },
    )
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_dmi_observation(default_settings: Settings) -> None:
    """Test dmi observation API."""
    request = DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date=datetime(2023, 6, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        end_date=datetime(2023, 6, 5, tzinfo=zoneinfo.ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(["06180"])
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_date", "height"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_rmi_observation(default_settings: Settings) -> None:
    """Test rmi observation API."""
    request = RmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date=datetime(2023, 6, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        end_date=datetime(2023, 6, 5, tzinfo=zoneinfo.ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(["6447"])
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # RMI stations carry no region/state, and Uccle is still active (null end_date).
    assert _is_complete_stations_df(request.df, exclude_columns={"end_date", "state"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail(raises=FSTimeoutError, strict=False, reason="ECCC server regularly times out")
@pytest.mark.remote
def test_api_eccc_observation(default_settings: Settings) -> None:
    """Test eccc observation API."""
    request = EcccObservationRequest(parameters=[("daily", "data")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "height"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail
@pytest.mark.remote
def test_api_imgw_hydrology(default_settings: Settings) -> None:
    """Test imgw hydrology API."""
    request = ImgwHydrologyRequest(parameters=[("daily", "hydrology")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df)
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail
@pytest.mark.remote
def test_api_imgw_meteorology(default_settings: Settings) -> None:
    """Test imgw meteorology API."""
    request = ImgwMeteorologyRequest(parameters=[("daily", "climate")], settings=default_settings).filter_by_station_id(
        "249200180",
    )
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df)
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_noaa_ghcn_hourly(default_settings: Settings) -> None:
    """Test noaa ghcn hourly API."""
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data", "precipitation_height")],
        settings=default_settings,
    ).filter_by_station_id("AQC00914594")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_noaa_ghcn_daily(default_settings: Settings) -> None:
    """Test noaa ghcn daily API."""
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "precipitation_height")],
        settings=default_settings,
    ).filter_by_station_id("AQC00914594")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df)
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_wsv_pegel(default_settings: Settings) -> None:
    """Test wsv pegel API."""
    # stage at the 15-minute gauges, which is two thirds of the network
    request = WsvPegelRequest(parameters=[("15_minutes", "data", "stage")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(
        request.df,
        exclude_columns={"start_date", "end_date", "latitude", "longitude", "height", "state"},
    )
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_ea_hydrology(default_settings: Settings) -> None:
    """Test ea hydrology API."""
    request = EAHydrologyRequest(parameters=[("daily", "data", "discharge_max")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state", "height"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_nws_observation(default_settings: Settings) -> None:
    """Test nws observation API."""
    request = NwsObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        settings=default_settings,
    ).filter_by_station_id("KBHM")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_eaufrance_hubeau(default_settings: Settings) -> None:
    """Test eaufrance hubeau API."""
    request = HubeauRequest(parameters=[("5_minutes", "data", "discharge")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()
    # humanizing keys on `name_original` as declared, so emitting a lowercased "q" left the values
    # un-humanized and made the skip criteria count the station as having no data
    assert values.get_column("parameter").unique().to_list() == ["discharge"]


@pytest.mark.remote
@pytest.mark.skipif(
    not MetnoFrostRequest.is_configured(),
    reason="MET Norway Frost credentials not set — provide WD_AUTH__METNO_FROST=<client_id>",
)
def test_api_metno_frost(default_settings: Settings) -> None:
    """Test metno frost API."""
    request = MetnoFrostRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start_date="2020-01-01",
        end_date="2020-01-02",
        settings=default_settings,
    ).filter_by_station_id("SN18700")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_date"})
    first_start_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_geosphere_observation(default_settings: Settings) -> None:
    """Test geosphere observation API."""
    request = GeosphereObservationRequest(
        parameters=[("daily", "data", "precipitation_height")],
        settings=default_settings,
    ).filter_by_station_id("5882")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_meteofrance_synop(default_settings: Settings) -> None:
    """Test Météo-France SYNOP API."""
    # bounded to a few days: without a date range, values would default to downloading and
    # parsing every yearly archive since 1996, which is unnecessarily slow for a smoke test
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_mean_2m")],
        start_date=datetime(2024, 1, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        end_date=datetime(2024, 1, 3, tzinfo=zoneinfo.ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id("07005")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_date", "state"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_meteofrance_observation(default_settings: Settings) -> None:
    """Test Météo-France observation API ("Données climatologiques de base")."""
    # bounded to a few months: without a date range, values would download every period-bucket
    # archive for the station's department (up to multi-decade, 100+ MB decompressed each)
    request = MeteoFranceObservationRequest(
        parameters=[("monthly", "data", "precipitation_height")],
        start_date=datetime(2023, 1, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        end_date=datetime(2023, 6, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id("31069001")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # end_date is legitimately null here: station "31069001" (Toulouse-Blagnac) is still open, and
    # the canonical Météo-France station registry (unlike the per-department archive scan this
    # used to derive dates from) reports null end_date for still-open stations
    assert _is_complete_stations_df(request.df, exclude_columns={"state", "end_date"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_meteoswiss_observation(default_settings: Settings) -> None:
    """Test MeteoSwiss observation API."""
    request = MeteoswissObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        settings=default_settings,
    ).filter_by_station_id("ABO")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_date"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail(strict=False, reason="AEMET server intermittently unavailable")
@pytest.mark.remote
@pytest.mark.skipif(
    not AemetObservationRequest.is_configured(),
    reason="AEMET credentials not set — provide WD_AUTH__AEMET=<api_key>",
)
def test_api_aemet_observation(default_settings: Settings) -> None:
    """Test AEMET observation API."""
    request = AemetObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date="2020-01-01",
        end_date="2020-01-02",
        settings=default_settings,
    ).filter_by_station_id("3195")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # AEMET's station inventory doesn't provide start_date/end_date at all.
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail(strict=False, reason="CHMI server intermittently unavailable")
@pytest.mark.remote
def test_api_chmi_observation(default_settings: Settings) -> None:
    """Test CHMI observation API."""
    request = ChmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date="2020-01-01",
        end_date="2020-01-02",
        settings=default_settings,
    ).filter_by_station_id("0-20000-0-11406")  # Cheb
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # CHMI's station catalogue provides no state/region and no end_date for active stations.
    assert _is_complete_stations_df(request.df, exclude_columns={"state", "end_date"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail(strict=False, reason="SMHI server intermittently unavailable")
@pytest.mark.remote
def test_api_smhi_observation(default_settings: Settings) -> None:
    """Test SMHI observation API."""
    request = SmhiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date="2020-01-01",
        end_date="2020-01-02",
        settings=default_settings,
    ).filter_by_station_id("188790")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_date", "state"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail(strict=False, reason="FMI server intermittently unavailable")
@pytest.mark.remote
def test_api_fmi_observation(default_settings: Settings) -> None:
    """Test FMI observation API."""
    request = FmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date="2024-01-01",
        end_date="2024-01-02",
        settings=default_settings,
    ).filter_by_station_id("100971")  # Helsinki Kaisaniemi
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # FMI's station catalogue exposes neither elevation nor an end_date for active stations.
    assert _is_complete_stations_df(request.df, exclude_columns={"end_date", "height"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail(strict=False, reason="KNMI server intermittently unavailable")
@pytest.mark.remote
@pytest.mark.skipif(
    not KnmiObservationRequest.is_configured(),
    reason="KNMI credentials not set — provide WD_AUTH__KNMI=<api_key>",
)
def test_api_knmi_observation(default_settings: Settings) -> None:
    """Test KNMI observation API."""
    request = KnmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date="2020-01-01",
        end_date="2020-01-01",
        settings=default_settings,
    ).filter_by_station_id("06260")  # De Bilt (WMO station number, from WSI 0-20000-0-06260)
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # KNMI's station inventory provides neither start_date/end_date nor a state.
    assert _is_complete_stations_df(request.df, exclude_columns={"start_date", "end_date", "state"})
    first_date = request.df.get_column("start_date").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_source_descriptions_reach_the_metadata() -> None:
    """Test that the per-provider field descriptions reach the metadata and discover output.

    Distinct from the canonical descriptions in the parameter table: those say what a quantity is,
    provider-independent, while these describe one source's own field. `description` was a declared
    but entirely unused slot on every metadata model before this.
    """
    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.metadata.source_descriptions import SOURCE_DESCRIPTIONS  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    assert SOURCE_DESCRIPTIONS

    # every key must still name a real declaration, or a description has been orphaned by a rename
    unknown = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            try:
                api = Wetterdienst(provider, network)
            except Exception:  # noqa: BLE001, S112
                continue
            metadata = getattr(api, "metadata", None)
            if metadata is None:
                continue
            declared = {
                (resolution.name, dataset.name, parameter.name_original)
                for resolution in metadata
                for dataset in resolution
                for parameter in dataset.parameters
            }
            unknown.extend(sorted(set(SOURCE_DESCRIPTIONS.get(metadata.name, {})) - declared))
    assert not unknown, f"descriptions for parameters that no longer exist: {unknown[:5]}"

    parameter = DwdObservationRequest.metadata["10_minutes"]["solar"]["radiation_global"]
    assert parameter.description == "Sum of global radiation during the previous 10 minutes."
    # a provider without a machine-readable sheet still gets the curated text
    assert DwdObservationRequest.metadata["daily"]["climate_summary"]["snow_depth"].description

    discovered = DwdObservationRequest.discover(resolutions="10_minutes", datasets="solar")
    solar = discovered["10_minutes"]["datasets"]["solar"]
    entry = next(p for p in solar["parameters"] if p["name"] == "radiation_global")
    assert entry["description"] == parameter.description
    # the dataset's own description is reachable now too, which is why the shape has this level
    assert solar["description"]


def test_source_descriptions_reach_the_parameter_they_name() -> None:
    """Test that each description lands on the parameter it is keyed to, and only that one.

    Checking that a key names a declared parameter is not enough. Providers commonly build one
    resolution's parameter list from another's by comprehension, which reuses the very same dicts,
    so writing a description into one used to attach it to every resolution sharing it: AEMET's
    annual parameters are its monthly ones minus humidity, and annual read "Monthly mean
    temperature" while its own seven entries went nowhere.
    """
    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.metadata.source_descriptions import (  # noqa: PLC0415
        DERIVED_DESCRIPTIONS,
        SOURCE_DESCRIPTIONS,
    )

    wrong = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            try:
                api = Wetterdienst(provider, network)
            except Exception:  # noqa: BLE001, S112
                continue
            metadata = getattr(api, "metadata", None)
            if metadata is None:
                continue
            # a derived description only fills a gap, never displaces one the source wrote
            expected = {
                **DERIVED_DESCRIPTIONS.get(metadata.name, {}),
                **SOURCE_DESCRIPTIONS.get(metadata.name, {}),
            }
            for resolution in metadata:
                for dataset in resolution:
                    for parameter in dataset.parameters:
                        key = (resolution.name, dataset.name, parameter.name_original)
                        if key in expected and parameter.description != expected[key]:
                            wrong.append(
                                f"{metadata.name} {'/'.join(key)}: "
                                f"got {parameter.description!r}, expected {expected[key]!r}",
                            )
    assert not wrong, "\n".join(wrong[:10])
