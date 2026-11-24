# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The columns of a streamed wide CSV are the parameters asked for, whatever the first station has (GH-4432).

A streamed CSV is written station by station, and its header is written with the first station. The wide frame of a
station has a column for each parameter that station delivers, so a column that only a later station had was dropped
from the CSV without a word. The header is now the columns of the request, in its order, known before the first
station is read. Every other answer (the JSON, the NDJSON lines, the MCP tool, the command line, the frames of Python)
is as it was: a wide frame has the columns of what was delivered, so a plain CSV and the streamed one differ by the
columns with no value at all in the answer, and by nothing else.

Served as `test_surface_parity.py` serves it: a small DWD network whose index and files are stubs. Of the three
stations, `00001` lacks the maximum and `00003` lacks the minimum of the air temperature.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.ui.test_mcp_formats import _call
from tests.ui.test_surface_parity import (  # noqa: F401
    _no_ambient_settings,
    _serve_dwd,
)
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.streaming import csv_stream

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

MIN = "temperature_air_min_2m"
MAX = "temperature_air_max_2m"
BOTH = f"daily/kl/{MIN},daily/kl/{MAX}"
STATIONS = "00001,00002,00003"
LACKING = {"00001": {MAX}, "00003": {MIN}}
WIDE = {"shape": "wide"}
IDENTITY = ["station_id", "resolution", "dataset", "timestamp"]
FLAGS = "_quality_flags"
STREAM_LOG = "wetterdienst.ui.streaming"


@pytest.fixture(autouse=True)
def _stations_that_lack_parameters(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Have the source hand over none of the parameters a station lacks, and nothing for an empty station."""
    request.getfixturevalue("_serve_dwd")
    original = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001
    empty = set(getattr(request, "param", ()))

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401
        df = original(self, station_id, parameter_or_dataset)
        if station_id in empty:
            return df.clear()
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        lacking = {parameter.name_original for parameter in dataset if parameter.name in LACKING.get(station_id, ())}
        return df.filter(~pl.col("parameter").is_in(lacking))

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _query(parameters: str = BOTH, **options: str) -> dict[str, str]:
    return {
        "provider": "dwd",
        "network": "observation",
        "parameters": parameters,
        "stations": STATIONS,
        "timestamp": "2020-05",
        **options,
    }


def _rest(fmt: str, **kwargs: str) -> str:
    response = TestClient(restapi.app, raise_server_exceptions=False).get(
        "/api/v1/values", params={**_query(**kwargs), "format": fmt}
    )
    assert response.status_code == 200, response.text
    return response.text


def _library_csv(parameters: str = BOTH) -> str:
    """Write the CSV of the whole result: what `to_csv` writes, which the command line writes as well."""
    request = DwdObservationRequest(
        parameters=parameters.split(","), start="2020-05-01", end="2020-05-31 23:59:59", options={"shape": "wide"}
    )
    return request.filter_by_station_id(STATIONS.split(",")).values().all().to_csv()


def _cli_args(parameters: str = BOTH, **options: str) -> list[str]:
    flags = [f"--{name.replace('_', '-')}={value}" for name, value in options.items()]
    return [
        "values",
        "--provider=dwd",
        "--network=observation",
        f"--parameters={parameters}",
        f"--stations={STATIONS}",
        "--timestamp=2020-05",
        *flags,
    ]


def _cli_csv(parameters: str = BOTH, **options: str) -> str:
    result = CliRunner().invoke(cli, [*_cli_args(parameters, **options), "--format=csv"])
    assert result.exit_code == 0, result.output
    # the command ends what it prints with a newline of its own
    return result.stdout.removesuffix("\n")


def _tool_csv(**kwargs: str) -> str:
    result, _ = _call(restapi.app, "values", {**_query(**kwargs), "format": "csv"})
    assert not result.is_error, result.content
    return result.content[0].text


def _header(csv: str) -> list[str]:
    return csv.splitlines()[0].split(",")


def _table(csv: str) -> pl.DataFrame:
    """Read a CSV as text, so that nothing is guessed."""
    return pl.read_csv(csv.encode(), infer_schema=False)


def _without_empty_columns(csv: str) -> pl.DataFrame:
    """Read a CSV and leave out the columns that have no value in any row."""
    frame = _table(csv)
    return frame.select([column for column in frame.columns if frame[column].null_count() < frame.height])


def test_a_streamed_wide_csv_has_the_column_only_a_later_station_has() -> None:
    """The first station has no maximum; its CSV had no column for it and the values of the others were lost."""
    csv = _rest("csv", **WIDE)

    assert MAX in _header(csv)
    frame = _table(csv)
    assert frame.filter(pl.col("station_id") == "00001")[MAX].null_count() == 3
    assert frame.filter(pl.col("station_id") == "00002")[MAX].null_count() == 0
    assert frame.filter(pl.col("station_id") == "00003")[MAX].null_count() == 0
    assert frame.filter(pl.col("station_id") == "00003")[MIN].null_count() == 3


@pytest.mark.parametrize(
    "options",
    [
        WIDE,
        {"shape": "wide", "humanize": "false"},
        {"shape": "wide", "convert_units": "false"},
        {"shape": "wide", "unit_targets": '{"temperature": "degree_fahrenheit"}'},
    ],
    ids=["wide", "wide-not-humanized", "wide-units-kept", "wide-converted"],
)
def test_the_streamed_wide_csv_is_the_plain_one_but_for_the_empty_columns(options: dict[str, str]) -> None:
    """The command line, an MCP tool (one body) and `to_csv` write one CSV; the stream's is it, columns and rows."""
    streamed = _without_empty_columns(_rest("csv", **options))

    assert streamed.height == 9
    assert streamed.equals(_without_empty_columns(_cli_csv(**options)))
    assert streamed.equals(_without_empty_columns(_tool_csv(**options)))
    if options == WIDE:
        assert streamed.equals(_without_empty_columns(_library_csv()))


@pytest.mark.parametrize(
    "options", [{"shape": "long"}, {"shape": "long", "humanize": "false"}], ids=["long", "long-raw"]
)
def test_the_streamed_long_csv_is_the_plain_one(options: dict[str, str]) -> None:
    """The long shape has fixed columns: the text is the same."""
    assert _rest("csv", **options) == _cli_csv(**options) == _tool_csv(**options)


def test_a_parameter_no_station_has_is_an_empty_column_of_the_stream_and_none_of_the_plain_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The header is known before the first station is read; the plain answer has the columns of what was delivered."""
    for station in ("00001", "00002", "00003"):
        monkeypatch.setitem(LACKING, station, {MAX})

    streamed, plain = _table(_rest("csv", **WIDE)), _table(_cli_csv(**WIDE))

    assert streamed.columns == [*plain.columns, MAX, f"{MAX}{FLAGS}"]
    assert streamed[MAX].null_count() == streamed.height
    assert streamed.select(plain.columns).equals(plain)


def test_the_columns_are_those_of_the_request_in_its_order() -> None:
    """The header is the request's, the first station's included: the maximum is listed first when it is."""
    forward, backward = _rest("csv", **WIDE), _rest("csv", parameters=f"daily/kl/{MAX},daily/kl/{MIN}", **WIDE)

    assert _header(forward) == [*IDENTITY, MIN, f"{MIN}{FLAGS}", MAX, f"{MAX}{FLAGS}"]
    assert _header(backward) == [*IDENTITY, MAX, f"{MAX}{FLAGS}", MIN, f"{MIN}{FLAGS}"]
    # the same values, whichever the order
    assert _table(backward).select(_header(forward)).equals(_table(forward))


def test_a_dataset_is_every_parameter_of_it_in_the_stream() -> None:
    """A request for a dataset names its parameters, so the header is the dataset's whatever the stations have."""
    streamed = _rest("csv", parameters="daily/kl", **WIDE)

    request = DwdObservationRequest(parameters=["daily/kl"])
    assert [name for name in _header(streamed) if name.endswith(FLAGS)] == [
        f"{parameter.name}{FLAGS}" for parameter in request.parameters
    ]
    # the plain answer has the columns in the order the stations bring them, where the first lacks the maximum
    plain = _without_empty_columns(_cli_csv(parameters="daily/kl", **WIDE))
    assert _without_empty_columns(streamed).select(plain.columns).equals(plain)
    assert set(_without_empty_columns(streamed).columns) == set(plain.columns)


@pytest.mark.parametrize("_stations_that_lack_parameters", [("00001",)], indirect=True)
def test_an_empty_first_station_leaves_the_header_to_the_next(_stations_that_lack_parameters: None) -> None:
    """A station without rows is not sent; the header is the same."""
    streamed = _rest("csv", **WIDE)

    assert _header(streamed) == [*IDENTITY, MIN, f"{MIN}{FLAGS}", MAX, f"{MAX}{FLAGS}"]
    assert _without_empty_columns(streamed).equals(_without_empty_columns(_cli_csv(**WIDE)))
    assert set(_table(streamed)["station_id"]) == {"00002", "00003"}


def test_the_plain_answers_are_as_they_were() -> None:
    """The frame of a station has no column of a parameter it lacks, and the JSON and NDJSON rows follow it."""
    request = DwdObservationRequest(
        parameters=BOTH.split(","), start="2020-05-01", end="2020-05-31 23:59:59", options={"shape": "wide"}
    )
    first = request.filter_by_station_id(["00001"]).values().all().df
    assert MAX not in first.columns
    assert f"{MAX}{FLAGS}" not in first.columns

    plain = TestClient(restapi.app).get("/api/v1/values", params={**_query(shape="wide"), "format": "json"}).json()
    lines = [json.loads(line) for line in _rest("ndjson", shape="wide").splitlines()][1:-1]
    first_rows = [row for row in lines if row["station_id"] == "00001"]
    assert first_rows
    assert all(MAX not in row for row in first_rows)
    # a row of the JSON answer has what the stream's has, and null for the rest
    for streamed, row in zip(lines, plain["values"], strict=True):
        assert {key: value for key, value in row.items() if key in streamed} == streamed
        assert all(value is None for key, value in row.items() if key not in streamed)


def test_the_ndjson_rows_of_the_long_shape_are_the_rows_of_the_json_answer() -> None:
    """No change for the long shape."""
    rows = [json.loads(line) for line in _rest("ndjson", shape="long").splitlines()][1:-1]
    plain = TestClient(restapi.app).get("/api/v1/values", params={**_query(shape="long"), "format": "json"}).json()

    assert rows == plain["values"]


def test_a_wide_csv_written_to_a_target_is_the_plain_csv(tmp_path: Path) -> None:
    """`--format csv --target`: the command line writes the file the plain answer is, the union of the stations'."""
    target = tmp_path / "values.csv"
    result = CliRunner().invoke(cli, [*_cli_args(shape="wide"), f"--target=file://{target}"])

    assert result.exit_code == 0, result.output
    assert _without_empty_columns(target.read_text()).equals(_without_empty_columns(_rest("csv", **WIDE)))


@pytest.mark.parametrize("humanize", [True, False])
def test_the_columns_of_the_header_are_the_ones_a_station_that_has_every_parameter_has(*, humanize: bool) -> None:
    """`wide_schema` names the columns as `_widen_df` does, the humanised ones or the source's."""
    request = DwdObservationRequest(parameters=BOTH.split(","), options={"shape": "wide", "humanize": humanize})
    reader = request.filter_by_station_id(["00002"]).values()

    assert list(reader.wide_schema()) == reader.all().df.columns


def _frames(*frames: pl.DataFrame) -> Iterator[pl.DataFrame]:
    yield from frames


def _write(frames: Iterator[pl.DataFrame], schema: pl.Schema | None = None) -> str:
    def to_csv(df: pl.DataFrame, *, header: bool) -> str:
        return df.write_csv(include_header=header)

    return b"".join(csv_stream(frames, to_csv, pl.DataFrame, lambda _e: None, schema)).decode()


def test_a_stream_given_its_columns_writes_them_for_a_frame_that_lacks_some() -> None:
    """The first frame lacks `b`: the header has it and the row has it empty."""
    schema = pl.Schema({"a": pl.Int64, "b": pl.Float64})

    text = _write(_frames(pl.DataFrame({"a": [1]}), pl.DataFrame({"b": [2.5], "a": [3]})), schema)

    assert text == "a,b\n1,\n3,2.5\n"


def test_a_column_the_header_lacks_is_logged_once_and_the_rest_is_written(caplog: pytest.LogCaptureFixture) -> None:
    """It cannot be added, and the stream that has sent rows is not cut: the log says so, once for each column."""
    frames = _frames(pl.DataFrame({"a": [1]}), pl.DataFrame({"a": [2], "b": [3]}), pl.DataFrame({"a": [4], "b": [5]}))

    with caplog.at_level(logging.WARNING, logger=STREAM_LOG):
        text = _write(frames)

    assert text == "a\n1\n2\n4\n"
    assert [record.getMessage() for record in caplog.records] == [
        "The CSV has no column 'b', its header was written without it: the values of it are left out."
    ]


def test_a_column_a_provider_adds_is_never_dropped_in_silence(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A station that delivers a column the request does not account for: the answer is whole, the log names it."""
    full = TimeseriesValues.wide_schema

    def without_the_maximum(self: TimeseriesValues) -> pl.Schema:
        return pl.Schema({name: dtype for name, dtype in full(self).items() if not name.startswith(MAX)})

    monkeypatch.setattr(TimeseriesValues, "wide_schema", without_the_maximum)

    with caplog.at_level(logging.WARNING, logger=STREAM_LOG):
        csv = _rest("csv", **WIDE)

    assert MAX not in _header(csv)
    assert _table(csv).height == 9
    messages = [record.getMessage() for record in caplog.records if record.name == STREAM_LOG]
    assert len(messages) == 2
    assert f"'{MAX}'" in messages[0]
