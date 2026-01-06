# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Logging utilities for the wetterdienst package."""

import io
import logging


class TqdmToLogger(io.StringIO):
    """Output stream for TQDM which will output to logger module instead of the StdOut.

    Source: https://stackoverflow.com/questions/14897756/python-progress-bar-through-logging-module
    """

    logger = None
    level = None
    buf = ""

    def __init__(self, logger: logging.Logger, level: int | None = None) -> None:
        """Initialize the TqdmToLogger.

        Args:
            logger: Logger instance.
            level: Log level.

        """
        super().__init__()
        self.logger = logger
        self.level = level or logging.INFO

    def write(self, buf: str) -> None:
        """Overwrite write method."""
        self.buf = buf.strip("\r\n\t ")

    def flush(self) -> None:
        """Overwrite flush method."""
        self.logger.log(self.level, self.buf)
