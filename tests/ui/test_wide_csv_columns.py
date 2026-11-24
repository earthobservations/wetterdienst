# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The columns of a wide answer are the parameters asked for, whatever the first station has (GH-4432).

A streamed CSV (and the rows of an NDJSON stream) is written station by station, and the header is written with the
first station. The wide frame of a station had a column for each parameter that station delivered, so a column that
only a later station had was dropped from the CSV without a word, and the CSV differed from the one the command line,
the MCP tool and `to_csv` of the whole result gave. Now every station's wide frame has every requested column (null
where the station has none), in the order of the request, so that the header of the first station is the header of
all, and every surface writes the same CSV.

Served as `test_surface_parity.py` serves it: a small DWD network whose index and files are stubs. Of the three
stations, `00001` lacks the maximum and `00003` lacks the minimum of the air temperature.
"""

from __future__ import annotations

import json
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
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.streaming import csv_stream

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

MIN = "temperature_air_min_2m"
MAX = "temperature_air_max_2m"
BOTH = f"daily/kl/{MIN},daily/kl/{MAX}"
STATIONS = "00001,00002,00003"
LACKING = {"00001": {MAX}, "00003": {MIN}}


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
    # `all()` is the diagonal concatenation of the stations
    return request.filter_by_station_id(STATIONS.split(",")).values().all().to_csv()


def _cli_args(parameters: str = BOTH, **options: str) -> list[str]:
    flags = [f"--{name.replace('_', '-')}={value}" for name, value in options.items()]
    query = _query(parameters)
    return [
        "values",
        "--provider=dwd",
        "--network=observation",
        f"--parameters={parameters}",
        f"--stations={query['stations']}",
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


WIDE = {"shape": "wide"}


def test_a_streamed_wide_csv_has_the_column_only_a_later_station_has() -> None:
    """The first station has no maximum; its CSV had no column for it and the values of the others were lost."""
    csv = _rest("csv", **WIDE)

    assert f"{MAX}" in _header(csv)
    frame = pl.read_csv(csv.encode())
    assert frame.filter(pl.col("station_id") == 2)[MAX].drop_nulls().len() == 3
    assert frame.filter(pl.col("station_id") == 3)[MAX].drop_nulls().len() == 3


@pytest.mark.parametrize(
    "options",
    [
        WIDE,
        {"shape": "wide", "humanize": "false"},
        {"shape": "wide", "convert_units": "false"},
        {"shape": "wide", "unit_targets": '{"temperature": "degree_fahrenheit"}'},
        {"shape": "long"},
        {"shape": "long", "humanize": "false"},
    ],
    ids=["wide", "wide-not-humanized", "wide-units-kept", "wide-converted", "long", "long-not-humanized"],
)
def test_the_streamed_csv_is_the_csv_of_the_whole_result_on_every_surface(options: dict[str, str]) -> None:
    """REST (streamed), the command line, an MCP tool (one body) and `to_csv` of the result write one CSV."""
    streamed = _rest("csv", **options)

    assert streamed == _cli_csv(**options) == _tool_csv(**options)
    if options == WIDE:
        assert streamed == _library_csv()


def test_the_columns_are_those_of_the_request_in_its_order() -> None:
    """A station's frame has the columns of the request, the first station's included, not those it happens to have."""
    forward, backward = _rest("csv", **WIDE), _rest("csv", parameters=f"daily/kl/{MAX},daily/kl/{MIN}", **WIDE)

    assert _header(forward) == [
        "station_id",
        "resolution",
        "dataset",
        "timestamp",
        MIN,
        f"{MIN}_quality_flags",
        MAX,
        f"{MAX}_quality_flags",
    ]
    assert _header(backward) == [
        "station_id",
        "resolution",
        "dataset",
        "timestamp",
        MAX,
        f"{MAX}_quality_flags",
        MIN,
        f"{MIN}_quality_flags",
    ]
    assert backward == _cli_csv(parameters=f"daily/kl/{MAX},daily/kl/{MIN}", shape="wide")


def test_a_dataset_is_every_parameter_of_it_on_the_streamed_and_the_plain_answer() -> None:
    """A request for a dataset names its parameters, so the header is the dataset's whatever the stations have."""
    streamed = _rest("csv", parameters="daily/kl", **WIDE)

    assert streamed == _cli_csv(parameters="daily/kl", **WIDE)
    request = DwdObservationRequest(parameters=["daily/kl"])
    assert [name for name in _header(streamed) if name.endswith("_quality_flags")] == [
        f"{parameter.name}_quality_flags" for parameter in request.parameters
    ]


@pytest.mark.parametrize("_stations_that_lack_parameters", [("00001",)], indirect=True)
def test_an_empty_first_station_leaves_the_header_to_the_next(_stations_that_lack_parameters: None) -> None:
    """A station without rows is not sent: the header is the first station with rows', which has every column."""
    streamed = _rest("csv", **WIDE)

    assert streamed == _cli_csv(**WIDE) == _tool_csv(**WIDE)
    assert MAX in _header(streamed)
    assert set(pl.read_csv(streamed.encode())["station_id"]) == {2, 3}


def test_the_rows_of_an_ndjson_stream_are_the_rows_of_the_json_answer_wide_and_long() -> None:
    """Every row of a station has the columns of the others, as the rows of the JSON answer have."""
    for shape in ("wide", "long"):
        lines = [json.loads(line) for line in _rest("ndjson", shape=shape).splitlines()]
        rows = lines[1:-1]
        plain = TestClient(restapi.app).get("/api/v1/values", params={**_query(shape=shape), "format": "json"}).json()

        assert rows == plain["values"]


def test_a_wide_csv_written_to_a_target_has_every_column(tmp_path: Path) -> None:
    """`--format csv --target`: the command line writes the file the streamed answer is."""
    target = tmp_path / "values.csv"
    result = CliRunner().invoke(cli, [*_cli_args(shape="wide"), f"--target=file://{target}"])

    assert result.exit_code == 0, result.output
    assert target.read_text() == _rest("csv", **WIDE)


def _frames(*frames: pl.DataFrame) -> Iterator[pl.DataFrame]:
    yield from frames


def _write(frames: Iterator[pl.DataFrame]) -> Callable[[], str]:
    return lambda: b"".join(
        csv_stream(frames, lambda df, header: df.write_csv(include_header=header), pl.DataFrame, lambda _e: None)
    ).decode()


def test_a_column_a_later_frame_has_that_the_header_lacks_is_a_failure_and_no_silent_loss() -> None:
    """The header is written with the first frame and cannot grow: a frame with another column cuts the stream."""
    write = _write(_frames(pl.DataFrame({"a": [1]}), pl.DataFrame({"a": [2], "b": [3]})))

    with pytest.raises(ValueError, match="b"):
        write()
