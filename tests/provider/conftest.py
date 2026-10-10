# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures for the provider tests."""

from typing import Any

import pytest

from tests.provider.timestamps import timestamp_problem
from wetterdienst.model import result as results

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


def _checked_init(init: Any) -> Any:  # noqa: ANN401
    def checked(self: Any, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        init(self, *args, **kwargs)
        problem = timestamp_problem(self.df)
        assert problem is None, f"{type(self).__name__}: {problem}"

    return checked
