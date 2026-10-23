# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The operating contract of the REST API (GH-3065): limits, streaming, timeout, problem types, request id.

Offline: the selection of the stations and the reader that walks them are stood in for, and the request goes through the
app's routes, middleware and handlers with a client.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
import threading
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
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import count_readings
from wetterdienst.settings import check_settings
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.deprecation import Deprecation, deprecated_route, deprecation_headers, mark_deprecated
from wetterdienst.ui.limits import estimate_point_rows, estimate_rows
from wetterdienst.ui.middleware import RequestContextMiddleware
from wetterdienst.ui.problems import PROBLEMS, ProblemKind, request_id_from
from wetterdienst.ui.render import ValuesSettings, render
from wetterdienst.util.response_warnings import _COUNTED, _RECORDED, begin_response, warn_response

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from wetterdienst.model.result import StationsResult, ValuesResult

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


def _selection_of(
    n: int, *, start: dt.datetime | None = None, end: dt.datetime | None = None, unbounded: bool = False
) -> pl.DataFrame:
    """Give the selection of `n` stations of the daily climate summary, with the record they bound it by.

    A month of 2020 unless the record is given; `unbounded` leaves it out, as a provider that publishes none does.
    """
    base = _values_result_of_shape("long").stations.df.filter(pl.col("dataset") == "climate_summary")
    frame = pl.concat([base.with_columns(pl.lit(f"{i:05d}").alias("station_id")) for i in range(n)])
    if start is None and not unbounded:
        start, end = dt.datetime(2020, 1, 1, tzinfo=dt.UTC), dt.datetime(2020, 1, 31, tzinfo=dt.UTC)
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
    # the web app answers kinds of its own, which the backend cannot: when it cannot reach the backend, and when
    # a client is over its rate limit
    app_kinds = {"backend-unreachable", "rate-limited"}
    documented = set(re.findall(r"`urn:wetterdienst:problem:([a-z-]+)`", docs)) - app_kinds

    for app_kind in app_kinds:
        assert f"urn:wetterdienst:problem:{app_kind}" in docs, app_kind
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
    ranked = replace(base.stations, df=_selection_of(50), _stations_filter=StationsFilter.BY_RANK, _rank=2)
    monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: ranked)
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: ranked)

    assert (
        client.get("/api/v1/values", params={**_OBSERVATION, "latitude": 51, "longitude": 13, "rank": 2}).status_code
        == 200
    )
    ranked = replace(ranked, _rank=3)
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
    # a station whose record is not published, in a request with no window, is counted from where the periods of
    # its dataset (historical and recent) put the start of a record: 1 January 1950, to now
    # (the end of the record is known here, so that the count does not move with the day)
    ended = _selection_of(2, unbounded=True).with_columns(
        pl.lit(None, pl.Datetime("us", "UTC")).alias("start_timestamp"),
        pl.lit(dt.datetime(2020, 12, 31, tzinfo=dt.UTC), pl.Datetime("us", "UTC")).alias("end_timestamp"),
    )
    unbounded = replace(base, request=DwdObservationRequest(parameters=parameters), df=ended)
    days = (dt.date(2020, 12, 31) - dt.date(1950, 1, 1)).days + 1
    assert estimate_rows(unbounded) == 2 * days * 2
    # given a start, the window holds, as for a station with a record
    windowed = replace(unbounded, request=request)
    assert estimate_rows(windowed) == 2 * 10 * 2
    assert estimate_point_rows(request.parameters, request.start, request.end) == 10 * 2
    assert estimate_point_rows(request.parameters, None, None) == 0


def _long_running_stations(
    periods: str | list[str] | None, parameters: str = "daily/kl", *, start: dt.datetime | None = None
) -> StationsResult:
    """Give two stations that have recorded since 1934 (or `start`) of the dataset of the parameters, read as asked."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    request = DwdObservationRequest(parameters=parameters, periods=periods)
    dataset = request.parameters[0].dataset
    record = {"start": start or dt.datetime(1934, 1, 1, tzinfo=dt.UTC), "end": dt.datetime(2026, 10, 20, tzinfo=dt.UTC)}
    df = _selection_of(2, **record).with_columns(
        pl.lit(dataset.resolution.name).alias("resolution"), pl.lit(dataset.name.lower()).alias("dataset")
    )
    return replace(_values_result_of_shape("long").stations, request=request, df=df)


def test_the_rows_of_a_request_for_the_recent_release_are_not_those_of_the_whole_record() -> None:
    """`periods=recent` reads about 500 days, whatever a station has recorded since; the others read the record."""
    parameters = 14
    record_days = (dt.date(2026, 10, 20) - dt.date(1934, 1, 1)).days + 1

    # the margin over the 500 days DWD's recent release holds: two years, for each of the 14 parameters
    assert estimate_rows(_long_running_stations("recent")) == 2 * 732 * parameters
    for periods in (None, "historical", ["historical", "recent"]):
        assert estimate_rows(_long_running_stations(periods)) == 2 * record_days * parameters


@pytest.mark.parametrize(
    ("parameters", "span_days"),
    [
        # no recent directory of their own: the record is read whatever the period
        ("hourly/solar", None),
        ("hourly/urban_temperature_air", None),
        # the recent release holds years: 1 and 5 minutes from 2023 and growing, annual five years
        ("1_minute/precipitation", 366 * 8),
        ("5_minutes/precipitation", 366 * 8),
        ("annual/climate_summary", 366 * 6),
    ],
)
def test_the_recent_release_is_counted_by_what_the_dataset_holds(parameters: str, span_days: int | None) -> None:
    """Only a dataset whose `recent` release reaches back two years at most is counted from two years (GH-3249)."""
    end = dt.datetime(2026, 10, 20, tzinfo=dt.UTC)
    whole = estimate_rows(_long_running_stations(None, parameters, start=dt.datetime(1981, 1, 1, tzinfo=dt.UTC)))
    recent = estimate_rows(_long_running_stations("recent", parameters, start=dt.datetime(1981, 1, 1, tzinfo=dt.UTC)))

    if span_days is None:
        assert recent == whole
    else:
        # the record of a station that began where the release is assumed to begin
        began = end - dt.timedelta(days=span_days)
        assert recent == estimate_rows(_long_running_stations(None, parameters, start=began))
        assert recent < whole


def test_the_datasets_that_hold_years_of_recent_data_are_counted_from_their_record() -> None:
    """The recent directories of the monthly derived data (2018 on) and of phenology's recent-only data hold years."""
    from wetterdienst.provider.dwd.derived import DwdDerivedRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.phenology import DwdPhenologyRequest  # noqa: PLC0415

    end = dt.datetime(2026, 10, 20, tzinfo=dt.UTC)
    base = _values_result_of_shape("long").stations
    for request in (
        DwdDerivedRequest(parameters="monthly/climate_correction_factor", periods="recent"),
        DwdPhenologyRequest(parameters="annual/annual_beet", periods="recent"),
    ):
        dataset = request.parameters[0].dataset
        assert request._recent_span_of(dataset) is None  # noqa: SLF001
        # a station that publishes no record: counted from the start of the oldest archives, not from two years back
        unbounded = _selection_of(1, unbounded=True).with_columns(
            pl.lit(dataset.resolution.name).alias("resolution"),
            pl.lit(dataset.name.lower()).alias("dataset"),
            pl.lit(None, pl.Datetime("us", "UTC")).alias("start_timestamp"),
            pl.lit(end, pl.Datetime("us", "UTC")).alias("end_timestamp"),
        )
        rows = estimate_rows(replace(base, request=request, df=unbounded))
        readings = count_readings(dataset.resolution.value, dt.datetime(1950, 1, 1, tzinfo=dt.UTC), end)
        assert rows == readings * len(request.parameters)
    # the daily derived data and the phenology files are not the only ones: the span is the default elsewhere
    daily = DwdDerivedRequest(parameters="daily/soil", periods="recent")
    assert daily._recent_span_of(daily.parameters[0].dataset) == dt.timedelta(days=731)  # noqa: SLF001


def test_a_provider_that_reads_no_periods_is_not_narrowed_on_a_recent_only_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The periods a dataset publishes are not periods the request chose, unless the provider reads per period."""
    from wetterdienst.provider.dwd.derived import DwdDerivedRequest  # noqa: PLC0415

    end = dt.datetime(2026, 10, 20, tzinfo=dt.UTC)
    request = DwdDerivedRequest(parameters="monthly/climate_correction_factor")
    dataset = request.parameters[0].dataset
    assert set(dataset.periods) == {Period.RECENT}
    monkeypatch.setattr(DwdDerivedRequest, "_selects_by_period", False)
    monkeypatch.setattr(DwdDerivedRequest, "_recent_span_of", lambda _self, _dataset: dt.timedelta(days=731))
    stations = replace(
        _values_result_of_shape("long").stations,
        request=request,
        df=_selection_of(1, start=dt.datetime(2010, 1, 1, tzinfo=dt.UTC), end=end).with_columns(
            pl.lit(dataset.resolution.name).alias("resolution"), pl.lit(dataset.name.lower()).alias("dataset")
        ),
    )

    assert estimate_rows(stations) == count_readings(
        dataset.resolution.value, dt.datetime(2010, 1, 1, tzinfo=dt.UTC), end
    )


def test_each_dataset_of_a_request_is_narrowed_by_its_own_span() -> None:
    """`daily/kl` and `daily/solar` read for `recent`: the first from two years, the second from its record."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    kl = _long_running_stations("recent", "daily/kl")
    solar = _long_running_stations("recent", "daily/solar")
    request = DwdObservationRequest(parameters=["daily/kl", "daily/solar"], periods="recent")
    both = replace(kl, request=request, df=pl.concat([kl.df, solar.df]))

    assert estimate_rows(both) == estimate_rows(kl) + estimate_rows(solar)
    assert estimate_rows(kl) == 2 * 732 * 14
    assert estimate_rows(solar) > 2 * 732 * len(solar.parameters)


@pytest.mark.parametrize(
    ("parameters", "span_days"),
    [
        # measured on the real `now` files (see `DwdObservationRequest._now_span_of`): up to about 55 hours
        ("1_minute/precipitation", 5),
        ("5_minutes/precipitation", 5),
        # the previous day and today: up to 48 hours
        ("10_minutes/temperature_air", 4),
        ("10_minutes/precipitation", 4),
        ("10_minutes/solar", 4),
        ("10_minutes/urban_temperature_air", 4),
    ],
)
def test_the_rows_of_a_request_for_the_now_release_are_those_of_its_span(parameters: str, span_days: int) -> None:
    """`periods=now` reads a day or two, whatever a station has recorded since (GH-3271)."""
    end = dt.datetime(2026, 10, 20, tzinfo=dt.UTC)
    start = dt.datetime(1993, 1, 1, tzinfo=dt.UTC)
    now = _long_running_stations("now", parameters, start=start)
    dataset = now.parameters[0].dataset

    readings = count_readings(dataset.resolution.value, end - dt.timedelta(days=span_days), end)
    assert estimate_rows(now) == 2 * readings * len(now.parameters)
    # the record counted whole is what the request was refused for
    for periods in (None, "historical", ["historical", "now"]):
        assert estimate_rows(_long_running_stations(periods, parameters, start=start)) > 1000 * estimate_rows(now)


@pytest.mark.parametrize(
    ("parameters", "readings_held"),
    [
        # what the largest `now` file can hold, from the measurement (`DwdObservationRequest._now_span_of`): about 55
        # hours of 1 and 5 minute readings (2,846 and 588 were the most seen), 48 of 10 minute ones (180 at most seen)
        ("1_minute/precipitation", 55 * 60),
        ("5_minutes/precipitation", 55 * 12),
        ("10_minutes/precipitation", 48 * 6),
        ("10_minutes/temperature_air", 48 * 6),
    ],
)
def test_the_margin_over_the_now_files_measured_is_twice_what_they_held(parameters: str, readings_held: int) -> None:
    """A `now` file that holds more than the estimate does would let a request through that is over the limit."""
    stations = _long_running_stations("now", parameters)
    two_stations, margin = 2, 2
    assert estimate_rows(stations) >= margin * two_stations * readings_held * len(stations.parameters)


def test_a_request_for_the_now_release_is_counted_by_the_widest_period_it_reads() -> None:
    """With `recent` it reads that release, with `historical` the record: `now` narrows only when it is alone."""
    parameters = "10_minutes/temperature_air"
    recent = estimate_rows(_long_running_stations("recent", parameters))
    assert estimate_rows(_long_running_stations(["recent", "now"], parameters)) == recent
    assert estimate_rows(_long_running_stations("now", parameters)) < recent
    assert estimate_rows(_long_running_stations(["historical", "now"], parameters)) > recent


def test_a_provider_with_no_span_for_its_now_release_is_counted_from_its_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """None says the release is not measured: the request is counted as it was before (GH-3271)."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    monkeypatch.setattr(DwdObservationRequest, "_now_span_of", lambda _self, _dataset: None)
    assert estimate_rows(_long_running_stations("now", "10_minutes/temperature_air")) == estimate_rows(
        _long_running_stations(None, "10_minutes/temperature_air")
    )


def test_a_window_inside_the_periods_read_is_what_bounds_the_rows() -> None:
    """The narrower of the window of the request and the periods it reads counts."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    stations = _long_running_stations("recent")
    window = {"start": dt.datetime(2026, 10, 1, tzinfo=dt.UTC), "end": dt.datetime(2026, 10, 10, tzinfo=dt.UTC)}
    inside = replace(stations, request=DwdObservationRequest(parameters="daily/kl", periods="recent", **window))
    assert estimate_rows(inside) == 2 * 10 * 14

    # the recent release holds none of 2010, but the window is what is counted, an upper bound
    old = {"start": dt.datetime(2010, 1, 1, tzinfo=dt.UTC), "end": dt.datetime(2010, 1, 10, tzinfo=dt.UTC)}
    outside = replace(stations, request=DwdObservationRequest(parameters="daily/kl", periods="recent", **old))
    assert estimate_rows(outside) == 2 * 10 * 14


def test_a_provider_that_reads_no_periods_is_counted_from_its_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """The periods of a provider that does not read per period narrow nothing, so they narrow no estimate."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    stations = _long_running_stations("recent")
    record_days = (dt.date(2026, 10, 20) - dt.date(1934, 1, 1)).days + 1
    monkeypatch.setattr(DwdObservationRequest, "_selects_by_period", False)
    assert estimate_rows(stations) == 2 * record_days * 14


def test_the_documented_values_request_for_the_recent_release_passes_the_default_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two long-running stations, `periods=recent`: the first sample of the docs, answered on a default server."""
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=_long_running_stations(None).df)
    asked: list[object] = []

    def stations_of(**kwargs: Any) -> StationsResult:  # noqa: ANN401
        """Give the two stations for the periods the route passed on."""
        periods = kwargs["request"].periods
        asked.append(periods)
        return _long_running_stations(periods or None)

    monkeypatch.setattr(restapi, "get_stations", stations_of)
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", stations_of)

    assert client.get("/api/v1/values", params={**_STATIONS, "periods": "recent"}).status_code == 200
    assert asked[-1], "the periods of the query reach the selection"

    # the same stations read as a whole are about 700,000 rows (GH-3249): still refused
    response = client.get("/api/v1/values", params=_STATIONS)
    assert response.status_code == 400
    assert response.json()["limit"] == "rows"


def test_a_values_request_for_the_now_release_passes_the_default_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two long-running stations, `periods=now`, 10 minute air temperature: refused as the whole record (GH-3271)."""
    parameters = "10_minutes/temperature_air"
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=_long_running_stations(None).df)

    def stations_of(**kwargs: Any) -> StationsResult:  # noqa: ANN401
        """Give the two stations for the periods the route passed on."""
        return _long_running_stations(
            kwargs["request"].periods or None, parameters, start=dt.datetime(1993, 1, 1, tzinfo=dt.UTC)
        )

    monkeypatch.setattr(restapi, "get_stations", stations_of)
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", stations_of)
    query = {**_STATIONS, "parameters": parameters}

    assert client.get("/api/v1/values", params={**query, "periods": "now"}).status_code == 200
    # the same stations read as a whole are about 21 million rows: still refused
    response = client.get("/api/v1/values", params=query)
    assert response.status_code == 400
    assert response.json()["limit"] == "rows"


def test_the_start_of_an_unpublished_record_is_assumed_from_the_periods_of_the_dataset() -> None:
    """Historical data from 1950, recent data two years and current data two days back, a forecast has none."""
    from wetterdienst.metadata.period import Period  # noqa: PLC0415
    from wetterdienst.ui.limits import _assumed_start  # noqa: PLC0415

    end = dt.datetime(2024, 6, 1, tzinfo=dt.UTC)

    assert _assumed_start([Period.HISTORICAL, Period.RECENT], end) == dt.datetime(1950, 1, 1, tzinfo=dt.UTC)
    assert _assumed_start([Period.RECENT, Period.NOW], end) == dt.datetime(2022, 6, 1, tzinfo=dt.UTC)
    assert _assumed_start([Period.NOW], end) == dt.datetime(2024, 5, 30, tzinfo=dt.UTC)
    assert _assumed_start([Period.FUTURE], end) is None


def test_a_request_for_a_provider_without_record_bounds_is_held_to_the_row_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a `timestamp`, stations that publish no record are no longer free of the row limit (GH-3089)."""
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "1000")
    _stub_stream(monkeypatch, [_values_result_of_shape("long")], stations_df=_selection_of(1, unbounded=True))

    response = client.get("/api/v1/values", params=_STATIONS)

    assert response.status_code == 400
    assert response.json()["type"] == "urn:wetterdienst:problem:limit-exceeded"
    assert response.json()["limit"] == "rows"


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
    # the handler waits for the end of the test, so that an answer in hand proves the 504 did not wait for it
    release, _begun, ended = _blocking_values(monkeypatch)

    try:
        response = client.get("/api/v1/values", params=_VALUES, headers={"X-Request-ID": "slow-1"})
        still_running = list(ended)
    finally:
        release.set()

    assert still_running == []
    assert response.status_code == 504
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:request-timeout"
    assert "0.3 seconds" in body["detail"]
    assert body["request_id"] == "slow-1"
    assert response.headers["Retry-After"] == "30"
    assert response.headers["X-Request-ID"] == "slow-1"


def test_the_timeout_leaves_the_rest_alone(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The index, the health check and a request in time are not held to it, and 0 switches it off."""
    # a timeout that no runner reaches: the request in time is a request that has nothing to do with it
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "30")
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
    """A stream may outlast the timeout; a chunk that takes longer ends it with a `request-timeout` error.

    The one gap that may not exceed the timeout is a pause of a quarter of it, so a runner that is slow by a
    factor of four still passes (a timeout of half a second with a pause of 0.35 s did not, GH-3251). The chunk
    that is too late is not a longer sleep but one that waits for the end of the test, which is as late as any
    timeout can make it, however fast the runner is.
    """
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "2")
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [])
    never = threading.Event()

    def query(_reader: object) -> Iterator[ValuesResult]:
        yield _chunk_of(result, "01048")
        time.sleep(0.5)
        yield _chunk_of(result, "01049")
        never.wait(30)
        yield _chunk_of(result, "01050")

    monkeypatch.setattr(type(result.stations.request)._values, "query", query)  # noqa: SLF001

    try:
        lines = _lines(client.get("/api/v1/values", params={**_VALUES, "format": "ndjson"}))
    finally:
        never.set()

    ids = [line.get("station_id") for line in lines[1:-1]]
    assert set(ids) == {"01048", "01049"}
    assert lines[-1]["error"]["type"] == "urn:wetterdienst:problem:request-timeout"
    assert lines[-1]["error"]["status"] == 504


def test_a_csv_stream_that_is_too_slow_is_cut(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """CSV has no place to say the timeout: the stream stops, and the connection is cut."""
    # the first chunk must come within the timeout, the second never does: it waits for the end of the test, which
    # is as late as any timeout can make it (see the stream above)
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "2")
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [])
    never = threading.Event()

    def query(_reader: object) -> Iterator[ValuesResult]:
        yield _chunk_of(result, "01048")
        never.wait(30)
        yield _chunk_of(result, "01049")

    monkeypatch.setattr(type(result.stations.request)._values, "query", query)  # noqa: SLF001

    try:
        response = client.get("/api/v1/values", params={**_VALUES, "format": "csv"})
    finally:
        never.set()

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


# --- the cap on requests served at once ---------------------------------------------------------------------------


def _async_client() -> Any:  # noqa: ANN401
    """Give a client that runs the app in the loop of the test, so that requests are in flight together."""
    import httpx2  # noqa: PLC0415

    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=restapi.app, raise_app_exceptions=False), base_url="http://testserver"
    )


def _blocking_values(monkeypatch: pytest.MonkeyPatch) -> tuple[threading.Event, list[str], list[str]]:
    """Make `values` wait in its thread until the test lets it go.

    Returns the event that lets it go, the handlers that have begun and the handlers that have ended.
    """
    release, begun, ended = threading.Event(), [], []

    def blocked(**_kwargs: object) -> None:
        begun.append("begun")
        release.wait(10)
        ended.append("done")
        msg = "released"
        raise exceptions.RequestError(msg)

    monkeypatch.setattr(restapi, "get_values", blocked)
    return release, begun, ended


async def _until(condition: Callable[[], bool], what: str, seconds: float = 60) -> None:
    """Wait for a condition of the app, which takes as long as the runner needs: the deadline is for a hang only."""
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, f"no {what} within {seconds:g} seconds"
        await asyncio.sleep(0.005)


async def _first_served(client: Any) -> int:  # noqa: ANN401
    """Ask until the request is no longer refused for want of a place, and give the status of the one that was not."""
    deadline = time.monotonic() + 60
    while (status := (await client.get("/api/v1/values", params=_VALUES)).status_code) == 503:
        assert time.monotonic() < deadline, "the place was not given back within 60 seconds"
        await asyncio.sleep(0.01)
    return status


def test_the_cap_is_a_setting_with_a_documented_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """32 requests by default, `WD_RESTAPI_MAX_CONCURRENT` sets it and 0 switches it off; it is reported by version."""
    assert Settings().restapi_max_concurrent == 32
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "5")
    assert Settings().restapi_max_concurrent == 5
    assert restapi.limits_of(Settings()).max_concurrent == 5
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "-1")
    with pytest.raises(ValueError, match="restapi_max_concurrent"):
        Settings()


def test_a_request_past_the_cap_is_a_503_that_says_to_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """With two requests being served, the third is not started: a `server-busy` problem with `Retry-After`."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "2")
    release, begun, _ended = _blocking_values(monkeypatch)

    async def run() -> tuple[list[Any], Any, Any, Any]:
        async with _async_client() as client:
            first = [asyncio.ensure_future(client.get("/api/v1/values", params=_VALUES)) for _ in range(2)]
            await _until(lambda: len(begun) == 2, "handler of the two requests being served")
            busy = await client.get("/api/v1/values", params=_VALUES, headers={"X-Request-ID": "busy-1"})
            # what is not counted is served: the health check, the index
            health = await client.get("/health")
            index = await client.get("/")
            release.set()
            return await asyncio.gather(*first), busy, health, index

    try:
        served, busy, health, index = asyncio.run(run())
    finally:
        release.set()

    assert busy.status_code == 503
    assert busy.json()["type"] == "urn:wetterdienst:problem:server-busy"
    assert busy.json()["request_id"] == "busy-1"
    assert busy.headers["Retry-After"] == "30"
    assert "2 requests" in busy.json()["detail"]
    assert (health.status_code, index.status_code) == (200, 200)
    assert [response.status_code for response in served] == [400, 400]


def test_a_cap_of_zero_is_no_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """0 switches the cap off: more requests than the default cap are all served."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "0")
    release, begun, _ended = _blocking_values(monkeypatch)

    async def run() -> list[int]:
        async with _async_client() as client:
            requests = [asyncio.ensure_future(client.get("/api/v1/values", params=_VALUES)) for _ in range(40)]
            # all of them are in their handlers together, none was refused or waits for a place
            await _until(lambda: len(begun) == 40, "handler of the 40 requests being served")
            release.set()
            return [response.status_code for response in await asyncio.gather(*requests)]

    try:
        statuses = asyncio.run(run())
    finally:
        release.set()

    assert statuses == [400] * 40


def test_a_request_that_timed_out_keeps_its_place_until_its_thread_is_done(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 504 is sent at the timeout, and the cap still counts the request: the thread it left running is its own."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "1")
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.2")
    release, _begun, ended = _blocking_values(monkeypatch)

    async def run() -> tuple[int, int, list[str], int]:
        async with _async_client() as client:
            timed_out = await client.get("/api/v1/values", params=_VALUES)
            # the answer is out, and the thread is still running
            refused = await client.get("/api/v1/values", params=_VALUES)
            still_running = list(ended)
            # from here on the timeout is no part of the test: the request that follows must not be answered with a
            # 504 because a slow runner took longer than 0.2 seconds to hand it to a thread
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            release.set()
            # the thread ends, and the place is free again: the next request is served (and refused by the stub)
            return timed_out.status_code, refused.status_code, still_running, await _first_served(client)

    try:
        timed_out, refused, still_running, served = asyncio.run(run())
    finally:
        release.set()

    assert (timed_out, refused) == (504, 503)
    assert still_running == []
    assert served == 400


def test_a_request_that_fails_after_its_timeout_gives_its_place_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The failure of the dropped request is logged as a server error, and the next request is served."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "1")
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.2")
    begun, fail = threading.Event(), threading.Event()

    def late(**_kwargs: object) -> None:
        begun.set()
        fail.wait(10)
        raise RuntimeError

    monkeypatch.setattr(restapi, "get_values", late)

    async def run() -> tuple[int, int]:
        async with _async_client() as client:
            first = await client.get("/api/v1/values", params=_VALUES)
            # the 504 is out, and the handler of the request may be yet to begin: it must call `late`, not what follows
            await _until(begun.is_set, "handler of the request that timed out")
            # the timeout is no part of the rest of the test, see above
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            monkeypatch.setattr(
                restapi, "get_values", lambda **_kwargs: (_ for _ in ()).throw(exceptions.RequestError("x"))
            )
            fail.set()
            return first.status_code, await _first_served(client)

    try:
        with caplog.at_level("WARNING"):
            assert asyncio.run(run()) == (504, 400)
    finally:
        fail.set()

    assert "failed with a 500: internal-error" in caplog.text


def test_a_request_in_time_gives_its_place_back(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Many requests one after the other are served with a cap of one."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "1")
    _stub_result(monkeypatch, "/api/values")

    assert [client.get("/api/v1/values", params=_VALUES).status_code for _ in range(5)] == [200] * 5


# --- the allowed hosts --------------------------------------------------------------------------------------------


def test_every_host_is_answered_to_by_default(client: TestClient) -> None:
    """Without `WD_RESTAPI_ALLOWED_HOSTS`, the server behaves as it did: a name it was not given is served."""
    assert Settings().restapi_allowed_hosts == ()
    assert client.get("/api/version", headers={"Host": "evil.example"}).status_code == 200
    assert (
        client.get("/api/version", headers={"Host": "evil.example", "Origin": "https://evil.example"}).status_code
        == 200
    )


def test_the_allowed_hosts_are_a_comma_separated_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """The variable is a list with commas; the names are normalised, and a malformed entry names the variable."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "Localhost, 127.0.0.1 ,[::1],*.example.org:8080,,")
    assert Settings().restapi_allowed_hosts == ("localhost", "127.0.0.1", "[::1]", "*.example.org:8080")
    assert Settings(restapi_allowed_hosts=["a.example", "A.example"]).restapi_allowed_hosts == ("a.example",)

    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "localhost,http://example.org")
    with pytest.raises(ValueError, match="restapi_allowed_hosts"):
        Settings()
    assert any(line.startswith("WD_RESTAPI_ALLOWED_HOSTS is invalid") for line in check_settings())


def test_a_host_that_is_not_listed_is_a_400_problem(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rebinding page reaches the server with its own name in `Host`; every route refuses it, but the health check."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")

    for path in ("/api/version", "/api/v1/version", "/api/v1/coverage", "/", "/robots.txt", "/mcp/v1"):
        refused = client.get(path, headers={"Host": "rebind.evil.example:7890", "X-Request-ID": "host-1"})
        assert refused.status_code == 400, path
        body = refused.json()
        assert body["type"] == "urn:wetterdienst:problem:host-not-allowed"
        assert body["request_id"] == "host-1"
        assert "rebind.evil.example" not in refused.text
        assert refused.headers["content-type"].startswith("application/problem+json")
    for host in ("localhost", "localhost:7890", "LOCALHOST:3000", "127.0.0.1:7890", "[::1]:7890"):
        assert client.get("/api/version", headers={"Host": host}).status_code == 200, host
    assert client.get("/health", headers={"Host": "service.internal"}).status_code == 200


def test_an_unlisted_host_is_refused_before_anything_is_fetched(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The handler is not called for a request the host check refused."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "localhost")
    called = []
    monkeypatch.setattr(restapi, "get_values", lambda **_kwargs: called.append(1))

    response = client.get("/api/v1/values", params=_VALUES, headers={"Host": "evil.example"})

    assert response.status_code == 400
    assert called == []


def _serve_on(listen: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Run `start_service` with a stand-in for uvicorn, which takes the request a server would and says what it got."""
    seen: dict[str, Any] = {}

    class _Uvicorn:
        @staticmethod
        def run(**kwargs: Any) -> None:  # noqa: ANN401
            seen.update(kwargs)
            client = TestClient(restapi.app)
            for name, host in (
                ("rebound", "rebind.evil.example"),
                ("local", "localhost:7890"),
                ("ip", "127.0.0.1:7890"),
            ):
                seen[name] = client.get("/api/version", headers={"Host": host}).status_code

    monkeypatch.setattr(restapi, "import_optional", lambda *_args, **_kwargs: _Uvicorn)
    monkeypatch.setattr(restapi, "setup_logging", lambda: None)
    restapi.start_service(listen)
    return seen


@pytest.mark.parametrize("listen", ["127.0.0.1:7890", "localhost:7890", "[::1]:7890", "::1:7890"])
def test_a_server_started_on_the_loopback_refuses_a_rebinding_host(
    listen: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`wetterdienst restapi` on a loopback `--listen` answers to the loopback names only, for that process."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "")  # restored afterwards: start_service sets the variable

    seen = _serve_on(listen, monkeypatch)

    assert (seen["rebound"], seen["local"], seen["ip"]) == (400, 200, 200)
    assert seen["port"] == 7890
    assert os.environ["WD_RESTAPI_ALLOWED_HOSTS"].split(",")[:3] == ["localhost", "127.0.0.1", "[::1]"]


def test_a_server_started_without_a_listen_address_is_on_the_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default `--listen` is `127.0.0.1:7890`."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "")
    monkeypatch.setattr(
        restapi, "import_optional", lambda *_args, **_kwargs: type("U", (), {"run": staticmethod(lambda **_k: None)})
    )
    monkeypatch.setattr(restapi, "setup_logging", lambda: None)

    restapi.start_service()

    assert os.environ["WD_RESTAPI_ALLOWED_HOSTS"] == "localhost,127.0.0.1,[::1]"


@pytest.mark.parametrize("listen", ["0.0.0.0:7890", "192.168.1.2:7890", "[::]:7890"])
def test_a_server_not_on_the_loopback_answers_to_any_host(listen: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hosted server behaves as before: no list is set."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "")

    seen = _serve_on(listen, monkeypatch)

    assert seen["rebound"] == 200
    assert os.environ["WD_RESTAPI_ALLOWED_HOSTS"] == ""


def test_a_list_that_is_given_is_not_replaced_on_the_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """A local server reached through a tunnel lists its own names, and `start_service` leaves them."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "tunnel.example.org")

    seen = _serve_on("127.0.0.1:7890", monkeypatch)

    assert os.environ["WD_RESTAPI_ALLOWED_HOSTS"] == "tunnel.example.org"
    assert (seen["local"], seen["ip"]) == (400, 400)


def test_a_malformed_listen_address_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """A listen address that is not `host:port` is a value error that says so, as before it was a bare unpack error."""
    monkeypatch.setattr(restapi, "import_optional", lambda *_args, **_kwargs: type("U", (), {"run": None}))
    monkeypatch.setattr(restapi, "setup_logging", lambda: None)

    with pytest.raises(ValueError, match="listen address"):
        restapi.start_service("7890")


# --- a count that no integer holds --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "name", "bound"),
    [("stations", "rank", "1000000"), ("values", "rank", "1000000"), ("interpolate", "num_additional_stations", "20")],
)
def test_a_count_no_integer_holds_is_a_422_not_an_overflow(
    client: TestClient, path: str, name: str, bound: str
) -> None:
    """`rank=99999999999999999999` was a 500 `OverflowError`; a number the library cannot represent is malformed."""
    params = {**_OBSERVATION, "latitude": 50, "longitude": 10, name: "99999999999999999999"}
    if path == "interpolate":
        params["timestamp"] = "2020-01-01/2020-01-03"

    response = client.get(f"/api/v1/{path}", params=params)

    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:invalid-parameters"
    assert body["errors"][0]["loc"] == ["query", name]
    assert body["errors"][0]["type"] == "less_than_equal"
    assert bound in body["detail"]


def test_a_count_at_the_bound_is_accepted(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The bound is inclusive: a `rank` of 1,000,000 passes validation (the limit on stations then applies)."""
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "2")
    _stub_stream(monkeypatch, [], stations_df=_selection_of(3))

    response = client.get("/api/v1/values", params={**_OBSERVATION, "latitude": 50, "longitude": 10, "rank": 1_000_000})

    assert response.status_code == 400
    assert response.json()["type"] == "urn:wetterdienst:problem:limit-exceeded"
