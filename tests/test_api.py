# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the API."""

import zoneinfo

import polars as pl
import pytest

from wetterdienst import Parameter, Settings
from wetterdienst.api import Wetterdienst
from wetterdienst.core.timeseries.unit import UnitConverter
from wetterdienst.provider.dwd.dmo import DwdDmoMetadata, DwdDmoRequest
from wetterdienst.provider.dwd.mosmix import DwdMosmixMetadata, DwdMosmixRequest
from wetterdienst.provider.dwd.observation import DwdObservationMetadata, DwdObservationRequest
from wetterdienst.provider.dwd.road import DwdRoadMetadata, DwdRoadRequest
from wetterdienst.provider.ea.hydrology import EAHydrologyMetadata, EAHydrologyRequest
from wetterdienst.provider.eaufrance.hubeau import HubeauMetadata, HubeauRequest
from wetterdienst.provider.eccc.observation import EcccObservationMetadata, EcccObservationRequest
from wetterdienst.provider.geosphere.observation import GeosphereObservationMetadata, GeosphereObservationRequest
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyMetadata, ImgwHydrologyRequest
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyMetadata, ImgwMeteorologyRequest
from wetterdienst.provider.noaa.ghcn import NoaaGhcnMetadata, NoaaGhcnRequest
from wetterdienst.provider.nws.observation import NwsObservationMetadata, NwsObservationRequest
from wetterdienst.provider.wsv.pegel import WsvPegelMetadata, WsvPegelRequest
from wetterdienst.util.eccodes import ensure_eccodes

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
def parameter_names() -> set[str]:
    """Provide parameter names."""
    return {parameter.name.lower() for parameter in Parameter}


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
    [
        DwdDmoMetadata,
        DwdMosmixMetadata,
        DwdObservationMetadata,
        DwdRoadMetadata,
        EAHydrologyMetadata,
        EcccObservationMetadata,
        GeosphereObservationMetadata,
        HubeauMetadata,
        ImgwHydrologyMetadata,
        ImgwMeteorologyMetadata,
        NoaaGhcnMetadata,
        NwsObservationMetadata,
        WsvPegelMetadata,
    ],
)
def test_metadata_parameter_names(parameter_names: list[str], metadata: dict) -> None:
    """Test metadata parameter names."""
    for resolution in metadata:
        for dataset in resolution:
            for parameter in dataset:
                assert parameter.name in parameter_names


@pytest.mark.parametrize(
    "metadata",
    [
        DwdDmoMetadata,
        DwdMosmixMetadata,
        DwdObservationMetadata,
        DwdRoadMetadata,
        EAHydrologyMetadata,
        EcccObservationMetadata,
        GeosphereObservationMetadata,
        HubeauMetadata,
        ImgwHydrologyMetadata,
        ImgwMeteorologyMetadata,
        NoaaGhcnMetadata,
        NwsObservationMetadata,
        WsvPegelMetadata,
    ],
)
def test_metadata_units(unit_converter: UnitConverter, unit_converter_unit_type_units: dict, metadata: dict) -> None:
    """Test metadata units."""
    for resolution in metadata:
        for dataset in resolution:
            for parameter in dataset:
                assert parameter.unit_type in unit_converter.targets
                assert parameter.unit in unit_converter_unit_type_units[parameter.unit_type]


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


def test_api_dwd_dmo(default_settings: Settings) -> None:
    """Test dwd dmo API."""
    request = DwdDmoRequest(parameters=[("hourly", "icon")], settings=default_settings).all()
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


@pytest.mark.skipif(not ensure_eccodes(), reason="eccodes not installed")
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
    request = WsvPegelRequest(parameters=[("dynamic", "data", "stage")], settings=default_settings).all()
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
    request = HubeauRequest(parameters=[("dynamic", "data", "discharge")], settings=default_settings).all()
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
