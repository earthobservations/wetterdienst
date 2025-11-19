# monthly

## metadata

| property      | value                                                                                    |
|---------------|------------------------------------------------------------------------------------------|
| name          | monthly                                                                                  |
| original name | monthly                                                                                  |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/)   |

## datasets

### heating_degreedays

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                                    |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | heating_degreedays                                                                                                                                                                                                                                                                                                       |
| original name | heating_degreedays                                                                                                                                                                                                                                                                                                       |
| description   | Data on degree days, comparing the monthly temperatures to the reference temperature of 20 degree Celsius ([details](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/heating_degreedays/hdd_3807/recent/DESCRIPTION_derivgermany_techn_monthly_heating_degreedays_hdd_3807_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/heating_degreedays/)                                                                                                                                                                                                                |

#### parameters

| name                                | original name         | description                                                                | unit type     | unit           | constraints   |
|-------------------------------------|-----------------------|----------------------------------------------------------------------------|---------------|----------------|---------------|
| amount_days_per_month               | Anzahl Tage           | number of available values of mean daily air temperatures per month        | dimensionless | dimensionless  | >=0           |
| heating_degreedays                  | Monatsgradtage        | sum of degree days over a month                                            | degree_day    | °Cd            | >=0           |
| amount_heating_degreedays_per_month | Anzahl Heiztage       | number of days with daily mean air temperature less than 15 degree Celsius | dimensionless | dimensionless  | >=0           |

### cooling_degreehours

#### metadata
To distinguish different base temperatures, there exist three datasets with the same parameters.

| property      | value                                                                                                                                                                                                                                                                                                                             |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | cooling_degreehours_13, cooling_degreehours_16, cooling_degreehours_18                                                                                                                                                                                                                                                            |
| original name | cooling_degreehours_13, cooling_degreehours_16, cooling_degreehours_18                                                                                                                                                                                                                                                            |
| description   | Data on cooling degree hours, comparing the hourly temperatures to different reference temperatures of 13, 16 and 18 degree Celsius ([details](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/cooling_degreehours/DESCRIPTION_derivgermany_techn_monthly_cooling_degreehours_cdh_recent_en.pdf))   |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/cooling_degreehours/)                                                                                                                                                                                                                        |

#### parameters

| name                 | original name           | description                                                                                                 | unit type      | unit          | constraints              |
|----------------------|-------------------------|-------------------------------------------------------------------------------------------------------------|----------------|---------------|--------------------------|
| amount_hours         | Anzahl Stunden          | number of hours per month                                                                                   | dimensionless  | dimensionless | >=0                      |
| amount_cooling_hours | Anzahl Kuehlstunden     | number of hours with positive temperature differences between air temperature and reference temperature     | dimensionless  | dimensionless | >=0                      |
| cooling_degreehours  | Kuehlgradstunden        | accumulated hourly temperature differences between air temperature and reference temperature                | degree_day     | °Cd           | >=0                      |
| cooling_days         | Anzahl Kühltage         | number of days with at least one cooling hour                                                               | dimensionless  | dimensionless | >=0                      |

