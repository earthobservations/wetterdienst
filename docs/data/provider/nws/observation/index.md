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
> simply have not reported this week. Set `ts_skip_empty=True` to have a rank-based request walk
> past them to stations that actually carry data.

A handful of stations sit outside the western hemisphere or below the equator and belong to the
United States all the same: the Aleutians west of Amchitka (`PASY`, `PAHT`, `KAHT`, `PAAH`), Pago
Pago (`NSTU`) and Tinian (`PGNT`). They are listed. MADIS also files a few genuinely American
stations under a state code rather than a country code — Barking Sands in Hawaii (`PHBK`) and the
two US Virgin Islands airports (`TIST`, `TISX`) — and those are *not* listed, since the same column
gives Guatemala the code `GU` that the United States gives Guam.

```{toctree}
:hidden:

hourly.md
```