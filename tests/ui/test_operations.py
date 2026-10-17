# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The operating contract of the REST API (GH-3065): limits, streaming, timeout, problem types, request id.

Offline: the selection of the stations and the reader that walks them are stood in for, and the request goes through the
app's routes, middleware and handlers with a client.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.ui.test_restapi import (
    _OBSERVATION,
    _stub_result,
    _stub_stream,
    _values_result_of_shape,
)
from wetterdienst import Options, Settings, exceptions
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.deprecation import Deprecation, deprecated_route, deprecation_headers, mark_deprecated
from wetterdienst.ui.limits import estimate_point_rows, estimate_rows
from wetterdienst.ui.middleware import RequestContextMiddleware
from wetterdienst.ui.problems import PROBLEMS, ProblemKind, request_id_from
from wetterdienst.ui.render import ValuesSettings, render
from wetterdienst.util.response_warnings import _COUNTED, _RECORDED, begin_response, warn_response

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.model.result import ValuesResult

_VALUES = {**_OBSERVATION, "stations": "01048"}
_STATIONS = {**_OBSERVATION, "all": "true"}


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings.

    And the warnings an earlier test recorded in this thread: the client runs the app in a context copied from
    it, which would then record for a stream whose own context was lost.
    """
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


def _selection_of(n: int, *, start: dt.datetime | None = None, end: dt.datetime | None = None) -> pl.DataFrame:
    """Give the selection of `n` stations of the daily climate summary, with the record they bound it by."""
    base = _values_result_of_shape("long").stations.df.filter(pl.col("dataset") == "climate_summary")
    frame = pl.concat([base.with_columns(pl.lit(f"{i:05d}").alias("station_id")) for i in range(n)])
    if start is not None:
        frame = frame.with_columns(
            pl.lit(start, pl.Datetime("us", "UTC")).alias("start_timestamp"),
            pl.lit(end, pl.Datetime("us", "UTC")).alias("end_timestamp"),
        )
    return frame


def _chunk_of(result: ValuesResult, station_id: str) -> ValuesResult:
    """Give the values of the stub, as the reader gives them for one station."""
    return replace(result, df=result.df.with_columns(pl.lit(station_id).alias("station_id")))


def _lines(response: Any) -> list[dict[str, Any]]:  # noqa: ANN401
    return [json.loads(line) for line in response.text.splitlines()]


# --- problem types and request ids -----------------------------------------------------------------------------


def test_every_kind_is_documented_and_answered_with_a_status_of_its_own() -> None:
    """The table, the enumeration and the docs list the same kinds; each is answered with a status from the table."""
    docs = (Path(__file__).parents[2] / "docs" / "usage" / "restapi.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"`urn:wetterdienst:problem:([a-z-]+)`", docs))

    assert set(PROBLEMS) == set(ProblemKind)
    assert documented == {kind.value for kind in ProblemKind}
    for kind, spec in PROBLEMS.items():
        assert re.search(rf"\| `urn:wetterdienst:problem:{kind.value}` \| {spec.status} \|", docs), kind


def test_the_request_id_is_echoed_when_plain_and_made_when_not(client: TestClient) -> None:
    """A client's own `X-Request-ID` comes back; one that is not plain text is replaced."""
    assert client.get("/api/version", headers={"X-Request-ID": "abc-123.x"}).headers["X-Request-ID"] == "abc-123.x"
    replaced = client.get("/api/version", headers={"X-Request-ID": "bad id with spaces"}).headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", replaced)
    assert request_id_from("x" * 129) != "x" * 129
    assert re.fullmatch(r"[0-9a-f]{32}", client.get("/health").headers["X-Request-ID"])


def test_a_server_error_is_logged_with_the_request_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The id a caller reports finds the log line of the failure."""

    def fail(**_kwargs: object) -> None:
        msg = "bug"
        raise RuntimeError(msg)

    monkeypatch.setattr(restapi, "get_values", fail)
    with caplog.at_level("WARNING", logger="wetterdienst.ui.problems"):
        client.get("/api/v1/values", params=_VALUES, headers={"X-Request-ID": "trace-9"})

    assert "Request trace-9 failed with a 500: internal-error." in caplog.text


def test_a_problem_carries_the_request_id_of_the_client(client: TestClient) -> None:
    """`instance` and `request_id` of a problem are the id the client sent, also in the header."""
    response = client.get("/api/v1/glossary", params={"limit": 0}, headers={"X-Request-ID": "trace-7"})

    body = response.json()
    assert (body["request_id"], body["instance"]) == ("trace-7", "urn:wetterdienst:request:trace-7")
    assert body["type"] == "urn:wetterdienst:problem:invalid-parameters"
    assert response.headers["X-Request-ID"] == "trace-7"


@pytest.mark.parametrize(
    ("error", "status", "retry"),
    [
        (exceptions.DownloadError("https://x.example/f", "reason"), 502, True),
        (exceptions.NoInternetError("No internet: could not reach https://x"), 503, True),
        (exceptions.RequestError("no"), 400, False),
        (exceptions.ConfigurationError("no"), 501, False),
        (RuntimeError("bug"), 500, False),
    ],
)
def test_retry_after_is_sent_where_a_retry_makes_sense(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, error: BaseException, status: int, *, retry: bool
) -> None:
    """502 and 503 (and 504, below) say when to retry; a refusal, a lack of the server and a defect do not."""

    def fail(**_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(restapi, "get_values", fail)
    response = client.get("/api/v1/values", params=_VALUES)

    assert response.status_code == status
    assert ("Retry-After" in response.headers) is retry
    if retry:
        assert response.headers["Retry-After"] == "30"


# --- limits ------------------------------------------------------------------------------------------------------


def test_the_limits_are_settings_with_documented_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """The defaults are the constants of the settings, and the host sets each with a `WD_RESTAPI_*` variable."""
    settings = Settings()
    assert (settings.restapi_max_stations, settings.restapi_max_rows) == (100, 500_000)
    assert (settings.restapi_max_stream_rows, settings.restapi_timeout) == (10_000_000, 60.0)

    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "7")
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "2.5")
    assert (Settings().restapi_max_stations, Settings().restapi_timeout) == (7, 2.5)
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "-1")
    with pytest.raises(ValueError, match="restapi_max_rows"):
        Settings()


def test_a_values_request_for_too_many_stations_is_refused_before_any_download(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stations are counted from the selection; the reader is not touched, and the problem says how to narrow."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "2")
    _stub_stream(monkeypatch, [], stations_df=_selection_of(3))
    downloaded = []
    monkeypatch.setattr(
        type(_values_result_of_shape("long").stations.request)._values,  # noqa: SLF001
        "query",
        lambda _reader: downloaded.append(1),
    )

    response = client.get("/api/v1/values", params={**_STATIONS, "all": "true"})

    assert response.status_code == 400
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:limit-exceeded"
    assert (body["limit"], body["maximum"], body["requested"]) == ("stations", 2, 3)
    assert "3 stations" in body["detail"]
    assert "rank" in body["detail"]
    assert not downloaded


def test_a_ranked_selection_counts_as_its_rank(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rank reads that many stations, however many the list holds."""
    from wetterdienst.model.result import StationsFilter  # noqa: PLC0415

    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "2")
    base = _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=_selection_of(50))
    ranked = replace(base.stations, df=_selection_of(50), stations_filter=StationsFilter.BY_RANK, rank=2)
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: ranked)
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: ranked)

    assert (
        client.get("/api/v1/values", params={**_OBSERVATION, "latitude": 51, "longitude": 13, "rank": 2}).status_code
        == 200
    )
    ranked = replace(ranked, rank=3)
    assert (
        client.get("/api/v1/values", params={**_OBSERVATION, "latitude": 51, "longitude": 13, "rank": 3}).status_code
        == 400
    )


def test_a_limit_of_zero_is_no_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """0 switches a limit off."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "0")
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=_selection_of(500))

    assert client.get("/api/v1/values", params=_STATIONS).status_code == 200


def test_the_rows_are_estimated_from_the_record_the_window_and_the_parameters() -> None:
    """Ten days of a daily dataset are ten readings for each of its parameters, a station's record bounds the window."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    base = _values_result_of_shape("long").stations
    parameters = [
        "daily/climate_summary/temperature_air_mean_2m",
        "daily/climate_summary/sunshine_duration",
    ]
    window = {"start": dt.datetime(2020, 1, 1, tzinfo=dt.UTC), "end": dt.datetime(2020, 1, 10, tzinfo=dt.UTC)}
    request = DwdObservationRequest(parameters=parameters, **window)
    stations = replace(
        base,
        request=request,
        df=_selection_of(3, start=dt.datetime(2019, 1, 1, tzinfo=dt.UTC), end=dt.datetime(2021, 1, 1, tzinfo=dt.UTC)),
    )

    assert estimate_rows(stations) == 3 * 10 * 2

    # a record that began on the 6th is cut short on that side
    late = replace(
        stations,
        df=_selection_of(1, start=dt.datetime(2020, 1, 6, tzinfo=dt.UTC), end=dt.datetime(2021, 1, 1, tzinfo=dt.UTC)),
    )
    assert estimate_rows(late) == 5 * 2
    # a station whose record is not published, in a request with no window, is not counted
    unbounded = replace(base, request=DwdObservationRequest(parameters=parameters), df=_selection_of(2))
    assert estimate_rows(unbounded) == 0
    assert estimate_point_rows(request.parameters, request.start, request.end) == 10 * 2
    assert estimate_point_rows(request.parameters, None, None) == 0


def test_an_answer_of_too_many_rows_is_refused_and_told_to_stream(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A JSON answer over the limit is a 400 that names ndjson and csv; a stream is let through up to its own limit."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    record = _selection_of(1, start=dt.datetime(1950, 1, 1, tzinfo=dt.UTC), end=dt.datetime(2020, 1, 1, tzinfo=dt.UTC))
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=record)
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", restapi.get_stations)

    refused = client.get("/api/v1/values", params=_VALUES)
    streamed = client.get("/api/v1/values", params={**_VALUES, "format": "ndjson"})

    assert refused.status_code == 400
    body = refused.json()
    assert (body["limit"], body["maximum"]) == ("rows", 1000)
    assert body["requested"] > 1000
    assert "format=ndjson" in body["detail"]
    assert "timestamp" in body["detail"]
    assert streamed.status_code == 200

    monkeypatch.setenv("WD_RESTAPI_MAX_STREAM_ROWS", "1000")
    too_long = client.get("/api/v1/values", params={**_VALUES, "format": "csv"})
    assert too_long.status_code == 400
    assert too_long.json()["limit"] == "stream_rows"
    assert "format=" not in too_long.json()["detail"]


def test_a_geo_answer_of_too_many_rows_is_refused(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The readings of the window of `interpolate` and `summarize` are counted from the request, before any download."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "100")
    reached = exceptions.RequestError("the estimate was reached")

    def estimate(*_args: object, **_kwargs: object) -> None:
        raise reached

    monkeypatch.setattr(DwdObservationRequest, "interpolate_by_station_id", estimate)
    monkeypatch.setattr(DwdObservationRequest, "summarize_by_station_id", estimate)
    params = {**_OBSERVATION, "station": "01048"}

    for endpoint in ("/api/v1/interpolate", "/api/v1/summarize"):
        short = client.get(endpoint, params={**params, "timestamp": "2020-01-01/2020-01-10"})
        long = client.get(endpoint, params={**params, "timestamp": "2000/2020"})

        # the short window is let through to the (stood in) estimate, the long one is refused before it
        assert short.json()["detail"] == "the estimate was reached", endpoint
        assert long.json()["type"] == "urn:wetterdienst:problem:limit-exceeded", endpoint
        assert (long.json()["limit"], long.json()["maximum"]) == ("rows", 100)


def test_a_stations_listing_is_held_to_the_row_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A listing is rows too: over the limit it is a 400 as JSON, and streams as ndjson."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "5")
    stations = replace(_values_result_of_shape("long").stations, df=_selection_of(8))
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)

    assert client.get("/api/v1/stations", params=_STATIONS).status_code == 400
    assert client.get("/api/v1/stations", params={**_STATIONS, "format": "ndjson"}).status_code == 200


def test_history_is_held_to_the_station_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """History downloads for each station, so the stations of one request are limited alike."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "2")
    stations = replace(_values_result_of_shape("long").stations, df=_selection_of(3))
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)

    response = client.get(
        "/api/v1/history", params={"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": "true"}
    )

    assert response.status_code == 400
    assert response.json()["limit"] == "stations"


# --- streaming ---------------------------------------------------------------------------------------------------


def test_ndjson_is_the_metadata_the_rows_and_the_end(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The first line is the `metadata` block, then a line for each row of each station, then `end` with the counts."""
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [_chunk_of(result, "01048"), _chunk_of(result, "01049")])

    response = client.get("/api/v1/values", params={**_VALUES, "format": "ndjson"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"
    assert response.headers["X-Request-ID"]
    assert "X-Wetterdienst-Rows" not in response.headers
    assert response.headers["X-Wetterdienst-License"] == "CC-BY-4.0"
    lines = _lines(response)
    assert set(lines[0]) == {"metadata"}
    assert lines[0]["metadata"]["request"]["parameters"][0].startswith("daily/climate_summary/")
    assert lines[0]["metadata"]["counts"]["rows"] == 0
    rows = lines[1:-1]
    expected = result.to_dict()["values"]
    assert len(rows) == 2 * len(expected)
    assert rows[0] == {**expected[0], "station_id": "01048"}
    assert [row["station_id"] for row in rows[len(expected) :]] == ["01049"] * len(expected)
    assert lines[-1] == {"end": {"counts": {"stations": 2, "rows": len(rows)}, "warnings": []}}


def test_ndjson_of_values_is_what_the_command_line_writes(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """REST and the command line write one answer: the same lines, but when it was retrieved."""
    result = _stub_stream(monkeypatch, [_values_result_of_shape("long")])
    request = restapi.ValuesRequest(**_VALUES, format="ndjson", with_metadata=True)

    streamed = _lines(client.get("/api/v1/values", params={**_VALUES, "format": "ndjson", "with_metadata": "true"}))
    from wetterdienst.ui.response_metadata import response_metadata  # noqa: PLC0415

    options = Options()
    rendered = [
        json.loads(line)
        for line in render(
            result, request, ValuesSettings, options, metadata=response_metadata(result, request, heavy=True)
        ).splitlines()
    ]

    for lines in (streamed, rendered):
        lines[0]["metadata"].pop("retrieved_at")
        # a stream does not know the rows as it begins: the counts are in `end`
        lines[0]["metadata"].pop("counts")
    assert streamed[0]["metadata"] == rendered[0]["metadata"]
    assert streamed[1:-1] == rendered[1:-1]
    assert set(streamed[0]) == {"metadata", "settings"}
    assert streamed[0]["settings"] == rendered[0]["settings"]
    assert streamed[-1]["end"]["counts"] == rendered[-1]["end"]["counts"]


def test_the_cli_writes_ndjson_too() -> None:
    """`--format=ndjson` is a choice of `stations` and `values`, and is refused with `--sql-values`."""
    from click.testing import CliRunner  # noqa: PLC0415

    for command in ("stations", "values"):
        assert "ndjson" in CliRunner().invoke(cli, [command, "--help"]).output
    refused = CliRunner().invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl",
            "--stations=01048",
            "--format=ndjson",
            "--sql-values=value>1",
        ],
    )
    assert refused.exit_code == 2
    assert "sql_values" in refused.output


def test_csv_is_sent_in_chunks_with_one_header(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CSV of several stations is the CSV of their concatenation; the header is written once."""
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [_chunk_of(result, "01048"), _chunk_of(result, "01049")])

    response = client.get("/api/v1/values", params={**_VALUES, "format": "csv"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    whole = pl.concat([_chunk_of(result, "01048").df, _chunk_of(result, "01049").df])
    assert response.text == replace(result, df=whole).to_csv()
    assert response.headers["X-Wetterdienst-License"] == "CC-BY-4.0"
    assert "X-Wetterdienst-Rows" not in response.headers


def test_csv_of_no_values_is_the_header(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A selection that finds no reading is a 200 with the header row and no rows, and an `end` of zeros as NDJSON."""
    _stub_stream(monkeypatch, [])
    monkeypatch.setattr(
        type(_values_result_of_shape("long").stations.request)._values,  # noqa: SLF001
        "_empty_values_df",
        lambda _reader: _values_result_of_shape("long").df.clear(),
    )

    csv = client.get("/api/v1/values", params={**_VALUES, "format": "csv"})
    ndjson = client.get("/api/v1/values", params={**_VALUES, "format": "ndjson"})

    assert csv.status_code == 200
    assert csv.text.splitlines() == [",".join(_values_result_of_shape("long").df.columns)]
    assert _lines(ndjson)[-1] == {"end": {"counts": {"stations": 0, "rows": 0}, "warnings": []}}


def test_csv_with_sql_values_is_still_one_body(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `sql_values` clause filters the answer as a frame, so csv with one is not streamed, and ndjson refuses it."""
    monkeypatch.setenv("WD_RESTAPI_SQL", "true")
    taken = _stub_result(monkeypatch, "/api/values")
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: pytest.fail("the csv was streamed"))

    csv = client.get("/api/v1/values", params={**_VALUES, "format": "csv", "sql_values": "value > 0"})
    ndjson = client.get("/api/v1/values", params={**_VALUES, "format": "ndjson", "sql_values": "value > 0"})
    stations = client.get("/api/v1/values", params={**_VALUES, "format": "ndjson", "with_stations": "true"})

    assert taken
    assert csv.status_code == 200
    assert ndjson.status_code == 400
    assert "sql_values" in ndjson.json()["detail"]
    assert stations.status_code == 400
    assert "with_stations" in stations.json()["detail"]


def test_warnings_raised_while_streaming_are_in_the_end_line(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A station skipped on the way cannot be in the first line; it is in `end`, with the context of the request."""
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [])

    def query(_reader: object) -> Iterator[ValuesResult]:
        yield _chunk_of(result, "01048")
        warn_response(restapi.log, "station-skipped", "station 00002 is skipped")
        yield _chunk_of(result, "01049")

    monkeypatch.setattr(type(result.stations.request)._values, "query", query)  # noqa: SLF001

    lines = _lines(client.get("/api/v1/values", params={**_VALUES, "format": "ndjson"}))

    assert lines[0]["metadata"]["warnings"] == []
    assert [w["code"] for w in lines[-1]["end"]["warnings"]] == ["station-skipped"]


def test_a_failure_on_the_first_station_has_its_status(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The first station is read before the response begins, so its failure is a 503 and not a 200 with an error."""
    _stub_stream(monkeypatch, [], error=exceptions.NoInternetError("No internet: could not reach https://x"))

    for fmt in ("ndjson", "csv"):
        response = client.get("/api/v1/values", params={**_VALUES, "format": fmt})
        assert response.status_code == 503, fmt
        assert response.json()["type"] == "urn:wetterdienst:problem:upstream-unreachable"
        assert response.headers["Retry-After"] == "30"


def test_a_failure_on_a_later_station_is_the_last_line(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The status is sent by then: the failure comes as `error`, a problem, and there is no `end`. It is logged."""
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [_chunk_of(result, "01048")], error=exceptions.DownloadError("https://x.example/f", "r"))

    response = client.get("/api/v1/values", params={**_VALUES, "format": "ndjson"}, headers={"X-Request-ID": "r-1"})

    assert response.status_code == 200
    lines = _lines(response)
    assert "end" not in lines[-1]
    problem = lines[-1]["error"]
    assert problem["type"] == "urn:wetterdienst:problem:upstream-failed"
    assert (problem["status"], problem["request_id"]) == (502, "r-1")
    assert "x.example" not in response.text


def test_stations_are_streamed_as_ndjson_and_csv(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A listing is written in batches: the same rows as the JSON, the same CSV."""
    stations = replace(_values_result_of_shape("long").stations, df=_selection_of(5))
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)
    monkeypatch.setattr("wetterdienst.ui.streaming.STATIONS_BATCH", 2)

    ndjson = client.get("/api/v1/stations", params={**_STATIONS, "format": "ndjson"})
    csv = client.get("/api/v1/stations", params={**_STATIONS, "format": "csv"})
    as_json = client.get("/api/v1/stations", params=_STATIONS).json()

    lines = _lines(ndjson)
    assert lines[1:-1] == as_json["stations"]
    assert lines[0]["metadata"]["counts"] == as_json["metadata"]["counts"]
    assert lines[-1]["end"]["counts"] == {"stations": 5, "rows": 5}
    assert csv.text == stations.to_csv()
    assert csv.text.count("station_id") == 1


def test_the_listing_of_stations_is_what_the_command_line_writes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REST and the command line write one NDJSON listing: the same rows, the same `end`."""
    from wetterdienst.ui.render import render_stations  # noqa: PLC0415

    stations = replace(_values_result_of_shape("long").stations, df=_selection_of(3))
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)
    request = restapi.StationsRequest(**_STATIONS, format="ndjson")

    streamed = _lines(client.get("/api/v1/stations", params={**_STATIONS, "format": "ndjson"}))
    rendered = [json.loads(line) for line in render_stations(stations, request).splitlines()]

    for lines in (streamed, rendered):
        lines[0]["metadata"].pop("retrieved_at")
    assert streamed == rendered


# --- the timeout -------------------------------------------------------------------------------------------------


def test_a_request_over_the_timeout_is_a_504_problem(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The answer is a 504 of the kind `request-timeout` with `Retry-After`, sent when the timeout is over."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")

    def slow(**_kwargs: object) -> None:
        time.sleep(1.5)

    monkeypatch.setattr(restapi, "get_values", slow)
    started = time.monotonic()
    response = client.get("/api/v1/values", params=_VALUES, headers={"X-Request-ID": "slow-1"})

    assert time.monotonic() - started < 1.2
    assert response.status_code == 504
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:request-timeout"
    assert "0.3 seconds" in body["detail"]
    assert body["request_id"] == "slow-1"
    assert response.headers["Retry-After"] == "30"
    assert response.headers["X-Request-ID"] == "slow-1"


def test_the_timeout_leaves_the_rest_alone(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The index, the health check and a request in time are not held to it, and 0 switches it off."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    _stub_result(monkeypatch, "/api/values")
    assert client.get("/api/v1/values", params=_VALUES).status_code == 200
    assert client.get("/health").status_code == 200

    def slow(**_kwargs: object) -> None:
        time.sleep(0.6)
        msg = "late"
        raise exceptions.RequestError(msg)

    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0")
    monkeypatch.setattr(restapi, "get_values", slow)
    assert client.get("/api/v1/values", params=_VALUES).status_code == 400


def test_a_stream_is_held_to_the_timeout_between_its_chunks(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stream may outlast the timeout; a chunk that takes longer ends it with a `request-timeout` error."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.5")
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [])

    def query(_reader: object) -> Iterator[ValuesResult]:
        yield _chunk_of(result, "01048")
        time.sleep(0.35)
        yield _chunk_of(result, "01049")
        time.sleep(1.5)
        yield _chunk_of(result, "01050")

    monkeypatch.setattr(type(result.stations.request)._values, "query", query)  # noqa: SLF001

    lines = _lines(client.get("/api/v1/values", params={**_VALUES, "format": "ndjson"}))

    ids = [line.get("station_id") for line in lines[1:-1]]
    assert set(ids) == {"01048", "01049"}
    assert lines[-1]["error"]["type"] == "urn:wetterdienst:problem:request-timeout"
    assert lines[-1]["error"]["status"] == 504


def test_a_csv_stream_that_is_too_slow_is_cut(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """CSV has no place to say the timeout: the stream stops, and the connection is cut."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.4")
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [])

    def query(_reader: object) -> Iterator[ValuesResult]:
        yield _chunk_of(result, "01048")
        time.sleep(1.2)
        yield _chunk_of(result, "01049")

    monkeypatch.setattr(type(result.stations.request)._values, "query", query)  # noqa: SLF001

    response = client.get("/api/v1/values", params={**_VALUES, "format": "csv"})

    # the status was sent with the first chunk; the second never comes
    assert response.status_code == 200
    assert "01049" not in response.text


# --- deprecation -------------------------------------------------------------------------------------------------


def test_the_headers_of_a_deprecation_follow_the_rfcs() -> None:
    """`Deprecation` is the date as a structured-field date, `Sunset` an HTTP date, and the link says where to look."""
    deprecation = Deprecation(since=dt.date(2026, 10, 5), sunset=dt.date(2027, 4, 1), link="https://docs.example/old")
    later = Deprecation(since=dt.date(2026, 11, 1), sunset=dt.date(2027, 1, 1))

    assert deprecation_headers([]) == {}
    assert deprecation_headers([deprecation]) == {
        "Deprecation": "@1791158400",
        "Sunset": "Thu, 01 Apr 2027 00:00:00 GMT",
        "Link": '<https://docs.example/old>; rel="deprecation"',
    }
    # of several, the earliest of each
    combined = deprecation_headers([later, deprecation])
    assert (combined["Deprecation"], combined["Sunset"]) == ("@1791158400", "Fri, 01 Jan 2027 00:00:00 GMT")


def test_a_deprecated_route_is_marked_in_openapi_and_answers_the_headers() -> None:
    """The helper marks the route `deprecated` in OpenAPI, and every response to it carries the headers.

    Nothing real is deprecated at the moment (GH-3077), so a synthetic route stands in for one.
    """
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    deprecation = Deprecation(since=dt.date(2026, 10, 5), sunset=dt.date(2027, 4, 1))

    @app.get("/old", **deprecated_route(deprecation))
    def old() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/new")
    def new() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.get("/old")

    assert response.json() == {"ok": "yes"}
    assert response.headers["Deprecation"] == "@1791158400"
    assert response.headers["Sunset"] == "Thu, 01 Apr 2027 00:00:00 GMT"
    assert "Deprecation" not in client.get("/new").headers
    paths = app.openapi()["paths"]
    assert paths["/old"]["get"]["deprecated"] is True
    assert "deprecated" not in paths["/new"]["get"]


def test_a_deprecated_parameter_answers_the_headers_and_is_a_warning() -> None:
    """A handler that reads a deprecated parameter marks it: the headers, and the `deprecated-parameter` warning.

    Nothing real is deprecated at the moment (`summarize`'s `use_nearby_station_distance` was removed, GH-3077), so
    the helper that marks a parameter is exercised by a synthetic route, as the one for an endpoint is above.
    """
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    deprecation = Deprecation(since=dt.date(2026, 10, 5), link="https://docs.example/old")

    @app.get("/thing")
    def thing(old: float | None = None) -> dict[str, Any]:
        begin_response()
        if old is not None:
            warn_response(restapi.log, "deprecated-parameter", "old is deprecated. Leave it out.")
            mark_deprecated(deprecation)
        return {"warnings": list(_RECORDED.get() or [])}

    client = TestClient(app)
    used = client.get("/thing", params={"old": "5"})
    unused = client.get("/thing")

    assert used.status_code == 200, used.text
    assert used.headers["Deprecation"] == "@1791158400"
    assert "Sunset" not in used.headers
    assert used.headers["Link"] == '<https://docs.example/old>; rel="deprecation"'
    assert [w["code"] for w in used.json()["warnings"]] == ["deprecated-parameter"]
    assert "Deprecation" not in unused.headers
    assert unused.json() == {"warnings": []}
