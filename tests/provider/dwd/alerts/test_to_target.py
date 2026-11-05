# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Offline tests for `DwdWeatherAlertResult.to_target`: the alerts written to JSON, GeoJSON and CSV files (GH-3706).

The alerts are CAP documents of the DWD profile, parsed by the reader that `query` uses, so the files hold what a
snapshot gives.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import logging
import zipfile
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.dwd.alerts.test_api import _URL, _make_zip
from tests.provider.dwd.alerts.test_parser import CAP_XML
from wetterdienst.exceptions import ExportRefusedError
from wetterdienst.provider.dwd.alerts import (
    DwdWeatherAlertGranularity,
    DwdWeatherAlertLanguage,
    DwdWeatherAlertRequest,
    DwdWeatherAlertResult,
)
from wetterdienst.provider.dwd.alerts.api import _SCHEMA
from wetterdienst.util.response_warnings import begin_response, warn_response

if TYPE_CHECKING:
    from pathlib import Path

UTC = ZoneInfo("UTC")
SNAPSHOT = dt.datetime(2026, 7, 26, 8, 0, tzinfo=UTC)

# A second warning: a German `<info>` first and an English one after it (what the `mul` product bundles), three entity
# areas and no polygon, so that it has no geometry. The identifier and the event differ from `CAP_XML`'s.
_SECOND_INFO = b"""<info>
    <language>en</language>
    <category>Met</category>
    <event>FROST</event>
    <urgency>Immediate</urgency>
    <severity>Minor</severity>
    <certainty>Likely</certainty>
    <eventCode><valueName>II</valueName><value>22</value></eventCode>
    <eventCode><valueName>GROUP</valueName><value>FROST</value></eventCode>
    <area><areaDesc>Stadt Passau</areaDesc></area>
  </info>"""
CAP_TWO_INFOS = (
    CAP_XML.replace(b".6bd1534c-24c8-4860-84a8-e89bab416fcd.ENG<", b".11111111-2222-3333-4444-555555555555.MUL<")
    .replace(b"<event>gale-force gusts</event>", b"<event>Frost</event>")
    .replace(b"<language>en</language>", b"<language>de</language>")
    .replace(b"</info>", b"</info>\n  " + _SECOND_INFO)
    .replace(
        b"""<area>
      <areaDesc>polygonal event area</areaDesc>
      <polygon>49.0,12.0 49.0,13.0 50.0,13.0 50.0,12.0 49.0,12.0</polygon>
      <geocode>
        <valueName>EXCLUDE_POLYGON</valueName>
        <value>49.4,12.4 49.4,12.6 49.6,12.6 49.6,12.4 49.4,12.4</value>
      </geocode>
    </area>
    """,
        b"""<area>
      <areaDesc>Stadt Hof</areaDesc>
      <geocode><valueName>WARNCELLID</valueName><value>809464000</value></geocode>
    </area>
    """,
    )
)


def _result(*documents: bytes, snapshot: dt.datetime | None = SNAPSHOT) -> DwdWeatherAlertResult:
    """Parse the CAP documents as `query` does and wrap them in the result of a community, English request."""
    alerts = DwdWeatherAlertRequest._parse_archive(_make_zip(*documents), _URL)  # noqa: SLF001
    df = DwdWeatherAlertRequest._build_dataframe(alerts)  # noqa: SLF001
    return DwdWeatherAlertResult(df, DwdWeatherAlertGranularity.COMMUNITY, DwdWeatherAlertLanguage.ENGLISH, snapshot)


def _empty() -> DwdWeatherAlertResult:
    """Make the result of a snapshot that holds no warning: DWD's archive of 22 bytes, an end of central directory."""
    buffer = io.BytesIO()
    zipfile.ZipFile(buffer, "w").close()
    buffer.seek(0)
    alerts = DwdWeatherAlertRequest._parse_archive(buffer, _URL)  # noqa: SLF001
    df = DwdWeatherAlertRequest._build_dataframe(alerts)  # noqa: SLF001
    return DwdWeatherAlertResult(df, DwdWeatherAlertGranularity.COMMUNITY, DwdWeatherAlertLanguage.ENGLISH, SNAPSHOT)


def _read_csv(path: Path) -> pl.DataFrame:
    """Read the CSV file with every column as text, so that nothing is turned into another type on the way in."""
    return pl.read_csv(path, infer_schema=False)


# --- JSON and GeoJSON -------------------------------------------------------------------------------------------------


def test_a_json_file_holds_what_the_rest_api_answers(tmp_path: Path) -> None:
    """`.json` is the answer of `format=json`: the block, the snapshot and the alerts, nested as `to_dict` has them."""
    result = _result(CAP_XML, CAP_TWO_INFOS)
    file = tmp_path / "alerts.json"
    result.to_target(f"file://{file}")
    data = json.loads(file.read_text(encoding="utf-8"))
    assert list(data) == ["metadata", "snapshot", "alerts"]
    assert data["snapshot"] == "2026-07-26T08:00:00.000000+00:00"
    assert [alert["event"] for alert in data["alerts"]] == ["gale-force gusts", "Frost"]
    assert data["alerts"][0]["geometry"]["type"] == "MultiPolygon"
    assert data["alerts"][0]["parameters"][1] == {"name": "wind direction", "value": "west"}
    assert data["alerts"][0]["warncell_ids"] == ["809272121", "809276148"]
    # without the block, it is `to_dict`
    assert {key: data[key] for key in ("snapshot", "alerts")} == result.to_dict()
    # on one line, as the answer and as the file always was
    assert file.read_text(encoding="utf-8").startswith('{"metadata"')
    assert len(file.read_text(encoding="utf-8").splitlines()) == 1
    assert not (tmp_path / "alerts.json.metadata.json").exists()


def test_the_block_of_a_json_file_is_the_one_of_the_rest_api(tmp_path: Path) -> None:
    """The licence, the credit line and the date of the data are in the file, as `/api/alerts` has them."""
    result = _result(CAP_XML)
    file = tmp_path / "alerts.json"
    result.to_target(f"file://{file}")
    block = json.loads(file.read_text(encoding="utf-8"))["metadata"]
    assert block["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert block["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert block["data_updated_at"] == "2026-07-26T07:23:00.000000+00:00"
    assert block["request"]["network"] == "alerts"
    assert block["counts"]["rows"] == 1
    assert block["producer"]["name"] == "wetterdienst"


def test_a_geojson_file_is_the_feature_collection_with_the_block_as_a_foreign_member(tmp_path: Path) -> None:
    """`.geojson` is a `FeatureCollection` that a GIS reads, its `metadata` a member after `type` as REST puts it."""
    result = _result(CAP_XML, CAP_TWO_INFOS)
    file = tmp_path / "alerts.geojson"
    result.to_target(f"file://{file}")
    data = json.loads(file.read_text(encoding="utf-8"))
    assert list(data) == ["type", "metadata", "snapshot", "features"]
    assert data["type"] == "FeatureCollection"
    assert data["metadata"]["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert [feature["properties"]["event"] for feature in data["features"]] == ["gale-force gusts", "Frost"]
    assert data["features"][0]["geometry"]["type"] == "MultiPolygon"
    # an alert of warn cells alone has no polygon
    assert data["features"][1]["geometry"] is None


def test_the_extension_is_read_in_any_case(tmp_path: Path) -> None:
    """`.CSV` is a CSV file, as it is for the other results."""
    file = tmp_path / "ALERTS.JSON"
    _result(CAP_XML).to_target(f"file://{file}")
    assert "alerts" in json.loads(file.read_text(encoding="utf-8"))


# --- CSV --------------------------------------------------------------------------------------------------------------


def test_a_csv_file_is_a_row_for_each_alert_with_the_columns_of_the_frame(tmp_path: Path) -> None:
    """A row is an alert (one CAP message), however many areas it covers, and its columns are the frame's."""
    result = _result(CAP_XML, CAP_TWO_INFOS)
    file = tmp_path / "alerts.csv"
    result.to_target(f"file://{file}")
    assert file.read_text(encoding="utf-8") == result.to_csv()
    csv = _read_csv(file)
    assert csv.columns == result.df.columns
    assert csv.height == result.df.height == 2
    # no `metadata` anywhere in it: a CSV is bare, and its block is the sidecar's
    assert not (tmp_path / "alerts.csv.metadata.json").exists()


def test_a_csv_row_loses_none_of_the_areas_the_parameters_or_the_geometry(tmp_path: Path) -> None:
    """The areas of an alert are two joined fields, and `parameters` and `geometry` are JSON that reads back whole."""
    result = _result(CAP_XML, CAP_TWO_INFOS)
    file = tmp_path / "alerts.csv"
    result.to_target(f"file://{file}")
    first, second = _read_csv(file).iter_rows(named=True)
    alerts = result.to_dict()["alerts"]

    # three entity areas of one alert are one row with every id and every name
    assert first["warncell_ids"] == "809272121,809276148"
    assert first["area_names"] == "Gemeinde Grainet,Stadt Zwiesel"
    assert first["groups"] == "WIND"
    assert second["warncell_ids"] == "809464000,809272121,809276148"
    assert second["area_names"] == "Stadt Hof,Gemeinde Grainet,Stadt Zwiesel"
    for row, alert in ((first, alerts[0]), (second, alerts[1])):
        assert row["warncell_ids"].split(",") == alert["warncell_ids"]
        assert row["area_names"].split(",") == alert["area_names"]
        # the nested fields are JSON text, and a parameter that repeats its name stays a list entry
        assert json.loads(row["parameters"]) == alert["parameters"]
        assert (json.loads(row["geometry"]) if row["geometry"] else None) == alert["geometry"]
        assert row["alert_id"] == alert["alert_id"]
    assert json.loads(first["geometry"])["coordinates"][0][1][0] == [12.4, 49.4]  # the hole of the polygon area
    # no polygon: an empty field, not the text `null`
    assert second["geometry"] is None
    # times are ISO strings in UTC, as in the JSON
    assert first["sent"] == alerts[0]["sent"] == "2026-07-26T07:23:00.000000+00:00"


def test_the_second_info_of_a_cap_message_is_in_no_file(tmp_path: Path) -> None:
    """The parser reads the first `<info>` (for `mul`, the first language): the files hold that and say nothing more."""
    result = _result(CAP_TWO_INFOS)
    for name in ("alerts.csv", "alerts.json", "alerts.geojson"):
        result.to_target(f"file://{tmp_path / name}")
    assert result.df["language"].to_list() == ["de"]
    assert "FROST" not in (tmp_path / "alerts.csv").read_text(encoding="utf-8")
    assert "FROST" not in (tmp_path / "alerts.json").read_text(encoding="utf-8")
    assert "FROST" not in (tmp_path / "alerts.geojson").read_text(encoding="utf-8")


def test_a_csv_file_is_utf8_with_unix_newlines(tmp_path: Path) -> None:
    """A text with an umlaut is written as UTF-8, and a line ends in a line feed on every platform."""
    result = _result(CAP_XML.replace(b"Gemeinde Grainet", "Gemeinde Gräfenhainichen".encode()))
    file = tmp_path / "alerts.csv"
    result.to_target(f"file://{file}")
    raw = file.read_bytes()
    assert "Gräfenhainichen".encode() in raw
    assert b"\r" not in raw


# --- no warning ------------------------------------------------------------------------------------------------------


def test_a_snapshot_without_a_warning_is_written_as_it_is(tmp_path: Path) -> None:
    """No warning is an answer: an empty list, no feature and the header alone, so a schedule does not keep old ones."""
    result = _empty()
    assert result.df.is_empty()
    result.to_target(f"file://{tmp_path / 'alerts.json'}")
    result.to_target(f"file://{tmp_path / 'alerts.geojson'}")
    result.to_target(f"file://{tmp_path / 'alerts.csv'}", with_metadata=True)
    data = json.loads((tmp_path / "alerts.json").read_text(encoding="utf-8"))
    assert data["alerts"] == []
    assert data["metadata"]["counts"]["rows"] == 0
    assert data["metadata"]["data_updated_at"] is None
    assert json.loads((tmp_path / "alerts.geojson").read_text(encoding="utf-8"))["features"] == []
    csv = (tmp_path / "alerts.csv").read_text(encoding="utf-8")
    assert csv.splitlines() == [",".join(_SCHEMA)]
    assert json.loads((tmp_path / "alerts.csv.metadata.json").read_text(encoding="utf-8"))["counts"]["rows"] == 0


def test_a_file_of_warnings_is_replaced_by_an_empty_snapshot(tmp_path: Path) -> None:
    """The next run of a schedule that finds no warning leaves no warning in the file."""
    file = tmp_path / "alerts.csv"
    _result(CAP_XML).to_target(f"file://{file}")
    assert len(file.read_text(encoding="utf-8").splitlines()) == 2
    _empty().to_target(f"file://{file}")
    assert len(file.read_text(encoding="utf-8").splitlines()) == 1


# --- the metadata beside a file ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["alerts.csv", "alerts.json", "alerts.geojson"])
def test_with_metadata_writes_the_block_beside_any_of_the_three(tmp_path: Path, name: str) -> None:
    """`<file>.metadata.json` is the block of `/api/alerts`: the licence, the credit line and the date of the data."""
    file = tmp_path / name
    _result(CAP_XML).to_target(f"file://{file}", with_metadata=True)
    sidecar = json.loads((tmp_path / f"{name}.metadata.json").read_text(encoding="utf-8"))
    assert sidecar["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert sidecar["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert sidecar["data_updated_at"] == "2026-07-26T07:23:00.000000+00:00"
    assert sidecar["retrieved_at"]
    assert sidecar["request"]["provider"] == "dwd"
    assert sidecar["request"]["network"] == "alerts"
    assert sidecar["counts"] == {"stations": 0, "rows": 1}
    assert sidecar["producer"]["name"] == "wetterdienst"
    assert "parameters" not in sidecar, "the warnings have no parameters to describe"


def test_the_block_is_the_one_the_builder_of_the_rest_api_builds(tmp_path: Path) -> None:
    """The sidecar and the block in the file are the builder's, so what it adds comes along with nothing named here."""
    from wetterdienst.ui.response_metadata import alerts_metadata, metadata_to_dict  # noqa: PLC0415

    result = _result(CAP_XML)
    begin_response()
    warn_response(logging.getLogger(__name__), "test_warning", "a warning of the request")
    expected = metadata_to_dict(alerts_metadata(DwdWeatherAlertRequest, result.df.height, result.data_updated_at))
    file = tmp_path / "alerts.json"
    result.to_target(f"file://{file}", with_metadata=True)
    sidecar = json.loads((tmp_path / "alerts.json.metadata.json").read_text(encoding="utf-8"))
    embedded = json.loads(file.read_text(encoding="utf-8"))["metadata"]
    for block in (sidecar, embedded):
        # the time of the write is the one thing that differs
        assert {**block, "retrieved_at": None} == {**expected, "retrieved_at": None}
        assert block["warnings"] == [{"code": "test_warning", "message": "a warning of the request"}]


def test_without_with_metadata_a_csv_file_has_no_sidecar_and_an_old_one_stays(tmp_path: Path) -> None:
    """A sidecar of an earlier write is overwritten by the next one with the flag and left by one without."""
    file = tmp_path / "alerts.csv"
    result = _result(CAP_XML)
    result.to_target(f"file://{file}", with_metadata=True)
    sidecar = tmp_path / "alerts.csv.metadata.json"
    sidecar.write_text("old")
    result.to_target(f"file://{file}")
    assert sidecar.read_text() == "old"
    result.to_target(f"file://{file}", with_metadata=True)
    assert json.loads(sidecar.read_text(encoding="utf-8"))["provider"]["license"]


# --- if_exists --------------------------------------------------------------------------------------------------------


def test_if_exists_replace_fail_and_skip(tmp_path: Path) -> None:
    """`replace` is the default, `fail` refuses a file that is there, `skip` leaves it, and neither writes a sidecar."""
    file = tmp_path / "alerts.csv"
    result = _result(CAP_XML)
    file.write_text("old")
    with pytest.raises(ExportRefusedError, match="already exists"):
        result.to_target(f"file://{file}", if_exists="fail", with_metadata=True)
    result.to_target(f"file://{file}", if_exists="skip", with_metadata=True)
    assert file.read_text() == "old"
    assert not (tmp_path / "alerts.csv.metadata.json").exists()
    result.to_target(f"file://{file}")
    assert file.read_text(encoding="utf-8") == result.to_csv()


def test_append_to_a_file_is_refused(tmp_path: Path) -> None:
    """A file is written whole, as it is for the other results."""
    file = tmp_path / "alerts.json"
    with pytest.raises(ExportRefusedError, match="Append mode is not supported"):
        _result(CAP_XML).to_target(f"file://{file}", if_exists="append")
    assert not file.exists()


# --- what is refused --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "duckdb:///alerts.duckdb?table=alerts",
        "sqlite:///alerts.sqlite?table=alerts",
        "influxdb://localhost/?database=dwd&table=alerts",
        "crate://localhost/?database=dwd&table=alerts",
        "postgresql://user:secret@localhost/dwd?table=alerts",
    ],
)
def test_a_database_target_is_refused_with_nothing_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    """An alert is nested (areas, parameters, a polygon) and no table is designed for it: every sink says so."""
    # the file of a relative target would land in the working directory, where the check below looks for it
    monkeypatch.chdir(tmp_path)
    result = _result(CAP_XML)
    with pytest.raises(ExportRefusedError, match="written to a file only") as refused:
        result.to_target(target)
    assert "file://alerts.json, alerts.geojson or alerts.csv" in str(refused.value)
    assert "secret" not in str(refused.value)
    with pytest.raises(ExportRefusedError, match="written to a file only"):
        result.to_target(target, with_metadata=True)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "extension", [".parquet", ".xlsx", ".feather", ".zarr", ".nc", ".jsonl", ".ndjson", ".txt", ""]
)
def test_a_file_type_of_none_of_the_three_is_refused_naming_them(tmp_path: Path, extension: str) -> None:
    """Parquet, a spreadsheet, Feather and the rest are no files of the alerts: the refusal lists the three."""
    file = tmp_path / f"alerts{extension}"
    with pytest.raises(ExportRefusedError, match="Unknown export file type") as refused:
        _result(CAP_XML).to_target(f"file://{file}", with_metadata=True)
    assert "this result is written as .csv, .geojson, .json" in str(refused.value)
    assert list(tmp_path.iterdir()) == []


def test_a_query_string_after_a_known_extension_says_so(tmp_path: Path) -> None:
    """`alerts.csv?a=1` is a file name, not a target with a query: the message of the other results."""
    with pytest.raises(ExportRefusedError, match="A file target has no query string"):
        _result(CAP_XML).to_target(f"file://{tmp_path / 'alerts.csv'}?a=1")


def test_a_plain_path_is_refused_as_any_target_that_is_no_url() -> None:
    """A library target is a `file://` URI, as it is for the other results; the command line reads a path itself."""
    with pytest.raises(ExportRefusedError, match="not a URL"):
        _result(CAP_XML).to_target("alerts.csv")


def test_an_upper_case_scheme_is_told_as_such_and_not_as_a_refused_file_target() -> None:
    """`FILE://x.csv` is read by no sink, and the refusal does not say that a file target is refused."""
    with pytest.raises(ExportRefusedError, match="lower case") as refused:
        _result(CAP_XML).to_target("FILE://alerts.csv")
    assert "is refused" not in str(refused.value)


# --- the type is read before the file is looked for -------------------------------------------------------------


@pytest.mark.parametrize("if_exists", ["replace", "fail", "skip", "append"])
@pytest.mark.parametrize("name", ["alerts.parquet", "alerts.txt", "alerts"])
def test_a_file_of_another_type_is_refused_by_its_type_whether_it_is_there_or_not(
    tmp_path: Path, name: str, if_exists: str
) -> None:
    """`skip` returned in silence for an existing `.parquet`, and `fail` said it was there: now each names the type."""
    file = tmp_path / name
    file.write_text("old")
    for there in (True, False):
        if not there:
            file.unlink()
        with pytest.raises(ExportRefusedError, match="Unknown export file type") as refused:
            _result(CAP_XML).to_target(f"file://{file}", if_exists=if_exists)  # ty: ignore[invalid-argument-type]
        assert "this result is written as .csv, .geojson, .json" in str(refused.value)
    assert list(tmp_path.iterdir()) == []


def test_the_files_of_the_other_results_are_still_looked_for_before_their_type(tmp_path: Path) -> None:
    """Only the alerts read the extension first: a frame's `skip` of an existing file of any name is as it was."""
    from wetterdienst.io.sinks import _write_file  # noqa: PLC0415
    from wetterdienst.util.url import ConnectionString  # noqa: PLC0415

    file = tmp_path / "frame.unknown"
    file.write_text("old")
    target = f"file://{file}"
    _write_file(_result(CAP_XML), target, ConnectionString(target), "skip")  # ty: ignore[invalid-argument-type]
    assert file.read_text() == "old"


# --- pretty -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["alerts.json", "alerts.geojson"])
def test_a_json_file_is_on_one_line_unless_pretty(tmp_path: Path, name: str) -> None:
    """A district snapshot is 614 KB on a line and 3.7 MB indented: the file is compact as it was, `pretty` indents."""
    result = _result(CAP_XML, CAP_TWO_INFOS)
    compact, pretty = tmp_path / f"compact_{name}", tmp_path / f"pretty_{name}"
    result.to_target(f"file://{compact}")
    result.to_target(f"file://{pretty}", pretty=True)
    assert len(compact.read_text(encoding="utf-8").splitlines()) == 1
    assert len(pretty.read_text(encoding="utf-8").splitlines()) > 50
    assert pretty.read_text(encoding="utf-8").startswith("{\n    ")
    # the same document
    assert (
        json.loads(compact.read_text(encoding="utf-8")).keys() == json.loads(pretty.read_text(encoding="utf-8")).keys()
    )
    assert compact.stat().st_size < pretty.stat().st_size


def test_pretty_changes_nothing_in_a_csv_file(tmp_path: Path) -> None:
    """A CSV has no indentation to give."""
    result = _result(CAP_XML)
    result.to_target(f"file://{tmp_path / 'a.csv'}")
    result.to_target(f"file://{tmp_path / 'b.csv'}", pretty=True)
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()
