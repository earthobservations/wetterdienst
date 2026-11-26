# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The zoom and centre of the station map hold every station in the picture (GH-3373).

Read off the projection of the chart, not off pixels. The map is 512 * 2 ** zoom pixels wide for the whole world,
which are 360 degrees of longitude and 2 pi of Mercator northing, and Vega's projection is given its scale, the
pixels of a radian, instead of the zoom.
"""

import datetime as dt
import math
import struct
from types import SimpleNamespace
from typing import Any

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.model import result as result_module
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.dwd.observation import DwdObservationRequest

_WIDTH, _HEIGHT = 700, 500


def _result(points: list[tuple[float, float]]) -> StationsResult:
    rows = [
        {
            "resolution": "hourly",
            "dataset": "temperature_air",
            "station_id": f"{index:05d}",
            "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
            "end_timestamp": None,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": 10.0,
            "name": f"Station {index}",
            "region": "Berlin",
        }
        for index, (latitude, longitude) in enumerate(points)
    ]
    df = pl.DataFrame(rows, schema=STATIONS_SCHEMA)
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_2m")], settings=Settings(cache_disable=True)
    )
    return StationsResult(request=request, df=df, _df_all=df, _stations_filter=StationsFilter.BY_STATION_ID)


def _northing(latitude: float) -> float:
    return math.asinh(math.tan(math.radians(latitude)))


def _view(chart: Any) -> SimpleNamespace:  # noqa: ANN401
    """Read the centre and the zoom the map was fitted to off the projection of the chart."""
    projection = chart.to_dict()["projection"]
    lon, lat = projection["center"]
    return SimpleNamespace(lat=lat, lon=lon, zoom=math.log2(projection["scale"] * 2 * math.pi / 512))


def _offsets(
    view: SimpleNamespace, points: list[tuple[float, float]], width: int, height: int
) -> list[tuple[float, float]]:
    """Pixels of each point right of and below the middle of the map, as the projection lays it out."""
    margin = result_module._MAP_MARGIN  # noqa: SLF001
    map_width = width - margin["l"] - margin["r"]
    map_height = height - margin["t"] - margin["b"]
    pixels = 512 * 2**view.zoom
    return [
        (
            (lon - view.lon) / 360 * pixels / (map_width / 2),
            (_northing(view.lat) - _northing(lat)) / (2 * math.pi) * pixels / (map_height / 2),
        )
        for lat, lon in points
    ]


def _square(span: float, latitude: float = 50.0, longitude: float = 10.0) -> list[tuple[float, float]]:
    """Four stations in the corners of a box of `span` degrees of latitude and as many of longitude."""
    half = span / 2
    return [(latitude + sign_lat * half, longitude + sign_lon * half) for sign_lat in (-1, 1) for sign_lon in (-1, 1)]


@pytest.fixture(autouse=True)
def _altair() -> None:
    pytest.importorskip("altair")


@pytest.mark.parametrize("span", [0.1, 1, 5, 20, 60])
def test_every_station_is_in_the_map_and_the_map_is_not_far_wider_than_they_are(span: float) -> None:
    """Whatever the extent of the stations, their box fills most of the map, and none of them is outside it.

    The zoom was `12 - lat_diff`, which cropped every station out of a region below about 6 degrees.
    """
    points = _square(span)
    view = _view(_result(points).to_plot())
    offsets = _offsets(view, points, _WIDTH, _HEIGHT)
    fill = max(max(abs(x), abs(y)) for x, y in offsets)
    assert fill <= 0.86  # in the map, with room for the labels
    if span >= 5:
        # not capped by the zoom of a single station: the box is what the zoom is fitted to
        assert fill >= 0.8


@pytest.mark.parametrize(
    ("name", "points"),
    [
        # the stations of the report of GH-3373: within 25 km of Berlin and within 60 km of Munich
        ("berlin", [(52.52, 13.405), (52.47, 13.40), (52.38, 13.53), (52.57, 13.31), (52.45, 13.30), (52.60, 13.49)]),
        ("munich", [(48.14, 11.58), (47.9, 11.1), (48.6, 12.2), (47.9, 12.0), (48.5, 11.0)]),
        ("germany", [(54.5, 8.5), (47.7, 9.0), (51.1, 6.0), (51.3, 14.9), (48.1, 11.6), (53.6, 10.0)]),
        ("world", [(60.0, 24.9), (-33.9, 151.2), (40.7, -74.0), (-34.6, -58.4), (28.6, 77.2)]),
        ("southern", [(-54.8, -68.3), (-33.9, 18.4), (-77.8, 166.7)]),
    ],
)
def test_the_stations_of_a_real_region_are_all_in_the_map(name: str, points: list[tuple[float, float]]) -> None:
    """A town, a metropolitan region, a country, the world, and the southern hemisphere."""
    view = _view(_result(points).to_plot())
    offsets = _offsets(view, points, _WIDTH, _HEIGHT)
    assert max(max(abs(x), abs(y)) for x, y in offsets) <= 0.86, name


def test_a_single_station_is_the_centre_of_a_map_of_a_town() -> None:
    """There is no extent to fit: the map is centred on the station, at a zoom a town fits in."""
    view = _view(_result([(52.52, 13.405)]).to_plot())
    assert view.lat == pytest.approx(52.52)
    assert view.lon == pytest.approx(13.405)
    assert view.zoom == pytest.approx(10)


def test_stations_on_one_parallel_or_one_meridian_are_fitted_by_the_direction_they_spread_in() -> None:
    """The extent is zero in the other direction, which must neither fail nor limit the zoom."""
    for points in ([(50.0, 5.0), (50.0, 15.0)], [(45.0, 10.0), (55.0, 10.0)]):
        view = _view(_result(points).to_plot())
        assert max(max(abs(x), abs(y)) for x, y in _offsets(view, points, _WIDTH, _HEIGHT)) == pytest.approx(
            0.85, abs=0.01
        )


def test_stations_at_the_poles_are_fitted_too() -> None:
    """Mercator has no latitude 90: the map reaches its edge at 85 degrees, which is where the zoom is fitted."""
    points = [(-90.0, 0.0), (90.0, 0.0)]
    view = _view(_result(points).to_plot())
    assert 0 <= view.zoom < 1
    assert math.isfinite(view.lat)


def test_the_center_is_the_middle_of_the_box_as_the_map_draws_it() -> None:
    """The latitudes are not evenly spaced in the map: the middle between 20 and 80 degrees is not 50."""
    view = _view(_result(_square(60.0)).to_plot())
    assert view.lon == pytest.approx(10.0)
    assert view.lat > 50.0
    assert _northing(view.lat) == pytest.approx((_northing(20.0) + _northing(80.0)) / 2)


def test_a_picture_of_another_size_is_fitted_to_its_size(monkeypatch: pytest.MonkeyPatch) -> None:
    """The zoom for the default size would crop a smaller picture: `width` and `height` fit the map again."""
    pytest.importorskip("vl_convert")
    drawn: list[Any] = []

    def render_image(chart: Any, *_args: object, **_kwargs: object) -> bytes:  # noqa: ANN401
        drawn.append(_view(chart))
        return b""

    monkeypatch.setattr(result_module, "render_image", render_image)
    points = _square(5.0)
    result = _result(points)
    result.to_image(fmt="png", width=300, height=300)
    result.to_image(fmt="png", width=1600, height=1000)
    result.to_image(fmt="png")
    small, wide, default = drawn
    for view, width, height in ((small, 300, 300), (wide, 1600, 1000)):
        offsets = _offsets(view, points, width, height)
        assert 0.8 <= max(max(abs(x), abs(y)) for x, y in offsets) <= 0.86
    assert default.zoom == _view(result.to_plot()).zoom
    assert small.zoom < default.zoom < wide.zoom


@pytest.mark.parametrize(("width", "height"), [(20, 40), (1, 1), (700, 20)])
def test_a_picture_smaller_than_its_margins_is_still_drawn(width: int, height: int) -> None:
    """No map is left at a width of 20 pixels, and the zoom is a number, not a `ValueError` of `log2`.

    The picture is drawn, and is as large as asked.
    """
    pytest.importorskip("vl_convert")
    png = _result(_square(5.0)).to_image(fmt="png", width=width, height=height)
    assert isinstance(png, bytes)
    assert struct.unpack(">II", png[16:24]) == (width, height)
