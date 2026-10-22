# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for radar file index creation."""

from pathlib import PurePath

import pytest

from wetterdienst import Period, Resolution, Settings
from wetterdienst.provider.dwd.radar.index import create_fileindex_radar, create_fileindex_radolan_cdc
from wetterdienst.provider.dwd.radar.metadata import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarParameter,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "folder"),
    [
        (DwdRadarParameter.RV_REFLECTIVITY, "rv"),
        (DwdRadarParameter.WN_REFLECTIVITY, "wn"),
        (DwdRadarParameter.RS_PRECIPITATION_SUM, "rs"),
    ],
)
def test_radar_fileindex_composite_tar(parameter: DwdRadarParameter, folder: str, default_settings: Settings) -> None:
    """Test file index creation for the DWD radar composites, one .tar of ODIM HDF5 files a run (GH-3279)."""
    file_index = create_fileindex_radar(parameter=parameter, settings=default_settings)
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match(f"*/weather/radar/composite/{folder}/composite_{folder}_*.tar") for url in urls)
    # the file of the latest run is one of them, named with one underscore or two
    assert sum("_LATEST.tar" in url for url in urls) == 1


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [
        DwdRadarParameter.RW_REFLECTIVITY,
        DwdRadarParameter.RY_REFLECTIVITY,
        DwdRadarParameter.SF_REFLECTIVITY,
        DwdRadarParameter.YW_REFLECTIVITY,
    ],
)
def test_radar_fileindex_radolan_reflectivity_bin(parameter: DwdRadarParameter, default_settings: Settings) -> None:
    """Test file index creation for DWD radar reflectivity."""
    file_index = create_fileindex_radar(parameter=parameter, settings=default_settings)
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(
        PurePath(url).match(f"*/weather/radar/radolan/{parameter.value}/*---bin.hdf5")
        for url in urls
        if not url.endswith(".bz2")
    )


@pytest.mark.remote
def test_radar_fileindex_sites_dx_reflectivity_bin(default_settings: Settings) -> None:
    """Test file index creation for DWD radar DX reflectivity, which is still the binary file."""
    file_index = create_fileindex_radar(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match("*/weather/radar/sites/dx/boo/*---bin") for url in urls)


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "folder"),
    [
        (DwdRadarParameter.HX_REFLECTIVITY, "hx"),
        (DwdRadarParameter.DMAX_REFLECTIVITY, "dmax"),
        (DwdRadarParameter.VII_INTEGRATED_ICE, "vii"),
        (DwdRadarParameter.HYMECNG_PRECIPITATION_TYPE, "hymecng"),
    ],
)
def test_radar_fileindex_composite_hdf5_files(
    parameter: DwdRadarParameter, folder: str, default_settings: Settings
) -> None:
    """Test file index creation for the composites that are one ODIM HDF5 file a run (GH-3283)."""
    file_index = create_fileindex_radar(parameter=parameter, settings=default_settings, parse_datetime=True)
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match(f"*/weather/radar/composite/{folder}/composite_*-hd5") for url in urls)
    # the LATEST file has no date and is left out of the dated index
    assert not any("latest" in url.lower() for url in urls)
    # a run every 5 minutes, for about two days
    assert 500 <= file_index.height <= 600


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "folder", "pattern"),
    [
        (DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS, "konrad3d", "KONRAD3D_*.xml"),
        (DwdRadarParameter.MESOCYCLONE_DETECTION, "mesocyclones", "meso_*.xml"),
    ],
)
def test_radar_fileindex_xml(
    parameter: DwdRadarParameter, folder: str, pattern: str, default_settings: Settings
) -> None:
    """Test file index creation for the XML files of the detections (GH-3283)."""
    file_index = create_fileindex_radar(parameter=parameter, settings=default_settings, parse_datetime=True)
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match(f"*/weather/radar/{folder}/{pattern}") for url in urls)
    assert 500 <= file_index.height <= 600


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [
        DwdRadarParameter.SWEEP_VOL_ZDR,
        DwdRadarParameter.SWEEP_VOL_RHOHV,
        DwdRadarParameter.SWEEP_VOL_PHIDP,
        DwdRadarParameter.SWEEP_PCP_ZDR,
        DwdRadarParameter.SWEEP_PCP_RHOHV,
        DwdRadarParameter.SWEEP_PCP_PHIDP,
    ],
)
def test_radar_fileindex_sites_sweep_polarimetric_unfiltered(
    parameter: DwdRadarParameter, default_settings: Settings
) -> None:
    """Test file index creation for the polarimetric sweeps, which have the folder `unfiltered` only (GH-3283)."""
    file_index = create_fileindex_radar(parameter=parameter, site=DwdRadarSite.BOO, settings=default_settings)
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(f"/weather/radar/sites/{parameter.value}/boo/unfiltered/" in url for url in urls)
    assert all(url.endswith("-hd5") for url in urls)


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "folder"),
    [
        (DwdRadarParameter.LMAX_VOLUME_SCAN, "lmax"),
        (DwdRadarParameter.PE_ECHO_TOP, "pe"),
        (DwdRadarParameter.PR_VELOCITY, "pr"),
        (DwdRadarParameter.PX250_REFLECTIVITY, "px250"),
        (DwdRadarParameter.PZ_CAPPI, "pz"),
    ],
)
def test_radar_fileindex_sites_hdf5(parameter: DwdRadarParameter, folder: str, default_settings: Settings) -> None:
    """Test file index creation for the DWD radar site products, which are ODIM HDF5 files (GH-3279)."""
    file_index = create_fileindex_radar(
        parameter=parameter,
        site=DwdRadarSite.BOO,
        settings=default_settings,
    )
    assert not file_index.is_empty()
    urls = file_index.get_column("filename").to_list()
    assert all(PurePath(url).match(f"*/weather/radar/sites/{folder}/boo/*-hd5") for url in urls)


@pytest.mark.remote
def test_radar_fileindex_sites_sweep_vol_v_hdf5_simple(default_settings: Settings) -> None:
    """Test file index creation for DWD radar sweep vol velocity."""
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
def test_radar_fileindex_sites_sweep_vol_v_hdf5_polarimetric(default_settings: Settings) -> None:
    """Test file index creation for polarimetric sweep volume velocity."""
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
def test_radar_fileindex_radolan_cdc_daily_recent(default_settings: Settings) -> None:
    """Test file index creation for RADOLAN CDC daily recent."""
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
def test_radar_fileindex_radolan_cdc_daily_historical(default_settings: Settings) -> None:
    """Test file index creation for RADOLAN CDC daily historical."""
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
def test_radar_fileindex_radolan_cdc_hourly_recent(default_settings: Settings) -> None:
    """Test file index creation for RADOLAN CDC hourly recent."""
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
def test_radar_fileindex_radolan_cdc_hourly_historical(default_settings: Settings) -> None:
    """Test file index creation for RADOLAN CDC hourly historical."""
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
def test_radar_fileindex_radolan_cdc_5minutes(default_settings: Settings) -> None:
    """Test file index creation for RADOLAN CDC 5 minutes."""
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
