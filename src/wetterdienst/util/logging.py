# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Logging utilities for the wetterdienst package."""

import io
import logging
import re

#: What forges a line of a log or moves a terminal: the C0 and C1 control characters (a newline, a carriage return, an
#: escape) and the two separators that Unicode counts as line breaks. A tab is one of them: it only shifts a column,
#: but a value that a caller sent has no use for it in a log line.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")


def escape_control_characters(text: str) -> str:
    r"""Write the control characters of a text as the escape sequences they stand for, so that it stays on one line.

    For text that a caller sent and a log line repeats -- a refused value, the path of a request -- which could
    otherwise end the line and start another that reads as the server's own (CWE-117). A newline becomes the two
    characters ``\n``. Everything else, a backslash included, is left as it is.
    """
    return _CONTROL_CHARACTERS.sub(lambda match: match.group().encode("unicode_escape").decode("ascii"), text)


class _EscapeControlCharacters(logging.Filter):
    """Escape the control characters of every record of the logger it is added to (see `escape_control_characters`)."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Replace the message of the record by its escaped, formatted text. A traceback is not part of it."""
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 -- a message that does not format is logging's to report, not this filter's
            return True
        record.msg = escape_control_characters(message)
        record.args = None
        return True


def get_one_line_logger(name: str) -> logging.Logger:
    """Give the logger of a module that repeats what a caller sent, which keeps each message on one line.

    A filter on the logger rather than an escape at each call: a line added later that repeats a request is
    held to the same rule without anyone having to remember it. It covers the message, not the traceback that
    ``exc_info`` appends, which has lines of its own by nature.
    """
    logger = logging.getLogger(name)
    if not any(isinstance(item, _EscapeControlCharacters) for item in logger.filters):
        logger.addFilter(_EscapeControlCharacters())
    return logger


class TqdmToLogger(io.StringIO):
    """Output stream for TQDM which will output to logger module instead of the StdOut.

    Source: https://stackoverflow.com/questions/14897756/python-progress-bar-through-logging-module
    """

    logger: logging.Logger
    level: int
    buf: str = ""

    def __init__(self, logger: logging.Logger, level: int | None = None) -> None:
        """Initialize the TqdmToLogger.

        Args:
            logger: Logger instance.
            level: Log level.

        """
        super().__init__()
        self.logger = logger
        self.level = level or logging.INFO

    def write(self, buf: str) -> int:
        """Overwrite write method."""
        self.buf = buf.strip("\r\n\t ")
        return len(buf)

    def flush(self) -> None:
        """Overwrite flush method."""
        self.logger.log(self.level, self.buf)
