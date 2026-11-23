# daily

## metadata

| property      | value   |
|---------------|---------|
| name          | daily   |
| original name | diarios |

## datasets

### data

#### parameters

| name                            | original name | description                                        | unit |
|---------------------------------|---------------|----------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | tmed | Daily mean temperature. | degree_celsius |
| {term}`temperature_air_max_2m` | tmax | Maximum temperature of the day. | degree_celsius |
| {term}`temperature_air_min_2m` | tmin | Minimum temperature of the day. | degree_celsius |
| {term}`precipitation_amount` | prec | Daily precipitation, from 07 to 07, in mm. The source's units text adds "Ip = less than 0.1 mm", returned as 0.0, and "Acum = accumulated precipitation", an amount over several days and not that day's, which is null. | millimeter |
| {term}`wind_direction_gust_max` | dir | Direction of the maximum gust, in tens of degrees (returned in degrees). The source's units text reads "99 = variable direction" and "88 = no data": both are no bearing and are null. | degree |
| {term}`wind_speed_mean` | velmedia | Mean wind speed. | meter_per_second |
| {term}`wind_gust_max` | racha | Maximum wind gust. | meter_per_second |
| {term}`pressure_air_site_max` | presmax | Maximum pressure at the station's reference level. | hectopascal |
| {term}`pressure_air_site_min` | presmin | Minimum pressure at the station's reference level. | hectopascal |
| {term}`humidity_relative_mean` | hrmedia | Daily mean relative humidity. | percent |
| {term}`humidity_relative_max` | hrmax | Daily maximum relative humidity. | percent |
| {term}`humidity_relative_min` | hrmin | Daily minimum relative humidity. | percent |
