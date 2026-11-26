# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`counts.stations_matched` of a `stations` answer says how many stations match, whatever cut the answer (GH-4472).

A `rank` keeps the nearest stations of those that could be ranked, a name the best matches, and a tool's answer is
cut to the budget of 40,000 characters: in each `counts.stations` is what is returned, and `stations_matched` is what
the selection found. Served from memory, so nothing leaves the machine.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.ui.test_mcp_budget import (
    _A_RANK,
    _STATIONS,
    _VALUES,
    _client_sees,
    _rest_client,
    _stations_by_rank,
    _stations_of,
    _stub_stations,
    _stub_values,
    _tool_client,
    _values_of,
)
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from wetterdienst.io.file_metadata import metadata_block
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import cli as cli_module
from wetterdienst.ui import restapi
from wetterdienst.ui.core import limit_stations_to_rank
from wetterdienst.ui.response_metadata import Counts

if TYPE_CHECKING:
    from pathlib import Path

    from wetterdienst.model.result import StationsResult

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

_UTC = ZoneInfo("UTC")
_DAILY = "daily/climate_summary/temperature_air_mean_2m"


# --- the cut of the budget, on REST as a tool, in every format ------------------------------------------------------


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv", "ndjson"])
def test_a_tool_answer_cut_to_the_budget_says_how_many_stations_match(
    monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """700 stations of `all` are cut to the first that fit: the counts say 700 match, in the block or the headers."""
    _stub_stations(monkeypatch, _stations_of(700, with_umlaut=True))

    response = _tool_client().get("/api/stations", params={**_STATIONS, "format": fmt})

    assert response.status_code == 200
    assert response.headers["x-wetterdienst-stations-matched"] == "700"
    kept = int(response.headers["x-wetterdienst-stations"])
    assert 0 < kept < 700
    if fmt in ("json", "geojson"):
        counts = response.json()["metadata"]["counts"]
        assert counts["stations"] == kept
        assert counts["stations_matched"] == 700
    elif fmt == "ndjson":
        lines = [json.loads(line) for line in response.text.splitlines()]
        assert lines[0]["metadata"]["counts"]["stations_matched"] == 700
        assert lines[-1]["end"]["counts"]["stations_matched"] == 700
        assert lines[-1]["end"]["counts"]["stations"] == kept


def test_a_bounding_box_cut_to_the_budget_says_how_many_stations_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same for a box, which is cut the way `all` is."""
    _stub_stations(monkeypatch, _stations_of(650, with_umlaut=True))
    box = {k: v for k, v in _STATIONS.items() if k != "all"} | {"left": 0, "bottom": 0, "right": 90, "top": 90}

    counts = _tool_client().get("/api/stations", params=box).json()["metadata"]["counts"]

    assert counts["stations"] < 650
    assert counts["stations_matched"] == 650


def test_a_mcp_client_receives_how_many_stations_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """Through a real MCP session, as `p1-count-all-and-cut` read it: the number is in the counts, not only the note."""
    _stub_stations(monkeypatch, _stations_of(700, with_umlaut=True))

    result = _client_sees("stations", {**_STATIONS, "format": "json"})

    assert not result.is_error, result.content
    counts = result.structured_content["result"]["metadata"]["counts"]  # ty: ignore[not-subscriptable]
    assert 0 < counts["stations"] < 700
    assert counts["stations_matched"] == 700


def test_an_answer_that_fits_says_the_stations_it_has(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is cut: `stations_matched` equals `stations`, as a tool and as any other caller."""
    _stub_stations(monkeypatch, _stations_of(20))

    for client in (_tool_client(), _rest_client()):
        counts = client.get("/api/stations", params=_STATIONS).json()["metadata"]["counts"]
        assert counts == {"stations": 20, "stations_matched": 20, "rows": 20}


def test_the_rest_api_answers_every_station_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Over REST nothing is cut to the budget: all 700 are returned, and 700 match."""
    _stub_stations(monkeypatch, _stations_of(700))

    response = _rest_client().get("/api/stations", params=_STATIONS)

    assert response.json()["metadata"]["counts"] == {"stations": 700, "stations_matched": 700, "rows": 700}
    assert response.headers["x-wetterdienst-stations-matched"] == "700"


# --- a rank ---------------------------------------------------------------------------------------------------------


def test_a_rank_says_how_many_stations_could_be_ranked(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rank=5` of 900 stations with a position lists 5, and 900 match."""
    _stub_stations(monkeypatch, _stations_by_rank(900, 5))

    response = _rest_client().get("/api/stations", params={**_A_RANK, "rank": 5})

    body = response.json()
    assert len(body["stations"]) == 5
    assert body["metadata"]["counts"] == {"stations": 5, "stations_matched": 900, "rows": 5}


def test_a_rank_cut_again_to_the_budget_keeps_the_number_that_could_be_ranked(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rank of 700 is cut to the budget: 900 still match, not the 700 the rank kept and not what fits."""
    _stub_stations(monkeypatch, _stations_by_rank(900, 700, with_umlaut=True))

    counts = _tool_client().get("/api/stations", params=_A_RANK).json()["metadata"]["counts"]

    assert 0 < counts["stations"] < 700
    assert counts["stations_matched"] == 900


def test_a_rank_streamed_as_ndjson_says_it_in_both_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    """The head of a stream and its `end` line say the same."""
    _stub_stations(monkeypatch, _stations_by_rank(300, 4))

    response = _rest_client().get("/api/stations", params={**_A_RANK, "rank": 4, "format": "ndjson"})

    lines = [json.loads(line) for line in response.text.splitlines()]
    assert lines[0]["metadata"]["counts"]["stations_matched"] == 300
    assert lines[-1]["end"]["counts"] == {"stations": 4, "rows": 4, "stations_matched": 300}


def test_a_rank_of_a_csv_has_the_number_in_a_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CSV has no block: its headers carry what is returned and what matched."""
    _stub_stations(monkeypatch, _stations_by_rank(300, 4))

    response = _rest_client().get("/api/stations", params={**_A_RANK, "rank": 4, "format": "csv"})

    assert response.headers["x-wetterdienst-stations"] == "4"
    assert response.headers["x-wetterdienst-stations-matched"] == "300"


def test_the_core_counts_the_stations_that_could_be_ranked() -> None:
    """`limit_stations_to_rank` is where the rank leaves the rest out: it keeps what it found."""
    listing = _stations_by_rank(50, 3)

    assert listing._matched is None  # noqa: SLF001
    ranked = limit_stations_to_rank(listing)

    assert ranked.df.get_column("station_id").n_unique() == 3
    assert ranked._matched == 50  # noqa: SLF001


# --- a name ---------------------------------------------------------------------------------------------------------


def _catalogue() -> pl.DataFrame:
    """Give five stations of one dataset, three of them named Kiel."""
    names = ["Kiel-Holtenau", "Kiel-Kronshagen", "Kiel", "Hamburg", "Bremen"]
    return pl.DataFrame(
        {
            "resolution": ["daily"] * 5,
            "dataset": ["climate_summary"] * 5,
            "station_id": [f"0000{i}" for i in range(5)],
            "start_timestamp": [dt.datetime(1950, 1, 1, tzinfo=_UTC)] * 5,
            "end_timestamp": [None] * 5,
            "latitude": [54.3, 54.3, 54.3, 53.6, 53.1],
            "longitude": [10.1, 10.1, 10.1, 10.0, 8.8],
            "elevation": [5.0] * 5,
            "name": names,
            "state": ["Schleswig-Holstein"] * 3 + ["Hamburg", "Bremen"],
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )


def _named(rank: int) -> StationsResult:
    request = DwdObservationRequest(parameters=_DAILY)
    return request.filter_by_name("Kiel", rank=rank, df_all=_catalogue())


def test_a_name_says_how_many_stations_matched_of_which_the_best_are_kept() -> None:
    """`rank=2` of the three that match Kiel lists two, and three matched."""
    result = _named(2)

    assert result.df.get_column("station_id").n_unique() == 2
    assert result._matched == 3  # noqa: SLF001


def test_a_name_says_how_many_matched_over_rest_the_command_line_and_python(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same selection through the three surfaces that build the block."""
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: _catalogue().lazy())
    query = {"provider": "dwd", "network": "observation", "parameters": _DAILY, "name": "Kiel", "rank": "2"}

    rest = TestClient(restapi.app).get("/api/stations", params=query)
    command = CliRunner().invoke(
        cli_module.cli,
        ["stations", "--provider=dwd", "--network=observation", f"--parameters={_DAILY}", "--name=Kiel", "--rank=2"],
    )
    python = metadata_block(_named(2), heavy=False)

    assert rest.status_code == 200, rest.text
    assert command.exit_code == 0, command.output
    assert python is not None
    for counts in (
        rest.json()["metadata"]["counts"],
        json.loads(command.stdout)["metadata"]["counts"],
        python["counts"],
    ):
        assert counts == {"stations": 2, "stations_matched": 3, "rows": 2}


def test_a_name_that_matches_fewer_than_its_rank_says_the_stations_it_has() -> None:
    """Three match and ten are allowed: three are listed, and three match."""
    result = _named(10)

    assert result.df.get_column("station_id").n_unique() == 3
    assert result._matched == 3  # noqa: SLF001


# --- the command line and Python ------------------------------------------------------------------------------------


def test_the_command_line_says_how_many_stations_a_rank_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """`stations` of the command line, with a rank of 3 over a listing of 40."""
    monkeypatch.setattr(cli_module, "get_stations", lambda **_kwargs: _stations_by_rank(40, 3))
    args = ["stations", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--latitude=52.5"]

    command = CliRunner().invoke(cli_module.cli, [*args, "--longitude=13.4", "--rank=3"])

    assert command.exit_code == 0, command.output
    counts = json.loads(command.stdout)["metadata"]["counts"]
    assert counts["stations"] == 3
    assert counts["stations_matched"] == 40


def test_the_command_line_says_the_stations_of_a_listing_that_is_not_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is cut: 12 are listed and 12 match."""
    monkeypatch.setattr(cli_module, "get_stations", lambda **_kwargs: _stations_of(12))

    command = CliRunner().invoke(
        cli_module.cli, ["stations", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--all"]
    )

    assert json.loads(command.stdout)["metadata"]["counts"] == {"stations": 12, "stations_matched": 12, "rows": 12}


def test_python_writes_how_many_stations_matched_beside_a_file(tmp_path: Path) -> None:
    """`to_target` with `with_metadata` writes the block, which has the number, as the answers do."""
    result = _named(1)

    result.to_target(f"file://{tmp_path / 'stations.csv'}", with_metadata=True)

    block = json.loads((tmp_path / "stations.csv.metadata.json").read_text())
    assert block["counts"]["stations"] == 1
    assert block["counts"]["stations_matched"] == 3


# --- what is not a list of stations ---------------------------------------------------------------------------------


def test_the_answer_of_values_has_no_stations_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only `stations` has the member: a `values` answer, which reads the stations of a rank too, does not."""
    _stub_values(monkeypatch, _values_of(dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0), 3))

    response = _rest_client().get("/api/values", params=_VALUES)

    assert response.json()["metadata"]["counts"].keys() == {"stations", "rows"}
    assert "x-wetterdienst-stations-matched" not in response.headers


def test_a_streamed_values_answer_has_no_stations_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    """The head of a stream of `values` is made from the selected stations too, and says nothing of a match."""
    from tests.ui.test_restapi import _stub_stream  # noqa: PLC0415

    result = _values_of(dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0), 3)
    _stub_stream(monkeypatch, [result])

    response = _rest_client().get("/api/values", params={**_VALUES, "format": "ndjson"})

    lines = [json.loads(line) for line in response.text.splitlines()]
    assert lines[0]["metadata"]["counts"].keys() == {"stations", "rows"}
    assert lines[-1]["end"]["counts"].keys() == {"stations", "rows"}


def test_the_block_has_no_member_where_it_is_not_given() -> None:
    """The default is no member, so that no other answer carries a null."""
    assert Counts(stations=1, rows=2).stations_matched is None
