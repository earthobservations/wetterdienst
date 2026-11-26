# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A reader of the compact format (GH-4445), written from the grammar of `docs/usage/compact.md` and from nothing else.

It shares no code with `wetterdienst.io.compact`: a writer and a reader that agree on every case of the tests, the
hostile text included, hold the grammar and not one function against itself. `parse` reads the lines (the first
line, the header, the tables, the end line), `values` reads the tables of values back into what they stand for,
`{(station, resolution, dataset, parameter, timestamp): (value, flags)}`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from typing import Any

FIRST = re.compile(r"^# wetterdienst-compact/(\d+) (\S+)$")
#: the notes after the default flags of a table of values
NOTE_ALL = " (all rows)"
NOTE_DIFFER = " (periods that differ are listed after the table)"


class FormatError(ValueError):
    """The text is not in the format."""


@dataclass
class Table:
    """A table: heading, attributes as `(key, text)`, columns, rows (each a list of text, None for an empty cell)."""

    heading: str
    attributes: list[tuple[str, str]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list[list[str | None]] = field(default_factory=list)

    def attribute(self, key: str) -> str | None:
        """Give the text of an attribute, None if the table has none."""
        return dict(self.attributes).get(key)


@dataclass
class Parsed:
    """An answer read: the version and tool of its first line, the header, the tables, the text after `# end `."""

    version: int
    tool: str
    header: list[tuple[str, str]]
    tables: list[Table]
    end: str

    def get(self, key: str, default: str | None = None) -> str | None:
        """Give the text of a header key, `default` if there is none."""
        return dict(self.header).get(key, default)

    def warnings(self) -> list[tuple[str, str]]:
        """Give the (code, text) of every warning line."""
        return [(key.removeprefix("warning "), value) for key, value in self.header if key.startswith("warning ")]

    def table(self, prefix: str) -> Table:
        """Give the first table whose heading starts with `prefix`."""
        return next(t for t in self.tables if t.heading.startswith(prefix))


def text_of(raw: str) -> str:
    """Read a header value: a JSON string where it starts with a quote, else the text as it is."""
    return json.loads(raw) if raw.startswith('"') else raw


def cells(line: str) -> list[str | None]:
    """Split a row at its commas: a cell that starts with a quote is a JSON string, an empty one is None."""
    out: list[str | None] = []
    i = 0
    while True:
        if line.startswith('"', i):
            j = i + 1
            while line[j] != '"':
                j += 2 if line[j] == "\\" else 1
            out.append(json.loads(line[i : j + 1]))
            i = j + 1
            if i < len(line) and line[i] != ",":
                msg = f"text after a quoted cell: {line!r}"
                raise FormatError(msg)
        else:
            j = line.find(",", i)
            j = len(line) if j < 0 else j
            out.append(line[i:j] or None)
            i = j
        if i >= len(line):
            return out
        i += 1
        if i == len(line):
            out.append(None)
            return out


def parse(text: str) -> Parsed:  # noqa: C901
    """Read an answer into its parts, refusing what is not in the format."""
    if not text.endswith("\n"):
        msg = "the text does not end with a newline"
        raise FormatError(msg)
    lines = text.split("\n")[:-1]
    # a reader that splits lines the way Python's `splitlines` does must find the same lines
    if text.splitlines() != lines:
        msg = "a character other than the newline breaks a line"
        raise FormatError(msg)
    first = FIRST.match(lines[0])
    if not first:
        msg = f"not the first line of the format: {lines[0]!r}"
        raise FormatError(msg)
    blocks: list[list[str]] = [[]]
    for line in lines[1:]:
        if line == "":
            blocks.append([])
        else:
            blocks[-1].append(line)
    header = [_keyed(line) for line in blocks[0]]
    tables: list[Table] = []
    end = None
    for block in blocks[1:]:
        if not block:
            msg = "two blank lines in a row"
            raise FormatError(msg)
        if block[0].startswith("# end "):
            if len(block) != 1 or end is not None:
                msg = "the end line is alone, and once"
                raise FormatError(msg)
            end = block[0].removeprefix("# end ")
            continue
        if end is not None:
            msg = "a block after the end line"
            raise FormatError(msg)
        if not block[0].startswith("## "):
            msg = f"a block that is no table: {block[0]!r}"
            raise FormatError(msg)
        table = Table(block[0][3:])
        rest = block[1:]
        while rest and rest[0].startswith("# "):
            table.attributes.append(_keyed(rest.pop(0)))
        if not rest:
            msg = f"a table without a column line: {table.heading!r}"
            raise FormatError(msg)
        columns = cells(rest[0])
        table.columns = [c or "" for c in columns]
        for row in rest[1:]:
            if row.startswith("#"):
                msg = f"a row that looks like a structural line: {row!r}"
                raise FormatError(msg)
            parsed = cells(row)
            if len(parsed) != len(columns):
                msg = f"a row of {len(parsed)} cells in a table of {len(columns)} columns: {row!r}"
                raise FormatError(msg)
            table.rows.append(parsed)
        tables.append(table)
    if end is None:
        msg = "no end line"
        raise FormatError(msg)
    return Parsed(int(first.group(1)), first.group(2), header, tables, end)


def _keyed(line: str) -> tuple[str, str]:
    """Read `# key: value`."""
    if not line.startswith("# "):
        msg = f"a header line that does not start with '# ': {line!r}"
        raise FormatError(msg)
    key, separator, value = line[2:].partition(": ")
    if not separator:
        msg = f"a header line without a colon: {line!r}"
        raise FormatError(msg)
    return key, text_of(value)


# ------------------------------------------------------------------------------------- tables of values


def _word(text: str, i: int) -> tuple[str, int]:
    """Read a word of a heading at `i`: a JSON string, or up to the next space."""
    if text.startswith('"', i):
        j = i + 1
        while text[j] != '"':
            j += 2 if text[j] == "\\" else 1
        return json.loads(text[i : j + 1]), j + 1
    j = text.find(" ", i)
    j = len(text) if j < 0 else j
    return text[i:j], j


def heading_of(heading: str) -> tuple[str, str, str, str, str | None, str]:
    """Read `values <resolution>/<dataset> station=<id>[ parameter=<name>][ (exceptions)]`.

    Gives (kind, resolution, dataset, station, parameter or None, the text after the words).
    """
    kind, i = _word(heading, 0)
    # the resolution and dataset are one word each, joined by a slash, and either may be quoted
    resolution, i = _slashed(heading, i + 1)
    dataset, i = _word(heading, i)
    if not heading.startswith(" station=", i):
        msg = f"no station in the heading: {heading!r}"
        raise FormatError(msg)
    station, i = _word(heading, i + len(" station="))
    parameter = None
    if heading.startswith(" parameter=", i):
        parameter, i = _word(heading, i + len(" parameter="))
    return kind, resolution, dataset, station, parameter, heading[i:]


def _slashed(text: str, i: int) -> tuple[str, int]:
    """Read a word that ends at a slash (a quoted one ends at its closing quote, then the slash)."""
    if text.startswith('"', i):
        word, j = _word(text, i)
        return word, j + 1
    j = text.index("/", i)
    return text[i:j], j + 1


def stamp(text: str) -> dt.datetime:
    """Read a timestamp of a table: a date (00:00 UTC) or a time in UTC ending in Z."""
    if len(text) == 10:
        return dt.datetime.fromisoformat(text).replace(tzinfo=dt.UTC)
    if not text.endswith("Z"):
        msg = f"a timestamp without a Z: {text!r}"
        raise FormatError(msg)
    return dt.datetime.fromisoformat(text.removesuffix("Z") + "+00:00")


def _defaults(table: Table, parameters: list[str]) -> dict[str, str | None]:
    """Read the default flags of a table: `flags` is every column's, `flags_by_column` lists those that have some."""
    out: dict[str, str | None] = dict.fromkeys(parameters)
    for key in ("flags", "flags_by_column"):
        value = table.attribute(key)
        if value is None:
            continue
        for note in (NOTE_ALL, NOTE_DIFFER):
            if value.endswith(note):
                value = value.removesuffix(note)
                break
        else:
            msg = f"{key} without its note: {value!r}"
            raise FormatError(msg)
        if key == "flags":
            out = dict.fromkeys(parameters, value)
            continue
        word = r'(?:"(?:[^"\\]|\\.)*"|[^\s,="]+)'
        if not re.fullmatch(rf"{word}={word}(?:, {word}={word})*", value):
            msg = f"a list of flags that is none: {value!r}"
            raise FormatError(msg)
        for name, flags in re.findall(rf"({word})=({word})", value):
            out[text_of(name)] = text_of(flags)
    return out


def values(parsed: Parsed) -> dict[tuple[str, str, str, str, dt.datetime], tuple[float | None, str | None]]:  # noqa: C901
    """Read the tables of values back into what they stand for: a reading is (value or None, quality flags).

    A cell that is empty is a reading with no value (None); a reading with no row is absent from the result. The
    flags of a reading are the default of its column, or those of the period of the table of flags it is in.
    """
    out: dict[tuple[str, str, str, str, dt.datetime], tuple[float | None, str | None]] = {}
    exceptions = {}
    for table in parsed.tables:
        if table.heading.startswith("flags "):
            _, resolution, dataset, station, only, rest = heading_of(table.heading)
            if rest != " (exceptions)":
                msg = f"the heading of a table of flags: {table.heading!r}"
                raise FormatError(msg)
            exceptions[(resolution, dataset, station, only)] = table
    for table in parsed.tables:
        if not table.heading.startswith("values "):
            continue
        _, resolution, dataset, station, only, rest = heading_of(table.heading)
        if rest:
            msg = f"text after the station in {table.heading!r}"
            raise FormatError(msg)
        if table.columns[0] != "timestamp":
            msg = "the first column of a table of values is the timestamp"
            raise FormatError(msg)
        names = [label[: label.rindex("(")] if "(" in label else label for label in table.columns[1:]]
        if only is not None and names != [only]:
            msg = f"a table of the parameter {only!r} with the columns {names!r}"
            raise FormatError(msg)
        defaults = _defaults(table, names)
        mine: dict[tuple[str, dt.datetime], tuple[float | None, str | None]] = {}
        for row in table.rows:
            moment = stamp(row[0] or "")
            for name, cell in zip(names, row[1:], strict=True):
                mine[(name, moment)] = (None if cell is None else float(cell), defaults[name])
        flag_table = exceptions.get((resolution, dataset, station, only))
        for row in flag_table.rows if flag_table else []:
            label, first, last, flags = row
            applied = names if label == "all" else (label or "").split("|")
            low, high = stamp(first or ""), stamp(last or "")
            for name in applied:
                for (column, moment), (number, _) in list(mine.items()):
                    if column == name and low <= moment <= high:
                        mine[(column, moment)] = (number, flags)
        out.update({(station, resolution, dataset, name, moment): reading for (name, moment), reading in mine.items()})
    return out


def truth(frame: Any) -> dict[tuple[str, str, str, str, dt.datetime], tuple[float | None, str | None]]:  # noqa: ANN401
    """Give the readings of a long frame as `values` gives them back."""
    return {
        (r["station_id"], r["resolution"], r["dataset"], r["parameter"], r["timestamp"]): (
            r["value"],
            r.get("quality_flags"),
        )
        for r in frame.to_dicts()
    }


def differences(got: dict, want: dict) -> list[str]:
    """List how what was read differs from the frame: a value, the flags of a reading, a reading that is not there."""
    problems = []
    for key in set(want) | set(got):
        wanted = want.get(key)
        found = got.get(key)
        if wanted is None:
            # a reading the frame has not is an empty cell of a table whose row another parameter has
            if found is not None and found[0] is not None:
                problems.append(f"a value that is not in the frame: {key} {found}")
            continue
        if found is None:
            problems.append(f"a reading that is lost: {key} {wanted}")
        elif (wanted[0] is None) != (found[0] is None) or (
            wanted[0] is not None and found[0] is not None and abs(wanted[0] - found[0]) > 1e-9 * max(1, abs(wanted[0]))
        ):
            problems.append(f"value {key}: {found[0]} != {wanted[0]}")
        elif found[1] != wanted[1]:
            problems.append(f"flags {key}: {found[1]!r} != {wanted[1]!r}")
    return problems
