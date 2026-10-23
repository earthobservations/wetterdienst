# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the layout of opendata.dwd.de/weather/radar as DWD publishes it (GH-3279).

The listings are lines of the real ones, read on 2026-10-22: the composites are ODIM HDF5, packed in a .tar a run;
the site products but the DX are ODIM HDF5 files; no product is published as BUFR any more; composite/hg,
composite/pg, sites/pf, radvor/re and radvor/rq hold no file, and sites/px only stale files of one site.
"""

import datetime as dt
import logging
import sys
import tarfile
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import InvalidEnumerationError, RequestError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.radar import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarDate,
    DwdRadarParameter,
    DwdRadarValues,
)
from wetterdienst.provider.dwd.radar import api as radar_api
from wetterdienst.provider.dwd.radar.index import build_path_to_parameter, create_fileindex_radar
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite
from wetterdienst.provider.dwd.radar.util import RADAR_DT_PATTERN, get_date_string_from_filename
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")
RADAR = "https://opendata.dwd.de/weather/radar"
_PCP = "ras07-pcpng01_sweeph5onem"

# lines of the listings of 2026-10-22 ~11:35 UTC
LISTINGS = {
    f"{RADAR}/composite/rv": [
        "composite_rv_20261022_1120.tar",
        "composite_rv_20261022_1125.tar",
        "composite_rv_20261022_1130.tar",
        "composite_rv_LATEST.tar",
    ],
    f"{RADAR}/composite/wn": [
        "composite_wn_20261022_1125.tar",
        "composite_wn_20261022_1130.tar",
        "composite_wn__LATEST.tar",
    ],
    f"{RADAR}/radolan/rw": [
        "raa01-rw_10000-2610221120-dwd---bin.hdf5",
        "raa01-rw_10000-2610221130-dwd---bin.hdf5",
        "raa01-rw_10000-latest-dwd---bin.hdf5",
    ],
    f"{RADAR}/sites/pe/boo": [
        "rab02-pe_10132-20261022112500-deboo-hd5",
        "rab02-pe_10132-20261022113000-deboo-hd5",
        "rab02-pe_10132-latest-deboo-hd5",
    ],
    f"{RADAR}/sites/px250/boo": [
        "rab02-tt_10132-20261022113000-deboo-hd5",
        "rab02-tt_10132-20261022113500-deboo-hd5",
        "rab02-tt_10132-latest-deboo-hd5",
    ],
    f"{RADAR}/sites/dx/boo": [
        "raa00-dx_10132-2610221130-boo---bin",
        "raa00-dx_10132-2610221135-boo---bin",
        "raa00-dx_10132-latest-boo---bin",
    ],
    f"{RADAR}/sites/sweep_vol_v/boo/hdf5/filter_simple": [
        "ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2026102211305700-boo-10132-hd5",
        "ras07-stqual-vol5minng01_sweeph5onem_vradh_09-2026102211290200-boo-10132-hd5",
    ],
}


@pytest.fixture(autouse=True)
def listings(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve the listings above, as the urls the listing of the server answers, and take down what is asked."""
    asked: list[str] = []

    def list_remote_files(url: str, settings: Settings, cache_expiry: CacheExpiry) -> list[str]:  # noqa: ARG001
        asked.append(url)
        return [f"{url.rstrip('/')}/{name}" for name in LISTINGS.get(url.rstrip("/"), [])]

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.index.list_remote_files_fsspec", list_remote_files)
    return asked


def _names(df: pl.DataFrame) -> list[str]:
    return [url.rsplit("/", 1)[1] for url in df.get_column("filename").to_list()]


@pytest.mark.parametrize(
    ("parameter", "folder"),
    [(DwdRadarParameter.RV_REFLECTIVITY, "rv"), (DwdRadarParameter.WN_REFLECTIVITY, "wn")],
)
def test_composite_index_lists_the_tars_and_dates_them(parameter: DwdRadarParameter, folder: str) -> None:
    """Test that a composite is one .tar a run, dated by its name, and the LATEST one is listed but not dated."""
    listed = create_fileindex_radar(parameter=parameter, settings=Settings())
    assert listed.height == len(LISTINGS[f"{RADAR}/composite/{folder}"])
    assert all(url.startswith(f"{RADAR}/composite/{folder}/composite_{folder}_") for url in listed["filename"])
    assert any("LATEST" in url for url in listed["filename"])

    dated = create_fileindex_radar(parameter=parameter, settings=Settings(), parse_datetime=True)
    assert dated.get_column("datetime").to_list() == [
        dt.datetime(2026, 10, 22, 11, minute, tzinfo=UTC) for minute in ([20, 25, 30] if folder == "rv" else [25, 30])
    ]


def test_composite_index_takes_nothing_but_the_tars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a file that is no .tar, such as the .bz2 of the layout before, is not a run."""
    monkeypatch.setitem(
        LISTINGS, f"{RADAR}/composite/rv", ["composite_rv_20261022_1130.tar", "FX2610221130.tar.bz2", "README.txt"]
    )
    listed = create_fileindex_radar(parameter=DwdRadarParameter.RV_REFLECTIVITY, settings=Settings())
    assert _names(listed) == ["composite_rv_20261022_1130.tar"]


@pytest.mark.parametrize(
    ("parameter", "folder", "newest"),
    [
        (DwdRadarParameter.PE_ECHO_TOP, "pe", dt.datetime(2026, 10, 22, 11, 30, tzinfo=UTC)),
        (DwdRadarParameter.PX250_REFLECTIVITY, "px250", dt.datetime(2026, 10, 22, 11, 35, tzinfo=UTC)),
    ],
)
def test_site_hdf5_index_is_the_folder_of_the_site(
    parameter: DwdRadarParameter, folder: str, newest: dt.datetime
) -> None:
    """Test that the HDF5 site products are the files of the site's folder, dated with four digits of the year."""
    listed = create_fileindex_radar(
        parameter=parameter,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        settings=Settings(),
        parse_datetime=True,
    )
    # the latest file is no dated one
    assert listed.height == 2
    assert all(f"/sites/{folder}/boo/" in url for url in listed["filename"])
    assert listed.get_column("datetime").to_list()[-1] == newest


def test_site_hdf5_index_names_its_format_for_itself() -> None:
    """Test that the format of a product served in one is no argument: left out, it is the one it is served in."""
    named = create_fileindex_radar(
        parameter=DwdRadarParameter.PE_ECHO_TOP, site=DwdRadarSite.BOO, fmt=DwdRadarDataFormat.HDF5, settings=Settings()
    )
    left_out = create_fileindex_radar(
        parameter=DwdRadarParameter.PE_ECHO_TOP, site=DwdRadarSite.BOO, settings=Settings()
    )
    assert named.equals(left_out)
    assert left_out.height == 3


def test_dx_is_the_binary_file_and_is_dated_with_two_digits_of_the_year() -> None:
    """Test that the DX, which is no HDF5, is still the binary file."""
    listed = create_fileindex_radar(
        parameter=DwdRadarParameter.DX_REFLECTIVITY, site=DwdRadarSite.BOO, settings=Settings(), parse_datetime=True
    )
    assert listed.get_column("datetime").to_list() == [
        dt.datetime(2026, 10, 22, 11, 30, tzinfo=UTC),
        dt.datetime(2026, 10, 22, 11, 35, tzinfo=UTC),
    ]


def test_sweep_index_is_the_folder_of_the_filter() -> None:
    """Test that the sweeps are still the HDF5 files in the folder of their filter."""
    listed = create_fileindex_radar(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        site=DwdRadarSite.BOO,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=Settings(),
        parse_datetime=True,
    )
    assert listed.height == 2
    assert all("/sites/sweep_vol_v/boo/hdf5/filter_simple/" in url for url in listed["filename"])
    assert listed.get_column("datetime").to_list()[0] == dt.datetime(2026, 10, 22, 11, 30, tzinfo=UTC)


def test_sweep_without_its_filter_is_refused() -> None:
    """Test that the sweeps are asked for their filter, which is the only choice left for them."""
    with pytest.raises(ValueError, match="Argument 'subset' is missing"):
        build_path_to_parameter(parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H, site=DwdRadarSite.BOO)


@pytest.mark.parametrize(
    ("parameter", "fmt"),
    [
        (DwdRadarParameter.PE_ECHO_TOP, DwdRadarDataFormat.BINARY),
        (DwdRadarParameter.PX250_REFLECTIVITY, DwdRadarDataFormat.BINARY),
        (DwdRadarParameter.DX_REFLECTIVITY, DwdRadarDataFormat.HDF5),
        (DwdRadarParameter.SWEEP_VOL_VELOCITY_H, DwdRadarDataFormat.BINARY),
    ],
)
def test_a_format_the_product_is_not_published_in_is_refused(
    parameter: DwdRadarParameter, fmt: DwdRadarDataFormat, listings: list[str]
) -> None:
    """Test that it is said, not answered with an empty listing, that a product has no file in that format."""
    with pytest.raises(RequestError, match=f"{parameter.name} is published as .* only, not as {fmt.name}"):
        DwdRadarValues(parameter=parameter, site=DwdRadarSite.BOO, fmt=fmt, start="2026-10-22 11:30")
    with pytest.raises(RequestError, match="only, not as"):
        create_fileindex_radar(parameter=parameter, site=DwdRadarSite.BOO, fmt=fmt, settings=Settings())
    # nothing was listed
    assert listings == []


def test_the_composites_are_hdf5() -> None:
    """Test that the format of a composite is HDF5, named or not, and nothing else."""
    assert DwdRadarValues(parameter="rv_reflectivity", start="2026-10-22 11:30").format == DwdRadarDataFormat.HDF5
    assert DwdRadarValues(parameter="wn", fmt="hdf5", start="2026-10-22 11:30").format == DwdRadarDataFormat.HDF5
    with pytest.raises(RequestError, match=r"RV_REFLECTIVITY is published as HDF5 .* only, not as BINARY"):
        DwdRadarValues(parameter="rv", fmt="binary", start="2026-10-22 11:30")


@pytest.mark.parametrize(
    "value", ["hg", "HG_REFLECTIVITY", "pg", "pg_reflectivity", "px", "pf", "re", "RQ_REFLECTIVITY"]
)
def test_a_product_dwd_stopped_publishing_is_refused_with_the_reason(value: str) -> None:
    """Test that HG, PG, PX, PF, RE and RQ, of which DWD publishes no file, say so and are no parameters."""
    with pytest.raises(InvalidEnumerationError, match=r"is not published any more: opendata\.dwd\.de/weather/radar/"):
        DwdRadarValues(parameter=value, start="2026-10-22 11:30")
    assert not any(
        name.startswith(("HG_", "PG_", "PX_", "PF_", "RE_", "RQ_")) for name in DwdRadarParameter.__members__
    )


def test_the_latest_of_a_site_hdf5_product_is_the_file_named_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that PE has a latest file, which is the one read, and that the sweeps have none."""
    downloaded: list[str] = []

    def download_file(url: str, **_: object) -> File:
        downloaded.append(url)
        return File(url=url, content=BytesIO(b"\x89HDF"), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.api.download_file", download_file)

    results = list(
        DwdRadarValues(
            parameter=DwdRadarParameter.PE_ECHO_TOP, site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST
        ).query()
    )

    assert downloaded == [f"{RADAR}/sites/pe/boo/rab02-pe_10132-latest-deboo-hd5"]
    assert len(results) == 1
    with pytest.raises(ValueError, match="HDF5 sweep data has no '-latest-' files"):
        DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H, site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST
        )


@pytest.mark.parametrize("fmt", [None, DwdRadarDataFormat.BINARY, DwdRadarDataFormat.HDF5])
def test_radolan_is_listed_as_before_whatever_format_it_is_asked_in(fmt: DwdRadarDataFormat | None) -> None:
    """Test that the RADOLAN files, which are named bin and are HDF5, are not filtered as the HDF5 products are."""
    listed = create_fileindex_radar(
        parameter=DwdRadarParameter.RW_REFLECTIVITY, fmt=fmt, settings=Settings(), parse_datetime=True
    )
    assert listed.get_column("datetime").to_list() == [
        dt.datetime(2026, 10, 22, 11, 20, tzinfo=UTC),
        dt.datetime(2026, 10, 22, 11, 30, tzinfo=UTC),
    ]


@pytest.mark.parametrize("fmt", ["bufr", "BUFR"])
def test_bufr_is_refused_with_the_reason_and_is_no_format_any_more(fmt: str) -> None:
    """Test that DWD publishes no radar product as BUFR: the format and its reader are gone, and a request says why."""
    with pytest.raises(InvalidEnumerationError, match=r"not offered any more: DWD no longer publishes any radar"):
        DwdRadarValues(parameter=DwdRadarParameter.PE_ECHO_TOP, site=DwdRadarSite.BOO, fmt=fmt, start="2026-10-22")
    assert "BUFR" not in DwdRadarDataFormat.__members__


def test_the_radar_bufr_reader_and_its_setting_are_gone() -> None:
    """Test that nothing of the radar BUFR path is left: the reader, the hook, the frame of a result and the setting."""
    assert not hasattr(radar_api, "read_radar_bufr")
    assert not hasattr(DwdRadarValues, "_attach_bufr")
    assert "df" not in radar_api.RadarResult.__dataclass_fields__
    with pytest.raises(ValueError, match="read_bufr is no setting any more: DWD publishes no radar product as BUFR"):
        Settings(read_bufr=True)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("composite_rv_20261022_1130.tar", "202610221130"),
        ("composite_rv_20261022_1130_005-hd5", "202610221130"),
        ("https://opendata.dwd.de/weather/radar/composite/wn/composite_wn_20261022_1135_120-hd5", "202610221135"),
        ("rab02-pe_10132-20261022113000-deboo-hd5", "202610221130"),
        ("raa00-dx_10132-2610221130-boo---bin", "2610221130"),
        ("composite_rv_LATEST.tar", None),
        ("composite_wn__LATEST.tar", None),
        # GH-3283
        ("composite_HymecNG_20261022_1305_000-hd5", "202610221305"),
        ("composite_VII_latest-hd5", None),
        ("KONRAD3D_20261022T130500.xml", "202610221305"),
        ("meso_20261022_1305.xml", "202610221305"),
        ("meso_latest.xml", None),
        ("raa01-yw_10000-2610221245-dwd---bin.hdf5", "2610221245"),
        ("ras07-vol5minng01_sweeph5onem_uzdr_09-2026102213140200-boo-10132-hd5", "202610221314"),
        ("ras07-vol5minng01_sweeph5onem_uzdr_09-LATEST-boo-10132-hd5", None),
    ],
)
def test_the_date_of_a_file_is_its_digits(name: str, expected: str | None) -> None:
    """Test that the date and the time of a composite, split by an underscore, are the digits of the others."""
    assert get_date_string_from_filename(name, RADAR_DT_PATTERN) == expected


@pytest.mark.parametrize(
    ("url", "cached"),
    [
        (f"{RADAR}/composite/rv/composite_rv_LATEST.tar", False),
        (f"{RADAR}/composite/wn/composite_wn__LATEST.tar", False),
        (f"{RADAR}/sites/pe/boo/rab02-pe_10132-latest-deboo-hd5", False),
        (f"{RADAR}/sites/dx/boo/raa00-dx_10132-latest-boo---bin", False),
        (f"{RADAR}/composite/rv/composite_rv_20261022_1130.tar", True),
    ],
)
def test_a_latest_file_is_never_cached(url: str, cached: bool) -> None:  # noqa: FBT001
    """Test that the files that change under their name are asked for again, which the LATEST of a composite did not."""
    assert DwdRadarValues._should_cache_download(url) is cached  # noqa: SLF001


def _member(lead: int) -> bytes:
    """Give an HDF5 file shaped as the composites are: ODIM_H5/V2_3, one dataset of 2 x 2 counts."""
    h5py = pytest.importorskip("h5py")
    buffer = BytesIO()
    with h5py.File(buffer, "w") as f:
        f.attrs["Conventions"] = b"ODIM_H5/V2_3"
        what = f.create_group("what")
        what.attrs.update({"object": "COMP", "version": "H5rad 2.3", "date": "20261022", "time": "113000"})
        f.create_group("dataset1/data1").create_dataset("data", data=[[lead, 1], [2, 3]])
    return buffer.getvalue()


def _tar(run: str, leads: tuple[int, ...]) -> bytes:
    """Give a tar as DWD packs a run: a file `composite_rv_<run>_<lead>-hd5` for every lead time."""
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for lead in leads:
            data = _member(lead)
            info = tarfile.TarInfo(f"composite_rv_{run}_{lead:03d}-hd5")
            info.size = len(data)
            tar.addfile(info, BytesIO(data))
    return buffer.getvalue()


def test_the_tar_of_a_run_is_read_as_one_file_for_every_lead_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a request reads the .tar, hands over every file in it dated to the run, and verifies them as HDF5."""
    pytest.importorskip("h5py")
    runs = {
        f"{RADAR}/composite/rv/composite_rv_20261022_1125.tar": _tar("20261022_1125", (0, 5, 10)),
        f"{RADAR}/composite/rv/composite_rv_20261022_1130.tar": _tar("20261022_1130", (0, 5, 10)),
    }
    downloaded: list[tuple[str, CacheExpiry]] = []

    def download_file(url: str, ttl: CacheExpiry, **_: object) -> File:
        downloaded.append((url, ttl))
        return File(url=url, content=BytesIO(runs[url]), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.api.download_file", download_file)

    results = list(
        DwdRadarValues(
            parameter=DwdRadarParameter.RV_REFLECTIVITY, start="2026-10-22 11:28", end=dt.timedelta(minutes=5)
        ).query()
    )

    # 11:28 is aligned to 11:25, the window is until 11:29:59: one run
    assert [url for url, _ in downloaded] == [f"{RADAR}/composite/rv/composite_rv_20261022_1125.tar"]
    assert [result.filename for result in results] == [
        f"composite_rv_20261022_1125_{lead:03d}-hd5" for lead in (0, 5, 10)
    ]
    assert {result.timestamp for result in results} == {dt.datetime(2026, 10, 22, 11, 25, tzinfo=UTC)}
    assert {result.url for result in results} == {f"{RADAR}/composite/rv/composite_rv_20261022_1125.tar"}
    assert all(result.data.getvalue().startswith(b"\x89HDF") for result in results)


def test_the_latest_composite_is_read_from_its_tar_and_asked_for_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that LATEST reads composite_rv_LATEST.tar, which is not served from the cache for 5 minutes."""
    pytest.importorskip("h5py")
    url = f"{RADAR}/composite/rv/composite_rv_LATEST.tar"
    downloaded: list[tuple[str, CacheExpiry]] = []

    def download_file(url: str, ttl: CacheExpiry, **_: object) -> File:
        downloaded.append((url, ttl))
        return File(url=url, content=BytesIO(_tar("20261022_1130", (0, 5))), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.api.download_file", download_file)

    results = list(DwdRadarValues(parameter=DwdRadarParameter.RV_REFLECTIVITY, start=DwdRadarDate.LATEST).query())

    assert downloaded == [(url, CacheExpiry.NO_CACHE)]
    # the first file of the tar is the analysis, which is what LATEST has always answered
    assert [result.filename for result in results] == ["composite_rv_20261022_1130_000-hd5"]
    assert results[0].timestamp == dt.datetime(2026, 10, 22, 11, 30, tzinfo=UTC)


def _odim(date: str, time: str) -> bytes:
    """Give an ODIM HDF5 file of a site product, with the date and the time its `/what` group says the scan is of."""
    h5py = pytest.importorskip("h5py")
    buffer = BytesIO()
    with h5py.File(buffer, "w") as f:
        f.attrs["Conventions"] = b"ODIM_H5/V2_1"
        what = f.create_group("what")
        what.attrs.update({"object": "PVOL", "version": "H5rad 2.1", "date": date.encode(), "time": time.encode()})
    return buffer.getvalue()


# the first bytes of the file `raa00-dx_10132-latest-boo---bin` of 2026-10-22 21:15 UTC (DDHHMM 222110, MMYY 1026)
DX_HEADER = b"DX222110101321026BY31755VS 2CO0CD4CS0EP0.80.80.80.80.80.80.80.8MS  0\x03\x03\x00 \x00\x00\x08\x00"


def _serve(monkeypatch: pytest.MonkeyPatch, content: bytes) -> None:
    """Serve the same content for any file asked for."""

    def download_file(url: str, **_: object) -> File:
        return File(url=url, content=BytesIO(content), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.api.download_file", download_file)


def test_the_latest_of_a_site_hdf5_product_is_dated_by_the_scan_time_in_the_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the latest file of PE, whose name has no time, is dated by `/what` `date` and `time` (GH-3299)."""
    _serve(monkeypatch, _odim("20261022", "211000"))

    (result,) = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP, site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST
    ).query()

    assert result.timestamp == dt.datetime(2026, 10, 22, 21, 10, tzinfo=UTC)
    # the file is handed over whole, from its start, as it was without the reading
    assert result.data.tell() == 0
    assert result.data.getvalue() == _odim("20261022", "211000")


def test_the_latest_of_dx_is_dated_by_its_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the binary DX file, which h5py cannot read, says its time in its header: DDHHMM, the site, MMYY."""
    _serve(monkeypatch, DX_HEADER)

    (result,) = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY, site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST
    ).query()

    assert result.timestamp == dt.datetime(2026, 10, 22, 21, 10, tzinfo=UTC)
    assert result.data.getvalue() == DX_HEADER


def test_the_latest_of_dx_is_dated_without_h5py(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that the DX header needs no h5py, and that no warning about it is made."""
    monkeypatch.setitem(sys.modules, "h5py", None)
    _serve(monkeypatch, DX_HEADER)

    with caplog.at_level(logging.WARNING):
        (result,) = DwdRadarValues(
            parameter=DwdRadarParameter.DX_REFLECTIVITY, site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST
        ).query()

    assert result.timestamp == dt.datetime(2026, 10, 22, 21, 10, tzinfo=UTC)
    assert "h5py" not in caplog.text


def test_the_latest_hdf5_is_undated_without_h5py_and_says_so_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that without h5py (the `radar` extra) the timestamps are None as before, with one warning per request."""
    monkeypatch.setitem(sys.modules, "h5py", None)
    content = b"\x89HDF\r\n\x1a\n" + bytes(64)
    _serve(monkeypatch, content)
    monkeypatch.setitem(
        LISTINGS,
        f"{RADAR}/sites/sweep_pcp_z/boo/unfiltered",
        [f"{_PCP}_{q}_00-LATEST-boo-10132-hd5" for q in ("th", "tv")],
    )

    with caplog.at_level(logging.WARNING):
        results = list(
            DwdRadarValues(
                parameter=DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
                site=DwdRadarSite.BOO,
                subset=DwdRadarDataSubset.UNFILTERED,
                start=DwdRadarDate.LATEST,
            ).query()
        )

    # TH and TV: two files, one warning
    assert [result.timestamp for result in results] == [None, None]
    assert all(result.data.getvalue() == content for result in results)
    records = [record for record in caplog.records if "h5py" in record.getMessage()]
    assert len(records) == 1
    assert "pip install wetterdienst[radar]" in records[0].getMessage()
    assert "without a timestamp" in records[0].getMessage()


@pytest.mark.parametrize("content", [b"\x89HDF", b"\x89HDF\r\n\x1a\n" + bytes(64), b"", b"<nowcast-data/>"])
def test_the_latest_file_that_says_no_time_is_undated_and_is_no_error(
    content: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a truncated file, an empty one, and one with no time in it (an XML) answer None, not an exception."""
    pytest.importorskip("h5py")
    _serve(monkeypatch, content)

    (result,) = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP, site=DwdRadarSite.BOO, start=DwdRadarDate.LATEST
    ).query()

    assert result.timestamp is None
    assert result.data.getvalue() == content


def test_a_file_dated_by_its_name_keeps_the_time_of_its_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that only a file with no time in its name is dated by its content: the name is what a window selects by."""
    # the file says 11:10, the name and the slot asked for 11:30: the timestamp stays the slot's
    _serve(monkeypatch, _odim("20261022", "111000"))

    (result,) = DwdRadarValues(
        parameter=DwdRadarParameter.PE_ECHO_TOP, site=DwdRadarSite.BOO, start="2026-10-22 11:30"
    ).query()

    assert result.timestamp == dt.datetime(2026, 10, 22, 11, 30, tzinfo=UTC)
