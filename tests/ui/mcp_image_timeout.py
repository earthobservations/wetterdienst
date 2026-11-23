# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An image timeout that reaches a test as the error of an MCP tool is an `ImageTimeoutError` again (GH-4367).

Kaleido draws an image in a Chrome, which on a loaded runner is not always done in the time the server gives it. The
REST API answers that with a 504 of the kind `image-timeout`, and a test that meets the `ImageTimeoutError` itself is
rerun (`--only-rerun ImageTimeoutError`, GH-3918). Through an MCP tool the 504 is no exception but the text of an
error result ("Error calling tool 'stations': HTTP error 504: Gateway Timeout - <detail>"), which an assertion on the
result reports as an `AssertionError`, and that is not rerun.

`raise_if_image_timeout` makes the one error that is the renderer's, and the same request can succeed on a retry, the
exception the rerun rule names. It reads the 504 with the detail the server writes for it, not "504" or "timeout"
alone: any other error, a 504 of an upstream provider included, is a result that a test asserts on and fails with.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from wetterdienst.exceptions import ImageTimeoutError

if TYPE_CHECKING:
    from collections.abc import Iterable


def _the_error_text_of_an_image_timeout() -> re.Pattern[str]:
    """Give the text a tool's error has for the `image-timeout` 504: its status line and the detail REST sends."""
    from wetterdienst.ui import restapi  # noqa: PLC0415 -- the app is only there where the tests of it are

    detail = restapi._image_timeout(ImageTimeoutError(None), "draw the image").detail  # noqa: SLF001
    return re.compile(rf"Error calling tool '(?P<tool>[^']+)': HTTP error 504: Gateway Timeout - {re.escape(detail)}")


def raise_if_image_timeout(result: Any) -> None:  # noqa: ANN401 -- a `ToolResult` of fastmcp, or what reads like one
    """Raise `ImageTimeoutError` if `result` is the error of a tool whose image was not rendered in time; else return.

    A success, and every other error, is left to the caller.
    """
    if not result.is_error:
        return
    pattern = _the_error_text_of_an_image_timeout()
    texts: Iterable[str] = (block.text for block in result.content if isinstance(getattr(block, "text", None), str))
    for text in texts:
        if found := pattern.fullmatch(text):
            error = ImageTimeoutError(None)
            error.add_note(f"the tool `{found['tool']}` answered the server's image-timeout 504: {text}")
            raise error
