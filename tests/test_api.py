# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import zoneinfo

import pytest

from wetterdienst import Parameter
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
    "station_id",
    "start_date",
    "end_date",
    "latitude",
    "longitude",
    "height",
    "name",
    "state",
}
DF_VALUES_MINIMUM_COLUMNS = {"station_id", "parameter", "date", "value", "quality"}


@pytest.fixture
def parameter_names():
    return {parameter.name.lower() for parameter in Parameter}


@pytest.fixture
def unit_converter():
    return UnitConverter()


@pytest.fixture
def unit_converter_unit_type_units(unit_converter):
    return {unit_type: [unit.name for unit in units] for unit_type, units in unit_converter.units.items()}


@pytest.mark.parametrize(
    "provider, network",
    [(provider, network) for provider in Wetterdienst.registry for network in Wetterdienst.registry[provider]],
)
def test_wetterdienst_api(provider, network):
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
def test_metadata_parameter_names(parameter_names, metadata):
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
def test_metadata_units(unit_converter, unit_converter_unit_type_units, metadata):
    for resolution in metadata:
        for dataset in resolution:
            for parameter in dataset:
                assert parameter.unit_type in unit_converter.targets
                assert parameter.unit in unit_converter_unit_type_units[parameter.unit_type]


def test_api_dwd_observation(settings_si_true):
    request = DwdObservationRequest(parameters=[("daily", "kl")], periods="recent", settings=settings_si_true).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_dwd_mosmix(settings_si_true):
    request = DwdMosmixRequest(parameters=[("hourly", "large")], settings=settings_si_true).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_dwd_dmo(settings_si_true):
    request = DwdDmoRequest(parameters=[("hourly", "icon")], settings=settings_si_true).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.skipif(not ensure_eccodes(), reason="eccodes not installed")
def test_api_dwd_road(settings_si_true):
    request = DwdRoadRequest(
        parameters=[("15_minutes", "data", "temperature_air_mean_2m")], settings=settings_si_true
    ).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail
def test_api_eccc_observation(settings_si_true):
    request = EcccObservationRequest(parameters=[("daily", "data")], settings=settings_si_true).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail
@pytest.mark.remote
def test_api_imgw_hydrology(settings_si_true):
    request = ImgwHydrologyRequest(parameters=[("daily", "hydrology")], settings=settings_si_true).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail
@pytest.mark.remote
def test_api_imgw_meteorology(settings_si_true):
    request = ImgwMeteorologyRequest(parameters=[("daily", "climate")], settings=settings_si_true).filter_by_station_id(
        "249200180"
    )
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_noaa_ghcn_hourly(settings_si_true):
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data", "precipitation_height")], settings=settings_si_true
    ).filter_by_station_id("AQC00914594")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_noaa_ghcn_daily(settings_si_true):
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "precipitation_height")], settings=settings_si_true
    ).filter_by_station_id("AQC00914594")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_start_date = request.df.get_column("start_date").to_list()[0]
    if first_start_date:
        assert first_start_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.xfail
def test_api_wsv_pegel(settings_si_true):
    request = WsvPegelRequest(parameters=[("dynamic", "data", "stage")], settings=settings_si_true).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_date").to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_ea_hydrology(settings_si_true):
    request = EAHydrologyRequest(parameters=[("daily", "data", "discharge")], settings=settings_si_true).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_date").to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_nws_observation(settings_si_true):
    request = NwsObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")], settings=settings_si_true
    ).filter_by_station_id("KBHM")
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_date").to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_eaufrance_hubeau(settings_si_true):
    request = HubeauRequest(parameters=[("dynamic", "data", "discharge")], settings=settings_si_true).all()
    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_date").to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()


def test_api_geosphere_observation(settings_si_true):
    request = GeosphereObservationRequest(
        parameters=[("daily", "data", "precipitation_height")], settings=settings_si_true
    ).filter_by_station_id("5882")

    assert not request.df.is_empty()
    assert set(request.df.columns).issuperset(DF_STATIONS_MINIMUM_COLUMNS)
    first_date = request.df.get_column("start_date").to_list()[0]
    if first_date:
        assert first_date.tzinfo == zoneinfo.ZoneInfo(key="UTC")
    values = next(request.values.query()).df
    first_date = values.get_column("date").to_list()[0]
    assert first_date.tzinfo
    assert set(values.columns).issuperset(DF_VALUES_MINIMUM_COLUMNS)
    assert not values.drop_nulls(subset="value").is_empty()
