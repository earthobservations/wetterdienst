# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD's RV composite as a map image (GH-3788).

The RV composite (https://opendata.dwd.de/weather/radar/composite/rv/) is DWD's 5-minute precipitation product: one
`.tar` a run (every 5 minutes) with an ODIM HDF5 file for the radar analysis (lead time 0) and one for each of the 24
forecasts of the next two hours. Each file is a 1100 x 1200 grid of 1 km cells in a polar stereographic projection (the
DE1200 grid), holding the precipitation of the 5 minutes that end at the time of the frame (`ACRR`, in mm, a
`uint32` with a gain of 0.001).

A browser cannot read that grid, and a map needs lat/lon bounds, so a frame is made into an image:

- the 5-minute sum is turned into a rate in mm/h (from the length the file states it is of, 300 s, so x 12) and sorted
  into the classes of `RAIN_CLASSES`, whose colours are one ramp of falling lightness, which reads for every kind of
  colour vision and in grey;
- the grid is warped to the Web Mercator (EPSG:3857) grid of an image whose pixels are square there and whose bounds
  are given in WGS84, which is what a Leaflet `ImageOverlay` stretches an image over: the polar stereographic grid is
  not drawn as it is, because its rows are not parallels. The warp takes the cell that contains the centre of each
  pixel (nearest neighbour), so the classes are never blended;
- the result is an indexed PNG whose colour 0 is transparent: no rain, and no data (outside the composite, or a radar
  that is missing) are both transparent.

Decoding needs `h5py` and `numpy`, which the `radar` extra installs; neither wradlib nor xradar is used. The
projection is written here (the ellipsoidal polar stereographic of Snyder, *Map Projections: A Working Manual*,
21-33 to 21-40) so that no `pyproj` is needed; the tests hold it to the corners DWD writes in every file and to PROJ.
"""

from __future__ import annotations

import datetime as dt
import math
import struct
import zlib
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from typing import TYPE_CHECKING, Any

from wetterdienst.exceptions import UpstreamError
from wetterdienst.util.extras import import_optional

if TYPE_CHECKING:
    import numpy as np

#: the unit of the rates a frame is drawn in
RATE_UNIT = "mm/h"

#: how wide the image is, in pixels. The grid of DWD is 1100 cells wide at about 1 km; the image is as wide as it is
#: across Germany's width at 51 N (about 1210 km), so a pixel is about a cell
IMAGE_WIDTH = 1200

#: the longest a lead time of the RV forecast is, in minutes, and the step between two frames
FORECAST_MINUTES = 120
STEP_MINUTES = 5


@dataclass(frozen=True)
class RainClass:
    """A class of the rate of precipitation: from `lower` (included) to `upper` (excluded; none for the last), mm/h."""

    lower: float
    upper: float | None
    color: str

    @property
    def label(self) -> str:
        """Say the class in words, in English."""
        if self.upper is None:
            return f"{self.lower:g} {RATE_UNIT} and more"
        return f"{self.lower:g} to under {self.upper:g} {RATE_UNIT}"


#: the classes of the legend. Light to dark, as the rate rises: ColorBrewer's YlGnBu from its third step on, which is a
#: sequential ramp for a map that is safe for the three kinds of colour blindness, and whose lightness falls by
#: more than 6 (CIE L*) from one class to the next, so that the order reads in grey as well (held by a test). A rate
#: under the first lower bound is no class: transparent
RAIN_CLASSES: tuple[RainClass, ...] = (
    RainClass(0.1, 0.5, "#c7e9b4"),
    RainClass(0.5, 1.0, "#7fcdbb"),
    RainClass(1.0, 2.5, "#41b6c4"),
    RainClass(2.5, 5.0, "#1d91c0"),
    RainClass(5.0, 10.0, "#225ea8"),
    RainClass(10.0, 25.0, "#253494"),
    RainClass(25.0, None, "#081d58"),
)


class RadarFormatError(UpstreamError, ValueError):
    """Raised when a file of the RV composite is not what the decoder is written for: DWD changed it, or it is cut."""


@dataclass(frozen=True)
class PolarStereographic:
    """The ellipsoidal polar stereographic projection of the north pole, true to scale at `lat_ts`, in metres.

    Coordinates are relative to the pole (no false easting or northing): x to the east of the central meridian `lon_0`
    at the pole, y negative to the south of it. Written after Snyder, *Map Projections*, 21-33, 21-34 and 21-36 (the
    ratio `t` of the latitude, `m` of the standard parallel) and 3-5 for the iteration of the inverse.
    """

    lon_0: float
    lat_ts: float
    a: float
    b: float

    @property
    def _e(self) -> float:
        return math.sqrt(1 - (self.b / self.a) ** 2)

    def _t(self, phi: Any) -> Any:  # noqa: ANN401
        """Give Snyder's `t` of a latitude in radians: 0 at the pole, growing to the south (an array or a number)."""
        np = _numpy()
        e = self._e
        sin = np.sin(phi)
        return np.tan(math.pi / 4 - phi / 2) / ((1 - e * sin) / (1 + e * sin)) ** (e / 2)

    @property
    def _scale(self) -> float:
        """Give `a * m_c / t_c`, the metres a unit of `t` is, for the standard parallel."""
        phi_ts = math.radians(self.lat_ts)
        e = self._e
        m_c = math.cos(phi_ts) / math.sqrt(1 - (e * math.sin(phi_ts)) ** 2)
        return self.a * m_c / float(self._t(phi_ts))

    def radius(self, lat: Any) -> Any:  # noqa: ANN401
        """Give the distance from the pole of a latitude in degrees, in metres."""
        np = _numpy()
        return self._scale * self._t(np.radians(lat))

    def forward(self, lon: Any, lat: Any) -> tuple[Any, Any]:  # noqa: ANN401
        """Project a position in degrees: `(x, y)` in metres."""
        np = _numpy()
        rho = self.radius(lat)
        dlam = np.radians(np.asarray(lon) - self.lon_0)
        return rho * np.sin(dlam), -rho * np.cos(dlam)

    def inverse(self, x: Any, y: Any) -> tuple[Any, Any]:  # noqa: ANN401
        """Give the position `(lon, lat)` in degrees of a point in metres."""
        np = _numpy()
        e = self._e
        t = np.hypot(x, y) / self._scale
        phi = math.pi / 2 - 2 * np.arctan(t)
        for _ in range(8):
            sin = np.sin(phi)
            phi = math.pi / 2 - 2 * np.arctan(t * ((1 - e * sin) / (1 + e * sin)) ** (e / 2))
        lam = np.radians(self.lon_0) + np.arctan2(x, -y)
        return np.degrees(lam), np.degrees(phi)


def _numpy() -> Any:  # noqa: ANN401
    """Import numpy, which the `radar` extra installs with h5py (a module-level import would need it to import this)."""
    return import_optional("numpy", "Drawing the radar composite", extra="radar")


@dataclass(frozen=True)
class RvGrid:
    """The grid of a file: its projection, its size and where its upper-left corner is, in metres from the pole."""

    projection: PolarStereographic
    width: int
    height: int
    pixel_x: float
    pixel_y: float
    x_left: float
    y_top: float

    @classmethod
    def at(
        cls,
        *,
        projection: PolarStereographic,
        width: int,
        height: int,
        pixel_x: float,
        pixel_y: float,
        upper_left: tuple[float, float],
    ) -> RvGrid:
        """Make the grid whose outer upper-left corner is at `upper_left` (lon, lat in degrees)."""
        x_left, y_top = projection.forward(*upper_left)
        return cls(projection, width, height, pixel_x, pixel_y, float(x_left), float(y_top))

    def same_as(self, other: RvGrid, *, tolerance: float = 1.0) -> bool:
        """Tell whether two grids are one, the position of the corner within `tolerance` metres."""
        return (
            self.projection == other.projection
            and (self.width, self.height, self.pixel_x, self.pixel_y)
            == (other.width, other.height, other.pixel_x, other.pixel_y)
            and math.hypot(self.x_left - other.x_left, self.y_top - other.y_top) <= tolerance
        )

    def check_corners(self, corners: dict[str, tuple[float, float]], *, tolerance: float = 100.0) -> None:
        """Refuse a grid whose other corners are not where the file says they are (lon, lat in degrees), within metres.

        The upper-left corner is where the grid is anchored, so the other three say whether the projection, the size and
        the cell size are what they are taken for.
        """
        expected = {
            "UR": (self.x_left + self.width * self.pixel_x, self.y_top),
            "LL": (self.x_left, self.y_top - self.height * self.pixel_y),
            "LR": (self.x_left + self.width * self.pixel_x, self.y_top - self.height * self.pixel_y),
        }
        for name, (x, y) in expected.items():
            lon, lat = corners[name]
            got_x, got_y = self.projection.forward(lon, lat)
            if math.hypot(float(got_x) - x, float(got_y) - y) > tolerance:
                msg = f"the {name} corner of the grid is not where its size and cell size put it"
                raise RadarFormatError(msg)


#: the grid of the RV composite as DWD writes it into every file (`where/projdef` and the corner `UL_lat`, `UL_lon`),
#: the DE1200 grid in WGS84: 1100 x 1200 cells of 1 km. Known here so that where the image lies can be told before
#: a file is read; a file of another grid is refused
DE1200_PROJDEF = (
    "+proj=stere +lat_ts=60 +lat_0=90 +lon_0=10 +x_0=543196.83521776402 +y_0=3622588.8619310022 +units=m "
    "+a=6378137 +b=6356752.3142451802 +no_defs"
)
DE1200_UPPER_LEFT = (1.463301510256666, 55.862087108249824)


@lru_cache(maxsize=1)
def de1200() -> RvGrid:
    """Give the DE1200 grid of the RV composite."""
    return RvGrid.at(
        projection=_projection_of(DE1200_PROJDEF),
        width=1100,
        height=1200,
        pixel_x=1000.0,
        pixel_y=1000.0,
        upper_left=DE1200_UPPER_LEFT,
    )


def image_frame(width: int = IMAGE_WIDTH) -> ImageFrame:
    """Give where the image of the RV composite lies and how large it is, which every frame shares."""
    return warp_index(de1200(), width)[1]


@dataclass(frozen=True)
class ImageFrame:
    """Where an image lies: its bounds in WGS84 degrees, which are its outer edges, and its size in pixels."""

    west: float
    south: float
    east: float
    north: float
    width: int
    height: int


@dataclass(frozen=True)
class RvField:
    """What a file holds: the sums as stored, how to read them, the time they are of and the grid."""

    raw: np.ndarray
    gain: float
    offset: float
    nodata: float
    undetect: float
    start: dt.datetime
    end: dt.datetime
    grid: RvGrid
    corners: dict[str, tuple[float, float]]

    @property
    def seconds(self) -> float:
        """Give how long the precipitation summed in a cell fell: 300 s for the RV composite."""
        return (self.end - self.start).total_seconds()


@dataclass(frozen=True)
class RvImage:
    """A frame drawn: the PNG, the time it is valid at and where it lies."""

    png: bytes
    valid_time: dt.datetime
    frame: ImageFrame


def _text(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _datetime(date: object, time: object) -> dt.datetime:
    return dt.datetime.strptime(f"{_text(date)}{_text(time)}", "%Y%m%d%H%M%S").replace(tzinfo=dt.UTC)


def _projection_of(projdef: str) -> PolarStereographic:
    """Read the projection a file names, refusing any but the polar stereographic of the north pole."""
    options = dict(part.lstrip("+").partition("=")[::2] for part in projdef.split() if part.startswith("+"))
    not_polar = f"the projection {projdef!r} is not the polar stereographic of the north pole"
    if options.get("proj") != "stere" or options.get("units", "m") != "m":
        raise RadarFormatError(not_polar)
    try:
        latitude_of_origin = float(options["lat_0"])
        projection = PolarStereographic(
            lon_0=float(options["lon_0"]),
            lat_ts=float(options["lat_ts"]),
            a=float(options["a"]),
            b=float(options["b"]),
        )
    except (KeyError, ValueError) as e:
        msg = f"the projection {projdef!r} lacks what the decoder needs of it"
        raise RadarFormatError(msg) from e
    if latitude_of_origin != 90.0:
        raise RadarFormatError(not_polar)
    return projection


def _read_array(dataset: Any) -> np.ndarray:  # noqa: ANN401
    """Read a dataset whole: a dataset of one chunk that is only deflated is inflated here, any other by HDF5.

    DWD's grid is one chunk of 1200 x 1100 `uint32` that is deflated and nothing more. HDF5's own filter pipeline holds
    on to about the size of the grid on every read in some builds (h5py 3.16 with HDF5 2.0 on macOS grew by 5.7 MB a
    read, without end, for a server that reads a frame every few seconds); the chunk read as it is stored and inflated
    by zlib does not, and is faster. The inflated size is held to the size of the dataset, so that a file that
    inflates to more is no bomb.
    """
    np = _numpy()
    one_chunk = dataset.chunks is not None and tuple(dataset.chunks) == tuple(dataset.shape)
    if not (one_chunk and _only_deflated(dataset)):
        return dataset[()]
    expected = int(np.prod(dataset.shape)) * dataset.dtype.itemsize
    filter_mask, chunk = dataset.id.read_direct_chunk((0,) * dataset.ndim)
    if filter_mask:
        # a filter the writer skipped for this chunk: the bytes are not deflated, and HDF5 knows what they are
        return dataset[()]
    try:
        inflated = zlib.decompressobj().decompress(chunk, expected + 1)
    except zlib.error as e:
        msg = "the grid is cut short or is not deflated data"
        raise RadarFormatError(msg) from e
    if len(inflated) != expected:
        msg = f"the grid inflates to {len(inflated)} bytes, not the {expected} its shape and type say"
        raise RadarFormatError(msg)
    return np.frombuffer(inflated, dtype=dataset.dtype).reshape(dataset.shape)


def _only_deflated(dataset: Any) -> bool:  # noqa: ANN401
    """Tell whether the filters of a dataset are deflate and nothing else (no shuffle, checksum or scale-offset)."""
    h5py = import_optional("h5py", "Reading the radar composite", extra="radar")
    plist = dataset.id.get_create_plist()
    return plist.get_nfilters() == 1 and plist.get_filter(0)[0] == h5py.h5z.FILTER_DEFLATE


#: the most cells a grid may state: DE1200 has 1.3 million, and the decoder holds it in memory a few times over
_MAX_CELLS = 16_000_000


def _check_shape(dataset: Any, where: dict) -> None:  # noqa: ANN401
    """Refuse a dataset that is not the size the file states for its grid, before it is read.

    The size the file states is what the grid is read as: a dataset of another size is no grid of it.
    """
    stated = (int(where["ysize"]), int(where["xsize"]))
    if tuple(dataset.shape) != stated or dataset.size > _MAX_CELLS:
        msg = f"the data is of shape {tuple(dataset.shape)}, not the {stated[0]} x {stated[1]} the file states"
        raise RadarFormatError(msg)


def read_field(data: bytes | BytesIO) -> RvField:
    """Read a file of the RV composite (ODIM HDF5): the grid of sums and what is needed to read and place them.

    Raises:
        RadarFormatError: The file is not HDF5 that holds a precipitation sum on the grid the decoder is written for.
        MissingDependencyError: `h5py` or `numpy` is not installed (the `radar` extra).

    """
    h5py = import_optional("h5py", "Reading the radar composite", extra="radar")
    np = _numpy()
    try:
        with h5py.File(BytesIO(data) if isinstance(data, bytes) else data, "r") as f:
            where = dict(f["where"].attrs)
            dataset = f["dataset1/data1/data"]
            _check_shape(dataset, where)
            raw = _read_array(dataset)
            what = dict(f["dataset1/data1/what"].attrs)
            when = dict(f["dataset1/what"].attrs)
    except RadarFormatError:
        raise
    except (OSError, KeyError, ValueError, AttributeError, TypeError) as e:
        msg = "the file is not an ODIM HDF5 file with the precipitation of the RV composite"
        raise RadarFormatError(msg) from e
    quantity = _text(what.get("quantity", b""))
    if quantity != "ACRR":
        msg = f"the quantity {quantity!r} is not an accumulation (ACRR)"
        raise RadarFormatError(msg)
    try:
        corners = {
            name: (float(where[f"{name}_lon"]), float(where[f"{name}_lat"])) for name in ("UL", "UR", "LL", "LR")
        }
        grid = RvGrid.at(
            projection=_projection_of(_text(where["projdef"])),
            width=int(where["xsize"]),
            height=int(where["ysize"]),
            pixel_x=float(where["xscale"]),
            pixel_y=float(where["yscale"]),
            upper_left=corners["UL"],
        )
        field = RvField(
            raw=raw,
            gain=float(what["gain"]),
            offset=float(what["offset"]),
            nodata=float(what["nodata"]),
            undetect=float(what["undetect"]),
            start=_datetime(when["startdate"], when["starttime"]),
            end=_datetime(when["enddate"], when["endtime"]),
            grid=grid,
            corners=corners,
        )
    except RadarFormatError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        msg = "the file lacks what the decoder reads of an RV composite"
        raise RadarFormatError(msg) from e
    if raw.shape != (grid.height, grid.width) or not np.issubdtype(raw.dtype, np.integer):
        msg = f"the data is {raw.dtype} of shape {raw.shape}, not integers of {(grid.height, grid.width)}"
        raise RadarFormatError(msg)
    if field.seconds <= 0 or field.gain <= 0:
        msg = "the file states no length of time for its sums, or no gain"
        raise RadarFormatError(msg)
    grid.check_corners(corners)
    if not grid.same_as(de1200()):
        msg = "the grid is not the DE1200 grid, which the bounds that are announced before a file is read are those of"
        raise RadarFormatError(msg)
    return field


def footprint(grid: RvGrid) -> tuple[float, float, float, float]:
    """Give the bounds `(west, south, east, north)` in degrees of the lat/lon box that holds the grid."""
    np = _numpy()
    along_x = np.linspace(grid.x_left, grid.x_left + grid.width * grid.pixel_x, grid.width + 1)
    along_y = np.linspace(grid.y_top, grid.y_top - grid.height * grid.pixel_y, grid.height + 1)
    x = np.concatenate([along_x, along_x, np.full_like(along_y, along_x[0]), np.full_like(along_y, along_x[-1])])
    y = np.concatenate([np.full_like(along_x, along_y[0]), np.full_like(along_x, along_y[-1]), along_y, along_y])
    lon, lat = grid.projection.inverse(x, y)
    return float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())


def _mercator_y(lat: Any) -> Any:  # noqa: ANN401
    """Give the Web Mercator ordinate of a latitude in degrees, in radians of the sphere."""
    np = _numpy()
    return np.arcsinh(np.tan(np.radians(lat)))


@lru_cache(maxsize=4)
def warp_index(grid: RvGrid, width: int = IMAGE_WIDTH) -> tuple[np.ndarray, ImageFrame]:
    """Work out which cell of the grid each pixel of the image takes, and where the image lies.

    The image is as wide as `width` pixels across the longitudes of the grid's box and as high as makes its pixels
    square in Web Mercator, and its bounds are those of that grid. The index is flat (row * width + column of the
    grid), and `grid.width * grid.height` for a pixel that is outside the grid, which a zero is appended for.
    """
    np = _numpy()
    west, south, east, north = footprint(grid)
    step = math.radians(east - west) / width
    y_north = float(_mercator_y(north))
    height = round((y_north - float(_mercator_y(south))) / step)
    # the south of the image is the one its whole pixels reach, which is the grid's south to within one pixel
    south = math.degrees(math.atan(math.sinh(y_north - height * step)))
    lon = west + (np.arange(width) + 0.5) * math.degrees(step)
    lat = np.degrees(np.arctan(np.sinh(y_north - (np.arange(height) + 0.5) * step)))
    # a pixel's centre is projected by its parallel (the radius) and its meridian (the angle) apart: no trigonometry of
    # the whole image
    rho = grid.projection.radius(lat)
    sin, cos = np.sin(np.radians(lon - grid.projection.lon_0)), np.cos(np.radians(lon - grid.projection.lon_0))
    outside = grid.width * grid.height
    index = np.empty((height, width), dtype=np.int32)
    # a band of rows at a time, which holds the working arrays (8 bytes a pixel each) to a few MB
    for first in range(0, height, 128):
        band = slice(first, first + 128)
        x = rho[band, None] * sin[None, :]
        y = -rho[band, None] * cos[None, :]
        column = np.floor((x - grid.x_left) / grid.pixel_x).astype(np.int32)
        row = np.floor((grid.y_top - y) / grid.pixel_y).astype(np.int32)
        inside = (column >= 0) & (column < grid.width) & (row >= 0) & (row < grid.height)
        index[band] = np.where(inside, row * grid.width + column, outside)
    return index, ImageFrame(west=west, south=south, east=east, north=north, width=width, height=height)


def classify(field: RvField) -> np.ndarray:
    """Sort the sums of a field into the classes: 0 for no class (no rain, or no data), 1 up for `RAIN_CLASSES`."""
    np = _numpy()
    # rate (mm/h) = (raw * gain + offset) * 3600 / seconds >= lower
    #   <=>  raw >= (lower * seconds / 3600 - offset) / gain
    thresholds = np.array([(c.lower * field.seconds / 3600 - field.offset) / field.gain for c in RAIN_CLASSES])
    classes = np.searchsorted(thresholds, field.raw, side="right").astype(np.uint8)
    classes[field.raw == field.nodata] = 0
    classes[field.raw == field.undetect] = 0
    return classes


def draw(field: RvField, *, width: int = IMAGE_WIDTH) -> RvImage:
    """Draw a field as the indexed PNG of Web Mercator described in the module."""
    np = _numpy()
    # the grid of the file is DE1200 (`read_field` refused any other), whose image is the one announced
    index, frame = warp_index(de1200(), width)
    classes = np.append(classify(field).ravel(), np.uint8(0))
    pixels = classes[index]
    palette = [(0, 0, 0), *(_rgb(c.color) for c in RAIN_CLASSES)]
    return RvImage(png=encode_png(pixels, palette), valid_time=field.end, frame=frame)


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def encode_png(pixels: np.ndarray, palette: list[tuple[int, int, int]]) -> bytes:
    """Encode a 2-D `uint8` array of palette indexes as an 8-bit indexed PNG whose index 0 is fully transparent."""
    np = _numpy()
    height, width = pixels.shape
    # every row is sent with the filter byte 0 (none): the rows are long runs of the same index, which deflate takes
    scanlines = np.concatenate([np.zeros((height, 1), dtype=np.uint8), pixels], axis=1)
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)),
            _chunk(b"PLTE", bytes(channel for colour in palette for channel in colour)),
            _chunk(b"tRNS", bytes([0] + [255] * (len(palette) - 1))),
            _chunk(b"IDAT", zlib.compress(scanlines.tobytes(), 6)),
            _chunk(b"IEND", b""),
        )
    )
