# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Hold every values frame a provider test produces to the physical range of its parameters (GH-2615)."""

from __future__ import annotations

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

    The check is made on the frame every provider's values pass through, after the unit conversion and before the
    result is shaped, so it sees what a caller is handed and in the unit it is handed in. It is collected and raised
    at teardown rather than on the spot, because several providers degrade on a bare `except Exception` and a raise
    there would be swallowed. A frame that is not converted is left alone: its values are in the source's own unit,
    which the ranges do not describe.

    A test that shows what a provider does with a value out of range on purpose asks for the list, which is the live
    one, asserts on it and clears it.
    """
    found: list[str] = []
    process_dataset = TimeseriesValues._process_dataset  # noqa: SLF001

    def checked(
        self: TimeseriesValues,
        station_id: str,
        dataset: DatasetModel,
        parameters: Sequence[ParameterModel],
    ) -> pl.DataFrame:
        df = process_dataset(self, station_id, dataset, parameters)
        if df.is_empty() or not self.sr.settings.ts_convert_units:
            return df
        # the column holds the source's own name for the parameter, in the case the provider wrote it in
        names = {parameter.name_original.lower(): parameter.name for parameter in dataset.parameters}
        outside = out_of_range(df.with_columns(pl.col("parameter").cast(pl.String).str.to_lowercase()), names)
        if not outside.is_empty():
            provider = type(self).__module__.removeprefix("wetterdienst.provider.")
            found.append(f"{provider} {dataset.resolution.name}/{dataset.name}: {describe(outside, names)}")
        return df

    # patched by hand rather than through `monkeypatch`, which a test may undo as a whole
    TimeseriesValues._process_dataset = checked  # noqa: SLF001
    try:
        yield found
    finally:
        TimeseriesValues._process_dataset = process_dataset  # noqa: SLF001
    if found and not request.node.get_closest_marker("synthetic_values"):
        pytest.fail(
            "a value outside the physical range of its parameter, which is what a missing-value sentinel that "
            f"reached the output looks like: {' | '.join(found)}",
            pytrace=False,
        )
