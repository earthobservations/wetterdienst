# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Write JSON that a strict parser reads."""

from __future__ import annotations

import json
import math
from typing import Any


def _non_finite_as_null(value: Any) -> Any:  # noqa: ANN401
    """Give back `value` with every NaN and infinity in it replaced by `None`; containers are copied, not changed."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _non_finite_as_null(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_non_finite_as_null(item) for item in value]
    return value


def dumps_json(value: Any, **kwargs: Any) -> str:  # noqa: ANN401
    """Write `value` as JSON, a NaN or an infinity as `null`.

    `json.dumps` writes them as the bare tokens `NaN` and `Infinity`, which RFC 8259 does not have and a strict parser
    such as JavaScript's `JSON.parse` refuses. `null` is what polars' `write_ndjson` writes for them. The common case, a
    value without any, is written once; only one that holds one is walked to replace them.

    Args:
        value: The value to write.
        **kwargs: The arguments of `json.dumps`, except `allow_nan`.

    Returns:
        The JSON text.

    """
    try:
        return json.dumps(value, allow_nan=False, **kwargs)
    except ValueError as e:
        # `json.dumps` raises a `ValueError` for a circular reference as well, which the second attempt raises again
        if "Out of range float values" not in str(e):
            raise
        return json.dumps(_non_finite_as_null(value), allow_nan=False, **kwargs)
