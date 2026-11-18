# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the parser of DWD's KONRAD3D scans: real scans, the missing values, the rings and the direction."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.provider.dwd.storm_cells.parser import bearing_degrees, parse_scan

from .stubs import EMPTY_SCAN, SPLIT_CELLS_SCAN, TWO_CELLS_SCAN, cell_xml, parts_scan, scan_xml, square

UTC = ZoneInfo("UTC")


def test_an_empty_scan_has_its_times_and_no_cell() -> None:
    """An empty scan is the usual one: a complete head, a self-closing `<cells/>`, and when it was."""
    scan = parse_scan(EMPTY_SCAN)

    assert scan.cells == []
    assert scan.reference_time == dt.datetime(2026, 11, 15, 22, 20, tzinfo=UTC)
    assert scan.created_at == dt.datetime(2026, 11, 15, 22, 25, 21, tzinfo=UTC)


def test_a_real_scan_with_two_cells() -> None:
    """The first cell of the scan of 2026-11-17 22:15, as DWD wrote it: every attribute the answer holds."""
    scan = parse_scan(TWO_CELLS_SCAN)
    assert [cell["cell_id"] for cell in scan.cells] == ["5", "53"]

    cell = scan.cells[0]
    assert cell["code"] == "2026111722150000000000"
    assert cell["reference_time"] == dt.datetime(2026, 11, 17, 22, 15, tzinfo=UTC)
    assert cell["first_detection"] == dt.datetime(2026, 11, 17, 22, 15, tzinfo=UTC)
    assert cell["number_detections"] == 1
    assert cell["predecessor_code"] is None
    assert (cell["split_event"], cell["merge_event"]) == (False, False)
    assert (cell["severity"], cell["severity_decimal"]) == (1, 0.5)
    assert (cell["hail_flag"], cell["heavy_rain_flag"], cell["gust_flag"]) == (0, 0, 1)
    assert (cell["centroid_latitude"], cell["centroid_longitude"]) == (49.05082, 6.90482)
    assert cell["cell_speed_kmh"] == 97.493
    assert cell["covered_area_km2"] == 58.1875
    assert cell["echo_top_msl_m"] == 4368.0
    assert cell["max_reflectivity_dbz"] == 52.23
    assert cell["vil_kg_m2"] == 6.468
    assert cell["max_estimated_gust_kmh"] == 79.01
    assert cell["heavy_rain_potential_mm"] == 4.59


def test_the_track_is_the_twelve_forecast_positions_in_time_order() -> None:
    """The nowcast: +5 to +60 minutes in steps of 5, each with the 1 sigma ellipse of the position."""
    cell = parse_scan(TWO_CELLS_SCAN).cells[0]
    track = cell["track"]

    assert len(track) == 12
    assert [point["time"] for point in track] == [
        dt.datetime(2026, 11, 17, 22, 15, tzinfo=UTC) + dt.timedelta(minutes=5 * n) for n in range(1, 13)
    ]
    assert track[0] == {
        "time": dt.datetime(2026, 11, 17, 22, 20, tzinfo=UTC),
        "latitude": 49.07276,
        "longitude": 7.00394,
        "uncertainty_major_km": 2.071,
        "uncertainty_minor_km": 1.169,
        "uncertainty_angle_degrees": 56.05,
    }


def test_the_direction_is_calculated_from_the_first_two_forecast_positions() -> None:
    """DWD gives the speed and no direction: the bearing from the +5 to the +10 minute position, from north."""
    cell = parse_scan(TWO_CELLS_SCAN).cells[0]
    first, second = cell["track"][:2]

    assert cell["direction_degrees"] == bearing_degrees(
        first["latitude"], first["longitude"], second["latitude"], second["longitude"]
    )
    # the cell moves to the east-north-east, by the positions
    assert cell["direction_degrees"] == 71.4


def test_the_outline_is_a_closed_ring() -> None:
    """DWD does not repeat the first vertex of a polygon, which GeoJSON asks for."""
    (ring,) = parse_scan(TWO_CELLS_SCAN).cells[0]["rings"]

    assert ring[0] == ring[-1]
    assert ring[0] == [6.95307, 49.09952]  # [longitude, latitude]
    assert len(ring) == 65


def test_a_split_has_its_predecessor() -> None:
    """`40*` was split off in this step: the flag is DWD's element, the id has no `*`, the predecessor is a code."""
    cells = {cell["cell_id"]: cell for cell in parse_scan(SPLIT_CELLS_SCAN).cells}

    assert set(cells) == {"40", "38", "32"}
    split = cells["40"]
    assert split["split_event"] is True
    assert split["merge_event"] is False
    assert split["predecessor_code"] == "2026111719550000000000"
    assert split["number_detections"] == 7
    assert cells["38"]["split_event"] is False
    # a cell that goes on has the code of its predecessor: the code is the cell's, from scan to scan
    assert cells["38"]["predecessor_code"] == cells["38"]["code"] == "2026111720200000000001"
    assert cells["32"]["predecessor_code"] == cells["32"]["code"]
    assert split["predecessor_code"] != split["code"]


def test_two_polygons_and_two_blocks_of_cells_are_both_read() -> None:
    """The format allows several polygons for one cell and several `cells` for several times: all are read."""
    scan = parse_scan(parts_scan())

    merged, other = scan.cells
    assert len(merged["rings"]) == 2
    assert all(ring[0] == ring[-1] for ring in merged["rings"])
    assert merged["reference_time"] == dt.datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    # the reference time of a cell is that of its own block
    assert other["reference_time"] == dt.datetime(2026, 7, 1, 12, 5, tzinfo=UTC)
    assert scan.reference_time == dt.datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def test_a_merger_is_read_from_its_element_and_its_surest_predecessor_is_given() -> None:
    """`#` is a merger for one step; of the predecessors (100 %, or 0 for those of a merger) the surest is the code."""
    merged = parse_scan(parts_scan()).cells[0]

    assert merged["cell_id"] == "7"
    assert merged["merge_event"] is True
    assert merged["split_event"] is False
    assert merged["predecessor_code"] == "2026070111550000000003"


def test_a_split_and_a_merge_are_told_by_the_identifier_where_the_file_has_no_element() -> None:
    """The `*` and `#` after an identifier say it too: the one source where the element is not there."""
    feature = (
        cell_xml("9*")
        .replace("<splits><split_event>false</split_event></splits>", "")
        .replace("<mergers><merge_event>false</merge_event>", "<mergers>")
    )
    cell = parse_scan(scan_xml(("2026-07-01T12:00:00Z", [feature]))).cells[0]

    assert cell["cell_id"] == "9"
    assert cell["split_event"] is True
    assert cell["merge_event"] is False


def test_dwds_missing_values_are_null() -> None:
    """`-1000000000` is a number DWD does not have, `not-a-date-time` a time: null in every element that is read."""
    feature = cell_xml(gust_flag="-1000000000", severity="-1000000000")
    cell = parse_scan(scan_xml(("2026-07-01T12:00:00Z", [feature]))).cells[0]

    assert cell["gust_flag"] is None  # the flag of a cell that DWD could not judge
    assert cell["severity"] is None
    assert cell["max_estimated_gust_kmh"] is None  # the written value of `-1000000000.000`
    # the other attributes are not nulled by it
    assert cell["heavy_rain_flag"] == 2
    assert cell["vil_kg_m2"] == 12.5


def test_a_time_that_is_not_a_date_time_is_null() -> None:
    """The first detection of a cell is a time like the others: `not-a-date-time` is none."""
    feature = cell_xml(first_detection="not-a-date-time")
    cell = parse_scan(scan_xml(("2026-07-01T12:00:00Z", [feature]))).cells[0]

    assert cell["first_detection"] is None


def test_a_polygon_that_is_closed_already_stays_as_it_is() -> None:
    """A ring that repeats its first vertex is not closed a second time."""
    lats, lons = square(50.0, 10.0)
    closed = (f"{lats} {lats.split()[0]}", f"{lons} {lons.split()[0]}")
    cell = parse_scan(scan_xml(("2026-07-01T12:00:00Z", [cell_xml(polygons=[closed])]))).cells[0]

    assert len(cell["rings"][0]) == 5


def test_a_cell_without_an_outline_has_none() -> None:
    """A polygon of fewer than three vertices is no outline."""
    cell = parse_scan(scan_xml(("2026-07-01T12:00:00Z", [cell_xml(polygons=[("50.0 50.1", "10.0 10.1")])]))).cells[0]

    assert cell["rings"] == []


def test_a_cell_with_one_forecast_position_has_no_direction() -> None:
    """The direction is between two positions."""
    feature = cell_xml(forecast=[("2026-07-01T12:05:00Z", "50.05", "10.0")])
    cell = parse_scan(scan_xml(("2026-07-01T12:00:00Z", [feature]))).cells[0]

    assert len(cell["track"]) == 1
    assert cell["direction_degrees"] is None


def test_a_cell_that_does_not_move_has_no_direction() -> None:
    """Two positions that are one have no bearing."""
    feature = cell_xml(forecast=[("2026-07-01T12:05:00Z", "50.05", "10.0"), ("2026-07-01T12:10:00Z", "50.05", "10.0")])
    cell = parse_scan(scan_xml(("2026-07-01T12:00:00Z", [feature]))).cells[0]

    assert cell["direction_degrees"] is None


@pytest.mark.parametrize(
    ("to", "expected"),
    [
        ((51.0, 10.0), 0.0),  # north
        ((50.0, 11.0), 89.6),  # east, the bearing of a parallel bends towards the pole
        ((49.0, 10.0), 180.0),
        ((50.0, 9.0), 270.3),
        ((51.0, 11.0), 32.1),
        ((49.0, 9.0), 213.4),
    ],
)
def test_the_bearing_is_clockwise_from_north(to: tuple[float, float], expected: float) -> None:
    """Degrees clockwise from north, 0 up to 360, on the great circle."""
    assert bearing_degrees(50.0, 10.0, *to) == pytest.approx(expected, abs=0.1)


def test_the_bearing_of_one_point_is_none() -> None:
    """There is no direction from a point to itself."""
    assert bearing_degrees(50.0, 10.0, 50.0, 10.0) is None


def test_a_truncated_file_does_not_parse() -> None:
    """A file read while DWD wrote it ends anywhere: lxml refuses it, as a `SyntaxError`."""
    with pytest.raises(SyntaxError):
        parse_scan(TWO_CELLS_SCAN[:5000])


def test_a_document_that_is_no_scan_is_refused() -> None:
    """An error page of a CDN that answers 200 may be well-formed XML: it is no KONRAD3D file."""
    with pytest.raises(ValueError, match="no KONRAD3D file"):
        parse_scan(b"<html><body>Service unavailable</body></html>")


def test_a_number_that_is_none_is_refused() -> None:
    """An element the parser reads that holds what is no number: the file's, not the request's, to answer for."""
    feature = cell_xml().replace(">30.0</covered_area>", ">thirty</covered_area>")
    with pytest.raises(ValueError, match="could not convert"):
        parse_scan(scan_xml(("2026-07-01T12:00:00Z", [feature])))
