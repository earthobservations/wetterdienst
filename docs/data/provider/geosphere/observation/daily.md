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
| url           | [here](https://data.hub.zamg.ac.at/dataset/klima-v1-1d)                              |

#### parameters

| name                      | original name | description                  | unit             | original unit    | constraints               |
|---------------------------|---------------|------------------------------|------------------|------------------|---------------------------|
| cloud_cover_total         | bewm_mittel   | total cloud cover            | :math:`\%`       | :math:`\%`       | :math:`\geq{0},\leq{100}` |
| humidity                  | rf_mittel     | relative humidity            | :math:`\%`       | :math:`\%`       | :math:`\geq{0},\leq{100}` |
| precipitation_height      | rr            | precipitation height         | :math:`kg / m^2` | :math:`mm`       | :math:`\geq{0}`           |
| pressure_air_site         | p_mittel      | air pressure at site         | :math:`Pa`       | :math:`hPa`      | :math:`\geq{0}`           |
| pressure_vapor            | dampf_mittel  | vapor pressure               | :math:`Pa`       | :math:`hPa`      | :math:`\geq{0}`           |
| radiation_global          | cglo_j        | global radiation             | :math:`J / m^2`  | :math:`J / cm^2` | :math:`\geq{0}`           |
| snow_depth                | sh            | snow depth                   | :math:`m`        | :math:`cm`       | :math:`\geq{0}`           |
| snow_depth_manual         | sh_manu       | manually measured snow depth | :math:`m`        | :math:`cm`       | :math:`\geq{0}`           |
| snow_depth_new            | shneu_manu    | new snow depth               | :math:`m`        | :math:`cm`       | :math:`\geq{0}`           |
| sunshine_duration         | so_h          | sunshine duration            | :math:`s`        | :math:`h`        | :math:`\geq{0}`           |
| temperature_air_max_2m    | tlmax         | air temperature max at 2m    | :math:`K`        | :math:`°C`       | :math:`None`              |
| temperature_air_mean_2m   | tl_mittel     | air temperature mean at 2m   | :math:`K`        | :math:`°C`       | :math:`None`              |
| temperature_air_min_2m    | tlmin         | air temperature min at 2m    | :math:`K`        | :math:`°C`       | :math:`None`              |
| temperature_air_min_0_05m | tsmin         | air temperature min at 0.05m | :math:`K`        | :math:`°C`       | :math:`None`              |
| wind_gust_max             | ffx           | wind gust max                | :math:`m / s`    | :math:`m / s`    | :math:`None`              |
| wind_speed                | vv_mittel     | wind speed                   | :math:`m / s`    | :math:`m / s`    | :math:`None`              |
