# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation summary."""

import dataclasses
import datetime as dt
import re
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.exceptions import LocationOutOfRangeError, NoStationsWithElevationError
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)


@pytest.mark.remote
def test_summary_by_station_id_answers_at_the_station_altitude(default_settings: Settings) -> None:
    """A summary named by a station is a summary at that station's altitude.

    Which is the same summary with an elevation, not the same summary: the reading of whichever
    station answers is brought from its own elevation to the named station's.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2022, 1, 3, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    elevation = request.all().df.filter(pl.col("station_id").eq("01050")).get_column("elevation").item()
    # the result says which elevation it answered for, so the contract is one call rather than two
    # compared against each other -- two live fetches can draw on different stations under a slow
    # or partial upstream, and then differ for reasons that have nothing to do with the elevation
    assert request.summarize_by_station_id(station_id="01050").elevation == elevation


@pytest.mark.remote
def test_summary_temperature_air_mean_2m_daily(default_settings: Settings) -> None:
    """Test summarization of temperature_air_mean_2m."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start=dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1965, 12, 31, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    selected_dates = [
        dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1940, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1950, 1, 1, tzinfo=ZoneInfo("UTC")),
    ]
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "7ac6c582",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "timestamp": selected_dates[0],
                "value": 0.5,
                "distance": 13.42,
                "taken_station_id": "01048",
            },
            {
                "station_id": "7ac6c582",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "timestamp": selected_dates[1],
                "value": -5.5,
                "distance": 5.05,
                "taken_station_id": "01051",
            },
            {
                "station_id": "7ac6c582",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "timestamp": selected_dates[2],
                "value": -2.7,
                "distance": 0.0,
                "taken_station_id": "01050",
            },
        ],
        orient="row",
    )
    for result in (request.summarize(latlon=(51.0221, 13.8470)),):
        given_df = result.df
        given_df = given_df.filter(pl.col("timestamp").is_in(selected_dates))
        assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_not_summarizable_parameter(default_settings: Settings) -> None:
    """Test that a parameter that cannot be summarized is handled correctly."""
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "precipitation_form")],
        start=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.summarize(latlon=(50.0, 8.9))
    given_df = result.df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    expected_df = pl.DataFrame(
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "distance": pl.Float64,
            "taken_station_id": pl.String,
        },
    )
    assert_frame_equal(
        given_df,
        expected_df,
    )


@pytest.mark.remote
def test_provider_dwd_mosmix(default_settings: Settings) -> None:
    """Test a MOSMIX request with date filter."""
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "temperature_air_2m")],
        start=dt.datetime.now(tz=ZoneInfo("UTC")) + dt.timedelta(days=1),
        end=dt.datetime.now(tz=ZoneInfo("UTC")) + dt.timedelta(days=8),
        settings=default_settings,
    )
    given_df = request.summarize(latlon=(50.0, 8.9)).df
    assert given_df.get_column("value").min() >= -40  # equals -40.0°C


def test_summary_error_no_start_date() -> None:
    """Test that an error is raised when start_date is missing."""
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_amount")],
    )
    with pytest.raises(ValueError, match="start and end are required for summarization"):
        request.summarize(latlon=(52.8, 12.9))


@pytest.mark.remote
def test_summary_at_an_elevation_none_of_the_stations_can_answer(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A summary emptied by an elevation says so rather than coming back empty.

    A summary answers with one station's reading rather than a blend, so a station it cannot place
    against the elevation asked about is the whole answer gone, not a quarter of it. DWD's stations
    stand in for FMI's here: same data, elevations taken away, and no second provider's outages
    deciding whether this passes.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2022, 1, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    original = DwdObservationRequest.filter_by_distance

    def without_elevations(self: DwdObservationRequest, *args: object, **kwargs: object) -> object:
        stations_ranked = original(self, *args, **kwargs)
        return dataclasses.replace(
            stations_ranked, df=stations_ranked.df.with_columns(pl.lit(None, dtype=pl.Float64).alias("elevation"))
        )

    monkeypatch.setattr(DwdObservationRequest, "filter_by_distance", without_elevations)
    with pytest.raises(
        NoStationsWithElevationError,
        match=r"nothing can be brought to 200\.0 m for daily/climate_summary/temperature_air_mean_2m",
    ):
        request.summarize(latlon=(47.48, 11.06), elevation=200.0)
    # and without an elevation the same stations answer as they always did
    assert not request.summarize(latlon=(47.48, 11.06)).df.is_empty()


class _ReachedStationSelection(Exception):  # noqa: N818
    """Raised by the stand-in for the selection of the stations, which is where a point is accepted."""


@pytest.fixture
def station_selection(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stand in for the station list and the selection, offline; the list records what was fetched."""
    fetched: list[str] = []
    stations = pl.DataFrame(
        {"station_id": ["00001"], "latitude": [95.0], "longitude": [10.0], "elevation": [None]},
        schema_overrides={"elevation": pl.Float64},
    )

    def all_stations(self: DwdObservationRequest) -> object:  # noqa: ARG001
        fetched.append("stations")
        return dataclasses.make_dataclass("Stations", ["df"])(df=stations)

    def select(*args: object, **kwargs: object) -> object:  # noqa: ARG001
        raise _ReachedStationSelection

    monkeypatch.setattr(DwdObservationRequest, "all", all_stations)
    monkeypatch.setattr("wetterdienst.core.summarize.get_summarized_df", select)
    return fetched


def _request(default_settings: Settings) -> DwdObservationRequest:
    return DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2022, 1, 3, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )


@pytest.mark.parametrize(
    ("latlon", "named"),
    [
        ((95.0, 0.0), "latitude 95.0 is outside the range -90 to 90"),
        ((-90.1, 0.0), "latitude -90.1 is outside the range -90 to 90"),
        ((0.0, 200.0), "longitude 200.0 is outside the range -180 to 180"),
        ((0.0, -180.1), "longitude -180.1 is outside the range -180 to 180"),
        ((float("nan"), 0.0), "latitude nan is outside the range -90 to 90"),
        ((0.0, float("inf")), "longitude inf is outside the range -180 to 180"),
    ],
)
def test_summary_refuses_a_point_beyond_the_globe(
    default_settings: Settings, station_selection: list[str], latlon: tuple[float, float], named: str
) -> None:
    """A point off the globe is refused, naming the range, before any station list is fetched (GH-3714).

    The REST API, the command line and MCP refused it already; the library answered with an empty frame.
    """
    with pytest.raises(LocationOutOfRangeError, match=re.escape(named)):
        _request(default_settings).summarize(latlon=latlon)
    assert station_selection == []


@pytest.mark.usefixtures("station_selection")
@pytest.mark.parametrize("latlon", [(90.0, 0.0), (-90.0, 180.0), (0.0, -180.0), (-90, -180), (90, 180)])
def test_summary_accepts_the_poles_and_the_antimeridian(
    default_settings: Settings, latlon: tuple[float, float]
) -> None:
    """The edges of the range are points on the globe, and the nearest station is picked with no projection."""
    with pytest.raises(_ReachedStationSelection):
        _request(default_settings).summarize(latlon=latlon)


@pytest.mark.usefixtures("station_selection")
def test_summary_by_station_id_refuses_a_station_listed_beyond_the_globe(default_settings: Settings) -> None:
    """A station whose listed position is off the globe is refused as a point is, not summarized at."""
    with pytest.raises(LocationOutOfRangeError, match=re.escape("latitude 95.0 is outside the range -90 to 90")):
        _request(default_settings).summarize_by_station_id(station_id="00001")


@pytest.mark.usefixtures("station_selection")
def test_summary_refuses_a_point_given_as_text_beyond_the_globe(default_settings: Settings) -> None:
    """A coordinate given as text is read as a number first, so it is refused as a number is, not with a TypeError."""
    with pytest.raises(LocationOutOfRangeError, match=re.escape("longitude 373.4 is outside")):
        _request(default_settings).summarize(latlon=("52.5", "373.4"))  # ty: ignore[invalid-argument-type]
