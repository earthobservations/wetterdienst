# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the DWD pollen forecast provider (GH-4088).

`s31fg.json` is a copy of DWD's file as served on 2026-11-17 (`last_update` 2026-11-17 11:00 Uhr, 27 regions; every
level was `0`, as it is in November, so the tests that need the other steps write them into a copy).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import polars as pl
import pytest
from aiohttp import ClientResponseError

from tests.provider.value_stubs import serve
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError, LocationOutOfRangeError, ProviderRateLimitError
from wetterdienst.provider.dwd.metadata import EXTENT_GERMANY
from wetterdienst.provider.dwd.pollen import DwdPollenMetadata, DwdPollenRequest
from wetterdienst.provider.dwd.pollen import api as dwd_pollen_api
from wetterdienst.provider.dwd.pollen.api import LEVELS, read_forecast
from wetterdienst.provider.dwd.pollen.metadata import POLLEN_TYPES
from wetterdienst.provider.dwd.pollen.regions import REGIONS, REGIONS_BY_ID, PollenRegion
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

UTC = dt.UTC

FIXTURE = (Path(__file__).parent / "s31fg.json").read_bytes()
DAY = dt.date(2026, 11, 17)
LAST_MODIFIED = dt.datetime(2026, 11, 17, 9, 58, 6, tzinfo=UTC)
DAYS = ("today", "tomorrow", "dayafter_to")


def _file(document: dict[str, Any] | bytes) -> bytes:
    return document if isinstance(document, bytes) else json.dumps(document).encode()


def _fixture_document() -> dict[str, Any]:
    return json.loads(FIXTURE)


def _with_levels(station_id: str, pollen: str, levels: tuple[Any, Any, Any]) -> bytes:
    """Give the file as served, with the three days of one pollen type of one region written as `levels`."""
    document = _fixture_document()
    region = REGIONS_BY_ID[station_id]
    for entry in document["content"]:
        if (entry["region_id"], entry["partregion_id"]) == (region.region_id, region.partregion_id):
            entry["Pollen"][pollen] = dict(zip(DAYS, levels, strict=True))
    return _file(document)


def _serve_file(monkeypatch: pytest.MonkeyPatch, content: bytes, *, status: int = 200) -> None:
    """Make the download of the provider answer with a file, dated as the server dates it."""
    monkeypatch.setattr(
        dwd_pollen_api,
        "download_file",
        lambda *_args, **_kwargs: File(
            url=dwd_pollen_api.URL, content=BytesIO(content), status=status, last_modified=LAST_MODIFIED
        ),
    )


def _request(*parameters: str, drop_nulls: bool = True) -> DwdPollenRequest:
    return DwdPollenRequest(
        parameters=[("daily", "data", name) for name in parameters] if parameters else [("daily", "data")],
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=drop_nulls),
    )


def _values(
    monkeypatch: pytest.MonkeyPatch, content: bytes, *stations: str, drop_nulls: bool = True, parameters: tuple = ()
) -> Any:  # noqa: ANN401
    _serve_file(monkeypatch, content)
    request = _request(*parameters, drop_nulls=drop_nulls)
    result = request.filter_by_station_id(list(stations)) if stations else request.all()
    return result.values().all()


# ---------------------------------------------------------------------------------------------------------------------
# the regions
# ---------------------------------------------------------------------------------------------------------------------


def test_the_regions_are_those_of_the_file() -> None:
    """The table holds the 27 regions of a real file, with its numbers and names, and no other."""
    document = _fixture_document()
    assert len(REGIONS) == 27
    in_the_file = {
        (entry["region_id"], entry["partregion_id"]): (entry["region_name"], entry["partregion_name"])
        for entry in document["content"]
    }
    in_the_table = {(r.region_id, r.partregion_id): (r.region_name, r.partregion_name) for r in REGIONS}
    assert in_the_table == in_the_file


def test_a_station_id_is_the_partregion_id_or_the_region_id() -> None:
    """The id is DWD's number: the part-region's, the region's where the file gives it `-1`; it is unique."""
    ids = [region.station_id for region in REGIONS]
    assert len(set(ids)) == len(ids) == 27
    for region in REGIONS:
        assert region.station_id == str(region.region_id if region.partregion_id == -1 else region.partregion_id)
    # the two regions without parts are stations by their own number, and every other region is none by its own
    assert {region.station_id for region in REGIONS if region.partregion_id == -1} == {"20", "50"}
    whole_regions = {str(region.region_id) for region in REGIONS if region.partregion_id != -1}
    assert not whole_regions & set(ids)


def test_a_station_is_named_by_its_region_and_part_region() -> None:
    """The name holds the region and the part-region, or the region alone where DWD gives it no parts."""
    by_id = {region.station_id: region.name for region in REGIONS}
    assert by_id["124"] == "Bayern: Mainfranken"
    assert by_id["11"] == "Schleswig-Holstein und Hamburg: Inseln und Marschen"
    assert by_id["20"] == "Mecklenburg-Vorpommern"
    assert by_id["50"] == "Brandenburg und Berlin"
    assert len(set(by_id.values())) == 27


def _part_name(region: PollenRegion) -> str:
    """Give what a user types for a region: its part-region's name, or the region's where DWD gives it no parts."""
    return region.region_name if region.partregion_id == -1 else region.partregion_name


@pytest.mark.parametrize(
    "region",
    [
        pytest.param(
            region,
            id=region.station_id,
            marks=pytest.mark.xfail(
                strict=True,
                reason="WRatio ranks 81 (`Sachsen: Tiefland Sachsen`) above 61, which holds the whole query; GH-4215",
            )
            if region.station_id == "61"
            else (),
        )
        for region in REGIONS
    ],
)
def test_a_part_region_is_found_by_its_own_name_alone(region: PollenRegion) -> None:
    """The parts of a region share its name as a prefix and tie in a match; the closer whole name wins (GH-4207).

    "Saarland" is 103 (not 101, the first part of the region), "Mainfranken" is 124 (not 123, the part without it).
    """
    found = _request().filter_by_name(_part_name(region), rank=1).df["station_id"].to_list()
    assert found == [region.station_id], f"{_part_name(region)!r} found {found}, not {region.station_id}"


def test_the_stations_are_listed_without_a_request_and_without_a_position(monkeypatch: pytest.MonkeyPatch) -> None:
    """The list is the table: no download, and DWD gives the regions no position, so it is null, never invented."""
    monkeypatch.setattr(dwd_pollen_api, "download_file", lambda *_a, **_k: pytest.fail("the list needs no download"))
    df = _request().all().df
    assert df.height == 27
    assert set(df["station_id"]) == {region.station_id for region in REGIONS}
    assert df["latitude"].null_count() == df["longitude"].null_count() == df["elevation"].null_count() == 27
    assert df.schema["latitude"] == pl.Float64
    row = df.filter(pl.col("station_id") == "124").row(0, named=True)
    assert row["name"] == "Bayern: Mainfranken"
    assert row["region"] == "Bayern"
    assert (row["resolution"], row["dataset"]) == ("daily", "data")


def test_the_regions_are_found_by_name_and_by_id() -> None:
    """A region is found by its name or its id; the best match of a name comes first."""
    request = _request()
    assert request.filter_by_name("Bayern: Mainfranken").df["station_id"].to_list() == ["124"]
    assert request.filter_by_name("Mecklenburg-Vorpommern").df["station_id"].to_list() == ["20"]
    found = request.filter_by_name("Harz", rank=5).df["station_id"].to_list()
    assert found[0] == "62"
    assert request.filter_by_station_id(["20", "124"]).df["station_id"].to_list() == ["20", "124"]
    assert request.filter_by_sql("region = 'Hessen'").df.height == 2


def test_a_search_by_place_finds_none_of_the_stations_and_is_no_error() -> None:
    """Without a position a station is in no box, no distance and no rank: the answer is empty, not a failure."""
    request = _request()
    assert request.filter_by_rank((50.0, 10.0), 5).df.is_empty()
    assert request.filter_by_distance((50.0, 10.0), 500).df.is_empty()
    assert request.filter_by_bbox(5.8, 47.2, 15.1, 55.1).df.is_empty()


def test_a_region_is_no_point_to_interpolate_or_summarize_at() -> None:
    """A station asked for as the point of an estimate has none, and says so as the core does for any such station."""
    with pytest.raises(LocationOutOfRangeError, match="has no position"):
        _request()._get_position_by_station_id("124")  # noqa: SLF001


def test_the_stations_are_geojson_features_without_a_geometry() -> None:
    """The OGC answer holds a feature with a null geometry (valid GeoJSON) for a station without a position."""
    collection = _request().filter_by_station_id(["124"]).to_ogc_feature_collection()
    (feature,) = collection["data"]["features"]
    assert feature["geometry"] is None
    assert feature["properties"]["id"] == "124"
    assert feature["properties"]["name"] == "Bayern: Mainfranken"


def test_the_metadata_is_a_daily_forecast_of_eight_parameters() -> None:
    """A forecast network with one daily dataset and a dimensionless parameter per pollen type."""
    assert DwdPollenMetadata.kind == "forecast"
    assert list(DwdPollenMetadata.extent.bbox) == EXTENT_GERMANY["bbox"]
    resolution = DwdPollenMetadata[0]
    assert resolution.name == "daily"
    assert [period.value for period in resolution.periods] == ["future"]
    parameters = list(resolution.datasets[0].parameters)
    assert {parameter.name_original: parameter.name for parameter in parameters} == {
        "Hasel": "pollen_load_hazel",
        "Erle": "pollen_load_alder",
        "Esche": "pollen_load_ash",
        "Birke": "pollen_load_birch",
        "Graeser": "pollen_load_grass",
        "Roggen": "pollen_load_rye",
        "Beifuss": "pollen_load_mugwort",
        "Ambrosia": "pollen_load_ragweed",
    }
    assert {parameter.unit for parameter in parameters} == {"dimensionless"}
    assert {parameter.effective_timestamp_position for parameter in parameters} == {"start"}
    assert set(POLLEN_TYPES) == {parameter.name_original for parameter in parameters}


# ---------------------------------------------------------------------------------------------------------------------
# the file
# ---------------------------------------------------------------------------------------------------------------------


def test_the_steps_are_those_of_the_legend() -> None:
    """The seven steps the reader knows are the seven the legend of the file names, as 0 to 3 in halves."""
    legend = _fixture_document()["legend"]
    steps = [legend[f"id{number}"] for number in range(1, 8)]
    assert steps == ["0", "0-1", "1", "1-2", "2", "2-3", "3"]
    assert list(LEVELS) == steps
    assert list(LEVELS.values()) == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def test_read_forecast_gives_the_day_and_the_three_days_of_every_pollen() -> None:
    """`today` is the date of `last_update`, and the three days of a pollen are kept as the file writes them."""
    forecast = read_forecast(FIXTURE)
    assert forecast.day == DAY
    assert len(forecast.regions) == 27
    assert forecast.unknown_pollen == ()
    assert forecast.names[(120, 124)] == "Bayern: Mainfranken"
    assert forecast.names[(20, -1)] == "Mecklenburg-Vorpommern"
    assert set(forecast.regions[(120, 124)]) == set(POLLEN_TYPES)
    assert forecast.regions[(120, 124)]["Birke"] == ("0", "0", "0")


def _entry(**changes: Any) -> dict[str, Any]:  # noqa: ANN401
    entry: dict[str, Any] = {
        "region_id": 20,
        "partregion_id": -1,
        "region_name": "Mecklenburg-Vorpommern",
        "partregion_name": "",
        "Pollen": {name: {"today": "0", "tomorrow": "0", "dayafter_to": "0"} for name in POLLEN_TYPES},
    }
    return entry | changes


def _document(*entries: dict[str, Any], **changes: Any) -> bytes:  # noqa: ANN401
    return json.dumps({"last_update": "2026-11-17 11:00 Uhr", "content": list(entries)} | changes).encode()


def _without_a_day(entry: dict[str, Any]) -> dict[str, Any]:
    pollen = json.loads(json.dumps(entry["Pollen"]))
    del pollen["Birke"]["tomorrow"]
    return entry | {"Pollen": pollen}


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        pytest.param(b"<html>maintenance</html>", "it is not JSON", id="html"),
        pytest.param(b"[]", "not a JSON object", id="a list"),
        pytest.param(_document(_entry(), last_update=None), "`last_update`", id="no date"),
        pytest.param(_document(_entry(), last_update="soon"), "`last_update`", id="bad date"),
        pytest.param(_document(_entry(), last_update="2026-13-45 11:00 Uhr"), "`last_update`", id="impossible date"),
        pytest.param(json.dumps({"last_update": "2026-11-17 11:00 Uhr"}).encode(), "`content`", id="no content"),
        pytest.param(_document(), "`content`", id="no region"),
        pytest.param(_document("a region"), "no object", id="a region that is no object"),  # ty: ignore[invalid-argument-type]
        pytest.param(_document(_entry(region_id="20")), "whole number `region_id`", id="a region id that is text"),
        pytest.param(_document(_entry(partregion_id=None)), "whole number `partregion_id`", id="no part-region id"),
        pytest.param(_document(_entry(Pollen=[])), "has no `Pollen`", id="no pollen"),
        pytest.param(_document(_entry(Pollen={"Hasel": "0"})), "is no object", id="a pollen that is no object"),
        pytest.param(_document(_without_a_day(_entry())), "has no tomorrow", id="a day is missing"),
        pytest.param(_document(_entry(), _entry()), "is listed twice", id="a region twice"),
    ],
)
def test_a_file_that_is_not_the_described_one_is_a_download_error(content: bytes, reason: str) -> None:
    """A changed layout is an upstream fault that is raised and says what is wrong, never an answer without rows."""
    with pytest.raises(DownloadError, match=reason) as error:
        read_forecast(content)
    assert dwd_pollen_api.URL in str(error.value)


def test_a_changed_layout_is_raised_by_the_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """The values of a request raise it as well: the file is the one source of the network."""
    _serve_file(monkeypatch, b"<html>maintenance</html>")
    with pytest.raises(DownloadError, match="it is not JSON"):
        _request().filter_by_station_id(["124"]).values().all()


# ---------------------------------------------------------------------------------------------------------------------
# the values
# ---------------------------------------------------------------------------------------------------------------------


def test_the_values_of_a_region_are_stamped_at_the_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    """`today`, `tomorrow` and `dayafter_to` are the dates of `last_update`, at 00:00 UTC, in the long form."""
    df = _values(monkeypatch, FIXTURE, "124").df.sort("parameter", "timestamp")
    assert df.columns == ["station_id", "resolution", "dataset", "parameter", "timestamp", "value", "quality_flags"]
    assert df["station_id"].unique().to_list() == ["124"]
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["dataset"].unique().to_list() == ["data"]
    assert df["parameter"].unique().sort().to_list() == sorted(POLLEN_TYPES.values())
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")
    assert df.filter(pl.col("parameter") == "pollen_load_birch")["timestamp"].to_list() == [
        dt.datetime(2026, 11, 17, tzinfo=UTC),
        dt.datetime(2026, 11, 18, tzinfo=UTC),
        dt.datetime(2026, 11, 19, tzinfo=UTC),
    ]
    assert df.height == 8 * 3
    assert df["value"].to_list() == [0.0] * 24
    assert df["quality_flags"].null_count() == 24


@pytest.mark.parametrize(("step", "value"), list(LEVELS.items()))
def test_every_step_is_its_number_and_each_day_its_own(
    monkeypatch: pytest.MonkeyPatch, step: str, value: float
) -> None:
    """Each of the seven steps is served as its number, on the day of its key and for its pollen only."""
    content = _with_levels("62", "Birke", (step, "0", step))
    df = _values(monkeypatch, content, "62").df
    birch = df.filter(pl.col("parameter") == "pollen_load_birch").sort("timestamp")
    assert birch["value"].to_list() == [value, 0.0, value]
    assert birch["quality_flags"].null_count() == 3
    assert df.filter(pl.col("parameter") != "pollen_load_birch")["value"].to_list() == [0.0] * 21


def test_the_days_are_kept_apart(monkeypatch: pytest.MonkeyPatch) -> None:
    """`today`, `tomorrow` and `dayafter_to` are three different days, not three readings of one."""
    df = _values(monkeypatch, _with_levels("101", "Graeser", ("0", "1-2", "3")), "101").df
    grass = df.filter(pl.col("parameter") == "pollen_load_grass").sort("timestamp")
    assert grass["timestamp"].to_list() == [dt.datetime(2026, 11, d, tzinfo=UTC) for d in (17, 18, 19)]
    assert grass["value"].to_list() == [0.0, 1.5, 3.0]


@pytest.mark.parametrize(
    ("text", "raw"),
    [
        pytest.param("-1", "raw:-1", id="DWD's marker of a missing value"),
        pytest.param(-1, "raw:-1", id="as a number"),
        pytest.param("hoch", "raw:hoch", id="a word"),
        pytest.param("0.5", "raw:0.5", id="a number that is no step"),
        pytest.param("4", "raw:4", id="a step above the scale"),
        pytest.param("3-4", "raw:3-4", id="a range above the scale"),
        pytest.param("1,5", "raw:1;5", id="a text with a comma, which the tokens are separated by"),
        pytest.param(True, "raw:true", id="a JSON boolean"),
    ],
)
def test_a_text_that_is_no_step_is_no_value_and_is_kept_as_raw(
    monkeypatch: pytest.MonkeyPatch, text: object, raw: str
) -> None:
    """A day the file does not give as one of the seven steps is null with the text it wrote as `raw:`."""
    content = _with_levels("62", "Birke", (text, "1", "0-1"))
    df = _values(monkeypatch, content, "62", drop_nulls=False).df
    birch = df.filter(pl.col("parameter") == "pollen_load_birch").sort("timestamp")
    assert birch["value"].to_list() == [None, 1.0, 0.5]
    assert birch["quality_flags"].to_list() == [raw, None, None]
    # no other pollen is touched
    assert df.filter(pl.col("parameter") != "pollen_load_birch")["quality_flags"].null_count() == 21


def test_a_null_or_blank_day_is_no_value_and_has_no_text_to_keep(monkeypatch: pytest.MonkeyPatch) -> None:
    """A JSON null and a blank text are no step and have nothing to keep: null, with no flag."""
    df = _values(monkeypatch, _with_levels("62", "Birke", (None, " ", "3")), "62", drop_nulls=False).df
    birch = df.filter(pl.col("parameter") == "pollen_load_birch").sort("timestamp")
    assert birch["value"].to_list() == [None, None, 3.0]
    assert birch["quality_flags"].to_list() == [None, None, None]


def test_the_days_without_a_value_are_dropped_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Like every network, a day without a value is no row unless `drop_nulls` is off."""
    df = _values(monkeypatch, _with_levels("62", "Birke", ("-1", "1", "1")), "62").df
    birch = df.filter(pl.col("parameter") == "pollen_load_birch")
    assert birch.height == 2
    assert birch["value"].to_list() == [1.0, 1.0]


def test_a_single_parameter_is_the_rows_of_that_pollen(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request for one parameter of the dataset answers that pollen only."""
    df = _values(monkeypatch, FIXTURE, "124", parameters=("pollen_load_birch",)).df
    assert df["parameter"].unique().to_list() == ["pollen_load_birch"]
    assert df.height == 3


def test_the_whole_network_is_648_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """27 regions, eight pollen types and three days, each with a value, from the one file."""
    df = _values(monkeypatch, FIXTURE).df
    assert df.height == 27 * 8 * 3
    assert df["station_id"].n_unique() == 27
    assert 0 <= df["value"].min() <= df["value"].max() <= 3


def test_the_file_is_read_once_for_all_the_stations(monkeypatch: pytest.MonkeyPatch) -> None:
    """One file holds every region, so a request for 27 stations downloads it once."""
    calls: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        calls.append(url or args[0])
        return File(url=dwd_pollen_api.URL, content=BytesIO(FIXTURE), status=200)

    monkeypatch.setattr(dwd_pollen_api, "download_file", download_file)
    _request().all().values().all()
    assert calls == [dwd_pollen_api.URL]


def test_the_date_of_the_file_is_the_date_of_the_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """A forecast has no issue, so the answer is dated by the file the server last wrote (`data_updated_at`)."""
    assert _values(monkeypatch, FIXTURE, "20").data_updated_at == LAST_MODIFIED


def test_the_days_follow_the_day_of_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stamps are those of `last_update`, whatever the day of the request: a month later is a month later."""
    document = _fixture_document()
    document["last_update"] = "2026-12-31 11:00 Uhr"
    df = _values(monkeypatch, _file(document), "20", parameters=("pollen_load_hazel",)).df
    assert df.sort("timestamp")["timestamp"].to_list() == [
        dt.datetime(2026, 12, 31, tzinfo=UTC),
        dt.datetime(2027, 1, 1, tzinfo=UTC),
        dt.datetime(2027, 1, 2, tzinfo=UTC),
    ]


def test_a_window_cuts_the_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """A start and an end of the request select among the three days."""
    _serve_file(monkeypatch, FIXTURE)
    request = DwdPollenRequest(
        parameters=[("daily", "data", "pollen_load_birch")],
        start=dt.datetime(2026, 11, 18, tzinfo=UTC),
        end=dt.datetime(2026, 11, 18, tzinfo=UTC),
        settings=Settings(cache_disable=True),
    )
    df = request.filter_by_station_id(["124"]).values().all().df
    assert df["timestamp"].to_list() == [dt.datetime(2026, 11, 18, tzinfo=UTC)]


# ---------------------------------------------------------------------------------------------------------------------
# a region that is not in the table, one that is not in the file, a file that is not served
# ---------------------------------------------------------------------------------------------------------------------


def test_a_region_of_the_file_that_is_not_in_the_table_is_skipped_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """DWD adds a region: it is named in the warning, once, and every station of the table is answered as before."""
    document = _fixture_document()
    template = document["content"][0]["Pollen"]
    document["content"].append(
        {
            "region_id": 130,
            "partregion_id": 131,
            "region_name": "Atlantis",
            "partregion_name": "Mitte",
            "Pollen": template,
        }
    )
    document["content"].append(
        {"region_id": 140, "partregion_id": -1, "region_name": "Lemuria", "partregion_name": "", "Pollen": template}
    )
    with caplog.at_level(logging.WARNING, logger=dwd_pollen_api.__name__):
        df = _values(monkeypatch, _file(document)).df
    assert df.height == 27 * 8 * 3
    assert set(df["station_id"]) == {region.station_id for region in REGIONS}
    warnings = [record.getMessage() for record in caplog.records if "not known here" in record.getMessage()]
    assert len(warnings) == 1
    assert "2 region(s)" in warnings[0]
    assert "Atlantis: Mitte" in warnings[0]
    assert "Lemuria" in warnings[0]


def test_a_region_of_the_table_that_the_file_does_not_hold_is_told(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """DWD drops or renumbers a region: it has no values, the warning names it, and the others are answered."""
    document = _fixture_document()
    document["content"] = [entry for entry in document["content"] if entry["partregion_id"] != 124]
    begin_response()
    with caplog.at_level(logging.WARNING, logger=dwd_pollen_api.__name__):
        result = _values(monkeypatch, _file(document))
    assert result.df.height == 26 * 8 * 3
    assert "124" not in set(result.df["station_id"])
    assert any("124" in record.getMessage() for record in caplog.records)
    (skipped,) = [warning for warning in recorded_warnings() if warning["code"] == "file-skipped"]
    assert skipped["stations"] == ["124"]
    # the file was read and holds nothing of the region, which is no file that "would not parse"
    assert ": the file holds no forecast of it." in skipped["message"]
    assert "would not parse" not in skipped["message"]
    assert "try again" not in skipped["message"].lower()


def test_a_pollen_that_a_region_lacks_has_no_rows_and_is_warned_about(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A region that does not give one of the eight pollen types has the other seven, and the log names it."""
    document = _fixture_document()
    for entry in document["content"]:
        if entry["partregion_id"] == 124:
            del entry["Pollen"]["Ambrosia"]
    with caplog.at_level(logging.WARNING, logger=dwd_pollen_api.__name__):
        df = _values(monkeypatch, _file(document), "124").df
    assert "pollen_load_ragweed" not in set(df["parameter"])
    assert df.height == 7 * 3
    assert any("Ambrosia" in record.getMessage() and "124" in record.getMessage() for record in caplog.records)


def _without_a_pollen_in_every_region(pollen: str) -> bytes:
    document = _fixture_document()
    for entry in document["content"]:
        del entry["Pollen"][pollen]
    return _file(document)


def test_a_pollen_that_no_region_has_is_no_error_and_has_no_rows() -> None:
    """DWD lists the keys as possible ones: a type the file holds for no region is read, as the others are."""
    forecast = read_forecast(_without_a_pollen_in_every_region("Erle"))
    assert len(forecast.regions) == 27
    assert all(set(by_type) == set(POLLEN_TYPES) - {"Erle"} for by_type in forecast.regions.values())


def test_a_pollen_that_no_region_has_is_told_and_the_present_one_is_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asked with a present type, the missing one has no rows and `parameter-without-rows` names it."""
    begin_response()
    result = _values(
        monkeypatch,
        _without_a_pollen_in_every_region("Erle"),
        "124",
        parameters=("pollen_load_birch", "pollen_load_alder"),
    )
    assert result.df["parameter"].unique().to_list() == ["pollen_load_birch"]
    assert result.df.height == 3
    (warning,) = [w for w in recorded_warnings() if w["code"] == "parameter-without-rows"]
    assert "pollen_load_alder" in warning["message"]
    assert "pollen_load_birch" not in warning["message"]


def test_a_request_for_the_present_pollen_alone_is_answered_without_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """A type missing from every region does not touch a request that does not ask for it."""
    begin_response()
    result = _values(monkeypatch, _without_a_pollen_in_every_region("Erle"), parameters=("pollen_load_birch",))
    assert result.df["station_id"].n_unique() == 27
    assert result.df.height == 27 * 3
    assert [w for w in recorded_warnings() if w["code"] == "parameter-without-rows"] == []


def test_a_pollen_type_of_the_file_that_is_not_one_of_the_eight_is_skipped_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """DWD adds a pollen type: it is named in the warning and the eight are answered as before."""
    document = _fixture_document()
    for entry in document["content"]:
        entry["Pollen"]["Pappel"] = {"today": "3", "tomorrow": "3", "dayafter_to": "3"}
    with caplog.at_level(logging.WARNING, logger=dwd_pollen_api.__name__):
        df = _values(monkeypatch, _file(document), "124").df
    assert df.height == 8 * 3
    assert [r.getMessage() for r in caplog.records if "pollen type(s)" in r.getMessage() and "Pappel" in r.getMessage()]


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
        dwd_pollen_api,
        "download_file",
        lambda *_args, **_kwargs: File(url=dwd_pollen_api.URL, content=body, status=status),
    )
    begin_response()
    with caplog.at_level(logging.WARNING, logger=dwd_pollen_api.__name__):
        result = _request().filter_by_station_id(["124"]).values().all()
    assert result.df.is_empty()
    assert any(dwd_pollen_api.URL in record.getMessage() for record in caplog.records)
    assert "file-skipped" in {warning["code"] for warning in recorded_warnings()}


def test_an_outage_is_raised_and_not_read_as_no_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    """A server error is a `DownloadError`, which swallowed would read as a day without a forecast (GH-2461)."""
    monkeypatch.setattr(
        dwd_pollen_api,
        "download_file",
        lambda *_args, **_kwargs: File(url=dwd_pollen_api.URL, content=OSError("reset"), status=503),
    )
    with pytest.raises(DownloadError):
        _request().filter_by_station_id(["124"]).values().all()


def test_a_429_is_the_rate_limit_error_and_is_never_let_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 limits how fast the client may ask: it is raised as such, not skipped as a file DWD has not got."""
    limited = ClientResponseError(request_info=MagicMock(), history=(), status=429, message="Too Many Requests")
    monkeypatch.setattr(
        dwd_pollen_api,
        "download_file",
        lambda *_args, **_kwargs: File(url=dwd_pollen_api.URL, content=limited, status=429),
    )
    with pytest.raises(ProviderRateLimitError):
        _request().filter_by_station_id(["124"]).values().all()


def test_an_outage_page_that_is_no_json_is_a_download_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 that is an error page of a CDN is the changed layout it looks like, and is raised."""
    _serve_file(monkeypatch, b"<!doctype html><title>502 Bad Gateway</title>")
    with pytest.raises(DownloadError, match="not the pollen forecast"):
        _request().all().values().all()


def test_the_value_stub_serves_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared `serve` helper of the stubs reaches the provider's download as well."""
    serve(monkeypatch, dwd_pollen_api, {"s31fg.json": FIXTURE})
    df = _request().filter_by_station_id(["124"]).values().all().df
    assert df.height == 8 * 3


# ---------------------------------------------------------------------------------------------------------------------
# remote
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.remote
def test_dwd_pollen_live(caplog: pytest.LogCaptureFixture) -> None:
    """The live file holds the 27 regions of the table and three days of the eight pollen types.

    Live by design, not guarded by an xfail: a region DWD renumbers or adds, or a layout it changes, is what this is
    for.
    A region the file lists that the table does not hold is only logged and skipped, so it is asked for here: the
    request names no region of the file that the table lacks (the warning), and every station of the table has rows.
    """
    request = DwdPollenRequest(parameters=[("daily", "data")], options=Options(drop_nulls=False))
    with caplog.at_level(logging.WARNING, logger=dwd_pollen_api.__name__):
        result = request.all().values().all()
    assert [r.getMessage() for r in caplog.records if "not known here" in r.getMessage()] == []
    df = result.df
    assert df["station_id"].n_unique() == 27
    assert df["parameter"].n_unique() == 8
    assert df.height == 27 * 8 * 3
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")
    days = sorted(df["timestamp"].unique().to_list())
    assert len(days) == 3
    assert days[1] - days[0] == dt.timedelta(days=1)
    assert days[2] - days[1] == dt.timedelta(days=1)
    # the file is written every morning: its first day is today or, before the update, yesterday
    today = dt.datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    assert today - dt.timedelta(days=2) <= days[0] <= today + dt.timedelta(days=1)
    # every day is a step of the legend, or DWD's -1 for a day without a forecast, which is null with its raw text
    assert df["value"].drop_nulls().is_in(list(LEVELS.values())).all()
    assert not any("suspect" in (flags or "") for flags in df["quality_flags"])
    assert result.data_updated_at is not None
    assert dt.datetime.now(tz=UTC) - result.data_updated_at < dt.timedelta(days=3)
