# daily

## metadata

| property      | value                                                                                               |
|---------------|-----------------------------------------------------------------------------------------------------|
| name          | daily                                                                                               |
| original name | dobowe                                                                                              |
| url           | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/) |

## datasets

### climate

#### metadata

| property      | value                                                                                                      |
|---------------|------------------------------------------------------------------------------------------------------------|
| name          | climate                                                                                                    |
| original name | klimat                                                                                                     |
| description   | historical daily climate data                                                                              |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/klimat/) |

#### parameters

| name                               | original name                      | description                | unit | constraints |
|------------------------------------|------------------------------------|----------------------------|------|-------------|
| {term}`cloud_cover_total_mean` | średnie dobowe zachmurzenie ogólne | Average daily total cloud cover, in oktas. | 1/8 | >=0,<=100 |
| {term}`humidity_relative_mean` | średnia dobowa wilgotność względna | Average daily relative humidity, in percent. | % | >=0,<=100 |
| {term}`precipitation_amount` | suma dobowa opadów | Daily precipitation sum, in mm. | mm | >=0 |
| {term}`snow_depth` | wysokość pokrywy śnieżnej | Height of the snow cover, in cm. | cm | >=0 |
| {term}`temperature_air_max_2m` | maksymalna temperatura dobowa | Maximum daily air temperature, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_mean_2m` | średnia dobowa temperatura | Average daily air temperature, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_min_0_05m` | temperatura minimalna przy gruncie | Minimum daily air temperature at the ground (przy gruncie), in °C. The source states no height: the file says at the ground, never 5 cm. | °C | - |
| {term}`temperature_air_min_2m` | minimalna temperatura dobowa | Minimum daily air temperature, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`wind_speed_mean` | średnia dobowa prędkość wiatru | Average daily wind speed, in m/s. | m/s | >=0 |

### precipitation

#### metadata

| property      | value                                                                                                    |
|---------------|----------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                            |
| original name | opad                                                                                                     |
| description   | historical daily precipitation data                                                                      |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/opad/) |

#### parameters

| name                         | original name                 | description                                                                                                                                            | unit | constraints |
|------------------------------|-------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`precipitation_amount` | suma dobowa opadów            | Daily precipitation sum, in mm. The status Z marks an opad zbiorczy: the sum of the preceding days without a measurement, without saying when it fell. | mm   | >=0         |
| {term}`snow_depth`           | wysokość pokrywy śnieżnej     | Height of the snow cover, in cm.                                                                                                                       | cm   | >=0         |
| {term}`snow_depth_new`       | wysokość świeżospałego śniegu | Height of the freshly fallen snow, in cm.                                                                                                              | cm   | >=0         |

### synop

#### metadata

| property      | value                                                                                                     |
|---------------|-----------------------------------------------------------------------------------------------------------|
| name          | synop                                                                                                     |
| original name | synop                                                                                                     |
| description   | historical daily synop data                                                                               |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop/) |

#### parameters

| name                            | original name                  | description          | unit | constraints |
|---------------------------------|--------------------------------|----------------------|------|-------------|
| {term}`cloud_cover_total_mean` | średnie dobowe zachmurzenie ogólne | Average daily total cloud cover, in oktas. | 1/8 | >=0,<=100 |
| {term}`humidity_relative_mean` | średnia dobowa wilgotność względna | Average daily relative humidity, in percent. | % | >=0,<=100 |
| {term}`precipitation_amount` | suma dobowa opadów | Daily precipitation sum, in mm. | mm | >=0 |
| {term}`precipitation_amount_day` | suma opadu dzień | Depth of precipitation collected during the daytime hours. | mm | >=0 |
| {term}`precipitation_amount_night` | suma opadu noc | Depth of precipitation collected during the night hours. | mm | >=0 |
| {term}`pressure_air_site_mean` | średnia dobowe ciśnienie na poziomie stacji | Average daily air pressure at station level, in hPa. | hPa | >=0 |
| {term}`pressure_air_sea_level_mean` | średnie dobowe ciśnienie na pozimie morza | Mean air pressure reduced to mean sea level over the period, so that stations at different heights compare. | hPa | >=0 |
| {term}`pressure_vapor_mean` | średnia dobowe ciśnienie pary wodnej | Average daily water vapor pressure, in hPa. | hPa | >=0 |
| {term}`snow_depth` | wysokość pokrywy śnieżnej | Height of the snow cover, in cm. | cm | >=0 |
| {term}`temperature_air_max_2m` | maksymalna temperatura dobowa | Maximum daily air temperature, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_mean_2m` | średnia dobowa temperatura | Average daily air temperature, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_min_0_05m` | temperatura minimalna przy gruncie | Minimum daily air temperature at the ground (przy gruncie), in °C. The source states no height: the file says at the ground, never 5 cm. | °C | - |
| {term}`temperature_air_min_2m` | minimalna temperatura dobowa | Minimum daily air temperature, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`wind_speed_mean` | średnia dobowa prędkość wiatru | Average daily wind speed, in m/s. | m/s | >=0 |
