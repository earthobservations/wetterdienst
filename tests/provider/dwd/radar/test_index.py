# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from pathlib import PurePath

import pytest

from wetterdienst import Period, Resolution
from wetterdienst.provider.dwd.radar.index import create_fileindex_radar, create_fileindex_radolan_cdc
from wetterdienst.provider.dwd.radar.metadata import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarParameter,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


@pytest.mark.remote
def test_radar_fileindex_composite_pg_reflectivity_bin(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PG_REFLECTIVITY,
        fmt=DwdRadarDataFormat.BINARY,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match("*/weather/radar/composite/pg/*---bin") for url in urls)


@pytest.mark.remote
def test_radar_fileindex_composite_pg_reflectivity_bufr(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PG_REFLECTIVITY,
        fmt=DwdRadarDataFormat.BUFR,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match("*/weather/radar/composite/pg/*---bufr") for url in urls)


@pytest.mark.remote
def test_radar_fileindex_composite_rv_reflectivity_bin(default_settings):
    file_index = create_fileindex_radar(parameter=DwdRadarParameter.RV_REFLECTIVITY, settings=default_settings)
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match("*/weather/radar/composite/rv/*.tar.bz2") for url in urls)


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [
        DwdRadarParameter.RW_REFLECTIVITY,
        DwdRadarParameter.RY_REFLECTIVITY,
        DwdRadarParameter.SF_REFLECTIVITY,
    ],
)
def test_radar_fileindex_radolan_reflectivity_bin(parameter, default_settings):
    file_index = create_fileindex_radar(parameter=parameter, settings=default_settings)
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(
        PurePath(url).match(f"*/weather/radar/radolan/{parameter.value}/*---bin")
        for url in urls
        if not url.endswith(".bz2")
    )


@pytest.mark.remote
def test_radar_fileindex_sites_px_reflectivity_bin(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PX_REFLECTIVITY,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BINARY,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match("*/weather/radar/sites/px/boo/*---bin") for url in urls)


@pytest.mark.remote
def test_radar_fileindex_sites_px_reflectivity_bufr(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PX_REFLECTIVITY,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BUFR,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match("*/weather/radar/sites/px/boo/*---buf") for url in urls)


@pytest.mark.remote
def test_radar_fileindex_sites_px250_reflectivity_bufr(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PX250_REFLECTIVITY,
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all("/weather/radar/sites/px250/boo" in url for url in urls)


@pytest.mark.remote
def test_radar_fileindex_sites_sweep_vol_v_hdf5_simple(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all("/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_simple" in url for url in urls)


@pytest.mark.remote
def test_radar_fileindex_sites_sweep_vol_v_hdf5_polarimetric(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.POLARIMETRIC,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all("/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_polarimetric" in url for url in urls)


@pytest.mark.remote
def test_radar_fileindex_radolan_cdc_daily_recent(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.DAILY,
        period=Period.RECENT,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(
        PurePath(url).match("*/climate_environment/CDC/grids_germany/daily/radolan/recent/bin/*---bin.gz")
        for url in urls
        if not url.endswith(".pdf")
    )


@pytest.mark.remote
def test_radar_fileindex_radolan_cdc_daily_historical(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(
        PurePath(url).match("*/climate_environment/CDC/grids_germany/daily/radolan/historical/bin/*/SF*.tar.gz")
        for url in urls
        if not url.endswith(".pdf")
    )


@pytest.mark.remote
def test_radar_fileindex_radolan_cdc_hourly_recent(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.HOURLY,
        period=Period.RECENT,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(
        PurePath(url).match("*/climate_environment/CDC/grids_germany/hourly/radolan/recent/bin/*---bin.gz")
        for url in urls
        if not url.endswith(".pdf")
    )


@pytest.mark.remote
def test_radar_fileindex_radolan_cdc_hourly_historical(default_settings):
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.HOURLY,
        period=Period.HISTORICAL,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(
        PurePath(url).match("*/climate_environment/CDC/grids_germany/hourly/radolan/historical/bin/*/RW*.tar.gz")
        for url in urls
        if not url.endswith(".pdf")
    )


@pytest.mark.remote
def test_radar_fileindex_radolan_cdc_5minutes(default_settings):
    file_index = create_fileindex_radolan_cdc(
        resolution=Resolution.MINUTE_5,
        period=Period.HISTORICAL,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/5_minutes/radolan/reproc/2017_002/bin/*/YW2017*.tar",
        )
        for url in urls
        if not url.endswith(".tar.gz")
    )
