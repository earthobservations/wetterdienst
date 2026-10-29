# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for how the Frost values requests are built and read a failed download, against a stubbed upstream."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.exceptions import InvalidParameterError
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

    from wetterdienst.provider.metno.frost.api import MetnoFrostValues

START = dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
END = dt.datetime(2020, 1, 2, tzinfo=ZoneInfo("UTC"))
LOGGER = "wetterdienst.provider.metno.frost.api"

SOURCES = {
    "data": [
        {
            "id": "SN18700",
            "name": "OSLO - BLINDERN",
            "validFrom": "1937-01-01T00:00:00.000Z",
            "geometry": {"coordinates": [10.72, 59.94]},
            "county": "OSLO",
            "countryCode": "NO",
            "masl": 94,
        },
    ],
}
AVAILABLE = {
    "data": [
        {
            "validFrom": "2000-01-01T00:00:00Z",
            "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0",
        },
    ],
}
OBSERVATIONS = {
    "data": [
        {
            "sourceId": "SN18700:0",
            "referenceTime": "2020-01-01T00:00:00.000Z",
            "observations": [{"elementId": "air_temperature", "value": 2.7, "qualityCode": 0}],
        },
    ],
}


def _ok(url: str, payload: dict) -> File:
    return File(url=url, content=BytesIO(json.dumps(payload).encode()), status=200)


def _failed(url: str, status: int) -> File:
    """Give a failed request as `download_file` hands it back: the exception, with no body."""
    return File(url=url, content=OSError(f"upstream answered {status}"), status=status)


def _values(
    monkeypatch: pytest.MonkeyPatch,
    observations: Callable[[str], File],
    parameters: list[tuple[str, str, str]] | None = None,
    start: dt.datetime = START,
    end: dt.datetime = END,
) -> tuple[MetnoFrostValues, list[str]]:
    """Give the values of one station, the stations and the observations answered as stubbed."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")
    seen: list[str] = []

    def _download(*, url: str, **_kwargs: object) -> File:
        seen.append(url)
        if "/sources/" in url:
            return _ok(url, SOURCES)
        return observations(url)

    monkeypatch.setattr(frost_api, "download_file", _download)
    request = MetnoFrostRequest(
        parameters=parameters or [("hourly", "data", "temperature_air_2m")],
        start=start,
        end=end,
    )
    return request.filter_by_station_id("SN18700").values(), seen


def test_metno_frost_every_dataset_is_date_required() -> None:
    """Test that every Frost dataset says it needs a window, as its reader answers nothing without one (GH-3560)."""
    datasets = [(r.name, d.name, d.date_required) for r in MetnoFrostRequest.metadata for d in r.datasets]

    assert datasets
    assert [(resolution, dataset) for resolution, dataset, required in datasets if not required] == []


def test_metno_frost_values_404_reaches_the_discovery_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a 404 on the batched request resolves each parameter, and on that, discovers the time series.

    `download_file` hands back a 404 as an exception with no body. The values request used to
    treat that as an empty file before it read the status, so neither fallback for an element
    that needs `timeseriesids` could run (GH-2494).
    """

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        if "timeseriesids=" in url:
            return _ok(url, OBSERVATIONS)
        return _failed(url, 404)

    values, seen = _values(monkeypatch, observations)
    df = values.all().df
    # the dataset is requested in one batch, which 404s; then the parameter that was asked for is
    # requested alone, which 404s as well, and its time series are discovered and read
    assert len(values.sr.parameters[0].dataset.parameters) > 1
    assert "," in seen[1].split("elements=")[1].split("&")[0]
    assert sum("availableTimeSeries" in url for url in seen) == 1
    assert sum("timeseriesids=" in url for url in seen) == 1
    assert df["parameter"].to_list() == ["temperature_air_2m"]
    assert df["value"].to_list() == [2.7]


def test_metno_frost_values_carry_the_quality_code_as_a_whole_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Frost's `qualityCode` comes back in `quality_flags` as the digit its table lists (GH-2018, GH-2758).

    frost.met.no/dataclarifications.html, "Quality code": "Frost tries to give the user a single value to represent
    the general quality of the observation. This value is set in the field qualityCode": 0 "OK, value is controlled
    and found O.K.", 1 "OK, value is controlled and corrected, or value is missing and interpolated", 2 "Slightly
    uncertain, value is not controlled", 4 "Slightly uncertain, value is not corrected", 5 "Very uncertain, value
    is not corrected", 6 "Very uncertain, model data", 7 "Erroneous, value is not corrected". A code is no scale.
    """
    payload = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": f"2020-01-01T0{hour}:00:00.000Z",
                "observations": [{"elementId": "air_temperature", "value": 2.7 + hour, "qualityCode": code}],
            }
            for hour, code in enumerate((0, 1, 7))
        ],
    }
    values, _ = _values(
        monkeypatch, lambda url: _ok(url, payload), end=dt.datetime(2020, 1, 1, 3, tzinfo=ZoneInfo("UTC"))
    )
    df = values.all().df.sort("timestamp")
    assert df.schema["quality_flags"] == pl.String
    assert df.get_column("quality_flags").to_list() == ["0", "1", "7"]
    assert "quality" not in df.columns


def test_metno_frost_hourly_wind_is_named_for_its_ten_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Frost's hourly wind, the means of the last ten minutes, is named so (GH-2707).

    Frost's own element name `wind_speed` still addresses the row, but the canonical `wind_direction`,
    the mean over the hour, is no longer a name of it.
    """
    payload = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": "2020-01-01T00:00:00.000Z",
                "observations": [
                    {"elementId": "wind_speed", "value": 3.1, "qualityCode": 0},
                    {"elementId": "wind_from_direction", "value": 90.0, "qualityCode": 0},
                ],
            },
        ],
    }
    parameters = [
        ("hourly", "data", "wind_speed_mean_last_10min"),
        ("hourly", "data", "wind_direction_mean_last_10min"),
    ]
    values, _ = _values(monkeypatch, lambda url: _ok(url, payload), parameters)
    df = values.all().df.sort("parameter")
    assert df["parameter"].to_list() == ["wind_direction_mean_last_10min", "wind_speed_mean_last_10min"]
    assert df["value"].to_list() == [90.0, 3.1]
    with pytest.raises(InvalidParameterError):
        MetnoFrostRequest(parameters=[("hourly", "data", "wind_direction")], start=START, end=END)


DAILY_OBSERVATIONS = {
    "data": [
        {
            "sourceId": "SN18700:0",
            "referenceTime": "2020-01-01T00:00:00.000Z",
            "observations": [
                {"elementId": "sum(precipitation_amount P1D)", "value": 0.1, "qualityCode": 0},
                {"elementId": "max(air_temperature P1D)", "value": 3.5, "qualityCode": 0},
            ],
        },
        # an instantaneous daily observation is stored with its time of day: "The referenceTime is equal to
        # the observation time" (https://frost.met.no/concepts2.html)
        {
            "sourceId": "SN18700:0",
            "referenceTime": "2020-01-01T06:00:00.000Z",
            "observations": [{"elementId": "surface_snow_thickness", "value": 12.0, "qualityCode": 0}],
        },
        {
            "sourceId": "SN18700:0",
            "referenceTime": "2020-01-02T06:00:00.000Z",
            "observations": [{"elementId": "surface_snow_thickness", "value": 11.0, "qualityCode": 0}],
        },
    ],
}
DAILY = [
    ("daily", "data", "precipitation_amount"),
    ("daily", "data", "temperature_air_max_2m"),
    ("daily", "data", "snow_depth"),
]


def _daily_values(
    monkeypatch: pytest.MonkeyPatch,
    observations: Callable[[str], File],
) -> tuple[MetnoFrostValues, list[str]]:
    """Give the values of the days 2020-01-01 and 2020-01-02, the daily parameters being requested together."""
    return _values(monkeypatch, observations, DAILY, start=START, end=END)


def test_metno_frost_daily_snow_depth_is_stamped_at_midnight_of_its_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the daily snow depth, an instant at 06:00 UTC, is stamped at 00:00 UTC of its date (GH-2729).

    It used to keep the observation time as its stamp, which a window of whole days, 00:00 to 00:00 UTC, leaves
    out besides the other daily parameters that are stamped at 00:00 UTC.
    """
    values, _ = _daily_values(monkeypatch, lambda url: _ok(url, DAILY_OBSERVATIONS))
    df = values.all().df.sort("parameter", "timestamp")
    assert df["parameter"].to_list() == [
        "precipitation_amount",
        "snow_depth",
        "snow_depth",
        "temperature_air_max_2m",
    ]
    assert df["timestamp"].to_list() == [START, START, END, START]


def test_metno_frost_daily_snow_depth_is_stamped_at_midnight_when_requested_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the request for one parameter, after a 404 on the batch, stamps the snow depth likewise (GH-2729)."""

    def observations(url: str) -> File:
        return _ok(url, DAILY_OBSERVATIONS) if "elements=surface_snow_thickness&" in url else _failed(url, 404)

    values, _ = _daily_values(monkeypatch, observations)
    df = values.all().df.filter(pl.col("parameter") == "snow_depth")
    assert df["timestamp"].to_list() == [START, END]
    assert df["value"].to_list() == [12.0, 11.0]


def test_metno_frost_daily_snow_depth_is_stamped_at_midnight_when_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a daily time series found by discovery is stamped likewise (GH-2729)."""

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        if "timeseriesids=" in url:
            return _ok(url, DAILY_OBSERVATIONS)
        return _failed(url, 404)

    values, _ = _daily_values(monkeypatch, observations)
    df = values.all().df.filter(pl.col("parameter") == "snow_depth")
    assert df["timestamp"].to_list() == [START, END]


@pytest.mark.parametrize("status", [400, 429])
def test_metno_frost_values_failure_is_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    status: int,
) -> None:
    """Test that a values request Frost refused, other than a 404 or 412, is logged, not taken for no data.

    A refusal of the client ID (401, 403) and an outage are raised instead (GH-3018, GH-3022).
    """
    values, seen = _values(monkeypatch, lambda url: _failed(url, status))
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    assert [record.getMessage() for record in caplog.records if record.name == LOGGER] == [
        f"Failed to download {seen[-1]}: upstream answered {status}",
    ]


def test_metno_frost_values_single_parameter_failure_is_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the single-parameter request warns for a refusal other than a 404 or 412 as well."""
    values, seen = _values(monkeypatch, lambda url: _failed(url, 429))
    parameter = values.sr.parameters[0]
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values._collect_single_parameter("SN18700", parameter, START, END, values.sr.settings, {})  # noqa: SLF001
    assert df.is_empty()
    assert [record.getMessage() for record in caplog.records if record.name == LOGGER] == [
        f"Failed to download {seen[-1]}: upstream answered 429",
    ]


def test_metno_frost_values_412_is_no_data(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Test that a 412, Frost's answer for no data in the window, is empty and goes unwarned."""
    values, seen = _values(monkeypatch, lambda url: _failed(url, 412))
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    assert len(seen) == 2
    assert [record for record in caplog.records if record.name == LOGGER] == []


def test_metno_frost_values_discovered_series_failure_is_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failed request for a discovered time series is warned about, not taken for no data."""

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        return _failed(url, 404 if "timeseriesids=" not in url else 429)

    values, _seen = _values(monkeypatch, observations)
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    warned = [record.getMessage() for record in caplog.records if record.name == LOGGER]
    assert len(warned) == 1
    assert all(
        message.startswith("Failed to download ") and message.endswith(": upstream answered 429") for message in warned
    )
    assert all("timeseriesids=" in message for message in warned)


def test_metno_frost_values_discovery_failure_is_warned_about(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failed request for the available time series is warned about, not taken for no data."""
    values, seen = _values(monkeypatch, lambda url: _failed(url, 404 if "availableTimeSeries" not in url else 429))
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    warned = [record.getMessage() for record in caplog.records if record.name == LOGGER]
    assert len(warned) == 1
    assert all(message.startswith("Failed to download ") for message in warned)
    assert all("availableTimeSeries" in message for message in warned)
    assert not any("timeseriesids=" in url for url in seen)


@pytest.mark.parametrize("status", [404, 412])
def test_metno_frost_values_no_time_series_is_no_data(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    status: int,
) -> None:
    """Test that a 404 or 412 for the available time series, Frost's answer for none, goes unwarned."""
    values, _seen = _values(monkeypatch, lambda url: _failed(url, status if "availableTimeSeries" in url else 404))
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    assert [record for record in caplog.records if record.name == LOGGER] == []


def _observation_requests(seen: list[str]) -> list[str]:
    """Give the observation and time series requests of a run, leaving out the stations request."""
    return [url for url in seen if "/sources/" not in url]


def test_metno_frost_values_404_fallback_asks_for_the_requested_parameters_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the fallback after a 404 on the batch resolves what was asked for, not the whole dataset (GH-2554)."""
    requested = [("hourly", "data", "temperature_air_2m"), ("hourly", "data", "wind_speed_mean_last_10min")]
    values, seen = _values(monkeypatch, lambda url: _failed(url, 404), requested)
    assert values.all().df.is_empty()
    batch, *rest = _observation_requests(seen)
    assert len(values.sr.parameters[0].dataset.parameters) > len(requested)
    assert batch.count(",") == len(values.sr.parameters[0].dataset.parameters) - 1
    # one request alone and one discovery per requested parameter, and nothing for the rest
    assert [url.split("elements=")[1].split("&")[0] for url in rest if "availableTimeSeries" not in url] == [
        "air_temperature",
        "wind_speed",
    ]
    assert [url.split("elements=")[1].split("&")[0] for url in rest if "availableTimeSeries" in url] == [
        "air_temperature",
        "wind_speed",
    ]


def test_metno_frost_values_404_on_a_one_parameter_dataset_is_not_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a 404 on a dataset of one parameter goes straight to discovery, not to the URL that 404'd (GH-2554)."""

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        if "timeseriesids=" in url:
            return _ok(url, precipitation)
        return _failed(url, 404)

    precipitation = {
        "data": [
            {
                **OBSERVATIONS["data"][0],
                "observations": [{"elementId": "sum(precipitation_amount PT6H)", "value": 1.5, "qualityCode": 0}],
            },
        ],
    }
    values, seen = _values(monkeypatch, observations, [("6_hours", "data", "precipitation_amount")])
    df = values.all().df
    requests = _observation_requests(seen)
    assert len(values.sr.parameters[0].dataset.parameters) == 1
    assert len(requests) == len(set(requests)) == 3
    assert ["availableTimeSeries" in url for url in requests] == [False, True, False]
    assert "timeseriesids=" in requests[2]
    assert df["value"].to_list() == [1.5]


def test_metno_frost_values_404_fallback_for_one_parameter_leaves_its_siblings_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the fallback for one parameter model resolves that parameter, not its siblings (GH-2554)."""
    requested = [("hourly", "data", "temperature_air_2m"), ("hourly", "data", "wind_speed_mean_last_10min")]
    values, seen = _values(monkeypatch, lambda url: _failed(url, 404), requested)
    assert values._collect_station_parameter_or_dataset("SN18700", values.sr.parameters[1]).is_empty()  # noqa: SLF001
    # the request for that parameter alone, then its discovery; air_temperature is never asked for
    assert [url.split("elements=")[1].split("&")[0] for url in _observation_requests(seen)] == [
        "wind_speed",
        "wind_speed",
    ]


OSLO = ZoneInfo("Europe/Oslo")
# 2025-03-30 is the day Norway moves to summer time: 00:00 CET (+01:00) to 23:00 CEST (+02:00) is
# 2025-03-29 23:00Z to 2025-03-30 21:00Z, the end a second later as Frost's end is exclusive (GH-2746). Read as
# UTC, the wall clocks would be 00:00Z to 23:00Z
REFERENCE_TIME = "referencetime=2025-03-29T23:00:00/2025-03-30T21:00:01"


def _oslo_values(
    monkeypatch: pytest.MonkeyPatch,
    observations: Callable[[str], File],
) -> tuple[MetnoFrostValues, list[str]]:
    """Give the values of a request that spans the change to summer time, bounded in Oslo time."""
    return _values(
        monkeypatch,
        observations,
        start=dt.datetime(2025, 3, 30, 0, 0, tzinfo=OSLO),
        end=dt.datetime(2025, 3, 30, 23, 0, tzinfo=OSLO),
    )


def test_metno_frost_values_bounds_are_sent_as_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the bounds of a request in local time reach Frost as the UTC instants they stand for (GH-2681)."""
    values, seen = _oslo_values(monkeypatch, lambda url: _failed(url, 412))
    # the request holds the bounds in UTC (GH-2682), which is all the send relies on
    assert values.sr.start == dt.datetime(2025, 3, 29, 23, tzinfo=dt.UTC)
    assert values.sr.end == dt.datetime(2025, 3, 30, 21, tzinfo=dt.UTC)
    assert values.all().df.is_empty()
    [url] = _observation_requests(seen)
    assert REFERENCE_TIME in url


def test_metno_frost_values_single_parameter_bounds_are_sent_as_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the request for one parameter converts the bounds to UTC as well (GH-2681)."""
    values, seen = _oslo_values(monkeypatch, lambda url: _failed(url, 412))
    values._collect_single_parameter(  # noqa: SLF001
        "SN18700", values.sr.parameters[0], values.sr.start, values.sr.end, values.sr.settings, {}
    )
    [url] = _observation_requests(seen)
    assert REFERENCE_TIME in url


def test_metno_frost_values_discovered_series_bounds_are_sent_as_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the request for a discovered time series converts the bounds to UTC as well (GH-2681)."""

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        return _failed(url, 412 if "timeseriesids=" in url else 404)

    values, seen = _oslo_values(monkeypatch, observations)
    assert values.all().df.is_empty()
    [url] = [url for url in seen if "timeseriesids=" in url]
    assert REFERENCE_TIME in url


def _frost_interval(url: str) -> tuple[dt.datetime, dt.datetime]:
    """Read the `referencetime` of a request as Frost does: the half-open interval [t0,t1>, UTC."""
    t0, t1 = url.split("referencetime=")[1].split("&", maxsplit=1)[0].split("/")
    return dt.datetime.fromisoformat(t0).replace(tzinfo=dt.UTC), dt.datetime.fromisoformat(t1).replace(tzinfo=dt.UTC)


def _frost(payload: dict) -> Callable[[str], File]:
    """Give a Frost that answers with the rows of a payload that lie in the `referencetime` of the request.

    This is the documented behaviour of Frost, not one observed: no credentials were available (GH-2746).

    "Intervals in Frost are open-ended: [t0,t1>, i.e. representing times later than or equal to t0 and earlier
    than t1" (https://frost.met.no/concepts2.html).
    """

    def observations(url: str) -> File:
        t0, t1 = _frost_interval(url)
        rows = [row for row in payload["data"] if t0 <= dt.datetime.fromisoformat(row["referenceTime"]) < t1]
        # no rows is no data for Frost (404 "No data was found for the query parameters", 412 "No available time
        # series for the query parameters, as here), not an empty answer
        return _ok(url, {"data": rows}) if rows else _failed(url, 412)

    return observations


def test_metno_frost_daily_request_of_one_day_gets_the_snow_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a request for one day, 00:00 to 00:00 UTC, is answered with its 06:00 snow depth (GH-2729)."""
    values, _ = _values(monkeypatch, _frost(DAILY_OBSERVATIONS), DAILY, start=START, end=START)
    df = values.all().df.sort("parameter")
    assert df["parameter"].to_list() == ["precipitation_amount", "snow_depth", "temperature_air_max_2m"]
    assert df["timestamp"].to_list() == [START] * 3


def test_metno_frost_daily_request_stops_at_the_date_of_its_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a daily request asks for the date of its end, not for the date after it (GH-2729)."""
    values, seen = _values(monkeypatch, _frost(DAILY_OBSERVATIONS), DAILY, start=START, end=END)
    df = values.all().df
    assert df.filter(pl.col("parameter") == "snow_depth")["timestamp"].to_list() == [START, END]
    [url] = _observation_requests(seen)
    assert "referencetime=2020-01-01T00:00:00/2020-01-03T00:00:00" in url


@pytest.mark.parametrize(
    ("end", "expected"),
    [
        (dt.datetime(2020, 1, 2, tzinfo=dt.UTC), "2020-01-03T00:00:00"),
        (dt.datetime(2020, 1, 2, 12, 30, tzinfo=dt.UTC), "2020-01-03T00:00:00"),
        (dt.datetime(2020, 1, 2, 23, 59, 59, tzinfo=dt.UTC), "2020-01-03T00:00:00"),
    ],
)
def test_metno_frost_end_of_a_daily_request_is_the_start_of_the_next_date(end: dt.datetime, expected: str) -> None:
    """Test that the end sent for a daily request is 00:00 UTC of the date after the date of the end (GH-2729)."""
    assert frost_api._frost_end(end, "daily") == expected  # noqa: SLF001


def test_metno_frost_end_of_a_daily_request_in_another_zone_is_the_date_of_its_utc_instant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the date of the end of a daily request is that of its UTC instant (GH-2729, GH-2682).

    2020-01-02 00:30 in Oslo is 2020-01-01 23:30Z, so the request asks for the date of the 1st, up to 00:00Z of the 2nd.
    """
    values, seen = _values(
        monkeypatch,
        _frost(DAILY_OBSERVATIONS),
        DAILY,
        start=dt.datetime(2020, 1, 1, 0, 30, tzinfo=OSLO),
        end=dt.datetime(2020, 1, 2, 0, 30, tzinfo=OSLO),
    )
    values.all()
    [url] = _observation_requests(seen)
    assert "referencetime=2019-12-31T23:30:00/2020-01-02T00:00:00" in url


@pytest.mark.parametrize("resolution", ["10_minutes", "hourly", "6_hours", "monthly", "annual"])
def test_metno_frost_end_of_a_request_is_a_second_later(resolution: str) -> None:
    """Test that the end sent is a second after the end of the window, which Frost leaves out (GH-2746)."""
    end = dt.datetime(2020, 2, 1, tzinfo=dt.UTC)
    assert frost_api._frost_end(end, resolution) == "2020-02-01T00:00:01"  # noqa: SLF001


def test_metno_frost_hourly_request_gets_the_value_stamped_at_its_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the hourly value stamped at the end of the window is returned as well (GH-2746)."""
    payload = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": f"2020-01-0{day}T00:00:00.000Z",
                "observations": [{"elementId": "air_temperature", "value": value, "qualityCode": 0}],
            }
            for day, value in ((1, 2.7), (2, 3.1), (3, 4.0))
        ],
    }
    values, _ = _values(monkeypatch, _frost(payload))
    df = values.all().df.sort("timestamp")
    # the value of 2020-01-03 is beyond the window and cut off, as the second added reaches no further
    assert df["timestamp"].to_list() == [START, END]
    assert df["value"].to_list() == [2.7, 3.1]


def test_metno_frost_single_parameter_request_ends_after_its_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the request for one parameter and the one for a discovered series extend the end as well."""
    values, seen = _values(monkeypatch, lambda url: _failed(url, 412), DAILY)
    values._collect_single_parameter(  # noqa: SLF001
        "SN18700", values.sr.parameters[2], values.sr.start, values.sr.end, values.sr.settings, {}
    )
    [url] = _observation_requests(seen)
    assert "referencetime=2020-01-01T00:00:00/2020-01-03T00:00:00" in url

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        return _failed(url, 412 if "timeseriesids=" in url else 404)

    values, seen = _values(monkeypatch, observations, DAILY)
    assert values.all().df.is_empty()
    [url] = [url for url in seen if "timeseriesids=" in url][:1]
    assert "referencetime=2020-01-01T00:00:00/2020-01-03T00:00:00" in url


def test_metno_frost_values_beyond_the_window_are_cut_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a row Frost answers beyond the window, the end being asked for later, is left out (GH-2746)."""
    beyond = {
        "sourceId": "SN18700:0",
        "referenceTime": "2020-01-03T06:00:00.000Z",
        "observations": [{"elementId": "surface_snow_thickness", "value": 9.0, "qualityCode": 0}],
    }
    payload = {"data": [*DAILY_OBSERVATIONS["data"], beyond]}
    values, _ = _daily_values(monkeypatch, lambda url: _ok(url, payload))
    df = values.all().df.filter(pl.col("parameter") == "snow_depth")
    assert df["timestamp"].to_list() == [START, END]


def test_metno_frost_discovered_daily_series_starting_on_the_end_date_is_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a daily series that starts at 06:00 UTC of the end date is read for that date (GH-2729)."""
    available = {
        "data": [
            {
                "validFrom": "2020-01-02T06:00:00Z",
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0",
            },
        ],
    }

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, available)
        if "timeseriesids=" in url:
            return _frost(DAILY_OBSERVATIONS)(url)
        return _failed(url, 404)

    values, seen = _values(monkeypatch, observations, DAILY, start=START, end=END)
    df = values.all().df.filter(pl.col("parameter") == "snow_depth")
    assert df["timestamp"].to_list() == [END]
    assert any("referencetime=2020-01-02T06:00:00/2020-01-03T00:00:00" in url for url in seen)


@pytest.mark.parametrize(
    ("resolution", "element", "hours"),
    [
        ("daily", "sum(duration_of_sunshine P1D)", 10.4),
        ("monthly", "sum(duration_of_sunshine P1M)", 258.3),
    ],
)
def test_metno_frost_sunshine_duration_is_read_as_hours(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    element: str,
    hours: float,
) -> None:
    """Test that the sunshine duration, which Frost answers in hours, comes back in seconds (GH-3137).

    The metadata said seconds for the element, so 10.4 hours came back as 10.4 seconds, 3,600 times too small.
    """
    payload = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": "2020-01-01T00:00:00.000Z",
                "observations": [{"elementId": element, "value": hours, "unit": "hours", "qualityCode": 2}],
            },
        ],
    }
    values, _ = _values(
        monkeypatch,
        lambda url: _ok(url, payload),
        [(resolution, "data", "sunshine_duration")],
        start=START,
        end=dt.datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")),
    )
    df = values.all().df
    assert df["value"].to_list() == [pytest.approx(hours * 3600)]
