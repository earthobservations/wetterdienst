# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for how the Frost values requests read a failed download, run against a stubbed upstream."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

START = dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
END = dt.datetime(2020, 1, 2, tzinfo=ZoneInfo("UTC"))
LOGGER = "wetterdienst.provider.metno.frost.api"

SOURCES = {
    "data": [
        {
            "id": "SN18700",
            "name": "OSLO - BLINDERN",
            "validFrom": "1937-01-01T00:00:00.000Z",
            "geometry": {"coordinates": [10.72, 59.94]},
            "county": "OSLO",
            "countryCode": "NO",
            "masl": 94,
        },
    ],
}
AVAILABLE = {
    "data": [
        {
            "validFrom": "2000-01-01T00:00:00Z",
            "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0",
        },
    ],
}
OBSERVATIONS = {
    "data": [
        {
            "sourceId": "SN18700:0",
            "referenceTime": "2020-01-01T00:00:00.000Z",
            "observations": [{"elementId": "air_temperature", "value": 2.7, "qualityCode": 0}],
        },
    ],
}


def _ok(url: str, payload: dict) -> File:
    return File(url=url, content=BytesIO(json.dumps(payload).encode()), status=200)


def _failed(url: str, status: int) -> File:
    """Give a failed request as `download_file` hands it back: the exception, with no body."""
    return File(url=url, content=OSError(f"upstream answered {status}"), status=status)


def _values(monkeypatch: pytest.MonkeyPatch, observations: Callable[[str], File]) -> tuple[object, list[str]]:
    """Give the values of one station, the stations and the observations answered as stubbed."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")
    seen: list[str] = []

    def _download(*, url: str, **_kwargs: object) -> File:
        seen.append(url)
        if "/sources/" in url:
            return _ok(url, SOURCES)
        return observations(url)

    monkeypatch.setattr(frost_api, "download_file", _download)
    request = MetnoFrostRequest(parameters=[("hourly", "data", "temperature_air_mean_2m")], start=START, end=END)
    return request.filter_by_station_id("SN18700").values, seen


def test_metno_frost_values_404_reaches_the_discovery_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a 404 on the batched request resolves each parameter, and on that, discovers the time series.

    `download_file` hands back a 404 as an exception with no body, which `File.is_empty` reports as
    empty too. The values request returned on that before it read the status, so neither fallback
    for an element that needs `timeseriesids` could run (GH-2494).
    """

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        if "timeseriesids=" in url:
            return _ok(url, OBSERVATIONS)
        return _failed(url, 404)

    values, seen = _values(monkeypatch, observations)
    df = values.all().df
    # the dataset is requested in one batch, which 404s; then each of its parameters is asked for
    # alone, which 404s as well, and its time series are discovered and read
    parameters = len(values.sr.parameters[0].dataset.parameters)
    assert parameters > 1
    assert "," in seen[1].split("elements=")[1].split("&")[0]
    assert sum("availableTimeSeries" in url for url in seen) == parameters
    assert sum("timeseriesids=" in url for url in seen) == parameters
    assert df["parameter"].to_list() == ["temperature_air_mean_2m"]
    assert df["value"].to_list() == [2.7]


@pytest.mark.parametrize("status", [401, 403, 500])
def test_metno_frost_values_failure_is_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    status: int,
) -> None:
    """Test that a failed values request other than a 404 or 412 is logged, not taken for no data."""
    values, seen = _values(monkeypatch, lambda url: _failed(url, status))
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    assert [record.getMessage() for record in caplog.records if record.name == LOGGER] == [
        f"Failed to download {seen[-1]}: upstream answered {status}",
    ]


def test_metno_frost_values_single_parameter_failure_is_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the single-parameter request warns for a failure other than a 404 or 412 as well."""
    values, seen = _values(monkeypatch, lambda url: _failed(url, 500))
    parameter = values.sr.parameters[0]
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values._collect_single_parameter("SN18700", parameter, START, END, values.sr.settings, {})  # noqa: SLF001
    assert df.is_empty()
    assert [record.getMessage() for record in caplog.records if record.name == LOGGER] == [
        f"Failed to download {seen[-1]}: upstream answered 500",
    ]


def test_metno_frost_values_412_is_no_data(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Test that a 412, Frost's answer for no data in the window, is empty and goes unwarned."""
    values, seen = _values(monkeypatch, lambda url: _failed(url, 412))
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    assert len(seen) == 2
    assert [record for record in caplog.records if record.name == LOGGER] == []


def test_metno_frost_values_discovered_series_failure_is_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failed request for a discovered time series is warned about, not taken for no data."""

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        return _failed(url, 404 if "timeseriesids=" not in url else 500)

    values, _seen = _values(monkeypatch, observations)
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    warned = [record.getMessage() for record in caplog.records if record.name == LOGGER]
    assert warned
    assert all(
        message.startswith("Failed to download ") and message.endswith(": upstream answered 500") for message in warned
    )
    assert all("timeseriesids=" in message for message in warned)
