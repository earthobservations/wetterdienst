# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD SWSMOS (road weather forecast) provider."""

import bz2
import datetime as dt
import logging
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest, api
from wetterdienst.provider.dwd.swsmos.api import _LATEST_FILE, DwdForecastDate, _read_run_csv, _run_url
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")


def test_read_run_csv_drops_run_timestamp_line() -> None:
    """A run file's line-2 run timestamp is dropped so the header aligns with the data rows."""
    raw = (
        b"ID;Lat;Lon;YYYYMMDDHHmm;TL;RC;TS\n"
        b"202607310700\n"  # the run-timestamp line between header and data
        b"A006;54.889156;8.908735;202607310800;17.9;1;24.2\n"
        b"A006;54.889156;8.908735;202607310900;17.6;2;25.1\n"
    )
    df = _read_run_csv(bz2.compress(raw))
    assert df.columns == ["ID", "Lat", "Lon", "YYYYMMDDHHmm", "TL", "RC", "TS"]
    assert df.height == 2  # only the two data rows, not the run-timestamp line
    assert df["TL"].to_list() == ["17.9", "17.6"]


def test_read_run_csv_too_short() -> None:
    """A file without any data rows yields an empty frame rather than raising."""
    assert _read_run_csv(bz2.compress(b"ID;TL\n202607310700\n")).is_empty()


def test_run_url() -> None:
    """The run URL is built from the issue hour (minutes/seconds are always zero)."""
    url = _run_url(dt.datetime(2026, 7, 31, 7, 0, tzinfo=UTC))
    assert url.endswith("/swsmos_20260731070000_opendata.csv.bz2")


def test_issue_defaults_to_latest() -> None:
    """Without an explicit issue, the request targets the latest model run."""
    request = DwdSwsmosRequest(parameters=[("hourly", "data")])
    assert request.issue is DwdForecastDate.LATEST


def test_issue_string_parsed_to_utc_hour() -> None:
    """An ISO issue string is floored to a UTC hour."""
    request = DwdSwsmosRequest(parameters=[("hourly", "data")], issue="2026-07-31T07:34")
    assert request.issue == dt.datetime(2026, 7, 31, 7, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Remote tests -- hit the live DWD opendata server. SWSMOS is a rolling forecast, so values are
# time-dependent; assert structure/ranges. xfail on outage matches the DWD/CHMI precedent.
# ---------------------------------------------------------------------------

xfail_if_dwd_unavailable = pytest.mark.xfail(strict=False, reason="DWD opendata intermittently unavailable")


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_swsmos_stations() -> None:
    """The road-station catalogue resolves to a populated set of German stations."""
    df = DwdSwsmosRequest(parameters=[("hourly", "data")]).all().df
    assert df.height > 1000
    assert df["resolution"].unique().to_list() == ["hourly"]
    # Germany: latitudes ~47-55 N, longitudes ~6-15 E
    assert df["latitude"].min() > 47.0
    assert df["latitude"].max() < 56.0
    assert df["longitude"].min() > 5.0
    assert df["longitude"].max() < 16.0


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_swsmos_values() -> None:
    """The latest run returns an hourly forecast with the expected parameters and sane ranges."""
    request = DwdSwsmosRequest(parameters=[("hourly", "data")])
    station_id = request.all().df["station_id"][0]
    df = request.filter_by_station_id(station_id).values.all().df
    assert not df.is_empty()
    assert df["resolution"].unique().to_list() == ["hourly"]
    assert set(df["parameter"].unique().to_list()) <= {
        "temperature_air_mean_2m",
        "temperature_dew_point_mean_2m",
        "temperature_surface_mean",
        "precipitation_height_liquid",
        "precipitation_height_last_6h",
        "probability_precipitation_liquid_last_6h",
        "probability_precipitation_height_gt_5mm_last_6h",
        "road_surface_condition",
    }
    # the forecast is hourly and lies in the future of the run
    dates = df["date"].unique().sort()
    assert len(dates) > 24  # multi-day hourly horizon
    deltas = dates.diff().drop_nulls().unique().to_list()
    assert deltas == [dt.timedelta(hours=1)]
    # air temperature in a physically plausible range
    air = df.filter(pl.col("parameter") == "temperature_air_mean_2m")["value"].drop_nulls()
    assert air.min() > -40.0
    assert air.max() < 55.0
    # dew point likewise -- swsmos publishes Celsius, unlike MOSMIX's Kelvin, and the whole of
    # Germany reading above 250 would mean we had silently inherited the MOSMIX unit
    dew_point = df.filter(pl.col("parameter") == "temperature_dew_point_mean_2m")["value"].drop_nulls()
    assert dew_point.min() > -40.0
    assert dew_point.max() < 40.0
    # and it cannot exceed the air temperature it is measured against
    assert dew_point.max() <= air.max()


# ---------------------------------------------------------------------------
# One run per request -- GH-1922
# ---------------------------------------------------------------------------


def _stub_stations(station_ids: tuple[str, ...] = ("A006",)) -> StationsResult:
    """Stand road stations up rather than look them up.

    Asked of the real catalogue, a test about how often the run is read would depend on which
    stations DWD still publishes, and would stop exercising anything the day they change.
    """
    request = DwdSwsmosRequest(parameters=[("hourly", "data")])
    df_stations = pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "data",
                "station_id": station_id,
                "start_date": None,
                "end_date": None,
                "latitude": 54.8892,
                "longitude": 8.9087,
                "height": 2.0,
                "name": f"Station {station_id}",
            }
            for station_id in station_ids
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "end_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
        },
        orient="row",
    )
    return StationsResult(
        stations=request,
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.BY_STATION_ID,
    )


def _run_file(*rows: tuple[str, str, str]) -> bytes:
    """Build a run file: header, the run-timestamp line, then ``ID;...;date;TL`` rows."""
    body = "".join(f"{station_id};54.889156;8.908735;{date};{temperature}\n" for station_id, date, temperature in rows)
    return bz2.compress(b"ID;Lat;Lon;YYYYMMDDHHmm;TL\n202607310700\n" + body.encode("latin-1"))


def test_swsmos_parses_the_run_once_for_all_its_stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """One run file holds every station, so it is read for the run and not for each station.

    The collection above this asks for one station at a time, and a run file holds them all -- so
    the run was listed, fetched and parsed once per station, with all but one station's rows thrown
    away each time. Five stations parsed the same 306,612 rows five times, 2.5 s of a 2.7 s
    request; twenty-five took 14.1 s where they now take 0.8 s.
    """
    content = _run_file(
        ("A006", "202607310800", "17.9"),
        ("B999", "202607310800", "9.1"),
        ("C111", "202607310800", "7.4"),
    )
    parses = []
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{api._BASE_URL}/{_LATEST_FILE}"])  # noqa: SLF001
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(content), status=200),
    )
    _read_run_csv_original = api._read_run_csv  # noqa: SLF001
    monkeypatch.setattr(api, "_read_run_csv", lambda c: parses.append(1) or _read_run_csv_original(c))

    values = _stub_stations(("A006", "B999", "C111")).values
    dataset = DwdSwsmosRequest.metadata["hourly"]["data"]
    answers = [values._collect_station_parameter_or_dataset(sid, dataset) for sid in ("A006", "B999", "C111")]  # noqa: SLF001

    assert len(parses) == 1, "the run should be parsed once, not once per station"
    # and each station still gets its own forecast out of it
    assert [df.get_column("station_id").unique().to_list() for df in answers] == [["A006"], ["B999"], ["C111"]]
    assert [df.get_column("value").to_list() for df in answers] == [[17.9], [9.1], [7.4]]


def test_swsmos_pins_every_station_to_one_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run published while the request is answered does not reach half of its stations.

    Resolving ``LATEST`` per station is not only a remote round trip per station: the stations
    walked after DWD publishes a new run were answered from it, so the frame quietly mixed two
    model runs. Resolving once pins them all to the run the first station was answered from.
    """
    runs = [
        _run_file(("A006", "202607310800", "17.9"), ("B999", "202607310800", "9.1")),
        # the next run, published between the first station and the second
        _run_file(("A006", "202607310900", "20.0"), ("B999", "202607310900", "11.0")),
    ]
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{api._BASE_URL}/{_LATEST_FILE}"])  # noqa: SLF001
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(runs.pop(0)), status=200),
    )

    values = _stub_stations(("A006", "B999")).values
    dataset = DwdSwsmosRequest.metadata["hourly"]["data"]
    answers = [values._collect_station_parameter_or_dataset(sid, dataset) for sid in ("A006", "B999")]  # noqa: SLF001

    assert len(runs) == 1, "the second run should never be fetched"
    assert [df.get_column("date").to_list() for df in answers] == [
        [dt.datetime(2026, 7, 31, 8, tzinfo=UTC)],
        [dt.datetime(2026, 7, 31, 8, tzinfo=UTC)],
    ]
    assert [df.get_column("value").to_list() for df in answers] == [[17.9], [9.1]]


def test_swsmos_run_that_cannot_be_fetched_is_asked_for_once(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A run DWD does not serve is an empty answer per station, and one attempt for the request."""
    caplog.set_level(logging.WARNING)
    downloads = []
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{api._BASE_URL}/{_LATEST_FILE}"])  # noqa: SLF001
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: (
            downloads.append(kwargs["url"]) or File(url=kwargs["url"], content=FileNotFoundError("404"), status=404)
        ),
    )

    values = _stub_stations(("A006", "B999")).values
    dataset = DwdSwsmosRequest.metadata["hourly"]["data"]
    answers = [values._collect_station_parameter_or_dataset(sid, dataset) for sid in ("A006", "B999")]  # noqa: SLF001

    assert all(df.is_empty() for df in answers)
    assert set(answers[0].columns) == {"resolution", "dataset", "parameter", "station_id", "date", "value", "quality"}
    assert len(downloads) == 1, "a run that cannot be fetched is not re-fetched for the next station"
    # and the outage is reported once for the request rather than once per station
    assert len([record for record in caplog.records if "Failed to fetch SWSMOS run" in record.message]) == 1


def test_swsmos_latest_asks_for_the_newest_run_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """``LATEST`` resolves to the newest run the listing names, not to the mutable alias.

    How long a run may be cached is a property of the URL rather than of the request, and the two
    URLs are the same bytes -- the server returns one ETag for the alias and the newest timestamped
    file. Asking by name is that answer from a URL that cannot change under its cache entry, where
    caching the alias for twelve hours answered "the latest run" with one up to twelve hours old:
    measured against the live server at 22:57 UTC, the 21:00 run while DWD was serving 22:00.
    """
    content = _run_file(("A006", "202607310800", "17.9"))
    asked = []
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: (
            asked.append((kwargs["url"].rsplit("/", 1)[-1], kwargs["ttl"]))
            or File(url=kwargs["url"], content=BytesIO(content), status=200)
        ),
    )
    dataset = DwdSwsmosRequest.metadata["hourly"]["data"]

    # the alias is published beside the runs, and is not what is asked for
    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [
            f"{api._BASE_URL}/{_LATEST_FILE}",  # noqa: SLF001
            f"{api._BASE_URL}/swsmos_20260731060000_opendata.csv.bz2",  # noqa: SLF001
            f"{api._BASE_URL}/swsmos_20260731070000_opendata.csv.bz2",  # noqa: SLF001
        ],
    )
    _stub_stations().values._collect_station_parameter_or_dataset("A006", dataset)  # noqa: SLF001
    # with nothing but the alias to go on it is used, and held only briefly
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{api._BASE_URL}/{_LATEST_FILE}"])  # noqa: SLF001
    _stub_stations().values._collect_station_parameter_or_dataset("A006", dataset)  # noqa: SLF001
    # and an explicitly requested run names itself
    stations = _stub_stations()
    stations.stations.issue = dt.datetime(2026, 7, 31, 7, tzinfo=UTC)
    stations.values._collect_station_parameter_or_dataset("A006", dataset)  # noqa: SLF001

    assert asked == [
        ("swsmos_20260731070000_opendata.csv.bz2", CacheExpiry.TWELVE_HOURS),
        (_LATEST_FILE, CacheExpiry.FIVE_MINUTES),
        ("swsmos_20260731070000_opendata.csv.bz2", CacheExpiry.TWELVE_HOURS),
    ]


def test_swsmos_query_asks_for_the_latest_run_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """The run is pinned for the length of a query and no longer.

    `StationsResult.values` builds a values object per access, so most callers get a fresh run
    either way -- but one that keeps the object and queries it again on a timer is asking for the
    latest run a second time, and would otherwise be answered from the one resolved on its first
    call for as long as it lived.
    """
    runs = [
        _run_file(("A006", "202607310800", "17.9")),
        _run_file(("A006", "202607310900", "20.0")),
    ]
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{api._BASE_URL}/{_LATEST_FILE}"])  # noqa: SLF001
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(runs.pop(0)), status=200),
    )

    values = _stub_stations().values
    first = values.all().df
    second = values.all().df

    assert first.get_column("value").to_list() == [17.9]
    assert second.get_column("value").to_list() == [20.0], "a second query should see the run published since"


def test_swsmos_run_does_not_outlive_the_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """The parsed run is released when the walk ends, rather than held by the result it produced.

    `ValuesResult` holds the values object that produced it, so a result kept by the caller keeps
    whatever that object holds -- and a request for one station's forecast would otherwise pin the
    whole network's parsed run, some 20 MB, for as long as the result lived.
    """
    content = _run_file(("A006", "202607310800", "17.9"))
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{api._BASE_URL}/{_LATEST_FILE}"])  # noqa: SLF001
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(content), status=200),
    )

    values = _stub_stations().values
    result = values.all()

    assert not result.df.is_empty()
    assert result.values is values  # the result does hold the object, which is why this matters
    assert values._run_frame_cache is None, "the run should be released with the walk that parsed it"  # noqa: SLF001


def test_swsmos_listing_entry_that_is_not_a_run_is_not_mistaken_for_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run file names itself exactly, and a sidebar published beside the runs is not one.

    Matching a bare ``swsmos_`` prefix also matches a checksum sidecar or a second product, and one
    of those sorts *after* the run it belongs to -- so the newest name would be a file that is not
    a run, handed straight to `bz2.decompress`.
    """
    content = _run_file(("A006", "202607310800", "17.9"))
    asked = []
    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [
            f"{api._BASE_URL}/swsmos_20260731070000_opendata.csv.bz2",  # noqa: SLF001
            f"{api._BASE_URL}/swsmos_20260731070000_opendata.csv.bz2.sha256",  # noqa: SLF001
            f"{api._BASE_URL}/swsmos_stationskatalog.csv.bz2",  # noqa: SLF001
        ],
    )
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: (
            asked.append(kwargs["url"].rsplit("/", 1)[-1])
            or File(url=kwargs["url"], content=BytesIO(content), status=200)
        ),
    )

    df = _stub_stations().values._collect_station_parameter_or_dataset(  # noqa: SLF001
        "A006",
        DwdSwsmosRequest.metadata["hourly"]["data"],
    )

    assert asked == ["swsmos_20260731070000_opendata.csv.bz2"]
    assert df.get_column("value").to_list() == [17.9]


def test_swsmos_run_that_cannot_be_read_falls_back_to_the_one_before_it(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A run still being written is answered with the hour before it, not with a traceback.

    The listing is deliberately uncached, so it names a run the moment it appears -- and a body
    that is not the bz2 a run file should be raises out of `bz2.decompress`, where nothing between
    there and the caller catches. It is cached for twelve hours too, so a single bad download would
    have ended every request in the same traceback for half a day.
    """
    caplog.set_level(logging.WARNING)
    bodies = {
        "swsmos_20260731080000_opendata.csv.bz2": b"\x42\x5a\x68truncated",  # still being written
        "swsmos_20260731070000_opendata.csv.bz2": _run_file(("A006", "202607310800", "17.9")),
    }
    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [f"{api._BASE_URL}/{name}" for name in bodies],  # noqa: SLF001
    )
    monkeypatch.setattr(
        api,
        "download_file",
        lambda **kwargs: File(url=kwargs["url"], content=BytesIO(bodies[kwargs["url"].rsplit("/", 1)[-1]]), status=200),
    )

    df = _stub_stations().values._collect_station_parameter_or_dataset(  # noqa: SLF001
        "A006",
        DwdSwsmosRequest.metadata["hourly"]["data"],
    )

    assert df.get_column("value").to_list() == [17.9]  # the 07:00 run, the 08:00 one being unreadable
    assert "Failed to read SWSMOS run" in caplog.text
    assert "swsmos_20260731080000_opendata.csv.bz2" in caplog.text
