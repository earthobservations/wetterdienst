# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD MOSMIX."""

import datetime as dt
import logging
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest

UTC = ZoneInfo("UTC")


@pytest.mark.remote
def test_dwd_mosmix_l(settings_humanize_false_drop_nulls_false: Settings) -> None:
    """Test some details of a typical MOSMIX-L response."""
    request = DwdMosmixRequest(
        parameters=[("hourly", "large")],
        settings=settings_humanize_false_drop_nulls_false,
    ).filter_by_station_id(
        station_id=["01001"],
    )
    response = next(request.values.query())

    # Verify list of stations.
    station_names = response.stations.df.get_column("name").unique().to_list()
    assert station_names == ["JAN MAYEN"]

    # Verify mosmix data.
    station_ids = response.df.get_column("station_id").unique().to_list()
    assert station_ids == ["01001"]
    assert len(response.df) > 200

    assert response.df_stations.get_column("station_id").to_list() == ["01001"]

    assert len(response.df.columns) == 7
    assert list(response.df.columns) == [
        "station_id",
        "resolution",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]

    assert set(response.df["parameter"]).issuperset(
        [
            "pppp",
            "e_ppp",
            "tx",
            "ttt",
            "e_ttt",
            "td",
            "e_td",
            "tn",
            "tg",
            "tm",
            "t5cm",
            "dd",
            "e_dd",
            "ff",
            "e_ff",
            "fx1",
            "fx3",
            "fx625",
            "fx640",
            "fx655",
            "fxh",
            "fxh25",
            "fxh40",
            "fxh55",
            "n",
            "neff",
            "nlm",
            "nh",
            "nm",
            "nl",
            "n05",
            "vv",
            "vv10",
            "wwm",
            "wwm6",
            "wwmh",
            "wwmd",
            "ww",
            "ww3",
            "w1w2",
            "wwp",
            "wwp6",
            "wwph",
            "wwpd",
            "wwz",
            "wwz6",
            "wwzh",
            "wwd",
            "wwd6",
            "wwdh",
            "wwc",
            "wwc6",
            "wwch",
            "wwt",
            "wwt6",
            "wwth",
            "wwtd",
            "wws",
            "wws6",
            "wwsh",
            "wwl",
            "wwl6",
            "wwlh",
            "wwf",
            "wwf6",
            "wwfh",
            "drr1",
            "rr6c",
            "rrhc",
            "rrdc",
            "rr1c",
            "rrs1c",
            "rrl1c",
            "rr3c",
            "rrs3c",
            "r101",
            "r102",
            "r103",
            "r105",
            "r107",
            "r110",
            "r120",
            "r130",
            "r150",
            "rr1o1",
            "rr1w1",
            "rr1u1",
            "r600",
            "r602",
            "r610",
            "r650",
            "rh00",
            "rh02",
            "rh10",
            "rh50",
            "rd00",
            "rd02",
            "rd10",
            "rd50",
            "sund",
            "rsund",
            "psd00",
            "psd30",
            "psd60",
            "rrad1",
            "rad1h",
            "sund1",
            "sund3",
            "pevap",
            "wpc11",
            "wpc31",
            "wpc61",
            "wpch1",
            "wpcd1",
        ],
    )


@pytest.mark.remote
@pytest.mark.slow
def test_dwd_mosmix_s(settings_humanize_false_drop_nulls_false: Settings) -> None:
    """Test some details of a typical MOSMIX-S response."""
    request = DwdMosmixRequest(
        parameters=[("hourly", "small")],
        settings=settings_humanize_false_drop_nulls_false,
    ).filter_by_station_id(
        station_id=["01028"],
    )
    response = next(request.values.query())
    # Verify list of stations.
    station_names = response.stations.df.get_column("name").unique().to_list()
    assert station_names == ["BJORNOYA"]
    # Verify mosmix data.
    station_ids = response.df.get_column("station_id").unique().to_list()
    assert station_ids == ["01028"]
    assert len(response.df) > 200
    assert len(response.df.columns) == 7
    assert list(response.df.columns) == [
        "station_id",
        "resolution",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]
    assert set(response.df["parameter"]).issuperset(
        [
            "pppp",
            "tx",
            "ttt",
            "td",
            "tn",
            "t5cm",
            "dd",
            "ff",
            "fx1",
            "fx3",
            "fxh",
            "fxh25",
            "fxh40",
            "fxh55",
            "n",
            "neff",
            "nh",
            "nm",
            "nl",
            "n05",
            "vv",
            "wwm",
            "wwm6",
            "wwmh",
            "ww",
            "w1w2",
            "rr1c",
            "rrs1c",
            "rr3c",
            "rrs3c",
            "r602",
            "r650",
            "rh00",
            "rh02",
            "rh10",
            "rh50",
            "rd02",
            "rd50",
            "rad1h",
            "sund1",
        ],
    )


@pytest.mark.remote
def test_mosmix_date_filter(settings_drop_nulls_false: Settings) -> None:
    """Test a MOSMIX request with date filter."""
    now = dt.datetime.now(tz=ZoneInfo("UTC"))
    request = DwdMosmixRequest(
        parameters=[("hourly", "small")],
        start_date=now - dt.timedelta(hours=1),
        end_date=now,
        issue=now - dt.timedelta(hours=5),
        settings=settings_drop_nulls_false,
    ).filter_by_rank(latlon=(52.122050, 11.619845), rank=1)
    given_df = request.values.all().df
    assert len(given_df) == 40


@pytest.mark.remote
def test_mosmix_l_parameters(settings_humanize_false_drop_nulls_false: Settings) -> None:
    """Test some details of a MOSMIX-L response when queried for specific parameters."""
    request = DwdMosmixRequest(
        parameters=[
            ("hourly", "large", "dd"),
            ("hourly", "large", "ww"),
        ],
        settings=settings_humanize_false_drop_nulls_false,
    ).filter_by_station_id(
        station_id=("01001", "123"),
    )
    response = next(request.values.query())
    # Verify mosmix data.
    station_ids = response.stations.df.get_column("station_id").unique().to_list()
    assert station_ids == ["01001"]
    assert len(response.df) > 200
    assert len(response.df.columns) == 7
    assert list(response.df.columns) == [
        "station_id",
        "resolution",
        "dataset",
        "parameter",
        "date",
        "value",
        "quality",
    ]
    assert set(response.df["parameter"]).issuperset(["dd", "ww"])


def test_mosmix_latest_answers_with_the_newest_run_the_listing_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """`LATEST` reads the newest named run, not the alias beside it.

    The two are the same bytes -- one ETag, one content-length, one Last-Modified for both -- but a
    run named by its timestamp is that run for good, where the alias is a name whose content DWD
    replaces every hour. Only the named one can be held, and `MOSMIX_S` is 36 MB.
    """
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [
            "https://example.com/kml/MOSMIX_L_2026092203_01001.kmz",
            "https://example.com/kml/MOSMIX_L_2026092209_01001.kmz",
            "https://example.com/kml/MOSMIX_L_LATEST_01001.kmz",
        ],
    )
    values = _stub_mosmix_stations().values

    resolved = values.get_url_for_date("https://example.com/kml/", api.DwdForecastDate.LATEST, one_station_only=True)

    assert resolved.rsplit("/", 1)[-1] == "MOSMIX_L_2026092209_01001.kmz"


def test_mosmix_latest_falls_back_to_the_alias_where_no_run_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """A listing naming no run has only the alias to go on, and it is held briefly for that reason."""
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: ["https://example.com/kml/MOSMIX_L_LATEST_01001.kmz"],
    )
    values = _stub_mosmix_stations().values

    resolved = values.get_url_for_date("https://example.com/kml/", api.DwdForecastDate.LATEST, one_station_only=True)

    assert resolved.rsplit("/", 1)[-1] == "MOSMIX_L_LATEST_01001.kmz"


def test_mosmix_latest_with_neither_a_run_nor_an_alias_says_which_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """A directory holding files, none of them a forecast, names itself.

    `next` raises `StopIteration` where its filter matches nothing, which the `except IndexError`
    guarding it never caught: raised inside `query()`'s generator that surfaced as `RuntimeError:
    generator raised StopIteration` (PEP 479), and called directly as a bare `StopIteration`.
    """
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: ["https://example.com/kml/README.txt"],
    )
    values = _stub_mosmix_stations().values

    with pytest.raises(IndexError, match="Unable to find LATEST file within"):
        values.get_url_for_date("https://example.com/kml/", api.DwdForecastDate.LATEST, one_station_only=True)


def test_mosmix_listing_entry_that_is_not_a_forecast_is_not_read_as_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A README beside the forecasts is a file this does not want, not `get index is out of bounds`.

    The date is read out of the third `_`-separated part of the name, and an entry carrying fewer
    than three raised `polars.exceptions.ComputeError` from the middle of the frame rather than the
    `IndexError` written for a date with no file.
    """
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    monkeypatch.setattr(
        api, "list_remote_files_fsspec", lambda *_args, **_kwargs: ["https://example.com/kml/README.txt"]
    )
    values = _stub_mosmix_stations().values

    with pytest.raises(IndexError, match=r"Unable to find 2026-09-01 09:00:00 file within"):
        values.get_url_for_date(
            "https://example.com/kml/",
            dt.datetime(2026, 9, 1, 9, tzinfo=UTC),
            one_station_only=True,
        )


def _stub_mosmix_stations() -> StationsResult:
    """Stand a MOSMIX station up rather than look one up, so the test needs no network."""
    request = DwdMosmixRequest(parameters=[("hourly", "large")])
    df_stations = pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "large",
                "station_id": "01001",
                "start_date": None,
                "end_date": None,
                "latitude": 70.93,
                "longitude": -8.67,
                "height": 10.0,
                "name": "JAN MAYEN",
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
    )


@pytest.mark.parametrize(
    "date",
    [
        pytest.param(dt.datetime(2026, 7, 31, 9, tzinfo=UTC), id="explicit-issue"),
        pytest.param("LATEST", id="latest"),
    ],
)
def test_mosmix_directory_holding_nothing_costs_that_station_and_no_more(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    date: dt.datetime | str,
) -> None:
    """A station whose directory DWD emptied answers with nothing, rather than ending the request.

    Nothing between `get_url_for_date` and `values.all()` catches, so one such station used to take
    the other forty-nine of a fifty-station request with it. `dwd/dmo` has always made this split;
    mosmix raised because its return type said it must.

    The listing is not proof either way -- `fs.find` walks with `on_error="omit"`, so a failed walk
    and a 404 both arrive looking like an empty directory -- which is why this is warned about
    rather than passed over.
    """
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])
    values = _stub_mosmix_stations().values
    asked = api.DwdForecastDate.LATEST if date == "LATEST" else date

    assert values.get_url_for_date("https://example.com/kml/", asked, one_station_only=True) is None
    assert "a listing that failed looks the same" in caplog.text


@pytest.mark.parametrize(
    ("listing", "asked", "expected"),
    [
        pytest.param(
            ["MOSMIX_L_2026092203_01001.kmz", "MOSMIX_L_LATEST_01001.kmz"],
            dt.datetime(2026, 9, 22, 3, tzinfo=UTC),
            "MOSMIX_L_2026092203_01001.kmz",
            id="one-station",
        ),
        pytest.param(
            # no station id in the name, so the third `_`-part carried the extension and the alias
            # read as `LATEST.kmz`, which the filter written to drop `LATEST` did not match
            ["MOSMIX_L_2026092203.kmz", "MOSMIX_L_LATEST.kmz"],
            dt.datetime(2026, 9, 22, 3, tzinfo=UTC),
            "MOSMIX_L_2026092203.kmz",
            id="all-stations",
        ),
        pytest.param(
            ["MOSMIX_S_2026092205_240.kmz", "MOSMIX_S_LATEST_240.kmz"],
            dt.datetime(2026, 9, 22, 5, tzinfo=UTC),
            "MOSMIX_S_2026092205_240.kmz",
            id="all-stations-s",
        ),
        pytest.param(
            # were DWD ever to publish both forms, the readable one is the answer:
            # `KMLReader.fetch` hands every download to `ZipFileSystem`, which raises `BadZipFile`
            # on a plain KML, so a rule that accepted `.kml` would resolve to a file that cannot
            # be opened
            ["MOSMIX_L_2026092203_01001.kmz", "MOSMIX_L_2026092203_01001.kml"],
            dt.datetime(2026, 9, 22, 3, tzinfo=UTC),
            "MOSMIX_L_2026092203_01001.kmz",
            id="a-run-published-in-both-forms",
        ),
    ],
)
def test_mosmix_reads_the_run_out_of_every_naming_layout(
    monkeypatch: pytest.MonkeyPatch,
    listing: list[str],
    asked: dt.datetime,
    expected: str,
) -> None:
    """DWD names a run three ways, and only one of them was read.

    Taking the third `_`-separated part of the name read the all-stations layouts as
    ``2026092203.kmz``, extension and all, and their alias as ``LATEST.kmz`` -- which the filter
    dropping ``LATEST`` does not match, so every row met `conversion from str to datetime failed`
    and the layout could not be asked for a run at all. The ten digits DWD stamps a run with are
    the one thing all three share.
    """
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [f"https://example.com/kml/{name}" for name in listing],
    )

    resolved = _stub_mosmix_stations().values.get_url_for_date("https://example.com/kml/", asked, one_station_only=True)

    assert resolved.rsplit("/", 1)[-1] == expected


@pytest.mark.parametrize(
    ("listing", "expected"),
    [
        pytest.param(["MOSMIX_L_LATEST_01001.kmz"], "MOSMIX_L_LATEST_01001.kmz", id="one-station"),
        pytest.param(["MOSMIX_L_LATEST.kmz"], "MOSMIX_L_LATEST.kmz", id="all-stations"),
        pytest.param(
            # the checksum sorts after the forecast today, so what kept it from being answered
            # with was the listing's order rather than any rule
            ["MOSMIX_L_LATEST_01001.kmz.sha256", "MOSMIX_L_LATEST_01001.kmz"],
            "MOSMIX_L_LATEST_01001.kmz",
            id="a-sidecar-beside-the-alias",
        ),
        pytest.param(
            # and the default path likewise answers with the form the reader can open
            ["MOSMIX_L_LATEST_01001.kmz", "MOSMIX_L_LATEST_01001.kml"],
            "MOSMIX_L_LATEST_01001.kmz",
            id="an-alias-in-both-forms",
        ),
        pytest.param(
            # two alias forms, which a second lead time would give -- `dwd/dmo` already publishes
            # two. Every path takes the last of the sort, so asking for the newest run and asking
            # for a run by name cannot answer with different files
            ["MOSMIX_S_LATEST_120.kmz", "MOSMIX_S_LATEST_240.kmz"],
            "MOSMIX_S_LATEST_240.kmz",
            id="two-alias-lead-times",
        ),
    ],
)
def test_mosmix_latest_answers_with_a_forecast_and_not_with_what_sits_beside_it(
    monkeypatch: pytest.MonkeyPatch,
    listing: list[str],
    expected: str,
) -> None:
    """The alias is held to the rule a dated run is held to, on the path a caller reaches by default."""
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [f"https://example.com/kml/{name}" for name in listing],
    )

    resolved = _stub_mosmix_stations().values.get_url_for_date(
        "https://example.com/kml/", api.DwdForecastDate.LATEST, one_station_only=True
    )

    assert resolved.rsplit("/", 1)[-1] == expected


@pytest.mark.parametrize(
    ("listing", "expected"),
    [
        pytest.param([], [], id="directory-holding-nothing"),
        pytest.param(["https://example.com/kml/README.txt"], [], id="nothing-that-is-a-forecast"),
        pytest.param(
            # a companion carrying the run stamp is not the forecast, and two rows matching one run
            # would raise `ValueError: can only call '.item()' if the Series is of length 1` out of
            # the `.item()` that answers with the URL
            ["https://example.com/kml/MOSMIX_L_2026092203_01001.kmz.sha256"],
            [],
            id="a-sidecar-carrying-the-run-stamp",
        ),
        pytest.param(
            [
                "https://example.com/kml/MOSMIX_L_2026092203_01001.kmz",
                "https://example.com/kml/MOSMIX_L_LATEST_01001.kmz",
            ],
            [dt.datetime(2026, 9, 22, 3, tzinfo=UTC)],
            id="one-run-and-its-alias",
        ),
    ],
)
def test_mosmix_available_issues_answers_rather_than_raises(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    listing: list[str],
    expected: list[dt.datetime],
) -> None:
    """`available_issues` carried the same faults one method down, where `history` reaches them.

    An empty directory raised `invalid series dtype: expected String, got null` and a non-forecast
    entry `get index is out of bounds`, where "which runs exist?" has an answer in both cases: none.
    Reached by a station whose directory DWD has emptied or retired, a missing path being answered
    with no entries rather than an error.
    """
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: listing)

    assert DwdMosmixRequest.available_issues("01001", Settings()) == expected
    # a listing that came back empty is also what a listing that failed looks like: `fs.find`
    # walks with `on_error="omit"` and aiohttp's `ClientOSError` is an `OSError`, so answering
    # "no runs" without saying so turns a blip into a fact about the station
    assert ("a listing that failed looks the same" in caplog.text) is (listing == [])
    # and a listing that named things, none of which is a forecast, is the same misreading one
    # step later: that is what a renaming upstream looks like, not a station without runs
    named_nothing_usable = listing != [] and expected == []
    assert ("No dated run listed within" in caplog.text) is named_nothing_usable


@pytest.mark.parametrize(
    ("listing", "expected_aliases"),
    [
        pytest.param(["MOSMIX_L_LATEST_01001.kmz"], 1, id="alias-only"),
        pytest.param(
            # the moment a checksum sits beside the alias, "every entry is an alias" stops being
            # true, and a rule written that way names a renaming that has not happened
            ["MOSMIX_L_LATEST_01001.kmz", "MOSMIX_L_LATEST_01001.kmz.sha256"],
            1,
            id="alias-and-a-sidecar",
        ),
        pytest.param(["README.txt"], 0, id="nothing-that-is-either"),
    ],
)
def test_mosmix_available_issues_counts_rather_than_diagnoses(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    listing: list[str],
    expected_aliases: int,
) -> None:
    """A directory with no dated run is reported by what is in it, not by a guess at why.

    An alias is a forecast and only a dated run is what this lists, so a directory pruned back to
    its alias is not the renaming this warning otherwise means. Saying so required "every entry is
    an alias", which a checksum beside the alias makes false -- so the counts are reported and the
    cause is left to the reader.
    """
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [f"https://example.com/kml/{name}" for name in listing],
    )

    assert DwdMosmixRequest.available_issues("01001", Settings()) == []
    assert f"({len(listing)} entries, {expected_aliases} of them the LATEST alias)" in caplog.text
    assert "No dated run listed within" in caplog.text


def test_mosmix_one_emptied_directory_does_not_cost_the_other_stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """The point of returning None: a request for several stations survives one of them going quiet."""
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    def listing(url: str, *_args: object, **_kwargs: object) -> list[str]:
        # 01001's directory has been emptied; 01002's still publishes
        return [] if "01001" in url else [f"{url}MOSMIX_L_2026092209_01002.kmz"]

    monkeypatch.setattr(api, "list_remote_files_fsspec", listing)
    read: list[str] = []
    monkeypatch.setattr(api.KMLReader, "read", lambda _self, url: read.append(url))
    monkeypatch.setattr(api.KMLReader, "get_station_forecast", lambda _self, _station_id: pl.DataFrame({"x": [1]}))

    values = _stub_mosmix_stations().values
    quiet = values.read_mosmix_large("01001", api.DwdForecastDate.LATEST)
    publishing = values.read_mosmix_large("01002", api.DwdForecastDate.LATEST)

    assert quiet.is_empty()
    assert not publishing.is_empty()
    assert read == [
        "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/01002/kml/MOSMIX_L_2026092209_01002.kmz"
    ]


@pytest.mark.parametrize(
    ("url", "expected_ttl"),
    [
        pytest.param("https://x/kml/MOSMIX_L_2026092209_01001.kmz", CacheExpiry.TWELVE_HOURS, id="a-named-run"),
        pytest.param("https://x/kml/MOSMIX_L_LATEST_01001.kmz", CacheExpiry.FIVE_MINUTES, id="the-alias"),
    ],
)
def test_mosmix_holds_a_named_run_longer_than_a_mutable_alias(url: str, expected_ttl: CacheExpiry) -> None:
    """How long a forecast may be held is a property of the URL, not of the reader.

    A run named by its timestamp is that run for good; a `LATEST` alias is a name whose content DWD
    replaces every hour. Holding everything briefly meant re-downloading `MOSMIX_S` -- 36 MB,
    published hourly -- up to twelve times an hour for a file that had not changed.
    """
    from wetterdienst.provider.dwd.mosmix.access import KMLReader  # noqa: PLC0415

    reader = KMLReader(station_ids=["01001"], settings=Settings())

    assert reader._filesystem_for(url) is reader._filesystems[expected_ttl]  # noqa: SLF001


def test_mosmix_a_cached_run_that_is_not_a_zip_is_dropped_and_asked_for_again(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A truncated blob under an immutable URL would otherwise fail for twelve hours.

    fsspec writes its cache metadata before the copy finishes -- `_make_local_details` records the
    entry and `get_file` fills it afterwards -- so a download interrupted mid-copy leaves a
    truncated blob that `_check_file` accepts for the life of the entry. Held five minutes that
    righted itself; held twelve hours, with `LATEST` resolving to that same immutable URL rather
    than to an alias, it would not.
    """
    import zipfile  # noqa: PLC0415
    from io import BytesIO  # noqa: PLC0415

    from wetterdienst.provider.dwd.mosmix.access import KMLReader  # noqa: PLC0415

    good = BytesIO()
    with zipfile.ZipFile(good, "w") as archive:
        archive.writestr("forecast.kml", "<kml/>")

    caplog.set_level(logging.WARNING)
    reader = KMLReader(station_ids=["01001"], settings=Settings())
    bodies = [BytesIO(b"not a zip at all"), BytesIO(good.getvalue())]
    dropped: list[str] = []
    monkeypatch.setattr(KMLReader, "download", lambda _self, _url: bodies.pop(0))
    monkeypatch.setattr(
        type(reader._filesystem_for("https://x/kml/MOSMIX_L_2026092209_01001.kmz")),  # noqa: SLF001
        "pop_from_cache",
        lambda _self, url: dropped.append(url),
    )

    handle = reader.fetch("https://x/kml/MOSMIX_L_2026092209_01001.kmz")

    assert handle.read() == b"<kml/>"
    assert dropped == ["https://x/kml/MOSMIX_L_2026092209_01001.kmz"]
    assert "is not a zip" in caplog.text


def test_mosmix_an_empty_all_stations_listing_is_not_a_quiet_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty listing means "this station retired" only where the directory is one station's.

    The all-stations products publish every station in one directory, so one empty listing there is
    every station at once: it means the listing failed or DWD moved the product, and `fs.find`
    swallowing an `OSError` makes those look identical to an empty directory. Answering `None`
    would turn a connection reset into an empty result for the whole request, exit 0 and HTTP 200.
    """
    from wetterdienst.provider.dwd.mosmix import api  # noqa: PLC0415

    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])
    values = _stub_mosmix_stations().values

    # one station's directory: an answer
    assert (
        values.get_url_for_date("https://example.com/kml/", api.DwdForecastDate.LATEST, one_station_only=True) is None
    )
    # the product's directory: not an answer
    with pytest.raises(IndexError, match="a listing that failed looks the same"):
        values.get_url_for_date("https://example.com/kml/", api.DwdForecastDate.LATEST, one_station_only=False)


@pytest.mark.parametrize(
    ("url", "expected_ttl"),
    [
        pytest.param("https://x/kmz/ptp_gdmog_01001_078_1_230000.kmz", CacheExpiry.TWELVE_HOURS, id="a-dmo-run"),
        pytest.param("https://x/kml/MOSMIX_L_2026092209_01001.kmz", CacheExpiry.TWELVE_HOURS, id="a-mosmix-run"),
        pytest.param("https://x/kml/MOSMIX_L_LATEST_01001.kmz", CacheExpiry.FIVE_MINUTES, id="the-mosmix-alias"),
    ],
)
def test_the_kml_reader_holds_dmo_by_the_same_rule_as_mosmix(url: str, expected_ttl: CacheExpiry) -> None:
    """`dwd/dmo` reads through this class too, so its downloads move with mosmix's.

    DMO names carry the same kind of immutable run stamp and none of them says `LATEST`, so every
    DMO file takes the long hold. Worth pinning rather than inferring, since the change was made
    for mosmix and DMO keeps only a handful of runs -- a blob there can outlive the file upstream.
    """
    from wetterdienst.provider.dwd.mosmix.access import KMLReader  # noqa: PLC0415

    reader = KMLReader(station_ids=["01001"], settings=Settings())

    assert reader._filesystem_for(url) is reader._filesystems[expected_ttl]  # noqa: SLF001


def test_a_run_that_is_not_a_zip_without_a_cache_is_not_asked_for_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    """With nothing held there is nothing to drop, and nothing a second request would answer.

    For MOSMIX-S that second request is another 36 MB spent to meet the same `BadZipFile`.
    """
    from zipfile import BadZipFile  # noqa: PLC0415

    from fsspec.implementations.http import HTTPFileSystem  # noqa: PLC0415

    from wetterdienst.provider.dwd.mosmix.access import KMLReader  # noqa: PLC0415

    reader = KMLReader(station_ids=["01001"], settings=Settings())
    downloads: list[str] = []
    monkeypatch.setattr(
        KMLReader,
        "download",
        lambda _self, url: downloads.append(url) or BytesIO(b"an upstream error page, not a zip"),
    )
    # a plain filesystem, which is what `cache_disable` produces -- named directly here because
    # `cache_disable` is not part of the registry key on this branch (GH-1947), so asking for one
    # by settings can hand back a caching filesystem an earlier test registered
    monkeypatch.setattr(KMLReader, "_filesystem_for", lambda _self, _url: HTTPFileSystem())

    with pytest.raises(BadZipFile):
        reader.fetch("https://x/kml/MOSMIX_L_2026092209_01001.kmz")

    assert len(downloads) == 1
