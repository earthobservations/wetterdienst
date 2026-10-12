# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures for the provider tests: the timestamp column and the physical range of the values (GH-2615)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.provider.physical_ranges import describe, out_of_range
from tests.provider.timestamps import timestamp_problem
from wetterdienst.model import result as results
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.unit import UnitConverter
from wetterdienst.model.values import TimeseriesValues

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from wetterdienst.model.metadata import DatasetModel, ParameterModel

# Columns a request's `_all()` still carries although `all()` drops them, by request class. Fixing the reader is the
# better answer; an entry is for a column that was there before the check was, and each is a to-do of its own.
INTERMEDIATE_STATION_COLUMNS: dict[str, frozenset[str]] = {
    # raw columns of the catalogue that the reader leaves in the frame, among them the WMO number (GH-2751)
    "GeosphereObservationRequest": frozenset(
        {
            "Synopstationsnummer",
            "Synop",
            "Startdatum Teilzeitreihe",
            "Enddatum Teilzeitreihe",
            "Verknüpfungsnummer",
            "zusammengesetzt",
        }
    ),
}

_RESULT_CLASSES = (results.ValuesResult, results.InterpolatedValuesResult, results.SummarizedValuesResult)


@pytest.fixture(autouse=True)
def _timestamp_column_is_utc_microseconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold the frame of every values result a test builds to one type of ``timestamp`` column.

    The provider tests are where the providers' offline fixtures live -- a canned response served in
    place of the upstream, parsed by the provider's own code -- and each of them ends in a result
    frame. Checking the column here, on construction, applies the one rule to every fixture present
    and to any added later without the author having to remember it, and names the test that built
    the frame. Remote tests are held to it too.

    A provider that stamps in local time or in nanoseconds has to convert in its own parser. Nothing
    downstream does: the values frame takes the column as it finds it, so a provider that hands back
    anything else leaks it to the caller.
    """
    for cls in _RESULT_CLASSES:
        monkeypatch.setattr(cls, "__init__", _checked_init(cls.__init__))


@pytest.fixture(autouse=True)
def station_column_findings() -> Generator[list[str]]:
    """Fail a test whose provider builds a station column its ``_base_columns`` leave out, and hand over what was found.

    `TimeseriesRequest.all()` keeps the columns in `_base_columns` and drops the rest without a word, so a reader that
    builds a column the request does not declare (WSV's river kilometre, GHCN's WMO number) loses it silently, and so
    does one that leaves a raw column of its source in the frame. Checking the frame `_all()` gives on every call that
    a provider test makes applies the rule to every fixture present and to any added later, and names the request
    class. Remote tests are held to it too. A column a reader keeps on purpose and drops itself is listed in
    `INTERMEDIATE_STATION_COLUMNS`, with its reason.

    It is collected and raised at teardown, because a provider may swallow what `all()` raises. A test that shows
    what the check finds on purpose asks for the list, which is the live one, asserts on it and clears it.
    """
    found: list[str] = []
    all_ = TimeseriesRequest.all

    def checked(self: TimeseriesRequest) -> Any:  # noqa: ANN401
        built = self._all

        def checked_all() -> pl.LazyFrame:
            frame = built()
            name = type(self).__name__
            undeclared = [
                column
                for column in frame.collect_schema().names()
                if column not in self._base_columns
                and column not in INTERMEDIATE_STATION_COLUMNS.get(name, frozenset())
            ]
            if undeclared:
                found.append(f"{name} builds {undeclared} but declares no such station column")
            return frame

        # the request is a plain dataclass, so the instance takes the wrapper in place of the method, for this call
        # only: a wrapper left on it would nest on the next call and be copied along with the request
        previous = self.__dict__.get("_all")
        self._all = checked_all  # ty: ignore[invalid-assignment]
        try:
            return all_(self)
        finally:
            if previous is None:
                del self.__dict__["_all"]
            else:
                self._all = previous  # ty: ignore[invalid-assignment]

    # patched by hand rather than through `monkeypatch`, which a test may undo as a whole
    TimeseriesRequest.all = checked  # ty: ignore[invalid-assignment]
    try:
        yield found
    finally:
        TimeseriesRequest.all = all_  # ty: ignore[invalid-assignment]
    if found:
        pytest.fail(
            "a station column that the reader builds and `all()` drops, because the request's `_base_columns` do not "
            f"list it (add it there, or drop it in the reader): {' | '.join(sorted(set(found)))}",
            pytrace=False,
        )


def _checked_init(init: Any) -> Any:  # noqa: ANN401
    def checked(self: Any, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        init(self, *args, **kwargs)
        problem = timestamp_problem(self.df)
        assert problem is None, f"{type(self).__name__}: {problem}"

    return checked


# the unit each unit type is returned in unless the caller asks for another
_DEFAULT_TARGETS = {unit_type: unit.name for unit_type, unit in UnitConverter().targets.items()}


@pytest.fixture(autouse=True)
def physical_range_findings(request: pytest.FixtureRequest) -> Generator[list[str]]:
    """Fail a test whose provider returned a value that no parameter can have, and hand over what was found.

    The check is made on the frame that `TimeseriesValues._process_dataset` gives for a station and a dataset, after
    the unit conversion and before the result is shaped, so it sees the values in the unit a caller is handed them
    in. The window of the request is cut after it, though a reader may have cut it already, so a sentinel outside the
    window can fail a test. A test that calls `_collect_station_parameter_or_dataset` directly never reaches it. It
    is collected and raised at teardown rather than on the spot, because several providers degrade on a bare
    `except Exception` and a raise there would be swallowed.

    The values of a unit type that is converted to another unit than the default one are left alone, and so is a frame
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
        options = self.sr.options
        if df.is_empty() or not options.convert_units:
            return df
        # the column holds the source's own name for the parameter, in the case the provider wrote it in; those
        # converted to units of the caller's choosing are not in the unit the ranges are written in
        names = {
            parameter.name_original.lower(): parameter.name
            for parameter in dataset.parameters
            if options.unit_targets.get(parameter.unit_type, _DEFAULT_TARGETS[parameter.unit_type])
            == _DEFAULT_TARGETS[parameter.unit_type]
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
