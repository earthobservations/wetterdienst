from pathlib import PurePath

from wetterdienst import TimeResolution
from wetterdienst.dwd.radar.metadata import RadarParameter, RadarDataType
from wetterdienst.dwd.radar.sites import RadarSites
from wetterdienst.dwd.radar.index import _create_fileindex_radar


def test_radar_composites_fileindex_pg_reflectivity_bin():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PG_REFLECTIVITY,
        radar_data_type=RadarDataType.BINARY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/pg/*---bin") for url in urls
    )


def test_radar_composites_fileindex_pg_reflectivity_bufr():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PG_REFLECTIVITY,
        radar_data_type=RadarDataType.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/pg/*---bufr") for url in urls
    )


def test_radar_composites_fileindex_rx_reflectivity_bin():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.RX_REFLECTIVITY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/composit/rx/*---bin") for url in urls
    )


def test_radar_sites_fileindex_px_reflectivity_bin():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PX_REFLECTIVITY,
        radar_site=RadarSites.BOO,
        radar_data_type=RadarDataType.BINARY,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/px/boo/*---bin") for url in urls
    )


def test_radar_sites_fileindex_px_reflectivity_bufr():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PX_REFLECTIVITY,
        radar_site=RadarSites.BOO,
        radar_data_type=RadarDataType.BUFR,
    )

    urls = file_index["FILENAME"].tolist()
    assert all(
        PurePath(url).match("*/weather/radar/sites/px/boo/*---buf") for url in urls
    )


def test_radar_sites_fileindex_px250_reflectivity_bufr():

    file_index = _create_fileindex_radar(
        parameter=RadarParameter.PX250_REFLECTIVITY,
        radar_site=RadarSites.BOO,
    )

    urls = file_index["FILENAME"].tolist()
    assert all("/weather/radar/sites/px250/boo" in url for url in urls)


def test_radar_sites_fileindex_sweep_bufr():

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


def test_radar_sites_fileindex_sweep_hdf5():

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
