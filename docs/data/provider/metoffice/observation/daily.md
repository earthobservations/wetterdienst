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

| name                         | original name | unit |
|------------------------------|---------------|------|
| {term}`precipitation_height` | prcp_amt      | mm   |

### temperature

#### metadata

| property      | value                    |
|---------------|--------------------------|
| name          | temperature              |
| original name | uk-daily-temperature-obs |

#### parameters

| name                              | original name | unit |
|-----------------------------------|---------------|------|
| {term}`temperature_air_max_2m`    | max_air_temp  | °C   |
| {term}`temperature_air_min_2m`    | min_air_temp  | °C   |
| {term}`temperature_air_min_0_05m` | min_grss_temp | °C   |

### weather

#### metadata

| property      | value                |
|---------------|----------------------|
| name          | weather              |
| original name | uk-daily-weather-obs |

#### parameters

| name                      | original name    | unit |
|---------------------------|------------------|------|
| {term}`sunshine_duration` | drv_24hr_sun_dur | h    |
| {term}`snow_depth`        | snow_depth       | cm   |
| {term}`snow_depth_new`    | frsh_snw_amt     | cm   |
