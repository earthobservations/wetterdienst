# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DMI (Danish Meteorological Institute) climate data observation provider."""

import datetime as dt
import json
import logging
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

import wetterdienst.provider.dmi.observation.api as dmi_api
from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

# Copenhagen (Zealand) — the reference station used across the remote tests.
COPENHAGEN_LANDBOHOJSKOLEN = "06180"
UTC = ZoneInfo("UTC")


def _dates_for(from_value: str, resolution: Resolution) -> dt.datetime:
    """Evaluate the provider's date expression for a single DMI ``from`` timestamp."""
    df = pl.DataFrame({"from": [from_value]}).select(
        dmi_api.DmiObservationValues._date_expression(resolution).alias("date"),  # noqa: SLF001
    )
    return df.get_column("date").to_list()[0]


def test_metadata_resolutions() -> None:
    """DMI exposes hour, day, month and year resolutions."""
    resolutions = {resolution.name for resolution in dmi_api.DmiObservationRequest.metadata}
    assert resolutions == {"hourly", "daily", "monthly", "annual"}


def test_metadata_no_auth() -> None:
    """DMI's open data service requires no authentication."""
    assert dmi_api.DmiObservationRequest.metadata.auth is False


def test_date_expression_hourly_is_utc_aligned() -> None:
    """Hourly aggregates are UTC-aligned and labelled by the start of the hour."""
    date = _dates_for("2023-06-01T00:00:00+00:00", Resolution.HOURLY)
    assert date == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)


def test_date_expression_hourly_tolerates_fractional_seconds() -> None:
    """Hourly parsing must not break if DMI includes fractional seconds in ``from``."""
    date = _dates_for("2023-06-01T00:00:00.000000+00:00", Resolution.HOURLY)
    assert date == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)


def test_date_expression_daily_uses_local_civil_date() -> None:
    """A Danish summer day (``from`` at +02:00) maps to that civil date at UTC midnight."""
    date = _dates_for("2023-06-02T00:00:00.001000+02:00", Resolution.DAILY)
    assert date == dt.datetime(2023, 6, 2, 0, 0, tzinfo=UTC)


def test_date_expression_daily_greenland_negative_offset() -> None:
    """A Greenland day (``from`` at a negative offset) maps to its civil date at UTC midnight.

    Taking the civil date straight from the ``from`` string keeps this correct regardless of
    the station's timezone — a naive UTC conversion would shift it onto the previous day.
    """
    date = _dates_for("2023-06-02T00:00:00.001000-02:00", Resolution.DAILY)
    assert date == dt.datetime(2023, 6, 2, 0, 0, tzinfo=UTC)


def test_date_expression_monthly_truncates_to_first_of_month() -> None:
    """Monthly aggregates are labelled by the first of the civil month at UTC midnight."""
    date = _dates_for("2023-07-01T00:00:00.001000+02:00", Resolution.MONTHLY)
    assert date == dt.datetime(2023, 7, 1, 0, 0, tzinfo=UTC)


def test_date_expression_annual_truncates_to_first_of_year() -> None:
    """Annual aggregates are labelled by the first of the civil year at UTC midnight."""
    date = _dates_for("2021-01-01T00:00:00.001000+01:00", Resolution.ANNUAL)
    assert date == dt.datetime(2021, 1, 1, 0, 0, tzinfo=UTC)


def _station_value_file(count: int, start: int = 0) -> File:
    """Build a DMI stationValue response File with ``count`` feature records."""
    features = [
        {
            "properties": {
                "parameterId": "mean_temp",
                "from": "2023-06-01T00:00:00+00:00",
                "value": float(index),
            },
        }
        for index in range(start, start + count)
    ]
    return File(url="", content=BytesIO(json.dumps({"features": features}).encode()), status=200)


def _iter_pages(values: dmi_api.DmiObservationValues) -> list[pl.DataFrame]:
    return list(
        values._iter_station_value_pages("06180", "hour", "start", "end", Settings(cache_disable=True)),  # noqa: SLF001
    )


def test_iter_station_value_pages_walks_all_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pagination advances the offset until a short (< limit) page and concatenates every page."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)
    # offset 0 -> full page (2), offset 2 -> full page (2), offset 4 -> short page (1) => stop
    pages = {0: 2, 2: 2, 4: 1}
    offsets: list[int] = []

    def fake_download_file(*, url: str, **_: object) -> File:
        offset = int(url.split("offset=")[1])
        offsets.append(offset)
        return _station_value_file(pages[offset], start=offset)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    dfs = _iter_pages(object.__new__(dmi_api.DmiObservationValues))
    assert offsets == [0, 2, 4]
    assert len(dfs) == 3
    assert sum(df.height for df in dfs) == 5


def test_iter_station_value_pages_single_short_page_stops_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    """A first page shorter than the limit ends pagination after one request."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 100)
    offsets: list[int] = []

    def fake_download_file(*, url: str, **_: object) -> File:
        offsets.append(int(url.split("offset=")[1]))
        return _station_value_file(3)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    dfs = _iter_pages(object.__new__(dmi_api.DmiObservationValues))
    assert offsets == [0]
    assert [df.height for df in dfs] == [3]


def test_iter_station_value_pages_stops_on_download_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A download error ends pagination without raising, keeps prior pages, and logs a warning."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        # first (full) page succeeds, second page errors
        if "offset=0" in url:
            return _station_value_file(2)
        return File(url=url, content=RuntimeError("boom"), status=500)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    with caplog.at_level(logging.WARNING, logger=dmi_api.log.name):
        dfs = _iter_pages(object.__new__(dmi_api.DmiObservationValues))
    assert [df.height for df in dfs] == [2]
    assert any("Failed to acquire DMI data" in record.message for record in caplog.records)


def test_iter_station_value_pages_no_internet_is_silent(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A NoInternetError ends pagination silently -- no warning (already logged at debug upstream)."""
    monkeypatch.setattr(dmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        return File(url=url, content=NoInternetError("offline"), status=503)

    monkeypatch.setattr(dmi_api, "download_file", fake_download_file)
    with caplog.at_level(logging.WARNING, logger=dmi_api.log.name):
        dfs = _iter_pages(object.__new__(dmi_api.DmiObservationValues))
    assert dfs == []
    assert not any("Failed to acquire DMI data" in record.message for record in caplog.records)


@pytest.mark.remote
def test_dmi_observation_stations() -> None:
    """Station discovery returns deduplicated stations with usable metadata."""
    request = dmi_api.DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).all()
    assert not request.df.is_empty()
    # DMI lists a station once per validity period; the provider collapses these to one row.
    assert request.df.get_column("station_id").n_unique() == request.df.height
    station = request.df.filter(pl.col("station_id") == COPENHAGEN_LANDBOHOJSKOLEN)
    assert station.height == 1
    row = station.to_dicts()[0]
    assert row["name"]
    assert row["state"] == "DNK"
    assert 54 < row["latitude"] < 58
    assert 8 < row["longitude"] < 16


@pytest.mark.remote
def test_dmi_observation_values_daily() -> None:
    """Daily values include both range boundaries (the local/UTC offset must not drop them)."""
    request = dmi_api.DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 5, tzinfo=UTC),
    ).filter_by_station_id([COPENHAGEN_LANDBOHOJSKOLEN])
    values = request.values.all().df
    dates = values.get_column("date").sort().to_list()
    assert dates[0] == dt.datetime(2023, 6, 1, tzinfo=UTC)
    assert dates[-1] == dt.datetime(2023, 6, 5, tzinfo=UTC)
    assert "UTC" in str(values.schema["date"])
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_dmi_observation_values_complete_aligns_to_utc_grid() -> None:
    """With ts_complete the base date grid (driven by timezone_data=UTC) must join the labels.

    A non-UTC timezone_data would generate the completion grid at local midnight converted to
    UTC (e.g. 22:00Z), which would not join the provider's UTC-midnight labels and would null
    out every value.
    """
    settings = Settings(cache_disable=True, ts_complete=True, ts_drop_nulls=False)
    request = dmi_api.DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 5, tzinfo=UTC),
        settings=settings,
    ).filter_by_station_id([COPENHAGEN_LANDBOHOJSKOLEN])
    values = request.values.all().df
    assert values.height == 5
    # every completed day aligns to a real UTC-midnight label and carries its value
    assert values.drop_nulls(subset="value").height == 5
    assert values.get_column("date").dt.hour().unique().to_list() == [0]


@pytest.mark.remote
def test_dmi_observation_values_hourly_utc() -> None:
    """Hourly values are UTC-aligned to the start of each hour."""
    request = dmi_api.DmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 1, 6, tzinfo=UTC),
    ).filter_by_station_id([COPENHAGEN_LANDBOHOJSKOLEN])
    values = request.values.all().df
    first_date = values.get_column("date").min()
    assert first_date == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_dmi_observation_values_empty_for_unknown_station() -> None:
    """An unknown station id yields an empty, well-formed values frame."""
    settings = Settings(cache_disable=True)
    request = dmi_api.DmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 5, tzinfo=UTC),
        settings=settings,
    ).filter_by_station_id(["00000"])
    values = request.values.all().df
    assert values.is_empty()
