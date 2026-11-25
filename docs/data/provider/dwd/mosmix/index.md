# Mosmix

## Overview

[Mosmix](https://www.dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html) is a forecast product of 
the DWD that is based on global weather models and that uses statistical downscaling for land-based climate stations 
based on their historical observations to provide more precise, local forecast. Mosmix is available for more than 5000
stations worldwide and is available in two versions, Mosmix-S and Mosmix-L. Mosmix-S comes with a set of 40 parameters 
and is published every hour while MOSMIX-L has a set of 114 parameters and is released every 6 hours 
(3am, 9am, 3pm, 9pm). MOSMIX-L has steps to +247 h and MOSMIX-S to +240 h (DWD says "bis +240h" for both).

Each element has its own window (1, 3, 6, 12 or 24 h), its own UTC steps and its own last step, and `RR1c` and
`RR3c` are zero late in a run while the 12 and 24 h totals still carry rain: see [the elements](elements/index.md).

## MOSMIX-SNOW

The dataset `hourly/snow` is [MOSMIX-SNOW](https://www.dwd.de/EN/ourservices/met_application_mosmix_snow/met_application_mosmix_snow.html),
a forecast of new snow, of the probability of new snow above a depth and of the snow depth for 15 stations in the
Bavarian Alps (`Z901` Hörmoos to `Z946` Kühroint, including `Z914` Zugspitzplatt). A run is published every hour with 48
hourly steps (about 10 KB). The stations of the dataset are those the newest run names (the 15 of the run of
2026-11-14, read from the 10 KB file once per request); the MOSMIX catalogue lists 37 `Z9xx` stations and cannot say
which they are, so a station DWD adds to the run is reachable. Where no run is listed (out of season) or it cannot
be read, `stations` lists those 15.

- DWD publishes it from November to April only, and while there is snow. Where no run is listed a request for values
  is a 404, a `ProductOutOfSeasonError` (an `IssueNotFoundError`, so a `NotFoundError` and an `IndexError` as well):
  from May to October it names the season, from November to April it says that no run is listed. It is no failure
  of the request.
- Request `snow` on its own. A request that mixes it with `small` or `large` is answered as a whole, so out of season
  it is the 404 and no rows of the other datasets; DWD says that the products are not to be mixed.
- The depths are in m in the file and come back in cm (`snow_depth`, `snow_depth_new_last_*h`), the probabilities in
  percent. Each is the window that ends at the timestamp (`end`), the snow depth the state at it.
- The new snow, its probabilities and the snow depth are given at the 00, 03, 06, ..., 21 UTC steps for every station and
  at further steps for some of them (the run of 2026-11-14 19 UTC, where the new snow of Hörmoos is given at 46 of the 48
  steps and that of Zugspitzplatt at 16); temperature, wind and precipitation are given every hour. A step an element has
  no value at is a `-` in the file, which is a null with `raw:-` in `quality_flags` (and no row by default).
- `Sa6`, `Sah` and `Sad` are DWD's sums of the shorter windows: the amount of the 3h values, of the 6h values and of the
  12h values. There is no single-station directory: the dataset reads the `all_stations` file only.
- The units and the meaning of the elements are those of DWD's
  [MetElementDefinition.xml](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml).

## Negative round-off

The model melts the last of a snow cover a little past zero: `SnCv`, the snow depth of MOSMIX-SNOW, is written as -0.01
or -0.02 m for a few hours (20 of 11,760 values in the 49 runs of 2026-11-15 to 2026-11-17, at `Z901` and `Z934`, and
-0.07 m in the run of 2026-11-18). That, the new snow, the amounts of precipitation, the radiation and the sunshine
duration, which cannot be negative, are held to the [plausibility](../../../plausibility.md) check `floor`: by default
(hard) the value is set to 0.0 and the number stays as `rejected:floor,raw:-0.02`; with `plausibility={"floor": "soft"}`
the value is kept as DWD wrote it and flagged `suspect:floor`. Only round-off is clipped, down to a tolerance for each
quantity (-0.2 mm for an amount of precipitation, -0.01 MJ/m2 for the radiation, -10 cm for a depth of snow, -0.02 h for
a duration; the same as for [`dwd/dmo`](../dmo/index.md)): a snow depth of -15 m is no round-off and is not set to 0 but
flagged `suspect:range`, the value kept, as every forecast value outside the range of its parameter. The percentages and
the wind that MOSMIX-L writes below 0 now and then (`RSunD` to -10 %, `N05` to -8 %, `wwS` -1 %, `FF` -0.51 m/s) are not
named by the floor and are held to the range, 0 at the low end: `suspect:range`. `E_DD`, a signed error, has no bound.

## The 24 hours of `TM`

`temperature_air_mean_2m_last_24h` (`TM`, MOSMIX-L only) is "Mean temperature during the last 24 hours" in DWD's
element table, given at the 06 UTC steps; which 24 hours is not stated. Against the hourly `TTT` of the same file, the
run of 2026-10-19 at 10 stations (100 values) fits the UTC day before the step's date (00 to 24 UTC, ending 6 hours
before the step) with a mean absolute difference of 0.33 K, the 24 hours ending at the step with 0.55 K and the UTC day
of the step with 1.1 K. That points one way and is not conclusive. The question was sent to DWD on 2026-10-19 and
2026-11-08 and is not answered (2026-11-22), so the parameter keeps its name, and its description and the
[time reference](../../../time_reference.md) say that the window is unconfirmed and which way the data point. If DWD
answers, the answer decides, and a rename is then a breaking change, announced as such
([GH-3137](https://github.com/earthobservations/wetterdienst/issues/3137)).

## Update date

A forecast is dated by its model run: the `data_updated_at` of the
[`metadata`](../../../../usage/restapi.md#response-metadata) of an answer is the run the forecast is of (the `IssueTime` that the file states), not the time DWD published the file, so it
is the same however often the run is read, and `retrieved_at` less `data_updated_at` is how old the forecast is.

```{toctree}
:hidden:

hourly.md
elements/index.md
```