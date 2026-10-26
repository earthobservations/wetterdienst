# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the MCP instructions tell a model about forecasts and where a network reaches (GH-3456).

A model asked for the forecast for Los Angeles refused it: `dwd/mosmix` is a German provider's, it took it for a
forecast for Germany. Nothing in the tools said that the station lists of `dwd/mosmix` and `dwd/dmo` are worldwide,
and that the `country` of a provider is its operator's. The instructions now say so; these tests hold the words to
the facts they state:

- the text names the forecast workflow, the global networks and what `country` means, by key phrases and not by the
  exact wording, which is improved without a new version,
- the example call of the forecast workflow is a call the tools take, and gives Los Angeles (`72295`) for it, against
  stubs of the two catalogues,
- the stubs of the catalogues hold a station on each continent and the reader returns each of them where it is, and
- the live lists do (remote), which is what the claim `worldwide` stands on.
"""

from __future__ import annotations

import ast
import asyncio
import re
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.provider.station_catalogue_stubs import _serve, _stations
from wetterdienst.model.quality_flags import raw_column
from wetterdienst.provider.dwd import catalogue as dwd_catalogue
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.dmo import api as dmo_api
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.mosmix import api as mosmix_api
from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import INSTRUCTIONS
from wetterdienst.ui.providers import Provider

if TYPE_CHECKING:
    from collections.abc import Callable


# a station of each continent that both lists hold, as the live lists of 2026-10-26 give them: id, ICAO, name,
# latitude, longitude, elevation (the same position in `dwd/mosmix` and `dwd/dmo`)
CONTINENTS: dict[str, tuple[str, str, str, float, float, int]] = {
    "North America": ("72295", "KLAX", "LOS ANGELES", 33.93, -118.4, 38),
    "South America": ("87576", "SAEZ", "BUENOS AIRES AERO", -34.82, -58.53, 20),
    "Africa": ("63740", "HKJK", "NAIROBI", -1.32, 36.92, 1624),
    "Asia": ("47662", "RJTD", "TOKYO NARITA", 35.68, 139.77, 5),
    "Oceania": ("94767", "YSSY", "SYDNEY AIRPORT", -33.95, 151.18, 6),
}
# ... and one of Europe, which no one doubts, so that the stub is not only the far continents
EUROPE = ("10147", "EDDH", "HAMBURG-FU.", 53.63, 10.0, 16)

LOS_ANGELES = CONTINENTS["North America"]

# how far a position read from the degrees and minutes of a list is from the decimal degrees it was written from: the
# list rounds to a whole minute (1/60 of a degree), the live frame to two decimals
POSITION_TOLERANCE = 0.02


def _degrees_minutes(value: float) -> str:
    """Write decimal degrees as the lists do: whole degrees, a point and the minutes in two digits (`33.56`)."""
    degrees, minutes = divmod(round(abs(value) * 60), 60)
    return f"{'-' if value < 0 else ''}{degrees}.{minutes:02d}"


def _catalogue(stations: list[tuple[str, str, str, float, float, int]], newline: str = "\n") -> bytes:
    """Write the stations as the station lists of DWD do: fixed columns, latitude and longitude in degrees.minutes."""
    lines = [
        "ID    ICAO NAME                 LAT    LON     ELEV",
        "----- ---- -------------------- -----  ------- -----",
    ]
    lines += [
        f"{station_id} {icao} {name:<20}{_degrees_minutes(latitude):>8}{_degrees_minutes(longitude):>8}{elevation:>10}"
        for station_id, icao, name, latitude, longitude, elevation in stations
    ]
    return (newline.join(lines) + newline).encode("latin-1")


STATIONS = [*CONTINENTS.values(), EUROPE]


def _serve_mosmix(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, dwd_catalogue, {"mosmix_stationskatalog": _catalogue(STATIONS)})


def _serve_dmo(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, dmo_api, {"dmo_stationsliste_txt": _catalogue(STATIONS, "\r\n")})
    directories = [{"name": f"single_stations/{station[0]}/"} for station in STATIONS]
    monkeypatch.setattr(dmo_api, "list_remote_directory_fsspec", lambda *_args, **_kwargs: directories)


def _text(*phrases: str) -> Callable[[str], bool]:
    """Say whether a text holds every phrase, in any case and whatever the white space."""

    def holds(text: str) -> bool:
        flat = " ".join(text.lower().split())
        return all(phrase.lower() in flat for phrase in phrases)

    return holds


# --- the words ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("what", "holds"),
    [
        pytest.param(
            "a forecast workflow", _text("forecast for <place>", "dwd", "mosmix", "hourly/large"), id="workflow"
        ),
        pytest.param("a point for the stations", _text("latitude=", "longitude=", "rank="), id="point"),
        pytest.param("mosmix and dmo as worldwide", _text("dwd/mosmix", "dwd/dmo", "every continent"), id="global"),
        pytest.param("the other networks of the family", _text("icon_eu", "europe", "dwd/swsmos"), id="not-global"),
        pytest.param("observations as national", _text("dwd/observation", "germany only"), id="observation"),
        pytest.param("a global observation network", _text("noaa/ghcn", "global"), id="ghcn"),
        pytest.param(
            "country as the operator's", _text("`country`", "agency that runs", "not the extent"), id="country"
        ),
        pytest.param("the kind to decide by", _text("`kind`", "observation", "forecast"), id="kind"),
        pytest.param("a refusal as wrong", _text("no reason to refuse"), id="refusal"),
    ],
)
def test_the_instructions_say(what: str, holds: Callable[[str], bool]) -> None:
    """The instructions carry what a model needs to take a German provider's forecast for a world one."""
    assert holds(INSTRUCTIONS), f"the instructions no longer say {what}"


def test_the_instructions_stay_compact() -> None:
    """They are read on every connection: the forecast workflow and the table of networks fit in what they cost."""
    assert len(INSTRUCTIONS) < 8500


def test_the_country_of_a_provider_is_described_as_the_operators() -> None:
    """The schema, which the REST docs and the MCP tool schemas of `providers` come from, says what `country` is."""
    properties = Provider.model_json_schema()["properties"]
    assert _text("agency that runs", "not the extent of its data", "worldwide")(properties["country"]["description"])
    assert _text("operator's", "not the extent of its data")(properties["country_code"]["description"])


def test_the_providers_tool_says_what_its_country_is() -> None:
    """The tool a model asks "which providers cover this country" is described with the operator's country."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def describe() -> str:
        async with Client(build_mcp_server(restapi.app)) as client:
            return next(tool.description or "" for tool in await client.list_tools() if tool.name == "providers")

    description = asyncio.run(describe())

    assert _text("country of the agency that runs it", "not the extent of its data", "worldwide")(description)


# --- the example call --------------------------------------------------------------------------------------------


def _example_arguments(tool: str) -> dict[str, Any]:
    """Read the arguments of the example call of a forecast tool in the instructions, as the model would write them."""
    section = INSTRUCTIONS.partition("## Typical workflow: weather forecast for a place")[2].partition("\n## ")[0]
    calls = re.findall(rf"^\s+{tool}\((.*)\)\s*$", section, flags=re.MULTILINE)
    assert len(calls) == 1, f"the forecast workflow has no single example of {tool}"
    call = ast.parse(f"{tool}({calls[0]})", mode="eval").body
    assert isinstance(call, ast.Call)
    return {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords if keyword.arg}


def _call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> dict[str, Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            content = (await client.call_tool(tool, arguments)).structured_content or {}
            # a tool whose answer is no object model has it under `result`
            return content.get("result", content)

    return asyncio.run(call())


def test_the_example_finds_los_angeles_by_its_coordinates(monkeypatch: pytest.MonkeyPatch) -> None:
    """`stations` of the example, as written, answers the nearest station to Los Angeles with `72295`."""
    _serve_mosmix(monkeypatch)
    arguments = _example_arguments("stations")

    answer = _call("stations", arguments)

    assert (arguments["provider"], arguments["network"]) == ("dwd", "mosmix")
    ids = [station["station_id"] for station in answer["stations"]]
    assert ids[0] == LOS_ANGELES[0]
    assert ids[0] in INSTRUCTIONS, "the instructions name the station the example finds"


def test_the_example_values_call_takes_that_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """`values` of the example, as written, gives the forecast of the station the first call found."""
    _serve_mosmix(monkeypatch)
    stations_arguments, arguments = _example_arguments("stations"), _example_arguments("values")
    assert arguments["stations"] == _call("stations", stations_arguments)["stations"][0]["station_id"]

    # the run: the files of DWD are not read, the forecast is two hours of what the file holds for a station
    url = "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/72295/kml/MOSMIX_L_2026102603_72295.kmz"
    monkeypatch.setattr(mosmix_api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [url])
    monkeypatch.setattr(mosmix_api.KMLReader, "read", lambda _self, _url: None)
    # the frame `KMLReader.get_station_forecast` builds: the stamps as the file writes them, and a column of the
    # file's own text beside each parameter
    stamps = ["2026-10-26T03:00:00.000Z", "2026-10-26T04:00:00.000Z"]
    forecast = pl.DataFrame({"timestamp": stamps, "ttt": [290.15, 291.15]}).with_columns(
        pl.lit(None, dtype=pl.String).alias(raw_column("ttt"))
    )
    monkeypatch.setattr(mosmix_api.KMLReader, "get_station_forecast", lambda _self, _station_id: forecast)

    answer = _call("values", arguments)

    assert [item["parameter"] for item in answer["values"]] == ["temperature_air_2m"] * 2
    # the file holds Kelvin, the answer degrees Celsius
    assert [round(item["value"], 2) for item in answer["values"]] == [17.0, 18.0]
    assert {item["station_id"] for item in answer["values"]} == {LOS_ANGELES[0]}


# --- the claim: the lists are worldwide --------------------------------------------------------------------------


def _held(frame: pl.DataFrame) -> dict[str, tuple[str, float, float]]:
    return {row["station_id"]: (row["name"], row["latitude"], row["longitude"]) for row in frame.to_dicts()}


@pytest.mark.parametrize(
    ("network", "serve", "request_class", "parameter"),
    [
        pytest.param("dwd/mosmix", _serve_mosmix, DwdMosmixRequest, ("hourly", "large"), id="mosmix"),
        pytest.param("dwd/dmo", _serve_dmo, DwdDmoRequest, ("hourly", "icon"), id="dmo"),
    ],
)
def test_the_stub_of_a_forecast_network_has_a_station_on_each_continent(
    network: str,
    serve: Callable[[pytest.MonkeyPatch], None],
    request_class: type,
    parameter: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reader gives each station of the stub, one for each continent, at the position the list writes for it.

    This holds the reader and the instructions' claim to the same rows; that the live list is as worldwide as the
    stub says is `test_the_live_lists_have_a_station_on_each_continent`.
    """
    serve(monkeypatch)

    held = _held(_stations(request_class, parameter))

    for continent, (station_id, _icao, _name, latitude, longitude, _elevation) in CONTINENTS.items():
        assert station_id in held, f"{network} has no station of {continent}"
        _, read_latitude, read_longitude = held[station_id]
        assert abs(read_latitude - latitude) < POSITION_TOLERANCE, (network, continent)
        assert abs(read_longitude - longitude) < POSITION_TOLERANCE, (network, continent)
    # five continents, the Americas apart by hemisphere: the positions are not all in one box
    assert {lat > 0 for _, lat, _ in held.values()} == {True, False}
    assert {lon > 0 for _, _, lon in held.values()} == {True, False}


@pytest.mark.remote
@pytest.mark.parametrize(
    ("network", "request_class", "parameter"),
    [
        pytest.param("dwd/mosmix", DwdMosmixRequest, ("hourly", "large"), id="mosmix"),
        pytest.param("dwd/dmo", DwdDmoRequest, ("hourly", "icon"), id="dmo"),
    ],
)
def test_the_live_lists_have_a_station_on_each_continent(
    network: str, request_class: type, parameter: tuple[str, str]
) -> None:
    """The station list of `dwd/mosmix` and of `dwd/dmo` (`icon`) holds a station of each continent where it is.

    The instructions say "stations on every continent"; this is what that stands on. A list DWD restricts to Europe
    is a change of the instructions, and not of this test.
    """
    from wetterdienst import Settings  # noqa: PLC0415

    frame = request_class(parameters=[parameter], settings=Settings(cache_disable=True)).all().df

    held = _held(frame)
    for continent, (station_id, _icao, _name, latitude, longitude, _elevation) in CONTINENTS.items():
        assert station_id in held, f"{network} has no station of {continent}"
        _, read_latitude, read_longitude = held[station_id]
        assert abs(read_latitude - latitude) < POSITION_TOLERANCE, (network, continent)
        assert abs(read_longitude - longitude) < POSITION_TOLERANCE, (network, continent)


@pytest.mark.remote
def test_the_live_dmo_icon_eu_list_is_europe() -> None:
    """The instructions say the `icon_eu` dataset of `dwd/dmo` is Europe, and that is why they name `icon`."""
    from wetterdienst import Settings  # noqa: PLC0415

    frame = DwdDmoRequest(parameters=[("hourly", "icon_eu")], settings=Settings(cache_disable=True)).all().df

    assert frame["latitude"].min() > 0
    assert frame["latitude"].max() < 80
    assert frame["longitude"].min() > -30
    assert frame["longitude"].max() < 60
