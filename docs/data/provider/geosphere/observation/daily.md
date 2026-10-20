# daily

## metadata

| property      | value                                                   |
|---------------|---------------------------------------------------------|
| name          | daily                                                   |
| original name | klima-v1-1d                                             |
| url           | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-1d) |

## datasets

### data

#### metadata

| property      | value                                                                                |
|---------------|--------------------------------------------------------------------------------------|
| name          | data                                                                                 |
| original name | data                                                                                 |
| description   | Historical daily station observations of 2m air temperature and humidity for Germany |
| access        | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-1d)                              |

#### parameters

| name                              | original name | description                  | unit  | constraints |
|-----------------------------------|---------------|------------------------------|-------|-------------|
| {term}`cloud_cover_total_mean` | bewm_mittel | total cloud cover | % | >=0,<=100 |
| {term}`humidity_relative_mean` | rf_mittel | relative humidity | % | >=0,<=100 |
| {term}`precipitation_amount` | rr | precipitation height | mm | >=0 |
| {term}`pressure_air_site_mean` | p_mittel | air pressure at site | hPa | >=0 |
| {term}`pressure_vapor_mean` | dampf_mittel | vapor pressure | hPa | >=0 |
| {term}`radiation_global` | cglo_j | global radiation | J/cm² | >=0 |
| {term}`snow_depth` | sh | snow depth | cm | >=0 |
| {term}`snow_depth_manual` | sh_manu | manually measured snow depth | cm | >=0 |
| {term}`snow_depth_new` | shneu_manu | new snow depth | cm | >=0 |
| {term}`sunshine_duration` | so_h | sunshine duration | h | >=0 |
| {term}`temperature_air_max_2m` | tlmax | air temperature max at 2m | °C | - |
| {term}`temperature_air_mean_minmax_2m` | tl_mittel | air temperature mean at 2m, calculated from (tlmax + tlmin)/2 | °C | - |
| {term}`temperature_air_min_2m` | tlmin | air temperature min at 2m | °C | - |
| {term}`temperature_air_min_0_05m_night` | tsmin | air temperature min at 0.05m at night (18 UTC of the previous day to 06 UTC) | °C | - |
| {term}`wind_gust_max` | ffx | wind gust max | m/s | - |
| {term}`wind_speed_mean` | vv_mittel | wind speed | m/s | - |
