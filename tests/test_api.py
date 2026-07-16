# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the API."""

import zoneinfo
from datetime import datetime

import polars as pl
import pytest
from fsspec.exceptions import FSTimeoutError

from tests.conftest import IS_CI, IS_WINDOWS
from wetterdienst import Parameter, Settings
from wetterdienst.api import Wetterdienst
from wetterdienst.model.unit import UnitConverter
from wetterdienst.provider.aemet.observation import AemetObservationMetadata, AemetObservationRequest
from wetterdienst.provider.dmi.observation import DmiObservationMetadata, DmiObservationRequest
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
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationMetadata, MeteoFranceObservationRequest
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopMetadata, MeteoFranceSynopRequest
from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationMetadata, MeteoswissObservationRequest
from wetterdienst.provider.metno.frost.api import MetnoFrostMetadata, MetnoFrostRequest
from wetterdienst.provider.noaa.ghcn import NoaaGhcnMetadata, NoaaGhcnRequest
from wetterdienst.provider.nws.observation import NwsObservationMetadata, NwsObservationRequest
from wetterdienst.provider.smhi.observation import SmhiObservationMetadata, SmhiObservationRequest
from wetterdienst.provider.wsv.pegel import WsvPegelMetadata, WsvPegelRequest
from wetterdienst.util.eccodes import ensure_eccodes, ensure_pdbufr

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
        AemetObservationMetadata,
        DmiObservationMetadata,
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
        MeteoFranceObservationMetadata,
        MeteoFranceSynopMetadata,
        MeteoswissObservationMetadata,
        MetnoFrostMetadata,
        NoaaGhcnMetadata,
        NwsObservationMetadata,
        SmhiObservationMetadata,
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
        AemetObservationMetadata,
        DmiObservationMetadata,
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
        MeteoFranceObservationMetadata,
        MeteoFranceSynopMetadata,
        MeteoswissObservationMetadata,
        MetnoFrostMetadata,
        NoaaGhcnMetadata,
        NwsObservationMetadata,
        SmhiObservationMetadata,
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
