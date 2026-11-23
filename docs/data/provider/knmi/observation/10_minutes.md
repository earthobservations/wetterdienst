# 10_minutes

10-minute in-situ observations. Each value is dated to the end of its 10-minute interval.
A `start` off a 10-minute boundary is floored to one for the request; values outside the requested
`[start, end]` range are then trimmed as usual.

## metadata

| property      | value      |
|---------------|------------|
| name          | 10_minutes |
| original name | 10_minutes |

## datasets

### data

#### parameters

| name                                    | original name | description                                                                                                                                                         | unit |
|-----------------------------------------|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_2m`              | ta            | Past minute mean air temperature at 1.50 meters, in degrees Celsius                                                                                                 | °C   |
| {term}`temperature_air_mean_0_1m`       | tg            | Past 1 minute mean air temperature at 10 centimeters, in degrees Celsius                                                                                            | °C   |
| {term}`temperature_dew_point_2m`        | td            | Past minute mean dew point temperature at 1.50 meters, in degrees Celsius                                                                                           | °C   |
| {term}`temperature_wet_mean_2m`         | tb            | Past 10 minute mean wet bulb temperature at 1.50 meters, in degrees Celsius                                                                                         | °C   |
| {term}`humidity_relative`               | rh            | Past minute mean relative humidity at 1.50 meters, in percentage                                                                                                    | %    |
| {term}`wind_speed_mean`                 | ff            | Past 10 minute mean wind speed, representative for 10 meters, in meters per second, with Marked Discontinuity (MD)                                                  | m/s  |
| {term}`wind_direction_mean`             | dd            | Past 10 minute mean wind direction in degrees, measured at sensor height, with Marked Discontinuity (MD)                                                            | °    |
| {term}`wind_gust_max`                   | fx            | Past 19 minute maximum wind gust, representative for 10 meters, in meters per second (as KNMI writes it)                                                            | m/s  |
| {term}`pressure_air_site`               | p0            | Past minute mean air pressure at station level                                                                                                                      | hPa  |
| {term}`pressure_air_sea_level`          | pp            | Past minute mean air pressure at mean sea level in hectopascal                                                                                                      | hPa  |
| {term}`radiation_global_intensity_mean` | qg            | Past 10 minute mean global solar radiation in watt per square meter                                                                                                 | W/m² |
| {term}`sunshine_duration`               | ss            | Past 10 minute duration of sunshine in minutes                                                                                                                      | min  |
| {term}`cloud_cover_total`               | n             | Past 30 minute total cloud cover, in okta. The source words no code; the files carry a 9 at fog visibilities (the sky is invisible), which is no cover and is null. | 1/8  |
| {term}`visibility_mean`                 | vv            | Past 10 minute mean horizontal visibility, in meters                                                                                                                | m    |
| {term}`precipitation_intensity_mean`    | rg            | Past 10 minute mean precipitation intensity in millimeters per hour, measured by rain gauge                                                                         | mm/h |
| {term}`precipitation_duration`          | dr            | Past 10 minute duration of precipitation in seconds, measured by rain gauge                                                                                         | s    |
