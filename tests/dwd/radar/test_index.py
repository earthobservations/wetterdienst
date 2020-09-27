import pytest
from pathlib import PurePath

from wetterdienst import TimeResolution, PeriodType
from wetterdienst.dwd.radar.metadata import RadarParameter, RadarDataType
from wetterdienst.dwd.radar.sites import RadarSites
from wetterdienst.dwd.radar.index import _create_fileindex_radar


def test_radar_fileindex_composite_pg_reflectivity_bin():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PG_REFLECTIVITY,
        radar_data_type=RadarDataType.BINARY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/pg/*---bin") for url in urls
    )


def test_radar_fileindex_composite_pg_reflectivity_bufr():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PG_REFLECTIVITY,
        radar_data_type=RadarDataType.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/pg/*---bufr") for url in urls
    )


def test_radar_fileindex_composite_rx_reflectivity_bin():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.RX_REFLECTIVITY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/rx/*---bin") for url in urls
    )


@pytest.mark.parametrize(
    "radar_parameter",
    [
        RadarParameter.RW_REFLECTIVITY,
        RadarParameter.RY_REFLECTIVITY,
        RadarParameter.SF_REFLECTIVITY,
    ],
)
def test_radar_fileindex_radolan_reflectivity_bin(radar_parameter):

    file_index = _create_fileindex_radar(
        parameter=radar_parameter,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(f"*/weather/radar/radolan/{radar_parameter.value}/*---bin")
        for url in urls
    )


def test_radar_fileindex_sites_px_reflectivity_bin():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PX_REFLECTIVITY,
        radar_site=RadarSites.BOO,
        radar_data_type=RadarDataType.BINARY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/px/boo/*---bin") for url in urls
    )


def test_radar_fileindex_sites_px_reflectivity_bufr():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PX_REFLECTIVITY,
        radar_site=RadarSites.BOO,
        radar_data_type=RadarDataType.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/px/boo/*---buf") for url in urls
    )


def test_radar_fileindex_sites_px250_reflectivity_bufr():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PX250_REFLECTIVITY,
        radar_site=RadarSites.BOO,
    )

    urls = file_index["FILENAME"].tolist()
    assert all("/weather/radar/sites/px250/boo" in url for url in urls)


def test_radar_fileindex_sites_sweep_bufr():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_V,
        radar_site=RadarSites.BOO,
        radar_data_type=RadarDataType.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/sweep_vol_v/boo/*--buf.bz2")
        for url in urls
    )


def test_radar_fileindex_sites_sweep_hdf5():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.SWEEP_VOL_VELOCITY_V,
        radar_site=RadarSites.BOO,
        radar_data_type=RadarDataType.HDF5,
    )

    urls = file_index["FILENAME"].tolist()
    assert any(
        "/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_polarimetric" in url
        for url in urls
    )
    assert any(
        "/weather/radar/sites/sweep_vol_v/boo/hdf5/filter_simple" in url for url in urls
    )


def test_radar_fileindex_grid_daily_recent():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.RADOLAN_GRID,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.RECENT,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/daily/radolan/recent/bin/*---bin.gz"
        )
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_grid_daily_historical():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.RADOLAN_GRID,
        time_resolution=TimeResolution.DAILY,
        period_type=PeriodType.HISTORICAL,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/daily/radolan/historical/bin/*/SF*.tar.gz"
        )
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_grid_hourly_recent():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.RADOLAN_GRID,
        time_resolution=TimeResolution.HOURLY,
        period_type=PeriodType.RECENT,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/hourly/radolan/recent/bin/*---bin.gz"
        )
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_grid_hourly_historical():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.RADOLAN_GRID,
        time_resolution=TimeResolution.HOURLY,
        period_type=PeriodType.HISTORICAL,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match(
            "*/climate_environment/CDC/grids_germany/hourly/radolan/historical/bin/*/RW*.tar.gz"
        )
        for url in urls
        if not url.endswith(".pdf")
    )


def test_radar_fileindex_grid_5minutes():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.RADOLAN_GRID,
        time_resolution=TimeResolution.MINUTE_5,
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
