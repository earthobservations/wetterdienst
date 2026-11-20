# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The grid of KOSTRA-DWD-2020: which cell a point is in, and where a cell is.

DWD states the reference system in its Anwendungshilfe zu KOSTRA-DWD-2020 (section 4): ETRS89-LAEA (EPSG:3035), 300 by
300 cells of 5 km, the lower left corner at 3,600,000 / 2,300,000. A cell is named by `INDEX_RC`, "(row * 1000) +
column" with the row counted from the north and the column from the west (section 5.1). The projection is the Lambert
azimuthal equal-area one on the GRS80 ellipsoid (Snyder, Map Projections, 24-27 to 24-31), written out here so that
the lookup needs no projection library: `pyproj` is no dependency of the package.

`tests/provider/dwd/kostra/test_grid.py` holds it to the cell centres DWD published in `KOSTRA-DWD-2020_geog_Bezug.xlsx`
(to 1e-8 degrees, all of the 90,000 cells were compared when this was written) and to `pyproj` where it is installed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from wetterdienst.exceptions import LocationOutOfRangeError
from wetterdienst.util.geo import require_location_in_range

#: the number of cells on a side of the grid
GRID_SIZE = 300
#: the width of a cell, in metres
CELL_SIZE = 5000.0
#: the easting of the western edge of the grid, in metres (`xllcorner` of DWD's ASCII grids)
X_MIN = 3_600_000.0
#: the northing of the southern edge of the grid, in metres (`yllcorner` of DWD's ASCII grids)
Y_MIN = 2_300_000.0
#: the northing of the northern edge, which the rows are counted from
Y_MAX = Y_MIN + GRID_SIZE * CELL_SIZE

# EPSG:3035: GRS80, the centre of the projection at 52 N, 10 E, false easting and northing 4321000 and 3210000
_A = 6_378_137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)
_E = math.sqrt(_E2)
_LAT_0 = math.radians(52.0)
_LON_0 = math.radians(10.0)
_FALSE_X = 4_321_000.0
_FALSE_Y = 3_210_000.0


def _q(sin_lat: float) -> float:
    """Give the authalic function of Snyder (3-12) for the sine of a latitude."""
    e_sin = _E * sin_lat
    return (1 - _E2) * (sin_lat / (1 - e_sin * e_sin) - math.log((1 - e_sin) / (1 + e_sin)) / (2 * _E))


_Q_POLE = _q(1.0)
_BETA_0 = math.asin(_q(math.sin(_LAT_0)) / _Q_POLE)
_R_Q = _A * math.sqrt(_Q_POLE / 2)
_D = _A * math.cos(_LAT_0) / math.sqrt(1 - _E2 * math.sin(_LAT_0) ** 2) / (_R_Q * math.cos(_BETA_0))
_SIN_BETA_0 = math.sin(_BETA_0)
_COS_BETA_0 = math.cos(_BETA_0)
# the series of the geodetic latitude of the authalic one (Snyder 3-18)
_P2 = _E2 / 3 + 31 * _E**4 / 180 + 517 * _E**6 / 5040
_P4 = 23 * _E**4 / 360 + 251 * _E**6 / 3780
_P6 = 761 * _E**6 / 45360


def to_laea(latitude: float, longitude: float) -> tuple[float, float]:
    """Project a point (WGS84 degrees, which is ETRS89 to the metre) to ETRS89-LAEA, EPSG:3035, in metres.

    Raises:
        LocationOutOfRangeError: the latitude or longitude is no point on the globe, or the point is the antipode of
            the centre of the projection, which it cannot be placed at.

    """
    require_location_in_range(latitude, longitude)
    lat = math.radians(latitude)
    d_lon = math.radians(longitude) - _LON_0
    beta = math.asin(max(-1.0, min(1.0, _q(math.sin(lat)) / _Q_POLE)))
    denominator = 1 + _SIN_BETA_0 * math.sin(beta) + _COS_BETA_0 * math.cos(beta) * math.cos(d_lon)
    if denominator < 1e-12:
        msg = f"the point {latitude}, {longitude} cannot be placed on the grid"
        raise LocationOutOfRangeError(msg)
    b = _R_Q * math.sqrt(2 / denominator)
    x = b * _D * math.cos(beta) * math.sin(d_lon)
    y = (b / _D) * (_COS_BETA_0 * math.sin(beta) - _SIN_BETA_0 * math.cos(beta) * math.cos(d_lon))
    return x + _FALSE_X, y + _FALSE_Y


def from_laea(x: float, y: float) -> tuple[float, float]:
    """Give the latitude and longitude (degrees) of a point of ETRS89-LAEA, EPSG:3035, given in metres."""
    x -= _FALSE_X
    y -= _FALSE_Y
    rho = math.hypot(x / _D, _D * y)
    if rho == 0:
        return math.degrees(_LAT_0), math.degrees(_LON_0)
    c = 2 * math.asin(rho / (2 * _R_Q))
    sin_c, cos_c = math.sin(c), math.cos(c)
    beta = math.asin(cos_c * _SIN_BETA_0 + _D * y * sin_c * _COS_BETA_0 / rho)
    lon = _LON_0 + math.atan2(x * sin_c, _D * rho * _COS_BETA_0 * cos_c - _D * _D * y * _SIN_BETA_0 * sin_c)
    lat = beta + _P2 * math.sin(2 * beta) + _P4 * math.sin(4 * beta) + _P6 * math.sin(6 * beta)
    return math.degrees(lat), math.degrees(lon)


@dataclass(frozen=True)
class Cell:
    """A cell of the grid: its row and column, the `INDEX_RC` DWD names it by, and where its centre is."""

    row: int
    column: int

    @property
    def index_rc(self) -> str:
        """Give the `INDEX_RC` as DWD writes it in its tables: (row * 1000) + column, in six digits."""
        return f"{self.row * 1000 + self.column:06d}"

    @property
    def centre(self) -> tuple[float, float]:
        """Give the latitude and longitude of the centre of the cell, in degrees."""
        return from_laea(X_MIN + (self.column + 0.5) * CELL_SIZE, Y_MAX - (self.row + 0.5) * CELL_SIZE)

    @classmethod
    def from_index_rc(cls, index_rc: str) -> Cell:
        """Read an `INDEX_RC` as DWD writes it (`105190`, or `1` for the cell of row 0 and column 1)."""
        number = int(index_rc)
        return cls(row=number // 1000, column=number % 1000)


def locate(latitude: float, longitude: float) -> Cell:
    """Give the cell of the grid that holds a point.

    Raises:
        LocationOutOfRangeError: the point is not on the globe, or lies outside the 300 x 300 cells of the grid, which
            reaches from about 43.4 N to 57.3 N and 1.8 W to 22.8 E (DWD gives values only for Germany and a border of
            about 10 km)

    """
    x, y = to_laea(latitude, longitude)
    column = math.floor((x - X_MIN) / CELL_SIZE)
    row = math.floor((Y_MAX - y) / CELL_SIZE)
    if not (0 <= column < GRID_SIZE and 0 <= row < GRID_SIZE):
        msg = (
            f"The point {latitude}, {longitude} is outside the area of KOSTRA-DWD-2020, which covers Germany and a "
            "border of about 10 km around it."
        )
        raise LocationOutOfRangeError(msg)
    return Cell(row=row, column=column)
