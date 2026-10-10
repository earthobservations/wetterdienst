# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Hold every values frame an offline provider test produces to the physical range of its parameters (GH-2615)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.physical_ranges import describe, out_of_range
from wetterdienst.model.values import TimeseriesValues

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from wetterdienst.model.metadata import DatasetModel, ParameterModel


@pytest.fixture(autouse=True)
def physical_range_findings(request: pytest.FixtureRequest) -> Generator[list[str]]:
    """Fail a test whose provider returned a value that no parameter can have, and hand over what was found.

    The check is made on the frame that `TimeseriesValues._process_dataset` gives for a station and a dataset, after
    the unit conversion and before the result is shaped, so it sees the values in the unit a caller is handed them
    in. The window of the request is cut after it, though a reader may have cut it already, so a sentinel outside the
    window can fail a test. A test that calls `_collect_station_parameter_or_dataset` directly never reaches it. It
    is collected and raised at teardown rather than on the spot, because several providers degrade on a bare
    `except Exception` and a raise there would be swallowed.

    The values of a unit type that is converted to another unit than the default are left alone, and so is a frame
    that is not converted at all: they are not in the unit the ranges are written in. A remote test is left alone as
    well, unless `WD_CHECK_RANGES_REMOTE` is set to `1`: what a real source answers with changes, and a leak the
    offline fixtures pin (`value_stubs.py`) would turn the remote tests red until the provider is fixed. A test marked
    `synthetic_values` serves numbers that are no readings and is left alone too.

    A test that shows what a provider does with a value out of range on purpose asks for the list, which is the live
    one, asserts on it and clears it.
    """
    found: list[str] = []
    skipped = request.node.get_closest_marker("synthetic_values") or (
        request.node.get_closest_marker("remote")
        and os.environ.get("WD_CHECK_RANGES_REMOTE", "").lower() not in {"1", "true", "yes"}
    )
    if skipped:
        yield found
        return
    process_dataset = TimeseriesValues._process_dataset  # noqa: SLF001

    def checked(
        self: TimeseriesValues,
        station_id: str,
        dataset: DatasetModel,
        parameters: Sequence[ParameterModel],
    ) -> pl.DataFrame:
        df = process_dataset(self, station_id, dataset, parameters)
        settings = self.sr.settings
        if df.is_empty() or not settings.ts_convert_units:
            return df
        # the column holds the source's own name for the parameter, in the case the provider wrote it in; those
        # converted to units of the caller's choosing are not in the unit the ranges are written in
        names = {
            parameter.name_original.lower(): parameter.name
            for parameter in dataset.parameters
            if parameter.unit_type not in settings.ts_unit_targets
        }
        if not names:
            return df
        resolution = dataset.resolution.name
        df_checked = df.filter(pl.col("parameter").cast(pl.String).str.to_lowercase().is_in(list(names)))
        outside = out_of_range(df_checked, names, resolution)
        if not outside.is_empty():
            provider = type(self).__module__.removeprefix("wetterdienst.provider.")
            found.append(f"{provider} {resolution}/{dataset.name}: {describe(outside, names, resolution=resolution)}")
        return df

    # patched by hand rather than through `monkeypatch`, which a test may undo as a whole
    TimeseriesValues._process_dataset = checked  # noqa: SLF001
    try:
        yield found
    finally:
        TimeseriesValues._process_dataset = process_dataset  # noqa: SLF001
    if found:
        pytest.fail(
            "a value outside the physical range of its parameter, which is what a missing-value sentinel that "
            f"reached the output looks like: {' | '.join(found)}",
            pytrace=False,
        )
