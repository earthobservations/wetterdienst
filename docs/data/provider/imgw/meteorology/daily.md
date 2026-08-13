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
| {term}`cloud_cover_total` | średnie dobowe zachmurzenie ogólne | Cloud cover total. | 1/8 | >=0,<=100 |
| {term}`humidity` | średnia dobowa wilgotność względna | Humidity. | % | >=0,<=100 |
| {term}`precipitation_height`       | suma dobowa opadów                 | precipitation height       | mm   | >=0         |
| {term}`snow_depth`                 | wysokość pokrywy śnieżnej          | snow depth                 | cm   | >=0         |
| {term}`temperature_air_max_2m`     | maksymalna temperatura dobowa      | temperature air max 2m     | °C   | -           |
| {term}`temperature_air_mean_0_05m` | temperatura minimalna przy gruncie | temperature air mean 0 05m | °C   | -           |
| {term}`temperature_air_mean_2m` | średnia dobowa temperatura | temperature air mean | °C | - |
| {term}`temperature_air_min_2m`     | minimalna temperatura dobowa       | temperature air min 2m     | °C   | -           |
| {term}`wind_speed`                 | średnia dobowa prędkość wiatru     | wind speed                 | m/s  | >=0         |

### precipitation

#### metadata

| property      | value                                                                                                    |
|---------------|----------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                            |
| original name | opad                                                                                                     |
| description   | historical daily precipitation data                                                                      |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/opad/) |

#### parameters

| name                         | original name                 | description          | unit | constraints |
|------------------------------|-------------------------------|----------------------|------|-------------|
| {term}`precipitation_height` | suma dobowa opadów            | precipitation height | mm   | >=0         |
| {term}`snow_depth`           | wysokość pokrywy śnieżnej     | snow depth           | cm   | >=0         |
| {term}`snow_depth_new`       | wysokość świeżospałego śniegu | snow depth new       | cm   | >=0         |

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
| {term}`cloud_cover_total` | średnie dobowe zachmurzenie ogólne | Cloud cover total. | 1/8 | >=0,<=100 |
| {term}`humidity` | średnia dobowa wilgotność względna | Humidity. | % | >=0,<=100 |
| {term}`precipitation_height`    | suma dobowa opadów             | precipitation height | mm   | >=0         |
| {term}`pressure_air_site` | średnia dobowe ciśnienie na poziomie stacji | Pressure air site. | hPa | >=0 |
| {term}`pressure_vapor` | średnia dobowe ciśnienie pary wodnej | Pressure vapor. | hPa | >=0 |
| {term}`temperature_air_mean_2m` | średnia dobowa temperatura     | temperature air mean | °C   | -           |
| {term}`wind_speed`              | średnia dobowa prędkość wiatru | wind speed           | m/s  | >=0         |
| {term}`precipitation_height_day` | suma opadu dzień | Depth of precipitation collected during the daytime hours. | millimeter | - |
| {term}`precipitation_height_night` | suma opadu noc | Depth of precipitation collected during the night hours. | millimeter | - |
| {term}`pressure_air_sea_level` | średnie dobowe ciśnienie na pozimie morza | Air pressure reduced to mean sea level, so that stations at different heights compare. | hectopascal | - |
