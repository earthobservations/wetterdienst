# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `metadata` block every JSON answer of the data routes carries, and the headers of the rest (GH-2561).

Offline: the results are the stubs of the REST tests, so the whole of the answer is rendered by the
routes and nothing but the readers is stood in for.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.conftest import RESPONSE_METADATA_ALWAYS
from tests.ui.cli.test_cli_history import _stations_without_histories
from tests.ui.test_restapi import _OBSERVATION, _station_of, _stub_result, _values_result_of_shape
from wetterdienst import Options, Wetterdienst
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.response_metadata import (
    API_VERSION,
    MAX_LISTED_STATION_IDS,
    SCHEMA_VERSION,
    response_metadata,
)
from wetterdienst.util.response_warnings import begin_response, recorded_warnings, warn_response

if TYPE_CHECKING:
    import pathlib

LOG = logging.getLogger(__name__)
#: the members of the block that every answer has, whatever was asked for
ALWAYS = RESPONSE_METADATA_ALWAYS
ENDPOINTS = ["/api/values", "/api/interpolate", "/api/summarize"]


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    begin_response()
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def client() -> TestClient:
    """Make a client of the app."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _params(endpoint: str, **extra: str) -> dict[str, str]:
    params = {**_OBSERVATION, _station_of(endpoint): "01048", **extra}
    if endpoint != "/api/values":
        params["timestamp"] = "2026-01-01"
    return params


# --- the block ------------------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("fmt", ["json", "geojson"])
def test_every_json_answer_has_the_block(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, fmt: str
) -> None:
    """The block is there without `with_metadata`, with what the answer is of and where it comes from."""
    _stub_result(monkeypatch, endpoint)

    response = client.get(endpoint, params=_params(endpoint, format=fmt))

    assert response.status_code == 200, response.text
    metadata = response.json()["metadata"]
    assert set(metadata) == ALWAYS
    assert (metadata["api_version"], metadata["schema_version"]) == (API_VERSION, SCHEMA_VERSION)
    assert metadata["retrieved_at"].endswith("+00:00")
    assert metadata["provider"]["license"] == {
        "spdx_id": "CC-BY-4.0",
        "name": "Creative Commons Attribution 4.0 International",
        "url": "https://creativecommons.org/licenses/by/4.0/",
    }
    assert metadata["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert metadata["crs"] == {
        "code": "EPSG:4326",
        "name": "WGS 84",
        "axis_order": "longitude, latitude",
        "elevation": "metres above mean sea level",
    }
    assert metadata["warnings"] == []


def test_the_request_is_told_as_it_was_resolved(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """`daily/climate_summary` is the list of parameters it means, and the stations are the ones selected."""
    _stub_result(monkeypatch, "/api/values")

    metadata = client.get("/api/values", params=_params("/api/values")).json()["metadata"]

    request = metadata["request"]
    assert (request["provider"], request["network"]) == ("dwd", "observation")
    assert "daily/climate_summary/temperature_air_mean_2m" in request["parameters"]
    assert len(request["parameters"]) > 1
    assert request["periods"] == ["historical", "recent"]
    assert (request["start"], request["end"]) == (None, None)
    assert request["stations"] == {"filter": "all", "count": 1, "ids": ["01048"]}
    assert metadata["counts"] == {"stations": 1, "rows": 2}


@pytest.mark.parametrize(
    ("stations", "listed"),
    [(MAX_LISTED_STATION_IDS, True), (MAX_LISTED_STATION_IDS + 1, False)],
    ids=["at-the-limit", "past-the-limit"],
)
def test_the_station_ids_are_listed_up_to_a_limit_and_counted_beyond_it(*, stations: int, listed: bool) -> None:
    """An answer of many stations says how many, not which: `ids` is null past `MAX_LISTED_STATION_IDS` (GH-3061)."""
    result = _values_result_of_shape("long").stations
    ids = [f"{number:05d}" for number in range(stations)]
    result = replace(result, df=pl.DataFrame({"station_id": ids}))

    block = response_metadata(result, SimpleNamespace(provider="dwd", network="observation", with_metadata=False))

    assert block.request.stations.count == stations
    assert block.request.stations.ids == (ids if listed else None)
    assert block.counts.stations == stations


def test_the_heavy_parts_are_with_metadata_alone(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """`with_metadata` adds the unit of every parameter and what `quality_flags` holds, and the settings."""
    _stub_result(monkeypatch, "/api/values")

    light = client.get("/api/values", params=_params("/api/values")).json()
    heavy = client.get("/api/values", params=_params("/api/values", with_metadata="true")).json()

    assert set(light["metadata"]) == ALWAYS
    assert set(heavy["metadata"]) == ALWAYS | {"parameters", "quality"}
    assert "settings" not in light
    assert "settings" in heavy
    temperature = next(p for p in heavy["metadata"]["parameters"] if p["name"] == "temperature_air_mean_2m")
    assert temperature["quantity"] == "temperature"
    assert temperature["unit"] == "°C"
    assert temperature["name_original"] == "tmk"
    assert heavy["metadata"]["quality"]["column"] == "quality_flags"
    assert {flag["name_original"] for flag in heavy["metadata"]["quality"]["source_flags"]} >= {"qn_3", "qn_4"}
    # the rest of the block is the same
    assert {k: v for k, v in heavy["metadata"].items() if k in ALWAYS - {"retrieved_at"}} == {
        k: v for k, v in light["metadata"].items() if k != "retrieved_at"
    }


@pytest.mark.parametrize(("convert_units", "unit"), [(True, "s"), (False, "h")])
def test_the_unit_is_the_sources_where_nothing_is_converted(*, convert_units: bool, unit: str) -> None:
    """The unit named is the target of the quantity, or, with `convert_units` off, the one the source publishes."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "sunshine_duration")], options=Options(convert_units=convert_units)
    )
    stations = replace(_values_result_of_shape("long").stations, request=request)

    metadata = response_metadata(stations, SimpleNamespace(provider="dwd", network="observation", with_metadata=True))

    assert [(p.name, p.unit) for p in metadata.parameters or []] == [("sunshine_duration", unit)]


def test_a_stations_answer_has_the_block(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The listing says how the stations were selected and how many there are."""
    stations = _values_result_of_shape("long").stations
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)

    response = client.get("/api/stations", params={**_OBSERVATION, "stations": "01048"})

    assert response.status_code == 200, response.text
    metadata = response.json()["metadata"]
    assert set(metadata) == ALWAYS
    assert metadata["request"]["stations"] == {"filter": "all", "count": 1, "ids": ["01048"]}
    assert metadata["counts"] == {"stations": 1, "rows": 2}


def test_a_history_answer_has_the_block(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The history of a station is an answer of the data routes too."""
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: _stations_without_histories())

    response = client.get("/api/history", params={**_OBSERVATION, "stations": "02564"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert list(body) == ["metadata", "histories"]
    assert body["metadata"]["counts"] == {"stations": 1, "rows": 0}
    assert body["metadata"]["provider"]["license"]["spdx_id"] == "CC-BY-4.0"


# --- the routes that answered without it (GH-3059) ---------------------------------------------------

_SWSMOS_RUN = "swsmos_20261004060000_opendata.csv.bz2"


def _swsmos_lists_one_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for DWD's directory of SWSMOS runs."""
    from wetterdienst.provider.dwd.swsmos import api  # noqa: PLC0415

    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{api._BASE_URL}/{_SWSMOS_RUN}"])  # noqa: SLF001


def _no_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for a DWD snapshot that holds no warning."""
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.alerts.api import _SCHEMA, DwdWeatherAlertResult  # noqa: PLC0415
    from wetterdienst.provider.dwd.alerts.metadata import (  # noqa: PLC0415
        DwdWeatherAlertGranularity,
        DwdWeatherAlertLanguage,
    )

    result = DwdWeatherAlertResult(
        pl.DataFrame(schema=_SCHEMA), DwdWeatherAlertGranularity.COMMUNITY, DwdWeatherAlertLanguage.ENGLISH
    )
    monkeypatch.setattr(DwdWeatherAlertRequest, "query", lambda _self: result)


def test_the_issues_have_the_block(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The runs of a forecast are about one station of a network, whose terms the answer names."""
    _swsmos_lists_one_run(monkeypatch)

    response = client.get("/api/issues", params={"provider": "dwd", "network": "swsmos", "station": "A006"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert list(body) == ["metadata", "issues"]
    metadata = body["metadata"]
    assert set(metadata) == ALWAYS
    assert metadata["request"] == {
        "provider": "dwd",
        "network": "swsmos",
        "parameters": [],
        "periods": [],
        "start": None,
        "end": None,
        "stations": {"filter": "by_station_id", "count": 1, "ids": ["A006"]},
    }
    assert metadata["counts"] == {"stations": 1, "rows": 1}
    assert metadata["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert metadata["provider"]["copyright"].endswith("SWSMOS road weather forecast")
    assert response.headers["X-Wetterdienst-License"] == "CC-BY-4.0"


def test_the_issues_on_the_command_line_are_the_ones_of_rest(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same request gives the same answer on both surfaces, but for the time it was made at."""
    _swsmos_lists_one_run(monkeypatch)
    given = {"provider": "dwd", "network": "swsmos", "station": "A006"}

    rest = client.get("/api/issues", params=given).json()
    result = CliRunner().invoke(cli, ["issues", *(f"--{key}={value}" for key, value in given.items())])

    assert result.exit_code == 0, result.output
    command_line = json.loads(result.stdout)
    for answer in (rest, command_line):
        answer["metadata"]["retrieved_at"] = ""
    assert command_line == rest


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
def test_the_alerts_have_the_block(client: TestClient, monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """A warning is about no station: its block says so, names DWD's terms, and a CSV answer has them in headers."""
    _no_alerts(monkeypatch)

    response = client.get("/api/alerts", params={"format": fmt})

    assert response.status_code == 200, response.text
    assert response.headers["X-Wetterdienst-License"] == "CC-BY-4.0"
    assert response.headers["X-Wetterdienst-Rows"] == "0"
    if fmt == "csv":
        return
    body = response.json()
    metadata = body["metadata"]
    assert set(metadata) == ALWAYS
    assert metadata["request"]["stations"] is None
    assert (metadata["request"]["provider"], metadata["request"]["network"]) == ("dwd", "alerts")
    assert metadata["counts"] == {"stations": 0, "rows": 0}
    assert metadata["provider"]["url"] == "https://opendata.dwd.de/weather/alerts/cap"
    assert metadata["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    if fmt == "geojson":
        # a foreign member of the collection (RFC 7946 6.1), the type first
        assert list(body) == ["type", "metadata", "snapshot", "features"]
    else:
        assert list(body) == ["metadata", "snapshot", "alerts"]


def test_the_alerts_on_the_command_line_are_the_ones_of_rest(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command line writes the block into the JSON as REST does."""
    _no_alerts(monkeypatch)

    rest = client.get("/api/alerts").json()
    result = CliRunner().invoke(cli, ["alerts"])

    assert result.exit_code == 0, result.output
    command_line = json.loads(result.stdout)
    for answer in (rest, command_line):
        answer["metadata"]["retrieved_at"] = ""
    assert command_line == rest


@pytest.mark.usefixtures("_no_ambient_settings")
def test_the_stripes_stations_have_the_block(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The listing has the block of every answer, which holds what its old `{provider, producer}` did."""
    from tests.ui.test_restapi import _stub_stripes_station  # noqa: PLC0415

    _stub_stripes_station(monkeypatch, "temperature", [1.0, 2.0])

    response = client.get("/api/stripes/stations", params={"kind": "temperature", "active": "false"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert list(body) == ["metadata", "stations"]
    assert set(body["metadata"]) == ALWAYS
    assert body["metadata"]["counts"] == {"stations": 1, "rows": 1}
    assert body["metadata"]["provider"]["name_english"] == "German Weather Service"
    assert body["metadata"]["producer"]["name"] == "wetterdienst"
    assert response.headers["X-Wetterdienst-Stations"] == "1"


@pytest.mark.usefixtures("_no_ambient_settings")
def test_the_stripes_values_have_the_block_and_a_series_for_what_they_are_of(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`station`, `resolution`, `dataset`, `parameter` and `unit` are the `series`, and the `metadata` is the block."""
    from tests.ui.test_restapi import _stub_stripes_station  # noqa: PLC0415

    _stub_stripes_station(monkeypatch, "temperature", [1.0, 2.0])

    response = client.get("/api/stripes/values", params={"kind": "temperature", "station": "01048"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"metadata", "series", "values"}
    metadata = body["metadata"]
    assert set(metadata) == ALWAYS
    assert set(body["series"]) == {"station", "resolution", "dataset", "parameter", "unit"}
    assert body["series"]["unit"] == "degree_celsius"
    assert body["series"]["station"]["station_id"] == "01048"
    assert metadata["request"]["parameters"] == ["annual/climate_summary/temperature_air_mean_2m"]
    assert metadata["request"]["stations"] == {"filter": "by_station_id", "count": 1, "ids": ["01048"]}
    assert metadata["counts"] == {"stations": 1, "rows": 2}
    assert response.headers["X-Wetterdienst-License"] == "CC-BY-4.0"


@pytest.mark.parametrize(
    "path",
    ["/history", "/issues", "/alerts", "/stripes/stations", "/stripes/values"],
)
def test_the_openapi_document_describes_the_answer_of_each_route_with_the_block(client: TestClient, path: str) -> None:
    """The document says what each of these answers, the block included, which MCP checks a tool's answer against."""
    document = client.get("/openapi.json").json()
    schema = document["paths"][f"/api/v1{path}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    def refs(node: Any) -> set[str]:  # noqa: ANN401
        if isinstance(node, dict):
            found = {node["$ref"].rsplit("/", 1)[-1]} if "$ref" in node else set()
            return found.union(*(refs(value) for value in node.values()))
        if isinstance(node, list):
            return set().union(*(refs(value) for value in node))
        return set()

    schemas = document["components"]["schemas"]
    # follow the references one level: the answer's own models name `ResponseMetadata` in their members
    named = refs(schema)
    named |= set().union(*(refs(schemas[name]) for name in list(named)))
    assert "ResponseMetadata" in named, schema


def test_a_history_answer_is_what_its_model_describes(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The answer reads back through the model the document describes it by."""
    from pydantic import TypeAdapter  # noqa: PLC0415

    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: _stations_without_histories())

    response = client.get("/api/history", params={**_OBSERVATION, "stations": "02564"})

    assert response.status_code == 200, response.text
    TypeAdapter(restapi._HistoryWithMetadataDict).validate_python(response.json())  # noqa: SLF001


# --- the warnings -----------------------------------------------------------------------------


def test_a_warning_is_logged_and_recorded_for_the_request_being_served(caplog: pytest.LogCaptureFixture) -> None:
    """The line stays in the log, and the answer of the request carries it by its code."""
    begin_response()
    with caplog.at_level(logging.INFO):
        warn_response(LOG, "some-code", "something was left out", level=logging.INFO)
        warn_response(LOG, "some-code", "something was left out", level=logging.INFO)
        warn_response(LOG, "other-code", "something else")

    assert "something was left out" in caplog.text
    assert recorded_warnings() == [
        {"code": "some-code", "message": "something was left out"},
        {"code": "other-code", "message": "something else"},
    ]


def test_a_request_starts_without_the_warnings_of_the_one_before(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Warnings belong to the request that raised them."""
    _stub_result(monkeypatch, "/api/values")
    stations = _values_result_of_shape("long").stations

    def lookup(**_kwargs: object) -> object:
        warn_response(LOG, "left-out", "an id was left out")
        return stations

    # a stations request raises one; a values request after it must not carry it
    monkeypatch.setattr(restapi, "get_stations", lookup)
    listed = client.get("/api/stations", params={**_OBSERVATION, "stations": "01048"}).json()
    values = client.get("/api/values", params=_params("/api/values")).json()

    assert [warning["code"] for warning in listed["metadata"]["warnings"]] == ["left-out"]
    assert values["metadata"]["warnings"] == []


# --- the headers ------------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_a_csv_answer_carries_the_block_in_headers(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """A CSV has no place in its body for the licence and the credit line, so they are headers and a `Link`."""
    _stub_result(monkeypatch, endpoint)

    response = client.get(endpoint, params=_params(endpoint, format="csv"))

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    headers = response.headers
    assert headers["X-Wetterdienst-API-Version"] == API_VERSION
    assert headers["X-Wetterdienst-Schema-Version"] == SCHEMA_VERSION
    assert headers["X-Wetterdienst-Retrieved-At"].endswith("+00:00")
    assert headers["X-Wetterdienst-License"] == "CC-BY-4.0"
    assert unquote(headers["X-Wetterdienst-Attribution"]) == "Source: Deutscher Wetterdienst"
    assert unquote(headers["X-Wetterdienst-Provider"]) == "German Weather Service"
    assert headers["X-Wetterdienst-Stations"] == "1"
    # the csv of values is streamed, whose rows are not known as the headers go out
    assert headers.get("X-Wetterdienst-Rows") == (None if endpoint == "/api/values" else "1")
    assert headers["Link"] == '<https://creativecommons.org/licenses/by/4.0/>; rel="license"'
    assert "X-Wetterdienst-Warnings" not in headers


def test_the_headers_are_on_a_json_answer_too(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A proxy that reads no body knows what the answer says of its licence and warnings."""
    _stub_result(monkeypatch, "/api/values")

    response = client.get("/api/values", params=_params("/api/values"))

    assert response.headers["X-Wetterdienst-License"] == "CC-BY-4.0"
    assert response.headers["X-Wetterdienst-Retrieved-At"] == response.json()["metadata"]["retrieved_at"]


def test_a_text_beyond_ascii_in_a_header_is_percent_encoded() -> None:
    """A credit line may carry more than ASCII (Météo-France); a header can not, and a client unquotes it."""
    from wetterdienst.ui.response_metadata import response_headers  # noqa: PLC0415

    metadata = restapi.response_metadata(
        _values_result_of_shape("long").stations, restapi.ValuesRequest(**_OBSERVATION, stations="01048")
    )
    metadata.provider["attribution"] = "© Météo-France"

    attribution = response_headers(metadata)["X-Wetterdienst-Attribution"]

    assert attribution.isascii()
    assert unquote(attribution) == "© Météo-France"


# --- the command line -------------------------------------------------------------------------


def test_the_command_line_prints_the_block_without_with_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """The block is on stdout whether or not `--with-metadata` is on; the heavy parts are with it."""
    from wetterdienst.ui import cli as cli_module  # noqa: PLC0415

    _stub_result(monkeypatch, "/api/values")
    monkeypatch.setattr(cli_module, "get_values", restapi.get_values)

    def run(*flags: str) -> dict[str, Any]:
        result = CliRunner().invoke(
            cli, ["values", *(f"--{k}={v}" for k, v in {**_OBSERVATION, "stations": "01048"}.items()), *flags]
        )
        assert result.exit_code == 0, result.output
        return json.loads(result.stdout)

    light, heavy = run(), run("--with-metadata")

    assert set(light["metadata"]) == ALWAYS
    assert set(heavy["metadata"]) == ALWAYS | {"parameters", "quality"}
    assert "settings" in heavy
    assert "settings" not in light


# --- the licence of every provider ------------------------------------------------------------

#: the networks whose provider states no terms of use anywhere this could be read, with where it was looked. A new
#: provider declares its licence, or is named here with the reason (`"license": None` in its metadata). None is,
#: since CHMI, IMGW, IPMA and NOAA GHCN were read against their own pages and catalogues (GH-3061).
LICENSE_NOT_STATED: dict[tuple[str, str], str] = {}

#: the licence of the providers whose terms are not a standard one or were read from a catalogue, as they state it
STATED_LICENCES = {
    ("chmi", "observation"): "CC-BY-4.0",
    ("dmi", "observation"): "CC-BY-4.0",
    ("noaa", "ghcn"): "CC0-1.0",
    ("imgw", "meteorology"): None,
    ("imgw", "hydrology"): None,
    ("ipma", "observation"): None,
}


@pytest.mark.parametrize(("network", "spdx_id"), list(STATED_LICENCES.items()))
def test_the_licence_a_provider_states_is_the_one_declared(network: tuple[str, str], spdx_id: str | None) -> None:
    """IMGW and IPMA state terms of their own, which no SPDX identifier names: they say so by `spdx_id` null."""
    metadata = Wetterdienst.resolve(*network).metadata

    assert metadata.license is not None
    assert metadata.license.spdx_id == spdx_id
    assert metadata.attribution


def test_imgw_asks_for_its_own_words() -> None:
    """§ 5 ust. 3 and 4 of IMGW-PIB's terms prescribe two statements, in Polish, carried as written."""
    source = "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy"  # noqa: RUF001 -- the dash the terms write
    processed = (
        "Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego zostały przetworzone"  # noqa: RUF001
    )

    for network in ("meteorology", "hydrology"):
        attribution = Wetterdienst.resolve("imgw", network).metadata.attribution

        assert attribution == f"{source}. {processed}."


def test_imgw_licence_points_at_its_terms() -> None:
    """The licence URL is the PDF of the terms, not the portal they are offered on."""
    for network in ("meteorology", "hydrology"):
        license_ = Wetterdienst.resolve("imgw", network).metadata.license

        assert license_ is not None
        assert license_.url == "https://danepubliczne.imgw.pl/docs/regulamin_udostepniania_danych.pdf"


def _timeseries_networks() -> list[tuple[str, str]]:
    return [
        (provider, network)
        for provider, networks in Wetterdienst.discover().items()
        for network, listed in networks.items()
        if listed["kind"] in {"observation", "forecast", "derived"}
    ]


@pytest.mark.parametrize(("provider", "network"), _timeseries_networks())
def test_every_network_declares_its_licence_or_says_why_not(provider: str, network: str) -> None:
    """A provider's licence and credit line are data of its metadata, never left out by forgetting."""
    metadata = Wetterdienst.resolve(provider, network).metadata

    if (provider, network) in LICENSE_NOT_STATED:
        assert metadata.license is None, f"{provider}/{network} states a licence now: drop it from LICENSE_NOT_STATED"
        return
    assert metadata.license is not None, f"{provider}/{network} declares no licence"
    assert metadata.license.url.startswith("https://")
    assert metadata.license.name
    if metadata.license.spdx_id:
        assert " " not in metadata.license.spdx_id.replace(" OR ", "").replace(" AND ", "")


def test_the_licence_of_a_network_is_in_its_answer_even_where_it_is_null(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where a provider states none the answer says `null` rather than leaving the member out."""
    stated = DwdObservationRequest.metadata
    monkeypatch.setattr(
        DwdObservationRequest, "metadata", stated.model_copy(update={"license": None, "attribution": None})
    )
    _stub_result(monkeypatch, "/api/values")

    response = client.get("/api/values", params=_params("/api/values"))

    assert response.status_code == 200, response.text
    provider = response.json()["metadata"]["provider"]
    assert provider["license"] is None
    assert provider["attribution"] is None
    assert "X-Wetterdienst-License" not in response.headers
    assert "Link" not in response.headers
