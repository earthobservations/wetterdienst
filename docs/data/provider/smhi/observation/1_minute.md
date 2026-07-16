# 1_minute

Live/rolling data with no fixed historical window — SMHI only exposes a short rolling
window for 1-minute data (via the `latest-day` period), similar to a real-time
observation feed.

## metadata

| property      | value    |
|---------------|----------|
| name          | 1_minute |
| original name | 1_minute |

## datasets

### data

#### parameters

| name                    | original name | unit type     | unit |
|-------------------------|----------------|----------------|------|
| temperature_air_mean_2m | 45             | temperature    | °C   |
| pressure_air_sea_level  | 44             | pressure       | hPa  |
| humidity                | 43             | fraction       | %    |
| snow_depth              | 52             | length         | m    |
| visibility_range        | 51             | length         | m    |
| wind_speed              | 47             | speed          | m/s  |
| wind_direction          | 48             | angle          | °    |
| precipitation_height    | 46             | precipitation  | mm   |
