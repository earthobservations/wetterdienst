# DMO

## Overview

[DMO](https://www.dwd.de/DE/leistungen/met_verfahren_ptp_dmo/met_verfahren_ptp_dmo.html) is a new forecast product of 
the DWD that takes model output and extracts it at known meteorological stations to produce consumable timeseries. In 
opposition to the Mosmix product, DMO is not a statistical postprocessing but a pure extraction of model output. The DMO 
product is available for the ICON model in its global (ICON) and regional (ICON-EU) configuration. For ICON-EU, the DMO 
product is available in hourly resolution with a lead time of 78 hours. For ICON, the DMO product is published as two 
runs: hourly out to a lead time of 78 hours, and 3-hourly from 78 out to 168 hours. The long run starts where the 
short one ends -- it is not a 3-hourly grid over the whole 168 hours.

Which parameters a run carries depends on that lead time. Each run carries the same 21 elements, except that the
3-hourly run substitutes the 3-hourly radiation and precipitation fields for their 1-hourly counterparts. `icon`
declares both families, so with the default `lead_time="short"` the four 3-hourly parameters
(`precipitation_height_last_3h`, `radiation_global_last_3h`, `radiation_sky_long_wave_last_3h` and
`water_equivalent_snow_depth_new_last_3h`) return no data, and with `lead_time="long"` the three 1-hourly ones
(`precipitation_height_last_1h`, `radiation_global` and `water_equivalent_snow_depth_new_last_1h`) return none
either. `icon_eu` publishes only the 78-hour run, so its parameters are all carried. Nothing in the request says
so yet, which [GH-1976](https://github.com/earthobservations/wetterdienst/issues/1976) tracks.

```{toctree}
:hidden:

hourly.md
```