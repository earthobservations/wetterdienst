# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The snippets of `docs/usage/large-requests.md` that ask a server are run against the app, offline (GH-3458).

`test_docs_samples.py` runs the Python of a page but cannot run what asks a server on `localhost:7890`. This module
starts the REST app on a free port of this machine, with the readings of a few stations served by a stub in place of
the download, a limit of 300 rows and 3 stations, and runs the code of the page itself, read out of the markdown, so
that the page and the test cannot drift: the NDJSON reader, the polars read of the CSV, the loop over windows and the
loop over batches of stations. Only the dates of the long window are replaced (twenty years of 10-minute readings is
thousands of calls with a limit of 300 rows).

The stub: the stations of the daily climate summary are eight, near Dresden, with a record from 1990; the 10-minute
air temperature is one of them (01048), whose record begins on 3 January 2020, so that the first window of a loop that
begins on the 1st is a window with no readings, which the server answers with a 200 and an empty `values`.
"""

from __future__ import annotations

import datetime as dt
import http.server
import re
import socket
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.request import urlopen

import polars as pl
import pytest
import uvicorn

from tests.test_docs_samples import DOCS, Sample, _samples
from wetterdienst.model.metadata import DatasetModel
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui import restapi

if TYPE_CHECKING:
    from collections.abc import Iterator

PAGE = DOCS / "usage" / "large-requests.md"
#: the stations of the stub: the first eight ids, from the position of Dresden outwards
IDS = ["01048", "04411", "01050", "01051", "01052", "01053", "01054", "01055"]
RECORD_END = dt.datetime(2026, 10, 24, tzinfo=dt.UTC)
#: the record of the 10-minute air temperature of 01048, which begins two days into the window of the loops
TEN_MINUTES_START = dt.datetime(2020, 1, 3, tzinfo=dt.UTC)
STEP = {"10_minutes": "10m", "daily": "1d"}


def _stations_frame(self: DwdObservationRequest) -> pl.LazyFrame:
    """Serve the stations of the datasets the request names, as the provider hands them to the core."""
    rows = []
    datasets = {(p.dataset.resolution.name, p.dataset.name) for p in self.parameters}  # ty: ignore[unresolved-attribute]
    for resolution, dataset in sorted(datasets):
        for number, station_id in enumerate(IDS):
            if resolution == "10_minutes" and station_id != "01048":
                continue
            start = TEN_MINUTES_START if resolution == "10_minutes" else dt.datetime(1990, 1, 1, tzinfo=dt.UTC)
            rows.append(
                {
                    "resolution": resolution,
                    "dataset": dataset,
                    "station_id": station_id,
                    "start_timestamp": start,
                    "end_timestamp": RECORD_END,
                    "latitude": 51.13 + 0.05 * number,
                    "longitude": 13.75 + 0.05 * number,
                    "elevation": 228.0,
                    "name": f"Station {station_id}",
                    "region": "Sachsen",
                }
            )
    schema = {
        "resolution": pl.String,
        "dataset": pl.String,
        "station_id": pl.String,
        "start_timestamp": pl.Datetime("us", "UTC"),
        "end_timestamp": pl.Datetime("us", "UTC"),
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "elevation": pl.Float64,
        "name": pl.String,
        "region": pl.String,
    }
    return pl.DataFrame(rows, schema=schema).lazy()


def _readings(self: DwdObservationValues, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
    """Serve the readings of the window of the request, as the source has them: one for each step of the resolution.

    DWD's datasets are collected whole, so the readings are those of every requested parameter of the dataset.
    """
    dataset = parameter_or_dataset if isinstance(parameter_or_dataset, DatasetModel) else parameter_or_dataset.dataset
    names = [
        parameter.name_original
        for parameter in self.sr.request.parameters  # ty: ignore[unresolved-attribute]
        if (parameter.dataset.resolution.name, parameter.dataset.name) == (dataset.resolution.name, dataset.name)
    ]
    start = max(self.sr.start, TEN_MINUTES_START) if dataset.resolution.name == "10_minutes" else self.sr.start
    timestamps = pl.datetime_range(start, self.sr.end, STEP[dataset.resolution.name], time_zone="UTC", eager=True)
    return pl.concat(
        pl.DataFrame(
            {
                "parameter": [name] * len(timestamps),
                "timestamp": timestamps,
                "value": [float(i % 10) for i in range(len(timestamps))],
                "quality_flags": ["10"] * len(timestamps),
            },
            schema={
                "parameter": pl.String,
                "timestamp": pl.Datetime("us", "UTC"),
                "value": pl.Float64,
                "quality_flags": pl.String,
            },
        )
        for name in names
    )


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    """Run the app on a free port, limited to 300 rows and 3 stations, and give its address."""
    import os  # noqa: PLC0415

    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.setenv("WD_RESTAPI_MAX_ROWS", "300")
    monkeypatch.setenv("WD_RESTAPI_MAX_STATIONS", "3")
    # the snippets use urllib, which would send a local address through a proxy of the environment
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setattr(DwdObservationRequest, "_all", _stations_frame)
    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", _readings)
    monkeypatch.chdir(tmp_path)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    app = uvicorn.Server(uvicorn.Config(restapi.app, log_level="warning"))
    thread = threading.Thread(target=app.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    while not app.started:
        thread.join(0.05)
    try:
        yield f"127.0.0.1:{port}"
    finally:
        app.should_exit = True
        thread.join(10)
        sock.close()


def _block(marker: str, *, kind: str = "python") -> Sample:
    found = [sample for sample in _samples(PAGE) if sample.kind == kind and marker in sample.code]
    assert len(found) == 1, f"{marker!r} is in {len(found)} blocks of the page, not one"
    return found[0]


def _run(sample: Sample, address: str, namespace: dict[str, Any], *, replace: dict[str, str] | None = None) -> None:
    code = sample.code.replace("localhost:7890", address)
    for old, new in (replace or {}).items():
        assert old in code, f"the page no longer has {old!r}"
        code = code.replace(old, new)
    exec(compile(code, sample.where, "exec"), namespace)  # noqa: S102


def test_the_ndjson_reader_of_the_page_reads_a_stream_longer_than_the_limit(server: str) -> None:
    """A stream is held to the limit of streams, not of one body: 732 rows with a limit of 300 are read, to the end."""
    namespace: dict[str, Any] = {}
    _run(_block('"format": "ndjson"'), server, namespace)

    assert namespace["end"]["counts"] == {"stations": 2, "rows": 732}
    lines = Path("rows.ndjson").read_text(encoding="utf8").splitlines()
    assert len(lines) == 732
    assert '"metadata"' not in "".join(lines)


def test_the_polars_read_of_the_csv_of_the_page_keeps_the_station_id_a_string(server: str) -> None:
    """The curl line of the page is made against the app, and the file it saves is read as the page reads it."""
    curl = _block("curl --fail-with-body", kind="shell")
    url = re.search(r'"(http[^"]+)"', curl.code)[1].replace("localhost:7890", server)  # ty: ignore[not-subscriptable]
    with urlopen(url) as response:  # noqa: S310
        Path("dresden.csv").write_bytes(response.read())

    namespace: dict[str, Any] = {}
    _run(_block("# needs the dresden.csv"), server, namespace)

    assert namespace["lazy"].collect_schema()["station_id"] == pl.String
    assert namespace["lazy"].collect_schema()["timestamp"] == pl.Datetime("us", "UTC")
    assert namespace["lazy"].select(pl.len()).collect().item() == 366


def test_the_window_loop_of_the_page_skips_a_window_without_readings(server: str) -> None:
    """The first window of 7 days is before the record: a 200 with no values, which writes no file and does not stop."""
    namespace: dict[str, Any] = {}
    window = {"dt.date(2000, 1, 1), dt.date(2019, 12, 31)": "dt.date(2020, 1, 1), dt.date(2020, 1, 7)"}
    _run(_block("def windows"), server, namespace, replace=window)

    # 300 rows of 144 a day are two days a call: the 1st-2nd is empty, then three windows of readings
    assert namespace["limits"]["max_rows"] == 300
    assert sorted(path.name for path in Path().glob("slice-*.parquet")) == [
        "slice-2020-01-03.parquet",
        "slice-2020-01-05.parquet",
        "slice-2020-01-07.parquet",
    ]
    df = namespace["df"]
    assert df.height == 5 * 144
    assert df.schema["timestamp"] == pl.Datetime("us", "UTC")


def test_the_window_loop_of_the_page_gives_an_empty_frame_when_every_window_is_empty(server: str) -> None:
    """Nothing in any window is no file and no `pl.concat([])`."""
    namespace: dict[str, Any] = {}
    window = {"dt.date(2000, 1, 1), dt.date(2019, 12, 31)": "dt.date(2019, 1, 1), dt.date(2019, 1, 6)"}
    _run(_block("def windows"), server, namespace, replace=window)

    assert not list(Path().glob("slice-*.parquet"))
    assert namespace["df"].is_empty()


def test_the_window_loop_of_the_page_resumes_from_the_files_of_an_earlier_run(server: str) -> None:
    """A window already on disk is not asked for again."""
    namespace: dict[str, Any] = {}
    window = {"dt.date(2000, 1, 1), dt.date(2019, 12, 31)": "dt.date(2020, 1, 1), dt.date(2020, 1, 7)"}
    _run(_block("def windows"), server, namespace, replace=window)
    before = {path.name: path.stat().st_mtime_ns for path in Path().glob("slice-*.parquet")}
    Path("slice-2020-01-05.parquet").unlink()

    _run(_block("def windows"), server, namespace, replace=window)

    after = {path.name: path.stat().st_mtime_ns for path in Path().glob("slice-*.parquet")}
    assert after.keys() == before.keys()
    assert after["slice-2020-01-03.parquet"] == before["slice-2020-01-03.parquet"]
    assert namespace["df"].height == 5 * 144


def test_the_batch_loop_of_the_page_reads_every_station_in_batches_that_fit_both_limits(server: str) -> None:
    """Eight stations are batches of 3, 3 and 2, each cut into windows of 100 days: a leap year of each, all in."""
    namespace: dict[str, Any] = {}
    window = {"dt.date(2000, 1, 1), dt.date(2019, 12, 31)": "dt.date(2020, 1, 1), dt.date(2020, 1, 7)"}
    _run(_block("def windows"), server, namespace, replace=window)
    _run(_block('rank="250"'), server, namespace)

    assert set(namespace["ids"]) == set(IDS)
    df = namespace["df"]
    assert df.get_column("station_id").n_unique() == len(IDS)
    assert df.height == len(IDS) * 366
    assert df.group_by("station_id").len().get_column("len").unique().to_list() == [366]


class _Flaky(http.server.BaseHTTPRequestHandler):
    """Answer 502 and 503 with `Retry-After: 0` twice, then 200 with a body; a 400 with its problem."""

    calls = 0

    def do_GET(self) -> None:
        type(self).calls += 1
        if self.path.startswith("/api/bad"):
            status, body = 400, b'{"detail": "narrow it"}'
        elif type(self).calls <= 2:
            status, body = (502, 503)[type(self).calls - 1], b"{}"
        else:
            status, body = 200, b'{"ok": true}'
        self.send_response(status)
        self.send_header("Retry-After", "0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Keep the test output clean."""


def test_get_of_the_page_asks_again_after_a_502_and_says_what_a_400_says(server: str) -> None:
    """A 502 and a 503 with `Retry-After` are asked again; a 400 is raised with its `detail`."""
    namespace: dict[str, Any] = {}
    window = {"dt.date(2000, 1, 1), dt.date(2019, 12, 31)": "dt.date(2020, 1, 1), dt.date(2020, 1, 1)"}
    _run(_block("def windows"), server, namespace, replace=window)

    flaky = http.server.HTTPServer(("127.0.0.1", 0), _Flaky)
    thread = threading.Thread(target=flaky.serve_forever, daemon=True)
    thread.start()
    try:
        namespace["BASE"] = f"http://127.0.0.1:{flaky.server_port}/api"
        assert namespace["get"]("anything") == {"ok": True}
        assert _Flaky.calls == 3
        with pytest.raises(RuntimeError, match="narrow it"):
            namespace["get"]("bad")
    finally:
        flaky.shutdown()
        thread.join(10)
