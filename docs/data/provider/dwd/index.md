# DWD

## Overview

The data as offered by the DWD through ``wetterdienst`` includes:

- [Observation](observation/index.md) — historical weather observations
    - historical (reaching back to the 19th century), recent (~500 days to yesterday) and now
      (yesterday up to the last hour) periods
    - every minute to yearly resolution
    - time series of over 1000 stations in Germany
- [Mosmix](mosmix/index.md) — statistically optimized point forecasts derived from weather models
    - MOSMIX-S (40 parameters, updated hourly) and MOSMIX-L (114 parameters, updated every 6 hours)
    - more than 5000 stations worldwide, forecast horizon up to 240 hours
- [DMO](dmo/index.md) — raw point forecasts extracted from weather models (no statistical postprocessing)
    - ICON (global) and ICON-EU (regional) models
    - hourly resolution (78 h lead time) and, for ICON, a second run 3-hourly from 78 to 168 h
    - ICON: more than 5000 stations worldwide, 23 parameters; ICON-EU: about 3700 stations, 19 parameters
- [Road](road/index.md) — weather observations from German motorway ("road") stations
    - 15-minute resolution, distributed in BUFR format
- [POI](poi/index.md) — current weather reports, the observed counterpart to MOSMIX
    - hourly resolution, roughly the last day, for the ~970 MOSMIX stations that report
    - 39 parameters, including the previous day's temperature and wind extremes
- [Pollen](pollen/index.md) — the forecast of the pollen load
    - daily resolution: the load of eight pollen types for today, tomorrow and the day after, for 27 regions of Germany
    - eight parameters, `pollen_load_birch` and its siblings, from one small JSON file that DWD rewrites every morning
- [UVI](uvi/index.md) — the forecast of the UV index
    - daily resolution: the highest UV index of today, tomorrow and the day after, for 38 places in Germany
    - one parameter, `uv_index_max`, from one small JSON file that DWD rewrites every morning
- [Radar](radar/index.md) — radar-based precipitation products
    - composite, radolan, sites and radolan_cdc
    - RADOLAN: gauge-calibrated areal precipitation; the composites RV (5-minute precipitation) and WN (reflectivity), each with a two-hour forecast
- [Derived products](derived/index.md) — secondary products computed from primary observations
    - technical products (heating/cooling degree days, climate correction factor) and climate
      products (radiation & sunshine duration, soil data)
    - hourly, daily and monthly resolution, for stations in Germany
- [Alerts](alerts/index.md) — public weather warnings in Common Alerting Protocol (CAP) format
    - all currently active warnings, one row per alert, with GeoJSON MultiPolygon geometry
    - community (Gemeinde) or district (Landkreis) granularity, several languages
- [Storm cells](storm_cells/index.md) — the thunderstorm cells KONRAD3D detects in the radar data
    - the newest scan, or one of the last 48 hours, one row per cell, every 5 minutes
    - severity, hail, heavy rain and gust flags, speed, direction, GeoJSON outline and forecast track
- [KOSTRA heavy rainfall](kostra/index.md) — DWD's heavy-rainfall statistics (KOSTRA-DWD-2020), a point lookup
    - for a point in Germany, the depth, intensity and uncertainty of a rain by 22 durations (5 minutes to 7 days) and 9 return periods (1 to 100 years)
    - the 5 km grid cell that holds the point, from tables that DWD wrote in December 2022
- [Phenology](phenology/index.md) — observed plant development dates from the phenological network
    - annual resolution: the day (`Jultag`) a plant reached a phase (flowering, leaf unfolding, harvest)
    - 110 plant datasets across two reporter groups, reaching back to 1925

## Update date

The `data_updated_at` of the [`metadata`](../../../usage/restapi.md#response-metadata) of an answer is what DWD
states of when the data was last updated, by network:

- **Files** (`observation`, `derived`, `phenology`, `poi`, `road`, and a `RadarResult` of `radar`): when DWD last wrote
  the file or files the answer was built from, the `Last-Modified` of their download, the newest of those that have
  rows in the answer. The daily archives of the observations are rewritten every day, so their date is that of the
  rewrite and not a sign that a reading in them changed. An archive cached before the library kept the date has none
  until its copy expires (12 hours at most) or the cache is cleared.
- **Forecasts** (`mosmix`, `dmo`, `swsmos`): the model run the forecast is of, which the file states (`IssueTime`) or
  its name does, and not when the run was published as a file. `pollen` and `uvi` have no run: it is when DWD last wrote
  its file.
- **Alerts**: the newest `sent` of the warnings in the answer.
- **Storm cells**: when DWD wrote the file of the scan, about 5 minutes after the scan it is of.

For a quick overview of the work of the DWD check the current
[dwd report](https://www.dwd.de/SharedDocs/downloads/DE/allgemein/zahlen_und_fakten.pdf?__blob=publicationFile&v=14)
(only in german language).

## License

The German Weather Service publishes its open data under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), "providing the source is duly acknowledged":
the text form is "Source: Deutscher Wetterdienst". Take a look at the
[Open Data Strategy at the DWD](https://www.dwd.de/EN/ourservices/opendata/opendata.html),
the [Official Copyright](https://www.dwd.de/EN/service/legal_notice/legal_notice.html) and the
[rules for acknowledging the DWD as source](https://www.dwd.de/EN/service/legal_notice/templates_dwd_as_source.html)
before using the data. Every answer of the REST API names the licence and the credit line in its
[response metadata](../../../usage/restapi.md#response-metadata).

The rules for acknowledging the DWD (read 2026-11-06) say the source details are due for data "used without
alteration" and also "if extracts of the data/services are used or if the data format is changed"; "In the event of more
advanced alterations or any processing, layout redesigns or other adaptation of the data/services, the DWD at least
expects to be mentioned in a central list of references or in the imprint/publishing details", with wordings such as
"Based on data from Deutscher Wetterdienst, averaged over individual values"; and the source details "must be placed
immediately next to the information used". For the official warnings the rule is stricter: "If any of the official
weather warnings issued by the DWD is changed, the source details provided with the data/services have to be deleted."
The `alerts` network reshapes the warnings into a table and leaves their content as the CAP files give it, which is our
reading of "not changed"; that is not DWD's. The
[open data page](https://www.dwd.de/EN/ourservices/opendata/opendata.html) adds that "service and availability levels
cannot be guaranteed" for opendata.dwd.de. DWD states no limit on requests on the pages read; the library fetches the
files of the next four stations while it parses one (`fetch_ahead`), and the page on
[what it does with the data](../data-use.md#how-it-asks-the-provider) says what else it does.

```{toctree}
:hidden:

dmo/index.md
mosmix/index.md
observation/index.md
road/index.md
swsmos/index.md
poi/index.md
pollen/index.md
uvi/index.md
phenology/index.md
radar/index.md
derived/index.md
alerts/index.md
storm_cells/index.md
kostra/index.md
```