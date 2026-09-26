# hourly

## metadata

| property      | value                                                                                     |
|---------------|-------------------------------------------------------------------------------------------|
| name          | hourly                                                                                    |
| original name | hourly                                                                                    |
| url           | [here](https://www.dwd.de/DE/leistungen/met_verfahren_ptp_dmo/met_verfahren_ptp_dmo.html) |

## datasets

### icon_eu

#### metadata

| property         | value                                                                                                                                                                                                                                          |
|------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | icon_eu                                                                                                                                                                                                                                        |
| original name    | icon_eu                                                                                                                                                                                                                                        |
| description      | Direct model output of the regional ICON-EU model, extracted at the stations it is published for, a smaller set than the global product's though not a subset of it. Issued twice a day (00 and 12 UTC), hourly out to a lead-time of 78 hours |
| description file | [here](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)                                                                                                                                                                           |
| access           | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon-eu/)                                                                                                                                                                           |

#### parameters

| name                                            | original name | description                                    | unit  | constraints |
|-------------------------------------------------|---------------|------------------------------------------------|-------|-------------|
| {term}`cloud_cover_above_7km`                   | nh            | High cloud cover (>7 km)                       | %     | >=0,<=100   |
| {term}`cloud_cover_below_1000ft`                | nl            | Low cloud cover (lower than 2 km).             | %     | >=0,<=100   |
| {term}`cloud_cover_between_2km_to_7km`          | nm            | Midlevel cloud cover (2-7 km)                  | %     | >=0,<=100   |
| {term}`cloud_cover_effective`                   | neff          | Effective cloud cover                          | %     | >=0,<=100   |
| {term}`cloud_cover_total`                       | n             | Total cloud cover                              | %     | >=0,<=100   |
| {term}`precipitation_height_last_1h`            | rr1           | Total precipitation during the last hour       | kg/m² | >=0         |
| {term}`pressure_air_site_reduced`               | pppp          | Surface pressure, reduced                      | Pa    | >=0         |
| {term}`radiation_global`                        | rad1h         | Global Irradiance                              | kJ/m² | >=0         |
| {term}`temperature_air_max_2m`                  | tx            | Maximum temperature - within the last 12 hours | K     | -           |
| {term}`temperature_air_mean_0_05m`              | t5cm          | Temperature 5cm above surface                  | K     | -           |
| {term}`temperature_air_mean_2m`                 | ttt           | Temperature 2m above surface                   | K     | -           |
| {term}`temperature_air_min_2m`                  | tn            | Minimum temperature - within the last 12 hours | K     | -           |
| {term}`temperature_dew_point_mean_2m`           | td            | Dewpoint 2m above surface                      | K     | -           |
| {term}`water_equivalent_snow_depth_new_last_1h` | rrs1c         | Snow-Rain-Equivalent during the last hour      | kg/m² | >=0         |
| {term}`weather_last_6h`                         | w1w2          | Past weather during the last 6 hours           | -     | -           |
| {term}`weather_significant`                     | ww            | Significant Weather                            | -     | -           |
| {term}`wind_direction`                          | dd            | Wind direction                                 | °     | >=0,<=360   |
| {term}`wind_gust_max_last_3h`                   | fx3           | Maximum wind gust within the last 3 hours      | m/s   | >=0         |
| {term}`wind_speed`                              | ff            | Wind speed                                     | m/s   | >=0         |

### icon

#### metadata

| property         | value                                                                                                                                                                                                   |
|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | icon                                                                                                                                                                                                    |
| original name    | icon                                                                                                                                                                                                    |
| description      | Direct model output of the global ICON model, extracted at worldwide stations. Issued twice a day (00 and 12 UTC) as two runs: hourly out to a lead-time of 78 hours, and 3-hourly from 78 to 168 hours |
| description file | [here](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)                                                                                                                                    |
| access           | [here](https://opendata.dwd.de/weather/local_forecasts/dmo/icon/)                                                                                                                                       |

#### parameters

| name                                            | original name | description                                          | unit  | constraints |
|-------------------------------------------------|---------------|------------------------------------------------------|-------|-------------|
| {term}`cloud_cover_above_7km`                   | nh            | High cloud cover (>7 km)                             | %     | >=0,<=100   |
| {term}`cloud_cover_below_1000ft`                | nl            | Low cloud cover (lower than 2 km).                   | %     | >=0,<=100   |
| {term}`cloud_cover_between_2km_to_7km`          | nm            | Midlevel cloud cover (2-7 km)                        | %     | >=0,<=100   |
| {term}`cloud_cover_effective`                   | neff          | Effective cloud cover                                | %     | >=0,<=100   |
| {term}`cloud_cover_total`                       | n             | Total cloud cover                                    | %     | >=0,<=100   |
| {term}`precipitation_height_last_1h`            | rr1           | Total precipitation during the last hour             | kg/m² | >=0         |
| {term}`precipitation_height_last_3h`            | rr3           | Total precipitation during the last 3 hours          | kg/m² | >=0         |
| {term}`pressure_air_site_reduced`               | pppp          | Surface pressure, reduced                            | Pa    | >=0         |
| {term}`radiation_global`                        | rad1h         | Global Irradiance                                    | kJ/m² | >=0         |
| {term}`radiation_global_last_3h`                | rads3         | Short wave radiation balance during the last 3 hours | kJ/m² | -           |
| {term}`radiation_sky_long_wave_last_3h`         | radl3         | Long wave radiation balance during the last 3 hours  | kJ/m² | -           |
| {term}`temperature_air_max_2m`                  | tx            | Maximum temperature - within the last 12 hours       | K     | -           |
| {term}`temperature_air_mean_0_05m`              | t5cm          | Temperature 5cm above surface                        | K     | -           |
| {term}`temperature_air_mean_2m`                 | ttt           | Temperature 2m above surface                         | K     | -           |
| {term}`temperature_air_min_2m`                  | tn            | Minimum temperature - within the last 12 hours       | K     | -           |
| {term}`temperature_dew_point_mean_2m`           | td            | Dewpoint 2m above surface                            | K     | -           |
| {term}`water_equivalent_snow_depth_new_last_1h` | rrs1c         | Snow-Rain-Equivalent during the last hour            | kg/m² | >=0         |
| {term}`water_equivalent_snow_depth_new_last_3h` | rrs3c         | Snow-Rain-Equivalent during the last 3 hours         | kg/m² | >=0         |
| {term}`weather_last_6h`                         | w1w2          | Past weather during the last 6 hours                 | -     | -           |
| {term}`weather_significant`                     | ww            | Significant Weather                                  | -     | -           |
| {term}`wind_direction`                          | dd            | Wind direction                                       | °     | >=0,<=360   |
| {term}`wind_gust_max_last_3h`                   | fx3           | Maximum wind gust within the last 3 hours            | m/s   | >=0         |
| {term}`wind_speed`                              | ff            | Wind speed                                           | m/s   | >=0         |
