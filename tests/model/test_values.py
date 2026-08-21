"""Tests for shared TimeseriesValues behavior."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
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
