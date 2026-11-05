# Alerts

## Overview

The DWD publishes its public weather warnings ("Warnungen") in the
[Common Alerting Protocol (CAP)](https://opendata.dwd.de/weather/alerts/cap/) v1.2 format. Each
warning is a CAP XML document describing a single alert — its event, severity, timing, texts and
affected areas. `wetterdienst` exposes the DWD full-snapshot products, which bundle one CAP file per
currently active warning, and flattens every alert into a single row.

Warnings are available on two spatial granularities, selected via the `granularity` argument:

- `community` (default) — per municipality (Gemeinde, `COMMUNEUNION` products)
- `district` — per district (Landkreis, `DISTRICT` products)

and in several languages via the `language` argument (`de`, `en` (default), `es`, `fr`, `mul`); see
[Languages](#languages) for `mul`, which holds eight.

Because the products are full snapshots, an empty result simply means there are currently no active
warnings. The data faithfully follows the official
[CAP DWD Profile](https://www.dwd.de/DE/leistungen/opendata/help/warnungen/cap_dwd_profile_en_pdf_1_12.pdf).

## Update date

The `data_updated_at` of the [`metadata`](../../../../usage/restapi.md#response-metadata) of an answer is the newest
`sent` of the warnings in it, which DWD states in each of them (a warning that is updated is sent again). A snapshot
with no warning has none.

## Languages

`de`, `en`, `es` and `fr` are products of one language: each CAP message has one `<info>` block, in `de-DE`, `en`,
`es` or `fr`. The `mul` product bundles eight in one message, `de-DE` first and then `en`, `fr`, `es`, `ar`, `ru`,
`tr` and `pl`. Measured on the live products (2026-11-06, both granularities, every message of each): the blocks of a
`mul` message differ in **four texts only**, `event`, `headline`, `description` and `instruction`. The times, the event
code, the groups, the parameters and the areas are the same in all eight.

So an alert of `mul` is **one row, the first block's** (German), as for the single languages, and the other seven blocks
are its `translations`: a list, in the order of the message, of the `language` of the block and the fields in which it
differs from the first block, which for DWD's messages are those four texts. A field that is not in a translation is the
row's. `translations` is `[]` for a message of one block, so the answer for `de`, `en`, `es` and `fr` holds `"translations": []`
and is 20 bytes an alert larger.

```json
{
  "alert_id": "2.49.0.0.276.0.DWD.PVW.1793919540000.77ce7ce7-312a-495c-97de-d1e9b23b8f85.MUL",
  "language": "de-DE",
  "event": "NEBEL",
  "headline": "Amtliche WARNUNG vor NEBEL",
  "...": "...",
  "translations": [
    {"language": "en", "event": "fog", "headline": "Official WARNING of FOG", "description": "There is a risk of fog (level 1 of 1).\n...", "instruction": "..."},
    {"language": "fr", "event": "Brouillard", "headline": "ALERTE officielle INTEMPÉRIES pour BROUILLARD", "...": "..."}
  ]
}
```

(The real answer has all the fields of an alert and the seven translations; two are shown, cut.) A block that DWD
should ever let differ in more than text would show that too: the field is then in its translation, and no block is
dropped. A text a block lacks and the first one has is `null` in its translation.

What it costs: the seven languages' texts make the answer for `mul` **12 % larger than the one for `de` on a community
snapshot and 8 % larger on a district one** (593 KB against 666 KB, and 819 KB against 882 KB, as JSON on 2026-11-06;
the geometry is most of an alert, and is held once). Ask for the language you read if you need only one.

## Historical snapshots

DWD keeps a rolling **~48-hour** window of timestamped snapshots (there is no long-term archive).
Pass a `timestamp` to select the warnings that were active at a point in time — the newest
snapshot produced at or before that moment is used. A naive datetime or ISO string is interpreted
as UTC. A `timestamp` outside the rolling window raises an error. Omit `timestamp` for the current
(latest) snapshot.

```python
import datetime as dt

from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest

# warnings that were active ~6 hours ago
six_hours_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6)
request = DwdWeatherAlertRequest(granularity="district", timestamp=six_hours_ago)
result = request.query()
print(result.snapshot)  # UTC production time of the selected snapshot
```

## As DataFrame

`DwdWeatherAlertRequest.query()` returns a `DwdWeatherAlertResult` whose `.df` attribute is a
[polars](https://pola.rs/) DataFrame with one row per alert. Each row carries the alert/info fields
(event, severity, urgency, certainty, timing, headline, description, ...), the DWD event code and
groups, the `parameters` (an ordered list of `{name, value}`, since a name such as `wind direction`
may repeat), the `translations` (the further languages of a `mul` alert, see [Languages](#languages)),
the affected `warncell_ids` / area names, and a GeoJSON `MultiPolygon` `geometry`
combining all of the alert's polygon areas (`null` for alerts that only reference warn cells without
polygons). The result's `.snapshot` attribute holds the UTC production time of the selected snapshot
(`None` for the latest one).

```python
from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest

request = DwdWeatherAlertRequest(granularity="community", language="en")
result = request.query()
print(result.df)
```

The result can also be rendered directly:

```python
result.to_dict()                    # {"snapshot": ..., "alerts": [...]} with nested geometry/parameters
result.to_ogc_feature_collection()  # GeoJSON FeatureCollection (geometry = MultiPolygon, + snapshot)
result.to_geojson()                 # GeoJSON string
result.to_csv()                     # CSV (list columns comma-joined, nested fields JSON-encoded)
result.to_format("GeoJSON", indent=2, with_metadata=True)  # "json", "geojson" or "csv", in any case
```

`to_json` and `to_geojson` take `indent` (a number of spaces, `True` for 4, `False` or `None` for one line, which is
the default here) and `with_metadata`, which puts the `metadata` block (provider, licence, credit line and the date of
the data) first, as the other results do; CSV has no place for it. The result is outside the
[frozen results](../../../../usage/compatibility.md#python-api) of the Python API.

## To a file

`result.to_target("file://alerts.csv")` writes the alerts to a file, in the format its extension names, as
`to_target` of the other results does ([Export](../../../../usage/export.md)):

| File | Holds |
| --- | --- |
| `.json` | what the REST API answers for `format=json`: `metadata`, `snapshot`, `alerts`; an alert has its areas, `parameters`, `translations` and `geometry` nested, as `to_dict` has them |
| `.geojson` | the `FeatureCollection` of `to_geojson`, with `metadata` and `snapshot` as foreign members |
| `.csv` | `to_csv`, bare: no `metadata` block, which `with_metadata=True` writes beside it |

A JSON or GeoJSON file is on one line, as the answer is (a district snapshot is about 614 KB so and 3.7 MB indented);
`pretty=True` (`--pretty` on the command line) indents it with 4 spaces. A CSV file has nothing to indent.

Nothing else is written. A database target (`duckdb://`, `sqlite://`, ...) is refused with an `ExportRefusedError`, as
are `.parquet`, `.xlsx` and the other file types, with the message naming the three the result is written as: an
alert is nested (one alert has several areas, `parameters`, `translations` and a polygon), and there is no table for it yet.
`if_exists` is `replace` (the default), `fail` or `skip`; `append` is refused for a file, as for the other results.

**A row of the CSV is an alert**, the row of `result.df`: one CAP message, so one line per warning, whatever number
of areas it covers. Its columns are the 29 of `df`, in its order (`alert_id`, `status`, ..., `parameters`, `warncell_ids`, `area_names`,
`geometry`, `references`, `language`, `translations`), written as follows:

- text and the codes (`event`, `severity`, `event_code`, ...) as they are; a gap is an empty field;
- `effective`, `onset`, `expires` and `sent` as ISO 8601 strings in UTC, `2026-07-26T07:23:00.000000+00:00`;
- the areas are two fields, `warncell_ids` and `area_names`, each the values of all the alert's entity areas joined
  with a comma: `809272121,809276148` and `Gemeinde Grainet,Stadt Zwiesel`. A name that itself holds a comma cannot be told
  from two names, so read the ids, or use JSON, which keeps both as lists;
- `groups` joined with a comma in the same way;
- `parameters` (the ordered `{name, value}` list, which repeats a name such as `wind direction` where DWD does),
  `translations` (the further languages of a `mul` alert: a list of the `language` and the texts that differ, `[]` for
  a single language) and `geometry` (the `MultiPolygon` of all the polygon areas, empty for an alert of warn cells
  alone) as JSON text in one field, which `json.loads` reads. A geometry is long: that of a large warning passes the 32,767 characters that
  Excel keeps of a cell (4 of the 11 on one district snapshot), and the 131,072 that Python's `csv` module reads of a
  field unless `csv.field_size_limit` is raised, where it raises `_csv.Error: field larger than field limit`. Read
  the geometry from the `.json` or `.geojson` file.

```text
alert_id,status,event,severity,sent,parameters,warncell_ids,area_names,geometry
2.49.0.0.276.0.DWD.PVW.1785050580000.6bd1534c-....ENG,Actual,gale-force gusts,Moderate,2026-07-26T07:23:00.000000+00:00,"[{""name"": ""gusts"", ""value"": ""65-75 [km/h]""}, {""name"": ""wind direction"", ""value"": ""west""}]","809272121,809276148","Gemeinde Grainet,Stadt Zwiesel","{""type"": ""MultiPolygon"", ""coordinates"": [[[[12.0, 49.0], ...]]]}"
```

(The real file has all 29 columns; 9 are shown, in their order, and the geometry is cut.) What a row holds is what
the frame holds, in every format: the fields of the first `<info>` block of the CAP message, and its further blocks as
`translations`. A `mul` message of eight languages is still one row of the CSV, with the seven others as JSON text in
its `translations` field, as the same list is in a JSON or GeoJSON file
([#3801](https://github.com/earthobservations/wetterdienst/issues/3801)).

A snapshot without a warning is written as it is: `"alerts": []` beside the `metadata` block in JSON, no features
in GeoJSON and the header alone in CSV, where the other results leave a target as it is for an empty result. No warning is an answer, and a file
that a schedule rewrites must not keep the warnings of the run before.

The JSON and the GeoJSON file carry the licence, the credit line and the date of the data in their `metadata` block. A
CSV file has no place for it, so `with_metadata=True` writes the block beside any of the three, as
`alerts.csv.metadata.json`, the block `/api/alerts` answers with:

```python
result.to_target("file://alerts.csv", with_metadata=True)  # alerts.csv and alerts.csv.metadata.json
```

## CLI

```bash
# all current warnings on community basis as JSON
wetterdienst alerts

# district basis, German, as GeoJSON
wetterdienst alerts --granularity=district --language=de --format=geojson

# warnings active 6 hours ago (UTC, within the rolling ~48h window; GNU date)
wetterdienst alerts --granularity=district --timestamp="$(date -u -d '6 hours ago' +%Y-%m-%dT%H:%M:%S)"

# write current warnings to a GeoJSON file, or a CSV one with its metadata beside it
wetterdienst alerts --target=file://alerts.geojson
wetterdienst alerts --target=alerts.csv --with-metadata
```

With `--target` the extension (`.json`, `.geojson` or `.csv`) decides the format, as it does for `stations` and
`values`, so a `--format` that names another one, or a file of another type, is a usage error (exit code 2), and a
database `--target` is refused. `--pretty` indents a JSON or GeoJSON file. `--if-exists` is `replace` by default, and `--with-metadata` writes
`<file>.metadata.json` beside the file, so it needs a `--target`. A file that cannot be written, or that `--if-exists=fail`
finds there, is an error with exit code 1.

## REST API

```bash
wetterdienst restapi
```

```bash
curl "http://localhost:7890/api/alerts?granularity=community&format=geojson"
```
