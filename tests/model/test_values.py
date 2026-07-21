"""Tests for shared TimeseriesValues behavior."""

import polars as pl
from polars.testing import assert_frame_equal

from wetterdienst.model.values import TimeseriesValues


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
