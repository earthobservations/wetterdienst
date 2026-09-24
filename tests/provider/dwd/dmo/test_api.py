# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD DMO API."""

import datetime as dt
from typing import Literal
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.dmo.api import add_date_from_filename


@pytest.fixture
def df_files_january() -> pl.DataFrame:
    """Provide DataFrame with two dates."""
    return pl.DataFrame(
        {
            "date_str": [
                "310000",
                "311200",
            ],
        },
        orient="col",
    )


@pytest.fixture
def df_files_two_month() -> pl.DataFrame:
    """Provide DataFrame with two dates."""
    return pl.DataFrame(
        {
            "date_str": [
                "311200",
                "010000",
                "011200",
                "020000",
            ],
        },
        orient="col",
    )


@pytest.fixture
def df_files_end_of_month() -> pl.DataFrame:
    """Provide DataFrame with two dates."""
    return pl.DataFrame(
        {
            "date_str": [
                "310000",
                "311200",
            ],
        },
        orient="col",
    )


@pytest.mark.remote
def test_dwd_dmo_stations(default_settings: Settings) -> None:
    """Test fetching of DWD DMO stations."""
    # Acquire data.
    stations = DwdDmoRequest(parameters=[("hourly", "icon")], settings=default_settings)
    given_df = stations.all().df
    assert not given_df.is_empty()
    assert given_df.select(pl.all().max()).to_dicts()[0] == {
        "resolution": "hourly",
        "dataset": "icon",
        "station_id": "Z949",
        "icao_id": "ZYTX",
        "start_date": None,
        "end_date": None,
        "latitude": 79.98,
        "longitude": 179.33,
        "height": 4670.0,
        "name": "ZWOENITZ",
        "state": None,
    }
    assert given_df.select(pl.all().min()).to_dicts()[0] == {
        "resolution": "hourly",
        "dataset": "icon",
        "station_id": "01001",
        "icao_id": "AFDU",
        "start_date": None,
        "end_date": None,
        "latitude": -78.45,
        "longitude": -176.17,
        "height": -350.0,
        "name": "16N55W",
        "state": None,
    }
    station_names_sorted = given_df.sort(pl.col("name").str.len_chars()).get_column("name").to_list()
    assert station_names_sorted[:5] == ["ELM", "PAU", "SAL", "AUE", "HOF"]
    assert station_names_sorted[-5:] == [
        "MÜNSINGEN-APFELSTETT",
        "VILLINGEN-SCHWENNING",
        "WEINGARTEN BEI RAVEN",
        "LONDON WEATHER CENT.",
        "QUITO/MARISCAL SUCRE",
    ]


def test_add_date_from_filename(df_files_two_month: pl.DataFrame) -> None:
    """Test that the date is correctly set."""
    df = add_date_from_filename(df_files_two_month, dt.datetime(2021, 11, 15, tzinfo=ZoneInfo("UTC")))
    assert df.get_column("date").to_list() == [
        dt.datetime(2021, 10, 31, 12, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2021, 11, 1, 0, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2021, 11, 1, 12, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2021, 11, 2, 0, tzinfo=ZoneInfo("UTC")),
    ]


def test_add_date_from_filename_early_in_month(df_files_end_of_month: pl.DataFrame) -> None:
    """Test that the date is correctly set when the date is early in the month."""
    df = add_date_from_filename(df_files_end_of_month, dt.datetime(2021, 11, 1, 2, tzinfo=ZoneInfo("UTC")))
    assert df.get_column("date").to_list() == [
        dt.datetime(2021, 10, 31, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2021, 10, 31, 12, 0, 0, tzinfo=ZoneInfo("UTC")),
    ]


def test_add_date_from_filename_early_in_year(df_files_january: pl.DataFrame) -> None:
    """Test that the date is correctly set when the date is early in the year."""
    df = add_date_from_filename(df_files_january, dt.datetime(2021, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")))
    assert df.get_column("date").to_list() == [
        dt.datetime(2020, 12, 31, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2020, 12, 31, 12, 0, 0, tzinfo=ZoneInfo("UTC")),
    ]


@pytest.mark.remote
def test_dwd_dmo_available_issues(default_settings: Settings) -> None:
    """Verify available_issues returns a non-empty sorted list of UTC datetimes."""
    issues = DwdDmoRequest.available_issues("10147", default_settings)
    assert len(issues) > 0
    assert all(isinstance(i, dt.datetime) for i in issues)
    assert all(i.tzinfo is not None for i in issues)
    assert issues == sorted(issues)


@pytest.mark.parametrize(
    ("listing", "expected_warning"),
    [
        pytest.param([], "a listing that failed looks the same", id="directory-holding-nothing"),
        pytest.param(
            ["https://example.com/kmz/README.txt"],
            "is a forecast file",
            id="nothing-that-is-a-forecast",
        ),
        pytest.param(
            # six digits and a strip of four is not a forecast file: the extension says so, and
            # `.kmz.md5` failing the stamp test is luck rather than a rule
            ["https://example.com/kmz/ptp_gdmog_10147_078_1_210000.txt"],
            "is a forecast file",
            id="a-sidecar-that-survives-the-strip",
        ),
    ],
)
def test_dmo_available_issues_answers_rather_than_raises(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    listing: list[str],
    expected_warning: str,
) -> None:
    """The same fault `dwd/mosmix` has, reached the same way: `wetterdienst issues`.

    An empty listing builds a `url` column of dtype Null and the split below it raised `invalid
    series dtype: expected String, got null`; an entry that is not a forecast reached
    `add_date_from_filename` and raised `conversion from str to i64 failed ... ["AD"]`. "Which runs
    exist?" has an answer in both cases: none, said out loud. GH-1946 does the same for the other
    provider; neither depends on the other.
    """
    import logging  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: listing)

    assert DwdDmoRequest.available_issues("01001", Settings()) == []
    assert expected_warning in caplog.text


def _stub_dmo_values(
    lead_time: Literal["short", "long"] = "short",
    dataset: str = "icon",
    station_group: Literal["single_stations", "all_stations"] = "single_stations",
) -> object:
    """Stand a DMO station up rather than look one up, so these need no network."""
    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415

    request = DwdDmoRequest(
        parameters=[("hourly", dataset)],
        lead_time=lead_time,
        station_group=station_group,
    )
    df_stations = pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "icon",
                "station_id": "02378",  # an id containing "78", which is the point
                "start_date": None,
                "end_date": None,
                "latitude": 52.5,
                "longitude": 13.4,
                "height": 40.0,
                "name": "Berlin",
                "state": None,
            },
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
            "state": pl.String,
        },
        orient="row",
    )
    return StationsResult(
        stations=request,
        df=df_stations,
        df_all=df_stations,
        stations_filter=StationsFilter.BY_STATION_ID,
    ).values


@pytest.mark.parametrize(
    ("listing", "expected"),
    [
        pytest.param(
            # the station id carries "78", which the bare substring match read as the lead time,
            # so both files were kept, both carried one run, and `.item()` raised
            ["ptp_gdmog_02378_078_1_210000.kmz", "ptp_gdmog_02378_168_3_210000.kmz"],
            "ptp_gdmog_02378_078_1_210000.kmz",
            id="a-station-id-containing-the-lead-time",
        ),
        pytest.param(
            # a checksum beside the forecast: kept by the substring match, mapped to the same run
            ["ptp_gdmog_02378_078_1_210000.kmz", "ptp_gdmog_02378_078_1_210000.kmz.md5"],
            "ptp_gdmog_02378_078_1_210000.kmz",
            id="a-checksum-beside-the-forecast",
        ),
        pytest.param(
            # worse than a crash: this one parses to a valid run and was answered with, so the
            # failure moved into the reader with nothing pointing back at the listing
            ["ptp_gdmog_02378_078_1_210000.kmz", "ptp_gdmog_02378_078_1_210000.txt"],
            "ptp_gdmog_02378_078_1_210000.kmz",
            id="a-sidecar-that-parses-to-a-run",
        ),
    ],
)
def test_dmo_reads_a_run_by_its_whole_name(monkeypatch: pytest.MonkeyPatch, listing: list[str], expected: str) -> None:
    """Every part of a DMO name was read by position or by substring, and each wrongly."""
    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [f"https://example.com/kmz/{name}" for name in listing],
    )

    resolved = _stub_dmo_values().get_url_for_date("https://example.com/kmz/", api.DwdForecastDate.LATEST)

    assert resolved.rsplit("/", 1)[-1] == expected


def test_dmo_accepts_the_issues_it_advertises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command that says which issues exist printed them in a form the next one rejected.

    `available_issues` returns tz-aware UTC datetimes, `get_url_for_date` compared against a naive
    column, and `get_issues` renders with `isoformat()` -- so the documented path raised
    `could not evaluate comparison between series 'date' of dtype: Datetime('us') and ... 'UTC'`.
    """
    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    listing = ["https://example.com/kmz/ptp_gdmog_02378_078_1_210000.kmz"]
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: listing)

    advertised = DwdDmoRequest.available_issues("02378", Settings())

    assert advertised
    assert advertised[0].tzinfo is not None
    resolved = _stub_dmo_values().get_url_for_date("https://example.com/kmz/", advertised[0])
    assert resolved == listing[0]


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        pytest.param(0, 0, id="a-release-hour"),
        pytest.param(3, 0, id="the-morning-floors-down"),
        pytest.param(11, 0, id="just-before-the-second-release"),
        pytest.param(12, 12, id="the-second-release-hour"),
        pytest.param(14, 12, id="the-afternoon-floors-down"),
        pytest.param(23, 12, id="the-end-of-the-day"),
    ],
)
def test_dmo_issue_is_floored_to_a_release_hour(hour: int, expected: int) -> None:
    """DMO releases at 00 and 12, and an issue between them belongs to the one before it.

    `hour % 12` is non-zero for 1 through 11 as well as 13 through 23, and sending both to 12
    rounded the morning *up*: asking for the 03:00 run returned the 12:00 one, issued nine hours
    later, or raised where 12:00 was not yet published while 00:00 sat there unasked for.

    Unreachable until the tz comparison in this branch was fixed -- every non-`LATEST` issue raised
    `SchemaError` before reaching here -- which is what made a latent rounding bug into a live one.
    """
    adjusted = DwdDmoRequest.adjust_datetime(dt.datetime(2026, 9, 22, hour, tzinfo=ZoneInfo("UTC")))

    assert adjusted.hour == expected


@pytest.mark.parametrize(
    ("given", "expected_hour"),
    [
        pytest.param("2026-09-22T13:00+02:00", 0, id="an-offset-is-converted-not-relabelled"),
        pytest.param("2026-09-22T11:00+00:00", 0, id="the-same-instant-in-utc"),
        pytest.param("2026-09-22T03:00", 0, id="a-naive-issue-is-utc"),
        pytest.param("2026-09-22T23:00+02:00", 12, id="an-offset-that-floors-to-the-later-release"),
    ],
)
def test_dmo_issue_given_in_another_zone_means_the_same_instant(given: str, expected_hour: int) -> None:
    """An issue was relabelled UTC rather than converted, so another zone floored to another run.

    `13:00+02:00` is 11:00 UTC and belongs to the 00:00 release; read as 13:00 UTC it floored to
    12:00 -- one release too late, and at 11:00 UTC a run not yet published, so the caller got an
    `IndexError` where the 00:00 run was sitting there. A naive issue is taken as UTC, which is
    what it has always meant here.
    """
    request = DwdDmoRequest(parameters=[("hourly", "icon")], issue=given)

    assert request.issue.hour == expected_hour
    assert request.issue.tzinfo == ZoneInfo("UTC")


def test_dmo_an_empty_listing_is_reported_once_per_product_not_once_per_station(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`single_stations` is the default, and its URL carries the station id.

    Keying the dedup on the URL itself deduplicated only the `all_stations` half. `icon_eu` has no
    single-station directory upstream at all (404), so a request for it would have printed one
    warning per station of the catalogue for one root cause.
    """
    import logging  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])
    values = _stub_dmo_values()

    for station_id in ("01001", "01002", "01003"):
        url = f"https://opendata.dwd.de/weather/local_forecasts/dmo/icon/single_stations/{station_id}/kmz/"
        assert values.get_url_for_date(url, api.DwdForecastDate.LATEST) is None

    warnings = [record for record in caplog.records if "No DMO run listed within" in record.message]
    assert len(warnings) == 1


@pytest.mark.parametrize(
    ("dataset", "station_group", "expected"),
    [
        ("icon", "single_stations", "dmo/icon/single_stations/01001/kmz/"),
        ("icon", "all_stations", "dmo/icon/all_stations/kmz"),
        ("icon_eu", "single_stations", "dmo/icon-eu/single_stations/01001/kmz/"),
        ("icon_eu", "all_stations", "dmo/icon-eu/all_stations/kmz"),
    ],
)
def test_dmo_available_issues_reads_the_directory_the_values_path_reads(
    monkeypatch: pytest.MonkeyPatch,
    dataset: Literal["icon", "icon_eu"],
    station_group: Literal["single_stations", "all_stations"],
    expected: str,
) -> None:
    """The whole of GH-1956: the two were hardcoded separately and named different directories.

    `available_issues` always listed `icon/single_stations/<id>/kmz/`, so it advertised the runs of
    one product for a request that would go on to read another -- and both mismatches were live.
    `all_stations` publishes only the `078` lead time, so an issue advertised from a `168` file met
    `IndexError: Unable to find a 168 h forecast within ...`; and `icon-eu` has no single-station
    directory upstream at all, so every issue advertised for it resolved to an empty frame.
    """
    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    listed = []

    def listing(url: str, *_args: object, **_kwargs: object) -> list[str]:
        listed.append(url)
        return []

    monkeypatch.setattr(api, "list_remote_files_fsspec", listing)
    DwdDmoRequest.available_issues("01001", Settings(), dataset=dataset, station_group=station_group)

    assert listed == [f"https://opendata.dwd.de/weather/local_forecasts/{expected}"]
    # and the values path, asked for the same thing, reads exactly that
    values = _stub_dmo_values(dataset=dataset, station_group=station_group)
    assert (
        values.get_dwd_dmo_path(DwdDmoRequest.metadata["hourly"][dataset], "01001")
        == f"weather/local_forecasts/{expected}"
    )


@pytest.mark.parametrize(
    ("lead_time", "expected_hours"),
    [("short", [0]), ("long", [12]), (None, [0, 12])],
    ids=["short", "long", "every-lead-time"],
)
def test_dmo_available_issues_answers_for_the_lead_time_it_is_asked_for(
    monkeypatch: pytest.MonkeyPatch,
    lead_time: str | None,
    expected_hours: list[int],
) -> None:
    """A run belongs to a lead time, and the values path filters to one.

    Listing both together advertised an issue carried only by a `168` file to a `short` request,
    which then raised. `None` keeps the old behaviour for a caller asking about the directory rather
    than about a request.
    """
    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    # one run per lead time, an hour apart, so which was kept is visible in the answer
    listing = [
        "https://example.com/kmz/ptp_gdmog_01001_078_1_010000.kmz",
        "https://example.com/kmz/ptp_gdmog_01001_168_3_011200.kmz",
    ]
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: listing)

    issues = DwdDmoRequest.available_issues("01001", Settings(), lead_time=lead_time)

    assert sorted(issue.hour for issue in issues) == expected_hours
    assert all(issue.tzinfo is not None for issue in issues)
