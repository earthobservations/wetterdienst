# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The limits of a chart of the REST API hold for the chart as it is drawn (GH-3238).

The size of an image is the picture's, not the size asked for: a chart of rows too small for its labels is the smallest
that holds them, and `scale` multiplies that. The points of a chart are its rows, whatever its labels hold. The tests go
through the routes with the real chart; only the stand-in of the provider's data and, where the picture is not the
point, of the renderer are not real.

Offline. `tests/ui/conftest.py` switches the charts of the REST API on for this directory.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.ui.test_restapi import _image_params, _unreached, _values_result_of_shape
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import render, restapi

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wetterdienst.model.result import ValuesResult

LONG_SCHEMA = {
    "station_id": pl.String,
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "timestamp": pl.Datetime(time_zone="UTC"),
    "value": pl.Float64,
    "quality_flags": pl.String,
}


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers what the server would, its 500 included."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _parameters_of(request: DwdObservationRequest) -> list[tuple[str, str, str]]:
    return [(p.dataset.resolution.name, p.dataset.name, p.name) for p in request.parameters]


def _values_of(parameters: Sequence[tuple[str, str, str]], rows: int = 48) -> ValuesResult:
    """Build the values of one station for `parameters`, `rows` hourly values for each, as a result of a request."""
    request = DwdObservationRequest(parameters=list(parameters))
    base = _values_result_of_shape("long")
    start = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
    frame = pl.DataFrame(
        [
            {
                "station_id": "01048",
                "resolution": resolution,
                "dataset": dataset,
                "parameter": parameter,
                "timestamp": start + dt.timedelta(hours=hour),
                "value": float(hour % 7),
                "quality_flags": None,
            }
            for resolution, dataset, parameter in _parameters_of(request)
            for hour in range(rows)
        ],
        schema=LONG_SCHEMA,
    )
    return replace(base, stations=replace(base.stations, request=request), df=frame)


def _serve(monkeypatch: pytest.MonkeyPatch, result: ValuesResult) -> None:
    monkeypatch.setattr(restapi, "get_values", lambda **_kwargs: result)


def _ask(client: TestClient, **given: Any) -> Any:  # noqa: ANN401
    return client.get("/api/v1/values", params=_image_params({"stations": "01048"}, format="png", **given))


def _daily(count: int) -> list[tuple[str, str, str]]:
    names = DwdObservationRequest(parameters=[("daily", "climate_summary")]).parameters
    return [("daily", "climate_summary", parameter.name) for parameter in names[:count]]


def _twenty() -> list[tuple[str, str, str]]:
    """Twenty parameters of three resolutions and several datasets: the label of a row holds line breaks."""
    request = DwdObservationRequest(
        parameters=[
            ("daily", "climate_summary"),
            ("hourly", "temperature_air"),
            ("hourly", "wind"),
            ("hourly", "precipitation"),
        ]
    )
    return _parameters_of(request)[:20]


# --- the size is the picture's -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("parameters", "size"),
    [
        pytest.param(_daily(4), {"width": 1, "height": 1, "scale": 8192}, id="4-parameters-1x1-scale-8192"),
        pytest.param(_twenty(), {"width": 100, "height": 100, "scale": 80}, id="20-parameters-100x100-scale-80"),
        pytest.param(_daily(4), {"width": 8, "height": 8, "scale": 1000}, id="4-parameters-8x8-scale-1000"),
    ],
)
def test_a_chart_too_small_for_its_labels_is_measured_as_drawn_and_refused_above_8192_px(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, parameters: list[tuple[str, str, str]], size: dict[str, int]
) -> None:
    """The requested size times `scale` is within the limit; the labels make the picture larger, which is refused."""
    monkeypatch.setattr("wetterdienst.model.result.render_image", _unreached)
    _serve(monkeypatch, _values_of(parameters))

    response = _ask(client, **size)

    assert response.status_code == 400, response.text
    problem = response.json()
    assert problem["type"] == "urn:wetterdienst:problem:image-too-large"
    assert "The image would be" in problem["detail"]


def test_the_size_is_told_before_the_points_where_a_chart_is_over_both(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chart of more points than the cap and a picture past the side is the 400 `image-too-large`, as the order is."""
    monkeypatch.setattr(render, "MAX_IMAGE_POINTS", 10)
    monkeypatch.setattr("wetterdienst.model.result.render_image", _unreached)
    _serve(monkeypatch, _values_of(_daily(4)))

    response = _ask(client, width=1, height=1, scale=8192)

    assert response.status_code == 400, response.text
    assert response.json()["type"] == "urn:wetterdienst:problem:image-too-large"
    # the same chart at a fine size is told it has too many points
    assert _ask(client).json()["type"] == "urn:wetterdienst:problem:limit-exceeded"


def test_a_chart_of_a_normal_size_is_unaffected_by_the_measure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Four parameters at the default size, and at a size just above what holds the labels, are drawn."""
    _serve(monkeypatch, _values_of(_daily(4)))

    default = _ask(client)
    small = _ask(client, width=300, height=1000, scale=2)

    assert default.status_code == 200, default.text
    assert default.content.startswith(b"\x89PNG")
    assert small.status_code == 200, small.text
    assert small.content.startswith(b"\x89PNG")


def test_the_renderer_refuses_the_picture_it_would_draw_where_it_is_given_a_limit() -> None:
    """`render_image` has the limit too, for a caller that gives one: the check of the size before it is not alone."""
    pytest.importorskip("vl_convert")
    from wetterdienst.exceptions import ImageTooLargeError  # noqa: PLC0415
    from wetterdienst.io.export import check_image_size, render_image  # noqa: PLC0415

    chart = _values_of(_daily(4)).to_plot()

    with pytest.raises(ImageTooLargeError):
        render_image(chart, "png", width=1, height=1, scale=8192, max_side=8192)
    with pytest.raises(ImageTooLargeError):
        check_image_size(chart, 1, 1, 8192, 8192)
    # no limit, no refusal: the library and the command line (a small scale, so the test draws little)
    assert render_image(chart, "png", width=1, height=1, scale=1).startswith(b"\x89PNG")
    check_image_size(chart, 1, 1, 8192, None)


# --- the points are the rows ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "parameters",
    [
        pytest.param(
            [("daily", "climate_summary", "temperature_air_mean_2m"), ("daily", "more_precip", "snow_depth")],
            id="two-datasets",
        ),
        pytest.param(
            [("daily", "climate_summary", "temperature_air_mean_2m"), ("hourly", "wind", "wind_speed_mean")],
            id="two-resolutions",
        ),
    ],
)
def test_the_line_break_of_a_row_label_is_no_point(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, parameters: list[tuple[str, str, str]]
) -> None:
    """The label of a row holds a line break where there are several datasets or resolutions: rows count once."""
    monkeypatch.setattr(render, "MAX_IMAGE_POINTS", 1_000)
    monkeypatch.setattr("wetterdienst.model.result.render_image", lambda *_args, **_kwargs: b"drawn")
    result = _values_of(parameters, rows=450)
    assert "\n" in "".join(result.to_plot().to_dict()["datasets"].values())
    _serve(monkeypatch, result)

    within = _ask(client)
    # one row more than the limit, counted as rows: 2 x 501 = 1,002
    _serve(monkeypatch, _values_of(parameters, rows=501))
    over = _ask(client)

    assert within.status_code == 200, within.text
    assert over.status_code == 400, over.text
    problem = over.json()
    assert problem["type"] == "urn:wetterdienst:problem:limit-exceeded"
    assert (problem["limit"], problem["maximum"], problem["requested"]) == ("image_points", 1_000, 1_002)


def test_the_points_of_a_chart_are_its_rows_at_the_size_of_the_limit() -> None:
    """87,600 rows of two datasets are 87,600 points: the line breaks of the labels were counted for rows (GH-3238)."""
    from wetterdienst.io.charts import count_points  # noqa: PLC0415

    parameters = [("daily", "climate_summary", "temperature_air_mean_2m"), ("daily", "more_precip", "snow_depth")]
    chart = _values_of(parameters, rows=43_800).to_plot()

    assert count_points(chart) == 87_600
    assert "\n" in "".join(chart.to_dict()["datasets"].values())


# --- the station map -----------------------------------------------------------------------------------------------


def _stations_of(count: int) -> StationsResult:
    request = DwdObservationRequest(parameters=[("hourly", "temperature_air", "temperature_air_2m")])
    start = dt.datetime(1934, 1, 1, tzinfo=dt.UTC)
    frame = pl.DataFrame(
        {
            "resolution": ["hourly"] * count,
            "dataset": ["temperature_air"] * count,
            "station_id": [f"{index:06d}" for index in range(count)],
            "start_timestamp": [start] * count,
            "end_timestamp": [None] * count,
            "latitude": [47.0 + (index % 1000) * 0.008 for index in range(count)],
            "longitude": [6.0 + (index // 1000) * 0.06 for index in range(count)],
            "elevation": [10.0] * count,
            "name": [f"Station {index}" for index in range(count)],
            "region": ["x"] * count,
            "wmo_id": [None] * count,
            "wigos_id": [None] * count,
            "icao_id": [None] * count,
        },
        schema=STATIONS_SCHEMA,
    )
    return StationsResult(request=request, df=frame, _df_all=frame, _stations_filter=StationsFilter.ALL)


def _map(client: TestClient, monkeypatch: pytest.MonkeyPatch, count: int, fmt: str) -> Any:  # noqa: ANN401
    stations = _stations_of(count)
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)
    return client.get(
        "/api/v1/stations", params=_image_params({"all": "true"}, parameters="hourly/temperature_air", format=fmt)
    )


@pytest.mark.parametrize("fmt", ["png", "html"])
def test_a_map_of_more_than_100000_stations_is_refused_before_it_is_drawn(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """The map has a point for each station, and the cap is the chart's whatever it draws."""
    monkeypatch.setattr("wetterdienst.model.result.render_image", _unreached)
    monkeypatch.setattr("wetterdienst.model.result.chart_to_html", _unreached)

    response = _map(client, monkeypatch, 100_001, fmt)

    assert response.status_code == 400, response.text
    problem = response.json()
    assert problem["type"] == "urn:wetterdienst:problem:limit-exceeded"
    assert (problem["limit"], problem["maximum"], problem["requested"]) == ("image_points", 100_000, 100_001)


def test_a_map_of_the_limit_passes_the_checks(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """100,000 stations are not more than the cap: the renderer, stood in for here as it takes seconds, is reached."""
    monkeypatch.setattr("wetterdienst.model.result.render_image", lambda *_args, **_kwargs: b"drawn")

    assert _map(client, monkeypatch, 100_000, "png").content == b"drawn"


def test_a_small_map_is_drawn(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A map of 28 stations is a real image of the real chart."""
    response = _map(client, monkeypatch, 28, "png")

    assert response.status_code == 200, response.text
    assert response.content.startswith(b"\x89PNG")
