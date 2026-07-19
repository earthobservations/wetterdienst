# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the KNMI (Netherlands) observation provider.

KNMI's Data Platform requires an API key and, unlike most providers, has no per-station
history endpoint -- every value fetch is a whole-network NetCDF download per timestamp
(see api.py). The KNMI key registration was also unavailable at the time these were
written, so the live end-to-end smoke test lives in tests/test_api.py (credential-gated,
skipped without WD_AUTH__KNMI). Everything here is deterministic and offline: the file
naming / date stepping, the NetCDF parser, the retry loop, and the auth guard.
"""

import datetime as dt
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation.api import (
    KnmiObservationRequest,
    _download_with_retry,
    _filename_for,
    _moments,
)
from wetterdienst.provider.knmi.observation.parser import parse_knmi_netcdf, public_station_id
from wetterdienst.settings import Settings
from wetterdienst.util.network import File

# The knmi extra (h5netcdf + h5py) may not be installed; skip the whole module if not, matching
# the radar tests. The provider itself imports h5netcdf lazily, so these are only needed here to
# build NetCDF fixtures.
h5netcdf = pytest.importorskip("h5netcdf", reason="h5netcdf not installed")
h5py = pytest.importorskip("h5py", reason="h5py not installed")

UTC = ZoneInfo("UTC")

# De Bilt. KNMI keys stations by full WSI (0-20000-0-06260); the provider exposes just the
# trailing WMO station number (06260) as station_id -- see parser.public_station_id.
DE_BILT = "06260"

# Applied per-test (not module-level) so the offline unit tests below still run without a key.
requires_knmi_credentials = pytest.mark.skipif(
    not KnmiObservationRequest.is_configured(),
    reason="KNMI credentials not set — provide WD_AUTH__KNMI=<api_key>",
)
# Live third-party API; xfail rather than a hard failure keeps a transient blip (or KNMI's
# per-key rate limit) from blocking CI/merges, matching the AEMET/SMHI/ECCC precedent.
xfail_if_knmi_unavailable = pytest.mark.xfail(strict=False, reason="KNMI server intermittently unavailable")


def _write_netcdf(path: Path) -> bytes:
    """Build a minimal KNMI-shaped NetCDF via h5netcdf: two stations, one timestamp.

    Mirrors the real files' shape: stations keyed by full WSI, data variables laid out as
    (station, time) with a single time step. No ``time`` variable is written because the
    parser never reads it (it dates values to the requested moment instead).
    """
    string_dtype = h5py.string_dtype()
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": 2, "time": 1}
        station = file.create_variable("station", ("station",), dtype=string_dtype)
        station[:] = ["0-20000-0-06260", "0-20000-0-06280"]  # public station_id is the "06xxx" tail
        stationname = file.create_variable("stationname", ("station",), dtype=string_dtype)
        stationname[:] = ["De Bilt", "Eelde"]
        tg = file.create_variable("TG", ("station", "time"), dtype="f8")
        tg[:] = [[6.6], [1.2]]
        rh = file.create_variable("RH", ("station", "time"), dtype="f8")
        rh[:] = [[-1.0], [3.4]]  # -1 is KNMI's trace-precipitation sentinel
        vv = file.create_variable("VV", ("station", "time"), dtype="f8")
        vv[:] = [[float("nan")], [10.0]]  # NaN is KNMI's missing-value fill
    return path.read_bytes()


@pytest.fixture
def netcdf_payload(tmp_path: Path) -> bytes:
    """Return a minimal KNMI-shaped NetCDF file's raw bytes."""
    return _write_netcdf(tmp_path / "knmi.nc")


def test_knmi_filename_for_10_minutes() -> None:
    """10-minute filenames use the KMDS naming with a minute-precision timestamp."""
    moment = dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC)
    assert _filename_for(Resolution.MINUTE_10, moment) == "KMDS__OPER_P___10M_OBS_L2_202006011210.nc"


def test_knmi_filename_for_hourly() -> None:
    """Hourly filenames carry both the date and the two-digit hour."""
    moment = dt.datetime(2020, 1, 1, 9, tzinfo=UTC)
    assert _filename_for(Resolution.HOURLY, moment) == "hourly-observations-validated-20200101-09.nc"


def test_knmi_filename_for_daily() -> None:
    """Daily filenames carry only the date."""
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert _filename_for(Resolution.DAILY, moment) == "daily-observations-validated-20200101.nc"


def test_knmi_moments_hourly_steps_by_hour_inclusive() -> None:
    """Hourly stepping covers both endpoints, one moment per hour."""
    start = dt.datetime(2020, 1, 1, 0, tzinfo=UTC)
    end = dt.datetime(2020, 1, 1, 3, tzinfo=UTC)
    assert list(_moments(start, end, Resolution.HOURLY)) == [
        dt.datetime(2020, 1, 1, 0, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 2, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 3, tzinfo=UTC),
    ]


def test_knmi_moments_daily_steps_by_day_inclusive() -> None:
    """Daily stepping covers both endpoints, one moment per day."""
    start = dt.datetime(2020, 1, 1, tzinfo=UTC)
    end = dt.datetime(2020, 1, 3, tzinfo=UTC)
    assert list(_moments(start, end, Resolution.DAILY)) == [
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 1, 2, tzinfo=UTC),
        dt.datetime(2020, 1, 3, tzinfo=UTC),
    ]


def test_knmi_moments_single_moment() -> None:
    """A zero-width range still yields exactly the one requested moment."""
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert list(_moments(moment, moment, Resolution.DAILY)) == [moment]


def test_knmi_moments_daily_does_not_floor_unaligned_start() -> None:
    """_moments itself leaves hourly/daily unfloored (mixed-request path).

    For single-resolution hourly/daily requests the request floors start_date up front (see
    the request-level tests below); _moments only floors 10-minute, to resolve filenames.
    """
    start = dt.datetime(2020, 1, 1, 6, 0, tzinfo=UTC)
    end = dt.datetime(2020, 1, 3, 6, 0, tzinfo=UTC)
    assert list(_moments(start, end, Resolution.DAILY)) == [
        dt.datetime(2020, 1, 1, 6, 0, tzinfo=UTC),
        dt.datetime(2020, 1, 2, 6, 0, tzinfo=UTC),
        dt.datetime(2020, 1, 3, 6, 0, tzinfo=UTC),
    ]


def _request(parameters: list, start: dt.datetime, end: dt.datetime) -> KnmiObservationRequest:
    return KnmiObservationRequest(
        parameters=parameters,
        start_date=start,
        end_date=end,
        settings=Settings(auth={"knmi": "dummy-key-for-test"}),
    )


def test_knmi_single_daily_request_floors_start_date_to_midnight() -> None:
    """A single-resolution daily request snaps an unaligned start_date down to midnight.

    This keeps the value dated to the true day boundary while keeping the start-containing day
    in the framework's [start, end] window (no dropped first period, correct label).
    """
    request = _request(
        [("daily", "data", "temperature_air_mean_2m")],
        dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC),
        dt.datetime(2020, 1, 3, tzinfo=UTC),
    )
    assert request.start_date == dt.datetime(2020, 1, 1, 0, 0, tzinfo=UTC)


def test_knmi_single_hourly_request_floors_start_date_to_hour() -> None:
    """A single-resolution hourly request snaps an unaligned start_date down to the hour."""
    request = _request(
        [("hourly", "data", "temperature_air_mean_2m")],
        dt.datetime(2020, 1, 1, 10, 30, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 12, tzinfo=UTC),
    )
    assert request.start_date == dt.datetime(2020, 1, 1, 10, 0, tzinfo=UTC)


def test_knmi_single_10_minutes_request_does_not_floor_start_date() -> None:
    """10-minute is left unfloored at the request level.

    Its end-labelled sub-hour intervals mean an unaligned start must exclude the pre-start
    interval (handled by the [start, end] filter), so start_date stays put and only _moments
    floors it to resolve filenames.
    """
    request = _request(
        [("10_minutes", "data", "temperature_air_mean_2m")],
        dt.datetime(2020, 1, 1, 10, 37, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 11, tzinfo=UTC),
    )
    assert request.start_date == dt.datetime(2020, 1, 1, 10, 37, tzinfo=UTC)


def test_knmi_mixed_resolution_request_does_not_floor_start_date() -> None:
    """A mixed-resolution request has no single boundary to floor to, so start_date is kept."""
    request = _request(
        [
            ("daily", "data", "temperature_air_mean_2m"),
            ("10_minutes", "data", "temperature_air_mean_2m"),
        ],
        dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC),
        dt.datetime(2020, 1, 3, tzinfo=UTC),
    )
    assert request.start_date == dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC)


def test_knmi_non_utc_start_end_normalized_to_utc() -> None:
    """A tz-aware non-UTC start/end is converted to UTC before flooring/filename formatting.

    KNMI files are keyed by UTC; without this, 10:07 Europe/Amsterdam (08:07 UTC) would format
    a wall-clock '10' into the filename and fetch the wrong hour. 10-minute is used so the
    request-level floor does not obscure the conversion.
    """
    ams = ZoneInfo("Europe/Amsterdam")
    request = _request(
        [("10_minutes", "data", "temperature_air_mean_2m")],
        dt.datetime(2020, 6, 1, 10, 7, tzinfo=ams),  # 10:07 CEST == 08:07 UTC
        dt.datetime(2020, 6, 1, 11, 0, tzinfo=ams),  # 11:00 CEST == 09:00 UTC
    )
    assert request.start_date == dt.datetime(2020, 6, 1, 8, 7, tzinfo=UTC)
    assert request.end_date == dt.datetime(2020, 6, 1, 9, 0, tzinfo=UTC)


def test_knmi_moments_10_minutes_floors_unaligned_start() -> None:
    """A start not on a 10-minute boundary is floored down so filenames resolve.

    12:07 -> 12:00, then step by 10 minutes through the end. The 12:00 file lands before
    the requested start but the framework trims it back to the requested range later.
    """
    start = dt.datetime(2020, 6, 1, 12, 7, tzinfo=UTC)
    end = dt.datetime(2020, 6, 1, 12, 30, tzinfo=UTC)
    assert list(_moments(start, end, Resolution.MINUTE_10)) == [
        dt.datetime(2020, 6, 1, 12, 0, tzinfo=UTC),
        dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC),
        dt.datetime(2020, 6, 1, 12, 20, tzinfo=UTC),
        dt.datetime(2020, 6, 1, 12, 30, tzinfo=UTC),
    ]


def test_knmi_parse_netcdf_extracts_requested_station_and_parameters(netcdf_payload: bytes) -> None:
    """Only the requested station's requested parameters come back."""
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "06280", ["TG"], moment)
    assert df.to_dicts() == [{"date": moment, "parameter": "TG", "value": 1.2}]


def test_knmi_parse_netcdf_uses_requested_moment_not_internal_time(netcdf_payload: bytes) -> None:
    """The returned date is the requested moment, not the file's internal ``time`` coord.

    Real KNMI files label each file with an end-of-period ``time`` (the 2020-01-01 file
    carries 2020-01-02); the parser ignores it entirely and attaches the requested
    ``moment`` instead (KNMI's convention, confirmed against the legacy CSV service).
    """
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "06260", ["TG"], moment)
    assert df["date"].to_list() == [moment]


def test_knmi_parse_netcdf_trace_precipitation_becomes_zero(netcdf_payload: bytes) -> None:
    """KNMI's -1 "trace precipitation" sentinel for RH is normalized to 0, not left negative."""
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "06260", ["RH"], moment)
    assert df.filter(pl.col("parameter").eq("RH"))["value"].item() == 0.0
    # a genuinely positive value at another station is left untouched
    df2 = parse_knmi_netcdf(netcdf_payload, "06280", ["RH"], moment)
    assert df2.filter(pl.col("parameter").eq("RH"))["value"].item() == pytest.approx(3.4)


def test_knmi_parse_netcdf_fill_value_becomes_null_not_nan(netcdf_payload: bytes) -> None:
    """A NaN _FillValue is emitted as a null value, not a NaN.

    A NaN would slip past the framework's ts_drop_nulls handling and make to_json emit an
    invalid bare `NaN` token. The row is still present -- with a null value -- so downstream
    null handling (drop or keep) applies uniformly.
    """
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "06260", ["VV"], moment)
    assert df["value"].to_list() == [None]
    assert df["value"].is_null().all()
    # a genuine value at another station is untouched
    df2 = parse_knmi_netcdf(netcdf_payload, "06280", ["VV"], moment)
    assert df2["value"].item() == pytest.approx(10.0)


def test_knmi_parse_netcdf_missing_station_returns_empty(netcdf_payload: bytes) -> None:
    """A station not present in the file yields an empty (correctly-typed) frame, not an error."""
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "999", ["TG"], moment)
    assert df.is_empty()
    assert df.schema["date"] == pl.Datetime(time_unit="us", time_zone="UTC")


def test_knmi_parse_netcdf_unknown_parameter_skipped(netcdf_payload: bytes) -> None:
    """A parameter absent from the file is skipped rather than raising."""
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "06260", ["TG", "DOES_NOT_EXIST"], moment)
    assert df["parameter"].to_list() == ["TG"]


def test_knmi_public_station_id_strips_wsi_prefix() -> None:
    """The public station_id is the trailing WMO number of the full WSI key."""
    assert public_station_id("0-20000-0-06260") == "06260"  # De Bilt (land station, block 06)
    assert public_station_id("0-20000-0-78990") == "78990"  # Bonaire (Caribbean, block 78)
    assert public_station_id("0-528-0-06213") == "06213"  # different WSI issuer, still the tail


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the retry backoff so the retry tests don't actually wait seconds."""
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._RETRY_WAIT_INITIAL_SECONDS", 0.01)
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._RETRY_WAIT_MAX_SECONDS", 0.01)


def test_knmi_download_retry_recovers_after_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient failure (e.g. a 503) is retried and the eventual success is returned."""
    responses = iter(
        [
            File(url="url", content=Exception("temporarily unavailable"), status=503),
            File(url="url", content=BytesIO(b"ok"), status=200),
        ],
    )
    calls = []
    monkeypatch.setattr(
        "wetterdienst.provider.knmi.observation.api.download_file",
        lambda **_kwargs: (calls.append(1), next(responses))[1],
    )
    result = _download_with_retry("https://example.org", Settings(), CacheExpiry.NO_CACHE)
    assert result.status == 200
    assert len(calls) == 2


def test_knmi_download_retry_gives_up_eventually(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent retryable failures are not retried forever -- the last failed File is returned."""
    calls = []

    def always_503(**_kwargs: object) -> File:
        calls.append(1)
        return File(url="url", content=Exception("still down"), status=503)

    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api.download_file", always_503)
    result = _download_with_retry("https://example.org", Settings(), CacheExpiry.NO_CACHE)
    assert result.status == 503
    assert isinstance(result.content, Exception)
    assert len(calls) == 3  # 1 initial attempt + 2 retries, then gives up


def test_knmi_download_permanent_failure_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-retryable status (e.g. 404) is returned immediately, without retrying."""
    calls = []

    def always_404(**_kwargs: object) -> File:
        calls.append(1)
        return File(url="url", content=Exception("not found"), status=404)

    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api.download_file", always_404)
    result = _download_with_retry("https://example.org", Settings(), CacheExpiry.NO_CACHE)
    assert result.status == 404
    assert len(calls) == 1


def test_knmi_request_requires_api_key() -> None:
    """Constructing a request without a KNMI key fails fast with a helpful message."""
    with pytest.raises(ValueError, match="KNMI Data Platform requires authentication"):
        KnmiObservationRequest(
            parameters=[("daily", "data", "temperature_air_mean_2m")],
            settings=Settings(auth={"knmi": None}),
        )


def test_knmi_request_constructs_with_api_key() -> None:
    """With a key present, construction succeeds (no network access happens yet)."""
    request = KnmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        settings=Settings(auth={"knmi": "dummy-key-for-test"}),
    )
    assert request.metadata.name_short == "KNMI"


@pytest.mark.remote
@requires_knmi_credentials
@xfail_if_knmi_unavailable
def test_knmi_observation_stations() -> None:
    """Station metadata for De Bilt matches the KNMI station inventory."""
    request = KnmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id(DE_BILT)
    df = request.df
    assert df.select(pl.exclude("latitude", "longitude", "height")).to_dicts() == [
        {
            "resolution": "daily",
            "dataset": "data",
            "station_id": DE_BILT,
            "start_date": None,
            "end_date": None,
            "name": "De Bilt",
            "state": None,
        },
    ]
    # coordinates/height with a tolerance -- KNMI may adjust these slightly over time
    assert df["latitude"].item() == pytest.approx(52.0989, abs=1e-2)
    assert df["longitude"].item() == pytest.approx(5.1797, abs=1e-2)
    assert df["height"].item() == pytest.approx(1.9, abs=1.0)


@pytest.mark.remote
@requires_knmi_credentials
@xfail_if_knmi_unavailable
def test_knmi_observation_values_daily() -> None:
    """Daily values at De Bilt for 2020-01-01 match the KNMI reference values.

    Cross-checked against KNMI's legacy daggegevens.knmi.nl CSV service for STN 260:
    TG=0.8, TN=-0.2, TX=1.8 °C, RH=0.0 mm. Also confirms KNMI's end-of-period internal
    time coord is handled: the value lands on 2020-01-01, not 2020-01-02.
    """
    df = (
        KnmiObservationRequest(
            parameters=[("daily", "data")],
            start_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 1, 1, tzinfo=UTC),
        )
        .filter_by_station_id(DE_BILT)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [DE_BILT]
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["date"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(0.8)
    assert value_of("temperature_air_min_2m") == pytest.approx(-0.2)
    assert value_of("temperature_air_max_2m") == pytest.approx(1.8)
    assert value_of("precipitation_height") == pytest.approx(0.0)


@pytest.mark.remote
@requires_knmi_credentials
@xfail_if_knmi_unavailable
def test_knmi_observation_values_10_minutes() -> None:
    """10-minute values at De Bilt for the 2020-06-01 12:10 UTC interval match the raw file.

    Values are cross-checked against the raw KMDS NetCDF: ta=23.2 °C, rh=32 % on disk
    (returned as the 0.32 fraction after unit conversion), ff=3.01 m/s. Also confirms the
    unaligned-start flooring: the query starts at 12:07 but the first returned interval is
    12:10 (12:00 is fetched then trimmed).
    """
    df = (
        KnmiObservationRequest(
            parameters=[("10_minutes", "data")],
            start_date=dt.datetime(2020, 6, 1, 12, 7, tzinfo=UTC),
            end_date=dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC),
        )
        .filter_by_station_id(DE_BILT)
        .values.all()
        .df
    )
    assert df["station_id"].unique().to_list() == [DE_BILT]
    assert df["resolution"].unique().to_list() == ["10_minutes"]
    assert df["date"].unique().to_list() == [dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(23.2)
    assert value_of("humidity") == pytest.approx(0.32)
    assert value_of("wind_speed") == pytest.approx(3.01)
