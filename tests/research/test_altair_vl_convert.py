# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The research prototype of GH-3238: Altair with vl-convert, and matplotlib, drawing what the library plots today.

Offline, on frames written here. Skipped where `altair`, `vl-convert-python` or `matplotlib` is not installed, which
none of the extras installs: `uv run --with altair --with vl-convert-python --with matplotlib pytest tests/research`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.model.result import StationsFilter, StationsResult, ValuesResult
from wetterdienst.model.schema import LONG_SCHEMA, STATIONS_SCHEMA
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.core import StripesData, StripesSeries

alt = pytest.importorskip("altair")
pytest.importorskip("vl_convert")
pytest.importorskip("matplotlib")

from research.altair_vl_convert import prototype  # noqa: E402
from research.altair_vl_convert.basemap import load_features  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n"


def _stations(n: int = 3) -> StationsResult:
    rows = [
        {
            "resolution": "hourly",
            "dataset": "temperature_air" if index % 2 else "solar",
            "station_id": f"0{index}048",
            "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
            "end_timestamp": None,
            "latitude": 51.0 + index * 0.3,
            "longitude": 13.0 + index * 0.2,
            "elevation": 228.0,
            "name": f"Station {index}",
            "region": "Sachsen",
        }
        for index in range(n)
    ]
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_2m")], settings=Settings(cache_disable=True)
    )
    df = pl.DataFrame(rows, schema=STATIONS_SCHEMA)
    return StationsResult(request=request, df=df, _df_all=df, _stations_filter=StationsFilter.BY_STATION_ID)


def _values(hours: int, station_ids: tuple[str, ...] = ("01048",)) -> ValuesResult:
    start = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
    rows = [
        {
            "resolution": "hourly",
            "dataset": "temperature_air",
            "parameter": "temperature_air_2m",
            "station_id": station_id,
            "timestamp": start + dt.timedelta(hours=hour),
            "value": float(hour % 17),
            "quality_flags": None,
        }
        for station_id in station_ids
        for hour in range(hours)
    ]
    return ValuesResult(stations=_stations(), df=pl.DataFrame(rows, schema=LONG_SCHEMA))


def _stripes(kind: str = "temperature") -> prototype.Stripes:
    years = list(range(1950, 2000))
    df = pl.DataFrame(
        {
            "timestamp": [dt.datetime(year, 1, 1, tzinfo=dt.UTC) for year in years],
            "value": [None if year in (1960, 1961) else 8.0 + (year - 1950) * 0.03 for year in years],
        }
    ).with_columns(
        pl.when(pl.col("value").is_null()).then(None).otherwise((pl.col("value") - 8.0) / 1.5).alias("value_scaled"),
        pl.when(pl.col("value").is_null()).then(None).otherwise(-0.02).alias("availability"),
    )
    station = {"station_id": "02290", "name": "Hohenpeißenberg"}
    series = StripesSeries(
        station=station, resolution="annual", dataset="climate_summary", parameter="temperature_air_mean_2m", unit="°C"
    )
    return prototype.Stripes(kind=kind, data=StripesData(series=series, df=df))  # ty: ignore[invalid-argument-type]


def test_a_values_chart_of_more_than_5000_rows_renders_and_leaves_altairs_limit_alone() -> None:
    """The data goes in as CSV text, which `MaxRowsError` does not count, and `data_transformers` stays as it is."""
    result = _values(hours=6000)
    before = alt.data_transformers.active
    spec = prototype.values_chart_altair(result).to_dict()
    assert alt.data_transformers.active == before
    assert spec["data"]["format"]["type"] == "csv"
    assert prototype.render_altair(prototype.values_chart_altair(result), "png").startswith(PNG)


def test_the_limit_is_what_the_prototype_goes_round() -> None:
    """The same 6000 rows as a polars frame are refused by Altair, which is the limit the CSV text avoids."""
    frame = _values(hours=6000).df
    with pytest.raises(alt.MaxRowsError):
        alt.Chart(frame).mark_line().encode(x="timestamp:T", y="value:Q").to_dict()


def test_a_station_id_with_a_leading_zero_stays_text() -> None:
    """Vega-Lite reads `00433` as the number 433 unless the column is parsed as a string."""
    chart = prototype.values_chart_altair(_values(hours=5, station_ids=("00433", "01048")))
    spec = chart.to_dict()
    assert spec["data"]["format"]["parse"]["station_id"] == "string"
    svg = prototype.render_altair(chart, "svg")
    assert isinstance(svg, str)
    assert "00433" in svg
    assert "01048" in svg


def test_the_values_chart_has_a_row_per_parameter_with_its_own_y_scale() -> None:
    """As `px.line(facet_row=...)` with `update_yaxes(matches=None)` does."""
    spec = prototype.values_chart_altair(_values(hours=5)).to_dict()
    assert spec["resolve"]["scale"]["y"] == "independent"
    assert spec["facet"]["row"]["field"] == "facet"


def test_the_formats_the_altair_engine_writes() -> None:
    """PNG, JPEG, SVG, PDF and HTML are written; WebP is not, which vl-convert cannot draw."""
    chart = prototype.stripes_chart_altair(_stripes())
    assert prototype.render_altair(chart, "png", scale=2).startswith(PNG)
    assert prototype.render_altair(chart, "jpg")[:3] == b"\xff\xd8\xff"
    assert str(prototype.render_altair(chart, "svg")).startswith("<svg")
    assert prototype.render_altair(chart, "pdf").startswith(b"%PDF")
    assert "<html" in str(prototype.render_altair(chart, "html")).lower()
    with pytest.raises(KeyError, match="Invalid format"):
        prototype.render_altair(chart, "webp")  # ty: ignore[invalid-argument-type]


def test_scale_multiplies_the_pixels_of_a_png() -> None:
    """`scale` is what `dpi / 100` is in the REST API and the CLI."""
    chart = prototype.stripes_chart_altair(_stripes())

    def size(scale: float) -> tuple[int, int]:
        png = prototype.render_altair(chart, "png", scale=scale)
        return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")

    (w1, h1), (w3, h3) = size(1), size(3)
    assert (w3, h3) == (w1 * 3, h1 * 3)


def test_the_stripes_of_a_gap_are_left_out_and_break_the_availability_line() -> None:
    """A year without data is no stripe and no point of the line, as in the Plotly stripes."""
    spec = prototype.stripes_chart_altair(_stripes()).to_dict()
    bars = spec["layer"][0]["data"]["values"]
    assert {1960, 1961}.isdisjoint(row["year"] for row in bars)
    assert len(bars) == 48
    line = spec["layer"][1]
    assert line["mark"]["invalid"] is None


def test_the_climate_colour_maps_are_the_ones_of_the_library() -> None:
    """Temperature is RdBu, precipitation BrBG reversed, in matplotlib's names and as the Vega scheme with `reverse`."""
    from wetterdienst.ui.core import CLIMATE_STRIPES_CONFIG  # noqa: PLC0415

    for kind, scheme in prototype.STRIPES_SCHEMES.items():
        assert scheme["matplotlib"] == CLIMATE_STRIPES_CONFIG[kind]["color_map"]  # ty: ignore[invalid-key]
    assert prototype.STRIPES_SCHEMES["precipitation"]["reverse"] is True
    spec = prototype.stripes_chart_altair(_stripes("precipitation")).to_dict()
    colour = spec["layer"][0]["encoding"]["color"]["scale"]
    assert colour["scheme"] == "brownbluegreen"
    assert colour["reverse"] is True


def test_the_station_map_draws_a_point_and_a_label_per_station_over_a_basemap(tmp_path: Path) -> None:
    """The layers are the basemap's polygons, a circle and a text per station; a country far away is cut out."""
    square = {"type": "Polygon", "coordinates": [[[12, 50], [14, 50], [14, 52], [12, 52], [12, 50]]]}
    far = {"type": "Polygon", "coordinates": [[[100, 10], [101, 10], [101, 11], [100, 10]]]}
    path = tmp_path / "countries.geojson"
    features = [{"type": "Feature", "properties": {"name": "x"}, "geometry": geometry} for geometry in (square, far)]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    features = load_features(path, 12.0, 50.0, 14.0, 52.0)
    assert len(features) == 1
    assert features[0]["properties"] == {}
    chart = prototype.stations_chart_altair(_stations(), basemap=features)
    spec = chart.to_dict()
    marks = [layer["mark"]["type"] if isinstance(layer["mark"], dict) else layer["mark"] for layer in spec["layer"]]
    assert marks == ["geoshape", "circle", "text"]
    assert prototype.render_altair(chart, "png").startswith(PNG)


def test_the_stations_are_drawn_in_a_stable_order() -> None:
    """The rows of a station list come in the order the lists were joined; the dataset drawn last is on top."""
    frame = prototype.stations_frame(_stations(4))
    assert frame["dataset"].to_list() == sorted(frame["dataset"].to_list(), reverse=True)


def test_matplotlib_draws_the_three_charts() -> None:
    """PNG, SVG and PDF of the three charts, and no HTML."""
    values = prototype.render_matplotlib(prototype.values_figure_mpl(_values(hours=48)), "png")
    stations = prototype.render_matplotlib(prototype.stations_figure_mpl(_stations()), "svg")
    stripes = prototype.render_matplotlib(prototype.stripes_figure_mpl(_stripes()), "pdf")
    assert values.startswith(PNG)
    assert stations.lstrip().startswith(b"<?xml")
    assert stripes.startswith(b"%PDF")
    with pytest.raises(KeyError, match="no interactive HTML"):
        prototype.render_matplotlib(prototype.stripes_figure_mpl(_stripes()), "html")


@pytest.mark.parametrize(
    ("west", "east", "south", "north", "low", "high"),
    [(6.0, 15.0, 47.0, 55.0, 4.0, 6.5), (13.3, 13.6, 52.4, 52.6, 9.5, 10.5)],
)
def test_the_zoom_that_fits_is_a_country_at_five_and_a_city_at_ten(
    west: float, east: float, south: float, north: float, low: float, high: float
) -> None:
    """The MapLibre zoom at which the stations fill the picture, which `StationsResult.to_plot` does not set."""
    df = pl.DataFrame({"longitude": [west, east], "latitude": [south, north]})
    assert low < prototype._fit_zoom(df) < high  # noqa: SLF001


def test_the_engine_is_a_switch_and_an_unknown_one_is_refused() -> None:
    """`to_image` is the switch between the engines."""
    with pytest.raises(KeyError, match="Unknown engine"):
        prototype.to_image(_stripes(), engine="gnuplot", fmt="png")  # ty: ignore[invalid-argument-type]


def test_the_engines_draw_the_same_values_chart_as_a_png() -> None:
    """Altair and matplotlib draw a PNG of a values result (Plotly needs a Chrome: measured, not tested)."""
    result = _values(hours=48, station_ids=("01048", "00433"))
    for engine in ("altair", "matplotlib"):
        assert prototype.to_image(result, engine=engine, fmt="png").startswith(PNG)  # ty: ignore[invalid-argument-type]


def test_nothing_in_the_library_imports_the_prototype() -> None:
    """The research stays beside the library: no module of `src` names it, and no extra installs what it needs."""
    root = Path(__file__).resolve().parents[2]
    offenders = [
        str(path.relative_to(root))
        for path in (root / "src" / "wetterdienst").rglob("*.py")
        if re.search(r"\b(altair|vl_convert|research\.altair_vl_convert)\b", path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "altair" not in pyproject
    assert "vl-convert" not in pyproject
