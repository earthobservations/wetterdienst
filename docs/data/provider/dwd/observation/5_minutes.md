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

| property         | value                                                                                                                                                      |
|------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name             | precipitation                                                                                                                                              |
| original name    | precipitation                                                                                                                                              |
| description      | missing                                                                                                                                                    |
| description file | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/5_minutes/precipitation/DESCRIPTION_obsgermany-climate-5min-rr_en.pdf) |
| url              | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/5_minutes/precipitation/)                                              |

#### parameters

| name                         | original name | description                                                          | unit             | original unit | constraints           |
|------------------------------|---------------|----------------------------------------------------------------------|------------------|---------------|-----------------------|
| precipitation_height         | rs_05         | precipitation height of last 5min                                    | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`       |
| precipitation_height_droplet | rth_05        | precipitation height of last 5min measured with droplet              | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`       |
| precipitation_height_rocker  | rwh_05        | precipitation height of last 5min measured with rocker               | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`       |
| precipitation_form           | rs_ind_05     | precipitation form of last 5min, codes taken from 10_minutes dataset | :math:`-`        | :math:`-`     | :math:`\in [0, 1, 3]` |

Codes (precipitation_form):

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |
