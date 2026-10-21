# monthly

## metadata

| property      | value                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------|
| name          | monthly                                                                                                 |
| original name | miesięczne                                                                                              |
| url           | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/) |

## datasets

### climate

#### metadata

| property      | value                                                                                                          |
|---------------|----------------------------------------------------------------------------------------------------------------|
| name          | climate |
| original name | klimat                                                                                                         |
| description   | historical monthly climate data                                                                                |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/klimat/) |

#### parameters

| name                                | original name                        | description                 | unit | constraints |
|-------------------------------------|--------------------------------------|-----------------------------|------|-------------|
| {term}`cloud_cover_total_mean` | średnie miesięczne zachmurzenie ogólne | Average monthly total cloud cover, in oktas. | 1/8 | >=0,<=100 |
| {term}`humidity_relative_mean` | średnia miesięczna wilgotność względna | Average monthly relative humidity, in percent. | % | >=0,<=100 |
| {term}`precipitation_amount` | miesieczna suma opadów | Monthly precipitation sum, in mm. | mm | >=0 |
| {term}`precipitation_amount_max` | maksymalna dobowa suma opadów | Maximum daily precipitation sum of the month, in mm. | mm | >=0 |
| {term}`snow_depth_max` | maksymalna wysokość pokrywy śnieżnej | Maximum height of the snow cover in the month, in cm. A 0 without a status means that there was no snow cover in the month or that the maximum cannot be determined. | cm | >=0 |
| {term}`temperature_air_max_2m` | absolutna temperatura maksymalna | Absolute maximum air temperature of the month, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_max_2m_mean` | średnia temperatura maksymalna | Average maximum air temperature of the month (the mean of the daily maxima), in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_mean_2m` | średnia miesięczna temperatura | Average monthly air temperature (the mean of the daily means), in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_min_0_05m` | minimalna temperatura przy gruncie | Minimum air temperature of the month at the ground (przy gruncie), in °C. The source states no height: the file says at the ground, never 5 cm. | °C | - |
| {term}`temperature_air_min_2m` | absolutna temperatura minimalna | Absolute minimum air temperature of the month, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_min_2m_mean` | średnia temperatura minimalna | Average minimum air temperature of the month (the mean of the daily minima), in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`wind_speed_mean` | średnia miesięczna prędkość wiatru | Average monthly wind speed, in m/s. | m/s | >=0 |

### precipitation

#### metadata

| property      | value                                                                                                        |
|---------------|--------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                |
| original name | opad                                                                                                         |
| description   | historical monthly precipitation data                                                                        |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/opad/) |

#### parameters

| name                             | original name          | description                                                                                                                                             | unit | constraints |
|----------------------------------|------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`precipitation_amount`     | miesięczna suma opadów | Monthly precipitation sum, in mm.                                                                                                                       | mm   | >=0         |
| {term}`precipitation_amount_max` | opad maksymalny        | Maximum precipitation of the month, in mm. The file names no period; it is the maximum daily sum of the month, as the climate and synop files state it. | mm   | >=0         |

### synop

#### metadata

| property      | value                                                                                                         |
|---------------|---------------------------------------------------------------------------------------------------------------|
| name          | synop                                                                                                         |
| original name | synop                                                                                                         |
| description   | historical monthly synop data                                                                                 |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/synop/) |

#### parameters

| name                                | original name                                   | description                 | unit | constraints |
|-------------------------------------|-------------------------------------------------|-----------------------------|------|-------------|
| {term}`cloud_cover_total_mean` | średnie miesięczne zachmurzenie ogólne | Average monthly total cloud cover, in oktas. | 1/8 | >=0,<=100 |
| {term}`humidity_relative_mean` | średnia miesięczna wilgotność względna | Average monthly relative humidity, in percent. | % | >=0,<=100 |
| {term}`precipitation_amount` | miesięczna suma opadów | Monthly precipitation sum, in mm. | mm | >=0 |
| {term}`precipitation_amount_day` | suma opadu dzień | Depth of precipitation collected during the daytime hours. | mm | >=0 |
| {term}`precipitation_amount_max` | maksymalna dobowa suma opadów | precipitation height max | mm | >=0 |
| {term}`precipitation_amount_night` | suma opadu noc | Depth of precipitation collected during the night hours. | mm | >=0 |
| {term}`pressure_air_site_mean` | średnie miesięczne ciśnienie na poziomie stacji | Average monthly air pressure at station level, in hPa. | hPa | >=0 |
| {term}`pressure_air_sea_level_mean` | średnie miesięczne ciśnienie na pozimie morza | Average monthly air pressure at sea level, in hPa. | hPa | >=0 |
| {term}`pressure_vapor_mean` | średnie miesięczne ciśnienie pary wodnej | Average monthly water vapor pressure, in hPa. | hPa | >=0 |
| {term}`snow_depth_max` | maksymalna wysokość pokrywy śnieżnej | Maximum height of the snow cover in the month, in cm. | cm | >=0 |
| {term}`temperature_air_max_2m` | absolutna temperatura maksymalna | Absolute maximum air temperature of the month, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_max_2m_mean` | średnia temperatura maksymalna | Average maximum air temperature of the month (the mean of the daily maxima), in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_min_2m` | absolutna temperatura minimalna | Absolute minimum air temperature of the month, in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_min_2m_mean` | średnia temperatura minimalna | Average minimum air temperature of the month (the mean of the daily minima), in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`temperature_air_min_0_05m` | minimalna temperatura przy gruncie | Minimum air temperature of the month at the ground (przy gruncie), in °C. The source states no height: the file says at the ground, never 5 cm. | °C | - |
| {term}`temperature_air_mean_2m` | średnia miesięczna temperatura | Average monthly air temperature (the mean of the daily means), in °C. The file states no height; the 2 m of the name is the shelter convention. | °C | - |
| {term}`wind_speed_mean` | średnia miesięczna prędkość wiatru | Average monthly wind speed, in m/s. | m/s | >=0 |
