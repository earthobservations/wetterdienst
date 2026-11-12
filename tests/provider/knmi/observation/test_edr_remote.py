# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The EDR route against the files, live, for De Bilt (GH-3928).

Needs both keys, `WD_AUTH__KNMI` of the Open Data API and `WD_AUTH__KNMI_EDR` of the EDR API, and is skipped without
either. Each case is a request or two of the EDR API (1,000 an hour) and a few of the Open Data API (an hour of
hourly values is 24 files, which is why the hourly case is a day and no more).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.provider.knmi.observation import edr
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.remote,
    pytest.mark.skipif(
        not (Settings().auth.knmi and Settings().auth.knmi_edr),
        reason="both keys are needed: WD_AUTH__KNMI (Open Data API) and WD_AUTH__KNMI_EDR (EDR API)",
    ),
]

UTC = dt.UTC
DE_BILT = "06260"


def _read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    parameters: list[tuple[str, ...]],
    start: dt.datetime,
    end: dt.datetime,
    *,
    drop_nulls: bool = False,
) -> tuple[pl.DataFrame, pl.DataFrame, list[str]]:
    """Read De Bilt from the EDR API and from the files, as one request: the frame of each, and the EDR requests."""
    settings = Settings()
    asked: list[str] = []
    real_request = edr.request_url

    def request_url(*args: object, **kwargs: object) -> str:
        url = real_request(*args, **kwargs)
        asked.append(url)
        return url

    monkeypatch.setattr(edr, "request_url", request_url)
    # one day or hour is far less than `MIN_FILES`: the point is that the two routes agree on it
    monkeypatch.setattr(edr, "MIN_FILES", 0)

    def frame(*, with_edr_key: bool) -> pl.DataFrame:
        # `None` and not a missing key: a key of the environment is read for a field that is not given
        auth = {"knmi": settings.auth.knmi, "knmi_edr": settings.auth.knmi_edr if with_edr_key else None}
        request = KnmiObservationRequest(
            parameters=parameters,
            start=start,
            end=end,
            settings=Settings(auth=auth, cache_dir=tmp_path / ("edr" if with_edr_key else "files")),
            options={"drop_nulls": drop_nulls},
        )
        return request.filter_by_station_id(DE_BILT).values().all().df

    from_api = frame(with_edr_key=True)
    assert asked, "the EDR API was not asked"
    asked_by_edr = list(asked)
    from_files = frame(with_edr_key=False)
    assert asked == asked_by_edr, "the files route asked the EDR API"
    return from_api, from_files, asked


def test_the_first_of_january_2020_is_the_same_from_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """De Bilt, daily, 2020-01-01: TG 0.8, TN -0.2, TX 1.8 and RH 0.0, dated that day by both routes."""
    from_api, from_files, _ = _read(
        tmp_path,
        monkeypatch,
        [("daily", "data")],
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 1, 1, tzinfo=UTC),
    )
    assert_frame_equal(from_api, from_files)
    day = {
        row["parameter"]: row["value"]
        for row in from_api.filter(
            pl.col("parameter").is_in(
                ["temperature_air_mean_2m", "temperature_air_min_2m", "temperature_air_max_2m", "precipitation_amount"]
            )
        ).iter_rows(named=True)
    }
    assert day == {
        "temperature_air_mean_2m": 0.8,
        "temperature_air_min_2m": -0.2,
        "temperature_air_max_2m": 1.8,
        "precipitation_amount": 0.0,
    }
    assert from_api.get_column("timestamp").unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]


def test_one_hourly_day_is_the_same_from_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """De Bilt, hourly, the day of 2020-06-01 (the hours 01:00 to 24:00): the same rows, flags and `raw:` tokens."""
    from_api, from_files, _ = _read(
        tmp_path,
        monkeypatch,
        [("hourly", "data")],
        dt.datetime(2020, 6, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 6, 2, 0, tzinfo=UTC),
    )
    assert from_api.height > 24
    assert_frame_equal(from_api, from_files)


def test_one_hour_of_10_minutes_is_the_same_from_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """De Bilt, 10 minutes, 2026-11-09 06:10 to 07:00 (a recent hour, in which every variable is in the files)."""
    from_api, from_files, _ = _read(
        tmp_path,
        monkeypatch,
        [("10_minutes", "data")],
        dt.datetime(2026, 11, 9, 6, 10, tzinfo=UTC),
        dt.datetime(2026, 11, 9, 7, 0, tzinfo=UTC),
    )
    assert from_api.height > 6
    assert_frame_equal(from_api, from_files)


def test_one_hour_of_10_minutes_in_2020_is_the_same_from_both_with_the_nulls_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The files of 2020 do not carry `tg` at all, where the API leaves it out for a station that has no such sensor.

    With the nulls kept that is a NaN row of the API and no row of the files, which cannot be told apart in the answer
    (De Bilt's `vv` is a NaN row of both): the values are the same, and so is the default, with the nulls dropped.
    """
    from_api, from_files, _ = _read(
        tmp_path,
        monkeypatch,
        [("10_minutes", "data")],
        dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC),
        dt.datetime(2020, 6, 1, 13, 0, tzinfo=UTC),
        drop_nulls=True,
    )
    assert from_api.height > 6
    assert_frame_equal(from_api, from_files)


@pytest.mark.parametrize(
    ("resolution", "start", "end"),
    [
        pytest.param("monthly", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 3, 1, tzinfo=UTC), id="monthly"),
        pytest.param("annual", dt.datetime(2018, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 1, tzinfo=UTC), id="annual"),
    ],
)
def test_months_and_years_are_the_same_from_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resolution: str, start: dt.datetime, end: dt.datetime
) -> None:
    """The monthly and the annual collections, which the API stamps with the end of the period, agree with the files."""
    from_api, from_files, _ = _read(tmp_path, monkeypatch, [(resolution, "data")], start, end)
    assert from_api.height > 0
    assert_frame_equal(from_api, from_files)
