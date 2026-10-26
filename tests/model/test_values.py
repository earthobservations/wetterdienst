"""Tests for shared TimeseriesValues behavior."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.options import Options
from wetterdienst.provider.dwd.observation import DwdObservationMetadata, DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.wsv.pegel import WsvPegelRequest
from wetterdienst.provider.wsv.pegel.api import WsvPegelValues
from wetterdienst.settings import Settings


def _values(parameters: list[tuple[str, str, str]]) -> TimeseriesValues:
    """Build a values object for the given parameters without touching the network."""
    request = WsvPegelRequest(parameters=parameters)
    return WsvPegelValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )


def _long(rows: list[tuple[str, str, str, int, float]]) -> pl.DataFrame:
    """Build a long frame of (resolution, dataset, parameter, minute-of-hour, value) rows."""
    return pl.DataFrame(
        {
            "station_id": ["01"] * len(rows),
            "resolution": [row[0] for row in rows],
            "dataset": [row[1] for row in rows],
            "parameter": [row[2] for row in rows],
            "timestamp": [dt.datetime(2026, 1, 1, 0, row[3], tzinfo=ZoneInfo("UTC")) for row in rows],
            "value": [row[4] for row in rows],
            "quality_flags": [None] * len(rows),
        },
        schema_overrides={"quality_flags": pl.String},
    )


def test_widen_df_keeps_resolutions_on_their_own_rows() -> None:
    """Test that two resolutions do not share a row, and neither shares the other's values.

    Resolution is what defines the time axis, so a 15-minute series and an hourly one do not have
    the same timestamps to begin with. Keying the wide row on the date alone put both resolutions'
    values on every row that shared a timestamp, so an hourly row reported a 15-minute reading.
    """
    df = _long(
        [
            ("15_minutes", "data", "stage", 0, 1.0),
            ("15_minutes", "data", "stage", 15, 2.0),
            ("hourly", "data", "temperature_air", 0, 20.0),
        ],
    )

    result = _values([("15_minutes", "data", "stage"), ("hourly", "data", "temperature_air")])._widen_df(df)  # noqa: SLF001

    result = result.sort("resolution", "timestamp")
    assert result.get_column("resolution").to_list() == ["15_minutes", "15_minutes", "hourly"]
    assert result.get_column("stage").to_list() == [1.0, 2.0, None]
    assert result.get_column("temperature_air").to_list() == [None, None, 20.0]


def test_widen_df_keeps_a_timestamp_one_parameter_is_missing() -> None:
    """Test that a parameter with no reading leaves a null rather than removing the timestamp.

    The parameter frames used to be joined inner, one after another, so the frame came out as the
    timestamps every requested parameter happened to share. A 15-minute series joined against an
    hourly one lost three readings in four -- readings that had been asked for and downloaded.
    """
    df = _long(
        [
            ("15_minutes", "data", "stage", 0, 1.0),
            ("15_minutes", "data", "stage", 15, 2.0),
            ("15_minutes", "data", "discharge", 0, 9.0),
        ],
    )

    result = _values([("15_minutes", "data", "stage"), ("15_minutes", "data", "discharge")])._widen_df(df)  # noqa: SLF001

    result = result.sort("timestamp")
    assert result.get_column("stage").to_list() == [1.0, 2.0]
    # discharge has no reading at 00:15 and must not take the whole timestamp out with it
    assert result.get_column("discharge").to_list() == [9.0, None]


def test_widen_df_gives_each_parameter_its_own_quality_flags_column() -> None:
    """Test that a reading's flags go next to its value as `<parameter>_quality_flags` (GH-2018, GH-2758)."""
    df = _long(
        [
            ("15_minutes", "data", "stage", 0, 1.0),
            ("15_minutes", "data", "stage", 15, 2.0),
            ("15_minutes", "data", "discharge", 0, 9.0),
        ],
    ).with_columns(quality_flags=pl.Series(["Good", "Suspect", None], dtype=pl.String))

    result = _values([("15_minutes", "data", "stage"), ("15_minutes", "data", "discharge")])._widen_df(df)  # noqa: SLF001

    result = result.sort("timestamp")
    assert result.get_column("stage_quality_flags").to_list() == ["Good", "Suspect"]
    # a flag is null where its parameter has no reading, as the value is, and where the reading has no flag
    assert result.get_column("discharge_quality_flags").to_list() == [None, None]
    assert result.schema["stage_quality_flags"] == pl.String
    # one column replaces the former `_quality` and `_quality_flag` pair
    assert not [column for column in result.columns if column.endswith(("_quality", "_quality_flag"))]
    assert result.columns.index("stage_quality_flags") == result.columns.index("stage") + 1


def test_a_provider_that_publishes_no_flag_still_returns_the_column() -> None:
    """Test that a frame handed over without `quality_flags` leaves the core with a String null."""
    values = _dwd_values([("daily", "climate_summary")])
    dataset = values.sr.parameters[0].dataset
    df = pl.DataFrame(
        {
            "parameter": ["tmk"],
            "timestamp": [dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "value": [1.0],
        }
    )

    result = values._shape(df, "01048", dataset)  # noqa: SLF001

    assert result.columns[-1] == "quality_flags"
    assert result.schema["quality_flags"] == pl.String
    assert result.get_column("quality_flags").to_list() == [None]


def _dwd_values(parameters: list[tuple[str, str]]) -> TimeseriesValues:
    """Build a DWD values object for the given datasets without touching the network."""
    request = DwdObservationRequest(parameters=parameters)
    return DwdObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )


def test_widen_df_merges_datasets_of_one_resolution_into_one_row() -> None:
    """Test that two datasets recorded at one resolution share a row, unnamed.

    They have the same timestamps, so their columns sit side by side -- which is what the
    dataset-name prefix is for. Keying the row on the dataset too used to emit the timestamp once
    per dataset and fill both rows with both datasets' values, so the `precipitation_more` row
    reported a `climate_summary` value. No single name describes the merged row, so it carries
    none: the column prefix names the datasets instead.
    """
    df = _long(
        [
            ("daily", "climate_summary", "temperature_air_mean_2m", 0, 5.0),
            ("daily", "precipitation_more", "precipitation_amount", 0, 1.0),
        ],
    )

    result = _dwd_values([("daily", "climate_summary"), ("daily", "precipitation_more")])._widen_df(df)  # noqa: SLF001

    assert result.height == 1
    assert result.get_column("dataset").to_list() == [None]
    assert result.get_column("climate_summary_temperature_air_mean_2m").to_list() == [5.0]
    assert result.get_column("precipitation_more_precipitation_amount").to_list() == [1.0]


def test_widen_df_keeps_the_dataset_name_where_a_resolution_has_one() -> None:
    """Test that only a row spanning several datasets loses its dataset name.

    Resolutions are not merged into one another, so a resolution holding a single dataset still has
    one name for every one of its rows and keeps it -- the null is reserved for rows where no
    single name would be true.
    """
    df = _long(
        [
            ("daily", "climate_summary", "temperature_air_mean_2m", 0, 5.0),
            ("daily", "precipitation_more", "precipitation_amount", 0, 1.0),
            ("hourly", "precipitation", "precipitation_amount", 0, 0.5),
        ],
    )

    values = _dwd_values(
        [("daily", "climate_summary"), ("daily", "precipitation_more"), ("hourly", "precipitation")],
    )
    result = values._widen_df(df).sort("resolution")  # noqa: SLF001

    assert result.get_column("resolution").to_list() == ["daily", "hourly"]
    assert result.get_column("dataset").to_list() == [None, "precipitation"]
    assert result.get_column("precipitation_precipitation_amount").to_list() == [None, 0.5]


def _hourly_values(start_date: dt.datetime, end_date: dt.datetime) -> TimeseriesValues:
    """Build an hourly DWD values object over the given window, without touching the network."""
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_2m")],
        start=start_date,
        end=end_date,
    )
    return DwdObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )


def _hourly_long(dates: list[dt.datetime]) -> pl.DataFrame:
    """Build a long frame of one parameter observed at the given timestamps.

    The parameter carries its source name rather than its canonical one, which is what a frame
    holds until `query` humanizes it -- and humanizing happens after coverage is measured.
    """
    return pl.DataFrame(
        {
            "station_id": ["01048"] * len(dates),
            "resolution": ["hourly"] * len(dates),
            "dataset": ["temperature_air"] * len(dates),
            "parameter": ["tt_tu"] * len(dates),
            "timestamp": dates,
            "value": [1.0] * len(dates),
            "quality_flags": [None] * len(dates),
        },
        schema_overrides={"quality_flags": pl.String},
    )


def _percentage(values: TimeseriesValues, df: pl.DataFrame, criteria: str = "min") -> float:
    """Read the coverage of a frame the way `query` does, under the given skip criteria."""
    values.sr.request.options = values.sr.request.options.replace(skip_criteria=criteria)
    return values._get_actual_percentage(df=df)  # noqa: SLF001


def test_actual_percentage_measures_against_the_requested_window() -> None:
    """Test that coverage is the share of the readings the request asked for.

    The window holds four hourly readings and the station delivered three of them, which is what
    the number says -- the frame it is read off carries three rows and nothing else, since there
    is no grid under it to spell the fourth out as a null.
    """
    start_date = dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2026, 1, 1, 3, tzinfo=ZoneInfo("UTC"))
    df = _hourly_long(
        [
            dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
        ],
    )

    assert _percentage(_hourly_values(start_date, end_date), df) == 0.75


def test_actual_percentage_counts_readings_that_miss_the_grid() -> None:
    """Test that a station reporting off the hour is counted as reporting.

    Completion joined onto the grid exactly, so a gauge reporting at seven minutes past matched no
    row and came back as a column of nulls -- a good third of Hubeau's hourly stations scored zero
    and were skipped for it. The count no longer asks where in the hour a reading fell.
    """
    start_date = dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2026, 1, 1, 2, tzinfo=ZoneInfo("UTC"))
    df = _hourly_long(
        [
            dt.datetime(2026, 1, 1, 0, 7, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 1, 7, tzinfo=ZoneInfo("UTC")),
        ],
    )

    assert _percentage(_hourly_values(start_date, end_date), df) == pytest.approx(2 / 3)


def test_actual_percentage_caps_a_station_reporting_more_often_than_its_resolution() -> None:
    """Test that reporting more often than the resolution reads as covered, not as over-covered."""
    start_date = dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2026, 1, 1, 1, tzinfo=ZoneInfo("UTC"))
    df = _hourly_long(
        [
            dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 0, 30, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 1, 30, tzinfo=ZoneInfo("UTC")),
        ],
    )

    assert _percentage(_hourly_values(start_date, end_date), df) == 1.0


def test_actual_percentage_counts_nulls_as_missing() -> None:
    """Test that a row carrying no value counts against the station like an absent row does."""
    start_date = dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2026, 1, 1, 3, tzinfo=ZoneInfo("UTC"))
    df = _hourly_long(
        [
            dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
        ],
    ).with_columns(pl.when(pl.col("timestamp").dt.hour() < 2).then(pl.col("value")).alias("value"))

    assert _percentage(_hourly_values(start_date, end_date), df) == 0.5


def test_actual_percentage_is_zero_for_a_parameter_that_came_back_with_nothing() -> None:
    """Test that a requested parameter absent from the frame counts as zero, not as unmeasured.

    It is measured by its absence: there is no row to read a ratio off, and a request for two
    parameters where one never arrived is not covered under the `min` criteria, however complete
    the other one is.
    """
    start_date = dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2026, 1, 1, 1, tzinfo=ZoneInfo("UTC"))
    request = DwdObservationRequest(
        parameters=[
            ("hourly", "temperature_air", "temperature_air_2m"),
            ("hourly", "temperature_air", "humidity_relative"),  # never arrives
        ],
        start=start_date,
        end=end_date,
    )
    values = DwdObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )
    df = _hourly_long([start_date, end_date])

    assert _percentage(values, df) == 0.0
    assert _percentage(values, df, criteria="max") == 1.0
    assert _percentage(values, df, criteria="mean") == 0.5


def test_actual_percentage_falls_back_to_the_span_of_the_series() -> None:
    """Test that a request naming no window is measured against the station's own series.

    A period-based request carries no dates to count against, and measuring the returned rows
    against themselves would call every station fully covered -- which is what made `skip_empty`
    do nothing wherever it was reachable at all.
    """
    df = _hourly_long(
        [
            dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
        ],
    )
    request = DwdObservationRequest(parameters=[("hourly", "temperature_air", "temperature_air_2m")])
    values = DwdObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )

    assert _percentage(values, df) == 0.75


def test_actual_percentage_does_not_let_oversampling_fill_in_for_silence() -> None:
    """Test that reporting twice an hour through half a window does not read as covering it.

    Counted reading by reading, a station reporting every 30 minutes through the first half of a
    10-hour window delivers 11 readings against the 11 the window holds and reads as complete --
    while the second half of the window holds nothing at all. Readings are counted by the grid
    slot they land in, so the five silent hours are five slots the station does not cover.
    """
    start_date = dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2026, 1, 1, 10, tzinfo=ZoneInfo("UTC"))
    df = _hourly_long(
        [dt.datetime(2026, 1, 1, hour, minute, tzinfo=ZoneInfo("UTC")) for hour in range(6) for minute in (0, 30)],
    )

    # 12 readings over 6 of the 11 hourly slots the window holds
    assert _percentage(_hourly_values(start_date, end_date), df) == pytest.approx(6 / 11)


def test_actual_percentage_reads_the_fallback_window_off_the_dataset_it_measures() -> None:
    """Test that a dataset is not measured against the span of another one in the same request.

    Without a window of its own the span comes off the frame, and a request pairing a series that
    reaches back decades with one that starts far later would measure the short series against the
    long one's span -- dropping a station whose record is complete for the whole of its life.
    """
    request = DwdObservationRequest(
        parameters=[
            ("hourly", "temperature_air", "temperature_air_2m"),
            ("daily", "climate_summary", "precipitation_amount"),
        ],
    )
    values = DwdObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )
    daily_dates = pl.datetime_range(
        dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")),
        interval="1d",
        eager=True,
    )
    df = pl.concat(
        [
            # complete for every hour it has ever run, but only since 2026
            _hourly_long(
                [dt.datetime(2026, 1, 1, hour, tzinfo=ZoneInfo("UTC")) for hour in range(24)],
            ),
            pl.DataFrame(
                {
                    "station_id": ["01048"] * len(daily_dates),
                    "resolution": ["daily"] * len(daily_dates),
                    "dataset": ["climate_summary"] * len(daily_dates),
                    "parameter": ["rsk"] * len(daily_dates),
                    "timestamp": daily_dates,
                    "value": [1.0] * len(daily_dates),
                    "quality_flags": [None] * len(daily_dates),
                },
                schema_overrides={"quality_flags": pl.String},
            ),
        ],
    )

    assert _percentage(values, df) == 1.0


def test_actual_percentage_matches_a_parameter_name_in_the_provider_own_casing() -> None:
    """Test that a provider emitting its own casing is not counted as having sent nothing.

    WSV reports `w` where its metadata declares `W`. Matched exactly, every WSV station scored
    zero on a parameter it had delivered in full and was skipped over it.
    """
    start_date = dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2026, 1, 1, 1, tzinfo=ZoneInfo("UTC"))
    request = WsvPegelRequest(
        parameters=[("15_minutes", "data", "stage")],
        start=start_date,
        end=end_date,
    )
    values = WsvPegelValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )
    dates = pl.datetime_range(start_date, end_date, interval="15m", eager=True)
    df = pl.DataFrame(
        {
            "station_id": ["48900237"] * len(dates),
            "resolution": ["15_minutes"] * len(dates),
            "dataset": ["data"] * len(dates),
            "parameter": ["w"] * len(dates),  # the metadata declares `W`
            "timestamp": dates,
            "value": [1.0] * len(dates),
            "quality_flags": [None] * len(dates),
        },
        schema_overrides={"quality_flags": pl.String},
    )

    assert _percentage(values, df) == 1.0


def _stub_dwd_daily(
    *,
    station_ids: list[str],
    data_year_by_station: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
    datasets: list[str] | None = None,
    collected: list[str] | None = None,
    index_start: dt.datetime | None = None,
    index_end: dt.datetime | None = None,
) -> None:
    """Stand in for DWD's station index and data files, so the walk can be exercised offline.

    The index range defaults wide enough to cover any window a test asks for, so that what the
    index says and what the files hold can be varied independently -- a station whose published
    range covers a window it has no readings in is the ordinary case, not a contradiction.
    """
    utc = ZoneInfo("UTC")
    datasets = datasets or ["climate_summary"]
    rows = [(station_id, dataset) for station_id in station_ids for dataset in datasets]
    df_stations = pl.DataFrame(
        {
            "resolution": ["daily"] * len(rows),
            "dataset": [dataset for _, dataset in rows],
            "station_id": [station_id for station_id, _ in rows],
            "start_timestamp": [index_start or dt.datetime(1900, 1, 1, tzinfo=utc)] * len(rows),
            "end_timestamp": [index_end or dt.datetime(2030, 1, 1, tzinfo=utc)] * len(rows),
            # spread along a meridian so the distance ranking follows the list order
            "latitude": [50.0 + station_ids.index(station_id) / 10 for station_id, _ in rows],
            "longitude": [8.0] * len(rows),
            "elevation": [100.0] * len(rows),
            "name": [station_id for station_id, _ in rows],
            "region": ["x"] * len(rows),
        },
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda self: df_stations.lazy())  # noqa: ARG005

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        if collected is not None:
            collected.append(station_id)
        year = data_year_by_station[station_id]
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        names = [parameter.name_original for parameter in dataset]
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(year, 1, day, tzinfo=utc) for day in range(1, 4) for _ in names],
                "parameter": names * 3,
                "value": [1.0] * (3 * len(names)),
                "quality_flags": ["1"] * (3 * len(names)),
                "resolution": ["daily"] * (3 * len(names)),
                "dataset": [dataset.name] * (3 * len(names)),
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def test_rank_is_not_spent_on_a_station_whose_data_misses_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station with no reading inside the window must not consume one of ``rank``'s slots.

    The two nearest stations hold data, but only outside the requested window; the third does
    cover it. Counting the near two as collected stopped the ranked walk before the third and
    returned nothing at all.
    """
    _stub_dwd_daily(
        station_ids=["00001", "00002", "00003"],
        data_year_by_station={"00001": 1990, "00002": 1990, "00003": 1930},
        monkeypatch=monkeypatch,
    )
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1930-01-01",
        end="1930-12-31",
    )

    values = request.filter_by_rank(latlon=(50.0, 8.0), rank=2).values()
    df = values.all().df

    assert df.get_column("station_id").unique().to_list() == ["00003"]
    assert df.height == 3


def test_a_request_that_collects_nothing_keeps_its_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty result is still shaped like a populated one, so it can be written or read from."""
    _stub_dwd_daily(
        station_ids=["00001"],
        data_year_by_station={"00001": 1990},
        monkeypatch=monkeypatch,
    )
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1930-01-01",
        end="1930-12-31",
    )

    df = request.filter_by_station_id("00001").values().all().df

    assert df.is_empty()
    assert df.columns == [
        "station_id",
        "resolution",
        "dataset",
        "parameter",
        "timestamp",
        "value",
        "quality_flags",
    ]
    assert df.schema["quality_flags"] == pl.String
    # a header rather than an empty file, and a column that can still be asked for
    assert df.write_csv() == "station_id,resolution,dataset,parameter,timestamp,value,quality_flags\n"
    assert df.get_column("timestamp").is_empty()


def test_wide_empty_result_matches_the_shape_of_a_populated_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wide request spanning two datasets returns the columns it would have, not an error.

    ``_widen_df`` reads the ``parameter`` column, which the wide form does not have, so building
    the empty frame in the shape asked for raised ``ColumnNotFoundError`` from inside it.
    """
    _stub_dwd_daily(
        station_ids=["00001"],
        data_year_by_station={"00001": 1990},
        monkeypatch=monkeypatch,
        datasets=["climate_summary", "precipitation_more"],
    )
    parameters = ["daily/kl/temperature_air_mean_2m", "daily/more_precip/precipitation_amount"]
    options = {"shape": "wide"}

    empty = (
        DwdObservationRequest(parameters=parameters, start="1930-01-01", end="1930-12-31", options=options)
        .filter_by_station_id("00001")
        .values()
        .all()
        .df
    )
    populated = (
        DwdObservationRequest(parameters=parameters, start="1990-01-01", end="1990-12-31", options=options)
        .filter_by_station_id("00001")
        .values()
        .all()
        .df
    )

    assert empty.is_empty()
    assert not populated.is_empty()
    # including the dataset prefix the populated frame carries, which the empty one used to omit
    assert empty.columns == populated.columns
    assert "climate_summary_temperature_air_mean_2m" in empty.columns
    # and its quality flags column after it, both branches alike (GH-2030, GH-2018, GH-2758)
    assert empty.columns.index("climate_summary_temperature_air_mean_2m_quality_flags") == (
        empty.columns.index("climate_summary_temperature_air_mean_2m") + 1
    )
    assert empty.schema["climate_summary_temperature_air_mean_2m_quality_flags"] == pl.String


def test_a_station_that_started_after_the_window_is_not_downloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """The index answers for a window a station cannot cover, so the walk stays bounded.

    Nothing bounds the ranked walk once a station returning nothing inside the window no longer
    counts towards ``rank``, so it would otherwise read every station in the provider.
    """
    station_ids = [f"{index:05d}" for index in range(1, 21)]
    _stub_dwd_daily(
        station_ids=station_ids,
        data_year_by_station=dict.fromkeys(station_ids, 1990),
        monkeypatch=monkeypatch,
        collected=(collected := []),
        index_start=dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC")),
    )
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1930-01-01",
        end="1930-12-31",
    )

    request.filter_by_rank(latlon=(50.0, 8.0), rank=5).values().all()

    # the stub's stations all start in 1990, so the index alone rules the 1930 window out
    assert collected == []


def test_a_station_still_reporting_is_not_ruled_out_by_a_lagging_end_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the start of a record rules a window out; an `end_timestamp` lags on a live station.

    A station index is written before the day it describes is over, so a station that is still
    reporting carries an `end_timestamp` a little behind the readings it can already answer for.
    """
    _stub_dwd_daily(
        station_ids=["00001"],
        data_year_by_station={"00001": 2020},
        monkeypatch=monkeypatch,
        # the index stops a year before the window, but the station does have the readings
        index_end=dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
    )
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="2020-01-01",
        end="2020-12-31",
    )

    df = request.filter_by_station_id("00001").values().all().df

    assert df.height == 3


def test_convert_units_keeps_a_reading_a_much_larger_target_holds_little_of() -> None:
    """A reading converted to a target far larger than its source keeps its significant figures.

    Rounding to a fixed four decimals after converting rounded away what a much larger unit holds of
    a reading: with `length_short` reported in miles, 5 cm of snow came back as 0.0, which reads as
    a measurement of no snow, and 150 cm kept one significant figure.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "snow_depth")],
        options={"unit_targets": {"length_short": "mile"}},
    )
    values = DwdObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )
    df = _long([("daily", "climate_summary", "shk_tag", 0, 5.0), ("daily", "climate_summary", "shk_tag", 1, 150.0)])

    result = values._convert_units(df, request.parameters[0].dataset)  # noqa: SLF001

    assert result.get_column("value").to_list() == [0.000031069, 0.000932057]


def test_convert_units_keeps_the_value_column_whatever_the_conversion_starts_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A conversion that opens with a number (`9 / 5 * x`) converts the column and adds none.

    The conversions run on the column as an expression, and an expression is named after its first
    operand: `9 / 5 * x` came back as a column `literal` beside the unconverted `value`.
    """
    request = DwdObservationRequest(parameters=[("daily", "climate_summary", "snow_depth")])
    values = DwdObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )
    monkeypatch.setattr(values, "_create_conversions", lambda _dataset: {"shk_tag": (lambda x: 9 / 5 * x, 2)})
    df = _long([("daily", "climate_summary", "shk_tag", 0, 5.0), ("daily", "climate_summary", "shk_tag", 1, 10.0)])

    result = values._convert_units(df, request.parameters[0].dataset)  # noqa: SLF001

    assert result.columns == df.columns
    assert result.get_column("value").to_list() == [9.0, 18.0]


def test_a_station_is_kept_when_one_dataset_leaves_its_start_timestamp_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unpublished ``start_timestamp`` for one dataset is not overruled by another dataset's bound.

    A station asked for two datasets has a row per dataset in the index. With one row lacking a
    ``start_timestamp`` and the other starting after the window, ``min()`` skipped the null, so the
    later bound decided for the whole station and the dataset that does cover the window was
    dropped with it (GH-2292).
    """
    _stub_dwd_daily(
        station_ids=["00001"],
        data_year_by_station={"00001": 1930},
        monkeypatch=monkeypatch,
        datasets=["climate_summary", "precipitation_more"],
    )
    stub_all = DwdObservationRequest._all  # noqa: SLF001
    monkeypatch.setattr(
        DwdObservationRequest,
        "_all",
        lambda self: stub_all(self).with_columns(
            start_timestamp=pl.when(pl.col("dataset") == "climate_summary")
            .then(pl.lit(None, dtype=pl.Datetime(time_zone="UTC")))
            .otherwise(pl.lit(dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC")))),
        ),
    )
    request = DwdObservationRequest(
        parameters=["daily/kl/temperature_air_mean_2m", "daily/more_precip/precipitation_amount"],
        start="1930-01-01",
        end="1930-12-31",
    )

    df = request.filter_by_station_id("00001").values().all().df

    # the stub hands out 1930 readings for either dataset; the one asked about is the dataset whose
    # start is unknown, which was dropped with the station
    assert df.filter(pl.col("dataset") == "climate_summary").height == 3


def test_a_station_whose_datasets_all_start_after_the_window_is_not_downloaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A station asked for several datasets is still ruled out when every one of them says so.

    The counterpart of keeping a station whose dataset leaves its start out: with each row
    publishing a start after the window, the index still answers for the station.
    """
    _stub_dwd_daily(
        station_ids=["00001"],
        data_year_by_station={"00001": 1930},
        monkeypatch=monkeypatch,
        datasets=["climate_summary", "precipitation_more"],
        collected=(collected := []),
        index_start=dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC")),
    )
    request = DwdObservationRequest(
        parameters=["daily/kl/temperature_air_mean_2m", "daily/more_precip/precipitation_amount"],
        start="1930-01-01",
        end="1930-12-31",
    )

    request.filter_by_station_id("00001").values().all()

    assert collected == []


def _values_with_a_null(
    monkeypatch: pytest.MonkeyPatch, *, settings: Settings | None = None, options: Options | None = None
) -> pl.DataFrame:
    """Return a station's daily mean temperature over two days, the second of which is null."""
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    utc = ZoneInfo("UTC")
    name = DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m.name_original

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, day, tzinfo=utc) for day in (1, 2)],
                "parameter": [name] * 2,
                "value": [1.0, None],
                "quality_flags": ["1"] * 2,
                "resolution": ["daily"] * 2,
                "dataset": ["climate_summary"] * 2,
            },
            schema_overrides={"value": pl.Float64},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-02",
        settings=settings or Settings(),
        options=options,
    )
    return request.filter_by_station_id("00001").values().all().df


def test_values_drop_nulls_again_for_options_once_wide_and_now_long(monkeypatch: pytest.MonkeyPatch) -> None:
    """An `Options` reused for a long request after a wide one drops the null rows (GH-2388).

    The wide request used to write False into the settings' `ts_drop_nulls`, which the long
    request reusing them then read, and returned the null rows.
    """
    wide_options = Options(shape="wide", drop_nulls=True)
    wide = _values_with_a_null(monkeypatch, options=wide_options)
    # the wide shape drops no nulls
    assert wide.get_column("temperature_air_mean_2m").to_list() == [1.0, None]

    long = _values_with_a_null(monkeypatch, options=wide_options.replace(shape="long"))
    assert long.get_column("value").to_list() == [1.0]
    assert_frame_equal(long, _values_with_a_null(monkeypatch, options=Options(shape="long", drop_nulls=True)))


def test_a_window_in_a_named_zone_cuts_the_utc_values_at_its_instants(monkeypatch: pytest.MonkeyPatch) -> None:
    """The window of a request in a named zone is compared with the UTC timestamps as the instants it names (GH-2682).

    Compared as it was handed in, polars refused it with a `SchemaError` -- a `Datetime` in
    `Europe/Vilnius` against one in `UTC` -- after the data had been downloaded.
    """
    vilnius = ZoneInfo("Europe/Vilnius")
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        # 1990-01-02 00:00 UTC to 1990-01-03 00:00 UTC; Vilnius is UTC+2 in winter
        start=dt.datetime(1990, 1, 2, 2, tzinfo=vilnius),
        end=dt.datetime(1990, 1, 3, 2, tzinfo=vilnius),
    )

    df = request.filter_by_station_id("00001").values().all().df

    assert df.get_column("timestamp").unique().sort().to_list() == [
        dt.datetime(1990, 1, 2, tzinfo=ZoneInfo("UTC")),
        dt.datetime(1990, 1, 3, tzinfo=ZoneInfo("UTC")),
    ]


def test_filter_by_window_keeps_both_ends_of_a_window_across_a_clock_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """A window that opens before a clock change and closes after it holds the hours between its instants (GH-2682).

    Vilnius moves to summer time on 2025-03-30, so its midnight is 22:00 UTC the day before and its 23:00
    is 20:00 UTC: the window is 23 hours long, not 24. Closed at both ends.
    """
    vilnius = ZoneInfo("Europe/Vilnius")
    utc = ZoneInfo("UTC")
    # only keeps the station index offline; the frame below is cut directly
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    values = (
        DwdObservationRequest(
            parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
            start=dt.datetime(2025, 3, 30, 0, tzinfo=vilnius),
            end=dt.datetime(2025, 3, 30, 23, tzinfo=vilnius),
        )
        .filter_by_station_id("00001")
        .values()
    )
    hours = pl.datetime_range(
        dt.datetime(2025, 3, 29, tzinfo=utc),
        dt.datetime(2025, 3, 31, tzinfo=utc),
        interval="1h",
        eager=True,
    )
    df = pl.DataFrame({"timestamp": hours, "value": range(hours.len())})

    windowed = values._filter_by_window(df)  # noqa: SLF001

    assert windowed.height == 23
    assert windowed.get_column("timestamp").min() == dt.datetime(2025, 3, 29, 22, tzinfo=utc)
    assert windowed.get_column("timestamp").max() == dt.datetime(2025, 3, 30, 20, tzinfo=utc)


def test_widen_df_has_one_column_for_a_parameter_of_a_dataset_at_two_resolutions() -> None:
    """Test that `precipitation_amount` of the hourly and of the 10-minute precipitation is one column, not two.

    The request names the parameter once per dataset, and the two datasets share their name, so the
    order of the columns the request gives has the name twice; joining the parameter's rows twice left
    a `precipitation_amount_right` beside it.
    """
    values = _dwd_values([("hourly", "precipitation"), ("minute_10", "precipitation")])
    df = _long(
        [
            ("hourly", "precipitation", "precipitation_amount", 0, 1.0),
            ("minute_10", "precipitation", "precipitation_amount", 0, 0.5),
            ("minute_10", "precipitation", "precipitation_amount", 10, 0.5),
        ],
    )

    result = values._widen_df(df)  # noqa: SLF001

    assert not [column for column in result.columns if column.endswith("_right")]
    assert result.columns.count("precipitation_amount") == 1
    assert sorted(result.get_column("precipitation_amount").to_list()) == [0.5, 0.5, 1.0]


def _noting_dates(monkeypatch: pytest.MonkeyPatch, dates: dict[str, list[dt.datetime]]) -> None:
    """Make the reader of DWD note the dates of a station, as a provider whose source states one does (GH-2567)."""
    collect = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001

    def noting(self: DwdObservationValues, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001
        for date in dates.get(station_id, []):
            self._note_data_updated(date)
        # a date the source does not state is not noted, and changes nothing
        self._note_data_updated(None)
        return collect(self, station_id, parameter_or_dataset)

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", noting)


def test_a_result_has_the_newest_date_the_reader_noted_for_its_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """One result per station, each with its own date; the date of `all()` is the newest of them (GH-2567).

    A station that noted none has none, and does not take the one of the station before it.
    """
    utc = ZoneInfo("UTC")
    stations = ["00001", "00002", "00003"]
    _stub_dwd_daily(station_ids=stations, data_year_by_station=dict.fromkeys(stations, 1990), monkeypatch=monkeypatch)
    _noting_dates(
        monkeypatch,
        {
            "00001": [dt.datetime(2026, 10, 25, 6, tzinfo=utc), dt.datetime(2026, 10, 26, 6, tzinfo=utc)],
            "00002": [dt.datetime(2026, 10, 24, 6, tzinfo=utc)],
        },
    )
    values = DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")]).all().values()

    assert [result.data_updated_at for result in values.query()] == [
        dt.datetime(2026, 10, 26, 6, tzinfo=utc),
        dt.datetime(2026, 10, 24, 6, tzinfo=utc),
        None,
    ]
    assert values.all().data_updated_at == dt.datetime(2026, 10, 26, 6, tzinfo=utc)


def test_a_reader_that_notes_no_date_leaves_the_result_undated(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider whose source states no date does nothing, and the answer has none rather than the time it was read."""
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)

    result = (
        DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")]).all().values().all()
    )

    assert not result.df.is_empty()
    assert result.data_updated_at is None


def test_a_date_that_is_no_plausible_one_does_not_date_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whatever the source of a date is, one from the future or from before 1990 is not noted (GH-2567)."""
    utc = ZoneInfo("UTC")
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    _noting_dates(
        monkeypatch,
        {
            "00001": [
                dt.datetime.now(utc) + dt.timedelta(days=3),
                dt.datetime(9999, 12, 31, tzinfo=utc),
                dt.datetime(1970, 1, 1, tzinfo=utc),
            ]
        },
    )

    result = (
        DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")]).all().values().all()
    )

    assert not result.df.is_empty()
    assert result.data_updated_at is None
