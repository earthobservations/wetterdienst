# 1_minute

## metadata

| property      | value                                                                                          |
|---------------|------------------------------------------------------------------------------------------------|
| name          | 1_minute                                                                                       |
| original name | 1_minute                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/) |

## datasets

### precipitation

#### metadata

| property      | value                                                                                                                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                                                                                                                             |
| original name | precipitation                                                                                                                                                                                                             |
| description   | 1-minute station observations of precipitation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/precipitation/DESCRIPTION_obsgermany-climate-1min-rr_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/precipitation/)                                                                                                              |

#### parameters

| name                         | original name | description                                              | unit type     | unit | constraints |
|------------------------------|---------------|----------------------------------------------------------|---------------|------|-------------|
| precipitation_height         | rs_01         | precipitation height of last 1min                        | precipitation | mm   | >=0         |
| precipitation_height_droplet | rth_01        | precipitation height of last 1min measured with droplet  | precipitation | mm   | >=0         |
| precipitation_height_rocker  | rwh_01        | precipitation height of last 1min measured with rocker   | precipitation | mm   | >=0         |
| precipitation_form           | rs_ind_01     | precipitation index, codes taken from 10_minutes dataset | dimensionless | -    | ∈ \[0,1,3\] |

Codes (precipitation_form):

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |
