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

| name                                    | original name | description                                                                                                                               | unit             |
|-----------------------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------------|------------------|
| {term}`wind_direction_mean_last_10min` | dd | Direction of the mean wind over 10 minutes, in steps of 10 degrees, north being 360. The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays. | degree |
| {term}`wind_speed_mean_last_10min` | ff | Speed of the mean wind over 10 minutes, in whole m/s (the mean cut to the integer). | meter_per_second |
| {term}`wind_gust_max_last_10min` | raf10 | Gusts over the last 10 minutes, in m/s. | meter_per_second |
| {term}`temperature_air_2m` | t | Temperature. | degree_kelvin |
| {term}`temperature_dew_point_2m` | td | Dew point at 2 m above ground, the temperature at which the air would become saturated. | degree_kelvin |
| {term}`temperature_air_min_2m_last_24h` | tn24 | Minimum air temperature at 2 m above ground over the preceding 24 hours. | degree_kelvin |
| {term}`temperature_air_max_2m_last_24h` | tx24 | Maximum air temperature at 2 m above ground over the preceding 24 hours. | degree_kelvin |
| {term}`humidity_relative` | u | Relative humidity of the air, the fraction of the moisture it could hold at that temperature, where the source states no statistic or a reading at one moment; the stated mean is `humidity_relative_mean`. | percent |
| {term}`visibility` | vv | Horizontal distance at which an object can still be made out, where the source states no statistic or a reading at one moment; the stated mean is `visibility_mean`. | meter |
| {term}`cloud_cover_total` | n | Fraction of the sky covered by cloud of any kind, where the source states no statistic or a reading at one moment; the stated mean is `cloud_cover_total_mean`. | percent |
| {term}`pressure_air_site` | pres | Air pressure as measured at station height, where the source states no statistic or a reading at one moment; the stated mean is `pressure_air_site_mean`. | pascal |
| {term}`pressure_air_sea_level` | pmer | Air pressure reduced to mean sea level, so that stations at different heights compare, where the source states no statistic or a reading at one moment; the stated mean is `pressure_air_sea_level_mean`. | pascal |
| {term}`precipitation_amount_last_1h` | rr1 | Depth of precipitation collected over the preceding hour. | millimeter |
| {term}`precipitation_amount_last_3h` | rr3 | Depth of precipitation collected over the preceding 3 hours. | millimeter |
| {term}`precipitation_amount_last_6h` | rr6 | Depth of precipitation collected over the preceding 6 hours. | millimeter |
| {term}`precipitation_amount_last_12h` | rr12 | Depth of precipitation collected over the preceding 12 hours. | millimeter |
| {term}`precipitation_amount_last_24h` | rr24 | Depth of precipitation collected over the preceding 24 hours. | millimeter |

