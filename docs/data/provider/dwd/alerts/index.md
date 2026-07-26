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

## Historical snapshots

DWD keeps a rolling **~48-hour** window of timestamped snapshots (there is no long-term archive).
Pass a `date` to select the warnings that were active at a point in time — the newest snapshot
produced at or before that moment is used. A naive datetime or ISO string is interpreted as UTC. A
`date` outside the rolling window raises an error. Omit `date` for the current (latest) snapshot.

```python
from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest

# warnings that were active ~6 hours ago
request = DwdWeatherAlertRequest(granularity="district", date="2026-07-26T10:00:00")
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
```

## CLI

```bash
# all current warnings on community basis as JSON
wetterdienst alerts

# district basis, German, as GeoJSON
wetterdienst alerts --granularity=district --language=de --format=geojson

# warnings active at a past point in time (within the rolling ~48h window)
wetterdienst alerts --granularity=district --date=2026-07-26T10:00:00

# write current warnings to a GeoJSON file
wetterdienst alerts --format=geojson --target=file://alerts.geojson
```

## REST API

```bash
wetterdienst restapi --listen 0.0.0.0:3000
```

```bash
curl "http://localhost:3000/api/alerts?granularity=community&format=geojson"
```
