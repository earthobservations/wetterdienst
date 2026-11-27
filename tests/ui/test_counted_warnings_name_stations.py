# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A warning that counts something over the stations says which stations the count belongs to (GH-4424).

`missing-value-marker`, `calm-wind-direction` and `rejected-by-plausibility` were one sum for the request: a model
read 18 marker values of one station for another's. The message now gives the total, then the first stations with
their count (their name where the list has one) and how many more there are, and `stations` lists the ones named.
Served as `test_surface_parity.py` serves it: a small DWD network whose index and files are stubs.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.ui.test_surface_parity import (  # noqa: F401
    PARAMETER,
    _no_ambient_settings,
    _response_warnings,
    _rest,
    _serve_dwd,
)
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.options import Options
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui import restapi
from wetterdienst.ui.budget import ANSWER_BUDGET
from wetterdienst.ui.cli import cli
from wetterdienst.ui.mcp import _mark_tool_requests
from wetterdienst.util import response_warnings
from wetterdienst.util.response_warnings import (
    CALM_WIND_DIRECTION,
    CALM_WIND_DIRECTION_MESSAGE,
    MISSING_VALUE_MARKER,
    REJECTED_BY_PLAUSIBILITY_MESSAGE,
    begin_response,
    count_response_warning,
    log_counted_warnings,
    recorded_warnings,
)

if TYPE_CHECKING:
    from collections.abc import Collection

WINDOW = {"start": "2020-05-01", "end": "2020-05-31 23:59:59"}
SUNSHINE = "daily/kl/sunshine_duration"


def _marking(
    monkeypatch: pytest.MonkeyPatch, per_station: dict[str, int], *, parameters: Collection[str] | None = None
) -> None:
    """Have the source write a marker for a missing value on the first days of each station, `per_station` of them.

    The stub of the source holds three days of May 2020 for each parameter; a marker is a null with the `raw:` token the
    source wrote, as a provider's reader leaves it. Only the parameters named (`name_original`), or every one.
    """
    original = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401
        df = original(self, station_id, parameter_or_dataset)
        marked = (pl.col("timestamp").dt.day() <= per_station.get(station_id, 0)) & (
            pl.col("parameter").is_in(parameters) if parameters is not None else pl.lit(value=True)
        )
        return df.with_columns(
            pl.when(marked).then(None).otherwise(pl.col("value")).alias("value"),
            pl.when(marked).then(pl.lit("raw:-999")).otherwise(pl.col("quality_flags")).alias("quality_flags"),
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _told(
    stations: list[str],
    *,
    code: str = MISSING_VALUE_MARKER,
    parameters: list[str] | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Read the values of `stations` in the library, and give the warning `code` the answer carries (one)."""
    begin_response()
    request = DwdObservationRequest(parameters=parameters or [PARAMETER], **WINDOW, **kwargs)
    request.filter_by_station_id(stations).values().all()
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == code]
    return warning


def test_one_station_is_named_with_its_name_and_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """The total comes first, then the station, with its name from the list and the count at it."""
    _marking(monkeypatch, {"00001": 2})

    warning = _told(["00001", "00002"])

    assert warning["message"].startswith(
        "2 readings of the source were a marker for a missing value and are null, at 00001 Dresden-Klotzsche (2); "
        "with drop_nulls"
    )
    assert warning["stations"] == ["00001"]


def test_the_stations_are_told_in_the_order_of_the_answer_with_the_count_of_each(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two stations with markers are two entries, a station without is none; the total is their sum."""
    _marking(monkeypatch, {"00001": 3, "00002": 1, "00003": 0, "00004": 2})

    warning = _told(["00001", "00002", "00003", "00004"])

    assert warning["message"].startswith(
        "6 readings of the source were a marker for a missing value and are null, at 00001 Dresden-Klotzsche (3), "
        "00002 Dresden-Hosterwitz (1) and 00004 Dresden-Pillnitz (2); "
    )
    assert warning["stations"] == ["00001", "00002", "00004"]


def test_a_long_list_names_the_first_stations_and_counts_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    """Past the limit the first stations are named, and how many more there are: the total is the sum of all."""
    monkeypatch.setattr(response_warnings, "COUNTED_STATIONS_LISTED", 2)
    _marking(monkeypatch, {"00001": 3, "00002": 1, "00003": 2, "00004": 2})

    warning = _told(["00001", "00002", "00003", "00004"])

    assert warning["message"].startswith(
        "8 readings of the source were a marker for a missing value and are null, at 00001 Dresden-Klotzsche (3), "
        "00002 Dresden-Hosterwitz (1) and 2 more stations; "
    )
    assert warning["stations"] == ["00001", "00002"]


def test_one_station_over_the_limit_is_one_more_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rest is worded as a count of one."""
    monkeypatch.setattr(response_warnings, "COUNTED_STATIONS_LISTED", 1)
    _marking(monkeypatch, {"00001": 1, "00002": 1})

    warning = _told(["00001", "00002"])

    assert ", at 00001 Dresden-Klotzsche (1) and 1 more station; " in warning["message"]


def test_the_markers_of_several_parameters_are_one_count_for_the_station(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two parameters with markers at a station add up under the station: it is one entry, and the total is the sum."""
    _marking(monkeypatch, {"00001": 2, "00002": 1})

    warning = _told(["00001", "00002"], parameters=[PARAMETER, SUNSHINE])

    assert warning["message"].startswith(
        "6 readings of the source were a marker for a missing value and are null, at 00001 Dresden-Klotzsche (4) and "
        "00002 Dresden-Hosterwitz (2); "
    )


def test_only_the_stations_whose_parameter_has_markers_are_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station whose markers are of a parameter that was not asked for has none to tell."""
    from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata  # noqa: PLC0415

    sunshine = DwdObservationMetadata.daily.climate_summary.sunshine_duration.name_original
    _marking(monkeypatch, {"00001": 3, "00002": 3}, parameters={sunshine})

    begin_response()
    DwdObservationRequest(parameters=[PARAMETER], **WINDOW).filter_by_station_id(["00001", "00002"]).values().all()

    assert [warning for warning in recorded_warnings() if warning["code"] == MISSING_VALUE_MARKER] == []


@pytest.mark.parametrize("drop_nulls", [True, False])
def test_the_station_is_named_whether_the_nulls_are_dropped_or_not(
    monkeypatch: pytest.MonkeyPatch, *, drop_nulls: bool
) -> None:
    """With the nulls dropped a station of nothing but markers is emptied: the count is still its own, named."""
    _marking(monkeypatch, {"00001": 3, "00002": 1})

    warning = _told(["00001", "00002"], options=Options(drop_nulls=drop_nulls))

    assert warning["message"].startswith(
        "4 readings of the source were a marker for a missing value and are null, at 00001 Dresden-Klotzsche (3) and "
        "00002 Dresden-Hosterwitz (1); "
    )
    assert warning["stations"] == ["00001", "00002"]


def test_the_values_a_check_rejected_name_their_stations_too() -> None:
    """The three counted warnings tell the stations: here the numbers a hard check rejected at two stations."""
    begin_response()
    request = DwdObservationRequest(
        parameters=[PARAMETER], **WINDOW, options=Options(limits={"temperature_air_mean_2m": (2, 3)})
    )

    request.filter_by_station_id(["00001", "00002"]).values().all()

    (warning,) = [w for w in recorded_warnings() if w["code"] == "rejected-by-plausibility"]
    assert warning["message"].startswith(
        "6 values were numbers a plausibility check rejected (limits 6; a value several checks rejected is counted "
        "under each) and are null, at 00001 Dresden-Klotzsche (3) and 00002 Dresden-Hosterwitz (3); with drop_nulls"
    )
    assert warning["stations"] == ["00001", "00002"]


def test_a_calm_names_its_station_and_a_station_without_a_name_is_named_by_its_id() -> None:
    """`calm-wind-direction` is worded the same way; a station the list gives no name is its id alone."""
    begin_response()
    count_response_warning(CALM_WIND_DIRECTION, 4, CALM_WIND_DIRECTION_MESSAGE, station="01975", station_name="Hamburg")
    count_response_warning(CALM_WIND_DIRECTION, 1, CALM_WIND_DIRECTION_MESSAGE, station="01048")
    count_response_warning(CALM_WIND_DIRECTION, 2, CALM_WIND_DIRECTION_MESSAGE, station="01975")

    (warning,) = recorded_warnings()

    assert warning["message"].startswith(
        "7 wind directions were a calm, which the source writes as 0 and which has no direction: they are null, at "
        "01975 Hamburg (6) and 01048 (1), and no reading is missing;"
    )
    assert warning["stations"] == ["01975", "01048"]


def test_a_count_without_a_station_is_told_as_before() -> None:
    """A caller of `count_response_warning` that names no station has the message without a place, and no `stations`."""
    begin_response()
    count_response_warning("rejected-by-plausibility", 2, REJECTED_BY_PLAUSIBILITY_MESSAGE, details={"range": 2})

    (warning,) = recorded_warnings()

    assert ", at " not in warning["message"]
    assert "stations" not in warning


# the same text on every surface


def _surfaces(stations: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Ask the library, the command line, REST (JSON and NDJSON) and the MCP tool for the values of `stations`."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    begin_response()
    DwdObservationRequest(parameters=[PARAMETER], **WINDOW).filter_by_station_id(stations).values().all()
    library = recorded_warnings()
    joined = ",".join(stations)
    cli_result = CliRunner().invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            f"--parameters={PARAMETER}",
            f"--stations={joined}",
            "--timestamp=2020-05",
        ],
    )
    assert cli_result.exit_code == 0, cli_result.output
    rest = _rest("/api/values", stations=joined, timestamp="2020-05")
    assert rest.status_code == 200, rest.text
    streamed = _rest("/api/values", stations=joined, timestamp="2020-05", format="ndjson")
    assert streamed.status_code == 200, streamed.text

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as client:
            result = await client.call_tool(
                "values",
                {
                    "provider": "dwd",
                    "network": "observation",
                    "parameters": PARAMETER,
                    "stations": joined,
                    "timestamp": "2020-05",
                    "format": "json",
                },
            )
            return result.structured_content

    answer = asyncio.run(call())
    lines = [json.loads(line) for line in streamed.text.splitlines()]
    return {
        "library": library,
        "cli": json.loads(cli_result.stdout)["metadata"]["warnings"],
        "rest": rest.json()["metadata"]["warnings"],
        "ndjson": lines[-1]["end"]["warnings"],
        "mcp": answer.get("result", answer)["metadata"]["warnings"],
    }


def test_the_warning_is_the_same_text_on_every_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    """The library, the command line, REST (JSON and NDJSON) and the MCP tool give the same message and `stations`."""
    _marking(monkeypatch, {"00001": 2, "00002": 1})

    told = _surfaces(["00001", "00002"])

    assert told["cli"] == told["rest"] == told["ndjson"] == told["mcp"] == told["library"]
    (warning,) = told["rest"]
    assert warning["code"] == MISSING_VALUE_MARKER
    assert warning["stations"] == ["00001", "00002"]
    assert (
        "are null, at 00001 Dresden-Klotzsche (2) and 00002 Dresden-Hosterwitz (1); with drop_nulls"
        in warning["message"]
    )


def test_the_command_line_says_it_on_stderr_for_a_csv_with_the_stations(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A CSV has no `metadata.warnings`: the line on stderr is the message of the answer, stations and all."""
    _marking(monkeypatch, {"00001": 2, "00002": 1})
    with caplog.at_level(logging.INFO):
        result = CliRunner().invoke(
            cli,
            [
                "values",
                "--provider=dwd",
                "--network=observation",
                f"--parameters={PARAMETER}",
                "--stations=00001,00002",
                "--timestamp=2020-05",
                "--format=csv",
            ],
        )

    assert result.exit_code == 0, result.output
    (line,) = _response_warnings(caplog)[MISSING_VALUE_MARKER]
    assert "are null, at 00001 Dresden-Klotzsche (2) and 00002 Dresden-Hosterwitz (1); with drop_nulls" in line


def test_the_logged_line_and_the_recorded_message_are_one_text() -> None:
    """`log_counted_warnings` (the command line) and `recorded_warnings` (the answer) word a count alike."""
    begin_response()
    count_response_warning(MISSING_VALUE_MARKER, 3, "{count} markers{where}.", station="01975", station_name="Hamburg")
    log = logging.getLogger("test")
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    log.addHandler(handler)
    try:
        log_counted_warnings(log)
    finally:
        log.removeHandler(handler)

    assert [record.getMessage() for record in records] == [w["message"] for w in recorded_warnings()]
    assert records[0].getMessage() == "3 markers, at 01975 Hamburg (3)."


# a hundred stations, in an answer of the MCP tool


@pytest.fixture
def _hundred_stations(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve a hundred stations, each with a marker on the first day of every parameter of the dataset."""
    import datetime as dt  # noqa: PLC0415

    ids = [f"{number:05d}" for number in range(100, 200)]
    frame = pl.DataFrame(
        {
            "resolution": ["daily"] * 100,
            "dataset": ["climate_summary"] * 100,
            "station_id": ids,
            "start_timestamp": [dt.datetime(1950, 1, 1, tzinfo=dt.UTC)] * 100,
            "end_timestamp": [dt.datetime(2026, 11, 1, tzinfo=dt.UTC)] * 100,
            "latitude": [51.0 + number / 1000 for number in range(100)],
            "longitude": [13.0 + number / 1000 for number in range(100)],
            "elevation": [100.0] * 100,
            "name": [f"Station Number {number}" for number in range(100)],
            "region": ["Sachsen"] * 100,
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda self: frame.lazy())  # noqa: ARG005
    _marking(monkeypatch, dict.fromkeys(ids, 1))
    return ids


@pytest.mark.usefixtures("_hundred_stations")
def test_a_hundred_stations_make_a_short_warning_and_the_budget_still_cuts_the_answer() -> None:
    """The message names the first stations and counts the rest, however many there are; the answer is still cut."""
    pytest.importorskip("fastmcp")
    client = TestClient(_mark_tool_requests(restapi.app), raise_server_exceptions=False)

    response = client.get(
        "/api/values",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "all": "true",
            "timestamp": "2020-05",
            "format": "json",
        },
    )

    assert response.status_code == 200, response.text
    warnings = {warning["code"]: warning for warning in response.json()["metadata"]["warnings"]}
    marker = warnings[MISSING_VALUE_MARKER]
    assert marker["stations"] == ["00100", "00101", "00102", "00103", "00104"]
    assert "at 00100 Station Number 0 (" in marker["message"]
    assert "and 95 more stations; with drop_nulls" in marker["message"]
    assert len(marker["message"]) < 500
    # the cut to the budget works as before, with the warning in the block that is counted
    assert "answer-truncated" in warnings
    assert len(json.dumps(response.json(), separators=(",", ":"), ensure_ascii=False)) <= ANSWER_BUDGET


# the name is the source's text: one line, bounded, the same in the message, the log line and the JSON

_NASTY = "Ham\nburg\x1b[31m\u202eevil\u2028" + "x" * 5000


def _renaming(monkeypatch: pytest.MonkeyPatch, station_id: str, name: str) -> None:
    """Have the station list write `name` for the station."""
    original = DwdObservationRequest._all  # noqa: SLF001

    def listing(self: DwdObservationRequest) -> pl.LazyFrame:
        return original(self).with_columns(
            pl.when(pl.col("station_id") == station_id).then(pl.lit(name)).otherwise(pl.col("name")).alias("name")
        )

    monkeypatch.setattr(DwdObservationRequest, "_all", listing)


def _is_clean(text: str) -> bool:
    return not any(char in text for char in ("\n", "\r", "\x1b", "\u202e", "\u2028"))


def test_a_name_with_control_characters_is_cleaned_and_cut_where_it_enters() -> None:
    """A newline, an escape, a bidi override and 5,000 characters leave a one-line name of at most 60 characters."""
    begin_response()
    count_response_warning(MISSING_VALUE_MARKER, 3, "{count} markers{where}.", station="01975", station_name=_NASTY)

    (warning,) = recorded_warnings()

    assert _is_clean(warning["message"])
    name = warning["message"].removeprefix("3 markers, at 01975 ").removesuffix(" (3).")
    assert len(name) == 60
    assert name.startswith("Ham\ufffdburg\ufffd[31m\ufffdevil\ufffdxxx")
    assert name.endswith("x\u2026")
    assert warning["stations"] == ["01975"]


def test_a_name_of_the_list_is_one_clean_text_in_the_answer_and_the_log_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Through the walk: the library's message, REST's, and the command line's stderr line are one clean text."""
    _renaming(monkeypatch, "00001", _NASTY)
    _marking(monkeypatch, {"00001": 2})

    library = _told(["00001"])["message"]
    rest = _rest("/api/values", stations="00001", timestamp="2020-05").json()["metadata"]["warnings"][0]["message"]
    with caplog.at_level(logging.INFO):
        result = CliRunner().invoke(
            cli,
            [
                "values",
                "--provider=dwd",
                "--network=observation",
                f"--parameters={PARAMETER}",
                "--stations=00001",
                "--timestamp=2020-05",
                "--format=csv",
            ],
        )

    assert result.exit_code == 0, result.output
    (line,) = _response_warnings(caplog)[MISSING_VALUE_MARKER]
    assert library == rest == line
    assert _is_clean(library)
    assert len(library) < 500


def test_the_name_of_a_station_is_the_first_row_trimmed_and_none_where_it_has_none() -> None:
    """`_name_of` reads the first row of the station's rows, trimmed; a blank, a null or no column is no name."""
    name_of = TimeseriesValues._name_of  # noqa: SLF001

    assert name_of(pl.DataFrame({"name": [" Hamburg ", "Second"]})) == "Hamburg"
    assert name_of(pl.DataFrame({"name": ["Hamburg", "  "]})) == "Hamburg"
    assert name_of(pl.DataFrame({"name": ["   ", "Second"]})) is None
    assert name_of(pl.DataFrame({"name": [None, "Second"]}, schema={"name": pl.String})) is None
    assert name_of(pl.DataFrame({"station_id": ["01975"]})) is None
    assert name_of(pl.DataFrame({"name": []}, schema={"name": pl.String})) is None
