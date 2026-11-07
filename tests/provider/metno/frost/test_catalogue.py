# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The station catalogue of Frost: the closed stations, and the start and the end read from the declared series.

The sources are asked with a `validtime` that takes in the closed stations, and the start and the end of each station
come from one request for the series Frost lists over the elements and resolutions the network declares (GH-3847,
GH-3864), not from the source's own `validFrom` and `validTo`, which are not the span of the data. The rows are those of
the real answers of 2026-11-07 (`catalogue_rows.py`), and every rule of the span is held to a station that shows it.
"""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import Any, NamedTuple
from urllib.parse import parse_qs, unquote, urlparse

import polars as pl
import pytest

from tests.provider.metno.frost.catalogue_rows import EXPECTED, SERIES, SOURCES, is_series_listing, is_sources_listing
from wetterdienst import Settings
from wetterdienst.exceptions import CredentialRejectedError, DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.network import File

UTC = dt.UTC
AUTH = {"metno_frost": ("stub-client", "stub-secret")}
FAILURES = [
    pytest.param(TimeoutError(), 408, id="timeout"),
    pytest.param(OSError("503 Service Unavailable"), 503, id="server-error"),
    pytest.param(FileNotFoundError("404 Not Found"), 404, id="not-found"),
]


def _ok(url: str, payload: dict) -> File:
    return File(url=url, content=BytesIO(json.dumps(payload).encode()), status=200)


class Failure(NamedTuple):
    """An answer that is no body: the exception a failed download stores, and its status."""

    error: Exception
    status: int


class Upstream:
    """The two requests of the catalogue, answered as given, and every request made to them kept."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        sources: dict | Failure | None = None,
        series: dict | Failure | None = None,
    ) -> None:
        """Serve the rows of the stub, or the answer given for either request, and keep what is asked."""
        self.calls: list[dict[str, Any]] = []
        self._sources = SOURCES if sources is None else sources
        self._series = SERIES if series is None else series
        monkeypatch.setattr(frost_api, "download_file", self._download)

    def _download(self, *, url: str, **kwargs: Any) -> File:  # noqa: ANN401
        self.calls.append({"url": url, **kwargs})
        for matches, answer in ((is_sources_listing, self._sources), (is_series_listing, self._series)):
            if matches(url):
                if isinstance(answer, Failure):
                    return File(url=url, content=answer.error, status=answer.status)
                return _ok(url, answer)
        msg = f"the stub serves nothing for {url}"
        raise AssertionError(msg)

    def urls(self, matches: Any) -> list[str]:  # noqa: ANN401
        """Give the requests that were made for the sources or the series."""
        return [call["url"] for call in self.calls if matches(call["url"])]

    def kwargs(self, matches: Any) -> dict[str, Any]:  # noqa: ANN401
        """Give the arguments of the one request made for the sources or the series."""
        (call,) = (call for call in self.calls if matches(call["url"]))
        return call


def _request(**options: Any) -> MetnoFrostRequest:  # noqa: ANN401
    return MetnoFrostRequest(
        parameters=[("daily", "data", "precipitation_amount")],
        settings=Settings(cache_disable=True, auth=AUTH),
        **options,
    )


def _catalogue() -> pl.DataFrame:
    return _request()._all().collect()  # noqa: SLF001


def _span(df: pl.DataFrame, station_id: str) -> tuple[dt.datetime | None, dt.datetime | None]:
    (row,) = df.filter(pl.col("station_id") == station_id).iter_rows(named=True)
    return row["start_timestamp"], row["end_timestamp"]


def _day(text: str | None) -> dt.datetime | None:
    """Give a day as the catalogue reads it before the core makes it UTC: a naive datetime."""
    return None if text is None else dt.datetime.fromisoformat(text)


@pytest.mark.parametrize(("station_id", "expected"), EXPECTED.items())
def test_a_station_starts_and_ends_with_its_declared_series(
    monkeypatch: pytest.MonkeyPatch, station_id: str, expected: tuple[str, str | None]
) -> None:
    """Test the start and the end of each station of the stub, each of which shows one rule of them.

    - `SN18700`: the source starts in 1931 and its series in 1937, so the source's start stands, and a series that is
      open leaves no end although another has ended
    - `SN99700`: the series begins in 1895, 61 years before the source, and ends in 1956 where the source is open
    - `SN18702`: the source ends before its series do, so the series' end stands
    - `SN57990`: a source that is closed, with series that are open: no end
    - `SN12240`: the one declared series ended, the series that are open are of an element or resolution that no dataset
      declares: it has ended
    - `SN76840`: no declared series, so the source's span stands
    """
    Upstream(monkeypatch)

    start, end = _span(_catalogue(), station_id)

    assert (start, end) == (_day(expected[0]), _day(expected[1]))


def test_the_closed_stations_are_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the sources are asked with a `validtime` from before the first station to now, and all are listed.

    Without it Frost answers the stations valid now only (2,234 of the 4,179 of 2026-11-07), and `ids=` of a closed
    station is a 404 either way, so the catalogue is the only way to one.
    """
    upstream = Upstream(monkeypatch)

    stations = _catalogue()

    (url,) = upstream.urls(is_sources_listing)
    assert parse_qs(urlparse(url).query)["validtime"] == ["1700-01-01/now"]
    assert stations["station_id"].to_list() == [source["id"] for source in SOURCES["data"]]
    # closed at its source (SN18702, SN76840) and at its series (SN99700)
    assert {"SN18702", "SN76840", "SN99700"} <= set(stations["station_id"])


def test_the_series_are_asked_over_the_declared_elements_and_resolutions_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the series request names every declared element and resolution, and nothing else, once."""
    upstream = Upstream(monkeypatch)

    _catalogue()

    (url,) = upstream.urls(is_series_listing)
    query = parse_qs(unquote(urlparse(url).query))
    declared = [
        (parameter.name_original, resolution.name_original)
        for resolution in MetnoFrostRequest.metadata
        for dataset in resolution.datasets
        for parameter in dataset.parameters
    ]
    assert sorted(query["elements"][0].split(",")) == sorted({element for element, _ in declared})
    assert sorted(query["timeresolutions"][0].split(",")) == sorted({resolution for _, resolution in declared})
    assert query["fields"] == ["sourceId,validFrom,validTo,timeResolution,elementId"]


def test_the_series_listing_is_cached_like_the_catalogue_and_waits_for_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the listing is kept as long as the sources are, and read with a timeout longer than the default.

    The server takes about 30 s for it (2026-11-07), 8 of them before it sends, so a stall of the default 30 s between
    two reads is no outage. A timeout that the caller set higher stays.
    """
    upstream = Upstream(monkeypatch)

    _catalogue()

    series = upstream.kwargs(is_series_listing)
    sources = upstream.kwargs(is_sources_listing)
    assert series["ttl"] is sources["ttl"] is CacheExpiry.METAINDEX
    assert series["client_kwargs"]["timeout"] == frost_api._SERIES_TIMEOUT  # noqa: SLF001
    assert sources["client_kwargs"]["timeout"] < frost_api._SERIES_TIMEOUT  # noqa: SLF001
    assert series["client_kwargs"]["headers"]["Authorization"] == sources["client_kwargs"]["headers"]["Authorization"]

    upstream = Upstream(monkeypatch)
    settings = Settings(cache_disable=True, auth=AUTH, fsspec_client_kwargs={"timeout": 600})
    MetnoFrostRequest(parameters=[("daily", "data")], settings=settings)._all().collect()  # noqa: SLF001
    assert upstream.kwargs(is_series_listing)["client_kwargs"]["timeout"] == 600


def test_a_series_of_a_station_that_is_no_source_of_the_list_is_not_a_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `SN6030`, which has a declared series and no source (58 such stations on 2026-11-07), is not listed."""
    Upstream(monkeypatch)

    assert "SN6030" in {row["sourceId"].split(":")[0] for row in SERIES["data"]}
    assert "SN6030" not in _catalogue()["station_id"].to_list()


def test_a_series_is_a_station_by_its_id_without_the_sensor_system(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the listing's `SN99700:0` is the station `SN99700`, and the id the catalogue lists has no suffix."""
    Upstream(monkeypatch)

    assert all(":" not in station_id for station_id in _catalogue()["station_id"])
    assert _span(_catalogue(), "SN99700")[0] == dt.datetime(1895, 7, 7)  # noqa: DTZ001


def test_a_series_of_another_resolution_of_a_declared_element_does_not_open_the_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the pair of element and resolution decides, as `air_temperature` is declared hourly and not at 10 min.

    `SN12240` has an `air_temperature` series at PT10M that is open. Read by the element's name alone it would hold the
    station open, where its only declared series has ended.
    """
    Upstream(monkeypatch)
    opens = [row for row in SERIES["data"] if row["sourceId"] == "SN12240:0" and "validTo" not in row]
    assert {(row["elementId"], row["timeResolution"]) for row in opens} >= {("air_temperature", "PT10M")}

    assert _span(_catalogue(), "SN12240")[1] == dt.datetime(2026, 8, 31)  # noqa: DTZ001


def test_the_stations_keep_the_order_of_the_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that reading the series changes no row of the list but its span: the same ids in the same order."""
    Upstream(monkeypatch)

    assert _catalogue()["station_id"].to_list() == [source["id"] for source in SOURCES["data"]]


def test_a_source_without_a_validto_and_series_without_one_read_as_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a listing in which no series has a `validTo` at all: the key is missing, and every station is open."""
    series = {"data": [{k: v for k, v in row.items() if k != "validTo"} for row in SERIES["data"]]}
    Upstream(monkeypatch, series=series)

    stations = _catalogue()

    assert stations.filter(pl.col("station_id") == "SN99700")["end_timestamp"].to_list() == [None]


def test_no_series_is_asked_for_a_list_without_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an empty list of sources is answered as it was, without the 30 s request for the series."""
    upstream = Upstream(monkeypatch, sources={"data": []})

    assert _request()._all().collect().is_empty()  # noqa: SLF001
    assert upstream.urls(is_series_listing) == []


@pytest.mark.parametrize(("error", "status"), FAILURES)
def test_a_failed_series_request_is_raised_and_no_catalogue_is_made_of_the_sources_alone(
    monkeypatch: pytest.MonkeyPatch, error: Exception, status: int
) -> None:
    """Test that a timeout, a 5xx or a 404 of the series listing raises a `DownloadError`, not a list of source dates.

    Read as no series, every station would keep the span its source gives it, and the catalogue would be wrong without
    a word. Even a 404 is an outage here: the listing is one required file, as the sources are.
    """
    Upstream(monkeypatch, series=Failure(error, status))

    with pytest.raises(DownloadError, match="availableTimeSeries") as excinfo:
        _catalogue()

    assert excinfo.value.__cause__ is error


def test_a_series_request_without_a_connection_raises_no_internet_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a connection that cannot be made is raised as it is, where the sources came but the series did not."""
    error = NoInternetError("offline")
    Upstream(monkeypatch, series=Failure(error, 503))

    with pytest.raises(NoInternetError) as excinfo:
        _catalogue()

    assert excinfo.value is error


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_series_request_is_a_rejected_credential(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """Test that a 401 or 403 on the series is the `CredentialRejectedError` the sources raise, not a download error."""
    Upstream(monkeypatch, series=Failure(OSError(str(status)), status))

    with pytest.raises(CredentialRejectedError):
        _catalogue()


@pytest.mark.parametrize("body", [{"data": []}, {"data": None}, {}, {"data": [None]}])
def test_an_answer_with_no_series_at_all_is_raised(monkeypatch: pytest.MonkeyPatch, body: dict) -> None:
    """Test that a 200 without a series is raised: with the sources there, series are, and none is a wrong answer."""
    Upstream(monkeypatch, series=body)

    with pytest.raises(DownloadError, match="no time series"):
        _catalogue()


def test_a_failed_sources_request_asks_nothing_more(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the sources come first: where they fail, the series request of 30 s is not made."""
    upstream = Upstream(monkeypatch, sources=Failure(OSError("503"), 503))

    with pytest.raises(DownloadError):
        _catalogue()

    assert upstream.urls(is_series_listing) == []


def test_a_window_before_1956_finds_the_station_whose_data_begins_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the window of the name search is held to the span of the series: 1900 finds `SN99700`, 2020 does not.

    `SN99700`'s source starts in 1956, which the window of 1900 would have left it out for, and ends in 1956 where the
    source says nothing.
    """
    Upstream(monkeypatch)
    request = _request(start=dt.datetime(1900, 1, 1, tzinfo=UTC), end=dt.datetime(1900, 1, 10, tzinfo=UTC))
    in_1900 = request.filter_by_name("BJØRNØYA", rank=5).df["station_id"].to_list()
    request = _request(start=dt.datetime(2020, 1, 1, tzinfo=UTC), end=dt.datetime(2020, 1, 10, tzinfo=UTC))
    in_2020 = request.filter_by_name("BJØRNØYA", rank=5).df["station_id"].to_list()

    assert in_1900 == ["SN99700"]
    assert in_2020 == []


def test_the_walk_asks_for_a_station_whose_data_begins_before_its_source_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the values of `SN99700` for 1900 are asked for and read, where the core would skip the station.

    The core leaves a station out of a walk when its `start_timestamp` is after the window (`_begins_after_window`):
    with the source's 1956 that was the case, and the days of 1895-1956 were out of reach.
    """
    upstream = Upstream(monkeypatch)
    observations = {
        "data": [
            {
                "sourceId": "SN99700:0",
                "referenceTime": f"1900-01-0{day}T00:00:00.000Z",
                "observations": [
                    {"elementId": "sum(precipitation_amount P1D)", "value": float(day), "timeOffset": "PT6H"}
                ],
            }
            for day in (1, 2, 3)
        ]
    }
    asked: list[str] = []

    def download(*, url: str, **kwargs: Any) -> File:  # noqa: ANN401
        if is_sources_listing(url) or is_series_listing(url):
            return upstream._download(url=url, **kwargs)  # noqa: SLF001
        asked.append(url)
        return _ok(url, observations)

    monkeypatch.setattr(frost_api, "download_file", download)
    request = _request(start=dt.datetime(1900, 1, 1, tzinfo=UTC), end=dt.datetime(1900, 1, 3, tzinfo=UTC))

    values = request.filter_by_station_id("SN99700").values().all()

    assert values.df["timestamp"].dt.date().to_list() == [dt.date(1900, 1, day) for day in (1, 2, 3)]
    assert values.df["value"].to_list() == [1.0, 2.0, 3.0]
    assert [parse_qs(urlparse(url).query)["sources"] for url in asked] == [["SN99700"]]
