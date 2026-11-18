# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the place of the storm cells: an outline that contains a point or is near it, or reaches into a box."""

from __future__ import annotations

import math

import pytest

from wetterdienst.exceptions import RequestError
from wetterdienst.provider.dwd.storm_cells.place import (
    check_bbox,
    check_distance,
    check_place,
    is_for_box,
    is_for_point,
    outline_distance_km,
)

# a square of 0.1 degrees around 50.0, 10.0: 7.1 km east to west, 11.1 km south to north
SQUARE = {
    "type": "Polygon",
    "coordinates": [[[9.95, 49.95], [10.05, 49.95], [10.05, 50.05], [9.95, 50.05], [9.95, 49.95]]],
}
#: and the same cell in two parts, the second one 1 degree to the north-east
PARTS = {
    "type": "MultiPolygon",
    "coordinates": [
        SQUARE["coordinates"],
        [[[10.95, 50.95], [11.05, 50.95], [11.05, 51.05], [10.95, 51.05], [10.95, 50.95]]],
    ],
}
KM_PER_DEGREE = 111.195


def test_a_point_in_the_outline_is_at_no_distance() -> None:
    """A point the outline contains is over the cell."""
    assert outline_distance_km(SQUARE, 50.0, 10.0) == 0.0
    assert is_for_point(SQUARE, 50.0, 10.0)


def test_a_point_on_the_edge_is_inside() -> None:
    """The edge of the outline counts as inside, as it does for the warnings."""
    assert is_for_point(SQUARE, 50.0, 10.05)
    assert is_for_point(SQUARE, 49.95, 9.95)


def test_a_point_outside_is_at_the_distance_to_the_nearest_edge() -> None:
    """The distance to an outline is to its nearest edge, not to its centre: 0.1 degrees north of the north edge."""
    expected = 0.1 * KM_PER_DEGREE

    assert outline_distance_km(SQUARE, 50.15, 10.0) == pytest.approx(expected, rel=0.01)
    assert not is_for_point(SQUARE, 50.15, 10.0, distance=expected * 0.98)
    assert is_for_point(SQUARE, 50.15, 10.0, distance=expected * 1.02)


def test_the_distance_to_a_corner_is_to_the_corner() -> None:
    """A point off the corner is nearer to the vertex than to either line through it."""
    expected = math.hypot(0.1 * KM_PER_DEGREE, 0.1 * KM_PER_DEGREE * math.cos(math.radians(50.0)))

    assert outline_distance_km(SQUARE, 50.15, 10.15) == pytest.approx(expected, rel=0.01)


def test_the_distance_east_is_a_degree_of_longitude_shorter() -> None:
    """A degree of longitude is cos(latitude) of one of latitude."""
    assert outline_distance_km(SQUARE, 50.0, 10.15) == pytest.approx(
        0.1 * KM_PER_DEGREE * math.cos(math.radians(50.0)), rel=0.01
    )


def test_a_cell_in_parts_is_near_by_its_nearest_part() -> None:
    """The outline in two parts: the second is the nearer to a point north-east of both."""
    assert outline_distance_km(PARTS, 51.15, 11.0) == pytest.approx(0.1 * KM_PER_DEGREE, rel=0.01)
    assert outline_distance_km(PARTS, 51.0, 11.0) == 0.0


def test_a_cell_without_an_outline_is_never_for_a_point() -> None:
    """No outline, no distance, and no place."""
    assert outline_distance_km(None, 50.0, 10.0) is None
    assert not is_for_point(None, 50.0, 10.0, distance=1000.0)


def test_a_zero_distance_is_the_cells_over_the_point() -> None:
    """The default distance of a point: only the outlines that contain it."""
    assert is_for_point(SQUARE, 50.0, 10.0, distance=0.0)
    assert not is_for_point(SQUARE, 50.06, 10.0, distance=0.0)


@pytest.mark.parametrize(
    ("box", "expected"),
    [
        ((9.0, 49.0, 11.0, 51.0), True),  # the outline inside the box
        ((9.99, 49.99, 10.01, 50.01), True),  # the box inside the outline: no vertex of either in the other
        ((10.0, 49.9, 10.1, 50.0), True),  # a corner of the outline in the box, and an edge across it
        ((9.9, 49.99, 10.1, 50.01), True),  # a band that crosses the outline with no vertex in it
        ((10.06, 49.0, 11.0, 51.0), False),  # east of the outline
        ((9.0, 50.06, 11.0, 51.0), False),  # north of it
        ((10.05, 50.05, 11.0, 51.0), True),  # touching at the corner
    ],
)
def test_a_box_is_reached_by_an_outline_that_has_a_part_in_it(
    box: tuple[float, float, float, float],
    expected: bool,  # noqa: FBT001
) -> None:
    """An outline is for a box if an edge has a part in it, or the outline goes around it."""
    assert is_for_box(SQUARE, *box) is expected


def test_a_box_is_reached_by_either_part_of_an_outline() -> None:
    """The second part of a cell is in the box, the first is not."""
    assert is_for_box(PARTS, 10.9, 50.9, 11.1, 51.1)
    assert not is_for_box(PARTS, 10.2, 50.2, 10.8, 50.8)


def test_a_cell_without_an_outline_is_never_for_a_box() -> None:
    """No outline, no box."""
    assert not is_for_box(None, -180, -90, 180, 90)


def test_a_place_that_is_half_a_point_is_refused() -> None:
    """A point is a latitude and a longitude."""
    with pytest.raises(RequestError, match="given together"):
        check_place(50.0, None, None, None, None, None, None)


def test_a_distance_without_a_point_is_refused() -> None:
    """A distance is the radius around a point."""
    with pytest.raises(RequestError, match="distance"):
        check_place(None, None, 25.0, None, None, None, None)


def test_a_point_and_a_box_together_are_refused() -> None:
    """The place is one of them."""
    with pytest.raises(RequestError, match="not both"):
        check_place(50.0, 10.0, 5.0, 9.0, 49.0, 11.0, 51.0)


@pytest.mark.parametrize(
    "box",
    [
        (9.0, 49.0, 11.0, None),
        (11.0, 49.0, 9.0, 51.0),  # left east of right
        (9.0, 51.0, 11.0, 49.0),  # bottom above top
        (9.0, 49.0, 11.0, 91.0),
        (math.nan, 49.0, 11.0, 51.0),
    ],
)
def test_a_box_that_is_no_box_is_refused(box: tuple[float, float, float, float | None]) -> None:
    """The four edges are given together, in order, on Earth."""
    with pytest.raises(RequestError):
        check_bbox(*box)


def test_no_box_is_no_box() -> None:
    """A request without edges has none to refuse."""
    assert check_bbox(None, None, None, None) is False
    assert check_bbox(9.0, 49.0, 11.0, 51.0) is True


@pytest.mark.parametrize("distance", [-1.0, math.inf, math.nan])
def test_a_distance_that_is_no_length_is_refused(distance: float) -> None:
    """Zero or more, and finite."""
    with pytest.raises(RequestError):
        check_distance(distance)
