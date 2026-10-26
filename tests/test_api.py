# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the API."""

import ast
import collections
import contextlib
import importlib
import logging
import os
import re
import zoneinfo
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

import polars as pl
import pytest
from pydantic import BaseModel, ValidationError

from tests.conftest import BUFR_AVAILABLE, FROST_RESOLVER_ON_MACOS
from wetterdienst import Settings
from wetterdienst.api import Wetterdienst
from wetterdienst.exceptions import ApiNotFoundError, MissingDependencyError
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.metadata.unit_type import UnitType
from wetterdienst.model.metadata import (
    NetworkKind,
    ParameterModel,
    TimeseriesKind,
    build_metadata_model,
    parse_parameters,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.unit import UnitConverter
from wetterdienst.provider.aemet.observation import AemetObservationMetadata, AemetObservationRequest
from wetterdienst.provider.chmi.observation import ChmiObservationMetadata, ChmiObservationRequest
from wetterdienst.provider.dmi.observation import DmiObservationMetadata, DmiObservationRequest
from wetterdienst.provider.dwd.derived import DwdDerivedMetadata
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
from wetterdienst.settings import Auth
from wetterdienst.ui.core import resolve_network

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
    "start_timestamp",
    "end_timestamp",
    "latitude",
    "longitude",
    "elevation",
    "name",
    "region",
}
DF_VALUES_MINIMUM_COLUMNS = {"resolution", "dataset", "station_id", "parameter", "timestamp", "value", "quality_flags"}


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
    columns = DF_VALUES_MINIMUM_COLUMNS - {"value", "quality_flags"}
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
    request = resolve_network(provider, network)
    assert request


@pytest.mark.parametrize("network", ["radar", "alerts"])
def test_resolve_refuses_a_standalone_network_and_names_the_entry_point(network: str) -> None:
    """`resolve` is for timeseries networks: dwd/radar and dwd/alerts are refused, naming the entry point (GH-3045)."""
    with pytest.raises(ApiNotFoundError, match=rf"resolve_standalone\('dwd', '{network}'\)"):
        Wetterdienst.resolve("dwd", network)


@pytest.mark.parametrize(
    ("provider", "network", "expected"),
    [
        ("dwd", "radar", "DwdRadarValues"),
        (" DWD ", "Alerts", "DwdWeatherAlertRequest"),
    ],
)
def test_resolve_standalone_returns_the_request_class_of_the_network(
    provider: str, network: str, expected: str
) -> None:
    """`resolve_standalone` gives the class of dwd/radar and dwd/alerts, reading names as `resolve` does (GH-3045)."""
    api = Wetterdienst.resolve_standalone(provider, network)
    assert api.__name__ == expected
    assert not issubclass(api, TimeseriesRequest)


def test_resolve_standalone_refuses_a_timeseries_network_and_names_the_entry_point() -> None:
    """A timeseries network is told to be resolved by `resolve`, not answered with a class (GH-3045)."""
    with pytest.raises(ApiNotFoundError, match=r"resolve it with Wetterdienst\.resolve\('dwd', 'observation'\)"):
        Wetterdienst.resolve_standalone("dwd", "observation")


def test_resolve_standalone_refuses_a_network_that_does_not_exist() -> None:
    """An unknown provider and network is the error `resolve` raises for it (GH-3045)."""
    with pytest.raises(ApiNotFoundError, match=r"No API available for provider foo and network bar\."):
        Wetterdienst.resolve_standalone("foo", "bar")


def test_the_standalone_networks_are_exactly_the_ones_that_are_no_timeseries_request() -> None:
    """`Wetterdienst.standalone` lists the networks of the registry that are no `TimeseriesRequest` (GH-3045)."""
    standalone = set()
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if not issubclass(resolve_network(provider, network), TimeseriesRequest):
                standalone.add((provider, network))
            assert Wetterdienst.is_standalone(provider, network) == ((provider, network) in standalone)
    assert standalone == Wetterdienst.standalone
    kinds = {Wetterdienst.discover()[provider][network]["kind"] for provider, network in standalone}
    assert kinds == {"radar", "alerts"}


@pytest.mark.parametrize(
    "args", [("dwd", "observation"), ("dwd", "radar"), ("dwd", "alerts"), ("foo", "bar"), ("dwd",), ()]
)
def test_the_constructor_form_is_refused_and_names_resolve(args: tuple[str, ...]) -> None:
    """`Wetterdienst(provider, network)` was removed in 0.173.0: it is a `TypeError` naming what to write (GH-3128)."""
    with pytest.raises(TypeError, match=r"Wetterdienst\(provider, network\) was removed") as excinfo:
        Wetterdienst(*args)
    assert "Wetterdienst.resolve(provider, network)" in str(excinfo.value)
    assert "Wetterdienst.resolve_standalone(provider, network)" in str(excinfo.value)


def test_the_constructor_form_is_refused_with_keywords() -> None:
    """The keyword spelling of the removed constructor form is refused the same way (GH-3128)."""
    with pytest.raises(TypeError, match=r"Wetterdienst\(provider, network\) was removed"):
        Wetterdienst(provider="dwd", network="observation")


def test_resolve_names_the_package_a_provider_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider whose dependency is absent says which package that is, and how to install it.

    `importlib` raises ModuleNotFoundError for a missing dependency of a module just as readily as
    for a missing module, and the two want different advice. Reported as "module not found", a
    reader goes looking for a provider that is in fact right there (GH-1929).
    """

    def _raise(_module_path: str) -> None:
        msg = "No module named 'h5py'"
        raise ModuleNotFoundError(msg, name="h5py")

    monkeypatch.setattr(importlib, "import_module", _raise)

    with pytest.raises(ImportError) as excinfo:
        Wetterdienst.resolve("knmi", "observation")

    message = str(excinfo.value)
    assert "requires h5py" in message
    # and which extra brings it, read from the installed metadata rather than from a list in the code
    assert "pip install wetterdienst[knmi]" in message


def test_resolve_still_reports_a_module_that_is_really_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider module that is itself missing is still reported as the missing module it is."""

    def _raise(module_path: str) -> None:
        msg = f"No module named {module_path!r}"
        raise ModuleNotFoundError(msg, name=module_path)

    monkeypatch.setattr(importlib, "import_module", _raise)

    with pytest.raises(ImportError, match=r"Module wetterdienst\.provider\.knmi\.observation not found\."):
        Wetterdienst.resolve("knmi", "observation")


def test_resolve_says_nothing_it_cannot_know_about_an_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dependency that belongs to no extra is named, without an install line invented for it."""

    def _raise(_module_path: str) -> None:
        msg = "No module named 'polars'"
        raise ModuleNotFoundError(msg, name="polars")

    monkeypatch.setattr(importlib, "import_module", _raise)

    with pytest.raises(ImportError) as excinfo:
        Wetterdienst.resolve("knmi", "observation")

    message = str(excinfo.value)
    assert "requires polars" in message
    assert "pip install" not in message


@pytest.mark.parametrize(
    "metadata",
    ALL_METADATA,
    # by name, so a failing case names its provider rather than an index
    ids=lambda metadata: metadata.name,
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


def test_the_smoke_tests_below_request_parameters_their_provider_declares() -> None:
    """Every request of this module's remote tests names parameters of its own provider.

    The remote tests are not in the offline selection, so a rename that left an old name here (`dwd/road`
    `temperature_air_2m`, GH-2614) went unseen until the scheduled run. The request classes this module calls with a
    literal `parameters=` are read from its source and parsed against their own metadata, which needs no network.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf8"))
    checked = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        request_class = globals().get(node.func.id)
        if not (isinstance(request_class, type) and issubclass(request_class, TimeseriesRequest)):
            continue
        for keyword in node.keywords:
            if keyword.arg != "parameters":
                continue
            try:
                literal = ast.literal_eval(keyword.value)
            except ValueError:  # a variable or a call
                continue
            # a list of the tuples (resolution, dataset[, parameter]), or one tuple
            parameters = [literal] if isinstance(literal, tuple) else literal
            if isinstance(parameters, list) and all(isinstance(item, tuple | str) for item in parameters):
                parse_parameters(parameters, request_class.metadata)
                checked += 1
    assert checked > 20


def test_every_resolution_and_period_is_served_by_a_provider() -> None:
    """Test that neither vocabulary carries a member no provider declares.

    Both are closed vocabularies rather than free labels: `Resolution` validates the keys of
    `geo_station_distance_resolution_factors`, is looked up by name in `Frequency`, and is
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
    from wetterdienst.options import (  # noqa: PLC0415
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


def test_every_canonical_name_is_declared_by_a_dataset() -> None:
    """Test that the table holds no name that no provider declares in any dataset.

    A name no dataset declares cannot be requested, yet it was listed by the table, the glossary of the docs and the app
    and accepted as a key of `geo_station_distance`: `groundwater_level_max` after the Environment Agency's river level
    became `stage_max`, `radiation_global_last_3h` after DMO's balances were named for what they are, and quality flags
    of a provider that has long stopped declaring them. When the last dataset to declare a name drops it, the name goes
    from the table with it; a rename of it stays as the hint that says what it is called now (`renamed.py`).
    """
    declared = {
        parameter.name
        for metadata in ALL_METADATA
        for resolution in metadata
        for dataset in resolution
        # the quality flags are no part of iterating a dataset, but are declared by it
        for parameter in dataset.parameters
    }
    # a provider that is registered but missing here would make a name it declares look unused
    registered = set()
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            with contextlib.suppress(ImportError):  # the extra of that network is not installed
                registered.add(Wetterdienst.resolve(provider, network).metadata.name)
    assert sorted(registered - {metadata.name for metadata in ALL_METADATA}) == []

    unused = sorted({p.name for p in PARAMETER_TABLE} - declared)
    assert not unused, f"canonical names that no dataset declares, remove them from the table: {unused}"


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
        "country_code": "DE",
        "copyright": "© Example",
        "license": None,
        "attribution": None,
        "url": "https://example.com",
        "kind": "observation",
        "extent": {"scope": "national", "continents": ["europe"], "countries": ["DE"], "bbox": [5.8, 47.2, 15.1, 55.1]},
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
    # by name, so a failing case names its provider rather than an index
    ids=lambda metadata: metadata.name,
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


@pytest.mark.remote
def test_api_dwd_observation(default_settings: Settings) -> None:
    """Test dwd observation API."""
    request = DwdObservationRequest(parameters=[("daily", "kl")], periods="recent", settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df)
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
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
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_dwd_mosmix(default_settings: Settings) -> None:
    """Test dwd mosmix API."""
    request = DwdMosmixRequest(parameters=[("hourly", "large")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "region"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_dwd_dmo_icon_single_stations(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(
        parameters=[("hourly", "icon")], station_group="single_stations", settings=default_settings
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "region"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_dwd_dmo_icon_all_stations(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(
        parameters=[("hourly", "icon")], station_group="all_stations", settings=default_settings
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "region"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_dwd_dmo_icon_eu_single_stations(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(
        parameters=[("hourly", "icon_eu")], station_group="single_stations", settings=default_settings
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "region"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_dwd_dmo_icon_eu_all_stations(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(
        parameters=[("hourly", "icon_eu")], station_group="all_stations", settings=default_settings
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "region"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
def test_api_dwd_road(default_settings: Settings) -> None:
    """Test dwd road API."""
    request = DwdRoadRequest(
        parameters=[("15_minutes", "data", "temperature_air")],
        settings=default_settings,
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(
        request.df,
        exclude_columns={
            "start_timestamp",
            "end_timestamp",
        },
    )
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_dmi_observation(default_settings: Settings) -> None:
    """Test dmi observation API."""
    request = DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start=datetime(2023, 6, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        end=datetime(2023, 6, 5, tzinfo=zoneinfo.ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(["06180"])
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # DMI gives no sub-national region, the country of a station is in `country` (GH-2019)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_timestamp", "elevation", "region"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_rmi_observation(default_settings: Settings) -> None:
    """Test rmi observation API."""
    request = RmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start=datetime(2023, 6, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        end=datetime(2023, 6, 5, tzinfo=zoneinfo.ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id(["6447"])
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # RMI stations carry no region, and Uccle is still active (null end_timestamp).
    assert _is_complete_stations_df(request.df, exclude_columns={"end_timestamp", "region"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_eccc_observation(default_settings: Settings) -> None:
    """Test eccc observation API."""
    request = EcccObservationRequest(parameters=[("daily", "data")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "elevation"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
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
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
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
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_noaa_ghcn_hourly(default_settings: Settings) -> None:
    """Test noaa ghcn hourly API."""
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data", "precipitation_amount_since_last_routine_report")],
        settings=default_settings,
    ).filter_by_station_id("AQC00914594")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "region"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_noaa_ghcn_daily(default_settings: Settings) -> None:
    """Test noaa ghcn daily API."""
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "precipitation_amount")],
        settings=default_settings,
    ).filter_by_station_id("AQC00914594")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df)
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_wsv_pegel(default_settings: Settings) -> None:
    """Test wsv pegel API."""
    # stage at the 15-minute gauges, which is two thirds of the network
    request = WsvPegelRequest(parameters=[("15_minutes", "data", "stage")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(
        request.df,
        exclude_columns={"start_timestamp", "end_timestamp", "latitude", "longitude", "elevation", "region"},
    )
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_ea_hydrology(default_settings: Settings) -> None:
    """Test ea hydrology API."""
    request = EAHydrologyRequest(parameters=[("daily", "data", "discharge_max")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # the listing gives "Banks Road" no position, the only one of 9537 stations (GH-2933)
    positioned = request.df.filter(pl.col("station_id") != "32f5b1ea-29f7-4d6c-b473-a9e5da0e59d1_U30028")
    assert request.df.height - positioned.height <= 1
    assert _is_complete_stations_df(
        positioned, exclude_columns={"start_timestamp", "end_timestamp", "region", "elevation"}
    )
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_nws_observation(default_settings: Settings) -> None:
    """Test nws observation API."""
    request = NwsObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        settings=default_settings,
    ).filter_by_station_id("KBHM")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "region"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_eaufrance_hubeau(default_settings: Settings) -> None:
    """Test eaufrance hubeau API."""
    request = HubeauRequest(parameters=[("5_minutes", "data", "discharge")], settings=default_settings).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()
    # humanizing keys on `name_original` as declared, so emitting a lowercased "q" left the values
    # un-humanized and made the skip criteria count the station as having no data
    assert values.get_column("parameter").unique().to_list() == ["discharge"]


@pytest.mark.remote
@FROST_RESOLVER_ON_MACOS
@pytest.mark.skipif(
    not MetnoFrostRequest.is_configured(),
    reason="MET Norway Frost credentials not set — provide WD_AUTH__METNO_FROST=<client_id>",
)
def test_api_metno_frost(default_settings: Settings) -> None:
    """Test metno frost API."""
    request = MetnoFrostRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start="2020-01-01",
        end="2020-01-02",
        settings=default_settings,
    ).filter_by_station_id("SN18700")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_timestamp"})
    first_start_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert _is_complete_values_df(values)
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_geosphere_observation(default_settings: Settings) -> None:
    """Test geosphere observation API."""
    request = GeosphereObservationRequest(
        parameters=[("daily", "data", "precipitation_amount")],
        settings=default_settings,
    ).filter_by_station_id("5882")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_meteofrance_synop(default_settings: Settings) -> None:
    """Test Météo-France SYNOP API."""
    # bounded to a few days: without a date range, values would default to downloading and
    # parsing every yearly archive since 1996, which is unnecessarily slow for a smoke test
    request = MeteoFranceSynopRequest(
        parameters=[("subdaily", "data", "temperature_air_2m")],
        start=datetime(2024, 1, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        end=datetime(2024, 1, 3, tzinfo=zoneinfo.ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id("07005")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_timestamp", "region"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_meteofrance_observation(default_settings: Settings) -> None:
    """Test Météo-France observation API ("Données climatologiques de base")."""
    # bounded to a few months: without a date range, values would download every period-bucket
    # archive for the station's department (up to multi-decade, 100+ MB decompressed each)
    request = MeteoFranceObservationRequest(
        parameters=[("monthly", "data", "precipitation_amount")],
        start=datetime(2023, 1, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        end=datetime(2023, 6, 1, tzinfo=zoneinfo.ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id("31069001")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # end_timestamp is legitimately null here: station "31069001" (Toulouse-Blagnac) is still open, and
    # the canonical Météo-France station registry (unlike the per-department archive scan this
    # used to derive dates from) reports null end_timestamp for still-open stations
    assert _is_complete_stations_df(request.df, exclude_columns={"region", "end_timestamp"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_meteoswiss_observation(default_settings: Settings) -> None:
    """Test MeteoSwiss observation API."""
    request = MeteoswissObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        settings=default_settings,
    ).filter_by_station_id("ABO")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_timestamp"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
@pytest.mark.skipif(
    not AemetObservationRequest.is_configured(),
    reason="AEMET credentials not set — provide WD_AUTH__AEMET=<api_key>",
)
def test_api_aemet_observation(default_settings: Settings) -> None:
    """Test AEMET observation API."""
    request = AemetObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start="2020-01-01",
        end="2020-01-02",
        settings=default_settings,
    ).filter_by_station_id("3195")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # AEMET's station inventory doesn't provide start_timestamp/end_timestamp at all.
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_chmi_observation(default_settings: Settings) -> None:
    """Test CHMI observation API."""
    request = ChmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start="2020-01-01",
        end="2020-01-02",
        settings=default_settings,
    ).filter_by_station_id("0-20000-0-11406")  # Cheb
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # CHMI's station catalogue provides no region and no end_timestamp for active stations.
    assert _is_complete_stations_df(request.df, exclude_columns={"region", "end_timestamp"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_smhi_observation(default_settings: Settings) -> None:
    """Test SMHI observation API."""
    request = SmhiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start="2020-01-01",
        end="2020-01-02",
        settings=default_settings,
    ).filter_by_station_id("188790")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    assert _is_complete_stations_df(request.df, exclude_columns={"end_timestamp", "region"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_api_fmi_observation(default_settings: Settings) -> None:
    """Test FMI observation API."""
    request = FmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start="2024-01-01",
        end="2024-01-02",
        settings=default_settings,
    ).filter_by_station_id("100971")  # Helsinki Kaisaniemi
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # FMI's station catalogue exposes neither elevation nor an end_timestamp for active stations.
    assert _is_complete_stations_df(request.df, exclude_columns={"end_timestamp", "elevation"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
@pytest.mark.skipif(
    not KnmiObservationRequest.is_configured(),
    reason="KNMI credentials not set — provide WD_AUTH__KNMI=<api_key>",
)
def test_api_knmi_observation(default_settings: Settings) -> None:
    """Test KNMI observation API."""
    request = KnmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start="2020-01-01",
        end="2020-01-01",
        settings=default_settings,
    ).filter_by_station_id("06260")  # De Bilt (WMO station number, from WSI 0-20000-0-06260)
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    # KNMI's station inventory provides neither start_timestamp/end_timestamp nor a region.
    assert _is_complete_stations_df(request.df, exclude_columns={"start_timestamp", "end_timestamp", "region"})
    first_date = request.df.get_column("start_timestamp").gather(0).to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values().query()).df
    first_date = values.get_column("timestamp").gather(0).to_list()[0]
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
            api = resolve_network(provider, network)
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
            api = resolve_network(provider, network)
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


def test_a_parameter_nothing_describes_reads_the_canonical_description() -> None:
    """Test that `build_metadata_model` falls back to the canonical sentence of the quantity (GH-1979).

    A provider whose field means what the quantity means declares no sentence of its own, so the
    glossary and the provider docs cannot drift apart over it. A sentence it does declare, inline or
    in `SOURCE_DESCRIPTIONS`, still wins.
    """

    def parameter(name: str, **declared: str) -> dict:
        return {"name": name, "name_original": "x", "unit": "degree_celsius", **declared}

    def build(*parameters: dict) -> list:
        dataset = {
            "name": "data",
            "name_original": "data",
            "grouped": False,
            "periods": ["historical"],
            "date_required": False,
            "parameters": list(parameters),
        }
        metadata = {
            "name_short": "T",
            "name_english": "Test",
            "name_local": "Test",
            "country": "Nowhere",
            "country_code": None,
            "copyright": "-",
            "license": None,
            "attribution": None,
            "url": "https://example.org",
            "kind": "observation",
            "extent": {
                "scope": "regional",
                "continents": ["europe"],
                "countries": [],
                "bbox": [0.0, 40.0, 10.0, 50.0],
            },
            "timezone": "UTC",
            "resolutions": [{"name": "daily", "name_original": "daily", "datasets": [dataset]}],
        }
        return build_metadata_model(metadata, "NotAMetadataModel")["daily"]["data"].parameters

    canonical = PARAMETERS["temperature_air_mean_2m"].description
    assert build(parameter("temperature_air_mean_2m"))[0].description == canonical
    assert build(parameter("temperature_air_mean_2m", description="Our own."))[0].description == "Our own."


def test_no_description_repeats_the_canonical_one() -> None:
    """Test that no description table spells out the sentence the model reads without it (GH-1979).

    An entry equal to the canonical sentence of its parameter is a second copy with nothing tying it
    to the first: sharpening one leaves the other behind. A provider that means something else keeps
    its own sentence, which is not equal and is not reported.
    """
    from wetterdienst.metadata.source_descriptions import (  # noqa: PLC0415
        DERIVED_DESCRIPTIONS,
        SOURCE_DESCRIPTIONS,
    )

    repeated = []
    for metadata in ALL_METADATA:
        for table_name, table in (("SOURCE", SOURCE_DESCRIPTIONS), ("DERIVED", DERIVED_DESCRIPTIONS)):
            entries = table.get(metadata.name, {})
            for resolution in metadata:
                for dataset in resolution:
                    for parameter in dataset.parameters:
                        key = (resolution.name, dataset.name, parameter.name_original)
                        if entries.get(key) == PARAMETERS[parameter.name].description:
                            repeated.append(f"{table_name}_DESCRIPTIONS {metadata.name} {'/'.join(key)}")
    assert not repeated, "\n".join(repeated[:10])


def test_metadata_monthly_and_annual_parameters_carry_no_hourly_window() -> None:
    """Test that no monthly or annual parameter is named for a window of hours.

    A `_last_<N>h` or `_<N>h` name says the value covers those hours, and its glossary entry says so
    too. A total over a month or a year declared under such a name reads as the quantity for those hours:
    DWD derived monthly `summe von vpgfao` and `summe von vpgh` came under the daily potential
    evapotranspiration names (GH-2042).
    """
    windowed = [
        f"{metadata.name} {resolution.name}/{dataset.name}/{parameter.name}"
        for metadata in ALL_METADATA
        for resolution in metadata
        if resolution.value in (Resolution.MONTHLY, Resolution.ANNUAL)
        for dataset in resolution
        for parameter in dataset
        # `_last_24h` and a bare `_24h` alike; a gust's `_1min` is how long it is averaged, not a window
        if re.search(r"_\d+h$", parameter.name)
    ]
    assert windowed == []
    soil = DwdDerivedMetadata["monthly"]["soil"]
    assert soil["summe von vpgfao"].name == "evapotranspiration_potential_grass_fao"
    assert soil["summe von vpgh"].name == "evapotranspiration_potential_grass_haude"


@pytest.fixture
def _malformed_ceda_credential(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Set the only invalid `WD_*` variable there is: a CEDA credential that is no `username:password`."""
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WD_AUTH__CEDA", "secret-ish")
    monkeypatch.setattr("wetterdienst.api._REPORTED_SETTINGS_PROBLEMS", set())


def _failing_import(monkeypatch: pytest.MonkeyPatch, *providers: str) -> None:
    """Make every network of the providers fail to import, as a broken install of a package they need does."""
    resolve = Wetterdienst.resolve

    def failing(provider: str, network: str) -> object:
        if provider in providers:
            msg = f"Module wetterdienst.provider.{provider}.{network} failed to import: lxml.etree not found."
            raise ImportError(msg)
        return resolve(provider, network)

    monkeypatch.setattr(Wetterdienst, "resolve", failing)


def test_discover_leaves_out_a_network_that_cannot_be_imported(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A network that fails to import is not listed, and not listed as one that needs no credentials (GH-2801).

    Nothing is known of it, so listing it as `auth` false and `configured` true would be a guess, wrong
    for a network that needs a credential. The reason is logged, and asking for the network itself raises
    it. One of two networks failing leaves the other, and the provider, in the listing.
    """
    resolve = Wetterdienst.resolve

    def failing_dmo(provider: str, network: str) -> object:
        if (provider, network) == ("dwd", "dmo"):
            msg = "Module wetterdienst.provider.dwd.dmo failed to import: lxml.etree not found."
            raise ImportError(msg)
        return resolve(provider, network)

    monkeypatch.setattr(Wetterdienst, "resolve", failing_dmo)
    with caplog.at_level(logging.WARNING, logger="wetterdienst.api"):
        discovered = Wetterdienst.discover()

    assert "dmo" not in discovered["dwd"]
    assert "observation" in discovered["dwd"]
    assert "Left dwd/dmo out of the listing, it cannot be imported: Module wetterdienst.provider.dwd.dmo" in caplog.text
    with pytest.raises(ImportError, match=r"lxml\.etree not found"):
        Wetterdienst.resolve("dwd", "dmo")


def test_discover_leaves_out_a_provider_none_of_whose_networks_can_be_imported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider without a listed network is not listed, rather than as an empty one (GH-2801)."""
    _failing_import(monkeypatch, "metno", "fmi")
    discovered = Wetterdienst.discover()
    assert "metno" not in discovered
    assert "fmi" not in discovered
    assert "dwd" in discovered
    assert all(networks for networks in discovered.values())


def test_a_dotted_module_that_is_not_found_is_a_plain_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A submodule of an installed package (`lxml.etree`) is a broken install, not an uninstalled extra (GH-2800).

    So it is neither a `MissingDependencyError`, which the REST API answers with a 501 and an instruction
    to install, nor an `ApiNotFoundError`, which it answers with a 404 for a network that does not exist.
    """

    def _raise(_module_path: str) -> None:
        msg = "No module named 'lxml.etree'"
        raise ModuleNotFoundError(msg, name="lxml.etree")

    # only the resolver's import, not every lazy import of the process
    monkeypatch.setattr("wetterdienst.api.importlib", SimpleNamespace(import_module=_raise))

    with pytest.raises(ImportError, match=r"failed to import: lxml\.etree not found\.") as excinfo:
        Wetterdienst.resolve("dwd", "dmo")

    assert type(excinfo.value) is ImportError
    assert not isinstance(excinfo.value, (MissingDependencyError, ApiNotFoundError))


@pytest.mark.usefixtures("_malformed_ceda_credential")
def test_discover_marks_providers_unconfigured_for_a_malformed_credential(caplog: pytest.LogCaptureFixture) -> None:
    """A credential that cannot be read leaves the providers that need one unconfigured, not the listing raising.

    `Settings()` raises for any invalid `WD_*` variable, and `is_configured()` builds it, so one
    malformed CEDA credential took the listing of every provider down (GH-2580). The problem is
    logged once however often the listing is asked for, and not with the value.
    """
    with caplog.at_level(logging.WARNING, logger="wetterdienst.api"):
        discovered = Wetterdienst.discover()
        Wetterdienst.discover()
    auth = {
        (provider, network): entry
        for provider, networks in discovered.items()
        for network, entry in networks.items()
        if entry["auth"]
    }
    # the networks the metadata says need a credential, not a list that a new one is to be added to
    assert set(auth) == set(_needing_a_credential())
    assert all(entry["configured"] is False for entry in auth.values())
    assert discovered["dwd"]["observation"]["configured"] is True
    assert [record.getMessage() for record in caplog.records if record.name == "wetterdienst.api"] == [
        (
            "The settings are invalid, so no credential is read: "
            "WD_AUTH__CEDA is invalid: ceda must be given as 'username:password'"
        )
    ]
    assert "secret-ish" not in caplog.text


@pytest.mark.usefixtures("_malformed_ceda_credential")
def test_is_configured_is_false_where_the_settings_cannot_be_built() -> None:
    """The check of a provider's credentials is false rather than raising, for every provider alike (GH-2580)."""
    needing_a_credential = _needing_a_credential()
    assert needing_a_credential
    answers = {key: Wetterdienst.is_configured(api) for key, api in needing_a_credential.items()}
    assert answers == dict.fromkeys(needing_a_credential, False)


class _OtherModel(BaseModel):
    value: int


class _FailsWith:
    """A provider whose credential check raises the error it is given."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def is_configured(self) -> bool:
        raise self.error


@pytest.mark.usefixtures("_malformed_ceda_credential")
def test_is_configured_raises_an_error_of_another_model() -> None:
    """An error of another model is not the settings', so it is not told as a provider unconfigured (GH-2580)."""
    try:
        _OtherModel(value="x")  # ty: ignore[invalid-argument-type]
    except ValidationError as e:
        error = e
    with pytest.raises(ValidationError, match="_OtherModel"):
        Wetterdienst.is_configured(_FailsWith(error))


def test_is_configured_raises_an_error_the_settings_do_not_reproduce(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An error that the settings built from the environment do not reproduce is raised, not hidden (GH-2580)."""
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError, match="ceda must be given"):
        # a credential given as an argument, not in the environment, so `check_settings()` finds none
        Wetterdienst.is_configured(_FailsWith(_settings_error()))


def _settings_error() -> ValidationError:
    try:
        Settings(auth={"ceda": "secret-ish"})
    except ValidationError as e:
        return e
    msg = "the settings were built"
    raise AssertionError(msg)


def test_discover_lists_metoffice_as_needing_a_credential(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The Met Office metadata says it needs a CEDA credential, so the listing follows `WD_AUTH__CEDA` (GH-2594)."""
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    assert Wetterdienst.discover()["metoffice"]["observation"] == {
        "name_short": "MetOffice",
        "country": "United Kingdom",
        "kind": "observation",
        "extent": {"scope": "national", "continents": ["europe"], "countries": ["GB"], "bbox": [-9.0, 49.0, 2.5, 61.0]},
        "url": "https://catalogue.ceda.ac.uk/uuid/dbd451271eb04662beade68da43546e1/",
        "auth": True,
        "configured": False,
        "date_required": False,
    }
    monkeypatch.setenv("WD_AUTH__CEDA", "user:password")
    entry = Wetterdienst.discover()["metoffice"]["observation"]
    assert (entry["auth"], entry["configured"]) == (True, True)


def test_discover_says_what_every_network_is() -> None:
    """Every network is listed with a name, a country, a url and a kind, which says if it is a timeseries (GH-2641).

    A timeseries network has a metadata model, which the four are read from, and a kind of the three in
    `TimeseriesKind`. A standalone one has no metadata model and its request class's `listing`, so that a
    network added to the registry without either fails here rather than in the answer of `/api/coverage`.
    """
    discovered = Wetterdienst.discover()
    timeseries_kinds = set(get_args(TimeseriesKind))
    standalone = set(get_args(NetworkKind)) - timeseries_kinds
    assert standalone == {"radar", "alerts"}

    standalone_networks = set()
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            entry = discovered[provider][network]
            api = resolve_network(provider, network)
            assert set(entry) == {
                "name_short",
                "country",
                "kind",
                "extent",
                "url",
                "auth",
                "configured",
                "date_required",
            }
            assert set(entry["extent"]) == {"scope", "continents", "countries", "bbox"}, f"{provider}/{network}"
            assert entry["name_short"], f"{provider}/{network}"
            assert entry["country"], f"{provider}/{network}"
            assert entry["url"].startswith("https://"), f"{provider}/{network}"
            if hasattr(api, "metadata"):
                assert entry["kind"] in timeseries_kinds, f"{provider}/{network}"
                assert entry["kind"] == api.metadata.kind
            else:
                standalone_networks.add((provider, network))
                assert entry["kind"] in standalone, f"{provider}/{network}"
    # the two networks no timeseries endpoint takes, which the contract names (docs/usage/restapi.md)
    assert standalone_networks == {("dwd", "radar"), ("dwd", "alerts")}
    assert (discovered["dwd"]["radar"]["kind"], discovered["dwd"]["alerts"]["kind"]) == ("radar", "alerts")
    assert discovered["dwd"]["radar"]["url"] == "https://opendata.dwd.de/weather/radar/"
    assert discovered["dwd"]["alerts"]["url"] == "https://opendata.dwd.de/weather/alerts/cap"
    # the name and the country of the standalone ones are the provider's, as the timeseries networks of it give them
    for network in ("radar", "alerts"):
        assert discovered["dwd"][network]["name_short"] == discovered["dwd"]["observation"]["name_short"]
        assert discovered["dwd"][network]["country"] == discovered["dwd"]["observation"]["country"]


def _registered_requests() -> list[tuple[str, str, type]]:
    """Every provider and network of the registry with its request class."""
    return [
        (provider, network, resolve_network(provider, network))
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
    ]


def _needing_a_credential() -> dict[tuple[str, str], type[TimeseriesRequest]]:
    """Return the networks that the metadata says need a credential, by provider and network."""
    return {
        (provider, network): api
        for provider, network, api in _registered_requests()
        if getattr(api, "metadata", None) is not None and api.metadata.auth
    }


# each field of `Settings.auth` as the environment takes it: a key, a `username:password`, a Frost client id and secret
_CREDENTIALS = {
    "aemet": "DUMMY-KEY",
    "knmi": "DUMMY-KEY",
    "metno_frost": '["DUMMY-ID", "DUMMY-SECRET"]',
    "ceda": "DUMMY-USER:DUMMY-SECRET",
}


def _overrides_is_configured(api: type[TimeseriesRequest]) -> bool:
    """Tell whether a request class reads a credential: it replaces the base class's `is_configured()`."""
    # dwd/radar and dwd/alerts are no timeseries requests, and have no check
    is_configured = getattr(api, "is_configured", None)
    return is_configured is not None and is_configured.__func__ is not TimeseriesRequest.is_configured.__func__


def test_request_classes_override_is_configured_exactly_where_the_metadata_says_auth() -> None:
    """A network is listed as needing a credential if and only if its request class checks for one (GH-2604).

    `discover()`, `/api/coverage` and `/api/auth` read `auth` from the metadata, and the check of the
    credential is the request class's `is_configured()`. Nothing else ties the two: the Met Office
    overrode `is_configured()` for a CEDA credential while its metadata lacked `"auth": True`, and
    was listed as needing none (GH-2594); the other way round, `auth` without an override is a
    network listed as needing a credential that is never checked, and so always configured.
    """
    mismatches = []
    for provider, network, api in _registered_requests():
        metadata = getattr(api, "metadata", None)
        auth = bool(metadata.auth) if metadata is not None else False
        overrides = _overrides_is_configured(api)
        if auth != overrides:
            mismatches.append(f"{provider}/{network}: metadata auth={auth}, is_configured overridden={overrides}")
    assert mismatches == []


def test_every_credential_of_the_settings_configures_exactly_one_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each field of `Settings.auth` configures one network, and every network needing one has a field (GH-2604).

    A credential the settings can hold and no network reads, or a network that needs one the
    settings cannot hold, is the same disconnect as an `auth` flag without its check.
    """
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    needing_a_credential = _needing_a_credential()
    assert needing_a_credential
    assert not any(Wetterdienst.is_configured(api) for api in needing_a_credential.values())
    # a credential added to the settings is to be given a value in `_CREDENTIALS`, and so a network
    assert set(_CREDENTIALS) == set(Auth.model_fields)
    configured_by = {}
    for field, credential in _CREDENTIALS.items():
        monkeypatch.setenv(f"WD_AUTH__{field.upper()}", credential)
        configured_by[field] = {key for key, api in needing_a_credential.items() if Wetterdienst.is_configured(api)}
        monkeypatch.delenv(f"WD_AUTH__{field.upper()}")
    assert {field: len(networks) for field, networks in configured_by.items()} == dict.fromkeys(Auth.model_fields, 1)
    assert set().union(*configured_by.values()) == set(needing_a_credential)


class _ProbeRaises:
    """A provider whose credential probe raises instead of answering."""

    @staticmethod
    def is_valid() -> bool:
        msg = "boom"
        raise RuntimeError(msg)


def test_is_valid_is_unknown_where_the_probe_raises(caplog: pytest.LogCaptureFixture) -> None:
    """A probe that raises could not tell, so it is told as unknown (None), not as credentials rejected (GH-2550)."""
    with caplog.at_level(logging.WARNING, logger="wetterdienst.api"):
        assert Wetterdienst.is_valid(_ProbeRaises) is None
    assert [record.getMessage() for record in caplog.records] == ["Could not check the credentials of _ProbeRaises"]


def test_is_valid_passes_on_what_the_probe_tells() -> None:
    """The three answers of a probe reach the caller as they are, and a provider without one is valid."""

    class _Probe:
        def __init__(self, answer: bool | None) -> None:  # noqa: FBT001
            self.answer = answer

        def is_valid(self) -> bool | None:
            return self.answer

    assert [Wetterdienst.is_valid(_Probe(answer)) for answer in (True, False, None)] == [True, False, None]
    assert Wetterdienst.is_valid(object()) is True


def test_discover_downloads_nothing_with_every_credential_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The listing of every provider makes no request, however many credentials are configured (GH-2564).

    It probed each configured provider in turn, inside the request that the app's parameter selection
    waits for: 76 s on a cold cache with AEMET failing. A configured network is listed as configured and
    nothing more, and `Wetterdienst.is_valid` is how it is checked.
    """
    import sys  # noqa: PLC0415

    from wetterdienst.util import network  # noqa: PLC0415

    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    # every provider's module loaded, so that the download each one imports can be found and replaced
    Wetterdienst.discover()
    downloads: list[str] = []

    def refuse(*args: object, **kwargs: object) -> None:
        downloads.append(str(kwargs.get("url") or args))
        msg = "the listing of providers downloaded something"
        raise AssertionError(msg)

    for module in list(sys.modules.values()):
        for name in ("download_file", "download_files"):
            if module is not None and getattr(module, name, None) is getattr(network, name):
                monkeypatch.setattr(module, name, refuse)
    # and a filesystem is what any other way of fetching goes through
    monkeypatch.setattr(network.NetworkFilesystemManager, "get", refuse)
    for field, credential in _CREDENTIALS.items():
        monkeypatch.setenv(f"WD_AUTH__{field.upper()}", credential)

    discovered = Wetterdienst.discover()

    assert downloads == []
    auth = {
        (provider, network_name): entry
        for provider, networks in discovered.items()
        for network_name, entry in networks.items()
        if entry["auth"]
    }
    assert auth
    assert set(auth) == set(_needing_a_credential())
    # the credentials are present, and whether they are accepted is not a thing the listing says (GH-2641)
    assert all(entry["configured"] is True and "valid" not in entry for entry in auth.values())
