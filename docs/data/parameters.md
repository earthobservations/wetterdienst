---
file_format: mystnb
kernelspec:
  name: python3
---

# Parameters

The data that is provided via `wetterdienst` and its implemented services comes in all kinds of different shapes. Every
provider publishes its own parameter codes, so each one is mapped onto a canonical parameter name that means the same
thing everywhere. Those names, and the unit type each of them implies, live in a single table
(`wetterdienst.metadata.parameter_table`) that every provider's metadata is tested against, so a name cannot mean two
different quantities depending on who reported it.

The glossary below lists them all. The provider pages link into it, so from any provider's parameter table you can jump
to what the parameter actually is.

## Metadata Model

Import the provider specific metadata model like:

You can inspect the metadata model of the services to see the available parameters and their descriptions. The metadata 
model is a Pydantic model with all its functionality so you can also extract a JSON schema.

Each parameter carries only what the provider itself knows -- the canonical `name`, the provider's own `name_original`
and the `unit` it publishes in. The unit type is not repeated here because it follows from the canonical name; look it
up in the glossary below, or in `wetterdienst.metadata.parameter_table`.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationMetadata

metadata = DwdObservationMetadata.model_dump_json(indent=2)
print(metadata)
```

## Reading the provider tables

The parameter tables of the provider pages have five columns:

| Column | What it is |
| --- | --- |
| name | the canonical name, linked to the glossary below |
| original name | the provider's own name of the field, accepted wherever the canonical name is |
| description | what the field is, in the provider's words where it has them |
| unit | the unit the provider publishes the value in; `-` is dimensionless. The values come back in the unit of the quantity's target (see [Units](../usage/units.md)) unless conversion is switched off |
| constraints | the range the quantity has by its definition, see below |

**`constraints` is information for the reader, not a rule the library applies.** It is prose: nothing in the model
holds it, so a value outside it is not removed, flagged or refused, and a test can only hold the cells to one
grammar: `-` where none is stated, bounds as `>=lo` and `<=hi` joined by a comma (`>=0,<=100` for a percentage), and a
set of admissible codes as `∈ {0, 1, 2}`.

Read `>=0` as "by definition non-negative", not as "every value of this provider is". A reading can lie outside the
definition where the instrument or the water does it: the discharge of a tidal river runs backwards, and a snow gauge
reads a few centimetres below its zero (MeteoSwiss' gauge at station PLF reads -1 to -5 cm in 11 % of its hours).

What the library does enforce is another thing and is not this column. A source writes a missing value as a number
outside every range (`-999`); the provider's reader maps it to null and keeps the text the source wrote in the
`quality_flags` of the reading (`raw:-999`). Where a source also has values no instrument can produce (4021 degrees
for a daily maximum), its reader nulls those too, with a range per provider and resolution that is generous, since it
is there to catch a sentinel and not a record. Both are told in [Quality flags](quality-flags.md).

## The statistic in a name

A quantity that has a value at a moment (temperature, humidity, pressure, wind, cloud cover, irradiance, soil
moisture ...) says in its name which statistic the number is, and the rule is the same for all of them:

| name | what the number is | example |
| --- | --- | --- |
| no word | a reading at one moment, or a source that states no statistic | `temperature_air_2m`, `wind_speed` |
| `_mean` | the mean of the row's own interval (the hour of an hourly row, the day of a daily one), as the source states it, in its own words or in its own field name (`*_mittel`, `średni*`, `*media`, `avg`) | `temperature_air_mean_2m`, `wind_speed_mean` |
| `_mean_last_10min` | the mean of a window shorter than the interval, stated by the source | `wind_speed_mean_last_10min` |
| `_max`, `_min` | the largest or smallest value of the interval | `temperature_air_max_2m`, `wind_gust_max` |
| a statistic after the whole name | a statistic of the daily statistics | `temperature_air_max_2m_mean` |
| `_sum` | the sum of the daily values of the period, of a quantity that is a reading at one moment: a sum with a unit of its own (cm times days), no total by nature | `snow_depth_sum` |
| `_net` | the balance of a downward and an upward flux, positive downward into the surface: no incoming radiation | `radiation_short_wave_net_last_3h`, `radiation_long_wave_net_last_3h` |
| a part of the day after the extreme | the extreme within 30 minutes or within the night, where the plain `_max` or `_min` is that of the whole interval | `precipitation_amount_max_30min`, `temperature_air_min_0_05m_night` |

The statistic comes straight after the quantity and before the height, depth or ground cover
(`temperature_soil_mean_loamy_sand_0_05m`), and before a window (`temperature_air_mean_2m_last_24h`). A total over
the interval (`precipitation_amount`, `sunshine_duration`, `radiation_global`) carries no word: it is a total by
nature. A source that says nothing about the statistic keeps the plain name, so a plain name never claims a mean
the source does not state. `tests/metadata/test_mean_names.py` holds the rule to the source's own description and
field name. The rule was applied to temperature first (GH-2651, GH-2657) and to the other quantities with GH-3151;
the renames of that change are listed below.

A name that was renamed is refused with the new name in the message (`'wind_speed' was renamed to
'wind_speed_mean' in this dataset`), and the plain name stays where the source states no mean. The old names of a
request, of the `parameter` column, of the wide column names and of `Options(geo_station_distance=...)` are the
ones to change: a distance given for `wind_speed` applies to the rows that are still plain `wind_speed` and not to
`wind_speed_mean`.

### Renamed for the rule

#### Wind

| old name | new name | rows |
| --- | --- | --- |
| `wind_direction` | `wind_direction_mean` | 14 |
| `wind_direction` | `wind_direction_mean_last_10min` | 1 |
| `wind_direction_last_10min` | `wind_direction_mean_last_10min` | 8 |
| `wind_direction_last_2min` | `wind_direction_mean_last_2min` | 2 |
| `wind_speed` | `wind_speed_mean` | 32 |
| `wind_speed` | `wind_speed_mean_last_10min` | 1 |
| `wind_speed_last_10min` | `wind_speed_mean_last_10min` | 8 |
| `wind_speed_last_2min` | `wind_speed_mean_last_2min` | 1 |

The rows, by network, resolution and dataset (`field` is the source's own name):

| network | resolution/dataset | field | old name | new name |
| --- | --- | --- | --- | --- |
| aemet/observation | daily/data | `velmedia` | `wind_speed` | `wind_speed_mean` |
| aemet/observation | hourly/data | `dv` | `wind_direction_last_10min` | `wind_direction_mean_last_10min` |
| aemet/observation | hourly/data | `vv` | `wind_speed_last_10min` | `wind_speed_mean_last_10min` |
| chmi/observation | daily/data | `F` | `wind_speed` | `wind_speed_mean` |
| dmi/observation | annual/data | `mean_wind_dir` | `wind_direction` | `wind_direction_mean` |
| dmi/observation | annual/data | `mean_wind_speed` | `wind_speed` | `wind_speed_mean` |
| dmi/observation | daily/data | `mean_wind_dir` | `wind_direction` | `wind_direction_mean` |
| dmi/observation | daily/data | `mean_wind_speed` | `wind_speed` | `wind_speed_mean` |
| dmi/observation | hourly/data | `mean_wind_dir` | `wind_direction` | `wind_direction_mean` |
| dmi/observation | hourly/data | `mean_wind_speed` | `wind_speed` | `wind_speed_mean` |
| dmi/observation | monthly/data | `mean_wind_dir` | `wind_direction` | `wind_direction_mean` |
| dmi/observation | monthly/data | `mean_wind_speed` | `wind_speed` | `wind_speed_mean` |
| dwd/observation | 10_minutes/urban_wind | `dd_st_10` | `wind_direction` | `wind_direction_mean` |
| dwd/observation | 10_minutes/urban_wind | `ff_st_10` | `wind_speed` | `wind_speed_mean` |
| dwd/observation | 10_minutes/wind | `dd_10` | `wind_direction` | `wind_direction_mean` |
| dwd/observation | 10_minutes/wind | `ff_10` | `wind_speed` | `wind_speed_mean` |
| dwd/observation | daily/climate_summary | `fm` | `wind_speed` | `wind_speed_mean` |
| dwd/observation | hourly/urban_wind | `windrichtung` | `wind_direction` | `wind_direction_mean` |
| dwd/observation | hourly/urban_wind | `windgeschwindigkeit` | `wind_speed` | `wind_speed_mean` |
| dwd/observation | hourly/wind | `d` | `wind_direction` | `wind_direction_mean` |
| dwd/observation | hourly/wind | `f` | `wind_speed` | `wind_speed_mean` |
| dwd/observation | hourly/wind_synoptic | `ff` | `wind_speed_last_10min` | `wind_speed_mean_last_10min` |
| dwd/poi | hourly/data | `mean_wind_direction_during_last_10 min_at_10_meters_above_ground` | `wind_direction_last_10min` | `wind_direction_mean_last_10min` |
| dwd/poi | hourly/data | `mean_wind_speed_during last_10_min_at_10_meters_above_ground` | `wind_speed_last_10min` | `wind_speed_mean_last_10min` |
| eccc/observation | hourly/data | `wind_direction` | `wind_direction_last_2min` | `wind_direction_mean_last_2min` |
| fmi/observation | hourly/data | `wd_10min` | `wind_direction_last_10min` | `wind_direction_mean_last_10min` |
| fmi/observation | hourly/data | `ws_10min` | `wind_speed_last_10min` | `wind_speed_mean_last_10min` |
| geosphere/observation | daily/data | `vv_mittel` | `wind_speed` | `wind_speed_mean` |
| geosphere/observation | monthly/data | `vv_mittel` | `wind_speed` | `wind_speed_mean` |
| imgw/meteorology | daily/climate | `średnia dobowa prędkość wiatru` | `wind_speed` | `wind_speed_mean` |
| imgw/meteorology | daily/synop | `średnia dobowa prędkość wiatru` | `wind_speed` | `wind_speed_mean` |
| imgw/meteorology | monthly/climate | `średnia miesięczna prędkość wiatru` | `wind_speed` | `wind_speed_mean` |
| imgw/meteorology | monthly/synop | `średnia miesięczna prędkość wiatru` | `wind_speed` | `wind_speed_mean` |
| knmi/observation | 10_minutes/data | `dd` | `wind_direction` | `wind_direction_mean` |
| knmi/observation | 10_minutes/data | `ff` | `wind_speed` | `wind_speed_mean` |
| knmi/observation | daily/data | `FG` | `wind_speed` | `wind_speed_mean` |
| knmi/observation | hourly/data | `DD` | `wind_direction_last_10min` | `wind_direction_mean_last_10min` |
| knmi/observation | hourly/data | `FH` | `wind_speed` | `wind_speed_mean` |
| meteofrance/observation | daily/core | `FFM` | `wind_speed` | `wind_speed_mean` |
| meteofrance/observation | hourly/core | `DD` | `wind_direction_last_10min` | `wind_direction_mean_last_10min` |
| meteofrance/observation | hourly/core | `FF` | `wind_speed_last_10min` | `wind_speed_mean_last_10min` |
| meteofrance/observation | monthly/data | `FFM` | `wind_speed` | `wind_speed_mean` |
| meteofrance/synop | subdaily/data | `dd` | `wind_direction_last_10min` | `wind_direction_mean_last_10min` |
| meteofrance/synop | subdaily/data | `ff` | `wind_speed_last_10min` | `wind_speed_mean_last_10min` |
| meteoswiss/observation | 10_minutes/data | `dkl010z0` | `wind_direction` | `wind_direction_mean` |
| meteoswiss/observation | 10_minutes/data | `fkl010z0` | `wind_speed` | `wind_speed_mean` |
| meteoswiss/observation | annual/data | `fkl010y0` | `wind_speed` | `wind_speed_mean` |
| meteoswiss/observation | daily/data | `dkl010d0` | `wind_direction` | `wind_direction_mean` |
| meteoswiss/observation | daily/data | `fkl010d0` | `wind_speed` | `wind_speed_mean` |
| meteoswiss/observation | hourly/data | `dkl010h0` | `wind_direction` | `wind_direction_mean` |
| meteoswiss/observation | hourly/data | `fkl010h0` | `wind_speed` | `wind_speed_mean` |
| meteoswiss/observation | monthly/data | `fkl010m0` | `wind_speed` | `wind_speed_mean` |
| metno/frost | daily/data | `mean(wind_speed P1D)` | `wind_speed` | `wind_speed_mean` |
| metno/frost | hourly/data | `wind_from_direction` | `wind_direction_last_10min` | `wind_direction_mean_last_10min` |
| metno/frost | hourly/data | `wind_speed` | `wind_speed_last_10min` | `wind_speed_mean_last_10min` |
| metno/frost | monthly/data | `mean(wind_speed P1M)` | `wind_speed` | `wind_speed_mean` |
| metoffice/observation | hourly/weather | `wind_direction` | `wind_direction` | `wind_direction_mean_last_10min` |
| metoffice/observation | hourly/weather | `wind_speed` | `wind_speed` | `wind_speed_mean_last_10min` |
| metoffice/observation | hourly/wind | `mean_wind_dir` | `wind_direction` | `wind_direction_mean` |
| metoffice/observation | hourly/wind | `mean_wind_speed` | `wind_speed` | `wind_speed_mean` |
| noaa/ghcn | daily/data | `awnd` | `wind_speed` | `wind_speed_mean` |
| nws/observation | hourly/data | `winddirection` | `wind_direction_last_2min` | `wind_direction_mean_last_2min` |
| nws/observation | hourly/data | `windspeed` | `wind_speed_last_2min` | `wind_speed_mean_last_2min` |
| smhi/observation | 1_minute/data | `48` | `wind_direction` | `wind_direction_mean` |
| smhi/observation | 1_minute/data | `47` | `wind_speed` | `wind_speed_mean` |
| smhi/observation | hourly/data | `3` | `wind_direction_last_10min` | `wind_direction_mean_last_10min` |
| smhi/observation | hourly/data | `4` | `wind_speed_last_10min` | `wind_speed_mean_last_10min` |


#### Humidity, pressure, cloud cover and visibility

| old name | new name | rows |
| --- | --- | --- |
| `cloud_cover_total` | `cloud_cover_total_mean` | 12 |
| `cloud_cover_total_midnight_to_midnight` | `cloud_cover_total_mean_midnight_to_midnight` | 1 |
| `cloud_cover_total_midnight_to_midnight_manual` | `cloud_cover_total_mean_midnight_to_midnight_manual` | 1 |
| `cloud_cover_total_sunrise_to_sunset` | `cloud_cover_total_mean_sunrise_to_sunset` | 1 |
| `cloud_cover_total_sunrise_to_sunset_manual` | `cloud_cover_total_mean_sunrise_to_sunset_manual` | 1 |
| `humidity_relative` | `humidity_relative_mean` | 26 |
| `pressure_air_sea_level` | `pressure_air_sea_level_mean` | 14 |
| `pressure_air_site` | `pressure_air_site_mean` | 11 |
| `pressure_vapor` | `pressure_vapor_mean` | 11 |
| `visibility` | `visibility_mean` | 2 |

The rows, by network, resolution and dataset (`field` is the source's own name):

| network | resolution/dataset | field | old name | new name |
| --- | --- | --- | --- | --- |
| aemet/observation | daily/data | `hrmedia` | `humidity_relative` | `humidity_relative_mean` |
| aemet/observation | monthly/data | `hr` | `humidity_relative` | `humidity_relative_mean` |
| chmi/observation | daily/data | `H` | `humidity_relative` | `humidity_relative_mean` |
| chmi/observation | daily/data | `P` | `pressure_air_site` | `pressure_air_site_mean` |
| dmi/observation | annual/data | `mean_relative_hum` | `humidity_relative` | `humidity_relative_mean` |
| dmi/observation | annual/data | `mean_pressure` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| dmi/observation | daily/data | `mean_relative_hum` | `humidity_relative` | `humidity_relative_mean` |
| dmi/observation | daily/data | `mean_pressure` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| dmi/observation | hourly/data | `mean_relative_hum` | `humidity_relative` | `humidity_relative_mean` |
| dmi/observation | hourly/data | `mean_pressure` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| dmi/observation | monthly/data | `mean_relative_hum` | `humidity_relative` | `humidity_relative_mean` |
| dmi/observation | monthly/data | `mean_pressure` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| dwd/observation | annual/climate_summary | `ja_n` | `cloud_cover_total` | `cloud_cover_total_mean` |
| dwd/observation | daily/climate_summary | `nm` | `cloud_cover_total` | `cloud_cover_total_mean` |
| dwd/observation | daily/climate_summary | `upm` | `humidity_relative` | `humidity_relative_mean` |
| dwd/observation | daily/climate_summary | `pm` | `pressure_air_site` | `pressure_air_site_mean` |
| dwd/observation | daily/climate_summary | `vpm` | `pressure_vapor` | `pressure_vapor_mean` |
| dwd/observation | monthly/climate_summary | `mo_n` | `cloud_cover_total` | `cloud_cover_total_mean` |
| geosphere/observation | daily/data | `bewm_mittel` | `cloud_cover_total` | `cloud_cover_total_mean` |
| geosphere/observation | daily/data | `rf_mittel` | `humidity_relative` | `humidity_relative_mean` |
| geosphere/observation | daily/data | `p_mittel` | `pressure_air_site` | `pressure_air_site_mean` |
| geosphere/observation | daily/data | `dampf_mittel` | `pressure_vapor` | `pressure_vapor_mean` |
| geosphere/observation | monthly/data | `bewm_mittel` | `cloud_cover_total` | `cloud_cover_total_mean` |
| geosphere/observation | monthly/data | `rf_mittel` | `humidity_relative` | `humidity_relative_mean` |
| geosphere/observation | monthly/data | `dampf_mittel` | `pressure_vapor` | `pressure_vapor_mean` |
| imgw/meteorology | daily/climate | `średnie dobowe zachmurzenie ogólne` | `cloud_cover_total` | `cloud_cover_total_mean` |
| imgw/meteorology | daily/climate | `średnia dobowa wilgotność względna` | `humidity_relative` | `humidity_relative_mean` |
| imgw/meteorology | daily/synop | `średnie dobowe zachmurzenie ogólne` | `cloud_cover_total` | `cloud_cover_total_mean` |
| imgw/meteorology | daily/synop | `średnia dobowa wilgotność względna` | `humidity_relative` | `humidity_relative_mean` |
| imgw/meteorology | daily/synop | `średnie dobowe ciśnienie na pozimie morza` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| imgw/meteorology | daily/synop | `średnia dobowe ciśnienie na poziomie stacji` | `pressure_air_site` | `pressure_air_site_mean` |
| imgw/meteorology | daily/synop | `średnia dobowe ciśnienie pary wodnej` | `pressure_vapor` | `pressure_vapor_mean` |
| imgw/meteorology | monthly/climate | `średnie miesięczne zachmurzenie ogólne` | `cloud_cover_total` | `cloud_cover_total_mean` |
| imgw/meteorology | monthly/climate | `średnia miesięczna wilgotność względna` | `humidity_relative` | `humidity_relative_mean` |
| imgw/meteorology | monthly/synop | `średnie miesięczne zachmurzenie ogólne` | `cloud_cover_total` | `cloud_cover_total_mean` |
| imgw/meteorology | monthly/synop | `średnia miesięczna wilgotność względna` | `humidity_relative` | `humidity_relative_mean` |
| imgw/meteorology | monthly/synop | `średnie miesięczne ciśnienie na pozimie morza` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| imgw/meteorology | monthly/synop | `średnie miesięczne ciśnienie na poziomie stacji` | `pressure_air_site` | `pressure_air_site_mean` |
| imgw/meteorology | monthly/synop | `średnie miesięczne ciśnienie pary wodnej` | `pressure_vapor` | `pressure_vapor_mean` |
| knmi/observation | 10_minutes/data | `vv` | `visibility` | `visibility_mean` |
| knmi/observation | daily/data | `NG` | `cloud_cover_total` | `cloud_cover_total_mean` |
| knmi/observation | daily/data | `UG` | `humidity_relative` | `humidity_relative_mean` |
| meteofrance/observation | daily/others | `UM` | `humidity_relative` | `humidity_relative_mean` |
| meteofrance/observation | daily/others | `PMERM` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| meteofrance/observation | daily/others | `TSVM` | `pressure_vapor` | `pressure_vapor_mean` |
| meteofrance/observation | monthly/data | `UMM` | `humidity_relative` | `humidity_relative_mean` |
| meteofrance/observation | monthly/data | `PMERM` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| meteofrance/observation | monthly/data | `TSVM` | `pressure_vapor` | `pressure_vapor_mean` |
| meteoswiss/observation | annual/data | `ure200y0` | `humidity_relative` | `humidity_relative_mean` |
| meteoswiss/observation | annual/data | `pp0qffy0` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| meteoswiss/observation | annual/data | `prestay0` | `pressure_air_site` | `pressure_air_site_mean` |
| meteoswiss/observation | annual/data | `pva200y0` | `pressure_vapor` | `pressure_vapor_mean` |
| meteoswiss/observation | daily/data | `ure200d0` | `humidity_relative` | `humidity_relative_mean` |
| meteoswiss/observation | daily/data | `pp0qffd0` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| meteoswiss/observation | daily/data | `prestad0` | `pressure_air_site` | `pressure_air_site_mean` |
| meteoswiss/observation | daily/data | `pva200d0` | `pressure_vapor` | `pressure_vapor_mean` |
| meteoswiss/observation | hourly/data | `ure200h0` | `humidity_relative` | `humidity_relative_mean` |
| meteoswiss/observation | hourly/data | `pp0qffh0` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| meteoswiss/observation | hourly/data | `prestah0` | `pressure_air_site` | `pressure_air_site_mean` |
| meteoswiss/observation | hourly/data | `pva200h0` | `pressure_vapor` | `pressure_vapor_mean` |
| meteoswiss/observation | monthly/data | `ure200m0` | `humidity_relative` | `humidity_relative_mean` |
| meteoswiss/observation | monthly/data | `pp0qffm0` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| meteoswiss/observation | monthly/data | `prestam0` | `pressure_air_site` | `pressure_air_site_mean` |
| meteoswiss/observation | monthly/data | `pva200m0` | `pressure_vapor` | `pressure_vapor_mean` |
| metno/frost | annual/data | `mean(cloud_area_fraction P1Y)` | `cloud_cover_total` | `cloud_cover_total_mean` |
| metno/frost | daily/data | `mean(relative_humidity P1D)` | `humidity_relative` | `humidity_relative_mean` |
| metno/frost | daily/data | `mean(air_pressure_at_sea_level P1D)` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| metno/frost | daily/data | `mean(surface_air_pressure P1D)` | `pressure_air_site` | `pressure_air_site_mean` |
| metno/frost | monthly/data | `mean(cloud_area_fraction P1M)` | `cloud_cover_total` | `cloud_cover_total_mean` |
| metno/frost | monthly/data | `mean(relative_humidity P1M)` | `humidity_relative` | `humidity_relative_mean` |
| metno/frost | monthly/data | `mean(air_pressure_at_sea_level P1M)` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` |
| metno/frost | monthly/data | `mean(surface_air_pressure P1M)` | `pressure_air_site` | `pressure_air_site_mean` |
| noaa/ghcn | daily/data | `acmc` | `cloud_cover_total_midnight_to_midnight` | `cloud_cover_total_mean_midnight_to_midnight` |
| noaa/ghcn | daily/data | `acmh` | `cloud_cover_total_midnight_to_midnight_manual` | `cloud_cover_total_mean_midnight_to_midnight_manual` |
| noaa/ghcn | daily/data | `acsc` | `cloud_cover_total_sunrise_to_sunset` | `cloud_cover_total_mean_sunrise_to_sunset` |
| noaa/ghcn | daily/data | `acsh` | `cloud_cover_total_sunrise_to_sunset_manual` | `cloud_cover_total_mean_sunrise_to_sunset_manual` |
| rmi/observation | 10_minutes/data | `humidity_rel_shelter_avg` | `humidity_relative` | `humidity_relative_mean` |
| rmi/observation | daily/data | `humidity_rel_shelter_avg` | `humidity_relative` | `humidity_relative_mean` |
| rmi/observation | hourly/data | `humidity_rel_shelter_avg` | `humidity_relative` | `humidity_relative_mean` |
| smhi/observation | 1_minute/data | `51` | `visibility` | `visibility_mean` |


#### Irradiance, soil moisture, snow depth, precipitation intensity and Beaufort

| old name | new name | rows |
| --- | --- | --- |
| `precipitation_intensity` | `precipitation_intensity_mean` | 1 |
| `radiation_global_intensity` | `radiation_global_intensity_mean` | 11 |
| `radiation_sky_long_wave_intensity` | `radiation_sky_long_wave_intensity_mean` | 5 |
| `radiation_sky_short_wave_diffuse_intensity` | `radiation_sky_short_wave_diffuse_intensity_mean` | 3 |
| `snow_depth` | `snow_depth_mean` | 1 |
| `soil_moisture_corn_loamy_silt_00cm_60cm` | `soil_moisture_mean_corn_loamy_silt_00cm_60cm` | 1 |
| `soil_moisture_corn_sand_00cm_60cm` | `soil_moisture_mean_corn_sand_00cm_60cm` | 1 |
| `soil_moisture_grass_loamy_silt_00cm_10cm` | `soil_moisture_mean_grass_loamy_silt_00cm_10cm` | 1 |
| `soil_moisture_grass_loamy_silt_00cm_60cm` | `soil_moisture_mean_grass_loamy_silt_00cm_60cm` | 1 |
| `soil_moisture_grass_loamy_silt_10cm_20cm` | `soil_moisture_mean_grass_loamy_silt_10cm_20cm` | 1 |
| `soil_moisture_grass_loamy_silt_20cm_30cm` | `soil_moisture_mean_grass_loamy_silt_20cm_30cm` | 1 |
| `soil_moisture_grass_loamy_silt_30cm_40cm` | `soil_moisture_mean_grass_loamy_silt_30cm_40cm` | 1 |
| `soil_moisture_grass_loamy_silt_40cm_50cm` | `soil_moisture_mean_grass_loamy_silt_40cm_50cm` | 1 |
| `soil_moisture_grass_loamy_silt_50cm_60cm` | `soil_moisture_mean_grass_loamy_silt_50cm_60cm` | 1 |
| `soil_moisture_grass_sand_00cm_60cm` | `soil_moisture_mean_grass_sand_00cm_60cm` | 1 |
| `soil_moisture_winter_wheat_loamy_silt_00cm_60cm` | `soil_moisture_mean_winter_wheat_loamy_silt_00cm_60cm` | 1 |
| `soil_moisture_winter_wheat_sand_00cm_60cm` | `soil_moisture_mean_winter_wheat_sand_00cm_60cm` | 1 |
| `wind_force_beaufort` | `wind_force_beaufort_mean` | 2 |

The rows, by network, resolution and dataset (`field` is the source's own name):

| network | resolution/dataset | field | old name | new name |
| --- | --- | --- | --- | --- |
| dwd/derived | monthly/soil | `mittel von bfml_ag` | `soil_moisture_corn_loamy_silt_00cm_60cm` | `soil_moisture_mean_corn_loamy_silt_00cm_60cm` |
| dwd/derived | monthly/soil | `mittel von bfms_ag` | `soil_moisture_corn_sand_00cm_60cm` | `soil_moisture_mean_corn_sand_00cm_60cm` |
| dwd/derived | monthly/soil | `mittel von bfgl01_ag` | `soil_moisture_grass_loamy_silt_00cm_10cm` | `soil_moisture_mean_grass_loamy_silt_00cm_10cm` |
| dwd/derived | monthly/soil | `mittel von bfgl_ag` | `soil_moisture_grass_loamy_silt_00cm_60cm` | `soil_moisture_mean_grass_loamy_silt_00cm_60cm` |
| dwd/derived | monthly/soil | `mittel von bfgl02_ag` | `soil_moisture_grass_loamy_silt_10cm_20cm` | `soil_moisture_mean_grass_loamy_silt_10cm_20cm` |
| dwd/derived | monthly/soil | `mittel von bfgl03_ag` | `soil_moisture_grass_loamy_silt_20cm_30cm` | `soil_moisture_mean_grass_loamy_silt_20cm_30cm` |
| dwd/derived | monthly/soil | `mittel von bfgl04_ag` | `soil_moisture_grass_loamy_silt_30cm_40cm` | `soil_moisture_mean_grass_loamy_silt_30cm_40cm` |
| dwd/derived | monthly/soil | `mittel von bfgl05_ag` | `soil_moisture_grass_loamy_silt_40cm_50cm` | `soil_moisture_mean_grass_loamy_silt_40cm_50cm` |
| dwd/derived | monthly/soil | `mittel von bfgl06_ag` | `soil_moisture_grass_loamy_silt_50cm_60cm` | `soil_moisture_mean_grass_loamy_silt_50cm_60cm` |
| dwd/derived | monthly/soil | `mittel von bfgs_ag` | `soil_moisture_grass_sand_00cm_60cm` | `soil_moisture_mean_grass_sand_00cm_60cm` |
| dwd/derived | monthly/soil | `mittel von bfwl_ag` | `soil_moisture_winter_wheat_loamy_silt_00cm_60cm` | `soil_moisture_mean_winter_wheat_loamy_silt_00cm_60cm` |
| dwd/derived | monthly/soil | `mittel von bfws_ag` | `soil_moisture_winter_wheat_sand_00cm_60cm` | `soil_moisture_mean_winter_wheat_sand_00cm_60cm` |
| dwd/observation | annual/climate_summary | `ja_fk` | `wind_force_beaufort` | `wind_force_beaufort_mean` |
| dwd/observation | monthly/climate_summary | `mo_fk` | `wind_force_beaufort` | `wind_force_beaufort_mean` |
| knmi/observation | 10_minutes/data | `rg` | `precipitation_intensity` | `precipitation_intensity_mean` |
| knmi/observation | 10_minutes/data | `qg` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| meteoswiss/observation | 10_minutes/data | `gre000z0` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| meteoswiss/observation | 10_minutes/data | `oli000z0` | `radiation_sky_long_wave_intensity` | `radiation_sky_long_wave_intensity_mean` |
| meteoswiss/observation | 10_minutes/data | `ods000z0` | `radiation_sky_short_wave_diffuse_intensity` | `radiation_sky_short_wave_diffuse_intensity_mean` |
| meteoswiss/observation | annual/data | `gre000y0` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| meteoswiss/observation | annual/data | `oli000y0` | `radiation_sky_long_wave_intensity` | `radiation_sky_long_wave_intensity_mean` |
| meteoswiss/observation | daily/data | `gre000d0` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| meteoswiss/observation | daily/data | `oli000d0` | `radiation_sky_long_wave_intensity` | `radiation_sky_long_wave_intensity_mean` |
| meteoswiss/observation | daily/data | `ods000d0` | `radiation_sky_short_wave_diffuse_intensity` | `radiation_sky_short_wave_diffuse_intensity_mean` |
| meteoswiss/observation | hourly/data | `gre000h0` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| meteoswiss/observation | hourly/data | `oli000h0` | `radiation_sky_long_wave_intensity` | `radiation_sky_long_wave_intensity_mean` |
| meteoswiss/observation | hourly/data | `ods000h0` | `radiation_sky_short_wave_diffuse_intensity` | `radiation_sky_short_wave_diffuse_intensity_mean` |
| meteoswiss/observation | monthly/data | `gre000m0` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| meteoswiss/observation | monthly/data | `oli000m0` | `radiation_sky_long_wave_intensity` | `radiation_sky_long_wave_intensity_mean` |
| metno/frost | daily/data | `mean(surface_downwelling_shortwave_flux_in_air P1D)` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| metno/frost | hourly/data | `mean(surface_downwelling_shortwave_flux_in_air PT1H)` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| metno/frost | monthly/data | `mean(surface_snow_thickness P1M)` | `snow_depth` | `snow_depth_mean` |
| rmi/observation | 10_minutes/data | `short_wave_from_sky_avg` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| rmi/observation | daily/data | `short_wave_from_sky_avg` | `radiation_global_intensity` | `radiation_global_intensity_mean` |
| rmi/observation | hourly/data | `short_wave_from_sky_avg` | `radiation_global_intensity` | `radiation_global_intensity_mean` |


### Renamed for what the number is

GH-2614 asked of each row whether its name says what the source's number is, and not only its statistic. Four names
did not. A name that is no longer declared by a dataset is refused with the new one named, as above, and a dataset that
keeps the old name for another row (`snow_depth` of the daily DWD rows, `precipitation_amount_max` of the monthly and
annual DMI rows) still answers to it there.

| network | resolution/dataset | field | old name | new name | what the number is |
| --- | --- | --- | --- | --- | --- |
| dwd/dmo | hourly/icon | `rads3` | `radiation_global_last_3h` | `radiation_short_wave_net_last_3h` | DWD: "Short wave radiation balance during the last 3 hours" |
| dwd/dmo | hourly/icon | `radl3` | `radiation_sky_long_wave_last_3h` | `radiation_long_wave_net_last_3h` | DWD: "Long wave radiation balance during the last 3 hours" |
| dwd/observation | monthly/precipitation_more | `mo_sh_s` | `snow_depth` | `snow_depth_sum` | the monthly sum of the daily snow depths, in cm times days |
| dwd/observation | annual/precipitation_more | `ja_sh_s` | `snow_depth` | `snow_depth_sum` | the annual sum of the daily snow depths |
| geosphere/observation | daily/data | `tsmin` | `temperature_air_min_0_05m` | `temperature_air_min_0_05m_night` | Geosphere: "Lufttemperatur 5cm Nachtminimum (18 UTC Vortag bis 6 UTC)" |
| dmi/observation | daily/data | `max_precip_30m` | `precipitation_amount_max` | `precipitation_amount_max_30min` | the largest 30 minutes of the day, counted from 23:31 local time of the previous day |

The two DMO names are net balances, positive downward into the surface. Read off the 3-hourly ICON run of
2026-10-20 00 UTC (5,894 stations): `RadS3` is 0.87 of the global radiation `Rad3h` at the median where that is above
50 J/cm² (never more than 0.95), which is the share the surface absorbs, and 99.7 % of the 182,714 values of `RadL3` are
negative, down to -3,573 kJ/m², because the surface emits more long-wave radiation than the sky returns. The unit of
each stays as it was declared, `rads3` in J/cm² and `radl3` in kJ/m², which differ inside one file; with the default
unit targets both come back in J/cm². The 10-minute and hourly `tsmin` of Geosphere stay
`temperature_air_min_0_05m`: they are the minimum of their interval.

#### The road stations and IPMA

Three more names say what the number is, and two of them take back a statistic (0.164.0, GH-2614). The road
temperatures lose a height the source never gave, and a plain name stands for a source that states none.

| network | resolution/dataset | field | old name | new name | what the number is |
| --- | --- | --- | --- | --- | --- |
| dwd/road | 15_minutes/data | `airTemperature` | `temperature_air_2m` | `temperature_air` | BUFR 0 12 101, the sensor height 0 07 032 before it reads 4.0, 4.05 or 5.0 m by station group and none in four |
| dwd/road | 15_minutes/data | `dewpointTemperature` | `temperature_dew_point_2m` | `temperature_dew_point` | BUFR 0 12 103, the same sensor height |
| dwd/road | 15_minutes/data | `relativeHumidity` | `humidity_relative_mean` | `humidity_relative` | BUFR 0 13 003 with no time significance or period before it in any station group: a reading |
| ipma/observation | hourly/data | `humidade` | `humidity_relative` | `humidity_relative_mean` | IPMA: "humidade relativa do ar registada a 1.5 metros de altura, média da hora" |
| ipma/observation | hourly/data | `pressao` | `pressure_air_sea_level` | `pressure_air_sea_level_mean` | IPMA: "pressão atmosférica, reduzida ao nível médio do mar (NMM), média da hora" |

No station group of the road messages states 2 m (read 2026-10-21), and `temperature_air_2m` stays the name of the
screen height. The height is in the provider's description of the two fields, not in the name, and the 0.139.0 names
`temperature_air_mean_2m` and `temperature_dew_point_mean_2m` of the road dataset are answered with the new ones. The
road humidity was `humidity_relative_mean` from 0.160.0 (GH-3151, the 27th row of the table above, now 26): its
description said "mean humidity", the BUFR template states none. Every other dataset keeps the old names for its own
rows.

## Glossary

The unit type is a property of the parameter itself and decides which unit values are returned in;
the unit a given provider publishes is listed per provider under [providers](provider/index.md).

```{parameter-glossary}
```