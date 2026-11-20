# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The RV composite of DWD decoded and drawn as a map image (GH-3788), from a real file of 2026-11-19."""

# ruff: noqa: SLF001  (the reading of a grid is a private function with its own cases)

from __future__ import annotations

import datetime as dt
import itertools
import math
import shutil
import struct
import zlib
from io import BytesIO
from typing import TYPE_CHECKING

import h5py
import numpy as np
import pytest

from tests.provider.dwd.radar.rv_stub import FIXTURE, FIXTURE_TIME
from wetterdienst.exceptions import UpstreamError
from wetterdienst.provider.dwd.radar import rv

if TYPE_CHECKING:
    from pathlib import Path

#: Germany's cities, which a frame has to put where they are
CITIES = {
    "Berlin": (13.405, 52.520),
    "Hamburg": (9.994, 53.551),
    "Munich": (11.582, 48.135),
    "Cologne": (6.960, 50.938),
    "Dresden": (13.738, 51.050),
    "Kiel": (10.135, 54.323),
    "Freiburg": (7.849, 47.999),
}


@pytest.fixture(scope="module")
def data() -> bytes:
    """Give the real file."""
    return FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def field(data: bytes) -> rv.RvField:
    """Give the real file read."""
    return rv.read_field(data)


# --- the file -------------------------------------------------------------------------------------------------------


def test_a_real_file_is_read_with_the_time_and_the_length_of_its_sums(field: rv.RvField) -> None:
    """The sums are those of the 5 minutes that end at the time of the file, which is the time of its run."""
    assert field.end == FIXTURE_TIME
    assert field.start == FIXTURE_TIME - dt.timedelta(minutes=5)
    assert field.seconds == 300
    assert field.raw.shape == (1200, 1100)
    assert field.raw.dtype == np.uint32
    assert field.grid.same_as(rv.de1200())


def test_the_four_corners_of_the_file_are_where_the_projection_puts_the_grid(field: rv.RvField) -> None:
    """DWD writes the outer corners of the grid in degrees: the grid anchored at one is at the other three to the metre.

    The projection is written in this package, so this is what holds it to DWD's own numbers.
    """
    grid = field.grid
    corners = {
        "UL": (grid.x_left, grid.y_top),
        "UR": (grid.x_left + grid.width * grid.pixel_x, grid.y_top),
        "LL": (grid.x_left, grid.y_top - grid.height * grid.pixel_y),
        "LR": (grid.x_left + grid.width * grid.pixel_x, grid.y_top - grid.height * grid.pixel_y),
    }
    for name, (x, y) in corners.items():
        lon, lat = grid.projection.inverse(x, y)
        assert (float(lon), float(lat)) == pytest.approx(field.corners[name], abs=1e-6), name


def test_the_projection_is_proj(field: rv.RvField) -> None:
    """The projection written here agrees with PROJ to a micrometre, forward and back, over the whole of Germany."""
    pyproj = pytest.importorskip("pyproj")
    p = field.grid.projection
    proj = pyproj.Transformer.from_crs(
        "EPSG:4326",
        f"+proj=stere +lat_ts={p.lat_ts} +lat_0=90 +lon_0={p.lon_0} +a={p.a} +b={p.b} +units=m",
        always_xy=True,
    )
    rng = np.random.default_rng(3788)
    lon, lat = rng.uniform(1.0, 19.0, 500), rng.uniform(45.0, 56.5, 500)
    x, y = p.forward(lon, lat)
    expected_x, expected_y = proj.transform(lon, lat)
    assert np.abs(x - expected_x).max() < 1e-6
    assert np.abs(y - expected_y).max() < 1e-6
    back_lon, back_lat = p.inverse(x, y)
    assert np.abs(back_lon - lon).max() < 1e-9
    assert np.abs(back_lat - lat).max() < 1e-9


def test_a_single_deflated_chunk_is_inflated_here_and_is_what_hdf5_reads(data: bytes) -> None:
    """The fast path reads the same numbers as HDF5 does, which it is there to avoid for the leak of its filters."""
    with h5py.File(BytesIO(data), "r") as f:
        dataset = f["dataset1/data1/data"]
        assert dataset.chunks == dataset.shape
        assert dataset.compression == "gzip"
        assert (rv._read_array(dataset) == dataset[()]).all()


def test_any_other_layout_is_left_to_hdf5(tmp_path: Path) -> None:
    """A dataset that is no single deflated chunk (a contiguous or a shuffled one) is read as HDF5 reads it."""
    values = np.arange(60, dtype=np.uint32).reshape(6, 10)
    with h5py.File(tmp_path / "other.h5", "w") as f:
        f.create_dataset("contiguous", data=values)
        f.create_dataset("shuffled", data=values, chunks=(6, 10), compression="gzip", shuffle=True)
        f.create_dataset("chunked", data=values, chunks=(3, 5), compression="gzip")
        for name in ("contiguous", "shuffled", "chunked"):
            assert (rv._read_array(f[name]) == values).all(), name


def test_a_chunk_that_inflates_to_more_than_the_dataset_is_refused(tmp_path: Path) -> None:
    """The size of the inflated chunk is held to the size of the dataset: a file made to be a bomb is no frame."""
    with h5py.File(tmp_path / "bomb.h5", "w") as f:
        dataset = f.create_dataset("grid", shape=(100, 100), dtype=np.uint32, chunks=(100, 100), compression="gzip")
        dataset[...] = 0
        _, chunk = dataset.id.read_direct_chunk((0, 0))
        # the same chunk, a dataset that says it is smaller
        small = f.create_dataset("small", shape=(10, 10), dtype=np.uint32, chunks=(10, 10), compression="gzip")
        small.id.write_direct_chunk((0, 0), chunk)
        with pytest.raises(rv.RadarFormatError, match="inflates"):
            rv._read_array(small)


def _edit(tmp_path: Path, edit: object) -> bytes:
    path = tmp_path / "edited.hd5"
    shutil.copyfile(FIXTURE, path)
    with h5py.File(path, "r+") as f:
        edit(f)  # ty: ignore[call-non-callable]
    return path.read_bytes()


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda f: f["dataset1/data1/what"].attrs.__setitem__("quantity", b"DBZH"), "not an accumulation"),
        (lambda f: f["where"].attrs.__setitem__("UL_lat", 54.0), "corner"),
        (lambda f: f["where"].attrs.__setitem__("projdef", b"+proj=longlat +datum=WGS84"), "projection"),
        (lambda f: f["where"].attrs.__setitem__("projdef", b"+proj=stere +lat_0=90"), "lacks"),
        (lambda f: f["dataset1/what"].attrs.__setitem__("starttime", b"211000"), "no length of time"),
        (lambda f: f["where"].attrs.__delitem__("xscale"), "lacks"),
    ],
    ids=["quantity", "corner", "projection", "projection-incomplete", "no-duration", "no-scale"],
)
def test_a_file_the_decoder_is_not_written_for_is_refused(tmp_path: Path, edit: object, message: str) -> None:
    """DWD changing the file is a 502 that says what changed, never a wrong picture."""
    with pytest.raises(rv.RadarFormatError, match=message):
        rv.read_field(_edit(tmp_path, edit))


def test_a_grid_that_is_not_de1200_is_refused(tmp_path: Path) -> None:
    """The bounds that are announced before a file is read are those of DE1200: a file of another grid is not drawn."""

    def move(f: h5py.File) -> None:
        # the same grid a kilometre further on: its corners agree with each other, and not with DE1200
        for corner in ("UL", "UR", "LL", "LR"):
            f["where"].attrs[f"{corner}_lat"] = f["where"].attrs[f"{corner}_lat"] + 0.02

    with pytest.raises(rv.RadarFormatError):
        rv.read_field(_edit(tmp_path, move))


@pytest.mark.parametrize("content", [b"", b"not hdf5", b"\x89HDF\r\n\x1a\n" + b"\x00" * 64])
def test_bytes_that_are_no_hdf5_are_a_format_error(content: bytes) -> None:
    """A file that is cut or is not one is an `UpstreamError` (a 502), not an exception of h5py."""
    with pytest.raises(rv.RadarFormatError) as excinfo:
        rv.read_field(content)
    assert isinstance(excinfo.value, UpstreamError)


# --- the classes ----------------------------------------------------------------------------------------------------


def test_the_classes_are_ordered_and_adjacent() -> None:
    """Each class begins where the one below ends, and the last has no end."""
    for lower, upper in zip(rv.RAIN_CLASSES, rv.RAIN_CLASSES[1:], strict=False):
        assert lower.upper == upper.lower
    assert rv.RAIN_CLASSES[-1].upper is None
    assert [c.label for c in rv.RAIN_CLASSES][:2] == ["0.1 to under 0.5 mm/h", "0.5 to under 1 mm/h"]
    assert rv.RAIN_CLASSES[-1].label == "25 mm/h and more"


def _lightness(color: str) -> float:
    """Give CIE L* of an sRGB colour written `#rrggbb`."""

    def linear(channel: int) -> float:
        c = channel / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(int(color[i : i + 2], 16)) for i in (1, 3, 5))
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    f = y ** (1 / 3) if y > (6 / 29) ** 3 else y / (3 * (6 / 29) ** 2) + 4 / 29
    return 116 * f - 16


def test_the_legend_reads_as_one_ramp_of_falling_lightness() -> None:
    """The order of the classes is the order of their lightness, by 6 or more: it reads in grey and for any eye.

    A ramp that differs in lightness only does not depend on hue to be told apart, which is what a colour-blind reader
    lacks; the lightest class is visible on a light map and the darkest is not black.
    """
    lightness = [_lightness(c.color) for c in rv.RAIN_CLASSES]
    steps = [a - b for a, b in itertools.pairwise(lightness)]
    assert all(step >= 6 for step in steps), lightness
    assert lightness[0] < 90
    assert lightness[-1] > 5


def _field(raw: np.ndarray, *, seconds: int = 300) -> rv.RvField:
    """Make a field of the sums `raw`, as DWD scales them (a gain of 0.001 and an offset of -0.001, 0 undetected)."""
    start = FIXTURE_TIME - dt.timedelta(seconds=seconds)
    return rv.RvField(
        raw=raw,
        gain=0.001,
        offset=-0.001,
        nodata=4294967295.0,
        undetect=0.0,
        start=start,
        end=FIXTURE_TIME,
        grid=rv.de1200(),
        corners={},
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0),  # 0 is what DWD writes for no rain detected
        (1, 0),  # the smallest sum there is is 0 mm: (1 * 0.001 - 0.001)
        (9, 0),  # 0.096 mm/h
        (10, 1),  # 0.108
        (42, 1),  # 0.492
        (43, 2),  # 0.504
        (84, 2),  # 0.996
        (85, 3),  # 1.008
        (209, 3),  # 2.496
        (210, 4),  # 2.508
        (417, 4),  # 4.992
        (418, 5),  # 5.004
        (834, 5),  # 9.996
        (835, 6),  # 10.008
        (2084, 6),  # 24.996
        (2085, 7),  # 25.008
        (4294967294, 7),  # the largest sum that is a sum
        (4294967295, 0),  # what DWD writes for no data
    ],
)
def test_a_sum_is_the_class_whose_bounds_its_rate_is_between(raw: int, expected: int) -> None:
    """A sum of 5 minutes is a rate in mm/h (x 12), the lower bound of a class is in the class, and no data is none."""
    assert int(rv.classify(_field(np.array([[raw]], dtype=np.uint32)))[0, 0]) == expected


def test_the_length_of_the_sums_is_the_one_the_file_states() -> None:
    """The same sum is a lower rate the longer the time it fell in, which the file says: it is not 5 minutes by name."""
    raw = np.array([[1002]], dtype=np.uint32)  # 1.001 mm
    assert int(rv.classify(_field(raw, seconds=300))[0, 0]) == 6  # 12 mm/h
    assert int(rv.classify(_field(raw, seconds=600))[0, 0]) == 5  # 6 mm/h
    assert int(rv.classify(_field(raw, seconds=3600))[0, 0]) == 3  # 1 mm/h


# --- the image ------------------------------------------------------------------------------------------------------


def _decode_png(png: bytes) -> tuple[int, int, list[tuple[int, int, int]], list[int], np.ndarray]:
    """Read an indexed PNG as the standard says, apart from the encoder: size, palette, alpha and the indexes."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    position, chunks, idat = 8, {}, b""
    while position < len(png):
        (length,) = struct.unpack(">I", png[position : position + 4])
        kind = png[position + 4 : position + 8]
        payload = png[position + 8 : position + 8 + length]
        (crc,) = struct.unpack(">I", png[position + 8 + length : position + 12 + length])
        assert zlib.crc32(kind + payload) == crc, kind
        if kind == b"IDAT":
            idat += payload
        else:
            chunks[kind] = payload
        position += 12 + length
    width, height, depth, colour_type, _, _, interlace = struct.unpack(">IIBBBBB", chunks[b"IHDR"])
    assert (depth, colour_type, interlace) == (8, 3, 0)
    palette = [tuple(chunks[b"PLTE"][i : i + 3]) for i in range(0, len(chunks[b"PLTE"]), 3)]
    rows = np.frombuffer(zlib.decompress(idat), dtype=np.uint8).reshape(height, width + 1)
    assert (rows[:, 0] == 0).all()
    return width, height, palette, list(chunks[b"tRNS"]), rows[:, 1:]


def test_a_frame_is_an_indexed_png_that_is_transparent_where_there_is_nothing(field: rv.RvField) -> None:
    """The picture is the classes of the file, warped: the colours of the legend, and index 0 fully transparent."""
    image = rv.draw(field)
    width, height, palette, alpha, pixels = _decode_png(image.png)

    assert (width, height) == (image.frame.width, image.frame.height) == (1200, 1169)
    assert palette[1:] == [
        (int(c.color[1:3], 16), int(c.color[3:5], 16), int(c.color[5:7], 16)) for c in rv.RAIN_CLASSES
    ]
    assert alpha == [0] + [255] * len(rv.RAIN_CLASSES)
    assert image.valid_time == FIXTURE_TIME
    counts = np.bincount(pixels.ravel(), minlength=8).tolist()
    # the rain of 2026-11-19 21:10 UTC, by class: the cells of the file are 1 km and a pixel of the image is 1.0 km at
    # 51 N and less to the north, so the pixels are a little fewer than the cells in the rain's classes, in the same
    # proportions (a regression of the decoding, the warp or the classes moves these)
    assert counts == [1282093, 66628, 24669, 22421, 6148, 834, 7, 0]


def test_a_frame_has_no_rain_outside_the_composite(field: rv.RvField) -> None:
    """The pixels that no cell of the grid holds are transparent, and the grid does not fill its box: they exist."""
    index, frame = rv.warp_index(field.grid)
    outside = field.grid.width * field.grid.height
    assert 0 < (index == outside).sum() < index.size * 0.5
    assert index.shape == (frame.height, frame.width)
    pixels = _decode_png(rv.draw(field).png)[4]
    assert (pixels[index == outside] == 0).all()


def test_the_bounds_are_the_box_of_the_grid_of_dwd(field: rv.RvField) -> None:
    """The west and the east are the longitudes of the upper corners DWD writes, which are the extremes of the grid."""
    frame = rv.image_frame()
    assert frame.west == pytest.approx(field.corners["UL"][0], abs=1e-9)
    assert frame.east == pytest.approx(field.corners["UR"][0], abs=1e-9)
    # the south is that of the lower corners, to the pixel the rows are whole in
    assert frame.south == pytest.approx(min(field.corners["LL"][1], field.corners["LR"][1]), abs=0.05)
    assert frame.north > field.corners["UL"][1]
    assert frame == rv.warp_index(field.grid)[1]


def _mercator_y(lat: float) -> float:
    return math.asinh(math.tan(math.radians(lat)))


@pytest.mark.parametrize("city", sorted(CITIES))
def test_a_pixel_of_the_image_is_the_cell_of_its_place(field: rv.RvField, city: str) -> None:
    """Put a city where a Leaflet overlay puts it, in the image whose bounds are given: the cell is that of the city.

    A browser stretches the image linearly in longitude and in Web Mercator `y` between `bounds`, so the pixel of a
    place is found that way; the cell the pixel takes is then taken apart by the inverse projection, and it must be the
    place: within the diagonal of a cell and a pixel, which are 1 km.
    """
    lon, lat = CITIES[city]
    index, frame = rv.warp_index(field.grid)
    column = int((lon - frame.west) / (frame.east - frame.west) * frame.width)
    top, bottom = _mercator_y(frame.north), _mercator_y(frame.south)
    row = int((top - _mercator_y(lat)) / (top - bottom) * frame.height)
    cell = int(index[row, column])
    assert cell < field.grid.width * field.grid.height, city
    cell_row, cell_column = divmod(cell, field.grid.width)
    grid = field.grid
    x = grid.x_left + (cell_column + 0.5) * grid.pixel_x
    y = grid.y_top - (cell_row + 0.5) * grid.pixel_y
    cell_lon, cell_lat = grid.projection.inverse(x, y)
    to_km = math.cos(math.radians(lat)) * 111.32
    distance = math.hypot((float(cell_lon) - lon) * to_km, (float(cell_lat) - lat) * 111.2)
    assert distance < 1.2, (city, distance)


def test_the_pixels_are_square_in_web_mercator() -> None:
    """The image is as high as makes its pixels square where a map stretches it, which is what `bounds` assumes."""
    frame = rv.image_frame()
    pixel_x = math.radians(frame.east - frame.west) / frame.width
    pixel_y = (_mercator_y(frame.north) - _mercator_y(frame.south)) / frame.height
    assert pixel_y == pytest.approx(pixel_x, rel=1e-9)


def test_the_png_encoder_round_trips() -> None:
    """What is written is read back by a decoder that shares nothing with it, for a size that is not a power of two."""
    pixels = (np.arange(7 * 13, dtype=np.uint8) % 4).reshape(7, 13)
    png = rv.encode_png(pixels, [(0, 0, 0), (1, 2, 3), (4, 5, 6), (7, 8, 9)])
    width, height, palette, alpha, decoded = _decode_png(png)
    assert (width, height) == (13, 7)
    assert palette == [(0, 0, 0), (1, 2, 3), (4, 5, 6), (7, 8, 9)]
    assert alpha == [0, 255, 255, 255]
    assert (decoded == pixels).all()


def test_pillow_reads_the_png_as_a_transparent_image(field: rv.RvField) -> None:
    """An image library that browsers' decoders are written like agrees: RGBA, transparent where index 0."""
    image_module = pytest.importorskip("PIL.Image")
    image = rv.draw(field)
    with image_module.open(BytesIO(image.png)) as picture:
        assert picture.size == (image.frame.width, image.frame.height)
        rgba = np.asarray(picture.convert("RGBA"))
    pixels = _decode_png(image.png)[4]
    assert (rgba[..., 3][pixels == 0] == 0).all()
    assert (rgba[..., 3][pixels > 0] == 255).all()


def test_a_chunk_that_is_not_deflated_data_is_a_format_error_and_not_a_zlib_one(tmp_path: Path) -> None:
    """A corrupted chunk is DWD's file being wrong (a 502), whatever zlib makes of it."""
    values = np.arange(100, dtype=np.uint32).reshape(10, 10)
    with h5py.File(tmp_path / "corrupt.h5", "w") as f:
        dataset = f.create_dataset("grid", data=values, chunks=(10, 10), compression="gzip")
        _, chunk = dataset.id.read_direct_chunk((0, 0))
        dataset.id.write_direct_chunk((0, 0), b"\x00" * len(chunk))
        with pytest.raises(rv.RadarFormatError):
            rv._read_array(dataset)
        dataset.id.write_direct_chunk((0, 0), chunk[: len(chunk) // 2])
        with pytest.raises(rv.RadarFormatError):
            rv._read_array(dataset)


def test_a_chunk_the_writer_did_not_deflate_is_left_to_hdf5(tmp_path: Path) -> None:
    """A filter mask that is not 0 says a filter was skipped for the chunk: HDF5 reads it, as it is not deflated."""
    values = np.arange(100, dtype=np.uint32).reshape(10, 10)
    with h5py.File(tmp_path / "skipped.h5", "w") as f:
        dataset = f.create_dataset("grid", data=values, chunks=(10, 10), compression="gzip")
        assert rv._read_array(dataset).tolist() == values.tolist()
        read_whole = []

        class Spy:
            """The dataset, which says it was read whole by HDF5."""

            def __init__(self) -> None:
                self.id = type(
                    "Id",
                    (),
                    {
                        "read_direct_chunk": staticmethod(lambda _offset: (1, b"not deflated")),
                        "get_create_plist": dataset.id.get_create_plist,
                    },
                )()

            def __getattr__(self, name: str) -> object:
                return getattr(dataset, name)

            def __getitem__(self, key: object) -> np.ndarray:
                read_whole.append(key)
                return dataset[key]

        assert rv._read_array(Spy()).tolist() == values.tolist()
        assert read_whole


def test_a_grid_of_another_size_than_the_file_states_is_refused_before_it_is_read(tmp_path: Path) -> None:
    """The shape of the dataset is held to `xsize` and `ysize` of the file, as the corners are held to the grid."""
    with pytest.raises(rv.RadarFormatError, match=r"not the 1200 x 1000 the file states"):
        rv.read_field(_edit(tmp_path, lambda f: f["where"].attrs.__setitem__("xsize", 1000)))


@pytest.mark.parametrize(
    "edit",
    [
        lambda f: f["where"].attrs.__setitem__("xsize", "wide"),
        lambda f: f["where"].attrs.__setitem__("projdef", 7),
        lambda f: f["dataset1/what"].attrs.__setitem__("endtime", b"nine"),
    ],
    ids=["size-text", "projdef-number", "time-text"],
)
def test_a_file_whose_attributes_are_of_another_type_is_a_format_error(tmp_path: Path, edit: object) -> None:
    """A malformed attribute is DWD's file being wrong (a 502), whatever Python makes of it."""
    with pytest.raises(rv.RadarFormatError):
        rv.read_field(_edit(tmp_path, edit))
