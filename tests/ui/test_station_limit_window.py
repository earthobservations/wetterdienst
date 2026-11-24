# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The size of a request counts the stations with data in its window, whichever way they were selected (GH-4418).

A box over Hamburg and the North Sea was refused as 114 stations, of which 30 had data in a day of 2022: the limit
read every station the selection lists, not the ones the request reads. The station list says when each station's
record begins and ends, and a station whose record is over (or has not begun) has nothing to read in the window, as
the stations listing and the name search already hold (`limit_to_window`). A bound the list does not publish, and an
end that lags a station that is still reporting, never leave a station out: the count is an upper bound, never short
of what is read.

Served from memory, so nothing leaves the machine.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import polars as pl
import pytest
from fastapi.testclient import TestClient

from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui.limits import estimate_rows, selected_station_count
from wetterdienst.ui.restapi import app

PARAMETER = "daily/kl/temperature_air_mean_2m"
_SELECTION = {"provider": "dwd", "network": "observation", "parameters": PARAMETER}
DAY = "2022-02-18"
_BOX = {"left": "6", "bottom": "53", "right": "11", "top": "56"}


def _utc(year: int, month: int, day: int) -> dt.datetime:
    return dt.datetime(year, month, day, tzinfo=dt.UTC)


#: (how many, start, end, in the window of 2022-02-18): the 114 stations of a box and what the list says of each record
_RECORDS: list[tuple[int, dt.datetime | None, dt.datetime | None, bool]] = [
    # closed long before the window
    (20, _utc(1950, 1, 1), _utc(2010, 12, 31), False),
    # closed eight days before it: more than the two days a catalogue's end lags
    (64, _utc(1990, 1, 1), _utc(2022, 2, 10), False),
    # began after it
    (0, _utc(2023, 1, 1), None, False),
    # still reporting: the end is a day or so behind, or the list publishes none
    (10, _utc(1990, 1, 1), _utc(2026, 11, 23), True),
    (8, _utc(1990, 1, 1), None, True),
    # no start published: nothing is said, so the station is kept
    (4, None, _utc(2026, 11, 23), True),
    # closed the day before the window, and two days before it: inside the lag of the end, so kept
    (4, _utc(1990, 1, 1), _utc(2022, 2, 17), True),
    (4, _utc(1990, 1, 1), _utc(2022, 2, 16), True),
]
IN_THE_WINDOW = sum(count for count, _, _, inside in _RECORDS if inside)
LISTED = sum(count for count, *_ in _RECORDS)
#: the ids of the stations with data in the window, as `_RECORDS` numbers them
IDS_IN_THE_WINDOW = {
    f"{number:05d}"
    for number, inside in enumerate(inside for count, _, _, inside in _RECORDS for _ in range(count))
    if inside
}


def _list_of_stations() -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for count, start, end, _inside in _RECORDS:
        for _ in range(count):
            number = len(rows)
            rows.append(
                {
                    "resolution": "daily",
                    "dataset": "climate_summary",
                    "station_id": f"{number:05d}",
                    "name": f"Station {number}",
                    "region": "Hamburg" if number % 2 else "Bremen",
                    "latitude": 54.0 + (number % 10) * 0.1,
                    "longitude": 7.0 + (number % 7) * 0.1,
                    "elevation": 10.0,
                    "start_timestamp": start,
                    "end_timestamp": end,
                }
            )
    return pl.DataFrame(
        rows,
        schema_overrides={
            "start_timestamp": pl.Datetime("us", "UTC"),
            "end_timestamp": pl.Datetime("us", "UTC"),
            "region": pl.String,
        },
    )


@pytest.fixture(autouse=True)
def collected(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve the list from memory, and note the stations whose values are collected."""
    stations = _list_of_stations()
    assert stations.height == LISTED == 114
    assert IN_THE_WINDOW == 30
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())
    reads: list[str] = []

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        reads.append(station_id)
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        names = [parameter.name_original for parameter in dataset]
        return pl.DataFrame(
            {
                "timestamp": [_utc(2022, 2, 18)] * len(names),
                "parameter": names,
                "value": [1.0] * len(names),
                "quality_flags": ["1"] * len(names),
                "resolution": ["daily"] * len(names),
                "dataset": [dataset.name] * len(names),
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    return reads


def _values(**query: str) -> Any:  # noqa: ANN401
    return TestClient(app).get("/api/values", params={**_SELECTION, **query})


def _request(**kwargs: Any) -> DwdObservationRequest:  # noqa: ANN401
    return DwdObservationRequest(parameters=PARAMETER, settings=Settings(), **kwargs)


# the analysis' box: 114 stations, 30 with data in the window of one day


def test_the_box_of_114_stations_is_read_for_the_30_that_have_data_in_the_window(collected: list[str]) -> None:
    """Refused as 114 without a window, answered as 30 with one: the limit is 100."""
    refused = _values(**_BOX)
    assert refused.status_code == 400, refused.text
    assert refused.json()["type"] == "urn:wetterdienst:problem:limit-exceeded"
    assert (refused.json()["limit"], refused.json()["requested"]) == ("stations", 114)
    assert collected == []

    answered = _values(**_BOX, timestamp=DAY)

    assert answered.status_code == 200, answered.text
    assert set(collected) >= IDS_IN_THE_WINDOW


def test_the_refusal_without_a_window_counts_every_station_of_the_box() -> None:
    """No window, no station to leave out: the number is the list's."""
    response = _values(**_BOX)

    assert response.status_code == 400, response.text
    assert (response.json()["limit"], response.json()["requested"]) == ("stations", 114)


@pytest.mark.parametrize(
    "selection",
    [
        pytest.param({"all": "true"}, id="all"),
        pytest.param(_BOX, id="a-box"),
        pytest.param({"stations": ",".join(f"{number:05d}" for number in range(114))}, id="ids"),
        pytest.param({"latitude": "54.5", "longitude": "7.3", "distance": "300"}, id="a-distance"),
    ],
)
def test_every_selection_counts_only_the_stations_with_data_in_the_window(selection: dict[str, str]) -> None:
    """A box, the whole list, ids and a distance: refused for 114, answered for the 30 of a day of 2022."""
    assert _values(**selection).status_code == 400
    assert _values(**selection, timestamp=DAY).status_code == 200


def test_a_region_counts_only_the_stations_with_data_in_the_window() -> None:
    """The stations of a region are those of the list; the window leaves out the ones that closed."""
    stations = _request(start=DAY, end=DAY).filter_by_region("Hamburg")
    hamburg = set(stations.df.get_column("station_id"))

    assert len(hamburg) == 57
    assert selected_station_count(stations) == len(hamburg & IDS_IN_THE_WINDOW)
    assert 0 < len(hamburg & IDS_IN_THE_WINDOW) < 57
    refused = _values(region="Hamburg,Bremen")
    assert refused.status_code == 400
    assert _values(region="Hamburg,Bremen", timestamp=DAY).status_code == 200


def test_a_ranked_selection_is_its_rank_among_the_stations_with_data_in_the_window() -> None:
    """A rank reads that many stations, and no more than the list has with data in the window."""
    ranked = _request(start=DAY, end=DAY).filter_by_rank((54.0, 7.0), rank=500)

    assert ranked.df.get_column("station_id").n_unique() == 114
    assert selected_station_count(ranked) == IN_THE_WINDOW
    assert selected_station_count(_request(start=DAY, end=DAY).filter_by_rank((54.0, 7.0), rank=5)) == 5


# never short: a station whose end is unknown or recent is counted


@pytest.mark.parametrize(
    ("start", "end", "counted"),
    [
        pytest.param(_utc(1990, 1, 1), None, True, id="no-end-published"),
        pytest.param(None, None, True, id="no-record-published"),
        pytest.param(None, _utc(2010, 1, 1), False, id="no-start-and-closed-long-before"),
        pytest.param(_utc(1990, 1, 1), _utc(2026, 11, 23), True, id="reporting-yesterday"),
        pytest.param(_utc(1990, 1, 1), _utc(2022, 2, 18), True, id="closed-on-the-day"),
        pytest.param(_utc(1990, 1, 1), _utc(2022, 2, 17), True, id="closed-the-day-before-inside-the-lag"),
        pytest.param(_utc(1990, 1, 1), _utc(2022, 2, 16), True, id="closed-two-days-before-the-lag-of-a-daily-end"),
        pytest.param(_utc(1990, 1, 1), _utc(2022, 2, 15), False, id="closed-three-days-before"),
        pytest.param(_utc(2022, 2, 18), None, True, id="began-on-the-day"),
        pytest.param(_utc(2022, 2, 19), None, False, id="began-the-day-after"),
    ],
)
def test_the_bounds_of_a_record_leave_a_station_out_only_where_the_list_says_it_has_nothing(
    monkeypatch: pytest.MonkeyPatch,
    start: dt.datetime | None,
    end: dt.datetime | None,
    counted: bool,  # noqa: FBT001
) -> None:
    """The count of one station by the rule of `limit_to_window`: a bound the list does not publish says nothing."""
    one = (
        _list_of_stations()
        .head(1)
        .with_columns(
            pl.lit(start, pl.Datetime("us", "UTC")).alias("start_timestamp"),
            pl.lit(end, pl.Datetime("us", "UTC")).alias("end_timestamp"),
        )
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: one.lazy())

    stations = _request(start=DAY, end=DAY).all()

    assert selected_station_count(stations) == int(counted)
    # the rows are held to the same rule, and where a station is counted it is not counted as nothing
    assert (estimate_rows(stations) > 0) is counted


def test_the_buffer_of_the_request_is_the_lag_of_the_end() -> None:
    """`station_window_end_buffer` says how far an end may be before the window for a station to be kept: 0 is exact."""
    one = (
        _list_of_stations()
        .head(1)
        .with_columns(
            pl.lit(_utc(1990, 1, 1), pl.Datetime("us", "UTC")).alias("start_timestamp"),
            pl.lit(_utc(2022, 2, 10), pl.Datetime("us", "UTC")).alias("end_timestamp"),
        )
    )

    def counted(buffer: int | None) -> tuple[int, int]:
        request = _request(
            start=DAY, end=DAY, options={"station_window_end_buffer": buffer} if buffer is not None else None
        )
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(DwdObservationRequest, "_all", lambda _self: one.lazy())
            stations = request.all()
        return selected_station_count(stations), estimate_rows(stations)

    assert counted(None)[0] == 0
    assert counted(7)[0] == 0
    assert counted(8) == (1, 1)
    assert counted(3660) == (1, 1)


def test_the_monthly_and_annual_ends_lag_by_more_so_a_station_of_either_is_kept_longer() -> None:
    """62 days for a monthly list and 732 for an annual one: the lag of the resolution, as the listing has it."""
    from wetterdienst.model.request import end_lag  # noqa: PLC0415

    assert end_lag("daily") == dt.timedelta(days=2)
    assert end_lag("hourly") == dt.timedelta(days=2)
    assert end_lag("monthly") == dt.timedelta(days=62)
    assert end_lag("annual") == dt.timedelta(days=732)
    assert end_lag("annual", 0) == dt.timedelta(0)
    assert end_lag("daily", 30) == dt.timedelta(days=30)


# the rows follow the same stations, and are never short of what a station kept by the lag may hold


def test_the_rows_of_a_station_that_closed_the_day_before_are_not_counted_as_none() -> None:
    """Inside the lag the station may still be reporting: its day of the window is counted, an upper bound."""
    one = (
        _list_of_stations()
        .head(1)
        .with_columns(
            pl.lit(_utc(1990, 1, 1), pl.Datetime("us", "UTC")).alias("start_timestamp"),
            pl.lit(_utc(2022, 2, 17), pl.Datetime("us", "UTC")).alias("end_timestamp"),
        )
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(DwdObservationRequest, "_all", lambda _self: one.lazy())
        stations = _request(start=DAY, end=DAY).all()

    assert estimate_rows(stations) == 1


def test_the_rows_of_the_box_are_those_of_the_stations_with_data() -> None:
    """30 stations of one day of one parameter: 30 rows, as the stations that are left out add none."""
    stations = _request(start=DAY, end=DAY).filter_by_bbox(6.0, 53.0, 11.0, 56.0)

    assert stations.df.get_column("station_id").n_unique() == 114
    assert selected_station_count(stations) == IN_THE_WINDOW
    assert estimate_rows(stations) == IN_THE_WINDOW


def test_a_request_without_a_window_counts_the_whole_list() -> None:
    """No window: nothing is left out, the rows are those of each record."""
    stations = _request().filter_by_bbox(6.0, 53.0, 11.0, 56.0)

    assert selected_station_count(stations) == 114


def test_the_history_limit_counts_the_stations_asked_for_without_a_window() -> None:
    """History takes no window, so the stations it reads are those it names."""
    response = TestClient(app).get("/api/history", params={**_SELECTION, "all": "true"})

    assert response.status_code == 400, response.text
    assert (response.json()["limit"], response.json()["requested"]) == ("stations", 114)
