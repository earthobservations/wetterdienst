# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The UIs hand a request the options the settings once carried, for each of the 15 options (GH-2639).

The REST API, the command line and the MCP tools (which are the REST API's) built a `Settings` with
the ``ts_*`` settings their query parameters and options name, and fetched with it. They now build
`Options` and fetch with that, the host's `Settings` left alone. The wire stays as it was: the same
query parameters, options and ``WD_TS_*`` variables set the same things.

Each test fetches nothing: the getter of the endpoint or command is stood in for, takes the options it is
given, and the test holds them to what ``Settings(ts_<option>=...)`` carried to a request before. The
frames the options then give are the requests' (`tests/test_request_options.py`).
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst import Settings
from wetterdienst.options import Options, options_from_settings
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable

_OBSERVATION = {"provider": "dwd", "network": "observation", "parameters": "daily/kl/temperature_air_mean_2m"}
_CLI_DWD = ["--provider=dwd", "--network=observation", "--parameters=daily/kl/temperature_air_mean_2m"]
#: what each endpoint and command needs besides its options
_REST_BASE = {
    "values": {**_OBSERVATION, "station": "01048"},
    "interpolate": {**_OBSERVATION, "station": "01048", "timestamp": "2026-01-01"},
    "summarize": {**_OBSERVATION, "station": "01048", "timestamp": "2026-01-01"},
}
_CLI_BASE = {
    "values": [*_CLI_DWD, "--station=01048"],
    "interpolate": [*_CLI_DWD, "--station=01048", "--timestamp=2026-01-01"],
    "summarize": [*_CLI_DWD, "--station=01048", "--timestamp=2026-01-01"],
}
_GETTER = {"values": "get_values", "interpolate": "get_interpolate", "summarize": "get_summarize"}

_FAHRENHEIT = {"temperature": "degree_fahrenheit"}


@dataclass(frozen=True)
class Case:
    """One option, the value it is set to, and how each surface sets it.

    `rest` and `cli` map an endpoint or command to what sets the option there, a surface with no
    entry leaving the option to the environment alone. `endpoints` are the ones the environment's
    variable is checked on.
    """

    option: str
    value: Any
    env: str
    endpoints: tuple[str, ...]
    rest: dict[str, dict[str, str]] = field(default_factory=dict)
    cli: dict[str, list[str]] = field(default_factory=dict)

    @property
    def variable(self) -> str:
        """Name the environment variable that sets the option."""
        return f"WD_TS_{self.option.upper()}"


_VALUES = ("values",)
_GEO = ("interpolate", "summarize")

CASES = [
    Case("humanize", False, "false", _VALUES, {"values": {"humanize": "false"}}, {"values": ["--humanize=false"]}),  # noqa: FBT003
    Case("shape", "wide", "wide", _VALUES, {"values": {"shape": "wide"}}, {"values": ["--shape=wide"]}),
    Case(
        "convert_units",
        False,  # noqa: FBT003
        "false",
        _VALUES,
        {"values": {"convert_units": "false"}},
        {"values": ["--convert_units=false"]},
    ),
    Case(
        "unit_targets",
        _FAHRENHEIT,
        json.dumps(_FAHRENHEIT),
        _VALUES,
        {"values": {"unit_targets": json.dumps(_FAHRENHEIT)}},
        {"values": [f"--unit_targets={json.dumps(_FAHRENHEIT)}"]},
    ),
    Case("skip_empty", True, "true", _VALUES, {"values": {"skip_empty": "true"}}, {"values": ["--skip_empty=true"]}),  # noqa: FBT003
    Case(
        "skip_threshold",
        0.5,
        "0.5",
        _VALUES,
        {"values": {"skip_threshold": "0.5"}},
        {"values": ["--skip_threshold=0.5"]},
    ),
    Case(
        "skip_criteria",
        "max",
        "max",
        _VALUES,
        {"values": {"skip_criteria": "max"}},
        {"values": ["--skip_criteria=max"]},
    ),
    Case(
        "drop_nulls",
        False,  # noqa: FBT003
        "false",
        _VALUES,
        {"values": {"drop_nulls": "false"}},
        {"values": ["--drop_nulls=false"]},
    ),
    Case(
        "geo_station_distance_homogeneous",
        60.0,
        "60",
        _GEO,
        {
            "interpolate": {"interpolation_station_distance_homogeneous": "60"},
            "summarize": {"summary_station_distance_homogeneous": "60"},
        },
        {
            "interpolate": ["--interpolation_station_distance_homogeneous=60"],
            "summarize": ["--summary_station_distance_homogeneous=60"],
        },
    ),
    Case(
        "geo_station_distance_heterogeneous",
        15.0,
        "15",
        _GEO,
        {
            "interpolate": {"interpolation_station_distance_heterogeneous": "15"},
            "summarize": {"summary_station_distance_heterogeneous": "15"},
        },
        {
            "interpolate": ["--interpolation_station_distance_heterogeneous=15"],
            "summarize": ["--summary_station_distance_heterogeneous=15"],
        },
    ),
    Case(
        "geo_station_distance",
        {"precipitation_amount": 25.0},
        '{"precipitation_amount": 25}',
        _GEO,
        {
            "interpolate": {"interpolation_station_distance": '{"precipitation_amount": 25}'},
            "summarize": {"summary_station_distance": '{"precipitation_amount": 25}'},
        },
        {
            "interpolate": ['--interpolation_station_distance={"precipitation_amount": 25}'],
            "summarize": ['--summary_station_distance={"precipitation_amount": 25}'],
        },
    ),
    Case(
        "geo_use_nearby_station_distance",
        0.5,
        "0.5",
        _GEO,
        {"interpolate": {"use_nearby_station_distance": "0.5"}},
        {"interpolate": ["--use_nearby_station_distance=0.5"]},
    ),
    Case(
        "geo_min_gain_of_value_pairs",
        0.5,
        "0.5",
        _GEO,
        {"interpolate": {"min_gain_of_value_pairs": "0.5"}, "summarize": {"min_gain_of_value_pairs": "0.5"}},
    ),
    Case(
        "geo_num_additional_stations",
        5,
        "5",
        _GEO,
        {"interpolate": {"num_additional_stations": "5"}, "summarize": {"num_additional_stations": "5"}},
    ),
    # set by the server alone: no query parameter and no command line option names it
    Case("geo_station_distance_resolution_factors", {"daily": 3.0}, '{"daily": 3.0}', _GEO),
]


def test_every_option_is_a_case() -> None:
    """Test no option is left out, as the 15 are the ones to hold the UIs to."""
    assert {case.option for case in CASES} == set(Options.model_fields)


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the options.

    The cache directory the test session gives each worker is kept.
    """
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


class _Taken(Exception):  # noqa: N818
    """Raised in place of fetching, to stop where the options have been taken."""


def _before(case: Case) -> Options:
    """Give the options that ``Settings(ts_<option>=...)`` carried to a request, as the UIs once built them."""
    return options_from_settings(Settings(**{f"ts_{case.option}": case.value}))


def _is_set(options: Options, case: Case) -> bool:
    """Tell whether the options carry the value the case sets, which a surface that dropped it would not."""
    return options.model_dump()[case.option] == case.value


def _take(monkeypatch: pytest.MonkeyPatch, getter: str) -> list[Options]:
    """Stand in for a getter of the UIs, to take the options it is given, as well as the host's settings."""
    taken: list[Options] = []

    def take(*, settings: Settings, options: Options, **_kwargs: object) -> None:
        assert isinstance(settings, Settings)
        taken.append(options)
        raise _Taken

    monkeypatch.setattr(f"wetterdienst.ui.restapi.{getter}", take)
    return taken


def _rest(monkeypatch: pytest.MonkeyPatch, endpoint: str, params: dict[str, str]) -> Options:
    """Answer a request to the REST API up to its fetch, and return the options it would fetch with."""
    taken = _take(monkeypatch, _GETTER[endpoint])
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        f"/api/{endpoint}", params={**_REST_BASE[endpoint], **params}
    )
    assert response.status_code == 500, response.text
    (options,) = taken
    return options


def _cli(monkeypatch: pytest.MonkeyPatch, command: str, args: list[str]) -> Options:
    """Run a command up to its fetch, and return the options it would fetch with."""
    taken: list[Options] = []

    def take(_get: object, *, settings: Settings, options: Options, **_kwargs: object) -> None:
        assert isinstance(settings, Settings)
        taken.append(options)
        raise _Taken

    monkeypatch.setattr("wetterdienst.ui.cli._collect_or_exit", take)
    result = CliRunner().invoke(cli, [command, *_CLI_BASE[command], *args])
    assert isinstance(result.exception, _Taken), result.output
    (options,) = taken
    return options


@pytest.fixture
def mcp_server() -> object:
    """Build the MCP server of the REST API, which the tools call in process.

    One for each test: its client is bound to the event loop of the call that first used it.
    """
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    return build_mcp_server(restapi.app)


def _mcp(monkeypatch: pytest.MonkeyPatch, server: object, tool: str, params: dict[str, str]) -> Options:
    """Call an MCP tool up to the REST API's fetch, and return the options it would fetch with."""
    from fastmcp import Client  # noqa: PLC0415

    taken = _take(monkeypatch, _GETTER[tool])
    # the REST API answers the stopped fetch with a 500, which the tool reports as its own error
    arguments = {**_REST_BASE[tool], **params}

    async def call() -> None:
        async with Client(server) as client:
            await client.call_tool(tool, arguments, raise_on_error=False)

    asyncio.run(call())
    (options,) = taken
    return options


def _rest_cases() -> list[Any]:
    return [pytest.param(case, endpoint, id=f"{case.option}-{endpoint}") for case in CASES for endpoint in case.rest]


def _cli_cases() -> list[Any]:
    return [pytest.param(case, command, id=f"{case.option}-{command}") for case in CASES for command in case.cli]


def _env_cases() -> list[Any]:
    return [
        pytest.param(case, endpoint, id=f"{case.option}-{endpoint}") for case in CASES for endpoint in case.endpoints
    ]


@pytest.mark.parametrize(("case", "endpoint"), _rest_cases())
def test_rest_query_parameter_sets_the_option_as_the_setting(
    monkeypatch: pytest.MonkeyPatch, case: Case, endpoint: str
) -> None:
    """Test a query parameter of a data endpoint gives the request the options the setting did."""
    options = _rest(monkeypatch, endpoint, case.rest[endpoint])
    assert _is_set(options, case)
    assert options.model_dump() == _before(case).model_dump()


@pytest.mark.parametrize(("case", "endpoint"), _env_cases())
def test_rest_environment_sets_the_option_as_the_setting(
    monkeypatch: pytest.MonkeyPatch, case: Case, endpoint: str
) -> None:
    """Test the server's WD_TS_* variable gives a request that leaves the option out the options the setting did."""
    monkeypatch.setenv(case.variable, case.env)
    options = _rest(monkeypatch, endpoint, {})
    assert _is_set(options, case)
    assert options.model_dump() == _before(case).model_dump()


@pytest.mark.parametrize(("case", "command"), _cli_cases())
def test_cli_option_sets_the_option_as_the_setting(monkeypatch: pytest.MonkeyPatch, case: Case, command: str) -> None:
    """Test a command line option gives the request the options the setting did."""
    options = _cli(monkeypatch, command, case.cli[command])
    assert _is_set(options, case)
    assert options.model_dump() == _before(case).model_dump()


@pytest.mark.parametrize(("case", "command"), _env_cases())
def test_cli_environment_sets_the_option_as_the_setting(
    monkeypatch: pytest.MonkeyPatch, case: Case, command: str
) -> None:
    """Test the WD_TS_* variable gives a command that leaves the option out the options the setting did."""
    monkeypatch.setenv(case.variable, case.env)
    options = _cli(monkeypatch, command, [])
    assert _is_set(options, case)
    assert options.model_dump() == _before(case).model_dump()


@pytest.mark.parametrize(("case", "endpoint"), _rest_cases())
def test_mcp_tool_argument_sets_the_option_as_the_setting(
    monkeypatch: pytest.MonkeyPatch, mcp_server: object, case: Case, endpoint: str
) -> None:
    """Test an argument of an MCP tool gives the request the options the setting did."""
    options = _mcp(monkeypatch, mcp_server, endpoint, case.rest[endpoint])
    assert _is_set(options, case)
    assert options.model_dump() == _before(case).model_dump()


@pytest.mark.parametrize(("case", "endpoint"), _env_cases())
def test_mcp_environment_sets_the_option_as_the_setting(
    monkeypatch: pytest.MonkeyPatch, mcp_server: object, case: Case, endpoint: str
) -> None:
    """Test the WD_TS_* variable gives an MCP tool that leaves the option out the options the setting did."""
    monkeypatch.setenv(case.variable, case.env)
    options = _mcp(monkeypatch, mcp_server, endpoint, {})
    assert _is_set(options, case)
    assert options.model_dump() == _before(case).model_dump()


def test_an_argument_outranks_the_environment_and_a_dict_is_merged_into_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test what the surfaces document of the environment: a value replaces it, a dict is merged into it.

    The unit targets the environment sets gain the entry the request gives, which wins where both name a
    quantity; the shape the request gives replaces the environment's, whatever that is.
    """
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", json.dumps({"temperature": "degree_fahrenheit", "speed": "knots"}))
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    given = {"unit_targets": json.dumps({"temperature": "degree_kelvin"}), "shape": "long"}
    options = _rest(monkeypatch, "values", given)
    assert options.unit_targets == {"temperature": "degree_kelvin", "speed": "knots"}
    assert options.shape == "long"
    cli_options = _cli(monkeypatch, "values", [f"--unit_targets={given['unit_targets']}", "--shape=long"])
    assert cli_options.model_dump() == options.model_dump()


def _getter_options(getter: Callable[..., object], monkeypatch: pytest.MonkeyPatch, request: object) -> Options:
    """Run a getter of `ui.core` to the request it builds, and return the options that request is built with."""
    from wetterdienst.ui import core  # noqa: PLC0415

    built: list[dict[str, object]] = []

    def stations_request(**kwargs: object) -> object:
        built.append(kwargs)
        raise _Taken

    monkeypatch.setattr(core, "_get_stations_request", stations_request)
    with pytest.raises(_Taken):
        getter(api=None, request=request, settings=Settings(), options=Options(humanize=False))
    (kwargs,) = built
    return kwargs["options"]  # ty: ignore[invalid-return-type]


@pytest.mark.parametrize("getter", ["get_values", "get_interpolate", "get_summarize"])
def test_the_getters_pass_their_options_to_the_request(monkeypatch: pytest.MonkeyPatch, getter: str) -> None:
    """Test each getter of the values hands the options it is given on, and does not read them out of the settings."""
    from wetterdienst.ui import core  # noqa: PLC0415

    model = {"get_values": core.ValuesRequest, "get_interpolate": core.InterpolationRequest}.get(
        getter, core.SummaryRequest
    )
    request = model.model_validate({**_REST_BASE[getter.removeprefix("get_")]})
    options = _getter_options(getattr(core, getter), monkeypatch, request)
    assert options.humanize is False


def test_a_request_is_built_with_the_options_given() -> None:
    """Test the request built for a getter carries the options, which the host's settings no longer do."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415
    from wetterdienst.ui import core  # noqa: PLC0415

    request = core.ValuesRequest.model_validate(_REST_BASE["values"])
    built = core._get_stations_request(  # noqa: SLF001
        api=DwdObservationRequest,
        request=request,
        timestamp=None,
        settings=Settings(),
        options=Options(humanize=False, shape="wide"),
    )
    assert (built.options.humanize, built.options.shape) == (False, "wide")


def test_the_stripes_read_the_values_long_and_whole_whatever_the_environment_sets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the stripes' requests are built with a long shape and no skipping of stations (GH-2348).

    They take the `value` column of a long frame and draw the gaps themselves. A malformed variable for
    either is not read, as their arguments outrank it.
    """
    from wetterdienst.ui import core  # noqa: PLC0415

    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    monkeypatch.setenv("WD_TS_SKIP_EMPTY", "true")
    monkeypatch.setenv("WD_TS_HUMANIZE", "false")
    for request in (core._get_stripes_temperature_request(), core._get_stripes_precipitation_request()):  # noqa: SLF001
        assert (request.options.shape, request.options.skip_empty) == ("long", False)
        # what is not replaced is the environment's
        assert request.options.humanize is False


def test_the_glossary_reports_the_units_of_the_options_given() -> None:
    """Test the glossary names the unit a values request with these options returns."""
    from wetterdienst.ui.core import get_glossary  # noqa: PLC0415

    entries = get_glossary(parameter="temperature_air_mean_2m", options=Options(unit_targets=_FAHRENHEIT))
    assert {entry["unit"] for entry in entries if entry["unit_type"] == "temperature"} == {"degree_fahrenheit"}


def test_the_glossary_reads_the_environments_options_when_given_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a glossary asked without options reports the unit the server's WD_TS_UNIT_TARGETS sets."""
    from wetterdienst.ui.core import get_glossary  # noqa: PLC0415

    monkeypatch.setenv("WD_TS_UNIT_TARGETS", json.dumps(_FAHRENHEIT))
    entries = get_glossary(parameter="temperature_air_mean_2m")
    assert {entry["unit"] for entry in entries if entry["unit_type"] == "temperature"} == {"degree_fahrenheit"}
