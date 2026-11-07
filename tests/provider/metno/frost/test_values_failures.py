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

from tests.provider.metno.frost.weekly_readers import unread_station_years
from wetterdienst.exceptions import CredentialRejectedError, InvalidParameterError
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

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
    options: dict | None = None,
    station: str = "SN18700",
) -> tuple[MetnoFrostValues, list[str]]:
    """Give the values of one station, the stations and the observations answered as stubbed."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "client-id")
    seen: list[str] = []
    sources = {"data": [{**SOURCES["data"][0], "id": station}]}

    def _download(*, url: str, **_kwargs: object) -> File:
        seen.append(url)
        if "/sources/" in url:
            return _ok(url, sources)
        return observations(url)

    monkeypatch.setattr(frost_api, "download_file", _download)
    request = MetnoFrostRequest(
        parameters=parameters or [("hourly", "data", "temperature_air_2m")],
        start=start,
        end=end,
        **({"options": options} if options else {}),
    )
    return request.filter_by_station_id(station).values(), seen


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
    # `7` is the one code Frost words as a verdict, and the check `source` flags it (GH-3677)
    assert df.get_column("quality_flags").to_list() == ["0", "1", "7,suspect:source"]
    assert "quality" not in df.columns


@pytest.mark.parametrize(
    ("mode", "flags", "values"),
    [
        (None, ["0", "1", "2", "4", "5", "6", "7,suspect:source"], [2.7, 3.7, 4.7, 5.7, 6.7, 7.7, 8.7]),
        ("hard", ["0", "1", "2", "4", "5", "6", "7,rejected:source,raw:8.7"], [2.7, 3.7, 4.7, 5.7, 6.7, 7.7, None]),
    ],
)
def test_metno_frost_flags_the_erroneous_quality_code_and_no_other(
    monkeypatch: pytest.MonkeyPatch, mode: str | None, flags: list[str], values: list[float | None]
) -> None:
    """Test that only `qualityCode` 7 is a verdict the check `source` reads: soft flags it, hard nulls it (GH-3677).

    https://frost.met.no/dataclarifications.html#quality-code words `7` as "Erroneous, value is not corrected". The
    others are a degree of confidence (2 "Slightly uncertain, value is not controlled", 4 "Slightly uncertain, value
    is not corrected", 5 "Very uncertain, value is not corrected"), a treatment (1) or model data (6), and none is
    flagged. The API needs a client id, so this is the documentation's wording on a stub, no live reading.
    """
    monkeypatch.setenv("WD_TS_DROP_NULLS", "false")
    if mode is not None:
        monkeypatch.setenv("WD_TS_PLAUSIBILITY__SOURCE", mode)
    payload = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": f"2020-01-01T0{hour}:00:00.000Z",
                "observations": [{"elementId": "air_temperature", "value": 2.7 + hour, "qualityCode": code}],
            }
            for hour, code in enumerate((0, 1, 2, 4, 5, 6, 7))
        ],
    }
    request_values, _ = _values(
        monkeypatch, lambda url: _ok(url, payload), end=dt.datetime(2020, 1, 1, 7, tzinfo=ZoneInfo("UTC"))
    )
    df = request_values.all().df.sort("timestamp")
    assert df.get_column("quality_flags").to_list() == flags
    assert [None if v is None else round(v, 1) for v in df.get_column("value").to_list()] == values


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


# Frost's answers without an observation: no `data` at all, an empty or null list of it, an entry with no
# `observations`, or with an empty or null one (GH-3750)
_ENTRY = {"sourceId": "SN18700:0", "referenceTime": "2020-01-01T00:00:00.000Z"}
EMPTY_ANSWERS = [
    {"@type": "ObservationResponse", "totalItemCount": 0},
    {"totalItemCount": 0, "data": []},
    {"totalItemCount": 0, "data": None},
    {"totalItemCount": 1, "data": [_ENTRY]},
    {"totalItemCount": 1, "data": [{**_ENTRY, "observations": []}]},
    {"totalItemCount": 1, "data": [{**_ENTRY, "observations": None}]},
]


@pytest.mark.parametrize("empty", EMPTY_ANSWERS)
@pytest.mark.parametrize(
    "requested", [("hourly", "data", "temperature_air_2m"), ("6_hours", "data", "precipitation_amount")]
)
def test_metno_frost_values_200_without_observations_is_no_data(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    empty: dict,
    requested: tuple[str, str, str],
) -> None:
    """Test that an empty 200, for any resolution, is no data: unwarned, and costing no discovery (GH-3750).

    The 6-hourly precipitation was once taken to discovery on such an answer (GH-3748). Frost answers that query
    with 200 and the observations, and the empty frame the caller then saw was the range check's, on a -1.
    """
    with caplog.at_level("WARNING", logger=LOGGER):
        values, seen = _values(monkeypatch, lambda url: _ok(url, empty), [requested])
        assert values.all().df.is_empty()
    assert all("availableTimeSeries" not in url for url in seen)
    # one request for the dataset, none for its parameters one by one
    assert len(_observation_requests(seen)) == 1
    assert [record for record in caplog.records if record.name == LOGGER] == []


@pytest.mark.parametrize("empty", EMPTY_ANSWERS)
def test_metno_frost_values_single_parameter_200_without_observations_is_no_data(
    monkeypatch: pytest.MonkeyPatch,
    empty: dict,
) -> None:
    """Test that after a 404 on the batch, an empty 200 for one parameter costs no discovery (GH-3750)."""

    def observations(url: str) -> File:
        batched = "," in url.split("elements=")[1].split("&", maxsplit=1)[0]
        return _failed(url, 404) if batched else _ok(url, empty)

    requested = [("hourly", "data", "temperature_air_2m"), ("hourly", "data", "wind_speed_mean_last_10min")]
    values, seen = _values(monkeypatch, observations, requested)
    assert values.all().df.is_empty()
    assert all("availableTimeSeries" not in url for url in seen)
    assert len(_observation_requests(seen)) == 3


def test_metno_frost_decodes_the_precipitation_code_from_the_cut_off_year_only() -> None:
    """Test that -1 of the 6-hourly and hourly precipitation is no precipitation from the cut-off year, null before.

    Frost states -1 as "No precipitation" for the 6-hourly sum, and writes it into 51 % of its readings from 1982 on.
    Before that year, in the old series, it is every reading of a station, wet days included, so it is null. The hourly
    sum is our reading of the same code. The daily sum has no cut-off year: Frost states 0.0 mm, and it is read in every
    year (GH-3820). The 10-minute, the monthly and the annual sum are not read at all. The code stays in the flags in
    every case it is read, as the last token (GH-3748).
    """
    year = frost_api._NO_PRECIPITATION_FROM_YEAR  # noqa: SLF001
    sums = ["PT6H", "PT1H", "P1D", "PT10M", "P1M", "P1Y"]
    given = pl.DataFrame(
        {
            "parameter": [f"sum(precipitation_amount {sum_})" for sum_ in sums] * 2
            + ["sum(precipitation_amount PT6H)"] * 3,
            "timestamp": [dt.datetime(year, 1, 1, tzinfo=dt.UTC)] * 6
            + [dt.datetime(year - 1, 12, 31, 18, tzinfo=dt.UTC)] * 6
            + [dt.datetime(year, 1, 1, tzinfo=dt.UTC)] * 3,
            # -1 of each sum from the cut-off year, then the year before it, then a 0, a measured sum and a 7
            "value": [-1.0] * 12 + [0.0, 1.3, -1.0],
            "quality_flags": ["2"] * 12 + ["0", "2", "7"],
        },
    )
    decoded = frost_api._decode_sentinels(given)  # noqa: SLF001
    assert decoded.get_column("value").to_list() == [
        # from the cut-off year: the three sums read, the others as they were
        0.0, 0.0, 0.0, -1.0, -1.0, -1.0,
        # before it: null for the two with a cut-off year, 0.0 for the daily sum, the others as they were
        None, None, 0.0, -1.0, -1.0, -1.0,
        0.0, 1.3, 0.0,
    ]  # fmt: skip
    # the code stays beside the value it stood for, and only there; a quality code of 7 stays in front of it
    assert decoded.get_column("quality_flags").to_list() == [
        "2,raw:-1", "2,raw:-1", "2,raw:-1", "2", "2", "2",
        "2,raw:-1", "2,raw:-1", "2,raw:-1", "2", "2", "2",
        "0", "2", "7,raw:-1",
    ]  # fmt: skip


AVAILABLE_TWO = {
    "data": [
        {
            "validFrom": "2000-01-01T00:00:00Z",
            "uri": f"https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids={series}",
        }
        for series in (0, 1)
    ],
}


@pytest.mark.parametrize("empty", EMPTY_ANSWERS)
def test_metno_frost_values_discovered_series_without_observations_moves_on_to_the_next(
    monkeypatch: pytest.MonkeyPatch,
    empty: dict,
) -> None:
    """Test that a discovered series answered 200 without observations is skipped, and the next is read (GH-3750)."""

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE_TWO)
        if "timeseriesids=0" in url:
            return _ok(url, empty)
        if "timeseriesids=1" in url:
            return _ok(url, OBSERVATIONS)
        return _failed(url, 404)

    values, seen = _values(monkeypatch, observations)
    df = values.all().df
    assert sum("timeseriesids=" in url for url in seen) == 2
    assert df["parameter"].to_list() == ["temperature_air_2m"]
    assert df["value"].to_list() == [2.7]


@pytest.mark.parametrize("empty", EMPTY_ANSWERS)
def test_metno_frost_values_discovered_series_all_without_observations_is_no_data(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    empty: dict,
) -> None:
    """Test that time series that all answer 200 without observations make an empty frame, unwarned (GH-3750)."""

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE_TWO)
        return _ok(url, empty) if "timeseriesids=" in url else _failed(url, 404)

    values, seen = _values(monkeypatch, observations)
    with caplog.at_level("WARNING", logger=LOGGER):
        df = values.all().df
    assert df.is_empty()
    assert sum("timeseriesids=" in url for url in seen) == 2
    assert [record for record in caplog.records if record.name == LOGGER] == []


def test_metno_frost_values_a_batch_with_an_entry_without_observations_keeps_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that an entry with no observations beside one that has them leaves the reading as it is (GH-3750)."""
    empty_entry = {**_ENTRY, "referenceTime": "2020-01-01T01:00:00.000Z", "observations": []}
    values, _ = _values(monkeypatch, lambda url: _ok(url, {"data": [empty_entry, *OBSERVATIONS["data"]]}))
    df = values.all().df
    assert df["parameter"].to_list() == ["temperature_air_2m"]
    assert df["value"].to_list() == [2.7]


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
    ("resolution", "element", "hours", "day"),
    [
        # a June day at Oslo (18.7 hours of day): 10.4 hours of sunshine on the 1st of January (6 hours of day) is none
        # the check `relations` accepts (GH-3681), and this test is about the unit
        pytest.param(
            "daily",
            "sum(duration_of_sunshine P1D)",
            10.4,
            dt.datetime(2020, 6, 1, tzinfo=ZoneInfo("UTC")),
            id="daily-sum(duration_of_sunshine P1D)-10.4",
        ),
        pytest.param(
            "monthly",
            "sum(duration_of_sunshine P1M)",
            258.3,
            dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
            id="monthly-sum(duration_of_sunshine P1M)-258.3",
        ),
    ],
)
def test_metno_frost_sunshine_duration_is_read_as_hours(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    element: str,
    hours: float,
    day: dt.datetime,
) -> None:
    """Test that the sunshine duration, which Frost answers in hours, comes back in hours (GH-3137, GH-3702).

    The metadata said seconds for the element, so 10.4 hours came back as 10.4 seconds, 3,600 times too small.
    """
    payload = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": f"{day:%Y-%m-%d}T00:00:00.000Z",
                "observations": [{"elementId": element, "value": hours, "unit": "hours", "qualityCode": 2}],
            },
        ],
    }
    values, _ = _values(
        monkeypatch,
        lambda url: _ok(url, payload),
        [(resolution, "data", "sunshine_duration")],
        start=day,
        end=day + dt.timedelta(days=31 if resolution == "monthly" else 1),
    )
    df = values.all().df
    assert df["value"].to_list() == [pytest.approx(hours)]


# --- a window over the limit, an answer without quality codes, `-1` through every reader (GH-3748) -----------------

FROM = frost_api._NO_PRECIPITATION_FROM_YEAR  # noqa: SLF001
TOO_MANY = (
    '{"error": {"code": 403, "message": "Forbidden", "reason": "The estimated number of observations (155123) '
    'exceeds the maximum number allowed (100000)"}}'
)


def _precipitation_answer(element: str, readings: list[tuple[str, float, int | None]]) -> dict:
    """Give Frost's answer for one precipitation element: the readings as (reference time, value, quality code)."""
    return {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": time,
                "observations": [
                    {"elementId": element, "value": value, **({} if quality is None else {"qualityCode": quality})}
                ],
            }
            for time, value, quality in readings
        ],
    }


def test_metno_frost_window_over_the_limit_is_a_time_interval_error_and_not_a_rejected_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a 403 whose body says too many observations is asked for narrower, and the key is not blamed.

    Frost answers a window of more than 100,000 observations (SN99710 `6_hours`, 1920 to 2026) with the status it gives
    a client ID it refuses; only the body tells them apart (GH-3748).
    """
    from wetterdienst.exceptions import CredentialRejectedError, InvalidTimeIntervalError  # noqa: PLC0415

    values, _ = _values(monkeypatch, lambda url: _failed(url, 403), [("6_hours", "data", "precipitation_amount")])
    asked: list[dict] = []

    def read_refusal(url: str, **kwargs: object) -> str:
        asked.append({"url": url, **kwargs})
        return TOO_MANY

    monkeypatch.setattr(frost_api, "read_refusal", read_refusal)
    with pytest.raises(InvalidTimeIntervalError, match=r"100,000.*155,123.*narrow the window") as excinfo:
        values.all()
    assert not isinstance(excinfo.value, CredentialRejectedError)
    assert "WD_AUTH" not in str(excinfo.value)
    # the refusal is read from the request that was refused, with the credential in its headers and not in the client
    assert len(asked) == 1
    assert asked[0]["url"].endswith("timeresolutions=PT6H")
    assert asked[0]["headers"]["Authorization"].startswith("Basic ")
    assert "headers" not in asked[0]["client_kwargs"]


@pytest.mark.parametrize("path", ["batch", "single", "discovery", "series"])
def test_metno_frost_window_over_the_limit_is_told_by_every_reader(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    """Test that the batch, the single parameter, the discovery listing and the discovered series all read a 403 why.

    Each of the four requests of a values read is refused as Frost refuses a window of too many observations, with the
    settings and the headers of the request handed on to read it (GH-3748).
    """
    from wetterdienst.exceptions import InvalidTimeIntervalError  # noqa: PLC0415

    asked: list[dict] = []

    def read_refusal(url: str, **kwargs: object) -> str:
        asked.append({"url": url, **kwargs})
        return TOO_MANY

    def observations(url: str) -> File:
        batched = "," in url.split("elements=")[1].split("&", maxsplit=1)[0]
        if "availableTimeSeries" in url:
            return _failed(url, 403) if path == "discovery" else _ok(url, AVAILABLE)
        if "timeseriesids=" in url:
            return _failed(url, 403)
        if path == "batch" or (path == "single" and not batched):
            return _failed(url, 403)
        return _failed(url, 404)

    requested = [("hourly", "data", "temperature_air_2m")]
    if path == "single":
        requested.append(("hourly", "data", "wind_speed_mean_last_10min"))
    values, _ = _values(monkeypatch, observations, requested)
    monkeypatch.setattr(frost_api, "read_refusal", read_refusal)
    with pytest.raises(InvalidTimeIntervalError, match="narrow the window"):
        values.all()
    assert len(asked) == 1
    assert asked[0]["headers"]["Authorization"].startswith("Basic ")
    assert "headers" not in asked[0]["client_kwargs"]


@pytest.mark.parametrize("status", [401, 404, 412, 429, 500])
def test_metno_frost_only_a_403_is_asked_why(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """Test that a refusal other than a 403 is not asked for again, and is read as it was, whatever a body might say."""
    asked: list[object] = []

    def read_refusal(*args: object, **kwargs: object) -> str:
        asked.append((args, kwargs))
        return TOO_MANY

    values, _ = _values(monkeypatch, lambda url: _failed(url, status))
    monkeypatch.setattr(frost_api, "read_refusal", read_refusal)
    if status == 401:
        with pytest.raises(CredentialRejectedError):
            values.all()
    else:
        values.all()
    assert asked == []


@pytest.mark.parametrize("reason", [None, "", '{"error": {"code": 403, "reason": "Forbidden"}}'])
def test_metno_frost_403_that_says_nothing_of_the_window_is_a_rejected_key(
    monkeypatch: pytest.MonkeyPatch,
    reason: str | None,
) -> None:
    """Test that a 403 with no reason, or another one, is still the refused client ID it was before (GH-3018)."""
    from wetterdienst.exceptions import CredentialRejectedError  # noqa: PLC0415

    values, _ = _values(monkeypatch, lambda url: _failed(url, 403))
    monkeypatch.setattr(frost_api, "read_refusal", lambda *_args, **_kwargs: reason)
    with pytest.raises(CredentialRejectedError, match="WD_AUTH__METNO_FROST"):
        values.all()


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
def test_metno_frost_answer_without_any_quality_code_is_read(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    """Test that observations none of which has a `qualityCode` are read, with no code in `quality_flags` (GH-3748).

    Frost leaves the key out of an observation it has no code for (SN30320 `daily`, 2015-05-01); selecting the column
    raised a `ColumnNotFoundError` in all three readers.
    """
    element = "sum(precipitation_amount P1D)"
    answer = _precipitation_answer(element, [("2020-01-01T00:00:00.000Z", 2.5, None)])

    def observations(url: str) -> File:
        batched = "," in url.split("elements=")[1].split("&", maxsplit=1)[0]
        if "availableTimeSeries" in url:
            return _ok(url, AVAILABLE)
        if "timeseriesids=" in url:
            return _ok(url, answer)
        if path == "batch" or (path == "single" and not batched):
            return _ok(url, answer)
        return _failed(url, 404)

    requested = [("daily", "data", "precipitation_amount")]
    if path == "single":
        requested.append(("daily", "data", "temperature_air_mean_2m"))
    values, _ = _values(monkeypatch, observations, requested, start=START, end=END)
    df = values.all().df.filter(pl.col("parameter") == "precipitation_amount")
    assert df["value"].to_list() == [2.5]
    assert df["quality_flags"].to_list() == [None]


# (element, resolution, years from the cut-off, the values that come back, the readers that reach it); the 6-hourly
# dataset has one parameter, so a request of it goes to discovery on a 404 and the single reader is not reached
_MINUS_ONE_CASES = [
    ("sum(precipitation_amount PT6H)", "6_hours", 0, [0.0, 1.3], ("batch", "discovery"), "6_hours-from"),
    ("sum(precipitation_amount PT6H)", "6_hours", -1, [1.3], ("batch", "discovery"), "6_hours-before"),
    ("sum(precipitation_amount PT1H)", "hourly", 0, [0.0, 1.3], ("batch", "single", "discovery"), "hourly-from"),
    ("sum(precipitation_amount PT1H)", "hourly", -1, [1.3], ("batch", "single", "discovery"), "hourly-before"),
    # the daily -1 is 0.0 mm as Frost states, in every year: no cut-off year (GH-3820)
    ("sum(precipitation_amount P1D)", "daily", 0, [0.0, 1.3], ("batch", "single", "discovery"), "daily-from"),
    ("sum(precipitation_amount P1D)", "daily", -1, [0.0, 1.3], ("batch", "single", "discovery"), "daily-before"),
]


@pytest.mark.parametrize(
    ("path", "element", "resolution", "year_offset", "expected"),
    [
        pytest.param(path, element, resolution, offset, expected, id=f"{case_id}-{path}")
        for element, resolution, offset, expected, paths, case_id in _MINUS_ONE_CASES
        for path in paths
    ],
)
def test_metno_frost_minus_one_of_precipitation_is_read_the_same_by_every_reader(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    element: str,
    resolution: str,
    year_offset: int,
    expected: list[float],
) -> None:
    """Test that the batch, the single and the discovered series all decode `-1`, from the cut-off year and not before.

    The discovery read once decoded nothing and every test passed (GH-3748): all three go through one rule. Before the
    cut-off year the code is null and the row is dropped, so that nothing false is returned for the old series. The
    daily sum has no cut-off year: its -1 is 0.0 mm in both (GH-3820).
    """
    year = FROM + year_offset
    start = dt.datetime(year, 1, 1, tzinfo=ZoneInfo("UTC"))
    end = dt.datetime(year, 1, 2, tzinfo=ZoneInfo("UTC"))
    answer = _precipitation_answer(
        element, [(f"{year}-01-01T00:00:00.000Z", -1, 2), (f"{year}-01-02T00:00:00.000Z", 1.3, 0)]
    )
    available = {
        "data": [
            {
                "validFrom": "1940-01-01T00:00:00Z",
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0",
            }
        ]
    }

    def observations(url: str) -> File:
        batched = "," in url.split("elements=")[1].split("&", maxsplit=1)[0]
        if "availableTimeSeries" in url:
            return _ok(url, available)
        if "timeseriesids=" in url:
            return _ok(url, answer)
        if path == "batch" or (path == "single" and not batched):
            return _ok(url, answer)
        return _failed(url, 404)

    requested = [(resolution, "data", "precipitation_amount")]
    if path == "single":
        sibling = {"hourly": "temperature_air_2m", "daily": "temperature_air_mean_2m"}[resolution]
        requested.append((resolution, "data", sibling))
    values, _ = _values(monkeypatch, observations, requested, start=start, end=end)
    df = values.all().df.filter(pl.col("parameter") == "precipitation_amount")
    assert sorted(df["value"].to_list()) == expected
    if expected == [0.0, 1.3]:
        assert df.filter(pl.col("value") == 0.0)["quality_flags"].to_list() == ["2,raw:-1"]


def test_metno_frost_decodes_sentinels() -> None:
    """Test that Frost's in-band codes become the value they stand for.

    Frost writes these into the value, where nothing distinguishes them from a measurement. Its element descriptions
    state two: snow depth -1 is "no snow", a depth of zero rather than an absent one, and cloud cover -3 and 9 both
    mean the cover could not be estimated (in eighths the latter two convert to -0.375 and 1.125 of the sky). Its data
    clarifications state more (GH-3748, GH-3137): the 6-hourly precipitation sum -1 is "No precipitation", the wind
    direction -3 is "No unique wind direction is given when winds are weak" and the snow depth -3 is "Not possible to
    measure snowdepth", where a snow depth of 0 is "Snowdepth less than 0.5 cm" and a reading.
    """
    given = pl.DataFrame(
        {
            "parameter": [
                "surface_snow_thickness",
                "surface_snow_thickness",
                "surface_snow_thickness",
                "surface_snow_thickness",
                "cloud_area_fraction",
                "cloud_area_fraction",
                "cloud_area_fraction",
                "wind_from_direction",
                "wind_from_direction",
                "air_temperature",
                "air_temperature",
            ],
            # one hour for each reading: two readings of one parameter at one time are two heights of a sensor
            "timestamp": [dt.datetime(2020, 1, 1, hour, tzinfo=dt.UTC) for hour in range(11)],
            "value": [-1.0, 12.0, 0.0, -3.0, -3.0, 9.0, 4.0, -3.0, 0.0, -1.0, -3.0],
            "quality_flags": ["0"] * 11,
        },
    )
    decoded = frost_api._decode_sentinels(given)  # noqa: SLF001
    values = decoded.get_column("value").to_list()
    # the code stays beside the value it stood for, after the quality code (GH-2759)
    assert decoded.get_column("quality_flags").to_list() == [
        "0,raw:-1",
        "0",
        "0",
        "0,raw:-3",
        "0,raw:-3",
        "0,raw:9",
        "0",
        "0,raw:-3",
        "0",
        "0",
        "0",
    ]
    # "no snow" is a depth of zero; a measured depth and a depth of less than 0.5 cm (0) are untouched
    assert values[:3] == [0.0, 12.0, 0.0]
    # a depth that could not be measured is no depth
    assert values[3] is None
    # both codes for "could not be estimated" become null; a real eighth is untouched
    assert values[4] is None
    assert values[5] is None
    assert values[6] == 4.0
    # no unique wind direction is null, and the 0 stays what Frost wrote where no speed is beside it to make it a calm
    assert values[7] is None
    assert values[8] == 0.0
    # -1 and -3 mean nothing special anywhere else, and a temperature may legitimately be negative
    assert values[9:] == [-1.0, -3.0]


# --- the 06-06 series of the precipitation sums, the calm of the wind direction, a removed parameter ----------


def _offset_answer(element: str, readings: list[tuple[str, str, float]]) -> dict:
    """Give Frost's answer for one element that has several series by `timeOffset`: (reference time, offset, value).

    Frost answers every series of the element when no `timeoffsets` is asked for, `PT18H` before `PT6H` for the same
    `referenceTime` (SN50540, 2026-10-29: 4.0 and 22.3).
    """
    return {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": time,
                "observations": [
                    {"elementId": element, "value": value, "timeOffset": offset}
                    for stamp, offset, value in readings
                    if stamp == time
                ],
            }
            for time in dict.fromkeys(time for time, _, _ in readings)
        ],
    }


def _answered_by(path: str, answer: dict, available: dict) -> Callable[[str], File]:
    """Give the stub of the upstream that serves ``answer`` to the reader ``path`` reaches."""

    def observations(url: str) -> File:
        batched = "," in url.split("elements=")[1].split("&", maxsplit=1)[0]
        if "availableTimeSeries" in url:
            return _ok(url, available)
        if "timeseriesids=" in url:
            return _ok(url, answer)
        if path == "batch" or (path == "single" and not batched):
            return _ok(url, answer)
        return _failed(url, 404)

    return observations


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize(
    ("element", "resolution", "stamps", "end"),
    [
        pytest.param(
            "sum(precipitation_amount P1D)",
            "daily",
            ["2026-10-28T00:00:00.000Z", "2026-10-29T00:00:00.000Z"],
            dt.datetime(2026, 10, 29, tzinfo=dt.UTC),
            id="P1D",
        ),
        pytest.param(
            "sum(precipitation_amount P1M)",
            "monthly",
            ["2020-01-01T00:00:00.000Z", "2020-02-01T00:00:00.000Z"],
            dt.datetime(2020, 2, 1, tzinfo=dt.UTC),
            id="P1M",
        ),
    ],
)
def test_metno_frost_precipitation_sum_is_the_series_of_the_standard_offset_by_every_reader(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    element: str,
    resolution: str,
    stamps: list[str],
    end: dt.datetime,
) -> None:
    """Test that the daily and monthly precipitation sum is the `PT6H` series, whichever Frost answers first (GH-3832).

    Frost answers both series of the sum for a date, `PT18H` (18-18 UTC) and `PT6H` (06-06 UTC): "Standard sampling
    period for precipitation is 07-06 UTC" (https://frost.met.no/dataclarifications.html). The core kept the first row
    of a reading, `PT18H`, so the sum of another window came back under a description of 06-06 (SN50540, 2026-10-29:
    4.0 for 22.3). All three readers choose the rows of the standard offset; the order of the answer is no part of it.
    """
    # the 18-18 sum before the 06-06 sum on the first date, as Frost answers it, and after it on the second
    readings = [
        (stamps[0], "PT18H", 4.0),
        (stamps[0], "PT6H", 22.3),
        (stamps[1], "PT6H", 1.6),
        (stamps[1], "PT18H", 0.1),
    ]
    available = {
        "data": [
            {
                "validFrom": "1940-01-01T00:00:00Z",
                "timeOffset": offset,
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0"
                f"&timeoffsets={offset}",
            }
            for offset in ("PT18H", "PT6H")
        ]
    }
    observations = _answered_by(path, _offset_answer(element, readings), available)
    requested = [(resolution, "data", "precipitation_amount")]
    if path == "single":
        requested.append((resolution, "data", "temperature_air_mean_2m"))
    start = dt.datetime.fromisoformat(stamps[0])
    values, seen = _values(monkeypatch, observations, requested, start=start, end=end)
    df = values.all().df.filter(pl.col("parameter") == "precipitation_amount").sort("timestamp")
    assert df["value"].to_list() == [22.3, 1.6]
    if path == "discovery":
        # the two series of the listing have one time series id: the series of the other offset is not asked for again
        assert sum("timeseriesids=" in url for url in seen) == 1


def test_metno_frost_precipitation_sum_of_a_date_that_only_the_other_series_has_is_not_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a date with only an 18-18 sum has no value, rather than that sum under the name of the 06-06 sum.

    At the stations of the list 1,178 days at 165 stations are of the 18-18 series only (158 of them the first day of
    that series, SN85380 692 from 2015-10 on), and SN59680 has no `PT6H` series at all (one day). Frost's own
    `timeoffsets=default` would return the 18-18 sum there. The answer says so (GH-3832).
    """
    answer = _offset_answer(
        "sum(precipitation_amount P1D)",
        [
            ("2020-01-01T00:00:00.000Z", "PT18H", 5.0),
            ("2020-01-02T00:00:00.000Z", "PT18H", 7.0),
            ("2020-01-02T00:00:00.000Z", "PT6H", 6.0),
        ],
    )
    values, _ = _values(
        monkeypatch, lambda url: _ok(url, answer), [("daily", "data", "precipitation_amount")], start=START, end=END
    )
    df = values.all().df
    assert df["timestamp"].to_list() == [END]
    assert df["value"].to_list() == [6.0]


def test_metno_frost_only_the_sums_the_daily_extremes_and_the_means_choose_an_offset() -> None:
    """Test that the rows of any other element are kept, as are those of an answer without an offset (GH-3832, GH-3843).

    The precipitation sums, the daily extremes and the daily and monthly mean keep their standard series alone (the
    mean's is `PT0H`, the calendar day, GH-3855); the rows of the other elements, and those that give no offset, are
    kept as they come.
    """
    given = pl.DataFrame(
        {
            "elementId": ["max(air_temperature P1D)"] * 2
            + ["mean(air_temperature P1D)"] * 2
            + ["mean(air_temperature P1M)"] * 2
            + ["sum(precipitation_amount P1D)"] * 3
            + ["mean(wind_speed P1D)"] * 2,
            "timeOffset": ["PT0H", "PT18H", "PT0H", "PT6H", "PT6H", "PT0H", "PT18H", "PT6H", None, "PT0H", "PT6H"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
        }
    )
    kept = frost_api._keep_standard_offset(given)["value"].to_list()  # noqa: SLF001
    assert kept == [2.0, 3.0, 6.0, 8.0, 9.0, 10.0, 11.0]
    assert frost_api._keep_standard_offset(given.drop("timeOffset")).height == 11  # noqa: SLF001


def test_metno_frost_a_daily_extreme_without_a_18_18_row_has_no_row() -> None:
    """Test that an extreme has no row where its offset is not `PT18H`, whatever the other elements have (GH-3843).

    The extremes are strict, like the precipitation: `PT0H` (or `PT6H`, which the minimum has alone at 9 stations of
    Frost's listing) is no fallback, and what is chosen for the maximum is no business of the minimum.
    """
    given = pl.DataFrame(
        {
            "elementId": ["max(air_temperature P1D)"] * 2 + ["min(air_temperature P1D)"] * 3,
            "timeOffset": ["PT0H", "PT0H", "PT0H", "PT18H", "PT6H"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    assert frost_api._keep_standard_offset(given)["value"].to_list() == [4.0]  # noqa: SLF001
    assert frost_api._keep_standard_offset(given.filter(pl.col("timeOffset") == "PT6H")).is_empty()  # noqa: SLF001


def _wind(readings: list[tuple[str, str, float, int]]) -> pl.DataFrame:
    """Give the frame a reader hands to `_decode_sentinels`: (parameter, height of its sensor, value, hour)."""
    return pl.DataFrame(
        {
            "parameter": [parameter for parameter, _, _, _ in readings],
            "timestamp": [dt.datetime(2020, 1, 1, hour, tzinfo=dt.UTC) for _, _, _, hour in readings],
            "value": [value for _, _, value, _ in readings],
            "quality_flags": ["0"] * len(readings),
            frost_api._LEVEL: [level for _, level, _, _ in readings],  # noqa: SLF001
        },
    )


def test_metno_frost_wind_direction_of_a_calm_is_null_and_a_0_beside_a_wind_stays() -> None:
    """Test that a direction of 0 beside a speed of 0 is null with `raw:0`, and beside a speed above 0 stays (GH-3833).

    Frost writes north as 360 ("360 degrees is north") and a calm as 0: the 0 stands beside a speed of 0 in 359 of 372
    readings at the foreign stations and in 1,014 of 1,068 at 20 Norwegian ones. As everywhere else (`calm`), a calm has
    no direction, and a 0 beside a wind that blows may be a north and stays.
    """
    given = _wind(
        [
            ("wind_from_direction", "10", 0.0, 0),
            ("wind_speed", "10", 0.0, 0),
            ("wind_from_direction", "10", 0.0, 1),
            ("wind_speed", "10", 2.1, 1),
            ("wind_from_direction", "10", 360.0, 2),
            ("wind_speed", "10", 0.0, 2),
            ("wind_from_direction", "10", 90.0, 3),
            ("wind_speed", "10", 0.0, 3),
        ]
    )
    decoded = frost_api._decode_sentinels(given)  # noqa: SLF001
    direction = decoded.filter(pl.col("parameter") == "wind_from_direction").sort("timestamp")
    assert direction["value"].to_list() == [None, 0.0, 360.0, 90.0]
    assert direction["quality_flags"].to_list() == ["0,raw:0", "0", "0", "0"]
    # the speed is not touched, and no helper column is left on the frame
    assert decoded.filter(pl.col("parameter") == "wind_speed")["value"].to_list() == [0.0, 2.1, 0.0, 0.0]
    assert decoded.columns == ["parameter", "timestamp", "value", "quality_flags"]


def test_metno_frost_wind_direction_without_a_speed_beside_stays_as_it_is() -> None:
    """Test that a direction of 0 whose speed is not in the frame stays, as in the single and discovery readers."""
    decoded = frost_api._decode_sentinels(  # noqa: SLF001
        _wind([("wind_from_direction", "10", 0.0, 0), ("wind_from_direction", "10", 0.0, 1)])
    )
    assert decoded["value"].to_list() == [0.0, 0.0]
    assert decoded["quality_flags"].to_list() == ["0", "0"]


def test_metno_frost_calm_is_judged_by_the_speed_of_the_height_of_the_direction() -> None:
    """Test that a direction takes the speed of its own height: 71 stations have the wind at several heights (GH-3833).

    SN99460 answers a speed and a direction at 10 m and again at 2 m for every hour. A calm at 2 m is no calm at 10 m,
    and a direction at a height that has no speed of its own has none beside it, whatever another height measures.
    """
    given = _wind(
        [
            ("wind_from_direction", "10", 0.0, 0),
            ("wind_speed", "10", 1.4, 0),
            ("wind_from_direction", "2", 0.0, 0),
            ("wind_speed", "2", 0.0, 0),
            # a direction at 5 m, a speed of 0 at 10 m only
            ("wind_from_direction", "5", 0.0, 1),
            ("wind_speed", "10", 0.0, 1),
        ]
    )
    decoded = frost_api._decode_sentinels(given)  # noqa: SLF001
    direction = decoded.filter(pl.col("parameter") == "wind_from_direction")
    assert direction["value"].to_list() == [0.0, None, 0.0]
    assert direction["quality_flags"].to_list() == ["0", "0,raw:0", "0"]


def test_metno_frost_batch_reads_a_calm_from_the_dataset_it_asks_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a request for the wind direction alone asks for the whole dataset, so the speed is there (GH-3833).

    The direction of 0 at 00:00 is beside a speed of 0 and is dropped as the null it is; the one at 01:00 is beside 3.1
    m/s and stays.
    """
    level = {"levelType": "height_above_ground", "value": 10}
    payload = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": f"2020-01-01T0{hour}:00:00.000Z",
                "observations": [
                    {"elementId": "wind_speed", "value": speed, "qualityCode": 0, "level": level},
                    {"elementId": "wind_from_direction", "value": 0, "qualityCode": 0, "level": level},
                ],
            }
            for hour, speed in enumerate([0.0, 3.1])
        ],
    }
    values, seen = _values(
        monkeypatch,
        lambda url: _ok(url, payload),
        [("hourly", "data", "wind_direction_mean_last_10min")],
        start=START,
        end=START + dt.timedelta(hours=1),
    )
    df = values.all().df
    assert "wind_speed" in seen[1].split("elements=")[1].split("&")[0]
    assert df["parameter"].to_list() == ["wind_direction_mean_last_10min"]
    assert df["timestamp"].to_list() == [START + dt.timedelta(hours=1)]
    assert df["value"].to_list() == [0.0]


def test_metno_frost_has_no_direction_of_the_gust() -> None:
    """Test that `wind_direction_gust_max` is refused for the 10-minute data (GH-3833).

    It read `max(wind_from_direction_of_gust PT10M)`, which Frost describes as "Varying wind direction last 10 minutes.
    Upper limit", not the direction of the gust. Frost lists that element at PT30M (119 series) and PT1M (5) only; the
    listing for PT10M answers 404 "No data found", and a request 412 at 12 of 12 stations (4 of which return the
    10-minute gust speed).
    """
    with pytest.raises(InvalidParameterError):
        MetnoFrostRequest(parameters=[("10_minutes", "data", "wind_direction_gust_max")], start=START, end=END)
    names = {
        parameter.name
        for resolution in MetnoFrostRequest.metadata
        if resolution.name == "10_minutes"
        for dataset in resolution.datasets
        for parameter in dataset.parameters
    }
    assert "wind_direction_gust_max" not in names
    assert "wind_gust_max" in names


def _told(code: str) -> list[dict]:
    """Give the warnings of the request with this code."""
    return [warning for warning in recorded_warnings() if warning["code"] == code]


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize(
    ("element", "resolution", "stamps", "name"),
    [
        pytest.param(
            "sum(precipitation_amount P1D)",
            "daily",
            ["2020-01-01T00:00:00.000Z", "2020-01-02T00:00:00.000Z", "2020-01-03T00:00:00.000Z"],
            "daily/data/precipitation_amount",
            id="P1D",
        ),
        pytest.param(
            "sum(precipitation_amount P1M)",
            "monthly",
            ["2020-01-01T00:00:00.000Z", "2020-02-01T00:00:00.000Z", "2020-03-01T00:00:00.000Z"],
            "monthly/data/precipitation_amount",
            id="P1M",
        ),
    ],
)
def test_metno_frost_dates_only_the_other_series_has_are_told_by_every_reader(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    element: str,
    resolution: str,
    stamps: list[str],
    name: str,
) -> None:
    """Test that a date that only the 18-18 series has is left out with a warning, never silently (GH-3832).

    SN85380 has 698 such days, 692 of them from 2015-10 on (its last `PT6H` date is 2015-09-01) and 6 gaps in 2013-14:
    the answer to a request from 2015-08 to 2018-12 had 2 rows and said nothing. The warning is
    `other-window-left-out`, with the parameter, the station and the number of dates. A date beyond the window of the
    request is not counted.
    """
    readings = [
        (stamps[0], "PT18H", 4.0),
        (stamps[0], "PT6H", 22.3),
        (stamps[1], "PT18H", 7.0),
        (stamps[2], "PT18H", 8.0),
    ]
    available = {
        "data": [
            {
                "validFrom": "1940-01-01T00:00:00Z",
                "timeOffset": offset,
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0"
                f"&timeoffsets={offset}",
            }
            for offset in ("PT18H", "PT6H")
        ]
    }
    observations = _answered_by(path, _offset_answer(element, readings), available)
    requested = [(resolution, "data", "precipitation_amount")]
    if path == "single":
        requested.append((resolution, "data", "temperature_air_mean_2m"))
    # the window ends with the second date: the third is not in the answer, and not counted
    values, _ = _values(
        monkeypatch,
        observations,
        requested,
        start=dt.datetime.fromisoformat(stamps[0]),
        end=dt.datetime.fromisoformat(stamps[1]),
    )
    begin_response()
    df = values.all().df.filter(pl.col("parameter") == "precipitation_amount")
    assert df["value"].to_list() == [22.3]
    (warning,) = _told("other-window-left-out")
    assert warning["parameter"] == name
    assert warning["stations"] == ["SN18700"]
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]
    # the series are named by the window of the resolution: a month is no 06-06 window of a day (GH-3867)
    if resolution == "daily":
        assert "in Frost's 18-18 UTC series (`timeOffset` PT18H) only" in warning["message"]
        assert "this parameter is the 06-06 UTC series (`timeOffset` PT6H)" in warning["message"]
    else:
        assert (
            "in Frost's month series from 18 UTC on the last day of the previous month to 18 UTC on the last day of "
            "the month (`timeOffset` PT18H) only" in warning["message"]
        )
        assert (
            "this parameter is the month series from 06 UTC on the last day of the previous month to 06 UTC on the "
            "last day of the month (`timeOffset` PT6H)" in warning["message"]
        )
        assert "06-06" not in warning["message"]
        assert "18-18" not in warning["message"]
    # the source has values there: nothing says that it has none
    assert [w for w in _told("parameter-without-rows") if w["parameter"] in (resolution + "/data", name)] == []


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize("asked", ["named", "whole"])
def test_metno_frost_a_station_with_only_the_other_series_is_no_station_without_values(
    monkeypatch: pytest.MonkeyPatch, path: str, asked: str
) -> None:
    """Test that a window with the 18-18 series only is told as that, and is not "the source has no values" (GH-3832).

    SN85380 in 2018-01 holds 31 `PT18H` readings (26.5 mm) and no `PT6H` one: the answer was empty, with
    `parameter-without-rows` saying that the source has no values. It says now that the source has values of another
    series, for a parameter asked for by its name and for a dataset asked for whole.
    """
    answer = _offset_answer(
        "sum(precipitation_amount P1D)",
        [("2020-01-01T00:00:00.000Z", "PT18H", 5.0), ("2020-01-02T00:00:00.000Z", "PT18H", 7.0)],
    )
    available = {
        "data": [
            {
                "validFrom": "1940-01-01T00:00:00Z",
                "timeOffset": "PT18H",
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0"
                "&timeoffsets=PT18H",
            }
        ]
    }
    observations = _answered_by(path, answer, available)
    requested = [("daily", "data", "precipitation_amount")] if asked == "named" else [("daily", "data")]
    if path == "single":
        # the single reader is reached by a parameter of a dataset whose batch 404s
        requested = [("daily", "data", "precipitation_amount"), ("daily", "data", "temperature_air_mean_2m")]
    values, _ = _values(monkeypatch, observations, requested, start=START, end=END)
    begin_response()
    assert values.all().df.is_empty()
    (warning,) = _told("other-window-left-out")
    assert warning["parameter"] == "daily/data/precipitation_amount"
    assert "on 2 dates that are not in the answer (SN18700 2)" in warning["message"]
    # not of the parameter, nor of the dataset asked for whole
    assert [
        w
        for w in _told("parameter-without-rows")
        if w["parameter"] in ("daily/data", "daily/data/precipitation_amount")
    ] == []


def test_metno_frost_nothing_is_told_where_the_standard_series_has_every_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a date the 06-06 series has too is no date left out (GH-3832)."""
    answer = _offset_answer(
        "sum(precipitation_amount P1D)",
        [
            ("2020-01-01T00:00:00.000Z", "PT18H", 5.0),
            ("2020-01-01T00:00:00.000Z", "PT6H", 6.0),
            ("2020-01-02T00:00:00.000Z", "PT18H", 7.0),
            ("2020-01-02T00:00:00.000Z", "PT6H", 8.0),
        ],
    )
    values, _ = _values(
        monkeypatch, lambda url: _ok(url, answer), [("daily", "data", "precipitation_amount")], start=START, end=END
    )
    begin_response()
    assert values.all().df["value"].to_list() == [6.0, 8.0]
    assert recorded_warnings() == []


# --- the 18-18 series of the daily temperature extremes (GH-3843) --------------------------------------------------

EXTREMES = [
    pytest.param("max(air_temperature P1D)", "temperature_air_max_2m", id="max"),
    pytest.param("min(air_temperature P1D)", "temperature_air_min_2m", id="min"),
]
EXTREME_STAMPS = ["2020-01-01T00:00:00.000Z", "2020-01-02T00:00:00.000Z", "2020-01-03T00:00:00.000Z"]
EXTREME_END = dt.datetime(2020, 1, 3, tzinfo=dt.UTC)


def _available_offsets(*offsets: str) -> dict:
    """Give the listing of the series of one element at SN18700, one `timeseriesids`, that differ in `timeOffset`."""
    return {
        "data": [
            {
                "validFrom": "1940-01-01T00:00:00Z",
                "timeOffset": offset,
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0"
                f"&timeoffsets={offset}",
            }
            for offset in offsets
        ]
    }


def _extreme_values(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    element: str,
    name: str,
    readings: list[tuple[str, str, float]],
    start: str = EXTREME_STAMPS[0],
    end: dt.datetime = EXTREME_END,
) -> pl.DataFrame:
    """Give the frame a reader of `path` returns for the daily extreme `name`, Frost answering `readings`."""
    offsets = sorted({offset for _, offset, _ in readings})
    observations = _answered_by(path, _offset_answer(element, readings), _available_offsets(*offsets))
    requested = [("daily", "data", name)]
    if path == "single":
        requested.append(("daily", "data", "temperature_air_mean_2m"))
    values, _ = _values(monkeypatch, observations, requested, start=dt.datetime.fromisoformat(start), end=end)
    begin_response()
    return values.all().df.filter(pl.col("parameter") == name).sort("timestamp")


def _told_of(name: str) -> list[dict]:
    """Give the warnings that name the parameter `name`.

    The mean that makes the single reader the one reached has no rows, and is told as that.
    """
    return [w for w in recorded_warnings() if w.get("parameter", "").endswith(name)]


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize(("element", "name"), EXTREMES)
def test_metno_frost_daily_temperature_extreme_is_the_18_18_series_by_every_reader(
    monkeypatch: pytest.MonkeyPatch, path: str, element: str, name: str
) -> None:
    """Test that a station with both series returns the `PT18H` extreme on every date it has (GH-3843).

    Frost answers `PT0H` (the calendar day) before `PT18H` (the 24 hours ending 18 UTC, which its table calls "19-18
    UTC": "Standard sampling period for temperature extremes is 19-18 UTC") for a date, and the core kept the first: a
    station with both returned the calendar day where `PT0H` had a row and the 18-18 window where it had not, so the
    window of one parameter changed along the series. A date that only the calendar-day series has is left out (and
    told, below).
    """
    readings = [
        (EXTREME_STAMPS[0], "PT0H", 5.0),
        (EXTREME_STAMPS[0], "PT18H", 6.0),
        # a date before the `PT0H` series began
        (EXTREME_STAMPS[1], "PT18H", 7.0),
        # a gap of the `PT18H` series
        (EXTREME_STAMPS[2], "PT0H", 8.0),
    ]
    df = _extreme_values(monkeypatch, path, element, name, readings)
    assert df["value"].to_list() == [6.0, 7.0]
    assert df["timestamp"].to_list() == [dt.datetime(2020, 1, 1, tzinfo=dt.UTC), dt.datetime(2020, 1, 2, tzinfo=dt.UTC)]


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize(("element", "name"), EXTREMES)
def test_metno_frost_daily_temperature_extreme_of_a_station_without_the_18_18_series_has_no_values(
    monkeypatch: pytest.MonkeyPatch, path: str, element: str, name: str
) -> None:
    """Test that a station that has `PT0H` only returns no extreme, and the answer says so (GH-3843).

    The maintainer decided on 2026-11-07 that the extremes are strict, like the precipitation: no fallback to the
    calendar day. None of the 683 stations of the station list is without `PT18H`, but a station of Frost's listing is
    (9 for the maximum), and the answer is no "the source has no values": the source has them.
    """
    readings = [(EXTREME_STAMPS[0], "PT0H", 5.0), (EXTREME_STAMPS[1], "PT0H", 7.0)]
    df = _extreme_values(monkeypatch, path, element, name, readings)
    assert df.is_empty()
    (warning,) = _told("other-window-left-out")
    assert warning["parameter"] == f"daily/data/{name}"
    assert "on 2 dates that are not in the answer (SN18700 2)" in warning["message"]
    assert [w for w in _told_of(name) if w["code"] == "parameter-without-rows"] == []


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize(("element", "name"), EXTREMES)
def test_metno_frost_daily_temperature_extreme_dates_of_the_calendar_day_only_are_told(
    monkeypatch: pytest.MonkeyPatch, path: str, element: str, name: str
) -> None:
    """Test that a date with the calendar-day extreme only is left out and told (GH-3843).

    Of the catalogue's 550 stations with both series of the daily maximum, 17 have a date that only `PT0H` has outside
    the validity of `PT18H` (17 dates in all years) and the nine years read have 50 gaps inside it. Those dates are not
    returned (a value of the calendar-day series under the name of the 18-18 one) and are never "the source has no
    values".
    """
    readings = [
        (EXTREME_STAMPS[0], "PT0H", 5.0),
        (EXTREME_STAMPS[0], "PT18H", 6.0),
        (EXTREME_STAMPS[1], "PT0H", 7.0),
        (EXTREME_STAMPS[2], "PT0H", 8.0),
    ]
    df = _extreme_values(monkeypatch, path, element, name, readings)
    assert df["value"].to_list() == [6.0]
    (warning,) = _told("other-window-left-out")
    assert warning["parameter"] == f"daily/data/{name}"
    assert warning["stations"] == ["SN18700"]
    assert "on 2 dates that are not in the answer (SN18700 2)" in warning["message"]
    assert (
        "other series (`timeOffset` PT0H, the hourly readings stamped 00:00 to 23:00, or PT6H) only"
        in (warning["message"])
    )
    assert "18-18 UTC series (`timeOffset` PT18H)" in warning["message"]
    assert [w for w in _told("parameter-without-rows") if w["parameter"] in ("daily/data", f"daily/data/{name}")] == []


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize(("element", "name"), EXTREMES)
def test_metno_frost_daily_temperature_extreme_of_a_gap_date_does_not_depend_on_the_window(
    monkeypatch: pytest.MonkeyPatch, path: str, element: str, name: str
) -> None:
    """Test that a date of a gap of `PT18H` is left out whether or not the window holds a `PT18H` row (GH-3843).

    The first version fell back to `PT0H` for a window with no `PT18H` row: SN60850 on 2022-09-27 returned the calendar
    day for a request of that day, and left it out, with a warning, for 2022-09-20 to 09-30. A window of that one date
    is the answer of Frost here: only the `PT0H` row.
    """
    readings = [(EXTREME_STAMPS[2], "PT0H", 8.0)]
    df = _extreme_values(monkeypatch, path, element, name, readings, start=EXTREME_STAMPS[2])
    assert df.is_empty()
    (warning,) = _told("other-window-left-out")
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]


def test_metno_frost_daily_temperature_extremes_are_chosen_each_for_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a maximum that has `PT18H` and a minimum that has `PT0H` only do not decide each other.

    One answer holds both elements: the maximum has both series, the minimum the calendar day alone. The maximum is the
    `PT18H` value, and the minimum has no row, and the warning names the minimum only (GH-3843).
    """
    answer = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": EXTREME_STAMPS[0],
                "observations": [
                    {"elementId": "max(air_temperature P1D)", "value": 5.0, "timeOffset": "PT0H"},
                    {"elementId": "max(air_temperature P1D)", "value": 6.0, "timeOffset": "PT18H"},
                    {"elementId": "min(air_temperature P1D)", "value": -2.0, "timeOffset": "PT0H"},
                ],
            }
        ]
    }
    values, _ = _values(
        monkeypatch,
        lambda url: _ok(url, answer),
        [("daily", "data", "temperature_air_max_2m"), ("daily", "data", "temperature_air_min_2m")],
        start=dt.datetime.fromisoformat(EXTREME_STAMPS[0]),
        end=dt.datetime.fromisoformat(EXTREME_STAMPS[0]),
    )
    begin_response()
    df = values.all().df
    assert df["parameter"].to_list() == ["temperature_air_max_2m"]
    assert df["value"].to_list() == [6.0]
    (warning,) = _told("other-window-left-out")
    assert warning["parameter"] == "daily/data/temperature_air_min_2m"


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
def test_metno_frost_daily_temperature_extreme_left_out_of_another_offset_does_not_name_the_calendar_day(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that the warning does not call a `PT6H` row the calendar-day series (GH-3843).

    9 stations of Frost's listing have a daily minimum of `PT6H` only (none is in the station list). The row is left
    out as any other offset's is, and the warning names the series it is no more than "another" one.
    """
    readings = [(EXTREME_STAMPS[0], "PT6H", 1.0), (EXTREME_STAMPS[1], "PT6H", 2.0)]
    df = _extreme_values(monkeypatch, path, "min(air_temperature P1D)", "temperature_air_min_2m", readings)
    assert df.is_empty()
    (warning,) = _told("other-window-left-out")
    assert "on 2 dates that are not in the answer (SN18700 2)" in warning["message"]
    assert "or PT6H) only" in warning["message"]
    assert "calendar-day series" not in warning["message"]


def _discovery_by_query(
    monkeypatch: pytest.MonkeyPatch, queries: list[tuple[str, str | None, list[tuple[str, str, float]]]]
) -> tuple[pl.DataFrame, list[dict]]:
    """Give the frame the discovery returns for the daily maximum, and the warnings, of series that differ in validity.

    ``queries`` are the series of the station in the order the listing gives them: the `timeseriesids`, its `validTo`
    (None for open) and what Frost answers for its query, `(reference time, offset, value)`.
    """
    element = "max(air_temperature P1D)"
    answers = {ts: _offset_answer(element, readings) for ts, _, readings in queries}
    starts = {ts: stamp[:4] for ts, _, readings in queries for stamp, _, _ in readings}
    available = {
        "data": [
            {
                "validFrom": f"{starts[ts]}-01-01T00:00:00Z",
                "validTo": valid_to,
                "timeOffset": "PT0H",
                "uri": f"https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids={ts}",
            }
            for ts, valid_to, _ in queries
        ]
    }

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, available)
        if "timeseriesids=" in url:
            return _ok(url, answers[url.split("timeseriesids=")[1].split("&", maxsplit=1)[0]])
        return _failed(url, 404)

    values, _ = _values(
        monkeypatch,
        observations,
        [("daily", "data", "temperature_air_max_2m")],
        start=dt.datetime(2000, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2006, 1, 3, tzinfo=dt.UTC),
    )
    begin_response()
    return values.all().df, recorded_warnings()


@pytest.mark.parametrize("pt18h_in", ["the earlier query", "the later query"])
def test_metno_frost_daily_temperature_extreme_is_chosen_over_the_queries_of_the_discovery(
    monkeypatch: pytest.MonkeyPatch, pt18h_in: str
) -> None:
    """Test that the discovery keeps `PT18H` and leaves the calendar day out in whichever query each is (GH-3843).

    Two series of the station that differ in their validity are two queries. The `PT18H` rows are in the earlier or in
    the later one, the calendar-day rows of the other query are left out and told, and what each query holds is counted
    once.
    """
    first, second = "2000-01-02T00:00:00.000Z", "2006-01-02T00:00:00.000Z"
    if pt18h_in == "the earlier query":
        queries = [
            ("0", "2005-12-31T00:00:00Z", [(first, "PT0H", 1.0), (first, "PT18H", 2.0)]),
            ("1", None, [(second, "PT0H", 3.0)]),
        ]
        expected = [2.0]
    else:
        queries = [
            ("0", "2005-12-31T00:00:00Z", [(first, "PT0H", 1.0)]),
            ("1", None, [(second, "PT0H", 3.0), (second, "PT18H", 4.0)]),
        ]
        expected = [4.0]
    df, _ = _discovery_by_query(monkeypatch, queries)
    assert df["value"].to_list() == expected
    (warning,) = _told("other-window-left-out")
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]


MEAN_STAMPS = ["2020-01-01T00:00:00.000Z", "2020-01-02T00:00:00.000Z", "2020-01-03T00:00:00.000Z"]


def _mean_values(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    resolution: str,
    readings: list[tuple[str, str, float]],
    start: str = MEAN_STAMPS[0],
    end: str = MEAN_STAMPS[1],
) -> pl.DataFrame:
    """Give the frame a reader of `path` returns for the mean of `resolution`, Frost answering `readings`."""
    element = f"mean(air_temperature {'P1M' if resolution == 'monthly' else 'P1D'})"
    offsets = sorted({offset for _, offset, _ in readings})
    observations = _answered_by(path, _offset_answer(element, readings), _available_offsets(*offsets))
    requested = [(resolution, "data", "temperature_air_mean_2m")]
    if path == "single":
        requested.append((resolution, "data", "precipitation_amount"))
    values, _ = _values(
        monkeypatch,
        observations,
        requested,
        start=dt.datetime.fromisoformat(start),
        end=dt.datetime.fromisoformat(end),
    )
    begin_response()
    return values.all().df.filter(pl.col("parameter") == "temperature_air_mean_2m").sort("timestamp")


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize("resolution", ["daily", "monthly"])
def test_metno_frost_the_mean_temperature_is_the_calendar_day_series_by_every_reader(
    monkeypatch: pytest.MonkeyPatch, path: str, resolution: str
) -> None:
    """Test that the daily and monthly mean is the `PT0H` series alone, and a date that only `PT6H` has is left out.

    The mean has `PT0H` (the calendar day, the hourly readings stamped 00:00 to 23:00) and `PT6H` (06-06 UTC) at 609
    and 605 stations of the catalogue, and Frost prefers `PT0H` for it ("For cases not listed above, PT0H is always the
    preferred offset"). The core kept the first row of a date, which is `PT0H` where it has one and `PT6H` where it has
    not, so the window of one parameter changed along a station's series: SN25830 2,966 days, SN27270 603 (GH-3855).
    """
    stamps = MEAN_STAMPS if resolution == "daily" else ["2020-01-01T00:00:00.000Z", "2020-02-01T00:00:00.000Z"]
    readings = [(stamps[0], "PT0H", 1.0), (stamps[0], "PT6H", 2.0), (stamps[1], "PT6H", 3.0)]
    df = _mean_values(monkeypatch, path, resolution, readings, start=stamps[0], end=stamps[1])
    assert df["value"].to_list() == [1.0]
    assert df["timestamp"].to_list() == [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)]
    (warning,) = _told("other-window-left-out")
    assert warning["parameter"] == f"{resolution}/data/temperature_air_mean_2m"
    assert warning["stations"] == ["SN18700"]
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]
    message = warning["message"]
    assert "other series (`timeOffset` PT6H" in message
    # Frost's table does not name a standard for the mean, it prefers `PT0H`: the clause says which of the two it is
    assert ", the one Frost prefers." in message
    assert "names its standard" not in message
    if resolution == "daily":
        assert "this parameter is the calendar-day series (`timeOffset` PT0H, the hourly readings stamped" in message
        assert "other series (`timeOffset` PT6H, the 06-06 UTC mean, or PT18H)" in message
    else:
        # a month is no day: it is not the hourly readings of 00:00 to 23:00
        assert "this parameter is the calendar-month series (`timeOffset` PT0H, midnight to midnight" in message
        assert "hourly readings" not in message
        assert "other series (`timeOffset` PT6H, 06 UTC to 06 UTC on the last days of the months, or PT18H)" in message
    # the source has values there: nothing says that it has none
    assert [w for w in _told_of("temperature_air_mean_2m") if w["code"] == "parameter-without-rows"] == []


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
def test_metno_frost_the_mean_temperature_of_a_date_that_only_pt6h_has_does_not_depend_on_the_window(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that a date that `PT0H` lacks is left out in a window of that date and in a wider one (GH-3855)."""
    readings = [(MEAN_STAMPS[0], "PT0H", 1.0), (MEAN_STAMPS[1], "PT6H", 3.0), (MEAN_STAMPS[2], "PT0H", 5.0)]
    df = _mean_values(monkeypatch, path, "daily", readings, start=MEAN_STAMPS[1], end=MEAN_STAMPS[1])
    assert df.is_empty()
    (warning,) = _told("other-window-left-out")
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]
    df = _mean_values(monkeypatch, path, "daily", readings, start=MEAN_STAMPS[0], end=MEAN_STAMPS[2])
    assert df["value"].to_list() == [1.0, 5.0]
    (warning,) = _told("other-window-left-out")
    assert "on 1 date that is not in the answer (SN18700 1)" in warning["message"]


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
def test_metno_frost_the_mean_temperature_of_a_station_that_has_no_pt0h_series_has_no_values(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that a station with `PT6H` (or `PT18H`) only returns no mean, and says so (GH-3855).

    None of the stations of the station list has no `PT0H` mean; one of Frost's listing has `PT18H` only, and 7 `PT6H`
    only. The answer is the "other series" one, never "the source has no values": the source has them.
    """
    readings = [(MEAN_STAMPS[0], "PT6H", 1.0), (MEAN_STAMPS[1], "PT6H", 2.0)]
    df = _mean_values(monkeypatch, path, "daily", readings)
    assert df.is_empty()
    (warning,) = _told("other-window-left-out")
    assert "on 2 dates that are not in the answer (SN18700 2)" in warning["message"]
    assert [w for w in _told_of("temperature_air_mean_2m") if w["code"] == "parameter-without-rows"] == []


def test_metno_frost_the_mean_temperature_is_decided_for_itself_beside_the_other_daily_elements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the mean that has `PT0H` and the maximum that has `PT18H` only do not decide each other (GH-3855)."""
    answer = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": MEAN_STAMPS[0],
                "observations": [
                    {"elementId": "mean(air_temperature P1D)", "value": 1.0, "timeOffset": "PT0H"},
                    {"elementId": "mean(air_temperature P1D)", "value": 9.0, "timeOffset": "PT6H"},
                    {"elementId": "max(air_temperature P1D)", "value": 4.0, "timeOffset": "PT18H"},
                    {"elementId": "mean(wind_speed P1D)", "value": 3.0, "timeOffset": "PT0H"},
                ],
            }
        ]
    }
    values, _ = _values(
        monkeypatch,
        lambda url: _ok(url, answer),
        [
            ("daily", "data", "temperature_air_mean_2m"),
            ("daily", "data", "temperature_air_max_2m"),
            ("daily", "data", "wind_speed_mean"),
        ],
        start=dt.datetime.fromisoformat(MEAN_STAMPS[0]),
        end=dt.datetime.fromisoformat(MEAN_STAMPS[0]),
    )
    begin_response()
    df = values.all().df.sort("parameter")
    assert df["parameter"].to_list() == ["temperature_air_max_2m", "temperature_air_mean_2m", "wind_speed_mean"]
    assert df["value"].to_list() == [4.0, 1.0, 3.0]
    assert _told("other-window-left-out") == []


def _two_heights(hours: list[list[tuple[str, int, float | None]]]) -> dict:
    """Give Frost's answer for the hourly wind of a station that measures it at two heights.

    Each hour is a list of (element, height, value), in the order Frost gives them.
    """
    return {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": f"2020-01-01T{hour:02d}:00:00.000Z",
                "observations": [
                    {
                        "elementId": element,
                        "value": value,
                        "qualityCode": 0,
                        "level": {"levelType": "height_above_ground", "unit": "m", "value": height},
                    }
                    for element, height, value in readings
                ],
            }
            for hour, readings in enumerate(hours)
        ],
    }


def test_metno_frost_a_calm_at_the_first_height_stays_a_calm_at_a_station_with_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the bearing of the second height does not fill a calm of the first, and the speed is of its height.

    SN99460 answers the wind at 10 m and 2 m for every hour, and the core keeps the first row of a reading that has a
    value: the calm of 10 m (null) was filled with the bearing of 2 m. 34 of the 79 calm hours at the 7 stations with
    two heights read as a wind that blows beside a speed of 0, 22 with a bearing above 0. A code of the first height
    (`-3` too) is what the hour is. A gap (a null that is no code) is filled from the other height, as it always was,
    and a first height with a bearing is the bearing.
    """
    wind = "wind_speed"
    direction = "wind_from_direction"
    hours = [
        # 00:00 the calm of 10 m beside a speed of 0, a bearing at 2 m beside a speed of 0
        [(wind, 10, 0.0), (wind, 2, 0.0), (direction, 10, 0), (direction, 2, 170)],
        # 01:00 both heights calm
        [(wind, 10, 0.0), (wind, 2, 0.0), (direction, 10, 0), (direction, 2, 0)],
        # 02:00 a gap at 10 m is filled from 2 m
        [(wind, 10, 1.0), (wind, 2, 1.0), (direction, 10, None), (direction, 2, 90)],
        # 03:00 a bearing at 10 m stays, whatever 2 m is
        [(wind, 10, 3.0), (wind, 2, 0.0), (direction, 10, 45), (direction, 2, 0)],
        # 04:00 no unique direction at 10 m is what the hour is
        [(wind, 10, 1.0), (wind, 2, 1.0), (direction, 10, -3), (direction, 2, 200)],
        # 05:00 the speeds come in the order 2 m, 10 m: the 0 of 10 m is beside the speed of 10 m, which is 0
        [(wind, 2, 3.0), (wind, 10, 0.0), (direction, 10, 0), (direction, 2, 90)],
        # 06:00 a 0 beside a wind that blows stays
        [(wind, 10, 2.0), (wind, 2, 2.0), (direction, 10, 0), (direction, 2, 270)],
    ]
    payload = _two_heights(hours)
    parameters = [
        ("hourly", "data", "wind_direction_mean_last_10min"),
        ("hourly", "data", "wind_speed_mean_last_10min"),
    ]
    values, _ = _values(
        monkeypatch,
        lambda url: _ok(url, payload),
        parameters,
        start=START,
        end=START + dt.timedelta(hours=6),
        options={"drop_nulls": False},
    )
    begin_response()
    df = values.all().df.filter(pl.col("parameter") == "wind_direction_mean_last_10min").sort("timestamp")
    assert df["value"].to_list() == [None, None, 90.0, 45.0, None, None, 0.0]
    flags = [flag.split(",")[-1] for flag in df["quality_flags"].to_list()]
    assert flags == ["raw:0", "raw:0", "0", "0", "raw:-3", "raw:0", "0"]
    # the calm hours are counted, whichever height would have filled them
    (calm,) = _told("calm-wind-direction")
    assert calm["message"].startswith("3 wind directions were a calm")


def test_metno_frost_a_gap_without_a_quality_code_is_filled_from_the_other_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a null at the first height that has no `qualityCode` is no code, and 2 m fills it (GH-3833).

    The null has no flags at all, so the test of the first height for a code was null and dropped the later row: the
    hour read null where `qualityCode: 0` made it 90.0. A calm without a `qualityCode` is a calm all the same.
    """
    wind = "wind_speed"
    direction = "wind_from_direction"
    hours = [
        [(wind, 10, 1.0), (wind, 2, 1.0), (direction, 10, None), (direction, 2, 90)],
        [(wind, 10, 0.0), (wind, 2, 0.0), (direction, 10, 0), (direction, 2, 170)],
    ]
    payload = _two_heights(hours)
    for day in payload["data"]:
        for observation in day["observations"]:
            del observation["qualityCode"]
    parameters = [
        ("hourly", "data", "wind_direction_mean_last_10min"),
        ("hourly", "data", "wind_speed_mean_last_10min"),
    ]
    values, _ = _values(
        monkeypatch,
        lambda url: _ok(url, payload),
        parameters,
        start=START,
        end=START + dt.timedelta(hours=1),
        options={"drop_nulls": False},
    )
    df = values.all().df.filter(pl.col("parameter") == "wind_direction_mean_last_10min").sort("timestamp")
    assert df["value"].to_list() == [90.0, None]
    assert df["quality_flags"].to_list() == [None, "raw:0"]


def test_metno_frost_the_first_height_is_the_first_row_of_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that "first" is the order of Frost's rows, not the height: a change of that order is noticed (GH-3833).

    Frost answered the 10 m rows before the 2 m rows at all 7 stations that have both, in 3 windows (2026-01, 2026-11,
    2024-06). The reader does not sort by height. A calm that comes first is the hour whichever height it is, and a
    bearing that comes first is the answer, a calm after it or not.
    """
    wind = "wind_speed"
    direction = "wind_from_direction"
    hours = [
        # 2 m first: its calm is the hour, and the bearing of 10 m does not fill it
        [(wind, 2, 0.0), (wind, 10, 3.0), (direction, 2, 0), (direction, 10, 90)],
        # 2 m first, with a bearing: it is the answer, and the calm of 10 m is no matter
        [(wind, 2, 3.0), (wind, 10, 0.0), (direction, 2, 45), (direction, 10, 0)],
    ]
    payload = _two_heights(hours)
    parameters = [
        ("hourly", "data", "wind_direction_mean_last_10min"),
        ("hourly", "data", "wind_speed_mean_last_10min"),
    ]
    values, _ = _values(
        monkeypatch,
        lambda url: _ok(url, payload),
        parameters,
        start=START,
        end=START + dt.timedelta(hours=1),
        options={"drop_nulls": False},
    )
    df = values.all().df.filter(pl.col("parameter") == "wind_direction_mean_last_10min").sort("timestamp")
    assert df["value"].to_list() == [None, 45.0]
    assert [flag.split(",")[-1] for flag in df["quality_flags"].to_list()] == ["raw:0", "0"]


def test_metno_frost_the_first_height_rule_is_the_wind_direction_s_alone() -> None:
    """Test that the rows of any other parameter at one time all stay, a code first or not (GH-3833).

    A cloud cover of 9 is a code too, and the next row of the same time is no other height of a wind direction.
    """
    given = pl.DataFrame(
        {
            "parameter": [
                "cloud_area_fraction",
                "cloud_area_fraction",
                "surface_snow_thickness",
                "surface_snow_thickness",
            ],
            "timestamp": [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)] * 4,
            "value": [9.0, 4.0, -3.0, 12.0],
            "quality_flags": ["0"] * 4,
        },
    )
    decoded = frost_api._decode_sentinels(given)  # noqa: SLF001
    assert decoded["value"].to_list() == [None, 4.0, None, 12.0]
    assert decoded["quality_flags"].to_list() == ["0,raw:9", "0", "0,raw:-3", "0"]


def test_metno_frost_a_parameter_that_was_not_asked_for_is_not_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the dates left out of an element of the batch that the request did not name are not told (GH-3832).

    The batch holds the whole dataset: the precipitation of a request for the temperature is read, and its 18-18 only
    dates are no business of the caller.
    """
    answer = {
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": "2020-01-01T00:00:00.000Z",
                "observations": [
                    {"elementId": "mean(air_temperature P1D)", "value": 1.5, "timeOffset": "PT0H"},
                    {"elementId": "sum(precipitation_amount P1D)", "value": 5.0, "timeOffset": "PT18H"},
                ],
            }
        ]
    }
    values, _ = _values(
        monkeypatch, lambda url: _ok(url, answer), [("daily", "data", "temperature_air_mean_2m")], start=START, end=END
    )
    begin_response()
    assert values.all().df["value"].to_list() == [1.5]
    assert _told("other-window-left-out") == []


def test_metno_frost_a_date_is_counted_once_however_many_series_answer_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the discovery counts a date left out once, though two of its queries both return it (GH-3832).

    SN85380 for 2013 to 2015 was told as 15 dates by the discovery and as the true 9 by the other readers: two queries
    (the series of a station differ in their validity) answer the same rows, and the dates are joined, not summed.
    """
    answer = _offset_answer(
        "sum(precipitation_amount P1D)",
        [("2020-01-01T00:00:00.000Z", "PT18H", 5.0), ("2020-01-02T00:00:00.000Z", "PT18H", 7.0)],
    )
    available = {
        "data": [
            {
                "validFrom": f"2020-01-01T{hour}:00:00Z",
                "timeOffset": "PT18H",
                "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&timeseriesids=0&timeoffsets=PT18H",
            }
            for hour in ("00", "06")
        ]
    }
    observations = _answered_by("discovery", answer, available)
    values, seen = _values(monkeypatch, observations, [("daily", "data", "precipitation_amount")], start=START, end=END)
    begin_response()
    assert values.all().df.is_empty()
    # two queries, as the series differ in their validity
    assert sum("timeseriesids=" in url for url in seen) == 2
    (warning,) = _told("other-window-left-out")
    assert "on 2 dates that are not in the answer (SN18700 2)" in warning["message"]


# --- the -1 of the daily precipitation sum, and the one station that writes it for a day nobody read (GH-3820) -------

DAILY_SUM = "sum(precipitation_amount P1D)"
# the exception of the reader: SN81930 (Storstilla), a weekly reader, up to and including 1993
WEEKLY_READER = "SN81930"


def _minus_one_days(
    monkeypatch: pytest.MonkeyPatch, path: str, station: str, element: str, stamps: list[str], offset: str = "PT6H"
) -> pl.DataFrame:
    """Give what a reader of `path` returns for `station` if Frost answers -1 on the first date and 1.3 on the next."""
    readings = [(stamps[0], offset, -1.0), (stamps[1], offset, 1.3)]
    resolution = "monthly" if element.endswith("P1M)") else "daily"
    observations = _answered_by(path, _offset_answer(element, readings), _available_offsets(offset))
    requested = [(resolution, "data", "precipitation_amount")]
    if path == "single":
        requested.append((resolution, "data", "temperature_air_mean_2m"))
    values, _ = _values(
        monkeypatch,
        observations,
        requested,
        start=dt.datetime.fromisoformat(stamps[0]),
        end=dt.datetime.fromisoformat(stamps[1]),
        options={"drop_nulls": False},
        station=station,
    )
    return values.all().df.filter(pl.col("parameter") == "precipitation_amount").sort("timestamp")


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
@pytest.mark.parametrize(
    ("station", "year", "value"),
    [
        # Frost states 0.0 mm, at every station and in every year: Bjornoya (1895-1956), Oslo, a new WMO series
        pytest.param("SN18700", 2026, 0.0, id="a-station-today"),
        pytest.param("SN18700", 1955, 0.0, id="a-station-of-the-1950s"),
        pytest.param("SN99700", 1950, 0.0, id="bjornoya"),
        # the weekly reader writes -1 for a day it did not read, up to and including 1993: null, with the code kept
        pytest.param(WEEKLY_READER, 1987, None, id="weekly-reader-1987"),
        pytest.param(WEEKLY_READER, 1993, None, id="weekly-reader-1993"),
        # from 1994 its -1 is dry-like (neighbours 18.9 % wet against 48 % before) and is read as Frost states it
        pytest.param(WEEKLY_READER, 1994, 0.0, id="weekly-reader-1994"),
        pytest.param(WEEKLY_READER, 2008, 0.0, id="weekly-reader-2008"),
    ],
)
def test_metno_frost_daily_minus_one_is_no_precipitation_but_a_weekly_readers_unread_day(
    monkeypatch: pytest.MonkeyPatch, path: str, station: str, year: int, value: float | None
) -> None:
    """Test that the daily `-1` is 0.0 mm with `raw:-1` at every station and year, except SN81930 up to 1993 (GH-3820).

    Frost states `-1` of `sum(precipitation_amount P1D)` as "No precipitation", converted to 0.0 mm. At SN81930 a
    weekly reader, it is a filler for the days of the week nobody read the gauge on, and the week's rain is in the next
    reading (the neighbours are wet on 48.0 % of those days, on 49.2 % of all days): null, with the code kept.
    """
    stamps = [f"{year}-03-01T00:00:00.000Z", f"{year}-03-02T00:00:00.000Z"]
    df = _minus_one_days(monkeypatch, path, station, DAILY_SUM, stamps)
    assert df["value"].to_list() == [value, 1.3]
    # the code is kept for the 0.0 and for the null alike, as the last token
    assert df["quality_flags"].to_list()[0] == "raw:-1"


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
def test_metno_frost_daily_minus_one_of_a_weekly_reader_is_by_the_year_of_the_date_not_of_the_window(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that the last day of 1993 is unread and the first of 1994 is dry, in one window and in another (GH-3820)."""
    stamps = ["1993-12-31T00:00:00.000Z", "1994-01-01T00:00:00.000Z"]
    df = _minus_one_days(monkeypatch, path, WEEKLY_READER, DAILY_SUM, stamps)
    assert df["value"].to_list() == [None, 1.3]
    stamps = ["1994-01-01T00:00:00.000Z", "1994-01-02T00:00:00.000Z"]
    df = _minus_one_days(monkeypatch, path, WEEKLY_READER, DAILY_SUM, stamps)
    assert df["value"].to_list() == [0.0, 1.3]


def test_metno_frost_daily_minus_one_of_a_weekly_reader_is_dropped_by_default_and_a_dry_one_is_found_by_its_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that an unread day has no row by default, and a dry `-1` is a row of 0.0 that `raw:-1` finds (GH-3820)."""
    readings = [
        ("1993-03-01T00:00:00.000Z", "PT6H", -1.0),
        ("1993-03-02T00:00:00.000Z", "PT6H", 2.0),
        ("1994-03-01T00:00:00.000Z", "PT6H", -1.0),
    ]
    observations = _answered_by("batch", _offset_answer(DAILY_SUM, readings), _available_offsets("PT6H"))
    values, _ = _values(
        monkeypatch,
        observations,
        [("daily", "data", "precipitation_amount")],
        start=dt.datetime(1993, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(1994, 12, 31, tzinfo=dt.UTC),
        station=WEEKLY_READER,
    )
    df = values.all().df.sort("timestamp")
    assert df["value"].to_list() == [2.0, 0.0]
    assert df["quality_flags"].to_list() == [None, "raw:-1"]


def test_metno_frost_only_the_daily_sum_has_a_day_that_is_not_read() -> None:
    """Test that the monthly sum and every other element read `-1` as they did, and the exception is the daily sum's.

    A -1 of the monthly sum (305, none since 1954) and of the other elements is decided by nobody here: the monthly
    sum's is left to the range check, a temperature of -1 is a temperature (GH-3820).
    """
    given = pl.DataFrame(
        {
            "parameter": [
                "sum(precipitation_amount P1D)",
                "sum(precipitation_amount P1M)",
                "mean(air_temperature P1D)",
                "sum(precipitation_amount PT6H)",
            ],
            "timestamp": [dt.datetime(1970, 1, 1, tzinfo=dt.UTC)] * 4,
            "value": [-1.0] * 4,
            "quality_flags": [None] * 4,
        }
    )
    decoded = frost_api._decode_sentinels(given, WEEKLY_READER)  # noqa: SLF001
    # the daily sum is the weekly reader's unread day; the 6-hourly sum, before 1982, null as it was; the rest as it was
    assert decoded["value"].to_list() == [None, -1.0, -1.0, None]
    assert decoded["quality_flags"].to_list() == ["raw:-1", None, None, "raw:-1"]
    decoded = frost_api._decode_sentinels(given, "SN18700")  # noqa: SLF001
    assert decoded["value"].to_list() == [0.0, -1.0, -1.0, None]
    assert decoded["quality_flags"].to_list() == ["raw:-1", None, None, "raw:-1"]


def test_metno_frost_the_rule_that_finds_a_weekly_reader_finds_the_pattern_of_the_census() -> None:
    """Test the rule on Storstilla's pattern (316 of 365 rows `-1`, a median gap of 7 days) and a dry spell's.

    The daily reader that has a dry spell has a `-1` on most days too, and a reading every few days at the most; the
    rule needs the median gap of 4 days or more, which only a weekly or monthly reader has (GH-3820).
    """
    days = [dt.date(1990, 1, 1) + dt.timedelta(days=n) for n in range(365)]
    weekly = pl.DataFrame(
        {
            "station_id": WEEKLY_READER,
            "date": days,
            "value": [2.0 if n % 7 == 6 else None for n in range(365)],
            "quality_flags": [None if n % 7 == 6 else "raw:-1" for n in range(365)],
        }
    )
    dry_spell = pl.DataFrame(
        {
            "station_id": "SN18700",
            "date": days,
            "value": [1.0 if n % 3 == 0 else 0.0 for n in range(365)],
            "quality_flags": [None if n % 3 == 0 else "raw:-1" for n in range(365)],
        }
    )
    monthly = pl.DataFrame(
        {
            "station_id": "SN53101",
            "date": [dt.date(1990, month, 1) for month in range(1, 13)],
            "value": [1.0] * 12,
            "quality_flags": [None] * 12,
        }
    )
    assert unread_station_years(pl.concat([weekly, dry_spell, monthly])) == {(WEEKLY_READER, 1990)}


def test_metno_frost_the_zero_of_a_daily_minus_one_is_not_judged_by_the_checks_and_is_no_null_to_drop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a daily `-1` read as 0.0 stays through `limits` and `drop_nulls`, a measured 0 does not (GH-3820).

    A reading that carries a `raw:` token is a code of the source and is not judged (`model/judge.py`): a lower bound of
    0.5 mm turns a measured `0` into null with `rejected:limits`, and keeps the `0.0` of a `-1`. Neither is dropped by
    `drop_nulls` for being null: the zero is a value. Read the `raw:-1` token to tell the two zeros apart.
    """
    readings = [(MEAN_STAMPS[0], "PT6H", -1.0), (MEAN_STAMPS[1], "PT6H", 0.0), (MEAN_STAMPS[2], "PT6H", 1.3)]
    for drop_nulls in (True, False):
        observations = _answered_by("batch", _offset_answer(DAILY_SUM, readings), _available_offsets("PT6H"))
        values, _ = _values(
            monkeypatch,
            observations,
            [("daily", "data", "precipitation_amount")],
            start=dt.datetime.fromisoformat(MEAN_STAMPS[0]),
            end=dt.datetime.fromisoformat(MEAN_STAMPS[2]),
            options={"drop_nulls": drop_nulls, "limits": {"precipitation_amount": (0.5, None)}},
        )
        df = values.all().df.sort("timestamp")
        measured_zero = [] if drop_nulls else [None]
        assert df["value"].to_list() == [0.0, *measured_zero, 1.3]
        assert df["quality_flags"].to_list()[0] == "raw:-1"
        if not drop_nulls:
            assert df["quality_flags"].to_list()[1].startswith("rejected:limits")


@pytest.mark.parametrize("path", ["batch", "single", "discovery"])
def test_metno_frost_a_reading_of_a_day_beats_the_minus_one_of_another_stamp_of_the_day(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Test that a day stamped several times keeps its reading, wherever its `-1` is, and a day of `-1` alone is 0.0.

    SN644700, one of four WMO stations that write several rows for a date, has on 2026-11-07 eight rows of `-1`
    (00:00 to 08:00) and five of 0.1 (10:00 to 16:00), and on 2026-11-04 the reading before its `-1`. The core keeps
    the first row of a day that has a value: the `-1` was null and lost, and as `0.0` it would win when it comes first
    (GH-3820). 2026-11-05 has `-1` rows alone.
    """
    readings = [
        ("2026-11-04T00:00:00.000Z", "PT6H", 0.1),
        ("2026-11-04T10:00:00.000Z", "PT6H", -1.0),
        ("2026-11-05T00:00:00.000Z", "PT6H", -1.0),
        ("2026-11-05T06:00:00.000Z", "PT6H", -1.0),
        ("2026-11-07T00:00:00.000Z", "PT6H", -1.0),
        ("2026-11-07T08:00:00.000Z", "PT6H", -1.0),
        ("2026-11-07T10:00:00.000Z", "PT6H", 0.1),
        ("2026-11-07T12:00:00.000Z", "PT6H", 0.1),
    ]
    observations = _answered_by(path, _offset_answer(DAILY_SUM, readings), _available_offsets("PT6H"))
    requested = [("daily", "data", "precipitation_amount")]
    if path == "single":
        requested.append(("daily", "data", "temperature_air_mean_2m"))
    values, _ = _values(
        monkeypatch,
        observations,
        requested,
        start=dt.datetime(2026, 11, 4, tzinfo=dt.UTC),
        end=dt.datetime(2026, 11, 7, tzinfo=dt.UTC),
        options={"drop_nulls": False},
        station="SN644700",
    )
    df = values.all().df.filter(pl.col("parameter") == "precipitation_amount").sort("timestamp")
    assert df["value"].to_list() == [pytest.approx(0.1), 0.0, pytest.approx(0.1)]
    assert df["quality_flags"].to_list() == [None, "raw:-1", None]


def test_metno_frost_a_reading_beats_the_minus_one_of_another_series_of_the_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the discovery, which reads each `timeseriesids` apart, leaves out a `-1` for a reading of another.

    The `-1` of series 0 is stamped 00:00 and the 0.1 of series 1 10:00 of the same date (GH-3820).
    """
    answers = {
        "0": _offset_answer(DAILY_SUM, [("2026-11-07T00:00:00.000Z", "PT6H", -1.0)]),
        "1": _offset_answer(DAILY_SUM, [("2026-11-07T10:00:00.000Z", "PT6H", 0.1)]),
    }
    available = {
        "data": [
            {
                "validFrom": "2026-11-01T00:00:00Z",
                "timeOffset": "PT6H",
                "uri": f"https://frost.met.no/observations/v0.jsonld?sources=SN644700:0&timeseriesids={ts}",
            }
            for ts in answers
        ]
    }

    def observations(url: str) -> File:
        if "availableTimeSeries" in url:
            return _ok(url, available)
        if "timeseriesids=" in url:
            return _ok(url, answers[url.split("timeseriesids=")[1].split("&", maxsplit=1)[0]])
        return _failed(url, 404)

    values, seen = _values(
        monkeypatch,
        observations,
        [("daily", "data", "precipitation_amount")],
        start=dt.datetime(2026, 11, 7, tzinfo=dt.UTC),
        end=dt.datetime(2026, 11, 7, tzinfo=dt.UTC),
        options={"drop_nulls": False},
        station="SN644700",
    )
    df = values.all().df
    assert sum("timeseriesids=" in url for url in seen) == 2
    assert df["value"].to_list() == [pytest.approx(0.1)]
    assert df["quality_flags"].to_list() == [None]


def test_metno_frost_a_reading_beats_a_minus_one_of_the_daily_sum_alone() -> None:
    """Test that the `-1` of another parameter, or of a sub-daily sum, beside a reading of its day is kept (GH-3820)."""
    day = dt.datetime(2026, 11, 7, tzinfo=dt.UTC)
    parameters = [
        "sum(precipitation_amount P1D)",
        "sum(precipitation_amount P1D)",
        "surface_snow_thickness",
        "surface_snow_thickness",
        "sum(precipitation_amount PT6H)",
        "sum(precipitation_amount PT6H)",
    ]
    given = pl.DataFrame(
        {
            "parameter": parameters,
            "timestamp": [day] * 6,
            "value": [0.0, 0.1, 0.0, 3.0, 0.0, 1.0],
            "quality_flags": ["raw:-1", None] * 3,
        }
    )
    kept = frost_api._a_reading_beats_a_minus_one(given)  # noqa: SLF001
    # only the daily sum's `-1` goes: the snow depth's and the 6-hourly sum's stay beside their readings
    assert kept["parameter"].to_list() == parameters[1:]
    assert kept["value"].to_list() == [0.1, 0.0, 3.0, 0.0, 1.0]
    # a `-1` alone, and a `-1` beside a `-1`, stay
    alone = given.head(1).vstack(given.head(1))
    assert frost_api._a_reading_beats_a_minus_one(alone).height == 2  # noqa: SLF001
