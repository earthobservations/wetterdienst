# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the result of the thunderstorm cells: the dict, GeoJSON and CSV it renders, and the files it writes."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.exceptions import ExportRefusedError, UnknownFormatError
from wetterdienst.provider.dwd.storm_cells import DwdStormCellsRequest, DwdStormCellsResult
from wetterdienst.provider.dwd.storm_cells.api import _SCHEMA
from wetterdienst.provider.dwd.storm_cells.metadata import STORM_CELLS_NOTE

from .stubs import EMPTY_SCAN, TWO_CELLS_SCAN, parts_scan, serve

if TYPE_CHECKING:
    from pathlib import Path

UTC = ZoneInfo("UTC")
NEWEST = "KONRAD3D_20261117T221500.xml"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 11, 17, 22, 20, tzinfo=UTC)
    )


def _result(monkeypatch: pytest.MonkeyPatch, scan: bytes = TWO_CELLS_SCAN, **arguments: object) -> DwdStormCellsResult:
    serve(monkeypatch, {NEWEST: scan})
    return DwdStormCellsRequest(**arguments).query()  # ty: ignore[invalid-argument-type]


def test_to_dict_has_the_reference_time_and_the_cells_nested(monkeypatch: pytest.MonkeyPatch) -> None:
    """`{"reference_time": ..., "cells": [...]}`: a cell has its outline decoded, its track a list, its times text."""
    data = _result(monkeypatch).to_dict()

    assert list(data) == ["reference_time", "cells"]
    assert data["reference_time"] == "2026-11-17T22:15:00.000000+00:00"
    cell = data["cells"][0]
    assert cell["geometry"]["type"] == "Polygon"
    assert cell["first_detection"] == "2026-11-17T22:15:00.000000+00:00"
    assert len(cell["track"]) == 12
    assert cell["track"][0]["time"] == "2026-11-17T22:20:00.000000+00:00"
    assert set(cell["track"][0]) == {
        "time",
        "latitude",
        "longitude",
        "uncertainty_major_km",
        "uncertainty_minor_km",
        "uncertainty_angle_degrees",
    }


def test_to_dict_of_an_empty_scan_says_when(monkeypatch: pytest.MonkeyPatch) -> None:
    """No cell is `[]`, and the answer has the time of the scan that it is true of."""
    data = _result(monkeypatch, EMPTY_SCAN).to_dict()

    assert data == {"reference_time": "2026-11-15T22:20:00.000000+00:00", "cells": []}


def test_with_metadata_puts_the_block_first_and_names_what_was_calculated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Licence, credit line and the date of the data (when DWD wrote the file); the note names what is calculated."""
    data = _result(monkeypatch).to_dict(with_metadata=True)

    assert list(data) == ["metadata", "reference_time", "cells"]
    metadata = data["metadata"]
    assert metadata["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert metadata["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert metadata["data_updated_at"] == "2026-11-17T22:19:44.000000+00:00"
    assert metadata["processing_note"].endswith(STORM_CELLS_NOTE)
    assert "direction_degrees` is calculated" in metadata["processing_note"]
    assert "track` is DWD's forecast" in metadata["processing_note"]


def test_the_feature_collection_has_the_outline_as_its_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `Feature` for each cell, with the outline as its geometry and the other columns as its properties."""
    collection = _result(monkeypatch).to_ogc_feature_collection()

    assert list(collection) == ["type", "reference_time", "features"]
    assert collection["type"] == "FeatureCollection"
    feature = collection["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["geometry"]["coordinates"][0][0] == feature["geometry"]["coordinates"][0][-1]
    assert "geometry" not in feature["properties"]
    assert feature["properties"]["cell_id"] == "5"
    assert len(feature["properties"]["track"]) == 12


def test_the_block_is_a_foreign_member_of_the_feature_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    """After `type`, as the REST API and the alerts have it (RFC 7946, 6.1)."""
    collection = _result(monkeypatch).to_ogc_feature_collection(with_metadata=True)

    assert list(collection) == ["type", "metadata", "reference_time", "features"]


def test_a_cell_in_parts_is_a_multipolygon_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    """The outline of a cell that fell apart into two parts."""
    features = _result(monkeypatch, parts_scan()).to_ogc_feature_collection()["features"]

    assert [feature["geometry"]["type"] for feature in features] == ["MultiPolygon", "Polygon"]


def test_the_geometry_of_a_centre_is_a_point_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    """`geometry="centroid"`: a point, of longitude and latitude."""
    feature = _result(monkeypatch, geometry="centroid").to_ogc_feature_collection()["features"][0]

    assert feature["geometry"] == {"type": "Point", "coordinates": [6.90482, 49.05082]}


def test_json_is_one_line_unless_indented(monkeypatch: pytest.MonkeyPatch) -> None:
    """As the alerts: compact by default, `indent` a number of spaces or `True` for 4."""
    result = _result(monkeypatch)

    assert "\n" not in result.to_json()
    assert result.to_json(True).startswith('{\n    "reference_time"')  # noqa: FBT003
    assert json.loads(result.to_json(2)) == result.to_dict()
    assert json.loads(result.to_geojson())["type"] == "FeatureCollection"


def test_csv_is_a_row_a_cell_with_the_nested_columns_as_json_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Times are ISO strings, the geometry GeoJSON text and the track a JSON list, in a column each."""
    rows = list(csv.DictReader(io.StringIO(_result(monkeypatch).to_csv())))

    assert [row["cell_id"] for row in rows] == ["5", "53"]
    first = rows[0]
    assert first["reference_time"] == "2026-11-17T22:15:00.000000+00:00"
    assert first["severity_label"] == "moderate"
    assert json.loads(first["geometry"])["type"] == "Polygon"
    track = json.loads(first["track"])
    assert len(track) == 12
    assert track[0]["time"] == "2026-11-17T22:20:00.000000+00:00"
    assert first["predecessor_code"] == ""


def test_csv_without_the_track_has_no_such_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """The column is left out of the frame, and so of the file."""
    header = _result(monkeypatch, track=False).to_csv().splitlines()[0].split(",")

    assert "track" not in header
    assert header[-1] == "geometry"


def test_csv_of_an_empty_scan_is_the_header_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """No cell is the header of every column, so a reader of the file finds its columns."""
    text = _result(monkeypatch, EMPTY_SCAN).to_csv()

    assert text.count("\n") == 1
    assert text.split(",")[0] == "reference_time"
    assert text.strip().split(",")[-2:] == ["geometry", "track"]


@pytest.mark.parametrize(("fmt", "method"), [("json", "to_json"), ("GeoJSON", "to_geojson"), ("CSV", "to_csv")])
def test_to_format_takes_the_format_in_any_case(monkeypatch: pytest.MonkeyPatch, fmt: str, method: str) -> None:
    """json, geojson or csv, as the alerts result renders them."""
    result = _result(monkeypatch)

    assert result.to_format(fmt) == getattr(result, method)()


def test_to_format_refuses_a_format_it_has_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """The formats it has are named."""
    with pytest.raises(UnknownFormatError, match="json"):
        _result(monkeypatch).to_format("parquet")


def test_to_format_refuses_an_argument_no_format_takes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mistyped argument is no silent default."""
    with pytest.raises(TypeError):
        _result(monkeypatch).to_format("json", with_metdata=True)


def test_the_empty_frame_of_the_schema_has_every_column() -> None:
    """The columns of an empty result are those of one with cells."""
    result = DwdStormCellsResult(pl.DataFrame(schema=_SCHEMA), None)

    assert result.to_dict() == {"reference_time": None, "cells": []}
    assert result.to_ogc_feature_collection()["features"] == []


# --- to a file ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["cells.json", "cells.geojson", "cells.csv"])
def test_to_target_writes_what_the_rest_api_answers_for_the_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    """The file of the extension holds the answer of `render_storm_cells`, the JSON formats with the block."""
    from wetterdienst.ui.render import render_storm_cells  # noqa: PLC0415

    result = _result(monkeypatch)
    target = tmp_path / name

    result.to_target(f"file://{target}")

    fmt = name.rsplit(".", 1)[1]
    written = target.read_text(encoding="utf8")
    answered = render_storm_cells(result, fmt)[0]
    if fmt == "csv":
        assert written == answered
        return
    # the block says when it was made, which differs between two renderings
    written_data, answered_data = json.loads(written), json.loads(answered)
    for data in (written_data, answered_data):
        data["metadata"]["retrieved_at"] = ""
    assert written_data == answered_data
    assert written_data["metadata"]["provider"]["license"]["spdx_id"] == "CC-BY-4.0"


def test_to_target_writes_an_empty_scan_as_it_is(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A file that a schedule rewrites must not keep the cells of the run before."""
    target = tmp_path / "cells.json"
    target.write_text("old")

    _result(monkeypatch, EMPTY_SCAN).to_target(f"file://{target}")

    data = json.loads(target.read_text(encoding="utf8"))
    assert data["cells"] == []
    assert data["reference_time"] == "2026-11-15T22:20:00.000000+00:00"


def test_to_target_pretty_indents_the_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`pretty` is 4 spaces."""
    target = tmp_path / "cells.json"

    _result(monkeypatch).to_target(f"file://{target}", pretty=True)

    assert '\n    "reference_time"' in target.read_text(encoding="utf8")


def test_to_target_with_metadata_writes_the_block_beside_the_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A CSV file has no place for the block: `<file>.metadata.json` holds what `/api/storm-cells` answers with."""
    target = tmp_path / "cells.csv"

    _result(monkeypatch).to_target(f"file://{target}", with_metadata=True)

    block = json.loads((tmp_path / "cells.csv.metadata.json").read_text(encoding="utf8"))
    assert block["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert block["request"]["network"] == "storm_cells"
    assert block["counts"]["rows"] == 2
    assert block["data_updated_at"] == "2026-11-17T22:19:44.000000+00:00"
    assert STORM_CELLS_NOTE in block["processing_note"]


@pytest.mark.parametrize("target", ["duckdb:///x.duckdb?table=t", "sqlite:///x.sqlite?table=t"])
def test_to_target_refuses_a_database(monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    """A cell has an outline and a track, and there is no table for it."""
    with pytest.raises(ExportRefusedError, match="file only"):
        _result(monkeypatch).to_target(target)


def test_to_target_refuses_another_file_type_and_append(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The three the result is written as are named; a file takes no `append`."""
    result = _result(monkeypatch)

    with pytest.raises(ExportRefusedError, match=r"\.json, \.geojson, \.csv|json"):
        result.to_target(f"file://{tmp_path / 'cells.parquet'}")
    with pytest.raises(ExportRefusedError, match="Append"):
        result.to_target(f"file://{tmp_path / 'cells.json'}", if_exists="append")


def test_to_target_fail_and_skip_leave_a_file_that_is_there(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`fail` refuses, `skip` writes nothing."""
    target = tmp_path / "cells.json"
    target.write_text("kept")
    result = _result(monkeypatch)

    with pytest.raises(ExportRefusedError):
        result.to_target(f"file://{target}", if_exists="fail")
    result.to_target(f"file://{target}", if_exists="skip")

    assert target.read_text() == "kept"
