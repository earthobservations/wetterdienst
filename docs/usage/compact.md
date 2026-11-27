# Compact format

The compact format is a text of a header and tables. It carries what the JSON of an answer carries (the provider, the
licence and the credit line, what wetterdienst did to the data, the warnings, the stations, every reading with its unit
and its quality flags) in a tenth of the characters or less, for a reader that pays for every one: an assistant that
reads the answer in its context, or a script that has no use for the JSON's keys. `values` has it today
(GH-4445); the other tools get it one at a time.

| Where | How |
| --- | --- |
| REST API | `GET /api/values?...&format=compact`, answered as `text/vnd.wetterdienst.compact; charset=utf-8`, one body (held to `rows`, not streamed) |
| Command line | `wetterdienst values ... --format=compact` |
| Python | `ValuesResult.to_compact(with_metadata=False)`, or `to_format("compact")` |
| MCP | the `values` tool, which answers `compact` when a call gives no `format` (its schema says so); `format=json` asks for the JSON |

On the live instance (2026-11-25) 264 hourly rows of one
parameter are 50,258 characters of JSON and 6,623 of compact text (-87 %); 89 days of 14 parameters are 229,554 and
7,836 (-97 %). A tool's answer is cut at
40,000 characters, which hold 1,691 hourly timestamps of one parameter in this format against 206 in the JSON.

## An answer

```text
# wetterdienst-compact/1 values
# provider: German Weather Service (dwd/observation)
# license: CC-BY-4.0 https://creativecommons.org/licenses/by/4.0/
# attribution: Source: Deutscher Wetterdienst
# source: https://opendata.dwd.de/climate_environment/CDC/
# processing: Processed by wetterdienst: the provider's data was reshaped into a uniform table, and its units converted where they differ.
# window: 2026-10-22T00:00Z/2026-10-30T23:59:59Z
# time: UTC
# retrieved: 2026-11-25T22:50Z (source updated 2026-11-25T09:05Z)
# producer: wetterdienst 0.199.0, doi 10.5281/zenodo.3960624
# warning missing-value-marker: 25 readings of the source were a marker for a missing value and are null, at 01975 Hamburg-Fuhlsbüttel (25); with drop_nulls they are not in the answer, ...

## stations
station_id,name,latitude,longitude,elevation_m,region,wmo_id
01975,Hamburg-Fuhlsbüttel,53.6332,9.9881,11,Hamburg,10147

## values daily/climate_summary station=01975
# flags: 1 (periods that differ are listed after the table)
timestamp,cloud_cover_total_mean(%),humidity_relative_mean(%),precipitation_amount(mm),precipitation_form(-),pressure_air_site_mean(hPa),pressure_vapor_mean(hPa),snow_depth(cm),sunshine_duration(h),temperature_air_max_2m(°C),temperature_air_mean_2m(°C),temperature_air_min_0_05m(°C),temperature_air_min_2m(°C),wind_gust_max(m/s),wind_speed_mean(m/s)
2026-10-22,60,83,0,6,1009.1,10.2,0,5.667,13.1,10,4.5,6.8,12.5,5.3
2026-10-23,83.75,91.5,3.6,6,1004.71,10.6,0,0,11.8,9,2.6,5.5,12.7,5.1
2026-10-24,95,84.83,11.8,6,1001.43,10.4,0,0,11.5,9.8,7.2,8.3,16.6,7.6
2026-10-25,,,,,,,0,2.833,12.8,10.5,7.1,8.1,,
2026-10-26,,,0.7,4,,,0,2.3,13,9.8,6.3,7.8,,
2026-10-27,,,1.5,4,,,0,0.1,15.5,12.6,9,9.4,,
2026-10-28,,,0,4,,,0,3.2,13.7,10.6,4.6,8.1,7.2,
2026-10-29,80,92.75,0.1,6,1027.47,12.1,0,3.1,14.5,11,5.7,8.1,5.9,2.4
2026-10-30,100,99.46,0,4,1031.06,11.4,0,0,9.9,9,7.7,7.5,4.8,1.8

## flags daily/climate_summary station=01975 (exceptions)
columns,from,to,flags
cloud_cover_total_mean|humidity_relative_mean|pressure_air_site_mean|pressure_vapor_mean|wind_speed_mean,2026-10-25,2026-10-28,"1,raw:-999"
precipitation_amount|precipitation_form,2026-10-25,2026-10-25,"1,raw:-999"
wind_gust_max,2026-10-25,2026-10-27,"1,raw:-999"

# end rows=126
```

The answer says in its first lines whose data it is, under which licence and with which credit line (as the
`metadata` block of the JSON does, and the headers of the other formats); the table says what each reading is, in the
unit of its column. A blank line ends a block; the last line says how many readings the answer holds, so that a reader
that stopped early knows it.

## The grammar

An answer is lines of UTF-8 text, each ended by a newline (no other character breaks a line, so the lines of
`str.splitlines` are the lines of the format). A line is one of these:

| Line | Is |
| --- | --- |
| `# wetterdienst-compact/<version> <tool>` | the first line: the format, its version and the tool the answer is of |
| `# <key>: <value>` | a line of the header (right after the first line) or an attribute of the table above it |
| `## <heading>` | the heading of a table, after a blank line |
| the line after the attributes | the columns of the table, separated by commas |
| anything else up to a blank line | a row of the table, its cells separated by commas |
| `# end rows=<n>` | the last line, after a blank line: how many readings the answer has: the rows of its long form, one for each non-empty cell and for each null reading the answer keeps (`drop_nulls=false`, which the wide shape always is), the same for either shape (`metadata.counts.rows` is the rows of the shape) |

**The first line** names the version of the format, `1`, and the tool, `values`. A key that is renamed, or a column,
raises the version. A reader ignores a key of the header and a column of a table it does not know: adding one is no
change of the version.

**The header** has these keys, in this order, each once but the warnings:

- `provider`: the provider's English name and `(provider/network)`; `license`: the identifier of the licence and the
  URL of its terms, or `not stated by the provider`; `attribution`: the credit line to cite, or `none stated`; `source`:
  the provider's URL; `processing`: what wetterdienst did to the data (the same text for every provider);
- `window`: the `start/end` of the window the request read in UTC (`..` for a side it has none), where it has one;
- `time`: `UTC`, the zone of every timestamp of the answer; `retrieved`: when the answer was made, and where the source
  states the date of its data, `(source updated ...)`; `producer`: this library, its version and its DOI;
- `warnings: none`, or one line `warning <code>: <message>` for each warning of the answer, in the words of the code
  of the JSON; a warning that is about a parameter or stations the message does not name has them added in brackets.
  A cut to the size budget of a tool (`answer-truncated`) and a forecast that starts at now (`forecast-from-now`) are such
  warnings;
- with `filter`, `sort`, `first`, `by` or `max_rows`: `search` (the options as read) and `search_totals` (what was
  searched, the rows that matched and those returned) and, where the series are not all listed, `series_not_listed`;
- with `with_metadata`: `settings` and `unit_targets`, the settings the values were read with.

A text that holds a line break, a backslash, a character that is not printable, an edge space or a quote at its start
is written as a JSON string, so that no text of the provider or of a warning can make a line of its own: a name with
`\n# warnings: none` in it is one value of one line.

**Tables.** A table's heading says what it is:

| Heading | Table |
| --- | --- |
| `stations` | the stations of the answer, one row each: `station_id`, `name`, `latitude`, `longitude`, `elevation_m`, `region`, and `wmo_id`, `wigos_id`, `icao_id` where a station has one |
| `values <resolution>/<dataset> station=<id>` | the readings of one station and dataset: `timestamp` and a column for each parameter, written `<parameter>(<unit>)`: the parameter is the text before the first `(`, and a unit that is not known is `(?)` |
| `values <resolution>/<dataset> parameter=<name>` | a sorted answer of several stations: the readings of one parameter in the order of the answer, `station_id`, `timestamp` and the parameter (`parameter=` only where the answer has several) |
| `flags <resolution>/<dataset> station=<id> (exceptions)` | the periods in which the readings of that table have other flags than its default (with a `station_id` column in the table of a sorted answer of several stations) |
| `search series` | with a row option: for each station and parameter, from when to when it was searched and how many values matched |
| `parameters`, `quality_flags legend`, `quality_flags codes`, `source quality flags` | with `with_metadata`: what each parameter is (the long descriptions are left out: see `coverage` and `glossary`) and what the flags of the answer mean (below) |

**The legend covers the flags in the answer, and no others** (the JSON's `metadata.quality.legend` keeps those of the
whole network). `quality_flags legend` has a row (`kind`, `written`, `meaning`) for each kind of token that some reading
of the answer has, with the first sentence of its meaning, or a line of its own for the kinds every network has
(`suspect`, `rejected`, `raw`); there is no `documentation` column. `quality_flags codes` has a row for each code that
occurs of a flag the source documents as a closed set, such as DWD's QN levels or a `zone`: with QN 10 in every
reading, it is the one row for 10. `source quality flags` is there where the source's own flag occurs, for the datasets
of the answer. The legend has the `source_flag_note` as an attribute where the library carries no flag of the source.
An answer none of whose readings has a flag has none of these tables: the `parameters` and the settings are still
there.

A word of a heading that has a space, a quote or anything a line cannot hold is a JSON string.

**Cells.** A cell is bare, or a JSON string (UTF-8, `\"` and `\\`, `\n`, `\uXXXX`) where it is empty text, holds a
comma, a quote, a backslash or a character that is not printable, has an edge space or starts with `#`. **An empty
cell is no value**: the reading is not there (the source has none or the request left it out). Numbers are written as
short as they read back, `5` for `5.0`; the unit of the column is not repeated. A timestamp is in UTC, `2026-11-10T04:00Z`,
with seconds only where there are some. A table of a daily or coarser resolution whose timestamps are all midnight has
dates (`2026-10-22`), so that a daily series is a date a row; an hourly or finer table keeps its times, even where all
its rows are at 00:00, which a date would read as a daily value.

**The readings of `values`.** A row is a timestamp, in time order; a column is a parameter. Several stations are
several tables, several datasets of a station too. The `quality_flags` of a reading (see
[the legend](restapi.md#response-metadata)) are written as the default of each column and the periods that differ:

- `# flags: <flags> (all rows)` says every reading of the table has these flags; where some differ, it says `(periods
  that differ are listed after the table)` and the table of flags lists them: the `columns` (`all`, or names joined
  by `|`), the `from` and `to` timestamps (as the table writes them) and the `flags`. The readings of a column between
  the two are those it has; a reading with the default flags ends a period, a missing reading does not.
- `# flags_by_column: a=1, b=3 (all rows)` where the columns have different defaults (a name or flags with a space, a
  comma, `=` or a quote is a JSON string there); no attribute means the default is no flags (null).
- a null reading that the source marked missing keeps its flags: `1,raw:-999` is the text the source wrote.

An answer the request sorted (`sort`) is in the order of its rows, over all its stations, which a table for each
station cannot keep: the ranking is the answer. It has a table for each parameter (`parameter=<name>` in the heading
where there are several), whose rows are in the order of the answer (newest first for `sort=-timestamp`), with a
`station_id` column first where it has several stations, and each period of the table of flags is one reading (with its
`station_id`). A sorted answer of one station has the table of that station, `station=<id>` in its heading.

`shape` does not apply: a table has a column for each parameter in either shape. `with_stations` does not either: the stations
are always in the answer.

## In a tool

A tool's answer is the text twice, as the other text formats are (as the content block and as the structured content
a client may hand the model alone), without the sentence in front that a `csv` has: the header carries the licence,
the processing note and the warnings. The size that is held to the 40,000 characters is that of the structured content,
`{"result": <text>}`, in JSON. An answer over it is cut after whole timestamps (every table to the same one) and says so in
the `answer-truncated` warning with the `timestamp` window to ask for the rest; where one timestamp alone is more than the budget, it is cut after
whole stations, never through the readings of one. The note does not offer `format=csv` with `shape=wide`, which is
larger than this. See [the size of an answer](mcp.md#the-size-of-an-answer).

## Reading it

A reader needs the lines and the cells, and nothing else:

1. read the lines up to the first blank line: the first line, then `# key: value` (a value that starts with a quote is a
   JSON string);
2. read each block after a blank line: `## heading`, the `# key: value` attributes, the column line, the rows; a cell
   that starts with a quote ends at its closing quote, so a comma inside is not a separator;
3. read the `# end rows=` line and compare it to the non-empty cells you read: it is that number where the answer
   keeps no null readings (the default, `drop_nulls=true`), and more where it keeps some (their cells are empty);
4. ignore every key and every column you do not know.

`tests/compact_reader.py` is such a reader, written from this page and sharing no code with the writer, and
`wetterdienst.io.compact` is the writer.

The format is **not frozen**: its keys, its columns and the text of its notes may change in a minor release, announced
in the changelog, with the version in the first line raised where a key or a column is renamed
([what is not promised](compatibility.md#what-is-not-promised)). The `format` value `compact` of the routes, the
commands and the tools is promised.
