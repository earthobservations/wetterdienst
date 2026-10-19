# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames the core hands out for every offline fixture of every provider, as committed (GH-2627).

The shaping of the final frame (the identity columns, the dtypes, the time zone, the column set) is written once in the
core and again in each provider, and is to move out of the providers into the core. That change must not move the
output, so this is the net under it: every offline test of `tests/provider` that collects values or stations records
the frame the core produced, and `tests/provider/frames.snapshot.json` holds what each recorded:

- ``values``: per test, per call of `TimeseriesValues._process_dataset` (the frame of a station and a dataset, after the
  unit conversion, `unique`, `drop_nulls` and the column order, which is the last of the core's steps that follows a
  provider's own), as ``[label, schema, rows, hash]``;
- ``stations``: per test, per call of `TimeseriesRequest.all` (the stations as a caller gets them), the same.

The label is the name of the provider's class and, for values, the resolution and dataset. The schema is the ordered
``name:dtype`` list, kept once in ``schemas`` and named by a hash of itself, since most frames share one. The hash is
that of the rows, which are sorted first: the output is sorted by the core before a caller sees it, and a provider that
downloads in parallel has no say in the order its pieces arrive in. Floats are written to 12 significant digits, so
that the hash does not depend on how a version of polars or of the platform formats the last one.

`tests/provider/conftest.py` compares each offline test to its entry when the test ends, and fails it where they differ,
naming the frame and what differs. A test with no entry fails too, so that a fixture does not sit outside the net. A
test marked `remote` is not recorded: what a real source answers with changes.

An intended change to what a fixture's frame holds (a provider that fixes a reading, a new test, a new provider) is a
change to the snapshot in the same pull request, where a reviewer sees it as a diff. Regenerate with

    uv run poe frames:snapshot

which runs the whole offline selection of `tests/provider` in one process and writes the file. What it holds is not
what the provider returned but what the core made of it, so a pull request that moves shaping from a provider into the
core, and leaves the diff of this file empty, has shown that it changed nothing.

What the snapshot does not cover is the networks that have no `TimeseriesValues` (`dwd/radar`, `dwd/alerts`) and a
network none of whose offline tests collects values: `NO_VALUES_FIXTURE` and `NO_STATIONS_FIXTURE` in
`test_frames_snapshot.py` list them, with the reason.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import polars as pl

SNAPSHOT = Path(__file__).parent / "frames.snapshot.json"
#: the environment variable that turns the recording into the writing of the snapshot
WRITE = "WD_FRAMES_SNAPSHOT"
_SIGNIFICANT_DIGITS = 12

Entry = list[Any]


def writing() -> bool:
    """Tell whether this run writes the snapshot rather than compares to it."""
    return os.environ.get(WRITE, "").lower() in {"1", "true", "yes", "write"}


def schema_of(df: pl.DataFrame) -> list[str]:
    """Give the ordered ``name:dtype`` list of a frame."""
    return [f"{name}:{dtype}" for name, dtype in df.schema.items()]


def schema_id(schema: list[str]) -> str:
    """Name a schema by a hash of itself, so that the snapshot holds each once."""
    return hashlib.sha256("\n".join(schema).encode()).hexdigest()[:8]


def _cell(value: object) -> str:
    if isinstance(value, float):
        return format(value, f".{_SIGNIFICANT_DIGITS}g")
    return repr(value)


def rows_hash(df: pl.DataFrame) -> str:
    """Hash the rows of a frame, in an order that does not depend on the order they arrived in."""
    nested = any(isinstance(dtype, pl.List | pl.Struct | pl.Array | pl.Object) for dtype in df.schema.values())
    if not nested and df.width:
        df = df.sort(df.columns, nulls_last=True)
    digest = hashlib.sha256()
    for row in df.iter_rows():
        digest.update("\x1f".join(_cell(cell) for cell in row).encode())
        digest.update(b"\x1e")
    return digest.hexdigest()[:16]


def describe(label: str, df: pl.DataFrame) -> Entry:
    """Describe a frame as ``[label, schema id, rows, hash]``."""
    return [label, schema_id(schema_of(df)), df.height, rows_hash(df)]


class Recorder:
    """What one test's calls produced, and the schemas they carry."""

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self.values: list[Entry] = []
        self.stations: list[Entry] = []
        self.schemas: dict[str, list[str]] = {}

    def record(self, kind: str, label: str, df: pl.DataFrame) -> None:
        """Take a frame of a kind (``values`` or ``stations``)."""
        self.schemas[schema_id(schema_of(df))] = schema_of(df)
        getattr(self, kind).append(describe(label, df))

    def empty(self) -> bool:
        """Tell whether the test made no call that is recorded."""
        return not (self.values or self.stations)


def load() -> dict[str, Any]:
    """Read the committed snapshot."""
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def write(
    values: dict[str, list[Entry]],
    stations: dict[str, list[Entry]],
    schemas: dict[str, list[str]],
    to: Path = SNAPSHOT,
) -> None:
    """Write the snapshot, a test to a line so that a diff reads as the tests it changes."""

    def lines(name: str, entries: dict[str, Any]) -> str:
        body = ",\n".join(
            f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(entries[key], ensure_ascii=False)}"
            for key in sorted(entries)
        )
        return f'"{name}": {{\n{body}\n}}'

    text = (
        "{\n"
        + ",\n".join(
            lines(name, entries)
            for name, entries in (
                ("schemas", schemas),
                ("values", values),
                ("stations", stations),
            )
        )
        + "\n}\n"
    )
    to.write_text(text, encoding="utf-8")


def differences(recorded: list[Entry], committed: list[Entry] | None, schemas: dict[str, list[str]]) -> list[str]:
    """Say, frame by frame, what a test's recording has that its committed entry does not."""
    if committed is None:
        return [f"{len(recorded)} frame(s) recorded, none in the snapshot"]
    found = []
    if len(recorded) != len(committed):
        found.append(f"{len(recorded)} frame(s) recorded, {len(committed)} in the snapshot")
    for number, (now, then) in enumerate(zip(recorded, committed, strict=False), start=1):
        if now == then:
            continue
        label, schema, rows, digest = now
        _, schema_then, rows_then, digest_then = then
        what = []
        if schema != schema_then:
            now_columns = set(schemas.get(schema, []))
            then_columns = set(schemas.get(schema_then, []))
            added, removed = sorted(now_columns - then_columns), sorted(then_columns - now_columns)
            what.append(f"schema: +{added} -{removed}" if added or removed else "schema: the order of the columns")
        if rows != rows_then:
            what.append(f"rows: {rows} not {rows_then}")
        if digest != digest_then and not what:
            what.append("the values differ")
        found.append(f"frame {number} ({label}): {'; '.join(what) or 'the label differs'}")
    return found


def compare(nodeid: str, recorder: Recorder) -> list[str]:
    """Say what the frames a test recorded have that its entry in the committed snapshot does not."""
    committed = load()
    schemas = committed["schemas"] | recorder.schemas
    found = []
    for kind in ("values", "stations"):
        recorded = getattr(recorder, kind)
        entry = committed[kind].get(nodeid)
        if recorded or entry:
            found += [f"{kind}: {line}" for line in differences(recorded, entry, schemas)]
    return found
