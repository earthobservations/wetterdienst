# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for RMI (Royal Meteorological Institute of Belgium) AWS observation provider."""

import datetime as dt
import json
import logging
from io import BytesIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import polars as pl
import pytest

import wetterdienst.provider.rmi.observation.api as rmi_api
from wetterdienst.exceptions import NoInternetError
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

# Uccle (Ukkel) — RMI headquarters, the reference station used across the remote tests.
UCCLE = "6447"
UTC = ZoneInfo("UTC")

# A minimal feature schema (numberMatched + timestamp + one parameter) for the pagination tests.
_SCHEMA = pl.Schema(
    {
        "numberMatched": pl.Int64,
        "features": pl.List(
            pl.Struct({"properties": pl.Struct({"timestamp": pl.String, "temp_dry_shelter_avg": pl.Float64})})
        ),
    },
)


def _hourly_dataset() -> rmi_api.DatasetModel:
    """Return the hourly grouped default dataset from the metadata model."""
    resolution = next(
        resolution for resolution in rmi_api.RmiObservationRequest.metadata if resolution.name == "hourly"
    )
    return next(iter(resolution))


def _feature_file(count: int, start: int = 0, number_matched: int | None = None) -> File:
    """Build a WFS GeoJSON response File with ``count`` hourly feature records.

    ``number_matched`` populates the response's ``numberMatched`` total; when omitted the key is
    absent (exercising the short-page fallback).
    """
    features = [
        {"properties": {"timestamp": "2023-06-01T00:00:00Z", "temp_dry_shelter_avg": float(index)}}
        for index in range(start, start + count)
    ]
    payload: dict = {"features": features}
    if number_matched is not None:
        payload["numberMatched"] = number_matched
    return File(url="", content=BytesIO(json.dumps(payload).encode()), status=200)


def _iter_pages(values: rmi_api.RmiObservationValues) -> list[pl.DataFrame]:
    return list(
        values._iter_value_pages("aws_1hour", "code = 6447", _SCHEMA, Settings(cache_disable=True)),  # noqa: SLF001
    )


def test_metadata_resolutions() -> None:
    """RMI exposes 10-minute, hourly and daily resolutions."""
    resolutions = {resolution.name for resolution in rmi_api.RmiObservationRequest.metadata}
    assert resolutions == {"10_minutes", "hourly", "daily"}


def test_metadata_no_auth() -> None:
    """RMI's open data service requires no authentication."""
    assert rmi_api.RmiObservationRequest.metadata.auth is False


@pytest.mark.parametrize(
    "raw",
    ["2023-06-01T00:00:00Z", "2023-06-01T00:00:00.000000Z"],
)
def test_parse_utc_z_tolerates_optional_fractional_seconds(raw: str) -> None:
    """Both second-precision and fractional-seconds UTC-Z timestamps parse to the same UTC instant."""
    date = pl.select(rmi_api._parse_utc_z(pl.lit(raw))).item()  # noqa: SLF001
    assert date == dt.datetime(2023, 6, 1, tzinfo=UTC)


def test_parse_utc_z_null_stays_null() -> None:
    """A null timestamp (e.g. an active station's date_end) parses to null rather than raising."""
    date = pl.select(rmi_api._parse_utc_z(pl.lit(None, dtype=pl.String))).item()  # noqa: SLF001
    assert date is None


def test_values_schema_parses_timestamp_and_mapped_parameters() -> None:
    """The per-dataset feature schema parses the timestamp and every mapped parameter column."""
    dataset = _hourly_dataset()
    schema = rmi_api._values_schema(dataset.parameters)  # noqa: SLF001
    content = BytesIO(
        json.dumps(
            {"features": [{"properties": {"timestamp": "2023-06-01T00:00:00Z", "temp_dry_shelter_avg": 15.27}}]},
        ).encode(),
    )
    df = pl.read_json(content, schema=schema)
    df = df.select(pl.col("features").explode().struct.field("properties")).unnest("properties")
    assert "timestamp" in df.columns
    assert {parameter.name_original for parameter in dataset.parameters} <= set(df.columns)
    assert df.get_column("temp_dry_shelter_avg").to_list() == [15.27]


def test_iter_value_pages_walks_all_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pagination advances startIndex until a short (< limit) page and yields every page."""
    monkeypatch.setattr(rmi_api, "_PAGE_LIMIT", 2)
    pages = {0: 2, 2: 2, 4: 1}
    indices: list[int] = []

    def fake_download_file(*, url: str, **_: object) -> File:
        start_index = int(url.split("startIndex=")[1].split("&", maxsplit=1)[0])
        indices.append(start_index)
        return _feature_file(pages[start_index], start=start_index)

    monkeypatch.setattr(rmi_api, "download_file", fake_download_file)
    dfs = _iter_pages(object.__new__(rmi_api.RmiObservationValues))
    assert indices == [0, 2, 4]
    assert sum(df.height for df in dfs) == 5


def test_iter_value_pages_numbermatched_drives_paging_when_server_caps_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page shorter than the requested count does not end paging while numberMatched says more.

    Simulates a server that caps each page at 2 features regardless of the requested count: the
    short-page heuristic alone would stop after the first page and drop the remaining rows, but
    numberMatched=5 keeps paging (advancing startIndex by the actual rows returned) until covered.
    """
    monkeypatch.setattr(rmi_api, "_PAGE_LIMIT", 500_000)
    pages = {0: 2, 2: 2, 4: 1}
    indices: list[int] = []

    def fake_download_file(*, url: str, **_: object) -> File:
        start_index = int(url.split("startIndex=")[1].split("&", maxsplit=1)[0])
        indices.append(start_index)
        return _feature_file(pages[start_index], start=start_index, number_matched=5)

    monkeypatch.setattr(rmi_api, "download_file", fake_download_file)
    dfs = _iter_pages(object.__new__(rmi_api.RmiObservationValues))
    assert indices == [0, 2, 4]
    assert sum(df.height for df in dfs) == 5


def test_iter_value_pages_runaway_guard_stops_after_max_pages(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A server returning full pages forever without numberMatched stops after _MAX_PAGES, warning."""
    monkeypatch.setattr(rmi_api, "_PAGE_LIMIT", 2)
    monkeypatch.setattr(rmi_api, "_MAX_PAGES", 3)

    def fake_download_file(*, url: str, **_: object) -> File:  # noqa: ARG001
        # always a full page (== _PAGE_LIMIT), never an empty/short page, no numberMatched
        return _feature_file(2)

    monkeypatch.setattr(rmi_api, "download_file", fake_download_file)
    with caplog.at_level(logging.WARNING, logger=rmi_api.log.name):
        dfs = _iter_pages(object.__new__(rmi_api.RmiObservationValues))
    assert len(dfs) == 3  # exactly _MAX_PAGES pages, then the guard bails out
    assert any("exceeded 3 pages" in record.message for record in caplog.records)


def test_iter_value_pages_single_short_page_stops_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    """A first page shorter than the limit ends pagination after one request."""
    monkeypatch.setattr(rmi_api, "_PAGE_LIMIT", 100)
    indices: list[int] = []

    def fake_download_file(*, url: str, **_: object) -> File:
        indices.append(int(url.split("startIndex=")[1].split("&", maxsplit=1)[0]))
        return _feature_file(3)

    monkeypatch.setattr(rmi_api, "download_file", fake_download_file)
    dfs = _iter_pages(object.__new__(rmi_api.RmiObservationValues))
    assert indices == [0]
    assert [df.height for df in dfs] == [3]


def test_iter_value_pages_stops_on_download_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A download error ends pagination without raising, keeps prior pages, and logs a warning."""
    monkeypatch.setattr(rmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        if "startIndex=0" in url:
            return _feature_file(2)
        return File(url=url, content=RuntimeError("boom"), status=500)

    monkeypatch.setattr(rmi_api, "download_file", fake_download_file)
    with caplog.at_level(logging.WARNING, logger=rmi_api.log.name):
        dfs = _iter_pages(object.__new__(rmi_api.RmiObservationValues))
    assert [df.height for df in dfs] == [2]
    assert any("Failed to acquire RMI data" in record.message for record in caplog.records)


def test_iter_value_pages_no_internet_is_silent(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A NoInternetError ends pagination silently -- no warning (already logged at debug upstream)."""
    monkeypatch.setattr(rmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        return File(url=url, content=NoInternetError("offline"), status=503)

    monkeypatch.setattr(rmi_api, "download_file", fake_download_file)
    with caplog.at_level(logging.WARNING, logger=rmi_api.log.name):
        dfs = _iter_pages(object.__new__(rmi_api.RmiObservationValues))
    assert dfs == []
    assert not any("Failed to acquire RMI data" in record.message for record in caplog.records)


def test_collect_reshapes_wide_features_to_long_utc_values() -> None:
    """The wide feature is reshaped to long, UTC-labelled values with qc_flags mapped to quality."""
    dataset = _hourly_dataset()
    names = [parameter.name_original for parameter in dataset.parameters]
    # qc_flags marks the first parameter validated (1.0) and the second not (0.0) for both rows
    validated = {names[0].upper(): True, names[1].upper(): False}
    qc_flags = json.dumps({"validated": validated})
    wide = pl.DataFrame(
        {"timestamp": ["2023-06-01T00:00:00Z", "2023-06-01T01:00:00Z"], "qc_flags": [qc_flags, qc_flags]},
    ).with_columns([pl.lit(float(index)).alias(name) for index, name in enumerate(names)])

    values = object.__new__(rmi_api.RmiObservationValues)
    values.sr = SimpleNamespace(
        stations=SimpleNamespace(settings=Settings(cache_disable=True)),
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 1, 1, tzinfo=UTC),
    )
    # bypass the network: feed the reshape a single wide page
    values._iter_value_pages = lambda *_args, **_kwargs: iter([wide])  # noqa: SLF001

    df = values._collect_station_parameter_or_dataset(UCCLE, dataset)  # noqa: SLF001
    assert df.columns == ["resolution", "dataset", "parameter", "station_id", "date", "value", "quality"]
    assert df.get_column("resolution").unique().to_list() == ["hourly"]
    assert df.get_column("station_id").unique().to_list() == [UCCLE]
    assert set(df.get_column("parameter").unique().to_list()) == set(names)
    # two timestamps x every parameter, none dropped (all non-null)
    assert df.height == 2 * len(names)
    assert str(df.schema["date"]).find("UTC") != -1
    assert df.get_column("date").min() == dt.datetime(2023, 6, 1, tzinfo=UTC)
    # qc_flags validation maps to the quality code: validated -> 1.0, not validated -> 0.0
    quality_by_parameter = dict(df.select("parameter", "quality").unique().iter_rows())
    assert quality_by_parameter[names[0]] == 1.0
    assert quality_by_parameter[names[1]] == 0.0


@pytest.mark.remote
def test_rmi_observation_stations() -> None:
    """Station discovery returns one row per station with usable metadata."""
    request = rmi_api.RmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
    ).all()
    assert not request.df.is_empty()
    assert request.df.get_column("station_id").n_unique() == request.df.height
    station = request.df.filter(pl.col("station_id") == UCCLE)
    assert station.height == 1
    row = station.to_dicts()[0]
    assert row["name"]
    assert 49 < row["latitude"] < 52
    assert 2 < row["longitude"] < 7


@pytest.mark.remote
def test_rmi_observation_values_hourly_utc() -> None:
    """Hourly values include both range boundaries and are UTC-aligned to the start of the hour."""
    request = rmi_api.RmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 1, 5, tzinfo=UTC),
    ).filter_by_station_id([UCCLE])
    values = request.values.all().df
    dates = values.get_column("date").sort().to_list()
    assert dates[0] == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)
    assert dates[-1] == dt.datetime(2023, 6, 1, 5, 0, tzinfo=UTC)
    assert "UTC" in str(values.schema["date"])
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_rmi_observation_values_daily() -> None:
    """Daily values are labelled at UTC midnight and include both range boundaries."""
    request = rmi_api.RmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 5, tzinfo=UTC),
    ).filter_by_station_id([UCCLE])
    values = request.values.all().df
    dates = values.get_column("date").sort().to_list()
    assert dates[0] == dt.datetime(2023, 6, 1, tzinfo=UTC)
    assert dates[-1] == dt.datetime(2023, 6, 5, tzinfo=UTC)
    assert values.get_column("date").dt.hour().unique().to_list() == [0]
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_rmi_observation_values_10_minutes() -> None:
    """10-minute values are UTC-aligned to the start of each interval."""
    request = rmi_api.RmiObservationRequest(
        parameters=[("10_minutes", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 1, 0, 50, tzinfo=UTC),
    ).filter_by_station_id([UCCLE])
    values = request.values.all().df
    assert values.get_column("date").min() == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_rmi_observation_values_empty_for_unknown_station() -> None:
    """An unknown station id yields an empty, well-formed values frame."""
    settings = Settings(cache_disable=True)
    request = rmi_api.RmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end_date=dt.datetime(2023, 6, 1, 5, tzinfo=UTC),
        settings=settings,
    ).filter_by_station_id(["99999"])
    values = request.values.all().df
    assert values.is_empty()
