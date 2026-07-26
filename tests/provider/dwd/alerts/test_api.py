# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the DWD CAP weather-alerts request/result API."""

from __future__ import annotations

import datetime as dt
import io
import json
import zipfile
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Wetterdienst
from wetterdienst.provider.dwd.alerts import (
    DwdWeatherAlertGranularity,
    DwdWeatherAlertLanguage,
    DwdWeatherAlertRequest,
    DwdWeatherAlertResult,
)
from wetterdienst.provider.dwd.alerts.api import _SCHEMA

from .test_parser import CAP_XML

UTC = ZoneInfo("UTC")


def test_registry_resolves_dwd_alerts() -> None:
    """Verify the provider is registered and resolvable via the Wetterdienst factory."""
    assert Wetterdienst("dwd", "alerts") is DwdWeatherAlertRequest


def test_url_community_english_default() -> None:
    """Verify the default request targets the community LATEST English snapshot."""
    request = DwdWeatherAlertRequest()
    assert request.granularity is DwdWeatherAlertGranularity.COMMUNITY
    assert request.language is DwdWeatherAlertLanguage.ENGLISH
    assert request.url == (
        "https://opendata.dwd.de/weather/alerts/cap/COMMUNEUNION_DWD_STAT/"
        "Z_CAP_C_EDZW_LATEST_PVW_STATUS_PREMIUMDWD_COMMUNEUNION_EN.zip"
    )


def test_url_district_german() -> None:
    """Verify the district/German request targets the correct snapshot."""
    request = DwdWeatherAlertRequest(granularity="district", language="de")
    assert request.url == (
        "https://opendata.dwd.de/weather/alerts/cap/DISTRICT_DWD_STAT/"
        "Z_CAP_C_EDZW_LATEST_PVW_STATUS_PREMIUMDWD_DISTRICT_DE.zip"
    )


def test_dateless_request_resolves_to_latest() -> None:
    """Verify a request without a date resolves to the LATEST alias with an unknown production time."""
    url, snapshot = DwdWeatherAlertRequest()._resolve_snapshot()  # noqa: SLF001
    assert url.endswith("Z_CAP_C_EDZW_LATEST_PVW_STATUS_PREMIUMDWD_COMMUNEUNION_EN.zip")
    assert snapshot is None


def test_date_parsing_assumes_utc() -> None:
    """Verify naive date input is interpreted as UTC and tz-aware input is converted to UTC."""
    naive = DwdWeatherAlertRequest(date="2026-07-26T10:00:00")
    assert naive.date == dt.datetime(2026, 7, 26, 10, 0, tzinfo=UTC)
    aware = DwdWeatherAlertRequest(date="2026-07-26T12:00:00+02:00")
    assert aware.date == dt.datetime(2026, 7, 26, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_date_means_latest(value: str) -> None:
    """Verify an empty/whitespace date string is treated as 'latest' (None), not an invalid date."""
    request = DwdWeatherAlertRequest(date=value)
    assert request.date is None
    url, snapshot = request._resolve_snapshot()  # noqa: SLF001
    assert url.endswith("_COMMUNEUNION_EN.zip")
    assert snapshot is None


def _fake_listing(*timestamps: str) -> list[dict[str, str]]:
    return [
        {
            "name": (
                "https://opendata.dwd.de/weather/alerts/cap/COMMUNEUNION_DWD_STAT/"
                f"Z_CAP_C_EDZW_{ts}_PVW_STATUS_PREMIUMDWD_COMMUNEUNION_EN.zip"
            ),
            "type": "file",
        }
        for ts in timestamps
    ]


def test_resolve_snapshot_selects_newest_at_or_before_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the newest snapshot produced at or before the requested date is chosen."""
    listing = _fake_listing("20260726100000", "20260726103220", "20260726110000")
    monkeypatch.setattr("wetterdienst.provider.dwd.alerts.api.list_remote_directory_fsspec", lambda *_a, **_k: listing)

    request = DwdWeatherAlertRequest(date="2026-07-26T10:45:00")
    url, snapshot = request._resolve_snapshot()  # noqa: SLF001
    assert snapshot == dt.datetime(2026, 7, 26, 10, 32, 20, tzinfo=UTC)
    assert url.endswith("Z_CAP_C_EDZW_20260726103220_PVW_STATUS_PREMIUMDWD_COMMUNEUNION_EN.zip")


def test_resolve_snapshot_before_window_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a date older than the whole rolling window raises a helpful error."""
    listing = _fake_listing("20260726100000", "20260726110000")
    monkeypatch.setattr("wetterdienst.provider.dwd.alerts.api.list_remote_directory_fsspec", lambda *_a, **_k: listing)

    request = DwdWeatherAlertRequest(date="2026-07-01T00:00:00")
    with pytest.raises(ValueError, match="rolling ~48-hour window"):
        request._resolve_snapshot()  # noqa: SLF001


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("community", DwdWeatherAlertGranularity.COMMUNITY),
        ("communeunion", DwdWeatherAlertGranularity.COMMUNITY),
        ("gemeinde", DwdWeatherAlertGranularity.COMMUNITY),
        ("DISTRICT", DwdWeatherAlertGranularity.DISTRICT),
        ("landkreis", DwdWeatherAlertGranularity.DISTRICT),
    ],
)
def test_granularity_parsing(value: str, expected: DwdWeatherAlertGranularity) -> None:
    """Verify granularity aliases are accepted case-insensitively."""
    assert DwdWeatherAlertRequest(granularity=value).granularity is expected


def test_invalid_granularity_raises() -> None:
    """Verify an unknown granularity is rejected."""
    with pytest.raises(ValueError, match="granularity"):
        DwdWeatherAlertRequest(granularity="bogus")


def test_invalid_language_raises() -> None:
    """Verify an unknown language is rejected."""
    with pytest.raises(ValueError, match="language"):
        DwdWeatherAlertRequest(language="it")


def _make_zip(*files: bytes) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for index, content in enumerate(files):
            archive.writestr(f"alert_{index}.xml", content)
    buffer.seek(0)
    return buffer


def test_parse_archive_builds_dataframe() -> None:
    """Verify an archive of CAP files is flattened into the schema-conformant DataFrame."""
    alerts = DwdWeatherAlertRequest._parse_archive(_make_zip(CAP_XML, CAP_XML))  # noqa: SLF001
    df = DwdWeatherAlertRequest._build_dataframe(alerts)  # noqa: SLF001
    assert df.height == 2
    assert df.schema == pl.Schema(_SCHEMA)
    assert df["event"].to_list() == ["gale-force gusts", "gale-force gusts"]
    assert df["warncell_ids"].to_list()[0] == ["809272121", "809276148"]
    # nested fields are JSON-encoded in the frame
    assert json.loads(df["parameters"][0]) == [
        {"name": "gusts", "value": "65-75 [km/h]"},
        {"name": "wind direction", "value": "west"},
    ]
    assert json.loads(df["geometry"][0])["type"] == "MultiPolygon"


def test_empty_archive_yields_empty_frame() -> None:
    """Verify an empty snapshot (no active warnings) produces an empty, schema-conformant frame."""
    df = DwdWeatherAlertRequest._build_dataframe(DwdWeatherAlertRequest._parse_archive(_make_zip()))  # noqa: SLF001
    assert df.is_empty()
    assert df.schema == pl.Schema(_SCHEMA)


def test_query_wraps_download_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a download failure (e.g. a 404 from a rolled-off snapshot) becomes a clean OSError."""
    from wetterdienst.util.network import File  # noqa: PLC0415

    def fake_download(*_a: object, **_k: object) -> File:
        return File(url="http://x", content=FileNotFoundError("404"), status=404)

    monkeypatch.setattr("wetterdienst.provider.dwd.alerts.api.download_file", fake_download)
    with pytest.raises(OSError, match="could not download weather alerts snapshot"):
        DwdWeatherAlertRequest().query()


def test_query_wraps_bad_zip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a non-zip 200 body becomes a clean OSError instead of a raw BadZipFile."""
    from wetterdienst.util.network import File  # noqa: PLC0415

    def fake_download(*_a: object, **_k: object) -> File:
        return File(url="http://x", content=io.BytesIO(b"<html>error</html>"), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.alerts.api.download_file", fake_download)
    with pytest.raises(OSError, match="not a valid zip archive"):
        DwdWeatherAlertRequest().query()


def test_result_formats_round_trip() -> None:
    """Verify to_dict/to_geojson/to_csv render the parsed alerts consistently."""
    alerts = DwdWeatherAlertRequest._parse_archive(_make_zip(CAP_XML))  # noqa: SLF001
    df = DwdWeatherAlertRequest._build_dataframe(alerts)  # noqa: SLF001
    snapshot = dt.datetime(2026, 7, 26, 8, 0, tzinfo=UTC)
    result = DwdWeatherAlertResult(df, DwdWeatherAlertGranularity.COMMUNITY, DwdWeatherAlertLanguage.ENGLISH, snapshot)

    data = result.to_dict()
    assert data["snapshot"] == "2026-07-26T08:00:00+00:00"
    assert len(data["alerts"]) == 1
    alert = data["alerts"][0]
    assert alert["event"] == "gale-force gusts"
    assert alert["geometry"]["type"] == "MultiPolygon"
    assert alert["parameters"] == [
        {"name": "gusts", "value": "65-75 [km/h]"},
        {"name": "wind direction", "value": "west"},
    ]
    # timestamps are serialised as ISO strings
    assert alert["sent"].startswith("2026-07-26T07:23:00")

    fc = json.loads(result.to_geojson())
    assert fc["type"] == "FeatureCollection"
    assert fc["snapshot"] == "2026-07-26T08:00:00+00:00"
    feature = fc["features"][0]
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert "geometry" not in feature["properties"]
    assert feature["properties"]["event"] == "gale-force gusts"

    csv = result.to_csv()
    header, first = csv.splitlines()[0], csv.splitlines()[1]
    assert "warncell_ids" in header
    # list column is comma-joined for CSV
    assert "809272121,809276148" in first


def test_to_format_invalid_raises() -> None:
    """Verify an unsupported output format is rejected."""
    result = DwdWeatherAlertResult(
        pl.DataFrame(schema=_SCHEMA),
        DwdWeatherAlertGranularity.COMMUNITY,
        DwdWeatherAlertLanguage.ENGLISH,
    )
    with pytest.raises(ValueError, match="format"):
        result.to_format("xml")


@pytest.mark.remote
@pytest.mark.parametrize("granularity", ["community", "district"])
def test_query_live_snapshot(granularity: str) -> None:
    """Verify a live snapshot downloads and parses into the expected schema.

    The number of active warnings is weather-dependent (possibly zero), so only structural
    invariants are asserted.
    """
    result = DwdWeatherAlertRequest(granularity=granularity).query()
    assert result.df.schema == pl.Schema(_SCHEMA)
    assert result.snapshot is None
    for alert in result.to_dict()["alerts"]:
        assert alert["alert_id"]
        geometry = alert["geometry"]
        if geometry is not None:
            assert geometry["type"] == "MultiPolygon"
            assert geometry["coordinates"]


@pytest.mark.remote
def test_query_live_timestamped_snapshot() -> None:
    """Verify selecting a snapshot from the rolling window returns a snapshot at or before the date."""
    target = dt.datetime.now(UTC) - dt.timedelta(hours=6)
    result = DwdWeatherAlertRequest(granularity="district", date=target).query()
    assert result.df.schema == pl.Schema(_SCHEMA)
    assert result.snapshot is not None
    assert result.snapshot <= target


@pytest.mark.remote
def test_query_live_date_before_window_raises() -> None:
    """Verify a date older than the rolling window raises a helpful error against the live listing."""
    with pytest.raises(ValueError, match="rolling ~48-hour window"):
        DwdWeatherAlertRequest(date="2000-01-01T00:00:00").query()
