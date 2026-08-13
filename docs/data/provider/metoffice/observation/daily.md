# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | daily |

## datasets

### rain

#### metadata

| property      | value             |
|---------------|-------------------|
| name          | rain              |
| original name | uk-daily-rain-obs |

#### parameters

| name                         | original name | description                                       | unit |
|------------------------------|---------------|---------------------------------------------------|------|
| {term}`precipitation_height` | prcp_amt      | Depth of precipitation collected over the period. | mm   |

### temperature

#### metadata

| property      | value                    |
|---------------|--------------------------|
| name          | temperature              |
| original name | uk-daily-temperature-obs |

#### parameters

| name                              | original name | description                                     | unit |
|-----------------------------------|---------------|-------------------------------------------------|------|
| {term}`temperature_air_max_2m`    | max_air_temp  | Maximum air temperature at 2 m above ground.    | °C   |
| {term}`temperature_air_min_2m`    | min_air_temp  | Minimum air temperature at 2 m above ground.    | °C   |
| {term}`temperature_air_min_0_05m` | min_grss_temp | Minimum air temperature at 0.05 m above ground. | °C   |

### weather

#### metadata

| property      | value                |
|---------------|----------------------|
| name          | weather              |
| original name | uk-daily-weather-obs |

#### parameters

| name                      | original name    | description                                | unit |
|---------------------------|------------------|--------------------------------------------|------|
| {term}`sunshine_duration` | drv_24hr_sun_dur | Length of time the sun shone unobstructed. | h    |
| {term}`snow_depth`        | snow_depth       | Depth of the snow lying on the ground.     | cm   |
| {term}`snow_depth_new`    | frsh_snw_amt     | Depth of snow that fell during the period. | cm   |
