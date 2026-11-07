# hourly

## metadata

| property      | value  |
|---------------|--------|
| name          | hourly |
| original name | PT1H   |

## datasets

### data

#### parameters

| name                                  | original name                                        | description                                                                                                                                                                                                                                                                                                            | unit |
|---------------------------------------|------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_2m` | air_temperature | Air temperature (default 2 m above ground), present value | degree_celsius |
| {term}`temperature_dew_point_2m` | dew_point_temperature | Dew-point temperature - the temperature at which the air, when cooled, will become saturated (and dew is formed) | degree_celsius |
| {term}`humidity_relative` | relative_humidity | Relative humidity | percent |
| {term}`wind_speed_mean_last_10min` | wind_speed | Mean wind speed is registered as a mean value of the wind speed over the last ten minutes before the observation time. (default: 10 meters above ground, some stations have measurements at 2 meters) | meter_per_second |
| {term}`wind_direction_mean_last_10min` | wind_from_direction | Mean wind direction over the last ten minutes before the observation time. Wind direction is defined as the direction from which the wind blows and is registered in degrees, where 360 degrees is north and 90 degrees is east. Code -3 means no unique wind direction is given when winds are weak (Frost's data clarifications), and is returned as null. A direction of 0 beside a wind speed of 0 (of the same time and height) is a calm and is returned as null; a 0 beside a speed above 0 stays, and so does a 0 read by itself after a 404 of the whole dataset. At a station with the wind at two heights (10 m and 2 m) a calm or a -3 of the first height is the answer for the hour, and the other height does not fill it. | degree |
| {term}`pressure_air_sea_level` | air_pressure_at_sea_level | Air pressure reduced to mean sea level. The parameter is usually called QFF in aviation and shows the measured air pressure reduced to mean sea level by applying actual atmospheric conditions. | hectopascal |
| {term}`pressure_air_site` | surface_air_pressure | Air pressure at the station. The parameter is usually called QFE in aviation and shows the measured air pressure reduced to the reference height of the station. | hectopascal |
| {term}`cloud_cover_total` | cloud_area_fraction | Total cloud cover is registered using a code 0 - 8 describing how many eights of the sky are covered by clouds (0 = no clouds, 8 = completely overcast). Code -3 or 9 means the cloud cover cannot be estimated because the sky is obstructed from view by fog, drifting snow and the like; both are returned as null. | one_eighth |
| {term}`radiation_global_intensity_mean` | mean(surface_downwelling_shortwave_flux_in_air PT1H) | Hourly mean global radiation. Global radiation is the total downwelling shortwave radiation from the sun. Shortwave radiation have wavelengths in the area 295-2800 nm and therefore includes ultraviolet, visible and infrared light. The instrument measures the radiation flux through a horizontal surface (W/m2). | watt_per_square_meter |
| {term}`precipitation_amount` | sum(precipitation_amount PT1H) | Amount of precipitation per hour. Code -1 is read as no precipitation (our reading: Frost's table lists it for the sum over an undefined period only): returned as 0 from 1982 on, and as null before. | millimeter |
| {term}`snow_depth` | surface_snow_thickness | The depth of the snow is measured in cm from the ground to the top of the snow cover. Code -1 means no snow (Frost's data clarifications: "Zero snowdepth or partial snow cover") and is returned as a depth of 0; code 0 means a depth of less than 0.5 cm and is returned as 0; code -3 means it was not possible to measure the depth, and is returned as null. | centimeter |

## Notes

`-1` of the precipitation sum is read as no precipitation, `0.0`, from 1982 on and is `null` before. That is our reading:
Frost's table lists the code for `sum_over_undefined_period(precipitation_amount PT1H)` and not for this element. See the
section [The code -1 of the precipitation sums](index.md) of the Frost page for the evidence.

The `-3` of `wind_direction_mean_last_10min` ("No unique wind direction is given when winds are weak") and of `snow_depth`
("Not possible to measure snowdepth") is `null` with `raw:-3`; the `-1` of `snow_depth` ("Zero snowdepth or partial snow
cover") is `0.0` with `raw:-1`, and a `0` ("Snowdepth less than 0.5 cm") stays `0.0`. See the section
[The other coded values](index.md) of the Frost page for the evidence.

A `0` of `wind_direction_mean_last_10min` is a calm where the wind speed of the same time and height is 0: it is `null`
with `raw:0`, as for every provider that writes a calm ([Special values](../../../special_values.md#wind)). Frost writes
north as 360. A `0` beside a speed above 0 stays `0.0`. The speed is read from the answer, which holds the whole dataset
whatever parameters were asked for, so it is there for a request of the direction alone; the one case without it is a
batch that Frost answers with a 404, when each parameter is asked for by itself and a `0` stays `0.0`. At a station with
the wind at two heights (71 have had a speed at more than one, 10 m and 2 m among them) a direction is held against the speed
of its own height; with no speed at that height it stays.

**At a station with two heights** Frost answers a direction for each, the 10 m one first, and the answer keeps one value
for an hour: the first height that has one. A calm of the first height is that value, `null` with `raw:0`, and the
bearing of the other height does not fill it (the `calm-wind-direction` warning counts it); the same holds for a `-3` of
the first height. A gap of the first height, a null with no code, is still filled from the other height, as every
direction and every other parameter of such a station always was. Where the first height has a bearing it is the
answer, whatever the other height says, a calm included. "First" is the first row of the answer for the hour, not the
height: the reader does not sort. Frost answered the 10 m row before the 2 m row in every one of the 2,195 two-height
hours of the 7 stations that have both (SN99460, SN76530, SN44300, SN26990, SN58070, SN99990 and SN38140) between
2026-01-10 and 2026-01-24, which is what has been seen, and a change of that order would change which height decides.
In those 15 days 79 hours had a calm at the first height (SN99460 71, SN99990 4, SN44300 2 and SN26990 2); 34 of them
would have been filled from the other height, 22 with a bearing above 0 and 12 with a 0 that stands beside a wind
(SN99460 30). One of the 79, SN99460 2026-01-10 23:00, has a 10 m `0` with no `qualityCode`, which is read as the calm it
stands for (the speed beside it is 0).
