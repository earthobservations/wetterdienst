# Observation

## Overview

KNMI's [Data Platform](https://dataplatform.knmi.nl/) provides 10-minute, hourly, daily, monthly and annual in-situ
meteorological observations from KNMI's station network across the Netherlands (the North Sea platforms and the
Caribbean Netherlands included). The values and the stations are read from the platform's
[EDR API](https://developer.dataplatform.knmi.nl/edr-api), which answers a range of several stations in one request.

## The key

The EDR API needs a key of its own, which is not the key of KNMI's Open Data API. Register at
[developer.dataplatform.knmi.nl](https://developer.dataplatform.knmi.nl/) and request an EDR key in the API Catalog
(`/apis` of the portal; the key is shown once, note it down), then set it:

```bash
export WD_AUTH__KNMI_EDR=<edr_key>
```

or `Settings(auth={"knmi_edr": "<edr_key>"})`. A key of the Open Data API is refused by the EDR API with a 403, and the
other way round. Until 0.186.0 the library read KNMI's Open Data files with the key of the former `auth.knmi` setting; it no longer
does. That setting, where it is still set, is ignored with one warning that names `WD_AUTH__KNMI_EDR` (the value is
never printed), so a process that still has it goes on serving every other provider, and a KNMI request without an EDR
key is refused with an error that says the old key no longer works. A request without the key, or with one the API
refuses, is an error that says where to get one. `wetterdienst auth
--provider=knmi --network=observation`, `GET /api/auth` and the MCP tool `auth` ask the API whether it takes the key
(`GET /`, one request of the quota; a refusal costs none), and `coverage` says whether it is `configured`.

The quota of a registered key is 1,000 requests an hour and 200 a second, whatever the size of a request (the API's
`X-Ratelimit-*` headers say how much is left). A 429 ends the query with an error that says so; nothing is read from
anywhere else.

## How the values are read

The EDR API answers `GET /collections/{collection}/locations/{wsi,wsi}?datetime=start/end&parameter-name=A,B` with
CoverageJSON (asked for compressed: a year of hourly values is about 25 KB). One request holds at most 300,000 points,
that is times times parameters times stations; beyond it the API answers 413.

- **Parameters.** Every parameter of the dataset is asked for (16, 12, 13, 23 and 23), whichever were requested: the
  core judges a parameter against its neighbours in the dataset (the maximum of a day against its mean and its minimum),
  and one request per dataset is one cached chunk for every parameter.
- **One station.** A request is a block of the calendar: a month at 10 minutes, a year at hourly and daily, a decade at
  monthly and annual, so that a query that overlaps an earlier one is served from the cache (below). The 10-minute and
  the hourly stamps mark the end of their interval, so their block is (its first moment, the first moment of the next
  block]: the calendar year 2020 of hourly values, 2020-01-01 01:00 to 2021-01-01 00:00, is one request (a query from
  2020-01-01 00:00 reaches back into 2019, the interval that ends then, and is two). A year of hourly values of one
  station is one request, ten years of 10-minute values 120.
- **Several stations.** The stations of the query that follow the one in hand are read with it: as many in a request as
  fit under the limit. For the stations that were asked for the cheaper of the blocks and the exact range is taken, the
  blocks where they cost the same: a day of 77 stations of hourly values is one request of the 24 hours (the blocks of a
  year would be 39), and 10 years of daily values of 70 stations are 12. The stations are planned batch by batch, as
  they are read (below), so 77 stations of 10 years of hourly values take 314 requests, not the 10 of a station times the
  stations that fit one request. `/locations/{ids}` and
  `/cube?bbox=` answer the same stations with the same values for the same request and count the same points
  (measured 2026-11-12), so a query of many stations costs no fewer requests that way.
- **Memory.** The readings of the stations that are read ahead are held until the walk comes to them, so no more than
  about 3 million points are read ahead: a long range is read one station at a time, a day of every station at once.
  `interpolate` and `summarize`, which stop where the data says, read the one station in hand.
- **Cost** (counted as the walk makes the requests, `edr.estimate_requests`). One station: a day of hourly values, 1
  request; a year, 1; ten years, 10; ten years of 10-minute values, 120. For 77 stations: a day of hourly or of 10-minute
  values, 1; a year of daily values, 2; ten years of hourly values, 314. All of the hourly values from 1951 for the 73
  stations that have them, 5,548; all of the 10-minute values from 2012 for the 76 that have them, 13,680. Each distinct range of the cache is a request the
  first time and none for 12 hours (settled) or 5 minutes (the last 6 hours).
- **Quota.** A query that takes more than 1,000 requests that the cache does not hold, which is the quota of the key for an
  hour, is refused before anything is asked, with a `RequestError` (REST 400) that gives the count and asks for a
  narrower range or fewer stations. `interpolate` and `summarize`, which stop where the data says, are not counted.
- **Not asked for.** A period that has not ended (the running 10 minutes, hour, day, month or year) and anything before
  the start of the collection (2012 at 10 minutes, 1951 hourly, 1901 for the other three).
- **Cache.** A chunk is kept under its URL, which holds the collection, the stations, the parameters and the stamps: a
  chunk whose last stamp is less than 6 hours old is kept for 5 minutes, any other for 12 hours (KNMI validates the
  hourly and the daily values one to four weeks after their period and replaces them then, so the twelve hours are a
  cap on how stale a copy is, and no claim that it is final). The stations of a request are part of the URL: `[A, B]`
  and then `[A]` are two requests, and `[A]` twice is one. The key is sent in a header and is in no URL, log line,
  repr or cached file; two keys do not share a copy.
- **Failures.** A 404 is no data in the chunk (not an error; asked once, as every request is a unit of the quota). A
  413 is asked again in two parts. A 400 or 422 means the API refused a station it does not know: the stations of the
  request are cut in two until the refused one is alone, which is then left out for the rest of the query with a warning
  (each distinct reason once), never asked for again, and the answer says `file-skipped` of it (a request that was
  turned down, not a station without values). KNMI answers 400 for an unknown parameter or datetime too, which is no
  station: a station refused alone before anything is answered waits (the walk goes on with the others, whatever its
  place in the order) and is left out once a request is answered; if the next request of several stations is refused as
  well, or none is answered, or a third station is refused, the query ends with a `DownloadError` that gives what the
  client knows of the 400. A 5xx or a dropped connection is retried twice, then it is a
  `DownloadError` (a 502); a 429 or an answer that is no CoverageJSON is a `DownloadError`; no connection a
  `NoInternetError`; a refused key a `CredentialRejectedError`. A range read in part is never an answer.

The "validated" collections lag real time (hourly: the values of an hour come 5.5 to 78 hours after it, median 25), so
only historical data is available; a period that is not yet published simply has no data in the answer.

## Timestamps and codes

The API stamps a value with the END of its interval, as the time coordinate of KNMI's NetCDF files does. The 10-minute
and the hourly values keep that stamp (the air temperature of 09:00 UTC, the past minute before it, is at 09:00, an hourly
sum at the end of its hour). A day, a month and a year are dated with their first moment, as every provider dates them:
the day of 2020-01-01 (De Bilt: TG 0.8, TN -0.2, TX 1.8, RH 0.0) is stamped `2020-01-02T00:00Z` by the API and is
2020-01-01 here. A request for the daily, the monthly or the annual resolution alone floors its `start` to the day, the
month or the year, so that one that begins inside it includes it.

The codes of the source are passed through by the API and handled as they always were: a NaN (a null of the API) is null,
`-1` for a trace of precipitation or of sunshine is 0.0 (not in the monthly and the annual values, whose sums describe no
such code), 0 (calm) and 990 (variable) of the hourly wind direction and 9 of the cloud cover (octants, "9=sky
invisible") are null, each with the source's number as the `raw:` token of `quality_flags`. A parameter that a station has
no sensor for is left out of its coverage by the API and is a null row, as the NaN of the files was (the 10-minute `tg` is
no empty row before 2020-07-23 07:40, the first file of the platform that carried it). The one difference is a station
whose values the files carried all as NaN, which has no rows in the API (06315 at 10 minutes, 06216 at annual): with
`drop_nulls=False` the files gave its null rows and the API gives none. The rows an answer is made into are
those the files returned until GH-3928 (`tests/provider/knmi/observation/files/frozen_*.csv`).

The monthly and the annual datasets (GH-4006) have the variables of the daily one, with `TG` the mean of the daily means,
`TN` and `TX` the extremes of the period and `RH`, `DR`, `SQ` and `Q` the sums; a variable a station does not measure is
missing. Not served, because the canonical parameters have no name for them yet: `EV24` (the potential evapotranspiration
of the period, where `evapotranspiration_potential_last_24h` is a day's), `FHVEC` (the vector mean wind speed), `T10N` (the
minimum air temperature at 10 cm), `VVN` and `VVX` (the minimum and maximum visibility, a code from 0 to 89 and no
distance) and `W1`, `W2`, `W3`, `W5` and `W6` (the number of "daily intervals" with fog, rain, snow, thunderstorm and ice
formation, which hold 0 or 1 for a whole year and so are no count of days).

## Stations

`GET /collections/{collection}/locations` lists the stations: 77, the same for every collection, with the name, the
position, the height above sea level, the `type` and the WMO number (`wmoId`, the `station_id`) and the WIGOS station
identifier as the `id` (`0-20000-0-06260` for De Bilt, the station's `wigos_id`). It has no dates, so two more requests
tell which stations are closed and when: two requests for the lists, one for the monthly values of the closed stations
and one for the daily values of each (8 on 2026-11-12), for every resolution, kept for 12 hours (both lists) and a week
(the dates):

- `/locations?datetime=<today>/<today>` lists the stations that are open: those the full list has and this one has not are
  closed (five on 2026-11-12: F16-A `06206`, Valkenburg `06210`, Hoorn-A `06212`, Soesterberg `06265`, Hoofdplaat
  `06311`). That list filters by the dates of the station in KNMI's catalogue and not by those of its data (Schiphol, whose
  station starts in 1990 and whose daily values in 1951, is not in it for 1960), so it is used to tell closed from open
  and never to cut a window by the start of a station.
- `end_timestamp` of a closed station is the end of its last day with a value. The last monthly value is not it: the
  last month of a station usually has none, so a cut there drops a station from a window it has data in (Soesterberg:
  last monthly value June 2008, daily values to 2008-11-16; F16-A: July 2020, to 2020-08-30; Hoorn-A: October 2022, to
  2022-11-27). One request for the monthly values of the closed stations (23 parameters, as many stations as fit) names
  the month, and one for the daily values of each from that month on names the day: Soesterberg 2008-11-17, Valkenburg
  2016-05-03, F16-A 2020-08-31, Hoorn-A 2022-11-28, Hoofdplaat 2016-02-01 (a day later at 10 minutes and hourly, whose
  data runs past the last day: F16-A has 10-minute values 12 hours after it, Hoorn-A about 40). It is empty for a station that is open,
  which is still reporting, and for a closed one without a value. A listing for a window leaves a station closed
  before it out (`limit_to_window`; Soesterberg was the second nearest station to De Bilt in a listing for 2026,
  GH-4008). `start_timestamp` is empty.
- The list of a resolution is the list without the stations its dataset cannot hold: the four fog stations
  (Assendelft `06233`, Muiden `06236`, Nieuw-Vennep `06237` and Nieuwkoop `06238`, compared by `type` stripped and in lower
  case) are 10-minute stations only, block 78 (Saba `78871`, Sint Eustatius `78873`, Bonaire `78990`) has daily and monthly
  values and no annual ones (the annual collection answers 404, read 2026-11-12), and a station that closed
  before a collection began (the 10-minute data starts in 2012) is not listed for it.

Each station's `station_id` is the WMO station number (`06260`) and its `wigos_id` the full identifier.

## License

Data is © KNMI, CC BY 4.0. See the [KNMI Data Platform](https://dataplatform.knmi.nl/) for further
information and usage conditions.

```{toctree}
:hidden:

10_minutes.md
hourly.md
daily.md
monthly.md
annual.md
```
