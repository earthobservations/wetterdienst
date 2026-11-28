# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The compact format: a text of a header and tables, which an assistant reads at a fraction of the JSON (GH-4445).

One writer for every tool that has it, so that the next tool adds a builder and no second grammar. The grammar is
that of `docs/usage/compact.md`; the first line names its version (`# wetterdienst-compact/1 values`), and a reader
ignores a key of the header and a column of a table it does not know. A renamed key or column raises the version.

    # wetterdienst-compact/1 values                 the first line: the format and the tool
    # provider: German Weather Service (dwd/observation)    the header: `# key: value`, one line each
    # warnings: none
                                                    a blank line ends a block
    ## values hourly/temperature_air station=01975  a table: its heading,
    # flags: 1 (all rows)                           its attributes (`# key: value`),
    timestamp,temperature_air_2m(°C)                its column line,
    2026-11-10T00:00Z,4.7                           and a line for each row
                                                    ...
    # end rows=24                                   the last line: how many rows the answer holds

Text is bare where it can be read as it is and a JSON string where it cannot (`quote`, `cell`): that is what keeps a
name, a warning or a licence that holds a line break, a quote or the text of a structural line from being read as
one. An empty cell is no value; an empty text is `""`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

#: the version of the grammar, in the first line of every answer: a key or a column that is renamed raises it
FORMAT_VERSION = "wetterdienst-compact/1"
#: the separator of a table's cells
SEPARATOR = ","
#: what a table of flags says of itself: the note after its default (`flags` attribute of a table of values)
FLAGS_ALL_ROWS = "all rows"
FLAGS_DIFFER = "periods that differ are listed after the table"

#: a character outside ASCII that a JSON string may hold as it is but that is a line break for `str.splitlines`
#: (U+0085, U+2028, U+2029, the C1 controls) or no printable character: written as an escape, so that a reader that
#: splits lines the way Python does reads the same lines
_NEEDS_ESCAPE = re.compile(r"[^\x20-\x7e]")


def _escape(match: re.Match[str]) -> str:
    r"""Write a character that is not printable as `\uXXXX`, and leave a printable one as it is."""
    char = match.group()
    if char.isprintable():
        return char
    code = ord(char)
    if code > 0xFFFF:
        code -= 0x10000
        return f"\\u{0xD800 + (code >> 10):04x}\\u{0xDC00 + (code & 0x3FF):04x}"
    return f"\\u{code:04x}"


def quote(text: str) -> str:
    """Write a text as a JSON string, UTF-8 kept, and no character a line is split at: one line, whatever it holds."""
    return _NEEDS_ESCAPE.sub(_escape, json.dumps(text, ensure_ascii=False))


def _is_bare(text: str) -> bool:
    """Tell whether a text reads back as written: printable, no backslash, no quote at its start, no edge space."""
    return text != "" and text.isprintable() and "\\" not in text and not text.startswith('"') and text == text.strip()


def text_value(text: str) -> str:
    """Write the value of a header line or of a table's attribute: bare, or a JSON string where it could be misread."""
    return text if _is_bare(text) else quote(text)


def token(text: str) -> str:
    """Write a word of a heading (`values hourly/x station=01975`): bare, or a JSON string if it has a space or more."""
    return text if _is_bare(text) and " " not in text and '"' not in text else quote(text)


def number(value: float) -> str:
    """Write a number as short as it reads back: no `.0` of a whole one."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = repr(float(value))
    return text.removesuffix(".0")


def cell(value: object) -> str:
    """Write one cell of a table: a number, a bare text, or a JSON string where the text could be misread.

    None is an empty cell: no value. A text is quoted where it is empty, holds the separator, a quote, a backslash or a
    character that is not printable (a tab, a line break), has an edge space, or starts with `#` (a line of the answer
    that starts so is no row).
    """
    if value is None:
        return ""
    if isinstance(value, bool | int | float):
        return number(value)
    text = str(value)
    if not _is_bare(text) or SEPARATOR in text or '"' in text or text.startswith("#"):
        return quote(text)
    return text


# ---------------------------------------------------------------------------------------------------------- time


def stamp(value: dt.datetime, *, date_only: bool = False, coarse: bool = False) -> str:
    """Write a timestamp in UTC: a date, or the minute, with the seconds (and a fraction) only where they are not zero.

    `coarse` is for a time the system stamped (when an answer was retrieved): no seconds.
    """
    value = value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value.astimezone(dt.UTC)
    if date_only:
        return value.strftime("%Y-%m-%d")
    if coarse:
        return value.strftime("%Y-%m-%dT%H:%MZ")
    text = value.strftime("%Y-%m-%dT%H:%M")
    if value.second or value.microsecond:
        text += value.strftime(":%S")
        if value.microsecond:
            text += f".{value.microsecond:06d}".rstrip("0")
    return f"{text}Z"


def _parse(text: str) -> dt.datetime:
    """Read a timestamp of the metadata block (ISO 8601 with an offset)."""
    return dt.datetime.fromisoformat(text)


def _window_bound(text: str | None) -> str:
    """Write a bound of the window: whole seconds, `..` where it has none (a day ends at 23:59:59.999999)."""
    return ".." if text is None else stamp(_parse(text).replace(microsecond=0))


# ------------------------------------------------------------------------------------------------------ document


@dataclass
class Table:
    """A table: the text after `## `, its attributes, its columns and its rows (the cells written already)."""

    heading: str
    columns: list[str]
    rows: list[list[str]]
    attributes: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Document:
    """An answer: the tool, the header (`(key, text)`, text written as `text_value` does), the tables, the end line."""

    tool: str
    header: list[tuple[str, str]]
    tables: list[Table]
    rows: int


def render(document: Document) -> str:
    """Write a document as text: lines ended by a newline, the last one the `# end` line."""
    lines = [f"# {FORMAT_VERSION} {document.tool}"]
    lines += [f"# {key}: {value}" for key, value in document.header]
    for table in document.tables:
        lines += ["", f"## {table.heading}"]
        lines += [f"# {key}: {value}" for key, value in table.attributes]
        lines.append(SEPARATOR.join(table.columns))
        lines += [SEPARATOR.join(row) for row in table.rows]
    lines += ["", f"# end rows={document.rows}"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------------ header


def _license_text(provider: Mapping[str, Any]) -> str:
    """Write the licence: its identifier (or its name) and the URL of the terms, or that the provider states none."""
    license_ = provider.get("license")
    if not license_:
        return "not stated by the provider"
    name = license_.get("spdx_id") or license_["name"]
    return f"{name} {license_['url']}" if license_.get("url") else str(name)


def _code(code: str) -> str:
    """Write a warning's code as one word: the codes are `a-z` and `-`, anything else is replaced."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", code) or "_"


def warning_text(warning: Mapping[str, Any]) -> str:
    """Write a warning's message, and what it is about (`parameter`, `stations`) where the message does not say."""
    message = str(warning["message"])
    extra = []
    if warning.get("parameter") and warning["parameter"] not in message:
        extra.append(f"parameter {warning['parameter']}")
    stations = warning.get("stations")
    if stations and not all(station in message for station in stations):
        extra.append("stations " + ",".join(stations))
    return message + (f" [{'; '.join(extra)}]" if extra else "")


def header_of(block: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Write the header lines of the `metadata` block of an answer: whose it is, the terms, what was done, the warnings.

    The same for every tool: the provider and network, the licence, the credit line, the source, the processing note,
    the window, the clock, when it was retrieved (and the date the source states for the data), the producer, and the
    warnings, one line each, or `warnings: none`. What the answer's tool adds is the tool's.
    """
    provider = block["provider"]
    request = block["request"]
    lines: list[tuple[str, str]] = [
        ("provider", text_value(f"{provider['name_english']} ({request['provider']}/{request['network']})")),
        ("license", text_value(_license_text(provider))),
        ("attribution", text_value(provider.get("attribution") or "none stated")),
        ("source", text_value(provider["url"])),
        ("processing", text_value(block["processing_note"])),
    ]
    if request.get("start") is not None or request.get("end") is not None:
        lines.append(("window", f"{_window_bound(request.get('start'))}/{_window_bound(request.get('end'))}"))
    lines.append(("time", "UTC"))
    retrieved = stamp(_parse(block["retrieved_at"]), coarse=True)
    if block.get("data_updated_at"):
        retrieved += f" (source updated {stamp(_parse(block['data_updated_at']), coarse=True)})"
    lines.append(("retrieved", retrieved))
    producer = block["producer"]
    lines.append(("producer", text_value(f"{producer['name']} {producer['version']}, doi {producer['doi']}")))
    warnings = block.get("warnings") or []
    if not warnings:
        lines.append(("warnings", "none"))
    lines += [(f"warning {_code(w['code'])}", text_value(warning_text(w))) for w in warnings]
    return lines


# ------------------------------------------------------------------------------------------------------- stations


def stations_table(stations: Iterable[Mapping[str, Any]], *, distance: bool = False) -> Table | None:
    """Write the stations of an answer as a table, each once; None where there are none.

    The columns are the id, name, position, elevation and region; a WMO number, WIGOS identifier and ICAO code only
    where some station has one. A station that is listed for several datasets is listed once.
    """
    seen: OrderedDict[str, Mapping[str, Any]] = OrderedDict()
    for station in stations:
        seen.setdefault(str(station["station_id"]), station)
    rows = list(seen.values())
    if not rows:
        return None
    columns = [
        ("station_id", "station_id"),
        ("name", "name"),
        ("latitude", "latitude"),
        ("longitude", "longitude"),
        ("elevation_m", "elevation"),
        ("region", "region"),
    ]
    columns += [(key, key) for key in ("wmo_id", "wigos_id", "icao_id") if any(row.get(key) for row in rows)]
    if distance:
        columns.append(("distance_km", "distance"))
    return Table(
        "stations", [name for name, _ in columns], [[cell(row.get(key)) for _, key in columns] for row in rows]
    )


# ---------------------------------------------------------------------------------------------------------- values


def _units_of(parameters: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str, str], str]:
    """Map (resolution, dataset, parameter) to the unit of its values, by the name and by the name the source gives."""
    units: dict[tuple[str, str, str], str] = {}
    for parameter in parameters:
        for name in (parameter["name"], parameter.get("name_original")):
            if name:
                units[(parameter["resolution"], parameter["dataset"], name)] = parameter["unit"]
    return units


#: the resolutions whose readings are of whole days: only there is a stamp at midnight a date
WHOLE_DAYS = frozenset({"daily", "monthly", "annual"})


def whole_days(resolution: str) -> bool:
    """Tell whether a resolution is one of whole days (daily or coarser), whose midnight stamps are written as dates."""
    return resolution.lower() in WHOLE_DAYS


def _midnight(value: dt.datetime) -> bool:
    return value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0


def _stamp_texts(series: pl.Series, *, days: bool) -> tuple[list[str], bool]:
    """Write the timestamps of a column in UTC, and say whether they are dates.

    They are where the resolution is one of whole days (`days`) and every stamp is at midnight: then dates only. An
    hourly table whose rows are all at 00:00 keeps its times, which a date would read as a daily value.
    """
    # a stamp without a zone is read as UTC, as everywhere in the library
    zone = getattr(series.dtype, "time_zone", None)
    zoned = series.dt.convert_time_zone("UTC") if zone else series.dt.replace_time_zone("UTC")
    values = zoned.to_list()
    date_only = days and all(_midnight(v) for v in values)
    if date_only:
        return zoned.dt.strftime("%Y-%m-%d").to_list(), True
    if all(v.second == 0 and v.microsecond == 0 for v in values):
        return zoned.dt.strftime("%Y-%m-%dT%H:%MZ").to_list(), False
    return [stamp(v) for v in values], False


def _label(parameter: str, resolution: str, dataset: str, units: Mapping[tuple[str, str, str], str]) -> str:
    """Write the heading of a column: the parameter and, in brackets, the unit its values are in (`?` if none is known).

    The parameter is the text before the first bracket, which is where the unit begins.
    """
    unit = units.get((resolution, dataset, parameter))
    return cell(f"{parameter}({'?' if unit is None else unit})")


def _flags_default(counts: list[tuple[str | None, int]]) -> str | None:
    """Give the flags most of a series' readings have: the first of those with the most."""
    return max(counts, key=lambda item: item[1])[0] if counts else None


def _mixed_flag(text: str) -> str:
    """Write a name or flags text of a list (`name=flags, name=flags`): bare, or a JSON string if it holds ` ,="`."""
    return text if _is_bare(text) and not re.search(r'[ ,="]', text) else quote(text)


def _runs(
    readings: list[tuple[dt.datetime, str | None]], default: str | None, *, ordered: bool
) -> list[tuple[dt.datetime, dt.datetime, str | None]]:
    """Give the periods of a series whose flags are not the default: (from, to, flags) of the readings it has.

    A reading with the default flags ends a period, a missing reading does not. Readings out of time order (the answer
    was sorted) are a period each.
    """
    runs: list[list[Any]] = []
    for timestamp, flags in readings:
        if flags == default:
            runs.append([None, None, flags])
        elif ordered and runs and runs[-1][0] is not None and runs[-1][2] == flags:
            runs[-1][1] = timestamp
        else:
            runs.append([timestamp, timestamp, flags])
    return [(a, b, f) for a, b, f in runs if a is not None]


def _values_tables(
    frame: pl.DataFrame,
    units: Mapping[tuple[str, str, str], str],
    *,
    chronological: bool,
) -> list[Table]:
    """Write the values of a long frame as tables: one for each station, resolution and dataset, a column a parameter.

    A row is a timestamp, in time order, and a reading that is not there is an empty cell. The quality flags are the
    default of each parameter, said under the heading, and the periods that differ, in a table of their own after it.

    An answer the request sorted (`sort`) is in the order of its rows, over all its stations, which a table for each
    station cannot keep (the ranking of the stations is the answer). It has a table for each parameter, in the order of
    the answer, with a `station_id` column where it has several stations (`_ranked_tables`).
    """
    tables: list[Table] = []
    has_flags = "quality_flags" in frame.columns
    if chronological:
        for key, group in frame.group_by(["station_id", "resolution", "dataset"], maintain_order=True):
            station, resolution, dataset = (str(part) for part in key)
            group = group.with_columns(pl.col("value").cast(pl.Float64, strict=False))
            tables += _series_tables(
                group, (station, resolution, dataset), "", units, chronological=True, has_flags=has_flags
            )
        return tables
    for key, group in frame.group_by(["resolution", "dataset"], maintain_order=True):
        resolution, dataset = (str(part) for part in key)
        group = group.with_columns(pl.col("value").cast(pl.Float64, strict=False))
        several = group.get_column("parameter").n_unique() > 1
        for name, part in group.group_by("parameter", maintain_order=True) if several else [((None,), group)]:
            tail = f" parameter={token(str(name[0]))}" if several else ""
            if part.get_column("station_id").n_unique() == 1:
                station = str(part.get_column("station_id")[0])
                tables += _series_tables(
                    part, (station, resolution, dataset), tail, units, chronological=False, has_flags=has_flags
                )
            else:
                tables += _ranked_tables(part, (resolution, dataset), tail, units, has_flags=has_flags)
    return tables


def _ranked_tables(
    group: pl.DataFrame,
    series: tuple[str, str],
    tail: str,
    units: Mapping[tuple[str, str, str], str],
    *,
    has_flags: bool,
) -> list[Table]:
    """Write the readings of one parameter of several stations, in the order of the answer, one row each.

    The columns are `station_id`, `timestamp` and the parameter. The flags are the default of the table, and every
    reading that has other flags is a period of its own, in a table of flags with its station.
    """
    resolution, dataset = series
    parameter = str(group.get_column("parameter")[0])
    texts, _ = _stamp_texts(group.get_column("timestamp"), days=whole_days(resolution))
    numbers = group.get_column("value").cast(pl.String).str.replace(r"\.0$", "").fill_null("").to_list()
    stations = [cell(station) for station in group.get_column("station_id").to_list()]
    where = f"{token(resolution)}/{token(dataset)}{tail}"
    table = Table(
        f"values {where}",
        ["station_id", "timestamp", _label(parameter, resolution, dataset, units)],
        [[station, text, number] for station, text, number in zip(stations, texts, numbers, strict=True)],
    )
    tables = [table]
    if has_flags:
        flags = group.get_column("quality_flags").to_list()
        counts: dict[str | None, int] = {}
        for item in flags:
            counts[item] = counts.get(item, 0) + 1
        default = _flags_default(list(counts.items()))
        exceptions = [
            [station, "all", text, text, cell(item)]
            for station, text, item in zip(stations, texts, flags, strict=True)
            if item != default
        ]
        if default is not None:
            note = FLAGS_DIFFER if exceptions else FLAGS_ALL_ROWS
            table.attributes.append(("flags", text_value(f"{default} ({note})")))
        if exceptions:
            tables.append(
                Table(f"flags {where} (exceptions)", ["station_id", "columns", "from", "to", "flags"], exceptions)
            )
    return tables


def _series_tables(
    group: pl.DataFrame,
    series: tuple[str, str, str],
    tail: str,
    units: Mapping[tuple[str, str, str], str],
    *,
    chronological: bool,
    has_flags: bool,
) -> list[Table]:
    """Write the table of one station, resolution and dataset (and parameter, in `tail`), and its table of flags."""
    station, resolution, dataset = series
    parameters = group.get_column("parameter").unique(maintain_order=True).to_list()
    wide = group.pivot(
        on="parameter", index="timestamp", values="value", aggregate_function="first", maintain_order=True
    )
    if chronological:
        wide = wide.sort("timestamp")
    texts, date_only = _stamp_texts(wide.get_column("timestamp"), days=whole_days(resolution))
    columns = [pl.Series("timestamp", texts)]
    columns += [
        wide.get_column(name).cast(pl.String).str.replace(r"\.0$", "").fill_null("").alias(name) for name in parameters
    ]
    # a cell is a number, which needs no quoting: the separator joins them
    rows = pl.DataFrame(columns).select(pl.concat_str(pl.all(), separator=SEPARATOR)).to_series().to_list()
    where = f"{token(resolution)}/{token(dataset)} station={token(station)}{tail}"
    table = Table(
        f"values {where}",
        ["timestamp", *(_label(p, resolution, dataset, units) for p in parameters)],
        [row.split(SEPARATOR) for row in rows],
    )
    tables = [table]
    if has_flags:
        flags = _flags_tables(
            group, wide.get_column("timestamp"), parameters, chronological=chronological, date_only=date_only
        )
        if flags is not None:
            default, exceptions = flags
            if default is not None:
                attribute, text = default
                note = FLAGS_DIFFER if exceptions else FLAGS_ALL_ROWS
                table.attributes.append((attribute, text_value(f"{text} ({note})")))
            if exceptions:
                exceptions.heading = f"flags {where} (exceptions)"
                tables.append(exceptions)
    return tables


def _parameter_runs(
    group: pl.DataFrame, parameter: str, default: str | None, order: Mapping[dt.datetime, int], *, chronological: bool
) -> list[tuple[dt.datetime, dt.datetime, str | None]]:
    """Give the periods of one parameter whose flags are not the default, in the order of the table."""
    readings = group.filter(pl.col("parameter") == parameter).select("timestamp", "quality_flags").rows()
    readings.sort(key=lambda reading: order[reading[0]])
    ordered = chronological or [r[0] for r in readings] == sorted(r[0] for r in readings)
    return _runs(readings, default, ordered=ordered)


def _flags_tables(
    group: pl.DataFrame, timestamps: pl.Series, parameters: list[str], *, chronological: bool, date_only: bool
) -> tuple[tuple[str, str] | None, Table | None] | None:
    """Give the attribute of a table of values that says its default flags, and the table of the periods that differ.

    The attribute is `flags` with the flags every column has by default, or `flags_by_column` with a list of the
    columns that have some (`name=flags, name=flags`, a name or flags with a space, comma or `=` a JSON string); the
    text of it is not written yet. None where no column has flags most of its readings share (those that have some,
    have them now and then); the whole is None where no reading has any.
    """
    counts = group.group_by(["parameter", "quality_flags"], maintain_order=True).len()
    per_parameter: dict[str, list[tuple[str | None, int]]] = {p: [] for p in parameters}
    for parameter, flags, count in counts.iter_rows():
        per_parameter[parameter].append((flags, count))
    defaults = {p: _flags_default(per_parameter[p]) for p in parameters}
    if all(default is None for default in defaults.values()) and all(len(c) == 1 for c in per_parameter.values()):
        return None
    distinct = set(defaults.values())
    attribute: tuple[str, str] | None
    if distinct == {None}:
        attribute = None
    elif len(distinct) == 1:
        (only,) = distinct
        attribute = ("flags", str(only))
    else:
        listed = ", ".join(f"{_mixed_flag(p)}={_mixed_flag(d)}" for p, d in defaults.items() if d is not None)
        attribute = ("flags_by_column", listed)
    order = {value: index for index, value in enumerate(timestamps.to_list())}
    runs_of: dict[str, list[tuple[dt.datetime, dt.datetime, str | None]]] = {}
    for parameter in parameters:
        # a parameter whose readings all have the flags most of them have has no period
        if len(per_parameter[parameter]) > 1 and (
            runs := _parameter_runs(group, parameter, defaults[parameter], order, chronological=chronological)
        ):
            runs_of[parameter] = runs
    if not runs_of:
        return attribute, None
    grouped: OrderedDict[tuple, list[str]] = OrderedDict()
    for parameter, runs in runs_of.items():
        grouped.setdefault(tuple(runs), []).append(parameter)
    rows = []
    for runs, names in grouped.items():
        label = "all" if len(names) == len(parameters) else "|".join(names)
        rows += [
            [cell(label), stamp(a, date_only=date_only), stamp(b, date_only=date_only), cell(flags)]
            for a, b, flags in runs
        ]
    return attribute, Table("", ["columns", "from", "to", "flags"], rows)


# ------------------------------------------------------------------------------------------------- search, settings


def _search_stamp(text: str | None, resolution: str) -> str:
    """Write the first or last timestamp of a series searched as a table of that resolution writes its stamps."""
    if not text:
        return ""
    moment = _parse(text)
    utc = moment.replace(tzinfo=dt.UTC) if moment.tzinfo is None else moment.astimezone(dt.UTC)
    return stamp(moment, date_only=whole_days(resolution) and _midnight(utc))


def _search_header(search: Mapping[str, Any] | None) -> tuple[list[tuple[str, str]], Table | None]:
    """Write what the row options (`filter`, `sort`, `first`, `by`, `max_rows`) searched: header lines, a table."""
    if not search:
        return [], None
    options = " ".join(f"{key}={value}" for key, value in search["options"].items() if value is not None)
    totals = search["totals"]
    summary = f"searched {totals['searched']}"
    if totals.get("expected") is not None:
        summary += f" of {totals['expected']} expected"
    if totals.get("gaps") is not None:
        summary += f", gaps {totals['gaps']}"
    summary += f"; matched {totals['matched']}, returned {totals['returned']}"
    lines = [("search", text_value(options or "none")), ("search_totals", summary)]
    if search.get("series_omitted"):
        lines.append(("series_not_listed", str(search["series_omitted"])))
    if not search.get("series"):
        return lines, None
    columns = ["station_id", "parameter", "first", "last", "searched", "expected", "gaps", "matched", "returned"]
    rows = []
    for series in search["series"]:
        first, last = series.get("first"), series.get("last")
        rows.append(
            [
                cell(series["station_id"]),
                cell(f"{series['resolution']}/{series['dataset']}/{series['parameter']}"),
                _search_stamp(first, series["resolution"]),
                _search_stamp(last, series["resolution"]),
                *(cell(series.get(name)) for name in columns[4:]),
            ]
        )
    return lines, Table("search series", columns, rows)


def _setting(value: object) -> str:
    """Write the value of a setting: `true`, a number, a word, or the JSON of a mapping."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return number(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _settings_header(settings: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    """Write the settings the values were read with (`with_metadata`): the unit targets on a line of their own."""
    if not settings:
        return []
    targets = settings.get("unit_targets") or {}
    plain = " ".join(
        f"{key}={_setting(value)}"
        for key, value in settings.items()
        if key != "unit_targets" and value not in (None, {})
    )
    lines = [("settings", text_value(plain))]
    if targets:
        lines.append(("unit_targets", text_value(" ".join(f"{key}={value}" for key, value in targets.items()))))
    return lines


#: how the tokens of `quality_flags` read, in the legend of an answer (the JSON's `format` is a paragraph)
_FLAGS_FORMAT = (
    "comma-separated tokens: the source's own flag as the source writes it, then `kind:code`, `raw:<text>` last"
)

#: the checks a plausibility token can name, as the legend of every network words them
_CHECKS = "`range`, `elevation`, `stuck`, `consistency`, `floor`, `limits`, `source`, `step` or `relations`"

#: the meanings of the kinds every network shares and of the zone, as short as they go while true in every case (the
#: JSON's `meaning` says what each check is; `tests/test_compact.py` holds these to what the checks do). Every other
#: kind is written with the whole meaning its network gives it: a cut would drop what it says of the datasets or
#: sources a code applies to (DWD's levels differ by dataset, and a dataset may have none described).
_SHORT_MEANINGS = {
    "suspect": (
        f"The value is kept, but a plausibility check found it implausible: {_CHECKS}, joined with `+` if several. "
        "The check is in the mode `soft` (on a forecast network every check but `floor` and `limits` is), or it is "
        "`source`, the suspect level of the source's own verdict, which is flagged so in the mode `hard` too."
    ),
    "rejected": (
        "A plausibility check in the mode `hard` rejected the number the source wrote, which `raw` holds: the value is "
        f"null, or for `floor` the floor of its quantity (0). The check is one of {_CHECKS}, joined with `+` if "
        "several; a forecast network has none but `floor` and `limits`."
    ),
    "raw": (
        "What the source wrote in place of the value, as it wrote it: a missing-value marker (the value is null, or "
        "what the source documents the marker to mean, no snow as 0), a number no sensor can have produced, a model "
        "value a little below the floor of its quantity (the value is the floor, 0), or after `rejected:<check>` the "
        "number that check rejected. Always the last token."
    ),
    "zone": (
        "The time zone the source stamped the row in, where it is not UTC; the code says how the stamp was shifted. "
        "Rows stamped in UTC carry no token."
    ),
}


def _meaning(kind: str | None, meaning: str) -> str:
    """Give the meaning of a kind of flag: a shared kind has its short words, any other the network's whole meaning."""
    return _SHORT_MEANINGS.get(kind or "", meaning)


def _written(entry: Mapping[str, Any]) -> str:
    """Write how a token of a kind reads: a kind with a set of codes says `<code>`, the table of codes lists them.

    The JSON's `written` names every code of the set (`zone:<mez|mez-1973-75|mez-local-mean-time|woz>`), among them
    those that no reading of the answer has.
    """
    return f"{entry['kind']}:<code>" if entry["kind"] and entry.get("codes") else entry["written"]


def _flags_that_occur(frame: pl.DataFrame, kinds: Iterable[str]) -> set[tuple[str | None, str]]:
    """Give the (kind, code) of every token the `quality_flags` of the frame hold; the kind is None for the plain one.

    A token is `kind:code` where its text before the first colon is a kind of the legend. The first token of a
    reading that is no such token is the source's own flag. Tokens are told apart by commas, which no code holds.
    """
    if "quality_flags" not in frame.columns:
        return set()
    known = set(kinds)
    found: set[tuple[str | None, str]] = set()
    for text in frame.get_column("quality_flags").drop_nulls().unique().to_list():
        for position, token in enumerate(text.split(SEPARATOR)):
            prefix, colon, code = token.partition(":")
            if colon and prefix in known:
                found.add((prefix, code))
            elif position == 0 and token:
                found.add((None, token))
    return found


def _quality_tables(quality: Mapping[str, Any], frame: pl.DataFrame) -> list[Table]:
    """Write what the quality flags that occur in the frame mean: nothing for a kind or a code that does not.

    The JSON keeps the legend of the network whatever the readings hold; here every row costs the reader, and a flag
    that is not in the answer is no use to it. No flag in the answer, no legend.
    """
    kinds = {e["kind"] for e in quality["legend"] if e["kind"] is not None}
    occurring = _flags_that_occur(frame, kinds)
    legend = [e for e in quality["legend"] if any(kind == e["kind"] for kind, _ in occurring)]
    if not legend:
        return []
    attributes = [("column", text_value(f"{quality['column']}: {_FLAGS_FORMAT}"))]
    if quality.get("source_flag_note"):
        # said where this library carries no flag of the source, as the JSON's `source_flag_note` does
        attributes.append(("source_flag_note", text_value(quality["source_flag_note"])))
    tables = [
        Table(
            "quality_flags legend",
            ["kind", "written", "meaning"],
            [[cell(e["kind"]), cell(_written(e)), cell(_meaning(e["kind"], e["meaning"]))] for e in legend],
            attributes,
        )
    ]
    # the codes of a flag the source documents as a closed set (DWD's QN levels): a row for each code that occurs
    codes = [
        [cell(e["kind"]), cell(c["code"]), cell(c["meaning"])]
        for e in legend
        for c in e.get("codes") or ()
        if (e["kind"], c["code"]) in occurring
    ]
    if codes:
        tables.append(Table("quality_flags codes", ["kind", "code", "meaning"], codes))
    # the columns the source's own flag is the code of: only where that flag occurs, and for the datasets of the answer
    if any(kind is None for kind, _ in occurring):
        datasets = {f"{r}/{d}" for r, d in frame.select("resolution", "dataset").unique().rows()}
        source_flags = [e for e in quality.get("source_flags") or () if f"{e['resolution']}/{e['dataset']}" in datasets]
        if source_flags:
            tables.append(
                Table(
                    "source quality flags",
                    ["dataset", "name_original", "description", "levels"],
                    [
                        [
                            cell(f"{e['resolution']}/{e['dataset']}"),
                            cell(e["name_original"]),
                            cell(e["description"]),
                            # the codes of this flag alone, as the dataset's document lists them; the table above has
                            # their words for the ones that occur
                            cell(",".join(c["code"] for c in e["codes"]) if e.get("codes") else None),
                        ]
                        for e in source_flags
                    ],
                )
            )
    return tables


def _metadata_tables(block: Mapping[str, Any], frame: pl.DataFrame) -> list[Table]:
    """Write the heavy parts of the block (`with_metadata`): the parameters, and what the quality flags hold."""
    tables: list[Table] = []
    if parameters := block.get("parameters"):
        tables.append(
            Table(
                "parameters",
                ["dataset", "parameter", "name_original", "quantity", "unit", "aggregation", "timestamp_position"],
                [
                    [
                        cell(f"{p['resolution']}/{p['dataset']}"),
                        cell(p["name"]),
                        cell(p["name_original"]),
                        cell(p["quantity"]),
                        cell(p["unit"]),
                        cell(p["aggregation"]),
                        cell(p["timestamp_position"]),
                    ]
                    for p in parameters
                ],
            )
        )
    if quality := block.get("quality"):
        tables += _quality_tables(quality, frame)
    return tables


def values_document(
    block: Mapping[str, Any],
    frame: pl.DataFrame,
    stations: Iterable[Mapping[str, Any]],
    parameters: Sequence[Mapping[str, Any]],
    *,
    settings: Mapping[str, Any] | None = None,
    tool: str = "values",
) -> Document:
    """Build the answer of a values tool: the header, the stations, a table for each series, what was searched.

    Args:
        block: The `metadata` block of the answer, as its JSON has it (`metadata_to_dict`): the provider, the terms,
            the warnings, the window, the search; its `parameters` and `quality` (`with_metadata`) become tables.
        frame: The values, in the long shape (`station_id`, `resolution`, `dataset`, `parameter`, `timestamp`, `value`,
            `quality_flags`), in the order of the answer.
        stations: The stations the values come from, a row each (as the `stations` of the JSON answer has them).
        parameters: The parameters of the answer with their unit (`name`, `name_original`, `resolution`, `dataset`,
            `unit`), which the column lines carry.
        settings: What the values were read with, written as header lines (`with_metadata`).
        tool: The tool the answer is of, in the first line.

    """
    search_lines, search_table = _search_header(block.get("search"))
    options = (block.get("search") or {}).get("options") or {}
    tables: list[Table] = []
    if station_table := stations_table(stations):
        tables.append(station_table)
    if not frame.is_empty() and "parameter" in frame.columns:
        tables += _values_tables(frame, _units_of(parameters), chronological=not options.get("sort"))
    if search_table is not None:
        tables.append(search_table)
    tables += _metadata_tables(block, frame)
    header = [*header_of(block), *search_lines, *_settings_header(settings)]
    # the readings of the answer: a row of the long frame each, whatever the shape it was asked in
    return Document(tool, header, tables, frame.height)


def values_text(
    block: Mapping[str, Any],
    frame: pl.DataFrame,
    stations: Iterable[Mapping[str, Any]],
    parameters: Sequence[Mapping[str, Any]],
    *,
    settings: Mapping[str, Any] | None = None,
    tool: str = "values",
) -> str:
    """Write the answer of a values tool as compact text (`values_document`, `render`)."""
    return render(values_document(block, frame, stations, parameters, settings=settings, tool=tool))
