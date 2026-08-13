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

| name                                  | original name | description                               | unit |
|---------------------------------------|---------------|-------------------------------------------|------|
| {term}`temperature_air_mean_2m`       | ta            | Air Temperature 1 Min Mean                | °C   |
| {term}`temperature_air_mean_0_1m`     | tg            | Air Temperature 10 cm Mean                | °C   |
| {term}`temperature_dew_point_mean_2m` | td            | Dew Point Temperature 1 Min Mean          | °C   |
| {term}`temperature_wet_mean_2m`       | tb            | Wet Bulb Temperature Mean                 | °C   |
| {term}`humidity`                      | rh            | Relative Humidity 1 Min Mean              | %    |
| {term}`wind_speed`                    | ff            | Wind Speed at 10 m Mean with MD           | m/s  |
| {term}`wind_direction`                | dd            | Wind Direction Mean with MD               | °    |
| {term}`wind_gust_max`                 | fx            | Wind Gust at 10 m Maximum last Interval   | m/s  |
| {term}`pressure_air_site`             | p0            | Air Pressure at Station Level 1 Min Mean  | hPa  |
| {term}`pressure_air_sea_level`        | pp            | Air Pressure at Mean Sea Level 1 Min Mean | hPa  |
| {term}`radiation_global_intensity`    | qg            | Global Solar Radiation Mean               | W/m² |
| {term}`sunshine_duration`             | ss            | Sunshine Duration                         | min  |
| {term}`cloud_cover_total`             | n             | Total Cloud Cover                         | 1/8  |
| {term}`visibility_range`              | vv            | Horizontal Visibility Mean                | m    |
| {term}`precipitation_intensity`       | rg            | Precipitation Intensity (Rain Gauge) Mean | mm/h |
| {term}`precipitation_duration`        | dr            | Precipitation Duration (Rain Gauge)       | s    |
