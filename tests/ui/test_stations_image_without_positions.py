# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A map of stations none of which has a position is a 422, not a 500 (GH-4206).

DWD gives the regions of its pollen forecast no position (`dwd/pollen`), so the figure of their map cannot fit its
extent. The library raises `NoStationPositionsError` (a `RequestError`), REST answers it with a 422, the command line
with a usage error (exit 2) and an MCP tool with a tool error, all with the same sentence. Stations of which only some
have a position are drawn without the others.
"""

from __future__ import annotations

import datetime as dt
import pickle
from typing import Any

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst import Settings
from wetterdienst.exceptions import NoStationPositionsError, RequestError
from wetterdienst.io.charts import count_points
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.pollen import DwdPollenRequest
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.core import failure_status

MESSAGE = "These stations have no position, so no map can be drawn; ask for json, csv or geojson instead."
IMAGE_FORMATS = ["html", "svg", "png"]
QUERY = {"provider": "dwd", "network": "pollen", "parameters": "daily/data", "all": "true"}


@pytest.fixture(autouse=True)
def _altair(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN401
    pytest.importorskip("altair")
    pytest.importorskip("vl_convert")
    monkeypatch.chdir(tmp_path)


def _stations_drawn(chart: Any) -> list[str]:  # noqa: ANN401
    """Give the labels of the stations a map holds: the data of its points, which is the text of a CSV file."""
    (text,) = (data for data in chart.to_dict()["datasets"].values() if isinstance(data, str))
    header, *lines = text.splitlines()
    column = header.split(",").index("name")
    return sorted(line.split(",")[column] for line in lines)


def _pollen() -> StationsResult:
    return DwdPollenRequest(parameters=[("daily", "data")], settings=Settings(cache_disable=True)).all()


def _result(points: list[tuple[float | None, float | None]]) -> StationsResult:
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


def test_the_library_raises_the_request_error_for_stations_none_of_which_has_a_position() -> None:
    """`to_plot` of the pollen regions is a `NoStationPositionsError`, a `RequestError`, not a `TypeError`."""
    result = _pollen()
    assert result.df["latitude"].null_count() == result.df.height > 0
    with pytest.raises(NoStationPositionsError) as error:
        result.to_plot()
    assert str(error.value) == MESSAGE
    assert isinstance(error.value, RequestError)


@pytest.mark.parametrize("fmt", IMAGE_FORMATS)
def test_the_library_raises_it_for_every_image_format(fmt: str) -> None:
    """`to_image` goes through `to_plot`, so each format of the map says the same, before a browser is started."""
    with pytest.raises(NoStationPositionsError, match="no map can be drawn"):
        _pollen().to_image(fmt=fmt)


def test_the_error_is_a_422_and_survives_a_pickle() -> None:
    """The one request error that `failure_status` gives a 422, and it is rebuilt from nothing but its class."""
    assert failure_status(NoStationPositionsError()) == 422
    copy = pickle.loads(pickle.dumps(NoStationPositionsError()))  # noqa: S301
    assert type(copy) is NoStationPositionsError
    assert str(copy) == MESSAGE


@pytest.mark.parametrize("fmt", IMAGE_FORMATS)
def test_rest_answers_a_map_of_stations_without_a_position_with_a_422(fmt: str) -> None:
    """png, svg and html are a 422 problem that says to ask for json, csv or geojson."""
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/stations", params={**QUERY, "format": fmt}
    )
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == 422
    assert problem["detail"] == MESSAGE
    # the kind is `invalid-parameters`, which promises an entry for each invalid parameter: it is `format`
    assert problem["type"] == "urn:wetterdienst:problem:invalid-parameters"
    assert problem["errors"] == [{"type": "no_positions", "loc": ["query", "format"], "msg": MESSAGE}]


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
def test_rest_still_lists_the_stations_in_the_formats_the_message_names(fmt: str) -> None:
    """The three formats the 422 points to answer, with the stations as the source gives them: no position."""
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/stations", params={**QUERY, "format": fmt}
    )
    assert response.status_code == 200, response.text
    assert "Mainfranken" in response.text


@pytest.mark.parametrize("fmt", IMAGE_FORMATS)
def test_the_command_line_tells_it_as_a_usage_error(fmt: str) -> None:
    """One line and exit 2, as for any refusal of the request, not a traceback."""
    result = CliRunner().invoke(
        cli, ["stations", "--provider=dwd", "--network=pollen", "--parameters=daily/data", "--all", f"--format={fmt}"]
    )
    assert result.exit_code == 2, result.output
    assert MESSAGE in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
def test_the_command_line_still_lists_the_stations_in_the_formats_the_message_names(fmt: str) -> None:
    """The three formats the usage error points to answer, with the stations as the source gives them."""
    result = CliRunner().invoke(
        cli, ["stations", "--provider=dwd", "--network=pollen", "--parameters=daily/data", "--all", f"--format={fmt}"]
    )
    assert result.exit_code == 0, result.output
    assert "Mainfranken" in result.output


def test_stations_of_which_only_some_have_a_position_are_drawn_without_the_others() -> None:
    """A mix draws as it did: the stations with no position are left out of the map, which fits the others."""
    result = _result([(52.52, 13.405), (None, None), (50.0, 10.0), (51.0, None)])
    chart = result.to_plot()
    # the two stations that have a position are the ones it can place, and the zoom is fitted to them
    assert _stations_drawn(chart) == ["Station 0 (00000)", "Station 2 (00002)"]
    assert chart.to_dict()["projection"]["scale"] > 0
    assert "<html" in result.to_image(fmt="html")


def test_stations_none_of_which_has_a_complete_position_are_refused() -> None:
    """A latitude without a longitude is no position: the box of the map would be fitted to nothing."""
    with pytest.raises(NoStationPositionsError):
        _result([(51.0, None), (None, 10.0)]).to_plot()


def test_no_station_at_all_is_an_empty_chart_as_before() -> None:
    """A listing that is empty is no refusal: there is nothing to say about positions."""
    assert count_points(_result([]).to_plot()) == 0


@pytest.mark.parametrize("fmt", IMAGE_FORMATS)
def test_the_postal_codes_of_the_correction_factor_are_refused_as_pollen_is(
    fmt: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`dwd/derived`'s `monthly/climate_correction_factor` has 100000 stations, no position: a 422, not a TypeError."""
    from wetterdienst.provider.dwd.derived import api as derived_api  # noqa: PLC0415

    monkeypatch.setattr(
        derived_api,
        "create_file_index_for_climate_derived",
        lambda *_args, **_kwargs: pl.LazyFrame({"station_id": []}, schema={"station_id": pl.String}),
    )
    params = {
        "provider": "dwd",
        "network": "derived",
        "parameters": "monthly/climate_correction_factor",
        "all": "true",
        "format": fmt,
    }
    response = TestClient(restapi.app, raise_server_exceptions=False).get("/api/stations", params=params)
    assert response.status_code == 422, response.text[:300]
    assert response.json()["detail"] == MESSAGE


def test_a_station_with_a_latitude_only_does_not_widen_the_map() -> None:
    """The view is fitted to the stations with both coordinates: a latitude of -30 and no longitude is not on it."""
    alone = _result([(52.52, 13.405), (52.6, 13.5)]).to_plot().to_dict()["projection"]
    with_half = _result([(52.52, 13.405), (52.6, 13.5), (-30.0, None), (None, 120.0)]).to_plot().to_dict()["projection"]
    assert with_half["scale"] == pytest.approx(alone["scale"])
    assert with_half["center"] == pytest.approx(alone["center"])
    # a picture of another size is fitted again to the same stations
    result = _result([(52.52, 13.405), (52.6, 13.5), (-30.0, None)])
    assert result._map_view(300, 300)[1] == pytest.approx(  # noqa: SLF001
        _result([(52.52, 13.405), (52.6, 13.5)])._map_view(300, 300)[1]  # noqa: SLF001
    )
