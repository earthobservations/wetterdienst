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
| {term}`quality` | qn | Quality flag published by the source for the values in the same dataset. | -             | - |
| {term}`precipitation_amount` | rs_01 | Sum of the precipitation height. | mm | >=0 |
| {term}`precipitation_amount_droplet` | rth_01 | Value of the precipitation gauge with droplet counter (German sheet: "Niederschlagmesser mit Tröpfchenzähler"; the English sheet says "tipping bucket rain gauge"). | mm | >=0 |
| {term}`precipitation_amount_rocker` | rwh_01 | Value of the electronic precipitation gauge with tilting scales (German sheet: "elektronischer Niederschlagmesser mit Kippwaage"). | mm | >=0 |
| {term}`precipitation_index` | rs_ind_01 | Indicator of precipitation; if QN = 1 then: 0 = no precipitation, permanent sensor installed; 1 = precipitation, permanent sensor installed; 2 = no precipitation, heating in operation, permanent sensor installed; 3 = precipitation, heating in operation, permanent sensor installed; if QN > 1 then: 0 = no precipitation; 1 = precipitation. | - | ∈ \[0,1,3\] |

Codes (precipitation_form):

| code | meaning                                                   |
|------|-----------------------------------------------------------|
| 0    | no precipitation                                          |
| 1    | precipitation has fallen                                  |
| 3    | precipitation has fallen and heating of instrument was on |
