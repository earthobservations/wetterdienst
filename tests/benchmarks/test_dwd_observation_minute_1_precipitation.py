# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Smoke test for the DWD 1-minute precipitation benchmark, so that it does not rot."""

from __future__ import annotations

import json
from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import ZipFile

from benchmarks import dwd_observation_minute_1_precipitation as benchmark

if TYPE_CHECKING:
    from pathlib import Path

_RECENT = (
    "STATIONS_ID;MESS_DATUM;QN;RS_01;RS_IND_01;eor\n"
    "        44;202501010000;    3;   0.00;-999;eor\n"
    "        44;202501010001;    3;   0.10;   1;eor\n"
    "        44;202501010002;    3;   0.00;-999;eor\n"
)
_HISTORICAL = (
    "STATIONS_ID;MESS_DATUM_BEGINN;MESS_DATUM_ENDE;QN;RS_01;RTH_01;RWH_01;RS_IND_01;eor\n"
    "        44;202201010000;202201010002;    3;  0.00;  -999;  -999;-999;eor\n"
)


def _zip(path: Path, product: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(product, text)
    path.write_bytes(buffer.getvalue())


def test_the_benchmark_runs_every_stage_on_cached_files(tmp_path: Path) -> None:
    """Test that each stage reads the cache directory alone and reports the rows it made."""
    _zip(
        tmp_path / "recent" / "1minutenwerte_nieder_00044_akt.zip",
        "produkt_ein_min_rr_20250101_20250101_00044.txt",
        _RECENT,
    )
    _zip(
        tmp_path / "historical" / "1minutenwerte_nieder_00044_20220101_20220131_hist.zip",
        "produkt_ein_min_rr_20220101_20220131_00044.txt",
        _HISTORICAL,
    )
    output = tmp_path / "result.json"
    report = benchmark.main(
        [
            "--cache-dir",
            str(tmp_path),
            "--stations",
            "00044",
            "--runs",
            "1",
            "--warmup",
            "0",
            "--in-process",
            "--output",
            str(output),
        ],
    )
    rows = {stage["stage"]: stage["rows"] for stage in report["stages"]}
    # the three minutes of each file; the long shape holds a row per reading, so the three amounts
    # and the one index the file gives, the -999 of the other two being no reading
    assert rows["parse"] == 3
    assert rows["historical"] == 3
    assert rows["values_wide"] == 3
    assert rows["values_long"] == 4
    assert json.loads(output.read_text())["header"]["polars"]


def test_the_benchmark_runs_a_stage_in_a_process_of_its_own(tmp_path: Path) -> None:
    """Test the path of the default run: a child process per stage, its JSON read from standard output."""
    _zip(
        tmp_path / "recent" / "1minutenwerte_nieder_00044_akt.zip",
        "produkt_ein_min_rr_20250101_20250101_00044.txt",
        _RECENT,
    )
    report = benchmark.main(
        ["--cache-dir", str(tmp_path), "--stations", "00044", "--runs", "1", "--warmup", "0", "--stage", "parse"],
    )
    (stage,) = report["stages"]
    assert stage["rows"] == 3
    # Windows has no resource module to read it from
    assert stage["peak_rss_mb"] is None or stage["peak_rss_mb"] > 0
