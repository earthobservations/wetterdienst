# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An image timeout in an MCP format test is rerun like the REST image tests, and nothing else is (GH-4367).

The server answers an image that Kaleido did not draw in time with a 504 of the kind `image-timeout`, which an MCP tool
reports as the text of an error result. `tests/ui/mcp_image_timeout.py` turns exactly that into `ImageTimeoutError`,
the exception `--only-rerun ImageTimeoutError` (GH-3918) names, so that a loaded runner does not fail a landing.

Offline: the renderer is stood in for, as the readers are in `test_mcp_formats.py`.
"""

from __future__ import annotations

import logging
import os
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

pytest.importorskip("fastmcp")

from mcp_types import EmbeddedResource, ImageContent, TextContent

from tests.test_rerun_rate_limit import _only_rerun, _rerun_except
from tests.ui.mcp_image_timeout import _the_error_text_of_an_image_timeout, raise_if_image_timeout
from tests.ui.test_mcp_formats import _call, _stub_stream, _values_result_of_shape
from tests.ui.test_operations import _VALUES, _no_ambient_settings  # noqa: F401
from wetterdienst.exceptions import ImageTimeoutError
from wetterdienst.model import result as result_module
from wetterdienst.ui import restapi

if TYPE_CHECKING:
    from _pytest.pytester import Pytester

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

#: the text of the error of the tool `values`, as the server's own 504 for an image comes through it
_IMAGE_TIMEOUT_TEXT = (
    "Error calling tool 'values': HTTP error 504: Gateway Timeout - "
    "The image was not rendered in time. The request was valid; try again later."
)


def _error(*texts: str) -> Any:  # noqa: ANN401
    """Give what a tool's error result reads like: `is_error` and text blocks."""
    return SimpleNamespace(is_error=True, content=[TextContent(type="text", text=text) for text in texts])


def _timing_out(_figure: object, _fmt: str, **_kwargs: object) -> bytes:
    raise ImageTimeoutError(1.0)


def test_a_tool_whose_image_was_not_rendered_in_time_raises_the_error_the_suite_reruns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real tool, with a renderer that times out: its 504 text is what the helper matches, and nothing looser."""
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])
    monkeypatch.setattr(result_module, "render_image", _timing_out)

    with pytest.raises(ImageTimeoutError) as raised:
        _call(restapi.app, "values", {**_VALUES, "format": "png"})

    assert any("image-timeout 504" in note and "`values`" in note for note in raised.value.__notes__)


def test_the_text_the_helper_matches_is_the_one_the_server_writes() -> None:
    """The text of the constant above is a tool's error for the server's detail, so a change of it fails here."""
    with pytest.raises(ImageTimeoutError):
        raise_if_image_timeout(_error(_IMAGE_TIMEOUT_TEXT))


@pytest.mark.parametrize(
    "texts",
    [
        # a 504 of a provider that did not answer, which is not the renderer's
        ("Error calling tool 'values': HTTP error 504: Gateway Timeout - The provider did not answer in time.",),
        # the detail alone, with no status, and the status alone, with another detail
        ("The image was not rendered in time. The request was valid; try again later.",),
        ("Error calling tool 'values': HTTP error 504: Gateway Timeout",),
        # a defect that names the same words somewhere in a longer text
        (f"{_IMAGE_TIMEOUT_TEXT} And a traceback of the server.",),
        (f"Defect. {_IMAGE_TIMEOUT_TEXT}",),
        # other statuses
        ("Error calling tool 'values': HTTP error 400: Bad Request - nope",),
        ("Error calling tool 'values': HTTP error 500: Internal Server Error - The server failed (ValueError).",),
        ("Error calling tool 'values': HTTP error 502: Bad Gateway - The image was not rendered in time.",),
        (),
    ],
    ids=["upstream-504", "detail-only", "status-only", "suffix", "prefix", "400", "500", "502", "no-text"],
)
def test_any_other_error_is_left_to_the_test_to_fail_on(texts: tuple[str, ...]) -> None:
    """Only the one text of the image-timeout 504 is the renderer's; every other error stays a result to assert on."""
    raise_if_image_timeout(_error(*texts))


def test_a_success_and_a_block_that_is_no_text_are_left_alone() -> None:
    """A result without an error is returned, whatever its blocks, and an error with an image block is not matched."""
    image = ImageContent(type="image", data="AAAA", mimeType="image/png")
    resource = EmbeddedResource(
        type="resource", resource={"uri": "file:///x.pdf", "mimeType": "application/pdf", "blob": "AAAA"}
    )
    raise_if_image_timeout(
        SimpleNamespace(is_error=False, content=[TextContent(type="text", text=_IMAGE_TIMEOUT_TEXT)])
    )
    raise_if_image_timeout(SimpleNamespace(is_error=True, content=[image, resource]))


def test_a_real_tool_error_that_is_no_image_timeout_is_still_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refusal of the request, through the real server, comes back as an error result and is not raised."""
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])

    result, _ = _call(restapi.app, "values", {**_VALUES, "format": "png", "width": 100_000})

    assert result.is_error
    assert "HTTP error 400" in result.content[0].text


def test_the_helper_writes_nothing_to_the_log_of_a_test_that_failed_for_another_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The server logs a warning of an image timeout where it writes the detail: not one for a 400 that is read here."""
    _the_error_text_of_an_image_timeout.cache_clear()  # the pattern is built in this test, where the log is read
    with caplog.at_level(logging.DEBUG):
        raise_if_image_timeout(_error("Error calling tool 'values': HTTP error 400: Bad Request - nope"))
        with pytest.raises(ImageTimeoutError):
            raise_if_image_timeout(_error(_IMAGE_TIMEOUT_TEXT))

    assert caplog.records == []


def test_a_request_that_outlasts_the_servers_timeout_is_no_image_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A render slower than the request's timeout is the 504 of the request, which is not the renderer's, nor rerun.

    This is why `test_mcp_formats.py` gives the server more time than the renderer has: with the timeout of the
    request first, a slow image fails there as it is, and the matcher is not widened to take it.
    """
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")

    def slow(_figure: object, _fmt: str, **_kwargs: object) -> bytes:
        time.sleep(1.5)
        return b"\x89PNG\r\n\x1a\n"

    monkeypatch.setattr(result_module, "render_image", slow)

    result, _ = _call(restapi.app, "values", {**_VALUES, "format": "png"})

    assert result.is_error
    assert "HTTP error 504" in result.content[0].text
    assert "image was not rendered" not in result.content[0].text


_INNER = """
import pytest
from pathlib import Path

from tests.ui.test_mcp_formats import _call, _stub_stream, _values_result_of_shape
from tests.ui.test_operations import _VALUES, _no_ambient_settings  # noqa: F401
from wetterdienst.exceptions import ImageTimeoutError
from wetterdienst.model import result as result_module
from wetterdienst.ui import restapi



def _renders(times_out):
    # one file for each parameter, which a rerun of the test finds again: the count is what carries over
    COUNT = Path(__file__).parent / f"renders_{times_out}.count"

    def render(figure, fmt, **kwargs):
        COUNT.write_text(COUNT.read_text() + "x" if COUNT.exists() else "x")
        if len(COUNT.read_text()) <= times_out:
            raise ImageTimeoutError(1.0)
        return b"\\x89PNG\\r\\n\\x1a\\n"

    return render


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("times_out", [1, 3])
def test_png_of_a_tool(times_out, monkeypatch):
    _stub_stream(monkeypatch, [_values_result_of_shape("long")])
    monkeypatch.setattr(result_module, "render_image", _renders(times_out))
    result, _ = _call(restapi.app, "values", {**_VALUES, "format": "png"})
    assert not result.is_error, result.content
"""


def test_an_image_that_times_out_once_in_a_tool_is_rerun_and_passes(
    pytester: Pytester, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run of the suite's own options: a render that is late once is the second attempt, one that never is fails.

    The inner run is a process of its own with the `addopts` of this one (`--only-rerun`, `--rerun-except`), so that
    what is held is the configuration of the suite and not a copy of it, as in `test_rerun_rate_limit.py`.
    """
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(filter(None, [str(request.config.rootpath), existing])))
    pytester.makeconftest("pytest_plugins = ['tests.conftest']\n")
    pytester.makepyfile(test_inner=_INNER)

    result = pytester.runpytest_subprocess(
        "-p",
        "no:randomly",
        "-p",
        "no:cacheprovider",
        "--reruns",
        "2",
        "--reruns-delay",
        "0",
        *_only_rerun(request),
        *_rerun_except(request),
    )

    # `times_out=1` passes on its second attempt; `times_out=3` meets the timeout in the run and in both reruns
    result.assert_outcomes(passed=1, failed=1)
    assert result.parseoutcomes()["rerun"] == 3
    result.stdout.fnmatch_lines(["*ImageTimeoutError*"])
    assert "AssertionError" not in result.stdout.str()
