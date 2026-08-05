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
| {term}`cloud_cover_total`         | bewm_mittel   | total cloud cover            | %     | >=0,<=100   |
| {term}`humidity`                  | rf_mittel     | relative humidity            | %     | >=0,<=100   |
| {term}`precipitation_height`      | rr            | precipitation height         | mm    | >=0         |
| {term}`pressure_air_site`         | p_mittel      | air pressure at site         | hPa   | >=0         |
| {term}`pressure_vapor`            | dampf_mittel  | vapor pressure               | hPa   | >=0         |
| {term}`radiation_global`          | cglo_j        | global radiation             | J/cm² | >=0         |
| {term}`snow_depth`                | sh            | snow depth                   | cm    | >=0         |
| {term}`snow_depth_manual`         | sh_manu       | manually measured snow depth | cm    | >=0         |
| {term}`snow_depth_new`            | shneu_manu    | new snow depth               | cm    | >=0         |
| {term}`sunshine_duration`         | so_h          | sunshine duration            | h     | >=0         |
| {term}`temperature_air_max_2m`    | tlmax         | air temperature max at 2m    | °C    | -           |
| {term}`temperature_air_mean_2m`   | tl_mittel     | air temperature mean at 2m   | °C    | -           |
| {term}`temperature_air_min_2m`    | tlmin         | air temperature min at 2m    | °C    | -           |
| {term}`temperature_air_min_0_05m` | tsmin         | air temperature min at 0.05m | °C    | -           |
| {term}`wind_gust_max`             | ffx           | wind gust max                | m/s   | -           |
| {term}`wind_speed`                | vv_mittel     | wind speed                   | m/s   | -           |
