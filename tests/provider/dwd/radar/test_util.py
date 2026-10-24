# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for radar utilities."""

import datetime as dt
import sys
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.exceptions import MissingDependencyError
from wetterdienst.provider.dwd.radar.util import (
    RADAR_DT_PATTERN,
    get_date_string_from_filename,
    read_scan_time,
    verify_hdf5,
)

HDF5_EXAMPLE = Path(__file__).parent / "files" / "ras07-vol5minng01_sweeph5onem_uzdr_07-2026102123583500-boo-10132-hd5"


def test_radar_get_date_from_filename() -> None:
    """Test date extraction from radar filename."""
    date = get_date_string_from_filename(
        "sweep_pcp_v_0-20200926143033_10132--buf.bz2",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "202009261430"

    date = get_date_string_from_filename(
        "ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "202009261430"

    date = get_date_string_from_filename(
        "ras07-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "202009261430"

    date = get_date_string_from_filename(
        "rab02-tt_10132-20200926161533-boo---buf",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "202009261615"

    date = get_date_string_from_filename(
        "rab02-tt_10132-2301010000-boo---buf",
        pattern=RADAR_DT_PATTERN,
    )
    assert date == "2301010000"


def test_radar_verify_hdf5_valid() -> None:
    """Test valid HDF5 file, a committed sweep of the site 10132, read from disk (GH-3370)."""
    pytest.importorskip("h5py", reason="h5py not installed")

    verify_hdf5(BytesIO(HDF5_EXAMPLE.read_bytes()))


def test_radar_verify_hdf5_invalid() -> None:
    """Test invalid HDF5 file."""
    pytest.importorskip("h5py", reason="h5py not installed")

    buffer = BytesIO()
    with pytest.raises(Exception, match=r"Unable to (synchronously )?open file \(file signature not found\)"):
        verify_hdf5(buffer)


def test_radar_verify_hdf5_without_h5py_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifying a radar HDF5 file without h5py says what to install, not a bare ModuleNotFoundError (GH-2667)."""
    monkeypatch.setitem(sys.modules, "h5py", None)

    with pytest.raises(MissingDependencyError) as excinfo:
        verify_hdf5(BytesIO())

    assert str(excinfo.value) == (
        "Verifying radar HDF5 requires h5py, which is not installed. Install it with: pip install wetterdienst[radar]"
    )


UTC = ZoneInfo("UTC")
DX_HEADER = b"DX222110101321026BY31755VS 2CO0CD4CS0EP0.80.80.80.80.80.80.80.8MS  0\x03\x03\x00"


def test_the_scan_time_of_a_real_odim_file_is_its_what_group() -> None:
    """Test that `/what` `date` 20261020 and `time` 132500 of a real VII composite is the time of the scan, in UTC."""
    pytest.importorskip("h5py", reason="h5py not installed")
    path = Path(__file__).parent / "files" / "composite_VII_20261020_1325-hd5"
    buffer = BytesIO(path.read_bytes())
    buffer.seek(100)

    assert read_scan_time(buffer) == dt.datetime(2026, 10, 20, 13, 25, tzinfo=UTC)
    assert buffer.tell() == 0


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (DX_HEADER, dt.datetime(2026, 10, 22, 21, 10, tzinfo=UTC)),
        # 31st of December, 23:55
        (b"DX312355101321226BY31755VS 2", dt.datetime(2026, 12, 31, 23, 55, tzinfo=UTC)),
        # the 31st of November and the 13th month are no dates
        (b"DX311355101321126BY31755VS 2", None),
        (b"DX221355101321326BY31755VS 2", None),
        # the XML of the mesocyclones: the time of the first event, none for a run with no event
        (
            (
                b'<?xml version="1.0"?>\n<nowcast-data><event ID="4"><time time-coordinate="UTC">2026-10-22T16:10:00'
                b"</time></event></nowcast-data>"
            ),
            dt.datetime(2026, 10, 22, 16, 10, tzinfo=UTC),
        ),
        (b'<?xml version="1.0"?>\n<nowcast-data><radar-stations>ASB,BOO</radar-stations></nowcast-data>', None),
        # not a DX header: another XML file, an empty file, a text that is too short
        (b"<nowcast-data/>", None),
        (b"", None),
        (b"DX2221", None),
    ],
)
def test_the_scan_time_of_a_dx_file_is_its_header(content: bytes, expected: dt.datetime | None) -> None:
    """Test that the header of a DX file, `DX` DDHHMM, the site, MMYY, is read for the time, and nothing else is."""
    buffer = BytesIO(content)

    assert read_scan_time(buffer) == expected
    assert buffer.tell() == 0


def test_the_scan_time_of_an_hdf5_file_needs_h5py(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an HDF5 file is not read without h5py, which says what to install, as verifying it does."""
    monkeypatch.setitem(sys.modules, "h5py", None)

    with pytest.raises(MissingDependencyError, match=r"pip install wetterdienst\[radar\]"):
        read_scan_time(BytesIO(b"\x89HDF\r\n\x1a\n" + bytes(64)))


@pytest.mark.parametrize("error", [OverflowError("Python int too large to convert to C ssize_t"), RuntimeError("h5py")])
def test_a_damaged_hdf5_file_has_no_scan_time_and_is_no_error(
    error: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that whatever h5py raises at a damaged file, the time is None and the latest file is still handed over."""
    h5py = pytest.importorskip("h5py", reason="h5py not installed")

    def broken(*_: object, **__: object) -> None:
        raise error

    monkeypatch.setattr(h5py, "File", broken)
    buffer = BytesIO(b"\x89HDF\r\n\x1a\n" + bytes(64))

    assert read_scan_time(buffer) is None
    assert buffer.tell() == 0
