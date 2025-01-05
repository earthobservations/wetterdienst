# 5_minutes

## metadata

| property      | value                                                                                           |
|---------------|-------------------------------------------------------------------------------------------------|
| name          | 5_minutes                                                                                       |
| original name | 5_minutes                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/5_minutes/) |

## datasets

### precipitation

#### metadata

| property      | value                                                                                                                                                                                                                      |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                                                                                                                              |
| original name | precipitation                                                                                                                                                                                                              |
| description   | 5-minute station observations of precipitation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/5_minutes/precipitation/DESCRIPTION_obsgermany-climate-5min-rr_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/5_minutes/precipitation/)                                                                                                              |

#### parameters

| name                         | original name | description                                                          | unit type     | unit          | constraints |
|------------------------------|---------------|----------------------------------------------------------------------|---------------|---------------|-------------|
| precipitation_height         | rs_05         | precipitation height of last 5min                                    | precipitation | mm            | >=0         |
| precipitation_height_droplet | rth_05        | precipitation height of last 5min measured with droplet              | precipitation | mm            | >=0         |
| precipitation_height_rocker  | rwh_05        | precipitation height of last 5min measured with rocker               | precipitation | mm            | >=0         |
| precipitation_form           | rs_ind_05     | precipitation form of last 5min, codes taken from 10_minutes dataset | dimensionless | -             | ∈ \[0,1,3\] |

Codes (precipitation_form):

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |
