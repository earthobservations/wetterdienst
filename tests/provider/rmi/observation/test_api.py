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
from tests.provider.value_stubs import stations_result
from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.model.plausibility import Plausibility, applying
from wetterdienst.model.schema import LONG_SCHEMA
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
    df = df.select(pl.col("features").explode(empty_as_null=True).struct.field("properties")).unnest("properties")
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


def test_iter_value_pages_raises_on_download_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download error raises, rather than ending pagination with the pages so far read as the whole answer."""
    monkeypatch.setattr(rmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        if "startIndex=0" in url:
            return _feature_file(2)
        return File(url=url, content=RuntimeError("boom"), status=500)

    monkeypatch.setattr(rmi_api, "download_file", fake_download_file)
    with pytest.raises(DownloadError, match="boom"):
        _iter_pages(object.__new__(rmi_api.RmiObservationValues))


def test_iter_value_pages_no_internet_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A NoInternetError ends pagination by raising, not by answering with the pages read (GH-2640)."""
    monkeypatch.setattr(rmi_api, "_PAGE_LIMIT", 2)

    def fake_download_file(*, url: str, **_: object) -> File:
        return File(url=url, content=NoInternetError("offline"), status=503)

    monkeypatch.setattr(rmi_api, "download_file", fake_download_file)
    with pytest.raises(NoInternetError):
        _iter_pages(object.__new__(rmi_api.RmiObservationValues))


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
        request=SimpleNamespace(settings=Settings(cache_disable=True)),
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 1, 1, tzinfo=UTC),
    )
    # bypass the network: feed the reshape a single wide page
    values._iter_value_pages = lambda *_args, **_kwargs: iter([wide])  # noqa: SLF001

    # what the provider hands over is the rows, `parameter`, `timestamp`, `value` and `quality_flags`; the identity
    # columns, the order and the dtypes are the core's (`shape_provider_frame`), so the assertions are on its frame
    handed = values._collect_station_parameter_or_dataset(UCCLE, dataset)  # noqa: SLF001
    assert handed.columns == ["parameter", "timestamp", "value", "quality_flags"]
    df = values._shape(handed, UCCLE, dataset)  # noqa: SLF001
    assert df.columns == list(LONG_SCHEMA)
    assert df.get_column("resolution").unique().to_list() == ["hourly"]
    assert df.get_column("station_id").unique().to_list() == [UCCLE]
    assert set(df.get_column("parameter").unique().to_list()) == set(names)
    # two timestamps x every parameter, none dropped (all non-null)
    assert df.height == 2 * len(names)
    assert str(df.schema["timestamp"]).find("UTC") != -1
    assert df.get_column("timestamp").min() == dt.datetime(2023, 6, 1, tzinfo=UTC)
    # qc_flags validation maps to the flag: validated -> "1", not validated -> "0"
    quality_by_parameter = dict(df.select("parameter", "quality_flags").unique().iter_rows())
    assert quality_by_parameter[names[0]] == "1"
    assert quality_by_parameter[names[1]] == "0"


def _collect_wide(
    resolution_name: str, rows: list[dict], qc: dict[str, bool] | None = None, station: str = "6414"
) -> pl.DataFrame:
    """Read wide features as the WFS serves them for the resolution of a dataset through the reader of RMI."""
    resolution = next(
        resolution for resolution in rmi_api.RmiObservationRequest.metadata if resolution.name == resolution_name
    )
    dataset = next(iter(resolution))
    names = [parameter.name_original for parameter in dataset.parameters]
    flags = json.dumps({"validated": qc or {}})
    wide = pl.DataFrame(
        [{**dict.fromkeys(names), **row, "qc_flags": flags} for row in rows],
        schema={"timestamp": pl.String, **dict.fromkeys(names, pl.Float64), "qc_flags": pl.String},
    )
    values = object.__new__(rmi_api.RmiObservationValues)
    values.sr = SimpleNamespace(
        request=SimpleNamespace(settings=Settings(cache_disable=True)),
        start=dt.datetime(2003, 8, 6, tzinfo=UTC),
        end=dt.datetime(2003, 10, 9, tzinfo=UTC),
    )
    values._iter_value_pages = lambda *_args, **_kwargs: iter([wide])  # noqa: SLF001
    return values._shape(values._collect_station_parameter_or_dataset(station, dataset), station, dataset)  # noqa: SLF001


def test_collect_nulls_a_value_outside_the_range_of_its_attribute_and_keeps_what_it_was() -> None:
    """The 4021 degrees and the 81.5 m/s gust of station 6414 are null with `raw:4021` and `raw:81.5` (GH-2797).

    Rows as the WFS serves them for the daily layer of 6414 (checked 2026-10-16): `temp_avg` 110.26 and `temp_max` 4021
    on 2003-08-06, `wind_gusts_speed` 81.5 on 2003-10-09, `qc_flags` not validated. The highest gust of any of the 14
    stations in the 36 years of the layer besides is 51.05 m/s (6434, 2002-12-30), which is kept. A source null is
    dropped as before, and a validated value is left alone.
    """
    qc = {"TEMP_AVG": False, "TEMP_MAX": False, "WIND_GUSTS_SPEED": False, "TEMP_MIN": True}
    rows = [
        {"timestamp": "2003-08-06T00:00:00Z", "temp_avg": 110.26, "temp_max": 4021.0, "temp_min": 16.84},
        {"timestamp": "2003-10-09T00:00:00Z", "temp_avg": 14.05, "temp_max": 17.79, "wind_gusts_speed": 81.5},
        {"timestamp": "2002-12-30T00:00:00Z", "wind_gusts_speed": 51.05},
    ]
    df = _collect_wide("daily", rows, qc)
    found = {(row["parameter"], row["timestamp"].date().isoformat()): row for row in df.iter_rows(named=True)}
    assert {key: (row["value"], row["quality_flags"]) for key, row in found.items()} == {
        ("temp_avg", "2003-08-06"): (None, "0,rejected:range,raw:110.26"),
        ("temp_max", "2003-08-06"): (None, "0,rejected:range,raw:4021"),
        ("temp_min", "2003-08-06"): (16.84, "1"),
        ("temp_avg", "2003-10-09"): (14.05, "0"),
        ("temp_max", "2003-10-09"): (17.79, "0"),
        ("wind_gusts_speed", "2003-10-09"): (None, "0,rejected:range,raw:81.5"),
        ("wind_gusts_speed", "2002-12-30"): (51.05, "0"),
    }


def test_collect_nulls_the_sunshine_of_6477_in_the_periods_of_its_stuck_and_dead_sensor() -> None:
    """The sunshine of 6477 is no reading from 2016-04-30 to 2017-05-31 and in two summers of zeros (GH-3031).

    A hard `stuck` check nulls it with `rejected:stuck,raw:`; the default is soft, which keeps the value as
    `suspect:stuck` (GH-3676, `test_collect_keeps_the_sunshine_of_6477_in_its_stuck_periods_by_default`).

    Rows of `aws:aws_1day` of station 6477 (read 2026-10-17): 2016-04-29 reads 533 minutes, the day before the
    sensor sticks, and 2017-06-01 338.67, its last day; 2016-05-10 reads 910 minutes with a mean radiation of
    93.6 W/m2, 2016-12-22 980 minutes, 2016-12-24 1,440 (the 10-minute values of that day are 10 in all 144
    intervals). 2015-04-24 (260.09) and 2015-08-20 (284.5) bound the first summer of zeros, 2015-06-15 and 2017-07-15
    read 0.0 on days of summer. Other stations and attributes are left alone. The source's `validated` flag for
    sunshine is false on 7,720 of the 8,134 days of the station, so it is false on all of these.
    """
    qc = {"SUN_DURATION": False, "SHORT_WAVE_FROM_SKY_AVG": False}
    rows = [
        {"timestamp": "2016-04-29T00:00:00Z", "sun_duration": 533.0, "short_wave_from_sky_avg": 34.13},
        {"timestamp": "2016-04-30T00:00:00Z", "sun_duration": 890.0, "short_wave_from_sky_avg": 99.73},
        {"timestamp": "2016-05-10T00:00:00Z", "sun_duration": 910.0, "short_wave_from_sky_avg": 93.6},
        {"timestamp": "2016-12-22T00:00:00Z", "sun_duration": 980.0},
        {"timestamp": "2016-12-24T00:00:00Z", "sun_duration": 1440.0, "short_wave_from_sky_avg": 24.03},
        {"timestamp": "2017-05-31T00:00:00Z", "sun_duration": 970.0},
        {"timestamp": "2017-06-01T00:00:00Z", "sun_duration": 338.67},
        {"timestamp": "2015-06-15T00:00:00Z", "sun_duration": 0.0},
        {"timestamp": "2017-07-15T00:00:00Z", "sun_duration": 0.0},
        {"timestamp": "2015-04-24T00:00:00Z", "sun_duration": 260.09},
        {"timestamp": "2015-08-20T00:00:00Z", "sun_duration": 284.5},
    ]
    with applying(Plausibility(stuck="hard")):
        df = _collect_wide("daily", rows, qc, station="6477")
    sunshine = {
        row["timestamp"].date().isoformat(): (row["value"], row["quality_flags"])
        for row in df.filter(pl.col("parameter") == "sun_duration").iter_rows(named=True)
    }
    assert sunshine == {
        "2016-04-29": (533.0, "0"),
        "2016-04-30": (None, "0,rejected:stuck,raw:890"),
        "2016-05-10": (None, "0,rejected:stuck,raw:910"),
        "2016-12-22": (None, "0,rejected:stuck,raw:980"),
        "2016-12-24": (None, "0,rejected:stuck,raw:1440"),
        "2017-05-31": (None, "0,rejected:stuck,raw:970"),
        "2017-06-01": (338.67, "0"),
        "2015-06-15": (None, "0,rejected:stuck,raw:0"),
        "2017-07-15": (None, "0,rejected:stuck,raw:0"),
        "2015-04-24": (260.09, "0"),
        "2015-08-20": (284.5, "0"),
    }
    # the radiation of the same days is a reading
    radiation = df.filter(pl.col("parameter") == "short_wave_from_sky_avg").get_column("value").drop_nulls()
    assert sorted(radiation.to_list()) == [24.03, 34.13, 93.6, 99.73]
    # another station keeps the same numbers
    other = _collect_wide("daily", rows[2:3], qc, station="6447")
    assert other.filter(pl.col("parameter") == "sun_duration").get_column("value").to_list() == [910.0]


def test_collect_keeps_the_sunshine_of_6477_in_its_stuck_periods_by_default() -> None:
    """The check `stuck` is soft by default: the value stays and is flagged `suspect:stuck` (GH-3676)."""
    rows = [
        {"timestamp": "2016-04-29T00:00:00Z", "sun_duration": 533.0},
        {"timestamp": "2016-04-30T00:00:00Z", "sun_duration": 890.0},
        {"timestamp": "2015-06-15T00:00:00Z", "sun_duration": 0.0},
    ]
    df = _collect_wide("daily", rows, {"SUN_DURATION": False}, station="6477")
    sunshine = {
        row["timestamp"].date().isoformat(): (row["value"], row["quality_flags"])
        for row in df.filter(pl.col("parameter") == "sun_duration").iter_rows(named=True)
    }
    assert sunshine == {
        "2016-04-29": (533.0, "0"),
        "2016-04-30": (890.0, "0,suspect:stuck"),
        "2015-06-15": (0.0, "0,suspect:stuck"),
    }


@pytest.mark.parametrize(
    ("resolution", "sunshine", "arrives"),
    [
        # the minutes of sunshine of the span: 30 is half an hour of sun, so no 10 minutes can hold it
        ("10_minutes", 30.0, False),
        ("10_minutes", 10.0, True),
        ("hourly", 30.0, True),
        ("hourly", 60.0, True),
        # 6459, 2013-03-24: a day whose hours add up to 3,807.66 minutes, 63.86 minutes at 10:00 and 373.08 at 13:00
        ("hourly", 63.86, False),
        ("hourly", 373.08, False),
        ("daily", 30.0, True),
        ("daily", 1440.0, True),
        # 6459, 2013-05-24, which no day holds
        ("daily", 13_850.58, False),
    ],
)
def test_collect_holds_the_sunshine_to_the_span_of_the_resolution(
    resolution: str,
    sunshine: float,
    arrives: bool,  # noqa: FBT001
) -> None:
    """The same number of minutes is a reading of a day and no reading of ten minutes (GH-2797)."""
    df = _collect_wide(resolution, [{"timestamp": "2013-05-24T00:00:00Z", "sun_duration": sunshine}])
    row = df.filter(pl.col("parameter") == "sun_duration").row(0, named=True)
    if arrives:
        assert row["value"] == sunshine
    else:
        assert (row["value"], row["quality_flags"]) == (None, f"rejected:range,raw:{sunshine:.15g}")


def test_collect_filters_a_zero_length_window_without_a_during_period() -> None:
    """A request with start == end (the one-day form) must not send `DURING X/X` (HTTP 400, GH-2823)."""
    dataset = _hourly_dataset()
    stamp = dt.datetime(2024, 6, 10, 2, tzinfo=ZoneInfo("Europe/Brussels"))  # 00:00 UTC
    request = rmi_api.RmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start=stamp,
        end=stamp,
        settings=Settings(cache_disable=True),
    )
    values = rmi_api.RmiObservationValues(sr=stations_result(request, "hourly", "data", UCCLE))
    filters: list[str] = []

    def fake_pages(_layer: str, cql_filter: str, *_args: object, **_kwargs: object) -> list[pl.DataFrame]:
        filters.append(cql_filter)
        return []

    values._iter_value_pages = fake_pages  # noqa: SLF001
    df = values._shape(values._collect_station_parameter_or_dataset(UCCLE, dataset), UCCLE, dataset)  # noqa: SLF001
    assert df.is_empty()
    assert df.schema == LONG_SCHEMA
    # bounds in UTC, both inclusive, and no period the GeoServer could reject as zero-length
    assert filters == [f"code = {UCCLE} AND timestamp >= 2024-06-10T00:00:00Z AND timestamp <= 2024-06-10T00:00:00Z"]
    assert "DURING" not in filters[0]


@pytest.mark.remote
def test_rmi_observation_values_start_equals_end() -> None:
    """Start == end returns the stamp at that instant for every resolution instead of raising (GH-2823)."""
    for resolution, hour in (("daily", 0), ("hourly", 12), ("10_minutes", 12)):
        instant = dt.datetime(2024, 6, 10, hour, tzinfo=UTC)
        request = rmi_api.RmiObservationRequest(
            parameters=[(resolution, "data", "temperature_air_mean_2m")],
            start=instant,
            end=instant,
        ).filter_by_station_id([UCCLE])
        values = request.values().all().df
        assert values.get_column("timestamp").unique().to_list() == [instant]


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
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 1, 5, tzinfo=UTC),
    ).filter_by_station_id([UCCLE])
    values = request.values().all().df
    dates = values.get_column("timestamp").sort().to_list()
    assert dates[0] == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)
    assert dates[-1] == dt.datetime(2023, 6, 1, 5, 0, tzinfo=UTC)
    assert "UTC" in str(values.schema["timestamp"])
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_rmi_observation_values_daily() -> None:
    """Daily values are labelled at UTC midnight and include both range boundaries."""
    request = rmi_api.RmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 5, tzinfo=UTC),
    ).filter_by_station_id([UCCLE])
    values = request.values().all().df
    dates = values.get_column("timestamp").sort().to_list()
    assert dates[0] == dt.datetime(2023, 6, 1, tzinfo=UTC)
    assert dates[-1] == dt.datetime(2023, 6, 5, tzinfo=UTC)
    assert values.get_column("timestamp").dt.hour().unique().to_list() == [0]
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_rmi_observation_values_10_minutes() -> None:
    """10-minute values are UTC-aligned to the start of each interval."""
    request = rmi_api.RmiObservationRequest(
        parameters=[("10_minutes", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 1, 0, 50, tzinfo=UTC),
    ).filter_by_station_id([UCCLE])
    values = request.values().all().df
    assert values.get_column("timestamp").min() == dt.datetime(2023, 6, 1, 0, 0, tzinfo=UTC)
    assert not values.drop_nulls(subset="value").is_empty()


@pytest.mark.remote
def test_rmi_observation_values_empty_for_unknown_station() -> None:
    """An unknown station id yields an empty, well-formed values frame."""
    settings = Settings(cache_disable=True)
    request = rmi_api.RmiObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2023, 6, 1, tzinfo=UTC),
        end=dt.datetime(2023, 6, 1, 5, tzinfo=UTC),
        settings=settings,
    ).filter_by_station_id(["99999"])
    values = request.values().all().df
    assert values.is_empty()
