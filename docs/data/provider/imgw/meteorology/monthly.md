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

| name                        | original name                        | description                 | unit               | original unit | constraints               |
|-----------------------------|--------------------------------------|-----------------------------|--------------------|---------------|---------------------------|
| cloud_cover_total           | średnie miesięczne zachmurzenie      | cloud cover total           | %         | 1/8   | >=0,<=100 |
| humidity                    | średnia miesięczna wilgotność        | humidity                    | %         | %    | >=0,<=100 |
| precipitation_height        | miesieczna suma opadów               | precipitation height        | kg/m² | mm    | >=0           |
| precipitation_height_max    | maksymalna dobowa suma opadóww       | precipitation height max    | kg/m² | mm    | >=0           |
| snow_depth_max              | maksymalna wysokość pokrywy śnieżnej | snow depth max              | m          | cm    | >=0           |
| temperature_air_max_2m      | absolutna temperatura maksymalna     | temperature air max 2m      | K          | °C    | -              |
| temperature_air_max_2m_mean | średnia temperatura maksymalna       | temperature air max 2m mean | K          | °C    | -              |
| temperature_air_mean_2m     | średnia miesięczna temperatura       | temperature air mean 2m     | K          | °C    | -              |
| temperature_air_min_0_05m   | minimalna temperatura przy gruncie   | temperature air min 0 05m   | K          | °C    | -              |
| temperature_air_min_2m      | absolutna temperatura minimalna      | temperature air min 2m      | K          | °C    | -              |
| temperature_air_min_2m_mean | średnia temperatura minimalna        | temperature air min 2m mean | K          | °C    | -              |
| wind_speed                  | średnia miesięczna prędkość wiatru   | wind speed                  | m/s        | m/s   | >=0           |

### precipitation

#### metadata

| property      | value                                                                                                        |
|---------------|--------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                |
| original name | opad                                                                                                         |
| description   | historical monthly precipitation data                                                                        |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/opad/) |

#### parameters

| name                     | original name          | description              | unit               | original unit | constraints     |
|--------------------------|------------------------|--------------------------|--------------------|---------------|-----------------|
| precipitation_height     | miesięczna suma opadów | precipitation height     | kg/m² | mm    | >=0 |
| precipitation_height_max | opad maksymalny        | precipitation height max | kg/m² | mm    | >=0 |

### synop

#### metadata

| property      | value                                                                                                         |
|---------------|---------------------------------------------------------------------------------------------------------------|
| name          | synop                                                                                                         |
| original name | synop                                                                                                         |
| description   | historical monthly synop data                                                                                 |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/miesieczne/synop/) |

#### parameters

| name                        | original name                                   | description                 | unit        | original unit | constraints               |
|-----------------------------|-------------------------------------------------|-----------------------------|-------------|---------------|---------------------------|
| cloud_cover_total           | średnie miesięczne zachmurzenie                 | cloud cover total           | %  | 1/8   | >=0,<=100 |
| humidity                    | średnia miesięczna wilgotność                   | humidity                    | %  | %    | >=0,<=100 |
| pressure_air_site           | średnie miesięczne ciśnienie na poziomie stacji | pressure air site           | Pa  | hPa   | >=0           |
| pressure_air_sea_level      | średnie miesięczne ciśnienie na pozimie morza   | pressure air sea level      | Pa  | hPa   | >=0           |
| pressure_vapor              | średnie miesięczne ciśnienie pary wodnej        | pressure vapor              | Pa  | hPa   | >=0           |
| snow_depth_max              | maksymalna wysokość pokrywy śnieżnej            | snow depth max              | m   | cm    | >=0           |
| temperature_air_max_2m      | absolutna temperatura maksymalna                | temperature air max 2m      | K   | °C    | -              |
| temperature_air_max_2m_mean | średnia temperatura maksymalna                  | temperature air max 2m mean | K   | °C    | -              |
| temperature_air_mean_2m     | średnia miesięczna temperatura                  | temperature air mean 2m     | K   | °C    | -              |
| temperature_air_min_0_05m   | minimalna temperatura przy gruncie              | temperature air min 0 05m   | K   | °C    | -              |
| temperature_air_min_2m      | absolutna temperatura minimalna                 | temperature air min 2m      | K   | °C    | -              |
| temperature_air_min_2m_mean | średnia temperatura minimalna                   | temperature air min 2m mean | K   | °C    | -              |
| wind_speed                  | średnia miesięczna prędkość wiatru              | wind speed                  | m/s | m/s   | >=0           |
