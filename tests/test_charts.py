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
import os
import re
import struct
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from importlib import resources
from pathlib import Path
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


def _coast_result() -> StationsResult:
    """Eight stations from the Danish border to the Weser, around the bay of Kiel and the estuary of the Elbe."""
    points = [
        (54.3774, 10.1436),
        (54.5275, 9.5486),
        (53.8712, 8.7058),
        (53.6332, 9.9881),
        (54.5297, 11.0617),
        (54.5, 10.27),
        (53.5333, 8.5833),
        (53.8053, 10.7192),
    ]
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
            "region": "Schleswig-Holstein",
        }
        for index, (latitude, longitude) in enumerate(points)
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
@pytest.mark.parametrize("kind", ["values", "map"])
def test_the_scale_multiplies_a_png_and_a_jpg(kind: str, scale: float) -> None:
    """`scale` of 3 makes the picture of 700 x 500 pixels one of 2100 x 1500, as it always did."""
    chart = {
        "values": lambda: charts.values_chart(_values()),
        "map": lambda: _stations_result().to_plot(),
    }[kind]()
    width, height = charts.default_size(chart)
    expected = (round(width * scale), round(height * scale))
    assert _png_size(render_image(chart, "png", scale=scale)) == expected
    assert _jpg_size(render_image(chart, "jpg", scale=scale)) == expected


@pytest.mark.parametrize(("width", "height"), [(1, 1), (100, 100), (700, 500), (300, 1000)])
def test_the_drawn_size_is_the_size_of_the_picture_a_chart_too_small_for_its_labels_makes(
    width: int, height: int
) -> None:
    """`drawn_size` is what the PNG has (the smallest that holds the labels where less is asked), before `scale`."""
    chart = charts.values_chart(_values(parameters=("a", "b", "c", "d")))
    drawn = charts.drawn_size(chart, width, height)

    assert _png_size(render_image(chart, "png", width=width, height=height)) == drawn
    assert drawn[0] >= width or drawn[1] >= height or drawn == (width, height)
    # a chart of one view is as large as asked, whatever it is asked for
    assert charts.drawn_size(charts.empty_chart(), 3, 4) == (3, 4)


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
    chart = _stations_result().to_plot()
    root = _svg_root(render_image(chart, "svg", width=640, height=480))
    assert (root["width"], root["height"], root["viewBox"]) == ("640", "480", "0 0 640 480")
    scaled = _svg_root(render_image(chart, "svg", width=640, height=480, scale=2.5))
    assert (scaled["width"], scaled["height"], scaled["viewBox"]) == ("1600", "1200", "0 0 640 480")


def test_a_pdf_page_is_the_picture_at_96_pixels_to_the_inch() -> None:
    """A picture of 640 x 480 pixels is a page of 480 x 360 points, as Plotly's was (700 x 500 was 525 x 375)."""
    chart = _stations_result().to_plot()
    assert _pdf_page(render_image(chart, "pdf", width=640, height=480)) == (480, 360)
    assert _pdf_page(render_image(chart, "pdf")) == (525, 375)
    assert _pdf_page(render_image(chart, "pdf", width=640, height=480, scale=2)) == (960, 720)


def test_the_text_of_a_pdf_is_text() -> None:
    """The title and the labels of the stations are in the PDF as text, set in the font the SVG names."""
    pypdf = pytest.importorskip("pypdf")
    pdf = render_image(charts.values_chart(_values()).properties(title="Values of a station"), "pdf")
    text = pypdf.PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "Values of a station" in text
    assert "01048" in text


def test_a_chart_of_one_view_keeps_its_own_size_in_the_chart() -> None:
    """The chart a caller holds draws at its default size without being asked: it says so itself."""
    chart = _stations_result().to_plot()
    spec = chart.to_dict()
    assert (spec["width"], spec["height"]) == (700, 500)
    assert spec["autosize"] == {"type": "fit", "contains": "padding"}


# --- the formats -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fmt", "magic"),
    [("png", b"\x89PNG\r\n\x1a\n"), ("jpg", b"\xff\xd8\xff"), ("svg", b"<svg"), ("pdf", b"%PDF-")],
)
@pytest.mark.parametrize("kind", ["values", "map", "empty"])
def test_every_image_format_of_every_chart_is_what_it_says(kind: str, fmt: str, magic: bytes) -> None:
    """A PNG, a JPEG, an SVG and a PDF by their first bytes, for the two charts and the empty one."""
    chart = {
        "values": lambda: charts.values_chart(_values()),
        "map": lambda: _stations_result().to_plot(),
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
        render_image(charts.empty_chart(), fmt)
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
    assert re.search(r'<script [^>]*src="https://cdn\.jsdelivr\.net/npm/vega@', cdn)
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


def _bare_environment() -> dict[str, str]:
    """Give a fresh process the environment to import this repository's `tests` and `wetterdienst` and nothing else.

    The root is found as a path, not by cutting text, so it is right on Windows too, which also needs `SYSTEMROOT`
    for a process to start its sockets and random numbers, and `USERPROFILE` for `Path.home()`, which Altair asks
    at import (Linux and macOS find the home in the password database).
    """
    root = str(Path(pytest.importorskip("tests").__path__[0]).parent)
    kept = {name: os.environ[name] for name in ("SYSTEMROOT", "TEMP", "TMP", "USERPROFILE") if name in os.environ}
    return {**kept, "PYTHONPATH": root, "PATH": ""}


# --- what it draws and what it fetches -------------------------------------------------------------------------------


def test_no_pandas_is_needed_and_no_file_is_written(tmp_path: Any) -> None:  # noqa: ANN401
    """Polars frames go in as they are, through narwhals; a render writes nothing and leaves the cwd as it was."""
    code = textwrap.dedent(
        """
        import sys

        from tests.test_charts import _stations_result, _values
        from wetterdienst.io import charts
        from wetterdienst.io.export import render_image

        render_image(charts.values_chart(_values()), "png")
        render_image(_stations_result().to_plot(), "svg")
        print(sorted(name for name in ("pandas", "pyarrow", "numpy") if name in sys.modules))
        """
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=_bare_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
    assert list(tmp_path.iterdir()) == []


_SERVER = """
import http.server
import sys

log, port = sys.argv[1], int(sys.argv[2])


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        with open(log, "a") as handle:
            handle.write(self.path + "\\n")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.end_headers()
        self.wfile.write(b"a\\n1\\n2\\n")

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def test_a_chart_that_asks_for_an_address_is_refused_and_the_address_is_not_asked(tmp_path: Any) -> None:  # noqa: ANN401
    """A specification holds its data, so no address is let through: a URL in one is an error, not a request.

    The server that would be asked runs in a process of its own, so that the test does not depend on what the
    renderer does with the interpreter while it waits for it. vl-convert 2 has no address per call: its configuration
    is the guard (`charts.vl_convert`).
    """
    import socket  # noqa: PLC0415
    import time  # noqa: PLC0415

    import altair as alt  # noqa: PLC0415

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    log = tmp_path / "asked.log"
    server = subprocess.Popen([sys.executable, "-c", _SERVER, str(log), str(port)])  # noqa: S603
    try:
        for _ in range(100):  # until it listens
            with socket.socket() as client:
                if client.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        chart = alt.Chart(f"http://127.0.0.1:{port}/secret.csv").mark_point().encode(x="a:Q")
        vlc = pytest.importorskip("vl_convert")
        found = vlc.get_config()["allowed_base_urls"]
        try:
            # whatever the caller has allowed for their own charts, ours are refused: by the check of the specification
            # (`charts._refuse_addresses`, which needs no setting of the process) ...
            for allowed in ([], ["*"]):
                vlc.configure(allowed_base_urls=allowed)
                with pytest.raises(Exception, match=r"(?i)allowed|url|http|127"):
                    render_image(chart, "png")
            # ... and, were one let past it, by the setting that is ours for the time of a render
            vlc.configure(allowed_base_urls=["*"])
            with charts.vl_convert() as inside, pytest.raises(Exception, match=r"(?i)allowed|url|http|127"):
                inside.vegalite_to_svg(chart.to_dict())
            assert vlc.get_config()["allowed_base_urls"] == ["*"]
        finally:
            vlc.configure(allowed_base_urls=found)
    finally:
        server.kill()
        server.wait()
    assert not log.exists()


def test_the_map_has_the_borders_and_the_stations_and_fetches_nothing() -> None:
    """The countries come from the file of the package, as an inline TopoJSON: the layer is in the chart itself."""
    spec = _stations_result().to_plot().to_dict()
    land, dots, anchors, *labels = spec["layer"]
    assert land["mark"]["type"] == "geoshape"
    assert land["data"]["format"] == {"type": "topojson", "feature": "countries"}
    border = land["data"]["values"]
    assert border["type"] == "Topology"
    # a map of 3 degrees holds the countries that reach into it, with the arcs they need and no others
    kept = border["objects"]["countries"]["geometries"]
    assert 1 <= len(kept) < 10
    used = [index if index >= 0 else ~index for geometry in kept for index in charts._arcs_of(geometry["arcs"])]  # noqa: SLF001
    assert max(used) < len(border["arcs"])
    assert len(border["arcs"]) < 500
    assert dots["mark"]["type"] == anchors["mark"]["type"] == "circle"
    assert anchors["mark"]["opacity"] == 0  # the points the labels are placed round, which nobody sees
    # the labels of the left half to the right of their stations and the right half to the left, a halo under each
    assert [layer["mark"]["type"] for layer in labels] == ["text"] * 4
    assert [layer["mark"]["align"] for layer in labels] == ["left", "left", "right", "right"]
    assert spec["projection"]["type"] == "mercator"
    assert "url" not in land["data"]
    assert "http" not in json.dumps(land)


def test_the_borders_of_a_region_are_the_same_drawing_as_those_of_the_world() -> None:
    """Cutting the file down to the countries of the view leaves the picture as it is, and is much less to draw."""
    result = _stations_result()
    chart = result.to_plot()
    cut = chart.to_dict()["layer"][0]["data"]["values"]
    whole = charts.world_borders().to_dict()["values"]
    assert len(whole["objects"]["countries"]["geometries"]) == 241
    assert len(json.dumps(cut)) < len(json.dumps(whole)) / 5

    full = chart.to_dict()
    full["layer"][0]["data"]["values"] = whole
    # the same picture, pixel for pixel: what was left out was outside the view
    assert render_image(chart, "png") == render_image(_Raw(full), "png")


class _Raw:
    """A chart that is a specification as it is, which `render_image` takes through its `to_dict`."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec

    def to_dict(self) -> dict[str, Any]:
        return self.spec


def test_a_german_coast_map_has_the_bay_of_kiel_and_the_elbe() -> None:
    """The 50m borders hold the coast of a region at the scale of a Land: the estuary and the bay are in the picture."""
    svg = render_image(_coast_result().to_plot(), "svg").decode()
    # the land is one path of the countries that reach into the view, with the coast in it: many points
    longest = max(len(path) for path in re.findall(r'<path[^>]*\sd="([^"]+)"', svg))
    assert longest > 1_500


def test_the_borders_are_drawn_where_they_are_on_the_map() -> None:
    """The picture has the countries' outlines: Germany's border to Austria is in the one of the stations near it."""
    svg = render_image(_stations_result().to_plot(), "svg").decode()
    # one path for the countries (a multi-polygon of the whole file) that has many points, and no external reference
    paths = re.findall(r'<path[^>]*\sd="([^"]+)"', svg)
    assert any(len(path) > 1_000 for path in paths)
    assert "http://" not in re.sub(r"xmlns(:\w+)?=\"[^\"]+\"", "", svg)


def test_the_world_file_is_small_and_is_natural_earth_50m() -> None:
    """733 KB of TopoJSON: the 241 countries of Natural Earth 1:50m, with no name and no id."""
    path = resources.files("wetterdienst.io").joinpath("natural_earth_50m_countries.topojson")
    text = path.read_text("utf-8")
    assert len(text.encode()) < 800_000
    topology = json.loads(text)
    assert topology["type"] == "Topology"
    assert list(topology["objects"]) == ["countries"]
    geometries = topology["objects"]["countries"]["geometries"]
    assert len(geometries) == 241
    assert all(set(geometry) <= {"type", "arcs", "bbox"} for geometry in geometries)


def test_the_font_is_the_one_vl_convert_carries_and_it_draws_text() -> None:
    """The stack starts with Liberation Sans, which vl-convert carries: the text is drawn with it, not a fallback.

    vl-convert 1 drew no text at all for a family that is installed nowhere; vl-convert 2 falls back to another font
    (`missing_fonts`), so the premise is that the stack and Liberation Sans alone are drawn the same, and a family
    nobody has is not drawn like it.
    """
    chart = charts.empty_chart().properties(title="Title of a chart")
    assert chart.to_dict()["config"]["font"] == charts.FONT
    assert charts.FONT.startswith("Liberation Sans,")
    svg = render_image(chart, "svg").decode()
    assert 'font-family="Liberation Sans, Arial, Helvetica, sans-serif"' in svg

    def ink(png: bytes) -> int:
        return sum(1 for pixel in _pixels(png).get_flattened_data() if pixel != (255, 255, 255))

    stack = render_image(chart, "png")
    assert ink(stack) > 200
    assert render_image(chart.configure(font="Liberation Sans"), "png") == stack
    # and the premise: with a family nobody has, the same chart is drawn with another font
    assert render_image(chart.configure(font="NoSuchFontAnywhere"), "png") != stack


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


def test_a_series_with_nulls_and_an_outlier_is_as_large_as_asked() -> None:
    """A null sorts first and was taken for the lowest value: the thinned data lost the range of the axes (GH-3238).

    A year of hourly data with gaps came out 705 x 305 for 700 x 300, and an outlier in the middle of a line 830 x 610
    for 800 x 600.
    """
    frame = _values(stations=("01048", "00044"), parameters=("a", "b"), hours=3_000)
    frame = (
        frame.with_row_index("_row")
        .with_columns(
            pl.when(pl.col("_row") % 7 == 0)
            .then(None)
            .when(pl.col("_row") == 1_500)
            .then(9_876.0)
            .when(pl.col("_row") == 700)
            .then(-98_765.0)
            .otherwise(pl.col("value"))
            .alias("value")
        )
        .drop("_row")
    )
    assert frame.height > 10_000
    chart = charts.values_chart(frame)
    for width, height in ((700, 300 * 2), (800, 600), (1000, 700)):
        assert _png_size(render_image(chart, "png", width=width, height=height)) == (width, height)
    spec = charts.sized_spec(chart, 800, 600)
    assert charts._measure(charts._thinned(spec)) == charts._measure(spec)  # noqa: SLF001


@pytest.mark.parametrize("inline", [True, False])
def test_a_station_name_cannot_end_the_script_of_the_page(inline: bool) -> None:  # noqa: FBT001
    """Altair writes the specification into the page as it is: `<`, `>` and `&` are escaped, so a name is data."""
    from wetterdienst.io.export import HTML_INLINE  # noqa: PLC0415

    evil = "</script><script>alert(1)</script>&"
    frame = _values(hours=3).with_columns(pl.col("station_id").replace({"01048": evil}))
    token = HTML_INLINE.set(inline)
    try:
        page = chart_to_html(charts.values_chart(frame))
        harmless = chart_to_html(charts.values_chart(_values(hours=3)))
    finally:
        HTML_INLINE.reset(token)
    assert "</script><script>" not in page
    assert page.count("<script") == harmless.count("<script")
    assert page.count("</script>") == harmless.count("</script>")
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert(1)\\u003c/script\\u003e\\u0026" in page
    # and it is the same data: the page's JSON reads back to the name
    match = re.search(r"(?:var|const) spec = (.*?);\s*(?:var|const) embedOpt", page, flags=re.DOTALL)
    assert match
    spec = json.loads(match.group(1))
    assert evil in next(iter(spec["datasets"].values()))


def test_the_values_chart_zooms_and_pans_along_time_in_the_page_only() -> None:
    """The time axis is bound to the wheel and a drag (a double click resets); the values keep their ranges."""
    spec = charts.values_chart(_values()).to_dict()
    (param,) = spec["params"]
    assert param["select"] == {"type": "interval", "encodings": ["x"]}
    assert param["bind"] == "scales"
    # the image is the same size with it, and an image has no pointer
    assert _png_size(render_image(charts.values_chart(_values()), "png")) == (700, 600)


def test_the_row_labels_are_drawn_as_lines_and_the_picture_is_as_large_as_asked() -> None:
    """Vega draws a line break of a string as a space; the header splits it, and the two lines are measured."""
    frame = _values(parameters=("a",)).with_columns(
        pl.concat_str(pl.lit("hourly\n"), pl.col("parameter")).alias("parameter")
    )
    chart = charts.values_chart(frame)
    assert chart.to_dict()["facet"]["row"]["header"]["labelExpr"] == "split(datum.value, '\\n')"
    svg = render_image(chart, "svg").decode()
    lines = re.findall(r"<tspan[^>]*>([^<]*)</tspan>", svg)
    assert lines[0] == "hourly"
    assert lines[1].startswith("a (")
    assert _png_size(render_image(chart, "png", width=640, height=400)) == (640, 400)


def test_without_vl_convert_the_html_with_vega_inline_is_a_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vega is bundled by vl-convert: its absence is a 501, not a `ModuleNotFoundError`; the CDN page needs none."""
    monkeypatch.setitem(sys.modules, "vl_convert", None)
    chart = charts.values_chart(_values(hours=3))
    with pytest.raises(MissingDependencyError, match=r"vl_convert.*pip install wetterdienst\[plotting\]"):
        chart_to_html(chart)
    assert re.search(r'src="https://cdn\.jsdelivr\.net/npm/', charts.chart_to_html(chart, inline=False))


def test_the_thinned_data_keeps_the_lowest_and_highest_values_where_a_line_has_nulls() -> None:
    """A null sorts first, and was kept as the lowest point: the thin data lost the real extremes of every line."""
    frame = _values(stations=("01048", "00044"), parameters=("a", "b"), hours=2_000)
    frame = (
        frame.with_row_index("_row")
        .with_columns(
            pl.when(pl.col("_row") % 7 == 0)
            .then(None)
            .when(pl.col("_row") % 2_000 == 701)
            .then(-12.5)
            .when(pl.col("_row") % 2_000 == 1_501)
            .then(5_000.5)
            .otherwise(pl.col("value"))
            .alias("value")
        )
        .drop("_row")
    )
    spec = charts.sized_spec(charts.values_chart(frame), 800, 600)
    (name,) = spec["datasets"]
    thin = pl.read_csv(
        io.StringIO(charts._thinned(spec)["datasets"][name]),  # noqa: SLF001
        schema_overrides={"station_id": pl.String, "parameter": pl.String},
    )
    assert thin.height < 200
    for (station, parameter), group in frame.group_by("station_id", "parameter"):
        kept = thin.filter((pl.col("station_id") == station) & (pl.col("parameter") == parameter))
        assert kept["value"].min() == group["value"].min() == -12.5
        assert kept["value"].max() == group["value"].max() == 5_000.5


def test_a_picture_writes_nothing_to_stderr(tmp_path: Any) -> None:  # noqa: ANN401
    """Nothing of a picture or a page is on stderr: no window for the zoom and pan, no `tree-shaker` pass."""
    code = textwrap.dedent(
        """
        from tests.test_charts import _stations_result, _values
        from wetterdienst.io import charts
        from wetterdienst.io.export import chart_to_html, render_image

        for chart in (charts.values_chart(_values()), _stations_result().to_plot()):
            # the first inline page of a process makes vl-convert's bundle, which wrote `tree-shaker; pass=1` and so on
            assert "vega" in chart_to_html(chart)
            assert "vega" in chart_to_html(chart)
            for fmt in ("png", "svg", "pdf"):
                render_image(chart, fmt)
        """
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=_bare_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert done.stderr == ""


def _every_way_to_draw() -> list[Any]:
    """Give the ways this library draws with vl-convert: the images, the measure of a chart of rows, the pages."""
    values = charts.values_chart(_values(parameters=("a", "b", "c"), hours=3))
    stations = _stations_result().to_plot()
    return [
        lambda: render_image(values, "svg"),
        lambda: render_image(stations, "png"),
        lambda: charts.chart_to_html(stations),
        lambda: charts.chart_to_html(stations, inline=False),
        lambda: charts.chart_to_html(values),
        lambda: charts.chart_to_html(values, inline=False),
    ]


def test_the_setting_of_the_caller_is_the_same_after_a_render(tmp_path: Any) -> None:  # noqa: ANN401
    """vl-convert 2's allowed addresses are the process's: ours are none, for a render, and then the caller's again."""
    vlc = pytest.importorskip("vl_convert")
    found = vlc.get_config()["allowed_base_urls"]
    csv_file = tmp_path / "own.csv"
    csv_file.write_text("a\n1\n2\n")
    own = {"data": {"url": str(csv_file)}, "mark": "point", "encoding": {"x": {"field": "a", "type": "quantitative"}}}
    ways = _every_way_to_draw()
    try:
        for setting in (["*"], ["https://example.com/"], [str(tmp_path)], ["http:", "https:"], []):
            vlc.configure(allowed_base_urls=setting)
            for draw in ways:
                draw()
                assert vlc.get_config()["allowed_base_urls"] == setting
        # a chart of the caller's own, with data from where they allowed, is drawn after ours as it was before
        vlc.configure(allowed_base_urls=[str(tmp_path)])
        render_image(charts.empty_chart(), "svg")
        assert vlc.vegalite_to_svg(own).startswith("<svg")
    finally:
        vlc.configure(allowed_base_urls=found)


def test_a_chart_that_reads_from_an_address_is_not_drawn_whatever_the_setting() -> None:
    """The check needs no setting of the process: the specification names a URL, an image, and it is refused."""
    import altair as alt  # noqa: PLC0415

    for chart in (
        alt.Chart("https://example.com/data.csv").mark_point().encode(x="a:Q"),
        alt.Chart(alt.InlineData(values=[{"a": 1, "u": "x"}])).mark_image().encode(url="u:N"),
    ):
        with pytest.raises(ValueError, match="URL"):
            render_image(chart, "svg")
        with pytest.raises(ValueError, match="URL"):
            charts.chart_to_html(chart)
        with pytest.raises(ValueError, match="URL"):
            charts.chart_to_html(chart, inline=False)
