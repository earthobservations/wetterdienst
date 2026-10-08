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

    from wetterdienst.provider.metno.frost.api import MetnoFrostValues

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


def _values(
    monkeypatch: pytest.MonkeyPatch,
    observations: Callable[[str], File],
    parameters: list[tuple[str, str, str]] | None = None,
) -> tuple[MetnoFrostValues, list[str]]:
    """Give the values of one station, the stations and the observations answered as stubbed."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")
    seen: list[str] = []

    def _download(*, url: str, **_kwargs: object) -> File:
        seen.append(url)
        if "/sources/" in url:
            return _ok(url, SOURCES)
        return observations(url)

    monkeypatch.setattr(frost_api, "download_file", _download)
    request = MetnoFrostRequest(
        parameters=parameters or [("hourly", "data", "temperature_air_mean_2m")],
        start=START,
        end=END,
    )
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
    # the dataset is requested in one batch, which 404s; then the parameter that was asked for is
    # requested alone, which 404s as well, and its time series are discovered and read
    assert len(values.sr.parameters[0].dataset.parameters) > 1
    assert "," in seen[1].split("elements=")[1].split("&")[0]
    assert sum("availableTimeSeries" in url for url in seen) == 1
    assert sum("timeseriesids=" in url for url in seen) == 1
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
    assert len(warned) == 1
    assert all(
        message.startswith("Failed to download ") and message.endswith(": upstream answered 500") for message in warned
    )
    assert all("timeseriesids=" in message for message in warned)


def test_metno_frost_values_discovery_failure_is_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failed request for the available time series is warned about, not taken for no data."""
    values, seen = _values(monkeypatch, lambda url: _failed(url, 404 if "availableTimeSeries" not in url else 500))
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    warned = [record.getMessage() for record in caplog.records if record.name == LOGGER]
    assert len(warned) == 1
    assert all(message.startswith("Failed to download ") for message in warned)
    assert all("availableTimeSeries" in message for message in warned)
    assert not any("timeseriesids=" in url for url in seen)


@pytest.mark.parametrize("status", [404, 412])
def test_metno_frost_values_no_time_series_is_no_data(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    status: int,
) -> None:
    """Test that a 404 or 412 for the available time series, Frost's answer for none, goes unwarned."""
    values, _seen = _values(monkeypatch, lambda url: _failed(url, status if "availableTimeSeries" in url else 404))
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    assert [record for record in caplog.records if record.name == LOGGER] == []


def _observation_requests(seen: list[str]) -> list[str]:
    """Give the observation and time series requests of a run, leaving out the stations request."""
    return [url for url in seen if "/sources/" not in url]


def test_metno_frost_values_404_fallback_asks_for_the_requested_parameters_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the fallback after a 404 on the batch resolves what was asked for, not the whole dataset (GH-2554)."""
    requested = [("hourly", "data", "temperature_air_mean_2m"), ("hourly", "data", "wind_speed")]
    values, seen = _values(monkeypatch, lambda url: _failed(url, 404), requested)
    assert values.all().df.is_empty()
    batch, *rest = _observation_requests(seen)
    assert len(values.sr.parameters[0].dataset.parameters) > len(requested)
    assert batch.count(",") == len(values.sr.parameters[0].dataset.parameters) - 1
    # one request alone and one discovery per requested parameter, and nothing for the rest
    assert [url.split("elements=")[1].split("&")[0] for url in rest if "availableTimeSeries" not in url] == [
        "air_temperature",
        "wind_speed",
    ]
    assert [url.split("elements=")[1].split("&")[0] for url in rest if "availableTimeSeries" in url] == [
        "air_temperature",
        "wind_speed",
    ]


def test_metno_frost_values_404_on_a_one_parameter_dataset_is_not_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a 404 on a dataset of one parameter goes straight to discovery, not to the URL that 404'd (GH-2554)."""

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        if "timeseriesids=" in url:
            return _ok(url, precipitation)
        return _failed(url, 404)

    precipitation = {
        "data": [
            {
                **OBSERVATIONS["data"][0],
                "observations": [{"elementId": "sum(precipitation_amount PT6H)", "value": 1.5, "qualityCode": 0}],
            },
        ],
    }
    values, seen = _values(monkeypatch, observations, [("6_hour", "data", "precipitation_amount")])
    df = values.all().df
    requests = _observation_requests(seen)
    assert len(values.sr.parameters[0].dataset.parameters) == 1
    assert len(requests) == len(set(requests)) == 3
    assert ["availableTimeSeries" in url for url in requests] == [False, True, False]
    assert "timeseriesids=" in requests[2]
    assert df["value"].to_list() == [1.5]


def test_metno_frost_values_404_fallback_for_one_parameter_leaves_its_siblings_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the fallback for one parameter model resolves that parameter, not its siblings (GH-2554)."""
    requested = [("hourly", "data", "temperature_air_mean_2m"), ("hourly", "data", "wind_speed")]
    values, seen = _values(monkeypatch, lambda url: _failed(url, 404), requested)
    assert values._collect_station_parameter_or_dataset("SN18700", values.sr.parameters[1]).is_empty()  # noqa: SLF001
    # the request for that parameter alone, then its discovery; air_temperature is never asked for
    assert [url.split("elements=")[1].split("&")[0] for url in _observation_requests(seen)] == [
        "wind_speed",
        "wind_speed",
    ]
