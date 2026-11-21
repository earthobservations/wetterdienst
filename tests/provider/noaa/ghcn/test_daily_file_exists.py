# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Whether the daily file of a GHCN station exists, which the id search asks of each hit (GH-4075).

The file is the one the values reader reads (NCEI's `by_station` file, then the AWS mirror's), asked through the same
download, so a 404 of both is a station with no file, and every other failure is a failure to check, as it is a failure
to read the values.
"""

from __future__ import annotations

import pytest

from tests.provider.noaa.ghcn.test_api_daily_bucket import _failed, _gone, _no_connection, _ok, _serve
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, NoInternetError, ProviderRateLimitError
from wetterdienst.provider.noaa.ghcn.api import daily_file_exists

#: one reading of the file as NCEI writes it: id, date, element, value, three flags, the hour
FILE = b"GMM00010628,20260101,TMAX,50,,,E,\n"
GEISENHEIM = "GMM00010628"
SETTINGS = Settings(cache_disable=True)


def test_a_station_with_a_file_at_ncei_is_one_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mirror is not asked where NCEI has the file."""
    calls = _serve(monkeypatch, ncei=_ok(FILE), aws=_gone)

    assert daily_file_exists(GEISENHEIM, SETTINGS) is True
    assert [call["url"] for call in calls if "by_station" in str(call["url"])] == [
        f"https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/{GEISENHEIM}.csv.gz"
    ]


def test_a_station_with_a_file_at_the_mirror_only_has_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """NCEI answers 404 and the mirror has it: the values are read from the mirror, so the station has a file."""
    _serve(monkeypatch, ncei=_gone, aws=_ok(FILE))

    assert daily_file_exists(GEISENHEIM, SETTINGS) is True


def test_a_station_both_say_they_have_no_file_of_has_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Geisenheim, WMO 10628: in the stations file, in no inventory, with no file at either."""
    _serve(monkeypatch, ncei=_gone, aws=_gone)

    assert daily_file_exists(GEISENHEIM, SETTINGS) is False


@pytest.mark.parametrize(
    ("ncei", "aws", "error"),
    [
        pytest.param(_failed(503), _gone, DownloadError, id="ncei-5xx-mirror-404"),
        pytest.param(_gone, _failed(502), DownloadError, id="ncei-404-mirror-5xx"),
        pytest.param(_no_connection, _no_connection, NoInternetError, id="no-connection"),
        pytest.param(_ok(b"<html><title>Maintenance</title></html>\n"), _gone, DownloadError, id="maintenance-page"),
    ],
)
def test_a_failure_is_no_answer_of_no_file(
    monkeypatch: pytest.MonkeyPatch, ncei: object, aws: object, error: type[Exception]
) -> None:
    """Not 404 at both is a failure, raised as the values reader raises it: a check that cannot be made is not a no."""
    _serve(monkeypatch, ncei=ncei, aws=aws)  # ty: ignore[invalid-argument-type]

    with pytest.raises(error):
        daily_file_exists(GEISENHEIM, SETTINGS)


def test_a_rate_limit_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 of NCEI is the `ProviderRateLimitError`, never a reason to go to the mirror or to say there is no file."""
    calls = _serve(monkeypatch, ncei=_failed(429), aws=_ok(FILE))

    with pytest.raises(ProviderRateLimitError):
        daily_file_exists(GEISENHEIM, SETTINGS)
    assert not any("amazonaws" in str(call["url"]) and "by_station" in str(call["url"]) for call in calls)
