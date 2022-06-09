# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from pathlib import PurePath

import pytest

from wetterdienst import Period, Resolution
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.radar.index import create_fileindex_radar
from wetterdienst.provider.dwd.radar.metadata import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarParameter,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


def test_radar_fileindex_composite_pg_reflectivity_bin():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PG_REFLECTIVITY,
        fmt=DwdRadarDataFormat.BINARY,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(PurePath(url).match("*/weather/radar/composit/pg/*---bin") for url in urls)


def test_radar_fileindex_composite_pg_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PG_REFLECTIVITY,
        fmt=DwdRadarDataFormat.BUFR,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(PurePath(url).match("*/weather/radar/composit/pg/*---bufr") for url in urls)


@pytest.mark.xfail(reason="Out of service", strict=True)
def test_radar_fileindex_composite_rx_reflectivity_bin():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RX_REFLECTIVITY,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(PurePath(url).match("*/weather/radar/composit/rx/*---bin") for url in urls)


@pytest.mark.parametrize(
    "parameter",
    [
        DwdRadarParameter.RW_REFLECTIVITY,
        DwdRadarParameter.RY_REFLECTIVITY,
        DwdRadarParameter.SF_REFLECTIVITY,
    ],
)
def test_radar_fileindex_radolan_reflectivity_bin(parameter):

    file_index = create_fileindex_radar(
        parameter=parameter,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(
        PurePath(url).match(f"*/weather/radar/radolan/{parameter.value}/*---bin")
        for url in urls
        if not url.endswith(".bz2")
    )


def test_radar_fileindex_sites_px_reflectivity_bin():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PX_REFLECTIVITY,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BINARY,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(PurePath(url).match("*/weather/radar/sites/px/boo/*---bin") for url in urls)


def test_radar_fileindex_sites_px_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PX_REFLECTIVITY,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BUFR,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(PurePath(url).match("*/weather/radar/sites/px/boo/*---buf") for url in urls)


def test_radar_fileindex_sites_px250_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.PX250_REFLECTIVITY,
        site=DwdRadarSite.BOO,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all("/weather/radar/sites/px250/boo" in url for url in urls)


def test_radar_fileindex_sites_sweep_bufr():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.BUFR,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(PurePath(url).match("*/weather/radar/sites/sweep_vol_v/boo/*--buf.bz2") for url in urls)


def test_radar_fileindex_sites_sweep_vol_v_hdf5_simple():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()

    assert all("/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_simple" in url for url in urls)


def test_radar_fileindex_sites_sweep_vol_v_hdf5_polarimetric():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.POLARIMETRIC,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()

    assert all("/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_polarimetric" in url for url in urls)


def test_radar_fileindex_radolan_cdc_daily_recent():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.DAILY,
        period=Period.RECENT,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(
        PurePath(url).match("*/climate_environment/CDC/grids_germany/daily/radolan/recent/bin/*---bin.gz")
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_radolan_cdc_daily_historical():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.DAILY,
        period=Period.HISTORICAL,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(
        PurePath(url).match("*/climate_environment/CDC/grids_germany/daily/radolan/historical/bin/*/SF*.tar.gz")
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_radolan_cdc_hourly_recent():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.HOURLY,
        period=Period.RECENT,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(
        PurePath(url).match("*/climate_environment/CDC/grids_germany/hourly/radolan/recent/bin/*---bin.gz")
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_radolan_cdc_hourly_historical():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.HOURLY,
        period=Period.HISTORICAL,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()
    assert all(
        PurePath(url).match("*/climate_environment/CDC/grids_germany/hourly/radolan/historical/bin/*/RW*.tar.gz")
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_radolan_cdc_5minutes():

    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=Resolution.MINUTE_5,
    )

    urls = file_index[DwdColumns.FILENAME.value].tolist()

    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/5_minutes/radolan/reproc/2017_002/bin/*/YW2017*.tar"
        )
        for url in urls
        if not url.endswith(".tar.gz")
    )
