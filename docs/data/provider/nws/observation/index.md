# Observation

## Overview

NOAA NWS Observation is a collection of **hourly** weather data from US weather stations: one report
for each hour (see [One report an hour](#one-report-an-hour)). Resolution is fixed on hourly and data is
provided for the last week.

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

A station that returns nothing is walked past by `filter_by_rank` without any option and without
using up a rank, so a request for the two nearest stations still returns two that carry data. What
the `skip_empty` option adds is the next step: passing over a station that *did* return data but too
little of it, as `skip_threshold` and `skip_criteria` define. Naming a silent station outright with
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

## One report an hour

The endpoint does not serve hourly data. For a station with an ASOS it holds about 12 observations an
hour: a 5-minute row at every multiple of five minutes (whole degrees Celsius, no sea level
pressure, no precipitation), the routine METAR once an hour at a minute of the station's own (:54 at
KBOS, :53 at KDEN, :51 at KORD and KJFK), and SPECI reports whenever the weather changes. `hourly`
returns one of them for each full hour, stamped with it, so that a frame never holds the same
station-hour twice (GH-2857):

1. an observation belongs to the full hour it is nearest to: 14:53 to 15:00, 14:20 to 14:00, and
   14:30 to 15:00 (a half hour goes to the later hour);
2. of the observations of an hour a *report*, a METAR or a SPECI, is kept over a 5-minute row, which
   the endpoint marks by leaving out the `precipitationLastHour` key (the text of the report is no
   marker: a quarter of the reports have an empty `rawMessage`). Without this rule the 5-minute row
   at the full hour, which is nearer to it than the METAR, would be kept, and with it none of the
   sea level pressure and precipitation;
3. of the reports the one nearest to the full hour is kept, and of two at the same distance the
   earlier one. That is the routine METAR, unless a SPECI was filed closer to the full hour: of
   the 25 hours of KDEN from 2026-10-14 12:00Z to 2026-10-15 12:00Z two keep a SPECI or a report of
   another minute (00:05 and 05:56), which carries no sea level pressure of its own. An hour that holds no
   report at all keeps the 5-minute row nearest to its full hour;
4. a quantity the kept observation has no value for is filled from another observation of the
   hour (see [Gaps of the kept observation](#gaps-of-the-kept-observation)).

The kept observation is stamped with the full hour, 15:00 for the METAR of 14:54, as DWD and ECCC
stamp their hourly readings. DWD's instant readings are those of about ten minutes before the stamp
([time zones and reference times](../../../time_reference.md)), the same kind of reading as a METAR
filed at :51 to :54. The minute of the report is not kept, as in `noaa/ghcn` hourly, which takes
the reading of each parameter nearest to the full hour rather than a whole report (GH-3000).
A full-hour
stamp is what `interpolate` and `summarize` join on, and a stamp at :54 would count for nothing
there; `skip_empty` counts by the truncated hour, and a day of KDEN with its own minutes came to 23
of 25 hours, below its default threshold of 0.95. A missing or late METAR shows as a SPECI or a
5-minute row in its place. Which report an hour keeps does not depend on the window of a request: the
endpoint is asked for half an hour more on either side, and what lies outside the window is cut
after the choice, so the edge of a window holds what a longer window holds there, within the
500-observation cap below.

### Gaps of the kept observation

The kept METAR or SPECI is not always complete: its temperature may not be controlled yet (MADIS
flag `Z`, no value) while a verified 5-minute row of the same hour has one. In 15 stations over 5 days
(read 2026-10-28, 1,766 station-hours) that was so for the temperature in 31 of 1,697 hours (1.8 %), and for
the wind speed in 88 of 1,694 (5.2 %); the donor was a median 0 and 5 minutes from the full hour.
For these quantities a missing value of the kept observation is therefore taken from the other
observation of the same hour that has one, the nearest to the full hour (a report over a 5-minute row at
the same distance, then the earlier), quantity by quantity, so two quantities of an hour may come from
two rows (GH-3480):

- filled: `temperature_air_2m`, `temperature_dew_point_2m`, `humidity_relative`,
  `pressure_air_site_reduced`, `pressure_air_sea_level`, `visibility`, `wind_speed_mean_last_2min`,
  `wind_direction_mean_last_2min`, `precipitation_amount_since_last_routine_report`,
  `precipitation_amount_last_3h` and `precipitation_amount_last_6h`;
- not filled: `wind_gust_max_last_10min` and `temperature_wind_chill`. A METAR leaves the gust out
  when there is none (408 of 460 missing gusts were none, read 2026-10-28), and the wind chill is
  there in the cold only, so the null is the report's answer and a value of another instant, up to
  30 minutes away, would contradict it.

The wind direction is filled only together with the wind speed, from the same row: where the speed
is filled, the direction is that of the row the speed comes from (and stays null if that row has
none, or if its direction is a calm 0 beside a speed above 0). A report that has a speed keeps its
own direction, null or not. The two cases differ in what the null means. A METAR whose speed and
direction are both null is a gap of MADIS (of 52 METARs with a null direction, 36 carried one in
their raw text, `KBOS 270754Z 33007KT`, read 2026-10-28). A METAR that has a speed and no direction
is a variable wind: in a week of 10 stations all 45 such METARs with a raw text were `VRB`
(`KMIA 211053Z VRB05KT`), so the report itself says there is no bearing, and a direction of a row up
to 30 minutes away would contradict it. A calm wind (direction 0, `raw:0`, GH-2794) is a value of
the report and is not replaced; a report with a calm direction and no speed is given no speed of
another row beside it, and a calm row (speed 0, direction 0) that fills the speed brings its calm
direction with it.

`precipitation_amount_since_last_routine_report` is taken from a report filed at or before the kept
one only; see the precipitation entry below.

A filled value comes with the `quality_flags` of the observation it is taken from, never with the
`Z` of the one it fills, and a value the kept observation has is never replaced. An hour with one
observation, or where no other observation has the quantity, keeps its null.

How to read the values of the kept report:

- `wind_speed`, `wind_direction`: the 2-minute averages ending at the report's time, not an hourly
  mean (GH-2837);
- `precipitation_amount_since_last_routine_report` (`precipitationLastHour`, called
  `precipitation_amount` until GH-2841): a running total since the last routine METAR (as the data
  read, the endpoint does not state it), not the amount that fell in the hour before the stamp. The
  kept report is the one rule 3 picks, the routine METAR unless a SPECI was filed nearer to the full
  hour, and its running total is what the hour returns. SPECI do not
  add to it: at KDEN on 2026-10-14 three SPECI (10:27, 10:34, 10:42) and the METAR of 10:53 each
  read 0.3 mm, and the 6-hour amount at 11:53 is 0.8 mm
  (GH-2841). A routine METAR therefore holds the full hour, and a series of these values is an
  hourly total except for an hour that keeps a SPECI. A SPECI that carries the group holds the part
  that had fallen when it was filed. A SPECI without it takes the total of the routine METAR it
  displaced, which was filed before it (KDEN 2026-10-15 00:00: the SPECI of 00:05 has none, the
  METAR of 23:53 says 0.0 mm, which is the value of the hour). A total of a report filed *after* the
  kept one is never used, because the next hour's METAR repeats it and the rain would be counted
  twice. A routine METAR without the group keeps its null unless an earlier SPECI of that hour
  carries it. The 3- and 6-hour amounts are filed with
  the synoptic METARs only and are empty in the others; for an hour in which a SPECI displaces the
  synoptic METAR they are taken from the METAR, whichever of the two was filed first (KDEN: the
  6-hour amount of the 23:53 METAR, the 00Z one, is the value of 00:00, though the report of 00:05
  is nearer to it and is the one kept; no other hour holds it), see
  [Gaps of the kept observation](#gaps-of-the-kept-observation);
- all other parameters are readings at the report's time.

The endpoint answers at most 500 observations per request, about 40 hours, and the provider does
not read the next page, so a longer window returns the latest 40 hours only, the oldest of them
decided on a partial hour (GH-2994).

```{toctree}
:hidden:

hourly.md
```