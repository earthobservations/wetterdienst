# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for shared interpolation and summary tools."""

import datetime as dt
import logging
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.core.util import DroppedForHeight, StationsInReach, build_date_grid
from wetterdienst.metadata.resolution import Resolution, reading_interval
from wetterdienst.provider.dwd.observation import DwdObservationRequest

UTC = ZoneInfo("UTC")


@pytest.mark.parametrize(
    ("resolution", "start_date", "end_date", "expected_height", "expected_first"),
    [
        (
            Resolution.MINUTE_10,
            dt.datetime(2024, 1, 1, tzinfo=UTC),
            dt.datetime(2024, 1, 2, tzinfo=UTC),
            145,
            dt.datetime(2024, 1, 1, tzinfo=UTC),
        ),
        (
            Resolution.DAILY,
            dt.datetime(2020, 1, 1, tzinfo=UTC),
            dt.datetime(2020, 3, 1, tzinfo=UTC),
            61,
            dt.datetime(2020, 1, 1, tzinfo=UTC),
        ),
        (
            # a monthly reading is dated to the first, which is what the range is rounded onto
            Resolution.MONTHLY,
            dt.datetime(2020, 1, 15, tzinfo=UTC),
            dt.datetime(2021, 6, 1, tzinfo=UTC),
            17,
            dt.datetime(2020, 1, 1, tzinfo=UTC),
        ),
        (
            Resolution.ANNUAL,
            dt.datetime(2000, 1, 1, tzinfo=UTC),
            dt.datetime(2010, 1, 1, tzinfo=UTC),
            11,
            dt.datetime(2000, 1, 1, tzinfo=UTC),
        ),
    ],
)
def test_build_date_grid_spans_the_window_at_the_resolution(
    resolution: Resolution,
    start_date: dt.datetime,
    end_date: dt.datetime,
    expected_height: int,
    expected_first: dt.datetime,
) -> None:
    """Test that the grid covers the window at the interval the resolution records at."""
    df = build_date_grid(resolution, start_date, end_date)

    assert df.columns == ["date"]
    assert df.height == expected_height
    assert df.get_column("date").min() == expected_first


def test_build_date_grid_snaps_an_off_phase_window_to_the_wall_clock() -> None:
    """Test that a window opening at half past does not carry its phase through the whole series.

    The range is generated from the window and then rounded to the same interval, so a request
    from 00:30 answers for whole hours rather than for every half past -- which is what every
    station's readings are joined onto, by an exact join.
    """
    df = build_date_grid(
        Resolution.HOURLY,
        dt.datetime(2024, 1, 1, 0, 30, tzinfo=UTC),
        dt.datetime(2024, 1, 1, 6, 30, tzinfo=UTC),
    )

    assert df.get_column("date").dt.minute().unique().to_list() == [0]
    assert df.get_column("date").min() == dt.datetime(2024, 1, 1, 1, tzinfo=UTC)


def test_build_date_grid_treats_subdaily_as_hourly() -> None:
    """Test that subdaily gets a grid, at the one interval available for it.

    `reading_interval` declines to name an interval for subdaily -- it is a bucket rather than an
    interval, and DWD takes three Termin readings a day where Meteo-France SYNOP reports every
    three hours. A grid still needs one, and naming it too fine only leaves rows no station has a
    reading for, which is harmless here in a way it is not where a station is measured against how
    much of a window it filled.
    """
    assert reading_interval(Resolution.SUBDAILY) is None

    df = build_date_grid(
        Resolution.SUBDAILY,
        dt.datetime(2024, 1, 1, tzinfo=UTC),
        dt.datetime(2024, 1, 2, tzinfo=UTC),
    )

    assert df.height == 25  # hourly, both ends included


def _ranked(dataset: str, rows: list[dict]) -> pl.DataFrame:
    """Build the shape `filter_by_distance` returns: a row per station and dataset, nearest first."""
    resolution = "daily" if dataset == "climate_summary" else "hourly"
    return pl.DataFrame(
        [{"resolution": resolution, "dataset": dataset, **row} for row in rows],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "distance": pl.Float64,
            "height": pl.Float64,
        },
        orient="row",
    )


def _answer(*rows: tuple[str, str, str, float | None]) -> pl.DataFrame:
    """Build a frame in the shape an interpolation or a summary returns."""
    return pl.DataFrame(
        [dict(zip(("resolution", "dataset", "parameter", "value"), row, strict=True)) for row in rows],
        schema={"resolution": pl.String, "dataset": pl.String, "parameter": pl.String, "value": pl.Float64},
        orient="row",
    )


INTERPOLATABLE = DwdObservationRequest.interpolatable_parameters
TEMPERATURE = ("daily", "climate_summary", "temperature_air_mean_2m")
PRECIPITATION = ("daily", "climate_summary", "precipitation_height")


def test_report_height_exclusions_raises_where_nothing_was_answered() -> None:
    """A request left unanswered by heights alone is a question that cannot be answered as asked.

    Rows of nulls are as unanswered as no rows: an interpolation wants four stations that surround
    the point, so a parameter the exclusions leave with three holds columns and still comes back
    null. Judged on the columns collected rather than on the frame, that case reads as answered and
    goes back to the caller silently, which is the whole thing this is here to do away with.
    """
    from wetterdienst.core.util import report_height_exclusions  # noqa: PLC0415
    from wetterdienst.exceptions import NoStationsWithHeightError  # noqa: PLC0415

    with pytest.raises(NoStationsWithHeightError, match=r"nothing that can answer daily/climate_summary/temperature"):
        report_height_exclusions(
            _answer((*TEMPERATURE, None), (*TEMPERATURE, None)),
            {},
            {TEMPERATURE: DroppedForHeight(9)},
            200.0,
            stations_needed=4,
        )
    # and the same for a parameter that never opened a row at all
    with pytest.raises(NoStationsWithHeightError, match=r"at 200\.0 m"):
        report_height_exclusions(_answer(), {}, {TEMPERATURE: DroppedForHeight(9)}, 200.0, stations_needed=4)


def test_report_height_exclusions_warns_where_something_still_answers(caplog: pytest.LogCaptureFixture) -> None:
    """A parameter left unanswered beside one that answered is named, not raised.

    There is a result to read the warning against, and taking the whole request down over one of
    its parameters would throw away readings the caller can use.
    """
    from wetterdienst.core.util import report_height_exclusions  # noqa: PLC0415

    df = _answer((*PRECIPITATION, 1.2), (*TEMPERATURE, None))
    with caplog.at_level(logging.WARNING):
        report_height_exclusions(df, {}, {TEMPERATURE: DroppedForHeight(9)}, 200.0, stations_needed=4)
    assert "daily/climate_summary/temperature_air_mean_2m" in caplog.text
    assert "the rest of the result stands" in caplog.text


def test_report_height_exclusions_counts_a_parameter_of_nulls_as_unanswered(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A parameter that produced only nulls does not stand in for a result.

    It used to: any parameter holding a station column made this a warning rather than a refusal,
    columns and answers not being the same thing, so a caller with nothing at all was told so in a
    log line they could not read.
    """
    from wetterdienst.core.util import report_height_exclusions  # noqa: PLC0415
    from wetterdienst.exceptions import NoStationsWithHeightError  # noqa: PLC0415

    df = _answer((*PRECIPITATION, None), (*TEMPERATURE, None))
    with caplog.at_level(logging.WARNING), pytest.raises(NoStationsWithHeightError):
        report_height_exclusions(df, {}, {TEMPERATURE: DroppedForHeight(9)}, 200.0, stations_needed=4)
    assert not caplog.text


def test_report_height_exclusions_keeps_quiet_where_the_answer_stands(caplog: pytest.LogCaptureFixture) -> None:
    """A station turned away where the rest sufficed cost the answer nothing.

    Nor is a request that lost no station to a height worth a word: this runs on every
    interpolation and summary, elevation or not.
    """
    from wetterdienst.core.util import report_height_exclusions  # noqa: PLC0415

    with caplog.at_level(logging.WARNING):
        # the parameter was answered by the stations that kept their heights
        report_height_exclusions(
            _answer((*TEMPERATURE, 3.4), (*TEMPERATURE, None)),
            {},
            {TEMPERATURE: DroppedForHeight(9)},
            200.0,
            stations_needed=4,
        )
        # and nothing was turned away at all
        report_height_exclusions(_answer(), {}, {}, None, stations_needed=4)
    assert not caplog.text


def test_collection_is_done_waits_for_a_parameter_that_has_yet_to_take_a_station() -> None:
    """A parameter every station was turned away from cannot hold the walk open by itself.

    It never opened an entry, so `all(finished)` passes over it, and the walk down the ranking
    stops on the parameters that did open -- reporting it as unanswerable while a station further
    out, still inside the radius, has a height and could have answered it.
    """
    from wetterdienst.core.util import _ParameterData, collection_is_done  # noqa: PLC0415

    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    finished = _ParameterData(grid.with_columns(pl.Series("00011", [1.0, 2.0, 3.0])), finished=True)
    assert collection_is_done({PRECIPITATION: finished}, set())
    # precipitation has what it needs, but every station so far said nothing about temperature
    assert not collection_is_done({PRECIPITATION: finished}, {TEMPERATURE})
    # once temperature has taken one, it speaks for itself again
    assert collection_is_done({PRECIPITATION: finished, TEMPERATURE: finished}, {TEMPERATURE})
    # nothing collected at all is not done, whatever was turned away
    assert not collection_is_done({}, set())


def test_report_height_exclusions_does_not_blame_the_heights_for_what_they_did_not_do(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A parameter that kept the stations it needs failed on something else.

    One height-less station among six leaves five that can be brought to the target, and if the
    answer is still null it is the geometry of where those five stand, or the data they hold. The
    cure the message names -- ask without an elevation -- returns the same nulls, so naming the
    heights here is a wrong diagnosis, and a hard error where there used to be a frame.
    """
    from wetterdienst.core.util import _ParameterData, report_height_exclusions  # noqa: PLC0415

    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    kept = grid.with_columns(pl.Series(station_id, [None, None, None], dtype=pl.Float64) for station_id in "abcde")
    with caplog.at_level(logging.WARNING):
        report_height_exclusions(
            _answer((*TEMPERATURE, None)),
            {TEMPERATURE: _ParameterData(kept)},
            {TEMPERATURE: DroppedForHeight(9)},
            200.0,
            stations_needed=4,
        )
    assert not caplog.text


def test_report_height_exclusions_refuses_only_where_a_parameter_took_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A parameter that took not one station is refused; one that took some is named in the log.

    With nothing taken there is nothing to interpolate from and nothing to wonder about. With three
    taken and one lost, the count is the whole of the evidence -- those four may be four that would
    never have surrounded the point -- and refusing on that takes a frame away from a caller over a
    reason that may not be theirs.
    """
    from wetterdienst.core.util import _ParameterData, report_height_exclusions  # noqa: PLC0415
    from wetterdienst.exceptions import NoStationsWithHeightError  # noqa: PLC0415

    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    kept = grid.with_columns(pl.Series(station_id, [None, None, None], dtype=pl.Float64) for station_id in "abc")
    df = _answer((*TEMPERATURE, None))
    with caplog.at_level(logging.WARNING):
        report_height_exclusions(
            df, {TEMPERATURE: _ParameterData(kept)}, {TEMPERATURE: DroppedForHeight(9)}, 200.0, stations_needed=4
        )
    assert "daily/climate_summary/temperature_air_mean_2m" in caplog.text
    caplog.clear()
    # nothing taken, and the stations that were turned away would have been enough
    with pytest.raises(NoStationsWithHeightError, match=r"nothing that can answer"):
        report_height_exclusions(df, {}, {TEMPERATURE: DroppedForHeight(9)}, 200.0, stations_needed=4)
    # a summary asks for one station, so the same three columns are three answers and go unmentioned
    with caplog.at_level(logging.WARNING):
        report_height_exclusions(
            df, {TEMPERATURE: _ParameterData(kept)}, {TEMPERATURE: DroppedForHeight(9)}, 200.0, stations_needed=1
        )
    assert not caplog.text


def test_collection_is_done_does_not_wait_where_no_station_reports_a_height() -> None:
    """A provider that publishes no heights has nothing for the walk to hold out for.

    FMI has 441 stations and a height for none of them. Holding the walk open for a parameter that
    can never take one would query every station inside the radius, one download each, to arrive at
    the answer the fourth station already gave.
    """
    from wetterdienst.core.util import _ParameterData, collection_is_done  # noqa: PLC0415

    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    finished = _ParameterData(grid.with_columns(pl.Series("00011", [1.0, 2.0, 3.0])), finished=True)
    assert collection_is_done({PRECIPITATION: finished}, set())
    # where some station does report one, the walk goes on until temperature has taken it
    assert not collection_is_done({PRECIPITATION: finished}, {TEMPERATURE})


def test_count_stations_in_reach_asks_per_parameter_radius() -> None:
    """Each parameter is counted inside its own radius, not the widest of the request.

    A quantity that decorrelates fast in space is given a narrower one: at hourly resolution
    precipitation reaches 20 km where temperature reaches 40, so a station at 35 km with a height
    on it answers the question "is there one in reach" for temperature and not for precipitation.
    One answer for the whole request would be the wrong one for at least one of them.
    """
    from wetterdienst.core.util import count_stations_in_reach  # noqa: PLC0415

    metadata = DwdObservationRequest.metadata["hourly"]
    parameters = [
        metadata["temperature_air"]["temperature_air_mean_2m"],
        metadata["precipitation"]["precipitation_height"],
    ]
    df_stations_ranked = pl.concat(
        _ranked(dataset, rows)
        for dataset in ("temperature_air", "precipitation")
        for rows in [
            [
                {"station_id": "00001", "distance": 5.0, "height": None},
                {"station_id": "00002", "distance": 15.0, "height": None},
                {"station_id": "00003", "distance": 35.0, "height": 210.0},
                {"station_id": "00004", "distance": 60.0, "height": 190.0},
            ],
        ]
    )
    counts = count_stations_in_reach(df_stations_ranked, parameters, Settings(), INTERPOLATABLE)
    # 40 km for temperature: three stations, the furthest of them the only one with a height
    assert counts[("hourly", "temperature_air", "temperature_air_mean_2m")] == (3, 1, 35.0)
    # 20 km for precipitation: two stations, and the station that has a height is outside it
    assert counts[("hourly", "precipitation", "precipitation_height")] == (2, 0, None)


def test_unanswerable_at_height_names_what_no_walk_can_reach() -> None:
    """A quantity that falls with height and has no station of known height in reach is unanswerable.

    Whatever the walk downloads, no reading can be brought to the height asked about. A quantity
    that does not fall with height is answered by those same stations as it always was, and with no
    elevation asked for nothing is unanswerable at all.
    """
    from wetterdienst.core.util import unanswerable_at_height  # noqa: PLC0415

    counts = {
        TEMPERATURE: StationsInReach(total=9, with_height=0, furthest_with_height=None),
        PRECIPITATION: StationsInReach(total=9, with_height=0, furthest_with_height=None),
    }
    assert unanswerable_at_height(counts, 200.0, 4) == {TEMPERATURE}
    # one station reporting a height is enough to be worth walking for
    with_one = {TEMPERATURE: StationsInReach(total=9, with_height=1, furthest_with_height=12.0)}
    assert unanswerable_at_height(with_one, 200.0, 4) == set()
    # a point with no station in reach at all -- out at sea, or a mistyped coordinate -- is empty
    # for a reason that has nothing to do with heights
    assert unanswerable_at_height({TEMPERATURE: StationsInReach(0, 0, None)}, 200.0, 4) == set()
    # and neither has a neighbourhood too thin to have answered from in the first place
    assert unanswerable_at_height({TEMPERATURE: StationsInReach(3, 0, None)}, 200.0, 4) == set()
    # which a summary, asking for one station, is not
    assert unanswerable_at_height({TEMPERATURE: StationsInReach(3, 0, None)}, 200.0, 1) == {TEMPERATURE}
    assert unanswerable_at_height(counts, None, 4) == set()


def test_report_height_exclusions_weighs_the_stations_that_held_the_parameter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """What the exclusions took is stations that held the parameter, not stations in the radius.

    Six stations stand within reach and two of them report the parameter in the window asked for,
    one without a height. Counting the radius says four were there to be had and blames the
    heights; counting what was turned away says two, which is short of the four an interpolation
    wants either way. Sending that caller back to ask without an elevation returns the same nulls.
    """
    from wetterdienst.core.util import _ParameterData, report_height_exclusions  # noqa: PLC0415

    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    kept = grid.with_columns(pl.Series("a", [None, None, None], dtype=pl.Float64))
    param_dict = {TEMPERATURE: _ParameterData(kept)}
    df = _answer((*TEMPERATURE, None))
    with caplog.at_level(logging.WARNING):
        # one taken and one turned away is two, and four are wanted: not the exclusions' doing
        report_height_exclusions(df, param_dict, {TEMPERATURE: DroppedForHeight(1)}, 200.0, stations_needed=4)
    assert not caplog.text
    with caplog.at_level(logging.WARNING):
        # three turned away would have made four, so they are named
        report_height_exclusions(df, param_dict, {TEMPERATURE: DroppedForHeight(3)}, 200.0, stations_needed=4)
    assert "daily/climate_summary/temperature_air_mean_2m" in caplog.text


def test_count_stations_in_reach_reads_the_nearest_row_of_a_station() -> None:
    """A station gets one row per dataset, and the walk reads the nearest of them.

    The two indexes can disagree about a height, and whichever row happened to sort last would
    answer "is there a station of known height in reach" differently from the station the
    collection loop actually reads -- which decides whether the request is refused before a single
    value is downloaded.
    """
    from wetterdienst.core.util import count_stations_in_reach  # noqa: PLC0415

    parameters = [DwdObservationRequest.metadata["hourly"]["temperature_air"]["temperature_air_mean_2m"]]
    df_stations_ranked = _ranked(
        "temperature_air",
        [
            {"station_id": "00001", "distance": 5.0, "height": 210.0},
            {"station_id": "00001", "distance": 5.2, "height": None},
        ],
    )
    assert count_stations_in_reach(df_stations_ranked, parameters, Settings(), INTERPOLATABLE) == {
        ("hourly", "temperature_air", "temperature_air_mean_2m"): (1, 1, 5.0),
    }


def test_parameters_still_in_reach_stops_at_the_last_station_that_has_a_height() -> None:
    """Past the furthest station of known height, no station left to visit can answer.

    A parameter with one such station in reach that turns out to hold no data would otherwise hold
    the walk open to the end of the ranking, downloading every station left to learn what the
    ranking already said.
    """
    from wetterdienst.core.util import parameters_still_in_reach  # noqa: PLC0415

    counts = {
        TEMPERATURE: StationsInReach(total=9, with_height=1, furthest_with_height=12.0),
        PRECIPITATION: StationsInReach(total=9, with_height=4, furthest_with_height=30.0),
    }
    assert parameters_still_in_reach(counts, 8.0) == {TEMPERATURE, PRECIPITATION}
    assert parameters_still_in_reach(counts, 20.0) == {PRECIPITATION}
    assert parameters_still_in_reach(counts, 31.0) == set()


def test_no_height_in_reach_error_says_what_the_ranking_alone_can_say() -> None:
    """The refusal that costs no download claims only what the station list shows.

    Not one station near the point says how high it stands, so no reading can be brought to the
    height asked about -- true whether or not those stations hold the parameter, which is the
    difference between this and the report that follows a walk.
    """
    from wetterdienst.core.util import no_height_in_reach_error  # noqa: PLC0415

    error = no_height_in_reach_error({TEMPERATURE, PRECIPITATION}, 200.0)
    assert "no station near the point reports a height of its own" in str(error)
    assert "nothing can be brought to 200.0 m" in str(error)
    # both parameters named, in a settled order
    assert "daily/climate_summary/precipitation_height, daily/climate_summary/temperature_air_mean_2m" in str(error)
    # and the remedy that applies to a request named by a station id as much as one by coordinates
    assert "naming a station id instead asks at that station's own height" in str(error)


def test_count_stations_in_reach_passes_over_what_the_walk_would_not_collect() -> None:
    """A parameter that cannot be interpolated at all is not counted.

    It can never be unanswerable for want of a height, so counting it would leave the set of
    unanswerable parameters short of the set of counted ones for ever -- and the refusal that costs
    no download, which asks whether those two are the same, would never be reached. Every station
    inside the radius would be fetched to arrive at the answer the station list already held.
    """
    from wetterdienst.core.util import count_stations_in_reach  # noqa: PLC0415

    metadata = DwdObservationRequest.metadata["daily"]["climate_summary"]
    # precipitation_form is the one member of daily/kl that is not interpolatable
    parameters = [metadata["temperature_air_mean_2m"], metadata["precipitation_form"]]
    df_stations_ranked = _ranked("climate_summary", [{"station_id": "00001", "distance": 5.0, "height": None}])
    counts = count_stations_in_reach(df_stations_ranked, parameters, Settings(), INTERPOLATABLE)
    assert set(counts) == {("daily", "climate_summary", "temperature_air_mean_2m")}


def test_report_height_exclusions_names_the_uncertain_losses_beside_the_certain_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A parameter that kept a station is still named when another is refused outright.

    The exception speaks only for what is certain, so a parameter emptied under the weaker light
    would otherwise go unmentioned altogether -- the warning branch having been passed over on the
    way to the refusal.
    """
    from wetterdienst.core.util import _ParameterData, report_height_exclusions  # noqa: PLC0415
    from wetterdienst.exceptions import NoStationsWithHeightError  # noqa: PLC0415

    maximum = ("daily", "climate_summary", "temperature_air_max_2m")
    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    kept = grid.with_columns(pl.Series(station_id, [None, None, None], dtype=pl.Float64) for station_id in "ab")
    df = _answer((*TEMPERATURE, None), (*maximum, None))
    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(NoStationsWithHeightError, match=r"temperature_air_mean_2m at 200\.0 m"),
    ):
        report_height_exclusions(
            df,
            {maximum: _ParameterData(kept)},
            {TEMPERATURE: DroppedForHeight(5), maximum: DroppedForHeight(3)},
            200.0,
            stations_needed=4,
        )
    assert "daily/climate_summary/temperature_air_max_2m" in caplog.text


def test_report_height_exclusions_counts_a_station_near_enough_to_answer_alone() -> None:
    """A station turned away from under the point cost one station, not four.

    An interpolation answers from a single station standing inside the nearby-station distance,
    without the four a hull wants around the point. Hold the exclusions to four and the caller
    standing on top of the one station in reach -- and it without a height -- is told nothing at
    all, though that station is exactly what the elevation cost them.
    """
    from wetterdienst.core.util import report_height_exclusions  # noqa: PLC0415
    from wetterdienst.exceptions import NoStationsWithHeightError  # noqa: PLC0415

    df = _answer((*TEMPERATURE, None))
    lost_nearby = {TEMPERATURE: DroppedForHeight(count=1, nearest=0.5)}
    with pytest.raises(NoStationsWithHeightError, match=r"nothing that can answer"):
        report_height_exclusions(df, {}, lost_nearby, 200.0, stations_needed=4, nearby_station_distance=1.0)
    # the same station a kilometre further out answers nothing on its own, and four is the bar again
    lost_far = {TEMPERATURE: DroppedForHeight(count=1, nearest=8.0)}
    report_height_exclusions(df, {}, lost_far, 200.0, stations_needed=4, nearby_station_distance=1.0)
    # nor where the shortcut is switched off
    report_height_exclusions(df, {}, lost_nearby, 200.0, stations_needed=4, nearby_station_distance=None)


def test_count_stations_in_reach_counts_a_station_under_its_own_dataset() -> None:
    """A station is counted for the dataset whose index it stands in.

    The ranking carries a row per station and dataset, so a station that reports a height in the
    hourly index would otherwise say there is a height in reach for a daily parameter it can never
    answer -- holding the walk open to its distance, and suppressing the refusal that costs no
    download.
    """
    from wetterdienst.core.util import count_stations_in_reach  # noqa: PLC0415

    daily = DwdObservationRequest.metadata["daily"]["climate_summary"]["temperature_air_mean_2m"]
    df_stations_ranked = pl.concat(
        [
            _ranked("climate_summary", [{"station_id": "00001", "distance": 5.0, "height": None}]),
            _ranked("temperature_air", [{"station_id": "00002", "distance": 39.0, "height": 210.0}]),
        ],
    )
    counts = count_stations_in_reach(df_stations_ranked, [daily], Settings(), INTERPOLATABLE)
    # one station, no height, and nothing to walk out to 39 km for
    assert counts[("daily", "climate_summary", "temperature_air_mean_2m")] == (1, 0, None)


def test_report_height_exclusions_claims_a_standing_result_only_where_there_is_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Nothing answered is not "the rest of the result stands".

    A parameter that kept a station or two and still answered nothing is named rather than raised,
    and where it is the whole request the frame that comes back is null throughout -- so there is no
    rest of it to stand.
    """
    from wetterdienst.core.util import _ParameterData, report_height_exclusions  # noqa: PLC0415

    grid = build_date_grid(Resolution.DAILY, dt.datetime(2022, 1, 1, tzinfo=UTC), dt.datetime(2022, 1, 3, tzinfo=UTC))
    kept = grid.with_columns(pl.Series(station_id, [None, None, None], dtype=pl.Float64) for station_id in "ab")
    param_dict = {TEMPERATURE: _ParameterData(kept)}
    with caplog.at_level(logging.WARNING):
        report_height_exclusions(
            _answer((*TEMPERATURE, None)),
            param_dict,
            {TEMPERATURE: DroppedForHeight(9)},
            200.0,
            stations_needed=4,
        )
    assert "the rest of the result stands" not in caplog.text
    caplog.clear()
    # beside a parameter that did answer, there is
    with caplog.at_level(logging.WARNING):
        report_height_exclusions(
            _answer((*TEMPERATURE, None), (*PRECIPITATION, 1.2)),
            param_dict,
            {TEMPERATURE: DroppedForHeight(9)},
            200.0,
            stations_needed=4,
        )
    assert "the rest of the result stands" in caplog.text
