"""The charts wetterdienst draws today, drawn with Altair (Vega-Lite) and with matplotlib (GH-3238).

Three charts, the ones the library plots (see the pull request for the call sites):

- the values chart of `ValuesResult.to_plot`: one row of lines and markers per parameter, a colour per station;
- the station map of `StationsResult.to_plot`: the stations as points, a colour per dataset, a label per station;
- the climate stripes of `ui.core._plot_stripes`: one stripe per year, coloured by the year's value.

Each takes what the library already has in hand (a result, or the stripes data) and returns a figure of its
engine. `to_image` is the switch: the same subject, an engine (`plotly` calls the code that is in `src`, as it is),
a format. Nothing in `src/wetterdienst` knows this module.

Dependencies (none of them is in an extra): `altair>=6`, `vl-convert-python`, `matplotlib`. Altair with a polars
frame needs narwhals, which Altair depends on, and no pandas.
"""

from __future__ import annotations

import io
import math
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path

    from wetterdienst.model.result import StationsResult, ValuesResult
    from wetterdienst.ui.core import StripesData

Engine = Literal["plotly", "altair", "matplotlib"]
Format = Literal["html", "png", "jpg", "svg", "pdf"]

#: what Plotly renders at when nothing names a size (`io.export._DEFAULT_IMAGE_WIDTH`)
WIDTH, HEIGHT = 700, 500
#: the colour maps of `ui.core.CLIMATE_STRIPES_CONFIG`: matplotlib's names, and the Vega scheme that is the same ramp
STRIPES_SCHEMES = {
    "temperature": {"matplotlib": "RdBu", "vega": "redblue", "reverse": False},
    "precipitation": {"matplotlib": "BrBG_r", "vega": "brownbluegreen", "reverse": True},
}
GOLD = "gold"


@dataclass(frozen=True)
class Stripes:
    """What `_plot_stripes` draws: the data of `_get_stripes_data` and the flags of the request."""

    kind: Literal["temperature", "precipitation"]
    data: StripesData
    show_title: bool = True
    show_years: bool = True
    show_data_availability: bool = True


# --------------------------------------------------------------------------------------------------------------
# shared preparation
# --------------------------------------------------------------------------------------------------------------


def values_frame(result: ValuesResult) -> tuple[pl.DataFrame, int]:
    """Return the long frame `ValuesResult.to_plot` draws, a row label per parameter, and the number of rows of charts."""
    df = result.df
    if "parameter" not in df.columns:
        df = result._lengthen(df)  # noqa: SLF001
    units = result._unit_symbols()  # noqa: SLF001
    n = df.select(["resolution", "dataset", "parameter"]).n_unique()
    n_resolutions, n_datasets = df["resolution"].n_unique(), df["dataset"].n_unique()
    label = pl.concat_str(
        pl.col("parameter"),
        pl.lit(" ("),
        result._unit_symbol_key().replace(units),  # noqa: SLF001
        pl.lit(")"),
    )
    if n_datasets > 1:
        label = pl.concat_str(pl.col("dataset"), pl.lit("\n"), label)
    if n_resolutions > 1:
        label = pl.concat_str(pl.col("resolution"), pl.lit("\n"), label)
    return df.with_columns(label.alias("facet")).select("station_id", "facet", "timestamp", "value"), n


def _iso(df: pl.DataFrame) -> pl.DataFrame:
    """Write the timestamps as ISO 8601 text in UTC, which every JavaScript engine reads the same."""
    return df.with_columns(pl.col("timestamp").dt.convert_time_zone("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ"))


def stations_frame(result: StationsResult) -> pl.DataFrame:
    """Return the points of the station map: position, label and the dataset that colours it."""
    df = result.df
    label = pl.col("resolution") + pl.lit("/") + pl.col("dataset")
    # a stable order: the rows come in the order the station lists were joined, which changes from run to run, and
    # a point drawn over another one takes its colour
    return df.sort("resolution", "dataset", "station_id", descending=[False, True, False]).select(
        "longitude",
        "latitude",
        (pl.col("name") + pl.lit(" (") + pl.col("station_id") + pl.lit(")")).alias("name"),
        label.alias("dataset"),
    )


# --------------------------------------------------------------------------------------------------------------
# Altair
# --------------------------------------------------------------------------------------------------------------


def values_chart_altair(result: ValuesResult, *, width: int = WIDTH - 140, row_height: int = 260) -> Any:  # noqa: ANN401
    """Draw the values chart: lines and markers, a row per parameter, its own y axis per row."""
    import altair as alt  # noqa: PLC0415

    df, _ = values_frame(result)
    # The data goes in as the text of a CSV file, written by polars in one call and parsed by Vega-Lite:
    # - Altair's 5,000-row limit (`MaxRowsError`) is checked on a DataFrame or a list of records, not on text, and
    #   no global state is set, as `alt.data_transformers.disable_max_rows()` does;
    # - 87,000 rows cost 0.1 s to build, where 87,000 records cost 5 s in Altair and 5 s more to validate;
    # - `parse` is given for every column, as Vega-Lite would read the station id `00433` as the number 433.
    data = alt.InlineData(
        values=_iso(df).write_csv(),
        format=alt.CsvDataFormat(
            type="csv", parse={"station_id": "string", "facet": "string", "timestamp": "date", "value": "number"}
        ),
    )
    base = (
        alt.Chart(data)
        .mark_line(point=alt.OverlayMarkDef(size=14), strokeWidth=1)
        .encode(
            x=alt.X("timestamp:T", scale=alt.Scale(type="utc"), axis=alt.Axis(title=None, labelFlush=False)),
            y=alt.Y("value:Q", scale=alt.Scale(zero=False), axis=alt.Axis(title=None)),
            color=alt.Color("station_id:N", legend=alt.Legend(title=None, orient="top", direction="horizontal")),
        )
        .properties(width=width, height=row_height)
    )
    return base.facet(
        row=alt.Row("facet:N", title=None, header=alt.Header(labelOrient="top", labelAnchor="start", labelAngle=0))
    ).resolve_scale(y="independent")


def _projection(df: pl.DataFrame, width: int, height: int) -> dict[str, Any]:
    """Return the mercator centre and scale that fit the stations into the view with room for their labels."""
    west, east = df["longitude"].min(), df["longitude"].max()
    south, north = df["latitude"].min(), df["latitude"].max()
    clon, clat = (west + east) / 2, (south + north) / 2

    def merc(lat: float) -> float:
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    span_x = max(math.radians(east - west), 1e-3)
    span_y = max(merc(north) - merc(south), 1e-3)
    scale = 0.65 * min(width / span_x, height / span_y)
    return {"center": [clon, clat], "scale": scale}


def stations_chart_altair(
    result: StationsResult,
    *,
    basemap: list[dict[str, Any]] | None = None,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> Any:  # noqa: ANN401
    """Draw the station map: the stations over a vector basemap, a colour per dataset and a label per station."""
    import altair as alt  # noqa: PLC0415

    df = stations_frame(result)
    points = alt.Chart(alt.Data(values=df.to_dicts()))
    layers = []
    if basemap:
        layers.append(
            alt.Chart(alt.Data(values=basemap)).mark_geoshape(fill="#f1efe9", stroke="#9aa0a6", strokeWidth=0.7)
        )
    layers.append(
        points.mark_circle(size=70, opacity=0.95, stroke="white", strokeWidth=0.8).encode(
            longitude="longitude:Q",
            latitude="latitude:Q",
            color=alt.Color("dataset:N", legend=alt.Legend(title=None, orient="top", direction="horizontal")),
        )
    )
    layers.append(
        points.mark_text(align="left", dx=7, fontSize=9, color="#222").encode(
            longitude="longitude:Q", latitude="latitude:Q", text="name:N"
        )
    )
    return (
        alt.layer(*layers)
        .project(type="mercator", **_projection(df, width, height))
        .properties(width=width, height=height)
    )


def stripes_chart_altair(stripes: Stripes, *, width: int = WIDTH, height: int = HEIGHT) -> Any:  # noqa: ANN401
    """Draw the climate stripes: a rectangle per year, the gold availability line, the years and the source."""
    import altair as alt  # noqa: PLC0415

    scheme = STRIPES_SCHEMES[stripes.kind]
    df = stripes.data.df
    station = stripes.data.series.station
    years = df.get_column("timestamp").dt.year()
    first, last = int(years.min()), int(years.max())
    rows = df.with_columns(years.alias("year")).filter(pl.col("value_scaled").is_not_null())
    bars = rows.select("year", "value_scaled").with_columns((pl.col("year") + 1).alias("year_end"))
    x_scale = alt.Scale(domain=[first, last + 1], nice=False, zero=False)
    x = alt.X("year:Q", axis=None, scale=x_scale)
    y_scale = alt.Scale(domain=[-0.12, 1], nice=False)
    layers = [
        alt.Chart(alt.Data(values=bars.to_dicts()))
        .mark_rect()
        .encode(
            x=x,
            x2="year_end:Q",
            y=alt.Y("zero:Q", axis=None, scale=y_scale),
            y2="one:Q",
            color=alt.Color(
                "value_scaled:Q",
                legend=None,
                scale=alt.Scale(scheme=scheme["vega"], domain=[0, 1], reverse=scheme["reverse"]),
            ),
        )
        .transform_calculate(zero="0", one="1")
    ]
    if stripes.show_data_availability:
        availability = df.with_columns(years.alias("year")).select("year", "availability")
        layers.append(
            alt.Chart(alt.Data(values=availability.to_dicts()))
            # a year without data is a null: `invalid=None` keeps it and breaks the line there, as Plotly does
            .mark_line(color=GOLD, strokeWidth=2, invalid=None)
            .encode(x=x, y=alt.Y("availability:Q", axis=None, scale=y_scale))
        )
    labels = [{"x": (first + last + 1) / 2, "y": -0.095, "text": "Source: Deutscher Wetterdienst", "align": "center"}]
    if stripes.show_data_availability:
        labels.append({"x": first, "y": -0.05, "text": "data availability", "align": "left", "color": GOLD})
    if stripes.show_years:
        labels += [
            {"x": first, "y": -0.095, "text": str(first), "align": "left"},
            {"x": last + 1, "y": -0.095, "text": str(last), "align": "right"},
        ]
    for label in labels:
        layers.append(
            alt.Chart(alt.Data(values=[{"x": label["x"], "y": label["y"], "text": label["text"]}]))
            .mark_text(align=label["align"], baseline="middle", fontSize=11, color=label.get("color", "#222"))
            .encode(
                x=alt.X("x:Q", scale=x_scale, axis=None),
                y=alt.Y("y:Q", scale=y_scale, axis=None),
                text="text:N",
            )
        )
    chart = alt.layer(*layers).properties(width=width, height=height).configure_view(stroke=None)
    if stripes.show_title:
        title = f"Climate stripes ({stripes.kind}) for {station['name']}, Germany ({station['station_id']})"
        chart = chart.properties(title=alt.TitleParams(title, anchor="start", fontSize=14, fontWeight="normal"))
    return chart


def render_altair(chart: Any, fmt: Format, scale: float = 1.0) -> bytes | str:  # noqa: ANN401
    """Render a chart as `fmt` with vl-convert, in this process, without a browser. `scale` multiplies the pixels."""
    import vl_convert as vlc  # noqa: PLC0415

    spec = chart.to_dict()
    # the spec holds all its data, so no external request is ever needed: refuse them all. vl-convert 1.x takes the
    # allow-list per call; 2.0 (release candidates) takes it from `configure`, once for the process
    options: dict[str, Any] = {}
    if hasattr(vlc, "configure"):
        with _PATCH_LOCK:
            if not _VLC_CONFIGURED:
                vlc.configure(allowed_base_urls=[])
                _VLC_CONFIGURED.append(True)
    else:
        options["allowed_base_urls"] = []
    if fmt == "png":
        return vlc.vegalite_to_png(spec, scale=scale, **options)
    if fmt == "jpg":
        return vlc.vegalite_to_jpeg(spec, scale=scale, **options)
    if fmt == "svg":
        return vlc.vegalite_to_svg(spec, **options)
    if fmt == "pdf":
        return vlc.vegalite_to_pdf(spec, **options)
    if fmt == "html":
        return chart.to_html()
    msg = f"Invalid format: {fmt}"
    raise KeyError(msg)


# --------------------------------------------------------------------------------------------------------------
# matplotlib
# --------------------------------------------------------------------------------------------------------------


def values_figure_mpl(result: ValuesResult, *, width: float = 7.0, row_height: float = 3.0) -> Any:  # noqa: ANN401
    """Draw the values chart with matplotlib: lines and markers, a row per parameter, an axis per row."""
    import matplotlib.dates as mdates  # noqa: PLC0415
    from matplotlib.figure import Figure  # noqa: PLC0415

    df, n = values_frame(result)
    facets = df["facet"].unique(maintain_order=True).to_list()
    stations = df["station_id"].unique(maintain_order=True).to_list()
    colours = [f"C{i}" for i in range(len(stations))]
    fig = Figure(figsize=(width, row_height * n), layout="constrained")
    axes = fig.subplots(len(facets), 1, squeeze=False)[:, 0]
    for ax, facet in zip(axes, facets, strict=True):
        for station, colour in zip(stations, colours, strict=True):
            part = df.filter((pl.col("facet") == facet) & (pl.col("station_id") == station))
            ax.plot(part["timestamp"].to_list(), part["value"].to_list(), "-o", ms=2, lw=1, color=colour, label=station)
        ax.set_title(facet, loc="left", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
        ax.tick_params(labelsize=8)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=len(labels), frameon=False, fontsize=9)
    return fig


def stations_figure_mpl(
    result: StationsResult,
    *,
    basemap: list[dict[str, Any]] | None = None,
    width: float = 7.0,
    height: float = 5.0,
) -> Any:  # noqa: ANN401
    """Draw the station map with matplotlib: points over the polygons of the basemap, equal-angle aspect."""
    from matplotlib.figure import Figure  # noqa: PLC0415
    from matplotlib.patches import Polygon  # noqa: PLC0415

    df = stations_frame(result)
    fig = Figure(figsize=(width, height), layout="constrained")
    ax = fig.subplots()
    for feature in basemap or []:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in polygons:
            ax.add_patch(Polygon(polygon[0], closed=True, fc="#f1efe9", ec="#9aa0a6", lw=0.7))
    for i, dataset in enumerate(df["dataset"].unique(maintain_order=True).to_list()):
        part = df.filter(pl.col("dataset") == dataset)
        ax.scatter(
            part["longitude"], part["latitude"], s=40, color=f"C{i}", ec="white", lw=0.8, label=dataset, zorder=3
        )
    for row in df.iter_rows(named=True):
        ax.annotate(
            row["name"], (row["longitude"], row["latitude"]), xytext=(5, 0), textcoords="offset points", fontsize=7
        )
    west, east, south, north = df["longitude"].min(), df["longitude"].max(), df["latitude"].min(), df["latitude"].max()
    pad_x, pad_y = (east - west) * 0.25 + 0.01, (north - south) * 0.15 + 0.01
    ax.set_xlim(west - pad_x, east + pad_x)
    ax.set_ylim(south - pad_y, north + pad_y)
    # the mercator at this latitude, near enough: a degree of longitude is cos(lat) as long as a degree of latitude
    ax.set_aspect(1 / math.cos(math.radians((south + north) / 2)))
    ax.set_axis_off()
    fig.legend(loc="outside upper center", ncol=df["dataset"].n_unique(), frameon=False, fontsize=9)
    return fig


def stripes_figure_mpl(stripes: Stripes, *, width: float = 7.0, height: float = 5.0) -> Any:  # noqa: ANN401
    """Draw the climate stripes with matplotlib: `bar` with the colour map the Plotly version names."""
    import matplotlib as mpl  # noqa: PLC0415
    from matplotlib.figure import Figure  # noqa: PLC0415

    cmap = mpl.colormaps[STRIPES_SCHEMES[stripes.kind]["matplotlib"]]
    df = stripes.data.df
    years = df.get_column("timestamp").dt.year()
    first, last = int(years.min()), int(years.max())
    fig = Figure(figsize=(width, height))
    ax = fig.add_axes((0.02, 0.1, 0.96, 0.8))
    rows = df.with_columns(years.alias("year")).filter(pl.col("value_scaled").is_not_null())
    ax.bar(rows["year"], 1.0, width=1.0, align="edge", color=cmap(rows["value_scaled"].to_numpy()), lw=0)
    if stripes.show_data_availability:
        availability = df.with_columns(years.alias("year")).select("year", "availability").drop_nulls()
        ax.plot(availability["year"] + 0.5, availability["availability"], color=GOLD, lw=2)
        ax.text(first, -0.08, "data availability", color=GOLD, ha="left", va="center", fontsize=9)
    ax.text((first + last + 1) / 2, -0.08, "Source: Deutscher Wetterdienst", ha="center", va="center", fontsize=9)
    if stripes.show_years:
        ax.text(first, -0.15, str(first), ha="left", va="center", fontsize=9)
        ax.text(last + 1, -0.15, str(last), ha="right", va="center", fontsize=9)
    ax.set_xlim(first, last + 1)
    ax.set_ylim(-0.2, 1)
    ax.set_axis_off()
    if stripes.show_title:
        station = stripes.data.series.station
        title = f"Climate stripes ({stripes.kind}) for {station['name']}, Germany ({station['station_id']})"
        fig.text(0.02, 0.95, title, ha="left", va="center", fontsize=11)
    return fig


def render_matplotlib(fig: Any, fmt: Format, scale: float = 1.0) -> bytes:  # noqa: ANN401
    """Render a figure as `fmt` with the Agg backend; `scale` x 100 is the dpi, as it is the Plotly scale."""
    if fmt == "html":
        msg = "matplotlib draws no interactive HTML"
        raise KeyError(msg)
    buffer = io.BytesIO()
    kwargs: dict[str, Any] = {"format": "jpeg" if fmt == "jpg" else fmt, "dpi": 100 * scale}
    fig.savefig(buffer, **kwargs)
    return buffer.getvalue()


# --------------------------------------------------------------------------------------------------------------
# the switch
# --------------------------------------------------------------------------------------------------------------


def to_image(
    subject: ValuesResult | StationsResult | Stripes,
    *,
    engine: Engine,
    fmt: Format,
    scale: float = 1.0,
    basemap: Path | list[dict[str, Any]] | None = None,
    fit_plotly_zoom: bool = False,
) -> bytes | str:
    """Draw `subject` with `engine` as `fmt`. `plotly` goes through the code in `src`, which is unchanged.

    `fit_plotly_zoom` replaces the zoom `StationsResult.to_plot` sets (`12 - lat_diff`, which crops the stations
    out of the picture for a region of less than a few degrees) with one that fits them, for the side-by-side.
    """
    from wetterdienst.model.result import StationsResult, ValuesResult  # noqa: PLC0415

    features = _features(subject, basemap)
    if engine == "plotly":
        return _plotly(subject, fmt, scale, fit_zoom=fit_plotly_zoom)
    if engine == "altair":
        if isinstance(subject, ValuesResult):
            chart = values_chart_altair(subject)
        elif isinstance(subject, StationsResult):
            chart = stations_chart_altair(subject, basemap=features)
        else:
            chart = stripes_chart_altair(subject)
        return render_altair(chart, fmt, scale)
    if engine == "matplotlib":
        if isinstance(subject, ValuesResult):
            fig = values_figure_mpl(subject)
        elif isinstance(subject, StationsResult):
            fig = stations_figure_mpl(subject, basemap=features)
        else:
            fig = stripes_figure_mpl(subject)
        return render_matplotlib(fig, fmt, scale)
    msg = f"Unknown engine: {engine}"
    raise KeyError(msg)


def _features(subject: object, basemap: Path | list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Give the basemap features of the station map: a path is read and cut to the stations' view."""
    from pathlib import Path  # noqa: PLC0415

    from research.altair_vl_convert.basemap import load_features  # noqa: PLC0415
    from wetterdienst.model.result import StationsResult  # noqa: PLC0415

    if basemap is None or not isinstance(subject, StationsResult):
        return None
    if isinstance(basemap, Path):
        df = subject.df
        return load_features(
            basemap,
            df["longitude"].min() - 3,
            df["latitude"].min() - 2,
            df["longitude"].max() + 3,
            df["latitude"].max() + 2,
        )
    return basemap


def _fit_zoom(df: pl.DataFrame, width: int = WIDTH, height: int = HEIGHT) -> float:
    """Return the MapLibre zoom (512 px tiles) at which the stations fill 85 % of the picture."""

    def merc(lat: float) -> float:
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    span_x = max(math.radians(df["longitude"].max() - df["longitude"].min()), 1e-3)
    span_y = max(merc(df["latitude"].max()) - merc(df["latitude"].min()), 1e-3)
    world = 512 / (2 * math.pi)  # pixels per radian at zoom 0
    return min(math.log2(0.85 * width / (world * span_x)), math.log2(0.85 * height / (world * span_y)))


_VLC_CONFIGURED: list[bool] = []
_STRIPES_DATA: dict[tuple[str, str], StripesData] = {}
_PATCH_LOCK = threading.Lock()


def _serve_stripes_data_from_memory() -> None:
    """Make `_plot_stripes` read the data a caller has in hand, once: patching it per call is not thread safe."""
    from wetterdienst.ui import core  # noqa: PLC0415

    with _PATCH_LOCK:
        if getattr(core._get_stripes_data, "_research", False):  # noqa: SLF001
            return
        original = core._get_stripes_data  # noqa: SLF001

        def from_memory(request: Any) -> StripesData:  # noqa: ANN401
            return _STRIPES_DATA.get((request.kind, request.station)) or original(request)

        from_memory._research = True  # type: ignore[attr-defined]  # noqa: SLF001
        core._get_stripes_data = from_memory  # noqa: SLF001


def _plotly(subject: object, fmt: Format, scale: float, *, fit_zoom: bool = False) -> bytes | str:
    """Render with the code that is in `src`: `to_image` of a result, `_plot_stripes` for the stripes."""
    if isinstance(subject, Stripes):
        from wetterdienst.ui import core  # noqa: PLC0415
        from wetterdienst.ui.core import StripesImageRequest  # noqa: PLC0415

        station = subject.data.series.station
        request = StripesImageRequest(
            kind=subject.kind,
            station=station["station_id"],
            show_title=subject.show_title,
            show_years=subject.show_years,
            show_data_availability=subject.show_data_availability,
        )
        # the data is fetched once by the caller: only the figure and its image are timed
        _STRIPES_DATA[(subject.kind, station["station_id"])] = subject.data
        _serve_stripes_data_from_memory()
        fig = core._plot_stripes(request)  # noqa: SLF001
        if fmt == "html":
            return fig.to_html()
        return fig.to_image(fmt, scale=scale)
    if fit_zoom and hasattr(subject, "to_plot") and "longitude" in subject.df.columns:  # ty: ignore[unresolved-attribute]
        fig = subject.to_plot()  # ty: ignore[unresolved-attribute]
        fig.update_layout(map_zoom=_fit_zoom(subject.df))  # ty: ignore[unresolved-attribute]
        return fig.to_html() if fmt == "html" else fig.to_image(fmt, scale=scale)
    return subject.to_image(fmt=fmt, scale=scale)  # ty: ignore[unresolved-attribute]
