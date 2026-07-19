# 10_minutes

10-minute in-situ observations. Each value is dated to the end of its 10-minute interval.
A `start_date` off a 10-minute boundary is floored to one so the underlying file resolves;
values outside the requested `[start_date, end_date]` range are then trimmed as usual.

## metadata

| property      | value      |
|---------------|------------|
| name          | 10_minutes |
| original name | 10_minutes |

## datasets

### data

#### parameters

| name                          | original name | unit type               | unit  |
|-------------------------------|---------------|-------------------------|-------|
| temperature_air_mean_2m       | ta            | temperature             | °C    |
| temperature_air_mean_0_1m     | tg            | temperature             | °C    |
| temperature_dew_point_mean_2m | td            | temperature             | °C    |
| temperature_wet_mean_2m       | tb            | temperature             | °C    |
| humidity                      | rh            | fraction                | %     |
| wind_speed                    | ff            | speed                   | m/s   |
| wind_direction                | dd            | angle                   | °     |
| wind_gust_max                 | fx            | speed                   | m/s   |
| pressure_air_site             | p0            | pressure                | hPa   |
| pressure_air_sea_level        | pp            | pressure                | hPa   |
| radiation_global              | qg            | power_per_area          | W/m²  |
| sunshine_duration             | ss            | time                    | min   |
| cloud_cover_total             | n             | fraction                | 1/8   |
| visibility_range              | vv            | length_medium           | m     |
| precipitation_intensity       | rg            | precipitation_intensity | mm/h  |
| precipitation_duration        | dr            | time                    | s     |
