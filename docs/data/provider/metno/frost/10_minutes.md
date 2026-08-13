# 10 minutes

## metadata

| property      | value   |
|---------------|---------|
| name          | 10_minutes |
| original name | PT10M   |

## datasets

### data

#### parameters

| name                            | original name                          | description                                         | unit |
|---------------------------------|----------------------------------------|-----------------------------------------------------|------|
| {term}`temperature_air_max_2m` | max(air_temperature PT10M) | Highest recorded air temperature per ten minutes | degree_celsius |
| {term}`temperature_air_min_2m` | min(air_temperature PT10M) | Lowest recorded air temperature per ten minutes | degree_celsius |
| {term}`humidity_max` | max(relative_humidity PT10M) | Maximum relative humidity per 10 min | percent |
| {term}`humidity_min` | min(relative_humidity PT10M) | Minimum relative humidity per 10 min | percent |
| {term}`wind_gust_max` | max(wind_speed_of_gust PT10M) | Maximum wind gust for the last ten minutes | meter_per_second |
| {term}`wind_direction_gust_max` | max(wind_from_direction_of_gust PT10M) | Varying wind direction last 10 minutes. Upper limit | degree |
| {term}`precipitation_height` | sum(precipitation_amount PT10M) | Amount of precipitation per 10 minutes | millimeter |
