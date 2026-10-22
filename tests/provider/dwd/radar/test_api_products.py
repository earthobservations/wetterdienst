# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the products DWD publishes that `dwd/radar` did not offer: composites, RADOLAN YW, sweeps, XML (GH-3283).

The listings are lines of the real ones, read on 2026-10-22; the files in `files/` are real files of that week, the
smallest of their product (DWD's open data, https://opendata.dwd.de/weather/radar/): `composite_VII_*` and
`composite_HymecNG_*` are composites, `composite_rs_*_000-hd5` is the analysis in a `.tar` of RS, `raa01-yw_*` is YW,
`ras07-vol5minng01_sweeph5onem_uzdr_07-*` a sweep of the volume scan, `KONRAD3D_*` and `meso_*` the XML files.
The reflectivity composites HX and DMAX (0.6 and 1.5 MB), and the sweeps of the precipitation scan, of RHOHV and of
PHIDP, are read by the remote tests only.
"""

from __future__ import annotations

import datetime as dt
import tarfile
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import RequestError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.radar import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarDate,
    DwdRadarParameter,
    DwdRadarValues,
)
from wetterdienst.provider.dwd.radar.index import build_path_to_parameter, create_fileindex_radar
from wetterdienst.provider.dwd.radar.metadata import (
    RADAR_DATA_FORMATS,
    RADAR_DATA_SUBSETS,
    RADAR_PARAMETERS_RADOLAN,
    RADAR_PARAMETERS_SWEEPS,
)
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
from wetterdienst.util.network import File

if TYPE_CHECKING:
    import polars as pl

UTC = ZoneInfo("UTC")
RADAR = "https://opendata.dwd.de/weather/radar"
FILES = Path(__file__).parent / "files"

_VOL = "ras07-vol5minng01_sweeph5onem"
_PCP = "ras07-pcpng01_sweeph5onem"
LISTINGS = {
    f"{RADAR}/composite/hx": [
        "composite_hx_20261022_1305-hd5",
        "composite_hx_20261022_1310-hd5",
        "composite_hx_LATEST-hd5",
    ],
    f"{RADAR}/composite/dmax": [
        "composite_dmax_20261022_1305-hd5",
        "composite_dmax_20261022_1310-hd5",
        "composite_dmax_LATEST-hd5",
    ],
    f"{RADAR}/composite/vii": [
        "composite_VII_20261022_1305-hd5",
        "composite_VII_20261022_1310-hd5",
        "composite_VII_latest-hd5",
    ],
    f"{RADAR}/composite/hymecng": [
        "composite_HymecNG_20261022_1305_000-hd5",
        "composite_HymecNG_20261022_1310_000-hd5",
        "composite_HymecNG_LATEST_000-hd5",
    ],
    f"{RADAR}/composite/rs": [
        "composite_rs_20261022_1305.tar",
        "composite_rs_20261022_1310.tar",
        "composite_rs_LATEST.tar",
    ],
    f"{RADAR}/radolan/yw": [
        "raa01-yw_10000-2610221240-dwd---bin.hdf5",
        "raa01-yw_10000-2610221245-dwd---bin.hdf5",
        "raa01-yw_10000-latest-dwd---bin.hdf5",
    ],
    f"{RADAR}/konrad3d": [
        "KONRAD3D_20261022T130500.xml",
        "KONRAD3D_20261022T131000.xml",
    ],
    f"{RADAR}/mesocyclones": [
        "meso_20261022_1305.xml",
        "meso_20261022_1310.xml",
        "meso_latest.xml",
    ],
    f"{RADAR}/sites/sweep_vol_zdr/boo/unfiltered": [
        f"{_VOL}_uzdr_00-2026102213105700-boo-10132-hd5",
        f"{_VOL}_uzdr_01-2026102213112000-boo-10132-hd5",
        f"{_VOL}_uzdr_09-2026102213140200-boo-10132-hd5",
        f"{_VOL}_uzdr_00-2026102213155700-boo-10132-hd5",
        f"{_VOL}_uzdr_09-LATEST-boo-10132-hd5",
    ],
    f"{RADAR}/sites/sweep_vol_rhohv/boo/unfiltered": [
        f"{_VOL}_urhohv_00-2026102213105700-boo-10132-hd5",
        f"{_VOL}_urhohv_09-2026102213140200-boo-10132-hd5",
    ],
    f"{RADAR}/sites/sweep_vol_phidp/boo/unfiltered": [
        f"{_VOL}_uphidp_00-2026102213105700-boo-10132-hd5",
        f"{_VOL}_uphidp_09-2026102213140200-boo-10132-hd5",
    ],
    f"{RADAR}/sites/sweep_pcp_zdr/boo/unfiltered": [
        f"{_PCP}_uzdr_00-2026102213103300-boo-10132-hd5",
        f"{_PCP}_uzdr_00-2026102213153300-boo-10132-hd5",
        f"{_PCP}_uzdr_00-LATEST-boo-10132-hd5",
    ],
    f"{RADAR}/sites/sweep_pcp_rhohv/boo/unfiltered": [
        f"{_PCP}_urhohv_00-2026102213103300-boo-10132-hd5",
        f"{_PCP}_urhohv_00-LATEST-boo-10132-hd5",
    ],
    f"{RADAR}/sites/sweep_pcp_phidp/boo/unfiltered": [
        f"{_PCP}_uphidp_00-2026102213103300-boo-10132-hd5",
        f"{_PCP}_uphidp_00-LATEST-boo-10132-hd5",
    ],
}


@pytest.fixture(autouse=True)
def listings(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve the listings above, as the urls the listing of the server answers, and take down what is asked.

    The remote tests, at the end, list the server itself.
    """
    asked: list[str] = []
    if request.node.get_closest_marker("remote"):
        return asked

    def list_remote_files(url: str, settings: Settings, cache_expiry: CacheExpiry) -> list[str]:  # noqa: ARG001
        asked.append(url)
        return [f"{url.rstrip('/')}/{name}" for name in LISTINGS.get(url.rstrip("/"), [])]

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.index.list_remote_files_fsspec", list_remote_files)
    return asked


def _names(df: pl.DataFrame) -> list[str]:
    return [url.rsplit("/", 1)[1] for url in df.get_column("filename").to_list()]


def _served(monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]) -> list[tuple[str, CacheExpiry]]:
    """Serve the files of these urls to the reader, and take down what is downloaded and for how long it may be kept."""
    downloaded: list[tuple[str, CacheExpiry]] = []

    def download_file(url: str, ttl: CacheExpiry, **_: object) -> File:
        downloaded.append((url, ttl))
        return File(url=url, content=BytesIO(files[url]), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.api.download_file", download_file)
    return downloaded


@pytest.mark.parametrize(
    ("parameter", "folder", "suffix"),
    [
        (DwdRadarParameter.HX_REFLECTIVITY, "hx", "-hd5"),
        (DwdRadarParameter.DMAX_REFLECTIVITY, "dmax", "-hd5"),
        (DwdRadarParameter.VII_INTEGRATED_ICE, "vii", "-hd5"),
        (DwdRadarParameter.HYMECNG_PRECIPITATION_TYPE, "hymecng", "_000-hd5"),
    ],
)
def test_a_composite_that_is_a_file_a_run_is_listed_and_dated_by_its_name(
    parameter: DwdRadarParameter, folder: str, suffix: str
) -> None:
    """Test that HX, DMAX, VII and HymecNG are the `-hd5` files themselves, not a .tar, and LATEST is not dated."""
    listed = create_fileindex_radar(parameter=parameter, settings=Settings())
    assert listed.height == 3
    assert all(url.startswith(f"{RADAR}/composite/{folder}/composite_") for url in listed["filename"])
    assert all(url.endswith("-hd5") for url in listed["filename"])
    assert parameter in RADAR_DATA_FORMATS
    assert DwdRadarValues(parameter=parameter, start="2026-10-22 13:07").format == DwdRadarDataFormat.HDF5

    dated = create_fileindex_radar(parameter=parameter, settings=Settings(), parse_datetime=True)
    assert dated.get_column("datetime").to_list() == [
        dt.datetime(2026, 10, 22, 13, 5, tzinfo=UTC),
        dt.datetime(2026, 10, 22, 13, 10, tzinfo=UTC),
    ]
    assert {url.endswith(suffix) for url in dated["filename"]} == {True}


def test_rs_is_a_tar_a_run_as_rv_is() -> None:
    """Test that RS, which has a lead time forecasts, is listed as the .tar of the run, and LATEST is not dated."""
    listed = create_fileindex_radar(
        parameter=DwdRadarParameter.RS_PRECIPITATION_SUM, settings=Settings(), parse_datetime=True
    )
    assert _names(listed) == ["composite_rs_20261022_1305.tar", "composite_rs_20261022_1310.tar"]
    assert listed.get_column("datetime").to_list()[-1] == dt.datetime(2026, 10, 22, 13, 10, tzinfo=UTC)


def test_yw_is_listed_as_the_radolan_products_are() -> None:
    """Test that YW, a RADOLAN product, is dated with two digits of the year, whatever format it is asked in."""
    for fmt in (None, DwdRadarDataFormat.HDF5, DwdRadarDataFormat.BINARY):
        listed = create_fileindex_radar(
            parameter=DwdRadarParameter.YW_REFLECTIVITY, fmt=fmt, settings=Settings(), parse_datetime=True
        )
        assert listed.get_column("datetime").to_list() == [
            dt.datetime(2026, 10, 22, 12, 40, tzinfo=UTC),
            dt.datetime(2026, 10, 22, 12, 45, tzinfo=UTC),
        ]
    assert DwdRadarParameter.YW_REFLECTIVITY in RADAR_PARAMETERS_RADOLAN
    assert build_path_to_parameter(DwdRadarParameter.YW_REFLECTIVITY) == "weather/radar/radolan/yw"


def test_yw_window_is_aligned_to_5_minutes_as_ry_is() -> None:
    """Test that YW, published every 5 minutes (RW is every 10), is aligned like RY, and reads one file for a start."""
    request = DwdRadarValues(parameter=DwdRadarParameter.YW_REFLECTIVITY, start="2026-10-22 12:47")
    assert request.start == dt.datetime(2026, 10, 22, 12, 45, tzinfo=UTC)
    assert request.end == dt.datetime(2026, 10, 22, 12, 49, 59, tzinfo=UTC)


@pytest.mark.parametrize(
    ("parameter", "folder", "names"),
    [
        (
            DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS,
            "konrad3d",
            ["KONRAD3D_20261022T130500.xml", "KONRAD3D_20261022T131000.xml"],
        ),
        (
            DwdRadarParameter.MESOCYCLONE_DETECTION,
            "mesocyclones",
            ["meso_20261022_1305.xml", "meso_20261022_1310.xml"],
        ),
    ],
)
def test_the_xml_products_are_listed_from_their_own_directory_and_dated(
    parameter: DwdRadarParameter, folder: str, names: list[str]
) -> None:
    """Test that KONRAD3D (`...T130500`) and the mesocyclones (`..._1305`) are dated to the run, which they name."""
    assert build_path_to_parameter(parameter) == f"weather/radar/{folder}"
    listed = create_fileindex_radar(parameter=parameter, settings=Settings(), parse_datetime=True)
    assert _names(listed) == names
    assert listed.get_column("datetime").to_list() == [
        dt.datetime(2026, 10, 22, 13, 5, tzinfo=UTC),
        dt.datetime(2026, 10, 22, 13, 10, tzinfo=UTC),
    ]
    assert RADAR_DATA_FORMATS[parameter] == (DwdRadarDataFormat.XML,)
    assert DwdRadarValues(parameter=parameter, start="2026-10-22 13:07").format == DwdRadarDataFormat.XML


@pytest.mark.parametrize(
    ("parameter", "folder", "quantity"),
    [
        (DwdRadarParameter.SWEEP_VOL_ZDR, "sweep_vol_zdr", "uzdr"),
        (DwdRadarParameter.SWEEP_VOL_RHOHV, "sweep_vol_rhohv", "urhohv"),
        (DwdRadarParameter.SWEEP_VOL_PHIDP, "sweep_vol_phidp", "uphidp"),
        (DwdRadarParameter.SWEEP_PCP_ZDR, "sweep_pcp_zdr", "uzdr"),
        (DwdRadarParameter.SWEEP_PCP_RHOHV, "sweep_pcp_rhohv", "urhohv"),
        (DwdRadarParameter.SWEEP_PCP_PHIDP, "sweep_pcp_phidp", "uphidp"),
    ],
)
def test_the_polarimetric_sweeps_are_the_files_of_the_unfiltered_folder(
    parameter: DwdRadarParameter, folder: str, quantity: str
) -> None:
    """Test that the folder is `unfiltered`, that no `subset` need be named, and that LATEST files are not dated."""
    assert parameter in RADAR_PARAMETERS_SWEEPS
    assert RADAR_DATA_SUBSETS[parameter] == (DwdRadarDataSubset.UNFILTERED,)
    path = build_path_to_parameter(parameter, site=DwdRadarSite.BOO)
    assert path == f"weather/radar/sites/{folder}/boo/unfiltered/"
    assert build_path_to_parameter(parameter, site=DwdRadarSite.BOO, subset=DwdRadarDataSubset.UNFILTERED) == path

    request = DwdRadarValues(parameter=parameter, site=DwdRadarSite.BOO, start="2026-10-22 13:10")
    assert request.format == DwdRadarDataFormat.HDF5
    assert request.subset == DwdRadarDataSubset.UNFILTERED

    listed = create_fileindex_radar(
        parameter=parameter, site=DwdRadarSite.BOO, settings=Settings(), parse_datetime=True
    )
    assert all(f"_{quantity}_" in url and f"/sites/{folder}/boo/unfiltered/" in url for url in listed["filename"])
    assert not any("LATEST" in url for url in listed["filename"])
    dated = [name for name in LISTINGS[f"{RADAR}/sites/{folder}/boo/unfiltered"] if "LATEST" not in name]
    assert listed.height == len(dated)


@pytest.mark.parametrize("subset", [DwdRadarDataSubset.SIMPLE, DwdRadarDataSubset.POLARIMETRIC])
def test_the_polarimetric_sweeps_have_no_filter_folder(subset: DwdRadarDataSubset, listings: list[str]) -> None:
    """Test that a folder of a filter, which only the velocity and the reflectivity have, is refused, not listed."""
    with pytest.raises(
        RequestError, match=rf"SWEEP_VOL_ZDR is offered as UNFILTERED \(unfiltered\) only, not as {subset.name}"
    ):
        DwdRadarValues(parameter="sweep_vol_zdr", site=DwdRadarSite.BOO, subset=subset, start="2026-10-22 13:10")
    with pytest.raises(RequestError, match="only, not as"):
        create_fileindex_radar(
            parameter=DwdRadarParameter.SWEEP_VOL_ZDR, site=DwdRadarSite.BOO, subset=subset, settings=Settings()
        )
    assert listings == []


def test_the_velocity_and_the_reflectivity_sweeps_are_asked_for_their_filter_as_before() -> None:
    """Test that SWEEP_VOL_VELOCITY_H still has two folders: naming none is the error it was, `unfiltered` is none."""
    with pytest.raises(ValueError, match="Argument 'subset' is missing"):
        build_path_to_parameter(DwdRadarParameter.SWEEP_VOL_VELOCITY_H, site=DwdRadarSite.BOO)
    with pytest.raises(RequestError, match=r"SWEEP_VOL_VELOCITY_H is offered as SIMPLE .* only, not as UNFILTERED"):
        DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
            site=DwdRadarSite.BOO,
            subset=DwdRadarDataSubset.UNFILTERED,
            start="2026-10-22 13:10",
        )
    assert (
        build_path_to_parameter(
            DwdRadarParameter.SWEEP_VOL_VELOCITY_H, site=DwdRadarSite.BOO, subset=DwdRadarDataSubset.SIMPLE
        )
        == "weather/radar/sites/sweep_vol_v/boo/hdf5/filter_simple/"
    )


def test_the_volume_sweeps_are_selected_by_elevation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `elevation` picks the sweep of the volume out of the five minutes, for the polarimetric moments too."""
    base = f"{RADAR}/sites/sweep_vol_zdr/boo/unfiltered"
    wanted = f"{_VOL}_uzdr_09-2026102213140200-boo-10132-hd5"
    downloaded = _served(monkeypatch, {f"{base}/{name}": b"\x89HDF" for name in LISTINGS[base]})

    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_ZDR, site=DwdRadarSite.BOO, start="2026-10-22 13:10", elevation=9
    )
    results = list(request.query())

    assert [url for url, _ in downloaded] == [f"{base}/{wanted}"]
    assert [result.timestamp for result in results] == [dt.datetime(2026, 10, 22, 13, 14, tzinfo=UTC)]

    everything = list(
        DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_VOL_ZDR, site=DwdRadarSite.BOO, start="2026-10-22 13:10"
        ).query()
    )
    # the three sweeps of the run at 13:10, not the one of 13:15 and not the LATEST
    assert len(everything) == 3


def test_the_precipitation_sweeps_have_no_elevation_to_choose() -> None:
    """Test that `elevation` is refused where the scan has one sweep, as it is for SWEEP_PCP_VELOCITY_H."""
    with pytest.raises(ValueError, match="Argument 'elevation' only valid for parameter"):
        DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_PCP_ZDR, site=DwdRadarSite.BOO, start="2026-10-22", elevation=0
        )


@pytest.mark.parametrize("parameter", ["sweep_vol_zdr", "sweep_vol_phidp"])
def test_the_volume_sweeps_have_no_single_latest_file(parameter: str) -> None:
    """Test that LATEST is refused for the volume sweeps: the folder holds one `-LATEST-` file for each elevation."""
    with pytest.raises(
        ValueError, match=r"has no '-latest-' files \(the unfiltered folders have one for each elevation"
    ):
        DwdRadarValues(parameter=parameter, site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST)


def test_the_sweeps_of_a_filter_have_no_latest_file() -> None:
    """Test that LATEST is refused as it was for the sweeps whose folders of a filter hold none."""
    with pytest.raises(ValueError, match=r"HDF5 sweep data has no '-latest-' files$"):
        DwdRadarValues(parameter="sweep_pcp_v", site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST)


@pytest.mark.parametrize(
    ("parameter", "folder", "latest"),
    [
        (DwdRadarParameter.SWEEP_PCP_ZDR, "sweep_pcp_zdr", f"{_PCP}_uzdr_00-LATEST-boo-10132-hd5"),
        (DwdRadarParameter.SWEEP_PCP_RHOHV, "sweep_pcp_rhohv", f"{_PCP}_urhohv_00-LATEST-boo-10132-hd5"),
        (DwdRadarParameter.SWEEP_PCP_PHIDP, "sweep_pcp_phidp", f"{_PCP}_uphidp_00-LATEST-boo-10132-hd5"),
    ],
)
def test_the_polarimetric_precipitation_sweeps_have_one_latest_file(
    parameter: DwdRadarParameter, folder: str, latest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that LATEST is the one `-LATEST-` file of the unfiltered folder, which is asked for again."""
    base = f"{RADAR}/sites/{folder}/boo/unfiltered"
    downloaded = _served(monkeypatch, {f"{base}/{latest}": b"\x89HDF"})

    results = list(DwdRadarValues(parameter=parameter, site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST).query())

    assert downloaded == [(f"{base}/{latest}", CacheExpiry.NO_CACHE)]
    assert len(results) == 1


def test_konrad3d_has_no_latest_file() -> None:
    """Test that LATEST is refused for KONRAD3D, whose directory has none (the mesocyclones have `meso_latest.xml`)."""
    with pytest.raises(ValueError, match="KONRAD3D data has no 'latest' file"):
        DwdRadarValues(parameter=DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS, start=DwdRadarDate.LATEST)


@pytest.mark.parametrize(
    ("parameter", "latest"),
    [
        (DwdRadarParameter.HX_REFLECTIVITY, "composite/hx/composite_hx_LATEST-hd5"),
        (DwdRadarParameter.DMAX_REFLECTIVITY, "composite/dmax/composite_dmax_LATEST-hd5"),
        (DwdRadarParameter.VII_INTEGRATED_ICE, "composite/vii/composite_VII_latest-hd5"),
        (DwdRadarParameter.HYMECNG_PRECIPITATION_TYPE, "composite/hymecng/composite_HymecNG_LATEST_000-hd5"),
        (DwdRadarParameter.YW_REFLECTIVITY, "radolan/yw/raa01-yw_10000-latest-dwd---bin.hdf5"),
        (DwdRadarParameter.MESOCYCLONE_DETECTION, "mesocyclones/meso_latest.xml"),
    ],
)
def test_the_latest_file_of_each_product_is_the_one_named_so_and_is_asked_for_again(
    parameter: DwdRadarParameter, latest: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that LATEST finds `LATEST`, `latest` and `_LATEST_000` alike, once, and does not serve it from the cache."""
    downloaded = _served(monkeypatch, {f"{RADAR}/{latest}": b"\x89HDF"})

    results = list(DwdRadarValues(parameter=parameter, start=DwdRadarDate.LATEST).query())

    assert downloaded == [(f"{RADAR}/{latest}", CacheExpiry.NO_CACHE)]
    assert len(results) == 1


def test_the_latest_of_rs_is_the_analysis_in_its_tar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that RS is read as RV is: the first file of the tar of the latest run."""
    member = (FILES / "composite_rs_20261020_1330_000-hd5").read_bytes()
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for lead in (0, 5):
            info = tarfile.TarInfo(f"composite_rs_20261020_1330_{lead:03d}-hd5")
            info.size = len(member)
            tar.addfile(info, BytesIO(member))
    url = f"{RADAR}/composite/rs/composite_rs_LATEST.tar"
    _served(monkeypatch, {url: buffer.getvalue()})

    results = list(DwdRadarValues(parameter=DwdRadarParameter.RS_PRECIPITATION_SUM, start=DwdRadarDate.LATEST).query())

    assert [result.filename for result in results] == ["composite_rs_20261020_1330_000-hd5"]
    assert results[0].timestamp == dt.datetime(2026, 10, 20, 13, 30, tzinfo=UTC)
    assert results[0].data.getvalue() == member


@pytest.mark.parametrize(
    "parameter", [DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS, DwdRadarParameter.MESOCYCLONE_DETECTION]
)
def test_the_xml_products_synthesize_the_most_recent_file_as_the_hdf5_ones_do(parameter: DwdRadarParameter) -> None:
    """Test that MOST_RECENT is the 5 minute slot before now, as DWD publishes a few minutes after the run."""
    request = DwdRadarValues(parameter=parameter, start=DwdRadarDate.MOST_RECENT)
    assert isinstance(request.start, dt.datetime)
    now = dt.datetime.now(UTC)
    assert dt.timedelta(minutes=5) <= now - request.start <= dt.timedelta(minutes=15)
    assert request.end - request.start == dt.timedelta(minutes=5) - dt.timedelta(seconds=1)


def test_a_vii_file_is_read_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the real VII composite is handed over as it is, dated to its run, and is vertically integrated ice."""
    h5py = pytest.importorskip("h5py")
    content = (FILES / "composite_VII_20261020_1325-hd5").read_bytes()
    url = f"{RADAR}/composite/vii/composite_VII_20261022_1305-hd5"
    downloaded = _served(monkeypatch, {url: content})

    results = list(DwdRadarValues(parameter=DwdRadarParameter.VII_INTEGRATED_ICE, start="2026-10-22 13:07").query())

    assert [(u, ttl) for u, ttl in downloaded] == [(url, CacheExpiry.FIVE_MINUTES)]
    assert len(results) == 1
    assert results[0].url == url
    assert results[0].timestamp == dt.datetime(2026, 10, 22, 13, 5, tzinfo=UTC)
    assert results[0].data.getvalue() == content
    with h5py.File(results[0].data, mode="r") as f:
        assert f.attrs["Conventions"] == b"ODIM_H5/V2_3"
        assert f["what"].attrs["object"] == b"COMP"
        assert f["dataset1/data1/what"].attrs["quantity"] == b"VIL"
        assert f["dataset1/data1/data"].shape == (1200, 1100)


def test_a_hymecng_file_carries_the_classes_in_its_legend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the real HymecNG composite is a CLASS dataset whose legend names the 11 classes DWD's sheet lists."""
    h5py = pytest.importorskip("h5py")
    content = (FILES / "composite_HymecNG_20261020_1325_000-hd5").read_bytes()
    url = f"{RADAR}/composite/hymecng/composite_HymecNG_20261022_1305_000-hd5"
    _served(monkeypatch, {url: content})

    results = list(
        DwdRadarValues(parameter=DwdRadarParameter.HYMECNG_PRECIPITATION_TYPE, start="2026-10-22 13:07").query()
    )

    assert len(results) == 1
    assert results[0].timestamp == dt.datetime(2026, 10, 22, 13, 5, tzinfo=UTC)
    with h5py.File(results[0].data, mode="r") as f:
        assert f["dataset1/data1/what"].attrs["quantity"] == b"CLASS"
        legend = {key.decode(): int(value) for key, value in f["dataset1/data1/legend"][()]}
    assert legend == {
        "NO_PRECIPITATION": 0,
        "NOT_CLASSIFIED": 1,
        "DRIZZLE": 2,
        "RAIN": 3,
        "FREEZING_DRIZZLE": 4,
        "FREEZING_RAIN": 5,
        "SNOW_RAIN": 6,
        "SNOW": 7,
        "GRAUPEL": 8,
        "HAIL": 9,
        "LARGE_HAIL": 10,
    }


def test_a_yw_file_is_a_rate_in_odim_hdf5(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the real YW file, which the name calls `bin`, is ODIM HDF5 of the RATE, and is dated by its name."""
    h5py = pytest.importorskip("h5py")
    content = (FILES / "raa01-yw_10000-2610201300-dwd---bin.hdf5").read_bytes()
    url = f"{RADAR}/radolan/yw/raa01-yw_10000-2610221245-dwd---bin.hdf5"
    _served(monkeypatch, {url: content})

    results = list(DwdRadarValues(parameter=DwdRadarParameter.YW_REFLECTIVITY, start="2026-10-22 12:46").query())

    assert len(results) == 1
    assert results[0].timestamp == dt.datetime(2026, 10, 22, 12, 45, tzinfo=UTC)
    with h5py.File(results[0].data, mode="r") as f:
        assert f.attrs["Conventions"] == b"ODIM_H5/V2_3"
        assert f["dataset1/data1/what"].attrs["quantity"] == b"RATE"
        assert f["dataset1/what"].attrs["prodname"] == b"YW"
        assert f["dataset1/data1/data"].shape == (1200, 1100)


def test_a_sweep_of_the_volume_scan_is_the_unfiltered_differential_reflectivity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the real sweep of ZDR is read and verified as HDF5, and its quantity is UZDR."""
    h5py = pytest.importorskip("h5py")
    content = (FILES / "ras07-vol5minng01_sweeph5onem_uzdr_07-2026102123583500-boo-10132-hd5").read_bytes()
    base = f"{RADAR}/sites/sweep_vol_zdr/boo/unfiltered"
    _served(monkeypatch, {f"{base}/{name}": content for name in LISTINGS[base]})

    results = list(
        DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_VOL_ZDR, site=DwdRadarSite.BOO, start="2026-10-22 13:15"
        ).query()
    )

    # the sweep of the run at 13:15 is the one of 13:15:57, and the LATEST is not a dated file
    assert [result.timestamp for result in results] == [dt.datetime(2026, 10, 22, 13, 15, tzinfo=UTC)]
    with h5py.File(results[0].data, mode="r") as f:
        assert f["dataset1/data1/what"].attrs["quantity"] == b"UZDR"
        assert f["what"].attrs["object"] == b"SCAN"
        assert f["how"].attrs["task"] == b"Sc_Vol-5Min-NG-01_BOO"
        assert f["dataset1/data1/data"].shape == (360, 240)


def test_the_xml_of_konrad3d_and_the_mesocyclones_is_handed_over_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the real XML files are the bytes DWD wrote, parseable, with the cells and events they hold."""
    konrad = (FILES / "KONRAD3D_20261022T131000.xml").read_bytes()
    meso = (FILES / "meso_20261021_1630.xml").read_bytes()
    urls = {
        f"{RADAR}/konrad3d/KONRAD3D_20261022T131000.xml": konrad,
        f"{RADAR}/mesocyclones/meso_20261022_1310.xml": meso,
    }
    downloaded = _served(monkeypatch, urls)

    cells = list(
        DwdRadarValues(parameter=DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS, start="2026-10-22 13:10").query()
    )
    events = list(DwdRadarValues(parameter=DwdRadarParameter.MESOCYCLONE_DETECTION, start="2026-10-22 13:10").query())

    assert [url for url, _ in downloaded] == list(urls)
    assert [result.timestamp for result in cells + events] == [dt.datetime(2026, 10, 22, 13, 10, tzinfo=UTC)] * 2
    assert cells[0].data.getvalue() == konrad
    assert events[0].data.getvalue() == meso
    root = ET.fromstring(cells[0].data.getvalue())  # noqa: S314
    assert root.tag == "konrad3d"
    assert root.attrib["data_model_name"] == "KONRAD3D"
    assert root.find("head/metadata/reference_time").text == "2026-10-22T13:10:00Z"
    assert root.findall("cells/feature")
    nowcast = ET.fromstring(events[0].data.getvalue())  # noqa: S314
    assert nowcast.tag == "nowcast-data"
    assert nowcast.find("radar-stations").text.split(",")[:2] == ["ASB", "BOO"]
    assert nowcast.find("event/nowcast-parameters/mesocyclone_shear_max").attrib == {"units": "m/s/km"}


def test_the_xml_of_a_run_without_a_cell_or_an_event_is_still_a_file() -> None:
    """Test that the real files of a quiet run are small documents of no cell and no event: an answer, not an error."""
    meso = ET.fromstring((FILES / "meso_20261020_1325.xml").read_bytes())  # noqa: S314
    assert meso.findall("event") == []
    assert meso.find("radar-stations") is not None


def test_every_product_that_is_no_radolan_one_names_the_format_it_is_served_in() -> None:
    """Test that a product is a row of `RADAR_DATA_FORMATS` unless it is RADOLAN, and every sweep has its folders."""
    for parameter in DwdRadarParameter:
        if parameter in RADAR_PARAMETERS_RADOLAN or parameter == DwdRadarParameter.RADOLAN_CDC:
            assert parameter not in RADAR_DATA_FORMATS
        else:
            assert parameter in RADAR_DATA_FORMATS, parameter
    assert set(RADAR_DATA_SUBSETS) == set(RADAR_PARAMETERS_SWEEPS)


# ---- the live source: the products are read as DWD publishes them (remote) ------------------------------------------


def _yesterday() -> dt.datetime:
    """Give the time of a day ago, which DWD, keeping about two days, still holds."""
    return dt.datetime.now(UTC).replace(tzinfo=None) - dt.timedelta(days=1)


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "shape", "quantity"),
    [
        (DwdRadarParameter.HX_REFLECTIVITY, (4800, 4400), b"DBZH"),
        (DwdRadarParameter.DMAX_REFLECTIVITY, (4800, 4400), b"DBZH"),
        (DwdRadarParameter.VII_INTEGRATED_ICE, (1200, 1100), b"VIL"),
        (DwdRadarParameter.HYMECNG_PRECIPITATION_TYPE, (1200, 1100), b"CLASS"),
    ],
)
def test_radar_request_composite_files_latest(
    parameter: DwdRadarParameter, shape: tuple[int, int], quantity: bytes, default_settings: Settings
) -> None:
    """Test radar COMPOSITES that are one ODIM HDF5 file a run: the latest one, the quantity DWD's sheet names."""
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    results = list(DwdRadarValues(parameter=parameter, start=DwdRadarDate.LATEST, settings=default_settings).query())

    assert len(results) == 1
    assert "latest" in results[0].url.lower()
    with h5py.File(results[0].data, mode="r") as f:
        assert f.attrs["Conventions"] == b"ODIM_H5/V2_3"
        assert f["what"].attrs["object"] == b"COMP"
        assert f["dataset1/data1/what"].attrs["quantity"] == quantity
        assert f["dataset1/data1/data"].shape == shape


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [
        DwdRadarParameter.HX_REFLECTIVITY,
        DwdRadarParameter.DMAX_REFLECTIVITY,
        DwdRadarParameter.VII_INTEGRATED_ICE,
        DwdRadarParameter.HYMECNG_PRECIPITATION_TYPE,
    ],
)
def test_radar_request_composite_files_timerange(parameter: DwdRadarParameter, default_settings: Settings) -> None:
    """Test radar COMPOSITES that are one file a run for a timerange: a file for each run, dated to it."""
    request = DwdRadarValues(
        parameter=parameter, start=_yesterday(), end=dt.timedelta(minutes=10), settings=default_settings
    )

    results = list(request.query())

    # two runs, of which DWD may drop one
    assert 1 <= len(results) <= 2
    assert {result.timestamp for result in results} <= {request.start, request.start + dt.timedelta(minutes=5)}
    assert all(result.data.getvalue().startswith(b"\x89HDF") for result in results)


@pytest.mark.remote
def test_radar_request_composite_rs(default_settings: Settings) -> None:
    """Test radar COMPOSITE RS: the .tar of a run holds the analysis and the 24 forecasts of the hourly sums."""
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.RS_PRECIPITATION_SUM,
        start=_yesterday(),
        end=dt.timedelta(minutes=5),
        settings=default_settings,
    )
    results = list(request.query())

    assert len(results) == 25
    assert [result.filename.split("_")[-1] for result in results] == [f"{lead:03d}-hd5" for lead in range(0, 125, 5)]
    assert {result.timestamp for result in results} == {request.start}
    with h5py.File(results[0].data, mode="r") as f:
        assert f["dataset1/data1/what"].attrs["quantity"] == b"ACRR"
        assert f["dataset1/data1/data"].shape == (1200, 1100)
        # the hour that ends at the run
        what = f["dataset1/what"].attrs
        assert what["prodname"] == b"RS_top_view"
        start = dt.datetime.strptime((what["startdate"] + what["starttime"]).decode() + "+0000", "%Y%m%d%H%M%S%z")
        end = dt.datetime.strptime((what["enddate"] + what["endtime"]).decode() + "+0000", "%Y%m%d%H%M%S%z")
        assert end - start == dt.timedelta(hours=1)

    latest = list(
        DwdRadarValues(
            parameter=DwdRadarParameter.RS_PRECIPITATION_SUM, start=DwdRadarDate.LATEST, settings=default_settings
        ).query()
    )
    assert [result.filename.split("_")[-1] for result in latest] == ["000-hd5"]


@pytest.mark.remote
def test_radar_request_radolan_yw(default_settings: Settings) -> None:
    """Test RADOLAN YW, the quasi-calibrated 5 minute rate, as ODIM HDF5 (it is published 35 to 40 minutes late)."""
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(
        parameter=DwdRadarParameter.YW_REFLECTIVITY,
        start=_yesterday(),
        end=dt.timedelta(minutes=10),
        settings=default_settings,
    )
    results = list(request.query())

    assert len(results) == 2
    assert {result.timestamp for result in results} == {request.start, request.start + dt.timedelta(minutes=5)}
    with h5py.File(results[0].data, mode="r") as f:
        assert f.attrs["Conventions"] == b"ODIM_H5/V2_3"
        assert f["dataset1/data1/what"].attrs["quantity"] == b"RATE"
        assert f["dataset1/what"].attrs["prodname"] == b"YW"
        assert f["dataset1/data1/data"].shape == (1200, 1100)

    latest = list(
        DwdRadarValues(
            parameter=DwdRadarParameter.YW_REFLECTIVITY, start=DwdRadarDate.LATEST, settings=default_settings
        ).query()
    )
    assert len(latest) == 1
    assert latest[0].data.getvalue().startswith(b"\x89HDF")


@pytest.mark.remote
def test_radar_request_konrad3d(default_settings: Settings) -> None:
    """Test KONRAD3D: one XML file a run, with the head of the run and the detected cells."""
    request = DwdRadarValues(
        parameter=DwdRadarParameter.KONRAD3D_CONVECTIVE_CELLS,
        start=_yesterday(),
        end=dt.timedelta(minutes=10),
        settings=default_settings,
    )
    results = list(request.query())

    assert len(results) == 2
    assert {result.timestamp for result in results} == {request.start, request.start + dt.timedelta(minutes=5)}
    for result in results:
        root = ET.fromstring(result.data.getvalue())  # noqa: S314
        assert root.tag == "konrad3d"
        assert root.attrib["data_model_name"] == "KONRAD3D"
        assert root.find("cells") is not None
        # the reference time of the file is the run named in its name
        reference = dt.datetime.fromisoformat(root.find("head/metadata/reference_time").text)
        assert reference == result.timestamp


@pytest.mark.remote
def test_radar_request_mesocyclones(default_settings: Settings) -> None:
    """Test the mesocyclone detection: one XML file a run, which holds an event only where one was detected."""
    request = DwdRadarValues(
        parameter=DwdRadarParameter.MESOCYCLONE_DETECTION,
        start=_yesterday(),
        end=dt.timedelta(minutes=10),
        settings=default_settings,
    )
    results = list(request.query())

    assert len(results) == 2
    assert {result.timestamp for result in results} == {request.start, request.start + dt.timedelta(minutes=5)}
    for result in results:
        root = ET.fromstring(result.data.getvalue())  # noqa: S314
        assert root.tag == "nowcast-data"
        assert root.find("radar-stations") is not None

    latest = list(
        DwdRadarValues(
            parameter=DwdRadarParameter.MESOCYCLONE_DETECTION, start=DwdRadarDate.LATEST, settings=default_settings
        ).query()
    )
    assert len(latest) == 1
    assert ET.fromstring(latest[0].data.getvalue()).tag == "nowcast-data"  # noqa: S314


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "quantity"),
    [
        (DwdRadarParameter.SWEEP_VOL_ZDR, b"UZDR"),
        (DwdRadarParameter.SWEEP_VOL_RHOHV, b"URHOHV"),
        (DwdRadarParameter.SWEEP_VOL_PHIDP, b"UPHIDP"),
    ],
)
def test_radar_request_site_sweep_vol_polarimetric(
    parameter: DwdRadarParameter, quantity: bytes, default_settings: Settings
) -> None:
    """Test the unfiltered polarimetric moments of the volume scan: the ten sweeps of a run, one by `elevation`."""
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(parameter=parameter, site=DwdRadarSite.BOO, start=_yesterday(), settings=default_settings)
    results = list(request.query())

    assert len(results) == 10
    with h5py.File(results[0].data, mode="r") as f:
        assert f["dataset1/data1/what"].attrs["quantity"] == quantity
        assert f["what"].attrs["object"] == b"SCAN"
        assert f["how"].attrs["task"] == b"Sc_Vol-5Min-NG-01_BOO"
        assert f["how"].attrs["scan_count"] == 10
        assert f["dataset1/how"].attrs["scan_index"] == 1

    single = list(
        DwdRadarValues(
            parameter=parameter, site=DwdRadarSite.BOO, start=request.start, elevation=9, settings=default_settings
        ).query()
    )
    assert len(single) == 1
    with h5py.File(single[0].data, mode="r") as f:
        assert f["dataset1/how"].attrs["scan_index"] == 10


@pytest.mark.remote
@pytest.mark.parametrize(
    ("parameter", "quantity"),
    [
        (DwdRadarParameter.SWEEP_PCP_ZDR, b"UZDR"),
        (DwdRadarParameter.SWEEP_PCP_RHOHV, b"URHOHV"),
        (DwdRadarParameter.SWEEP_PCP_PHIDP, b"UPHIDP"),
    ],
)
def test_radar_request_site_sweep_pcp_polarimetric(
    parameter: DwdRadarParameter, quantity: bytes, default_settings: Settings
) -> None:
    """Test the unfiltered polarimetric moments of the precipitation scan: the one sweep of a run."""
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    request = DwdRadarValues(parameter=parameter, site=DwdRadarSite.BOO, start=_yesterday(), settings=default_settings)
    results = list(request.query())

    assert len(results) == 1
    with h5py.File(results[0].data, mode="r") as f:
        assert f["dataset1/data1/what"].attrs["quantity"] == quantity
        assert f["how"].attrs["task"] == b"Sc_Pcp-NG-01_BOO"
        assert f["how"].attrs["scan_count"] == 1
        assert f["dataset1/how"].attrs["scan_index"] == 1


@pytest.mark.remote
def test_radar_request_site_sweep_pcp_polarimetric_latest(default_settings: Settings) -> None:
    """Test that LATEST of a polarimetric sweep of the precipitation scan is the one file DWD names so."""
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    results = list(
        DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_PCP_RHOHV,
            site=DwdRadarSite.BOO,
            start=DwdRadarDate.LATEST,
            settings=default_settings,
        ).query()
    )

    assert len(results) == 1
    assert results[0].url.endswith("_urhohv_00-LATEST-boo-10132-hd5")
    with h5py.File(results[0].data, mode="r") as f:
        assert f["dataset1/data1/what"].attrs["quantity"] == b"URHOHV"
