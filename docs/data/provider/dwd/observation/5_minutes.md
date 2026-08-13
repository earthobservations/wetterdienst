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

| name                                 | original name | description                                                          | unit | constraints |
|--------------------------------------|---------------|----------------------------------------------------------------------|------|-------------|
| {term}`precipitation_height` | rs_05 | Sum of the precipitation height of the previous 5 minutes. | mm | >=0 |
| {term}`precipitation_height_droplet` | rth_05 | Precipitation height of last 5min measured with droplet. | mm | >=0 |
| {term}`precipitation_height_rocker` | rwh_05 | Precipitation height of last 5min measured with rocker. | mm | >=0 |
| {term}`precipitation_index` | rs_ind_05 | Indicator of precipitation; if QN = 1 then: 0 = no precipitation, permanent sensor installed; 1 = precipitation, permanent sensor installed; 2 = no precipitation, heating in operation, permanent sensor installed; 3 = precipitation, heating in operation, permanent sensor installed; if QN > 1 then: 0 = no precipitation; 1 = precipitation. | - | ∈ \[0,1,3\] |
| {term}`quality` | qn_5min | Quality flag published by the source for the values in the same dataset. | dimensionless | - |

Codes (precipitation_form):

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |
