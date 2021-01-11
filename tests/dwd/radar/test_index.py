from pathlib import PurePath

import pytest

from wetterdienst.dwd.radar.index import create_fileindex_radar
from wetterdienst.dwd.radar.metadata import (
    DWDRadarDataFormat,
    DWDRadarDataSubset,
    DWDRadarParameter,
    DWDRadarPeriod,
    DWDRadarResolution,
)
from wetterdienst.dwd.radar.sites import DWDRadarSite


def test_radar_fileindex_composite_pg_reflectivity_bin():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.PG_REFLECTIVITY,
        fmt=DWDRadarDataFormat.BINARY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/pg/*---bin") for url in urls
    )


def test_radar_fileindex_composite_pg_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.PG_REFLECTIVITY,
        fmt=DWDRadarDataFormat.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/pg/*---bufr") for url in urls
    )


def test_radar_fileindex_composite_rx_reflectivity_bin():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.RX_REFLECTIVITY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/rx/*---bin") for url in urls
    )


@pytest.mark.parametrize(
    "parameter",
    [
        DWDRadarParameter.RW_REFLECTIVITY,
        DWDRadarParameter.RY_REFLECTIVITY,
        DWDRadarParameter.SF_REFLECTIVITY,
    ],
)
def test_radar_fileindex_radolan_reflectivity_bin(parameter):

    file_index = create_fileindex_radar(
        parameter=parameter,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(f"*/weather/radar/radolan/{parameter.value}/*---bin")
        for url in urls
    )


def test_radar_fileindex_sites_px_reflectivity_bin():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.PX_REFLECTIVITY,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BINARY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/px/boo/*---bin") for url in urls
    )


def test_radar_fileindex_sites_px_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.PX_REFLECTIVITY,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/px/boo/*---buf") for url in urls
    )


def test_radar_fileindex_sites_px250_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.PX250_REFLECTIVITY,
        site=DWDRadarSite.BOO,
    )

    urls = file_index["FILENAME"].tolist()
    assert all("/weather/radar/sites/px250/boo" in url for url in urls)


def test_radar_fileindex_sites_sweep_bufr():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/sweep_vol_v/boo/*--buf.bz2")
        for url in urls
    )


def test_radar_fileindex_sites_sweep_vol_v_hdf5_simple():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.HDF5,
        subset=DWDRadarDataSubset.SIMPLE,
    )

    urls = file_index["FILENAME"].tolist()

    assert all(
        "/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_simple" in url for url in urls
    )


def test_radar_fileindex_sites_sweep_vol_v_hdf5_polarimetric():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.HDF5,
        subset=DWDRadarDataSubset.POLARIMETRIC,
    )

    urls = file_index["FILENAME"].tolist()

    assert all(
        "/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_polarimetric" in url
        for url in urls
    )


def test_radar_fileindex_radolan_cdc_daily_recent():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.DAILY,
        period=DWDRadarPeriod.RECENT,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/daily/radolan/recent/bin/*---bin.gz"
        )
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_radolan_cdc_daily_historical():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.DAILY,
        period=DWDRadarPeriod.HISTORICAL,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/daily/radolan/historical/bin/*/SF*.tar.gz"
        )
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_radolan_cdc_hourly_recent():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.HOURLY,
        period=DWDRadarPeriod.RECENT,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/hourly/radolan/recent/bin/*---bin.gz"
        )
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_radolan_cdc_hourly_historical():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.HOURLY,
        period=DWDRadarPeriod.HISTORICAL,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/hourly/radolan/historical/bin/*/RW*.tar.gz"
        )
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_radolan_cdc_5minutes():

    file_index = create_fileindex_radar(
        parameter=DWDRadarParameter.RADOLAN_CDC,
        resolution=DWDRadarResolution.MINUTE_5,
    )

    urls = file_index["FILENAME"].tolist()
    for url in urls:
        print(url)
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/5_minutes/radolan/reproc/2017_002/bin/*/YW2017*.tar"
        )
        for url in urls
        if not url.endswith(".tar.gz")
    )
