# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what `dwd/mosmix` does per product: the runs `issues` lists, the files a mixed request reads (GH-4093)."""

from __future__ import annotations

import datetime as dt
import logging
from io import BytesIO

import polars as pl
import pytest

from tests.provider.value_stubs import _DWD_KML, _KML, _options, _settings
from wetterdienst import Settings
from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest, api
from wetterdienst.provider.dwd.mosmix.access import KMLReader

UTC = dt.UTC

BASE = "https://opendata.dwd.de/weather/local_forecasts/mos"


def _names(directory: str, names: list[str]) -> list[str]:
    return [f"{BASE}/{directory}/{name}" for name in names]


#: the three layouts of DWD's directories, as the server lists them: the directory and what it holds
LISTINGS = {
    "large": (
        "MOSMIX_L/single_stations/01001/kml/",
        ["MOSMIX_L_2026111409_01001.kmz", "MOSMIX_L_2026111415_01001.kmz", "MOSMIX_L_LATEST_01001.kmz"],
        [dt.datetime(2026, 11, 14, 9, tzinfo=UTC), dt.datetime(2026, 11, 14, 15, tzinfo=UTC)],
    ),
    "small": (
        "MOSMIX_S/all_stations/kml/",
        ["MOSMIX_S_2026111413_240.kmz", "MOSMIX_S_2026111414_240.kmz", "MOSMIX_S_LATEST_240.kmz"],
        [dt.datetime(2026, 11, 14, 13, tzinfo=UTC), dt.datetime(2026, 11, 14, 14, tzinfo=UTC)],
    ),
    "snow": (
        "MOSMIX-SNOW_S/all_stations/kml/",
        ["MOSMIX-SNOW_S_2026111419_48.kmz", "MOSMIX-SNOW_S_2026111420_48.kmz", "MOSMIX-SNOW_S_aktuell_48.kmz"],
        [dt.datetime(2026, 11, 14, 19, tzinfo=UTC), dt.datetime(2026, 11, 14, 20, tzinfo=UTC)],
    ),
}


@pytest.mark.parametrize("dataset", ["large", "small", "snow"])
def test_available_issues_lists_the_directory_of_the_product(monkeypatch: pytest.MonkeyPatch, dataset: str) -> None:
    """Each product's runs come from the directory the values path reads for it, and the alias beside them is no run."""
    directory, names, expected = LISTINGS[dataset]
    asked: list[str] = []

    def listing(url: str, *_args: object, **_kwargs: object) -> list[str]:
        asked.append(url)
        return _names(directory, names)

    monkeypatch.setattr(api, "list_remote_files_fsspec", listing)

    assert DwdMosmixRequest.available_issues("01001", Settings(), dataset=dataset) == expected
    assert asked == [f"{BASE}/{directory}"]


def test_available_issues_defaults_to_mosmix_l(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no dataset the answer is MOSMIX-L's, as it was before the product could be named."""
    directory, names, expected = LISTINGS["large"]
    asked: list[str] = []

    def listing(url: str, *_args: object, **_kwargs: object) -> list[str]:
        asked.append(url)
        return _names(directory, names)

    monkeypatch.setattr(api, "list_remote_files_fsspec", listing)

    assert DwdMosmixRequest.available_issues("01001", Settings()) == expected
    assert asked == [f"{BASE}/{directory}"]


@pytest.mark.parametrize("dataset", ["small", "snow"])
def test_available_issues_of_an_all_stations_product_is_the_same_for_any_station(
    monkeypatch: pytest.MonkeyPatch, dataset: str
) -> None:
    """One file holds every station of MOSMIX-S and MOSMIX-SNOW, so the station does not decide the directory."""
    directory, names, expected = LISTINGS[dataset]
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: _names(directory, names))

    assert DwdMosmixRequest.available_issues("Z914", Settings(), dataset=dataset) == expected
    assert DwdMosmixRequest.available_issues("10147", Settings(), dataset=dataset) == expected


def test_available_issues_refuses_a_dataset_the_network_does_not_have() -> None:
    """A name that is none of the three products is refused, not answered with the runs of another."""
    with pytest.raises(InvalidEnumerationError, match="dataset must be one of large, small, snow"):
        DwdMosmixRequest.available_issues("01001", Settings(), dataset="icon")


def test_available_issues_of_snow_counts_its_alias_as_one(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """MOSMIX-SNOW's alias is `aktuell`, and a directory pruned back to it says one entry of one is the alias."""
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(
        api,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: _names("MOSMIX-SNOW_S/all_stations/kml/", ["MOSMIX-SNOW_S_aktuell_48.kmz"]),
    )

    assert DwdMosmixRequest.available_issues("Z914", Settings(), dataset="snow") == []
    assert "(1 entries, 1 of them the LATEST alias)" in caplog.text


def test_available_issues_of_snow_out_of_season_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """MOSMIX-SNOW is published from November to April: an empty directory is the season, no product that moved."""
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [])

    assert DwdMosmixRequest.available_issues("Z914", Settings(), dataset="snow") == []
    assert "No MOSMIX-SNOW run is listed within" in caplog.text


# --- one parse per file in a mixed request


def _kml(
    stations: dict[str, dict[str, str]],
    run: str = "2026-10-10T09:00:00.000Z",
    hours: tuple[int, ...] = (10, 11, 12),
) -> bytes:
    """Build a run of the given hours holding the given stations, each with its elements as the file writes them."""
    steps = "".join(f"<dwd:TimeStep>2026-10-10T{hour}:00:00.000Z</dwd:TimeStep>" for hour in hours)
    placemarks = "".join(
        f"<kml:Placemark><kml:name>{station_id}</kml:name><kml:ExtendedData>"
        + "".join(
            f'<dwd:Forecast dwd:elementName="{name}"><dwd:value>{values}</dwd:value></dwd:Forecast>'
            for name, values in elements.items()
        )
        + "</kml:ExtendedData></kml:Placemark>"
        for station_id, elements in stations.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<kml:kml xmlns:kml="{_KML}" xmlns:dwd="{_DWD_KML}"><kml:Document>'
        "<kml:ExtendedData><dwd:ProductDefinition><dwd:Issuer>DWD</dwd:Issuer><dwd:ProductID>MOSMIX</dwd:ProductID>"
        f"<dwd:GeneratingProcess>S</dwd:GeneratingProcess><dwd:IssueTime>{run}</dwd:IssueTime>"
        f"<dwd:ForecastTimeSteps>{steps}</dwd:ForecastTimeSteps></dwd:ProductDefinition></kml:ExtendedData>"
        f"{placemarks}</kml:Document></kml:kml>"
    ).encode()


SMALL = "https://example.invalid/MOSMIX_S_2026101009_240.kmz"
SNOW = "https://example.invalid/MOSMIX-SNOW_S_2026101009_48.kmz"
LARGE = "https://example.invalid/MOSMIX_L_2026101009.kmz"

RUNS = {
    SMALL: _kml({"01001": {"TTT": "275.15 276.15 277.15"}, "01002": {"TTT": "270.15 271.15 272.15"}}),
    # other steps than the others, in hours and in number, so that a reader that keeps the wrong ones shows
    SNOW: _kml(
        {"01001": {"SnCv": "0.10 0.20 0.30 0.35"}, "01002": {"SnCv": "0.40 0.50 0.60 0.65"}},
        "2026-10-10T08:00:00.000Z",
        hours=(20, 21, 22, 23),
    ),
    LARGE: _kml({"01001": {"TX": "- - 280.15"}, "01002": {"TX": "- - 281.15"}}, "2026-10-10T03:00:00.000Z"),
}


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve the runs by URL and count the files parsed: a parse is one `fetch`, the streamed handle of a file."""
    fetched: list[str] = []

    def fetch(_self: KMLReader, url: str) -> BytesIO:
        fetched.append(url)
        return BytesIO(RUNS[url])

    monkeypatch.setattr(KMLReader, "fetch", fetch)
    return fetched


def _reader(keep_parsed: int | None = None) -> KMLReader:
    kwargs = {} if keep_parsed is None else {"keep_parsed": keep_parsed}
    return KMLReader(station_ids=["01001", "01002"], settings=_settings(), **kwargs)


def test_reader_parses_each_file_once_when_read_in_turn(parses: list[str]) -> None:
    """Two files read in turn, as two datasets do at every station, are parsed once each."""
    reader = _reader(keep_parsed=2)

    for _ in range(3):
        reader.read(SMALL)
        assert reader.get_station_forecast("01002")["ttt"].to_list() == [270.15, 271.15, 272.15]
        assert reader.metadata["issue_time"] == dt.datetime(2026, 10, 10, 9, tzinfo=UTC)
        assert [step[11:13] for step in reader.timesteps] == ["10", "11", "12"]
        assert [step[11:13] for step in reader.get_station_forecast("01002")["timestamp"]] == ["10", "11", "12"]
        reader.read(SNOW)
        assert reader.get_station_forecast("01002")["sncv"].to_list() == [0.40, 0.50, 0.60, 0.65]
        assert reader.metadata["issue_time"] == dt.datetime(2026, 10, 10, 8, tzinfo=UTC)
        assert [step[11:13] for step in reader.timesteps] == ["20", "21", "22", "23"]
        assert [step[11:13] for step in reader.get_station_forecast("01002")["timestamp"]] == ["20", "21", "22", "23"]

    assert parses == [SMALL, SNOW]


def test_reader_that_holds_one_file_parses_the_other_again(parses: list[str]) -> None:
    """The default of one file is what the reader did: with a second file in turn each read parses again."""
    reader = _reader()

    for _ in range(2):
        reader.read(SMALL)
        reader.read(SNOW)

    assert parses == [SMALL, SNOW, SMALL, SNOW]


def test_reader_holds_no_more_files_than_it_is_told_to(parses: list[str]) -> None:
    """The memory is that of `keep_parsed` files: reading a third drops the one read longest ago."""
    reader = _reader(keep_parsed=2)

    reader.read(SMALL)
    reader.read(SNOW)
    reader.read(LARGE)
    assert len(reader._parsed) == 2  # noqa: SLF001
    assert list(reader._parsed) == [SNOW, LARGE]  # noqa: SLF001
    # the small run was the one dropped, so asking for it parses it again, and drops the snow run in turn
    reader.read(SMALL)
    assert parses == [SMALL, SNOW, LARGE, SMALL]
    assert list(reader._parsed) == [LARGE, SMALL]  # noqa: SLF001


def test_reader_reading_a_held_file_makes_it_the_newest(parses: list[str]) -> None:
    """A file read again is kept over the one read after it: a file read at every station is never the one dropped."""
    reader = _reader(keep_parsed=2)

    reader.read(SMALL)
    reader.read(SNOW)
    reader.read(SMALL)
    reader.read(LARGE)

    assert list(reader._parsed) == [SMALL, LARGE]  # noqa: SLF001
    assert parses == [SMALL, SNOW, LARGE]


def test_mixed_request_parses_each_file_once_for_all_stations(
    monkeypatch: pytest.MonkeyPatch, parses: list[str]
) -> None:
    """A request for `small` and `snow` at two stations reads two files, not two per station (GH-4093)."""
    stations = pl.DataFrame(
        [
            {"resolution": "hourly", "dataset": dataset, "station_id": station_id, "latitude": 50.0, "longitude": 10.0}
            for dataset in ("small", "snow")
            for station_id in ("01001", "01002")
        ]
        # the columns a station of the catalogue carries that the read does not look at
    ).with_columns(
        pl.lit(None, pl.Datetime("us", "UTC")).alias("start_timestamp"),
        pl.lit(None, pl.Datetime("us", "UTC")).alias("end_timestamp"),
        pl.lit(100.0).alias("elevation"),
        pl.lit("Stub").alias("name"),
    )
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "ttt"), ("hourly", "snow", "sncv")],
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    result = StationsResult(
        request=request, df=stations, _df_all=stations, _stations_filter=StationsFilter.BY_STATION_ID
    )
    monkeypatch.setattr(
        api.DwdMosmixValues,
        "get_url_for_date",
        lambda _self, url, *_args, **_kwargs: SNOW if "SNOW" in url else SMALL,
    )

    df = result.values().all().df

    assert parses == [SMALL, SNOW]
    assert df.group_by("station_id", "dataset").len().sort("station_id", "dataset").rows() == [
        ("01001", "small", 3),
        ("01001", "snow", 4),
        ("01002", "small", 3),
        ("01002", "snow", 4),
    ]
    # each value is the file's own: the small run's temperature and the snow run's depth, at both stations
    sncv = df.filter(pl.col("dataset") == "snow", pl.col("station_id") == "01002").sort("timestamp")["value"].to_list()
    assert sncv == pytest.approx([40.0, 50.0, 60.0, 65.0])
