# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | P1D   |

## datasets

### data

#### parameters

| name                        | original name                                       | unit type       | unit |
|-----------------------------|-----------------------------------------------------|-----------------|------|
| temperature_air_mean_2m     | mean(air_temperature P1D)                           | temperature     | °C   |
| temperature_air_max_2m      | max(air_temperature P1D)                            | temperature     | °C   |
| temperature_air_min_2m      | min(air_temperature P1D)                            | temperature     | °C   |
| precipitation_height        | sum(precipitation_amount P1D)                       | precipitation   | mm   |
| wind_speed                  | mean(wind_speed P1D)                                | speed           | m/s  |
| wind_speed_rolling_mean_max | max(wind_speed P1D)                                 | speed           | m/s  |
| humidity                    | mean(relative_humidity P1D)                         | fraction        | %    |
| pressure_air_sea_level      | mean(air_pressure_at_sea_level P1D)                 | pressure        | hPa  |
| pressure_air_site           | mean(surface_air_pressure P1D)                      | pressure        | hPa  |
| radiation_global            | mean(surface_downwelling_shortwave_flux_in_air P1D) | power_per_area  | W/m² |
| snow_depth                  | surface_snow_thickness                              | length_short    | cm   |
| sunshine_duration           | sum(duration_of_sunshine P1D)                       | time            | s    |
