# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests of the KNMI (Netherlands) observation request, whose only source is KNMI's EDR API since GH-3928.

The key of the EDR API (`WD_AUTH__KNMI_EDR`) is the one credential of the provider: the request is refused without
it, and
`Wetterdienst.is_valid` asks the API whether it takes it. The values, the stations and the requests they cost have
their own files (`test_values`, `test_stations`, `test_edr`); here are the request, its window and the key.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.exceptions import CredentialMissingError
from wetterdienst.provider.knmi.observation import KnmiObservationRequest
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

    from tests.provider.knmi.observation.edr_stub import EdrStub

UTC = ZoneInfo("UTC")
KEY = "knmi-edr-key-for-test-9f3a"


def _request(parameters: list[tuple[str, ...]], start: dt.datetime, end: dt.datetime) -> KnmiObservationRequest:
    return KnmiObservationRequest(
        parameters=parameters, start=start, end=end, settings=Settings(auth={"knmi_edr": "dummy-key-for-test"})
    )


def test_knmi_single_daily_request_floors_start_date_to_midnight() -> None:
    """A single-resolution daily request snaps an unaligned start_date down to midnight.

    This keeps the value dated to the true day boundary while keeping the start-containing day
    in the framework's [start, end] window (no dropped first period, correct label).
    """
    request = _request(
        [("daily", "data", "temperature_air_mean_2m")],
        dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC),
        dt.datetime(2020, 1, 3, tzinfo=UTC),
    )
    assert request.start == dt.datetime(2020, 1, 1, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("resolution", "start", "floored"),
    [
        ("monthly", dt.datetime(2020, 1, 17, 6, tzinfo=UTC), dt.datetime(2020, 1, 1, tzinfo=UTC)),
        ("annual", dt.datetime(2020, 5, 17, 6, tzinfo=UTC), dt.datetime(2020, 1, 1, tzinfo=UTC)),
    ],
)
def test_a_single_monthly_or_annual_request_floors_its_start_to_the_period(
    resolution: str, start: dt.datetime, floored: dt.datetime
) -> None:
    """A month and a year are stamped with their first day, so a start inside one includes it."""
    request = _request([(resolution, "data", "temperature_air_mean_2m")], start, dt.datetime(2022, 1, 1, tzinfo=UTC))
    assert request.start == floored


def test_knmi_single_hourly_request_does_not_floor_start_date() -> None:
    """Hourly is left unfloored at the request level, like 10-minute.

    Its values are stamped with the end of the hour, so an unaligned start must exclude the hour that ends
    before it (the [start, end] filter does).
    """
    request = _request(
        [("hourly", "data", "temperature_air_2m")],
        dt.datetime(2020, 1, 1, 10, 30, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 12, tzinfo=UTC),
    )
    assert request.start == dt.datetime(2020, 1, 1, 10, 30, tzinfo=UTC)


def test_knmi_single_10_minutes_request_does_not_floor_start_date() -> None:
    """10-minute is left unfloored at the request level: its values are stamped with the end of the interval."""
    request = _request(
        [("10_minutes", "data", "temperature_air_2m")],
        dt.datetime(2020, 1, 1, 10, 37, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 11, tzinfo=UTC),
    )
    assert request.start == dt.datetime(2020, 1, 1, 10, 37, tzinfo=UTC)


def test_knmi_mixed_resolution_request_does_not_floor_start_date() -> None:
    """A mixed-resolution request has no single boundary to floor to, so start_date is kept."""
    request = _request(
        [
            ("daily", "data", "temperature_air_mean_2m"),
            ("10_minutes", "data", "temperature_air_2m"),
        ],
        dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC),
        dt.datetime(2020, 1, 3, tzinfo=UTC),
    )
    assert request.start == dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC)


def test_knmi_non_utc_start_end_normalized_to_utc() -> None:
    """A tz-aware non-UTC start/end is converted to UTC: the API's stamps are UTC, and so is the window."""
    ams = ZoneInfo("Europe/Amsterdam")
    request = _request(
        [("10_minutes", "data", "temperature_air_2m")],
        dt.datetime(2020, 6, 1, 10, 7, tzinfo=ams),  # 10:07 CEST == 08:07 UTC
        dt.datetime(2020, 6, 1, 11, 0, tzinfo=ams),  # 11:00 CEST == 09:00 UTC
    )
    assert request.start == dt.datetime(2020, 6, 1, 8, 7, tzinfo=UTC)
    assert request.end == dt.datetime(2020, 6, 1, 9, 0, tzinfo=UTC)


def test_knmi_request_requires_the_edr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without `knmi_edr` a request is refused with the setting to set and where to get the key."""
    monkeypatch.delenv("WD_AUTH__KNMI_EDR", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CredentialMissingError, match=r"WD_AUTH__KNMI_EDR=<api_key>") as raised:
        KnmiObservationRequest(parameters=[("daily", "data", "temperature_air_mean_2m")], settings=Settings())
    assert "https://developer.dataplatform.knmi.nl/edr-api" in str(raised.value)
    assert "Open Data" in str(raised.value)


def test_knmi_request_with_only_the_old_open_data_key_says_it_no_longer_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A request with `WD_AUTH__KNMI` set and no EDR key is refused with the reason: the old key is no longer read."""
    monkeypatch.delenv("WD_AUTH__KNMI_EDR", raising=False)
    monkeypatch.chdir(tmp_path)
    old = "old-open-data-key-for-test"

    with caplog.at_level(logging.WARNING), pytest.raises(CredentialMissingError) as raised:
        KnmiObservationRequest(
            parameters=[("daily", "data", "temperature_air_mean_2m")], settings=Settings(auth={"knmi": old})
        )

    message = str(raised.value)
    assert "WD_AUTH__KNMI holds the key of KNMI's Open Data API" in message
    assert "no longer reads" in message
    assert "WD_AUTH__KNMI_EDR=<api_key>" in message
    assert "https://developer.dataplatform.knmi.nl/edr-api" in message
    assert old not in message + caplog.text


def test_knmi_request_with_both_keys_uses_the_edr_key() -> None:
    """The old key beside the EDR key is dropped (with a warning) and the request is built."""
    request = KnmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        settings=Settings(auth={"knmi": "old-key", "knmi_edr": "new-key"}),
    )
    assert request is not None


def test_knmi_request_constructs_with_the_edr_key() -> None:
    """With the key of the EDR API a request is built, and no request is made to build it."""
    request = _request(
        [("daily", "data", "temperature_air_mean_2m")],
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 1, 2, tzinfo=UTC),
    )
    assert request is not None


def test_knmi_is_configured_by_the_edr_key_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`coverage` says `configured` for the one credential, the key of the EDR API."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WD_AUTH__KNMI_EDR", raising=False)
    assert KnmiObservationRequest.is_configured() is False
    monkeypatch.setenv("WD_AUTH__KNMI_EDR", KEY)
    assert KnmiObservationRequest.is_configured() is True


def _settings(tmp_path: Path, key: str | None = KEY) -> Settings:
    return Settings(auth={"knmi_edr": key} if key else {}, cache_dir=tmp_path / "cache")


def test_the_key_is_checked_against_the_api_with_its_landing_page(edr_server: EdrStub, tmp_path: Path) -> None:
    """`auth` asks `GET /` (1 KB): True for a key the API takes, and one request, kept for a minute."""
    edr_server.key = KEY
    settings = _settings(tmp_path)

    assert KnmiObservationRequest.is_valid(settings) is True
    assert KnmiObservationRequest.is_valid(settings) is True

    assert [path.rstrip("/") for path in edr_server.asked()] == ["/edr/v1"]
    assert edr_server.requests[0]["headers"]["authorization"] == KEY


def test_a_key_the_api_refuses_is_invalid_and_costs_no_quota_and_is_not_kept(
    edr_server: EdrStub, tmp_path: Path
) -> None:
    """A 403 (a key of the Open Data API, or any other) or a 401 is `False`, and asked again each time."""
    edr_server.key = "the-key-the-api-takes"
    settings = _settings(tmp_path, "an-open-data-key")

    assert KnmiObservationRequest.is_valid(settings) is False
    assert KnmiObservationRequest.is_valid(settings) is False

    # each call asks, and asks again for the body of the 403, which tells a refused key from a used-up quota
    assert [request["status"] for request in edr_server.requests] == [403, 403, 403, 403]


def test_a_quota_that_is_used_up_leaves_the_key_unknown_and_never_invalid(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, tmp_path: Path
) -> None:
    """The gateway answers 403 `Quota exceeded` for a key that is fine: `None`, not `False` (GH-4046)."""
    edr_server.quota_after = 0
    edr_server.quota_headers = {"Retry-After": "900"}

    with caplog.at_level(logging.WARNING):
        assert KnmiObservationRequest.is_valid(_settings(tmp_path)) is None

    assert "quota" in caplog.text
    assert KEY not in caplog.text


def test_no_key_is_invalid_without_a_request(edr_server: EdrStub, tmp_path: Path) -> None:
    """No key configured: `False`, and nothing asked."""
    assert KnmiObservationRequest.is_valid(_settings(tmp_path, None)) is False
    assert edr_server.requests == []


@pytest.mark.parametrize("status", [429, 500, 503])
def test_an_api_that_cannot_say_leaves_the_key_unknown(
    caplog: pytest.LogCaptureFixture, edr_server: EdrStub, tmp_path: Path, status: int
) -> None:
    """A 429, a 5xx: `None`, not rejected, with a warning that says nothing of the key."""
    edr_server.statuses.extend([status])
    with caplog.at_level(logging.WARNING):
        assert KnmiObservationRequest.is_valid(_settings(tmp_path)) is None
    assert KEY not in caplog.text
