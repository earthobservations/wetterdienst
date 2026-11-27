# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The compact format (GH-4445): what its writer makes of a frame, read back by a reader that shares nothing with it.

`tests/compact_reader.py` is written from the grammar of `docs/usage/compact.md`. Every case here is written by
`wetterdienst.io.compact` and read by it: the readings, their flags and the header must come back, and no text of the
answer, a name or a warning or a licence, may make a line of the format that is not one.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import random
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from tests import compact_reader
from tests.compact_reader import FormatError, differences, heading_of, parse, truth, values
from wetterdienst.io import compact

UTC = dt.UTC

#: what a block of the metadata of an answer has, as its JSON has it: only the parts the format reads
BLOCK: dict[str, Any] = {
    "provider": {
        "name_english": "German Weather Service",
        "url": "https://opendata.dwd.de/climate_environment/CDC/",
        "license": {"spdx_id": "CC-BY-4.0", "name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"},
        "attribution": "Source: Deutscher Wetterdienst",
    },
    "processing_note": "Processed by wetterdienst: the provider's data was reshaped into a uniform table.",
    "request": {"provider": "dwd", "network": "observation", "start": "2026-11-10T00:00:00+00:00", "end": None},
    "retrieved_at": "2026-11-25T22:48:17.123456+00:00",
    "data_updated_at": "2026-11-25T08:45:00+00:00",
    "producer": {"name": "wetterdienst", "version": "0.200.0", "doi": "10.5281/zenodo.3960624"},
    "warnings": [],
    "counts": {"stations": 1, "rows": 0},
}

STATION = {
    "station_id": "01975",
    "name": "Hamburg-Fuhlsbüttel",
    "latitude": 53.6332,
    "longitude": 9.9881,
    "elevation": 11.0,
    "region": "Hamburg",
    "wmo_id": "10147",
    "wigos_id": None,
    "icao_id": None,
}

SCHEMA = {
    "station_id": pl.String,
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "timestamp": pl.Datetime("us", "UTC"),
    "value": pl.Float64,
    "quality_flags": pl.String,
}


def parameter(
    name: str, resolution: str = "daily", dataset: str = "climate_summary", unit: str = "°C"
) -> dict[str, str]:
    """Describe a parameter as the metadata block does."""
    return {"resolution": resolution, "dataset": dataset, "name": name, "name_original": name.upper(), "unit": unit}


def frame(rows: list[tuple[Any, ...]]) -> pl.DataFrame:
    """Build a long frame of rows `(station, resolution, dataset, parameter, timestamp, value, flags)`."""
    return pl.DataFrame(rows, schema=SCHEMA, orient="row")


def write(
    rows: list[tuple[Any, ...]],
    parameters: list[dict[str, str]],
    *,
    block: dict[str, Any] | None = None,
    stations: list[dict[str, Any]] | None = None,
) -> str:
    """Write rows as compact text: the block says how many rows there are, as the metadata of an answer does."""
    block = copy.deepcopy(block or BLOCK)
    block["counts"]["rows"] = len(rows)
    return compact.values_text(block, frame(rows), [STATION] if stations is None else stations, parameters)


def day(n: int) -> dt.datetime:
    """Give midnight UTC of the n-th day of November 2026."""
    return dt.datetime(2026, 11, 1, tzinfo=UTC) + dt.timedelta(days=n)


def hour(n: int, start: dt.datetime = dt.datetime(2026, 11, 10, tzinfo=UTC)) -> dt.datetime:
    """Give the n-th hour from `start`."""
    return start + dt.timedelta(hours=n)


def assert_round_trip(text: str, rows: list[tuple[Any, ...]]) -> Any:  # noqa: ANN401
    """Read the text and hold what it stands for to the rows."""
    parsed = parse(text)
    assert differences(values(parsed), truth(frame(rows))) == []
    assert parsed.end == f"rows={len(rows)}"
    return parsed


# --- the cases of the design: a series, many parameters with nulls and raw flags, stations, datasets, a forecast -----


def test_one_series_is_a_header_a_station_and_a_table_with_the_unit_in_its_column_line() -> None:
    """24 hours of air temperature: the grammar of the first example, line by line."""
    rows = [
        ("01975", "hourly", "temperature_air", "temperature_air_2m", hour(i), round(4.7 - i / 10, 1), "1")
        for i in range(24)
    ]
    text = write(rows, [parameter("temperature_air_2m", "hourly", "temperature_air")])

    lines = text.split("\n")
    assert lines[:5] == [
        "# wetterdienst-compact/1 values",
        "# provider: German Weather Service (dwd/observation)",
        "# license: CC-BY-4.0 https://creativecommons.org/licenses/by/4.0/",
        "# attribution: Source: Deutscher Wetterdienst",
        "# source: https://opendata.dwd.de/climate_environment/CDC/",
    ]
    assert "# window: 2026-11-10T00:00Z/.." in lines
    assert "# time: UTC" in lines
    assert "# retrieved: 2026-11-25T22:48Z (source updated 2026-11-25T08:45Z)" in lines
    assert "# producer: wetterdienst 0.200.0, doi 10.5281/zenodo.3960624" in lines
    assert "# warnings: none" in lines
    i = lines.index("## values hourly/temperature_air station=01975")
    assert lines[i + 1 : i + 5] == [
        "# flags: 1 (all rows)",
        "timestamp,temperature_air_2m(°C)",
        "2026-11-10T00:00Z,4.7",
        "2026-11-10T01:00Z,4.6",
    ]
    assert lines[-2:] == ["# end rows=24", ""]
    assert (
        "## stations\nstation_id,name,latitude,longitude,elevation_m,region,wmo_id\n01975,Hamburg-Fuhlsbüttel,53.6332"
        in text
    )
    assert_round_trip(text, rows)


def test_fourteen_parameters_with_nulls_and_raw_flags_say_the_default_and_the_periods_that_differ() -> None:
    """A null is an empty cell and its `raw:` flags are a period of the table of flags: the rows stay short."""
    names = [f"parameter_{i:02d}" for i in range(14)]
    rows = []
    for d in range(9):
        for i, name in enumerate(names):
            # the first five parameters lack their readings on days 3 to 6, which the source wrote as -999
            missing = i < 5 and 3 <= d <= 6
            rows.append(
                (
                    "01975",
                    "daily",
                    "climate_summary",
                    name,
                    day(d),
                    None if missing else d + i / 4,
                    "1,raw:-999" if missing else "1",
                )
            )
    text = write(rows, [parameter(name) for name in names])

    parsed = assert_round_trip(text, rows)
    table = parsed.table("values daily/climate_summary")
    assert table.attribute("flags") == "1 (periods that differ are listed after the table)"
    assert table.rows[3][1:6] == [None] * 5
    assert table.rows[2][0] == "2026-11-03"
    flags = parsed.table("flags daily/climate_summary")
    # five columns share one period: one line, not five
    assert flags.rows == [
        ["parameter_00|parameter_01|parameter_02|parameter_03|parameter_04", "2026-11-04", "2026-11-07", "1,raw:-999"]
    ]
    assert flags.heading == "flags daily/climate_summary station=01975 (exceptions)"


def test_columns_with_different_defaults_list_theirs() -> None:
    """Where the columns do not share their flags, the attribute names each column's."""
    rows = [("01975", "daily", "d", "a", day(i), float(i), "1") for i in range(3)]
    rows += [("01975", "daily", "d", "b", day(i), float(i), "3") for i in range(3)]
    rows += [("01975", "daily", "d", "c", day(i), float(i), None) for i in range(3)]
    text = write(rows, [parameter(name, dataset="d") for name in "abc"])

    parsed = assert_round_trip(text, rows)
    assert parsed.table("values").attribute("flags") is None
    assert parsed.table("values").attribute("flags_by_column") == "a=1, b=3 (all rows)"


def test_a_default_of_flags_with_a_comma_or_a_space_is_quoted_in_a_list() -> None:
    """The list `name=flags, name=flags` is read at its commas, so a flags text with one is a JSON string."""
    rows = [("01975", "daily", "d", "a", day(i), float(i), "1,raw:-999") for i in range(3)]
    rows += [("01975", "daily", "d", "b", day(i), float(i), "a b") for i in range(3)]
    text = write(rows, [parameter(name, dataset="d") for name in "ab"])

    parsed = assert_round_trip(text, rows)
    assert parsed.table("values").attribute("flags_by_column") == 'a="1,raw:-999", b="a b" (all rows)'


def test_a_column_with_flags_now_and_then_and_none_by_default_has_a_table_of_flags_and_no_attribute() -> None:
    """No flags in most readings of a column: the readings that have some are periods, and there is no default."""
    rows = [("01975", "daily", "d", "a", day(i), float(i), "1" if 2 <= i <= 3 else None) for i in range(6)]
    text = write(rows, [parameter("a", dataset="d")])

    parsed = assert_round_trip(text, rows)
    assert parsed.table("values").attribute("flags") is None
    assert parsed.table("flags").rows == [["all", "2026-11-03", "2026-11-04", "1"]]


def test_a_gap_does_not_end_a_period_and_a_reading_with_the_default_does() -> None:
    """The readings of a column that a period holds are those it has: a missing reading between two is no break."""
    flags = {0: "x", 1: "x", 3: "x", 5: "1", 6: "x"}
    rows = [("01975", "daily", "d", "a", day(i), float(i), flags[i]) for i in flags]
    rows += [("01975", "daily", "d", "a", day(i), float(i), "1") for i in (7, 8, 9, 10)]
    text = write(rows, [parameter("a", dataset="d")])

    parsed = assert_round_trip(text, rows)
    runs = [r[1:] for r in parsed.table("flags").rows]
    assert runs == [["2026-11-01", "2026-11-04", "x"], ["2026-11-07", "2026-11-07", "x"]]


def test_three_stations_have_a_table_each_and_one_stations_table() -> None:
    """A table is a station, a resolution and a dataset; the stations are listed once in front."""
    rows = [(sid, "daily", "d", "a", day(i), float(i), "1") for sid in ("00011", "01975", "04411") for i in range(3)]
    stations = [{**STATION, "station_id": sid, "name": sid} for sid in ("00011", "01975", "04411")]
    text = write(rows, [parameter("a", dataset="d")], stations=stations)

    parsed = assert_round_trip(text, rows)
    assert [t.heading for t in parsed.tables] == [
        "stations",
        "values daily/d station=00011",
        "values daily/d station=01975",
        "values daily/d station=04411",
    ]
    assert [row[0] for row in parsed.table("stations").rows] == ["00011", "01975", "04411"]


def test_two_datasets_and_two_resolutions_of_one_station_are_two_tables_each_with_its_units() -> None:
    """The column line says the unit of its dataset: the same name may be hours in one and minutes in another."""
    rows = [("01975", "daily", "climate_summary", "sunshine_duration", day(i), float(i), "1") for i in range(2)]
    rows += [("01975", "hourly", "sun", "sunshine_duration", hour(i), float(i), "1") for i in range(2)]
    parameters = [
        parameter("sunshine_duration", "daily", "climate_summary", "h"),
        parameter("sunshine_duration", "hourly", "sun", "min"),
    ]
    text = write(rows, parameters)

    parsed = assert_round_trip(text, rows)
    assert parsed.table("values daily/climate_summary").columns == ["timestamp", "sunshine_duration(h)"]
    assert parsed.table("values hourly/sun").columns == ["timestamp", "sunshine_duration(min)"]
    # a table of whole days has dates, one of hours has times
    assert parsed.table("values daily").rows[0][0] == "2026-11-01"
    assert parsed.table("values hourly").rows[0][0] == "2026-11-10T00:00Z"


def test_a_forecast_with_parameters_that_come_at_other_times_leaves_empty_cells_and_says_what_it_left_out() -> None:
    """Probabilities every sixth hour, a temperature every hour: a row for each hour, an empty cell where none."""
    rows = []
    for i in range(24):
        rows.append(("72295", "hourly", "small", "temperature_air_2m", hour(i), 20 - i / 3, None))
        if i % 6 == 0:
            rows.append(("72295", "hourly", "small", "probability_precipitation", hour(i), float(i), None))
    block = copy.deepcopy(BLOCK)
    block["warnings"] = [
        {
            "code": "forecast-from-now",
            "message": "The answer starts at the current hour (2026-11-10T00:00:00+00:00): 4 timestamps are left out.",
        },
        {"code": "missing-value-marker", "message": "43 readings were a marker.", "stations": ["72295"]},
    ]
    parameters = [
        parameter("temperature_air_2m", "hourly", "small"),
        parameter("probability_precipitation", "hourly", "small", "%"),
    ]
    text = write(rows, parameters, block=block, stations=[{**STATION, "station_id": "72295"}])

    parsed = assert_round_trip(text, rows)
    assert [code for code, _ in parsed.warnings()] == ["forecast-from-now", "missing-value-marker"]
    # what the message does not say, the structured part of the warning does
    assert parsed.warnings()[1][1] == "43 readings were a marker. [stations 72295]"
    assert parsed.get("warnings") is None
    table = parsed.table("values hourly/small")
    assert table.columns == ["timestamp", "temperature_air_2m(°C)", "probability_precipitation(%)"]
    assert table.rows[1][2] is None
    assert table.rows[6][2] == "6"
    assert table.attribute("flags") is None


def test_a_table_the_request_sorted_keeps_the_order_of_the_answer_and_a_period_is_a_reading() -> None:
    """The rows of `sort=-timestamp` come newest first: each exception is its own period, which names its timestamp."""
    rows = [("01975", "daily", "d", "a", day(i), float(i), "9" if i in (3, 4) else "1") for i in (9, 7, 5, 4, 3, 1)]
    block = copy.deepcopy(BLOCK)
    block["search"] = {
        "options": {"filter": "value<=9", "sort": "-timestamp", "first": None, "by": None, "max_rows": None},
        "window": {"start": None, "end": None},
        "series": [
            {
                "station_id": "01975",
                "name": "x",
                "resolution": "daily",
                "dataset": "d",
                "parameter": "a",
                "first": "2026-11-01T00:00:00+00:00",
                "last": "2026-11-10T00:00:00+00:00",
                "searched": 10,
                "expected": 10,
                "gaps": 0,
                "matched": 6,
                "returned": 6,
            }
        ],
        "series_omitted": 0,
        "totals": {"searched": 10, "expected": 10, "gaps": 0, "matched": 6, "returned": 6},
    }
    text = write(rows, [parameter("a", dataset="d")], block=block)

    parsed = assert_round_trip(text, rows)
    assert [r[0] for r in parsed.table("values").rows] == [f"2026-11-{d:02d}" for d in (10, 8, 6, 5, 4, 2)]
    assert [r[1:3] for r in parsed.table("flags").rows] == [["2026-11-05", "2026-11-05"], ["2026-11-04", "2026-11-04"]]
    assert parsed.get("search") == "filter=value<=9 sort=-timestamp"
    assert parsed.get("search_totals") == "searched 10 of 10 expected, gaps 0; matched 6, returned 6"
    assert parsed.table("search series").rows == [
        ["01975", "daily/d/a", "2026-11-01", "2026-11-10", "10", "10", "0", "6", "6"]
    ]


def test_an_empty_answer_is_a_header_with_its_warning_and_no_rows() -> None:
    """No row is an answer: the warning that says why is there, and the end line counts none."""
    block = copy.deepcopy(BLOCK)
    block["warnings"] = [{"code": "parameter-without-rows", "message": "The source has no values for x."}]
    text = write([], [parameter("a")], block=block, stations=[])

    parsed = parse(text)
    assert parsed.tables == []
    assert parsed.end == "rows=0"
    assert parsed.warnings() == [("parameter-without-rows", "The source has no values for x.")]
    assert text.endswith("\n\n# end rows=0\n")


def test_a_wide_frame_is_written_as_the_long_one_with_its_flags_and_null_readings() -> None:
    """The wide shape of a result is turned back to the long one before it is written: the same text either way."""
    from tests.ui.test_restapi import _values_result_of_shape  # noqa: PLC0415

    wide = _values_result_of_shape("wide")
    long_ = wide._long_frame()  # noqa: SLF001

    assert {"station_id", "resolution", "dataset", "parameter", "timestamp", "value", "quality_flags"} <= set(
        long_.columns
    )
    again = wide._long_frame().sort("parameter", "timestamp")  # noqa: SLF001
    assert again.height == long_.height > 0
    assert long_.filter(pl.col("quality_flags").is_not_null()).height >= 0


# --- timestamps, numbers ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "written"),
    [
        (dt.datetime(2026, 11, 10, 4, 0, tzinfo=UTC), "2026-11-10T04:00Z"),
        (dt.datetime(2026, 11, 10, 4, 5, 6, tzinfo=UTC), "2026-11-10T04:05:06Z"),
        (dt.datetime(2026, 11, 10, 4, 5, 6, 250000, tzinfo=UTC), "2026-11-10T04:05:06.25Z"),
        (dt.datetime(2026, 11, 10, 4, 0, tzinfo=dt.timezone(dt.timedelta(hours=2))), "2026-11-10T02:00Z"),
    ],
)
def test_a_timestamp_is_in_utc_with_seconds_only_where_they_are_not_zero(moment: dt.datetime, written: str) -> None:
    """Minutes, a Z; seconds and a fraction only where there are some; any zone is written as UTC."""
    assert compact.stamp(moment) == written


def test_a_table_of_days_has_dates_unless_one_stamp_is_not_midnight() -> None:
    """A daily series stamped at the start of a local day (22:00 UTC) keeps its times: no stamp is read as another."""
    local = [("01975", "daily", "d", "a", day(i) - dt.timedelta(hours=2), float(i), "1") for i in range(1, 4)]
    text = write(local, [parameter("a", dataset="d")])

    assert "2026-11-01T22:00Z,1" in text
    assert_round_trip(text, local)


@pytest.mark.parametrize(
    ("number", "written"),
    [
        (5.0, "5"),
        (0.0, "0"),
        (-0.0, "-0"),
        (4.7, "4.7"),
        (1009.1, "1009.1"),
        (1e-05, "1e-05"),
        (1.5e20, "1.5e+20"),
        (10, "10"),
    ],
)
def test_a_number_is_as_short_as_it_reads_back(number: float, written: str) -> None:
    """A whole number has no `.0`; the rest is the shortest text that reads back as itself."""
    assert compact.number(number) == written
    assert float(written) == number


def test_a_number_in_a_table_is_written_as_the_shortest_text() -> None:
    """The cells of a table of values are the numbers of `compact.number`, whatever polars writes for a float."""
    rows = [
        ("01975", "daily", "d", "a", day(i), v, "1")
        for i, v in enumerate([5.0, 4.7, 1e-05, 123456789.5, 0.1 + 0.2, -3.0])
    ]
    text = write(rows, [parameter("a", dataset="d")])

    assert_round_trip(text, rows)
    assert (
        "2026-11-01,5\n2026-11-02,4.7\n2026-11-03,0.00001\n2026-11-04,123456789.5\n2026-11-05,0.30000000000000004\n2026-11-06,-3\n"
        in text
    )


# --- the header ----------------------------------------------------------------------------------------------------


def test_the_header_says_whose_data_it_is_what_was_done_and_what_is_missing() -> None:
    """Provider, licence with its URL, credit line, source, processing note, clock and producer, in this order."""
    parsed = parse(write([], [], stations=[]))

    assert [key for key, _ in parsed.header] == [
        "provider",
        "license",
        "attribution",
        "source",
        "processing",
        "window",
        "time",
        "retrieved",
        "producer",
        "warnings",
    ]
    assert parsed.get("processing") == BLOCK["processing_note"]


def test_a_provider_without_terms_or_a_credit_line_says_so_and_an_open_window_has_two_dots() -> None:
    """A licence that is not stated is said so; no credit line is `none stated`; a bound that is missing is `..`."""
    block = copy.deepcopy(BLOCK)
    block["provider"].update({"license": None, "attribution": None})
    block["request"].update({"start": None, "end": "2026-11-12T23:59:59.999999+00:00"})
    block["data_updated_at"] = None

    parsed = parse(write([], [], block=block, stations=[]))

    assert parsed.get("license") == "not stated by the provider"
    assert parsed.get("attribution") == "none stated"
    assert parsed.get("window") == "../2026-11-12T23:59:59Z"
    assert parsed.get("retrieved") == "2026-11-25T22:48Z"


def test_a_licence_with_a_name_and_no_identifier_is_named_by_it() -> None:
    """`spdx_id` is null for terms that have none: the name stands, with the URL."""
    block = copy.deepcopy(BLOCK)
    block["provider"]["license"] = {"spdx_id": None, "name": "Custom terms, v2", "url": "https://example.org/terms"}

    assert parse(write([], [], block=block, stations=[])).get("license") == "Custom terms, v2 https://example.org/terms"


def test_with_metadata_adds_the_settings_and_the_tables_of_the_parameters_and_the_flags() -> None:
    """The heavy block becomes a table each; the descriptions of the parameters are not in them."""
    block = copy.deepcopy(BLOCK)
    block["parameters"] = [
        {
            "resolution": "daily",
            "dataset": "d",
            "name": "a",
            "name_original": "A",
            "description": "a very long description " * 50,
            "quantity": "temperature",
            "unit": "°C",
            "aggregation": "mean",
            "timestamp_position": None,
        }
    ]
    block["quality"] = {
        "column": "quality_flags",
        "format": "One string per reading.",
        "source_flags": [
            {"resolution": "daily", "dataset": "d", "name_original": "qn_3", "description": "Quality flag."}
        ],
        "legend": [{"kind": "source", "written": "<code>", "meaning": "The source's own flag, as it writes it."}],
    }
    rows = [("01975", "daily", "d", "a", day(0), 1.0, "1")]
    text = compact.values_text(
        {**block, "counts": {"stations": 1, "rows": 1}},
        frame(rows),
        [STATION],
        block["parameters"],
        settings={"humanize": True, "shape": "long", "unit_targets": {"temperature": "degree_celsius"}, "limits": {}},
    )

    parsed = assert_round_trip(text, rows)
    assert parsed.get("settings") == "humanize=true shape=long"
    assert parsed.get("unit_targets") == "temperature=degree_celsius"
    assert parsed.table("parameters").rows == [["daily/d", "a", "A", "temperature", "°C", "mean", None]]
    assert parsed.table("quality_flags legend").attribute("column") == "quality_flags: One string per reading."
    assert parsed.table("source quality flags").rows == [["daily/d", "qn_3", "Quality flag."]]
    assert "very long" not in text


def _quality_block(provider: str, network: str, datasets: list[str] | None = None) -> dict:
    """Give a block with the `quality` of a network as `with_metadata` writes it: its legend and its note."""
    from wetterdienst.model.quality_legend import quality_legend, source_flag_note  # noqa: PLC0415

    block = copy.deepcopy(BLOCK)
    block["quality"] = {
        "column": "quality_flags",
        "format": "One string per reading.",
        "source_flags": [],
        "legend": [entry.model_dump(mode="json") for entry in quality_legend(provider, network, datasets)],
        "source_flag_note": source_flag_note(provider, network),
    }
    return block


def test_the_note_of_a_source_flag_the_library_does_not_carry_is_an_attribute_of_the_legend() -> None:
    """`dwd/mosmix` has no flag of the source: the JSON says so in `source_flag_note`, and so does the text."""
    block = _quality_block("dwd", "mosmix")
    assert block["quality"]["source_flag_note"]

    parsed = parse(write([], [], block=block, stations=[]))
    legend = parsed.table("quality_flags legend")

    assert legend.attribute("source_flag_note") == block["quality"]["source_flag_note"]
    assert [row[0] for row in legend.rows] == [e["kind"] for e in block["quality"]["legend"]]
    assert "codes" not in parsed.tables[-1].heading


def test_a_network_that_carries_a_flag_of_the_source_has_no_note_and_its_codes_are_a_table() -> None:
    """DWD's QN levels are the codes of the source's own flag: a row each, with the kind empty for that flag."""
    block = _quality_block("dwd", "observation", ["daily/climate_summary"])
    assert block["quality"]["source_flag_note"] is None
    expected = [(c["code"], c["meaning"]) for e in block["quality"]["legend"] if e["kind"] is None for c in e["codes"]]
    assert expected

    parsed = parse(write([], [], block=block, stations=[]))

    assert parsed.table("quality_flags legend").attribute("source_flag_note") is None
    codes = parsed.table("quality_flags codes")
    assert codes.columns == ["kind", "code", "meaning"]
    assert [(row[1], row[2]) for row in codes.rows if row[0] is None] == expected
    documented = [e for e in block["quality"]["legend"] if e.get("documentation")]
    legend = parsed.table("quality_flags legend")
    assert [row[3] for row in legend.rows if row[3]] == [e["documentation"] for e in documented]


# --- hostile text --------------------------------------------------------------------------------------------------


NASTY = [
    "Hamburg-Fuhlsbüttel",
    "Hamburg, Stadt",
    'Say "hi"',
    "line1\nline2",
    "# warnings: none",
    "\n# warnings: none",
    "## values hourly/x station=evil",
    "# end rows=0",
    "@2026-01-01",
    " leading space",
    "trailing space ",
    "back\\slash",
    "back\\nslash",
    "tab\there",
    "pipe|char",
    "-",
    "",
    "end rows=0",
    "key: value",
    '"',
    '"quoted"',
    "x\r\ny",
    "carriage\rreturn",
    "next\x85line",
    "line\u2028separator",
    "paragraph\u2029separator",
    "vertical\x0btab",
    "form\x0cfeed",
    "file\x1cseparator",
    "group\x1dseparator",
    "record\x1eseparator",
    "nul\x00char",
    "delete\x7fchar",
    "ünï ©öde ☃",
    "astral \U0001f600 \U000e0001",
    "01975,evil,53.0,9.0,1,Hamburg",
    ",",
    ",,",
]


def structural(text: str) -> list[str]:
    """Give the lines of a text that begin a structure: a `#` or a `##`."""
    return [line for line in text.split("\n") if line.startswith("#")]


@pytest.mark.parametrize("hostile", NASTY)
def test_no_text_of_an_answer_forges_a_line_of_it(hostile: str) -> None:
    """A name, a warning, a credit line, a licence and a station id come back as the text they are, and add no line.

    The lines that begin with `#` are the first line, the header (counted), the headings, the attributes and the end
    line, whatever the text says; and the text is one line of the header, a cell, or a word of a heading.
    """
    block = copy.deepcopy(BLOCK)
    block["provider"].update(
        {
            "name_english": hostile,
            "attribution": hostile,
            "license": {"spdx_id": None, "name": hostile, "url": "https://example.org/terms"},
            "url": hostile,
        }
    )
    block["processing_note"] = hostile
    block["warnings"] = [{"code": hostile, "message": hostile, "parameter": hostile, "stations": [hostile]}]
    station = {**STATION, "station_id": hostile or "x", "name": hostile, "region": hostile}
    rows = [
        (hostile or "x", "daily", "d", "a", day(0), 1.5, hostile or None),
        (hostile or "x", "daily", "d", "a", day(1), 2.5, "1"),
    ]
    text = compact.values_text(
        {**block, "counts": {"stations": 1, "rows": 2}},
        frame(rows),
        [station],
        [parameter("a", dataset="d")],
        settings={"humanize": hostile},
    )

    parsed = parse(text)
    # every line that starts a structure is one the grammar knows: the first line, the header, headings, attributes, end
    assert len(parsed.header) == len(text.split("\n\n")[0].split("\n")[1:])
    assert parsed.get("attribution") == (hostile or "none stated")
    assert parsed.get("processing") == hostile
    assert parsed.get("source") == hostile
    assert parsed.get("provider") == f"{hostile} (dwd/observation)"
    assert parsed.get("license") == f"{hostile} https://example.org/terms"
    assert len(parsed.warnings()) == 1
    assert parsed.warnings()[0][1].startswith(hostile)
    assert [t.heading.split(" ")[0] for t in parsed.tables] == ["stations", "values", "flags"]
    assert parsed.table("stations").rows[0][1] == hostile
    assert values(parsed)[(hostile or "x", "daily", "d", "a", day(0))] == (1.5, hostile or None)
    # no free text made a line of its own: the lines that start with `#` are the format's
    heads = structural(text)
    assert sum(1 for line in heads if line.startswith("## ")) == 3
    assert sum(1 for line in heads if line.startswith("# end ")) == 1
    assert sum(1 for line in heads if line.startswith("# wetterdienst-compact/")) == 1
    assert text.splitlines() == text.split("\n")[:-1]


def test_a_name_that_holds_a_forged_header_stays_one_cell() -> None:
    """The case of the issue: a station named with a newline and `# warnings: none` is one cell, quoted."""
    station = {**STATION, "name": "Evil\n# warnings: none\n## stations"}
    text = write([], [], stations=[station])

    assert '"Evil\\n# warnings: none\\n## stations"' in text
    parsed = parse(text)
    assert parsed.table("stations").rows[0][1] == "Evil\n# warnings: none\n## stations"
    assert parsed.get("warnings") == "none"
    assert parsed.warnings() == []


@pytest.mark.parametrize("seed", range(8))
def test_a_random_answer_with_hostile_names_reads_back_exactly(seed: int) -> None:
    """Random stations, datasets, parameters, times, nulls and flags (and a random order) come back as they went in."""
    rnd = random.Random(4445 + seed)  # noqa: S311 - a seeded test of a format, no secret
    flags_pool = [
        None,
        "1",
        "3",
        "1,raw:-999",
        "9,suspect:range",
        "a b",
        'q"uote',
        "back\\slash",
        "a,b,c",
        "x=y",
        "# not a line",
    ]
    names = ["alpha", "b,eta", 'ga"mma', "del ta", "#epsilon", "z\neta"]
    rows: list[tuple[Any, ...]] = []
    parameters = []
    stations = []
    for station_id in rnd.sample(["00001", "01975", "04411", "a b", 'q"s', "x,y", "# s", "é"], rnd.randint(1, 4)):
        stations.append({**STATION, "station_id": station_id, "name": rnd.choice(NASTY)})
        for resolution, dataset in rnd.sample(
            [("daily", "kl"), ("hourly", "air"), ("hourly", "wind"), ("monthly", "m")], 2
        ):
            chosen = rnd.sample(names, rnd.randint(1, 4))
            unit = rnd.choice(["°C", "%", "m/s", "sign [0..95]", "x,y"])
            default = rnd.choice(flags_pool)
            for name in chosen:
                if not any(p["name"] == name and p["dataset"] == dataset for p in parameters):
                    parameters.append(parameter(name, resolution, dataset, unit))
                stamps = rnd.sample(range(40), rnd.randint(1, 30))
                for step in sorted(stamps):
                    moment = hour(step) if resolution == "hourly" else day(step)
                    reading = None if rnd.random() < 0.2 else rnd.choice([0.0, 1.5, -3.25, 1e-07, 12345.678, 7.0])
                    flags = default if rnd.random() < 0.8 else rnd.choice(flags_pool)
                    rows.append((station_id, resolution, dataset, name, moment, reading, flags))
    if rnd.random() < 0.5:
        rnd.shuffle(rows)
    block = copy.deepcopy(BLOCK)
    block["search"] = (
        {
            "options": {"filter": None, "sort": "-timestamp", "first": None, "by": None, "max_rows": None},
            "window": {"start": None, "end": None},
            "series": [],
            "series_omitted": 0,
            "totals": {"searched": 1, "expected": None, "gaps": None, "matched": 1, "returned": 1},
        }
        if rnd.random() < 0.5
        else None
    )
    # the same station, resolution, dataset and parameter has one reading a timestamp
    seen = {}
    for row in rows:
        seen[row[:5]] = row
    rows = list(seen.values())
    text = write(rows, parameters, block=block, stations=stations)

    parsed = assert_round_trip(text, rows)
    assert [r[0] for r in parsed.table("stations").rows] == list(dict.fromkeys(s["station_id"] for s in stations))
    for table in parsed.tables:
        if table.heading.startswith("values "):
            heading_of(table.heading)


def test_the_reader_refuses_what_a_writer_must_never_make() -> None:
    """Held so that the tests above can fail: a forged structure, a loose line and a short row are refused."""
    good = write([("01975", "daily", "d", "a", day(0), 1.0, "1")], [parameter("a", dataset="d")])
    parse(good)

    for bad in (
        good.replace("# end rows=1\n", ""),
        good.replace("2026-11-01,1\n", "2026-11-01\n"),
        good.replace("# time: UTC\n", "# time: UTC\n## stations\n"),
        good.replace("# time: UTC", "time: UTC"),
        good.replace("# time: UTC\n", "# time: UTC\u2028# warnings: none\n"),
        good.replace("2026-11-01,1\n", "2026-11-01,1\n# 2026-11-02,3\n"),
    ):
        with pytest.raises(FormatError):
            parse(bad)


def test_text_is_bare_where_it_reads_back_and_a_json_string_where_it_would_not() -> None:
    """The rules of `cell` and `text_value`: what a line may hold bare, and what it quotes."""
    assert [
        compact.cell(x)
        for x in ["a", "a b", "ü", "", " a", "a ", "#a", "a,b", 'a"b', "a\\b", "a\tb", "-", None, 1.0, 2]
    ] == [
        "a",
        "a b",
        "ü",
        '""',
        '" a"',
        '"a "',
        '"#a"',
        '"a,b"',
        '"a\\"b"',
        '"a\\\\b"',
        '"a\\tb"',
        "-",
        "",
        "1",
        "2",
    ]
    assert [compact.text_value(x) for x in ["a, b", "a:b", "", '"a', "a\nb", "# x"]] == [
        "a, b",
        "a:b",
        '""',
        '"\\"a"',
        '"a\\nb"',
        "# x",
    ]
    assert compact.quote("a\u2028b\x85c\U0001f600\U000e0001") == '"a\\u2028b\\u0085c\U0001f600\\udb40\\udc01"'
    assert compact.token("a b") == '"a b"'
    assert compact.token("01975") == "01975"


# --- real answers --------------------------------------------------------------------------------------------------

REAL = Path(__file__).parent / "compact_real"
#: the answers of the hosted instance the design was studied on (2026-11-25), cut to what the format reads: the metadata
#: block (the units are its `parameters`), the stations and the rows; `many_parameters_with_nulls` is nine days of 14
#: parameters with the readings the source marked missing kept (`drop_nulls=false`), `three_stations` and
#: `two_datasets` are small, `forecast` is MOSMIX, `row_options` a `filter` and a `sort`, `empty` a day with no reading
_REAL_ANSWERS = json.loads((REAL / "answers.json").read_text(encoding="utf-8"))


def _real_text(name: str) -> tuple[str, list[tuple[Any, ...]]]:
    """Write a real answer as the writer does, and give the rows of it."""
    answer = _REAL_ANSWERS[name]
    meta = answer["metadata"]
    rows = [
        (
            r["station_id"],
            r["resolution"],
            r["dataset"],
            r["parameter"],
            dt.datetime.fromisoformat(r["timestamp"]),
            r["value"],
            r["quality_flags"],
        )
        for r in answer["values"]
    ]
    block = {key: value for key, value in meta.items() if key != "parameters"}
    return compact.values_text(block, frame(rows), answer["stations"], meta["parameters"]), rows


@pytest.mark.parametrize("name", list(_REAL_ANSWERS))
def test_a_real_answer_is_written_and_read_back_to_its_readings_and_flags(name: str) -> None:
    """Every real answer of the study: a series, many parameters with nulls, stations, datasets, a forecast, rows."""
    text, rows = _real_text(name)

    parsed = assert_round_trip(text, rows)
    assert parsed.get("license") == "CC-BY-4.0 https://creativecommons.org/licenses/by/4.0/"


@pytest.mark.parametrize("name", ["one_series", "many_parameters_with_nulls", "row_options", "empty", "forecast"])
def test_a_real_answer_is_the_text_of_its_golden_file(name: str) -> None:
    """The first, second and fifth example of the study, byte for byte, and two more: a refactor changes none."""
    text, _ = _real_text(name)

    assert text == (REAL / f"{name}.txt").read_text(encoding="utf-8")


def test_the_real_answers_are_a_fraction_of_their_json() -> None:
    """The sizes the study measured, on the slices the fixture holds: a fifth of the JSON of the rows or less."""
    for name, answer in _REAL_ANSWERS.items():
        text, rows = _real_text(name)
        json_size = len(json.dumps(answer["values"], separators=(",", ":"), ensure_ascii=False))
        if len(rows) >= 100:
            assert len(text) < json_size / 5, name


def test_a_lone_surrogate_in_a_header_text_is_written_as_an_escape_and_the_text_encodes() -> None:
    """A text that is no valid UTF-8 (a lone surrogate) is an escape of the line, so the answer encodes."""
    block = copy.deepcopy(BLOCK)
    block["warnings"] = [{"code": "station-skipped", "message": "bad \ud800 text"}]

    text = write([], [], block=block, stations=[])

    assert text.encode("utf-8")
    assert parse(text).warnings() == [("station-skipped", "bad \ud800 text")]
    assert compact.quote("𐏿") == '"\\ud800\\udfff"'


def test_a_sorted_answer_of_several_parameters_has_a_table_for_each_in_the_order_of_the_answer() -> None:
    """The rows of `sort=-timestamp` are in order per parameter, not per timestamp: one table each keeps the order."""
    rows = [("01975", "daily", "d", "a", day(i), float(i), "1") for i in (9, 7, 5)]
    rows += [("01975", "daily", "d", "b", day(i), float(i), "1") for i in (8, 7, 2)]
    block = copy.deepcopy(BLOCK)
    block["search"] = {
        "options": {"filter": None, "sort": "-timestamp", "first": None, "by": None, "max_rows": None},
        "window": {"start": None, "end": None},
        "series": [],
        "series_omitted": 0,
        "totals": {"searched": 6, "expected": None, "gaps": None, "matched": 6, "returned": 6},
    }
    text = write(rows, [parameter(name, dataset="d") for name in "ab"], block=block)

    parsed = assert_round_trip(text, rows)
    assert [t.heading for t in parsed.tables if t.heading.startswith("values ")] == [
        "values daily/d station=01975 parameter=a",
        "values daily/d station=01975 parameter=b",
    ]
    assert [row[0] for row in parsed.table("values daily/d station=01975 parameter=b").rows] == [
        "2026-11-09",
        "2026-11-08",
        "2026-11-03",
    ]
    assert text.count("search_totals") == 1


def test_a_table_with_seconds_or_a_fraction_in_its_stamps_writes_them_and_none_is_read_as_another() -> None:
    """Minutes only where all stamps are on the minute, seconds where one is not, a fraction where there is one."""
    seconds = [dt.datetime(2026, 11, 10, 0, 0, 30, tzinfo=UTC), dt.datetime(2026, 11, 10, 1, 0, 0, tzinfo=UTC)]
    fraction = [dt.datetime(2026, 11, 10, 0, 0, 0, 500000, tzinfo=UTC), dt.datetime(2026, 11, 10, 1, 0, tzinfo=UTC)]
    on_the_minute = [dt.datetime(2026, 11, 10, 0, 1, tzinfo=UTC), dt.datetime(2026, 11, 10, 1, 0, tzinfo=UTC)]
    # all at midnight but for the seconds of one: a table of whole days has no seconds
    midnight = [dt.datetime(2026, 11, 10, 0, 0, 30, tzinfo=UTC), dt.datetime(2026, 11, 11, 0, 0, tzinfo=UTC)]
    expected = {
        "midnight": ["2026-11-10T00:00:30Z", "2026-11-11T00:00Z"],
        "seconds": ["2026-11-10T00:00:30Z", "2026-11-10T01:00Z"],
        "fraction": ["2026-11-10T00:00:00.5Z", "2026-11-10T01:00Z"],
        "minute": ["2026-11-10T00:01Z", "2026-11-10T01:00Z"],
    }

    for name, stamps in (
        ("seconds", seconds),
        ("fraction", fraction),
        ("minute", on_the_minute),
        ("midnight", midnight),
    ):
        rows = [("01975", "minute_1", "d", "a", moment, float(i), "1") for i, moment in enumerate(stamps)]
        text = write(rows, [parameter("a", "minute_1", "d")])

        assert_round_trip(text, rows)
        assert [row[0] for row in parse(text).table("values").rows] == expected[name], name


@pytest.mark.parametrize(
    ("resolution", "written"),
    [
        ("daily", ["2026-11-10", "2026-11-11"]),
        ("monthly", ["2026-11-10", "2026-11-11"]),
        ("annual", ["2026-11-10", "2026-11-11"]),
        ("hourly", ["2026-11-10T00:00Z", "2026-11-11T00:00Z"]),
        ("minute_10", ["2026-11-10T00:00Z", "2026-11-11T00:00Z"]),
        ("minute_1", ["2026-11-10T00:00Z", "2026-11-11T00:00Z"]),
    ],
)
def test_midnight_is_a_date_only_where_the_resolution_is_whole_days(resolution: str, written: list[str]) -> None:
    """An hourly table whose rows are all at 00:00 (`first=1`) keeps its times: a date would read as a daily value."""
    rows = [("01975", resolution, "d", "a", day(9 + i), float(i), "1" if i else "2") for i in range(2)]
    text = write(rows, [parameter("a", resolution, "d")])

    parsed = assert_round_trip(text, rows)
    assert [row[0] for row in parsed.table("values").rows] == written
    # the table of flags writes its periods as the table writes its stamps
    assert [row[1] for row in parsed.table("flags").rows] == [written[1]]


def test_the_series_a_search_reports_have_dates_where_the_resolution_is_whole_days_and_times_where_it_is_not() -> None:
    """`first` and `last` of the search table follow the rule of the tables: an hourly series starts at 00:00."""
    block = copy.deepcopy(BLOCK)
    series = {
        "station_id": "01975",
        "name": "x",
        "dataset": "d",
        "parameter": "a",
        "searched": 2,
        "expected": 2,
        "gaps": 0,
        "matched": 2,
        "returned": 2,
    }
    block["search"] = {
        "options": {"filter": None, "sort": None, "first": 1, "by": None, "max_rows": None},
        "window": {"start": None, "end": None},
        "series": [
            {
                **series,
                "resolution": "daily",
                "first": "2026-11-10T00:00:00+00:00",
                "last": "2026-11-11T00:00:00+00:00",
            },
            {
                **series,
                "resolution": "hourly",
                "first": "2026-11-10T00:00:00+00:00",
                "last": "2026-11-11T05:00:00+00:00",
            },
            {**series, "resolution": "hourly", "first": None, "last": None},
        ],
        "series_omitted": 0,
        "totals": {"searched": 6, "expected": 6, "gaps": 0, "matched": 6, "returned": 6},
    }

    parsed = parse(write([], [], block=block, stations=[]))

    assert [row[2:4] for row in parsed.table("search series").rows] == [
        ["2026-11-10", "2026-11-11"],
        ["2026-11-10T00:00Z", "2026-11-11T05:00Z"],
        [None, None],
    ]


def test_a_unit_the_lookup_does_not_find_is_a_question_mark_and_the_parameter_is_the_text_before_the_bracket() -> None:
    """A column without a unit is `(?)`, and both readers split at the first bracket."""
    rows = [("01975", "daily", "d", "a", day(0), 1.0, "1"), ("01975", "daily", "d", "b", day(0), 2.0, "1")]
    text = write(rows, [parameter("a", dataset="d")])

    parsed = assert_round_trip(text, rows)
    assert parsed.table("values").columns == ["timestamp", "a(°C)", "b(?)"]
    assert compact_reader.name_of("b(?)") == "b"
    assert compact_reader.name_of("sunshine(m s-1 (x))") == "sunshine"
    assert compact_reader.name_of("plain") == "plain"


def test_a_ranking_of_several_stations_is_one_table_in_the_order_of_the_answer_with_flags_of_a_station() -> None:
    """Readings of two stations ranked by value stay interleaved; a period of flags names its station."""
    rows = [
        ("00002", "daily", "d", "a", day(3), 9.0, "1"),
        ("00001", "daily", "d", "a", day(5), 8.0, "1,suspect:range"),
        ("00002", "daily", "d", "a", day(5), 7.0, "1"),
        ("00001", "daily", "d", "a", day(3), 6.0, "1"),
    ]
    block = copy.deepcopy(BLOCK)
    block["search"] = {
        "options": {"filter": None, "sort": "-value", "first": 2, "by": "none", "max_rows": None},
        "window": {"start": None, "end": None},
        "series": [],
        "series_omitted": 0,
        "totals": {"searched": 4, "expected": None, "gaps": None, "matched": 4, "returned": 4},
    }
    text = write(rows, [parameter("a", dataset="d")], block=block)

    parsed = assert_round_trip(text, rows)
    assert [t.heading for t in parsed.tables if t.heading.startswith(("values", "flags"))] == [
        "values daily/d",
        "flags daily/d (exceptions)",
    ]
    table = parsed.table("values daily/d")
    assert table.columns == ["station_id", "timestamp", "a(°C)"]
    assert [row[:2] for row in table.rows] == [
        ["00002", "2026-11-04"],
        ["00001", "2026-11-06"],
        ["00002", "2026-11-06"],
        ["00001", "2026-11-04"],
    ]
    assert table.attribute("flags") == "1 (periods that differ are listed after the table)"
    assert parsed.table("flags").columns == ["station_id", "columns", "from", "to", "flags"]
    assert parsed.table("flags").rows == [["00001", "all", "2026-11-06", "2026-11-06", "1,suspect:range"]]
    assert [(who, moment.day) for who, _, _, _, moment in compact_reader.readings_in_order(parsed)] == [
        ("00002", 4),
        ("00001", 6),
        ("00002", 6),
        ("00001", 4),
    ]
