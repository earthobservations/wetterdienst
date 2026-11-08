# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An estimate tells the values of an open window it left out, as a cause of `source-data-left-out` (GH-3883).

Frost serves the value of a day, month or year that has not closed and marks nothing. `values` leaves a daily one out
and returns a monthly or annual one marked `completeness:Incomplete` (GH-3856). An estimate cannot carry that mark, so
it leaves the monthly and annual value of an open window out too, and tells all of them as a fourth cause of its one
warning, beside a file the provider could not use, dates of another series and values a plausibility check rejected.

Nothing here reaches the network: Frost is served from stubs and the clock is `frost_api._now`.
"""

from __future__ import annotations

import datetime as dt
import threading
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.provider.metno.frost.catalogue_rows import is_series_listing, series_of
from tests.provider.metno.frost.test_values_failures import SOURCES, _answered_by, _offset_answer, _ok
from tests.ui.test_empty_listing import _DESCRIPTION, dwd  # noqa: F401
from tests.ui.test_estimate_left_out import (
    _DWD_POINT,
    _FROST_POINT,
    ESTIMATES,
    _dwd_request,
    _summary,
    _surfaces,
    _twelve_stations,
)
from wetterdienst import Settings
from wetterdienst.model.parameter_rows import MAX_STATIONS_LISTED, EstimateLeftOut, ParameterRows
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.response_warnings import (
    SOURCE_DATA_LEFT_OUT,
    SkipCause,
    begin_response,
    note_open_window,
    recorded_warnings,
)

if TYPE_CHECKING:
    from tests.ui.test_empty_listing import _Dwd
    from wetterdienst.util.network import File

UTC = dt.UTC
HOUR = dt.timedelta(hours=1)
#: the time of every request: 10:00 UTC on 2026-11-07, when the day, the month and the year are open
NOW = dt.datetime(2026, 11, 7, 10, tzinfo=UTC)
MINUTE_BEFORE_CLOSING = {
    "daily": dt.datetime(2026, 11, 7, 18, tzinfo=UTC) - dt.timedelta(minutes=1),
}
CLOSED = "window-not-closed"


class Series:
    """What a test serves: the element Frost names, the series, the parameter, the window it asks for and its stamps."""

    def __init__(
        self,
        resolution: str,
        element: str,
        offset: str,
        name: str,
        closed: dt.datetime,
        open_: dt.datetime,
        end: dt.datetime,
    ) -> None:
        """Hold the series: `closed` is the stamp of a window that has closed, `open_` of the one that has not."""
        self.resolution = resolution
        self.element = element
        self.offset = offset
        self.name = name
        self.closed = closed
        self.open_ = open_
        self.end = end

    @property
    def full(self) -> str:
        """Give the name a warning calls the parameter by."""
        return f"{self.resolution}/data/{self.name}"

    @property
    def parameters(self) -> list[tuple[str, str, str]]:
        """Give the parameters of the request."""
        return [(self.resolution, "data", self.name)]


SERIES = [
    pytest.param(
        Series(
            "daily",
            "max(air_temperature P1D)",
            "PT18H",
            "temperature_air_max_2m",
            dt.datetime(2026, 11, 6, tzinfo=UTC),
            dt.datetime(2026, 11, 7, tzinfo=UTC),
            dt.datetime(2026, 11, 7, tzinfo=UTC),
        ),
        "for today",
        id="daily",
    ),
    pytest.param(
        Series(
            "monthly",
            "mean(air_temperature P1M)",
            "PT0H",
            "temperature_air_mean_2m",
            dt.datetime(2026, 10, 1, tzinfo=UTC),
            dt.datetime(2026, 11, 1, tzinfo=UTC),
            dt.datetime(2026, 11, 1, tzinfo=UTC),
        ),
        "for this month",
        id="monthly",
    ),
    pytest.param(
        Series(
            "annual",
            "max(air_temperature P1Y)",
            "PT18H",
            "temperature_air_max_2m",
            dt.datetime(2025, 1, 1, tzinfo=UTC),
            dt.datetime(2026, 1, 1, tzinfo=UTC),
            dt.datetime(2026, 1, 1, tzinfo=UTC),
        ),
        "for this year",
        id="annual",
    ),
]
#: the series without what their window is called, for the tests that do not read it
SERIES_ONLY = [pytest.param(param.values[0], id=param.id) for param in SERIES]
#: the value of the window that has closed and of the one that has not
CLOSED_VALUE, OPEN_VALUE = 5.0, 9.0


def _stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _serve(monkeypatch: pytest.MonkeyPatch, series: Series, *, path: str = "batch", now: dt.datetime = NOW) -> None:
    """Serve Oslo/Blindern with a closed and an open value of the series, at the time `now`, by the reader `path`."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")
    monkeypatch.setenv("WD_CACHE_DISABLE", "1")
    monkeypatch.setattr(frost_api, "_now", lambda: now)
    readings = [
        (_stamp(series.closed), series.offset, CLOSED_VALUE),
        (_stamp(series.open_), series.offset, OPEN_VALUE),
    ]
    available = {
        "data": [
            {
                "validFrom": "1940-01-01T00:00:00Z",
                "timeOffset": series.offset,
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0"
                f"&timeoffsets={series.offset}",
            }
        ]
    }
    observations = _answered_by(path, _offset_answer(series.element, readings), available)

    def download(*, url: str, **_: object) -> File:
        if is_series_listing(url):
            return _ok(url, series_of("SN18700"))
        return _ok(url, SOURCES) if "/sources/" in url else observations(url)

    monkeypatch.setattr(frost_api, "download_file", download)
    monkeypatch.setattr(frost_api, "read_refusal", lambda *_args, **_kwargs: None)


#: a second parameter of the dataset by resolution, whose batched request the stub answers with a 404, so that the
#: reader of one parameter is the one reached
HELPERS = {"monthly": "wind_speed_mean", "annual": "cloud_cover_total_mean"}


def _request(series: Series, *, helper: bool = False) -> MetnoFrostRequest:
    parameters = [*series.parameters, (series.resolution, "data", HELPERS[series.resolution])] if helper else None
    return MetnoFrostRequest(
        parameters=parameters or series.parameters,
        start=series.closed,
        end=series.end,
        settings=Settings(cache_disable=True),
    )


def _codes() -> list[str]:
    return [warning["code"] for warning in recorded_warnings()]


def _closed_and_open_rows(df: pl.DataFrame, series: Series) -> tuple[list[float | None], list[float | None]]:
    """Give the values of the date that has closed and of the one that has not."""
    closed = df.filter(pl.col("timestamp") == series.closed)["value"].to_list()
    open_ = df.filter(pl.col("timestamp") == series.open_)["value"].to_list()
    return closed, open_


# --- does an estimate accept Frost's monthly and annual parameters? Yes: the core asks nothing of the resolution ------


@pytest.mark.parametrize("estimate", ESTIMATES)
@pytest.mark.parametrize("series", SERIES_ONLY[1:])
def test_an_estimate_accepts_a_monthly_and_an_annual_frost_parameter(
    monkeypatch: pytest.MonkeyPatch, series: Series, estimate: str
) -> None:
    """The REST contract names the parameter, and the answer has its rows: a monthly or annual one is estimated."""
    _serve(monkeypatch, series, now=series.end + dt.timedelta(days=400))

    result = getattr(_request(series), estimate)(_FROST_POINT)

    assert {*result.df["resolution"].to_list()} == {series.resolution}
    assert {*result.df["parameter"].to_list()} == {series.name}


# --- the open value is left out of an estimate and told ---------------------------------------------------------------


@pytest.mark.parametrize(("series", "for_"), SERIES)
@pytest.mark.parametrize("estimate", ESTIMATES)
def test_an_estimate_tells_the_values_of_an_open_window_it_left_out(
    monkeypatch: pytest.MonkeyPatch, series: Series, for_: str, estimate: str
) -> None:
    """One value of the day, month or year that has not closed: one warning, with the cause, the station and the count.

    The closing time is told by neither code: `window-not-closed` is the warning of a values request, and the estimate
    tells the cause once, whatever the resolution.
    """
    _serve(monkeypatch, series)
    begin_response()

    getattr(_request(series), estimate)(_FROST_POINT)

    (warning,) = recorded_warnings()
    assert warning["code"] == SOURCE_DATA_LEFT_OUT
    assert warning["stations"] == ["SN18700"]
    message = warning["message"]
    assert "Source data was left out of this estimate at 1 of the 1 stations it read." in message
    assert (
        f"1 value at 1 station (SN18700) was of a window that had not closed yet (1 {for_}) and is left out" in message
    )
    assert (
        "it is partial and may still change, and the source does not mark it. "
        "It is not missing at the source and comes back once the window has closed." in message
    )
    # no other cause is told, and no code of a values request
    assert "Dates of another series" not in message
    assert "plausibility" not in message
    assert "A file the provider could not use" not in message
    assert not {CLOSED, "other-window-left-out", "file-skipped", "parameter-without-rows"} & set(_codes())


@pytest.mark.parametrize("series", SERIES_ONLY)
def test_a_summary_takes_the_value_of_the_window_that_closed_and_none_of_the_open_one(
    monkeypatch: pytest.MonkeyPatch, series: Series
) -> None:
    """The partial value is not in the estimate: the open window's date has no value, the closed one its own."""
    _serve(monkeypatch, series)

    result = _request(series).summarize(_FROST_POINT)

    closed, open_ = _closed_and_open_rows(result.df, series)
    assert closed == [CLOSED_VALUE]
    assert open_ == [None]


@pytest.mark.parametrize("series", SERIES_ONLY)
def test_an_estimate_over_closed_windows_says_nothing(monkeypatch: pytest.MonkeyPatch, series: Series) -> None:
    """A request made after the windows closed has nothing left out, and the warning does not appear."""
    _serve(monkeypatch, series, now=series.end + dt.timedelta(days=400))
    begin_response()

    result = _request(series).summarize(_FROST_POINT)

    assert recorded_warnings() == []
    assert result.df.filter(pl.col("timestamp") == series.open_)["value"].to_list() == [OPEN_VALUE]


@pytest.mark.parametrize("path", ["single", "discovery"])
@pytest.mark.parametrize(("series", "for_"), SERIES[1:])
@pytest.mark.parametrize("estimate", ESTIMATES)
def test_the_single_and_the_discovery_reader_leave_an_open_month_and_year_out_of_an_estimate_too(
    monkeypatch: pytest.MonkeyPatch, series: Series, for_: str, path: str, estimate: str
) -> None:
    """The three readers of Frost agree: the value of an open month or year is not in the estimate and is told."""
    _serve(monkeypatch, series, path=path)
    begin_response()

    result = getattr(_request(series, helper=path == "single"), estimate)(_FROST_POINT)

    (warning,) = recorded_warnings()
    assert warning["code"] == SOURCE_DATA_LEFT_OUT
    assert f"(1 {for_}) and is left out" in warning["message"]
    if estimate == "summarize":
        # and it is not in the answer, which the tally alone would not show
        assert _closed_and_open_rows(result.df, series) == ([CLOSED_VALUE], [None])


def test_several_open_values_are_counted_by_what_the_window_is() -> None:
    """The count says how many values of each window were left out, and is one sentence for all of them."""
    left_out = EstimateLeftOut()
    for station in ("A", "B", "C"):
        left_out.collected(station)
    left_out.open_window("A", "daily/data/temperature_air_max_2m", 1)
    left_out.open_window("A", "daily/data/precipitation_amount", 1)
    left_out.open_window("B", "monthly/data/temperature_air_mean_2m", 1)
    left_out.open_window("C", "annual/data/temperature_air_mean_2m", 1)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A", "B", "C"]
    assert "at 3 of the 3 stations it read." in warning["message"]
    assert (
        "4 values at 3 stations (A, B, C) were of a window that had not closed yet "
        "(2 for today, 1 for this month, 1 for this year) and are left out" in warning["message"]
    )


def test_the_sentence_for_several_open_values_is_in_the_plural() -> None:
    """The tail of the sentence is inflected as its head is: one value is `it` and `comes`, two `they` and `come`."""
    left_out = EstimateLeftOut()
    left_out.collected("A")
    left_out.open_window("A", "daily/data/x", 2)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert (
        "2 values at 1 station (A) were of a window that had not closed yet (2 for today) and are left out: "
        "they are partial and may still change, and the source does not mark them. "
        "They are not missing at the source and come back once the window has closed." in warning["message"]
    )


def test_the_listing_of_open_stations_is_capped_and_the_count_is_whole() -> None:
    """A walk that lost an open window at many stations lists the first ten and counts them all."""
    stations = tuple(f"{number:05d}" for number in range(1, 26))
    left_out = EstimateLeftOut()
    for station in stations:
        left_out.collected(station)
        left_out.open_window(station, "daily/data/temperature_air_max_2m", 1)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == list(stations[:MAX_STATIONS_LISTED])
    assert "at 25 of the 25 stations it read." in warning["message"]
    assert "25 stations (the first 10 of them 00001, " in warning["message"]


def test_the_open_window_is_a_cause_beside_the_others_in_one_warning() -> None:
    """A station that lost a file and one that lost an open value are two of the three the warning counts."""
    left_out = EstimateLeftOut()
    for station in ("A", "B", "C"):
        left_out.collected(station)
    left_out.skipped("A", SkipCause.FAILED, whole_request=False)
    left_out.open_window("B", "monthly/data/temperature_air_mean_2m", 2)
    left_out.rejected("B", 1, {"range": 1})
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A", "B"]
    assert "at 2 of the 3 stations it read." in warning["message"]
    assert "2 values at 1 station (B) were of a window that had not closed yet (2 for this month)" in warning["message"]
    assert "1 values at 1 station (B) were numbers a plausibility check rejected" in warning["message"]
    assert "left out at 1 station (A)" in warning["message"]


def test_an_unknown_resolution_is_the_current_period() -> None:
    """A provider that names another resolution is told as the current period, without a guess."""
    left_out = EstimateLeftOut()
    left_out.collected("A")
    left_out.open_window("A", "weekly/data/x", 1)
    begin_response()

    left_out.warn()

    (warning,) = recorded_warnings()
    assert "(1 for the current period)" in warning["message"]


# --- forget and forget_since undo it --------------------------------------------------------------------------------


def test_forget_leaves_the_open_values_of_a_station_out_of_the_count() -> None:
    """The station the walk stops at is out of the count, the sums and the windows, and a window left empty is gone."""
    left_out = EstimateLeftOut()
    for station in ("A", "B"):
        left_out.collected(station)
    left_out.open_window("A", "daily/data/x", 1)
    left_out.open_window("B", "daily/data/x", 2)
    left_out.open_window("B", "monthly/data/x", 3)
    begin_response()

    left_out.forget("B")
    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A"]
    assert "at 1 of the 1 stations it read." in warning["message"]
    assert "1 value at 1 station (A) was of a window that had not closed yet (1 for today)" in warning["message"]
    assert "this month" not in warning["message"]


def test_forget_of_the_only_station_with_open_values_leaves_no_warning() -> None:
    """Nothing is told when the only station that lost an open window is the one the walk stopped at."""
    left_out = EstimateLeftOut()
    left_out.collected("A")
    left_out.collected("B")
    left_out.open_window("B", "monthly/data/x", 1)
    begin_response()

    left_out.forget("B")
    left_out.warn()

    assert recorded_warnings() == []


def test_forget_since_leaves_out_the_open_values_of_the_stations_read_after_the_mark() -> None:
    """A station read after the last one used, for which the walk was done, takes its open values with it."""
    left_out = EstimateLeftOut()
    left_out.collected("A")
    left_out.open_window("A", "daily/data/x", 1)
    mark = left_out.mark()
    left_out.collected("B")
    left_out.open_window("B", "daily/data/x", 4)
    begin_response()

    left_out.forget_since(mark, lambda station: station == "B")
    left_out.warn()

    (warning,) = recorded_warnings()
    assert warning["stations"] == ["A"]
    assert "1 value at 1 station (A)" in warning["message"]


def test_a_value_the_provider_returned_is_not_counted_by_an_estimate() -> None:
    """Only the values left out are a cause: one returned (marked) is in the answer, and `returned` true is no tally."""
    left_out = EstimateLeftOut()
    left_out.collected("A")
    rows = ParameterRows(_dwd_request(), None, None, enabled=False, left_out=left_out)
    with rows.collecting("A"):
        note_open_window("monthly/data/x", 1, NOW, returned=True)
    begin_response()

    left_out.warn()

    assert recorded_warnings() == []


# --- the station the walk stops at is not counted, through the walk of both estimates ---------------------------------


def _serving_open_values(monkeypatch: pytest.MonkeyPatch, *, opening: set[str] = frozenset()) -> list[str]:
    """Have each station answer three monthly readings, and tell an open window for `opening`; give the order read."""
    read: list[str] = []

    def collect(self: DwdObservationValues, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        read.append(station_id)
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        name = next(parameter.name_original for parameter in dataset if parameter.name == "temperature_air_mean_2m")
        if station_id in opening:
            note_open_window("monthly/climate_summary/temperature_air_mean_2m", 1, NOW, returned=False)
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(2026, month, 1, tzinfo=UTC) for month in (1, 2, 3)],
                "parameter": [name] * 3,
                "value": [10.0, 11.0, 12.0],
                "quality_flags": ["1"] * 3,
                "resolution": ["monthly"] * 3,
                "dataset": [dataset.name] * 3,
            }
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    return read


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_the_station_the_walk_stops_at_does_not_count_its_open_values(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    estimate: str,
) -> None:
    """An estimate reads one station more than it uses; the open window that one lost is no loss to the answer."""
    _twelve_stations(dwd, monkeypatch)
    clean = _serving_open_values(monkeypatch)
    getattr(_dwd_request(), estimate)(_DWD_POINT)
    last = clean[-1]
    assert last != "00055", "the walk read every station: there is no station it stopped at"

    _serving_open_values(monkeypatch, opening={last})
    begin_response()
    getattr(_dwd_request(), estimate)(_DWD_POINT)

    assert _summary() == []


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_a_station_the_walk_used_counts_its_open_values(
    dwd: _Dwd,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    estimate: str,
) -> None:
    """The first station of the walk is used by both estimates, and what it lost is told."""
    _twelve_stations(dwd, monkeypatch)
    clean = _serving_open_values(monkeypatch)
    getattr(_dwd_request(), estimate)(_DWD_POINT)
    first = clean[0]

    _serving_open_values(monkeypatch, opening={first})
    begin_response()
    getattr(_dwd_request(), estimate)(_DWD_POINT)

    (warning,) = _summary()
    assert warning["stations"] == [first]
    assert "was of a window that had not closed yet (1 for this month) and is left out" in warning["message"]


# --- `values` is unchanged ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("series", SERIES_ONLY[1:])
def test_values_still_returns_an_open_month_and_year_marked_and_told_by_its_own_code(
    monkeypatch: pytest.MonkeyPatch, series: Series
) -> None:
    """The mark is carried by `values`: the open value comes back `completeness:Incomplete` and `window-not-closed`."""
    _serve(monkeypatch, series)
    begin_response()

    df = _request(series).filter_by_station_id("SN18700").values().all().df.sort("timestamp")

    assert df["value"].to_list() == [CLOSED_VALUE, OPEN_VALUE]
    assert df["quality_flags"].to_list() == [None, "completeness:Incomplete"]
    (warning,) = recorded_warnings()
    assert warning["code"] == CLOSED
    assert (
        "are of a window that had not closed" in warning["message"]
        or "is of a window that had not closed" in (warning["message"])
    )
    assert "marked `completeness:Incomplete`" in warning["message"]
    assert SOURCE_DATA_LEFT_OUT not in _codes()


def test_values_still_leaves_an_open_day_out_and_tells_it_by_its_own_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """A daily value of an open window is left out of `values` as before, with `window-not-closed`."""
    series = SERIES[0].values[0]
    _serve(monkeypatch, series)
    begin_response()

    df = _request(series).filter_by_station_id("SN18700").values().all().df

    assert df["value"].to_list() == [CLOSED_VALUE]
    (warning,) = recorded_warnings()
    assert warning["code"] == CLOSED
    assert "is left out of the answer" in warning["message"]


# --- every surface --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("estimate", ESTIMATES)
def test_the_open_window_is_told_alike_on_every_surface(monkeypatch: pytest.MonkeyPatch, estimate: str) -> None:
    """The library, the command line, REST and MCP carry the same warning once; REST names it in a header."""
    series = SERIES[1].values[0]
    _serve(monkeypatch, series)

    told = _surfaces(
        lambda: getattr(_request(series), estimate)(_FROST_POINT),
        {
            "provider": "metno",
            "network": "frost",
            "parameters": f"monthly/data/{series.name}",
            "latitude": str(_FROST_POINT[0]),
            "longitude": str(_FROST_POINT[1]),
            "timestamp": "2026-10-01/2026-11-01",
        },
        estimate,
    )

    (warning,) = told["rest"]
    assert warning["code"] == SOURCE_DATA_LEFT_OUT
    assert warning["stations"] == ["SN18700"]
    assert "was of a window that had not closed yet (1 for this month) and is left out" in warning["message"]
    assert told["cli"] == told["rest"] == told["mcp"] == told["library"]
    assert told["header"] == [{"code": SOURCE_DATA_LEFT_OUT}]


# --- one request object reused: the leave-out belongs to the read, not to the object or the process -------------------


def _values_rows(request: MetnoFrostRequest) -> tuple[list[float | None], list[str | None]]:
    df = request.filter_by_station_id("SN18700").values().all().df.sort("timestamp")
    return df["value"].to_list(), df["quality_flags"].to_list()


def _summary_open(request: MetnoFrostRequest, series: Series) -> list[float | None]:
    df = request.summarize(_FROST_POINT).df
    return df.filter(pl.col("timestamp") == series.open_)["value"].to_list()


MARKED = ([CLOSED_VALUE, OPEN_VALUE], [None, "completeness:Incomplete"])


@pytest.mark.parametrize("series", SERIES_ONLY[1:])
@pytest.mark.parametrize("order", ["estimate-first", "values-first"])
def test_one_request_reused_for_an_estimate_and_for_values_keeps_each_to_its_own_rule(
    monkeypatch: pytest.MonkeyPatch, series: Series, order: str
) -> None:
    """An estimate leaves the open month or year out, `values` of the same request returns it marked, in any order.

    The flag that makes the reader leave it out is set for the estimate's own read: a flag that stuck (on the request,
    the values or the module) would leave the value out of `values` after an estimate, or put it back into an estimate
    after `values`.
    """
    _serve(monkeypatch, series)
    request = _request(series)

    if order == "estimate-first":
        assert _summary_open(request, series) == [None]
        assert _values_rows(request) == MARKED
        assert _summary_open(request, series) == [None]
    else:
        assert _values_rows(request) == MARKED
        assert _summary_open(request, series) == [None]
        assert _values_rows(request) == MARKED


@pytest.mark.parametrize("series", SERIES_ONLY[1:])
def test_an_estimate_and_values_inside_the_download_at_once_keep_to_their_own_rule(
    monkeypatch: pytest.MonkeyPatch, series: Series
) -> None:
    """Two threads of one request, an estimate and `values`, both inside the observations' download (a barrier)."""
    _serve(monkeypatch, series)
    served = frost_api.download_file
    barrier = threading.Barrier(2, timeout=20)
    inside: list[str] = []

    def download(*, url: str, **kwargs: object) -> File:
        if "observations/v0" in url and "/sources/" not in url and "availableTimeSeries" not in url:
            inside.append(threading.current_thread().name)
            barrier.wait()
        return served(url=url, **kwargs)

    monkeypatch.setattr(frost_api, "download_file", download)
    request = _request(series)
    out: dict[str, Any] = {}

    def estimate() -> None:
        begin_response()
        out["estimate"] = _summary_open(request, series)
        out["estimate_codes"] = _codes()

    def values() -> None:
        begin_response()
        out["values"] = _values_rows(request)
        out["values_codes"] = _codes()

    threads = [threading.Thread(target=estimate, name="E"), threading.Thread(target=values, name="V")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)

    assert sorted(inside) == ["E", "V"]
    assert out["estimate"] == [None]
    assert out["estimate_codes"] == [SOURCE_DATA_LEFT_OUT]
    assert out["values"] == MARKED
    assert out["values_codes"] == [CLOSED]
