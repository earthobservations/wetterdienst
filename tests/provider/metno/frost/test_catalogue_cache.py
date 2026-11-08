# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A 200 of Frost's catalogue that is no listing is not kept in the cache (GH-3847).

`download_file` holds a 200 for the whole expiry, twelve hours for the sources and a week for the series. A page of a
proxy, an answer with no `data`, a list with no row where Frost has thousands: each would be read back for that long, so
the cached copy is dropped before the failure is raised, and the next request asks Frost again. Through the real
download and cache, against a server of this machine.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from tests.provider.metno.frost.catalogue_rows import SERIES, SOURCES
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError
from wetterdienst.provider.metno.frost import MetnoFrostRequest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

HTML = b"<html><body>Service temporarily unavailable</body></html>"
GOOD_SOURCES = json.dumps(SOURCES).encode()
GOOD_SERIES = json.dumps(SERIES).encode()


class Frost:
    """A server that answers the two requests of the catalogue with the bodies set, and counts each."""

    def __init__(self) -> None:
        """Start with the real rows for both."""
        self.bodies = {"sources": GOOD_SOURCES, "series": GOOD_SERIES}
        self.hits = {"sources": 0, "series": 0}


@pytest.fixture
def frost(monkeypatch: pytest.MonkeyPatch) -> Iterator[Frost]:
    """Serve the catalogue from this machine, and point the request at it."""
    state = Frost()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            which = "series" if "availableTimeSeries" in self.path else "sources"
            state.hits[which] += 1
            body = state.bodies[which]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """Say nothing."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setattr(MetnoFrostRequest, "_sources_url", base + "/sources/v0.jsonld?types=SensorSystem&validtime=x")
    monkeypatch.setattr(
        MetnoFrostRequest,
        "_series_url",
        base + "/observations/availableTimeSeries/v0.jsonld?elements={elements}&timeresolutions={time_resolutions}",
    )
    yield state
    server.shutdown()
    server.server_close()


def _catalogue(cache_dir: Path) -> list[str]:
    settings = Settings(cache_dir=cache_dir, auth={"metno_frost": ("stub-client", "stub-secret")})
    request = MetnoFrostRequest(parameters=[("daily", "data")], settings=settings)
    stations = request._all().collect()  # noqa: SLF001
    return stations["station_id"].to_list() if stations.height else []


def test_a_good_catalogue_is_kept(frost: Frost, tmp_path: Path) -> None:
    """Test the control: the answers are read once, and the second catalogue comes from the cache."""
    first = _catalogue(tmp_path)
    second = _catalogue(tmp_path)

    assert first == second == [source["id"] for source in SOURCES["data"]]
    assert frost.hits == {"sources": 1, "series": 1}


@pytest.mark.parametrize(
    ("body", "message"),
    [
        pytest.param(b'{"data": []}', "no time series", id="no-row"),
        pytest.param(b'{"data": [null]}', "no time series", id="null-row"),
        pytest.param(b"{}", "no `data`", id="no-data"),
        pytest.param(HTML, "not a JSON listing", id="html"),
    ],
)
def test_a_series_answer_that_is_no_listing_is_raised_and_not_kept(
    frost: Frost, tmp_path: Path, body: bytes, message: str
) -> None:
    """Test that a bad 200 for the series is a `DownloadError` and is asked again, where it was kept for 12 h."""
    frost.bodies["series"] = body
    with pytest.raises(DownloadError, match=message):
        _catalogue(tmp_path)

    frost.bodies["series"] = GOOD_SERIES

    assert _catalogue(tmp_path) == [source["id"] for source in SOURCES["data"]]
    assert frost.hits["series"] == 2


@pytest.mark.parametrize(
    ("body", "message"),
    [
        pytest.param(b"{}", "no `data`", id="no-data"),
        pytest.param(HTML, "not a JSON listing", id="html"),
    ],
)
def test_a_sources_answer_that_is_no_listing_is_raised_and_not_kept(
    frost: Frost, tmp_path: Path, body: bytes, message: str
) -> None:
    """Test that a bad 200 for the sources is a `DownloadError`, where it was a polars error, and is asked again."""
    frost.bodies["sources"] = body
    with pytest.raises(DownloadError, match=message) as raised:
        _catalogue(tmp_path)

    assert frost.hits["series"] == 0
    assert "sources" in raised.value.url
    frost.bodies["sources"] = GOOD_SOURCES

    assert _catalogue(tmp_path) == [source["id"] for source in SOURCES["data"]]
    assert frost.hits["sources"] == 2


def test_a_list_of_sources_with_no_row_is_no_station_and_is_not_kept(frost: Frost, tmp_path: Path) -> None:
    """Test that `{"data": []}` is the empty catalogue, as before, and Frost is asked again where it was kept 12 h."""
    frost.bodies["sources"] = b'{"data": []}'
    assert _catalogue(tmp_path) == []
    assert frost.hits["series"] == 0

    frost.bodies["sources"] = GOOD_SOURCES

    assert _catalogue(tmp_path) == [source["id"] for source in SOURCES["data"]]
    assert frost.hits["sources"] == 2
