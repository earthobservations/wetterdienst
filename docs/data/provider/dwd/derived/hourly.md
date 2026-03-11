# hourly

## metadata

| property      | value                                                                                    |
|---------------|------------------------------------------------------------------------------------------|
| name          | hourly                                                                                  |
| original name | hourly                                                                                  |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/) |

## datasets

### radiation_global

#### metadata

| property      | value                                                                                                                                                                                                               |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | radiation_global                                                                                                                                                                                                    |
| original name | radiation_global                                                                                                                                                                                                    |
| description   | Hourly global radiation data with quality flags and uncertainty estimates ([details](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/DESCRIPTION_derived_germany-climate-hourly-duett_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/)                                                                                                                       |

#### parameters

| name                          | original name   | description                              | unit type      | unit                        | constraints |
|-------------------------------|-----------------|------------------------------------------|-----------------|------------------------------|-----------|
| quality                       | qn_952          | quality flag                             | dimensionless   | dimensionless              | -          |
| radiation_global              | fg_duett        | global radiation                         | energy_per_area | joule_per_square_centimeter | >=0       |
| radiation_global_uncertainty  | fg_un_duett     | uncertainty of global radiation          | energy_per_area | joule_per_square_centimeter | >=0       |

### sunshine_duration

#### metadata

| property      | value                                                                                                                                                                                                               |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | sunshine_duration                                                                                                                                                                                                   |
| original name | sunshine_duration                                                                                                                                                                                                   |
| description   | Hourly sunshine duration data with quality flags and uncertainty estimates ([details](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/DESCRIPTION_derived_germany-climate-hourly-duett_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/)                                                                                                                       |

#### parameters

| name                            | original name   | description                               | unit type      | unit          | constraints |
|---------------------------------|-----------------|-------------------------------------------|-----------------|---------------|-----------|
| quality                         | qn_952          | quality flag                              | dimensionless   | dimensionless | -          |
| sunshine_duration               | sd_duett        | sunshine duration                         | time            | minute        | >=0       |
| sunshine_duration_uncertainty   | fg_un_duett     | uncertainty of sunshine duration          | time            | minute        | >=0       |
