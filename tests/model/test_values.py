"""Tests for shared TimeseriesValues behavior."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.wsv.pegel import WsvPegelRequest
from wetterdienst.provider.wsv.pegel.api import WsvPegelValues


def test_cast_metadata_to_enum_uses_sorted_unique_categories() -> None:
    """Metadata columns become Enum with categories taken from the sorted unique values."""
    df = pl.DataFrame(
        {
            "station_id": ["00044", "00011", "00044"],
            "resolution": ["daily", "daily", "daily"],
            "dataset": ["climate_summary"] * 3,
            "parameter": ["temperature_air_mean_2m", "precipitation_height", "temperature_air_mean_2m"],
            "value": [1.0, 2.0, 3.0],
        },
    )

    result = TimeseriesValues._cast_metadata_to_enum(df)  # noqa: SLF001

    assert result.schema["station_id"] == pl.Enum(["00011", "00044"])
    assert result.schema["resolution"] == pl.Enum(["daily"])
    assert result.schema["dataset"] == pl.Enum(["climate_summary"])
    assert result.schema["parameter"] == pl.Enum(["precipitation_height", "temperature_air_mean_2m"])
    # value column is untouched and the data is preserved
    assert result.schema["value"] == pl.Float64
    assert_frame_equal(result.with_columns(pl.col(pl.Enum).cast(pl.String)), df)


def test_cast_metadata_to_enum_never_fails_on_unexpected_values() -> None:
    """Categories come from the data itself, so provider casing quirks (e.g. WSV 'w') never crash."""
    df = pl.DataFrame({"station_id": ["x"], "parameter": ["w"], "value": [1.0]})

    result = TimeseriesValues._cast_metadata_to_enum(df)  # noqa: SLF001

    assert result.schema["parameter"] == pl.Enum(["w"])


def test_cast_metadata_to_enum_skips_absent_columns() -> None:
    """Columns not present (e.g. no `parameter` in wide shape) are simply skipped."""
    df = pl.DataFrame({"station_id": ["x"], "resolution": ["daily"], "value": [1.0]})

    result = TimeseriesValues._cast_metadata_to_enum(df)  # noqa: SLF001

    assert result.schema["station_id"] == pl.Enum(["x"])
    assert "parameter" not in result.columns


def _values(parameters: list[tuple[str, str, str]]) -> TimeseriesValues:
    """Build a values object for the given parameters without touching the network."""
    request = WsvPegelRequest(parameters=parameters)
    return WsvPegelValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
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
            "date": [dt.datetime(2026, 1, 1, 0, row[3], tzinfo=ZoneInfo("UTC")) for row in rows],
            "value": [row[4] for row in rows],
            "quality": [None] * len(rows),
        },
        schema_overrides={"quality": pl.Float64},
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
            ("hourly", "data", "temperature_air_mean_2m", 0, 20.0),
        ],
    )

    result = _values([("15_minutes", "data", "stage"), ("hourly", "data", "temperature_air_mean_2m")])._widen_df(df)  # noqa: SLF001

    result = result.sort("resolution", "date")
    assert result.get_column("resolution").to_list() == ["15_minutes", "15_minutes", "hourly"]
    assert result.get_column("stage").to_list() == [1.0, 2.0, None]
    assert result.get_column("temperature_air_mean_2m").to_list() == [None, None, 20.0]


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

    result = result.sort("date")
    assert result.get_column("stage").to_list() == [1.0, 2.0]
    # discharge has no reading at 00:15 and must not take the whole timestamp out with it
    assert result.get_column("discharge").to_list() == [9.0, None]


def _dwd_values(parameters: list[tuple[str, str]]) -> TimeseriesValues:
    """Build a DWD values object for the given datasets without touching the network."""
    request = DwdObservationRequest(parameters=parameters)
    return DwdObservationValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
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
            ("daily", "precipitation_more", "precipitation_height", 0, 1.0),
        ],
    )

    result = _dwd_values([("daily", "climate_summary"), ("daily", "precipitation_more")])._widen_df(df)  # noqa: SLF001

    assert result.height == 1
    assert result.get_column("dataset").to_list() == [None]
    assert result.get_column("climate_summary_temperature_air_mean_2m").to_list() == [5.0]
    assert result.get_column("precipitation_more_precipitation_height").to_list() == [1.0]


def test_widen_df_keeps_the_dataset_name_where_a_resolution_has_one() -> None:
    """Test that only a row spanning several datasets loses its dataset name.

    Resolutions are not merged into one another, so a resolution holding a single dataset still has
    one name for every one of its rows and keeps it -- the null is reserved for rows where no
    single name would be true.
    """
    df = _long(
        [
            ("daily", "climate_summary", "temperature_air_mean_2m", 0, 5.0),
            ("daily", "precipitation_more", "precipitation_height", 0, 1.0),
            ("hourly", "precipitation", "precipitation_height", 0, 0.5),
        ],
    )

    values = _dwd_values(
        [("daily", "climate_summary"), ("daily", "precipitation_more"), ("hourly", "precipitation")],
    )
    result = values._widen_df(df).sort("resolution")  # noqa: SLF001

    assert result.get_column("resolution").to_list() == ["daily", "hourly"]
    assert result.get_column("dataset").to_list() == [None, "precipitation"]
    assert result.get_column("precipitation_precipitation_height").to_list() == [None, 0.5]


def _hourly_values(start_date: dt.datetime, end_date: dt.datetime) -> TimeseriesValues:
    """Build an hourly DWD values object over the given window, without touching the network."""
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_mean_2m")],
        start_date=start_date,
        end_date=end_date,
    )
    return DwdObservationValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
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
            "date": dates,
            "value": [1.0] * len(dates),
            "quality": [None] * len(dates),
        },
        schema_overrides={"quality": pl.Float64},
    )


def _percentage(values: TimeseriesValues, df: pl.DataFrame, criteria: str = "min") -> float:
    """Read the coverage of a frame the way `query` does, under the given skip criteria."""
    values.sr.stations.settings.ts_skip_criteria = criteria
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
    ).with_columns(pl.when(pl.col("date").dt.hour() < 2).then(pl.col("value")).alias("value"))

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
            ("hourly", "temperature_air", "temperature_air_mean_2m"),
            ("hourly", "temperature_air", "humidity"),  # never arrives
        ],
        start_date=start_date,
        end_date=end_date,
    )
    values = DwdObservationValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
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
    request = DwdObservationRequest(parameters=[("hourly", "temperature_air", "temperature_air_mean_2m")])
    values = DwdObservationValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
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
            ("hourly", "temperature_air", "temperature_air_mean_2m"),
            ("daily", "climate_summary", "precipitation_height"),
        ],
    )
    values = DwdObservationValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
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
                    "date": daily_dates,
                    "value": [1.0] * len(daily_dates),
                    "quality": [None] * len(daily_dates),
                },
                schema_overrides={"quality": pl.Float64},
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
        start_date=start_date,
        end_date=end_date,
    )
    values = WsvPegelValues(
        sr=StationsResult(
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
        ),
    )
    dates = pl.datetime_range(start_date, end_date, interval="15m", eager=True)
    df = pl.DataFrame(
        {
            "station_id": ["48900237"] * len(dates),
            "resolution": ["15_minutes"] * len(dates),
            "dataset": ["data"] * len(dates),
            "parameter": ["w"] * len(dates),  # the metadata declares `W`
            "date": dates,
            "value": [1.0] * len(dates),
            "quality": [None] * len(dates),
        },
        schema_overrides={"quality": pl.Float64},
    )

    assert _percentage(values, df) == 1.0


def _stub_dwd_daily(
    *,
    station_ids: list[str],
    data_year_by_station: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stand in for DWD's station index and data files, so the walk can be exercised offline."""
    utc = ZoneInfo("UTC")
    df_stations = pl.DataFrame(
        {
            "resolution": ["daily"] * len(station_ids),
            "dataset": ["climate_summary"] * len(station_ids),
            "station_id": station_ids,
            "start_date": [dt.datetime(1990, 1, 1, tzinfo=utc)] * len(station_ids),
            "end_date": [dt.datetime(2020, 1, 1, tzinfo=utc)] * len(station_ids),
            # spread along a meridian so the distance ranking follows the list order
            "latitude": [50.0 + index / 10 for index in range(len(station_ids))],
            "longitude": [8.0] * len(station_ids),
            "height": [100.0] * len(station_ids),
            "name": station_ids,
            "state": ["x"] * len(station_ids),
        },
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda self: df_stations.lazy())  # noqa: ARG005

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        year = data_year_by_station[station_id]
        return pl.DataFrame(
            {
                "date": [dt.datetime(year, 1, day, tzinfo=utc) for day in range(1, 4)],
                "parameter": ["tmk"] * 3,
                "value": [1.0] * 3,
                "quality": [1.0] * 3,
                "resolution": ["daily"] * 3,
                "dataset": ["climate_summary"] * 3,
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
        start_date="1930-01-01",
        end_date="1930-12-31",
    )

    values = request.filter_by_rank(latlon=(50.0, 8.0), rank=2).values
    df = values.all().df

    assert values.stations_collected == ["00003"]
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
        start_date="1930-01-01",
        end_date="1930-12-31",
    )

    df = request.filter_by_station_id("00001").values.all().df

    assert df.is_empty()
    assert df.columns == ["station_id", "resolution", "dataset", "parameter", "date", "value", "quality"]
    # a header rather than an empty file, and a column that can still be asked for
    assert df.write_csv() == "station_id,resolution,dataset,parameter,date,value,quality\n"
    assert df.get_column("date").is_empty()
