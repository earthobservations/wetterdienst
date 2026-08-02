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

| name                 | original name | unit type     | unit |
|----------------------|---------------|---------------|------|
| precipitation_height | prcp_amt      | precipitation | mm   |

### temperature

#### metadata

| property      | value                    |
|---------------|--------------------------|
| name          | temperature              |
| original name | uk-daily-temperature-obs |

#### parameters

| name                      | original name | unit type   | unit |
|---------------------------|---------------|-------------|------|
| temperature_air_max_2m    | max_air_temp  | temperature | °C   |
| temperature_air_min_2m    | min_air_temp  | temperature | °C   |
| temperature_air_min_0_05m | min_grss_temp | temperature | °C   |

### weather

#### metadata

| property      | value                |
|---------------|----------------------|
| name          | weather              |
| original name | uk-daily-weather-obs |

#### parameters

| name              | original name    | unit type    | unit |
|-------------------|------------------|--------------|------|
| sunshine_duration | drv_24hr_sun_dur | time         | h    |
| snow_depth        | snow_depth       | length_short | cm   |
| snow_depth_new    | frsh_snw_amt     | length_short | cm   |
