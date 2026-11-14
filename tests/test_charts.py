# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The charts of the results, drawn with Altair and rendered by vl-convert (GH-3238).

The images are held to what a caller asks of them, not to their pixels: their format, their size, the data they hold
and what they are drawn from. A snapshot of pixels would hold the fonts and the rasteriser of the machine that wrote
it; the text is set in the Liberation Sans that vl-convert carries, so the output does not depend on the system's
fonts, but nothing here holds the anti-aliasing of two architectures to the same bytes.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import struct
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from importlib import resources
from typing import Any

import polars as pl
import pytest

from tests.model.test_results import _stations, _stations_frame, _values_frame
from wetterdienst import Settings
from wetterdienst.exceptions import MissingDependencyError, UnknownFormatError
from wetterdienst.io import charts
from wetterdienst.io.export import chart_to_html, render_image
from wetterdienst.model.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
    ValuesResult,
)
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import core

pytest.importorskip("altair")
pytest.importorskip("vl_convert")

_PNG = b"\x89PNG\r\n\x1a\n"


# --- what the tests look at ------------------------------------------------------------------------------------------


def _png_size(png: bytes) -> tuple[int, int]:
    assert png.startswith(_PNG)
    return struct.unpack(">II", png[16:24])


def _jpg_size(jpg: bytes) -> tuple[int, int]:
    """Read the size off the first frame header of a JPEG: the segments are a marker, a length and the bytes."""
    assert jpg.startswith(b"\xff\xd8\xff")
    position = 2
    while position < len(jpg):
        marker = jpg[position + 1]
        length = struct.unpack(">H", jpg[position + 2 : position + 4])[0]
        if marker in {0xC0, 0xC1, 0xC2}:  # a baseline, extended or progressive frame
            height, width = struct.unpack(">HH", jpg[position + 5 : position + 9])
            return width, height
        position += 2 + length
    pytest.fail("a JPEG without a frame header")


def _svg_root(svg: bytes) -> dict[str, str]:
    assert svg.lstrip().startswith(b"<svg")
    return dict(ET.fromstring(svg).attrib)  # noqa: S314


def _pdf_page(pdf: bytes) -> tuple[float, float]:
    assert pdf.startswith(b"%PDF-")
    box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*]", pdf)
    assert box, "a PDF without a page size"
    return float(box.group(1)), float(box.group(2))


def _pixels(png: bytes) -> Any:  # noqa: ANN401
    image = pytest.importorskip("PIL.Image")
    return image.open(io.BytesIO(png)).convert("RGB")


# --- the data of the charts ------------------------------------------------------------------------------------------


def _values(
    *, stations: tuple[str, ...] = ("01048", "00044"), parameters: tuple[str, ...] = ("a", "b"), hours: int = 48
) -> pl.DataFrame:
    """Give a long frame of the values chart: a row for each station, parameter and hour."""
    start = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
    return pl.DataFrame(
        [
            {
                "station_id": station,
                "parameter": f"{parameter} (°C)",
                "timestamp": start + dt.timedelta(hours=hour),
                "value": float((hour * (index + 1)) % 17 + int(station)),
            }
            for station in stations
            for index, parameter in enumerate(parameters)
            for hour in range(hours)
        ],
        schema={
            "station_id": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
        },
    )


def _stripes_frame(years: int = 60, *, gap: tuple[int, int] | None = (20, 25)) -> pl.DataFrame:
    """Give the frame of the stripes: a year each, the warmest first as 0, and a gap of years without a value."""
    rows = []
    for index in range(years):
        has_value = gap is None or not gap[0] <= index < gap[1]
        rows.append(
            {
                "timestamp": dt.datetime(1950 + index, 1, 1, tzinfo=dt.UTC),
                "value_scaled": index / (years - 1) if has_value else None,
                "availability": -0.02 if has_value else None,
            }
        )
    return pl.DataFrame(
        rows, schema={"timestamp": pl.Datetime(time_zone="UTC"), "value_scaled": pl.Float64, "availability": pl.Float64}
    )


def _stripes(frame: pl.DataFrame | None = None, **kwargs: Any) -> Any:  # noqa: ANN401
    options = {
        "colors": core.CLIMATE_STRIPES_CONFIG["temperature"]["colors"],
        "title": "Climate stripes",
        "source": "Source: somebody",
        "show_years": True,
        "show_data_availability": True,
    }
    return charts.stripes_chart(_stripes_frame() if frame is None else frame, **{**options, **kwargs})


def _stations_result(count: int = 6) -> StationsResult:
    rows = [
        {
            "resolution": "hourly",
            "dataset": "temperature_air" if index % 3 else "solar",
            "station_id": f"{index:05d}",
            "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
            "end_timestamp": None,
            "latitude": 48.0 + 0.2 * index,
            "longitude": 11.0 + 0.3 * index,
            "elevation": 10.0,
            "name": f"Station {index}",
            "region": "Bayern",
        }
        for index in range(count)
    ]
    df = pl.DataFrame(rows, schema=STATIONS_SCHEMA)
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_2m")], settings=Settings(cache_disable=True)
    )
    return StationsResult(request=request, df=df, _df_all=df, _stations_filter=StationsFilter.BY_STATION_ID)


def _values_result(*, hours: int = 48) -> ValuesResult:
    rows = []
    for station in ("01048", "00044"):
        for parameter in ("temperature_air_mean_2m", "precipitation_height"):
            for hour in range(hours):
                rows.append(
                    {
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "parameter": parameter,
                        "station_id": station,
                        "timestamp": dt.datetime(2020, 1, 1, tzinfo=dt.UTC) + dt.timedelta(hours=hour),
                        "value": float(hour % 7),
                        "quality_flags": None,
                    }
                )
    frame = _values_frame()
    return ValuesResult(stations=_stations(), df=pl.DataFrame(rows, schema=frame.schema))


# --- the size of an image --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chart",
    [
        pytest.param(lambda: charts.values_chart(_values()), id="values-two-rows"),
        pytest.param(lambda: charts.values_chart(_values(parameters=("a",))), id="values-one-row"),
        pytest.param(
            lambda: charts.values_chart(_values(parameters=("a", "b", "c", "d"), stations=("01048", "00044", "00433"))),
            id="values-four-rows-three-stations",
        ),
        pytest.param(lambda: _stations_result().to_plot(), id="map"),
        pytest.param(lambda: _stations_result(1).to_plot(), id="map-one-station"),
        pytest.param(_stripes, id="stripes"),
        pytest.param(lambda: _stripes(title=None, show_years=False, show_data_availability=False), id="stripes-bare"),
        pytest.param(charts.empty_chart, id="empty"),
    ],
)
@pytest.mark.parametrize(("width", "height"), [(None, None), (700, 500), (1000, 600), (333, 777), (4000, 400)], ids=str)
def test_a_png_is_as_large_as_asked(chart: Any, width: int | None, height: int | None) -> None:  # noqa: ANN401
    """`width` and `height` are the pixels of the picture, axes, legend and padding included.

    Vega-Lite's own `width` and `height` are those of the plot area: a chart drawn at 700 x 500 came out as
    712 x 528 pixels, and a chart of rows at whatever its labels added.
    """
    built = chart()
    default_width, default_height = charts.default_size(built)
    png = render_image(built, "png", width=width, height=height)
    assert isinstance(png, bytes)
    assert _png_size(png) == (width or default_width, height or default_height)


@pytest.mark.parametrize("scale", [0.5, 1, 2, 3])
@pytest.mark.parametrize("kind", ["values", "map", "stripes"])
def test_the_scale_multiplies_a_png_and_a_jpg(kind: str, scale: float) -> None:
    """The stripes image is asked for at `dpi / 100`: 300 dpi is 2100 x 1500 pixels, as it always was."""
    chart = {
        "values": lambda: charts.values_chart(_values()),
        "map": lambda: _stations_result().to_plot(),
        "stripes": _stripes,
    }[kind]()
    width, height = charts.default_size(chart)
    expected = (round(width * scale), round(height * scale))
    assert _png_size(render_image(chart, "png", scale=scale)) == expected
    assert _jpg_size(render_image(chart, "jpg", scale=scale)) == expected


def test_a_chart_of_rows_is_as_tall_as_its_rows_make_it_by_default() -> None:
    """300 pixels for each row of parameters: the default height is read off the chart, and is what is drawn."""
    for rows in (1, 2, 5):
        chart = charts.values_chart(_values(parameters=tuple("abcde")[:rows]))
        assert charts.default_size(chart) == (700, 300 * rows)
        assert _png_size(render_image(chart, "png")) == (700, 300 * rows)


def test_a_picture_too_small_for_its_rows_is_the_smallest_that_holds_them() -> None:
    """Four rows, their labels and their axes do not fit 300 pixels: the plot areas are a pixel each, not less."""
    chart = charts.values_chart(_values(parameters=("a", "b", "c", "d")))
    width, height = _png_size(render_image(chart, "png", width=700, height=300))
    assert width == 700
    assert 300 < height < 400


def test_a_picture_with_a_legend_that_wraps_is_still_as_large_as_asked() -> None:
    """Many stations make a legend of several lines, which a plot area fitted for one line would overflow."""
    stations = tuple(f"{index:05d}" for index in range(1, 30))
    chart = charts.values_chart(_values(stations=stations, hours=6))
    for width in (300, 700, 1500):
        assert _png_size(render_image(chart, "png", width=width, height=700)) == (width, 700)


def test_an_svg_says_the_size_asked_for_and_the_scale_multiplies_it() -> None:
    """A vector: the same drawing at any scale. Plotly's SVG said its size, scaled, in its root, and so does this."""
    chart = _stripes()
    root = _svg_root(render_image(chart, "svg", width=640, height=480))
    assert (root["width"], root["height"], root["viewBox"]) == ("640", "480", "0 0 640 480")
    scaled = _svg_root(render_image(chart, "svg", width=640, height=480, scale=2.5))
    assert (scaled["width"], scaled["height"], scaled["viewBox"]) == ("1600", "1200", "0 0 640 480")


def test_a_pdf_page_is_the_picture_at_96_pixels_to_the_inch() -> None:
    """A picture of 640 x 480 pixels is a page of 480 x 360 points, as Plotly's was (700 x 500 was 525 x 375)."""
    chart = _stripes()
    assert _pdf_page(render_image(chart, "pdf", width=640, height=480)) == (480, 360)
    assert _pdf_page(render_image(chart, "pdf")) == (525, 375)
    assert _pdf_page(render_image(chart, "pdf", width=640, height=480, scale=2)) == (960, 720)


def test_the_text_of_a_pdf_is_text() -> None:
    """The title and the source of the stripes are in the PDF as text, set in the font the SVG names."""
    pypdf = pytest.importorskip("pypdf")
    pdf = render_image(_stripes(title="Climate stripes of a station"), "pdf")
    text = pypdf.PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "Climate stripes of a station" in text
    assert "Source: somebody" in text


def test_a_chart_of_one_view_keeps_its_own_size_in_the_chart() -> None:
    """The chart a caller holds draws at its default size without being asked: it says so itself."""
    chart = _stripes()
    spec = chart.to_dict()
    assert (spec["width"], spec["height"]) == (700, 500)
    assert spec["autosize"] == {"type": "fit", "contains": "padding"}


# --- the formats -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fmt", "magic"),
    [("png", b"\x89PNG\r\n\x1a\n"), ("jpg", b"\xff\xd8\xff"), ("svg", b"<svg"), ("pdf", b"%PDF-")],
)
@pytest.mark.parametrize("kind", ["values", "map", "stripes", "empty"])
def test_every_image_format_of_every_chart_is_what_it_says(kind: str, fmt: str, magic: bytes) -> None:
    """A PNG, a JPEG, an SVG and a PDF by their first bytes, for the three charts and the empty one."""
    chart = {
        "values": lambda: charts.values_chart(_values()),
        "map": lambda: _stations_result().to_plot(),
        "stripes": _stripes,
        "empty": charts.empty_chart,
    }[kind]()
    image = render_image(chart, fmt)
    assert isinstance(image, bytes)
    assert image.lstrip().startswith(magic)
    assert len(image) > 200


@pytest.mark.parametrize("fmt", ["webp", "html", "gif", "bmp"])
def test_a_format_that_is_no_image_is_an_unknown_format_error_naming_the_images(fmt: str) -> None:
    """`webp` went with Plotly and Kaleido; the error lists what there is."""
    with pytest.raises(UnknownFormatError) as error:
        render_image(_stripes(), fmt)
    assert error.value.supported == ("png", "jpg", "svg", "pdf")


def test_the_html_holds_the_vega_lite_specification_and_all_the_data() -> None:
    """The page works offline with Vega inline, and from the CDN without it; both carry the chart and its data."""
    chart = charts.values_chart(_values(stations=("01048", "00433")))
    inline = chart_to_html(chart)
    assert "vegaEmbed" in inline
    assert "vega-lite" in inline
    assert '"$schema": "https://vega.github.io/schema/vega-lite/' in inline
    assert "01048" in inline
    assert "00433" in inline
    assert "2020-01-01T00:00:00Z" in inline
    # the Vega libraries are in the page: it asks the network for none of them
    assert "cdn.jsdelivr.net" not in inline
    assert len(inline) > 500_000

    from wetterdienst.io.export import HTML_INLINE  # noqa: PLC0415

    token = HTML_INLINE.set(False)
    try:
        cdn = chart_to_html(chart)
    finally:
        HTML_INLINE.reset(token)
    assert "cdn.jsdelivr.net/npm/vega" in cdn
    assert "01048" in cdn
    assert len(cdn) < 100_000


# --- the rows ---------------------------------------------------------------------------------------------------------


def test_more_than_5000_rows_are_drawn_and_nothing_is_dropped() -> None:
    """Altair raises a `MaxRowsError` for a frame of 5001 rows; a series of years of hourly values has 8760 a year."""
    frame = _values(stations=("01048", "00044"), parameters=("a", "b"), hours=6_000)  # 24,000 rows
    assert frame.height > 20_000
    chart = charts.values_chart(frame)
    spec = chart.to_dict()
    csv = next(iter(spec["datasets"].values()))
    # every row is in the data, and a header: the limit is not lifted by dropping any
    assert csv.count("\n") == frame.height + 1
    png = render_image(chart, "png", width=900, height=700)
    assert _png_size(png) == (900, 700)
    assert len(chart.to_html()) > frame.height * 10


def test_the_limit_on_rows_is_not_lifted_for_anything_else() -> None:
    """The way round it is no global state: the process keeps its transformer, and a frame is still refused."""
    import altair as alt  # noqa: PLC0415

    before = alt.data_transformers.active
    charts.values_chart(_values(hours=3_000))
    render_image(charts.values_chart(_values(hours=3_000)), "svg")
    assert alt.data_transformers.active == before
    with pytest.raises(alt.MaxRowsError):
        alt.Chart(_values(hours=3_000)).mark_line().to_dict()


def test_a_measuring_render_of_much_data_gives_the_size_of_the_whole() -> None:
    """The size is measured on the lines' first, last, lowest and highest points: the same ticks, labels and legend."""
    frame = _values(stations=("01048", "00044", "00433"), parameters=("a", "b", "c"), hours=2_000)
    # one reading in the middle of a line that no other is near: its axis labels are wider than all others
    frame = frame.with_row_index("_row").with_columns(
        pl.when(pl.col("_row") == 1_000).then(123_456.0).otherwise(pl.col("value")).alias("value")
    )
    frame = frame.drop("_row")
    spec = charts.sized_spec(charts.values_chart(frame), 800, 900)
    measured = charts._thinned(spec)  # noqa: SLF001
    (name,) = spec["datasets"]
    thin, full = measured["datasets"][name], spec["datasets"][name]
    assert thin.count("\n") < 200
    assert full.count("\n") > 10_000
    # the picture of the thin data is the size of the picture of the whole, which is what the thinning is for
    assert charts._measure(measured) == charts._measure(spec)  # noqa: SLF001
    assert _png_size(render_image(charts.values_chart(frame), "png", width=800, height=900)) == (800, 900)


def test_a_station_id_with_leading_zeros_stays_text_and_the_times_are_utc() -> None:
    """Vega-Lite reads `00433` as the number 433 unless told, and a time zone-less time as the viewer's own."""
    chart = charts.values_chart(_values(stations=("00433", "01048"), hours=2))
    spec = chart.to_dict()
    csv = next(iter(spec["datasets"].values()))
    assert spec["data"]["format"]["parse"] == {
        "station_id": "string",
        "parameter": "string",
        "timestamp": "date",
        "value": "number",
    }
    assert csv.splitlines()[1].startswith("00433,")
    assert "2020-01-01T00:00:00Z" in csv
    assert spec["spec"]["encoding"]["x"]["scale"] == {"type": "utc"}
    svg = render_image(chart, "svg").decode()
    assert "00433" in svg


def test_timestamps_of_another_zone_are_the_same_instants_in_utc() -> None:
    """A frame in Berlin time says the instants it says: the chart's data is in UTC and ends in `Z`."""
    frame = _values(hours=3).with_columns(pl.col("timestamp").dt.convert_time_zone("Europe/Berlin"))
    csv = next(iter(charts.values_chart(frame).to_dict()["datasets"].values()))
    assert "2020-01-01T00:00:00Z" in csv
    assert "+01:00" not in csv


# --- what it draws and what it fetches -------------------------------------------------------------------------------


def test_no_pandas_is_needed_and_no_file_is_written(tmp_path: Any) -> None:  # noqa: ANN401
    """Polars frames go in as they are, through narwhals; a render writes nothing and leaves the cwd as it was."""
    code = textwrap.dedent(
        """
        import sys

        from tests.test_charts import _stripes, _values
        from wetterdienst.io import charts
        from wetterdienst.io.export import render_image

        render_image(charts.values_chart(_values()), "png")
        render_image(_stripes(), "svg")
        print(sorted(name for name in ("pandas", "pyarrow", "numpy") if name in sys.modules))
        """
    )
    root = str(pytest.importorskip("tests").__path__[0]).rsplit("/tests", 1)[0]
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={"PYTHONPATH": root, "PATH": ""},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
    assert list(tmp_path.iterdir()) == []


def test_a_chart_that_asks_for_an_address_is_refused_and_the_address_is_not_asked() -> None:
    """A specification holds its data, so no address is let through: a URL in one is an error, not a request."""
    import threading  # noqa: PLC0415
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: PLC0415

    import altair as alt  # noqa: PLC0415

    asked: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            asked.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.end_headers()
            self.wfile.write(b"a\n1\n2\n")

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        chart = alt.Chart(f"http://127.0.0.1:{server.server_port}/secret.csv").mark_point().encode(x="a:Q")
        with pytest.raises(Exception, match=r"(?i)allowed|url|http|127"):
            render_image(chart, "png")
    finally:
        server.shutdown()
        server.server_close()
    assert asked == []


def test_the_map_has_the_borders_and_the_stations_and_fetches_nothing() -> None:
    """The countries come from the file of the package, as an inline TopoJSON: the layer is in the chart itself."""
    spec = _stations_result().to_plot().to_dict()
    land, dots, *labels = spec["layer"]
    assert land["mark"]["type"] == "geoshape"
    assert land["data"]["format"] == {"type": "topojson", "feature": "countries"}
    border = land["data"]["values"]
    assert border["type"] == "Topology"
    assert len(border["objects"]["countries"]["geometries"]) > 150
    assert dots["mark"]["type"] == "circle"
    # the labels of the left half to the right of their stations and the right half to the left, a halo under each
    assert [layer["mark"]["type"] for layer in labels] == ["text"] * 4
    assert [layer["mark"]["align"] for layer in labels] == ["left", "left", "right", "right"]
    assert spec["projection"]["type"] == "mercator"
    assert "url" not in land["data"]
    assert "http" not in json.dumps(land)


def test_the_borders_are_drawn_where_they_are_on_the_map() -> None:
    """The picture has the countries' outlines: Germany's border to Austria is in the one of the stations near it."""
    svg = render_image(_stations_result().to_plot(), "svg").decode()
    # one path for the countries (a multi-polygon of the whole file) that has many points, and no external reference
    paths = re.findall(r'<path[^>]*\sd="([^"]+)"', svg)
    assert any(len(path) > 1_000 for path in paths)
    assert "http://" not in re.sub(r"xmlns(:\w+)?=\"[^\"]+\"", "", svg)


def test_the_world_file_is_small_and_is_natural_earth_110m() -> None:
    """96 KB of TopoJSON: the 177 countries of Natural Earth 1:110m, with no name and no id."""
    path = resources.files("wetterdienst.io").joinpath("natural_earth_110m_countries.topojson")
    text = path.read_text("utf-8")
    assert len(text.encode()) < 150_000
    topology = json.loads(text)
    assert topology["type"] == "Topology"
    assert list(topology["objects"]) == ["countries"]
    geometries = topology["objects"]["countries"]["geometries"]
    assert len(geometries) == 177
    assert all(set(geometry) <= {"type", "arcs"} for geometry in geometries)


def test_the_font_is_the_one_vl_convert_carries_and_it_draws_text() -> None:
    """A family installed nowhere draws no text at all: the stack starts with Liberation Sans, which is there."""
    chart = charts.empty_chart().properties(title="Climate stripes of a station")
    assert chart.to_dict()["config"]["font"] == charts.FONT
    assert charts.FONT.startswith("Liberation Sans,")
    svg = render_image(chart, "svg").decode()
    assert 'font-family="Liberation Sans, Arial, Helvetica, sans-serif"' in svg

    def ink(png: bytes) -> int:
        return sum(1 for pixel in _pixels(png).get_flattened_data() if pixel != (255, 255, 255))

    assert ink(render_image(chart, "png")) > 200
    # and the premise: with a family nobody has, the same chart has none of it
    nobody = chart.configure(font="NoSuchFontAnywhere")
    assert ink(render_image(nobody, "png")) == 0


# --- the stripes ------------------------------------------------------------------------------------------------------


def _stripe_colours(frame: pl.DataFrame, **kwargs: Any) -> list[tuple[int, int, int]]:  # noqa: ANN401
    """Read the colour of each stripe at the middle of its column, in the upper part of the picture."""
    chart = _stripes(frame, title=None, show_years=False, show_data_availability=False, **kwargs)
    width = 400
    image = _pixels(render_image(chart, "png", width=width, height=200))
    first = frame["timestamp"].dt.year().min()
    last = frame["timestamp"].dt.year().max()
    years = last - first + 1
    padding = 10  # the stripes fill the picture inside its padding
    colours = []
    for index in range(years):
        x = padding + (index + 0.5) * (width - 2 * padding) / years
        colours.append(image.getpixel((round(x), 40)))
    return colours


def _near(colour: tuple[int, int, int], expected: tuple[int, int, int], tolerance: int = 3) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(colour, expected, strict=True))


def test_the_temperature_stripes_are_red_for_the_highest_year_and_blue_for_the_lowest() -> None:
    """`value_scaled` 0 is the highest year: ColorBrewer's RdBu from its dark red to its dark blue, as it always was."""
    frame = _stripes_frame(10, gap=None)
    colours = _stripe_colours(frame)
    assert _near(colours[0], (103, 0, 31)), colours[0]
    assert _near(colours[-1], (5, 48, 97)), colours[-1]


def test_the_precipitation_stripes_are_teal_for_the_wettest_year_and_brown_for_the_driest() -> None:
    """Reversed, as the wettest year is scaled to 0 and took brown (GH-2063)."""
    config = core.CLIMATE_STRIPES_CONFIG["precipitation"]
    colours = _stripe_colours(_stripes_frame(10, gap=None), colors=config["colors"])
    assert _near(colours[0], (0, 60, 48)), colours[0]
    assert _near(colours[-1], (84, 48, 5)), colours[-1]


def test_a_year_without_a_value_is_a_gap_in_the_stripes_and_in_the_gold_line() -> None:
    """No stripe, and the availability line stops there: the years that have a value are its runs."""
    frame = _stripes_frame(60, gap=(20, 25))
    colours = _stripe_colours(frame)
    assert all(colour == (255, 255, 255) for colour in colours[20:25])
    assert all(colour != (255, 255, 255) for colour in colours[:20] + colours[25:])
    runs = charts._runs(frame.with_columns(pl.col("timestamp").dt.year().alias("year")))  # noqa: SLF001
    assert runs.to_dicts() == [
        {"start": 1950, "end": 1970, "level": -0.02},
        {"start": 1975, "end": 2010, "level": -0.02},
    ]


def test_the_availability_line_is_gold_and_is_left_out_when_not_asked_for() -> None:
    """The gold of Plotly's line, `#FFD700`, under the stripes."""

    def gold(**kwargs: Any) -> int:  # noqa: ANN401
        image = _pixels(render_image(_stripes(**kwargs), "png"))
        return sum(1 for pixel in image.get_flattened_data() if _near(pixel, (255, 215, 0), 12))

    assert gold(show_data_availability=True) > 500
    assert gold(show_data_availability=False) == 0


def test_the_stripes_say_their_title_years_and_source_where_asked() -> None:
    """The title, the first and the last year and the source are the text of the picture, each by its flag."""

    def texts(chart: Any) -> list[str]:  # noqa: ANN401
        svg = render_image(chart, "svg").decode()
        return re.findall(r"<text\b[^>]*>([^<]*)</text>", svg)

    full = texts(_stripes(title="Climate stripes (temperature) for Somewhere"))
    assert sorted(full) == sorted(
        ["Climate stripes (temperature) for Somewhere", "Source: somebody", "1950", "2009", "data availability"]
    )
    assert texts(_stripes(title=None, show_years=False, show_data_availability=False)) == ["Source: somebody"]


# --- the charts of the results ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(_stations_result, id="stations"),
        pytest.param(_values_result, id="values"),
    ],
)
def test_a_result_gives_an_altair_chart_and_an_image_of_the_size_asked(result: Any) -> None:  # noqa: ANN401
    """`to_plot()` is an Altair chart, and `to_image` writes the formats the registry lists."""
    import altair as alt  # noqa: PLC0415

    built = result()
    assert isinstance(built.to_plot(), alt.TopLevelMixin)
    png = built.to_image(fmt="png", width=640, height=480, scale=2)
    assert isinstance(png, bytes)
    assert _png_size(png) == (1280, 960)
    html = built.to_image(fmt="html")
    assert isinstance(html, str)
    assert "vegaEmbed" in html


def test_the_values_of_a_result_are_the_rows_of_the_chart_with_their_units() -> None:
    """A row for each parameter, labelled with the unit in brackets, a colour for each station."""
    spec = _values_result().to_plot().to_dict()
    rows = spec["facet"]["row"]["sort"]
    assert rows[0] == "temperature_air_mean_2m (°C)"
    assert rows[1].startswith("precipitation_height (")
    assert spec["spec"]["encoding"]["color"]["scale"]["domain"] == ["01048", "00044"]
    csv = next(iter(spec["datasets"].values()))
    assert csv.count("\n") == 2 * 2 * 48 + 1


def test_an_empty_result_is_an_empty_chart_that_is_drawn() -> None:
    """No rows is a chart with nothing in it, at the default size: an image, not an error."""
    empty = StationsResult(
        request=_stations_result().request,
        df=_stations_frame().clear(),
        _df_all=_stations_frame().clear(),
        _stations_filter=StationsFilter.ALL,
    )
    assert _png_size(empty.to_image(fmt="png")) == (700, 500)  # ty: ignore[invalid-argument-type]
    values = ValuesResult(stations=_stations(), df=_values_frame().clear())
    assert _png_size(values.to_image(fmt="png")) == (700, 500)  # ty: ignore[invalid-argument-type]


def test_the_interpolated_and_the_summarized_values_name_the_stations_taken_in_the_tooltip() -> None:
    """The labels were never drawn in Plotly (its mode had no text) and are on hover; here they are in the tooltip."""
    frame = _values_frame().with_columns(
        pl.lit(["01048", "00044"]).alias("taken_station_ids"),
        pl.lit("01048").alias("taken_station_id"),
        pl.lit(None, dtype=pl.Float64).alias("distance"),
    )
    interpolated = InterpolatedValuesResult(stations=_stations(), df=frame, latlon=(51.0, 13.0))  # ty: ignore[unknown-argument]
    spec = interpolated.to_plot().to_dict()
    assert {"field": "taken_station_ids", "title": "taken_station_ids", "type": "nominal"} in spec["spec"]["encoding"][
        "tooltip"
    ]
    assert "01048,00044" in next(iter(spec["datasets"].values()))
    summarized = SummarizedValuesResult(stations=_stations(), df=frame, latlon=(51.0, 13.0))  # ty: ignore[unknown-argument]
    spec = summarized.to_plot().to_dict()
    assert {"field": "taken_station_id", "title": "taken_station_id", "type": "nominal"} in spec["spec"]["encoding"][
        "tooltip"
    ]


def test_a_missing_package_is_a_missing_dependency_error_naming_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without vl-convert the image is a `MissingDependencyError` that says what to install, and not a traceback."""
    monkeypatch.setitem(sys.modules, "vl_convert", None)
    with pytest.raises(MissingDependencyError, match=r"vl_convert.*pip install wetterdienst\[plotting\]"):
        _stations_result().to_image(fmt="png")
    monkeypatch.setitem(sys.modules, "altair", None)
    with pytest.raises(MissingDependencyError, match=r"altair.*pip install wetterdienst\[plotting\]"):
        _stations_result().to_plot()
