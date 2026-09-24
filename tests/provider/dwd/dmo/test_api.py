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
        # Y0353 MONT BLANC, and Y0342 "ÄGYPT. WÜSTE" whose leading Ä sorts past Z -- both stations
        # the shared catalogue omits, described from the run instead (GH-1966)
        "height": 4806.0,
        "name": "ÄGYPT. WÜSTE",
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
    # by length and then by name: 248 stations share the longest name length, so sorting by length
    # alone leaves the ends of this list to whatever order the frame happened to be built in --
    # which is how appending the station patches used to decide it
    station_names_sorted = given_df.sort(pl.col("name").str.len_chars(), pl.col("name")).get_column("name").to_list()
    assert station_names_sorted[:5] == ["ARE", "AUE", "AUE", "AUE", "BAM"]
    assert station_names_sorted[-5:] == [
        "WUTOESCHINGEN-OFTER.",
        "ZELL I.WIES.-PFAFFB.",
        "ZERBST/SACHS.-ANHALT",  # one of the stations the catalogue omits (GH-1966)
        "ZINNWALD-GEORGENFELD",
        "ZUERICH (TOWN/VILLE)",
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

    Keying the dedup on the URL itself deduplicated only the `all_stations` half. A request for
    `icon_eu` would have printed one warning per station of the catalogue for one root cause,
    because the catalogue was the one shared by both products and 2255 of its stations have no
    `icon_eu` directory to list (GH-1964).
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
    `icon_eu`'s `all_stations` publishes only the `078` lead time, so an issue advertised from a
    `168` file met `IndexError: Unable to find a 168 h forecast within ...`; and a station the
    shared catalogue listed for `icon_eu` without `icon_eu` covering it has no single-station
    directory upstream, so every issue advertised for it resolved to an empty frame (GH-1964).
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


def _catalogue_line(station_id: str, name: str, latitude: str = "54.23", longitude: str = "10.30") -> str:
    """Lay one station out at the fixed-width offsets `_all` reads the DWD catalogue at.

    Positions are written the way the catalogue writes them -- degrees and minutes, the minutes right
    aligned in two columns -- so a caller can hand in `. 5` or `.-6` and have it arrive as the reader
    really meets it, padding and all.
    """
    return f"{station_id:<5}{'----':<5}{name:<21}{latitude:>8}{longitude:>8} {'40':>9}"


def _stub_catalogue(
    monkeypatch: pytest.MonkeyPatch,
    station_ids: list[str],
    positions: dict[str, tuple[str, str]] | None = None,
) -> None:
    """Answer the shared `dmo_stationsliste_txt.asc` with a catalogue of exactly these stations."""
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    positions = positions or {}
    lines = ["ID   ICAO NAME                      LAT      LON    ELEV", "-" * 57]
    lines += [
        _catalogue_line(station_id, f"Station {station_id}", *positions.get(station_id, ("54.23", "10.30")))
        for station_id in station_ids
    ]
    # `_all` pops the header and then skips one more line, so both of those have to be here
    content = ("\n".join(lines) + "\n").encode("latin-1")

    class _StubFile:
        def __init__(self) -> None:
            self.content = BytesIO(content)

        def raise_if_exception(self) -> None:
            pass

    monkeypatch.setattr(api, "download_file", lambda **_kwargs: _StubFile())


def _stub_coverage(monkeypatch: pytest.MonkeyPatch, coverage: dict[str, list[str]]) -> None:
    """Answer each product's `single_stations/` listing with the stations it is said to cover."""
    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    def listing(url: str, *_args: object, **_kwargs: object) -> list[dict]:
        product = "icon_eu" if "icon-eu" in url else "icon"
        return [{"name": f"{url.rstrip('/')}/{station_id}/", "type": "directory"} for station_id in coverage[product]]

    monkeypatch.setattr(api, "list_remote_directory_fsspec", listing)


def _advertised(df: pl.DataFrame, dataset: str) -> list[str]:
    """Give back the catalogue stations one dataset advertises."""
    return sorted(set(df.filter(dataset=dataset).get_column("station_id").to_list()))


def test_dmo_a_station_is_advertised_only_for_the_product_that_covers_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole of GH-1964: one catalogue was served for two products covering different stations.

    `dmo_stationsliste_txt.asc` is one list for both, and matches neither -- of its 5811 stations
    `icon` covers 5622 and `icon_eu` 3556 (measured 2026-09-24). So `icon_eu` advertised 2255
    stations that could only ever answer with an empty frame, which from the caller's side is
    indistinguishable from a forecast that is merely missing right now, and from the swallowed
    listing GH-1947 was about.
    """
    _stub_catalogue(monkeypatch, ["01001", "01023", "01047"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "01023", "01047"], "icon_eu": ["01023"]})

    df = DwdDmoRequest(parameters=[("hourly", "icon"), ("hourly", "icon_eu")]).all().df

    assert _advertised(df, "icon") == ["01001", "01023", "01047"]
    assert _advertised(df, "icon_eu") == ["01023"]


@pytest.mark.parametrize(
    ("dataset", "expected"),
    [
        ("icon", "https://opendata.dwd.de/weather/local_forecasts/dmo/icon/single_stations"),
        ("icon_eu", "https://opendata.dwd.de/weather/local_forecasts/dmo/icon-eu/single_stations"),
    ],
)
def test_dmo_coverage_is_read_from_the_directory_that_holds_one_entry_per_station(
    monkeypatch: pytest.MonkeyPatch,
    dataset: Literal["icon", "icon_eu"],
    expected: str,
) -> None:
    """`single_stations/` holds a directory per station; `all_stations/kmz` holds the runs.

    Listing the latter would hand back run filenames as if they were station ids, and every station
    in the catalogue would then be filtered out of it -- an empty stations result for a product that
    covers thousands.
    """
    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    listed = []

    def listing(url: str, *_args: object, **_kwargs: object) -> list[dict]:
        listed.append(url)
        return [{"name": f"{url}/01001/", "type": "directory"}]

    _stub_catalogue(monkeypatch, ["01001"])
    monkeypatch.setattr(api, "list_remote_directory_fsspec", listing)
    DwdDmoRequest(parameters=[("hourly", dataset)]).all()

    assert listed == [expected]


def test_dmo_a_station_listing_that_cannot_be_read_keeps_the_catalogue_and_says_why(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A listing that failed and a product that covers nothing mean opposite things.

    Answering the second for the first would empty the stations result over a transient network
    fault, so the shared catalogue stays -- but the caller has to hear that it is the wider one.
    """
    import logging  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    _stub_catalogue(monkeypatch, ["01001", "01023"])

    def raising(*_args: object, **_kwargs: object) -> list[dict]:
        msg = "connection reset"
        raise OSError(msg)

    monkeypatch.setattr(api, "list_remote_directory_fsspec", raising)

    df = DwdDmoRequest(parameters=[("hourly", "icon_eu")]).all().df

    assert _advertised(df, "icon_eu") == ["01001", "01023"]
    assert [record for record in caplog.records if "falling back to the catalogue" in record.message]


def test_dmo_an_empty_station_listing_keeps_the_catalogue_too(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An empty listing is the swallowed-walk shape of GH-1947, not a product without stations."""
    import logging  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    _stub_catalogue(monkeypatch, ["01001", "01023"])
    monkeypatch.setattr(api, "list_remote_directory_fsspec", lambda *_args, **_kwargs: [])

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert _advertised(df, "icon") == ["01001", "01023"]
    assert [record for record in caplog.records if "No station listed within" in record.message]


def test_every_dmo_product_has_a_directory_upstream() -> None:
    """The metadata names a product; only this mapping knows what upstream serves it from.

    A third DMO product would otherwise inherit the metadata spelling by default and 404 at request
    time, far from the decision that was never made -- the way `icon_eu` would have, being served
    from `icon-eu`.
    """
    from wetterdienst.provider.dwd.dmo.api import _DMO_PRODUCT_DIRS  # noqa: PLC0415

    products = {dataset.name_original for resolution in DwdDmoRequest.metadata for dataset in resolution}

    assert products <= set(_DMO_PRODUCT_DIRS), f"no upstream directory for {products - set(_DMO_PRODUCT_DIRS)}"


def test_dmo_refuses_a_product_it_knows_no_directory_for() -> None:
    """Named as itself, rather than passed through to a 404 the caller works backwards from."""
    from wetterdienst.provider.dwd.dmo.api import _dmo_product_dir  # noqa: PLC0415

    with pytest.raises(ValueError, match="No DMO product directory is known for 'icon_d2'"):
        _dmo_product_dir("icon_d2")


@pytest.mark.remote
def test_dmo_the_two_products_really_do_cover_different_stations(default_settings: Settings) -> None:
    """Upstream rather than a stub, because the premise of the fix is a fact about upstream."""
    covered = {
        dataset: set(
            DwdDmoRequest(parameters=[("hourly", dataset)], settings=default_settings)
            .all()
            .df.get_column("station_id")
            .to_list()
        )
        for dataset in ("icon", "icon_eu")
    }

    assert covered["icon"], "icon covers no station at all"
    assert covered["icon_eu"], "icon_eu covers no station at all"
    assert len(covered["icon_eu"]) < len(covered["icon"]), "icon_eu covers at least as many stations as icon"


@pytest.mark.parametrize(
    ("written", "expected_dd"),
    [
        # what the catalogue writes for most stations: degrees, then zero-padded minutes
        pytest.param("70.56", 70.93, id="degrees-and-minutes"),
        pytest.param("-8.40", -8.67, id="negative-degrees-and-minutes"),
        pytest.param("51.05", 51.08, id="minutes-under-ten-keep-their-zero"),
        # and what it writes where the degrees are zero: no degrees, minutes unpadded
        pytest.param(".19", 0.32, id="no-degrees-two-minute-digits"),
        pytest.param(".5", 0.08, id="no-degrees-one-minute-digit"),
        pytest.param("-.31", -0.52, id="negative-with-no-degrees"),
        pytest.param(".0", 0.0, id="no-degrees-no-minutes"),
        # and where such a value is negative, the sign lands on the minutes
        pytest.param(".-6", -0.1, id="sign-written-onto-the-minutes"),
        pytest.param(".-12", -0.2, id="sign-onto-two-minute-digits"),
        # minutes rounded up to a full sixty carry into the degrees by arithmetic
        pytest.param("-4.60", -5.0, id="sixty-minutes"),
        # the repair is for degreeless fields only: a field that carries its degrees is left alone,
        # so an unanchored rule that rewrote `51.5` into `510.05` would be caught here. No row in the
        # catalogue is written this way today -- every one of its 11 545 fields that carries degrees
        # pads its minutes -- which is exactly why nothing but a test pins it
        pytest.param("51.5", 51.83, id="degrees-present-are-left-alone"),
        # the columns arrive padded out of the fixed-width read, and every rule above is anchored
        pytest.param("    .-6 ", -0.1, id="padded-sign-onto-minutes"),
        pytest.param("  51.31 ", 51.52, id="padded-degrees-and-minutes"),
    ],
)
def test_dmo_a_position_is_read_as_the_degrees_and_minutes_it_is_written_in(
    written: str,
    expected_dd: float,
) -> None:
    """`.5` is five minutes, not fifty; `.-6` is minus six minutes, not a parse error.

    Both were live. Read as a plain decimal `.5` puts a station 84 km from where DWD says it is and
    raises nothing, and `.-6` raised `conversion from str to f64 failed` -- which is what the seven
    hardcoded station patches existed to avoid, less accurately than this.
    """
    from wetterdienst.provider.dwd.dmo.api import _dm_degrees  # noqa: PLC0415

    got = pl.DataFrame({"latitude": [written]}).select(_dm_degrees("latitude")).item()

    # `convert_dm_to_dd` rounds the converted minutes to two decimals, which is what makes these
    # land exactly on the values DWD's own KMZ placemarks carry
    assert got == pytest.approx(expected_dd, abs=5e-3)


def test_dmo_a_catalogue_of_awkward_positions_still_reaches_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """A position that would not cast took the whole stations result down with it.

    The seven that did were listed by hand; nothing said so when an eighth appeared, and the error
    named neither the column nor the station. Every degreeless shape the file actually writes is in
    this catalogue, read end to end rather than through `_dm_degrees` alone.
    """
    positions = {
        "01001": ("54.23", ". 5"),  # one minute digit, behind the space the format leaves
        "01023": (". 3", "10.30"),  # the same in the latitude column
        "01047": ("51.31", ".-6"),  # the sign written onto the minutes
        "01052": (".19", "-.31"),  # degreeless and readable as written, both signs
    }
    stations = list(positions)
    _stub_catalogue(monkeypatch, stations, positions)
    _stub_coverage(monkeypatch, {"icon": stations, "icon_eu": []})

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert sorted(df.get_column("station_id").to_list()) == stations
    assert df.get_column("latitude").null_count() == 0
    assert df.get_column("longitude").null_count() == 0
    positions_read = {row["station_id"]: (row["latitude"], row["longitude"]) for row in df.iter_rows(named=True)}
    assert positions_read["01001"] == pytest.approx((54.38, 0.08), abs=5e-3)
    assert positions_read["01023"] == pytest.approx((0.05, 10.5), abs=5e-3)
    assert positions_read["01047"] == pytest.approx((51.52, -0.1), abs=5e-3)
    assert positions_read["01052"] == pytest.approx((0.32, -0.52), abs=5e-3)


@pytest.mark.remote
def test_dmo_the_catalogue_upstream_needs_no_hardcoded_positions(default_settings: Settings) -> None:
    """Upstream, because the claim being made is about the file DWD publishes today.

    Every position in it parses, and the stations that used to be patched are among them -- so the
    hardcoded rows are not merely unused, they are unnecessary.
    """
    formerly_patched = ["03779", "03781", "61226", "82106", "84071", "F9766", "P0478"]

    df = (
        DwdDmoRequest(parameters=[("hourly", "icon")], settings=default_settings)
        .all()
        .df.filter(pl.col("station_id").is_in(formerly_patched))
    )

    assert sorted(df.get_column("station_id").to_list()) == sorted(formerly_patched)
    assert df.get_column("latitude").null_count() == 0
    assert df.get_column("longitude").null_count() == 0
    # the value DWD's own KMZ placemarks carry for this station, which the patch missed by 11 km
    london = df.filter(station_id="03779")
    assert london.get_column("longitude").item() == pytest.approx(-0.1, abs=5e-3)
    assert london.get_column("height").item() == pytest.approx(43, abs=1)


def test_dmo_a_listing_that_names_no_station_is_not_believed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A directory tree that stops being one directory per station still yields names.

    Were `single_stations/` reorganised into a subdirectory per lead time, the listing would come
    back as `{"078", "168"}` -- not empty, so the emptiness check passes, and sharing no station with
    the catalogue, so filtering by it removes every station there is. That is an empty stations frame
    with nothing raised and nothing logged: the silence GH-1964 exists to end, arriving through the
    change that ends it.
    """
    import logging  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    _stub_catalogue(monkeypatch, ["01001", "01023"])
    _stub_coverage(monkeypatch, {"icon": ["078", "168"], "icon_eu": []})

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert _advertised(df, "icon") == ["01001", "01023"]
    assert [record for record in caplog.records if "names a station in the catalogue" in record.message]


def test_dmo_one_station_in_common_is_enough_to_narrow_by(monkeypatch: pytest.MonkeyPatch) -> None:
    """The products really do cover different subsets, so the guard has to allow a near-total drop.

    Anything stricter than "names at least one of ours" would refuse the disagreement this reads the
    listing to represent.
    """
    _stub_catalogue(monkeypatch, ["01001", "01023", "01047"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "01023", "01047"], "icon_eu": ["01023"]})

    df = DwdDmoRequest(parameters=[("hourly", "icon_eu")]).all().df

    assert _advertised(df, "icon_eu") == ["01023"]


def test_dmo_the_coverage_listing_is_read_once_per_product_per_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """`all()` is not memoized and the filters call it repeatedly.

    `filter_by_rank` calls it twice and `filter_by_distance` four times, so without this the 640 KB
    index is fetched once per call -- and `cache_disable`, which a caller sets to get fresh data,
    turns fsspec's listings cache off too, so nothing else deduplicates it.
    """
    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    listed = []

    def listing(url: str, *_args: object, **_kwargs: object) -> list[dict]:
        listed.append(url)
        return [{"name": f"{url}/{station_id}/", "type": "directory"} for station_id in ("01001", "01023")]

    _stub_catalogue(monkeypatch, ["01001", "01023"])
    monkeypatch.setattr(api, "list_remote_directory_fsspec", listing)

    request = DwdDmoRequest(parameters=[("hourly", "icon")])
    for _ in range(4):
        request.all()

    assert len(listed) == 1

    # and a second request does its own reading, rather than inheriting the first one's answer
    DwdDmoRequest(parameters=[("hourly", "icon")]).all()
    assert len(listed) == 2


def _kml_of(placemarks: dict[str, tuple[str, str]]) -> bytes:
    """Build the document `KMLReader.fetch` hands back, carrying just these placemarks.

    The document rather than the archive, because `fetch` is what these tests stand in for and
    unzipping is its job.
    """
    body = "".join(
        f"""<kml:Placemark>
            <kml:name>{station_id}</kml:name>
            <kml:description>{name}</kml:description>
            <kml:Point><kml:coordinates>{coordinates}</kml:coordinates></kml:Point>
        </kml:Placemark>"""
        for station_id, (name, coordinates) in placemarks.items()
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml:kml xmlns:kml="http://www.opengis.net/kml/2.2">'
        f"<kml:Document>{body}</kml:Document></kml:kml>"
    )
    return document.encode()


def _stub_runs(monkeypatch: pytest.MonkeyPatch, placemarks: dict[str, tuple[str, str]]) -> list[str]:
    """Answer the `all_stations` listing with one run, carrying these placemarks."""
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    listed = []

    def listing(url: str, *_args: object, **_kwargs: object) -> list[str]:
        listed.append(url)
        return [f"{url}/ptp_gdmog_078_1_240000.kmz"]

    monkeypatch.setattr(api, "list_remote_files_fsspec", listing)
    monkeypatch.setattr(api.KMLReader, "fetch", lambda _self, _url: BytesIO(_kml_of(placemarks)))
    return listed


def test_dmo_a_station_the_catalogue_omits_is_described_from_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """GH-1966: 135 stations `icon` forecasts for are absent from the shared catalogue.

    Absent from it they were filtered out of every request, so they could not be asked for at all --
    although their forecasts are published and fetch with HTTP 200. The run describes them.
    """
    _stub_catalogue(monkeypatch, ["01001"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "Y0330"], "icon_eu": []})
    _stub_runs(monkeypatch, {"Y0330": ("KEHYTSCHIWKA", "35.75,49.28,152.0")})

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert _advertised(df, "icon") == ["01001", "Y0330"]
    added = df.filter(station_id="Y0330").row(0, named=True)
    assert added["name"] == "KEHYTSCHIWKA"
    assert (added["latitude"], added["longitude"]) == pytest.approx((49.28, 35.75))
    assert added["height"] == pytest.approx(152.0)
    # the run carries no ICAO id, which is why this fills the catalogue rather than replacing it
    assert added["icao_id"] is None


def test_dmo_the_catalogue_is_left_alone_where_it_describes_a_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """The catalogue is the only source of an ICAO id, so it keeps the stations it does list."""
    _stub_catalogue(monkeypatch, ["01001"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "Y0330"], "icon_eu": []})
    # the run describes 01001 too, differently; the catalogue's description is the one that stands
    _stub_runs(
        monkeypatch,
        {"01001": ("SOMEWHERE ELSE", "1.0,2.0,3.0"), "Y0330": ("KEHYTSCHIWKA", "35.75,49.28,152.0")},
    )

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    catalogued = df.filter(station_id="01001").row(0, named=True)
    assert catalogued["name"] == "Station 01001"
    assert catalogued["latitude"] == pytest.approx(54.38, abs=5e-3)
    assert len(df.filter(station_id="01001")) == 1


def test_dmo_a_complete_catalogue_costs_no_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is fetched when the catalogue already lists every station the product covers.

    So a catalogue DWD completes stops costing the ~8 MB run download by itself.
    """
    _stub_catalogue(monkeypatch, ["01001", "01023"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "01023"], "icon_eu": []})
    listed = _stub_runs(monkeypatch, {"Y0330": ("KEHYTSCHIWKA", "35.75,49.28,152.0")})

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert _advertised(df, "icon") == ["01001", "01023"]
    assert listed == []


def test_dmo_a_run_that_cannot_be_read_leaves_the_catalogue_as_it_was(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The stations it would have described stay unreachable; the rest of the request still works."""
    import logging  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    _stub_catalogue(monkeypatch, ["01001"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "Y0330"], "icon_eu": []})

    def raising(*_args: object, **_kwargs: object) -> list[str]:
        msg = "connection reset"
        raise OSError(msg)

    monkeypatch.setattr(api, "list_remote_files_fsspec", raising)

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert _advertised(df, "icon") == ["01001"]
    assert [record for record in caplog.records if "stay unreachable" in record.message]


def test_dmo_the_run_is_read_once_per_product_per_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """`all()` is not memoized, and this fetch is the expensive one of the two."""
    _stub_catalogue(monkeypatch, ["01001"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "Y0330"], "icon_eu": []})
    listed = _stub_runs(monkeypatch, {"Y0330": ("KEHYTSCHIWKA", "35.75,49.28,152.0")})

    request = DwdDmoRequest(parameters=[("hourly", "icon")])
    for _ in range(4):
        request.all()

    assert len(listed) == 1


def test_dmo_the_newest_run_describes_the_stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station list read from a run should be the current one, not whichever the directory names first.

    The directory holds several runs at once -- eight for `icon` -- and a station added or moved
    upstream appears in the newest, so reading an older one would describe the catalogue's gaps as
    they were up to twelve hours ago.
    """
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    # across a month boundary, because the stamp is a day of the month: sorted as text the 31st
    # follows the 1st, so sorting by the stamp itself answers with the oldest run in the directory
    # for the first hours of every month
    runs = {
        "ptp_gdmog_078_1_311200.kmz": {"Y0330": ("AS IT WAS LAST MONTH", "1.0,2.0,3.0")},
        "ptp_gdmog_078_1_011200.kmz": {"Y0330": ("KEHYTSCHIWKA", "35.75,49.28,152.0")},
        "ptp_gdmog_078_1_010000.kmz": {"Y0330": ("AS IT WAS AT MIDNIGHT", "4.0,5.0,6.0")},
    }

    def listing(url: str, *_args: object, **_kwargs: object) -> list[str]:
        return [f"{url}/{name}" for name in runs]

    monkeypatch.setattr(api, "list_remote_files_fsspec", listing)
    monkeypatch.setattr(
        api.KMLReader,
        "fetch",
        lambda _self, url: BytesIO(_kml_of(runs[url.rsplit("/", 1)[-1]])),
    )
    _stub_catalogue(monkeypatch, ["01001"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "Y0330"], "icon_eu": []})

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert df.filter(station_id="Y0330").get_column("name").item() == "KEHYTSCHIWKA"


def test_dmo_an_empty_run_listing_is_reported_as_one(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An empty listing and a directory that could not be read are different things.

    An empty list gives polars a null-dtype column, and `_run_stamp`'s `str.split` raises
    `SchemaError` on it -- which the handler around the fetch would report as a failure to read the
    directory, diagnosing a swallowed walk as a network fault.
    """
    import logging  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    _stub_catalogue(monkeypatch, ["01001"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "Y0330"], "icon_eu": []})
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert _advertised(df, "icon") == ["01001"]
    messages = [record.message for record in caplog.records]
    assert [m for m in messages if "No DMO run listed within" in m]
    assert not [m for m in messages if "SchemaError" in m]


def test_dmo_a_comment_in_a_run_does_not_cost_the_stations_it_describes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lxml gives a comment a callable tag, so `endswith` on it raises.

    Raised inside the parse, it discarded every station the run described -- all 135 of them for one
    comment anywhere in the document.
    """
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo import api  # noqa: PLC0415

    document = _kml_of({"Y0330": ("KEHYTSCHIWKA", "35.75,49.28,152.0")}).replace(
        b"<kml:Placemark>",
        b"<kml:Placemark><!-- a comment -->",
    )
    _stub_catalogue(monkeypatch, ["01001"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "Y0330"], "icon_eu": []})
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda url, *_a, **_k: [f"{url}/ptp_gdmog_078_1_240000.kmz"])
    monkeypatch.setattr(api.KMLReader, "fetch", lambda _self, _url: BytesIO(document))

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert _advertised(df, "icon") == ["01001", "Y0330"]


def test_dmo_one_unreadable_placemark_does_not_cost_the_others(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The run is the only description these stations have, so it is read for what it does carry."""
    import logging  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    _stub_catalogue(monkeypatch, ["01001"])
    _stub_coverage(monkeypatch, {"icon": ["01001", "Y0330", "G431"], "icon_eu": []})
    _stub_runs(
        monkeypatch,
        {
            "Y0330": ("KEHYTSCHIWKA", "35.75,49.28,152.0"),
            "G431": ("NOWHERE", "not,a,number"),
        },
    )

    df = DwdDmoRequest(parameters=[("hourly", "icon")]).all().df

    assert _advertised(df, "icon") == ["01001", "Y0330"]
    assert [record for record in caplog.records if "could be read" in record.message]


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        pytest.param("240000", dt.datetime(2026, 9, 24, 0, 0, tzinfo=ZoneInfo("UTC")), id="midnight"),
        pytest.param("241200", dt.datetime(2026, 9, 24, 12, 0, tzinfo=ZoneInfo("UTC")), id="noon"),
        pytest.param("010300", dt.datetime(2026, 9, 1, 3, 0, tzinfo=ZoneInfo("UTC")), id="single-digit-hour"),
        pytest.param("010900", dt.datetime(2026, 9, 1, 9, 0, tzinfo=ZoneInfo("UTC")), id="another-hour"),
    ],
)
def test_dmo_a_run_stamp_becomes_the_hour_it_names(stamp: str, expected: dt.datetime) -> None:
    """Every part of `DDHHMM` is padded back to two digits before the datetime is parsed.

    The hour was not, so `3` made `...01300`, where `%H` takes the `30` it can see and rejects it as
    an hour. `00` survived only because `%H` could take both its digits and leave `%M` the one it
    needed. DMO publishes at `00` and `12` so no run has ever hit this, but the rule is about the
    stamp rather than about which hours DWD happens to use.
    """
    from wetterdienst.provider.dwd.dmo.api import add_date_from_filename  # noqa: PLC0415

    df = add_date_from_filename(
        pl.DataFrame({"date_str": [stamp]}),
        dt.datetime(2026, 9, 24, 12, 0, tzinfo=ZoneInfo("UTC")),
    )

    assert df.get_column("date").item() == expected


# upstream serves these and no canonical parameter names them, so the metadata cannot declare them
# yet. Named here rather than skipped, so that adding one of them makes this test say so. `rad3h`
# is only in the 3-hourly run, which is why `icon_eu`, publishing 078 alone, does not see it
@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "lead_times", "without_a_canonical_name"),
    [
        pytest.param("icon", ("078", "168"), {"rad3h", "radl1", "rads1"}, id="icon"),
        pytest.param("icon_eu", ("078",), {"radl1", "rads1"}, id="icon_eu"),
    ],
)
def test_dmo_declares_the_elements_its_runs_carry(
    dataset: str,
    lead_times: tuple[str, ...],
    without_a_canonical_name: set[str],
    default_settings: Settings,
) -> None:
    """A DMO run carries 21 elements; the metadata declared 122 for `icon` and 40 for `icon_eu`.

    Those lists were MOSMIX's, copied in when the provider was written -- which is also why `icon`
    held MOSMIX-L's 115 and `icon_eu` MOSMIX-S's 40, a split DMO does not have: both products carry
    the same elements, and differ in the domain and the lead times they carry them for. A request
    for one of the other 99 and 22 came back empty with nothing saying the product never forecasts
    it, which reads exactly like a station with no data.

    Upstream rather than a stub, because what is asserted is a fact about upstream. It reads a
    single-station run through `KMLReader`, the same handle the values path parses.
    """
    import re  # noqa: PLC0415
    from urllib.parse import urljoin  # noqa: PLC0415

    from wetterdienst.provider.dwd.dmo.api import DwdDmoStationGroup, _dmo_kmz_path  # noqa: PLC0415
    from wetterdienst.provider.dwd.mosmix.access import KMLReader  # noqa: PLC0415
    from wetterdienst.util.network import list_remote_directory_fsspec  # noqa: PLC0415

    name_original = DwdDmoRequest.metadata["hourly"][dataset].name_original
    stations = (
        DwdDmoRequest(parameters=[("hourly", dataset)], settings=default_settings)
        .all()
        .df.get_column("station_id")
        .to_list()
    )
    assert stations, f"{dataset} covers no station at all"

    # a station the catalogue lists may still have no directory of its own, so take the first that
    # does rather than pinning one id that upstream is free to drop
    files: list[str] = []
    for station_id in stations[:5]:
        url = urljoin(
            "https://opendata.dwd.de",
            _dmo_kmz_path(name_original, DwdDmoStationGroup.SINGLE_STATIONS, station_id),
        )
        try:
            entries = list_remote_directory_fsspec(url, settings=default_settings)
        except Exception:  # noqa: BLE001, S112
            continue
        files = [entry["name"] for entry in entries if entry["name"].endswith(".kmz")]
        if files:
            break
    assert files, f"none of the first five {dataset} stations publishes a run"

    reader = KMLReader(station_ids=[station_id], settings=default_settings)
    served = set()
    for lead_time in lead_times:
        # which run does not matter -- the element set is a property of the product, not of the run
        runs = [file for file in files if f"_{lead_time}_" in file.rsplit("/", 1)[-1]]
        assert runs, f"{dataset} publishes no {lead_time} h run for station {station_id}"
        raw = reader.fetch(runs[0]).read()
        served |= {element.decode().lower() for element in re.findall(rb'elementName="([^"]+)"', raw)}

    declared = {parameter.name_original.lower() for parameter in DwdDmoRequest.metadata["hourly"][dataset]}

    assert not declared - served, f"{dataset} declares parameters no run carries: {sorted(declared - served)}"
    assert served - declared == without_a_canonical_name, (
        f"{dataset} serves elements it does not declare: {sorted(served - declared)}"
    )
