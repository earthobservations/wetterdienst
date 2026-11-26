# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`interpolate` and `summarize` say the elevation they were made at and whether a height correction was made.

The `request` block of the answer has `elevation` (null where there is none) and `elevation_corrected`, the parameters
whose readings were brought from each station's height to it: the table declares which quantities fall with height,
and only where there is an elevation are they corrected. In `p2-elevation-hut` a model used `elevation=1500` rightly
and could not tell from the answer that the value was corrected. Served from memory, so nothing leaves the machine.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import polars as pl
import pytest
from click.testing import CliRunner

from tests.ui.test_mcp_budget import _VALUES, _client_sees, _rest_client, _stub_values, _tool_client, _values_of
from tests.ui.test_mcp_budget_estimates import _ESTIMATE, _estimate_of, _stub
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from wetterdienst.io.file_metadata import metadata_block
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import cli as cli_module

if TYPE_CHECKING:
    from pathlib import Path

    from wetterdienst.model.result import InterpolatedValuesResult, SummarizedValuesResult

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

_TEMPERATURE = "daily/climate_summary/temperature_air_mean_2m"
_PRECIPITATION = "daily/precipitation_more/precipitation_amount"
_FIELDS = {"elevation", "elevation_corrected"}


def _at(tool: str, elevation: float | None, days: int = 2) -> InterpolatedValuesResult | SummarizedValuesResult:
    """Give an estimate made at `elevation`, of an air temperature, which falls with height, and a precipitation."""
    return replace(_estimate_of(tool, days), elevation=elevation)


# --- REST -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
@pytest.mark.parametrize("fmt", ["json", "geojson"])
def test_an_estimate_at_an_elevation_says_it_and_the_parameters_it_corrected(
    monkeypatch: pytest.MonkeyPatch, tool: str, fmt: str
) -> None:
    """1500 m: the air temperature is corrected, the precipitation is not, and the answer says so."""
    _stub(monkeypatch, tool, _at(tool, 1500.0))

    response = _rest_client().get(f"/api/{tool}", params={**_ESTIMATE, "elevation": 1500, "format": fmt})

    assert response.status_code == 200, response.text
    request = response.json()["metadata"]["request"]
    assert request["elevation"] == 1500.0
    assert request["elevation_corrected"] == [_TEMPERATURE]
    assert request["parameters"] == [_TEMPERATURE, _PRECIPITATION]


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_an_estimate_without_an_elevation_says_nothing_was_corrected(
    monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    """No elevation: it is null, and no parameter is corrected, however many fall with height."""
    _stub(monkeypatch, tool, _at(tool, None))

    request = _rest_client().get(f"/api/{tool}", params=_ESTIMATE).json()["metadata"]["request"]

    assert request["elevation"] is None
    assert request["elevation_corrected"] == []


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_an_elevation_of_zero_is_an_elevation(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """The coast is a height like any other: 0 is echoed, not read as none."""
    _stub(monkeypatch, tool, _at(tool, 0.0))

    request = _rest_client().get(f"/api/{tool}", params={**_ESTIMATE, "elevation": 0}).json()["metadata"]["request"]

    assert request["elevation"] == 0.0
    assert request["elevation_corrected"] == [_TEMPERATURE]


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_an_elevation_corrects_no_parameter_that_does_not_fall_with_height(
    monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    """The elevation is echoed, and the answer does not claim a correction of a quantity that has none."""
    result = _at(tool, 1500.0)
    stations = result.stations
    request = stations.request
    only_rain = type(request)(parameters=[("daily", "precipitation_more", "precipitation_amount")])
    _stub(monkeypatch, tool, replace(result, stations=replace(stations, request=only_rain)))

    block = _rest_client().get(f"/api/{tool}", params={**_ESTIMATE, "elevation": 1500}).json()["metadata"]["request"]

    assert block["elevation"] == 1500.0
    assert block["elevation_corrected"] == []


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_a_csv_says_the_elevation_in_its_headers(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """A CSV has no block: the headers carry the elevation and the parameters that were corrected."""
    _stub(monkeypatch, tool, _at(tool, 1500.0))

    corrected = _rest_client().get(f"/api/{tool}", params={**_ESTIMATE, "elevation": 1500, "format": "csv"})
    _stub(monkeypatch, tool, _at(tool, None))
    plain = _rest_client().get(f"/api/{tool}", params={**_ESTIMATE, "format": "csv"})

    assert corrected.headers["x-wetterdienst-elevation"] == "1500.0"
    assert corrected.headers["x-wetterdienst-elevation-corrected"] == _TEMPERATURE
    assert "x-wetterdienst-elevation" not in plain.headers
    assert "x-wetterdienst-elevation-corrected" not in plain.headers


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_a_cut_estimate_keeps_the_elevation(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """A tool's answer cut to the budget is made again for what is left: it is still the answer at 1500 m."""
    _stub(monkeypatch, tool, _at(tool, 1500.0, days=366))

    response = _tool_client().get(f"/api/{tool}", params={**_ESTIMATE, "elevation": 1500})

    answer = response.json()
    assert "answer-truncated" in response.headers["x-wetterdienst-warnings"]
    assert answer["metadata"]["request"]["elevation"] == 1500.0
    assert answer["metadata"]["request"]["elevation_corrected"] == [_TEMPERATURE]


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_a_cut_csv_keeps_the_elevation_in_its_headers(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """The CSV of a tool's answer is cut as well, and keeps what its headers say."""
    _stub(monkeypatch, tool, _at(tool, 1500.0, days=366))

    response = _tool_client().get(f"/api/{tool}", params={**_ESTIMATE, "elevation": 1500, "format": "csv"})

    assert unquote(response.headers["x-wetterdienst-truncated"])
    assert response.headers["x-wetterdienst-elevation"] == "1500.0"


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_a_mcp_client_receives_the_elevation(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """Through a real MCP session, as `p2-elevation-hut` read the answer."""
    _stub(monkeypatch, tool, _at(tool, 1500.0))

    result = _client_sees(tool, {**_ESTIMATE, "elevation": 1500})

    assert not result.is_error, result.content
    request = result.structured_content["result"]["metadata"]["request"]  # ty: ignore[not-subscriptable]
    assert request["elevation"] == 1500.0
    assert request["elevation_corrected"] == [_TEMPERATURE]


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_a_mcp_csv_says_the_elevation_in_its_sentence_and_meta(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """A CSV has no block: the sentence of the tool and the `_meta` of the result carry what the headers say."""
    _stub(monkeypatch, tool, _at(tool, 1500.0))

    result = _client_sees(tool, {**_ESTIMATE, "elevation": 1500, "format": "csv"})

    assert not result.is_error, result.content
    sentence = result.structured_content["result"]  # ty: ignore[not-subscriptable]
    assert " Elevation: 1500.0 m." in sentence
    assert f" Corrected for the elevation: {_TEMPERATURE}." in sentence
    assert result.meta["wetterdienst"]["elevation"] == "1500.0"  # ty: ignore[not-subscriptable]
    assert result.meta["wetterdienst"]["elevation_corrected"] == [_TEMPERATURE]  # ty: ignore[not-subscriptable]


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_a_mcp_csv_without_an_elevation_says_none(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """No elevation, no correction: the sentence has neither."""
    _stub(monkeypatch, tool, _at(tool, None))

    result = _client_sees(tool, {**_ESTIMATE, "format": "csv"})

    assert "Elevation" not in result.structured_content["result"]  # ty: ignore[not-subscriptable]
    assert "Corrected" not in result.structured_content["result"]  # ty: ignore[not-subscriptable]


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_a_cut_mcp_csv_keeps_the_elevation_in_its_sentence(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """The cut answer is counted with the sentence, and it still says the elevation."""
    _stub(monkeypatch, tool, _at(tool, 1500.0, days=900))

    result = _client_sees(tool, {**_ESTIMATE, "elevation": 1500, "format": "csv"})

    sentence = result.structured_content["result"]  # ty: ignore[not-subscriptable]
    assert "answer-truncated" in result.meta["wetterdienst"]["warnings"]  # ty: ignore[not-subscriptable]
    assert " Elevation: 1500.0 m." in sentence


# --- a point named by a station -------------------------------------------------------------------------------------


def _serve_a_station(monkeypatch: pytest.MonkeyPatch, elevation: float | None) -> None:
    """Serve one DWD station, with its own elevation, and stand in for the estimate made at its position."""
    station = pl.DataFrame(
        {
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "station_id": ["01048"],
            "start_timestamp": [dt.datetime(1950, 1, 1, tzinfo=dt.UTC)],
            "end_timestamp": [None],
            "latitude": [51.1],
            "longitude": [13.8],
            "elevation": [elevation],
            "name": ["Dresden-Klotzsche"],
            "state": ["Sachsen"],
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC"), "elevation": pl.Float64},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: station.lazy())
    template = _estimate_of("interpolate", 2)

    def estimated(_self: object, latlon: tuple[float, float], elevation: float | None, **_kwargs: object) -> Any:  # noqa: ANN401
        assert latlon == (51.1, 13.8)
        return replace(template, elevation=elevation)

    monkeypatch.setattr(DwdObservationRequest, "_interpolate", estimated)


def _by_station(**kwargs: float) -> dict[str, Any]:
    request = DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")])
    block = metadata_block(request.interpolate_by_station_id("01048", **kwargs), heavy=False)
    assert block is not None
    return block["request"]


def test_a_point_named_by_a_station_is_made_at_the_station_s_elevation(monkeypatch: pytest.MonkeyPatch) -> None:
    """No elevation given: the answer is made at the station's own, 228 m, and says so."""
    _serve_a_station(monkeypatch, 228.0)

    request = _by_station()

    assert request["elevation"] == 228.0
    assert request["elevation_corrected"] == [_TEMPERATURE]


def test_an_elevation_given_beats_the_one_of_the_station_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """The station names the point, the caller names the height: 1500 m, not 228 m."""
    _serve_a_station(monkeypatch, 228.0)

    assert _by_station(elevation=1500.0)["elevation"] == 1500.0


def test_a_point_named_by_a_station_that_has_no_elevation_has_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station that lists no elevation names none: the answer says null and corrects nothing."""
    _serve_a_station(monkeypatch, None)

    request = _by_station()

    assert request["elevation"] is None
    assert request["elevation_corrected"] == []


# --- the command line and Python ------------------------------------------------------------------------------------


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_the_command_line_says_the_elevation(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """The command prints the answer of the route, `metadata` first."""
    result = _at(tool, 1500.0)
    monkeypatch.setattr(cli_module, f"get_{tool}", lambda **_kwargs: result)

    command = CliRunner().invoke(
        cli_module.cli,
        [
            tool,
            "--provider=dwd",
            "--network=observation",
            f"--parameters={_TEMPERATURE}",
            "--latitude=51.1",
            "--longitude=13.8",
            "--elevation=1500",
            "--timestamp=2024",
        ],
    )

    assert command.exit_code == 0, command.output
    request = json.loads(command.stdout)["metadata"]["request"]
    assert request["elevation"] == 1500.0
    assert request["elevation_corrected"] == [_TEMPERATURE]


@pytest.mark.parametrize("tool", ["interpolate", "summarize"])
def test_python_writes_the_elevation_beside_a_file(tool: str, tmp_path: Path) -> None:
    """`to_target` with `with_metadata` writes the block of the answer, which has them."""
    result = _at(tool, 1500.0)

    result.to_target(f"file://{tmp_path / 'estimate.csv'}", with_metadata=True)

    block = json.loads((tmp_path / "estimate.csv.metadata.json").read_text())
    assert block["request"]["elevation"] == 1500.0
    assert block["request"]["elevation_corrected"] == [_TEMPERATURE]
    plain = metadata_block(_at(tool, None), heavy=False)
    assert plain is not None
    assert plain["request"]["elevation"] is None
    assert plain["request"]["elevation_corrected"] == []


# --- the other answers ----------------------------------------------------------------------------------------------


def test_the_answer_of_values_has_no_elevation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the two estimates have the members: `values` and its request block are as they were."""
    _stub_values(monkeypatch, _values_of(dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0), 3))

    request: dict[str, Any] = _rest_client().get("/api/values", params=_VALUES).json()["metadata"]["request"]

    assert not _FIELDS & request.keys()
