# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Met Office (MIDAS Open) observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.metoffice.observation import MetOfficeObservationRequest
from wetterdienst.provider.metoffice.observation.parser import (
    parse_station_metadata,
    parse_values,
)

UTC = ZoneInfo("UTC")

# a busy long-running station (Lerwick, Shetland) present across most MIDAS Open datasets
LERWICK = "00009"


def _badc(header_rows: bytes, columns: str, data_rows: bytes) -> bytes:
    """Assemble a minimal BADC-CSV file: G-attribute header, a bare ``data`` line, table, trailer."""
    return header_rows + b"data\n" + columns.encode() + b"\n" + data_rows + b"end data\n"


def test_parse_station_metadata() -> None:
    """The station-metadata catalogue maps to one row per station with year-bounded dates."""
    content = _badc(
        b"Conventions,G,BADC-CSV,1\ntitle,G,Midas-open: Station site metadata\n",
        "src_id,station_name,station_file_name,historic_county,authority,"
        "station_latitude,station_longitude,station_elevation,first_year,last_year",
        b"00001,FOULA,foula,shetland,Met Office,60.154,-2.074,22,1989,2003\n",
    )
    df = parse_station_metadata(content)
    assert df.to_dicts() == [
        {
            "station_id": "00001",
            "name": "FOULA",
            "historic_county": "shetland",
            "station_file_name": "foula",
            "latitude": 60.154,
            "longitude": -2.074,
            "height": 22.0,
            "start_date": dt.datetime(1989, 1, 1, tzinfo=UTC),
            "end_date": dt.datetime(2003, 12, 31, tzinfo=UTC),
        },
    ]


def test_parse_values_collapses_multiple_report_types() -> None:
    """A day with 12h night/day readings plus a 24h reading collapses to one daily extreme.

    ``max`` for max-type, ``min`` for ``min_columns`` is idempotent over the duplication, so the
    result equals the true 24-hour value regardless of which report types a station transmits.
    """
    content = _badc(
        b"Conventions,G,BADC-CSV,1\n",
        "ob_end_time,ob_hour_count,met_domain_name,max_air_temp,max_air_temp_q,min_air_temp,min_air_temp_q",
        # night 12h (ends 09:00), full-day 24h (ends 09:00), day 12h (ends 21:00)
        b"2000-01-01 09:00:00,12,AWSDLY,4.8,6,0.3,6\n"
        b"2000-01-01 09:00:00,24,DLY3208,5.4,4,0.3,4\n"
        b"2000-01-01 21:00:00,12,AWSDLY,5.1,6,2.8,6\n",
    )
    df = parse_values(
        content,
        time_column="ob_end_time",
        columns=["max_air_temp", "min_air_temp"],
        granularity="1d",
        min_columns=frozenset({"min_air_temp"}),
    ).sort("parameter")
    assert df.to_dicts() == [
        # max over {4.8, 5.4, 5.1} == the 24h value 5.4; quality is that of the extreme row
        {"date": dt.datetime(2000, 1, 1, tzinfo=UTC), "parameter": "max_air_temp", "value": 5.4, "quality": 4.0},
        # min over {0.3, 0.3, 2.8} == 0.3
        {"date": dt.datetime(2000, 1, 1, tzinfo=UTC), "parameter": "min_air_temp", "value": 0.3, "quality": 6.0},
    ]


def test_parse_values_drops_multiday_accumulations() -> None:
    """Rows whose period-count column isn't 1 are dropped (multi-day rain accumulations)."""
    content = _badc(
        b"Conventions,G,BADC-CSV,1\n",
        "ob_date,ob_day_cnt,prcp_amt,prcp_amt_q",
        b"2000-01-01 00:00:00,31,146.7,22576\n"  # 31-day accumulation -> dropped
        b"2000-01-02 00:00:00,1,3.7,2576\n",  # genuine single-day value -> kept
    )
    df = parse_values(
        content,
        time_column="ob_date",
        columns=["prcp_amt"],
        granularity="1d",
        period_count_column="ob_day_cnt",
    )
    assert df.to_dicts() == [
        {"date": dt.datetime(2000, 1, 2, tzinfo=UTC), "parameter": "prcp_amt", "value": 3.7, "quality": 2576.0},
    ]


def test_parse_values_scales_visibility_to_metres() -> None:
    """Visibility is stored in decametres and scaled to metres; hourly timestamps are preserved."""
    content = _badc(
        b"Conventions,G,BADC-CSV,1\n",
        "ob_time,visibility,visibility_q",
        b"2015-07-01 13:00:00,1900,6\n",  # 1900 decametres -> 19000 metres (19 km)
    )
    df = parse_values(
        content,
        time_column="ob_time",
        columns=["visibility"],
        granularity="1h",
        scale={"visibility": 10.0},
    )
    assert df.to_dicts() == [
        {
            "date": dt.datetime(2015, 7, 1, 13, 0, tzinfo=UTC),
            "parameter": "visibility",
            "value": 19000.0,
            "quality": 6.0,
        },
    ]


def test_parse_values_empty_input() -> None:
    """A file with no data rows yields an empty frame with the expected schema."""
    content = _badc(b"Conventions,G,BADC-CSV,1\n", "ob_date,prcp_amt", b"")
    df = parse_values(content, time_column="ob_date", columns=["prcp_amt"], granularity="1d")
    assert df.is_empty()
    assert df.columns == ["date", "parameter", "value", "quality"]


def _fake_jwt(exp: float) -> str:
    """Build a minimal unsigned JWT string carrying just an ``exp`` claim (base64url payload)."""
    import base64  # noqa: PLC0415
    import json  # noqa: PLC0415

    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"header.{payload}.signature"


def test_ceda_token_is_cached_until_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CEDA token is minted once and reused from cache until shortly before its ``exp`` claim."""
    import time  # noqa: PLC0415

    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415

    creds = ("user", "pass")
    download._TOKEN_CACHE.clear()  # noqa: SLF001
    settings = Settings(auth={"ceda": "user:pass"})

    calls = {"n": 0}

    def _fake_post(*_args: object, **_kwargs: object) -> object:
        calls["n"] += 1

        class _Resp:
            def raise_for_status(self) -> None: ...
            def json(self) -> dict:
                return {"access_token": _fake_jwt(time.time() + 3 * 24 * 3600)}

        return _Resp()

    monkeypatch.setattr(download.httpx, "post", _fake_post)

    first = download.get_ceda_token(settings)
    second = download.get_ceda_token(settings)
    assert first == second
    assert calls["n"] == 1  # second call served from cache, no re-mint

    # an expired cache entry forces a fresh mint
    token, _ = download._TOKEN_CACHE[creds]  # noqa: SLF001
    download._TOKEN_CACHE[creds] = (token, time.time() - 1)  # noqa: SLF001
    download.get_ceda_token(settings)
    assert calls["n"] == 2
    download._TOKEN_CACHE.clear()  # noqa: SLF001


def test_ceda_token_missing_credentials_returns_none() -> None:
    """With no CEDA credentials configured, token retrieval returns None rather than raising."""
    from wetterdienst.provider.metoffice.observation.download import get_ceda_token  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415

    assert get_ceda_token(Settings(auth={"ceda": None})) is None


@pytest.mark.parametrize(
    "body",
    [
        "<html>login page</html>",  # non-JSON body on a 200 (e.g. redirected login page)
        {"detail": "no token here"},  # JSON body missing the access_token field
        ["unexpected"],  # JSON that is not even an object
    ],
)
def test_ceda_token_bad_response_returns_none(body: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 whose body is not usable JSON with an access_token is an auth failure, not a crash."""
    import json  # noqa: PLC0415

    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415

    download._TOKEN_CACHE.clear()  # noqa: SLF001

    def _fake_post(*_args: object, **_kwargs: object) -> object:
        class _Resp:
            def raise_for_status(self) -> None: ...
            def json(self) -> object:
                if isinstance(body, str):
                    return json.loads(body)  # invalid JSON raises JSONDecodeError, like httpx does
                return body

        return _Resp()

    monkeypatch.setattr(download.httpx, "post", _fake_post)
    assert download.get_ceda_token(Settings(auth={"ceda": "user:pass"})) is None
    download._TOKEN_CACHE.clear()  # noqa: SLF001


def test_ceda_token_valid_until_falls_back_on_unreadable_payload() -> None:
    """A JWT whose payload is valid JSON but not a dict falls back to a short TTL, not a crash."""
    import base64  # noqa: PLC0415
    import json  # noqa: PLC0415
    import time  # noqa: PLC0415

    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415

    # payload decodes to JSON ``null`` -> ["exp"] would be a TypeError; must fall back, not raise
    payload = base64.urlsafe_b64encode(json.dumps(None).encode()).rstrip(b"=").decode()
    valid_until = download._token_valid_until(f"header.{payload}.signature")  # noqa: SLF001
    assert time.time() < valid_until <= time.time() + download._FALLBACK_TTL_SECONDS + 5  # noqa: SLF001


@pytest.mark.parametrize("body", [b"<html>temporary error</html>", b'["not", "a", "dict"]'])
def test_latest_release_version_bad_listing_returns_none(body: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-JSON or unexpectedly-shaped archive listing reads as 'no release', not a crash."""
    from wetterdienst.provider.metoffice.observation import fileindex  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415

    class _Content:
        def read(self) -> bytes:
            return body

    class _File:
        content = _Content()

    monkeypatch.setattr(fileindex, "download_file", lambda **_kwargs: _File())
    assert fileindex.latest_release_version(Settings(), token="t") is None  # noqa: S106


# ---------------------------------------------------------------------------
# Remote tests -- require a free CEDA account (WD_AUTH__CEDA=<username>:<password>).
# ---------------------------------------------------------------------------

pytest_credentials = pytest.mark.skipif(
    not MetOfficeObservationRequest.is_configured(),
    reason="CEDA credentials not set -- provide WD_AUTH__CEDA=<username>:<password>",
)


@pytest.mark.remote
@pytest_credentials
def test_metoffice_observation_stations() -> None:
    """The daily-rain catalogue resolves and contains the reference station."""
    df = (
        MetOfficeObservationRequest(parameters=[("daily", "rain", "precipitation_height")])
        .filter_by_station_id(LERWICK)
        .df
    )
    assert df.height == 1
    row = df.row(0, named=True)
    assert row["station_id"] == LERWICK
    assert row["resolution"] == "daily"
    assert row["dataset"] == "rain"
    assert row["name"]  # a non-empty station name
    assert 59.0 < row["latitude"] < 61.0  # Shetland
    assert -2.0 < row["longitude"] < -1.0


@pytest.mark.remote
@pytest_credentials
def test_metoffice_observation_values_daily_rain() -> None:
    """Daily precipitation returns one day-truncated row per day, all non-negative."""
    df = (
        MetOfficeObservationRequest(
            parameters=[("daily", "rain", "precipitation_height")],
            start_date=dt.datetime(2023, 7, 1, tzinfo=UTC),
            end_date=dt.datetime(2023, 7, 10, tzinfo=UTC),
        )
        .filter_by_station_id(LERWICK)
        .values.all()
        .df
    )
    assert not df.is_empty()
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["parameter"].unique().to_list() == ["precipitation_height"]
    # one value per day, timestamps truncated to midnight
    assert (df["date"] == df["date"].dt.truncate("1d")).all()
    assert df["date"].n_unique() == df.height
    assert df["value"].min() >= 0.0


@pytest.mark.remote
@pytest_credentials
def test_metoffice_observation_values_daily_temperature_one_row_per_day() -> None:
    """Daily temperature collapses multiple report types to a single row per day/parameter."""
    df = (
        MetOfficeObservationRequest(
            parameters=[("daily", "temperature")],
            start_date=dt.datetime(2023, 7, 1, tzinfo=UTC),
            end_date=dt.datetime(2023, 7, 5, tzinfo=UTC),
        )
        .filter_by_station_id(LERWICK)
        .values.all()
        .df
    )
    assert not df.is_empty()
    # no (date, parameter) duplicates -> report types were collapsed
    assert df.select("date", "parameter").is_unique().all()
    maxes = df.filter(pl.col("parameter") == "temperature_air_max_2m")
    mins = df.filter(pl.col("parameter") == "temperature_air_min_2m")
    if not maxes.is_empty() and not mins.is_empty():
        joined = maxes.join(mins, on="date", suffix="_min")
        assert (joined["value"] >= joined["value_min"]).all()
