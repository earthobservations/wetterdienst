"""Utility functions for user interface."""

from __future__ import annotations


def read_list(data: str | None, separator: str = ",") -> list[str]:
    """Read a list from a string."""
    if data is None:
        return []

    result = [x.strip() for x in data.split(separator)]

    if len(result) == 1 and not result[0]:
        return []

    return result
