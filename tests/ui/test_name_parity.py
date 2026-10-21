# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A `name` selects the same stations, in the same order, in Python, over REST, on the command line and in MCP.

(GH-3025, GH-3026.) The best matches come first and a station is one match whatever its number of datasets;
a request for a window matches the name among the stations that have a record in it, whether it lists them
(`stations`) or reads them (`values`). Served from memory, so nothing leaves the machine.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst import Settings
from wetterdienst.model.request import DEFAULT_NAME_RANK, DEFAULT_NAME_RANK_LISTING
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app

PARAMETER = "daily/kl/temperature_air_mean_2m"
_SELECTION = {"provider": "dwd", "network": "observation", "parameters": PARAMETER}
_UTC = ZoneInfo("UTC")
WINDOW = "2020-05-01/2020-05-03"
CLOSED, KRONSHAGEN, OPEN = "00001", "00002", "00004"
DUESSELDORF, KOELN = "00010", "00013"


def _utc(year: int) -> dt.datetime:
    return dt.datetime(year, 1, 1, tzinfo=_UTC)


@pytest.fixture(autouse=True)
def _serve_dwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve stations from memory, two of them called "Kiel" of which only the one that is open covers 2020."""
    rows = [
        # the id, the name, the first and the last day of the record
        (CLOSED, "Kiel", _utc(1950), _utc(1990)),
        (KRONSHAGEN, "Kiel-Kronshagen", _utc(1980), None),
        (OPEN, "Kiel", _utc(1991), None),
        ("00005", "Dresden-Klotzsche", _utc(1934), None),
        # a name that is written with and without its umlaut: the station that closed in 2015, and the one that begins
        # in 2021, are no candidates for a window in 2020
        (DUESSELDORF, "Düsseldorf", _utc(1950), None),
        ("00011", "Dusseldorf-Flughafen", _utc(1990), _utc(2015)),
        ("00012", "DÜSSELDORF", _utc(2021), None),
        (KOELN, "Köln", _utc(1950), None),
    ]
    stations = pl.DataFrame(
        {
            "resolution": ["daily"] * len(rows),
            "dataset": ["climate_summary"] * len(rows),
            "station_id": [row[0] for row in rows],
            "start_timestamp": [row[2] for row in rows],
            "end_timestamp": [row[3] for row in rows],
            "latitude": [54.0] * len(rows),
            "longitude": [10.0] * len(rows),
            "elevation": [10.0] * len(rows),
            "name": [row[1] for row in rows],
            "state": ["Schleswig-Holstein"] * len(rows),
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        # a reading a day in 2020 from every station asked, so that what is read is told by the station
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        names = [parameter.name_original for parameter in dataset]
        days = [dt.datetime(2020, 1, 1, tzinfo=_UTC) + dt.timedelta(days=offset) for offset in range(366)]
        rows = len(days) * len(names)
        return pl.DataFrame(
            {
                "timestamp": [day for day in days for _ in names],
                "parameter": names * len(days),
                "value": [1.0] * rows,
                "quality_flags": ["1"] * rows,
                "resolution": ["daily"] * rows,
                "dataset": [dataset.name] * rows,
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _ids(answer: dict[str, Any], kind: str) -> list[str]:
    """Give the station ids of an answer, in the order it gives them, each once."""
    return list(dict.fromkeys(row["station_id"] for row in answer[kind]))


def _rest(kind: str, **query: str) -> list[str]:
    response = TestClient(app).get(f"/api/{kind}", params={**_SELECTION, **query})
    assert response.status_code == 200, response.text
    return _ids(response.json(), kind)


def _cli(kind: str, **query: str) -> list[str]:
    args = [f"--{key.replace('_', '-')}={value}" for key, value in {**_SELECTION, **query}.items()]
    result = CliRunner().invoke(cli, [kind, *args])
    assert result.exit_code == 0, result.output
    return _ids(json.loads(result.stdout), kind)


def _mcp(kind: str, **query: str) -> list[str]:
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> dict[str, Any]:
        async with Client(build_mcp_server(app)) as client:
            result = await client.call_tool(kind, {**_SELECTION, **query})
            answer = result.structured_content
            assert answer is not None
            return answer.get("result", answer)

    return _ids(asyncio.run(call()), kind)


def _python(kind: str, **query: str) -> list[str]:
    """Give what the library selects for the same input: the window of the request is applied by `filter_by_name`."""
    window = query.get("timestamp")
    start, end = window.split("/") if window else (None, None)
    request = DwdObservationRequest(parameters=PARAMETER, start=start, end=end, settings=Settings())
    # the library's default is the best match; a listing offers the best five (DEFAULT_NAME_RANK_LISTING)
    default_rank = DEFAULT_NAME_RANK_LISTING if kind == "stations" else DEFAULT_NAME_RANK
    stations = request.filter_by_name(query["name"], rank=int(query.get("rank", default_rank)))
    if kind == "stations":
        return list(dict.fromkeys(stations.df.get_column("station_id")))
    return list(dict.fromkeys(row["station_id"] for row in stations.values().all().df.iter_rows(named=True)))


def _every_interface(kind: str, **query: str) -> dict[str, list[str]]:
    pytest.importorskip("fastmcp")
    return {
        "python": _python(kind, **query),
        "rest": _rest(kind, **query),
        "cli": _cli(kind, **query),
        "mcp": _mcp(kind, **query),
    }


@pytest.mark.parametrize(
    ("kind", "query", "expected"),
    [
        # the exact name first, the stations that merely hold it after, ties by station_id
        ("stations", {"name": "Kiel", "rank": "5"}, [CLOSED, OPEN, KRONSHAGEN]),
        # no window, no filter: the station that closed ties with the open one and is first by its id
        ("values", {"name": "Kiel"}, [CLOSED]),
        ("values", {"name": "Kiel", "rank": "2"}, [CLOSED, OPEN]),
        ("values", {"name": "Kiel", "rank": "3"}, [CLOSED, OPEN, KRONSHAGEN]),
    ],
)
def test_a_name_without_a_window_selects_the_best_matches_in_the_same_order_everywhere(
    kind: str, query: dict[str, str], expected: list[str]
) -> None:
    """Without a window every station is a candidate, in the order of the score and then of the id."""
    answers = _every_interface(kind, **query)

    assert answers == dict.fromkeys(answers, expected)


@pytest.mark.parametrize(
    ("kind", "query", "expected"),
    [
        # the station that closed is no candidate: the open one is the best match
        ("values", {"name": "Kiel"}, [OPEN]),
        ("values", {"name": "Kiel", "rank": "2"}, [OPEN, KRONSHAGEN]),
        ("values", {"name": "Kiel", "rank": "5"}, [OPEN, KRONSHAGEN]),
        ("stations", {"name": "Kiel", "rank": "5"}, [OPEN, KRONSHAGEN]),
        ("stations", {"name": "Kiel"}, [OPEN, KRONSHAGEN]),
    ],
)
def test_a_name_is_matched_among_the_stations_that_have_a_record_in_the_window_everywhere(
    kind: str, query: dict[str, str], expected: list[str]
) -> None:
    """The window comes before the ranking, so that the best match is a station that can have a reading in it."""
    answers = _every_interface(kind, **query, timestamp=WINDOW)

    assert answers == dict.fromkeys(answers, expected)


def test_a_window_no_station_of_that_name_covers_is_an_empty_answer_everywhere() -> None:
    """A window before every record leaves no candidate, which is an empty answer and no fallback to a closed one."""
    answers = {
        "rest": _rest("values", name="Kiel", timestamp="1920-01-01/1920-01-03"),
        "cli": _cli_empty(name="Kiel", timestamp="1920-01-01/1920-01-03"),
    }

    assert answers == {"rest": [], "cli": []}


def _cli_empty(**query: str) -> list[str]:
    args = [f"--{key}={value}" for key, value in {**_SELECTION, **query}.items()]
    result = CliRunner().invoke(cli, ["values", *args])
    assert result.exit_code == 0, result.output
    return _ids(json.loads(result.stdout), "values")


@pytest.mark.parametrize("name", ["Düsseldorf", "Dusseldorf", "duesseldorf", "DUSSELDORF"])
def test_a_name_with_or_without_its_umlaut_selects_the_same_station_everywhere(name: str) -> None:
    """However the umlaut is written, the station of that name is the best match, in the same order everywhere."""
    answers = _every_interface("stations", name=name, rank="5")

    expected = ["00010", "00012", "00011"]
    assert answers == dict.fromkeys(answers, expected)


@pytest.mark.parametrize("name", ["Köln", "Koln", "koeln"])
def test_koeln_is_found_by_every_spelling_everywhere(name: str) -> None:
    """The case that found the station by one spelling only: `Koln`, `Köln` and `koeln` are the same name."""
    answers = _every_interface("values", name=name)

    expected = [KOELN]
    assert answers == dict.fromkeys(answers, expected)


@pytest.mark.parametrize("kind", ["stations", "values"])
def test_dusseldorf_in_a_window_selects_the_station_that_has_a_record_in_it_everywhere(kind: str) -> None:
    """Python has the window of its request as the command line, REST and MCP have a `timestamp`: one station."""
    answers = _every_interface(kind, name="Dusseldorf", rank="5", timestamp=WINDOW)

    expected = [DUESSELDORF]
    assert answers == dict.fromkeys(answers, expected)
