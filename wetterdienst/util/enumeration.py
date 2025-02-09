# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Enumeration utilities for the wetterdienst package."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from wetterdienst.exceptions import InvalidEnumerationError

if TYPE_CHECKING:
    from enum import Enum


def parse_enumeration_from_template(  # noqa: C901
    enum_: str | Enum,
    intermediate: type[Enum],
    base: type[Enum] | None = None,
) -> Enum | None:
    """Parse an enumeration from a template.

    Args:
        enum_: the enumeration to parse
        intermediate: the intermediate enumeration
        base: the base enumeration

    Returns:
        the parsed enumeration or None

    """
    if enum_ is None:
        return None

    enum_name = None

    # Attempt to decode parameter either as string or Enum item.
    if isinstance(enum_, str):
        enum_name = enum_
    else:
        with contextlib.suppress(AttributeError):
            enum_name = enum_.name

    try:
        enum_parsed = intermediate[enum_name.upper()]
    except (KeyError, AttributeError):
        try:
            if isinstance(enum_, str):
                candidates = [enum_, enum_.lower()]
                success = False
                for candidate in candidates:
                    try:
                        enum_parsed = intermediate(candidate)
                        success = True
                        break
                    except ValueError:
                        pass
                if not success:
                    raise ValueError  # noqa: TRY301
            else:
                enum_parsed = intermediate(enum_)
        except ValueError as e:
            msg = f"{enum_} could not be parsed from {intermediate.__name__}."
            raise InvalidEnumerationError(msg) from e

    if base:
        try:
            enum_parsed = base[enum_parsed.name]
        except (KeyError, AttributeError):
            try:
                enum_parsed = base(enum_parsed)
            except ValueError as e:
                msg = f"{enum_parsed} could not be parsed from {base.__name__}."
                raise InvalidEnumerationError(msg) from e

    return enum_parsed
