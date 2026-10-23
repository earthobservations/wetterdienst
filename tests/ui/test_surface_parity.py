# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The same request gives the same answer in the library, on the command line and on the REST API (GH-2635).

Each test serves a small DWD network from a stub of the station index and of the files the values are read
from, so that the whole of a request runs -- parameter parsing, the station selection, the collection and the
rendering -- and nothing but the network is stood in for. A request is then made on each surface and the
answers are held to each other.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import TYPE_CHECKING, Any

import click
import polars as pl
import pytest
from click.testing import CliRunner, Result
from fastapi.testclient import TestClient

from tests.conftest import is_no_such_option
from wetterdienst.exceptions import StationNotFoundError
from wetterdienst.model.request import DEFAULT_NAME_RANK, DEFAULT_NAME_RANK_LISTING
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui import cli as cli_module
from wetterdienst.ui import core, restapi
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    import pathlib

    from pydantic import BaseModel

UTC = dt.UTC
PARAMETER = "daily/kl/temperature_air_mean_2m"
_TODAY = dt.datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
# an index lists the last day it holds, which for a station still reporting is yesterday's
_YESTERDAY = _TODAY - dt.timedelta(days=1)

# id, name, latitude, longitude, start, end; the names are alike on purpose: a fuzzy match on "Dresden" finds six
_STATIONS = [
    ("00001", "Dresden-Klotzsche", 51.13, 13.75, dt.datetime(1934, 1, 1, tzinfo=UTC), _YESTERDAY),
    ("00002", "Dresden-Hosterwitz", 51.02, 13.85, dt.datetime(1950, 1, 1, tzinfo=UTC), _YESTERDAY),
    ("00003", "Dresden-Strehlen", 51.03, 13.76, dt.datetime(1960, 1, 1, tzinfo=UTC), _YESTERDAY),
    ("00004", "Dresden-Pillnitz", 51.00, 13.88, dt.datetime(1970, 1, 1, tzinfo=UTC), _YESTERDAY),
    ("00005", "Dresden-Gohlis", 51.07, 13.70, dt.datetime(1980, 1, 1, tzinfo=UTC), _YESTERDAY),
    ("00006", "Dresden-Neustadt", 51.06, 13.74, dt.datetime(1990, 1, 1, tzinfo=UTC), _YESTERDAY),
    # nearest of all to the point asked about, and closed a century ago
    ("00007", "Altstadt", 51.05, 13.74, dt.datetime(1901, 1, 1, tzinfo=UTC), dt.datetime(1920, 12, 31, tzinfo=UTC)),
    ("00008", "Leipzig", 51.30, 12.40, dt.datetime(1940, 1, 1, tzinfo=UTC), _YESTERDAY),
]
_DRESDEN = {f"0000{number}" for number in range(1, 7)}
_POINT = (51.05, 13.74)


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    import os  # noqa: PLC0415

    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def _serve_dwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for DWD's station index and for its files, which hold three days of May 2020 for each station."""
    df = pl.DataFrame(
        {
            "resolution": ["daily"] * len(_STATIONS),
            "dataset": ["climate_summary"] * len(_STATIONS),
            "station_id": [row[0] for row in _STATIONS],
            "start_timestamp": [row[4] for row in _STATIONS],
            "end_timestamp": [row[5] for row in _STATIONS],
            "latitude": [row[2] for row in _STATIONS],
            "longitude": [row[3] for row in _STATIONS],
            "elevation": [100.0] * len(_STATIONS),
            "name": [row[1] for row in _STATIONS],
            "region": ["Sachsen"] * len(_STATIONS),
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda self: df.lazy())  # noqa: ARG005

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        names = [parameter.name_original for parameter in dataset]
        days = [dt.datetime(2020, 5, day, tzinfo=UTC) for day in range(1, 4)]
        return pl.DataFrame(
            {
                "timestamp": [day for day in days for _ in names],
                "parameter": names * len(days),
                "value": [1.0] * (len(days) * len(names)),
                "quality_flags": ["1"] * (len(days) * len(names)),
                "resolution": ["daily"] * (len(days) * len(names)),
                "dataset": [dataset.name] * (len(days) * len(names)),
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _request(**kwargs: Any) -> DwdObservationRequest:  # noqa: ANN401
    """Make the library's request for the one parameter."""
    return DwdObservationRequest(parameters=[PARAMETER], **kwargs)


def _cli(*args: str) -> Result:
    """Run a command of the command line on the parameter."""
    command, *rest = args
    return CliRunner().invoke(
        cli, [command, "--provider=dwd", "--network=observation", f"--parameters={PARAMETER}", *rest]
    )


def _rest(path: str, **params: str) -> Any:  # noqa: ANN401
    """Make a request to the REST API on the parameter."""
    client = TestClient(restapi.app, raise_server_exceptions=False)
    return client.get(path, params={"provider": "dwd", "network": "observation", "parameters": PARAMETER, **params})


def _untimed(text: str) -> str:
    """Give an answer without the time it was made at, which no two requests share."""
    return re.sub(r'"retrieved_at": "[^"]*"', '"retrieved_at": ""', text)


def _json(text: str) -> Any:  # noqa: ANN401
    """Read the JSON of an answer but for the time it was made at."""
    return json.loads(_untimed(text))


def _versioned(path: str) -> str:
    """Give the path the OpenAPI document lists an endpoint under: the alias is served, but not documented."""
    return path.replace("/api/", "/api/v1/", 1)


def _ids(stations: Any) -> set[str]:  # noqa: ANN401
    """Name the stations of a listing."""
    return {station["station_id"] for station in stations["stations"]}


# the one way to ask each surface for the stations a selection names, giving the ids it answers with
def _library_stations(**selection: str) -> set[str]:
    request = _request()
    if "name" in selection:
        rank = {"rank": int(selection["rank"])} if "rank" in selection else {}
        result = request.filter_by_name(selection["name"], **rank)
    else:
        result = request.filter_by_station_id(selection["stations"].split(","))
    return set(result.df.get_column("station_id"))


def _cli_stations(**selection: str) -> set[str]:
    result = _cli("stations", *(f"--{key}={value}" for key, value in selection.items()))
    assert result.exit_code == 0, result.output
    return _ids(json.loads(result.stdout))


def _rest_stations(**selection: str) -> set[str]:
    response = _rest("/api/stations", **selection)
    assert response.status_code == 200, response.text
    return _ids(response.json())


SURFACES = {"library": _library_stations, "cli": _cli_stations, "rest": _rest_stations}


def test_a_name_lists_the_same_best_five_on_the_command_line_and_rest_as_in_the_library() -> None:
    """A listing for a name offers its best five on both surfaces, which the library gives for `rank=5`."""
    assert (DEFAULT_NAME_RANK_LISTING, DEFAULT_NAME_RANK) == (5, 1)
    library = _library_stations(name="Dresden", rank=str(DEFAULT_NAME_RANK_LISTING))
    cli_ids, rest_ids = _cli_stations(name="Dresden"), _rest_stations(name="Dresden")

    # six stations are called Dresden-something, and five of them are listed
    assert cli_ids == rest_ids == library
    assert len(library) == DEFAULT_NAME_RANK_LISTING
    assert library <= _DRESDEN


def test_a_name_fetches_the_one_best_match_on_every_surface() -> None:
    """The values of a name come from the one station it matches best -- in the library, as on the other two.

    The command line and REST read five stations' values for a name, where the library read one.
    """
    library = set(_request().filter_by_name("Dresden").values().all().df.get_column("station_id"))
    cli_values = _cli("values", "--name=Dresden", "--timestamp=2020-05")
    rest_values = _rest("/api/values", name="Dresden", timestamp="2020-05")

    assert cli_values.exit_code == 0, cli_values.output
    assert rest_values.status_code == 200
    assert {item["station_id"] for item in json.loads(cli_values.stdout)["values"]} == library
    assert {item["station_id"] for item in rest_values.json()["values"]} == library
    assert len(library) == DEFAULT_NAME_RANK == 1


@pytest.mark.parametrize("surface", SURFACES)
def test_an_explicit_rank_is_the_number_of_matches_everywhere(surface: str) -> None:
    """A rank given gives that many matches, wherever the name is looked up."""
    assert len(SURFACES[surface](name="Dresden", rank="2")) == 2


def test_the_rank_of_a_name_is_described_with_the_numbers_it_defaults_to() -> None:
    """The request models, which the OpenAPI schema and the MCP tools describe, say what a name defaults to."""
    openapi = TestClient(restapi.app).get("/openapi.json").json()
    parameters = {
        parameter["name"]: parameter for parameter in openapi["paths"]["/api/v1/stations"]["get"]["parameters"]
    }
    assert f"default {DEFAULT_NAME_RANK_LISTING} for `stations`" in parameters["rank"]["description"]
    assert f"{DEFAULT_NAME_RANK} for `values`" in parameters["rank"]["description"]


# an empty result: what the library hands back, the REST API answers with a 200, and the command line with exit 0


def test_a_window_without_readings_is_an_empty_result_on_every_surface(caplog: pytest.LogCaptureFixture) -> None:
    """A window in which a station has no reading is an empty frame, a 200 and exit 0, all with the same body.

    The command line exited 1, as for a failure, so a schedule asking for a value before it is published failed.
    """
    window = {"timestamp": "1930-06-01"}
    library = _request(start="1930-06-01", end="1930-06-01").filter_by_station_id("00001").values().all().df
    with caplog.at_level(logging.WARNING):
        cli_result = _cli("values", "--stations=00001", "--timestamp=1930-06-01")
    rest_response = _rest("/api/values", stations="00001", **window)

    assert library.is_empty()
    assert cli_result.exit_code == 0, cli_result.output
    assert rest_response.status_code == 200
    assert _json(cli_result.stdout) == _json(rest_response.text)
    assert _json(cli_result.stdout)["values"] == []
    # said once, on stderr, where the logs go -- and not on stdout, which is the answer
    said = [
        record.getMessage()
        for record in caplog.records
        if record.name == "wetterdienst.ui.cli" and record.levelno == logging.WARNING
    ]
    assert said == ["No data available for given constraints"]
    assert "No data available" not in cli_result.stdout


def test_an_empty_csv_is_the_header_on_both_surfaces() -> None:
    """The CSV of an empty result is its header, as the REST API sends it."""
    cli_result = _cli("values", "--stations=00001", "--timestamp=1930-06-01", "--format=csv")
    rest_response = _rest("/api/values", stations="00001", timestamp="1930-06-01", format="csv")

    assert cli_result.exit_code == 0, cli_result.output
    assert cli_result.stdout.strip() == rest_response.text.strip()
    assert cli_result.stdout.startswith("station_id,resolution,dataset,parameter,timestamp,value")


def test_no_station_found_is_an_empty_listing_on_every_surface(caplog: pytest.LogCaptureFixture) -> None:
    """A name nothing is called is an empty listing: exit 0 beside the 200, and the same body."""
    assert _request().filter_by_name("Nowhereville").df.is_empty()
    with caplog.at_level(logging.WARNING):
        cli_result = _cli("stations", "--name=Nowhereville")
    rest_response = _rest("/api/stations", name="Nowhereville")

    assert cli_result.exit_code == 0, cli_result.output
    assert rest_response.status_code == 200
    assert _json(cli_result.stdout) == _json(rest_response.text)
    assert _json(cli_result.stdout)["stations"] == []
    assert "No stations available for given constraints" in caplog.text


def test_an_empty_result_leaves_a_target_as_it_is(tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:
    """Nothing to write is nothing written: a table a schedule keeps is not replaced with an empty one."""
    target = tmp_path / "values.csv"
    target.write_text("kept")
    with caplog.at_level(logging.WARNING):
        result = _cli("values", "--stations=00001", "--timestamp=1930-06-01", f"--target=file://{target}")

    assert result.exit_code == 0, result.output
    assert target.read_text() == "kept"
    assert "Nothing was written to --target" in caplog.text


def test_a_failure_is_still_an_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit 1 is for failure: a request that cannot be answered is not told as an empty result."""
    from wetterdienst.exceptions import MissingDependencyError  # noqa: PLC0415

    def refuse(**_kwargs: object) -> None:
        msg = "pip install wetterdienst[bufr]"
        raise MissingDependencyError(msg)

    monkeypatch.setattr(cli_module, "get_values", refuse)
    result = _cli("values", "--stations=00001", "--timestamp=2020-05")
    assert result.exit_code == 1


# unknown ids in a station list


@pytest.mark.parametrize("surface", SURFACES)
def test_an_unknown_station_id_in_a_list_is_left_out_and_named(surface: str, caplog: pytest.LogCaptureFixture) -> None:
    """The stations that exist are listed, and a warning names the id that does not -- on every surface."""
    with caplog.at_level(logging.WARNING):
        found = SURFACES[surface](stations="00001,99999")

    assert found == {"00001"}
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert any("99999" in message and "00001" not in message for message in warnings), warnings


@pytest.mark.parametrize("surface", SURFACES)
def test_only_unknown_station_ids_are_an_empty_listing(surface: str, caplog: pytest.LogCaptureFixture) -> None:
    """A list of ids none of which exists is an empty result and a warning, not an error."""
    with caplog.at_level(logging.WARNING):
        found = SURFACES[surface](stations="99998,99999")

    assert found == set()
    assert any("99998, 99999" in record.getMessage() for record in caplog.records)


def test_unknown_station_ids_give_empty_values_and_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    """The values of ids that do not exist are empty on the library, the command line and REST, with the warning."""
    with caplog.at_level(logging.WARNING):
        library = _request().filter_by_station_id("99999").values().all().df
        cli_result = _cli("values", "--stations=99999", "--timestamp=2020-05")
        rest_response = _rest("/api/values", stations="99999", timestamp="2020-05")

    assert library.is_empty()
    assert cli_result.exit_code == 0, cli_result.output
    assert rest_response.status_code == 200
    assert _json(cli_result.stdout) == _json(rest_response.text)
    assert _json(cli_result.stdout)["values"] == []
    assert caplog.text.count("No station with station_id 99999") == 3
    # the answer says it too, by a code that stays: a caller of REST cannot read the log
    warnings = rest_response.json()["metadata"]["warnings"]
    assert [warning["code"] for warning in warnings] == ["unknown-station"]
    assert "99999" in warnings[0]["message"]
    assert rest_response.headers["X-Wetterdienst-Warnings"] == "unknown-station"


def test_the_reference_station_of_a_summary_keeps_its_404(caplog: pytest.LogCaptureFixture) -> None:
    """The one station an estimate is made at is a lookup, not a list: unknown, it is still an error everywhere."""
    request = _request(start="2020-05-01", end="2020-05-03")
    with pytest.raises(StationNotFoundError):
        request.summarize_by_station_id("99999")
    with caplog.at_level(logging.WARNING):
        cli_result = _cli("summarize", "--station=99999", "--timestamp=2020-05")
        rest_response = _rest("/api/summarize", station="99999", timestamp="2020-05")

    assert cli_result.exit_code == 2, cli_result.output
    assert rest_response.status_code == 404


# a window for the listing of stations


def test_stations_take_a_window_and_keep_those_that_overlap_it() -> None:
    """A nearest-three listing for 2020 leaves out the station that closed in 1920, on the command line and REST."""
    point = {"latitude": str(_POINT[0]), "longitude": str(_POINT[1]), "rank": "3"}
    # the closed station is the nearest, so without a window it is listed
    assert "00007" in _cli_stations(**point)
    assert "00007" in _rest_stations(**point)

    with_window = {**point, "timestamp": "2020-05"}
    cli_ids, rest_ids = _cli_stations(**with_window), _rest_stations(**with_window)

    assert cli_ids == rest_ids
    assert "00007" not in cli_ids
    assert len(cli_ids) == 3


def test_a_window_before_a_station_started_leaves_it_out() -> None:
    """A station that began after the window ended cannot have a reading in it."""
    cli_result = _cli("stations", "--all", "--timestamp=1910")
    rest_ids = _rest_stations(all="true", timestamp="1910")

    assert _ids(json.loads(cli_result.stdout)) == rest_ids == {"00007"}


def test_a_window_of_today_keeps_the_stations_that_report_it() -> None:
    """The end an index publishes lags: a station still reporting ends yesterday, and is not left out of today."""
    today = _TODAY.date().isoformat()
    cli_result = _cli("stations", "--all", f"--timestamp={today}")
    rest_ids = _rest_stations(all="true", timestamp=today)

    assert _ids(json.loads(cli_result.stdout)) == rest_ids
    # all but the one that closed in 1920
    assert rest_ids == {row[0] for row in _STATIONS} - {"00007"}


def test_a_window_can_be_given_as_start_and_end_as_for_values() -> None:
    """`--start` and `--end` are the other way to name the window, as for `values`."""
    by_timestamp = _cli("stations", "--all", "--timestamp=1910-01-01/1912-01-01")
    by_start_end = _cli("stations", "--all", "--start=1910-01-01", "--end=1912-01-01")

    assert by_timestamp.exit_code == by_start_end.exit_code == 0
    assert _untimed(by_timestamp.stdout) == _untimed(by_start_end.stdout)
    assert _ids(json.loads(by_start_end.stdout)) == {"00007"}


def test_a_window_both_ways_is_refused_as_for_values() -> None:
    """`--timestamp` with `--start` is a usage error, as for `values`."""
    result = _cli("stations", "--all", "--timestamp=2020", "--start=2020-01-01")
    assert result.exit_code == 2
    assert "not both" in result.output


def test_a_reversed_window_is_refused_on_both_surfaces() -> None:
    """A window that ends before it starts is the request's mistake: a usage error, and a 400."""
    cli_result = _cli("stations", "--all", "--timestamp=2020-06/2020-05")
    rest_response = _rest("/api/stations", all="true", timestamp="2020-06/2020-05")

    assert cli_result.exit_code == 2, cli_result.output
    assert rest_response.status_code == 400


# the same rendering


def _stubbed_result(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    """Answer an estimate with a result of one row, on the command line as on the REST API."""
    from tests.ui.test_restapi import _FETCH_OF_ENDPOINT, _stub_result  # noqa: PLC0415

    _stub_result(monkeypatch, endpoint)
    name = _FETCH_OF_ENDPOINT[endpoint]
    monkeypatch.setattr(cli_module, name, getattr(restapi, name))


_COMMAND = {"/api/values": "values", "/api/interpolate": "interpolate", "/api/summarize": "summarize"}


@pytest.mark.parametrize("fmt", ["json", "geojson"])
@pytest.mark.parametrize("endpoint", ["/api/values", "/api/interpolate", "/api/summarize"])
def test_the_command_line_renders_what_the_rest_api_does(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
    fmt: str,
) -> None:
    """With `with_metadata`, the command line writes the `settings` block too: the one function renders for both."""
    _stubbed_result(monkeypatch, endpoint)
    extra = {} if endpoint == "/api/values" else {"timestamp": "2026-01-01"}
    station = "stations" if endpoint == "/api/values" else "station"
    rest_response = _rest(endpoint, **{station: "01048"}, format=fmt, with_metadata="true", humanize="false", **extra)
    cli_result = _cli(
        _COMMAND[endpoint],
        f"--{station}=01048",
        f"--format={fmt}",
        "--with-metadata=true",
        "--humanize=false",
        *(f"--{key}={value}" for key, value in extra.items()),
    )

    assert rest_response.status_code == 200, rest_response.text
    assert cli_result.exit_code == 0, cli_result.output
    payload = json.loads(cli_result.stdout)
    assert list(payload)[:2] == ["metadata", "settings"]
    assert payload["settings"]["humanize"] is False
    assert _json(cli_result.stdout) == _json(rest_response.text)


def test_the_values_of_the_stubbed_network_are_rendered_alike() -> None:
    """The values read through the stubbed network are the same text on the command line and over REST."""
    cli_result = _cli("values", "--stations=00001", "--timestamp=2020-05", "--with-metadata=true", "--pretty")
    rest_response = _rest("/api/values", stations="00001", timestamp="2020-05", with_metadata="true", pretty="true")

    assert cli_result.exit_code == 0, cli_result.output
    assert "settings" in json.loads(cli_result.stdout)
    assert _untimed(cli_result.stdout.rstrip("\n")) == _untimed(rest_response.text)


def test_a_chart_is_written_as_the_image_the_rest_api_sends() -> None:
    """A chart is the bytes of the image on stdout, not the `repr` of them that `print` wrote."""
    cli_result = _cli("stations", "--all", "--format=png")
    rest_response = _rest("/api/stations", all="true", format="png")

    assert cli_result.exit_code == 0, cli_result.output
    assert rest_response.status_code == 200
    assert cli_result.stdout_bytes == rest_response.content
    assert cli_result.stdout_bytes.startswith(b"\x89PNG")


def test_a_vector_chart_is_text_on_stdout() -> None:
    """An SVG is written as the markup it is, which `print` wrote as the `repr` of its bytes."""
    result = _cli("stations", "--all", "--format=svg")
    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("<svg ")


# one spelling of --pretty


def _commands(group: click.Group, prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], click.Command]]:
    """Walk the commands of a group, the groups' own."""
    found = []
    for name, command in group.commands.items():
        if isinstance(command, click.Group):
            found.extend(_commands(command, (*prefix, name)))
        else:
            found.append(((*prefix, name), command))
    return found


def test_every_command_spells_pretty_the_same() -> None:
    """Each command that writes JSON has `--pretty` as one option: bare to turn it on, or given a boolean."""
    with_pretty = {
        " ".join(path): next(param for param in command.params if param.name == "pretty")
        for path, command in _commands(cli)
        if any(param.name == "pretty" for param in command.params)
    }

    # stations, history, values, interpolate and summarize, alerts and the stripes' stations
    assert set(with_pretty) == {
        "stations",
        "history",
        "values",
        "interpolate",
        "summarize",
        "alerts",
        "stripes stations",
    }
    spellings = {
        (tuple(param.opts), param.type.name, param.is_flag, param.flag_value, param.default)
        for param in with_pretty.values()
    }
    assert spellings == {(("--pretty",), "boolean", False, "true", False)}


@pytest.mark.parametrize("endpoint", ["/api/values", "/api/interpolate", "/api/summarize"])
def test_pretty_is_a_flag_and_a_boolean_on_every_command(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    """`--pretty` and `--pretty=true` do the same and `--pretty=false` leaves the JSON compact, interpolate included."""
    _stubbed_result(monkeypatch, endpoint)
    extra = ["--timestamp=2026-01-01"] if endpoint != "/api/values" else []

    def run(*pretty: str) -> str:
        station = "--stations=01048" if endpoint == "/api/values" else "--station=01048"
        result = _cli(_COMMAND[endpoint], station, *extra, *pretty)
        assert result.exit_code == 0, result.output
        return result.stdout

    bare, valued, off, default = run("--pretty"), run("--pretty=true"), run("--pretty=false"), run()

    assert _untimed(bare) == _untimed(valued)
    assert _untimed(off) == _untimed(default)
    assert _untimed(bare) != _untimed(off)
    assert "\n    " in bare
    assert "\n" not in off.rstrip("\n")


def test_a_bare_pretty_does_not_swallow_the_option_after_it() -> None:
    """`--pretty` followed by another option is a flag: it takes that option's place, not its text."""
    result = _cli("stations", "--stations=00001", "--pretty", "--format=json")
    assert result.exit_code == 0, result.output
    assert "\n    " in result.stdout


def test_a_name_is_matched_among_the_stations_of_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """The best matches of a name for a window are taken among the stations that have a record in it.

    The five best matches of "Berlin" are closed, and the sixth is not: matched first and windowed after,
    the listing came back empty, as a window of today, while a current station matches the name.
    """
    closed = [
        (f"1000{n}", f"Berlin-Alt {n}", dt.datetime(1900, 1, 1, tzinfo=UTC), dt.datetime(1950, 1, 1, tzinfo=UTC))
        for n in range(5)
    ]
    current = [("20000", "Berlin-Tempelhof-Flughafen-Wetterwarte", dt.datetime(1950, 1, 1, tzinfo=UTC), _YESTERDAY)]
    rows = [*closed, *current]
    df = pl.DataFrame(
        {
            "resolution": ["daily"] * len(rows),
            "dataset": ["climate_summary"] * len(rows),
            "station_id": [row[0] for row in rows],
            "start_timestamp": [row[2] for row in rows],
            "end_timestamp": [row[3] for row in rows],
            "latitude": [52.5] * len(rows),
            "longitude": [13.4] * len(rows),
            "elevation": [50.0] * len(rows),
            "name": [row[1] for row in rows],
            "region": ["Berlin"] * len(rows),
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda self: df.lazy())  # noqa: ARG005

    # the closed ones are the best matches: without a window they are what is listed
    assert "20000" not in _cli_stations(name="Berlin", rank="5")
    window = {"name": "Berlin", "rank": "5", "timestamp": "2020-05"}
    assert _cli_stations(**window) == _rest_stations(**window) == {"20000"}


def test_an_empty_listing_leaves_a_target_as_it_is(tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:
    """A listing that finds no station writes nothing to its target either."""
    target = tmp_path / "stations.csv"
    target.write_text("kept")
    with caplog.at_level(logging.WARNING):
        result = _cli("stations", "--name=Nowhereville", f"--target=file://{target}")

    assert result.exit_code == 0, result.output
    assert target.read_text() == "kept"
    assert "Nothing was written to --target" in caplog.text


# one vocabulary: a request is spelled the same on the command line, the REST API and the MCP tools (GH-2561)

#: each request model, with the command, the endpoint and the MCP tool that take it. The REST API's query
#: parameters are the model's fields, and the tools are generated from the endpoints, so what is checked is
#: that the command line has them as options, by the one rule that makes a field an option: hyphens
#: for underscores
_SURFACES = {
    core.StationsRequest: (("stations",), "/api/stations", "stations"),
    core.ValuesRequest: (("values",), "/api/values", "values"),
    core.InterpolationRequest: (("interpolate",), "/api/interpolate", "interpolate"),
    core.SummaryRequest: (("summarize",), "/api/summarize", "summarize"),
    core.HistoryRequest: (("history",), "/api/history", "history"),
    core.IssuesRequest: (("issues",), "/api/issues", "issues"),
    core.AlertsRequest: (("alerts",), "/api/alerts", "alerts"),
    core.AuthRequest: (("about", "auth"), "/api/auth", "auth"),
    core.CoverageRequest: (("about", "coverage"), "/api/coverage", "coverage"),
    core.GlossaryRequest: (("about", "glossary"), "/api/glossary", "glossary"),
    core.ProvidersRequest: (("about", "providers"), "/api/providers", "providers"),
    core.StripesStationsRequest: (("stripes", "stations"), "/api/stripes/stations", "stripes_stations"),
    # the data of the stripes has no command of its own yet (GH-3035)
    core.StripesImageRequest: (("stripes", "image"), "/api/stripes/image", "stripes_image"),
    core.StripesValuesRequest: (None, "/api/stripes/values", "stripes_values"),
    core.SettingsRequest: (None, "/api/settings", None),
}

#: what a surface has beside the fields of the request, and why: the short list a new parameter cannot join
#: by being forgotten
_CLI_ONLY = {
    "target": "writes the result to a file or a database instead of stdout, where REST answers the caller",
    "if_exists": "what --target does with data already there",
    "start": "with --end, the window as two options, read as the one `timestamp`",
    "end": "with --start, the window as two options, read as the one `timestamp`",
}
_CLI_ONLY_OF = {
    ("history",): {"format": "history writes JSON only, as REST does without a `format`"},
}
_REST_ONLY_OF = {
    core.CoverageRequest: {"pretty": "the command line always indents"},
    core.ProvidersRequest: {"pretty": "the command line always indents"},
}
_NO_COMMAND = {
    core.StripesValuesRequest: (
        "the data of the stripes has no command yet: `stripes values`, once the image's name, is not reused (GH-3128)"
    ),
    core.SettingsRequest: "the settings of the server are reported by REST alone, and are no tool",
}


def _cli_command(path: tuple[str, ...]) -> click.Command:
    command: click.Command = cli
    for name in path:
        command = command.commands[name]  # ty: ignore[unresolved-attribute]
    return command


def _cli_options(path: tuple[str, ...]) -> dict[str, click.Option]:
    """Give each option of a command by the field of the request it sets, which is its name with underscores."""
    return {
        param.opts[0].removeprefix("--").replace("-", "_"): param
        for param in _cli_command(path).params
        if isinstance(param, click.Option) and param.expose_value and not param.hidden
    }


def _tools() -> dict[str, dict[str, Any]]:
    """Give the input schema of each MCP tool."""
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def list_tools() -> dict[str, dict[str, Any]]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return {tool.name: tool.input_schema for tool in await client.list_tools()}

    return asyncio.run(list_tools())


def _kind(schema: dict[str, Any]) -> str:
    """Name the JSON type of a field's schema, a reference to an enumeration being a string."""
    options = schema.get("anyOf") or [schema]
    kinds = {option.get("type", "string" if "$ref" in option else None) for option in options}
    (kind,) = kinds - {None, "null"}
    return kind


def _cli_kind(param: click.Option) -> str:
    """Name the JSON type a command line option is read as: a list or a mapping is written as one string."""
    if param.type is click.BOOL:
        return "boolean"
    if isinstance(param.type, click.types.IntParamType):
        return "integer"
    if isinstance(param.type, click.types.FloatParamType):
        return "number"
    return "string"


@pytest.mark.parametrize("model", _SURFACES, ids=lambda model: model.__name__)
def test_every_field_of_a_request_is_an_option_and_an_mcp_argument(model: type[BaseModel]) -> None:
    """Each field has an option of the name and the type on the command line and an argument of them in the MCP tool.

    A parameter then cannot be added to one surface and forgotten on another: the fields of the request model,
    the query parameters of its endpoint and the arguments of its tool are one list, and the command line's
    options are that list with underscores as hyphens, but for the few that are written down above with the
    reason they have no counterpart.
    """
    path, endpoint, tool = _SURFACES[model]
    fields = model.model_fields
    schema = model.model_json_schema()["properties"]

    # the endpoint takes the fields, and the tool is the endpoint
    parameters = {p["name"]: p for p in restapi.app.openapi()["paths"][_versioned(endpoint)]["get"]["parameters"]}
    assert set(parameters) == set(fields)
    if tool is not None:
        arguments = _tools()[tool]["properties"]
        assert set(arguments) == set(fields)
        assert {name: _kind(argument) for name, argument in arguments.items()} == {
            name: _kind(schema[name]) for name in fields
        }

    if path is None:
        assert model in _NO_COMMAND
        return
    options = _cli_options(path)
    rest_only = _REST_ONLY_OF.get(model, {})
    cli_only = {**_CLI_ONLY, **_CLI_ONLY_OF.get(path, {})}
    assert set(fields) - set(options) == set(rest_only), "a field without an option is written down with its reason"
    assert set(options) - set(fields) <= set(cli_only), "an option without a field is written down with its reason"
    for name in set(fields) & set(options):
        param = options[name]
        assert _cli_kind(param) == {"array": "string", "object": "string"}.get(_kind(schema[name]), _kind(schema[name]))
        # a choice of the command line is the choice of the request
        choices = next((o["enum"] for o in schema[name].get("anyOf", [schema[name]]) if "enum" in o), None)
        if isinstance(param.type, click.Choice) and choices is not None:
            assert {c.lower() for c in param.type.choices} == {c.lower() for c in choices}, name


def _options_of_every_command() -> list[tuple[tuple[str, ...], click.Option]]:
    return [
        (path, param)
        for path, command in _commands(cli)
        for param in command.params
        if isinstance(param, click.Option) and param.expose_value and not param.hidden
    ]


def test_no_option_of_the_command_line_has_an_underscore() -> None:
    """The command line spells an option with hyphens, and REST and MCP the same parameter with underscores (GH-2561).

    The mapping is the one this module tests the options against: `--name-threshold` is `name_threshold`.
    """
    spelled = [(" ".join(path), opt) for path, param in _options_of_every_command() for opt in param.opts]
    assert spelled
    assert [(command, opt) for command, opt in spelled if "_" in opt] == []


@pytest.mark.parametrize(
    ("path", "option"),
    [
        pytest.param(path, param.opts[0], id=f"{' '.join(path)} {param.opts[0]}")
        for path, param in _options_of_every_command()
        if "-" in param.opts[0].removeprefix("--")
    ],
)
@pytest.mark.parametrize("given", ["{old}=x", "{old} x", "{old}"])
def test_an_option_by_its_underscored_name_is_refused_naming_the_hyphenated_one(
    path: tuple[str, ...], option: str, given: str
) -> None:
    """The names the command line had, with underscores, are refused naming the new one, not read (GH-2561).

    Not an alias: a hard rename, as the other renames of the 1.0 series are, with or without a value.
    """
    old = "--" + option.removeprefix("--").replace("-", "_")
    result = CliRunner().invoke(cli, [*path, *given.format(old=old).split()])

    assert result.exit_code == 2, result.output
    assert f"Error: {old} was renamed to {option}." in result.output


# a list is plural on every surface: what the singular was is refused naming the plural
_SINGULARS = [
    ((command,), old, new)
    for command in ("stations", "values", "history")
    for old, new in (("--station", "--stations"), ("--parameter", "--parameters"))
] + [
    (("stations",), "--period", "--periods"),
    (("values",), "--period", "--periods"),
    (("interpolate",), "--parameter", "--parameters"),
    (("interpolate",), "--period", "--periods"),
    (("summarize",), "--parameter", "--parameters"),
    (("summarize",), "--period", "--periods"),
    (("about", "coverage"), "--resolution", "--resolutions"),
    (("about", "coverage"), "--dataset", "--datasets"),
]


@pytest.mark.parametrize(
    ("path", "old", "new"), _SINGULARS, ids=lambda value: " ".join(value) if isinstance(value, tuple) else value
)
@pytest.mark.parametrize("given", ["{old}=x", "{old} x", "{old}"])
def test_an_option_by_the_singular_of_its_list_is_refused_naming_the_plural(
    path: tuple[str, ...], old: str, new: str, given: str
) -> None:
    """A parameter that takes a list is plural on the command line as it is over REST and MCP (GH-2561)."""
    result = CliRunner().invoke(cli, [*path, *given.format(old=old).split()])

    assert result.exit_code == 2, result.output
    assert f"Error: {old} was renamed to {new}." in result.output


@pytest.mark.parametrize(
    ("endpoint", "old", "new"),
    [
        (endpoint, old, new)
        for endpoint in ("/api/stations", "/api/values", "/api/history")
        for old, new in (("station", "stations"), ("parameter", "parameters"))
    ]
    + [(endpoint, "period", "periods") for endpoint in ("/api/stations", "/api/values")]
    + [("/api/coverage", "resolution", "resolutions"), ("/api/coverage", "dataset", "datasets")],
)
def test_the_singular_of_a_list_is_refused_over_rest_naming_the_plural(endpoint: str, old: str, new: str) -> None:
    """Over REST, as on the command line, the old name fails with the new one in the answer (GH-2561)."""
    response = _rest(endpoint, **{old: "x"})

    assert response.status_code == 422, response.text
    assert f"{old} was renamed to {new}" in response.json()["detail"]
    assert [error["type"] for error in response.json()["errors"] if error["loc"] == ["query", old]] == ["renamed"]


@pytest.mark.parametrize(
    ("tool", "old", "new"),
    [
        ("values", "station", "stations"),
        ("stations", "station", "stations"),
        ("history", "station", "stations"),
        ("values", "parameter", "parameters"),
        ("values", "period", "periods"),
        ("coverage", "resolution", "resolutions"),
        ("coverage", "dataset", "datasets"),
    ],
)
def test_the_singular_of_a_list_is_refused_by_the_mcp_tool_naming_the_plural(tool: str, old: str, new: str) -> None:
    """The MCP tools take the plural, and refuse the singular by naming it, as the endpoints do (GH-2561)."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> None:
        async with Client(build_mcp_server(restapi.app)) as client:
            await client.call_tool(tool, {"provider": "dwd", "network": "observation", old: "x"})

    with pytest.raises(ToolError, match=f"{old} was renamed to {new}"):
        asyncio.run(call())


def test_the_one_reference_station_of_an_estimate_stays_singular_on_every_surface() -> None:
    """`interpolate` and `summarize` take one `station`, not a list, and the plural is not an alias of it (GH-2561)."""
    for endpoint, path in (("/api/interpolate", ("interpolate",)), ("/api/summarize", ("summarize",))):
        assert "station" in {
            p["name"] for p in restapi.app.openapi()["paths"][_versioned(endpoint)]["get"]["parameters"]
        }
        assert "station" in _cli_options(path)
        assert "stations" not in _cli_options(path)
    response = _rest("/api/interpolate", stations="00001", timestamp="2020-05")
    assert response.status_code == 422
    assert "renamed" not in response.text


# lists are comma-separated by contract


def test_the_openapi_document_has_each_list_as_one_comma_separated_value() -> None:
    """A list in a query is documented as `?parameters=a,b`, and the repeated key is left out of it (GH-2561)."""
    lists = [
        (path, parameter)
        for path, operations in restapi.app.openapi()["paths"].items()
        for operation in operations.values()
        for parameter in operation.get("parameters", [])
        if any(option.get("type") == "array" for option in parameter["schema"].get("anyOf", [parameter["schema"]]))
    ]
    assert {parameter["name"] for _, parameter in lists} >= {"parameters", "periods", "stations", "sections"}
    assert [(path, parameter["name"]) for path, parameter in lists if parameter.get("explode") is not False] == []
    assert {parameter.get("style") for _, parameter in lists} == {"form"}


@pytest.mark.parametrize("surface", ["cli", "rest"])
def test_a_list_is_read_comma_separated_and_repeated_alike(surface: str) -> None:
    """The comma-separated list is the contract; the repeated key is read as the same, and not documented (GH-2561)."""
    if surface == "rest":
        client = TestClient(restapi.app, raise_server_exceptions=False)
        base = {"provider": "dwd", "network": "observation", "parameters": PARAMETER}
        comma = client.get("/api/stations", params={**base, "stations": "00001,00002"})
        repeated = client.get("/api/stations", params={**base, "stations": ["00001", "00002"]})
        assert comma.status_code == repeated.status_code == 200, (comma.text, repeated.text)
        assert _json(comma.text) == _json(repeated.text)
        assert _ids(comma.json()) == {"00001", "00002"}
    else:
        comma = _cli("stations", "--stations=00001,00002")
        repeated = _cli("stations", "--stations=00001", "--stations=00002")
        # an option given twice is the last one given: a list is comma-separated here, and not repeated
        assert comma.exit_code == 0, comma.output
        assert _ids(json.loads(comma.stdout)) == {"00001", "00002"}
        assert _ids(json.loads(repeated.stdout)) == {"00002"}


# one boolean spelling

_TRUE = ["true", "1", "yes", "on", "t", "y", "TRUE", "True"]
_FALSE = ["false", "0", "no", "off", "f", "n", "FALSE", "False"]
_NOT_BOOLEAN = ["maybe", "2", "truee", "nope"]


@pytest.mark.parametrize("spelling", [*_TRUE, *_FALSE, *_NOT_BOOLEAN])
def test_a_boolean_is_spelled_the_same_on_the_command_line_and_over_rest(spelling: str) -> None:
    """`true`, `1`, `yes`, `on`, `t`, `y` and their opposites are a boolean on both, and nothing else is (GH-2561)."""
    rest = _rest("/api/stations", all="true", pretty=spelling)
    cli_result = _cli("stations", "--all", f"--pretty={spelling}")

    if spelling in _NOT_BOOLEAN:
        assert (rest.status_code, cli_result.exit_code) == (422, 2)
        return
    assert (rest.status_code, cli_result.exit_code) == (200, 0), (rest.text, cli_result.output)
    # the one value decides the same, whichever surface reads it
    assert ("\n" in rest.text) == ("\n" in cli_result.stdout.rstrip("\n")) == (spelling in _TRUE)


def test_every_boolean_option_is_one_option_whatever_the_command() -> None:
    """Each boolean option is on bare, and takes `=true` or `=false`: no flag takes no value (GH-2561)."""
    booleans = [(path, param) for path, param in _options_of_every_command() if param.type is click.BOOL]
    assert {param.opts[0] for _, param in booleans} >= {
        "--all",
        "--debug",
        "--pretty",
        "--with-metadata",
        "--humanize",
        "--skip-empty",
        "--show-title",
    }
    assert [
        (" ".join(path), param.opts[0])
        for path, param in booleans
        if (param.is_flag, param.flag_value) != (False, "true") or param.default not in {True, False}
    ] == []
    # the options that are no boolean take a value, so none is a bare flag of another kind
    assert [(" ".join(path), param.opts[0]) for path, param in _options_of_every_command() if param.is_flag] == []


@pytest.mark.parametrize("command", [["stations", "--all"], ["values", "--all", "--timestamp=2020-05"]])
def test_a_bare_boolean_is_on_and_a_boolean_with_a_value_is_that_value(command: list[str]) -> None:
    """`--with-metadata` is `--with-metadata=true`, as `--pretty` and `--all` are theirs (GH-2561)."""
    bare = _cli(*command, "--with-metadata")
    valued = _cli(*command, "--with-metadata=true")
    off = _cli(*command, "--with-metadata=false")

    assert bare.exit_code == valued.exit_code == off.exit_code == 0, (bare.output, off.output)
    assert _untimed(bare.stdout) == _untimed(valued.stdout)
    assert _untimed(bare.stdout) != _untimed(off.stdout)
    assert "parameters" in json.loads(bare.stdout)["metadata"]
    assert "parameters" not in json.loads(off.stdout)["metadata"]


# exclusive selections are one rule: the same error type, and the alternatives named


@pytest.mark.parametrize(
    ("selection", "error_type"),
    [
        pytest.param({}, "missing_one_of", id="none"),
        pytest.param({"stations": "00001", "name": "Dresden"}, "mutually_exclusive", id="stations-and-name"),
        pytest.param({"all": "true", "sql": "region='Sachsen'"}, "mutually_exclusive", id="all-and-sql"),
        pytest.param(
            {"latitude": "51", "longitude": "13", "rank": "2", "distance": "9"},
            "mutually_exclusive",
            id="rank-distance",
        ),
    ],
)
def test_a_bad_station_selection_is_the_same_refusal_on_every_surface(
    selection: dict[str, str], error_type: str
) -> None:
    """None, two or half of a station selection is the one error, which names the alternatives, everywhere (GH-2561)."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    rest = _rest("/api/values", **selection)
    assert rest.status_code == 422, rest.text
    assert {error["type"] for error in rest.json()["errors"]} == {error_type}
    named = "rank or distance" if "rank" in selection else "all, stations, name"
    assert f"xactly one of {named}" in rest.json()["detail"]

    cli_result = _cli("values", *(f"--{key}={value}" for key, value in selection.items()))
    assert cli_result.exit_code == 2, cli_result.output
    option_names = "'--rank' or '--distance'" if "rank" in selection else "'--all', '--stations', '--name'"
    assert f"one of {option_names}" in cli_result.output

    async def call() -> None:
        async with Client(build_mcp_server(restapi.app)) as client:
            await client.call_tool(
                "values", {"provider": "dwd", "network": "observation", "parameters": PARAMETER, **selection}
            )

    with pytest.raises(ToolError) as tool_error:
        asyncio.run(call())
    assert f"xactly one of {named}" in str(tool_error.value)


@pytest.mark.parametrize("given", [["00001", "00002"], "00001,00002"])
def test_an_mcp_list_argument_is_a_list_or_one_comma_separated_string(given: list[str] | str) -> None:
    """A tool takes a list as the JSON array its schema says, and as the comma-separated string (GH-2561)."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as client:
            result = await client.call_tool(
                "stations", {"provider": "dwd", "network": "observation", "parameters": PARAMETER, "stations": given}
            )
            return result.structured_content

    answer = asyncio.run(call())
    assert _ids(answer.get("result", answer)) == {"00001", "00002"}


@pytest.mark.parametrize(
    ("command", "option"),
    [("history", "--section"), ("values", "--start_date"), ("stations", "--statio")],
)
def test_an_option_that_was_never_renamed_is_clicks_own_refusal(command: str, option: str) -> None:
    """Only a name an option had is told as a rename: a typo, or a name a refusal answers for, is click's (GH-2561)."""
    result = CliRunner().invoke(cli, [command, f"{option}=x"])
    assert result.exit_code == 2, result.output
    assert "was renamed" not in result.output
    assert is_no_such_option(result.output, option)


@pytest.mark.parametrize("option", ["--lead-time", "--issue"])
def test_stations_on_the_command_line_do_not_take_the_run(option: str) -> None:
    """`stations` has no `--lead-time` and `--issue`, the run being chosen for `values`, which has them (GH-3056).

    0.156.0 added them to satisfy the parity test, and they changed nothing in the list.
    """
    result = _cli("stations", "--all", f"{option}=long")
    assert result.exit_code == 2, result.output
    assert is_no_such_option(result.output, option)
    assert {"lead_time", "issue"} <= set(_cli_options(("values",)))


@pytest.mark.parametrize("name", ["lead_time", "issue"])
def test_stations_over_rest_refuse_the_run(name: str) -> None:
    """`/api/stations` answers a run with a 422, as it does any parameter it does not take (GH-3056, GH-3061).

    0.156.0 took the pair onto `stations` to satisfy this file, and they changed nothing in the list;
    the command line and the tool dropped them in GH-3056, REST now does too.
    """
    response = TestClient(restapi.app).get(
        _versioned("/api/stations"),
        params={"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": "true", name: "long"},
    )
    assert response.status_code == 422, response.text
    assert name in response.text
    parameters = restapi.app.openapi()["paths"][_versioned("/api/stations")]["get"]["parameters"]
    assert name not in {p["name"] for p in parameters}
    assert {"lead_time", "issue"} <= {
        p["name"] for p in restapi.app.openapi()["paths"][_versioned("/api/values")]["get"]["parameters"]
    }


@pytest.mark.parametrize("name", ["lead_time", "issue"])
def test_the_stations_tool_refuses_the_run(name: str) -> None:
    """The MCP `stations` tool does not take the run, and a call giving it is refused, as for any other argument."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> None:
        async with Client(build_mcp_server(restapi.app)) as client:
            await client.call_tool("stations", {"provider": "dwd", "network": "observation", name: "long"})

    with pytest.raises(ToolError, match=f"{name} is not an argument of stations"):
        asyncio.run(call())
    # the tools that read a run keep it
    assert {"lead_time", "issue"} <= set(_tools()["values"]["properties"])


# a failure is the same classification on REST and in the MCP tools (GH-2561, GH-2984)


def _classified_failures() -> list[Any]:
    from wetterdienst import exceptions  # noqa: PLC0415

    timeout = exceptions.DownloadError("https://opendata.example.org/file.zip", "timed out")
    timeout.__cause__ = TimeoutError()
    return [
        pytest.param(exceptions.RequestError("the request cannot be served"), 400, id="request"),
        pytest.param(exceptions.StationNotFoundError("no such station"), 404, id="not-found"),
        pytest.param(exceptions.CredentialRejectedError("WD_AUTH__X was rejected"), 501, id="credential"),
        pytest.param(exceptions.MissingDependencyError("pip install x"), 501, id="dependency"),
        pytest.param(exceptions.DownloadError("https://opendata.example.org/file.zip", "503"), 502, id="download"),
        pytest.param(
            exceptions.NoInternetError("No internet connection: could not reach https://x"), 503, id="offline"
        ),
        pytest.param(timeout, 504, id="timeout"),
        pytest.param(RuntimeError("/srv/secret/path"), 500, id="bug"),
    ]


@pytest.mark.parametrize(("error", "status"), _classified_failures())
def test_a_failure_is_classified_alike_over_rest_and_through_the_mcp_tool(
    monkeypatch: pytest.MonkeyPatch, error: BaseException, status: int
) -> None:
    """One exception gets one status and one sentence on REST and as a tool error, not each surface's own (GH-2561).

    The tool error is made from the REST API's problem, so it carries the status and the `detail`
    over, and whatever the REST API leaves out of the `detail` -- a path, a URL, a setting -- is
    left out of the tool error too. An exception no endpoint handled is covered by
    `test_an_unhandled_exception_is_the_fixed_500_over_http_and_through_mcp` (GH-2984).
    """
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    def raises(**_kwargs: object) -> None:
        raise error

    monkeypatch.setattr("wetterdienst.ui.restapi.get_values", raises)
    arguments = {"provider": "dwd", "network": "observation", "parameters": PARAMETER, "stations": "00001"}

    rest = _rest("/api/values", stations="00001")
    assert rest.status_code == status, rest.text
    assert rest.headers["content-type"] == "application/problem+json"
    detail = rest.json()["detail"]

    async def call() -> None:
        async with Client(build_mcp_server(restapi.app)) as client:
            await client.call_tool("values", arguments)

    with pytest.raises(ToolError) as tool_error:
        asyncio.run(call())
    message = str(tool_error.value)
    assert f"HTTP error {status}" in message
    assert detail in message
    for secret in ("/srv/secret/path", "opendata.example.org", "WD_AUTH__X"):
        assert secret not in message or secret in detail, secret


# the metadata block says what the request resolved to


def test_the_stations_selected_by_id_are_told_as_such() -> None:
    """A selection by `station_id` is told as that, with the ids that are in the answer and not those that are not."""
    metadata = _rest("/api/stations", stations="00001,99999").json()["metadata"]

    assert metadata["request"]["stations"] == {"filter": "by_station_id", "count": 1, "ids": ["00001"]}
    assert metadata["request"]["provider"] == "dwd"
    assert [warning["code"] for warning in metadata["warnings"]] == ["unknown-station"]


def test_readings_dropped_for_being_a_missing_value_marker_are_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The readings that are a marker for a missing value leave with the nulls, and the answer says how many."""
    original = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001

    def marked(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401
        df = original(self, station_id, parameter_or_dataset)
        return df.with_columns(
            pl.when(pl.col("timestamp") == dt.datetime(2020, 5, 1, tzinfo=UTC))
            .then(None)
            .otherwise(pl.col("value"))
            .alias("value"),
            pl.when(pl.col("timestamp") == dt.datetime(2020, 5, 1, tzinfo=UTC))
            .then(pl.lit("raw:-999"))
            .otherwise(pl.col("quality_flags"))
            .alias("quality_flags"),
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", marked)

    dropped = _rest("/api/values", stations="00001,00002", timestamp="2020-05").json()
    kept = _rest("/api/values", stations="00001,00002", timestamp="2020-05", drop_nulls="false").json()

    assert [warning["code"] for warning in dropped["metadata"]["warnings"]] == ["missing-value-marker"]
    assert dropped["metadata"]["warnings"][0]["message"].startswith("2 readings")
    assert "2020-05-01" not in {row["timestamp"][:10] for row in dropped["values"]}
    # kept as null, the readings carry the marker in their flags, and are counted all the same
    assert {row["quality_flags"] for row in kept["values"] if row["value"] is None} == {"raw:-999"}
    assert kept["metadata"]["warnings"][0]["message"].startswith("2 readings")
