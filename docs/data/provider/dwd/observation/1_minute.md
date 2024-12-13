# 1_minute

## Metadata

| property      | value                                                                                          |
|---------------|------------------------------------------------------------------------------------------------|
| original name | 1_minute                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/) |

## Datasets

### Precipitation

#### Metadata

| property         | value                                                                                                        |
|------------------|--------------------------------------------------------------------------------------------------------------|
| name             | precipitation                                                                                                |
| original name    | precipitation                                                                                                |
| description      | missing                                                                                                      |
| description file | [here](https://opendata.dwd.de/climate_environment/CDC/help/Abkuerzung_neu_Spaltenname_CDC_20171128.xlsx)    |
| url              | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/precipitation/) |


#### Parameters

| name                         | original name | description                                              | unit             | original unit | constraints           |
|------------------------------|---------------|----------------------------------------------------------|------------------|---------------|-----------------------|
| precipitation_height         | rs_01         | precipitation height of last 1min                        | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`       |
| precipitation_height_droplet | rth_01        | precipitation height of last 1min measured with droplet  | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`       |
| precipitation_height_rocker  | rwh_01        | precipitation height of last 1min measured with rocker   | :math:`kg / m^2` | :math:`mm`    | :math:`\geq{0}`       |
| precipitation_form           | rs_ind_01     | precipitation index, codes taken from 10_minutes dataset | :math:`-`        | :math:`-`     | :math:`\in [0, 1, 3]` |

Codes for precipitation form:

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |