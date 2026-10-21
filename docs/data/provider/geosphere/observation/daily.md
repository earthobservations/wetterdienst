# daily

## metadata

| property      | value                                                     |
|---------------|-----------------------------------------------------------|
| name          | daily                                                     |
| original name | klima-v2-1d                                               |
| url           | [here](https://data.hub.geosphere.at/dataset/klima-v2-1d) |

## datasets

### data

#### metadata

| property      | value                                                                       |
|---------------|-----------------------------------------------------------------------------|
| name          | data                                                                        |
| original name | data                                                                        |
| description   | Historical daily station observations for Austria, with quality information |
| access        | [here](https://data.hub.geosphere.at/dataset/klima-v2-1d)                   |

#### parameters

| name                                    | original name | description                                                                                                                                                                                    | unit  | constraints |
|-----------------------------------------|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|-------------|
| {term}`cloud_cover_total_mean`          | bewm_mittel   | Cloud cover, daily mean calculated from the observation times I, II and III (06, 13 and 18 UTC), multiplied by 10 (the source's unit is 1/100, i.e. percent).                                  | %     | >=0,<=100   |
| {term}`humidity_relative_mean`          | rf_mittel     | Relative humidity, daily mean of the observation times I, II and III (06, 13 and 18 UTC).                                                                                                      | %     | >=0,<=100   |
| {term}`precipitation_amount`            | rr            | Precipitation, 24-hour sum of the one-minute values from 06:01 UTC to 06:00 UTC of the following day. The source's -1 (no precipitation) is 0.0; its 0 (less than 1/10 mm, a trace) stays 0.0. | mm    | >=0         |
| {term}`pressure_air_site_mean`          | p_mittel      | Air pressure, daily mean of the observation times I, II and III (06, 13 and 18 UTC).                                                                                                           | hPa   | >=0         |
| {term}`pressure_vapor_mean`             | dampf_mittel  | Vapor pressure, daily mean calculated from the observation times I, II and III (06, 13 and 18 UTC).                                                                                            | hPa   | >=0         |
| {term}`radiation_global`                | cglo_j        | Global radiation, calibrated 24-hour sum of the hourly values 0-24 h MOZ (23 UTC of the day before to 23 UTC of the day).                                                                      | J/cm² | >=0         |
| {term}`snow_depth`                      | sh            | Total snow depth from automatic snow gauge measurement, offset corrected, at observation time I (06 UTC). The source's -1 (no snow) is 0.0.                                                    | cm    | >=0         |
| {term}`snow_depth_manual`               | sh_manu       | Total snow depth, manual measurement at observation time I (06 UTC). The source's -1 (no snow) is 0.0.                                                                                         | cm    | >=0         |
| {term}`snow_depth_new`                  | shneu_manu    | New snow depth, 24-hour sum, manual measurement at observation time I (06 UTC). The source's -1 (no snow) is 0.0.                                                                              | cm    | >=0         |
| {term}`sunshine_duration`               | so_h          | Sunshine duration, sum of the hourly values 0-24 h MOZ (23 UTC of the day before to 23 UTC of the day).                                                                                        | h     | >=0         |
| {term}`temperature_air_max_2m`          | tlmax         | Air temperature at 2 m height, maximum of the ten-minute values (tlmax) from 18:10 UTC of the day before to 18:00 UTC of the day                                                               | °C    | -           |
| {term}`temperature_air_mean_minmax_2m`  | tl_mittel     | air temperature mean at 2m, calculated from (tlmax + tlmin)/2                                                                                                                                  | °C    | -           |
| {term}`temperature_air_min_2m`          | tlmin         | Air temperature at 2 m height, minimum of the ten-minute values (tlmin) from 18:10 UTC of the day before to 18:00 UTC of the day                                                               | °C    | -           |
| {term}`temperature_air_min_0_05m_night` | tsmin         | Air temperature at 5 cm height, minimum in the night from 18:10 UTC of the day before to 06:00 UTC of the day                                                                                  | °C    | -           |
| {term}`wind_gust_max`                   | ffx           | Wind speed (peak gust), daily maximum of the hourly values 0-24 h MOZ (23 UTC of the day before to 23 UTC of the day).                                                                         | m/s   | -           |
| {term}`wind_speed_mean`                 | vv_mittel     | Wind speed, daily mean of the observation times I, II and III (06, 13 and 18 UTC).                                                                                                             | m/s   | -           |
