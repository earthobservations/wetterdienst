# hourly

## metadata

| property      | value  |
|---------------|--------|
| name          | hourly |
| original name | PT1H   |

## datasets

### data

#### parameters

| name                                  | original name                                        | description                                                                                                                                                                                                                                                                                                            | unit |
|---------------------------------------|------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m`       | air_temperature                                      | Air temperature (default 2 m above ground), present value                                                                                                                                                                                                                                                              | °C   |
| {term}`temperature_dew_point_mean_2m` | dew_point_temperature                                | Dew-point temperature - the temperature at which the air, when cooled, will become saturated (and dew is formed)                                                                                                                                                                                                       | °C   |
| {term}`humidity`                      | relative_humidity                                    | Relative humidity                                                                                                                                                                                                                                                                                                      | %    |
| {term}`wind_speed`                    | wind_speed                                           | Mean wind speed is registered as a mean value of the wind speed over the last ten minutes before the observation time. (default: 10 meters above ground, some stations have measurements at 2 meters)                                                                                                                  | m/s  |
| {term}`wind_direction`                | wind_from_direction                                  | Mean wind direction over the last ten minutes before the observation time. Wind direction is defined as the direction from which the wind blows and is registered in degrees, where 360 degrees is north and 90 degrees is east.                                                                                       | °    |
| {term}`pressure_air_sea_level`        | air_pressure_at_sea_level                            | Air pressure reduced to mean sea level. The parameter is usually called QFF in aviation and shows the measured air pressure reduced to mean sea level by applying actual atmospheric conditions.                                                                                                                       | hPa  |
| {term}`pressure_air_site`             | surface_air_pressure                                 | Air pressure at the station. The parameter is usually called QFE in aviation and shows the measured air pressure reduced to the reference height of the station.                                                                                                                                                       | hPa  |
| {term}`cloud_cover_total`             | cloud_area_fraction                                  | Total cloud cover is registered using a code 0 - 8 describing how many eights of the sky are covered by clouds (0 = no clouds, 8 = completely overcast. Code -3 or 9 = cloud cover can not be estimated because the sky is obstructed from view because of fog, drifting snow etc. Code -3 is presented as .).         | %    |
| {term}`radiation_global_intensity`    | mean(surface_downwelling_shortwave_flux_in_air PT1H) | Hourly mean global radiation. Global radiation is the total downwelling shortwave radiation from the sun. Shortwave radiation have wavelengths in the area 295-2800 nm and therefore includes ultraviolet, visible and infrared light. The instrument measures the radiation flux through a horizontal surface (W/m2). | W/m² |
| {term}`precipitation_height`          | sum(precipitation_amount PT1H)                       | Amount of precipitation per hour                                                                                                                                                                                                                                                                                       | mm   |
| {term}`snow_depth`                    | surface_snow_thickness                               | The depth of the snow is measured in cm from the ground to the top of the snow cover. (Code=-1 means no snow and can be presented as .)                                                                                                                                                                                | cm   |
