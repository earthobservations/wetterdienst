# daily

## metadata

| property      | value    |
|---------------|----------|
| name          | daily    |
| original name | aws_1day |

## datasets

### data

#### parameters

| name                                    | original name            | description                                                                                                                                               | unit |
|-----------------------------------------|--------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m`         | temp_avg                 | Mean air temperature at 2 m above ground.                                                                                                                 | °C   |
| {term}`temperature_air_max_2m`          | temp_max                 | Maximum air temperature at 2 m above ground.                                                                                                              | °C   |
| {term}`temperature_air_min_2m`          | temp_min                 | Minimum air temperature at 2 m above ground.                                                                                                              | °C   |
| {term}`precipitation_amount`            | precip_quantity          | Depth of precipitation collected over the period.                                                                                                         | mm   |
| {term}`temperature_surface_mean`        | temp_grass_pt100_avg     | Mean temperature of a surface (the ground, or the grass on it) as a probe lying on it reads it.                                                           | °C   |
| {term}`temperature_soil_mean_0_05m`     | temp_soil_avg_5cm        | Mean soil temperature at 0.05 m depth.                                                                                                                    | °C   |
| {term}`temperature_soil_mean_0_1m`      | temp_soil_avg_10cm       | Mean soil temperature at 0.1 m depth.                                                                                                                     | °C   |
| {term}`temperature_soil_mean_0_2m`      | temp_soil_avg_20cm       | Mean soil temperature at 0.2 m depth.                                                                                                                     | °C   |
| {term}`temperature_soil_mean_0_5m`      | temp_soil_avg_50cm       | Mean soil temperature at 0.5 m depth.                                                                                                                     | °C   |
| {term}`wind_speed`                      | wind_speed_10m           | Speed of the wind where the source states no statistic or a reading at one moment; the stated mean over the interval is `wind_speed_mean`.                | m/s  |
| {term}`wind_gust_max`                   | wind_gusts_speed         | Speed of the strongest gust of the period.                                                                                                                | m/s  |
| {term}`humidity_relative_mean`          | humidity_rel_shelter_avg | Mean relative humidity of the air over the period, the fraction of the moisture it could hold at that temperature.                                        | %    |
| {term}`pressure_air_site`               | pressure                 | Air pressure as measured at station height, where the source states no statistic or a reading at one moment; the stated mean is `pressure_air_site_mean`. | hPa  |
| {term}`sunshine_duration`               | sun_duration             | Length of time the sun shone unobstructed.                                                                                                                | min  |
| {term}`radiation_global_intensity_mean` | short_wave_from_sky_avg  | Mean global irradiance on a horizontal surface over the period, reported as power rather than energy.                                                     | W/m² |
