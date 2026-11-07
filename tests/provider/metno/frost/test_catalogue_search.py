# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A search by place with a window leaves out the stations that closed before it, for Frost (GH-3847).

The catalogue lists the closed stations, and the end of a station is that of its last declared series, which does not
lag a station that is still reporting. So a rank, distance or box search with a window looks among the stations with a
record in it: a closed station is not counted against `WD_RESTAPI_MAX_STATIONS` or `max_rows`, and the walk of a rank
does not ask Frost for it, three times each, before the first station in service. Without a window the whole list is
searched, closed stations included, and a search by id or by SQL looks among the whole list whatever the window.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from tests.provider.metno.frost.catalogue_rows import Upstream, is_series_listing, is_sources_listing, ok
from wetterdienst import Settings
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.ui import restapi
from wetterdienst.util.network import File

UTC = dt.UTC
AUTH = {"metno_frost": ("stub-client", "stub-secret")}
# Blindern, where SN18700 is in service and SN18702 closed in 1996 (the two are 40 m apart)
BLINDERN = (59.9423, 10.72)
OCTOBER_2026 = {"start": dt.datetime(2026, 10, 1, tzinfo=UTC), "end": dt.datetime(2026, 10, 31, tzinfo=UTC)}
IN_1990 = {"start": dt.datetime(1990, 7, 1, tzinfo=UTC), "end": dt.datetime(1990, 7, 31, tzinfo=UTC)}
OBSERVATION = {
    "data": [
        {
            "sourceId": "SN18700:0",
            "referenceTime": "2026-10-05T00:00:00.000Z",
            "observations": [{"elementId": "sum(precipitation_amount P1D)", "value": 1.0, "timeOffset": "PT6H"}],
        }
    ]
}


def _request(**window: dt.datetime) -> MetnoFrostRequest:
    return MetnoFrostRequest(
        parameters=[("daily", "data", "precipitation_amount")],
        settings=Settings(cache_disable=True, auth=AUTH),
        **window,
    )


def _ids(stations: Any) -> list[str]:  # noqa: ANN401
    return stations.df["station_id"].unique(maintain_order=True).to_list()


def _serve_observations(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve the catalogue and one reading of SN18700 for any request of values, and give the stations asked for."""
    upstream = Upstream(monkeypatch)
    asked: list[str] = []

    def download(*, url: str, **kwargs: Any) -> File:  # noqa: ANN401
        if is_sources_listing(url) or is_series_listing(url):
            return upstream._download(url=url, **kwargs)  # noqa: SLF001
        station = parse_qs(urlparse(url).query)["sources"][0].split(":")[0]
        asked.append(station)
        if station == "SN18700" and "availableTimeSeries" not in url:
            return ok(url, OBSERVATION)
        return File(url=url, content=FileNotFoundError(url), status=404)

    monkeypatch.setattr(frost_api, "download_file", download)
    return asked


def test_a_box_with_a_window_holds_the_stations_with_a_record_in_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a box around Blindern for October 2026 has SN18700 and not SN18702, which closed in 1996."""
    Upstream(monkeypatch)

    in_2026 = _ids(_request(**OCTOBER_2026).filter_by_bbox(10.0, 59.0, 11.0, 60.5))
    in_1990 = _ids(_request(**IN_1990).filter_by_bbox(10.0, 59.0, 11.0, 60.5))

    assert "SN18700" in in_2026
    assert "SN18702" not in in_2026
    assert {"SN18700", "SN18702"} <= set(in_1990)


def test_a_distance_with_a_window_holds_the_stations_with_a_record_in_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that 5 km around Blindern for October 2026 is SN18700, and for July 1990 SN18700 and SN18702."""
    Upstream(monkeypatch)

    in_2026 = _ids(_request(**OCTOBER_2026).filter_by_distance(BLINDERN, 5))
    in_1990 = _ids(_request(**IN_1990).filter_by_distance(BLINDERN, 5))

    assert in_2026 == ["SN18700"]
    assert sorted(in_1990) == ["SN18700", "SN18702"]


def test_a_rank_with_a_window_ranks_the_stations_with_a_record_in_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the ranking at SN18702's own position puts SN18700 first for October 2026, SN18702 for July 1990."""
    Upstream(monkeypatch)

    in_2026 = _ids(_request(**OCTOBER_2026).filter_by_rank((59.9427, 10.72), rank=1))
    in_1990 = _ids(_request(**IN_1990).filter_by_rank((59.9427, 10.72), rank=1))

    assert in_2026[0] == "SN18700"
    assert "SN18702" not in in_2026
    assert in_1990[0] == "SN18702"


def test_a_rank_walk_never_asks_for_a_station_that_closed_before_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that rank 1 at SN18702's position for October 2026 asks Frost for SN18700 alone.

    SN18702 is the nearest station and closed in 1996. Walked, it is asked for three times (the batch, the parameter,
    the discovery of its series) before the station in service is, and a catalogue of 4,179 stations has ten such
    stations before the first in service at Oslo.
    """
    asked = _serve_observations(monkeypatch)

    values = _request(**OCTOBER_2026).filter_by_rank((59.9427, 10.72), rank=1).values().all()

    assert values.df["station_id"].unique().to_list() == ["SN18700"]
    assert set(asked) == {"SN18700"}


def test_a_search_without_a_window_looks_among_the_whole_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that without a window a distance, a rank and a box find the closed stations, as there is nothing to cut by.

    The values of Frost need a window, so this is the listing of `stations` alone, with the dates of each station.
    """
    Upstream(monkeypatch)
    request = _request()

    assert sorted(_ids(request.filter_by_distance(BLINDERN, 5))) == ["SN18700", "SN18702"]
    assert {"SN18700", "SN18702"} <= set(_ids(request.filter_by_rank(BLINDERN, rank=2)))
    assert {"SN18700", "SN18702"} <= set(_ids(request.filter_by_bbox(10.0, 59.0, 11.0, 60.5)))


def test_a_search_by_id_or_sql_keeps_the_closed_stations_whatever_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the stations asked for by id or by SQL are found though they closed before the window."""
    Upstream(monkeypatch)
    request = _request(**OCTOBER_2026)

    assert _ids(request.filter_by_station_id("SN18702")) == ["SN18702"]
    assert _ids(request.filter_by_sql("station_id = 'SN99700'")) == ["SN99700"]


def test_the_rest_values_of_a_distance_do_not_count_the_stations_that_closed_before_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a values request by distance at Blindern for October 2026 reads one station, not two.

    With the closed station counted it was a 400 "reads 2 stations" against `WD_RESTAPI_MAX_STATIONS=1`: 163 against
    85 for 25 km around Oslo on 2026-11-07, where the list before the closed stations answered 200.
    """
    monkeypatch.setenv("WD_AUTH__METNO_FROST", json.dumps(["stub-client", "stub-secret"]))
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "1")
    asked = _serve_observations(monkeypatch)

    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/values",
        params={
            "provider": "metno",
            "network": "frost",
            "parameters": "daily/data/precipitation_amount",
            "latitude": BLINDERN[0],
            "longitude": BLINDERN[1],
            "distance": 5,
            "timestamp": "2026-10-01/2026-10-31",
        },
    )

    assert response.status_code == 200, response.text
    assert {row["station_id"] for row in response.json()["values"]} == {"SN18700"}
    assert set(asked) == {"SN18700"}


def test_the_same_request_for_a_window_that_holds_both_is_refused_by_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the control of the one above: July 1990 holds both stations, and the limit of 1 refuses it."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", json.dumps(["stub-client", "stub-secret"]))
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "1")
    _serve_observations(monkeypatch)

    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/values",
        params={
            "provider": "metno",
            "network": "frost",
            "parameters": "daily/data/precipitation_amount",
            "latitude": BLINDERN[0],
            "longitude": BLINDERN[1],
            "distance": 5,
            "timestamp": "1990-07-01/1990-07-31",
        },
    )

    assert response.status_code == 400


@pytest.mark.parametrize("estimate", ["interpolate", "summarize"])
def test_an_estimate_never_asks_for_a_station_that_closed_before_the_window(
    monkeypatch: pytest.MonkeyPatch, estimate: str
) -> None:
    """Test that `interpolate` and `summarize` at SN18702's position for October 2026 ask Frost for SN18700 alone.

    The library estimates reach `filter_by_rank` with the station list they hold already (`df_all`), which the hook
    narrows to the window as well: a hook that only a list built by the rank itself passes through leaves the closed
    stations to be asked (24 stations, 15 of them closed, around Oslo on 2026-11-07).
    """
    asked = _serve_observations(monkeypatch)

    getattr(_request(**OCTOBER_2026), estimate)((59.9427, 10.72))

    assert asked
    assert set(asked) == {"SN18700"}
