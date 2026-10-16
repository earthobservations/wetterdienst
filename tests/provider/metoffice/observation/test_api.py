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
            "elevation": 22.0,
            "start_timestamp": dt.datetime(1989, 1, 1, tzinfo=UTC),
            "end_timestamp": dt.datetime(2003, 12, 31, tzinfo=UTC),
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
        # max over {4.8, 5.4, 5.1} == the 24h value 5.4; the flags are those of the extreme row
        {
            "timestamp": dt.datetime(2000, 1, 1, tzinfo=UTC),
            "parameter": "max_air_temp",
            "value": 5.4,
            "quality_flags": "4",
        },
        # min over {0.3, 0.3, 2.8} == 0.3
        {
            "timestamp": dt.datetime(2000, 1, 1, tzinfo=UTC),
            "parameter": "min_air_temp",
            "value": 0.3,
            "quality_flags": "6",
        },
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
        {
            "timestamp": dt.datetime(2000, 1, 2, tzinfo=UTC),
            "parameter": "prcp_amt",
            "value": 3.7,
            "quality_flags": "2576",
        },
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
            "timestamp": dt.datetime(2015, 7, 1, 13, 0, tzinfo=UTC),
            "parameter": "visibility",
            "value": 19000.0,
            "quality_flags": "6",
        },
    ]


def test_parse_values_keeps_the_mesql_code_as_the_text_the_file_writes() -> None:
    """MESQL comes back as the text the file writes, not as a float (GH-2018, GH-2758).

    The CEDA documentation (dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html): "This _q attribute is a
    five digit number (of the form MESQL), where each digit describes one aspect of the quality of a meteorological
    element": M qc_marker, E qc_estimate, S qc_status, Q qc_query, L qc_level. The files write the integer, so
    "2576" is MESQL 02576; a float would give "2576.0".
    """
    content = _badc(
        b"Conventions,G,BADC-CSV,1\n",
        "ob_date,ob_day_cnt,prcp_amt,prcp_amt_q",
        b"2000-01-01 00:00:00,1,3.7,2576\n2000-01-02 00:00:00,1,0.0,20001\n2000-01-03 00:00:00,1,1.1,\n",
    )
    df = parse_values(
        content, time_column="ob_date", columns=["prcp_amt"], granularity="1d", period_count_column="ob_day_cnt"
    ).sort("timestamp")
    assert df.get_column("quality_flags").to_list() == ["2576", "20001", None]


def test_parse_values_keeps_the_na_of_a_day_that_has_no_value() -> None:
    """An `NA` beside a value of its day is no value and no flag; a day of nothing but `NA` keeps it (GH-2759)."""
    content = _badc(
        b"Conventions,G,BADC-CSV,1\n",
        "ob_end_time,ob_hour_count,met_domain_name,max_air_temp,max_air_temp_q,min_air_temp,min_air_temp_q",
        b"2000-01-01 09:00:00,12,AWSDLY,NA,NA,0.3,6\n"
        b"2000-01-01 21:00:00,12,AWSDLY,5.1,6,NA,NA\n"
        b"2000-01-02 09:00:00,12,AWSDLY,NA,NA,NA,NA\n",
    )
    df = parse_values(
        content,
        time_column="ob_end_time",
        columns=["max_air_temp", "min_air_temp"],
        granularity="1d",
        min_columns=frozenset({"min_air_temp"}),
    ).sort("parameter", "timestamp")
    assert df.select("parameter", "timestamp", "value", "quality_flags").rows() == [
        ("max_air_temp", dt.datetime(2000, 1, 1, tzinfo=UTC), 5.1, "6"),
        ("max_air_temp", dt.datetime(2000, 1, 2, tzinfo=UTC), None, "raw:NA"),
        ("min_air_temp", dt.datetime(2000, 1, 1, tzinfo=UTC), 0.3, "6"),
        ("min_air_temp", dt.datetime(2000, 1, 2, tzinfo=UTC), None, "raw:NA"),
    ]


def test_parse_values_empty_input() -> None:
    """A file with no data rows yields an empty frame with the expected schema."""
    content = _badc(b"Conventions,G,BADC-CSV,1\n", "ob_date,prcp_amt", b"")
    df = parse_values(content, time_column="ob_date", columns=["prcp_amt"], granularity="1d")
    assert df.is_empty()
    assert df.columns == ["timestamp", "parameter", "value", "quality_flags"]


def _fake_jwt(exp: float) -> str:
    """Build a minimal unsigned JWT string carrying just an ``exp`` claim (base64url payload)."""
    import base64  # noqa: PLC0415
    import json  # noqa: PLC0415

    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"header.{payload}.signature"


def test_ceda_token_is_cached_until_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CEDA token is minted once and reused from cache until shortly before its ``exp`` claim."""
    import json  # noqa: PLC0415
    import time  # noqa: PLC0415
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    download._TOKEN_CACHE.clear()  # noqa: SLF001
    settings = Settings(auth={"ceda": "user:pass"})
    # the cache is keyed by the secrets themselves, not by what they hold
    creds = settings.auth.ceda

    calls = {"n": 0}

    def _fake_post(*_args: object, **_kwargs: object) -> File:
        calls["n"] += 1
        body = json.dumps({"access_token": _fake_jwt(time.time() + 3 * 24 * 3600)}).encode()
        return File(url=download._TOKEN_URL, content=BytesIO(body), status=200)  # noqa: SLF001

    monkeypatch.setattr(download, "post_file", _fake_post)

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
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    download._TOKEN_CACHE.clear()  # noqa: SLF001

    def _fake_post(*_args: object, **_kwargs: object) -> File:
        payload = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        return File(url=download._TOKEN_URL, content=BytesIO(payload), status=200)  # noqa: SLF001

    monkeypatch.setattr(download, "post_file", _fake_post)
    assert download.get_ceda_token(Settings(auth={"ceda": "user:pass"})) is None
    download._TOKEN_CACHE.clear()  # noqa: SLF001


def test_ceda_token_redirect_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """CEDA answering the token request with a redirect is an auth failure, named by its status."""
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    download._TOKEN_CACHE.clear()  # noqa: SLF001

    def _fake_post(*_args: object, **_kwargs: object) -> File:
        return File(url=download._TOKEN_URL, content=BytesIO(b""), status=302)  # noqa: SLF001

    monkeypatch.setattr(download, "post_file", _fake_post)
    assert download.get_ceda_token(Settings(auth={"ceda": "user:pass"})) is None
    assert not download._TOKEN_CACHE  # noqa: SLF001


def test_ceda_token_exchange_that_never_reached_ceda_raises_no_internet(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token exchange that never reached CEDA raises `NoInternetError`, and is not cached (GH-2640)."""
    from wetterdienst.exceptions import NoInternetError  # noqa: PLC0415
    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    download._TOKEN_CACHE.clear()  # noqa: SLF001

    def _fake_post(*_args: object, **_kwargs: object) -> File:
        return File(
            url=download._TOKEN_URL,  # noqa: SLF001
            content=NoInternetError("Cannot connect to host services.ceda.ac.uk:443"),
            status=503,
        )

    monkeypatch.setattr(download, "post_file", _fake_post)
    with pytest.raises(NoInternetError):
        download.get_ceda_token(Settings(auth={"ceda": "user:pass"}))
    assert not download._TOKEN_CACHE  # noqa: SLF001


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
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.metoffice.observation import fileindex  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    file = File(url=fileindex._RELEASE_LISTING_URL, content=BytesIO(body), status=200)  # noqa: SLF001
    monkeypatch.setattr(fileindex, "download_file", lambda **_kwargs: file)
    assert fileindex.latest_release_version(Settings(), token="t") is None  # noqa: S106


def test_metoffice_station_list_gives_the_historic_county_as_region(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station's `region` is the county MIDAS files it under, as published (GH-2019).

    The catalogue gives every station a `historic_county`, the first path component of its data files
    (`shetland`), and the request left `region` null; `station_file_name` stays out of the frame.
    """
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.metoffice.observation import api  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    content = _badc(
        b"Conventions,G,BADC-CSV,1\ntitle,G,Midas-open: Station site metadata\n",
        "src_id,station_name,station_file_name,historic_county,authority,"
        "station_latitude,station_longitude,station_elevation,first_year,last_year",
        b"00001,FOULA,foula,shetland,Met Office,60.154,-2.074,22,1989,2003\n"
        b"00009,LERWICK,lerwick,shetland,Met Office,60.139,-1.183,82,1930,2025\n"
        b"00036,KEW GARDENS,kew-gardens,surrey,Met Office,51.478,-0.295,5,1901,2025\n",
    )
    monkeypatch.setattr(api, "get_ceda_token", lambda _settings: "token")
    monkeypatch.setattr(api, "latest_release_version", lambda _settings, _token: "202507")
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(content), status=200),
    )

    df = MetOfficeObservationRequest(parameters=[("daily", "rain", "precipitation_amount")]).all().df

    assert df.select("station_id", "name", "region").rows() == [
        ("00001", "FOULA", "shetland"),
        ("00009", "LERWICK", "shetland"),
        ("00036", "KEW GARDENS", "surrey"),
    ]
    assert "station_file_name" not in df.columns


@pytest.mark.parametrize("status", [401, 403])
def test_ceda_token_exchange_that_ceda_refuses_raises_credential_rejected_error(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """A username and password CEDA refuses is raised, naming the setting and not them; no token is cached (GH-3018)."""
    from wetterdienst.exceptions import CredentialRejectedError  # noqa: PLC0415
    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    download._TOKEN_CACHE.clear()  # noqa: SLF001

    def _fake_post(*_args: object, **_kwargs: object) -> File:
        return File(url=download._TOKEN_URL, content=OSError(f"{status}, message='refused'"), status=status)  # noqa: SLF001

    monkeypatch.setattr(download, "post_file", _fake_post)
    with pytest.raises(CredentialRejectedError, match=f"HTTP {status}") as raised:
        download.get_ceda_token(Settings(auth={"ceda": "ceda-user:ceda-secret"}))
    assert "WD_AUTH__CEDA" in str(raised.value)
    assert "ceda-user" not in f"{raised.value!s}{raised.value!r}"
    assert "ceda-secret" not in f"{raised.value!s}{raised.value!r}"
    assert not download._TOKEN_CACHE  # noqa: SLF001


def test_ceda_token_exchange_that_failed_otherwise_still_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only a refusal (401, 403) is the credential's: any other failed exchange keeps its warning and no token."""
    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    download._TOKEN_CACHE.clear()  # noqa: SLF001

    def _fake_post(*_args: object, **_kwargs: object) -> File:
        return File(url=download._TOKEN_URL, content=OSError("400, message='bad request'"), status=400)  # noqa: SLF001

    monkeypatch.setattr(download, "post_file", _fake_post)
    assert download.get_ceda_token(Settings(auth={"ceda": "user:pass"})) is None


@pytest.mark.parametrize("status", [401, 403])
def test_metoffice_station_list_raises_credential_rejected_error_for_a_refused_token(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """A token CEDA refuses for the station catalogue is raised, not read as a dataset without stations (GH-3018)."""
    from wetterdienst.exceptions import CredentialRejectedError  # noqa: PLC0415
    from wetterdienst.provider.metoffice.observation import api  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    monkeypatch.setattr(api, "get_ceda_token", lambda _settings: "token")
    monkeypatch.setattr(api, "latest_release_version", lambda _settings, _token: "202507")
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=OSError(f"{status}, message='refused'"), status=status),
    )
    request = MetOfficeObservationRequest(parameters=[("daily", "rain", "precipitation_amount")])
    with pytest.raises(CredentialRejectedError, match=f"HTTP {status}"):
        request.all()


@pytest.mark.parametrize("status", [401, 403])
def test_metoffice_values_raise_credential_rejected_error_for_a_refused_token(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """A token CEDA refuses for a data file is raised, where a year the archive lacks (404) is not (GH-3018)."""
    from wetterdienst.exceptions import CredentialRejectedError  # noqa: PLC0415
    from wetterdienst.provider.metoffice.observation import api  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=OSError(f"{status}, message='refused'"), status=status),
    )
    values = object.__new__(api.MetOfficeObservationValues)
    with pytest.raises(CredentialRejectedError, match=f"HTTP {status}"):
        values._download("https://dap.ceda.ac.uk/badc/x.csv", Settings(cache_disable=True), "token")  # noqa: SLF001


@pytest.mark.parametrize("status", [401, 403])
def test_metoffice_release_listing_that_refuses_the_token_raises_credential_rejected_error(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """The release listing is sent the token, and comes first: its refusal is the token's."""
    from wetterdienst.exceptions import CredentialRejectedError  # noqa: PLC0415
    from wetterdienst.provider.metoffice.observation import fileindex  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    monkeypatch.setattr(
        fileindex,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=OSError(f"{status}, message='refused'"), status=status),
    )
    with pytest.raises(CredentialRejectedError, match=f"HTTP {status}"):
        fileindex.latest_release_version(Settings(cache_disable=True), "token")


def test_metoffice_release_listing_that_fails_otherwise_stays_a_download_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only a refusal is the credential's: a 404 of the listing is a download error as before (GH-2519)."""
    from wetterdienst.exceptions import DownloadError  # noqa: PLC0415
    from wetterdienst.provider.metoffice.observation import fileindex  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    monkeypatch.setattr(
        fileindex,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=FileNotFoundError("404"), status=404),
    )
    with pytest.raises(DownloadError):
        fileindex.latest_release_version(Settings(cache_disable=True), "token")


def test_a_token_ceda_refuses_is_forgotten() -> None:
    """A refused token leaves the cache, so a revoked one is minted again and not refused for its three days."""
    import time  # noqa: PLC0415

    from wetterdienst.exceptions import CredentialRejectedError  # noqa: PLC0415
    from wetterdienst.provider.metoffice.observation import download  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import File  # noqa: PLC0415

    settings = Settings(auth={"ceda": "user:pass"})
    download._TOKEN_CACHE.clear()  # noqa: SLF001
    download._TOKEN_CACHE[settings.auth.ceda] = ("token", time.time() + 3600)  # noqa: SLF001
    refused = File(url="https://dap.ceda.ac.uk/x", content=OSError("403, message='refused'"), status=403)
    with pytest.raises(CredentialRejectedError):
        download.raise_if_ceda_rejected(refused, settings)
    assert not download._TOKEN_CACHE  # noqa: SLF001


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
        MetOfficeObservationRequest(parameters=[("daily", "rain", "precipitation_amount")])
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
            parameters=[("daily", "rain", "precipitation_amount")],
            start=dt.datetime(2023, 7, 1, tzinfo=UTC),
            end=dt.datetime(2023, 7, 10, tzinfo=UTC),
        )
        .filter_by_station_id(LERWICK)
        .values()
        .all()
        .df
    )
    assert not df.is_empty()
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["parameter"].unique().to_list() == ["precipitation_amount"]
    # one value per day, timestamps truncated to midnight
    assert (df["timestamp"] == df["timestamp"].dt.truncate("1d")).all()
    assert df["timestamp"].n_unique() == df.height
    assert df["value"].min() >= 0.0


@pytest.mark.remote
@pytest_credentials
def test_metoffice_observation_values_daily_temperature_one_row_per_day() -> None:
    """Daily temperature collapses multiple report types to a single row per day/parameter."""
    df = (
        MetOfficeObservationRequest(
            parameters=[("daily", "temperature")],
            start=dt.datetime(2023, 7, 1, tzinfo=UTC),
            end=dt.datetime(2023, 7, 5, tzinfo=UTC),
        )
        .filter_by_station_id(LERWICK)
        .values()
        .all()
        .df
    )
    assert not df.is_empty()
    # no (timestamp, parameter) duplicates -> report types were collapsed
    assert df.select("timestamp", "parameter").is_unique().all()
    maxes = df.filter(pl.col("parameter") == "temperature_air_max_2m")
    mins = df.filter(pl.col("parameter") == "temperature_air_min_2m")
    if not maxes.is_empty() and not mins.is_empty():
        joined = maxes.join(mins, on="timestamp", suffix="_min")
        assert (joined["value"] >= joined["value_min"]).all()
