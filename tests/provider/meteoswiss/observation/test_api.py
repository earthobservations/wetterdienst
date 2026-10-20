# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for MeteoSwiss observation API."""

from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import serve
from wetterdienst import Settings
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationRequest
from wetterdienst.provider.meteoswiss.observation import api as meteoswiss_api
from wetterdienst.util.network import File


@pytest.mark.remote
def test_meteoswiss_observation_api_stations() -> None:
    """Test that station metadata can be retrieved and is complete."""
    request = MeteoswissObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id("ABO")
    df = request.df
    assert not df.is_empty()
    assert df.get_column("name").to_list() == ["Adelboden"]
    assert df.get_column("region").to_list() == ["BE"]


@pytest.mark.remote
def test_meteoswiss_observation_api_daily() -> None:
    """Test daily values, spanning both the historical and recent data files."""
    request = MeteoswissObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2020, 1, 3, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("ABO")
    df = next(request.values().query()).df
    assert df.get_column("value").is_not_null().sum() == 3


@pytest.mark.remote
@pytest.mark.parametrize(
    "resolution",
    [
        "10_minutes",
        "hourly",
        "daily",
        "monthly",
        "annual",
    ],
)
def test_meteoswiss_observation_api_resolutions(resolution: str) -> None:
    """Test that all resolutions can be requested and yield tidy data.

    Monthly and annual values are dated to the first of the month/year, so a full-year
    window is used to reliably capture a value regardless of resolution.
    """
    # the 10-minute file holds the current value (tre200s0), every other resolution a mean
    parameter = "temperature_air_2m" if resolution == "10_minutes" else "temperature_air_mean_2m"
    request = MeteoswissObservationRequest(
        parameters=[(resolution, "data", parameter)],
        start=datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=datetime(2022, 12, 31, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("ABO")
    df = next(request.values().query()).df
    assert df.get_column("value").is_not_null().sum() > 0


_BASE = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn"
_STATIONS = (
    "station_abbr;station_name;station_canton;station_data_since;station_height_masl;"
    "station_coordinates_wgs84_lat;station_coordinates_wgs84_lon\n"
    "BER;Bern / Zollikofen;BE;01.01.1864;553.0;46.990744;7.464061\n"
)
_HEADER = "station_abbr;reference_timestamp;tre200h0\n"


def _hourly_values(monkeypatch: pytest.MonkeyPatch, start: str, end: str) -> tuple[pl.DataFrame, list[str]]:
    """Give the hourly values of BER for the bounds from a stub of the source, and the files that were read.

    The source keeps the hourly history of BER in files of a decade, named by the decade of their UTC time stamps. The
    last hour of 2009 (23:00 UTC) is in the 2000-2009 file, the first of 2010 (00:00 UTC) in the 2010-2019 file.
    """
    files = {
        "ogd-smn_ber_h_historical_2000-2009.csv": _HEADER + "BER;31.12.2009 23:00;5.3\n",
        "ogd-smn_ber_h_historical_2010-2019.csv": _HEADER + "BER;01.01.2010 00:00;4.9\n",
    }
    item = {"assets": {name: {"href": f"{_BASE}/ber/{name}"} for name in files}}
    read: list[str] = []

    def reader(body: str):  # noqa: ANN202
        def read_file(url: str) -> bytes:
            read.append(url.rsplit("/", 1)[-1])
            return body.encode("windows-1252")

        return read_file

    serve(
        monkeypatch,
        meteoswiss_api,
        {
            "ogd-smn_meta_stations.csv": _STATIONS.encode("windows-1252"),
            "/items/ber": json.dumps(item).encode("utf8"),
            **{name: reader(body) for name, body in files.items()},
        },
    )
    request = MeteoswissObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
    ).filter_by_station_id("BER")
    return request.values().all().df, read


@pytest.mark.parametrize(
    ("start", "end"),
    [
        # the same instants, 2009-12-31 22:30 to 23:00 UTC, in two notations: the second is already in 2010
        ("2009-12-31T22:30:00+00:00", "2009-12-31T23:00:00+00:00"),
        ("2010-01-01T00:30:00+02:00", "2010-01-01T01:00:00+02:00"),
    ],
)
def test_meteoswiss_observation_decade_file_follows_utc_year(
    monkeypatch: pytest.MonkeyPatch,
    start: str,
    end: str,
) -> None:
    """Test that the decade file is chosen by the UTC year of the bounds, not by the year as written (GH-2680)."""
    df, read = _hourly_values(monkeypatch, start, end)
    assert read == ["ogd-smn_ber_h_historical_2000-2009.csv"]
    assert df.get_column("value").to_list() == [5.3]
    assert df.get_column("timestamp").to_list() == [datetime(2009, 12, 31, 23, tzinfo=ZoneInfo("UTC"))]


def test_meteoswiss_observation_decade_file_zone_behind_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the other direction: 19:30 on 2009-12-31 in a zone five hours behind UTC is already 2010 in UTC."""
    df, read = _hourly_values(monkeypatch, "2009-12-31T19:00:00-05:00", "2009-12-31T19:30:00-05:00")
    assert read == ["ogd-smn_ber_h_historical_2010-2019.csv"]
    assert df.get_column("value").to_list() == [4.9]


def test_meteoswiss_observation_decade_files_span_the_new_year(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that bounds across New Year in UTC read both decade files."""
    df, read = _hourly_values(monkeypatch, "2009-12-31T23:00:00+00:00", "2010-01-01T00:00:00+00:00")
    assert sorted(read) == ["ogd-smn_ber_h_historical_2000-2009.csv", "ogd-smn_ber_h_historical_2010-2019.csv"]
    assert df.get_column("value").to_list() == [5.3, 4.9]


def _serve_station_files(monkeypatch: pytest.MonkeyPatch, assets: dict[str, str]) -> None:
    """Serve the stations, the STAC item of BER naming the assets and the files by name."""
    item_body = json.dumps({"assets": {name: {"href": f"{_BASE}/ber/{name}"} for name in assets}}).encode()

    def download_file(url: str, **_: object) -> File:
        if "ogd-smn_meta_stations.csv" in url:
            return File(url=url, content=BytesIO(_STATIONS.encode("windows-1252")), status=200)
        if "/items/ber" in url:
            return File(url=url, content=BytesIO(item_body), status=200)
        body = assets[url.rsplit("/", 1)[-1]]
        return File(url=url, content=BytesIO(body.encode("windows-1252")), status=200)

    monkeypatch.setattr(meteoswiss_api, "download_file", download_file)


def _ber_values(resolution: str = "daily", parameter: str = "temperature_air_mean_2m") -> pl.DataFrame:
    request = MeteoswissObservationRequest(
        parameters=[(resolution, "data", parameter)],
        start="2020-01-01T00:00:00+00:00",
        end="2020-01-03T00:00:00+00:00",
        settings=Settings(cache_disable=True),
    ).filter_by_station_id("BER")
    return request.values().all().df


def test_meteoswiss_observation_daily_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The daily files of BER, the historical one and the recent one, stamped at midnight and read as UTC (GH-2627)."""
    _serve_station_files(
        monkeypatch,
        {
            "ogd-smn_ber_d_historical.csv": "station_abbr;reference_timestamp;tre200d0\nBER;01.01.2020 00:00;1.5\n",
            "ogd-smn_ber_d_recent.csv": "station_abbr;reference_timestamp;tre200d0\nBER;02.01.2020 00:00;-0.4\n",
        },
    )
    df = _ber_values().sort("timestamp")
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.select("resolution", "dataset", "station_id", "parameter").unique().rows() == [
        ("daily", "data", "BER", "temperature_air_mean_2m")
    ]
    assert df.get_column("timestamp").to_list() == [
        datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 2, tzinfo=ZoneInfo("UTC")),
    ]
    assert df.get_column("value").to_list() == [1.5, -0.4]


def test_meteoswiss_observation_a_station_without_a_file_of_the_resolution_comes_out_as_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A station whose item lists no file of the resolution (BER has only the hourly decades here) is no rows."""
    _serve_station_files(monkeypatch, {"ogd-smn_ber_h_historical_2010-2019.csv": ""})
    df = _ber_values()
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
