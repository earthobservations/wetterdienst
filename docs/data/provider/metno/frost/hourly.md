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
| {term}`temperature_air_2m` | air_temperature | Air temperature (default 2 m above ground), present value. At a station with several heights the 2 m sensor, and the nearest height where it has no value. | degree_celsius |
| {term}`temperature_dew_point_2m` | dew_point_temperature | Dew-point temperature - the temperature at which the air, when cooled, will become saturated (and dew is formed) | degree_celsius |
| {term}`humidity_relative` | relative_humidity | Relative humidity. At a station with several heights the 2 m sensor, and the nearest height where it has no value. | percent |
| {term}`wind_speed_mean_last_10min` | wind_speed | Mean wind speed is registered as a mean value of the wind speed over the last ten minutes before the observation time. (default: 10 meters above ground, some stations have measurements at 2 meters). At a station with several heights the speed and the direction are of one height: 10 m if it has both, else the nearest height that has both; where no height has both, each is the 10 m one first. | meter_per_second |
| {term}`wind_direction_mean_last_10min` | wind_from_direction | Mean wind direction over the last ten minutes before the observation time. Wind direction is defined as the direction from which the wind blows and is registered in degrees, where 360 degrees is north and 90 degrees is east. Code -3 means no unique wind direction is given when winds are weak (Frost's data clarifications), and is returned as null. A direction of 0 beside a wind speed of 0 (of the same time and height) is a calm and is returned as null; a 0 beside a speed above 0 stays, and so does a 0 read by itself after a 404 of the whole dataset. At a station with several heights the speed and the direction are of one height: 10 m if it has both, else the nearest height that has both; a calm or a -3 there is the answer for the hour: no other height fills it. Where no height has both, each is the 10 m one first, else the nearest. | degree |
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
batch that Frost answers with a 404, when each parameter is asked for by itself and a `0` stays `0.0`.

**At a station with several heights** (71 stations have had a wind speed at more than one, 10 m and 2 m among them; the
temperature and the humidity have 2 m and another) a time is served from one height
([#3844](https://github.com/earthobservations/wetterdienst/issues/3844)): `temperature_air_2m` and `humidity_relative`
from 2 m, where that height has a value, and otherwise from the other height that has one (the nearest to the standard).
The height does not depend on the order of Frost's answer, which lists the highest first. The wind speed and the bearing
(`wind_speed_mean_last_10min`, `wind_direction_mean_last_10min`) are a pair of one height: the 10 m one if it has both a
speed and a bearing, else the nearest height that has both, speed and bearing of it (SN44300 since June 2026 has a 10 m speed
with no 10 m bearing, so its hours are the 2 m pair), else, where no height has both, each of them the 10 m one first. That
last case is the only one in which a bearing stands beside a speed of another height (SN92120 and SN92130 in 1992-02 to
1993-12, speed at 2 m and bearing at 10 m; SN49490 for 4 days in 2013), and no bearing is lost. The speed of a request for
the speed alone is the speed of the pair. A calm or a `-3` at the pair's height is the hour (the `calm-wind-direction` warning counts the calms), and no other
height fills it. The
Frost page ([Sensors at several heights](index.md#sensors-at-several-heights)) has the counts and the standard heights of the
other resolutions. Before, the core kept the first row of Frost's answer that had a value: the 10 m reading of the
wind, but the 10 m reading of the temperature too, though 2 m had one, and a gap at 10 m was filled from 2 m.
