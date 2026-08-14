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
| {term}`precipitation_height` | prcp_amt | Precipitation amount, reported to the nearest 0.1 mm. | mm |

### temperature

#### metadata

| property      | value                    |
|---------------|--------------------------|
| name          | temperature              |
| original name | uk-daily-temperature-obs |

#### parameters

| name                              | original name | description                                     | unit |
|-----------------------------------|---------------|-------------------------------------------------|------|
| {term}`temperature_air_max_2m` | max_air_temp | Maximum air temperature, to the nearest 0.1 deg C. | °C |
| {term}`temperature_air_min_2m` | min_air_temp | Minimum air temperature, to the nearest 0.1 deg C. | °C |
| {term}`temperature_air_min_0_05m` | min_grss_temp | Minimum grass temperature, to the nearest 0.1 deg C. | °C |

### weather

#### metadata

| property      | value                |
|---------------|----------------------|
| name          | weather              |
| original name | uk-daily-weather-obs |

#### parameters

| name                      | original name    | description                                | unit |
|---------------------------|------------------|--------------------------------------------|------|
| {term}`sunshine_duration` | drv_24hr_sun_dur | Derived 24 hour sunshine duration, for stations carrying radiation sensors only, which use the global radiation values to derive it. | h |
| {term}`snow_depth` | snow_depth | Snow depth, cm. | cm |
| {term}`snow_depth_new` | frsh_snw_amt | Fresh snow amount, cm. | cm |
