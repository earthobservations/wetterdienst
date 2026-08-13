# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | P1D   |

## datasets

### data

#### parameters

| name                                | original name                                       | description                                                                                                                                                                                                                                                                                                                            | unit |
|-------------------------------------|-----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | mean(air_temperature P1D) | Daily mean temperature. The mean is an arithmetic mean of 24 hourly values (00-00 UTC), or a formula based mean value when only a limited number of observations is available (e.g. 06, 12, 18 UTC). | degree_celsius |
| {term}`temperature_air_max_2m` | max(air_temperature P1D) | Highest recorded air temperature per 24 hours | degree_celsius |
| {term}`temperature_air_min_2m` | min(air_temperature P1D) | Lowest recorded air temperature per 24 hours | degree_celsius |
| {term}`precipitation_height` | sum(precipitation_amount P1D) | Daily precipitation sum (between 06-06 UTC). | millimeter |
| {term}`wind_speed` | mean(wind_speed P1D) | Daily mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available). | meter_per_second |
| {term}`wind_speed_rolling_mean_max` | max(wind_speed P1D) | Daily maximum mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available). | meter_per_second |
| {term}`humidity` | mean(relative_humidity P1D) | Daily mean relative humidity. | percent |
| {term}`pressure_air_sea_level` | mean(air_pressure_at_sea_level P1D) | Mean daily air pressure reduced to sea level. The parameter is usually called QFF in aviation and shows the measured air pressure reduced to mean sea level by applying actual atmospheric conditions. | hectopascal |
| {term}`pressure_air_site` | mean(surface_air_pressure P1D) | Daily mean air pressure at the station. The parameter is usually called QFE in aviation and shows the measured air pressure reduced to the reference height of the station. | hectopascal |
| {term}`radiation_global_intensity` | mean(surface_downwelling_shortwave_flux_in_air P1D) | Mean global radiation over the last 24 hours. Global radiation is the total downwelling shortwave radiation from the sun. Shortwave radiation have wavelengths in the area 295-2800 nm and therefore includes ultraviolet, visible and infrared light. The instrument measures the radiation flux through a horizontal surface (W/m2). | watt_per_square_meter |
| {term}`snow_depth` | surface_snow_thickness | The depth of the snow is measured in cm from the ground to the top of the snow cover. Code -1 means no snow. | centimeter |
| {term}`sunshine_duration` | sum(duration_of_sunshine P1D) | Number of hours of sunshine over the last 24 hours. | second |
