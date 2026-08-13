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

| name                                 | original name | description                                              | unit | constraints |
|--------------------------------------|---------------|----------------------------------------------------------|------|-------------|
| {term}`precipitation_height` | rs_01 | Sum of the precipitation height. | mm | >=0 |
| {term}`precipitation_height_droplet` | rth_01 | Precipitation height during the previous minute from the tipping bucket rain gauge. | mm | >=0 |
| {term}`precipitation_height_rocker` | rwh_01 | Precipitation height during the previous minute from the electronic rain gauge with tilting scales. | mm | >=0 |
| {term}`precipitation_index` | rs_ind_01 | Indicator of precipitation; the codes are those of the 10 minutes dataset. | - | ∈ \[0,1,3\] |
| {term}`quality` | qn | Quality flag published by the source for the values in the same dataset. | dimensionless | - |

Codes (precipitation_form):

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |
