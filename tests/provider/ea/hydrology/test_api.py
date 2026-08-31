# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the Environment Agency hydrology API, in particular how measures are matched."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.provider.ea.hydrology import EAHydrologyRequest
from wetterdienst.provider.ea.hydrology import api as ea_api
from wetterdienst.provider.ea.hydrology.api import (
    _RESOLUTIONS_BY_PERIOD,
    EAHydrologyMetadata,
    EAHydrologyValues,
    _measure_parameter,
)
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from wetterdienst import Settings
    from wetterdienst.model.metadata import ParameterModel

STATIONS_URL = "https://environment.data.gov.uk/hydrology/id/stations.json"
STATION_URL = "https://environment.data.gov.uk/hydrology/id/stations/{station_id}.json"
MEASURE_URL = "https://environment.data.gov.uk/hydrology/id/measures/{notation}"


def _measure(station_id: str, notation: str) -> dict[str, Any]:
    """Build one measure as the station endpoints report it."""
    parameter, _statistic, period = notation.split("-")
    return {
        "@id": MEASURE_URL.format(notation=f"{station_id}-{notation}-m3s-qualified"),
        "parameter": parameter,
        "parameterName": parameter.capitalize(),
        "period": int(period),
    }


def _station(station_id: str, notations: list[str], latitude: float = 51.5) -> dict[str, Any]:
    """Build one station as the listing reports it."""
    return {
        "label": f"Station {station_id}",
        "notation": station_id,
        "easting": 400000,
        "northing": 300000,
        "lat": latitude,
        "long": -1.0,
        "dateOpened": "1990-01-01",
        "dateClosed": None,
        "measures": [_measure(station_id, notation) for notation in notations],
    }


def _serve(responses: dict[str, bytes]) -> Any:  # noqa: ANN401
    """Serve the given payloads by URL, and fail loudly on any other request."""

    def _download(**kwargs: Any) -> File:  # noqa: ANN401
        url = kwargs["url"]
        if url not in responses:
            msg = f"unexpected request to {url}"
            raise AssertionError(msg)
        return File(url=url, content=BytesIO(responses[url]), status=200)

    return _download


def test_ea_measure_parameter_is_the_leading_token_of_the_notation() -> None:
    """Test that every declared parameter yields the measure parameter the station listing names.

    The listing names a measure by its parameter and its period, never by the statistic in
    between, so the pair the station filter is built from has to come off the notation. The map
    this replaces was keyed by wetterdienst parameter name and still spelled the 15-minute ones
    `discharge_instant` and `groundwater_level_instant`, so every 15-minute request raised a
    KeyError before a single station was looked at.
    """
    derived = {
        f"{resolution.name}/{parameter.name}": _measure_parameter(parameter)
        for resolution in EAHydrologyMetadata
        for dataset in resolution
        for parameter in dataset.parameters
    }
    assert derived == {
        "15_minutes/discharge": "flow",
        "15_minutes/groundwater_level": "level",
        "daily/discharge_max": "flow",
        "daily/discharge_mean": "flow",
        "daily/discharge_min": "flow",
        "daily/groundwater_level_max": "level",
        "daily/groundwater_level_min": "level",
    }


def test_ea_resolutions_are_keyed_by_the_period_of_their_measures() -> None:
    """Test that each resolution is reached by exactly the period its notations declare.

    A resolution whose parameters disagreed about the period would collapse two resolutions onto
    one key here and silently serve the wrong interval under one of them.
    """
    assert _RESOLUTIONS_BY_PERIOD == {"900": "15_minutes", "86400": "daily"}


@pytest.mark.parametrize(
    ("parameter", "expected_station_ids"),
    [
        (("15_minutes", "data", "discharge"), ["0001"]),
        (("15_minutes", "data", "groundwater_level"), ["0002"]),
        (("daily", "data", "discharge_max"), ["0002"]),
    ],
)
def test_ea_stations_are_listed_under_the_period_they_record_at(
    parameter: tuple[str, str, str],
    expected_station_ids: list[str],
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a station is listed for a parameter only where it records it at that period.

    Station 0002 records flow daily and level every 15 minutes, so it must not answer for
    15-minute flow, and station 0001, which records flow every 15 minutes only, must not answer
    for daily flow.
    """
    listing = json.dumps(
        {
            "items": [
                _station("0001", ["flow-i-900"]),
                _station("0002", ["level-i-900", "flow-max-86400"]),
                # a period the metadata declares no resolution for is served under none
                _station("0003", ["flow-i-3600"]),
            ],
        },
    ).encode()
    monkeypatch.setattr(ea_api, "download_file", _serve({STATIONS_URL: listing}))
    request = EAHydrologyRequest(parameters=[parameter], settings=default_settings).all()
    assert request.df.get_column("station_id").to_list() == expected_station_ids


def test_ea_a_station_is_listed_once_however_many_measures_match(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a station recording several matching measures is still one station.

    The listing carries a row per measure, so a station recording two of the requested parameters
    matches twice -- and so does one recording two daily statistics of a single requested
    parameter, since the listing reports only the parameter and the period those two share. The
    duplicates reach the distance-sorted frame `filter_by_rank` hands to value collection, where
    rank is spent per row, so the one station is counted against it twice.
    """
    listing = json.dumps(
        {
            "items": [
                _station("0001", ["flow-i-900", "level-i-900"]),
                _station("0002", ["flow-i-900"], latitude=51.6),
            ],
        },
    ).encode()
    monkeypatch.setattr(ea_api, "download_file", _serve({STATIONS_URL: listing}))
    request = EAHydrologyRequest(
        parameters=[("15_minutes", "data", "discharge"), ("15_minutes", "data", "groundwater_level")],
        settings=default_settings,
    )
    assert request.all().df.get_column("station_id").to_list() == ["0001", "0002"]
    # sorted by distance rather than cut to `rank`, which is spent while collecting values
    ranked = request.filter_by_rank(latlon=(51.5, -1.0), rank=1)
    assert ranked.df.get_column("station_id").to_list() == ["0001", "0002"]


def test_ea_values_read_the_measure_of_the_requested_parameter(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the readings come from the measure matching parameter, statistic and period.

    Station 0004 publishes daily flow under three statistics, all of which share the parameter and
    the period the station listing reports, so only the notation tells them apart.
    """
    station_id = "0004"
    notations = ["flow-max-86400", "flow-m-86400", "flow-min-86400"]
    listing = json.dumps({"items": [_station(station_id, notations)]}).encode()
    station = json.dumps({"items": [{"measures": [_measure(station_id, n) for n in notations]}]}).encode()
    readings = {
        notation: json.dumps(
            {
                "items": [
                    {"dateTime": "2020-01-01T00:00:00", "value": float(index), "quality": "Good"},
                ],
            },
        ).encode()
        for index, notation in enumerate(notations)
    }
    responses = {
        STATIONS_URL: listing,
        STATION_URL.format(station_id=station_id): station,
    } | {
        f"{MEASURE_URL.format(notation=f'{station_id}-{notation}-m3s-qualified')}/readings.json": payload
        for notation, payload in readings.items()
    }
    monkeypatch.setattr(ea_api, "download_file", _serve(responses))
    request = EAHydrologyRequest(parameters=[("daily", "data", "discharge_mean")], settings=default_settings)
    df = request.all().values.all().df
    assert df.get_column("parameter").unique().to_list() == ["discharge_mean"]
    # the second of the three notations, so anything matching on parameter and period alone
    # would have taken the first
    assert df.get_column("value").to_list() == [1.0]


def _values_for(
    parameter: tuple[str, str, str],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    **kwargs: Any,  # noqa: ANN401
) -> tuple[EAHydrologyValues, ParameterModel]:
    """Give a values object for one parameter, off a stubbed one-station listing."""
    listing = json.dumps({"items": [_station("0001", ["flow-i-900"])]}).encode()
    monkeypatch.setattr(ea_api, "download_file", _serve({STATIONS_URL: listing}))
    request = EAHydrologyRequest(parameters=[parameter], settings=settings, **kwargs)
    return EAHydrologyValues(request.all()), request.parameters[0]


def test_ea_readings_are_asked_for_the_window_the_request_names(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a readings request carries the window and a page large enough to hold it.

    The endpoint answers an unbounded request with its default page of 100_000 readings, oldest
    first, and reports no truncation. At 15 minutes that page runs out after some 2.8 years, so
    every window past it -- which is every recent one -- used to arrive empty: the readings of
    2008 to 2011 came back and the post-filter dropped all of them.
    """
    values, parameter = _values_for(
        ("15_minutes", "data", "discharge"),
        default_settings,
        monkeypatch,
        start_date=dt.datetime(2020, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2020, 6, 3, tzinfo=ZoneInfo("UTC")),
    )
    query = parse_qs(urlparse(values._readings_url(MEASURE_URL.format(notation="x"), parameter)).query)  # noqa: SLF001
    # a day either side of the window, since the endpoint dates its readings without a zone
    assert query["mineq-dateTime"] == ["2020-05-31T00:00:00"]
    assert query["maxeq-dateTime"] == ["2020-06-04T00:00:00"]
    # the readings four days of 15-minute measurement can hold, so the page cannot cut the window
    assert query["_limit"] == ["385"]


def test_ea_readings_page_holds_a_window_longer_than_the_default(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a window past the default page raises it rather than being cut to it.

    A decade of 15-minute readings is some 350_000, well past the 100_000 the endpoint returns
    when it is not told otherwise, and it is the long window the silent cut costs most.
    """
    values, parameter = _values_for(
        ("15_minutes", "data", "discharge"),
        default_settings,
        monkeypatch,
        start_date=dt.datetime(2010, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
    )
    query = parse_qs(urlparse(values._readings_url(MEASURE_URL.format(notation="x"), parameter)).query)  # noqa: SLF001
    assert int(query["_limit"][0]) > 100_000


def test_ea_readings_are_unbounded_without_a_window(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a request naming no window asks for none, rather than for an empty one."""
    values, parameter = _values_for(("15_minutes", "data", "discharge"), default_settings, monkeypatch)
    assert urlparse(values._readings_url(MEASURE_URL.format(notation="x"), parameter)).query == ""  # noqa: SLF001


@pytest.mark.remote
def test_ea_15_minute_values_come_from_the_window_asked_for(default_settings: Settings) -> None:
    """Test that a 15-minute window past the endpoint's default page is answered with that window.

    The unbounded request this replaces was answered with the oldest 100_000 readings, which for
    a 15-minute measure is the years around 2008 to 2011, so every window after them was filtered
    away to nothing. A window inside that first page would pass whether or not it is asked for,
    which is why this one sits well after it.
    """
    start_date = dt.datetime(2020, 6, 1, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2020, 6, 3, tzinfo=ZoneInfo("UTC"))
    request = EAHydrologyRequest(
        parameters=[("15_minutes", "data", "discharge")],
        settings=default_settings,
        start_date=start_date,
        end_date=end_date,
    )
    df = request.filter_by_rank(latlon=(51.5, -1.0), rank=1).values.all().df
    assert not df.is_empty()
    assert df.get_column("date").min() >= start_date
    assert df.get_column("date").max() <= end_date


@pytest.mark.remote
def test_ea_15_minute_stations_are_reachable(default_settings: Settings) -> None:
    """Test that the 15-minute resolution lists stations at all.

    The stubbed tests above pin the matching; this one pins that the notations the metadata
    declares are still the ones the service publishes, which no fixture can tell us.
    """
    request = EAHydrologyRequest(parameters=[("15_minutes", "data", "discharge")], settings=default_settings).all()
    assert not request.df.is_empty()
