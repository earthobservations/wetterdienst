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

and in several languages via the `language` argument (`de`, `en` (default), `es`, `fr`, `mul`).

Because the products are full snapshots, an empty result simply means there are currently no active
warnings. The data faithfully follows the official
[CAP DWD Profile](https://www.dwd.de/DE/leistungen/opendata/help/warnungen/cap_dwd_profile_en_pdf_1_12.pdf).

## Update date

The `data_updated_at` of the [`metadata`](../../../../usage/restapi.md#response-metadata) of an answer is the newest
`sent` of the warnings in it, which DWD states in each of them (a warning that is updated is sent again). A snapshot
with no warning has none.

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
may repeat), the affected `warncell_ids` / area names, and a GeoJSON `MultiPolygon` `geometry`
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
[frozen results](../../../../usage/compatibility.md#python-api) of the Python API, and there is no `to_target` for it yet.

## CLI

```bash
# all current warnings on community basis as JSON
wetterdienst alerts

# district basis, German, as GeoJSON
wetterdienst alerts --granularity=district --language=de --format=geojson

# warnings active 6 hours ago (UTC, within the rolling ~48h window; GNU date)
wetterdienst alerts --granularity=district --timestamp="$(date -u -d '6 hours ago' +%Y-%m-%dT%H:%M:%S)"

# write current warnings to a GeoJSON file
wetterdienst alerts --format=geojson --target=file://alerts.geojson
```

## REST API

```bash
wetterdienst restapi
```

```bash
curl "http://localhost:7890/api/alerts?granularity=community&format=geojson"
```
