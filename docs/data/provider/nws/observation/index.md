# Observation

## Overview

NOAA NWS Observation is a collection of **hourly** weather data from US weather stations. Resolution is fixed on hourly
and data is provided for the last week.

The values come from `api.weather.gov`, which keeps a rolling week per station and clips a window
that reaches further back rather than refusing it — so a request for older data returns nothing
rather than an error. The window a request asks for is passed to the endpoint, which otherwise
answers with its whole week however little of it was wanted.

The station list comes from somewhere else: the MADIS METAR table, narrowed to the stations MADIS
files under the United States. `api.weather.gov` publishes a listing of its own, but it runs to
some fifty thousand stations across four hundred cursor-paged requests — mostly mesonet sites this
provider does not read — which is not something to walk through to answer "which stations are
there".

> [!WARNING]
> The station list is therefore a proxy rather than the truth, and it over-promises: of forty
> stations sampled at random, twenty-five returned observations and fifteen returned an empty list.
> Roughly a third of the listed stations are silent — decommissioned METAR sites, radar and office
> identifiers such as `KPSR` or `KOHX` that were never observation stations, and stations that
> simply have not reported this week.

A station that returns nothing is walked past by `filter_by_rank` without any setting and without
using up a rank, so a request for the two nearest stations still returns two that carry data. What
`ts_skip_empty` adds is the next step: passing over a station that *did* return data but too little
of it, as `ts_skip_threshold` and `ts_skip_criteria` define. Naming a silent station outright with
`filter_by_station_id` returns an empty frame either way.

MADIS files three genuinely American stations under a state code rather than a country code —
Barking Sands on Kauai (`PHBK`) and the two US Virgin Islands airports (`TIST`, `TISX`) — so they
are named one by one rather than caught by the country column, which cannot be read as a state
code in general: `PR` in it is Peru and `GU` is Guatemala, and of its four `VI` rows two are
American and two are British.

Six further rows sit outside the western hemisphere or below the equator and are United States
territory all the same: three duplicate Amchitka entries (`PAHT`, `KAHT`, `PAAH`), Shemya (`PASY`),
Pago Pago (`NSTU`) and Tinian (`PGNT`). They are listed, since deciding nationality by hemisphere
is not something this provider should do — but only `PASY` and `NSTU` are stations
`api.weather.gov` knows, and both are silent at present, so expect nothing from any of the six.

```{toctree}
:hidden:

hourly.md
```