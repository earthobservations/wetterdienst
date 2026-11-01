# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The licence, the credit line and the date of the data in the files that are written (GH-3449, decision 7).

A Parquet file, a NetCDF file and a Zarr group carry the `metadata` block of the REST API by default; the text
formats stay bare, and `with_metadata=True` writes the block beside them as `<file>.metadata.json`. Every test writes
a file and reads it back.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.model.test_results import _every_result
from wetterdienst.api import Wetterdienst
from wetterdienst.exceptions import ExportRefusedError
from wetterdienst.io.export import ExportMixin
from wetterdienst.io.file_metadata import BLOCK_KEY, SIDECAR_SUFFIX, block_attributes
from wetterdienst.io.sinks import FILE_WRITERS, SELF_DESCRIBING
from wetterdienst.ui.response_metadata import metadata_to_dict, response_metadata

if TYPE_CHECKING:
    from pathlib import Path

    from wetterdienst.model.result import StationsResult, ValuesResult

#: the results that are written to a file: a stations result and the three that hold values
_RESULTS = ("stations", "values", "interpolated", "summarized")

#: what the file types that are bare by default are written as; Feather is written without it by polars
_BARE = [".csv", ".json", ".jsonl", ".ndjson", ".geojson", ".xlsx", ".feather"]


def _result(name: str) -> Any:  # noqa: ANN401
    return _every_result()[name]


def _rest_block(result: Any, *, heavy: bool) -> dict[str, Any]:  # noqa: ANN401
    """Build the block as the REST API does for the request of a result, with the builder it calls."""
    request = SimpleNamespace(provider="dwd", network="observation", with_metadata=heavy)
    return metadata_to_dict(response_metadata(result, request, heavy=heavy))  # ty: ignore[invalid-argument-type]


def _same_block(written: dict[str, Any], expected: dict[str, Any]) -> None:
    """Compare a written block with the REST API's, but for the time it was made at."""
    assert written.pop("retrieved_at")
    expected = {key: value for key, value in expected.items() if key != "retrieved_at"}
    assert written == expected


def _block_of(attributes: dict[str, str]) -> dict[str, Any]:
    return json.loads(attributes[BLOCK_KEY])


def test_every_file_type_is_bare_or_self_describing() -> None:
    """The file types that carry the block themselves are the ones that have a place for it; the rest are listed."""
    assert set(FILE_WRITERS) == {*SELF_DESCRIBING, *_BARE}
    assert {".parquet", ".zarr", ".nc"} == SELF_DESCRIBING


# --- Parquet ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", _RESULTS)
def test_parquet_carries_the_block_of_the_rest_api_by_default(name: str, tmp_path: Path) -> None:
    """The key-value metadata of the file holds the licence, the credit line, the date and the whole block."""
    result = _result(name)
    filename = tmp_path / "data.parquet"
    result.to_target(f"file://{filename}")
    stored = pl.read_parquet_metadata(filename)
    block = _block_of(stored)
    assert "parameters" not in block
    assert "quality" not in block
    _same_block(block, _rest_block(result, heavy=False))
    provider = result.stations.request.metadata if name != "stations" else result.request.metadata
    assert stored["provider"] == provider.name_english
    assert stored["attribution"] == provider.attribution
    assert stored["license_url"] == provider.license.url
    assert stored["license"] == (provider.license.spdx_id or provider.license.name)
    assert stored["retrieved_at"] == json.loads(stored[BLOCK_KEY])["retrieved_at"]
    # nothing is written beside it
    assert [path.name for path in tmp_path.iterdir()] == ["data.parquet"]


def test_parquet_still_holds_the_frame(tmp_path: Path) -> None:
    """The metadata is no column: the frame reads back as it was written."""
    result: ValuesResult = _result("values")
    filename = tmp_path / "data.parquet"
    result.to_target(f"file://{filename}")
    assert pl.read_parquet(filename).equals(result.df)


def test_parquet_with_metadata_adds_the_units_and_the_quality_legend(tmp_path: Path) -> None:
    """`with_metadata=True` is what it is for an answer: the heavy parts, here in the file and in no sidecar."""
    result = _result("values")
    filename = tmp_path / "data.parquet"
    result.to_target(f"file://{filename}", with_metadata=True)
    block = _block_of(pl.read_parquet_metadata(filename))
    assert block["parameters"][0]["unit"]
    assert "quality" in block
    _same_block(block, _rest_block(result, heavy=True))
    assert [path.name for path in tmp_path.iterdir()] == ["data.parquet"]


# --- NetCDF and Zarr --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", _RESULTS)
def test_netcdf_carries_the_block_as_attributes(name: str, tmp_path: Path) -> None:
    """The attributes of the group hold the same keys as Parquet's metadata."""
    xarray = pytest.importorskip("xarray")
    pytest.importorskip("h5netcdf")
    result = _result(name)
    filename = tmp_path / "data.nc"
    result.to_target(f"file://{filename}")
    attrs = dict(xarray.open_dataset(filename, group=_group_of(result)).attrs)
    block = _block_of(attrs)
    assert "parameters" not in block
    assert "quality" not in block
    _same_block(block, _rest_block(result, heavy=False))
    assert attrs["license"]
    assert attrs["attribution"]
    assert attrs["retrieved_at"]
    assert [path.name for path in tmp_path.iterdir()] == ["data.nc"]


def _group_of(result: Any) -> str:  # noqa: ANN401
    """Name the group the frame is written into: the datasets it holds, else the resolutions."""
    column = "dataset" if "dataset" in result.df.columns else "resolution"
    return "_".join(sorted(result.df.get_column(column).drop_nulls().unique().to_list()))


@pytest.mark.parametrize("name", _RESULTS)
def test_zarr_carries_the_block_as_attributes(name: str, tmp_path: Path) -> None:
    """The attributes of the Zarr group hold the same keys as Parquet's metadata."""
    xarray = pytest.importorskip("xarray")
    pytest.importorskip("zarr")
    result = _result(name)
    filename = tmp_path / "data.zarr"
    result.to_target(f"file://{filename}")
    attrs = dict(xarray.open_zarr(filename, group=_group_of(result), consolidated=False).attrs)
    block = _block_of(attrs)
    assert "parameters" not in block
    assert "quality" not in block
    _same_block(block, _rest_block(result, heavy=False))
    assert attrs["license"]
    assert attrs["attribution"]


def test_netcdf_with_metadata_adds_the_heavy_parts(tmp_path: Path) -> None:
    """The same `with_metadata` as for Parquet."""
    xarray = pytest.importorskip("xarray")
    pytest.importorskip("h5netcdf")
    filename = tmp_path / "data.nc"
    _result("values").to_target(f"file://{filename}", with_metadata=True)
    block = _block_of(dict(xarray.open_dataset(filename, group="climate_summary").attrs))
    assert block["parameters"]
    assert "quality" in block
    assert [path.name for path in tmp_path.iterdir()] == ["data.nc"]


# --- the text formats and Feather -------------------------------------------------------------------------------------


@pytest.mark.parametrize("extension", _BARE)
def test_a_bare_format_is_bare_by_default(extension: str, tmp_path: Path) -> None:
    """Nothing is written beside a CSV, a spreadsheet, JSON, JSON Lines, GeoJSON or Feather, and nothing is in it."""
    filename = tmp_path / f"data{extension}"
    _result("values").to_target(f"file://{filename}")
    assert [path.name for path in tmp_path.iterdir()] == [filename.name]


def test_a_csv_is_what_to_csv_returns(tmp_path: Path) -> None:
    """The file is the CSV of the frame and no more: no comment lines, no extra column."""
    result = _result("values")
    filename = tmp_path / "data.csv"
    result.to_target(f"file://{filename}")
    assert filename.read_text() == result.to_csv()
    assert not (tmp_path / f"data.csv{SIDECAR_SUFFIX}").exists()


@pytest.mark.parametrize("name", _RESULTS)
@pytest.mark.parametrize("extension", _BARE)
def test_with_metadata_writes_the_block_beside_a_bare_file(extension: str, name: str, tmp_path: Path) -> None:
    """`<file>.metadata.json` holds the block of the REST API with its heavy parts, and the file is the bare one."""
    if extension == ".xlsx":
        pytest.importorskip("xlsxwriter")
    result = _result(name)
    bare = tmp_path / f"bare{extension}"
    filename = tmp_path / f"data{extension}"
    result.to_target(f"file://{bare}")
    result.to_target(f"file://{filename}", with_metadata=True)
    sidecar = tmp_path / f"data{extension}{SIDECAR_SUFFIX}"
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted([bare.name, filename.name, sidecar.name])
    if extension != ".xlsx":
        # a spreadsheet holds the time it was made at
        assert filename.read_bytes() == bare.read_bytes()
    block = json.loads(sidecar.read_text(encoding="utf-8"))
    assert "parameters" in block
    assert "quality" in block
    _same_block(block, _rest_block(result, heavy=True))


def test_the_sidecar_keeps_the_text_of_the_attribution(tmp_path: Path) -> None:
    """UTF-8 as it is, not escaped: the credit line of a provider may carry more than ASCII."""
    filename = tmp_path / "data.csv"
    _result("values").to_target(f"file://{filename}", with_metadata=True)
    text = (tmp_path / f"data.csv{SIDECAR_SUFFIX}").read_text(encoding="utf-8")
    assert "\\u" not in text
    block = json.loads(text)
    assert block["provider"]["attribution"]
    assert block["provider"]["license"]["url"].startswith("http")


def test_a_file_that_is_skipped_gets_no_sidecar(tmp_path: Path) -> None:
    """`if_exists='skip'` writes nothing, the sidecar included."""
    filename = tmp_path / "data.csv"
    filename.write_text("kept")
    _result("values").to_target(f"file://{filename}", if_exists="skip", with_metadata=True)
    assert [path.name for path in tmp_path.iterdir()] == ["data.csv"]
    assert filename.read_text() == "kept"


def test_a_write_without_with_metadata_leaves_the_sidecar_of_an_earlier_one(tmp_path: Path) -> None:
    """The sidecar is the caller's to keep or delete: only a `with_metadata` write touches it."""
    filename = tmp_path / "data.csv"
    _result("values").to_target(f"file://{filename}", with_metadata=True)
    sidecar = tmp_path / f"data.csv{SIDECAR_SUFFIX}"
    sidecar.write_text("earlier")
    _result("values").to_target(f"file://{filename}")
    assert sidecar.read_text() == "earlier"


def test_a_sidecar_is_replaced_with_its_file(tmp_path: Path) -> None:
    """The sidecar follows the file under `replace`: the second write leaves one block."""
    filename = tmp_path / "data.csv"
    _result("values").to_target(f"file://{filename}", with_metadata=True)
    sidecar = tmp_path / f"data.csv{SIDECAR_SUFFIX}"
    sidecar.write_text("stale")
    _result("values").to_target(f"file://{filename}", with_metadata=True)
    assert json.loads(sidecar.read_text(encoding="utf-8"))["provider"]


# --- to_csv -----------------------------------------------------------------------------------------------------------


def test_to_csv_with_metadata_writes_the_sidecar_beside_its_file(tmp_path: Path) -> None:
    """`to_csv(file=..., with_metadata=True)` writes the CSV and `<file>.metadata.json`."""
    result = _result("values")
    filename = tmp_path / "data.csv"
    result.to_csv(file=filename, with_metadata=True)
    assert filename.read_text() == result.to_csv()
    _same_block(
        json.loads((tmp_path / f"data.csv{SIDECAR_SUFFIX}").read_text(encoding="utf-8")),
        _rest_block(result, heavy=True),
    )


def test_to_csv_takes_a_path_as_a_string(tmp_path: Path) -> None:
    """`file` is the polars argument: a string names the file as a `Path` does."""
    filename = str(tmp_path / "data.csv")
    _result("stations").to_csv(file=filename, with_metadata=True)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["data.csv", f"data.csv{SIDECAR_SUFFIX}"]


def test_to_csv_is_bare_by_default(tmp_path: Path) -> None:
    """Without `with_metadata` a file is written as before, and nothing beside it."""
    filename = tmp_path / "data.csv"
    _result("values").to_csv(file=filename)
    assert [path.name for path in tmp_path.iterdir()] == ["data.csv"]


def test_to_csv_with_metadata_needs_a_file() -> None:
    """A string has no file to write a sidecar beside: it is refused, not dropped."""
    with pytest.raises(ValueError, match="give the path of the file as `file`"):
        _result("values").to_csv(with_metadata=True)


def test_to_format_csv_still_takes_with_metadata_and_returns_the_text() -> None:
    """The one set of arguments a caller builds for every format reaches the CSV, which has no use for it."""
    result = _result("values")
    assert result.to_format("csv", with_metadata=True) == result.to_csv()


# --- what is refused --------------------------------------------------------------------------------------------------


def test_with_metadata_for_a_database_is_refused(tmp_path: Path) -> None:
    """A database has no file to write it beside; it is told, and nothing is connected to."""
    with pytest.raises(ExportRefusedError, match="beside a file target"):
        _result("values").to_target(f"sqlite:///{tmp_path / 'data.sqlite'}?table=weather", with_metadata=True)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("extension", [*_BARE, *sorted(SELF_DESCRIBING)])
def test_with_metadata_for_a_frame_without_a_provider_is_refused(extension: str, tmp_path: Path) -> None:
    """A bare `ExportMixin` of a frame has no provider, so there is nothing to describe: refused, whatever the type."""
    exporter = ExportMixin(df=pl.DataFrame({"a": [1]}))
    with pytest.raises(ExportRefusedError, match="has no provider to describe"):
        exporter.to_target(f"file://{tmp_path / f'data{extension}'}", with_metadata=True)
    # before anything is written, not after the data file
    assert list(tmp_path.iterdir()) == []


def test_to_csv_with_metadata_for_a_frame_without_a_provider_writes_no_file(tmp_path: Path) -> None:
    """The refusal comes before the CSV is written, as for `to_target`."""
    with pytest.raises(ExportRefusedError, match="has no provider to describe"):
        ExportMixin(df=pl.DataFrame({"a": [1]})).to_csv(file=tmp_path / "data.csv", with_metadata=True)
    assert list(tmp_path.iterdir()) == []


def test_a_request_class_the_registry_does_not_name_has_no_provider_to_describe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The registry says which provider and network the data is from: without it the block is refused, not guessed."""
    monkeypatch.setattr(Wetterdienst, "_network_of", classmethod(lambda _cls, _request_class: ""))
    result = _result("values")
    result.to_target(f"file://{tmp_path / 'data.parquet'}")
    assert BLOCK_KEY not in pl.read_parquet_metadata(tmp_path / "data.parquet")
    with pytest.raises(ExportRefusedError, match="registry of Wetterdienst names"):
        result.to_target(f"file://{tmp_path / 'data.csv'}", with_metadata=True)
    assert [path.name for path in tmp_path.iterdir()] == ["data.parquet"]


def test_a_self_describing_file_of_a_frame_without_a_provider_is_written_without(tmp_path: Path) -> None:
    """The metadata is carried where there is some; a frame of no result is written as it always was."""
    filename = tmp_path / "data.parquet"
    ExportMixin(df=pl.DataFrame({"a": [1]})).to_target(f"file://{filename}")
    assert BLOCK_KEY not in pl.read_parquet_metadata(filename)
    assert pl.read_parquet(filename).to_dict(as_series=False) == {"a": [1]}


# --- the attributes ---------------------------------------------------------------------------------------------------


def test_a_provider_that_states_no_licence_writes_none() -> None:
    """A part the block has no value for is left out, not written as null: NetCDF has no null attribute."""
    block = {
        "provider": {"name_english": "Somebody", "license": None, "attribution": None},
        "retrieved_at": "2026-11-01T00:00:00Z",
        "data_updated_at": None,
    }
    attributes = block_attributes(block)
    assert set(attributes) == {"provider", "retrieved_at", BLOCK_KEY}
    assert json.loads(attributes[BLOCK_KEY]) == block


def test_a_licence_is_named_by_its_spdx_identifier_or_else_by_its_name() -> None:
    """As the `X-Wetterdienst-License` header names it."""
    provider = {"name_english": "A", "attribution": "credit"}
    spdx = block_attributes(
        {
            "provider": {**provider, "license": {"spdx_id": "CC-BY-4.0", "name": "n", "url": "u"}},
            "retrieved_at": "t",
            "data_updated_at": "d",
        }
    )
    named = block_attributes(
        {
            "provider": {**provider, "license": {"spdx_id": None, "name": "Own terms", "url": "u"}},
            "retrieved_at": "t",
            "data_updated_at": "d",
        }
    )
    assert spdx["license"] == "CC-BY-4.0"
    assert named["license"] == "Own terms"
    assert spdx["data_updated_at"] == "d"


def test_the_block_is_the_one_the_rest_api_builds(tmp_path: Path) -> None:
    """The stations of a result are described as the REST API describes them: the same members, not a second shape."""
    stations: StationsResult = _result("stations")
    filename = tmp_path / "stations.csv"
    stations.to_target(f"file://{filename}", with_metadata=True)
    block = json.loads((tmp_path / f"stations.csv{SIDECAR_SUFFIX}").read_text(encoding="utf-8"))
    assert set(block) == set(_rest_block(stations, heavy=True))
    assert block["request"]["provider"] == "dwd"
    assert block["request"]["network"] == "observation"
    assert block["counts"]["stations"] == stations.df.height
