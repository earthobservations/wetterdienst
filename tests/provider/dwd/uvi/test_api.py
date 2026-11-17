# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the DWD UV index forecast provider (GH-4089).

`uvi.json` is a copy of DWD's file as served on 2026-11-17 (`forecast_day` 2026-11-17, written 07:30 local, 38 places).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from tests.provider.value_stubs import serve
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError
from wetterdienst.provider.dwd.metadata import EXTENT_GERMANY
from wetterdienst.provider.dwd.uvi import DwdUviMetadata, DwdUviRequest
from wetterdienst.provider.dwd.uvi import api as dwd_uvi_api
from wetterdienst.provider.dwd.uvi.api import read_forecast
from wetterdienst.provider.dwd.uvi.places import PLACES, PLACES_BY_NAME, slug
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

UTC = dt.UTC

FIXTURE = (Path(__file__).parent / "uvi.json").read_bytes()
DAY = dt.date(2026, 11, 17)
LAST_MODIFIED = dt.datetime(2026, 11, 17, 5, 31, 8, tzinfo=UTC)


def _file(document: dict[str, Any] | bytes) -> bytes:
    return document if isinstance(document, bytes) else json.dumps(document).encode()


def _fixture_document() -> dict[str, Any]:
    return json.loads(FIXTURE)


def _serve_file(monkeypatch: pytest.MonkeyPatch, content: bytes, *, status: int = 200) -> None:
    """Make the download of the provider answer with a file, dated as the server dates it."""
    monkeypatch.setattr(
        dwd_uvi_api,
        "download_file",
        lambda *_args, **_kwargs: File(
            url=dwd_uvi_api.URL, content=BytesIO(content), status=status, last_modified=LAST_MODIFIED
        ),
    )


def _request(*, drop_nulls: bool = True) -> DwdUviRequest:
    return DwdUviRequest(
        parameters=[("daily", "data")], settings=Settings(cache_disable=True), options=Options(drop_nulls=drop_nulls)
    )


def _values(monkeypatch: pytest.MonkeyPatch, content: bytes, *stations: str, drop_nulls: bool = True) -> Any:  # noqa: ANN401
    _serve_file(monkeypatch, content)
    request = _request(drop_nulls=drop_nulls)
    result = request.filter_by_station_id(list(stations)) if stations else request.all()
    return result.values().all()


# ---------------------------------------------------------------------------------------------------------------------
# the places
# ---------------------------------------------------------------------------------------------------------------------


def test_the_places_are_the_cities_of_the_file() -> None:
    """The table holds the 38 cities of a real file, and no other: a place DWD adds or drops shows here."""
    forecast = read_forecast(FIXTURE)
    assert len(PLACES) == 38
    assert {place.name for place in PLACES} == set(forecast.cities)


def test_a_station_id_is_the_slug_of_the_name() -> None:
    """The id is documented as the name's slug, and is unique and safe in a path and in a command line."""
    ids = [place.station_id for place in PLACES]
    assert len(set(ids)) == len(ids)
    for place in PLACES:
        assert place.station_id == slug(place.name)
        assert place.station_id.replace("-", "").isalnum()
        assert place.station_id.isascii()
        assert place.station_id == place.station_id.lower()
        assert not place.station_id.startswith("-")


@pytest.mark.parametrize(
    ("name", "station_id"),
    [
        ("Frankfurt/Main", "frankfurt-main"),
        ("Großer Arber", "grosser-arber"),
        ("Düsseldorf", "duesseldorf"),
        ("München", "muenchen"),
        ("Nürnberg", "nuernberg"),
        ("Osnabrück", "osnabrueck"),
        ("Würzburg", "wuerzburg"),
        ("List auf Sylt", "list-auf-sylt"),
        ("Sankt Peter-Ording", "sankt-peter-ording"),
        ("Zugspitze", "zugspitze"),
    ],
)
def test_the_slug_of_a_name(name: str, station_id: str) -> None:
    """The names with a umlaut, an eszett, a slash, a blank or a hyphen get the ids the documentation gives."""
    assert slug(name) == station_id
    assert PLACES_BY_NAME[name].station_id == station_id


def test_every_place_has_a_position_in_germany_and_a_source() -> None:
    """The position of a place is in the box of the network, and says where it is from."""
    west, south, east, north = EXTENT_GERMANY["bbox"]
    for place in PLACES:
        assert south <= place.latitude <= north, place.name
        assert west <= place.longitude <= east, place.name
        assert -10 <= place.elevation <= 3000, place.name
        assert place.source.startswith(("DWD ", "GeoNames ")), place.name


def test_the_summits_have_their_station_height() -> None:
    """The mountain places are at the height of the DWD station there, where the elevation matters most."""
    heights = {place.name: place.elevation for place in PLACES}
    assert heights["Zugspitze"] == 2956.0
    assert heights["Großer Arber"] == 1436.0
    assert heights["Kahler Asten"] == 839.0
    assert heights["Weinbiet"] == 553.0


def test_the_stations_are_listed_without_a_request() -> None:
    """The list of stations is the table, so it needs no download and is the same every time."""
    df = _request().all().df
    assert df.height == 38
    assert set(df["station_id"]) == {place.station_id for place in PLACES}
    zugspitze = df.filter(pl.col("station_id") == "zugspitze").row(0, named=True)
    assert zugspitze["name"] == "Zugspitze"
    assert zugspitze["latitude"] == pytest.approx(47.421)
    assert zugspitze["longitude"] == pytest.approx(10.9848)
    assert zugspitze["elevation"] == 2956.0
    assert (zugspitze["resolution"], zugspitze["dataset"]) == ("daily", "data")


def test_the_metadata_is_a_daily_forecast_of_one_parameter() -> None:
    """A forecast network with one daily dataset and the one parameter `uv_index_max`, dimensionless."""
    assert DwdUviMetadata.kind == "forecast"
    resolution = DwdUviMetadata[0]
    assert resolution.name == "daily"
    assert [period.value for period in resolution.periods] == ["future"]
    parameters = list(resolution.datasets[0].parameters)
    assert [parameter.name for parameter in parameters] == ["uv_index_max"]
    assert parameters[0].unit == "dimensionless"
    assert parameters[0].effective_timestamp_position == "start"


# ---------------------------------------------------------------------------------------------------------------------
# the file
# ---------------------------------------------------------------------------------------------------------------------


def test_read_forecast_gives_the_day_and_the_three_days_of_every_city() -> None:
    """`today` is `forecast_day`, and the three days of a city are kept as the file writes them."""
    forecast = read_forecast(FIXTURE)
    assert forecast.day == DAY
    assert len(forecast.cities) == 38
    expected = {entry["city"]: entry["forecast"] for entry in _fixture_document()["content"]}
    for city, days in forecast.cities.items():
        assert days == tuple(str(expected[city][key]) for key in ("today", "tomorrow", "dayafter_to"))


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        pytest.param(b"<html>maintenance</html>", "it is not JSON", id="html"),
        pytest.param(b"[]", "not a JSON object", id="a list"),
        pytest.param(json.dumps({"content": []}).encode(), "`forecast_day`", id="no forecast_day"),
        pytest.param(json.dumps({"forecast_day": "soon", "content": []}).encode(), "`forecast_day`", id="bad day"),
        pytest.param(json.dumps({"forecast_day": "2026-11-17"}).encode(), "`content`", id="no content"),
        pytest.param(json.dumps({"forecast_day": "2026-11-17", "content": []}).encode(), "`content`", id="no place"),
        pytest.param(
            json.dumps({"forecast_day": "2026-11-17", "content": [{"city": "Bonn"}]}).encode(),
            "no `city` or no `forecast`",
            id="no forecast",
        ),
        pytest.param(
            json.dumps(
                {"forecast_day": "2026-11-17", "content": [{"city": "Bonn", "forecast": {"today": 1, "tomorrow": 1}}]}
            ).encode(),
            "no dayafter_to",
            id="a day is missing",
        ),
        pytest.param(
            json.dumps(
                {
                    "forecast_day": "2026-11-17",
                    "content": [
                        {"city": "Bonn", "forecast": {"today": 1, "tomorrow": 1, "dayafter_to": 1}},
                        {"city": "Bonn", "forecast": {"today": 2, "tomorrow": 2, "dayafter_to": 2}},
                    ],
                }
            ).encode(),
            "Bonn is listed twice",
            id="a city twice",
        ),
    ],
)
def test_a_file_that_is_not_the_described_one_is_a_download_error(content: bytes, reason: str) -> None:
    """A changed layout is an upstream fault that is raised and says what is wrong, never an answer without rows."""
    with pytest.raises(DownloadError, match=reason) as error:
        read_forecast(content)
    assert dwd_uvi_api.URL in str(error.value)


def test_a_changed_layout_is_raised_by_the_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """The values of a request raise it as well: the file is the one source of the network."""
    _serve_file(monkeypatch, b"<html>maintenance</html>")
    with pytest.raises(DownloadError, match="it is not JSON"):
        _request().filter_by_station_id(["bonn"]).values().all()


# ---------------------------------------------------------------------------------------------------------------------
# the values
# ---------------------------------------------------------------------------------------------------------------------


def test_the_values_of_a_place_are_stamped_at_the_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    """`today`, `tomorrow` and `dayafter_to` are the dates of `forecast_day`, at 00:00 UTC, in the long form."""
    result = _values(monkeypatch, FIXTURE, "kassel")
    df = result.df.sort("timestamp")
    document = {entry["city"]: entry["forecast"] for entry in _fixture_document()["content"]}["Kassel"]
    assert df.columns == ["station_id", "resolution", "dataset", "parameter", "timestamp", "value", "quality_flags"]
    assert df["station_id"].unique().to_list() == ["kassel"]
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["parameter"].unique().to_list() == ["uv_index_max"]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")
    assert df["timestamp"].to_list() == [
        dt.datetime(2026, 11, 17, tzinfo=UTC),
        dt.datetime(2026, 11, 18, tzinfo=UTC),
        dt.datetime(2026, 11, 19, tzinfo=UTC),
    ]
    assert df["value"].to_list() == [float(document[key]) for key in ("today", "tomorrow", "dayafter_to")]
    assert df["quality_flags"].to_list() == [None, None, None]


def test_the_whole_network_is_114_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """38 places and three days, each with a value, from the one file."""
    df = _values(monkeypatch, FIXTURE).df
    assert df.height == 38 * 3
    assert df["station_id"].n_unique() == 38
    assert df["value"].min() >= 0


def test_the_file_is_read_once_for_all_the_stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """One file holds every place, so a request for 38 stations downloads it once."""
    calls: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        calls.append(url or args[0])
        return File(url=dwd_uvi_api.URL, content=BytesIO(FIXTURE), status=200)

    monkeypatch.setattr(dwd_uvi_api, "download_file", download_file)
    _request().all().values().all()
    assert calls == [dwd_uvi_api.URL]


def test_the_date_of_the_file_is_the_date_of_the_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """A forecast has no issue, so the answer is dated by the file the server last wrote (`data_updated_at`)."""
    result = _values(monkeypatch, FIXTURE, "hamburg")
    assert result.data_updated_at == LAST_MODIFIED


def test_the_days_follow_the_day_of_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stamps are those of `forecast_day`, whatever the day of the request: a month later is a month later."""
    document = _fixture_document()
    document["forecast_day"] = "2026-12-31"
    result = _values(monkeypatch, _file(document), "bonn")
    assert result.df.sort("timestamp")["timestamp"].to_list() == [
        dt.datetime(2026, 12, 31, tzinfo=UTC),
        dt.datetime(2027, 1, 1, tzinfo=UTC),
        dt.datetime(2027, 1, 2, tzinfo=UTC),
    ]


def test_a_window_cuts_the_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """A start and an end of the request select among the three days."""
    _serve_file(monkeypatch, FIXTURE)
    request = DwdUviRequest(
        parameters=[("daily", "data")],
        start=dt.datetime(2026, 11, 18, tzinfo=UTC),
        end=dt.datetime(2026, 11, 18, tzinfo=UTC),
        settings=Settings(cache_disable=True),
    )
    df = request.filter_by_station_id(["zugspitze"]).values().all().df
    assert df["timestamp"].to_list() == [dt.datetime(2026, 11, 18, tzinfo=UTC)]


def test_a_text_that_is_no_number_is_no_value_and_is_kept_as_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    """A day the file does not give as a number is null with the text it wrote as `raw:`, never a made-up number.

    DWD describes no marker for a day without a forecast, so the text here (`---`, as `dwd/poi` writes a missing
    value) is the stub's own wording; a JSON null is none and has no text to keep.
    """
    document = _fixture_document()
    for entry in document["content"]:
        if entry["city"] == "Bonn":
            entry["forecast"] = {"today": "---", "tomorrow": None, "dayafter_to": 3}
    df = _values(monkeypatch, _file(document), "bonn", drop_nulls=False).df.sort("timestamp")
    assert df["value"].to_list() == [None, None, 3.0]
    assert df["quality_flags"].to_list() == ["raw:---", None, None]


def test_a_value_beyond_the_scale_is_flagged_and_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """A forecast network judges soft: 99 is no UV index, and stays, marked `suspect:range` (0 to 25 is the range)."""
    document = _fixture_document()
    for entry in document["content"]:
        if entry["city"] == "Bonn":
            entry["forecast"] = {"today": 99, "tomorrow": 11, "dayafter_to": 0}
    df = _values(monkeypatch, _file(document), "bonn").df.sort("timestamp")
    assert df["value"].to_list() == [99.0, 11.0, 0.0]
    assert df["quality_flags"].to_list() == ["suspect:range", None, None]


# ---------------------------------------------------------------------------------------------------------------------
# a city that is not in the table, a place that is not in the file, a file that is not served
# ---------------------------------------------------------------------------------------------------------------------


def test_a_city_of_the_file_that_is_not_in_the_table_is_skipped_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """DWD adds a place: it is named in the warning, once, and every place of the table is answered as before."""
    document = _fixture_document()
    document["content"].append({"city": "Atlantis", "forecast": {"today": 9, "tomorrow": 9, "dayafter_to": 9}})
    document["content"].append({"city": "Lindau", "forecast": {"today": 1, "tomorrow": 1, "dayafter_to": 1}})
    with caplog.at_level(logging.WARNING, logger=dwd_uvi_api.__name__):
        df = _values(monkeypatch, _file(document)).df
    assert df.height == 38 * 3
    assert set(df["station_id"]) == {place.station_id for place in PLACES}
    warnings = [record.getMessage() for record in caplog.records if "no position here" in record.getMessage()]
    assert len(warnings) == 1
    assert "2 place(s)" in warnings[0]
    assert "Atlantis" in warnings[0]
    assert "Lindau" in warnings[0]


def test_a_place_of_the_table_that_the_file_does_not_hold_is_told(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """DWD drops or renames a place: it has no values, the warning names it, and the others are answered."""
    document = _fixture_document()
    document["content"] = [entry for entry in document["content"] if entry["city"] != "Zugspitze"]
    begin_response()
    with caplog.at_level(logging.WARNING, logger=dwd_uvi_api.__name__):
        result = _values(monkeypatch, _file(document))
    assert result.df.height == 37 * 3
    assert "zugspitze" not in set(result.df["station_id"])
    assert any("zugspitze" in record.getMessage() for record in caplog.records)
    (skipped,) = [warning for warning in recorded_warnings() if warning["code"] == "file-skipped"]
    assert skipped["stations"] == ["zugspitze"]


@pytest.mark.parametrize(
    ("content", "status"),
    [
        pytest.param(OSError("gone"), 404, id="withdrawn"),
        pytest.param(b"", 200, id="empty"),
    ],
)
def test_a_file_that_is_not_there_is_a_warning_and_no_rows(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, content: object, status: int
) -> None:
    """A withdrawn or an empty file is no answer: it is told in the log and as `file-skipped`, never silent."""
    body = content if isinstance(content, Exception) else BytesIO(content)  # ty: ignore[invalid-argument-type]
    monkeypatch.setattr(
        dwd_uvi_api,
        "download_file",
        lambda *_args, **_kwargs: File(url=dwd_uvi_api.URL, content=body, status=status),
    )
    begin_response()
    with caplog.at_level(logging.WARNING, logger=dwd_uvi_api.__name__):
        result = _request().filter_by_station_id(["bonn"]).values().all()
    assert result.df.is_empty()
    assert any(dwd_uvi_api.URL in record.getMessage() for record in caplog.records)
    assert "file-skipped" in {warning["code"] for warning in recorded_warnings()}


def test_an_outage_is_raised_and_not_read_as_no_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    """A server error is a `DownloadError`, which swallowed would read as a day without a forecast (GH-2461)."""
    monkeypatch.setattr(
        dwd_uvi_api,
        "download_file",
        lambda *_args, **_kwargs: File(url=dwd_uvi_api.URL, content=OSError("reset"), status=503),
    )
    with pytest.raises(DownloadError):
        _request().filter_by_station_id(["bonn"]).values().all()


def test_the_value_stub_serves_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared `serve` helper of the stubs reaches the provider's download as well."""
    serve(monkeypatch, dwd_uvi_api, {"uvi.json": FIXTURE})
    df = _request().filter_by_station_id(["zugspitze"]).values().all().df
    assert df.height == 3


# ---------------------------------------------------------------------------------------------------------------------
# remote
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.remote
def test_dwd_uvi_live() -> None:
    """The live file holds the 38 places of the table and a forecast for today, tomorrow and the day after.

    Live by design, not guarded by an xfail: a place DWD renames or adds, or a layout it changes, is what this is for.
    """
    request = DwdUviRequest(parameters=[("daily", "data")])
    result = request.all().values().all()
    df = result.df
    assert df["station_id"].n_unique() == 38
    assert df.height == 38 * 3
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")
    days = sorted(df["timestamp"].unique().to_list())
    assert len(days) == 3
    assert days[1] - days[0] == dt.timedelta(days=1)
    assert days[2] - days[1] == dt.timedelta(days=1)
    # the file is written every morning: its first day is today or, before the update, yesterday
    today = dt.datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    assert today - dt.timedelta(days=2) <= days[0] <= today + dt.timedelta(days=1)
    assert 0 <= df["value"].min() <= df["value"].max() <= 25
    assert not any("suspect" in (flags or "") for flags in df["quality_flags"])
    assert result.data_updated_at is not None
    assert dt.datetime.now(tz=UTC) - result.data_updated_at < dt.timedelta(days=3)
