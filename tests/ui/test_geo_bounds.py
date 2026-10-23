# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What one request of `interpolate` or `summarize` may ask for on the REST API and MCP (GH-2606).

The radius, the number of additional stations and the gain a station has to bring are bounded in the request of
the server, and the stations within reach of the point are held to the limit of stations before any value is
downloaded. The library and the command line take what they always took.

Offline: the station list is stood in for, and the reader of the values raises where a download would begin.
"""

from __future__ import annotations

import datetime as dt
import math
import os
from queue import Queue
from typing import TYPE_CHECKING

import polars as pl
import pytest
from fastapi.testclient import TestClient

from wetterdienst import exceptions
from wetterdienst.core.interpolate import (
    MAX_STATION_GROUPS,
    apply_interpolation,
    calculate_interpolation,
    get_valid_station_groups,
    has_valid_station_group,
)
from wetterdienst.core.util import _ParameterData
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import restapi
from wetterdienst.ui.core import (
    MAX_ADDITIONAL_STATIONS,
    MAX_STATION_DISTANCE,
    InterpolationRequest,
    RestInterpolationRequest,
    RestSummaryRequest,
    SummaryRequest,
)
from wetterdienst.util.response_warnings import _COUNTED, _RECORDED

if TYPE_CHECKING:
    from pathlib import Path

_OBSERVATION = {"provider": "dwd", "network": "observation", "parameters": "daily/kl/temperature_air_mean_2m"}
_POINT = {"latitude": 50.0, "longitude": 10.0, "timestamp": "2020-01-01/2020-01-03"}
_DOWNLOAD = "a download began"
_ENDPOINTS = [
    pytest.param("interpolate", "interpolation_station_distance", id="interpolate"),
    pytest.param("summarize", "summary_station_distance", id="summarize"),
]


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    _RECORDED.set(None)
    _COUNTED.set(None)
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _stations_along_a_meridian(
    n: int, spacing: float, *, closed: int = 0, dataset: str = "climate_summary"
) -> pl.DataFrame:
    """Give `n` stations of the daily `dataset`, `spacing` degrees of latitude apart from 50 N, 10 E on.

    The first `closed` of them stopped reporting in 1990.
    """
    return pl.DataFrame(
        {
            "resolution": ["daily"] * n,
            "dataset": [dataset] * n,
            "station_id": [f"{i:05d}" for i in range(n)],
            "start_timestamp": [dt.datetime(1950, 1, 1, tzinfo=dt.UTC)] * n,
            "end_timestamp": [dt.datetime(1990, 1, 1, tzinfo=dt.UTC)] * closed
            + [dt.datetime(2021, 1, 1, tzinfo=dt.UTC)] * (n - closed),
            "latitude": [50.0 + i * spacing for i in range(n)],
            "longitude": [10.0] * n,
            "elevation": [100.0] * n,
            "name": [f"station {i}" for i in range(n)],
            "state": ["state"] * n,
        },
        schema_overrides={"start_timestamp": pl.Datetime("us", "UTC"), "end_timestamp": pl.Datetime("us", "UTC")},
    )


def _stand_in_for_the_stations(monkeypatch: pytest.MonkeyPatch, df: pl.DataFrame) -> list[str]:
    """List `df` as the stations of dwd/observation, and make the reader of the values raise where a download begins.

    Gives the downloads that were begun, so a test can say that none was.
    """
    begun: list[str] = []

    def all_(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(request=self, df=df, _df_all=df, _stations_filter=StationsFilter.ALL)

    def values(self: StationsResult) -> None:
        # the stations the walk is about to read
        begun.append(f"{_DOWNLOAD}: {self.df.get_column('station_id').n_unique()}")
        raise exceptions.RequestError(_DOWNLOAD)

    monkeypatch.setattr(DwdObservationRequest, "all", all_)
    monkeypatch.setattr(StationsResult, "values", values)
    return begun


# --- the stations within reach ----------------------------------------------------------------------------------


@pytest.mark.parametrize(("endpoint", "distance"), _ENDPOINTS)
def test_a_point_with_more_stations_in_reach_than_the_limit_is_refused_before_a_download(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, distance: str
) -> None:
    """150 stations within the radius are a 400 of the kind `limit-exceeded` that names the field to narrow it."""
    begun = _stand_in_for_the_stations(monkeypatch, _stations_along_a_meridian(150, spacing=0.002))

    response = client.get(f"/api/v1/{endpoint}", params={**_OBSERVATION, **_POINT})

    assert response.status_code == 400
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:limit-exceeded"
    assert (body["limit"], body["maximum"], body["requested"]) == ("stations", 100, 150)
    assert f"`{distance}`" in body["detail"]
    assert begun == []


@pytest.mark.parametrize(("endpoint", "distance"), _ENDPOINTS)
def test_a_wider_radius_that_reaches_more_stations_than_the_limit_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, distance: str
) -> None:
    """The stations 5 km apart are 8 within the radius of 40 km and 36 within 200 km, of a limit of 10."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "10")
    begun = _stand_in_for_the_stations(monkeypatch, _stations_along_a_meridian(150, spacing=0.05))

    narrow = client.get(f"/api/v1/{endpoint}", params={**_OBSERVATION, **_POINT})
    wide = client.get(
        f"/api/v1/{endpoint}", params={**_OBSERVATION, **_POINT, f"{distance}_homogeneous": MAX_STATION_DISTANCE}
    )

    # within the limit the request goes on to the values, where it is stopped by the stand-in
    assert (narrow.status_code, narrow.json()["detail"]) == (400, _DOWNLOAD)
    assert wide.json()["type"] == "urn:wetterdienst:problem:limit-exceeded"
    assert wide.json()["maximum"] == 10
    assert wide.json()["requested"] > 10
    assert len(begun) == 1


@pytest.mark.parametrize(("endpoint", "distance"), _ENDPOINTS)
def test_a_station_as_the_point_is_held_to_the_limit_as_well(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, distance: str
) -> None:
    """The point of `station=` is the station's own, and what is in reach of it is counted all the same."""
    begun = _stand_in_for_the_stations(monkeypatch, _stations_along_a_meridian(150, spacing=0.002))

    response = client.get(
        f"/api/v1/{endpoint}", params={**_OBSERVATION, "station": "00005", "timestamp": _POINT["timestamp"]}
    )

    assert response.json()["type"] == "urn:wetterdienst:problem:limit-exceeded"
    assert f"`{distance}`" in response.json()["detail"]
    assert begun == []


@pytest.mark.parametrize("endpoint", ["interpolate", "summarize"])
def test_only_the_stations_with_a_record_in_the_window_are_counted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """A default request in a dense network passes where most of what stands there closed before the window."""
    begun = _stand_in_for_the_stations(monkeypatch, _stations_along_a_meridian(150, spacing=0.002, closed=100))

    response = client.get(f"/api/v1/{endpoint}", params={**_OBSERVATION, **_POINT})

    assert response.json()["detail"] == _DOWNLOAD
    # and the walk reads those that were counted, not the ones that closed before the window
    assert begun == [f"{_DOWNLOAD}: 50"]


@pytest.mark.parametrize("endpoint", ["interpolate", "summarize"])
def test_a_station_is_counted_once_for_every_dataset_it_is_in(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """60 stations of two datasets are 120 rows of the list and 60 stations, of a limit of 100."""
    df = pl.concat(
        [_stations_along_a_meridian(60, 0.002), _stations_along_a_meridian(60, 0.002, dataset="more_precip")]
    )
    begun = _stand_in_for_the_stations(monkeypatch, df)
    parameters = "daily/kl/temperature_air_mean_2m,daily/more_precip/precipitation_amount"

    response = client.get(f"/api/v1/{endpoint}", params={**_OBSERVATION, **_POINT, "parameters": parameters})

    assert response.json()["detail"] == _DOWNLOAD
    assert begun == [f"{_DOWNLOAD}: 60"]


@pytest.mark.parametrize("endpoint", ["interpolate", "summarize"])
def test_a_limit_of_zero_does_not_count_the_stations_in_reach(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """`WD_RESTAPI_MAX_STATIONS=0` switches the limit off here as it does for `values`."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "0")
    begun = _stand_in_for_the_stations(monkeypatch, _stations_along_a_meridian(150, spacing=0.002))

    response = client.get(f"/api/v1/{endpoint}", params={**_OBSERVATION, **_POINT})

    assert response.json()["detail"] == _DOWNLOAD
    assert begun == [f"{_DOWNLOAD}: 150"]


def test_the_library_is_not_held_to_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request of the Python API sets no check, and reads as many stations as are in reach."""
    begun = _stand_in_for_the_stations(monkeypatch, _stations_along_a_meridian(150, spacing=0.002))
    request = DwdObservationRequest(parameters="daily/kl/temperature_air_mean_2m", start="2020-01-01", end="2020-01-03")

    with pytest.raises(exceptions.RequestError, match=_DOWNLOAD):
        request.interpolate((50.0, 10.0))
    with pytest.raises(exceptions.RequestError, match=_DOWNLOAD):
        request.summarize((50.0, 10.0))

    assert begun == [f"{_DOWNLOAD}: 150", f"{_DOWNLOAD}: 150"]


# --- the bounds of the request ----------------------------------------------------------------------------------


@pytest.mark.parametrize(("endpoint", "distance"), _ENDPOINTS)
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("{distance}_homogeneous", MAX_STATION_DISTANCE + 1),
        ("{distance}_heterogeneous", 1e9),
        ("{distance}", '{"temperature_air_mean_2m": 20000}'),
        ("num_additional_stations", MAX_ADDITIONAL_STATIONS + 1),
        ("num_additional_stations", 1_000_000),
        ("min_gain_of_value_pairs", 0),
        ("min_gain_of_value_pairs", -1),
    ],
)
def test_a_request_past_the_bounds_is_a_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, distance: str, name: str, value: float | str
) -> None:
    """A radius, a count or a gain past the bounds is refused as malformed, with no station list built for it."""
    begun = _stand_in_for_the_stations(monkeypatch, _stations_along_a_meridian(3, spacing=0.05))
    name = name.format(distance=distance)

    response = client.get(f"/api/v1/{endpoint}", params={**_OBSERVATION, **_POINT, name: value})

    assert response.status_code == 422
    assert response.json()["type"] == "urn:wetterdienst:problem:invalid-parameters"
    assert response.json()["errors"][0]["loc"][:2] == ["query", name]
    assert begun == []


@pytest.mark.parametrize(("endpoint", "distance"), _ENDPOINTS)
def test_a_request_at_the_bounds_is_let_through(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, distance: str
) -> None:
    """The bounds are inclusive: the largest radius and count, and a gain of the least above 0, are served."""
    begun = _stand_in_for_the_stations(monkeypatch, _stations_along_a_meridian(3, spacing=0.05))

    response = client.get(
        f"/api/v1/{endpoint}",
        params={
            **_OBSERVATION,
            **_POINT,
            f"{distance}_homogeneous": MAX_STATION_DISTANCE,
            f"{distance}_heterogeneous": MAX_STATION_DISTANCE,
            distance: f'{{"temperature_air_mean_2m": {MAX_STATION_DISTANCE}}}',
            "num_additional_stations": MAX_ADDITIONAL_STATIONS,
            "min_gain_of_value_pairs": 1e-9,
        },
    )

    assert response.json()["detail"] == _DOWNLOAD
    assert begun == [f"{_DOWNLOAD}: 3"]


def test_the_bounds_are_the_requests_of_the_server_alone() -> None:
    """The request of the library and the command line takes the radius, the count and the gain as it always did."""
    arguments = {**_OBSERVATION, **_POINT, "num_additional_stations": 1000, "min_gain_of_value_pairs": 0.0}

    request = InterpolationRequest(
        **arguments, interpolation_station_distance_homogeneous=5000.0, interpolation_station_distance_heterogeneous=1e6
    )
    summary = SummaryRequest(**arguments, summary_station_distance={"temperature_air_mean_2m": 5000.0})

    assert request.interpolation_station_distance_homogeneous == 5000.0
    assert summary.summary_station_distance == {"temperature_air_mean_2m": 5000.0}
    assert (request.num_additional_stations, request.min_gain_of_value_pairs) == (1000, 0.0)
    with pytest.raises(ValueError, match="less than or equal to"):
        RestInterpolationRequest(**arguments, interpolation_station_distance_homogeneous=5000.0)
    with pytest.raises(ValueError, match="greater than 0"):
        RestSummaryRequest(**arguments)


def test_the_bounds_are_in_the_schema_of_the_routes(client: TestClient) -> None:
    """A client reads the bounds from the OpenAPI document, for each route that takes the field."""
    schema = client.get("/openapi.json").json()
    for route in ("interpolate", "summarize", "settings"):
        parameters = {p["name"]: p["schema"] for p in schema["paths"][f"/api/v1/{route}"]["get"]["parameters"]}
        assert parameters["num_additional_stations"]["maximum"] == MAX_ADDITIONAL_STATIONS, route
        assert parameters["min_gain_of_value_pairs"]["exclusiveMinimum"] == 0, route
        for name, bound in parameters.items():
            if name.endswith(("_homogeneous", "_heterogeneous")):
                assert bound["anyOf"][0]["maximum"] == MAX_STATION_DISTANCE, (route, name)


def test_the_bounds_hold_for_the_mcp_tools() -> None:
    """The MCP tools are the routes, and carry their bounds in their input schema."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def _tools() -> dict[str, dict]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return {tool.name: tool.input_schema for tool in await client.list_tools()}

    tools = asyncio.run(_tools())
    for tool in ("interpolate", "summarize"):
        properties = tools[tool]["properties"]
        assert properties["num_additional_stations"]["maximum"] == MAX_ADDITIONAL_STATIONS, tool
        assert properties["min_gain_of_value_pairs"]["exclusiveMinimum"] == 0, tool


# --- the search for a group of stations -------------------------------------------------------------------------


def _ring_of_stations(n: int, *, nearest_last: bool = False) -> dict[str, tuple[float, float, float]]:
    """Give `n` stations on a ring around the origin, as `(x, y, distance)`, in the order they are held.

    `nearest_last` holds the farthest first, so that the order a dict gives is not the order of the distance.
    """
    stations = {f"s{i}": (math.cos(i) * 1e4, math.sin(i) * 1e4, 10.0 + i) for i in range(n)}
    return dict(reversed(list(stations.items()))) if nearest_last else stations


def test_the_groups_of_few_stations_are_all_of_them() -> None:
    """Up to the cap every combination of four that surrounds the point is a group, as before."""
    stations = _ring_of_stations(20)

    groups = list(get_valid_station_groups(stations, 0.0, 0.0).queue)

    assert groups, "a ring surrounds its centre"
    assert math.comb(20, 4) <= MAX_STATION_GROUPS
    assert {station for group in groups for station in group} == set(stations)


def test_the_groups_of_many_stations_are_those_of_the_nearest(caplog: pytest.LogCaptureFixture) -> None:
    """Past the cap only the nearest stations that fit under it are grouped, whatever order they are held in."""
    stations = _ring_of_stations(40, nearest_last=True)
    nearest = {f"s{i}" for i in range(30)}
    assert math.comb(30, 4) <= MAX_STATION_GROUPS < math.comb(31, 4)

    with caplog.at_level("INFO", logger="wetterdienst.core.interpolate"):
        groups = list(get_valid_station_groups(stations, 0.0, 0.0).queue)

    assert groups
    assert {station for group in groups for station in group} <= nearest
    assert "only the nearest 30 are grouped" in caplog.text


def test_a_point_only_the_farther_stations_surround_still_has_a_group() -> None:
    """The walk stops when all the stations taken surround the point: 30 on one side and a farther one are a group."""
    near_side = {f"n{i}": (1e3 + i * 10.0, (i % 7) * 10.0 - 30.0, 1.0 + i) for i in range(30)}
    stations = {**near_side, "far": (-5e4, 0.0, 99.0)}
    assert has_valid_station_group(stations, 0.0, 0.0)

    groups = list(get_valid_station_groups(stations, 0.0, 0.0).queue)

    assert len(groups) == 1
    assert "far" in groups[0]
    assert len(set(groups[0])) == 4
    assert list(get_valid_station_groups(stations, 0.0, 0.0, max_groups=10**9).queue)


def test_the_cap_is_an_argument() -> None:
    """A caller of the library that wants more or fewer groups says so; at least four stations are grouped."""
    stations = _ring_of_stations(12)

    few = {s for group in get_valid_station_groups(stations, 0.0, 0.0, max_groups=5).queue for s in group}
    many = {s for group in get_valid_station_groups(stations, 0.0, 0.0, max_groups=495).queue for s in group}

    assert len(few) <= 5
    assert many == set(stations)


def _interpolated(
    stations: dict[str, tuple[float, float, float]], columns: dict[str, dict[str, float]]
) -> pl.DataFrame:
    """Interpolate to the origin the readings of one day, `columns` being those of each parameter by station."""
    param_dict = {
        ("daily", "climate_summary", parameter): _ParameterData(
            values=pl.DataFrame(
                {"timestamp": [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)], **{s: [v] for s, v in readings.items()}}
            )
        )
        for parameter, readings in columns.items()
    }
    return calculate_interpolation(0.0, 0.0, stations, param_dict, None)


def test_a_group_around_the_point_found_past_the_cap_interpolates_to_the_value_of_the_field() -> None:
    """The stations are a field `x + 2y + 100`: the group of the fallback gives the value of it at the point."""
    near_side = {f"n{i}": (1e3 + i * 10.0, (i % 7) * 10.0 - 30.0, 1.0 + i) for i in range(30)}
    stations = {**near_side, "far": (-5e4, 0.0, 99.0)}
    assert math.comb(len(stations), 4) > MAX_STATION_GROUPS
    readings = {s: x + 2 * y + 100 for s, (x, y, _) in stations.items()}

    df = _interpolated(stations, {"temperature_air_mean_2m": readings})

    assert df.get_column("value").to_list() == [pytest.approx(100.0)]


def test_a_parameter_with_few_stations_keeps_its_groups_when_others_fill_the_cap() -> None:
    """26 stations near the point read one parameter and 8 farther ones another: each has the groups of its own."""
    near = {f"a{i}": (1e3 * math.cos(i), 1e3 * math.sin(i), 1.0 + i) for i in range(26)}
    far = {f"b{i}": (1e4 * math.cos(i), 1e4 * math.sin(i), 100.0 + i) for i in range(8)}
    stations = {**near, **far}
    assert math.comb(len(stations), 4) > MAX_STATION_GROUPS

    df = _interpolated(
        stations,
        {
            "temperature_air_mean_2m": dict.fromkeys(near, 50.0),
            "temperature_air_max_2m": dict.fromkeys(far, 100.0),
        },
    )

    assert dict(zip(df.get_column("parameter"), df.get_column("value"), strict=True)) == {
        "temperature_air_mean_2m": 50.0,
        "temperature_air_max_2m": 100.0,
    }


def test_the_readings_are_taken_in_the_order_of_the_group() -> None:
    """A group whose order differs from that of the row still interpolates each reading at its own station."""
    stations = {"a": (1e3, 0.0, 1.0), "b": (0.0, 1e3, 2.0), "c": (-1e3, -1e3, 3.0), "d": (1e3, 1e3, 4.0)}
    row = {s: x + 2 * y + 100 for s, (x, y, _) in stations.items()}
    groups = Queue()
    groups.put(("c", "a", "d", "b"))

    result = apply_interpolation(
        row, stations, groups, "daily", "climate_summary", "temperature_air_mean_2m", 0.0, 0.0, []
    )

    assert result[3] == pytest.approx(100.0)
