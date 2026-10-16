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
from typing import TYPE_CHECKING, Any

import click
import polars as pl
import pytest
from click.testing import CliRunner, Result
from fastapi.testclient import TestClient

from wetterdienst.exceptions import StationNotFoundError
from wetterdienst.model.request import DEFAULT_NAME_RANK, DEFAULT_NAME_RANK_LISTING
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui import cli as cli_module
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    import pathlib

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
_EMPTY_VALUES = {"values": []}


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
        result = request.filter_by_station_id(selection["station"].split(","))
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
    library = set(_request().filter_by_name("Dresden").values.all().df.get_column("station_id"))
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
    parameters = {parameter["name"]: parameter for parameter in openapi["paths"]["/api/stations"]["get"]["parameters"]}
    assert f"default {DEFAULT_NAME_RANK_LISTING} for `stations`" in parameters["rank"]["description"]
    assert f"{DEFAULT_NAME_RANK} for `values`" in parameters["rank"]["description"]


# an empty result: what the library hands back, the REST API answers with a 200, and the command line with exit 0


def test_a_window_without_readings_is_an_empty_result_on_every_surface(caplog: pytest.LogCaptureFixture) -> None:
    """A window in which a station has no reading is an empty frame, a 200 and exit 0, all with the same body.

    The command line exited 1, as for a failure, so a schedule asking for a value before it is published failed.
    """
    window = {"timestamp": "1930-06-01"}
    library = _request(start="1930-06-01", end="1930-06-01").filter_by_station_id("00001").values.all().df
    with caplog.at_level(logging.WARNING):
        cli_result = _cli("values", "--station=00001", "--timestamp=1930-06-01")
    rest_response = _rest("/api/values", station="00001", **window)

    assert library.is_empty()
    assert cli_result.exit_code == 0, cli_result.output
    assert rest_response.status_code == 200
    assert json.loads(cli_result.stdout) == rest_response.json() == _EMPTY_VALUES
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
    cli_result = _cli("values", "--station=00001", "--timestamp=1930-06-01", "--format=csv")
    rest_response = _rest("/api/values", station="00001", timestamp="1930-06-01", format="csv")

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
    assert json.loads(cli_result.stdout) == rest_response.json() == {"stations": []}
    assert "No stations available for given constraints" in caplog.text


def test_an_empty_result_leaves_a_target_as_it_is(tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture) -> None:
    """Nothing to write is nothing written: a table a schedule keeps is not replaced with an empty one."""
    target = tmp_path / "values.csv"
    target.write_text("kept")
    with caplog.at_level(logging.WARNING):
        result = _cli("values", "--station=00001", "--timestamp=1930-06-01", f"--target=file://{target}")

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
    result = _cli("values", "--station=00001", "--timestamp=2020-05")
    assert result.exit_code == 1


# unknown ids in a station list


@pytest.mark.parametrize("surface", SURFACES)
def test_an_unknown_station_id_in_a_list_is_left_out_and_named(surface: str, caplog: pytest.LogCaptureFixture) -> None:
    """The stations that exist are listed, and a warning names the id that does not -- on every surface."""
    with caplog.at_level(logging.WARNING):
        found = SURFACES[surface](station="00001,99999")

    assert found == {"00001"}
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert any("99999" in message and "00001" not in message for message in warnings), warnings


@pytest.mark.parametrize("surface", SURFACES)
def test_only_unknown_station_ids_are_an_empty_listing(surface: str, caplog: pytest.LogCaptureFixture) -> None:
    """A list of ids none of which exists is an empty result and a warning, not an error."""
    with caplog.at_level(logging.WARNING):
        found = SURFACES[surface](station="99998,99999")

    assert found == set()
    assert any("99998, 99999" in record.getMessage() for record in caplog.records)


def test_unknown_station_ids_give_empty_values_and_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    """The values of ids that do not exist are empty on the library, the command line and REST, with the warning."""
    with caplog.at_level(logging.WARNING):
        library = _request().filter_by_station_id("99999").values.all().df
        cli_result = _cli("values", "--station=99999", "--timestamp=2020-05")
        rest_response = _rest("/api/values", station="99999", timestamp="2020-05")

    assert library.is_empty()
    assert cli_result.exit_code == 0, cli_result.output
    assert rest_response.status_code == 200
    assert json.loads(cli_result.stdout) == rest_response.json() == _EMPTY_VALUES
    assert caplog.text.count("No station with station_id 99999") == 3


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
    assert by_timestamp.stdout == by_start_end.stdout
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
    rest_response = _rest(endpoint, station="01048", format=fmt, with_metadata="true", humanize="false", **extra)
    cli_result = _cli(
        _COMMAND[endpoint],
        "--station=01048",
        f"--format={fmt}",
        "--with_metadata=true",
        "--humanize=false",
        *(f"--{key}={value}" for key, value in extra.items()),
    )

    assert rest_response.status_code == 200, rest_response.text
    assert cli_result.exit_code == 0, cli_result.output
    payload = json.loads(cli_result.stdout)
    assert list(payload)[:2] == ["metadata", "settings"]
    assert payload["settings"]["humanize"] is False
    assert payload == rest_response.json()


def test_the_values_of_the_stubbed_network_are_rendered_alike() -> None:
    """The values read through the stubbed network are the same text on the command line and over REST."""
    cli_result = _cli("values", "--station=00001", "--timestamp=2020-05", "--with_metadata=true", "--pretty")
    rest_response = _rest("/api/values", station="00001", timestamp="2020-05", with_metadata="true", pretty="true")

    assert cli_result.exit_code == 0, cli_result.output
    assert "settings" in json.loads(cli_result.stdout)
    assert cli_result.stdout.rstrip("\n") == rest_response.text


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
        result = _cli(_COMMAND[endpoint], "--station=01048", *extra, *pretty)
        assert result.exit_code == 0, result.output
        return result.stdout

    bare, valued, off, default = run("--pretty"), run("--pretty=true"), run("--pretty=false"), run()

    assert bare == valued
    assert off == default
    assert bare != off
    assert "\n    " in bare
    assert "\n" not in off.rstrip("\n")


def test_a_bare_pretty_does_not_swallow_the_option_after_it() -> None:
    """`--pretty` followed by another option is a flag: it takes that option's place, not its text."""
    result = _cli("stations", "--station=00001", "--pretty", "--format=json")
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
