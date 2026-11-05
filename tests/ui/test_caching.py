# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests of the cache headers, the conditional requests and the readiness probe of the REST API (GH-3134)."""

from __future__ import annotations

import datetime as dt
import itertools
import os
from email.utils import format_datetime
from typing import TYPE_CHECKING, Any

import pytest
from starlette.testclient import TestClient

from tests.ui.cli.test_cli_history import _stations_without_histories
from tests.ui.test_restapi import (
    _OBSERVATION,
    _stub_result,
    _stub_stream,
    _stub_stripes_station,
    _values_result_of_shape,
)
from wetterdienst.ui import restapi
from wetterdienst.ui.caching import (
    CATALOGUE_CACHE_CONTROL,
    HISTORY_CACHE_CONTROL,
    settings_changed_at,
    weak_etag,
)
from wetterdienst.ui.problems import PROBLEMS, ProblemKind

if TYPE_CHECKING:
    from pathlib import Path

#: the routes whose answer is sent to be kept, with a request each and whether they have a `Last-Modified`
_CATALOGUE = [
    pytest.param("/api/v1/coverage", {}, id="coverage"),
    pytest.param("/api/v1/coverage", {"provider": "dwd", "network": "observation"}, id="coverage-of-a-network"),
    pytest.param("/api/v1/providers", {}, id="providers"),
    pytest.param("/api/v1/glossary", {"limit": 5}, id="glossary"),
]
_HISTORY = ("/api/v1/history", {**_OBSERVATION, "stations": "02564"})
_CACHE_HEADERS = ("etag", "cache-control", "last-modified", "expires", "age", "vary")


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


@pytest.fixture
def history_of_one_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer the history of a station offline: the lookup of its stations has one, without sections."""
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: _stations_without_histories())


def _history_of(monkeypatch: pytest.MonkeyPatch, entries: list[dict[str, Any]]) -> None:
    """Answer the history of the station with these entries, as the provider's files say them."""

    class _History:
        def to_dict(self, **_kwargs: object) -> dict[str, Any]:
            return {"histories": entries}

    def stations(**_kwargs: object) -> Any:  # noqa: ANN401
        result = _stations_without_histories()
        object.__setattr__(result, "history", _History)
        return result

    monkeypatch.setattr(restapi, "get_stations", stations)


def _cache_headers(response: Any) -> dict[str, str]:  # noqa: ANN401
    """Give the headers of a response that say how it is cached."""
    return {name: value for name, value in response.headers.items() if name in _CACHE_HEADERS}


# --- what is cached, and for how long -----------------------------------------------------------------------------


@pytest.mark.parametrize(("path", "params"), _CATALOGUE)
def test_the_catalogue_is_sent_to_be_kept_with_its_validators(client: TestClient, path: str, params: dict) -> None:
    """Coverage, providers and the glossary change with the release: kept five minutes, with a tag and a time."""
    response = client.get(path, params=params)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == CATALOGUE_CACHE_CONTROL == "public, max-age=300"
    assert response.headers["ETag"].startswith('W/"')
    assert response.headers["Last-Modified"].endswith(" GMT")
    # nothing in a request but its URL changes these answers: no `Vary`, so a cache keys on the URL alone
    assert "Vary" not in response.headers


@pytest.mark.usefixtures("history_of_one_station")
def test_a_history_is_sent_to_be_kept_with_a_tag_and_no_time(client: TestClient) -> None:
    """The source of a history says no time it changed, so it has an `ETag` and no `Last-Modified`."""
    response = client.get(*_HISTORY[:1], params=_HISTORY[1])

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == HISTORY_CACHE_CONTROL == "public, max-age=3600"
    assert response.headers["ETag"].startswith('W/"')
    assert "Last-Modified" not in response.headers
    assert "Vary" not in response.headers
    # the headers of the metadata block are still there
    assert response.headers["X-Wetterdienst-Retrieved-At"] == response.json()["metadata"]["retrieved_at"]


def test_the_alias_of_the_routes_is_cached_as_they_are(client: TestClient) -> None:
    """`/api/...` is the same handler as `/api/v1/...`: the same tag, and a 304 for it."""
    versioned = client.get("/api/v1/glossary", params={"limit": 3})
    alias = client.get("/api/glossary", params={"limit": 3}, headers={"If-None-Match": versioned.headers["ETag"]})

    assert alias.status_code == 304


# --- If-None-Match ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("path", "params"), _CATALOGUE)
def test_the_tag_sent_back_is_answered_with_a_304_without_a_body(client: TestClient, path: str, params: dict) -> None:
    """A 304 has no body and the headers that say how the answer is cached, and none of the 200's own."""
    first = client.get(path, params=params)

    second = client.get(path, params=params, headers={"If-None-Match": first.headers["ETag"]})

    assert second.status_code == 304
    assert second.content == b""
    assert "content-length" not in second.headers
    assert "content-type" not in second.headers
    assert _cache_headers(second) == _cache_headers(first)
    # a cache that updates what it holds from the 304 keeps the retrieval time of the body it holds
    assert not [name for name in second.headers if name.lower().startswith("x-wetterdienst-")]
    # the headers of every answer are still sent
    assert second.headers["X-Content-Type-Options"] == "nosniff"
    assert second.headers["X-Request-ID"]


@pytest.mark.parametrize(
    ("header", "status"),
    [
        pytest.param("{etag}", 304, id="the tag"),
        pytest.param('"other", {etag}', 304, id="one of a list"),
        pytest.param("{strong}", 304, id="a strong tag of the same value, which a weak comparison takes"),
        pytest.param("*", 304, id="any"),
        pytest.param('W/"other"', 200, id="another tag"),
        pytest.param("", 200, id="empty"),
        pytest.param("garbage", 200, id="not a tag"),
    ],
)
def test_if_none_match_is_compared_as_the_standard_has_it(client: TestClient, header: str, status: int) -> None:
    """A list, a strong form of the tag and `*` match; what is not a tag of the answer does not."""
    first = client.get("/api/v1/glossary", params={"limit": 4})
    etag = first.headers["ETag"]

    response = client.get(
        "/api/v1/glossary",
        params={"limit": 4},
        headers={"If-None-Match": header.format(etag=etag, strong=etag.removeprefix("W/"))},
    )

    assert response.status_code == status
    if status == 200:
        assert response.json() == first.json()


def test_a_change_of_what_is_asked_is_another_tag_and_is_not_answered_with_a_304(client: TestClient) -> None:
    """The format and every option are in the query: the tag of one is no tag of another, and it is sent in full."""
    plain = client.get("/api/v1/coverage", params={"provider": "dwd", "network": "observation"})
    pretty = client.get("/api/v1/coverage", params={"provider": "dwd", "network": "observation", "pretty": "true"})
    narrower = client.get(
        "/api/v1/coverage", params={"provider": "dwd", "network": "observation", "resolutions": "daily"}
    )

    assert len({plain.headers["ETag"], pretty.headers["ETag"], narrower.headers["ETag"]}) == 3
    asked = client.get(
        "/api/v1/coverage",
        params={"provider": "dwd", "network": "observation", "pretty": "true"},
        headers={"If-None-Match": plain.headers["ETag"]},
    )
    assert asked.status_code == 200
    assert asked.json() == pretty.json()
    # the same question has the same tag
    again = client.get("/api/v1/coverage", params={"provider": "dwd", "network": "observation"})
    assert again.headers["ETag"] == plain.headers["ETag"]


def test_the_request_header_accept_does_not_change_the_answer_or_its_tag(client: TestClient) -> None:
    """None of these routes negotiates a media type, so `Accept` has no `Vary` and changes neither body nor tag."""
    params = {"limit": 4}
    base = client.get("/api/v1/glossary", params=params)

    for accept in ("text/csv", "text/html", "application/xml"):
        response = client.get("/api/v1/glossary", params=params, headers={"Accept": accept})
        assert response.status_code == 200
        assert response.content == base.content
        assert response.headers["ETag"] == base.headers["ETag"]
        assert "Vary" not in response.headers


def test_providers_tag_leaves_out_the_time_of_the_answer(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """`retrieved_at` differs between two answers and the tag does not: a 304 means the rest is the same."""
    stamps = (f"2026-11-05T12:00:{second:02d}.000000+00:00" for second in itertools.count())
    monkeypatch.setattr("wetterdienst.ui.response_metadata._retrieved_at", lambda: next(stamps))

    first = client.get("/api/v1/providers")
    second = client.get("/api/v1/providers", headers={"If-None-Match": first.headers["ETag"]})
    third = client.get("/api/v1/providers")

    assert first.json()["metadata"]["retrieved_at"] != third.json()["metadata"]["retrieved_at"]
    assert first.headers["X-Wetterdienst-Retrieved-At"] != third.headers["X-Wetterdienst-Retrieved-At"]
    assert first.headers["ETag"] == third.headers["ETag"]
    assert second.status_code == 304


def test_providers_tag_covers_the_rest_of_the_answer(client: TestClient) -> None:
    """A provider asked for is another answer, and its tag is not the one of every provider."""
    every = client.get("/api/v1/providers")
    one = client.get("/api/v1/providers", params={"provider": "dwd"})

    assert one.headers["ETag"] != every.headers["ETag"]
    assert (
        client.get(
            "/api/v1/providers", params={"provider": "dwd"}, headers={"If-None-Match": every.headers["ETag"]}
        ).status_code
        == 200
    )


def test_weak_etag_leaves_out_only_what_it_is_told() -> None:
    """The tag is of the bytes without the texts given; another difference is another tag."""
    stamped = '{"retrieved_at":"A","rows":[1]}'
    assert weak_etag(stamped, ignoring=["A"]) == weak_etag('{"retrieved_at":"B","rows":[1]}', ignoring=["B"])
    assert weak_etag(stamped, ignoring=["A"]) != weak_etag('{"retrieved_at":"A","rows":[2]}', ignoring=["A"])
    assert weak_etag(stamped) != weak_etag(stamped, ignoring=["A"])
    assert weak_etag(stamped.encode()) == weak_etag(stamped)


# --- If-Modified-Since --------------------------------------------------------------------------------------------


def _http_date(moment: dt.datetime) -> str:
    return format_datetime(moment, usegmt=True)


@pytest.mark.parametrize(("path", "params"), _CATALOGUE)
def test_if_modified_since_is_answered_with_a_304_while_the_server_has_not_changed(
    client: TestClient, path: str, params: dict
) -> None:
    """The time sent back, or a later one, is a 304; an earlier one is the answer in full."""
    first = client.get(path, params=params)
    changed = dt.datetime.strptime(first.headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=dt.UTC)

    same = client.get(path, params=params, headers={"If-Modified-Since": first.headers["Last-Modified"]})
    later = client.get(path, params=params, headers={"If-Modified-Since": _http_date(changed + dt.timedelta(days=1))})
    earlier = client.get(
        path, params=params, headers={"If-Modified-Since": _http_date(changed - dt.timedelta(seconds=1))}
    )

    assert (same.status_code, later.status_code, earlier.status_code) == (304, 304, 200)
    assert same.content == b""
    assert _cache_headers(same) == _cache_headers(first)
    assert len(earlier.content) > 0
    assert earlier.headers["ETag"] == first.headers["ETag"]


@pytest.mark.parametrize("value", ["yesterday", "", "32 Jan 2026", "Thu, 05 Nov 2026"])
def test_a_date_that_is_not_one_is_ignored(client: TestClient, value: str) -> None:
    """An `If-Modified-Since` that is not an HTTP date is no condition: the answer in full."""
    response = client.get("/api/v1/glossary", params={"limit": 4}, headers={"If-Modified-Since": value})

    assert response.status_code == 200
    assert response.json()


def test_if_none_match_decides_when_it_is_sent_with_if_modified_since(client: TestClient) -> None:
    """A tag that does not match is a 200 whatever the date says, as the standard has it."""
    first = client.get("/api/v1/glossary", params={"limit": 4})

    response = client.get(
        "/api/v1/glossary",
        params={"limit": 4},
        headers={"If-None-Match": 'W/"other"', "If-Modified-Since": first.headers["Last-Modified"]},
    )
    matching = client.get(
        "/api/v1/glossary",
        params={"limit": 4},
        headers={"If-None-Match": first.headers["ETag"], "If-Modified-Since": "Mon, 01 Jan 1990 00:00:00 GMT"},
    )

    assert response.status_code == 200
    assert matching.status_code == 304


@pytest.mark.usefixtures("history_of_one_station")
def test_a_history_has_no_time_to_compare_with(client: TestClient) -> None:
    """No `Last-Modified` was sent, so an `If-Modified-Since` is not honoured: a 304 would claim a date nobody gave."""
    response = client.get(
        _HISTORY[0], params=_HISTORY[1], headers={"If-Modified-Since": "Fri, 01 Jan 2100 00:00:00 GMT"}
    )

    assert response.status_code == 200
    assert response.json()["histories"] == []


def test_the_time_of_the_catalogue_moves_with_the_env_file_that_every_request_reads(
    client: TestClient, tmp_path: Path
) -> None:
    """An edit of `.env` reaches the answers without a restart, so it is a change: the older copy is sent anew."""
    before = client.get("/api/v1/glossary", params={"limit": 4})
    assert (
        client.get(
            "/api/v1/glossary", params={"limit": 4}, headers={"If-Modified-Since": before.headers["Last-Modified"]}
        ).status_code
        == 304
    )

    env = tmp_path / ".env"
    env.write_text("WD_RESTAPI_TIMEOUT=60\n")
    edited = dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)
    os.utime(env, (edited.timestamp(), edited.timestamp()))

    after = client.get(
        "/api/v1/glossary", params={"limit": 4}, headers={"If-Modified-Since": before.headers["Last-Modified"]}
    )

    assert after.status_code == 200
    assert after.headers["Last-Modified"] == _http_date(edited.replace(microsecond=0))
    assert settings_changed_at() == edited.replace(microsecond=0)


# --- the history ----------------------------------------------------------------------------------------------------


@pytest.mark.usefixtures("history_of_one_station")
def test_a_history_answers_its_tag_with_a_304_and_leaves_out_the_time_of_the_answer(client: TestClient) -> None:
    """`retrieved_at` of the block differs between two answers, the tag does not, and a 304 has no body."""
    first = client.get(_HISTORY[0], params=_HISTORY[1])

    second = client.get(_HISTORY[0], params=_HISTORY[1], headers={"If-None-Match": first.headers["ETag"]})
    third = client.get(_HISTORY[0], params=_HISTORY[1])

    assert first.json()["metadata"]["retrieved_at"] != third.json()["metadata"]["retrieved_at"]
    assert first.headers["ETag"] == third.headers["ETag"]
    assert second.status_code == 304
    assert second.content == b""
    assert _cache_headers(second) == _cache_headers(first)


def test_a_history_that_changed_is_sent_again_whatever_the_client_holds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tag is of the content: once the source says something else the tag the client holds is no longer right."""
    _history_of(monkeypatch, [{"station_id": "02564", "name": "old"}])
    first = client.get(_HISTORY[0], params=_HISTORY[1])
    _history_of(monkeypatch, [{"station_id": "02564", "name": "renamed"}])

    second = client.get(_HISTORY[0], params=_HISTORY[1], headers={"If-None-Match": first.headers["ETag"]})
    third = client.get(_HISTORY[0], params=_HISTORY[1], headers={"If-None-Match": second.headers["ETag"]})

    assert second.status_code == 200
    assert second.json()["histories"] == [{"station_id": "02564", "name": "renamed"}]
    assert second.headers["ETag"] != first.headers["ETag"]
    assert third.status_code == 304


# --- what carries none ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "params", "status"),
    [
        pytest.param("/api/v1/coverage", {"provider": "dwd"}, 400, id="coverage-without-a-network"),
        pytest.param("/api/v1/coverage", {"provider": "nope", "network": "observation"}, 404, id="coverage-unknown"),
        pytest.param("/api/v1/providers", {"provider": "nope"}, 404, id="providers-unknown"),
        pytest.param("/api/v1/glossary", {"limit": "0"}, 422, id="glossary-invalid"),
        pytest.param(
            "/api/v1/history", {**_OBSERVATION, "network": "nope", "stations": "1"}, 404, id="history-unknown"
        ),
        pytest.param(
            "/api/v1/history",
            {"provider": "dwd", "network": "mosmix", "parameters": "hourly/large", "stations": "10147"},
            501,
            id="history-not-implemented",
        ),
        pytest.param("/api/v1/history", _HISTORY[1], 422, id="history-without-a-selection"),
        pytest.param("/api/v1/nowhere", {}, 404, id="unknown-path"),
    ],
)
def test_an_error_carries_no_cache_header_and_is_never_a_304(
    client: TestClient, path: str, params: dict, status: int
) -> None:
    """A refusal is not kept, and a tag or a date the client sends does not turn it into a 304."""
    if path.endswith("history") and status == 422:
        params = {key: value for key, value in params.items() if key != "stations"}
    response = client.get(
        path,
        params=params,
        headers={"If-None-Match": "*", "If-Modified-Since": "Fri, 01 Jan 2100 00:00:00 GMT"},
    )

    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert _cache_headers(response) == {}


def test_a_failure_of_the_history_carries_no_cache_header(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 500 from inside the handler is no answer to keep either."""

    def fail(*_args: object, **_kwargs: object) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(restapi, "get_stations", fail)

    response = client.get(_HISTORY[0], params=_HISTORY[1], headers={"If-None-Match": "*"})

    assert response.status_code == 500
    assert _cache_headers(response) == {}


def test_a_refused_host_carries_no_cache_header(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The middleware's own 400 is not kept."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "localhost")

    response = client.get("/api/v1/glossary", headers={"Host": "elsewhere.example"})

    assert response.status_code == 400
    assert _cache_headers(response) == {}


@pytest.mark.parametrize("fmt", ["json", "csv", "ndjson"])
def test_values_are_not_cached(client: TestClient, monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """Values are not stable by themselves, a provider revises its data: no header, whatever the format and stream."""
    _stub_result(monkeypatch, "/api/values")

    response = client.get(
        "/api/v1/values",
        params={**_OBSERVATION, "stations": "01048", "format": fmt},
        headers={"If-None-Match": "*"},
    )

    assert response.status_code == 200
    assert _cache_headers(response) == {}


def test_a_stream_is_not_cached(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """NDJSON and CSV are sent station by station, before the answer is known: no tag can be made of them."""
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])

    for fmt in ("ndjson", "csv"):
        response = client.get("/api/v1/values", params={**_OBSERVATION, "stations": "01048", "format": fmt})
        assert response.status_code == 200
        assert _cache_headers(response) == {}


@pytest.mark.parametrize("endpoint", ["/api/v1/interpolate", "/api/v1/summarize"])
def test_a_point_is_not_cached(client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    """An estimate is made from values that are not kept, so nothing about it is."""
    _stub_result(monkeypatch, endpoint.replace("/v1", ""))

    response = client.get(
        endpoint,
        params={**_OBSERVATION, "station": "01048", "timestamp": "2020-06-30"},
        headers={"If-None-Match": "*"},
    )

    assert response.status_code == 200
    assert _cache_headers(response) == {}


def test_stations_are_not_cached(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A list of stations changes with the provider's catalogue, which no route here is told about."""
    stations = _values_result_of_shape("long").stations
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)

    response = client.get("/api/v1/stations", params={**_OBSERVATION, "all": "true"}, headers={"If-None-Match": "*"})

    assert response.status_code == 200
    assert _cache_headers(response) == {}


@pytest.mark.usefixtures("figure_draws_itself")
def test_the_stripes_are_not_cached(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stripes of a station end with the year being recorded, and the image is drawn from them."""

    class _Figure:
        def to_image(self, *_args: object, **_kwargs: object) -> bytes:
            return b"image"

    _stub_stripes_station(monkeypatch, "temperature", [1.0, 2.0])
    monkeypatch.setattr(restapi, "_draw_stripes", lambda _data, _request: _Figure())

    values = client.get("/api/v1/stripes/values", params={"kind": "temperature", "station": "01048"})
    image = client.get("/api/v1/stripes/image", params={"kind": "temperature", "station": "01048", "format": "png"})

    assert (values.status_code, image.status_code) == (200, 200)
    assert _cache_headers(values) == {}
    assert _cache_headers(image) == {}


@pytest.mark.parametrize("path", ["/api/v1/version", "/api/v1/settings", "/health", "/ready", "/robots.txt"])
def test_the_rest_of_the_server_sends_no_validators(client: TestClient, path: str) -> None:
    """Only the four routes are kept; the others say nothing about it (a probe says `no-store`)."""
    response = client.get(path)

    assert response.status_code == 200
    assert not {"etag", "last-modified", "expires"} & set(response.headers)
    assert response.headers.get("cache-control") in (None, "no-store")


def test_the_openapi_document_declares_the_cache_headers_and_the_304(client: TestClient) -> None:
    """The four routes document the headers of their 200 and the 304; no other route has a 304."""
    document = client.get("/openapi.json").json()
    declared = {"/api/v1/coverage", "/api/v1/providers", "/api/v1/glossary", "/api/v1/history"}

    for path, item in document["paths"].items():
        responses = item["get"]["responses"]
        if path in declared:
            assert {"ETag", "Cache-Control"} <= set(responses["200"]["headers"]), path
            assert set(responses["304"]["headers"]) == set(responses["200"]["headers"]), path
            assert ("Last-Modified" in responses["200"]["headers"]) == (path != "/api/v1/history"), path
        else:
            assert "304" not in responses, path


# --- readiness ----------------------------------------------------------------------------------------------------


def test_a_server_that_can_serve_is_ready(client: TestClient) -> None:
    """`/ready` answers `ready`, and `/health` is as it was."""
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/health").json() == {"status": "OK"}


def test_a_server_whose_settings_are_invalid_is_not_ready_but_alive(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A setting that went bad after the start makes every data request a 500: not ready, and not for a restart."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "a-secret-that-is-no-number")

    with caplog.at_level("WARNING"):
        response = client.get("/ready", headers={"X-Request-ID": "ready-1"})

    assert response.status_code == 503
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:not-ready"
    assert body["checks"] == ["settings"]
    assert body["request_id"] == "ready-1"
    assert response.headers["Retry-After"] == "30"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "a-secret-that-is-no-number" not in response.text
    # the log says which variable, and not its value
    assert "WD_RESTAPI_TIMEOUT" in caplog.text
    assert "a-secret-that-is-no-number" not in caplog.text
    assert client.get("/health").status_code == 200


def test_a_cache_directory_that_cannot_be_used_is_not_ready(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A cache directory that is a file, or lies below one, fails every download; the path is not told."""
    blocker = tmp_path / "blocker"
    blocker.write_text("a file")

    for directory in (blocker, blocker / "cache"):
        monkeypatch.setenv("WD_CACHE_DIR", str(directory))
        response = client.get("/ready")
        assert response.status_code == 503, directory
        assert response.json()["checks"] == ["cache"]
        assert str(tmp_path) not in response.text


def test_a_cache_directory_that_does_not_exist_yet_is_ready_where_it_can_be_made(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The library makes the directory on its first download: a missing one below a writable one is ready."""
    directory = tmp_path / "not" / "yet"
    monkeypatch.setenv("WD_CACHE_DIR", str(directory))

    assert client.get("/ready").status_code == 200
    assert not directory.exists()


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="needs permissions")
def test_a_cache_directory_nobody_may_write_to_is_not_ready(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A directory that exists and is read-only fails every download."""
    directory = tmp_path / "read-only"
    directory.mkdir(mode=0o500)
    monkeypatch.setenv("WD_CACHE_DIR", str(directory))
    try:
        assert client.get("/ready").status_code == 503
    finally:
        directory.chmod(0o700)


def test_a_disabled_cache_needs_no_directory(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With `WD_CACHE_DISABLE` nothing is written, so the directory does not matter."""
    blocker = tmp_path / "blocker"
    blocker.write_text("a file")
    monkeypatch.setenv("WD_CACHE_DIR", str(blocker))
    monkeypatch.setenv("WD_CACHE_DISABLE", "true")

    assert client.get("/ready").status_code == 200


def test_readiness_asks_no_provider_and_needs_no_credential(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider that is down is no reason to leave the pool: nothing is fetched, and no credential is read."""

    def forbidden(*_args: object, **_kwargs: object) -> None:
        msg = "readiness reached for a provider"
        raise AssertionError(msg)

    monkeypatch.setattr("wetterdienst.util.network.download_file", forbidden)
    monkeypatch.setattr("wetterdienst.util.network.list_remote_files_fsspec", forbidden)
    monkeypatch.setattr(restapi, "get_stations", forbidden)

    assert client.get("/ready").status_code == 200


def test_readiness_is_a_problem_kind_with_its_status_and_a_probe_not_a_tool() -> None:
    """The kind is declared with its status; `/ready` is documented under the `Server` tag with its 503."""
    assert PROBLEMS[ProblemKind.NOT_READY].status == 503
    document = restapi.app.openapi()
    operation = document["paths"]["/ready"]["get"]

    assert operation["tags"] == ["Server"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Ready"
    }
    assert operation["responses"]["503"] == {"$ref": "#/components/responses/Unavailable"}
    assert "ready" not in {name for name in document["paths"] if name.startswith("/api")}
