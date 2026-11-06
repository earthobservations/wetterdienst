# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A set of utility functions."""

from __future__ import annotations

import logging
import os
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Set up the logging for the wetterdienst package.

    Args:
        level: Log level.

    Returns:
        None

    """
    log_format = "%(asctime)-15s [%(name)-40s] %(levelname)-7s: %(message)s"
    logging.basicConfig(format=log_format, stream=sys.stderr, level=level)

    # Silence INFO messages from numexpr.
    numexpr_logger = logging.getLogger("numexpr")
    numexpr_logger.setLevel(logging.WARNING)


def no_color() -> bool:
    """Tell whether the environment asks for no colour: `NO_COLOR` is set to anything but the empty string.

    That is the whole of https://no-color.org: any value counts, `0` and `false` too, and an empty one does not.
    """
    return bool(os.environ.get("NO_COLOR"))
