# subdaily

## metadata

| property      | value |
|---------------|-------|
| name          | subdaily |
| original name | synop |
| description   | SYNOP reports, made at their native three-hourly interval. |

## datasets

### data

#### metadata

| property      | value |
|---------------|-------|
| name          | data |
| original name | synop |
| grouped       | True |
| periods       | historical |

#### parameters

| name                                    | original name | description                                                                                   | unit             |
|-----------------------------------------|---------------|-----------------------------------------------------------------------------------------------|------------------|
| {term}`wind_direction`                  | dd            | Direction the wind is blowing from, clockwise from true north.                                | degree           |
| {term}`wind_speed`                      | ff            | Mean speed of the wind over the period.                                                       | meter_per_second |
| {term}`wind_gust_max`                   | raf10         | Speed of the strongest gust of the period.                                                    | meter_per_second |
| {term}`temperature_air_mean_2m`         | t             | Mean air temperature at 2 m above ground.                                                     | degree_kelvin    |
| {term}`temperature_dew_point_mean_2m`   | td            | Dew point at 2 m above ground, the temperature at which the air would become saturated.       | degree_kelvin    |
| {term}`temperature_air_min_2m_last_24h` | tn24          | Minimum air temperature at 2 m above ground over the preceding 24 hours.                      | degree_kelvin    |
| {term}`temperature_air_max_2m_last_24h` | tx24          | Maximum air temperature at 2 m above ground over the preceding 24 hours.                      | degree_kelvin    |
| {term}`humidity`                        | u             | Relative humidity of the air, the fraction of the moisture it could hold at that temperature. | percent          |
| {term}`visibility_range`                | vv            | Horizontal distance at which an object can still be made out.                                 | meter            |
| {term}`cloud_cover_total`               | n             | Fraction of the sky covered by cloud of any kind.                                             | percent          |
| {term}`pressure_air_site`               | pres          | Air pressure as measured at station height.                                                   | pascal           |
| {term}`pressure_air_sea_level`          | pmer          | Air pressure reduced to mean sea level, so that stations at different heights compare.        | pascal           |
| {term}`precipitation_height_last_1h`    | rr1           | Depth of precipitation collected over the preceding hour.                                     | millimeter       |
| {term}`precipitation_height_last_3h`    | rr3           | Depth of precipitation collected over the preceding 3 hours.                                  | millimeter       |
| {term}`precipitation_height_last_6h`    | rr6           | Depth of precipitation collected over the preceding 6 hours.                                  | millimeter       |
| {term}`precipitation_height_last_12h`   | rr12          | Depth of precipitation collected over the preceding 12 hours.                                 | millimeter       |
| {term}`precipitation_height_last_24h`   | rr24          | Depth of precipitation collected over the preceding 24 hours.                                 | millimeter       |

