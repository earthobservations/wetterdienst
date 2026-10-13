# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The collects of the values that polars 2 runs slower on its streaming default name the in-memory engine (GH-2781).

polars 2 collects with the streaming engine unless told otherwise. On the plans below it was measured slower than the
in-memory engine polars 1 always used, by a factor of 6 for the hourly derived radiation and 4 for 60 years of ECCC
daily rows, and the results are the same. A result cannot tell the engines apart, so these tests ask the call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.provider.value_stubs import STUBS

if TYPE_CHECKING:
    from collections.abc import Callable

    import polars as pl


@pytest.mark.parametrize(
    ("stub", "module"),
    [
        ("dwd/observation daily/climate_summary", "provider/dwd/observation/api.py"),
        ("dwd/derived hourly/radiation_global", "provider/dwd/derived/api.py"),
    ],
)
def test_dwd_values_collect_with_the_in_memory_engine(
    monkeypatch: pytest.MonkeyPatch, collect_engines: dict[str, list[str | None]], stub: str, module: str
) -> None:
    """Test that the one collect of a DWD station's values, a parse and a merge, asks for the in-memory engine."""
    build: Callable[..., pl.DataFrame] = next(s.build for s in STUBS if s.provider == stub)
    assert not build(monkeypatch).is_empty()
    assert collect_engines[module] == ["in-memory"]
