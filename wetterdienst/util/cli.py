# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A set of utility functions."""

from __future__ import annotations

import logging
import sys
import textwrap


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


def docstring_format_verbatim(text: str) -> str:
    """Format docstring to be displayed verbatim as a help text by Click.

    - https://click.palletsprojects.com/en/8.1.x/documentation/#preventing-rewrapping
    - https://github.com/pallets/click/issues/56
    """
    text = textwrap.dedent(text)
    lines = [line if line.strip() else "\b" for line in text.splitlines()]
    return "\n".join(lines)
