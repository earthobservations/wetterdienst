# hourly

## metadata

| property      | value  |
|---------------|--------|
| name          | hourly |
| original name | hourly |

## datasets

### data

#### parameters

| name                              | original name | description                                                      | unit  |
|-----------------------------------|---------------|------------------------------------------------------------------|-------|
| {term}`temperature_air_2m` | T | Temperature | °C |
| {term}`temperature_dew_point_2m` | TD | Dew point temperature | °C |
| {term}`humidity_relative` | U | Relative atmospheric humidity | % |
| {term}`wind_speed_mean` | FH | Mean wind speed | m/s |
| {term}`wind_direction_mean_last_10min` | DD | Past 10 minute mean wind direction, representative for 10 meters. The source's codes "0=windstil" (calm) and "990=veranderlijk" (variable) are no bearing and are null. | ° |
| {term}`wind_gust_max` | FX | Maximum wind gust | m/s |
| {term}`precipitation_amount` | RH | Precipitation amount. The source writes -1 for less than 0.05 mm ("-1 for <0.05 mm"), which is returned as 0.0. | mm |
| {term}`precipitation_duration` | DR | Precipitation duration | h |
| {term}`pressure_air_sea_level` | P | Air pressure reduced to mean sea level, at the time of observation. | hPa |
| {term}`sunshine_duration` | SQ | Sunshine duration, calculated from global radiation. The source writes -1 for less than 0.05 hour ("-1 for <0.05 hour"), which is returned as 0.0. | h |
| {term}`radiation_global` | Q | Global solar radiation | J/cm² |
| {term}`cloud_cover_total` | N | Cloud cover, in octants, at the time of observation. The source's 9 is "9=sky invisible", no cover, and is null. | 1/8 |
