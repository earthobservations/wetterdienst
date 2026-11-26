# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The labels of the station map are placed by Vega's `label` transform (GH-3238, vl-convert 2).

Every dot stays; a label is placed round its dot where it is clear of the other labels and of every dot, and is
hidden (opacity 0) where it fits nowhere; a station of two datasets is labelled once; the page keeps the name of every
station in its tooltip. The positions and the opacity are read off the scenegraph vl-convert draws.
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import math
import random
import re
from typing import Any

import polars as pl
import pytest

pytest.importorskip("altair")
vlc = pytest.importorskip("vl_convert")

from wetterdienst import Settings  # noqa: E402
from wetterdienst.io import charts  # noqa: E402
from wetterdienst.io.export import chart_to_html, render_image  # noqa: E402
from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: E402
from wetterdienst.model.schema import STATIONS_SCHEMA  # noqa: E402
from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: E402

GERMANY = [
    ("Hamburg", 53.55, 9.99), ("Berlin", 52.52, 13.40), ("Munich", 48.14, 11.58), ("Cologne", 50.94, 6.96),
    ("Frankfurt", 50.11, 8.68), ("Stuttgart", 48.78, 9.18), ("Dresden", 51.05, 13.74), ("Leipzig", 51.34, 12.37),
    ("Hanover", 52.37, 9.73), ("Nuremberg", 49.45, 11.08), ("Bremen", 53.08, 8.80), ("Kiel", 54.32, 10.14),
    ("Rostock", 54.09, 12.14), ("Schwerin", 53.63, 11.41), ("Magdeburg", 52.13, 11.63), ("Erfurt", 50.98, 11.03),
    ("Kassel", 51.31, 9.48), ("Saarbruecken", 49.23, 7.00), ("Mainz", 50.00, 8.27), ("Freiburg", 47.99, 7.85),
    ("Konstanz", 47.66, 9.18), ("Passau", 48.57, 13.43), ("Regensburg", 49.01, 12.10), ("Wuerzburg", 49.79, 9.95),
    ("Muenster", 51.96, 7.63), ("Osnabrueck", 52.28, 8.04), ("Oldenburg", 53.14, 8.21), ("Flensburg", 54.78, 9.44),
    ("Greifswald", 54.09, 13.38), ("Cottbus", 51.76, 14.33), ("Potsdam", 52.40, 13.07), ("Goerlitz", 51.15, 14.99),
    ("Hof", 50.31, 11.91), ("Trier", 49.75, 6.64), ("Aachen", 50.78, 6.08), ("Bielefeld", 52.02, 8.53),
    ("Ulm", 48.40, 9.99), ("Augsburg", 48.37, 10.90), ("Zugspitze", 47.42, 10.98), ("Brocken", 51.80, 10.62),
]  # fmt: skip


def _stations(
    points: list[tuple[str, float, float]], datasets: tuple[str, ...] = ("temperature_air",)
) -> StationsResult:
    """Make stations of `points`, a row for each dataset (every second station only in the datasets after the first)."""
    rows = [
        {
            "resolution": "hourly",
            "dataset": dataset,
            "station_id": f"{index + 1:05d}",
            "start_timestamp": dt.datetime(1934, 1, 1, tzinfo=dt.UTC),
            "end_timestamp": None,
            "latitude": lat,
            "longitude": lon,
            "elevation": 10.0,
            "name": name,
            "region": "x",
        }
        for position, dataset in enumerate(datasets)
        for index, (name, lat, lon) in enumerate(points)
        if not position or index % 2 == 0
    ]
    df = pl.DataFrame(rows, schema=STATIONS_SCHEMA)
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_2m")], settings=Settings(cache_disable=True)
    )
    return StationsResult(request=request, df=df, _df_all=df, _stations_filter=StationsFilter.ALL)


def _vega(chart: Any) -> dict[str, Any]:  # noqa: ANN401
    """Give the Vega the chart is drawn from as an image."""
    return charts._vega_of(charts.sized_spec(chart, 700, 500))  # noqa: SLF001


def _scenegraph(chart: Any) -> dict[str, Any]:  # noqa: ANN401
    """Draw the chart as an image does and give what vega drew: the marks by their names."""
    graph = vlc.vega_to_scenegraph(_vega(chart))
    found: dict[str, Any] = {}

    def walk(node: Any) -> None:  # noqa: ANN401
        if isinstance(node, dict):
            if "marktype" in node and node.get("name"):
                found[node["name"]] = node
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(graph)
    return found


def _dots(chart: Any) -> list[dict[str, Any]]:  # noqa: ANN401
    """Give the items of the mark of the dots: the first mark of circles of the chart."""
    name = next(mark["name"] for mark in _vega(chart)["marks"] if mark["type"] == "symbol")
    return _scenegraph(chart)[name]["items"]


def _boxes(
    chart: Any,  # noqa: ANN401
    per_character: float = 4.4,
) -> tuple[list[tuple[str, tuple[float, float, float, float]]], list[tuple[float, float]]]:
    """Give the boxes of the visible labels, as small as the text can be, and the centres of the dots.

    The box is a little narrower and lower than the text (4.4 pixels a character, 8 high), placed as the align and the
    baseline of the label say: a test that finds two of them overlap has found labels that overlap.
    """
    labels = []
    for item in _scenegraph(chart)["label_text"]["items"]:
        if item["opacity"] == 0:
            continue
        width = per_character * len(item["text"])
        left = {"left": item["x"], "right": item["x"] - width}.get(item["align"], item["x"] - width / 2)
        top = {"top": item["y"], "bottom": item["y"] - 8}.get(item["baseline"], item["y"] - 4)
        labels.append((item["text"], (left, top, left + width, top + 8)))
    return labels, [(item["x"], item["y"]) for item in _dots(chart)]


def _overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_a_dense_map_keeps_no_label_on_another_label_or_on_a_dot() -> None:
    """Forty stations of two datasets in a picture of 700 x 500: what is shown is clear of everything else."""
    result = _stations(GERMANY, ("temperature_air", "precipitation"))
    labels, dots = _boxes(result.to_plot())

    assert 25 <= len(labels) <= 40
    for (first, a), (second, b) in itertools.combinations(labels, 2):
        assert not _overlap(a, b), (first, second)
    for name, box in labels:
        assert not any(box[0] < x < box[2] and box[1] < y < box[3] for x, y in dots), name


def test_every_dot_stays() -> None:
    """The dots are the rows of the data, labelled or not, and none of them is moved by the labels."""
    result = _stations(GERMANY, ("temperature_air", "precipitation"))
    assert len(_dots(result.to_plot())) == result.df.height


def test_a_sparse_map_keeps_every_label() -> None:
    """Four stations far apart: nothing collides, so all four are shown."""
    result = _stations(GERMANY[:4])
    labels, _ = _boxes(result.to_plot())

    assert sorted(name for name, _ in labels) == sorted(f"{n} ({i:05d})" for i, (n, _, _) in enumerate(GERMANY[:4], 1))


def test_a_station_of_two_datasets_is_labelled_once() -> None:
    """The rows of a station in a second dataset are dots on the same spot: one label for both."""
    result = _stations(GERMANY[:6], ("temperature_air", "precipitation"))
    labels, dots = _boxes(result.to_plot())

    assert len(dots) > 6
    names = [name for name, _ in labels]
    assert len(names) == len(set(names)) == 6


def _placed(chart: Any) -> list[tuple[str, float, float, float]]:  # noqa: ANN401
    return [
        (item["text"], item.get("x"), item.get("y"), item["opacity"])
        for item in _scenegraph(chart)["label_text"]["items"]
    ]


def test_the_same_stations_give_the_same_labels_in_whatever_order() -> None:
    """The labels are taken in the order of the names, not of the rows: shuffles give the same picture."""
    result = _stations(GERMANY, ("temperature_air", "precipitation"))
    expected = _placed(result.to_plot())
    assert _placed(result.to_plot()) == expected

    frame = result.df
    for seed in range(3):
        rows = list(range(frame.height))
        random.Random(seed).shuffle(rows)  # noqa: S311
        shuffled = StationsResult(
            request=result.request, df=frame[rows], _df_all=frame[rows], _stations_filter=StationsFilter.ALL
        )
        assert _placed(shuffled.to_plot()) == expected


def test_the_page_places_the_labels_in_the_browser_and_keeps_every_name_in_its_tooltip() -> None:
    """The page is the Vega that is drawn as an image, with the `label` transform, and the data of all the dots."""
    result = _stations(GERMANY, ("temperature_air", "precipitation"))
    chart = result.to_plot()
    names = [f"{n} ({i:05d})" for i, (n, _, _) in enumerate(GERMANY, 1)]

    for inline in (True, False):
        page = chart_to_html(chart) if inline else charts.chart_to_html(chart, inline=False)
        start = re.search(r"(?:var|const) spec = ", page).end()  # type: ignore[union-attr]
        spec, _ = json.JSONDecoder().raw_decode(page[start:])
        transforms = [t for mark in spec["marks"] for t in mark.get("transform", []) if t["type"] == "label"]
        # vega-embed gets a Vega specification: the Vega-Lite one has no such transform
        assert "vega-lite" not in spec["$schema"]
        assert len(transforms) == 2
        assert all(name in page for name in names)
        dots = next(mark for mark in spec["marks"] if mark["type"] == "symbol")
        assert "tooltip" in dots["encode"]["update"]
        assert transforms[0]["avoidMarks"] == [dots["name"]]


def test_the_labels_are_set_in_the_font_of_every_chart() -> None:
    """The text of a label is Liberation Sans as the rest is, not the generic font Vega falls back to."""
    svg = render_image(_stations(GERMANY[:4]).to_plot(), "svg").decode()

    assert 'font-family="sans-serif"' not in svg


def test_no_text_of_the_map_is_the_word_null() -> None:
    """A label that is hidden is drawn with no opacity, and none is an empty text, which would read null."""
    result = _stations(GERMANY, ("temperature_air", "precipitation"))
    svg = render_image(result.to_plot(), "svg").decode()
    texts = re.findall(r"<text\b[^>]*>([^<]*)</text>", svg)

    assert texts
    assert "null" not in texts
    assert "" not in texts


def test_a_name_on_two_spots_is_labelled_at_the_same_one_in_whatever_order() -> None:
    """Two rows of one name at two spots (a station two datasets place differently): the same dot is labelled."""
    rows = [("Same (00001)", 50.0, 10.0), ("Same (00001)", 50.2, 10.4), ("Other (00002)", 51.0, 11.0)]
    frames = [
        pl.DataFrame(
            {
                "longitude": [r[2] for r in order],
                "latitude": [r[1] for r in order],
                "name": [r[0] for r in order],
                "dataset": "d",
            }
        )
        for order in (rows, rows[::-1])
    ]
    center = {"lat": 50.5, "lon": 10.5}

    first, second = (_placed(charts.stations_chart(frame, center=center, zoom=6)) for frame in frames)

    assert first == second


COAST = [
    ("Kiel", 54.38, 10.14), ("Schleswig", 54.53, 9.55), ("Buesum", 54.13, 8.86), ("Cuxhaven", 53.87, 8.71),
    ("Hamburg", 53.63, 9.99), ("Fehmarn", 54.53, 11.06), ("Eckernfoerde", 54.47, 9.84), ("Bremerhaven", 53.54, 8.58),
    ("Luebeck", 53.80, 10.72), ("Husum", 54.48, 9.05), ("Heide", 54.20, 9.10), ("Itzehoe", 53.92, 9.52),
    ("Neumuenster", 54.07, 9.98), ("Rendsburg", 54.30, 9.66), ("Flensburg", 54.78, 9.44), ("Sylt", 54.92, 8.35),
    ("Brunsbuettel", 53.89, 9.14), ("Stade", 53.60, 9.48), ("Gluecksstadt", 53.79, 9.43), ("Eutin", 54.14, 10.61),
    ("Ploen", 54.16, 10.42), ("Meldorf", 54.09, 9.07), ("Toenning", 54.32, 8.94), ("Schlei", 54.56, 9.90),
]  # fmt: skip


def _crowded(extra: int) -> list[tuple[str, float, float]]:
    """Give the stations of Germany and `extra` more, each near one of them: too many for every label to fit."""
    rng = random.Random(11)  # noqa: S311
    points = list(GERMANY)
    for index in range(extra):
        name, lat, lon = GERMANY[rng.randrange(len(GERMANY))]
        points.append((f"Near{name}{index}", lat + rng.uniform(-0.25, 0.25), lon + rng.uniform(-0.35, 0.35)))
    return points


def _candidates(anchor: tuple[float, float], text: str) -> list[tuple[float, float, float, float]]:
    """Give the boxes a label of `text` can be put in round `anchor`, as the transform tries them: 8 sides, 3 distances.

    The box is as large as the text can be (5.6 pixels a character and 2 more, 12 high), where the boxes it has to be
    clear of are 5.3 pixels a character and 3 more all round (`_blocked`): a place that is free of them is free
    whatever the font makes of the text, so a label with such a place left should not have been hidden.
    """
    x, y = anchor
    width = 5.6 * len(text) + 2
    boxes = []
    for offset in (6, 14, 24):
        near = offset + 0.5
        diagonal = offset / math.sqrt(2) + 0.5
        for dx, dy in (
            (near, 0), (-near, 0), (0, -near), (0, near),
            (diagonal, -diagonal), (-diagonal, -diagonal), (diagonal, diagonal), (-diagonal, diagonal),
        ):  # fmt: skip
            left = x + dx if dx > 0 else x + dx - width if dx < 0 else x - width / 2
            top = y - 6 if dy == 0 else y + dy if dy > 0 else y + dy - 12
            boxes.append((left, top, left + width, top + 12))
    return boxes


def _blocked(chart: Any) -> tuple[list[str], list[str]]:  # noqa: ANN401
    """Give the labels that are hidden and, of them, the ones that had a box free: those should not be hidden."""
    drawn = _scenegraph(chart)
    labels, dots = _boxes(chart, per_character=5.3)
    # what a label has to be clear of, with the 3 pixels the font and the pixels the transform works in take
    taken = [(b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3) for _, b in labels]
    taken += [(x - 7.4, y - 7.4, x + 7.4, y + 7.4) for x, y in dots]
    hidden, free = [], []
    view = (0.0, 0.0, 680.0, 433.0)
    for item, anchor in zip(drawn["label_text"]["items"], drawn["layer_2_marks"]["items"], strict=True):
        if item["opacity"] != 0:
            continue
        hidden.append(item["text"])
        for box in _candidates((anchor["x"], anchor["y"]), item["text"]):
            inside = box[0] >= view[0] and box[1] >= view[1] and box[2] <= view[2] and box[3] <= view[3]
            if inside and not any(_overlap(box, other) for other in taken):
                free.append(item["text"])
                break
    return hidden, free


@pytest.mark.parametrize(
    ("points", "datasets"),
    [
        pytest.param(GERMANY, ("temperature_air", "precipitation"), id="germany-40"),
        pytest.param(COAST, ("temperature_air",), id="coast-24"),
        pytest.param(GERMANY[:5], ("temperature_air",), id="small-5"),
    ],
)
def test_the_maps_of_the_pictures_hide_no_label(
    points: list[tuple[str, float, float]], datasets: tuple[str, ...]
) -> None:
    """Forty stations of two datasets, the coast and a small map: every dot has its label."""
    hidden, _ = _blocked(_stations(points, datasets).to_plot())

    assert hidden == []


@pytest.mark.parametrize("extra", [30, 60, 100])
def test_a_dot_has_no_label_only_where_every_place_for_it_is_taken(extra: int) -> None:
    """On a map with too many stations, a label that is hidden has none of its 24 places free (side and distance)."""
    hidden, free = _blocked(_stations(_crowded(extra)).to_plot())

    assert hidden
    assert free == []


def test_the_most_crowded_stations_are_placed_first_which_hides_fewer_labels() -> None:
    """Seventy stations, 30 of them beside another: in the order of the names 15 labels were hidden, crowded first 8."""
    hidden, _ = _blocked(_stations(_crowded(30)).to_plot())

    assert len(hidden) <= 10


def test_the_candidates_of_the_transform_are_the_8_sides_at_3_distances() -> None:
    """The places the test above works out are the ones the transform is given: 24 of them."""
    spec = _vega(_stations(GERMANY[:3]).to_plot())
    transform = next(m["transform"][0] for m in spec["marks"] if m["name"] == "label_text")

    assert transform["anchor"] == charts._SIDES * 3  # noqa: SLF001
    assert transform["offset"] == [6] * 8 + [14] * 8 + [24] * 8
