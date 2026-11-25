"""Utility functions for user interface."""

from __future__ import annotations

import unicodedata

#: how long a name of a station or a region is written in a message; the source's own names are short, one beyond this
#: is cut
MAX_SHOWN_LENGTH = 60
#: the Unicode categories of a character replaced in a message: control, format (a bidi override), surrogate,
#: private-use and unassigned characters, and the line and paragraph separators
_BREAKING = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


def shown_text(text: str) -> str:
    """Write a name of the source's or the caller's in a message: breaking characters replaced, a long text cut.

    A newline, an escape or a bidi override would break the line of a log or a terminal or misread in a message, and
    a name of thousands of characters would fill it: each such character becomes U+FFFD and a text beyond
    `MAX_SHOWN_LENGTH` is cut with an ellipsis, so that the message, the log line and the JSON are one text. Light on
    purpose: the command line imports it at start (`tests/ui/cli/test_cli_imports.py`).
    """
    clean = "".join("\ufffd" if unicodedata.category(char) in _BREAKING else char for char in text)
    return clean if len(clean) <= MAX_SHOWN_LENGTH else f"{clean[: MAX_SHOWN_LENGTH - 1]}\u2026"


def read_list(data: str | None, separator: str = ",") -> list[str]:
    """Read a list from a string."""
    if data is None:
        return []

    result = [x.strip() for x in data.split(separator)]

    if len(result) == 1 and not result[0]:
        return []

    return result
