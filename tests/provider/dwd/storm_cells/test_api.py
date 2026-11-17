# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the DWD thunderstorm cells request and result: the selection of a scan, the filters and the warnings."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Wetterdienst
from wetterdienst.exceptions import (
    DownloadError,
    InvalidTimeIntervalError,
    MetaFileFormatError,
    MetaFileNotFoundError,
    RequestError,
)
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.storm_cells import SEVERITY_LABELS, DwdStormCellsRequest, DwdStormCellsResult
from wetterdienst.provider.dwd.storm_cells.api import _SCHEMA, SCAN_STALE_AFTER
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

from .stubs import (
    BERLIN,
    DIRECTORY,
    EMPTY_SCAN,
    HAMBURG,
    SPLIT_CELLS_SCAN,
    TWO_CELLS_SCAN,
    listing,
    parts_scan,
    serve,
    three_cells_scan,
)

if TYPE_CHECKING:
    from collections.abc import Callable

UTC = ZoneInfo("UTC")

#: the instant the tests run at, four minutes after the scan of `TWO_CELLS_SCAN`: a scan as fresh as DWD publishes one
NOW = dt.datetime(2026, 11, 17, 22, 19, 44, tzinfo=UTC)
TWO_CELLS = "KONRAD3D_20261117T221500.xml"
EMPTY = "KONRAD3D_20261115T222000.xml"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the clock the age of a scan is measured against, and start the warnings of a request."""
    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.api._now", lambda: NOW)
    begin_response()


def _codes() -> list[str]:
    return [warning["code"] for warning in recorded_warnings()]


def test_registry_resolves_dwd_storm_cells() -> None:
    """The network is registered, standalone, and resolved by its own entry point."""
    assert Wetterdienst.resolve_standalone("dwd", "storm_cells") is DwdStormCellsRequest
    assert Wetterdienst.is_standalone("dwd", "storm_cells")


def test_the_network_says_who_publishes_it_and_under_which_terms() -> None:
    """The licence and the credit line are DWD's, the extent is the grid of the radar composite."""
    terms = DwdStormCellsRequest.terms

    assert terms.license is not None
    assert terms.license.spdx_id == "CC-BY-4.0"
    assert terms.attribution == "Source: Deutscher Wetterdienst"
    assert list(terms.extent.bbox) == [1.4, 45.7, 18.8, 55.9]
    assert terms.extent.scope == "national"
    assert DwdStormCellsRequest.listing["kind"] == "storm_cells"


# --- the selection of a scan ------------------------------------------------------------------------------------------


def test_the_newest_scan_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """There is no `latest` file: the newest of the listing is the one."""
    downloaded = serve(monkeypatch, {EMPTY: EMPTY_SCAN, TWO_CELLS: TWO_CELLS_SCAN})

    result = DwdStormCellsRequest().query()

    assert downloaded == [f"{DIRECTORY}{TWO_CELLS}"]
    assert result.df.height == 2
    assert result.reference_time == dt.datetime(2026, 11, 17, 22, 15, tzinfo=UTC)
    assert result.data_updated_at == dt.datetime(2026, 11, 17, 22, 19, 44, tzinfo=UTC)


def test_the_listing_is_read_for_a_minute_and_a_scan_is_kept_for_half_a_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scan is a file named for its time, so never changes; the listing grows every five minutes."""
    seen: dict[str, object] = {}

    def fake_listing(url: str, settings: object, cache_expiry: CacheExpiry = CacheExpiry.FILEINDEX) -> list[dict]:  # noqa: ARG001
        seen["listing"] = cache_expiry
        return listing("20261117T221500")

    def fake_download(url: str, **kwargs: object) -> File:
        seen["download"] = kwargs["ttl"]
        return File(url=url, content=BytesIO(TWO_CELLS_SCAN), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.api.list_remote_directory_fsspec", fake_listing)
    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.api.download_file", fake_download)

    DwdStormCellsRequest().query()

    assert seen == {"listing": CacheExpiry.ONE_MINUTE, "download": CacheExpiry.TWELVE_HOURS}


def test_a_timestamp_selects_the_newest_scan_at_or_before_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The newest at or before the time: one in the middle of two, and one on the instant."""
    files = {
        "KONRAD3D_20261117T201500.xml": EMPTY_SCAN,
        "KONRAD3D_20261117T202500.xml": SPLIT_CELLS_SCAN,
        "KONRAD3D_20261117T221500.xml": TWO_CELLS_SCAN,
    }
    downloaded = serve(monkeypatch, files)

    DwdStormCellsRequest(timestamp="2026-11-17T21:00:00").query()
    DwdStormCellsRequest(timestamp="2026-11-17T22:15:00+00:00").query()
    DwdStormCellsRequest(timestamp="2026-11-17T23:15:00+01:00").query()  # an offset, the same instant

    assert [url.rsplit("/", 1)[-1] for url in downloaded] == [
        "KONRAD3D_20261117T202500.xml",
        "KONRAD3D_20261117T221500.xml",
        "KONRAD3D_20261117T221500.xml",
    ]


def test_a_timestamp_before_the_window_is_the_callers(monkeypatch: pytest.MonkeyPatch) -> None:
    """DWD keeps about 48 hours: a time before the oldest file is refused, naming the oldest."""
    serve(monkeypatch, {EMPTY: EMPTY_SCAN, TWO_CELLS: TWO_CELLS_SCAN})

    with pytest.raises(InvalidTimeIntervalError, match="earliest available is 2026-11-15T22:20:00"):
        DwdStormCellsRequest(timestamp="2026-11-01T00:00:00").query()


def test_a_timestamp_after_the_last_scan_is_the_last_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    """The newest at or before a time in the future is the newest."""
    downloaded = serve(monkeypatch, {EMPTY: EMPTY_SCAN, TWO_CELLS: TWO_CELLS_SCAN})

    DwdStormCellsRequest(timestamp="2026-11-18T00:00:00").query()

    assert downloaded[-1].endswith(TWO_CELLS)


def test_a_listing_without_a_scan_is_a_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A directory with no `KONRAD3D_*.xml` is DWD's to answer for, and no time's doing."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api.list_remote_directory_fsspec",
        lambda *_a, **_k: listing(other=["index.html", "KONRAD3D_latest.txt"]),
    )

    with pytest.raises(MetaFileNotFoundError, match="no KONRAD3D scan listed"):
        DwdStormCellsRequest().query()
    with pytest.raises(MetaFileNotFoundError):
        DwdStormCellsRequest(timestamp="2026-11-17T22:00:00").query()


def test_the_names_that_are_no_scan_are_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only `KONRAD3D_YYYYMMDDThhmmss.xml` is a scan."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api.list_remote_directory_fsspec",
        lambda *_a, **_k: listing("20261117T221500", other=["KONRAD3D_20261117T230000.xml.tmp", "meso_latest.xml"]),
    )

    url, reference_time = DwdStormCellsRequest()._resolve_scan()  # noqa: SLF001

    assert url == f"{DIRECTORY}KONRAD3D_20261117T221500.xml"
    assert reference_time == dt.datetime(2026, 11, 17, 22, 15, tzinfo=UTC)


@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_timestamp_means_the_newest(value: str) -> None:
    """A `timestamp=` that is present and empty is none."""
    assert DwdStormCellsRequest(timestamp=value).timestamp is None


def test_a_timestamp_is_utc_unless_it_says_otherwise() -> None:
    """A naive time is UTC, an offset is converted."""
    assert DwdStormCellsRequest(timestamp="2026-07-26T10:00:00").timestamp == dt.datetime(2026, 7, 26, 10, tzinfo=UTC)
    assert DwdStormCellsRequest(timestamp="2026-07-26T12:00:00+02:00").timestamp == dt.datetime(
        2026, 7, 26, 10, tzinfo=UTC
    )


@pytest.mark.parametrize("value", ["yesterday", "0001-01-01T00:00:00+01:00"])
def test_a_timestamp_that_cannot_be_read_is_the_callers(value: str) -> None:
    """One that does not parse, or one an offset carries out of what a datetime holds."""
    with pytest.raises(RequestError, match="timestamp"):
        DwdStormCellsRequest(timestamp=value)


# --- the cells of a scan ----------------------------------------------------------------------------------------------


def test_the_frame_has_a_row_for_every_cell_and_the_columns_of_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """One row per cell, flat columns in DWD's units named for them, the outline as GeoJSON and the track nested."""
    serve(monkeypatch, {TWO_CELLS: TWO_CELLS_SCAN})

    df = DwdStormCellsRequest().query().df

    assert df.columns == list(_SCHEMA)
    assert df.schema == pl.Schema(_SCHEMA)
    assert df["cell_id"].to_list() == ["5", "53"]
    assert df["severity"].to_list() == [1, 1]
    assert df["severity_label"].to_list() == ["moderate", "moderate"]
    assert df["track"].list.len().to_list() == [12, 12]
    first = df.row(0, named=True)
    assert json.loads(first["geometry"])["type"] == "Polygon"
    assert first["track"][0]["time"] == dt.datetime(2026, 11, 17, 22, 20, tzinfo=UTC)


def test_every_severity_has_its_label() -> None:
    """0 weak, 1 moderate, 2 severe, 3 extreme."""
    assert SEVERITY_LABELS == ("weak", "moderate", "severe", "extreme")


def test_an_empty_scan_is_an_empty_frame_that_says_when_with_no_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most scans hold no cell: the answer is the frame of its columns with no row, and the time of the scan."""
    serve(monkeypatch, {"KONRAD3D_20261117T221500.xml": EMPTY_SCAN})

    result = DwdStormCellsRequest().query()

    assert result.df.is_empty()
    assert result.df.schema == pl.Schema(_SCHEMA)
    assert result.reference_time == dt.datetime(2026, 11, 15, 22, 20, tzinfo=UTC)
    assert _codes() == []


def test_a_request_without_the_track_leaves_the_column_out_and_keeps_the_direction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The track is 1.6 KB of JSON a cell; the direction is calculated from it either way."""
    serve(monkeypatch, {TWO_CELLS: TWO_CELLS_SCAN})

    df = DwdStormCellsRequest(track=False).query().df

    assert "track" not in df.columns
    assert df["direction_degrees"].to_list() == [71.4, pytest.approx(df["direction_degrees"][1])]
    assert df["direction_degrees"].null_count() == 0


def test_the_geometry_of_a_cell_is_its_outline_or_its_centre(monkeypatch: pytest.MonkeyPatch) -> None:
    """`centroid` is a point, a few dozen characters, where an outline is a few hundred to two thousand."""
    serve(monkeypatch, {TWO_CELLS: TWO_CELLS_SCAN})

    outline = DwdStormCellsRequest().query().df["geometry"].to_list()
    centre = DwdStormCellsRequest(geometry="centroid").query().df["geometry"].to_list()

    assert json.loads(centre[0]) == {"type": "Point", "coordinates": [6.90482, 49.05082]}
    assert all(len(point) < len(polygon) / 5 for point, polygon in zip(centre, outline, strict=True))


def test_an_outline_in_parts_is_a_multipolygon_with_closed_rings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two polygons for one cell: both are in its geometry, and so are both blocks of cells."""
    serve(monkeypatch, {"KONRAD3D_20261117T221500.xml": parts_scan()})

    df = DwdStormCellsRequest().query().df

    assert df["cell_id"].to_list() == ["7", "8"]
    merged = json.loads(df["geometry"][0])
    assert merged["type"] == "MultiPolygon"
    assert len(merged["coordinates"]) == 2
    assert all(polygon[0][0] == polygon[0][-1] for polygon in merged["coordinates"])
    assert json.loads(df["geometry"][1])["type"] == "Polygon"
    assert df["merge_event"].to_list() == [True, False]
    assert df["predecessor_code"][0] == "2026070111550000000003"


def test_the_missing_values_of_dwd_are_null_in_the_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gust flag and the estimated gust of the hand-made cell are DWD's missing value."""
    serve(monkeypatch, {"KONRAD3D_20261117T221500.xml": parts_scan()})

    row = DwdStormCellsRequest().query().df.row(0, named=True)

    assert row["gust_flag"] is None
    assert row["max_estimated_gust_kmh"] is None
    assert row["heavy_rain_flag"] == 2


# --- the filters ------------------------------------------------------------------------------------------------------


@pytest.fixture
def three(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the scan of three cells as the newest, a few minutes old."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 7, 1, 12, 6, tzinfo=UTC)
    )
    serve(monkeypatch, {"KONRAD3D_20260701T120000.xml": three_cells_scan()})


def _ids(**filters: object) -> list[str]:
    return DwdStormCellsRequest(**filters).query().df["cell_id"].to_list()  # ty: ignore[invalid-argument-type]


@pytest.mark.usefixtures("three")
def test_no_filter_is_every_cell() -> None:
    """A request that names no place is the whole scan, with nothing said."""
    assert _ids() == ["1", "2", "3"]
    assert _codes() == []


@pytest.mark.usefixtures("three")
def test_a_point_in_a_cell_finds_it() -> None:
    """The outline contains the point: distance 0 is the default."""
    assert _ids(latitude=BERLIN[0] + 0.02, longitude=BERLIN[1] - 0.02) == ["2"]


@pytest.mark.usefixtures("three")
def test_a_point_near_an_outline_finds_it_by_distance_and_not_by_the_centre() -> None:
    """A point 8 km north of the Berlin square's north edge is 13.6 km from its centre.

    A cell of 11 km has its centre 5.6 km from its edge: the distance is to the outline, so 9 km finds the cell, which a
    distance to the centre would need 14 km for.
    """
    point = {"latitude": BERLIN[0] + 0.05 + 0.072, "longitude": BERLIN[1]}  # 8 km north of the north edge

    assert _ids(**point) == []
    assert _ids(**point, distance=7.0) == []
    assert _ids(**point, distance=9.0) == ["2"]


@pytest.mark.usefixtures("three")
def test_a_point_far_from_every_cell_finds_none_and_says_so() -> None:
    """Three cells and none for Dresden: an answer, with the warning that says how many are elsewhere."""
    begin_response()

    assert _ids(latitude=51.05, longitude=13.74, distance=10.0) == []

    (warning,) = recorded_warnings()
    assert warning["code"] == "no-storm-cells-for-place"
    assert "within 10 km of the point 51.05, 13.74" in warning["message"]
    assert "3 cells are elsewhere" in warning["message"]
    assert "not an error" in warning["message"]


@pytest.mark.usefixtures("three")
def test_a_box_finds_the_cells_that_reach_into_it() -> None:
    """left, bottom, right, top: Berlin's cell is in the east, Munich's in the south."""
    assert _ids(left=12.0, bottom=51.0, right=15.0, top=54.0) == ["2"]
    assert _ids(left=5.0, bottom=47.0, right=15.0, top=55.0) == ["1", "2", "3"]
    assert _ids(left=5.0, bottom=47.0, right=15.0, top=50.0) == ["3"]


@pytest.mark.usefixtures("three")
def test_the_minimum_severity_keeps_the_cells_of_it_and_above() -> None:
    """0 weak, 1 moderate, 2 severe, 3 extreme."""
    assert _ids(min_severity=0) == ["1", "2", "3"]
    assert _ids(min_severity=2) == ["2", "3"]
    assert _ids(min_severity=3) == ["3"]


@pytest.mark.usefixtures("three")
def test_a_place_and_a_severity_must_both_hold() -> None:
    """Berlin's cell is severe, Hamburg's is weak."""
    assert _ids(left=5.0, bottom=47.0, right=15.0, top=55.0, min_severity=3) == ["3"]
    begin_response()
    assert _ids(latitude=HAMBURG[0], longitude=HAMBURG[1], min_severity=1) == []
    (warning,) = recorded_warnings()
    assert warning["code"] == "no-storm-cells-for-place"
    assert "severity 1 (moderate) or more" in warning["message"]
    assert "over the point" in warning["message"]


@pytest.mark.usefixtures("three")
def test_a_filter_on_an_empty_scan_says_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """No cell at all is no cell elsewhere: the warning is for a scan that has some."""
    serve(monkeypatch, {"KONRAD3D_20260701T120000.xml": EMPTY_SCAN})

    assert _ids(latitude=52.5, longitude=13.4) == []
    assert _codes() == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"latitude": 50.0},
        {"distance": 5.0},
        {"left": 9.0, "bottom": 49.0},
        {"latitude": 50.0, "longitude": 10.0, "left": 9.0, "bottom": 49.0, "right": 11.0, "top": 51.0},
        {"min_severity": 4},
        {"min_severity": -1},
        {"geometry": "polygon"},
        {"distance": -1.0, "latitude": 50.0, "longitude": 10.0},
    ],
)
def test_a_request_that_asks_for_no_place_is_refused(arguments: dict[str, object]) -> None:
    """Half a point, a distance of no point, half a box, both, a severity that is none, a geometry that is none."""
    with pytest.raises(RequestError):
        DwdStormCellsRequest(**arguments)  # ty: ignore[invalid-argument-type]


# --- an old scan ------------------------------------------------------------------------------------------------------


def _stale(monkeypatch: pytest.MonkeyPatch, minutes: float) -> None:
    """Make now `minutes` after the scan of `TWO_CELLS_SCAN`."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now",
        lambda: dt.datetime(2026, 11, 17, 22, 15, tzinfo=UTC) + dt.timedelta(minutes=minutes),
    )


def test_the_staleness_is_20_minutes() -> None:
    """Four runs of five minutes missed: a constant, as the longest delay seen is 9 minutes."""
    assert dt.timedelta(minutes=20) == SCAN_STALE_AFTER


def test_a_scan_that_is_old_says_so_where_it_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one thing an empty answer must not hide: DWD's run stopped, and no cell is no all-clear."""
    serve(monkeypatch, {"KONRAD3D_20261117T221500.xml": EMPTY_SCAN})
    _stale(monkeypatch, 45)

    result = DwdStormCellsRequest().query()

    assert result.df.is_empty()
    (warning,) = recorded_warnings()
    assert warning["code"] == "scan-stale"
    assert "45 minutes" in warning["message"]
    assert "2026-11-17T22:15:00.000000+00:00" in warning["message"]
    assert "no all-clear" in warning["message"]


@pytest.mark.parametrize(("minutes", "stale"), [(0, False), (10, False), (20, False), (20.5, True), (60, True)])
def test_a_scan_is_stale_after_twenty_minutes(monkeypatch: pytest.MonkeyPatch, minutes: float, stale: bool) -> None:  # noqa: FBT001
    """Twenty minutes is as old as a scan may be; a bit more is old."""
    serve(monkeypatch, {"KONRAD3D_20261117T221500.xml": TWO_CELLS_SCAN})
    _stale(monkeypatch, minutes)

    DwdStormCellsRequest().query()

    assert _codes() == (["scan-stale"] if stale else [])


def test_a_timestamp_is_measured_against_itself_and_not_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scan of days ago asked for by its time is not old; a time with no scan within 20 minutes before it is."""
    files = {"KONRAD3D_20261117T221500.xml": TWO_CELLS_SCAN, "KONRAD3D_20261117T230000.xml": EMPTY_SCAN}
    serve(monkeypatch, files)
    _stale(monkeypatch, 60 * 24)

    DwdStormCellsRequest(timestamp="2026-11-17T22:30:00").query()
    assert _codes() == []

    DwdStormCellsRequest(timestamp="2026-11-17T22:40:00").query()  # 25 minutes after the scan, and none between
    assert _codes() == ["scan-stale"]


# --- what goes wrong ------------------------------------------------------------------------------------------------


def test_a_file_that_does_not_parse_is_a_format_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A file read while DWD was still writing it: the file's fault, an upstream error."""
    serve(monkeypatch, {TWO_CELLS: TWO_CELLS_SCAN[:5000]})

    with pytest.raises(MetaFileFormatError, match="holds what the parser does not expect"):
        DwdStormCellsRequest().query()


def test_a_page_that_is_no_scan_is_a_format_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CDN's error page answered with a 200 is well-formed and no scan."""
    serve(monkeypatch, {TWO_CELLS: b"<html><body>Service Unavailable</body></html>"})

    with pytest.raises(MetaFileFormatError, match="no KONRAD3D file"):
        DwdStormCellsRequest().query()


def _download_of(*bodies: tuple[bytes, bool]) -> tuple[Callable[..., File], list[dict[str, object]]]:
    """Make a download that answers with these bodies in turn, `(body, from_cache)`, and note what it was asked."""
    asked: list[dict[str, object]] = []
    remaining = list(bodies)

    def download(url: str, **kwargs: object) -> File:
        asked.append(kwargs)
        body, from_cache = remaining.pop(0)
        return File(url=url, content=BytesIO(body), status=200, from_cache=from_cache)

    return download, asked


def test_a_copy_of_the_cache_that_does_not_parse_is_fetched_once_more(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cache keeps a file for 12 hours: one read while DWD wrote it must not make every request fail until then."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api.list_remote_directory_fsspec",
        lambda *_a, **_k: listing("20261117T221500"),
    )
    download, asked = _download_of((TWO_CELLS_SCAN[:5000], True), (TWO_CELLS_SCAN, False))
    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.api.download_file", download)

    result = DwdStormCellsRequest().query()

    assert result.df.height == 2
    # the first read takes the copy of the cache as it is, the second asks for it again
    assert asked[0]["refetch_before"] is None
    assert asked[1]["refetch_before"] is not None


def test_a_file_just_fetched_that_does_not_parse_is_not_fetched_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body that came off the wire a moment ago says what DWD has now: there is nothing to ask again."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api.list_remote_directory_fsspec",
        lambda *_a, **_k: listing("20261117T221500"),
    )
    download, asked = _download_of((TWO_CELLS_SCAN[:5000], False))
    monkeypatch.setattr("wetterdienst.provider.dwd.storm_cells.api.download_file", download)

    with pytest.raises(MetaFileFormatError):
        DwdStormCellsRequest().query()

    assert len(asked) == 1


def test_a_download_that_failed_is_a_download_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scan that rolled off the window between the listing and the download, say, is a 404: named, with its cause."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api.list_remote_directory_fsspec",
        lambda *_a, **_k: listing("20261117T221500"),
    )
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api.download_file",
        lambda url, **_k: File(url=url, content=FileNotFoundError("404"), status=404),
    )

    with pytest.raises(DownloadError, match=r"KONRAD3D_20261117T221500\.xml"):
        DwdStormCellsRequest().query()


def test_the_result_is_a_result_of_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """The type the library hands out."""
    serve(monkeypatch, {TWO_CELLS: TWO_CELLS_SCAN})

    assert isinstance(DwdStormCellsRequest().query(), DwdStormCellsResult)


def test_the_request_has_a_representation() -> None:
    """The arguments are in it, which a log line wants."""
    text = repr(DwdStormCellsRequest(latitude=50.0, longitude=10.0, distance=5.0, min_severity=2))

    assert "latitude=50.0" in text
    assert "distance=5.0" in text
    assert "min_severity=2" in text
