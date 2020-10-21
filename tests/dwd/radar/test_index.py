import pytest
from pathlib import PurePath
from wetterdienst.dwd.radar.metadata import (
    RadarParameter,
    RadarDataFormat,
    RadarDataSubset,
    DWDRadarTimeResolution,
    DWDRadarPeriodType
)
from wetterdienst.dwd.radar.sites import RadarSite
from wetterdienst.dwd.radar.index import create_fileindex_radar


def test_radar_fileindex_composite_pg_reflectivity_bin():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.PG_REFLECTIVITY,
        format=RadarDataFormat.BINARY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/pg/*---bin") for url in urls
    )


def test_radar_fileindex_composite_pg_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.PG_REFLECTIVITY,
        format=RadarDataFormat.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/pg/*---bufr") for url in urls
    )


def test_radar_fileindex_composite_rx_reflectivity_bin():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.RX_REFLECTIVITY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/rx/*---bin") for url in urls
    )


@pytest.mark.parametrize(
    "parameter",
    [
        RadarParameter.RW_REFLECTIVITY,
        RadarParameter.RY_REFLECTIVITY,
        RadarParameter.SF_REFLECTIVITY,
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
        parameter=RadarParameter.PX_REFLECTIVITY,
        site=RadarSite.BOO,
        format=RadarDataFormat.BINARY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/px/boo/*---bin") for url in urls
    )


def test_radar_fileindex_sites_px_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.PX_REFLECTIVITY,
        site=RadarSite.BOO,
        format=RadarDataFormat.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/px/boo/*---buf") for url in urls
    )


def test_radar_fileindex_sites_px250_reflectivity_bufr():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.PX250_REFLECTIVITY,
        site=RadarSite.BOO,
    )

    urls = file_index["FILENAME"].tolist()
    assert all("/weather/radar/sites/px250/boo" in url for url in urls)


def test_radar_fileindex_sites_sweep_bufr():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_H,
        site=RadarSite.BOO,
        format=RadarDataFormat.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/sweep_vol_v/boo/*--buf.bz2")
        for url in urls
    )


def test_radar_fileindex_sites_sweep_vol_v_hdf5_simple():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_H,
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.SIMPLE,
    )

    urls = file_index["FILENAME"].tolist()

    assert all(
        "/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_simple" in url for url in urls
    )


def test_radar_fileindex_sites_sweep_vol_v_hdf5_polarimetric():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_H,
        site=RadarSite.BOO,
        format=RadarDataFormat.HDF5,
        subset=RadarDataSubset.POLARIMETRIC,
    )

    urls = file_index["FILENAME"].tolist()

    assert all(
        "/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_polarimetric" in url
        for url in urls
    )


def test_radar_fileindex_radolan_cdc_daily_recent():

    file_index = create_fileindex_radar(
        parameter=RadarParameter.RADOLAN_CDC,
        time_resolution=DWDRadarTimeResolution.DAILY,
        period_type=DWDRadarPeriodType.RECENT,
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
        parameter=RadarParameter.RADOLAN_CDC,
        time_resolution=DWDRadarTimeResolution.DAILY,
        period_type=DWDRadarPeriodType.HISTORICAL,
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
        parameter=RadarParameter.RADOLAN_CDC,
        time_resolution=DWDRadarTimeResolution.HOURLY,
        period_type=DWDRadarPeriodType.RECENT,
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
        parameter=RadarParameter.RADOLAN_CDC,
        time_resolution=DWDRadarTimeResolution.HOURLY,
        period_type=DWDRadarPeriodType.HISTORICAL,
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
        parameter=RadarParameter.RADOLAN_CDC,
        time_resolution=DWDRadarTimeResolution.MINUTE_5,
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
