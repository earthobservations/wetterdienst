# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The note every answer carries about what wetterdienst did to the data, and the notice of a provider (GH-2567).

Licences such as CC BY ask that changes be indicated. Every answer's `metadata` block has the one `processing_note`
that says the data was reshaped and its units converted; the answers of interpolate, summarize and the climate
stripes add that the values are derived. A provider whose terms restrict what may be done with its data (ECCC's
redistribution clause) has a `notice`, which goes where the credit line goes. Offline: the results are the stubs of
the REST tests.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.ui.test_response_metadata import ENDPOINTS, _Figure, _params
from tests.ui.test_restapi import (
    _FETCH_OF_ENDPOINT,
    _OBSERVATION,
    _stub_result,
    _stub_stripes_station,
    _values_result_of_shape,
)
from wetterdienst import Wetterdienst
from wetterdienst.model.processing_note import DERIVED_NOTE, PROCESSING_NOTE, processing_note
from wetterdienst.model.result import describe_provider
from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.mcp import _REPORTING_HEADERS, _report_of, _sentence_of
from wetterdienst.ui.response_metadata import (
    _header_text,
    alerts_metadata,
    metadata_to_dict,
    response_headers,
    response_metadata,
)
from wetterdienst.util.response_warnings import _COUNTED, _RECORDED

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def _unrecorded() -> Iterator[None]:
    """Start every test with no record of warnings, as the thread of a server has before its handler begins one."""
    recorded, counted = _RECORDED.set(None), _COUNTED.set(None)
    yield
    _COUNTED.reset(counted)
    _RECORDED.reset(recorded)


@pytest.fixture
def client() -> TestClient:
    """Make a client of the app."""
    return TestClient(restapi.app, raise_server_exceptions=False)


PROCESSING_HEADER = "X-Wetterdienst-Processing"
NOTICE_HEADER = "X-Wetterdienst-Notice"
#: what an answer of each route says: the plain note, or the note with the derived wording after it
DERIVED_ENDPOINTS = {"/api/interpolate", "/api/summarize"}


def _expected(endpoint: str) -> str:
    return processing_note(derived=endpoint in DERIVED_ENDPOINTS)


# --- the wording ---------------------------------------------------------------------------------------------------


def test_the_note_says_what_was_done_and_claims_nothing_of_the_licence() -> None:
    """One short note for every licence: reshaped, units converted, and for derived values that they are derived."""
    assert "reshaped" in PROCESSING_NOTE
    assert "units" in PROCESSING_NOTE
    assert "derived" in DERIVED_NOTE
    assert processing_note() == PROCESSING_NOTE
    assert processing_note(derived=True) == f"{PROCESSING_NOTE} {DERIVED_NOTE}"
    # it says what happened to the data, not what a licence demands (that is no legal advice)
    for text in (PROCESSING_NOTE, DERIVED_NOTE):
        assert "licen" not in text.lower()
        assert "required" not in text.lower()
        assert "permitted" not in text.lower()
        assert text.isascii()


# --- REST: the block -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("fmt", ["json", "geojson"])
def test_every_json_answer_has_the_note_and_the_derived_ones_say_so(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, fmt: str
) -> None:
    """Values say what was done; interpolate and summarize say besides that the values are derived."""
    _stub_result(monkeypatch, endpoint)

    response = client.get(endpoint, params=_params(endpoint, format=fmt))

    assert response.status_code == 200, response.text
    assert response.json()["metadata"]["processing_note"] == _expected(endpoint)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_the_note_is_the_same_with_and_without_with_metadata(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """The note is not one of the heavy parts: it is in the block whatever was asked for."""
    _stub_result(monkeypatch, endpoint)

    notes = {
        client.get(endpoint, params=_params(endpoint, with_metadata=flag)).json()["metadata"]["processing_note"]
        for flag in ("true", "false")
    }

    assert notes == {_expected(endpoint)}


def test_a_stations_answer_has_the_plain_note(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A list of stations is reshaped too, and nothing in it is derived."""
    _stub_result(monkeypatch, "/api/values")
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: _stub_result_stations())

    response = client.get("/api/stations", params={**_OBSERVATION, "all": "true"})

    assert response.status_code == 200, response.text
    assert response.json()["metadata"]["processing_note"] == PROCESSING_NOTE


def _stub_result_stations() -> Any:  # noqa: ANN401
    return _values_result_of_shape("long").stations


def test_the_blocks_without_a_result_have_the_plain_note() -> None:
    """The warnings of `dwd/alerts` are parsed into a table, and are no derived values."""
    block = metadata_to_dict(alerts_metadata(DwdWeatherAlertRequest, 0))

    assert block["processing_note"] == PROCESSING_NOTE


# --- REST: the headers ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_a_csv_answer_carries_the_note_in_a_header(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """A CSV has no place in its body for the note, so it is a header, derived where the values are."""
    _stub_result(monkeypatch, endpoint)

    response = client.get(endpoint, params=_params(endpoint, format="csv"))

    assert response.status_code == 200, response.text
    assert unquote(response.headers[PROCESSING_HEADER]) == _expected(endpoint)


def test_the_header_is_on_a_json_answer_too(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A proxy that reads no body knows what was done to the data."""
    _stub_result(monkeypatch, "/api/interpolate")

    response = client.get("/api/interpolate", params=_params("/api/interpolate"))

    assert unquote(response.headers[PROCESSING_HEADER]) == response.json()["metadata"]["processing_note"]


# --- stripes -------------------------------------------------------------------------------------------------------


def test_the_stripes_values_and_image_say_the_values_are_derived(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stripes are drawn from yearly values calculated from a station's readings: the block and the headers say so."""
    _stub_stripes_station(monkeypatch, "temperature", [1.0, 2.0])
    monkeypatch.setattr(restapi, "_draw_stripes", lambda _data, _request: _Figure())
    params = {"kind": "temperature", "station": "01048"}

    values = client.get("/api/stripes/values", params=params)
    image = client.get("/api/stripes/image", params={**params, "format": "png"})

    assert values.json()["metadata"]["processing_note"] == processing_note(derived=True)
    assert unquote(values.headers[PROCESSING_HEADER]) == processing_note(derived=True)
    assert image.status_code == 200, image.text
    assert unquote(image.headers[PROCESSING_HEADER]) == processing_note(derived=True)


def test_the_stripes_stations_are_a_list_of_stations_and_not_derived(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stations climate stripes are made for are listed as they are: reshaped, nothing calculated."""
    _stub_stripes_station(monkeypatch, "temperature", [1.0, 2.0])

    response = client.get("/api/stripes/stations", params={"kind": "temperature", "active": "false"})

    assert response.json()["metadata"]["processing_note"] == PROCESSING_NOTE


# --- the command line ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ["/api/values", "/api/interpolate", "/api/summarize"])
def test_the_command_line_prints_the_note(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    """The command line renders the block the REST API does, with `--with-metadata` or without it."""
    from wetterdienst.ui import cli as cli_module  # noqa: PLC0415

    _stub_result(monkeypatch, endpoint)
    monkeypatch.setattr(cli_module, _FETCH_OF_ENDPOINT[endpoint], getattr(restapi, _FETCH_OF_ENDPOINT[endpoint]))
    command = endpoint.removeprefix("/api/")
    params = {**_OBSERVATION, "station" if command != "values" else "stations": "01048"}
    if command != "values":
        params["timestamp"] = "2026-01-01"

    for flag in ("--with-metadata=true", "--with-metadata=false"):
        result = CliRunner().invoke(cli, [command, *(f"--{k}={v}" for k, v in params.items()), flag])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["metadata"]["processing_note"] == _expected(endpoint)


# --- MCP -----------------------------------------------------------------------------------------------------------


def test_the_report_of_the_mcp_reads_the_note_and_the_notice_off_the_headers() -> None:
    """An answer that is no JSON (a CSV, an image) has them in headers, and the tool's sentence tells them."""
    headers = {
        "x-wetterdienst-notice": _header_text("Pass these terms on: https://example.org/terms"),
        "x-wetterdienst-processing": _header_text(processing_note(derived=True)),
    }

    report = _report_of(headers)

    assert report == {
        "notice": "Pass these terms on: https://example.org/terms",
        "processing_note": processing_note(derived=True),
    }
    sentence = _sentence_of("text/csv", 1, "text content", report)
    assert "Notice: Pass these terms on: https://example.org/terms" in sentence
    assert sentence.endswith(processing_note(derived=True))


def test_the_mcp_carries_the_new_headers_through_its_envelope() -> None:
    """The headers that say whose data it is are the ones the envelope of a non-JSON answer keeps."""
    assert {"x-wetterdienst-notice", "x-wetterdienst-processing"} <= set(_REPORTING_HEADERS)


# --- the notice of a provider --------------------------------------------------------------------------------------


def test_eccc_declares_its_notice() -> None:
    """The redistribution clause of ECCC is in its metadata, with where the licence agreement is."""
    notice = EcccObservationRequest.metadata.notice

    assert notice is not None
    assert "same restrictions" in notice
    assert "no fee" in notice
    assert "https://climate.weather.gc.ca/prods_servs/attachment1_e.html" in notice


def test_no_other_network_has_a_notice() -> None:
    """A notice is for a restriction of the terms: DWD, whose terms have none, has none."""
    assert DwdObservationRequest.metadata.notice is None
    assert DwdWeatherAlertRequest.terms.notice is None
    declared = {
        f"{provider}/{network}"
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if _terms(provider, network).notice
    }
    assert declared == {"eccc/observation"}


def _terms(provider: str, network: str) -> Any:  # noqa: ANN401
    if Wetterdienst.is_standalone(provider, network):
        return Wetterdienst.resolve_standalone(provider, network).terms
    return Wetterdienst.resolve(provider, network).metadata


def test_a_notice_is_in_the_block_and_the_headers_and_nothing_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The notice goes where the credit line goes: `provider.notice`, `X-Wetterdienst-Notice`; the answer is a 200."""
    _stub_result(monkeypatch, "/api/values")
    notice = "Pass these terms on: https://example.org/terms é"
    monkeypatch.setattr(DwdObservationRequest.metadata, "notice", notice)

    json_answer = client.get("/api/values", params=_params("/api/values"))
    csv_answer = client.get("/api/values", params=_params("/api/values", format="csv"))

    assert json_answer.status_code == csv_answer.status_code == 200
    assert json_answer.json()["metadata"]["provider"]["notice"] == notice
    assert unquote(json_answer.headers[NOTICE_HEADER]) == notice
    assert unquote(csv_answer.headers[NOTICE_HEADER]) == notice
    assert csv_answer.headers[NOTICE_HEADER].isascii()


def test_an_answer_without_a_notice_says_null_and_has_no_header(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As for the licence: the member is always there, null where there is none, and the header is left out."""
    _stub_result(monkeypatch, "/api/values")

    response = client.get("/api/values", params=_params("/api/values"))

    assert response.json()["metadata"]["provider"]["notice"] is None
    assert NOTICE_HEADER not in response.headers


def test_the_headers_of_a_block_name_the_notice_of_eccc() -> None:
    """The block of an ECCC answer, built as every answer's is, has the notice in its headers."""
    metadata = response_metadata(
        _values_result_of_shape("long"), restapi.ValuesRequest(**_OBSERVATION, stations="01048")
    )
    metadata.provider = describe_provider(EcccObservationRequest.metadata)["provider"]

    headers = response_headers(metadata)

    assert unquote(headers[NOTICE_HEADER]) == EcccObservationRequest.metadata.notice
    assert (
        headers["X-Wetterdienst-License"] == "Licence Agreement for Use of Environment and Climate Change Canada Data"
    )
