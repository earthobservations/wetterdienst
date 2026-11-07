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

from wetterdienst.exceptions import CredentialRejectedError, InvalidParameterError
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
    sum is our reading of the same code. The daily sum (Frost states 0.0 mm; GH-3820 has it), the 10-minute, the
    monthly and the annual sum are not read at all. The code stays in the flags in every case it is read, as the last
    token (GH-3748).
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
        # from the cut-off year: the two sums read, the others as they were
        0.0, 0.0, -1.0, -1.0, -1.0, -1.0,
        # before it: null for the two, the others as they were
        None, None, -1.0, -1.0, -1.0, -1.0,
        0.0, 1.3, 0.0,
    ]  # fmt: skip
    # the code stays beside the value it stood for, and only there; a quality code of 7 stays in front of it
    assert decoded.get_column("quality_flags").to_list() == [
        "2,raw:-1", "2,raw:-1", "2", "2", "2", "2",
        "2,raw:-1", "2,raw:-1", "2", "2", "2", "2",
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
    # the daily -1 is not read, from the cut-off year or before: the range check nulls it, as it always did (GH-3820)
    ("sum(precipitation_amount P1D)", "daily", 0, [1.3], ("batch", "single", "discovery"), "daily-from"),
    ("sum(precipitation_amount P1D)", "daily", -1, [1.3], ("batch", "single", "discovery"), "daily-before"),
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
    daily sum is not read in either year.
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
            "timestamp": [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)] * 11,
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

    The `PT18H` series reaches a day before the `PT6H` one at 350 of the stations that have both (562 such dates at 198
    stations in the nine years sampled, GH-3832), and two stations have no `PT6H` series at all (SN10000 in July 1998,
    SN59680 in April 2005). Frost's own `timeoffsets=default` would return the 18-18 sum there.
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


def test_metno_frost_only_the_precipitation_sums_choose_an_offset() -> None:
    """Test that the rows of any other element are kept, as are those of an answer without an offset (GH-3832).

    `max(air_temperature P1D)` has `PT0H` and `PT18H` at 579 stations. Which of them to return is not decided here, so
    what comes back of it is what came back.
    """
    given = pl.DataFrame(
        {
            "elementId": ["max(air_temperature P1D)"] * 2 + ["sum(precipitation_amount P1D)"] * 3,
            "timeOffset": ["PT0H", "PT18H", "PT18H", "PT6H", None],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    assert frost_api._keep_standard_offset(given)["value"].to_list() == [1.0, 2.0, 4.0, 5.0]  # noqa: SLF001
    assert frost_api._keep_standard_offset(given.drop("timeOffset")).height == 5  # noqa: SLF001


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
