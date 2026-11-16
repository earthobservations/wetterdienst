# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The WMO numbers of `dwd/observation` come from DWD's Stationslexikon, and a page that is not it fails (GH-4073).

The table is an HTML page, which is no data format: DWD may rename a header, move a column or serve another page at the
address, and the reader must say so and not hand back stations with an empty column. These tests hold the rule that
picks a station's number, the layout the reader asks of the page, what the stations carry and what a search by
`wmo_id` finds, and what happens when the page cannot be had. The stub is `stationslexikon_rows.py`, real rows of the
page of 2026-11-16; the last test reads the live page.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.dwd.observation.stationslexikon_rows import EXPECTED_WMO_IDS, HEADERS, ROWS, STATIONSLEXIKON, page
from tests.provider.station_catalogue_stubs import _serve
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, MetaFileFormatError, NoInternetError, ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.observation import DwdObservationRequest, stationslexikon
from wetterdienst.provider.dwd.observation import fileindex as dwd_fileindex
from wetterdienst.provider.dwd.observation import metaindex as dwd_metaindex
from wetterdienst.provider.dwd.observation.stationslexikon import (
    STATIONSLEXIKON_URL,
    WMO_IDS_UNAVAILABLE,
    StationslexikonLayoutError,
    parse_wmo_ids,
    read_wmo_ids,
    with_wmo_id,
)
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from pathlib import Path

# lines of `KL_Tageswerte_Beschreibung_Stationen.txt` (daily/kl, 2026-11-16), cut at the blanks they are padded with:
# Aachen (`SY` and `MN` have its number), Donaueschingen (they have an id of DWD's own), Berlin-Dahlem and Hamburg
_DESCRIPTION = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "---------- ------\r\n"
    "00003 18910101 20110331            202     50.7827    6.0941 Aachen                                   "
    "Nordrhein-Westfalen                      Frei\r\n"
    "00011 19800901 20261013            680     47.9736    8.5205 Donaueschingen (Landeplatz)              "
    "Baden-Württemberg                        Frei\r\n"
    "00403 19500101 20261115             51     52.4537   13.3017 Berlin-Dahlem (FU)                       "
    "Berlin                                   Frei\r\n"
    "01975 19360101 20261115             11     53.6332    9.9881 Hamburg-Fuhlsbüttel                      "
    "Hamburg                                  Frei\r\n"
)
_BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/historical/"


def _request(monkeypatch: pytest.MonkeyPatch, lexikon: bytes = STATIONSLEXIKON) -> DwdObservationRequest:
    """Give a request for the stations of `_DESCRIPTION`, which read their WMO numbers from the given page."""
    files = [f"{_BASE}KL_Tageswerte_Beschreibung_Stationen.txt"]
    files += [
        f"{_BASE}tageswerte_KL_{line[:5]}_{line[6:14]}_{line[15:23]}_hist.zip" for line in _DESCRIPTION.splitlines()[2:]
    ]
    monkeypatch.setattr(dwd_fileindex, "list_remote_files_fsspec", lambda *_args, **_kwargs: files)
    _serve(monkeypatch, dwd_metaindex, {"Beschreibung_Stationen": _DESCRIPTION.encode("latin-1")})
    _serve(monkeypatch, stationslexikon, {"statlex_html": lexikon})
    return DwdObservationRequest(
        parameters=[("daily", "climate_summary")], periods="historical", settings=Settings(cache_disable=True)
    )


def _wmo_ids(frame: pl.DataFrame) -> dict[str, str | None]:
    return dict(zip(frame["station_id"], frame["wmo_id"], strict=True))


# the rule: which of a station's rows give its number


def test_a_station_gets_the_five_digit_number_of_its_sy_and_mn_rows() -> None:
    """Berlin-Dahlem has it in `SY` alone, Hamburg and Aachen in `SY` and `MN` with one number, five digits each."""
    found = parse_wmo_ids(STATIONSLEXIKON)
    assert dict(zip(found["station_id"], found["wmo_id"], strict=True)) == EXPECTED_WMO_IDS
    assert found.schema == {"station_id": pl.String, "wmo_id": pl.String}


def test_an_id_of_dwds_own_and_the_numbers_of_other_products_are_no_wmo_number() -> None:
    """`H808`, `Q870` of `SY` and `MN` and the `03319` and `46552` of the other products of Berlin-Dahlem are none."""
    found = parse_wmo_ids(STATIONSLEXIKON)["wmo_id"].to_list()
    assert not {"03319", "46552", "01459", "02205"} & set(found)
    assert set(found) == {"10501", "10427", "10381", "10147"}


def test_a_number_that_moved_with_the_station_belongs_to_both_its_ids() -> None:
    """10427 is Altastenberg until 1954 and Kahler Asten from then: each id keeps the number of its own rows."""
    found = _wmo_ids(parse_wmo_ids(STATIONSLEXIKON))
    assert found["00098"] == found["02483"] == "10427"


def test_a_station_with_two_different_numbers_has_none_and_the_log_says_so(caplog: pytest.LogCaptureFixture) -> None:
    """DWD's rows do not do that today (read 2026-11-16: no station); which number is the station's is not guessed."""
    rows = (
        *ROWS,
        "Synthetic|9|SY|10001|50.0|8.0|100||HE|01.01.2000|14.11.2026",
        "Synthetic|9|MN|10002|50.0|8.0|100||HE|01.01.2008|14.11.2026",
    )
    with caplog.at_level(logging.WARNING, logger=stationslexikon.log.name):
        found = _wmo_ids(parse_wmo_ids(page(rows)))
    assert "00009" not in found
    assert found["01975"] == "10147"
    assert any("00009 (10001/10002)" in record.getMessage() for record in caplog.records)


def test_a_number_of_another_length_or_an_alphanumeric_one_is_ignored_beside_a_good_one() -> None:
    """Four and six digits are no WMO number, nor `H808`; a good row of the same station still counts."""
    rows = (
        "Synthetic|7|SY|1038|50.0|8.0|100||HE|01.01.2000|14.11.2026",
        "Synthetic|7|MN|10381|50.0|8.0|100||HE|01.01.2008|14.11.2026",
        "Synthetic|8|SY|103811|50.0|8.0|100||HE|01.01.2000|14.11.2026",
        "Synthetic|8|MN|H808|50.0|8.0|100||HE|01.01.2008|14.11.2026",
        "Synthetic|10|KL|10382|50.0|8.0|100||HE|01.01.2008|14.11.2026",
        "Synthetic|x1|SY|10383|50.0|8.0|100||HE|01.01.2008|14.11.2026",
        *ROWS,
    )
    found = _wmo_ids(parse_wmo_ids(page(rows)))
    assert found["00007"] == "10381"
    assert not {"00008", "00010", "x1", "000x1"} & found.keys()


# the layout: which pages are the table, and which fail


def test_the_columns_are_found_by_their_header_and_not_by_position() -> None:
    """A table with its columns in another order, one more in front, and the headers spelled differently, is read."""
    reordered = page(order=(3, 2, 1, 0, 4, 5, 6, 7, 8, 9, 10))
    assert _wmo_ids(parse_wmo_ids(reordered)) == EXPECTED_WMO_IDS
    respelled = list(HEADERS)
    respelled[1], respelled[2], respelled[3] = "Stations_Id", "KENNUNG", "Stations kennung"
    assert _wmo_ids(parse_wmo_ids(page(headers=tuple(respelled)))) == EXPECTED_WMO_IDS


def _with_header(index: int, text: str) -> bytes:
    headers = list(HEADERS)
    headers[index] = text
    return page(headers=tuple(headers))


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        pytest.param(_with_header(3, "Stationskennzeichen"), "Stations-kennung", id="a-header-renamed"),
        pytest.param(_with_header(2, "Produkt"), "Kennung", id="the-product-header-renamed"),
        pytest.param(_with_header(1, "Station"), "Stations_ID", id="the-id-header-renamed"),
        pytest.param(page(()), "no row", id="no-row"),
        pytest.param(
            page(tuple(line for line in ROWS if "|SY|" not in line and "|MN|" not in line)),
            "none of its",
            id="no-sy-or-mn-row",
        ),
        pytest.param(
            page(tuple(line.replace("|SY|", "|XX|").replace("|MN|", "|XY|") for line in ROWS)),
            "none of its",
            id="products-renamed",
        ),
        pytest.param(
            b"<html><head><title>Wartungsarbeiten</title></head><body><p>Bitte sp\xe4ter wieder.</p></body></html>",
            "no header row",
            id="another-page",
        ),
        pytest.param(b"", "no HTML document", id="empty"),
        pytest.param(b'{"error": "not found"}', "no header row", id="a-json-answer"),
    ],
)
def test_a_page_that_is_not_the_table_raises_naming_the_address(content: bytes, reason: str) -> None:
    """A renamed header, no rows, no WMO number, an error page or no page at all raises, naming the URL."""
    with pytest.raises(StationslexikonLayoutError) as raised:
        parse_wmo_ids(content)
    assert STATIONSLEXIKON_URL in str(raised.value)
    assert reason in str(raised.value)
    assert raised.value.url == STATIONSLEXIKON_URL
    assert isinstance(raised.value, MetaFileFormatError)


def test_the_table_is_asked_for_with_its_view_and_kept_for_a_week(monkeypatch: pytest.MonkeyPatch) -> None:
    """The address without the view is the 46 KB introduction; the table is the one with it, and is cached a week."""
    asked: dict = {}

    def download_file(**kwargs: object) -> File:
        asked.update(kwargs)
        return File(url=str(kwargs["url"]), content=BytesIO(STATIONSLEXIKON), status=200)

    monkeypatch.setattr(stationslexikon, "download_file", download_file)
    assert _wmo_ids(read_wmo_ids(Settings(cache_disable=True))) == EXPECTED_WMO_IDS
    assert asked["url"] == STATIONSLEXIKON_URL
    assert asked["url"].endswith("statlex_html.html?view=nasPublication")
    assert asked["ttl"] is CacheExpiry.ONE_WEEK


def test_a_page_that_is_not_the_table_is_dropped_from_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Else the next call would read the same page for a week."""
    dropped: list[tuple] = []
    monkeypatch.setattr(
        stationslexikon,
        "download_file",
        lambda **kwargs: File(
            url=str(kwargs["url"]), content=BytesIO(b"<html><body>Wartung</body></html>"), status=200
        ),
    )
    monkeypatch.setattr(stationslexikon, "drop_cached_file", lambda *args, **_kwargs: dropped.append(args))
    with pytest.raises(StationslexikonLayoutError):
        read_wmo_ids(Settings(cache_disable=True))
    assert [args[:3] for args in dropped] == [
        (STATIONSLEXIKON_URL, Settings(cache_disable=True).cache_dir, CacheExpiry.ONE_WEEK)
    ]


# what the stations carry, and what a search by wmo_id finds


def test_the_stations_carry_the_wmo_id_and_a_search_by_it_finds_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hamburg-Fuhlsbüttel `10147` is `01975`, Berlin-Dahlem `10381` is `00403`, as a number or a text."""
    request = _request(monkeypatch)
    stations = request.all().df
    assert _wmo_ids(stations.unique(subset="station_id", maintain_order=True)) == {
        "00003": "10501",
        "00011": None,
        "00403": "10381",
        "01975": "10147",
    }
    assert stations.schema["wmo_id"] == pl.String
    assert request.filter_by_wmo_id("10147").df["station_id"].to_list() == ["01975"]
    assert request.filter_by_wmo_id(10381).df["station_id"].to_list() == ["00403"]
    assert request.filter_by_wmo_id(["10501", "10147"]).df["station_id"].to_list() == ["00003", "01975"]


def test_a_station_without_a_wmo_number_is_not_found_by_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Donaueschingen has an id of DWD's own in `SY` and `MN`: no `wmo_id`, and `Q870` is no id to search by."""
    request = _request(monkeypatch)
    assert request.all().df.filter(pl.col("station_id") == "00011")["wmo_id"].to_list() == [None]
    assert request.filter_by_wmo_id("10803").df.is_empty()


# when the page cannot be had


def test_a_page_that_is_not_the_table_leaves_the_stations_without_wmo_id_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The station list is the answer and the number an addition: they come back, with the warning and no number."""
    request = _request(monkeypatch, lexikon=_with_header(3, "Stationskennzeichen"))
    begin_response()
    with caplog.at_level(logging.WARNING, logger=stationslexikon.log.name):
        stations = request.all().df
    assert stations["station_id"].unique().sort().to_list() == ["00003", "00011", "00403", "01975"]
    assert stations["wmo_id"].null_count() == stations.height
    assert stations.schema["wmo_id"] == pl.String
    (warning,) = [w for w in recorded_warnings() if w["code"] == WMO_IDS_UNAVAILABLE]
    assert STATIONSLEXIKON_URL in warning["message"]
    assert [record.response_warning for record in caplog.records if hasattr(record, "response_warning")] == [
        WMO_IDS_UNAVAILABLE
    ]


def test_a_server_that_answers_badly_leaves_the_stations_without_wmo_id_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 5xx, a 404 or a cut connection of this one page costs the numbers and not the stations."""

    def fail(_settings: object) -> pl.DataFrame:
        raise DownloadError(STATIONSLEXIKON_URL, "503, message='Service Unavailable'")

    stations = pl.LazyFrame({"station_id": ["00003"]})
    monkeypatch.setattr(stationslexikon, "read_wmo_ids", fail)
    begin_response()
    assert with_wmo_id(stations, Settings(cache_disable=True)).collect().to_dict(as_series=False) == {
        "station_id": ["00003"],
        "wmo_id": [None],
    }
    assert [w["code"] for w in recorded_warnings()] == [WMO_IDS_UNAVAILABLE]


def test_a_connection_that_cannot_be_made_leaves_the_stations_without_wmo_id_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A proxy or a name that does not resolve for `www.dwd.de` must not fail every stations request (GH-4073)."""
    refusal = NoInternetError("No internet connection: could not reach www.dwd.de")

    def fail(_settings: object) -> pl.DataFrame:
        raise refusal

    monkeypatch.setattr(stationslexikon, "read_wmo_ids", fail)
    begin_response()
    stations = with_wmo_id(pl.LazyFrame({"station_id": ["00003"]}), Settings(cache_disable=True)).collect()
    assert stations.to_dict(as_series=False) == {"station_id": ["00003"], "wmo_id": [None]}
    assert [w["code"] for w in recorded_warnings()] == [WMO_IDS_UNAVAILABLE]


def test_a_rate_limit_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 is never let go, and the next request meets it too."""

    def fail(_settings: object) -> pl.DataFrame:
        raise ProviderRateLimitError(STATIONSLEXIKON_URL, "limited", 7)

    monkeypatch.setattr(stationslexikon, "read_wmo_ids", fail)
    with pytest.raises(ProviderRateLimitError):
        with_wmo_id(pl.LazyFrame({"station_id": ["00003"]}), Settings(cache_disable=True))


# what the process remembers


class _Clock:
    """A clock the test sets, for the memory of the reader."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    """Replace the clock of the memory of the reader."""
    fake = _Clock()
    monkeypatch.setattr(stationslexikon, "_clock", fake)
    return fake


def _counting_download(monkeypatch: pytest.MonkeyPatch, answers: list) -> list[str]:
    """Answer each download with the next of `answers` (a body, or an exception), and list the downloads made."""
    asked: list[str] = []

    def download_file(**kwargs: object) -> File:
        asked.append(str(kwargs["url"]))
        answer = answers[min(len(asked), len(answers)) - 1]
        content = answer if isinstance(answer, Exception) else BytesIO(answer)
        return File(url=str(kwargs["url"]), content=content, status=200 if isinstance(answer, bytes) else 0)

    monkeypatch.setattr(stationslexikon, "download_file", download_file)
    return asked


def test_the_table_is_read_once_for_the_expiry_of_the_cache(monkeypatch: pytest.MonkeyPatch, clock: _Clock) -> None:
    """A second lookup reads nothing, whether the cache is on or off; after the week it reads the page again."""
    asked = _counting_download(monkeypatch, [STATIONSLEXIKON])
    settings = Settings(cache_disable=True)
    assert _wmo_ids(read_wmo_ids(settings)) == EXPECTED_WMO_IDS
    assert _wmo_ids(read_wmo_ids(settings)) == EXPECTED_WMO_IDS
    assert len(asked) == 1
    clock.now += CacheExpiry.ONE_WEEK.value - 1
    read_wmo_ids(settings)
    assert len(asked) == 1
    clock.now += 2
    read_wmo_ids(settings)
    assert len(asked) == 2


def test_the_memory_is_for_the_cache_and_the_settings_the_table_was_read_with(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Another cache directory, or the cache on and off, is another read."""
    asked = _counting_download(monkeypatch, [STATIONSLEXIKON])
    read_wmo_ids(Settings(cache_disable=True))
    read_wmo_ids(Settings(cache_disable=True))
    assert len(asked) == 1
    read_wmo_ids(Settings(cache_dir=tmp_path / "other", cache_disable=True))
    assert len(asked) == 2
    read_wmo_ids(Settings(cache_dir=tmp_path / "other", cache_disable=False))
    assert len(asked) == 3


def test_a_failure_is_remembered_for_a_few_minutes_and_then_asked_again(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    """A page that is down is not downloaded again by every request; once the minutes have passed it is."""
    asked = _counting_download(monkeypatch, [TimeoutError(), STATIONSLEXIKON])
    settings = Settings(cache_disable=True)
    for _ in range(3):
        with pytest.raises(DownloadError):
            read_wmo_ids(settings)
    assert len(asked) == 1
    clock.now += stationslexikon.STATIONSLEXIKON_FAILURE_MEMORY - 1
    with pytest.raises(DownloadError):
        read_wmo_ids(settings)
    assert len(asked) == 1
    clock.now += 2
    assert _wmo_ids(read_wmo_ids(settings)) == EXPECTED_WMO_IDS
    assert len(asked) == 2


def test_a_page_that_is_not_the_table_is_remembered_too_and_every_request_still_says_so(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    """The stations of each request come back with the warning, without the page being read for each."""
    asked = _counting_download(monkeypatch, [b"<html><body>Wartung</body></html>", STATIONSLEXIKON])
    monkeypatch.setattr(stationslexikon, "drop_cached_file", lambda *_args, **_kwargs: None)
    settings = Settings(cache_disable=True)
    for _ in range(2):
        begin_response()
        stations = with_wmo_id(pl.LazyFrame({"station_id": ["00003"]}), settings).collect()
        assert stations["wmo_id"].to_list() == [None]
        assert [w["code"] for w in recorded_warnings()] == [WMO_IDS_UNAVAILABLE]
    assert len(asked) == 1
    clock.now += stationslexikon.STATIONSLEXIKON_FAILURE_MEMORY + 1
    begin_response()
    stations = with_wmo_id(pl.LazyFrame({"station_id": ["00003"]}), settings).collect()
    assert stations["wmo_id"].to_list() == ["10501"]
    assert len(asked) == 2


def test_a_download_that_failed_is_a_download_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `File` the network layer stores a failure in is raised by the reader, naming the address."""
    monkeypatch.setattr(
        stationslexikon,
        "download_file",
        lambda **kwargs: File(url=str(kwargs["url"]), content=TimeoutError(), status=0),
    )
    with pytest.raises(DownloadError) as raised:
        read_wmo_ids(Settings(cache_disable=True))
    assert "statlex_html.html" in str(raised.value)


# the live page


@pytest.mark.remote
def test_the_live_stationslexikon_gives_the_numbers_of_the_issue() -> None:
    """Berlin-Dahlem `00403` is 10381, Hamburg-Fuhlsbüttel `01975` is 10147, and about 300 stations have a number.

    Read 2026-11-16: 314 stations, of 13,779 in the page.
    """
    found = _wmo_ids(read_wmo_ids(Settings(cache_disable=True)))
    assert found["00403"] == "10381"
    assert found["01975"] == "10147"
    assert len(found) >= 250
    assert all(len(number) == 5 and number.isdigit() for number in found.values())
    assert all(len(station_id) == 5 and station_id.isdigit() for station_id in found)
    # an id of DWD's own is no WMO number: Donaueschingen, which `SY` and `MN` give `Q870`
    assert "00011" not in found
