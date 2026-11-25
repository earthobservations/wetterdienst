# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parameter names as columns of `filter` and `sort`: the names, the refusals, the frames (GH-4419).

The names are looked up among the parameters of the request and nowhere else; a word that is none is refused with the
closest of the request's. What a name does to a frame is checked by hand here on small frames of two stations, the
oracle of `tests/ui/row_options_oracle.py` holds the reader and the surfaces to the same on the stub network.
"""

from __future__ import annotations

import datetime as dt
import random
import string
from typing import Any

import polars as pl
import pytest

from wetterdienst import Wetterdienst
from wetterdienst.model.row_selection import (
    FILTER_COLUMNS,
    RESERVED_WORDS,
    SORT_COLUMNS,
    STEP_TWO_WORDS,
    ParameterColumn,
    ParameterNames,
    RowSelectionError,
    RowSelectionRefusedError,
    parse_filter,
    parse_row_selection,
    parse_sort,
)
from wetterdienst.model.values import _requested_wide_columns
from wetterdienst.provider.dwd.observation import DwdObservationRequest


def _parameters(*texts: str) -> list[Any]:
    """Resolve parameters of the DWD observation network as the request does."""
    return list(DwdObservationRequest(parameters=list(texts), start="2020-01-01", end="2020-01-02").parameters)


def _names(*texts: str, humanize: bool = True) -> ParameterNames:
    return ParameterNames.of(_parameters(*texts), humanize=humanize)


DAILY = ("daily/climate_summary/temperature_air_min_2m", "daily/climate_summary/wind_gust_max")
STAMP = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)


def test_a_name_is_the_parameters_own_name_or_its_name_after_its_dataset() -> None:
    """Both spellings reach the parameter, in either case; the written name comes back as the answer writes it."""
    names = _names(*DAILY)
    for written in ("temperature_air_min_2m", "TEMPERATURE_AIR_MIN_2M", "climate_summary_temperature_air_min_2m"):
        selection = parse_row_selection(filter=f"{written}<0", parameters=names)
        assert selection is not None
        ((name, column),) = selection.names
        assert column.parameter == "temperature_air_min_2m"
        assert (column.resolution, column.dataset) == ("daily", "climate_summary")
        assert name == written.lower() or name == "temperature_air_min_2m"
        assert selection.conditions[0].column == name
    assert names.resolutions == ("daily",)
    assert names.unwritable == ()


def test_the_names_are_in_the_order_they_are_written_once_each() -> None:
    """Conditions first, then the keys; a name written twice, or in both, is one parameter once."""
    selection = parse_row_selection(
        filter="wind_gust_max>=10,temperature_air_min_2m<0,wind_gust_max<30",
        sort="-temperature_air_min_2m,wind_gust_max",
        first=3,
        parameters=_names(*DAILY),
    )
    assert selection is not None
    assert [name for name, _ in selection.names] == ["wind_gust_max", "temperature_air_min_2m"]
    assert selection.by_names
    assert selection.echo()["filter"] == "wind_gust_max>=10,temperature_air_min_2m<0,wind_gust_max<30"
    assert selection.echo()["sort"] == "-temperature_air_min_2m,wind_gust_max"


def test_a_selection_without_a_name_binds_to_none() -> None:
    """No name, no `names`: the row of the choice is the reading as it was in #4411."""
    selection = parse_row_selection(filter="value<0,month=12", sort="-value", first=1, parameters=_names(*DAILY))
    assert selection is not None
    assert selection.names == ()
    assert not selection.by_names


def test_a_word_that_is_no_parameter_is_refused_with_the_closest_of_the_requests() -> None:
    """The refusal has the position, the word, what is allowed and a `did you mean`."""
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="value>0,temperature_air_min_2<0", parameters=_names(*DAILY))
    error = caught.value
    assert error.option == "filter"
    assert error.position == 9
    assert "'temperature_air_min_2'" in str(error)
    assert "Did you mean temperature_air_min_2m?" in str(error)
    assert "or a parameter of this request (temperature_air_min_2m, wind_gust_max)" in str(error)
    assert len(str(error)) < 700
    with pytest.raises(RowSelectionError, match="Did you mean wind_gust_max"):
        parse_row_selection(sort="-wind_gust", parameters=_names(*DAILY))
    # a word that is close to nothing: no suggestion, still the list
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="xyzzy<1", parameters=_names(*DAILY))
    assert "Did you mean" not in str(caught.value)
    assert "wind_gust_max" in str(caught.value)


def test_a_parameter_the_request_does_not_ask_for_is_no_name() -> None:
    """Only the request's own parameters are names: another of the dataset is refused."""
    with pytest.raises(RowSelectionError, match="is not a column of this option"):
        parse_row_selection(filter="temperature_air_max_2m>20", parameters=_names(*DAILY))


@pytest.mark.parametrize("column", sorted(set(FILTER_COLUMNS) | set(SORT_COLUMNS)))
def test_a_column_of_the_options_is_a_column_even_where_a_parameter_has_its_name(column: str) -> None:
    """A word that is a column is never looked up among the names: `month` is the month of the timestamp."""
    names = _names(*DAILY)
    # even a request that holds a parameter called like the column (none does, see the registry test below)
    clash = ParameterNames(
        lookup={column: (("month", next(iter(names.lookup.values()))[0][1]),)}, resolutions=("daily",), listed=(column,)
    )
    if column in FILTER_COLUMNS:
        for bound in (None, clash):
            assert parse_filter(f"{column}=1", bound)[0].column == column
    if column in SORT_COLUMNS:
        for bound in (None, clash):
            assert parse_sort(column, bound)[0].column == column


def test_a_parameter_named_like_a_column_cannot_be_reached_by_its_bare_name() -> None:
    """The one place a clash is told: the word is the column, so the bare name never means the parameter."""
    for word in sorted(RESERVED_WORDS):
        assert word.lower() == word


def test_no_parameter_of_any_provider_is_named_like_a_column_or_a_word_that_is_told_what_to_do_instead() -> None:
    """The refusal of `RESERVED_WORDS` without the request (the REST model) is right while no parameter has one."""
    clashes = []
    unwritable = 0
    checked = 0
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            for resolution in Wetterdienst.resolve(provider, network).metadata:
                for dataset in resolution:
                    for parameter in dataset:
                        for name in (parameter.name, parameter.name_original):
                            if name and name.lower() in RESERVED_WORDS:
                                clashes.append((provider, network, dataset.name, name))
                        unwritable += not parameter.name.isidentifier()
                        checked += 1
    assert checked > 2000  # the registry is read, not an empty loop
    assert clashes == []
    # the canonical names are all words; only a provider's own names have signs a filter cannot write
    assert unwritable == 0


def test_a_name_in_two_datasets_is_refused_with_the_name_after_its_dataset() -> None:
    """`temperature_air_2m` is in `temperature_air` and `dew_point` of the hourly data: say which."""
    names = _names("hourly/temperature_air/temperature_air_2m", "hourly/dew_point/temperature_air_2m")
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="temperature_air_2m<0", parameters=names)
    message = str(caught.value)
    assert "is the name of 2 parameters of this request" in message
    assert "temperature_air_temperature_air_2m, dew_point_temperature_air_2m" in message
    assert "The datasets are temperature_air, dew_point" in message
    selection = parse_row_selection(
        filter="temperature_air_temperature_air_2m<0,dew_point_temperature_air_2m>-5", parameters=names
    )
    assert selection is not None
    assert [c.dataset for _, c in selection.names] == ["temperature_air", "dew_point"]
    # one parameter in one dataset is not ambiguous
    parse_row_selection(
        filter="temperature_dew_point_2m>0",
        parameters=_names("hourly/temperature_air/temperature_air_2m", "hourly/dew_point/temperature_dew_point_2m"),
    )


def test_the_column_of_the_wide_shape_is_what_the_answer_calls_it() -> None:
    """`ParameterColumn.wide` is the column `_widen_df` writes: bare for one dataset, after the dataset for several."""
    for texts in (
        DAILY,
        ("hourly/temperature_air/temperature_air_2m", "hourly/dew_point/temperature_dew_point_2m"),
        ("daily/climate_summary", "daily/more_precip"),
    ):
        for humanize in (True, False):
            parameters = _parameters(*texts)
            names = ParameterNames.of(parameters, humanize=humanize)
            wide = {column.wide for entries in names.lookup.values() for _, column in entries}
            asked = set(_requested_wide_columns(parameters, humanize=humanize))
            assert wide == asked, (texts, humanize)


def test_a_provider_own_name_with_a_sign_cannot_be_written_and_the_refusal_says_why() -> None:
    """With `humanize=false` a name like `mittel von ts05` is no word: told apart from a typo."""
    names = _names("daily/climate_summary", humanize=False)
    assert "tnk" in names.lookup
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="tnx<0", parameters=names)
    assert "Did you mean" in str(caught.value)
    odd = ParameterNames(unwritable=("Anzahl Tage",), listed=("tnk",), lookup=names.lookup, resolutions=("daily",))
    with pytest.raises(RowSelectionError, match=r"1 parameter\(s\) of this request have a name with a sign"):
        parse_row_selection(filter="zzz<0", parameters=odd)


def test_value_beside_a_name_and_names_over_several_resolutions_are_refused() -> None:
    """`value` is one parameter's reading and a name a timestamp: not in one selection; one resolution only."""
    names = _names(*DAILY)
    for options in ({"filter": "value<0,wind_gust_max>1"}, {"filter": "wind_gust_max>1", "sort": "value", "first": 1}):
        with pytest.raises(RowSelectionRefusedError, match="`value` and a parameter's name are in one selection"):
            parse_row_selection(**options, parameters=names)
    mixed = _names("daily/climate_summary/temperature_air_min_2m", "hourly/temperature_air/temperature_air_2m")
    with pytest.raises(RowSelectionRefusedError, match=r"has 2 \(daily, hourly\)"):
        parse_row_selection(filter="temperature_air_min_2m<0", parameters=mixed)
    # no name, no refusal: `value` over several resolutions is what it was
    assert parse_row_selection(filter="value<0", parameters=mixed) is not None


def test_a_selection_read_without_the_request_accepts_what_can_be_a_name() -> None:
    """The REST model and the command line read the text alone: a word that can be a name passes."""
    selection = parse_row_selection(filter="wind_gust_max>=10", sort="temperature_air_min_2m", first=2)
    assert selection is not None
    assert selection.names == ()
    assert [c.column for c in selection.conditions] == ["wind_gust_max"]
    assert [k.column for k in selection.sort] == ["temperature_air_min_2m"]
    for text, hint in (("parameter=wind", "A parameter is a column by its own name"), ("timestamp>2", "window")):
        with pytest.raises(RowSelectionError, match=hint):
            parse_filter(text)
    for text in ("5<3", "a-b<3", "_<1", "wind gust<3"):
        with pytest.raises(RowSelectionError):
            parse_filter(text)
    with pytest.raises(RowSelectionError, match="is not a column of this option"):
        parse_sort("wind gust")
    # `by` takes no name: groups are the calendar and the station
    with pytest.raises(RowSelectionError, match="is not a column of this option"):
        parse_row_selection(sort="wind_gust_max", first=1, by="wind_gust_max")


def test_the_reserved_words_are_no_columns_and_no_names_with_or_without_the_request() -> None:
    """`window`, `aggregate`, `count`, `min` and the others are refused as names, a 422 each as in #4428."""
    assert STEP_TWO_WORDS <= RESERVED_WORDS
    assert {"count", "min", "max", "mean", "sum"} <= RESERVED_WORDS
    for names in (None, _names(*DAILY)):
        for word in (*sorted(STEP_TWO_WORDS), "count", "min", "max", "mean", "sum"):
            with pytest.raises(RowSelectionError):
                parse_filter(f"{word}<1", names)
            with pytest.raises(RowSelectionError):
                parse_sort(word, names)
    for word in STEP_TWO_WORDS:
        with pytest.raises(RowSelectionError):
            parse_row_selection(sort="value", first=1, by=word)


def _long(rows: list[tuple[str, str, int, float | None]]) -> pl.DataFrame:
    """Build a long frame of `(station, parameter, day, value)`, as a reader has it: by station, parameter, time."""
    frame = pl.DataFrame(
        {
            "station_id": [r[0] for r in rows],
            "resolution": ["daily"] * len(rows),
            "dataset": ["climate_summary"] * len(rows),
            "parameter": [r[1] for r in rows],
            "timestamp": [STAMP + dt.timedelta(days=r[2]) for r in rows],
            "value": [r[3] for r in rows],
            "quality_flags": ["1"] * len(rows),
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC"), "value": pl.Float64},
    )
    return frame.sort("station_id", "parameter", "timestamp", maintain_order=True)


def _frame() -> pl.DataFrame:
    """Two stations, three parameters, five days: the gust is missing on day 1 and on day 3 of the first station."""
    rows = []
    tmin = {1: [-3.0, 2.0, -1.0, 4.0, -5.0], 2: [-6.0, -2.0, 1.0, -4.0, 0.0]}
    gust = {1: [20.0, None, 18.0, None, 9.0], 2: [3.0, 21.0, 30.0, 25.0, 17.2]}
    tmax = {1: [1.0, 5.0, 2.0, 8.0, -1.0], 2: [0.0, 1.0, 3.0, 1.0, 2.0]}
    for station in (1, 2):
        for day in range(5):
            rows.append((f"{station:05d}", "temperature_air_min_2m", day, tmin[station][day]))
            rows.append((f"{station:05d}", "wind_gust_max", day, gust[station][day]))
            rows.append((f"{station:05d}", "temperature_air_max_2m", day, tmax[station][day]))
    return _long([r for r in rows if r[3] is not None])


_NAMES = _names(
    "daily/climate_summary/temperature_air_min_2m",
    "daily/climate_summary/wind_gust_max",
    "daily/climate_summary/temperature_air_max_2m",
)


def _choose(frame: pl.DataFrame, **options: Any) -> pl.DataFrame:  # noqa: ANN401
    selection = parse_row_selection(parameters=_NAMES, **options)
    assert selection is not None
    return selection.apply(frame)


def _stamps(frame: pl.DataFrame) -> list[tuple[str, int]]:
    """Give the (station, day) of a frame, once each, in the order of its first row."""
    days = [(r["station_id"], (r["timestamp"] - STAMP).days) for r in frame.iter_rows(named=True)]
    return list(dict.fromkeys(days))


def test_both_conditions_must_hold_at_one_timestamp_and_a_missing_value_meets_none() -> None:
    """Frost with gusts: days 0 and 2 of station 1, days 1 and 3 of station 2; not day 1 of station 1 (no gust)."""
    answer = _choose(_frame(), filter="temperature_air_min_2m<0,wind_gust_max>=17.2")
    assert sorted(_stamps(answer)) == [("00001", 0), ("00001", 2), ("00002", 1), ("00002", 3)]
    # the rows are those of every requested parameter at those days: three of each
    assert answer.height == 12
    assert set(answer.get_column("parameter")) == {"temperature_air_min_2m", "wind_gust_max", "temperature_air_max_2m"}
    # a station's rows by time, then parameter (not by parameter: a cut of the answer must keep every parameter)
    assert answer.get_column("station_id").to_list() == ["00001"] * 6 + ["00002"] * 6
    one = answer.filter(pl.col("station_id") == "00001")
    assert (
        one.get_column("parameter").to_list()
        == ["temperature_air_max_2m", "temperature_air_min_2m", "wind_gust_max"] * 2
    )
    assert one.get_column("timestamp").to_list() == [STAMP] * 3 + [STAMP + dt.timedelta(days=2)] * 3
    # a cut of it keeps the first timestamps with all their parameters
    assert _choose(_frame(), filter="temperature_air_min_2m<0,wind_gust_max>=17.2", max_rows=4).get_column(
        "parameter"
    ).to_list() == ["temperature_air_max_2m", "temperature_air_min_2m", "wind_gust_max", "temperature_air_max_2m"]
    # a day that meets one condition and lacks the other is not there: day 4 of station 1 has a gust of 9
    assert ("00001", 4) not in _stamps(answer)


def test_a_missing_value_is_not_met_by_any_operator_not_even_not_equal() -> None:
    """Day 1 and day 3 of station 1 have no gust: `!=` does not meet them either."""
    answer = _choose(_frame(), filter="wind_gust_max!=18")
    assert ("00001", 1) not in _stamps(answer)
    assert ("00001", 3) not in _stamps(answer)
    assert ("00001", 2) not in _stamps(answer)  # 18 itself
    assert ("00001", 0) in _stamps(answer)


def test_the_value_of_a_parameter_is_the_value_at_the_same_timestamp_not_the_value_of_the_row() -> None:
    """A condition on the gust keeps the temperature rows of the days the gust met it."""
    answer = _choose(_frame(), filter="wind_gust_max>=30")
    assert answer.height == 3
    assert answer.filter(pl.col("parameter") == "temperature_air_min_2m").get_column("value").to_list() == [1.0]
    assert answer.get_column("station_id").unique().to_list() == ["00002"]


def test_the_wind_on_the_coldest_days_ranks_timestamps_not_rows() -> None:
    """`sort=temperature_air_min_2m&first=2` keeps two days of each station with all three parameters, not two rows."""
    answer = _choose(_frame(), sort="temperature_air_min_2m", first=2)
    assert answer.height == 4 * 3
    # the order of the answer: the coldest first, whatever the station
    assert _stamps(answer) == [("00002", 0), ("00001", 4), ("00002", 3), ("00001", 0)]


def test_a_timestamp_where_the_sorted_parameter_has_no_value_has_no_place() -> None:
    """The gust is missing on day 1 of station 1: it is not among the first, and comes last without `first`."""
    first = _choose(_frame(), sort="-wind_gust_max", first=10)
    assert ("00001", 1) not in _stamps(first)
    assert ("00001", 3) not in _stamps(first)
    ordered = _choose(_frame(), sort="-wind_gust_max")
    assert _stamps(ordered)[-2:] == [("00001", 1), ("00001", 3)]
    assert _stamps(ordered)[0] == ("00002", 2)


def test_the_groups_of_first_are_station_and_resolution_not_parameter() -> None:
    """`by=none` ranks the timestamps of both stations together: the one coldest day, every parameter of it."""
    answer = _choose(_frame(), sort="temperature_air_min_2m", first=1, by="none")
    assert _stamps(answer) == [("00002", 0)]
    assert answer.height == 3
    by_year = _choose(_frame(), sort="-wind_gust_max", first=1, by="year")
    assert _stamps(by_year) == [("00002", 2)]


def test_ties_of_the_last_timestamp_are_kept_whole() -> None:
    """Equal values of the sorted parameter tie, and all their timestamps come with all their parameters."""
    rows = [
        (s, p, d, 1.0 if p == "wind_gust_max" else float(d))
        for s in ("00001",)
        for d in range(4)
        for p in ("wind_gust_max", "temperature_air_min_2m")
    ]
    answer = _choose(_long(rows), sort="wind_gust_max", first=1)
    assert len(_stamps(answer)) == 4
    assert answer.height == 8


def test_a_cut_of_a_station_to_max_rows_leaves_a_timestamp_whole() -> None:
    """The rows held for a later step keep the timestamps they cut into: their sort value is in the row that was cut."""
    selection = parse_row_selection(sort="-wind_gust_max", max_rows=4, parameters=_NAMES)
    assert selection is not None
    reduced = selection.reduce_station(_frame().filter(pl.col("station_id") == "00002"))
    station = selection.cap_station(reduced, held=True)
    # 4 rows are cut in the second day's rows: the timestamp is kept whole, 6 rows
    assert station.height == 6
    assert len(_stamps(station)) == 2
    # the rows `query` yields are cut exactly
    assert selection.cap_station(reduced).height == 4
    # and the whole is cut exactly, as the last step
    assert selection.cap(selection.finish([station])).height == 4


def test_a_condition_on_a_parameter_the_station_does_not_deliver_meets_nothing() -> None:
    """A station without the gust has no timestamp that meets a condition on it, and no error."""
    without = _frame().filter(pl.col("parameter") != "wind_gust_max")
    assert _choose(without, filter="wind_gust_max>=0").is_empty()
    assert _choose(without, sort="wind_gust_max", first=3).is_empty()
    # sorting without `first` keeps every row; the missing key is last for all
    assert _choose(without, sort="wind_gust_max").height == without.height


def _wide(rows: list[tuple[str, int, float | None, float | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "station_id": [r[0] for r in rows],
            "resolution": ["daily"] * len(rows),
            "dataset": ["climate_summary"] * len(rows),
            "timestamp": [STAMP + dt.timedelta(days=r[1]) for r in rows],
            "temperature_air_min_2m": [r[2] for r in rows],
            "wind_gust_max": [r[3] for r in rows],
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
    )


def test_the_wide_shape_judges_the_columns_it_has_and_adds_none_to_the_answer() -> None:
    """A wide row is the timestamp: names are its columns; a column the station lacks is missing, not added."""
    frame = _wide(
        [("00001", 0, -3.0, 20.0), ("00001", 1, 2.0, None), ("00001", 2, -1.0, 18.0), ("00002", 0, -6.0, 3.0)]
    )
    answer = _choose(frame, filter="temperature_air_min_2m<0,wind_gust_max>=17.2")
    assert answer.columns == frame.columns
    assert answer.get_column("timestamp").to_list() == [STAMP, STAMP + dt.timedelta(days=2)]
    without = frame.drop("wind_gust_max")
    assert _choose(without, filter="wind_gust_max>=0").is_empty()
    kept = _choose(without, sort="-temperature_air_min_2m", first=1)
    assert kept.columns == without.columns
    assert kept.height == 2  # one timestamp of each station
    assert _choose(frame, sort="-wind_gust_max").get_column("wind_gust_max").to_list() == [20.0, 18.0, 3.0, None]


def test_a_wide_row_without_the_sorted_value_has_no_place_in_first() -> None:
    """The wide frame keeps the days a parameter lacks as null rows: a `first` above the valid ones leaves them out."""
    frame = _wide(
        [("00001", 0, -3.0, 20.0), ("00001", 1, 2.0, None), ("00001", 2, -1.0, 18.0), ("00002", 0, -6.0, None)]
    )
    kept = _choose(frame, sort="-wind_gust_max", first=10)
    assert kept.get_column("wind_gust_max").to_list() == [20.0, 18.0]
    # the same of a long frame, where the row of the missing value is not there at all
    long = _frame().filter(pl.col("station_id") == "00001")
    assert ("00001", 1) not in _stamps(_choose(long, sort="-wind_gust_max", first=10))


def test_a_wide_frame_with_two_datasets_is_judged_by_the_prefixed_names() -> None:
    """With two datasets the column is `dataset_name`, and either spelling reaches it."""
    names = _names("daily/climate_summary/wind_gust_max", "daily/more_precip/snow_depth_new")
    wide = {column.parameter: column.wide for entries in names.lookup.values() for _, column in entries}
    assert wide["wind_gust_max"] == "climate_summary_wind_gust_max"
    assert wide["snow_depth_new"].endswith("_snow_depth_new")
    frame = pl.DataFrame(
        {
            "station_id": ["00001"] * 3,
            "resolution": ["daily"] * 3,
            "dataset": [None] * 3,
            "timestamp": [STAMP + dt.timedelta(days=d) for d in range(3)],
            wide["wind_gust_max"]: [20.0, 3.0, 18.0],
            wide["snow_depth_new"]: [0.0, 5.0, 12.0],
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC"), "dataset": pl.String},
    )
    for text in (
        "wind_gust_max>=10,snow_depth_new>1",
        f"{wide['wind_gust_max']}>=10,{wide['snow_depth_new']}>1",
    ):
        selection = parse_row_selection(filter=text, parameters=names)
        assert selection is not None
        assert selection.apply(frame).get_column("timestamp").to_list() == [STAMP + dt.timedelta(days=2)]


def test_the_choice_is_the_same_whatever_the_order_the_rows_come_in() -> None:
    """A property: the rows chosen do not depend on how the frame is ordered."""
    rng = random.Random("names-order")  # noqa: S311
    frame = _frame()
    for options in (
        {"filter": "temperature_air_min_2m<0,wind_gust_max>=10"},
        {"sort": "-wind_gust_max,temperature_air_min_2m", "first": 3},
        {"filter": "wind_gust_max>=3", "sort": "temperature_air_min_2m", "first": 2, "by": "none"},
    ):
        want = _choose(frame, **options)
        for _ in range(5):
            shuffled = frame.sample(fraction=1.0, shuffle=True, seed=rng.randint(0, 10**6))
            got = _choose(shuffled, **options)
            key = ["station_id", "parameter", "timestamp"]
            assert got.sort(key).equals(want.sort(key)), options


def _random_name_text(rng: random.Random, kind: str) -> str:
    words = (
        "wind_gust_max",
        "temperature_air_min_2m",
        "WIND_GUST_MAX",
        "value",
        "month",
        "x",
        "wind gust",
        "5",
        "_",
        "a-b",
    )
    pieces = []
    for _ in range(rng.randint(0, 5)):
        word = rng.choice(words)
        if kind == "filter":
            pieces.append(
                word
                + rng.choice(["", "<", ">=", "!=", "=", "==", "<>", " <= "])
                + rng.choice(["-20", "0.5", "1e3", "nan", "", "x"])
                + (f"|{rng.choice(['1', '2.5', 'x'])}" if rng.random() < 0.3 else "")
            )
        else:
            pieces.append(rng.choice(["", "-"]) + word)
    text = rng.choice([",", ", ", ",,"]).join(pieces)
    if rng.random() < 0.3 and text:
        i = rng.randrange(len(text))
        text = text[:i] + rng.choice(string.printable + "ä☃\x00" + chr(0x202E)) + text[i + rng.randint(0, 2) :]
    return text


@pytest.mark.parametrize("kind", ["filter", "sort"])
@pytest.mark.parametrize("bound", [False, True], ids=["alone", "with the request"])
def test_nothing_but_the_errors_of_the_parser_comes_out_of_any_text_with_names(*, kind: str, bound: bool) -> None:
    """Words that are names, nearly names and hostile: a selection, or `RowSelectionError`, never anything else."""
    names = _NAMES if bound else None
    rng = random.Random(f"names-{kind}-{bound}")  # noqa: S311
    parse = parse_filter if kind == "filter" else parse_sort
    parsed = refused = 0
    for _ in range(20_000):
        text = _random_name_text(rng, kind)
        try:
            result = parse(text, names)
        except RowSelectionError as error:
            refused += 1
            checked = (error.option, error.position, len(str(error)))
            assert checked[0] == kind
            assert checked[1] is None or 1 <= checked[1] <= max(len(text), 1) + 1
            assert checked[2] < 1500
        else:
            parsed += 1
            assert all(item.column == item.column.lower() or bound for item in result)
    assert parsed > 200
    assert refused > 200


def test_hostile_text_is_never_read_as_an_expression() -> None:
    """SQL, polars, Python and format strings in a name's place are words that are no parameter."""
    hostile = (
        "pl.col('a')<1",
        "__import__('os')<1",
        "wind_gust_max; DROP TABLE x<1",
        "wind_gust_max OR 1=1",
        "(wind_gust_max)<1",
        "wind_gust_max+1<5",
        "abs(wind_gust_max)<1",
        "{wind_gust_max}<1",
        "wind_gust_max/2<1",
        "wind_gust_max<wind_gust_max",
        "`wind_gust_max`<1",
        '"wind_gust_max"<1',
        "wind_gust_max.value<1",
        "wind_gust_max<1 AND temperature_air_min_2m<0",
        "wind_gust_max<1;temperature_air_min_2m<0",
    )
    for text in hostile:
        with pytest.raises(RowSelectionError):
            parse_filter(text, _NAMES)
        with pytest.raises(RowSelectionError):
            parse_filter(text)


def test_the_text_of_a_refusal_is_bounded_by_the_names_it_lists() -> None:
    """A request of 400 parameters lists twelve and counts the rest: the text does not grow with the request."""
    parameters = _parameters("daily/climate_summary")
    names = ParameterNames.of(parameters, humanize=True)
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="zzz<1", parameters=names)
    assert "and 2 more" in str(caught.value) or len(parameters) <= 12
    assert len(str(caught.value)) < 800
    long_word = "t" * 380
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter=f"{long_word}<1", parameters=names)
    assert len(str(caught.value)) < 1000


def test_a_name_in_a_request_of_one_dataset_is_the_one_the_answer_writes() -> None:
    """`water_equivalent_snow_depth` is a parameter of `water_equivalent` and also `snow_depth` after its dataset."""
    names = _names("daily/water_equivalent")
    own = parse_row_selection(filter="water_equivalent_snow_depth<1,snow_depth>0", parameters=names)
    assert own is not None
    assert [c.parameter for _, c in own.names] == ["water_equivalent_snow_depth", "snow_depth"]
    # in a request of several datasets the spelling means two parameters, told with the spellings that are unique
    several = _names("daily/water_equivalent", "daily/climate_summary/wind_gust_max")
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="water_equivalent_snow_depth<1", parameters=several)
    message = str(caught.value)
    assert "is the name of 2 parameters of this request" in message
    assert "water_equivalent_water_equivalent_snow_depth" in message
    assert message.count("water_equivalent_water_equivalent_snow_depth") == 1


def test_in_every_dataset_a_bare_name_means_its_own_parameter_and_a_dataset_spelling_means_one() -> None:
    """Held for every dataset of every provider: the names of a dataset alone are unambiguous (GH-4419)."""
    # the dataset spellings that are the bare name of another parameter of the dataset: the bare name wins there
    known = {
        ("dwd", "observation", "daily", "water_equivalent", "water_equivalent_snow_depth"),
        ("dwd", "observation", "daily", "water_equivalent", "water_equivalent_snow_depth_sampled"),
    }
    seen = set()
    checked = 0
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                continue
            for resolution in Wetterdienst.resolve(provider, network).metadata:
                for dataset in resolution:
                    parameters = list(dataset)
                    names = ParameterNames.of(parameters, humanize=True)
                    for parameter in parameters:
                        checked += 1
                        bare = names.lookup[parameter.name.lower()]
                        assert [c.parameter for _, c in bare] == [parameter.name], (provider, network, dataset.name)
                        prefixed = names.lookup[f"{dataset.name.lower()}_{parameter.name}".lower()]
                        if len(prefixed) != 1 or prefixed[0][1].parameter != parameter.name:
                            seen.add(
                                (provider, network, resolution.name, dataset.name, f"{dataset.name}_{parameter.name}")
                            )
    assert checked > 2000
    assert seen == known


def test_the_same_name_at_two_resolutions_is_the_refusal_of_the_resolutions() -> None:
    """A request of two resolutions has no names: a name both have says that, not that it is ambiguous."""
    metadata = Wetterdienst.resolve("aemet", "observation").metadata
    parameters = [
        dataset["temperature_air_max_2m"]
        for resolution in metadata
        for dataset in resolution
        if resolution.name in ("daily", "hourly")
    ]
    assert len(parameters) == 2
    names = ParameterNames.of(parameters, humanize=True)
    assert len(names.lookup["temperature_air_max_2m"]) == 2
    with pytest.raises(RowSelectionRefusedError, match=r"has 2 \("):
        parse_row_selection(filter="temperature_air_max_2m<0", parameters=names)


def test_the_refusal_of_a_name_of_many_parameters_lists_a_few_and_counts_the_rest() -> None:
    """Phenology has 81 datasets with one name: the text is bounded, not 7,000 characters."""
    columns = [ParameterColumn("yearly", f"plant_{i}", "phase", f"plant_{i}_phase") for i in range(81)]
    lookup: dict[str, Any] = {"phase": tuple(("phase", c) for c in columns)}
    lookup |= {f"{c.dataset}_phase": ((f"{c.dataset}_phase", c),) for c in columns}
    names = ParameterNames(lookup=lookup, resolutions=("yearly",), listed=("phase",))
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="phase<3", parameters=names)
    message = str(caught.value)
    assert "is the name of 81 parameters of this request" in message
    assert "plant_0_phase" in message
    assert "plant_11_phase and 69 more" in message
    assert "plant_12_phase" not in message
    assert len(message) < 900


def test_a_name_of_two_datasets_is_judged_on_the_rows_of_its_own_dataset() -> None:
    """Two datasets with one parameter name at the same stamps: each spelling reads its own dataset's value."""
    names = _names("hourly/temperature_air/temperature_air_2m", "hourly/dew_point/temperature_air_2m")
    rows = [
        ("00001", "temperature_air_2m", 0, -1.0, "temperature_air"),
        ("00001", "temperature_air_2m", 0, 5.0, "dew_point"),
        ("00001", "temperature_air_2m", 1, 5.0, "temperature_air"),
        ("00001", "temperature_air_2m", 1, -1.0, "dew_point"),
    ]
    frame = pl.DataFrame(
        {
            "station_id": [r[0] for r in rows],
            "resolution": ["hourly"] * 4,
            "dataset": [r[4] for r in rows],
            "parameter": [r[1] for r in rows],
            "timestamp": [STAMP + dt.timedelta(hours=r[2]) for r in rows],
            "value": [r[3] for r in rows],
            "quality_flags": ["1"] * 4,
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
    )
    for text, hour in (("temperature_air_temperature_air_2m<0", 0), ("dew_point_temperature_air_2m<0", 1)):
        selection = parse_row_selection(filter=text, parameters=names)
        assert selection is not None
        assert set(selection.apply(frame).get_column("timestamp")) == {STAMP + dt.timedelta(hours=hour)}, text


def test_where_no_spelling_tells_a_parameter_apart_the_refusal_says_to_request_its_dataset_alone() -> None:
    """`snow_depth` is in `water_equivalent` and in `climate_summary`: no spelling names the first of them."""
    names = _names("daily/water_equivalent", "daily/climate_summary")
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="water_equivalent_snow_depth<1", parameters=names)
    message = str(caught.value)
    assert "request `water_equivalent` alone for its `snow_depth`" in message
    hits = names.lookup["water_equivalent_snow_depth"]
    assert [c.parameter for c in names.without_spelling(hits)] == ["snow_depth"]
    # the spellings offered are those that are unique, and the parameter without one is not offered
    spellings = names.distinct_spellings(hits)
    assert spellings == ["water_equivalent_water_equivalent_snow_depth"]
    assert all(len(names.lookup[spelling.lower()]) == 1 for spelling in spellings)
    # a parameter with a unique spelling is not told to be requested alone
    alone = _names("daily/water_equivalent", "daily/climate_summary/wind_gust_max")
    with pytest.raises(RowSelectionError) as caught:
        parse_row_selection(filter="water_equivalent_snow_depth<1", parameters=alone)
    assert "request `" not in str(caught.value)


def test_the_stations_of_a_filter_of_names_keep_the_order_they_came_in() -> None:
    """Without `sort` the rows of the stations stay in the order of the frame: not sorted by station id."""
    frame = _frame()
    backwards = pl.concat(
        [frame.filter(pl.col("station_id") == "00002"), frame.filter(pl.col("station_id") == "00001")]
    )
    answer = _choose(backwards, filter="temperature_air_min_2m<0,wind_gust_max>=17.2")
    stations = answer.get_column("station_id").to_list()
    assert stations == ["00002"] * 6 + ["00001"] * 6
    assert answer.filter(pl.col("station_id") == "00002").get_column("timestamp").is_sorted()
