# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The charts of the results: Altair draws them as Vega-Lite specifications, vl-convert renders them (GH-3238).

Three charts, one for each thing the library plots:

- `values_chart`: a row of lines and markers for each parameter, a colour for each station;
- `stations_chart`: the stations as points on a map of the country borders, a colour for each dataset;
- `stripes_chart`: the climate stripes, a stripe for each year.

A chart is a Vega-Lite specification and holds all its data, so the same chart is a page (`to_html`) or an image
(`render_image`), and drawing one needs no browser and fetches nothing: the map's borders come with the package
(`natural_earth_50m_countries.topojson`, Natural Earth, public domain). Altair and vl-convert are the `plotting`
extra and are imported where a chart is drawn, never at import.

The data goes into a chart as the text of a CSV file, written by polars in one call (`_inline_data`): Altair raises a
`MaxRowsError` for a frame of more than 5000 rows, and the ways round it that are global state (`disable_max_rows`) or
write a file (the `json` transformer) are no way for a server. Text is no frame and no list of records, so the limit
does not apply, 87,000 points build in a tenth of a second, and nothing is shared between two charts.
"""

from __future__ import annotations

import functools
import io
import json
import math
import re
from importlib import resources
from typing import TYPE_CHECKING, Any

import polars as pl

from wetterdienst.util.extras import import_optional

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    import altair as alt

#: the font of every chart. Liberation Sans is carried by vl-convert itself, so an image looks the same wherever it is
#: drawn and needs no font of the system (a family that is installed nowhere draws no text at all); the rest of the
#: list is what a browser takes for the html page, which has no Liberation Sans of its own
FONT = "Liberation Sans, Arial, Helvetica, sans-serif"
#: the size in pixels of a chart that nothing gives another: a chart is `DEFAULT_WIDTH` wide, and as high as
#: `DEFAULT_HEIGHT`, or `ROW_HEIGHT` for each row of parameters in a chart that has rows
DEFAULT_WIDTH, DEFAULT_HEIGHT = 700, 500
ROW_HEIGHT = 300
#: where a chart keeps what `render_image` needs to know about it (`usermeta` is Vega-Lite's place for it, which no
#: renderer reads): the size it is drawn at, and the rows of parameters, a chart that cannot say its own size
_META = "wetterdienst"
#: the colour of the stripes' availability line, as it was in Plotly
_GOLD = "#FFD700"
_TEXT_COLOR = "#2a3f5f"

#: width in pixels of the whole world at zoom 0 of the map `StationsResult` fits its extent to (512 px tiles)
MAP_WORLD_PIXELS = 512
#: the padding of the station map in pixels
_MAP_PADDING = {"left": 10, "right": 10, "top": 10, "bottom": 10}


def altair() -> Any:  # noqa: ANN401 -- the module, optional
    """Give Altair, or raise the `MissingDependencyError` that says to install the `plotting` extra."""
    return import_optional("altair", "Plotting", extra="plotting")


def _meta(width: int, height: int, rows: int | None = None) -> dict[str, dict[str, int]]:
    """Give the `usermeta` of a chart: the size it is drawn at and the rows it has."""
    meta = {"width": width, "height": height}
    if rows:
        meta["rows"] = rows
    return {_META: meta}


def _style(chart: alt.TopLevelMixin, *, view_stroke: str | None = None, background: str = "white") -> alt.TopLevelMixin:
    """Give a finished chart the font and the background that every chart of the library has, white unless told."""
    return chart.configure(font=FONT, background=background).configure_view(stroke=view_stroke)


def _utc_text(timestamp: pl.Expr) -> pl.Expr:
    """Write a timestamp as ISO 8601 text in UTC, which every JavaScript engine reads as the same instant."""
    return timestamp.dt.convert_time_zone("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _inline_data(df: pl.DataFrame, parse: dict[str, str]) -> Any:  # noqa: ANN401
    """Give the rows of a frame as the CSV text of an inline dataset, with the types of its columns.

    `parse` is needed for every column: Vega-Lite would read the station id `00433` as the number 433.
    """
    alt = altair()
    return alt.InlineData(values=df.write_csv(), format=alt.CsvDataFormat(type="csv", parse=parse))


def empty_chart() -> alt.TopLevelMixin:
    """Give the chart of a result that has no rows: an empty frame, drawn at the default size."""
    alt = altair()
    chart = (
        alt.Chart(alt.InlineData(values=[]))
        .mark_point()
        .properties(
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            autosize=alt.AutoSizeParams(type="fit", contains="padding"),
            usermeta=_meta(DEFAULT_WIDTH, DEFAULT_HEIGHT),
        )
    )
    return _style(chart)


def values_chart(df: pl.DataFrame, *, tooltip: str | None = None) -> alt.TopLevelMixin:
    r"""Draw the values chart: lines and markers, a row for each parameter with an y axis of its own.

    Args:
        df: The long frame with `station_id`, `parameter` (the label of the row; a line break written `\\n` is drawn
            as one), `timestamp` (a datetime) and `value`, and the column `tooltip` names where the markers say more.
        tooltip: The column of `df` the marker shows beside the station, the time and the value.

    Returns:
        The chart, `ROW_HEIGHT` pixels high for each row and `DEFAULT_WIDTH` wide: the size of the image it makes
        unless `render_image` is given another.

    """
    alt = altair()
    # a station can have no timestamp that is not in UTC: the instant is what is drawn, and the scale is UTC
    frame = df.with_columns(_utc_text(pl.col("timestamp")).alias("timestamp"))
    columns = ["station_id", "parameter", "timestamp", "value"]
    parse = {"station_id": "string", "parameter": "string", "timestamp": "date", "value": "number"}
    if tooltip:
        columns.append(tooltip)
        parse[tooltip] = "string"
    rows = frame.get_column("parameter").unique(maintain_order=True).to_list()
    stations = frame.get_column("station_id").unique(maintain_order=True).to_list()
    cell_width, cell_height = _cell(DEFAULT_WIDTH, ROW_HEIGHT * len(rows), len(rows))
    shown = [
        alt.Tooltip("station_id:N", title="station"),
        alt.Tooltip("timestamp:T", title="time", format="%Y-%m-%d %H:%M", timeUnit="utcyearmonthdatehoursminutes"),
        alt.Tooltip("value:Q"),
    ]
    if tooltip:
        shown.append(alt.Tooltip(f"{tooltip}:N", title=tooltip))
    chart = (
        alt.Chart(_inline_data(frame.select(columns), parse))
        .mark_line(point=alt.OverlayMarkDef(size=14), strokeWidth=1)
        .encode(
            x=alt.X("timestamp:T", scale=alt.Scale(type="utc"), axis=alt.Axis(title=None, labelFlush=False)),
            y=alt.Y("value:Q", scale=alt.Scale(zero=False), axis=alt.Axis(title=None)),
            color=alt.Color(
                "station_id:N",
                scale=alt.Scale(domain=stations),
                legend=alt.Legend(
                    title="station_id",
                    orient="top",
                    direction="horizontal",
                    # every station has its entry, and a row of them is as wide as the picture
                    symbolLimit=0,
                    columns=_legend_columns(stations, DEFAULT_WIDTH),
                ),
            ),
            tooltip=shown,
        )
        .properties(width=cell_width, height=cell_height)
        # zoom and pan along the time with the wheel and a drag, a double click resets: the page only, an image has
        # no pointer. The values are not bound, each row keeps its own range
        .interactive(bind_y=False)
        .facet(
            row=alt.Row(
                "parameter:N",
                title=None,
                sort=rows,
                header=alt.Header(
                    labelOrient="top",
                    labelAnchor="start",
                    labelAngle=0,
                    labelLimit=0,
                    # Vega draws a line break of a string as a space: an array of lines is drawn as lines
                    labelExpr="split(datum.value, '\\n')",
                ),
            )
        )
        .resolve_scale(y="independent")
        .properties(usermeta=_meta(DEFAULT_WIDTH, ROW_HEIGHT * len(rows), len(rows)))
    )
    return _style(chart, view_stroke="#ddd")


def _legend_columns(entries: list[str], width: int) -> int:
    """Give the number of entries of a horizontal legend that fit a row of a picture of `width` pixels.

    Vega-Lite does not wrap a horizontal legend by itself, and the legend of 30 stations is wider than the picture.
    An entry is a symbol and the text, which the font sets at about 7 pixels a character.
    """
    entry = max((len(str(label)) for label in entries), default=1) * 7 + 40
    return max(1, (width - 30) // entry)


def _cell(width: int, height: int, rows: int) -> tuple[int, int]:
    """Guess the size of the plot area of one row of the values chart for a picture of `width` x `height` pixels.

    What is around it (the axis of the row, the legend, the label of the row, the padding) is not known until
    the chart is drawn, so this is where `_fit_rows` starts.
    """
    return max(10, width - 90), max(10, (height - 70) // rows - 45)


def stations_chart(
    df: pl.DataFrame,
    *,
    center: dict[str, float],
    zoom: float,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> alt.TopLevelMixin:
    """Draw the station map: the stations on the borders of the countries, a colour for each dataset, a label for each.

    Args:
        df: The frame with `longitude`, `latitude`, `name` (the label of the station) and `dataset` (what colours it).
        center: The `lat` and `lon` the map is centred on.
        zoom: The zoom of the map, as a map of 512 px tiles counts it, which is how far the extent of the stations
            is shown (`_fit_map_view` of the results); the same zoom shows the same part of the world at any size.
        width: The width of the picture in pixels.
        height: The height of the picture in pixels.

    Returns:
        The chart, `width` x `height` pixels as an image, the legend and the padding included.

    """
    alt = altair()
    frame = df.select("longitude", "latitude", "name", "dataset")
    points = alt.Chart(
        _inline_data(frame, {"longitude": "number", "latitude": "number", "name": "string", "dataset": "string"})
    )
    datasets = frame.get_column("dataset").unique(maintain_order=True).to_list()
    position = {"longitude": "longitude:Q", "latitude": "latitude:Q"}
    # the countries, drawn from the file that comes with the package: no tile is fetched
    scale = MAP_WORLD_PIXELS * 2**zoom / (2 * math.pi)
    land = alt.Chart(world_borders(_visible(center, scale, width, height))).mark_geoshape(
        fill="#f4f1ea", stroke="#a9a49a", strokeWidth=0.6
    )
    dots = points.mark_circle(size=60, opacity=0.95, stroke="white", strokeWidth=0.8).encode(
        **position,
        color=alt.Color(
            "dataset:N",
            scale=alt.Scale(domain=datasets),
            legend=alt.Legend(title="dataset", orient="top", direction="horizontal"),
        ),
        tooltip=[alt.Tooltip("name:N", title="station"), alt.Tooltip("dataset:N")],
    )
    # a label is to the right of its station, to the left of those in the right half of the map, where it would leave
    # the picture. Drawn twice, the first time as a white halo that keeps it readable over a border
    middle = center["lon"]
    labels = []
    for keep, align, offset in (
        (alt.datum.longitude <= middle, "left", 7),
        (alt.datum.longitude > middle, "right", -7),
    ):
        text = points.transform_filter(keep)
        halo = {"color": "white", "stroke": "white", "strokeWidth": 3, "strokeJoin": "round"}
        labels.append(text.mark_text(align=align, dx=offset, fontSize=10, **halo).encode(**position, text="name:N"))
        labels.append(
            text.mark_text(align=align, dx=offset, fontSize=10, color="#222").encode(**position, text="name:N")
        )
    chart = (
        alt.layer(land, dots, *labels)
        .project(
            type="mercator",
            center=[center["lon"], center["lat"]],
            scale=scale,
        )
        .properties(
            width=width,
            height=height,
            padding=_MAP_PADDING,
            autosize=alt.AutoSizeParams(type="fit", contains="padding"),
            usermeta=_meta(width, height),
            view=alt.ViewConfig(fill="#e3edf4", stroke=None),
        )
    )
    return _style(chart)


@functools.cache
def _world() -> dict[str, Any]:
    """Read the countries of the world from the file of the package, once."""
    text = resources.files("wetterdienst.io").joinpath("natural_earth_50m_countries.topojson").read_text("utf-8")
    return json.loads(text)


def _renumbered(node: Any, new: dict[int, int]) -> Any:  # noqa: ANN401
    """Give a TopoJSON geometry the numbers its arcs have in a list of fewer arcs; a reversed arc is `~index`."""
    if isinstance(node, int):
        return new[node] if node >= 0 else ~new[~node]
    return [_renumbered(child, new) for child in node]


def _arcs_of(node: Any) -> Iterable[int]:  # noqa: ANN401
    """Give the indexes of the arcs of a TopoJSON geometry."""
    if isinstance(node, int):
        yield node if node >= 0 else ~node
    else:
        for child in node:
            yield from _arcs_of(child)


def world_borders(view: tuple[float, float, float, float] | None = None) -> Any:  # noqa: ANN401
    """Give the borders and coastlines of the world as a dataset: Natural Earth 1:50m, public domain.

    The file is the countries of `ne_50m_admin_0_countries` as TopoJSON (742 KB), and is read from the package. Each
    country has its bounding box in it: of a `view` (west, south, east, north, in degrees) only the countries that
    reach into it are given, with the arcs they need, as the whole file is 20 times what a map of a region draws and
    drawing it takes seconds.
    """
    alt = altair()
    topology = _world()
    if view is not None:
        west, south, east, north = view
        countries = topology["objects"]["countries"]
        kept = [
            geometry
            for geometry in countries["geometries"]
            if geometry["bbox"][0] <= east
            and geometry["bbox"][2] >= west
            and geometry["bbox"][1] <= north
            and geometry["bbox"][3] >= south
        ]
        used = sorted({index for geometry in kept for index in _arcs_of(geometry["arcs"])})
        new = {old: position for position, old in enumerate(used)}
        topology = {
            **topology,
            "objects": {
                "countries": {
                    **countries,
                    "geometries": [{**geometry, "arcs": _renumbered(geometry["arcs"], new)} for geometry in kept],
                }
            },
            "arcs": [topology["arcs"][index] for index in used],
        }
    return alt.Data(values=topology, format=alt.DataFormat(type="topojson", feature="countries"))


def _visible(center: dict[str, float], scale: float, width: int, height: int) -> tuple[float, float, float, float]:
    """Give the longitudes and latitudes a mercator map of `scale` pixels to the radian shows, with room to spare."""
    spare = 1.3
    half_width = math.degrees(width / 2 / scale) * spare
    middle = math.log(math.tan(math.pi / 4 + math.radians(max(-85.0, min(85.0, center["lat"]))) / 2))
    half_height = height / 2 / scale * spare
    north = math.degrees(math.atan(math.sinh(middle + half_height)))
    south = math.degrees(math.atan(math.sinh(middle - half_height)))
    return center["lon"] - half_width, south, center["lon"] + half_width, north


def stripes_chart(
    df: pl.DataFrame,
    *,
    colors: Sequence[str],
    title: str | None,
    source: str | None,
    show_years: bool,
    show_data_availability: bool,
    padding: int = 10,
    background: str = "white",
) -> alt.TopLevelMixin:
    """Draw the climate stripes: a stripe for each year, coloured by the year's value, and the gold availability line.

    Args:
        df: The frame with `timestamp` (a datetime, a year each), `value_scaled` (0 to 1, null for a year without a
            value; the stripe of 0 is the first colour of the scheme) and `availability` (null for a year without).
        colors: The colours of the stripes as hex, from the one of `value_scaled` 0 to the one of 1, between which the
            colour of a year is interpolated in RGB as evenly spaced stops.
        title: The title above the stripes, none where it is left out.
        source: Whose data it is, written under the stripes, none where it is left out.
        show_years: Write the first and the last year.
        show_data_availability: Draw the line that shows the years that have a value.
        padding: The pixels around the stripes.
        background: The colour of the background, `transparent` for none.

    Returns:
        The chart, `DEFAULT_WIDTH` x `DEFAULT_HEIGHT` pixels as an image.

    """
    alt = altair()
    years = df.with_columns(pl.col("timestamp").dt.year().alias("year"))
    # a frame with a year each has a first and a last, which `min` and `max` type as possibly none
    first, last = int(years["year"].min()), int(years["year"].max())  # ty: ignore[invalid-argument-type]
    x_scale = alt.Scale(domain=[first, last + 1], nice=False, zero=False)
    # the lowest tenth is where the availability line and the text are, under the stripes
    # and nothing under the stripes where there is no text to write
    has_text = bool(source) or show_years or show_data_availability
    y_scale = alt.Scale(domain=[-0.12 if has_text else 0, 1], nice=False)
    stripes = (
        years.filter(pl.col("value_scaled").is_not_null())
        .select("year", "value_scaled")
        .with_columns((pl.col("year") + 1).alias("year_end"), pl.lit(0.0).alias("bottom"), pl.lit(1.0).alias("top"))
    )
    layers = [
        alt.Chart(_inline_data(stripes, dict.fromkeys(stripes.columns, "number")))
        .mark_rect()
        .encode(
            x=alt.X("year:Q", axis=None, scale=x_scale),
            x2="year_end:Q",
            y=alt.Y("bottom:Q", axis=None, scale=y_scale),
            y2="top:Q",
            color=alt.Color(
                "value_scaled:Q",
                legend=None,
                # a scale with a stop for each colour: Vega's own schemes are not the ColorBrewer ramps
                scale=alt.Scale(
                    domain=[index / (len(colors) - 1) for index in range(len(colors))],
                    range=list(colors),
                    interpolate="rgb",
                ),
            ),
        )
    ]
    texts = []
    if source:
        texts.append(
            {"x": (first + last + 1) / 2, "y": -0.095, "text": source, "align": "center", "color": _TEXT_COLOR}
        )
    if show_data_availability:
        # a run of the years that have a value is a line, and a year without one is where it stops
        runs = _runs(years)
        layers.append(
            alt.Chart(_inline_data(runs, dict.fromkeys(runs.columns, "number")))
            .mark_rule(color=_GOLD, strokeWidth=2)
            .encode(
                x=alt.X("start:Q", axis=None, scale=x_scale),
                x2="end:Q",
                y=alt.Y("level:Q", axis=None, scale=y_scale),
            )
        )
        texts.append({"x": first, "y": -0.05, "text": "data availability", "align": "left", "color": _GOLD})
    if show_years:
        texts.append({"x": first, "y": -0.095, "text": str(first), "align": "left", "color": _TEXT_COLOR})
        texts.append({"x": last + 1, "y": -0.095, "text": str(last), "align": "right", "color": _TEXT_COLOR})
    for aligned in ("left", "center", "right"):
        rows = [text for text in texts if text["align"] == aligned]
        if rows:
            frame = pl.DataFrame(rows).select("x", "y", "text", "color")
            layers.append(
                alt.Chart(_inline_data(frame, {"x": "number", "y": "number", "text": "string", "color": "string"}))
                .mark_text(align=aligned, baseline="middle", fontSize=11)
                .encode(
                    x=alt.X("x:Q", axis=None, scale=x_scale),
                    y=alt.Y("y:Q", axis=None, scale=y_scale),
                    text="text:N",
                    color=alt.Color("color:N", scale=None, legend=None),
                )
            )
    chart = alt.layer(*layers).properties(
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
        padding=dict.fromkeys(("left", "right", "top", "bottom"), padding),
        autosize=alt.AutoSizeParams(type="fit", contains="padding"),
        usermeta=_meta(DEFAULT_WIDTH, DEFAULT_HEIGHT),
    )
    if title:
        chart = chart.properties(
            title=alt.TitleParams(title, anchor="start", fontSize=16, fontWeight="normal", color=_TEXT_COLOR)
        )
    return _style(chart, background=background)


def _runs(years: pl.DataFrame) -> pl.DataFrame:
    """Give the runs of years that have a value as `start`, `end` (the first year after it) and `level` of the line."""
    return (
        years.select("year", pl.col("availability").is_not_null().alias("has"), pl.col("availability").alias("level"))
        .with_columns((pl.col("has") != pl.col("has").shift(1, fill_value=False)).cum_sum().alias("run"))
        .filter(pl.col("has"))
        .group_by("run", maintain_order=True)
        .agg(
            pl.col("year").min().alias("start"),
            (pl.col("year").max() + 1).alias("end"),
            pl.col("level").first().alias("level"),
        )
        .select("start", "end", "level")
    )


# --------------------------------------------------------------------------------------------------------------
# the size of an image
# --------------------------------------------------------------------------------------------------------------

#: the points of a PDF page for a pixel of the picture: 72 points to the inch, 96 pixels to the inch
_PDF_POINTS_PER_PIXEL = 0.75
#: the autosize of a chart whose width and height are the whole picture, axes, legend and padding included
_FIT = {"type": "fit", "contains": "padding"}
#: the root of an SVG: its size, in pixels
_SVG_ROOT = re.compile(r'(<svg\b[^>]*?)\swidth="([\d.]+)"\sheight="([\d.]+)"')
#: the lines of the data (all of them, the header included) above which a measuring render is given a cut down copy
_MEASURED_ROWS = 4000


def count_points(chart: alt.TopLevelMixin) -> int:
    """Count the points a chart draws: the rows of its largest inline dataset, which a page embeds as well."""
    spec = chart.to_dict()
    sizes = [data.count("\n") - 1 for data in spec.get("datasets", {}).values() if isinstance(data, str)]
    return max(sizes, default=0)


def default_size(chart: alt.TopLevelMixin) -> tuple[int, int]:
    """Give the size in pixels a chart is drawn at where nothing asks for another."""
    meta = _spec_meta(chart.to_dict())
    return meta.get("width", DEFAULT_WIDTH), meta.get("height", DEFAULT_HEIGHT)


def _spec_meta(spec: dict[str, Any]) -> dict[str, int]:
    return spec.get("usermeta", {}).get(_META, {})


def sized_spec(chart: alt.TopLevelMixin, width: int | None = None, height: int | None = None) -> dict[str, Any]:
    """Give the specification of a chart that is exactly `width` x `height` pixels, the sizes left out the default.

    Vega-Lite's `width` and `height` are those of the plot area, so a chart drawn at 700 x 500 is 712 x 528 pixels
    once its axes and padding are added. A chart of one view (the map, the stripes) is told to fit: its `width` and
    `height` are then the whole picture. A chart of rows cannot be (`autosize: fit` is not for facets), so it is
    drawn once, small, to see what its axes, legend and labels take, and its plot areas are those that leave the rest;
    what the whole numbers of pixels leave over goes to the padding.
    """
    spec = chart.to_dict()
    meta = _spec_meta(spec)
    wide, high = width or meta.get("width", DEFAULT_WIDTH), height or meta.get("height", DEFAULT_HEIGHT)
    rows = meta.get("rows")
    if rows:
        _fit_rows(spec, wide, high, rows)
    else:
        spec.update(width=wide, height=high, autosize=_FIT)
    return spec


def _fit_rows(spec: dict[str, Any], width: int, height: int, rows: int) -> None:
    """Set the plot area of a row and the padding of a chart so that it is `width` x `height` pixels."""
    cell = spec["spec"]
    cell["width"], cell["height"] = _cell(width, height, rows)
    legend = cell["encoding"]["color"]["legend"]
    legend["columns"] = _legend_columns(cell["encoding"]["color"]["scale"]["domain"], width)
    spec["padding"] = {"left": 5, "right": 5, "top": 5, "bottom": 5}
    measuring = _thinned(spec)
    measured_width, measured_height = _measure(measuring)
    # drawing again after a change of the plot area, which can change how the legend wraps: a few rounds settle it
    for _ in range(4):
        missing_width, missing_height = width - measured_width, height - measured_height
        if not missing_width and not missing_height:
            break
        cell["width"] = max(1, cell["width"] + missing_width)
        # the rows share what is missing, and what does not divide goes to the padding below
        cell["height"] = max(1, cell["height"] + missing_height // rows)
        measuring["spec"].update(width=cell["width"], height=cell["height"])
        measured_width, measured_height = _measure(measuring)
    # the whole numbers of pixels may leave a few: they are padding, as are those a chart too small for its
    # legend and axes cannot lose (the plot area is not less than a pixel)
    spec["padding"]["right"] += max(0, math.ceil(width - measured_width))
    spec["padding"]["bottom"] += max(0, math.ceil(height - measured_height))


def _measure(spec: dict[str, Any]) -> tuple[float, float]:
    """Draw a specification as SVG and read the size of the picture."""
    vlc = import_optional("vl_convert", "Rendering an image", extra="plotting")
    svg = vlc.vegalite_to_svg(spec, allowed_base_urls=[])
    root = _SVG_ROOT.search(svg)
    if root is None:
        msg = "vl-convert wrote an SVG without a size"
        raise RuntimeError(msg)
    return float(root.group(2)), float(root.group(3))


def _thinned(spec: dict[str, Any]) -> dict[str, Any]:
    """Give the specification with the data cut down to what shapes the axes and the legend, where there is much.

    The picture's size does not depend on how many points a line has, but a measuring render pays for all of them
    (2.5 s for 87,000). The first, the last, the lowest and the highest point of each line are kept: they hold the
    same stations, the same time and value ranges and so the same ticks, labels and legend.
    """
    name = spec.get("data", {}).get("name")
    data = spec.get("datasets", {}).get(name)
    if not isinstance(data, str) or data.count("\n") <= _MEASURED_ROWS:
        return {**spec, "spec": dict(spec["spec"])}
    frame = pl.read_csv(io.StringIO(data), infer_schema_length=0).with_row_index("_row")
    value = pl.col("value").cast(pl.Float64)
    kept = (
        frame.group_by("parameter", "station_id")
        .agg(
            pl.col("_row").first().alias("first"),
            pl.col("_row").last().alias("last"),
            # a null sorts first, and is no lowest value
            pl.col("_row").sort_by(value, nulls_last=True).first().alias("lowest"),
            pl.col("_row").sort_by(value, descending=True, nulls_last=True).first().alias("highest"),
        )
        .select(pl.concat_list("first", "last", "lowest", "highest").explode().unique().alias("_row"))
    )
    thin = frame.join(kept, on="_row").sort("_row").drop("_row")
    return {**spec, "spec": dict(spec["spec"]), "datasets": {**spec["datasets"], name: thin.write_csv()}}


# --------------------------------------------------------------------------------------------------------------
# the page and the images
# --------------------------------------------------------------------------------------------------------------


class _HtmlSafeEncoder(json.JSONEncoder):
    r"""Write JSON that cannot end the script it is put in: `<`, `>`, `&` are written as `\u003c`, `\u003e`, `\u0026`.

    Altair puts the specification into the page as it is, so a station named `</script><script>...` would be
    markup. These characters are in the strings of the JSON only, where the escapes read as the characters.
    """

    def encode(self, o: object) -> str:
        """Encode as JSON, with no character that is markup."""
        return super().encode(o).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def chart_to_html(chart: alt.TopLevelMixin, *, inline: bool = True) -> str:
    """Write a chart as an html page, with Vega inline, which works offline, or from the CDN (a few kilobytes).

    Vega inline is bundled by vl-convert, so that is needed for it and not for the page that loads Vega.
    """
    if inline:
        import_optional("vl_convert", "Rendering an html page", extra="plotting")
    return chart.to_html(inline=inline, json_kwds={"cls": _HtmlSafeEncoder})


def render(chart: alt.TopLevelMixin, fmt: str, *, width: int | None, height: int | None, scale: float | None) -> bytes:
    """Draw a chart as `png`, `jpg`, `svg` or `pdf` with vl-convert, in this process, with no browser.

    The size of the picture is `width` x `height` pixels, times `scale`. A PNG and a JPG have that many pixels; an SVG
    says that size in its root, and is a vector: its drawing is the same at every scale; the page of a PDF is that
    size in points at 96 pixels to the inch, which is 0.75 point to the pixel (a picture of 700 x 500 pixels is a page
    of 525 x 375 points, as it was).
    """
    vlc = import_optional("vl_convert", "Rendering an image", extra="plotting")
    spec = sized_spec(chart, width, height)
    # a specification holds all its data, so no address is needed: none is let through
    options: dict[str, Any] = {"allowed_base_urls": []}
    factor = 1.0 if scale is None else scale
    if fmt == "png":
        return vlc.vegalite_to_png(spec, scale=factor, **options)
    if fmt == "jpg":
        return vlc.vegalite_to_jpeg(spec, scale=factor, **options)
    svg = vlc.vegalite_to_svg(spec, **options)
    if fmt == "pdf":
        # the page of a picture of 700 x 500 px is 525 x 375 pt, 96 px to the inch, as the browser that drew it before
        return vlc.svg_to_pdf(_scaled_svg(svg, _PDF_POINTS_PER_PIXEL * factor))
    if fmt == "svg":
        return _scaled_svg(svg, factor).encode()
    msg = f"{fmt!r} is no image vl-convert draws"
    raise KeyError(msg)


def _scaled_svg(svg: str, scale: float) -> str:
    """Write the size of an SVG `scale` times as large; the drawing is a vector and its `viewBox` stays."""
    if scale == 1:
        return svg

    def scaled(match: re.Match[str]) -> str:
        return f'{match.group(1)} width="{float(match.group(2)) * scale:g}" height="{float(match.group(3)) * scale:g}"'

    return _SVG_ROOT.sub(scaled, svg, count=1)
