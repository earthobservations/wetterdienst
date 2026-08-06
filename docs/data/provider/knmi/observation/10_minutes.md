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

| name                                  | original name | unit |
|---------------------------------------|---------------|------|
| {term}`temperature_air_mean_2m`       | ta            | °C   |
| {term}`temperature_air_mean_0_1m`     | tg            | °C   |
| {term}`temperature_dew_point_mean_2m` | td            | °C   |
| {term}`temperature_wet_mean_2m`       | tb            | °C   |
| {term}`humidity`                      | rh            | %    |
| {term}`wind_speed`                    | ff            | m/s  |
| {term}`wind_direction`                | dd            | °    |
| {term}`wind_gust_max`                 | fx            | m/s  |
| {term}`pressure_air_site`             | p0            | hPa  |
| {term}`pressure_air_sea_level`        | pp            | hPa  |
| {term}`radiation_global_intensity`    | qg            | W/m² |
| {term}`sunshine_duration`             | ss            | min  |
| {term}`cloud_cover_total`             | n             | 1/8  |
| {term}`visibility_range`              | vv            | m    |
| {term}`precipitation_intensity`       | rg            | mm/h |
| {term}`precipitation_duration`        | dr            | s    |
