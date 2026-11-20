# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The grid of KOSTRA-DWD-2020: the projection (EPSG:3035), the index of a cell and where its centre is."""

from __future__ import annotations

import math

import pytest

from wetterdienst.exceptions import LocationOutOfRangeError
from wetterdienst.provider.dwd.kostra.grid import GRID_SIZE, Cell, from_laea, locate, to_laea

from .stubs import BERLIN, FRANKFURT, HAMBURG, MUNICH

#: cells of `KOSTRA-DWD-2020_geog_Bezug.xlsx` of DWD: the index and the latitude and longitude of the centre, as the
#: worksheet gives them (the first and the last cell of the grid, and those of the stub tables)
DWD_CENTRES = [
    ("000000", 56.746962447676303, -1.79415711790058),
    ("000001", 56.754302306653301, -1.7134933821820699),
    ("083144", 53.5501837159091, 10.022628297581599),
    ("105190", 52.512909414598603, 13.4112892444513),
    ("160126", 50.083114101223899, 8.7635449062226094),
    ("203167", 48.144945405345702, 11.5648848928112),
    ("299000", 43.448008457728903, 1.12349361591715),
    ("299299", 43.383765050082999, 19.586740089298299),
]


@pytest.mark.parametrize(("index_rc", "latitude", "longitude"), DWD_CENTRES)
def test_the_centre_of_a_cell_is_where_dwd_puts_it(index_rc: str, latitude: float, longitude: float) -> None:
    """The index is (row * 1000) + column from the north-west, on the grid of EPSG:3035 (to 1e-8 degrees)."""
    centre = Cell.from_index_rc(index_rc).centre

    assert centre[0] == pytest.approx(latitude, abs=1e-8)
    assert centre[1] == pytest.approx(longitude, abs=1e-8)


@pytest.mark.parametrize(("index_rc", "latitude", "longitude"), DWD_CENTRES)
def test_the_centre_of_a_cell_is_in_the_cell(index_rc: str, latitude: float, longitude: float) -> None:
    """The centres DWD published are found in their own cells."""
    assert locate(latitude, longitude).index_rc == index_rc


def test_the_point_of_dwds_example_is_in_the_cell_it_names() -> None:
    """DWD's Anwendungshilfe works out `160126` for 50.089149 N, 8.785514 E, the example of its worksheet."""
    assert locate(*FRANKFURT).index_rc == "160126"


@pytest.mark.parametrize(
    ("point", "index_rc"),
    [(BERLIN, "105190"), (HAMBURG, "083144"), (MUNICH, "203167")],
)
def test_cities_are_in_their_cells(point: tuple[float, float], index_rc: str) -> None:
    """The cell of a city, which the tables hold the values of."""
    assert locate(*point).index_rc == index_rc


def test_the_index_is_the_row_and_column_without_losing_its_padding() -> None:
    """`INDEX_RC` is six digits, `zzzsss`, as DWD writes it: row 0, column 1 is `000001`, row 36, column 34 `036034`."""
    assert Cell(row=0, column=1).index_rc == "000001"
    assert Cell(row=36, column=34).index_rc == "036034"
    assert Cell.from_index_rc("102005") == Cell(row=102, column=5)
    assert Cell.from_index_rc("1") == Cell(row=0, column=1)


def test_the_projection_is_the_lambert_azimuthal_equal_area_of_etrs89() -> None:
    """The centre of the projection (52 N, 10 E) is its false origin, 4321000 / 3210000; a metre is a metre."""
    assert to_laea(52.0, 10.0) == pytest.approx((4_321_000.0, 3_210_000.0), abs=1e-6)
    assert from_laea(4_321_000.0, 3_210_000.0) == pytest.approx((52.0, 10.0))
    # the corner of the grid DWD names in its ASCII headers (`xllcorner` 3600000, `yllcorner` 2300000)
    latitude, longitude = from_laea(3_600_000.0, 2_300_000.0)
    # the series of the inverse is good to a millimetre
    assert to_laea(latitude, longitude) == pytest.approx((3_600_000.0, 2_300_000.0), abs=1e-2)


def test_the_projection_agrees_with_proj() -> None:
    """Held to `pyproj` on a lattice over Europe, where it is installed (it is no dependency of the package)."""
    pyproj = pytest.importorskip("pyproj")
    transformer = pyproj.Transformer.from_crs(4326, 3035, always_xy=True)

    for latitude in range(40, 61, 3):
        for longitude in range(-5, 26, 3):
            x, y = to_laea(latitude, longitude)
            expected_x, expected_y = transformer.transform(longitude, latitude)
            assert math.isclose(x, expected_x, abs_tol=1e-4)
            assert math.isclose(y, expected_y, abs_tol=1e-4)


@pytest.mark.parametrize(
    "point",
    [(40.0, 0.0), (60.0, 10.0), (52.0, 30.0), (-33.9, 18.4), (52.0, -170.0)],
)
def test_a_point_off_the_grid_is_refused(point: tuple[float, float]) -> None:
    """The grid is 300 cells of 5 km a side, and a point outside it is out of range, not clamped to an edge."""
    with pytest.raises(LocationOutOfRangeError, match="outside the area of KOSTRA-DWD-2020"):
        locate(*point)


def test_the_antipode_of_the_projection_is_refused() -> None:
    """The point opposite the centre of the projection has no place in it."""
    with pytest.raises(LocationOutOfRangeError, match="cannot be placed"):
        to_laea(-52.0, -170.0)


@pytest.mark.parametrize("point", [(91.0, 10.0), (50.0, 181.0), (float("nan"), 10.0)])
def test_a_point_that_is_none_is_refused(point: tuple[float, float]) -> None:
    """A latitude beyond the poles, a longitude beyond the antimeridian and NaN are no points on the globe."""
    with pytest.raises(LocationOutOfRangeError, match="outside the range"):
        locate(*point)


def test_the_edges_of_the_grid_are_the_cells_inside() -> None:
    """The cell of the western edge and the northern edge is column 0 and row 0, which is half open."""
    assert GRID_SIZE == 300
    assert locate(*from_laea(3_600_000.0 + 1.0, 3_800_000.0 - 1.0)) == Cell(row=0, column=0)
    assert locate(*from_laea(5_100_000.0 - 1.0, 2_300_000.0 + 1.0)) == Cell(row=299, column=299)
    # a metre beyond is out
    with pytest.raises(LocationOutOfRangeError):
        locate(*from_laea(3_600_000.0 - 1.0, 3_000_000.0))
