# hourly

## metadata

| property      | value |
|---------------|-------|
| name          | hourly |
| original name | hour |

## datasets

### data

#### parameters

| name                                | original name        | description                                                                                                                        | unit |
|-------------------------------------|----------------------|------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | mean_temp | Mean air temperature of the hour (UTC), measured 2 m over terrain; in Greenland possibly the reading at minute 0. | °C |
| {term}`temperature_air_max_2m` | max_temp_w_date | Highest air temperature of the hour (UTC), measured 2 m over terrain. | °C |
| {term}`temperature_air_min_2m` | min_temp | Lowest air temperature of the hour (UTC), measured 2 m over terrain. | °C |
| {term}`humidity_relative_mean` | mean_relative_hum | Mean relative humidity of the hour (UTC), measured 2 m over terrain: in Denmark the average of the 6 underlying values within the hour. | % |
| {term}`pressure_air_sea_level_mean` | mean_pressure | Mean atmospheric pressure of the hour (UTC), reduced to mean sea level: in Denmark the average of the 6 underlying values within the hour. | hPa |
| {term}`precipitation_amount` | acc_precip | Accumulated precipitation of the hour (UTC), in mm. | mm |
| {term}`wind_speed_mean` | mean_wind_speed | Mean wind speed of the hour (UTC), measured 10 m over terrain: the average of the 6 underlying values within the hour. For Greenland the source says the value is not calculated correctly before 2024. | m/s |
| {term}`wind_speed_rolling_mean_max` | max_wind_speed_10min | Highest of the 6 underlying 10 minute average wind speeds within the hour (UTC), measured 10 m over terrain. | m/s |
| {term}`wind_gust_max` | max_wind_speed_3sec | Highest 3 second average wind speed (gust) of the hour (UTC), measured 10 m over terrain. | m/s |
| {term}`wind_direction_mean` | mean_wind_dir | Direction the wind blows from (north is 360, 0 means calm) over the hour (UTC), measured 10 m over terrain; in Greenland possibly the reading at minute 0. The source's 0 beside a mean wind speed of 0 (a calm wind) is null. | ° |
