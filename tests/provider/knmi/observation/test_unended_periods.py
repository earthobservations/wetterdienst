# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A period that has not ended has no file, so none is asked for (GH-4008).

A range that ran into the running hour, day, month or year asked KNMI for a file that cannot exist (the annual file of
2026 is made in 2027), and the 404 was reported as a `file-skipped` warning that calls the answer partial and says to
try again later. A period that ends after now is skipped with no request and no warning, at every resolution; the
running 10 minutes and hour of a range that reaches now are asked for as soon as they have ended, which is when their
file is made (read 2026-11-11: the 10-minute file named 22:00 was created at 22:03).
"""

import datetime as dt
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tests.provider.knmi.observation.catalogue import catalogue_frame
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import api
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest, _moments
from wetterdienst.settings import Settings

h5netcdf = pytest.importorskip("h5netcdf", reason="h5netcdf not installed")
h5py = pytest.importorskip("h5py", reason="h5py not installed")

UTC = ZoneInfo("UTC")
#: Now, in the middle of the 10 minutes that end at 12:40, of the hour that ends at 13:00, of 11 November, of 2026
NOW = dt.datetime(2026, 11, 11, 12, 34, tzinfo=UTC)
DE_BILT = "06260"


@pytest.fixture(autouse=True)
def _pinned_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_now", lambda: NOW)


def _at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=UTC)


@pytest.mark.parametrize(
    ("resolution", "start", "end", "expected"),
    [
        pytest.param(
            Resolution.MINUTE_10,
            _at(2026, 11, 11, 12, 0),
            _at(2026, 11, 12),
            [_at(2026, 11, 11, 12, m) for m in (0, 10, 20, 30)],
            id="10 minutes: the file named 12:40 is not made before 12:40",
        ),
        pytest.param(
            Resolution.HOURLY,
            _at(2026, 11, 11, 10),
            _at(2026, 11, 12),
            [_at(2026, 11, 11, h) for h in (9, 10, 11)],
            id="hourly: the hour 12 to 13 is running",
        ),
        pytest.param(
            Resolution.DAILY,
            _at(2026, 11, 9),
            _at(2026, 11, 13),
            [_at(2026, 11, 9), _at(2026, 11, 10)],
            id="daily: today is running",
        ),
        pytest.param(
            Resolution.MONTHLY,
            _at(2026, 9, 1),
            _at(2026, 12, 1),
            [_at(2026, 9, 1), _at(2026, 10, 1)],
            id="monthly: November is running",
        ),
        pytest.param(
            Resolution.ANNUAL,
            _at(2024, 1, 1),
            _at(2027, 1, 1),
            [_at(2024, 1, 1), _at(2025, 1, 1)],
            id="annual: 2026 is running",
        ),
    ],
)
def test_the_moments_stop_at_the_period_that_has_not_ended(
    resolution: Resolution, start: dt.datetime, end: dt.datetime, expected: list[dt.datetime]
) -> None:
    """The moments of a range that reaches beyond now are those of the periods that have ended."""
    assert list(_moments(start, end, resolution)) == expected


def test_a_period_that_ends_exactly_now_has_ended(monkeypatch: pytest.MonkeyPatch) -> None:
    """The file of the hour 11 to 12 is asked for at 12:00, and the 10-minute file named 12:30 at 12:30."""
    monkeypatch.setattr(api, "_now", lambda: _at(2026, 11, 11, 12))
    assert list(_moments(_at(2026, 11, 11, 11), _at(2026, 11, 11, 13), Resolution.HOURLY))[-1] == _at(2026, 11, 11, 11)
    assert list(_moments(_at(2026, 11, 11, 11, 50), _at(2026, 11, 11, 13), Resolution.MINUTE_10))[-1] == _at(
        2026, 11, 11, 12
    )


def test_a_range_wholly_in_the_future_has_no_moments() -> None:
    """No file of December 2026 or of the year 2027 can exist yet."""
    assert list(_moments(_at(2026, 12, 1), _at(2026, 12, 31), Resolution.DAILY)) == []
    assert list(_moments(_at(2027, 1, 1), _at(2027, 12, 31), Resolution.ANNUAL)) == []


def _file(path: Path, variable: str, value: float) -> bytes:
    """Build a NetCDF with De Bilt as its one station and one value."""
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": 1, "time": 1}
        station = file.create_variable("station", ("station",), dtype=h5py.string_dtype())
        station[:] = ["0-20000-0-06260"]
        data = file.create_variable(variable, ("station", "time"), dtype="f8")
        data[:] = [[value]]
    return path.read_bytes()


def _values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    parameter: tuple[str, str, str],
    start: dt.datetime,
    end: dt.datetime,
) -> tuple[list[str], list[logging.LogRecord]]:
    """Read De Bilt's values of a range from files that all exist, and give the files asked for and the warnings."""
    variable = {"10_minutes": "ta", "hourly": "T", "daily": "TG", "monthly": "TG", "annual": "TG"}[parameter[0]]
    payload = _file(tmp_path / "file.nc", variable, 12.3)
    asked: list[str] = []

    def fetch(_dataset: str, _version: str, filename: str, _settings: Settings, _expiry: object = None) -> bytes:
        asked.append(filename)
        return payload

    monkeypatch.setattr(api, "_station_catalogue", lambda *_args: catalogue_frame(DE_BILT))
    monkeypatch.setattr(api, "_fetch_netcdf", fetch)
    records: list[logging.LogRecord] = []

    class Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Handler(level=logging.WARNING)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        request = KnmiObservationRequest(
            parameters=[parameter], start=start, end=end, settings=Settings(auth={"knmi": "dummy-key-for-test"})
        )
        request.filter_by_station_id(DE_BILT).values().all()
    finally:
        root.removeHandler(handler)
    return asked, records


@pytest.mark.parametrize(
    ("parameter", "start", "end", "asked"),
    [
        pytest.param(
            ("daily", "data", "temperature_air_mean_2m"),
            _at(2026, 11, 10),
            _at(2026, 11, 14),
            ["daily-observations-validated-20261110.nc"],
            id="daily",
        ),
        pytest.param(
            ("monthly", "data", "temperature_air_mean_2m"),
            _at(2026, 10, 1),
            _at(2026, 12, 31),
            ["monthly-observations-validated-202610.nc"],
            id="monthly",
        ),
        pytest.param(
            ("annual", "data", "temperature_air_mean_2m"),
            _at(2025, 1, 1),
            _at(2026, 12, 31),
            ["annual-observations-validated-2025.nc"],
            id="annual",
        ),
    ],
)
def test_a_period_that_has_not_ended_is_not_asked_for_and_not_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    parameter: tuple[str, str, str],
    start: dt.datetime,
    end: dt.datetime,
    asked: list[str],
) -> None:
    """The running day, month or year makes no request and so no 404, and no `file-skipped` warning of it."""
    files, warnings = _values(monkeypatch, tmp_path, parameter, start, end)
    assert files == asked
    assert [record.getMessage() for record in warnings] == []


@pytest.mark.parametrize(
    ("parameter", "start", "end", "asked"),
    [
        pytest.param(
            ("hourly", "data", "temperature_air_2m"),
            _at(2026, 11, 11, 10),
            _at(2026, 11, 11, 15),
            [f"hourly-observations-validated-20261111-{hour:02d}.nc" for hour in (9, 10, 11)],
            id="hourly: the hours that have ended, the running one left out",
        ),
        pytest.param(
            ("10_minutes", "data", "temperature_air_2m"),
            _at(2026, 11, 11, 12),
            _at(2026, 11, 11, 13),
            [f"KMDS__OPER_P___10M_OBS_L2_2026111112{minute:02d}.nc" for minute in (0, 10, 20, 30)],
            id="10 minutes: up to the 10 minutes that have ended",
        ),
    ],
)
def test_the_partial_current_hour_or_10_minutes_are_read_as_far_as_they_have_ended(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    parameter: tuple[str, str, str],
    start: dt.datetime,
    end: dt.datetime,
    asked: list[str],
) -> None:
    """A range into the present is answered with what has ended, with no warning for what has not."""
    files, warnings = _values(monkeypatch, tmp_path, parameter, start, end)
    assert files == asked
    assert [record.getMessage() for record in warnings] == []
