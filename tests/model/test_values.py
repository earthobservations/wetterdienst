"""Tests for shared TimeseriesValues behavior."""

import datetime as dt
import logging
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst.exceptions import ProviderContractError
from wetterdienst.model.judge import plan_for
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.model.values import TimeseriesValues, _declared_parameter_names, merge_duplicate_readings
from wetterdienst.options import Options
from wetterdienst.provider.dwd.observation import DwdObservationMetadata, DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.provider.wsv.pegel import WsvPegelRequest
from wetterdienst.provider.wsv.pegel.api import WsvPegelValues
from wetterdienst.settings import Settings
from wetterdienst.util.response_warnings import begin_response, recorded_warnings


def _values(parameters: list[tuple[str, str, str]]) -> TimeseriesValues:
    """Build a values object for the given parameters without touching the network."""
    # WSV is read by a window (`date_required`), and the reader refuses a request without one (GH-3562)
    request = WsvPegelRequest(parameters=parameters, start="2020-01-01", end="2020-01-02")
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


def test_actual_percentage_counts_the_values_no_soft_check_flagged_suspect() -> None:
    """Test that a value flagged `suspect:` is no coverage, so a station with only such values is skipped (GH-3676).

    Three of the four hourly readings of the window are values and one of them is flagged suspect by a check that is
    soft; the coverage is the two unflagged ones. A station whose every value is flagged covers nothing, as it did when
    the check nulled them. A `raw:` token and a source's own flag are no suspicion.
    """
    start_date = dt.datetime(2026, 1, 1, 0, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2026, 1, 1, 3, tzinfo=ZoneInfo("UTC"))
    hours = [dt.datetime(2026, 1, 1, hour, tzinfo=ZoneInfo("UTC")) for hour in range(3)]
    df = _hourly_long(hours)
    values = _hourly_values(start_date, end_date)
    assert _percentage(values, df) == 0.75
    flagged = df.with_columns(pl.Series("quality_flags", ["3,suspect:range", "3,raw:-999", "3"]))
    assert _percentage(values, flagged) == 0.5
    only_suspect = df.with_columns(pl.lit("suspect:stuck").alias("quality_flags"))
    assert _percentage(values, only_suspect) == 0.0
    assert _percentage(values, only_suspect, "max") == 0.0


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
    resolution: str = "daily",
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
            "resolution": [resolution] * len(rows),
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


def test_a_grouped_dataset_keeps_a_parameter_the_provider_wrote_in_another_casing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a name in another casing than the metadata's is neither dropped nor left unhumanized (GH-3595).

    No provider does this today (every grouped dataset of every offline fixture was checked). The core matches names
    exactly where it filters a grouped dataset and where it humanizes, and case-insensitively where it converts units
    and measures the share of readings, so a provider that wrote `TMK` for the declared `tmk` lost the rows of the
    first and would have kept the source's spelling in the second.
    """
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    parameter = "temperature_air_mean_2m"
    declared = DwdObservationRequest(parameters=[("daily", "climate_summary", parameter)]).parameters[0].name_original
    assert declared == declared.lower()

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC"))],
                "parameter": [declared.upper()],
                "value": [1.0],
                "quality_flags": ["1"],
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", parameter)],
        start="1990-01-01",
        end="1990-01-03",
    )

    df = request.filter_by_station_id("00001").values().all().df

    assert df.get_column("parameter").to_list() == [parameter]
    assert df.get_column("value").to_list() == [1.0]


def _climate_values() -> DwdObservationValues:
    """Build the values of a daily DWD dataset without touching the network."""
    request = DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")])
    return DwdObservationValues(
        sr=StationsResult(
            request=request, df=pl.DataFrame(), _df_all=pl.DataFrame(), _stations_filter=StationsFilter.ALL
        ),
    )


def test_a_file_whose_only_rows_are_in_another_casing_still_dates_the_answer() -> None:
    """Test that `_note_files_with_rows` counts the rows the core keeps, whatever the casing of the name (GH-3595)."""
    values = _climate_values()
    updated = dt.datetime(2026, 10, 26, 6, 0, tzinfo=ZoneInfo("UTC"))
    df = pl.DataFrame(
        {
            "parameter": ["TMK"],
            "timestamp": [dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "value": [1.0],
            "updated": [updated],
        },
    )

    result = values._note_files_with_rows(df, values.sr.parameters[0].dataset)  # noqa: SLF001

    assert values._data_updated == [updated]  # noqa: SLF001
    assert result.get_column("parameter").to_list() == ["tmk"]


class _Dataset(list):
    """A dataset as `_declared_parameter_names` reads it: a sequence of parameters with a `name_original`."""


def _names(emitted: list[str], *declared: str) -> dict[str, str]:
    dataset = _Dataset(SimpleNamespace(name_original=name) for name in declared)
    return _declared_parameter_names(pl.DataFrame({"parameter": emitted}), dataset)  # ty: ignore[invalid-argument-type]


def test_a_name_two_declared_names_match_alike_is_left_but_the_others_are_mapped() -> None:
    """Test that an ambiguous casing switches off its own name only, not the rewrite of the dataset (GH-3595)."""
    # `AB` could be `Ab` or `aB`, so it is left as written; `w` and `W` are declared as they are written
    assert _names(["TMK", "AB", "w", "W"], "Ab", "aB", "W", "w", "tmk") == {"TMK": "tmk"}


def test_a_name_declared_twice_is_one_name() -> None:
    """Test that an exact duplicate in the metadata does not switch the rewrite off (GH-3595)."""
    assert _names(["TMK"], "tmk", "tmk") == {"TMK": "tmk"}
    assert _names(["W", "w"], "W", "W") == {"w": "W"}


def test_a_non_grouped_call_with_an_undeclared_name_is_a_contract_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the unit conversion names the parameter and the dataset instead of raising a bare `KeyError`."""
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    values = _climate_values()
    dataset = values.sr.parameters[0].dataset
    df = pl.DataFrame(
        {
            "station_id": ["00001"],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "parameter": ["not_a_parameter"],
            "timestamp": [dt.datetime(1990, 1, 1, tzinfo=ZoneInfo("UTC"))],
            "value": [1.0],
            "quality_flags": [None],
        },
        schema_overrides={"quality_flags": pl.String},
    )

    with pytest.raises(ProviderContractError, match=r"DwdObservationValues.*'not_a_parameter'.*daily/climate_summary"):
        values._to_requested_units(df, dataset, plan_for("dwd/observation", dataset), canonical=False)  # noqa: SLF001


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

    result = values._to_requested_units(  # noqa: SLF001
        df, request.parameters[0].dataset, plan_for("dwd/observation", request.parameters[0].dataset), canonical=False
    )

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
    monkeypatch.setattr(values.unit_converter, "lambda_between", lambda *_: lambda x: 9 / 5 * x)
    df = _long([("daily", "climate_summary", "shk_tag", 0, 5.0), ("daily", "climate_summary", "shk_tag", 1, 10.0)])

    result = values._to_requested_units(  # noqa: SLF001
        df, request.parameters[0].dataset, plan_for("dwd/observation", request.parameters[0].dataset), canonical=False
    )

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


_READING = ["station_id", "resolution", "dataset", "parameter", "timestamp"]


def _readings(*rows: tuple[str, str, int, float | None, str | None]) -> pl.DataFrame:
    """Build a long frame of (station, parameter, hour, value, quality_flags) rows of one hourly dataset."""
    return pl.DataFrame(
        {
            "station_id": [row[0] for row in rows],
            "resolution": ["hourly"] * len(rows),
            "dataset": ["climate"] * len(rows),
            "parameter": [row[1] for row in rows],
            "timestamp": [dt.datetime(2026, 1, 1, row[2], tzinfo=ZoneInfo("UTC")) for row in rows],
            "value": [row[3] for row in rows],
            "quality_flags": [row[4] for row in rows],
        },
        schema={**LONG_SCHEMA},
    )


def test_merge_duplicate_readings_takes_the_value_of_the_second_row_where_the_first_has_none() -> None:
    """A null first row no longer takes the reading with it (GH-3450), and the flag is the value's own."""
    df = _readings(("01", "t", 0, None, "raw:-999"), ("01", "t", 0, 5.0, "3"))

    merged = merge_duplicate_readings(df, _READING)

    assert_frame_equal(merged, _readings(("01", "t", 0, 5.0, "3")))


def test_merge_duplicate_readings_keeps_the_value_of_the_first_row_where_the_second_has_none() -> None:
    """A null second row takes nothing from the first, and does not add its flag to it."""
    df = _readings(("01", "t", 0, 5.0, "3"), ("01", "t", 0, None, "raw:-999"))

    merged = merge_duplicate_readings(df, _READING)

    assert_frame_equal(merged, _readings(("01", "t", 0, 5.0, "3")))


def test_merge_duplicate_readings_keeps_the_first_of_two_values_and_counts_the_conflict(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Two different values keep the first, with its flag, and one debug line says how many readings conflicted."""
    df = _readings(
        ("01", "t", 0, 5.0, "3"),
        ("01", "t", 0, 6.0, "1"),
        # the same value twice is no conflict
        ("01", "t", 1, 7.0, "3"),
        ("01", "t", 1, 7.0, "1"),
        # a value after a null is not one either
        ("01", "t", 2, None, None),
        ("01", "t", 2, 8.0, "1"),
    )

    with caplog.at_level(logging.DEBUG, logger="wetterdienst.model.values"):
        merged = merge_duplicate_readings(df, _READING)

    assert_frame_equal(merged, _readings(("01", "t", 0, 5.0, "3"), ("01", "t", 1, 7.0, "3"), ("01", "t", 2, 8.0, "1")))
    assert "6 rows share a reading with another and make 3 readings, 1 with different values" in caplog.text


def test_merge_duplicate_readings_hands_back_a_frame_without_duplicates_as_it_is() -> None:
    """No two rows of one reading is the identity, and the object itself."""
    df = _readings(("01", "t", 0, None, "raw:-999"), ("01", "t", 1, 5.0, "3"), ("01", "w", 0, 1.0, None))

    assert merge_duplicate_readings(df, _READING) is df


def test_merge_duplicate_readings_keeps_a_reading_with_no_value_as_its_first_row() -> None:
    """Where every row of a reading is null the first stays, with the text the source wrote for it."""
    df = _readings(("01", "t", 0, None, "raw:-999"), ("01", "t", 0, None, "raw:-99"))

    assert_frame_equal(merge_duplicate_readings(df, _READING), _readings(("01", "t", 0, None, "raw:-999")))


def test_merge_duplicate_readings_reads_each_parameter_and_each_station_on_its_own() -> None:
    """A null of one parameter or station is not filled from the row of another that shares its timestamp."""
    df = _readings(
        ("01", "t", 0, None, None),
        ("01", "w", 0, 3.0, "3"),
        ("02", "t", 0, 4.0, "3"),
        ("01", "t", 0, 5.0, "1"),
        ("02", "w", 0, None, None),
        ("02", "t", 0, None, "raw:-999"),
        ("01", "w", 0, None, None),
    )

    merged = merge_duplicate_readings(df, _READING)

    # in the order the readings first appeared in
    assert_frame_equal(
        merged,
        _readings(
            ("01", "t", 0, 5.0, "1"),
            ("01", "w", 0, 3.0, "3"),
            ("02", "t", 0, 4.0, "3"),
            ("02", "w", 0, None, None),
        ),
    )


def test_merge_duplicate_readings_keeps_the_order_of_the_rows_it_does_not_merge() -> None:
    """The readings keep the order of their first row, whether they are merged or not."""
    df = _readings(
        ("01", "t", 3, 3.0, None),
        ("01", "t", 1, None, None),
        ("01", "t", 2, 2.0, None),
        ("01", "t", 1, 1.0, "3"),
        ("01", "t", 0, 0.0, None),
    )

    merged = merge_duplicate_readings(df, _READING)

    assert merged.get_column("value").to_list() == [3.0, 1.0, 2.0, 0.0]
    assert merged.columns == df.columns
    assert merged.schema == df.schema


def test_merge_duplicate_readings_takes_every_other_column_from_the_row_of_the_value() -> None:
    """A column beside `value` (the date of a file) is the one of the row the value is of."""
    df = _readings(("01", "t", 0, None, None), ("01", "t", 0, 5.0, "3")).with_columns(
        pl.Series(
            "updated",
            [dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2026, 2, 1, tzinfo=ZoneInfo("UTC"))],
        )
    )

    merged = merge_duplicate_readings(df, _READING)

    assert merged.get_column("updated").to_list() == [dt.datetime(2026, 2, 1, tzinfo=ZoneInfo("UTC"))]


def test_a_reading_given_by_two_rows_has_the_value_of_the_one_that_has_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The case of GH-3450 through the whole core: a provider hands two rows for one day, the first without a value."""
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    utc = ZoneInfo("UTC")
    name = DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m.name_original

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, day, tzinfo=utc) for day in (1, 1, 2, 2)],
                "parameter": [name] * 4,
                "value": [None, 1.5, 2.5, None],
                "quality_flags": ["raw:-999", "3", "1", "raw:-999"],
            },
            schema_overrides={"value": pl.Float64},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-02",
    )

    df = request.filter_by_station_id("00001").values().all().df

    assert df.get_column("value").to_list() == [1.5, 2.5]
    assert df.get_column("quality_flags").to_list() == ["3", "1"]


@pytest.mark.parametrize("drop_nulls", [True, False])
def test_the_missing_value_marker_warning_counts_the_window_and_not_the_file(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool
) -> None:
    """The file holds a marker on each of ten days; the warning of a 2-day request counts the two inside the window."""
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    utc = ZoneInfo("UTC")
    name = DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m.name_original
    days = range(1, 11)

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, day, tzinfo=utc) for day in days],
                "parameter": [name] * len(days),
                "value": [None] * len(days),
                "quality_flags": ["raw:-999"] * len(days),
            },
            schema_overrides={"value": pl.Float64},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-04",
        end="1990-01-05",
        options=Options(drop_nulls=drop_nulls),
    )

    request.filter_by_station_id("00001").values().all()

    # with the nulls dropped the parameter has no row left, which `parameter-without-rows` tells besides
    warnings = [warning for warning in recorded_warnings() if warning["code"] != "parameter-without-rows"]
    assert [warning["code"] for warning in warnings] == ["missing-value-marker"]
    assert warnings[0]["message"].startswith("2 readings of the source")


def _stub_marked_readings(monkeypatch: pytest.MonkeyPatch, *, markers_of: dict[str, int], days: int = 4) -> None:
    """Have each station hold `days` daily readings of January 1990, the first `markers_of[station]` of them a marker.

    A marker is a null value with the `raw:` token the source wrote, as a provider's reader leaves it.
    """
    utc = ZoneInfo("UTC")
    name = DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m.name_original

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        marked = [day < markers_of[station_id] for day in range(days)]
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, day + 1, tzinfo=utc) for day in range(days)],
                "parameter": [name] * days,
                "value": [None if mark else 1.0 for mark in marked],
                "quality_flags": ["raw:-999" if mark else "1" for mark in marked],
            },
            schema_overrides={"value": pl.Float64},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _the_missing_value_marker_warning() -> list[str]:
    """Give the messages of the `missing-value-marker` warnings recorded for the request."""
    return [warning["message"] for warning in recorded_warnings() if warning["code"] == "missing-value-marker"]


@pytest.mark.parametrize("drop_nulls", [True, False])
def test_the_missing_value_marker_warning_leaves_out_a_station_skip_empty_drops(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool
) -> None:
    """A station skipped for having no reading is not in the answer, and its markers are not counted (GH-3554).

    With the nulls dropped (the default) the station's frame is empty, with them kept it is a frame of nulls: both
    are left out by `skip_empty`, and neither is counted.
    """
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    _stub_marked_readings(monkeypatch, markers_of={"00001": 4})
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-04",
        options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.5),
    )

    df = request.filter_by_station_id("00001").values().all().df

    assert df.is_empty()
    assert _the_missing_value_marker_warning() == []


@pytest.mark.parametrize("skip_empty", [True, False])
@pytest.mark.parametrize("drop_nulls", [True, False])
def test_the_missing_value_marker_warning_counts_the_station_a_rank_walk_ends_on_and_not_the_ones_it_skips(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool, skip_empty: bool
) -> None:
    """`rank=1` walks past the nearest station, which has no reading, and ends on the next: only its 2 markers count.

    The nearest is skipped by `skip_empty`, or, where that is off, emptied by `drop_nulls` and not a slot of the rank;
    where the nulls are kept and `skip_empty` is off it is the station the rank ends on (4 markers).
    """
    _stub_dwd_daily(
        station_ids=["00001", "00002"],
        data_year_by_station={"00001": 1990, "00002": 1990},
        monkeypatch=monkeypatch,
    )
    _stub_marked_readings(monkeypatch, markers_of={"00001": 4, "00002": 2})
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-04",
        options=Options(drop_nulls=drop_nulls, skip_empty=skip_empty, skip_threshold=0.5),
    )

    df = request.filter_by_rank(latlon=(50.0, 8.0), rank=1).values().all().df

    ends_on_nearest = not drop_nulls and not skip_empty
    assert df.get_column("station_id").unique().to_list() == ["00001" if ends_on_nearest else "00002"]
    messages = _the_missing_value_marker_warning()
    assert len(messages) == 1
    assert messages[0].startswith("4 readings of the source" if ends_on_nearest else "2 readings of the source")


@pytest.mark.parametrize("by", ["station_id", "name"])
@pytest.mark.parametrize("drop_nulls", [True, False])
def test_the_missing_value_marker_warning_counts_a_station_the_request_names_when_the_nulls_empty_it(
    monkeypatch: pytest.MonkeyPatch, *, by: str, drop_nulls: bool
) -> None:
    """A station picked by id or by name, whose window holds markers only, counts them with or without `drop_nulls`.

    `filter_by_name` sets a rank (of 1) as well, but no station takes the place of the one it picked.
    """
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
    _stub_marked_readings(monkeypatch, markers_of={"00001": 4})
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-04",
        options=Options(drop_nulls=drop_nulls),
    )
    stations = request.filter_by_station_id("00001") if by == "station_id" else request.filter_by_name("00001")

    stations.values().all()

    messages = _the_missing_value_marker_warning()
    assert len(messages) == 1
    assert messages[0].startswith("4 readings of the source")


def test_the_missing_value_marker_warning_counts_the_stations_a_name_matches_up_to_its_rank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`filter_by_name` with `rank=2` picks the two best matches, and the markers of both count: 4 and 1."""
    _stub_dwd_daily(
        station_ids=["00001", "00002"],
        data_year_by_station={"00001": 1990, "00002": 1990},
        monkeypatch=monkeypatch,
    )
    _stub_marked_readings(monkeypatch, markers_of={"00001": 4, "00002": 1})
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-04",
    )

    request.filter_by_name("0000", rank=2).values().all()

    messages = _the_missing_value_marker_warning()
    assert len(messages) == 1
    assert messages[0].startswith("5 readings of the source")


def test_the_missing_value_marker_warning_leaves_out_a_station_a_distance_filter_skips_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the nulls dropped, a station `skip_empty` skips under a distance filter is not counted, the others are."""
    _stub_dwd_daily(
        station_ids=["00001", "00002", "00003"],
        data_year_by_station=dict.fromkeys(["00001", "00002", "00003"], 1990),
        monkeypatch=monkeypatch,
    )
    _stub_marked_readings(monkeypatch, markers_of={"00001": 4, "00002": 1, "00003": 1})
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-04",
        options=Options(skip_empty=True, skip_threshold=0.5),
    )

    df = request.filter_by_distance(latlon=(50.0, 8.0), distance=30).values().all().df

    assert sorted(df.get_column("station_id").unique().to_list()) == ["00002", "00003"]
    messages = _the_missing_value_marker_warning()
    assert len(messages) == 1
    assert messages[0].startswith("2 readings of the source")


@pytest.mark.parametrize("method", ["summarize", "interpolate"])
def test_an_estimate_carries_no_missing_value_marker_warning(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    """The estimate is not the readings of the source, so it does not count the markers of the stations it reads."""
    latitude, longitude = 50.0, 8.9
    offsets = {"00001": (-0.03, -0.03), "00002": (-0.03, 0.03), "00003": (0.03, 0.03), "00004": (0.03, -0.03)}
    stations = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "climate_summary",
                "station_id": station_id,
                "latitude": latitude + d_lat,
                "longitude": longitude + d_lon,
                "elevation": 100.0,
                "distance": 4.0 + index / 10,
            }
            for index, (station_id, (d_lat, d_lon)) in enumerate(offsets.items())
        ],
    )

    def all_(self: DwdObservationRequest) -> StationsResult:
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.ALL)

    def filter_by_distance(
        self: DwdObservationRequest,
        latlon: tuple[float, float],  # noqa: ARG001
        distance: float,  # noqa: ARG001
        df_all: pl.DataFrame | None = None,  # noqa: ARG001
    ) -> StationsResult:
        return StationsResult(request=self, df=stations, _df_all=stations, _stations_filter=StationsFilter.BY_DISTANCE)

    monkeypatch.setattr(DwdObservationRequest, "all", all_)
    monkeypatch.setattr(DwdObservationRequest, "filter_by_distance", filter_by_distance)
    # a marker in each station, and three valid readings left of the four days
    _stub_marked_readings(monkeypatch, markers_of=dict.fromkeys(offsets, 1))
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-04",
    )

    result = getattr(request, method)(latlon=(latitude, longitude))

    assert not result.df.is_empty()
    assert _the_missing_value_marker_warning() == []


def _warning_codes_by_station() -> dict[str, list[str]]:
    """Give the codes of the warnings recorded for the request, with the message of each `station-skipped`."""
    return {
        "station-skipped": [w["message"] for w in recorded_warnings() if w["code"] == "station-skipped"],
        "parameter-without-rows": [w["message"] for w in recorded_warnings() if w["code"] == "parameter-without-rows"],
    }


@pytest.mark.parametrize("by", ["station_id", "rank"])
@pytest.mark.parametrize("shape", ["long", "wide"])
@pytest.mark.parametrize("skip_empty", [True, False])
@pytest.mark.parametrize("drop_nulls", [True, False])
def test_station_skipped_is_told_for_a_station_of_nulls_whatever_drop_nulls_is(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool, skip_empty: bool, shape: str, by: str
) -> None:
    """`skip_empty` leaves a station out and says so, with the nulls dropped (the default) or kept (GH-3567).

    The first station holds nothing but markers, the second four readings. With the nulls dropped the first station's
    frame is empty and used to be passed over unsaid; with them kept it is a frame of nulls, which `skip_empty` skips
    and tells. A rank walk that does not have `skip_empty` passes it over (nulls dropped) or ends on it (nulls kept):
    it is not skipped by `skip_empty` and nothing is told, as before. What the answer holds does not depend on this.
    """
    _stub_dwd_daily(
        station_ids=["00001", "00002"], data_year_by_station={"00001": 1990, "00002": 1990}, monkeypatch=monkeypatch
    )
    _stub_marked_readings(monkeypatch, markers_of={"00001": 4, "00002": 0})
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-04",
        options=Options(drop_nulls=drop_nulls, skip_empty=skip_empty, skip_threshold=0.5, shape=shape),
    )
    stations = (
        request.filter_by_station_id("00001")
        if by == "station_id"
        else request.filter_by_rank(latlon=(50.0, 8.0), rank=1)
    )

    df = stations.values().all().df

    codes = _warning_codes_by_station()
    if skip_empty:
        assert codes["station-skipped"] == [
            "station 00001 is skipped as percentage of actual values (0.0) is below threshold (0.5)."
        ]
    else:
        assert codes["station-skipped"] == []
    # the data is not what this changes: a station the walk leaves out is not in the answer, in either setting
    # (the wide shape drops no nulls: `drop_nulls` is ignored there)
    nulls_kept = not drop_nulls or shape == "wide"
    in_answer = df.get_column("station_id").unique().to_list()
    if by == "station_id":
        assert in_answer == ([] if skip_empty or not nulls_kept else ["00001"])
    else:
        assert in_answer == (["00001"] if not skip_empty and nulls_kept else ["00002"])


@pytest.mark.parametrize("shape", ["long", "wide"])
@pytest.mark.parametrize("skip_empty", [True, False])
@pytest.mark.parametrize("drop_nulls", [True, False])
def test_a_station_of_suspect_values_only_is_skipped_by_skip_empty(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool, skip_empty: bool, shape: str
) -> None:
    """`skip_empty` counts the unflagged values alone: a station whose values a soft check flagged is skipped (GH-3676).

    Both stations hold four readings with a value. The first has every one flagged `suspect:range` (a check that is
    soft keeps the value), the second none, and a `raw:` token or the source's own flag is no suspicion. Without
    `skip_empty` the first station's values are in the answer, flagged; with it the station is skipped and told, as a
    station of nulls is, and the second stays.
    """
    _stub_dwd_daily(
        station_ids=["00001", "00002"], data_year_by_station={"00001": 1990, "00002": 1990}, monkeypatch=monkeypatch
    )
    utc = ZoneInfo("UTC")
    name = DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m.name_original
    flags = {"00001": "3,suspect:range", "00002": "3"}

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, day, tzinfo=utc) for day in range(1, 5)],
                "parameter": [name] * 4,
                "value": [1.0] * 4,
                "quality_flags": [flags[station_id]] * 4,
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="1990-01-01",
        end="1990-01-04",
        options=Options(drop_nulls=drop_nulls, skip_empty=skip_empty, skip_threshold=0.5, shape=shape),
    )

    df = request.filter_by_station_id(["00001", "00002"]).values().all().df

    in_answer = sorted(df.get_column("station_id").unique().to_list())
    if skip_empty:
        assert in_answer == ["00002"]
        assert _warning_codes_by_station()["station-skipped"] == [
            "station 00001 is skipped as percentage of actual values (0.0) is below threshold (0.5)."
        ]
    else:
        assert in_answer == ["00001", "00002"]
        assert _warning_codes_by_station()["station-skipped"] == []


@pytest.mark.parametrize("shape", ["long", "wide"])
@pytest.mark.parametrize("skip_empty", [True, False])
def test_a_station_skip_empty_leaves_out_is_told_the_same_with_the_nulls_dropped_or_kept(
    monkeypatch: pytest.MonkeyPatch, *, skip_empty: bool, shape: str
) -> None:
    """The warnings of a station of nulls that the request names are the same under `skip_empty`, nulls dropped or kept.

    Besides `station-skipped`, `parameter-without-rows`: the station had rows (of nulls), so under `skip_empty` it
    says nothing of them, as with the nulls kept. Without `skip_empty` the nulls dropped leave the parameter without
    a row, as ever (and the station is in the answer, as a frame of nulls, only with them kept).
    """
    by_drop_nulls = {}
    for drop_nulls in (True, False):
        _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1990}, monkeypatch=monkeypatch)
        _stub_marked_readings(monkeypatch, markers_of={"00001": 4})
        begin_response()
        request = DwdObservationRequest(
            parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
            start="1990-01-01",
            end="1990-01-04",
            options=Options(drop_nulls=drop_nulls, skip_empty=skip_empty, skip_threshold=0.5, shape=shape),
        )
        request.filter_by_station_id("00001").values().all()
        by_drop_nulls[drop_nulls] = _warning_codes_by_station()

    if skip_empty or shape == "wide":
        assert by_drop_nulls[True] == by_drop_nulls[False]
    if skip_empty:
        assert len(by_drop_nulls[True]["station-skipped"]) == 1
        assert by_drop_nulls[True]["parameter-without-rows"] == []


def test_a_station_with_no_reading_in_the_window_is_not_told_as_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station with no row in the window at all is left out unsaid, with the nulls dropped or kept (GH-3567)."""
    for drop_nulls in (True, False):
        _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1980}, monkeypatch=monkeypatch)
        begin_response()
        request = DwdObservationRequest(
            parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
            start="1990-01-01",
            end="1990-01-04",
            options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.5),
        )

        request.filter_by_station_id("00001").values().all()

        assert _warning_codes_by_station()["station-skipped"] == []


def _stub_readings(
    monkeypatch: pytest.MonkeyPatch, *, readings_of: dict[str, tuple[int, dict[str, list[float | None]]]]
) -> None:
    """Have each station hold the readings `readings_of` gives: its year of January, and the values of each parameter.

    The parameters are named by their dataset and canonical name (`climate_summary/temperature_air_mean_2m`); a
    parameter a station has no entry for has no rows, and a dataset asked for whole is answered with the parameters the
    station has. A value of None is a reading without a value.
    """
    utc = ZoneInfo("UTC")

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        year, values_of = readings_of[station_id]
        parameters = [parameter_or_dataset] if hasattr(parameter_or_dataset, "dataset") else list(parameter_or_dataset)
        timestamps, names, values = [], [], []
        for parameter in parameters:
            for day, value in enumerate(values_of.get(f"{parameter.dataset.name}/{parameter.name}", []), start=1):
                timestamps.append(dt.datetime(year, 1, day, tzinfo=utc))
                names.append(parameter.name_original)
                values.append(value)
        return pl.DataFrame(
            {
                "timestamp": timestamps,
                "parameter": names,
                "value": values,
                "quality_flags": ["1"] * len(values),
            },
            schema={
                "timestamp": pl.Datetime(time_zone="UTC"),
                "parameter": pl.String,
                "value": pl.Float64,
                "quality_flags": pl.String,
            },
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


_REQUESTED_PARTLY_EMPTIED = {
    "parameters": (
        [
            ("daily", "climate_summary", "temperature_air_mean_2m"),
            ("daily", "climate_summary", "temperature_air_max_2m"),
        ],
        {
            "climate_summary/temperature_air_mean_2m": [None] * 4,
            "climate_summary/temperature_air_max_2m": [1.0, None, None, None],
        },
    ),
    "datasets": (
        [("daily", "climate_summary"), ("daily", "precipitation_more")],
        {
            "climate_summary/temperature_air_mean_2m": [None] * 4,
            "precipitation_more/precipitation_amount": [1.0, None, None, None],
        },
    ),
}


@pytest.mark.parametrize("by", ["station_id", "rank"])
@pytest.mark.parametrize("requested", ["parameters", "datasets"])
@pytest.mark.parametrize("drop_nulls", [True, False])
def test_a_station_skip_empty_leaves_out_with_a_parameter_of_nulls_is_told_the_same_whatever_drop_nulls_is(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool, requested: str, by: str
) -> None:
    """A station skipped with some readings left, one parameter or dataset of it all nulls, says no more (GH-3567).

    The parameter of nulls is a row the station has, as with the nulls kept: so `parameter-without-rows` is told of
    neither parameter (or dataset), with the nulls dropped as well as kept, and `station-skipped` of the station.
    """
    parameters, values = _REQUESTED_PARTLY_EMPTIED[requested]
    _stub_dwd_daily(
        station_ids=["00001"],
        data_year_by_station={"00001": 1990},
        monkeypatch=monkeypatch,
        datasets=["climate_summary", "more_precip"],
    )
    _stub_readings(monkeypatch, readings_of={"00001": (1990, values)})
    begin_response()
    request = DwdObservationRequest(
        parameters=parameters,
        start="1990-01-01",
        end="1990-01-04",
        options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.5),
    )
    stations = (
        request.filter_by_station_id("00001")
        if by == "station_id"
        else request.filter_by_rank(latlon=(50.0, 8.0), rank=1)
    )

    df = stations.values().all().df

    assert df.is_empty()
    assert [warning["code"] for warning in recorded_warnings()] == ["station-skipped"]
    assert recorded_warnings()[0]["message"].startswith("station 00001 is skipped as percentage of actual values (")


@pytest.mark.parametrize("drop_nulls", [True, False])
def test_a_rank_walk_tells_station_skipped_of_the_station_of_nulls_only(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool
) -> None:
    """The nulls of one station are not the next station's: the walk past a station with no row in the window is silent.

    00001 holds nothing but nulls (skipped, told), 00002 has rows only outside the window (passed over, unsaid), 00003
    has values (the rank is spent on it).
    """
    name = "temperature_air_mean_2m"
    key = f"climate_summary/{name}"
    _stub_dwd_daily(
        station_ids=["00001", "00002", "00003"],
        data_year_by_station={"00001": 1990, "00002": 1980, "00003": 1990},
        monkeypatch=monkeypatch,
    )
    _stub_readings(
        monkeypatch,
        readings_of={
            "00001": (1990, {key: [None] * 4}),
            "00002": (1980, {key: [1.0] * 4}),
            "00003": (1990, {key: [1.0] * 4}),
        },
    )
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", name)],
        start="1990-01-01",
        end="1990-01-04",
        options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.5),
    )

    df = request.filter_by_rank(latlon=(50.0, 8.0), rank=1).values().all().df

    assert df.get_column("station_id").unique().to_list() == ["00003"]
    skipped = [warning["message"] for warning in recorded_warnings() if warning["code"] == "station-skipped"]
    assert len(skipped) == 1
    assert skipped[0].startswith("station 00001 is skipped")


@pytest.mark.parametrize("drop_nulls", [True, False])
def test_the_nulls_outside_the_window_are_not_a_station_skipped(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool
) -> None:
    """A station whose readings without a value all lie outside the window has no row in it, and is left out unsaid."""
    name = "temperature_air_mean_2m"
    _stub_dwd_daily(station_ids=["00001"], data_year_by_station={"00001": 1980}, monkeypatch=monkeypatch)
    _stub_readings(monkeypatch, readings_of={"00001": (1980, {f"climate_summary/{name}": [None] * 4})})
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", name)],
        start="1990-01-01",
        end="1990-01-04",
        options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.5),
    )

    request.filter_by_station_id("00001").values().all()

    assert [warning for warning in recorded_warnings() if warning["code"] == "station-skipped"] == []


@pytest.mark.parametrize("blank", ["", " ", "n/a", "nan", "inf"])
def test_merge_duplicate_readings_reads_a_text_that_is_no_number_as_no_value(blank: str) -> None:
    """A frame whose `value` is still text (as the provider hands it over) has a value where a number can be read."""
    df = pl.DataFrame(
        {
            "parameter": ["t", "t", "w", "w"],
            "timestamp": [dt.datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC"))] * 4,
            "value": [blank, " 5.0 ", "1", "1.0"],
            "quality_flags": ["a", "b", "c", "d"],
        },
    )

    merged = merge_duplicate_readings(df, ["parameter", "timestamp"])

    # the second row of "t" has the number; "1" and "1.0" of "w" are one number, so no conflict, and the first is kept
    assert merged.get_column("value").to_list() == [" 5.0 ", "1"]
    assert merged.get_column("quality_flags").to_list() == ["b", "c"]


def test_merge_duplicate_readings_does_not_collide_with_a_column_of_its_own_names() -> None:
    """The columns the merge adds beside the rows are named after none of the frame's."""
    df = _readings(("01", "t", 0, None, "raw:-999"), ("01", "t", 0, 5.0, "3")).with_columns(
        pl.Series("row", [1, 2]), pl.Series("conflict", ["a", "b"]), pl.Series("_row", [3, 4])
    )

    merged = merge_duplicate_readings(df, _READING)

    assert merged.columns == df.columns
    assert merged.row(0, named=True)["row"] == 2
    assert merged.row(0, named=True)["conflict"] == "b"
    assert merged.row(0, named=True)["_row"] == 4


def _stub_readings_by_station(monkeypatch: pytest.MonkeyPatch, readings: dict[str, list[float | None]]) -> None:
    """Have each station hold the daily readings of January 1990 `readings` names (None is a null), from the 1st on."""
    utc = ZoneInfo("UTC")
    name = DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m.name_original

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        values = readings[station_id]
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, day + 1, tzinfo=utc) for day in range(len(values))],
                "parameter": [name] * len(values),
                "value": values,
                "quality_flags": [None if value is not None else "raw:-999" for value in values],
            },
            schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


@pytest.mark.parametrize("drop_nulls", [True, False])
def test_skip_empty_measures_a_request_without_a_window_against_the_span_with_the_nulls_kept(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool
) -> None:
    """The same stations are skipped with the nulls dropped or kept, for a request that names no window (GH-3578).

    A request without a window measures a station against the span of its own series. That span was read off the frame
    after `drop_nulls`, so a station whose first readings are nulls was measured against the shorter series of its
    values: complete, and kept, with the nulls dropped, and skipped with them kept (2 of the 4 days). Now both are
    measured against the series with the nulls in it (the threshold is 0.8):

    - `lead` and `lead_one` begin with nulls (2/4 and 3/4 of the days have a value): skipped
    - `trail` ends in a null (3/4): skipped
    - `middle` has a null among its readings (3/4): skipped, as it always was
    - `full` has all four: kept
    """
    readings: dict[str, list[float | None]] = {
        "00001": [None, None, 1.0, 1.0],  # lead
        "00002": [None, 1.0, 1.0, 1.0],  # lead_one
        "00003": [1.0, 1.0, 1.0, None],  # trail
        "00004": [1.0, None, 1.0, 1.0],  # middle
        "00005": [1.0, 1.0, 1.0, 1.0],  # full
    }
    _stub_dwd_daily(
        station_ids=list(readings), data_year_by_station=dict.fromkeys(readings, 1990), monkeypatch=monkeypatch
    )
    _stub_readings_by_station(monkeypatch, readings)
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.8),
    )

    df = request.filter_by_station_id(list(readings)).values().all().df

    assert df.get_column("station_id").unique().to_list() == ["00005"]
    assert sorted(_warning_codes_by_station()["station-skipped"]) == [
        f"station {station_id} is skipped as percentage of actual values ({share}) is below threshold (0.8)."
        for station_id, share in [("00001", 0.5), ("00002", 0.75), ("00003", 0.75), ("00004", 0.75)]
    ]


def test_skip_empty_with_a_window_does_not_depend_on_drop_nulls(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request that names a window is measured against it, so `drop_nulls` never mattered there."""
    readings: dict[str, list[float | None]] = {"00001": [None, None, 1.0, 1.0], "00002": [1.0, 1.0, 1.0, 1.0]}
    _stub_dwd_daily(
        station_ids=list(readings), data_year_by_station=dict.fromkeys(readings, 1990), monkeypatch=monkeypatch
    )
    _stub_readings_by_station(monkeypatch, readings)
    kept = []
    for drop_nulls in (True, False):
        request = DwdObservationRequest(
            parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
            start="1990-01-01",
            end="1990-01-04",
            options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.8),
        )
        kept.append(
            request.filter_by_station_id(list(readings)).values().all().df.get_column("station_id").unique().to_list()
        )

    assert kept == [["00002"], ["00002"]]


_SUBDAILY_CASES = {
    # half of 00001's readings are nulls: skipped
    "no-window": (None, {"00001": [None, None, 1.0, 1.0], "00002": [1.0, 1.0, 1.0, 1.0]}, {"00001": 0.5}),
    # the window ends at 12:00 and holds three of the four readings: 00001 has a value for each of them (its null is
    # outside), 00003 for one of the three
    "window-cuts-readings": (
        ("1990-01-01", "1990-01-01 12:00"),
        {"00001": [1.0, 1.0, 1.0, None], "00002": [1.0, 1.0, 1.0, 1.0], "00003": [None, None, 1.0, 1.0]},
        {"00003": 1 / 3},
    ),
}


@pytest.mark.parametrize("drop_nulls", [True, False])
@pytest.mark.parametrize("case", list(_SUBDAILY_CASES), ids=list(_SUBDAILY_CASES))
def test_skip_empty_of_a_resolution_without_a_grid_does_not_depend_on_drop_nulls(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool, case: str
) -> None:
    """A subdaily request, which has no grid to count readings by, skips the same stations whatever `drop_nulls` is.

    The share is then of the readings the station has in the window: the non-null ones of those it holds with the
    nulls kept. It was of the rows left by `drop_nulls`, which are all non-null, so the nulls-dropped share was always
    1 and no station was skipped (GH-3578). The same holds with a window, which does not give a subdaily series a grid,
    and it is the readings in the window that count, not those of the whole file.
    """
    utc = ZoneInfo("UTC")
    window, readings, skipped = _SUBDAILY_CASES[case]
    _stub_dwd_daily(
        station_ids=list(readings),
        data_year_by_station=dict.fromkeys(readings, 1990),
        datasets=["temperature_air"],
        resolution="subdaily",
        monkeypatch=monkeypatch,
    )
    name = DwdObservationMetadata.subdaily.temperature_air.temperature_air_2m.name_original

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        values = readings[station_id]
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, 1, 6 * hour, tzinfo=utc) for hour in range(len(values))],
                "parameter": [name] * len(values),
                "value": values,
                "quality_flags": [None] * len(values),
            },
            schema_overrides={"value": pl.Float64, "quality_flags": pl.String},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    begin_response()
    start, end = window or (None, None)
    request = DwdObservationRequest(
        parameters=[("subdaily", "temperature_air", "temperature_air_2m")],
        start=start,
        end=end,
        options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.8),
    )

    df = request.filter_by_station_id(list(readings)).values().all().df

    assert sorted(df.get_column("station_id").unique().to_list()) == sorted(set(readings) - set(skipped))
    assert sorted(_warning_codes_by_station()["station-skipped"]) == [
        f"station {station_id} is skipped as percentage of actual values ({share}) is below threshold (0.8)."
        for station_id, share in sorted(skipped.items())
    ]


@pytest.mark.parametrize("drop_nulls", [True, False])
def test_skip_empty_spans_are_those_of_the_station_in_hand(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool
) -> None:
    """A station without a window is measured against its own span, not against the one of the stations before it.

    Both stations are complete over their own days (1 to 10 and 6 to 10 of January). Measured against the span of
    both, the second would hold half of it and be skipped.
    """
    utc = ZoneInfo("UTC")
    days = {"00001": range(1, 11), "00002": range(6, 11)}
    _stub_dwd_daily(station_ids=list(days), data_year_by_station=dict.fromkeys(days, 1990), monkeypatch=monkeypatch)
    name = DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m.name_original

    def collect(self, station_id: str, parameter_or_dataset) -> pl.DataFrame:  # noqa: ANN001, ARG001
        return pl.DataFrame(
            {
                "timestamp": [dt.datetime(1990, 1, day, tzinfo=utc) for day in days[station_id]],
                "parameter": [name] * len(days[station_id]),
                "value": [1.0] * len(days[station_id]),
                "quality_flags": [None] * len(days[station_id]),
            },
            schema_overrides={"quality_flags": pl.String},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    begin_response()
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        options=Options(drop_nulls=drop_nulls, skip_empty=True, skip_threshold=0.8),
    )

    df = request.filter_by_station_id(list(days)).values().all().df

    assert sorted(df.get_column("station_id").unique().to_list()) == ["00001", "00002"]
    assert _warning_codes_by_station()["station-skipped"] == []


def test_the_readings_a_station_has_are_matched_to_a_parameter_in_the_providers_own_casing() -> None:
    """The readings counted before `drop_nulls` are found for a parameter the provider writes in its own casing.

    As for the frame (WSV reports `w` where its metadata declares `W`): the rows of `TT_TER` are those of `tt_ter`, or
    the share would be taken of the rows left, which are all non-null (GH-3578).
    """
    request = DwdObservationRequest(parameters=[("subdaily", "temperature_air", "temperature_air_2m")])
    values = DwdObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )
    stamps = [dt.datetime(1990, 1, 1, 6 * hour, tzinfo=ZoneInfo("UTC")) for hour in range(2)]
    # two readings are left of four once the nulls are dropped
    df = pl.DataFrame(
        {
            "station_id": ["01048"] * 2,
            "resolution": ["subdaily"] * 2,
            "dataset": ["temperature_air"] * 2,
            "parameter": ["tt_ter"] * 2,
            "timestamp": stamps,
            "value": [1.0, 1.0],
            "quality_flags": [None] * 2,
        },
        schema_overrides={"quality_flags": pl.String},
    )
    values._window_rows.append(  # noqa: SLF001
        pl.DataFrame({"resolution": ["subdaily"], "dataset": ["temperature_air"], "parameter": ["TT_TER"], "rows": [4]})
    )

    assert values._get_actual_percentage(df=df, rows=values._station_rows()) == 0.5  # noqa: SLF001


def _values_with_stations(df: pl.DataFrame) -> DwdObservationValues:
    """Give a values object whose station list is `df`, without a request behind it."""
    values = DwdObservationValues.__new__(DwdObservationValues)
    values.sr = SimpleNamespace(df=df)  # ty: ignore[invalid-assignment]
    return values


def test_the_elevation_of_a_station_is_the_one_of_the_row_of_its_dataset() -> None:
    """Test that a list with a row per resolution and dataset gives the elevation of the dataset asked for (GH-3627)."""
    df = pl.DataFrame(
        {
            "station_id": ["00433", "00433", "00433", "05792"],
            "resolution": ["daily", "hourly", "hourly", "hourly"],
            "dataset": ["climate_summary", "pressure", "moisture", "pressure"],
            "elevation": [48.0, 51.0, None, 2956.0],
        }
    )
    values = _values_with_stations(df)
    pressure = DwdObservationMetadata.hourly.pressure
    assert values._station_elevation("00433", pressure) == 51.0  # noqa: SLF001
    assert values._station_elevation("00433", DwdObservationMetadata.daily.climate_summary) == 48.0  # noqa: SLF001
    # a dataset whose row has no elevation, or that the station has no row of, gives none
    assert values._station_elevation("00433", DwdObservationMetadata.hourly.moisture) is None  # noqa: SLF001
    assert values._station_elevation("05792", DwdObservationMetadata.daily.climate_summary) is None  # noqa: SLF001
    assert values._station_elevation("00433") == 48.0  # noqa: SLF001


def test_the_elevation_of_a_station_list_without_dataset_columns_or_elevation() -> None:
    """Test that a list without resolution and dataset columns is read by station, and one without elevation is none."""
    with_elevation = _values_with_stations(pl.DataFrame({"station_id": ["1", "1"], "elevation": [None, 7.0]}))
    assert with_elevation._station_elevation("1", DwdObservationMetadata.hourly.pressure) == 7.0  # noqa: SLF001
    without = _values_with_stations(pl.DataFrame({"station_id": ["1"]}))
    assert without._station_elevation("1") is None  # noqa: SLF001
