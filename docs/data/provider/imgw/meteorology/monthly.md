# monthly

## metadata

| property      | value                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------|
| name          | monthly                                                                                                 |
| original name | miesięczne                                                                                              |
| url           | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/) |

## datasets

### data

#### metadata

| property      | value                                                                                                          |
|---------------|----------------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                           |
| original name | klimat                                                                                                         |
| description   | historical monthly climate data                                                                                |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/klimat/) |

#### parameters

| name                                | original name                        | description                 | unit | constraints |
|-------------------------------------|--------------------------------------|-----------------------------|------|-------------|
| {term}`cloud_cover_total`           | średnie miesięczne zachmurzenie      | cloud cover total           | 1/8  | >=0,<=100   |
| {term}`humidity`                    | średnia miesięczna wilgotność        | humidity                    | %    | >=0,<=100   |
| {term}`precipitation_height`        | miesieczna suma opadów               | precipitation height        | mm   | >=0         |
| {term}`precipitation_height_max`    | maksymalna dobowa suma opadóww       | precipitation height max    | mm   | >=0         |
| {term}`snow_depth_max`              | maksymalna wysokość pokrywy śnieżnej | snow depth max              | cm   | >=0         |
| {term}`temperature_air_max_2m`      | absolutna temperatura maksymalna     | temperature air max 2m      | °C   | -           |
| {term}`temperature_air_max_2m_mean` | średnia temperatura maksymalna       | temperature air max 2m mean | °C   | -           |
| {term}`temperature_air_mean_2m`     | średnia miesięczna temperatura       | temperature air mean 2m     | °C   | -           |
| {term}`temperature_air_min_0_05m`   | minimalna temperatura przy gruncie   | temperature air min 0 05m   | °C   | -           |
| {term}`temperature_air_min_2m`      | absolutna temperatura minimalna      | temperature air min 2m      | °C   | -           |
| {term}`temperature_air_min_2m_mean` | średnia temperatura minimalna        | temperature air min 2m mean | °C   | -           |
| {term}`wind_speed`                  | średnia miesięczna prędkość wiatru   | wind speed                  | m/s  | >=0         |

### precipitation

#### metadata

| property      | value                                                                                                        |
|---------------|--------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                |
| original name | opad                                                                                                         |
| description   | historical monthly precipitation data                                                                        |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/opad/) |

#### parameters

| name                             | original name          | description              | unit | constraints |
|----------------------------------|------------------------|--------------------------|------|-------------|
| {term}`precipitation_height`     | miesięczna suma opadów | precipitation height     | mm   | >=0         |
| {term}`precipitation_height_max` | opad maksymalny        | precipitation height max | mm   | >=0         |

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
| {term}`cloud_cover_total` | średnie miesięczne zachmurzenie ogólne | Cloud cover total. | 1/8 | >=0,<=100 |
| {term}`humidity` | średnia miesięczna wilgotność względna | Humidity. | % | >=0,<=100 |
| {term}`pressure_air_site`           | średnie miesięczne ciśnienie na poziomie stacji | pressure air site           | hPa  | >=0         |
| {term}`pressure_air_sea_level`      | średnie miesięczne ciśnienie na pozimie morza   | pressure air sea level      | hPa  | >=0         |
| {term}`pressure_vapor`              | średnie miesięczne ciśnienie pary wodnej        | pressure vapor              | hPa  | >=0         |
| {term}`snow_depth_max`              | maksymalna wysokość pokrywy śnieżnej            | snow depth max              | cm   | >=0         |
| {term}`temperature_air_max_2m`      | absolutna temperatura maksymalna                | temperature air max 2m      | °C   | -           |
| {term}`temperature_air_max_2m_mean` | średnia temperatura maksymalna                  | temperature air max 2m mean | °C   | -           |
| {term}`temperature_air_mean_2m`     | średnia miesięczna temperatura                  | temperature air mean 2m     | °C   | -           |
| {term}`temperature_air_min_0_05m`   | minimalna temperatura przy gruncie              | temperature air min 0 05m   | °C   | -           |
| {term}`temperature_air_min_2m`      | absolutna temperatura minimalna                 | temperature air min 2m      | °C   | -           |
| {term}`temperature_air_min_2m_mean` | średnia temperatura minimalna                   | temperature air min 2m mean | °C   | -           |
| {term}`wind_speed`                  | średnia miesięczna prędkość wiatru              | wind speed                  | m/s  | >=0         |
