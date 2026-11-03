# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The licence, the credit line and the date of a file that is written (GH-3449).

A REST answer says in its `metadata` block where its data comes from, under which licence and with which credit
line, and when it was retrieved. A file written by `to_target` or `to_csv` carries the same block: inside the file
where the format has a place for it (Parquet's key-value metadata, the attributes of a NetCDF file or a Zarr group),
and beside it, as `<file>.metadata.json`, where the caller asks for it with `with_metadata=True` and the format is not
written with it (CSV, spreadsheets, JSON, JSON Lines, GeoJSON and Feather, whose writer in polars takes no metadata).
The block is the one `ui.response_metadata` builds for the REST API, the command line and MCP; this module only picks
the provider and the network out of a result and writes it.

The block describes the file as it is written: `retrieved_at` is the time of the write, and `warnings` are those
recorded since the command or request began (`begin_response`); a library call records none, so they are empty there.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wetterdienst.exceptions import ExportRefusedError
from wetterdienst.util.json_util import dumps_json

if TYPE_CHECKING:
    from wetterdienst.io.export import ExportMixin

#: the attribute that holds the whole block as JSON, in Parquet's key-value metadata and in the attributes of a NetCDF
#: file or a Zarr group; the others below are single values of it for a tool that lists the keys (`parquet-tools`,
#: `ncdump -h`)
BLOCK_KEY = "wetterdienst_metadata"

#: the suffix of the file that holds the block beside a file of a format that has no place for it
SIDECAR_SUFFIX = ".metadata.json"


def metadata_block(result: ExportMixin, *, heavy: bool) -> dict[str, Any] | None:
    """Build the `metadata` block of the REST API for a result, as the JSON of an answer has it.

    `heavy` adds the unit of every parameter and what `quality_flags` holds, as `with_metadata` does for an answer.

    Returns:
        The block, or `None` for a result that has no provider to describe: a bare `ExportMixin` built of a frame,
        or a result of a request class that the registry of `Wetterdienst` does not name (the block says which
        provider and network the data is from).

    """
    # the module imports the results, which import `ExportMixin`; and the block is the REST API's, built once there
    from wetterdienst.api import Wetterdienst  # noqa: PLC0415
    from wetterdienst.model.result import StationsResult, _ValuesResult  # noqa: PLC0415
    from wetterdienst.ui.response_metadata import metadata_to_dict, result_metadata  # noqa: PLC0415

    if not isinstance(result, StationsResult | _ValuesResult):
        return None
    stations = result if isinstance(result, StationsResult) else result.stations
    provider, _, network = Wetterdienst._network_of(type(stations.request)).partition("/")  # noqa: SLF001
    if not network:
        return None
    return metadata_to_dict(result_metadata(result, provider=provider, network=network, heavy=heavy))


def block_attributes(block: dict[str, Any]) -> dict[str, str]:
    """Give the key-value pairs a self-describing file holds: the block as JSON, and its parts a tool lists.

    Only text, as Parquet's key-value metadata and the attributes of NetCDF and Zarr are; a part the block has no value
    for (a provider that states no licence, a date the source does not state) is left out rather than written as null.
    """
    provider = block["provider"]
    license_ = provider["license"]
    parts = {
        "provider": provider["name_english"],
        "license": None if license_ is None else license_["spdx_id"] or license_["name"],
        "license_url": None if license_ is None else license_["url"],
        "attribution": provider["attribution"],
        "retrieved_at": block["retrieved_at"],
        "data_updated_at": block["data_updated_at"],
    }
    return {
        **{key: value for key, value in parts.items() if value},
        BLOCK_KEY: dumps_json(block, ensure_ascii=False),
    }


def sidecar_path(filepath: str | os.PathLike[str]) -> Path:
    """Name the file that holds the block beside the file at `filepath`: the path and `.metadata.json`."""
    return Path(f"{os.fspath(filepath)}{SIDECAR_SUFFIX}")


def require_block(result: ExportMixin, *, heavy: bool, beside: str | os.PathLike[str]) -> dict[str, Any]:
    """Build the block for a caller that asked for it, before anything is written.

    Raises:
        ExportRefusedError: The result has no provider to describe, so `with_metadata` has nothing to write beside
            the file at `beside`.

    """
    block = metadata_block(result, heavy=heavy)
    if block is None:
        msg = (
            f"{type(result).__name__} has no provider to describe, so there is no metadata to write for "
            f"'{os.fspath(beside)}'; with_metadata needs the result of a stations or a values request that the "
            "registry of Wetterdienst names"
        )
        raise ExportRefusedError(msg)
    return block


def write_sidecar(block: dict[str, Any], filepath: str | os.PathLike[str]) -> Path:
    """Write the `metadata` block beside the file at `filepath`, as `<file>.metadata.json`.

    Returns:
        The path of the sidecar

    """
    path = sidecar_path(filepath)
    # bytes, as `ensure_ascii=False` writes UTF-8 and a text file would translate the newlines on Windows
    path.write_bytes(dumps_json(block, indent=4, ensure_ascii=False).encode("utf-8"))
    return path
