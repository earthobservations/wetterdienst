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
| {term}`precipitation_amount` | prcp_amt | Precipitation amount, reported to the nearest 0.1 mm. | mm |

### temperature

#### metadata

| property      | value                    |
|---------------|--------------------------|
| name          | temperature              |
| original name | uk-daily-temperature-obs |

#### parameters

| name                              | original name | description                                     | unit |
|-----------------------------------|---------------|-------------------------------------------------|------|
| {term}`temperature_air_max_2m` | max_air_temp | Maximum air temperature, to the nearest 0.1 deg C. The 24 hours ending 09Z on the stamped day (09-09Z) at every station: a 24 hour row ending 09:00 as it is, else the extreme of the 21-09Z row ending 09:00 on the day and the 09-21Z row ending 21:00 on the day before. A day with both kinds of row is the 24 hour row; a day with only one 12 hour half has no value and is told (other-window-left-out). | °C |
| {term}`temperature_air_min_2m` | min_air_temp | Minimum air temperature, to the nearest 0.1 deg C. The 24 hours ending 09Z on the stamped day (09-09Z) at every station: a 24 hour row ending 09:00 as it is, else the extreme of the 21-09Z row ending 09:00 on the day and the 09-21Z row ending 21:00 on the day before. A day with both kinds of row is the 24 hour row; a day with only one 12 hour half has no value and is told (other-window-left-out). | °C |
| {term}`temperature_air_min_0_05m` | min_grss_temp | Minimum grass temperature, to the nearest 0.1 deg C. The day ending 09Z on the stamped day: a 24 hour row ending 09:00 as it is (09-09Z); at a 12 hour station the 21-09Z row ending 09:00 on the day, which stands for the 09-09Z window, the only 12 hour window the file reports it in. A day with both kinds of row is the 24 hour row. | °C |

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
