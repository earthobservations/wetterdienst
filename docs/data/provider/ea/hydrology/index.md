# Hydrology

## Overview

The EA runs the Hydrology interface as one of their offers to the public. Detailed information can be looked up at their
[EA Hydrology Reference](https://environment.data.gov.uk/hydrology/doc/reference). 
The data provided through ``wetterdienst`` includes:

- flow
- river water level (stage)
- groundwater level (15 minutes)

in resolutions 15 minutes and daily for stations in England.

## Station ids

A station's `station_id` is the `notation` of the listing, a UUID (`959f3e4f-bb6e-4f4a-8082-0157eea99482`). The listing
also gives some stations the ids they have in the Environment Agency's other services, which are columns of their own
(null where the listing gives none), found with `filter_by_sql("nrfa_id = '52017'")`:

- `nrfa_id`, `nrfaStationID` of the listing, the number of the station in the National River Flow Archive (`52017`):
  850 of the 9,537 stations (read 2026-11-17).
- `rloi_id`, `RLOIid`, the id of the station in River Levels on the Internet, which the listing links to
  [Check for flooding](https://check-for-flooding.service.gov.uk/) (`3060`): 1,808 stations. 52 of them have two ids
  (an array in the listing, `["3416", "3060"]`); one is picked so that the same is read every time: the all-digit id, then the lowest (6 of the arrays pair a 4-digit id
  with a code such as `0890TH`, and the 4-digit one is read).

An id can name more than one station (2 NRFA numbers and 64 RLOI ids are on two stations or more). The listing
has two more ids of the station, `wiskiID` (7,588 stations) and `stationReference` (3,520), which are not read.
None of them is a WMO, WIGOS or ICAO id: `wmo_id`, `wigos_id` and `icao_id` are null.

## The source's own verdict (`source`)

Every reading carries the `quality` the API words as "quality: The quality of this reading: Good, Estimated, Suspect,
Unchecked, Missing" ([EA Hydrology Reference, Readings](https://environment.data.gov.uk/hydrology/doc/reference#readings-section)),
as the plain flag of `quality_flags` (a daily reading is followed by its `completeness`). The check `source` reads `Suspect`. Not read: `Good`,
`Estimated` (a treatment), `Unchecked` (no control) and `Missing`. A `Suspect` reading comes with its value: of the 2,000
readings the API gave for 2024-01-01 (read 2026-11-02), 1,378 were `Good`, 563 `Unchecked`, 48 `Suspect`, 8 `Missing` and
3 `Estimated`, and a `Suspect` one reads `{"value": 0.411, "qcode": "Edited", "quality": "Suspect"}`, flagged
`Suspect,suspect:source`.

With `plausibility={"source": "hard"}` the value is null and the token is `rejected:source,raw:<text>`; the
default is `soft`, which keeps the value and writes `suspect:source`, so interpolation and summaries leave it
out. See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

```{toctree}
:hidden:

15_minutes.md
daily.md
```