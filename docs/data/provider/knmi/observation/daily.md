# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | daily |

## datasets

### data

#### parameters

| name                                          | original name | description                            | unit  |
|-----------------------------------------------|---------------|----------------------------------------|-------|
| {term}`temperature_air_mean_2m`               | TG            | Mean temperature                       | °C    |
| {term}`temperature_air_min_2m`                | TN            | Minimum temperature                    | °C    |
| {term}`temperature_air_max_2m`                | TX            | Maximum temperature                    | °C    |
| {term}`humidity_relative_mean`                | UG            | Mean relative atmospheric humidity     | %     |
| {term}`wind_speed_mean`                       | FG            | Mean wind speed                        | m/s   |
| {term}`wind_gust_max`                         | FXX           | Maximum wind gust                      | m/s   |
| {term}`precipitation_amount`                  | RH            | Precipitation amount. The source writes -1 for less than 0.05 mm ("-1 for <0.05 mm"), which is returned as 0.0. | mm    |
| {term}`precipitation_duration`                | DR            | Precipitation duration                 | h     |
| {term}`pressure_air_sea_level_mean`           | PG            | Daily mean sea level pressure, calculated as a mean of the 24 pressure values of that day (midnight to midnight UTC). | hPa   |
| {term}`sunshine_duration`                     | SQ            | Sunshine duration, calculated from global radiation. The source writes -1 for less than 0.05 hour ("-1 for <0.05 hour"), which is returned as 0.0. | h     |
| {term}`radiation_global`                      | Q             | Global solar radiation                 | J/cm² |
| {term}`cloud_cover_total_mean`                | NG            | Mean cloud cover, in octants. The source's 9 is "9=sky invisible" ("9=bovenlucht onzichtbaar"), no cover, and is null. | 1/8   |
| {term}`evapotranspiration_potential_last_24h` | EV24          | Potential evapotranspiration (Makkink) | mm    |
