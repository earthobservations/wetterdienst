# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A requested station that returned no rows, while others did, is told by `station-without-rows` (GH-3828).

Served as `test_surface_parity.py` serves it: a small DWD network whose index and files are stubs, so that a
request runs whole and only the network is stood in for. Eight stations hold three days of May 2020 each; a test
empties the ones it wants empty.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner

from tests.ui.test_surface_parity import (  # noqa: F401
    _POINT,
    PARAMETER,
    _no_ambient_settings,
    _rest,
    _serve_dwd,
    _withdrawing,
)
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.util.response_warnings import begin_response, note_skipped_download, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable

CODE = "station-without-rows"
WINDOW = {"start": "2020-05-01", "end": "2020-05-31 23:59:59"}


def _serving(monkeypatch: pytest.MonkeyPatch, **by_station: Callable[[pl.DataFrame], pl.DataFrame]) -> None:
    """Change what the source hands over for the stations named (`00002="..."` as `s00002`), as the core receives it."""
    original = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401
        df = original(self, station_id, parameter_or_dataset)
        change = by_station.get(f"s{station_id}")
        return df if change is None else change(df)

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)


def _nothing(df: pl.DataFrame) -> pl.DataFrame:
    """Hold no reading: the frame the source answers a station that has none."""
    return df.clear()


def _nulls(df: pl.DataFrame) -> pl.DataFrame:
    """Hold readings that are all null."""
    return df.with_columns(pl.lit(None, pl.Float64).alias("value"))


def _told(stations: list[str] | str, *, code: str = CODE, parameters: list[str] | None = None, **kwargs: Any) -> Any:  # noqa: ANN401
    """Read the values of stations named by id in the library, and give the warnings of `code`."""
    begin_response()
    request = DwdObservationRequest(parameters=parameters or [PARAMETER], **WINDOW, **kwargs)
    request.filter_by_station_id(stations).values().all()
    return [warning for warning in recorded_warnings() if warning["code"] == code]


def _codes() -> list[str]:
    return [warning["code"] for warning in recorded_warnings()]


# one empty station among others, and the wording


def test_an_empty_station_among_others_is_told_with_its_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ids that returned nothing are named once, the others are not, and the message says what it can be."""
    _serving(monkeypatch, s00002=_nothing)

    (warning,) = _told(["00001", "00002", "00003"])

    assert warning["stations"] == ["00002"]
    assert "parameter" not in warning
    assert warning["message"] == (
        "No rows for station 00002 from 2020-05-01 to 2020-05-31. The source holds no values of it there, or every "
        "value was null and left out (`drop_nulls`)."
    )
    assert _codes() == [CODE]


def test_several_empty_stations_are_one_warning_in_the_order_of_the_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    """The order is the answer's, the catalogue's, as `values` and `metadata.request.stations.ids` have it."""
    _serving(monkeypatch, s00002=_nothing, s00004=_nothing)

    (warning,) = _told(["00004", "00003", "00002", "00001"])

    assert warning["stations"] == ["00002", "00004"]
    assert "stations 00002, 00004 " in warning["message"]
    assert warning["message"].endswith(
        "The source holds no values of them there, or all of them were null and left out (`drop_nulls`)."
    )
    assert "every value" not in warning["message"]
    assert "all of them were null" in warning["message"]


def test_the_message_does_not_say_what_the_other_stations_have(monkeypatch: pytest.MonkeyPatch) -> None:
    """The others may have no rows left (another warning explains them, `sql_values` cuts them): it is not claimed."""
    _serving(monkeypatch, s00002=_nothing)

    (warning,) = _told(["00001", "00002"])

    assert "other" not in warning["message"]
    assert "while" not in warning["message"]


def test_rows_that_sql_values_cuts_afterwards_do_not_change_what_is_told(monkeypatch: pytest.MonkeyPatch) -> None:
    """00002 had no rows before the clause and is told whatever it leaves: the message is true, and says no more."""
    _serving(monkeypatch, s00002=_nothing)
    monkeypatch.setenv("WD_RESTAPI_SQL", "true")

    cut = _rest("/api/values", stations="00001,00002,00003", timestamp="2020-05", sql_values="station_id = '00003'")
    assert cut.status_code == 200, cut.text
    (warning,) = cut.json()["metadata"]["warnings"]
    assert warning["code"] == CODE
    assert warning["stations"] == ["00002"]
    assert "other" not in warning["message"]
    # a clause that leaves no row of any station: the walk's warning is the same
    none = _rest("/api/values", stations="00001,00002,00003", timestamp="2020-05", sql_values="value > 100")
    assert none.status_code == 200, none.text
    assert [w["stations"] for w in none.json()["metadata"]["warnings"] if w["code"] == CODE] == [["00002"]]


def test_the_list_is_cut_and_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """As every warning lists its stations: the first ones, and how many there are in all."""
    _serving(monkeypatch, s00002=_nothing, s00003=_nothing, s00004=_nothing)
    monkeypatch.setattr("wetterdienst.model.parameter_rows.MAX_STATIONS_LISTED", 2)

    (warning,) = _told(["00001", "00002", "00003", "00004"])

    assert warning["stations"] == ["00002", "00003"]
    assert "3 stations, the first 2 of them 00002, 00003" in warning["message"]


def test_a_request_where_every_station_has_rows_is_told_of_nothing() -> None:
    """The control: no empty station, no warning."""
    assert _told(["00001", "00002", "00003"]) == []


def test_a_station_the_window_precedes_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """The index says it began after the window ended: it is not read, and has no rows in it, which is told."""
    # the stub holds May 2020; 00001 (begun 1934) holds May 1935 instead, 00002 (1950) and 00005 (1980) began after it
    _serving(monkeypatch, s00001=lambda df: df.with_columns(pl.col("timestamp").dt.replace(year=1935)))
    begin_response()
    request = DwdObservationRequest(parameters=[PARAMETER], start="1935-05-01", end="1935-05-03")

    assert not request.filter_by_station_id(["00001", "00002", "00005"]).values().all().df.is_empty()

    (warning,) = [w for w in recorded_warnings() if w["code"] == CODE]
    assert warning["stations"] == ["00002", "00005"]
    assert warning["message"].startswith("No rows for stations 00002, 00005 from 1935-05-01 to 1935-05-03.")


# what narrowed the request, and what could have emptied the station


def test_the_periods_asked_for_are_named_as_the_sibling_names_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """`periods=recent` over a window of the historical period: the values may be in the other one, and it is said."""
    _serving(monkeypatch, s00001=lambda df: df.with_columns(pl.col("timestamp").dt.replace(year=2010)))
    request = DwdObservationRequest(
        parameters=[PARAMETER], periods="recent", start="2010-05-01", end="2010-05-31 23:59:59"
    )
    begin_response()
    request.filter_by_station_id(["00001", "00002"]).values().all()

    (warning,) = [w for w in recorded_warnings() if w["code"] == CODE]
    assert warning["message"] == (
        "No rows for station 00002 from 2010-05-01 to 2010-05-31 in the periods asked for (recent). The source holds "
        "no values of it there, or every value was null and left out (`drop_nulls`). Try without `periods`."
    )
    # the same words as the sibling warning of the same request
    _serving(monkeypatch, s00001=_nothing)
    begin_response()
    request.filter_by_station_id(["00001", "00002"]).values().all()
    (sibling,) = [w for w in recorded_warnings() if w["code"] == "parameter-without-rows"]
    assert "in the periods asked for (recent)" in sibling["message"]
    assert "Try without `periods`" in sibling["message"]


def test_what_narrowed_any_dataset_of_the_request_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """The phrases are joined over the request's datasets, as `parameter-without-rows` gives them for each."""
    _serving(monkeypatch, s00002=_nothing)
    monkeypatch.setattr(
        DwdObservationRequest,
        "_narrowed_by",
        lambda _self, dataset: [("the run issued", "try another run")] if dataset.name == "precipitation_more" else [],
    )

    (warning,) = _told(["00001", "00002"], parameters=[PARAMETER, "daily/more_precip/precipitation_amount"])

    assert "from 2020-05-01 to 2020-05-31 in the run issued. " in warning["message"]
    assert warning["message"].endswith(" Try another run.")


def test_a_request_with_no_window_has_no_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is referred to without a window, and no period narrows what is read."""
    _serving(monkeypatch, s00002=_nothing)
    begin_response()
    DwdObservationRequest(parameters=[PARAMETER]).filter_by_station_id(["00001", "00002"]).values().all()

    (warning,) = [w for w in recorded_warnings() if w["code"] == CODE]
    assert warning["message"] == (
        "No rows for station 00002. The source holds no values of it, or every value was null and left out "
        "(`drop_nulls`)."
    )


@pytest.mark.parametrize(
    "options",
    [pytest.param({"drop_nulls": False}, id="drop_nulls false"), pytest.param({"shape": "wide"}, id="wide")],
)
def test_the_nulls_are_not_a_reason_where_none_are_dropped(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]
) -> None:
    """Where the answer keeps its null rows (`drop_nulls=False`, the wide shape) the text does not offer that reason."""
    _serving(monkeypatch, s00002=_nothing)

    (warning,) = _told(["00001", "00002"], options=options)

    assert warning["message"] == (
        "No rows for station 00002 from 2020-05-01 to 2020-05-31. The source holds no values of it there."
    )


def test_readings_all_null_in_the_wide_shape_are_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Null rows are not dropped in the wide shape, so a station of nulls has rows there and is not named."""
    _serving(monkeypatch, s00002=_nulls)

    assert _told(["00001", "00002"], options={"shape": "wide"}) == []


# when it is not told: every station empty, another selection


def test_every_station_empty_is_the_warning_of_the_parameter_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nobody has rows: `parameter-without-rows` is the word, and no second warning says the same of the stations."""
    _serving(monkeypatch, s00001=_nothing, s00002=_nothing)

    assert _told(["00001", "00002"]) == []
    assert _codes() == ["parameter-without-rows"]


@pytest.mark.parametrize(
    "select",
    [
        pytest.param(lambda request: request.all(), id="all"),
        pytest.param(lambda request: request.filter_by_rank(_POINT, rank=6), id="rank"),
        pytest.param(lambda request: request.filter_by_distance(_POINT, distance=500), id="distance"),
        pytest.param(lambda request: request.filter_by_bbox(13.0, 50.0, 14.0, 52.0), id="bbox"),
        pytest.param(lambda request: request.filter_by_name("Dresden", rank=6), id="name"),
    ],
)
def test_a_selection_that_is_no_list_of_ids_does_not_tell_it(
    monkeypatch: pytest.MonkeyPatch, select: Callable[[DwdObservationRequest], Any]
) -> None:
    """A point, a box, a name or `rank` have empty stations as the ordinary case, and a ranked walk ends early."""
    _serving(monkeypatch, s00002=_nothing, s00004=_nothing)
    begin_response()
    request = DwdObservationRequest(parameters=[PARAMETER], **WINDOW)

    result = select(request).values().all()

    assert not result.df.is_empty()
    assert CODE not in _codes()


def test_a_station_asked_for_by_sql_is_not_a_list_of_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """A selection by SQL says nothing of the ids: a station it picks that is empty is not told."""
    _serving(monkeypatch, s00002=_nothing)
    begin_response()
    request = DwdObservationRequest(parameters=[PARAMETER], **WINDOW)

    request.filter_by_sql("station_id IN ('00001', '00002')").values().all()

    assert CODE not in _codes()


@pytest.mark.parametrize("estimate", ["summarize", "interpolate"])
def test_an_estimate_does_not_tell_it(monkeypatch: pytest.MonkeyPatch, estimate: str) -> None:
    """An estimate reads the stations around a point as candidates, most of them empty, and does not warn of that."""
    _serving(monkeypatch, s00001=_nothing, s00002=_nothing)
    begin_response()

    getattr(DwdObservationRequest(parameters=[PARAMETER], start="2020-05-01", end="2020-05-03"), estimate)(_POINT)

    assert CODE not in _codes()


def test_a_reader_that_is_not_to_warn_does_not_tell_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """What an estimate sets on its reader (`_warn_without_rows`) silences this warning as the other two."""
    _serving(monkeypatch, s00002=_nothing)
    begin_response()
    request = DwdObservationRequest(parameters=[PARAMETER], **WINDOW)

    reader = request.filter_by_station_id(["00001", "00002"]).values()
    reader._warn_without_rows = False  # noqa: SLF001
    reader.all()

    assert recorded_warnings() == []


# an id the network has no station for


def test_an_unknown_id_is_told_by_unknown_station_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """It is not in the walk: the one that is empty is named here, the one that is not there only by its own code."""
    _serving(monkeypatch, s00002=_nothing)

    (warning,) = _told(["00001", "00002", "99999"])

    assert warning["stations"] == ["00002"]
    assert "99999" not in warning["message"]
    (unknown,) = [w for w in recorded_warnings() if w["code"] == "unknown-station"]
    assert "99999" in unknown["message"]
    assert "00002" not in unknown["message"]
    assert _codes() == ["unknown-station", CODE]


def test_an_unknown_id_beside_stations_with_rows_adds_nothing() -> None:
    """Only the id the network has no station for is missing: told once, not twice."""
    assert _told(["00001", "99999"]) == []
    assert _codes() == ["unknown-station"]


# what has rows, and what the answer holds


def test_a_station_with_rows_of_one_parameter_and_none_of_another_is_not_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """It has rows: the parameter that is empty is `parameter-without-rows`'s, not this warning's."""
    _serving(monkeypatch, s00002=lambda df: df.filter(pl.col("parameter") != "sdk"))
    named = ["daily/kl/sunshine_duration", PARAMETER]

    assert _told(["00001", "00002", "00003"], parameters=named) == []
    assert "parameter-without-rows" not in _codes()


def test_readings_all_null_are_no_rows_unless_the_nulls_are_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """The warning is true of the answer: dropped nulls leave no row of the station, kept ones are rows."""
    _serving(monkeypatch, s00002=_nulls)

    (dropped,) = _told(["00001", "00002"])
    assert dropped["stations"] == ["00002"]

    assert _told(["00001", "00002"], options={"drop_nulls": False}) == []


def test_readings_a_check_rejected_are_told_by_the_check_and_named_here_only_while_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A station all of whose readings a hard check rejected has no rows once dropped, and the answer says both."""
    _serving(monkeypatch, s00002=lambda df: df.with_columns(pl.lit(999.0).alias("value")))

    (dropped,) = _told(["00001", "00002"])
    assert dropped["stations"] == ["00002"]
    assert "rejected-by-plausibility" in _codes()

    assert _told(["00001", "00002"], options={"drop_nulls": False}) == []
    assert "rejected-by-plausibility" in _codes()


def test_a_station_that_skip_empty_dropped_is_named_by_station_skipped_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """One day in the 31 of the window is below the threshold and told so; no reading at all has no such word."""
    _serving(monkeypatch, s00002=lambda df: df.filter(pl.col("timestamp").dt.day() == 1), s00003=_nothing)

    # the stub's three days are 10 % of the window, one day 3 %
    (warning,) = _told(["00001", "00002", "00003"], options={"skip_empty": True, "skip_threshold": 0.05})

    assert warning["stations"] == ["00003"]
    assert "station-skipped" in _codes()


def test_a_station_skip_empty_leaves_out_for_nulls_is_named_by_station_skipped_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All its readings are null and dropped, which `skip_empty` tells as it does a share below the threshold."""
    _serving(monkeypatch, s00002=_nulls, s00003=_nothing)

    (warning,) = _told(["00001", "00002", "00003"], options={"skip_empty": True, "skip_threshold": 0.05})

    assert warning["stations"] == ["00003"]
    assert any(w["code"] == "station-skipped" and "00002" in w["message"] for w in recorded_warnings())


def test_a_file_that_serves_every_station_covers_the_stations_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A whole-request file let go is every collected station's: its emptiness is `file-skipped`'s, not told here."""

    def lets_go(df: pl.DataFrame) -> pl.DataFrame:
        note_skipped_download(whole_request=True)
        return df

    _serving(monkeypatch, s00001=lets_go, s00002=_nothing)

    assert _told(["00001", "00002"]) == []
    assert [w["stations"] for w in recorded_warnings() if w["code"] == "file-skipped"] == [["00001", "00002"]]


def test_a_station_not_read_is_named_beside_a_whole_request_file_let_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """The file covers the stations that were read; one the index says began after the window was never read."""

    def lets_go(df: pl.DataFrame) -> pl.DataFrame:
        note_skipped_download(whole_request=True)
        return df.with_columns(pl.col("timestamp").dt.replace(year=1955))

    _serving(monkeypatch, s00001=lets_go)
    begin_response()
    request = DwdObservationRequest(parameters=[PARAMETER], start="1955-05-01", end="1955-05-03")

    request.filter_by_station_id(["00001", "00005"]).values().all()

    (warning,) = [w for w in recorded_warnings() if w["code"] == CODE]
    assert warning["stations"] == ["00005"]


def test_a_station_whose_file_was_let_go_is_named_by_file_skipped_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Its values may be missing for the failure, not for lack of data: that is the other warning's reason."""
    _serving(monkeypatch, s00003=_nothing)
    _withdrawing(monkeypatch, "00002")

    (warning,) = _told(["00001", "00002", "00003"])

    assert warning["stations"] == ["00003"]
    (skipped,) = [w for w in recorded_warnings() if w["code"] == "file-skipped"]
    assert skipped["stations"] == ["00002"]


# a walk that does not reach its end says nothing of the stations it did not reach


def _collected(request: DwdObservationRequest, stations: list[str]) -> Any:  # noqa: ANN401
    return request.filter_by_station_id(stations).values()


def test_a_consumer_that_stops_has_no_warning_for_stations_it_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A closed generator (a stream whose client left, a `break`) has read some stations: it names none."""
    _serving(monkeypatch, s00002=_nothing, s00003=_nothing)
    begin_response()
    request = DwdObservationRequest(parameters=[PARAMETER], **WINDOW)

    walk = _collected(request, ["00001", "00002", "00003", "00004"]).query()
    next(walk)
    walk.close()
    assert CODE not in _codes()

    begin_response()
    assert len(list(_collected(request, ["00001", "00002", "00003", "00004"]).query())) == 2
    (warning,) = [w for w in recorded_warnings() if w["code"] == CODE]
    assert warning["stations"] == ["00002", "00003"]


def test_a_failure_in_the_walk_has_no_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """An error raised at a later station raises; the stations before it are not told as empty."""
    _serving(monkeypatch, s00002=_nothing)

    def fails(df: pl.DataFrame) -> pl.DataFrame:
        raise RuntimeError(df.height)

    _serving(monkeypatch, s00003=fails)
    begin_response()
    request = DwdObservationRequest(parameters=[PARAMETER], **WINDOW)

    with pytest.raises(RuntimeError):
        request.filter_by_station_id(["00001", "00002", "00003"]).values().all()

    assert CODE not in _codes()


# every surface says the same, and the answer is the same the next time


def _surfaces(stations: str) -> dict[str, list[dict[str, Any]]]:
    """Ask the library, the command line, REST (JSON and NDJSON) and the MCP tool for the values of the stations."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    begin_response()
    request = DwdObservationRequest(parameters=[PARAMETER], **WINDOW)
    request.filter_by_station_id(stations.split(",")).values().all()
    library = recorded_warnings()
    cli_result = CliRunner().invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            f"--parameters={PARAMETER}",
            f"--stations={stations}",
            "--timestamp=2020-05",
        ],
    )
    assert cli_result.exit_code == 0, cli_result.output
    rest = _rest("/api/values", stations=stations, timestamp="2020-05")
    assert rest.status_code == 200, rest.text
    streamed = _rest("/api/values", stations=stations, timestamp="2020-05", format="ndjson")
    assert streamed.status_code == 200, streamed.text

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as client:
            result = await client.call_tool(
                "values",
                {
                    "provider": "dwd",
                    "network": "observation",
                    "parameters": PARAMETER,
                    "stations": stations,
                    "timestamp": "2020-05",
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


def test_it_is_told_alike_on_every_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    """The library, the command line, REST (JSON and NDJSON) and the MCP tool name the same station the same way."""
    _serving(monkeypatch, s00002=_nothing)

    told = _surfaces("00001,00002,00003")

    (warning,) = told["rest"]
    assert warning["code"] == CODE
    assert warning["stations"] == ["00002"]
    assert told["cli"] == told["rest"] == told["ndjson"] == told["mcp"] == told["library"]
    rest = _rest("/api/values", stations="00001,00002,00003", timestamp="2020-05")
    assert rest.headers["X-Wetterdienst-Warnings"] == CODE
    # the stations of the answer are the ones with rows, and the warning is the one that says 00002 is not there
    assert rest.json()["metadata"]["request"]["stations"]["ids"] == ["00001", "00003"]


def test_nothing_is_told_on_any_surface_where_every_station_has_rows() -> None:
    """The control of the above, which names no one."""
    assert _surfaces("00001,00002") == {surface: [] for surface in ("library", "cli", "rest", "ndjson", "mcp")}


def test_the_next_request_says_it_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """The warning is raised by the walk, not by the download, so what is served from the cache says it as well.

    The REST API sends no `Cache-Control` for `values`, so a client keeps no answer that would hold it; the library
    gives the same warning for each walk.
    """
    _serving(monkeypatch, s00002=_nothing)

    first = _told(["00001", "00002"])
    second = _told(["00001", "00002"])
    assert first == second
    assert len(first) == 1
    response = _rest("/api/values", stations="00001,00002", timestamp="2020-05")
    assert "cache-control" not in response.headers
    assert (
        response.json()["metadata"]["warnings"]
        == _rest("/api/values", stations="00001,00002", timestamp="2020-05").json()["metadata"]["warnings"]
    )
