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
import json
import logging
import ssl
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from aiohttp import ClientPayloadError, ClientResponseError, ServerDisconnectedError
from fsspec.exceptions import FSTimeoutError

from tests.conftest import skip_if_upstream_unavailable
from wetterdienst.exceptions import CredentialRejectedError, DownloadError, MissingDependencyError, NoInternetError
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
EELDE = "06280"

# Applied per-test (not module-level) so the offline unit tests below still run without a key.
requires_knmi_credentials = pytest.mark.skipif(
    not KnmiObservationRequest.is_configured(),
    reason="KNMI credentials not set — provide WD_AUTH__KNMI=<api_key>",
)


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
        start=start,
        end=end,
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
    assert request.start == dt.datetime(2020, 1, 1, 0, 0, tzinfo=UTC)


def test_knmi_single_hourly_request_floors_start_date_to_hour() -> None:
    """A single-resolution hourly request snaps an unaligned start_date down to the hour."""
    request = _request(
        [("hourly", "data", "temperature_air_2m")],
        dt.datetime(2020, 1, 1, 10, 30, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 12, tzinfo=UTC),
    )
    assert request.start == dt.datetime(2020, 1, 1, 10, 0, tzinfo=UTC)


def test_knmi_single_10_minutes_request_does_not_floor_start_date() -> None:
    """10-minute is left unfloored at the request level.

    Its end-labelled sub-hour intervals mean an unaligned start must exclude the pre-start
    interval (handled by the [start, end] filter), so start_date stays put and only _moments
    floors it to resolve filenames.
    """
    request = _request(
        [("10_minutes", "data", "temperature_air_2m")],
        dt.datetime(2020, 1, 1, 10, 37, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 11, tzinfo=UTC),
    )
    assert request.start == dt.datetime(2020, 1, 1, 10, 37, tzinfo=UTC)


def test_knmi_mixed_resolution_request_does_not_floor_start_date() -> None:
    """A mixed-resolution request has no single boundary to floor to, so start_date is kept."""
    request = _request(
        [
            ("daily", "data", "temperature_air_mean_2m"),
            ("10_minutes", "data", "temperature_air_2m"),
        ],
        dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC),
        dt.datetime(2020, 1, 3, tzinfo=UTC),
    )
    assert request.start == dt.datetime(2020, 1, 1, 6, 30, tzinfo=UTC)


def test_knmi_non_utc_start_end_normalized_to_utc() -> None:
    """A tz-aware non-UTC start/end is converted to UTC before flooring/filename formatting.

    KNMI files are keyed by UTC; without this, 10:07 Europe/Amsterdam (08:07 UTC) would format
    a wall-clock '10' into the filename and fetch the wrong hour. 10-minute is used so the
    request-level floor does not obscure the conversion.
    """
    ams = ZoneInfo("Europe/Amsterdam")
    request = _request(
        [("10_minutes", "data", "temperature_air_2m")],
        dt.datetime(2020, 6, 1, 10, 7, tzinfo=ams),  # 10:07 CEST == 08:07 UTC
        dt.datetime(2020, 6, 1, 11, 0, tzinfo=ams),  # 11:00 CEST == 09:00 UTC
    )
    assert request.start == dt.datetime(2020, 6, 1, 8, 7, tzinfo=UTC)
    assert request.end == dt.datetime(2020, 6, 1, 9, 0, tzinfo=UTC)


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
    assert df.to_dicts() == [{"timestamp": moment, "parameter": "TG", "value": 1.2, "quality_flags": None}]


def test_knmi_parse_netcdf_uses_requested_moment_not_internal_time(netcdf_payload: bytes) -> None:
    """The returned date is the requested moment, not the file's internal ``time`` coord.

    Real KNMI files label each file with an end-of-period ``time`` (the 2020-01-01 file
    carries 2020-01-02); the parser ignores it entirely and attaches the requested
    ``moment`` instead (KNMI's convention, confirmed against the legacy CSV service).
    """
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "06260", ["TG"], moment)
    assert df["timestamp"].to_list() == [moment]


def test_knmi_parse_netcdf_trace_precipitation_becomes_zero(netcdf_payload: bytes) -> None:
    """KNMI's -1 "trace precipitation" sentinel for RH is normalized to 0, not left negative."""
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "06260", ["RH"], moment)
    assert df.filter(pl.col("parameter").eq("RH"))["value"].item() == 0.0
    # the -1 stays beside the 0.0 as the text of the sentinel (GH-2759)
    assert df["quality_flags"].to_list() == ["raw:-1"]
    # a genuinely positive value at another station is left untouched
    df2 = parse_knmi_netcdf(netcdf_payload, "06280", ["RH"], moment)
    assert df2.filter(pl.col("parameter").eq("RH"))["value"].item() == pytest.approx(3.4)
    assert df2["quality_flags"].to_list() == [None]


def test_knmi_parse_netcdf_fill_value_becomes_null_not_nan(netcdf_payload: bytes) -> None:
    """A NaN _FillValue is emitted as a null value, not a NaN.

    A NaN would slip past the framework's drop_nulls handling and make to_json emit an
    invalid bare `NaN` token. The row is still present -- with a null value -- so downstream
    null handling (drop or keep) applies uniformly.
    """
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "06260", ["VV"], moment)
    assert df["value"].to_list() == [None]
    assert df["value"].is_null().all()
    # the fill value stays beside the null as its text (GH-2759)
    assert df["quality_flags"].to_list() == ["raw:NaN"]
    # a genuine value at another station is untouched
    df2 = parse_knmi_netcdf(netcdf_payload, "06280", ["VV"], moment)
    assert df2["value"].item() == pytest.approx(10.0)
    assert df2["quality_flags"].to_list() == [None]


@pytest.mark.parametrize(
    ("code", "raw"),
    [(990.0, "raw:990"), (0.0, "raw:0")],
    ids=["variable", "calm"],
)
def test_knmi_parse_netcdf_hourly_wind_direction_codes_are_no_bearing(tmp_path: Path, code: float, raw: str) -> None:
    """The hourly DD is "360=north, ... 0=calm, 990=variable": the codes are null, with KNMI's text kept (GH-2850)."""
    string_dtype = h5py.string_dtype()
    path = tmp_path / "knmi.nc"
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": 2, "time": 1}
        station = file.create_variable("station", ("station",), dtype=string_dtype)
        station[:] = ["0-20000-0-06260", "0-20000-0-06280"]
        dd = file.create_variable("DD", ("station", "time"), dtype="f8")
        dd[:] = [[code], [360.0]]
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    coded = parse_knmi_netcdf(path.read_bytes(), "06260", ["DD"], moment)
    assert coded["value"].to_list() == [None]
    assert coded["quality_flags"].to_list() == [raw]
    # north is 360, a bearing
    north = parse_knmi_netcdf(path.read_bytes(), "06280", ["DD"], moment)
    assert north["value"].to_list() == [360.0]
    assert north["quality_flags"].to_list() == [None]


def test_knmi_parse_netcdf_missing_station_returns_empty(netcdf_payload: bytes) -> None:
    """A station not present in the file yields an empty (correctly-typed) frame, not an error."""
    moment = dt.datetime(2020, 1, 1, tzinfo=UTC)
    df = parse_knmi_netcdf(netcdf_payload, "999", ["TG"], moment)
    assert df.is_empty()
    assert df.schema["timestamp"] == pl.Datetime(time_unit="us", time_zone="UTC")


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
    assert not result.is_no_internet_error
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


def test_knmi_station_list_gives_the_wigos_identifier(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A station's `wigos_id` is the full WSI its file keys it by; `station_id` is its trailing number (GH-2019).

    The files key a station by WSI, such as `0-20000-0-06260` for De Bilt, and `station_id` keeps only the
    WMO number at its end, so the WSI was not in the station list at all.
    """
    path = tmp_path / "stations.nc"
    string_dtype = h5py.string_dtype()
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": 2}
        station = file.create_variable("station", ("station",), dtype=string_dtype)
        station[:] = ["0-20000-0-06260", "0-20000-0-78990"]
        stationname = file.create_variable("stationname", ("station",), dtype=string_dtype)
        stationname[:] = ["De Bilt", "Bonaire"]
        for name, values in {"lat": [52.0989, 12.1306], "lon": [5.1797, -68.2695], "height": [1.9, 4.0]}.items():
            variable = file.create_variable(name, ("station",), dtype="f8")
            variable[:] = values
    payload = path.read_bytes()
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._latest_filename", lambda *_args: "latest.nc")
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._fetch_netcdf", lambda *_args: payload)

    request = _request([("daily", "data", "temperature_air_mean_2m")], dt.datetime(2020, 1, 1, tzinfo=UTC), None)
    df = request.all().df

    assert df.select("station_id", "wigos_id", "name").rows() == [
        ("06260", "0-20000-0-06260", "De Bilt"),
        ("78990", "0-20000-0-78990", "Bonaire"),
    ]


@pytest.mark.parametrize("where", ["lookup", "file"])
def test_knmi_station_list_offline_raises(monkeypatch: pytest.MonkeyPatch, where: str) -> None:
    """An unreachable KNMI is no network without stations, whether the lookup or the file meets it (GH-2640)."""
    offline = NoInternetError("no route to host")
    lookup = offline if where == "lookup" else "latest.nc"
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._latest_filename", lambda *_args: lookup)
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._fetch_netcdf", lambda *_args: offline)

    request = _request([("daily", "data", "temperature_air_mean_2m")], dt.datetime(2020, 1, 1, tzinfo=UTC), None)

    with pytest.raises(NoInternetError) as raised:
        request.all()
    assert raised.value is offline


def test_knmi_station_list_without_h5netcdf_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """The station list reads a NetCDF file too, and without h5netcdf says what to install (GH-2667)."""
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._latest_filename", lambda *_args: "latest.nc")
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._fetch_netcdf", lambda *_args: b"not read")
    monkeypatch.setitem(sys.modules, "h5netcdf", None)

    request = _request([("daily", "data", "temperature_air_mean_2m")], dt.datetime(2020, 1, 1, tzinfo=UTC), None)

    with pytest.raises(MissingDependencyError, match=r"pip install wetterdienst\[knmi\]"):
        request.all()


_STATION_FILE = "https://s3.example.invalid/stations.nc?X-Amz-Signature=secret"


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status)


def _serve_station_requests(
    monkeypatch: pytest.MonkeyPatch, *, listing: File | None = None, resolve: File | None = None
) -> None:
    """Serve the request for the latest file of a dataset as `listing`, and the one for its link as `resolve`."""

    def download(url: str, *_args: object, **_kwargs: object) -> File:
        if "/files?maxKeys=1" in url:
            if listing is not None:
                return File(url=url, content=listing.content, status=listing.status)
            body = BytesIO(json.dumps({"files": [{"filename": "latest.nc"}]}).encode())
            return File(url=url, content=body, status=200)
        assert url.endswith("/latest.nc/url")
        assert resolve is not None
        return File(url=url, content=resolve.content, status=resolve.status)

    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._download_with_retry", download)


def _stations() -> pl.DataFrame:
    request = _request([("daily", "data", "temperature_air_mean_2m")], dt.datetime(2020, 1, 1, tzinfo=UTC), None)
    return request.all().df


def _failed(failure: Exception, status: int) -> File:
    return File(url="https://api.dataplatform.knmi.nl/x", content=failure, status=status)


@pytest.mark.parametrize("where", ["listing", "resolve"])
@pytest.mark.parametrize(
    ("failure", "status"),
    [
        pytest.param(FSTimeoutError(), 408, id="timeout"),
        pytest.param(ServerDisconnectedError(), 500, id="dropped connection"),
        pytest.param(ClientPayloadError("body cut short"), 500, id="cut body"),
        pytest.param(_response_error(503), 503, id="503"),
        pytest.param(ssl.SSLCertVerificationError("certificate verify failed"), 500, id="tls"),
    ],
)
def test_knmi_station_list_raises_a_download_error_for_a_request_that_did_not_answer(
    monkeypatch: pytest.MonkeyPatch, where: str, failure: Exception, status: int
) -> None:
    """An outage of the latest-file lookup or of its link is no network without stations (GH-3022)."""
    failed = _failed(failure, status)
    _serve_station_requests(monkeypatch, listing=failed if where == "listing" else None, resolve=failed)
    with pytest.raises(DownloadError) as raised:
        _stations()
    assert raised.value.__cause__ is failure
    assert raised.value.url.endswith("/files" if where == "listing" else "/files/latest.nc/url")
    assert "?" not in raised.value.url


@pytest.mark.parametrize("where", ["listing", "resolve"])
@pytest.mark.parametrize("status", [401, 403])
def test_knmi_station_list_raises_credential_rejected_error_for_a_refused_key(
    monkeypatch: pytest.MonkeyPatch, where: str, status: int
) -> None:
    """A key KNMI refuses for the station list is raised, not read as a network without stations (GH-3018)."""
    failed = _failed(_response_error(status), status)
    _serve_station_requests(monkeypatch, listing=failed if where == "listing" else None, resolve=failed)
    with pytest.raises(CredentialRejectedError, match=f"HTTP {status}"):
        _stations()


@pytest.mark.parametrize("where", ["listing", "resolve"])
@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(FileNotFoundError("not published"), id="404"),
        pytest.param(_response_error(429), id="429"),
    ],
)
def test_knmi_station_list_keeps_the_empty_result_for_an_answer(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, where: str, answer: Exception
) -> None:
    """A 404 or a 429 for the station list is KNMI answering: no stations, warned about, as before."""
    status = 404 if isinstance(answer, FileNotFoundError) else 429
    failed = _failed(answer, status)
    _serve_station_requests(monkeypatch, listing=failed if where == "listing" else None, resolve=failed)
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.knmi"):
        assert _stations().is_empty()
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == 1


def _serve_knmi(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: Exception | None,
    *,
    at: str = "resolve",
    ok: tuple[str, ...] = (),
) -> list[str]:
    """Serve KNMI: the station list and the files named in `ok` as files, every other file as `failure`.

    `at` says which request of a failing file fails: the resolve of its download link or the download itself.
    Returns the data files asked for (the names).
    """
    path = tmp_path / "stations.nc"
    string_dtype = h5py.string_dtype()
    with h5netcdf.File(path, "w") as file:
        file.dimensions = {"station": 2}
        station = file.create_variable("station", ("station",), dtype=string_dtype)
        station[:] = ["0-20000-0-06260", "0-20000-0-06280"]
        stationname = file.create_variable("stationname", ("station",), dtype=string_dtype)
        stationname[:] = ["De Bilt", "Eelde"]
        for name, values in {"lat": [52.0989, 53.1], "lon": [5.1797, 6.6], "height": [1.9, 4.0]}.items():
            variable = file.create_variable(name, ("station",), dtype="f8")
            variable[:] = values
    stations = path.read_bytes()
    data = _write_netcdf(tmp_path / "data.nc")
    asked: list[str] = []

    def download(url: str, *_args: object, **_kwargs: object) -> File:
        status = getattr(failure, "status", 500)
        if "/files?maxKeys=1" in url:
            return File(
                url=url, content=BytesIO(json.dumps({"files": [{"filename": "latest.nc"}]}).encode()), status=200
            )
        if url.endswith("/url"):
            name = url.rsplit("/", 2)[-2]
            if name == "latest.nc":
                link = _STATION_FILE
            elif name in ok or failure is None or at == "download":
                link = f"https://s3.example.invalid/{name}?X-Amz-Signature=secret"
            else:
                asked.append(name)
                return File(url=url, content=failure, status=status)
            return File(url=url, content=BytesIO(json.dumps({"temporaryDownloadUrl": link}).encode()), status=200)
        name = url.split("?", maxsplit=1)[0].rsplit("/", 1)[-1]
        if name == "stations.nc":
            return File(url=url, content=BytesIO(stations), status=200)
        if name in ok or failure is None:
            asked.append(name)
            return File(url=url, content=BytesIO(data), status=200)
        asked.append(name)
        return File(url=url, content=failure, status=status)

    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._download_with_retry", download)
    return asked


def _daily_values(days: int = 1) -> pl.DataFrame:
    start = dt.datetime(2020, 1, 1, tzinfo=UTC)
    return (
        _request([("daily", "data", "temperature_air_mean_2m")], start, start + dt.timedelta(days=days - 1))
        .filter_by_station_id(DE_BILT)
        .values()
        .all()
        .df
    )


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(FSTimeoutError(), id="timeout"),
        pytest.param(ServerDisconnectedError(), id="dropped connection"),
        pytest.param(ClientPayloadError("body cut short"), id="cut body"),
        pytest.param(_response_error(500), id="500"),
        pytest.param(_response_error(503), id="503"),
    ],
)
@pytest.mark.parametrize("at", ["resolve", "download"])
def test_knmi_values_raise_a_download_error_for_a_file_that_did_not_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: Exception, at: str
) -> None:
    """A timeout, a dropped connection, a cut body or a 5xx ends the request, naming the file, without the signature."""
    asked = _serve_knmi(monkeypatch, tmp_path, failure, at=at)
    with pytest.raises(DownloadError) as raised:
        _daily_values(days=3)
    assert raised.value.__cause__ is failure
    assert "daily-observations-validated-20200101.nc" in raised.value.url
    assert "?" not in raised.value.url
    assert "secret" not in str(raised.value)
    assert len(asked) == 1  # the next day is not asked for


def test_knmi_values_raise_for_a_file_that_did_not_answer_after_one_that_did(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A range read in part is not an answer: the day that failed raises, rather than the day before it."""
    _serve_knmi(monkeypatch, tmp_path, _response_error(503), ok=("daily-observations-validated-20200101.nc",))
    with pytest.raises(DownloadError) as raised:
        _daily_values(days=2)
    assert "daily-observations-validated-20200102.nc" in raised.value.url


def test_knmi_values_raise_no_internet_error_as_before(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A failed connection is still the `NoInternetError` it was (GH-2640)."""
    offline = NoInternetError("no route to host")
    asked = _serve_knmi(monkeypatch, tmp_path, offline)
    with pytest.raises(NoInternetError) as raised:
        _daily_values(days=3)
    assert raised.value is offline
    assert len(asked) == 1


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(FileNotFoundError("not published"), id="404"),
        pytest.param(_response_error(404), id="404 as a response error"),
        pytest.param(_response_error(429), id="429"),
        pytest.param(_response_error(400), id="400"),
    ],
)
def test_knmi_values_skip_a_file_that_is_an_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, answer: Exception
) -> None:
    """A file KNMI answers for with a 404, a 429 or another 4xx is skipped with a warning, as before (GH-2965)."""
    asked = _serve_knmi(monkeypatch, tmp_path, answer)
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.knmi"):
        df = _daily_values(days=2)
    assert df.is_empty()
    assert len(asked) == 2
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == 2


@pytest.mark.parametrize("status", [401, 403])
def test_knmi_values_skip_a_file_whose_download_link_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, status: int
) -> None:
    """The link KNMI hands out is pre-signed and takes no key: its 401 or 403 says nothing of the key (GH-3018)."""
    asked = _serve_knmi(monkeypatch, tmp_path, _response_error(status), at="download")
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.knmi"):
        df = _daily_values(days=2)
    assert df.is_empty()
    assert len(asked) == 2
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == 2


@pytest.mark.parametrize("status", [401, 403])
def test_knmi_values_raise_credential_rejected_error_for_a_refused_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, status: int
) -> None:
    """A key KNMI refuses ends the request at the first file, naming the setting and not the key (GH-3018)."""
    asked = _serve_knmi(monkeypatch, tmp_path, _response_error(status))
    with pytest.raises(CredentialRejectedError, match=f"HTTP {status}") as raised:
        _daily_values(days=3)
    assert "WD_AUTH__KNMI" in str(raised.value)
    assert "dummy-key-for-test" not in f"{raised.value!s}{raised.value!r}"
    assert len(asked) == 1  # the next day is not asked for


def test_knmi_values_skip_a_missing_day_and_keep_the_others(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A day that is not published is left out of a range whose other day is read."""
    _serve_knmi(monkeypatch, tmp_path, FileNotFoundError("x"), ok=("daily-observations-validated-20200102.nc",))
    df = _daily_values(days=2)
    assert df.get_column("timestamp").unique().to_list() == [dt.datetime(2020, 1, 2, tzinfo=UTC)]


@pytest.mark.parametrize(
    ("failure", "skipped"),
    [
        pytest.param(FSTimeoutError(), True, id="timeout"),
        pytest.param(_response_error(502), True, id="502"),
        pytest.param(FileNotFoundError("not published"), False, id="404 is an answer"),
    ],
)
def test_knmi_outage_met_by_the_values_reader_skips_the_remote_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: Exception,
    skipped: bool,  # noqa: FBT001
) -> None:
    """A remote KNMI test is skipped on an outage of the values, which used to reach it as an empty frame."""
    _serve_knmi(monkeypatch, tmp_path, failure)

    @skip_if_upstream_unavailable()
    def _remote_test() -> None:
        assert not _daily_values().is_empty()

    with pytest.raises(pytest.skip.Exception if skipped else AssertionError):
        _remote_test()


@pytest.mark.remote
@requires_knmi_credentials
def test_knmi_observation_stations() -> None:
    """Station metadata for De Bilt matches the KNMI station inventory."""
    request = KnmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id(DE_BILT)
    df = request.df
    assert df.select(pl.exclude("latitude", "longitude", "elevation")).to_dicts() == [
        {
            "resolution": "daily",
            "dataset": "data",
            "station_id": DE_BILT,
            "start_timestamp": None,
            "end_timestamp": None,
            "name": "De Bilt",
            "region": None,
            "wigos_id": "0-20000-0-06260",
        },
    ]
    # coordinates/height with a tolerance -- KNMI may adjust these slightly over time
    assert df["latitude"].item() == pytest.approx(52.0989, abs=1e-2)
    assert df["longitude"].item() == pytest.approx(5.1797, abs=1e-2)
    assert df["elevation"].item() == pytest.approx(1.9, abs=1.0)


@pytest.mark.remote
@requires_knmi_credentials
def test_knmi_observation_values_daily() -> None:
    """Daily values at De Bilt for 2020-01-01 match the KNMI reference values.

    Cross-checked against KNMI's legacy daggegevens.knmi.nl CSV service for STN 260:
    TG=0.8, TN=-0.2, TX=1.8 °C, RH=0.0 mm. Also confirms KNMI's end-of-period internal
    time coord is handled: the value lands on 2020-01-01, not 2020-01-02.
    """
    df = (
        KnmiObservationRequest(
            parameters=[("daily", "data")],
            start=dt.datetime(2020, 1, 1, tzinfo=UTC),
            end=dt.datetime(2020, 1, 1, tzinfo=UTC),
        )
        .filter_by_station_id(DE_BILT)
        .values()
        .all()
        .df
    )
    assert df["station_id"].unique().to_list() == [DE_BILT]
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["timestamp"].unique().to_list() == [dt.datetime(2020, 1, 1, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_mean_2m") == pytest.approx(0.8)
    assert value_of("temperature_air_min_2m") == pytest.approx(-0.2)
    assert value_of("temperature_air_max_2m") == pytest.approx(1.8)
    assert value_of("precipitation_amount") == pytest.approx(0.0)


@pytest.mark.remote
@requires_knmi_credentials
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
            start=dt.datetime(2020, 6, 1, 12, 7, tzinfo=UTC),
            end=dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC),
        )
        .filter_by_station_id(DE_BILT)
        .values()
        .all()
        .df
    )
    assert df["station_id"].unique().to_list() == [DE_BILT]
    assert df["resolution"].unique().to_list() == ["10_minutes"]
    assert df["timestamp"].unique().to_list() == [dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC)]

    def value_of(parameter: str) -> float:
        return df.filter(pl.col("parameter").eq(parameter)).get_column("value").item()

    assert value_of("temperature_air_2m") == pytest.approx(23.2)
    assert value_of("humidity_relative") == pytest.approx(0.32)
    assert value_of("wind_speed_mean") == pytest.approx(3.01)


def test_knmi_download_no_internet_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download that failed for want of a network is returned at once, not retried."""
    calls = []

    def offline(**_kwargs: object) -> File:
        calls.append(1)
        return File(url="url", content=NoInternetError("no route to host"), status=503)

    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api.download_file", offline)
    result = _download_with_retry("https://example.org", Settings(), CacheExpiry.NO_CACHE)
    assert result.is_no_internet_error
    assert len(calls) == 1


def _fake_downloads(monkeypatch: pytest.MonkeyPatch, *answers: bytes | Exception) -> list[str]:
    """Answer the KNMI file downloads with `answers` in order, the last for all after; return the filenames."""
    attempted: list[str] = []

    def fake_fetch_netcdf(_dataset: str, _version: str, filename: str, _settings: Settings) -> bytes | Exception:
        attempted.append(filename)
        return answers[min(len(attempted), len(answers)) - 1]

    monkeypatch.setattr(
        "wetterdienst.provider.knmi.observation.api.KnmiObservationRequest._station_frame",
        staticmethod(
            lambda *_args: pl.DataFrame({"station_id": [DE_BILT, EELDE], "name": ["De Bilt", "Eelde"]}),
        ),
    )
    monkeypatch.setattr("wetterdienst.provider.knmi.observation.api._fetch_netcdf", fake_fetch_netcdf)
    return attempted


def _hourly_values(days: int, station_ids: tuple[str, ...] = (DE_BILT,)) -> pl.DataFrame:
    start = dt.datetime(2020, 1, 1, tzinfo=UTC)
    return (
        _request([("hourly", "data", "temperature_air_2m")], start, start + dt.timedelta(days=days))
        .filter_by_station_id(station_ids)
        .values()
        .all()
        .df
    )


def test_knmi_values_offline_raise_at_the_first_moment(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Offline, the per-moment loop raises `NoInternetError` after one download and logs no warning (GH-2640)."""
    attempted = _fake_downloads(monkeypatch, NoInternetError("no route to host"))
    with caplog.at_level(logging.DEBUG, logger="wetterdienst.provider.knmi"), pytest.raises(NoInternetError):
        _hourly_values(days=30)
    assert len(attempted) == 1
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_knmi_values_offline_raise_at_the_first_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline, the request ends at the first download: the second station is not tried (GH-2620)."""
    attempted = _fake_downloads(monkeypatch, NoInternetError("no route to host"))
    with pytest.raises(NoInternetError):
        _hourly_values(days=30, station_ids=(DE_BILT, EELDE))
    assert len(attempted) == 1


def test_knmi_values_offline_raise_at_the_first_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline, the request ends at the first download: the station's other resolution is not tried (GH-2620)."""
    attempted = _fake_downloads(monkeypatch, NoInternetError("no route to host"))
    start = dt.datetime(2020, 1, 1, tzinfo=UTC)
    request = _request(
        [("hourly", "data", "temperature_air_2m"), ("daily", "data", "temperature_air_mean_2m")],
        start,
        start + dt.timedelta(days=3),
    ).filter_by_station_id(DE_BILT)
    with pytest.raises(NoInternetError):
        request.values().all()
    assert len(attempted) == 1


def test_knmi_values_going_offline_midway_raises(
    monkeypatch: pytest.MonkeyPatch,
    netcdf_payload: bytes,
) -> None:
    """A network lost after the first file raises, rather than answering with the values read (GH-2640)."""
    attempted = _fake_downloads(monkeypatch, netcdf_payload, NoInternetError("no route to host"))
    start = dt.datetime(2020, 1, 1, tzinfo=UTC)
    request = _request([("daily", "data", "temperature_air_mean_2m")], start, start + dt.timedelta(days=5))
    with pytest.raises(NoInternetError):
        request.filter_by_station_id((DE_BILT, EELDE)).values().all()
    assert len(attempted) == 2


def test_knmi_values_failed_moment_is_skipped_and_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failure that is not a missing network still skips only its own moment, with a warning."""
    attempted = _fake_downloads(monkeypatch, Exception("not found"))
    with caplog.at_level(logging.WARNING, logger="wetterdienst.provider.knmi"):
        df = _hourly_values(days=1)
    assert df.is_empty()
    assert len(attempted) == 25
    assert len([record for record in caplog.records if record.levelno == logging.WARNING]) == 25


def test_parse_knmi_netcdf_without_h5netcdf_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """The parser's lazy import of h5netcdf says what to install instead of a bare ModuleNotFoundError (GH-2545)."""
    monkeypatch.setitem(sys.modules, "h5netcdf", None)

    with pytest.raises(MissingDependencyError, match=r"pip install wetterdienst\[knmi\]"):
        parse_knmi_netcdf(b"not read", DE_BILT, ["TG"], dt.datetime(2020, 1, 1, tzinfo=UTC))
