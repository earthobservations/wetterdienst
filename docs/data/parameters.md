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

The statistic comes straight after the quantity and before the height, depth or ground cover
(`temperature_soil_mean_loamy_sand_0_05m`), and before a window (`temperature_air_mean_2m_last_24h`). A total over
the interval (`precipitation_amount`, `sunshine_duration`, `radiation_global`) carries no word: it is a total by
nature. A source that says nothing about the statistic keeps the plain name, so a plain name never claims a mean
the source does not state. `tests/metadata/test_mean_names.py` holds the rule to the source's own description and
field name. The rule was applied to temperature first (GH-2651, GH-2657) and is being applied to the other
quantities one family at a time (GH-3151); a quantity not listed below is still named as it was.

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


## Glossary

The unit type is a property of the parameter itself and decides which unit values are returned in;
the unit a given provider publishes is listed per provider under [providers](provider/index.md).

```{parameter-glossary}
```