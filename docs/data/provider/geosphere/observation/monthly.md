# monthly

## metadata

| property      | value                                                   |
|---------------|---------------------------------------------------------|
| name          | monthly                                                 |
| original name | klima-v1-1m                                             |
| url           | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-1m) |

## datasets

### data

#### metadata

| property      | value                                                                                  |
|---------------|----------------------------------------------------------------------------------------|
| name          | data                                                                                   |
| original name | data                                                                                   |
| description   | Historical monthly station observations of 2m air temperature and humidity for Germany |
| url           | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-1m)                                |

#### parameters

| name                         | original name  | description                     | unit             | original unit    | constraints                |
|------------------------------|----------------|---------------------------------|------------------|------------------|----------------------------|
| cloud_cover_total            | bewm_mittel    | cloud cover total               | :math:`\%`       | :math:`\%`       | :math:`\geq{0}, \leq{100}` |
| humidity                     | rf_mittel      | relative humidity               | :math:`\%`       | :math:`\%`       | :math:`\geq{0}, \leq{100}` |
| precipitation_height         | rr             | precipitation height            | :math:`kg / m^2` | :math:`mm`       | :math:`\geq{0}`            |
| precipitation_height_max     | rr_max         | precipitation height max        | :math:`kg / m^2` | :math:`mm`       | :math:`\geq{0}`            |
| pressure_air_site            | p              | air pressure at site            | :math:`Pa`       | :math:`hPa`      | :math:`\geq{0}`            |
| pressure_air_site_max        | pmax           | air pressure at site max        | :math:`Pa`       | :math:`hPa`      | :math:`\geq{0}`            |
| pressure_air_site_min        | pmin           | air pressure at site min        | :math:`Pa`       | :math:`hPa`      | :math:`\geq{0}`            |
| pressure_vapor               | dampf_mittel   | vapor pressure                  | :math:`Pa`       | :math:`hPa`      | :math:`\geq{0}`            |
| radiation_global             | cglo_j         | global radiation                | :math:`J / m^2`  | :math:`J / cm^2` | :math:`\geq{0}`            |
| snow_depth_new               | shneu_manu     | snow depth new                  | :math:`m`        | :math:`cm`       | :math:`\geq{0}`            |
| snow_depth_new_max           | shneu_manu_max | snow depth new max              | :math:`m`        | :math:`cm`       | :math:`\geq{0}`            |
| snow_depth_max               | sh_manu_max    | snow depth max                  | :math:`m`        | :math:`cm`       | :math:`\geq{0}`            |
| sunshine_duration            | so_h           | sunshine duration               | :math:`s`        | :math:`h`        | :math:`\geq{0}`            |
| sunshine_duration_relative   | so_r           | sunshine duration relative      | :math:`\%`       | :math:`\%`       | :math:`\geq{0},\leq{100}`  |
| temperature_air_max_2m       | tlmax          | air temperature max at 2m       | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_concrete_max_0m  | bet0_max       | concrete temperature max at 0m  | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_air_mean_2m      | tl_mittel      | air temperature mean at 2m      | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_concrete_mean_0m | bet0           | concrete temperature mean at 0m | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_air_min_2m       | tlmin          | air temperature min at 2m       | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_concrete_min_0m  | bet0_min       | concrete temperature min at 0m  | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_max_0_1m    | tb10_max       | soil temperature max at 0.1m    | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_max_0_2m    | tb20_max       | soil temperature max at 0.2m    | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_max_0_5m    | tb50_max       | soil temperature max at 0.5m    | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_max_1m      | tb100_max      | soil temperature max at 1m      | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_max_2m      | tb200_max      | soil temperature max at 2m      | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_mean_0_1m   | tb10_mittel    | soil temperature mean at 0.1m   | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_mean_0_2m   | tb20_mittel    | soil temperature mean at 0.2m   | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_mean_0_5m   | tb50_mittel    | soil temperature mean at 0.5m   | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_mean_1m     | tb100_mittel   | soil temperature mean at 1m     | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_mean_2m     | tb200_mittel   | soil temperature mean at 2m     | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_min_0_1m    | tb10_min       | soil temperature min at 0.1m    | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_min_0_2m    | tb20_min       | soil temperature min at 0.2m    | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_min_0_5m    | tb50_min       | soil temperature min at 0.5m    | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_min_1m      | tb100_min      | soil temperature min at 1m      | :math:`K`        | :math:`°C`       | :math:`None`               |
| temperature_soil_min_2m      | tb200_min      | soil temperature min at 2m      | :math:`K`        | :math:`°C`       | :math:`None`               |
| wind_speed                   | vv_mittel      | wind speed                      | :math:`m / s`    | :math:`m / s`    | :math:`\geq{0}`            |
