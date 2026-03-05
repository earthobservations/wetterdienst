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

| name                      | original name   | description                                                                | unit type     | unit          | constraints |
| ------------------------- | --------------- | -------------------------------------------------------------------------- | ------------- | ------------- | ----------- |
| number_of_days_per_month  | Anzahl Tage     | number of available values of mean daily air temperatures per month        | dimensionless | dimensionless | >=0         |
| heating_degree_day        | Monatsgradtage  | sum of degree days over a month                                            | degree_day    | °Cd           | >=0         |
| count_days_heating_degree | Anzahl Heiztage | number of days with daily mean air temperature less than 15 degree Celsius | dimensionless | dimensionless | >=0         |

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

| name                       | original name       | description                                                                                             | unit type     | unit          | constraints |
| -------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------- | ------------- | ------------- | ----------- |
| number_of_hours_per_month  | Anzahl Stunden      | number of hours per month                                                                               | dimensionless | dimensionless | >=0         |
| count_hours_cooling_degree | Anzahl Kuehlstunden | number of hours with positive temperature differences between air temperature and reference temperature | dimensionless | dimensionless | >=0         |
| cooling_degree_hour        | Kuehlgradstunden    | accumulated hourly temperature differences between air temperature and reference temperature            | degree_day    | °Cd           | >=0         |
| count_days_cooling_degree  | Anzahl Kühltage     | number of days with at least one cooling hour                                                           | dimensionless | dimensionless | >=0         |

### climate_correction_factor

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                                    |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | climate_correction_factor                                                                                                                                                                                                                                                                                                |
| original name | climate_correction_factor                                                                                                                                                                                                                                                                                                |
| description   | Data on climate correction factors, comparing the degree days between a postal code and a reference station ([details](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/climate_correction_factor/recent/DESCRIPTION_derivgermany_techn_monthly_climate_correction_factor_recent_en.pdf))   |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/climate_correction_factor/)                                                                                                                                                                                                         |

#### parameters

| name                      | original name       | description                                                                    | unit type      | unit          | constraints              |
|---------------------------|---------------------|--------------------------------------------------------------------------------|----------------|---------------|--------------------------|
| climate_correction_factor | KF                  | quotient of yearly degree days of reference station in Potsdam and postal code | dimensionless  | dimensionless | >=0                      |

### soil

#### metadata

| property      | value                                                                                                                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | soil                                                                                                                                                                                                    |
| original name | soil                                                                                                                                                                                                    |
| description   | Monthly aggregated soil data including temperature at various depths, soil moisture, and evapotranspiration estimates                                                                                   |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/monthly/)                                                                                                                   |

#### parameters

| name                                              | original name           | description                                                                           | unit type      | unit            | constraints |
|---------------------------------------------------|-------------------------|---------------------------------------------------------------------------------------|-----------------|-----------------|-----------|
| temperature_soil_mean_0_05m                       | mittel von ts05         | mean soil temperature at 0.05m depth                                                 | temperature    | °C              | -          |
| temperature_soil_mean_0_1m                        | mittel von ts10         | mean soil temperature at 0.1m depth                                                  | temperature    | °C              | -          |
| temperature_soil_mean_0_2m                        | mittel von ts20         | mean soil temperature at 0.2m depth                                                  | temperature    | °C              | -          |
| temperature_soil_mean_0_5m                        | mittel von ts50         | mean soil temperature at 0.5m depth                                                  | temperature    | °C              | -          |
| temperature_soil_mean_1m                          | mittel von ts100        | mean soil temperature at 1m depth                                                    | temperature    | °C              | -          |
| temperature_soil_mean_loamysand_0_05m             | mittel von tsls05       | mean soil temperature for loamy sand at 0.05m depth                                  | temperature    | °C              | -          |
| temperature_soil_mean_loamysilt_0_05m             | mittel von tssl05       | mean soil temperature for loamy silt at 0.05m depth                                  | temperature    | °C              | -          |
| frozen_ground_layer_thickness_max_month           | maximum von zfumi       | maximum frozen ground layer thickness in the month                                    | length_short   | cm              | >=0       |
| thawing_thickness_plantstock_max_month            | maximum von ztkmi       | maximum thawing thickness under vegetation in the month                               | length_short   | cm              | >=0       |
| thawing_thickness_bare_max_month                  | maximum von ztumi       | maximum thawing thickness under bare soil in the month                                | length_short   | cm              | >=0       |
| soil_moisture_gras_loamysilt_00cm_10cm            | mittel von bfgl01_ag    | mean soil moisture for meadow on loamy silt 0-10cm                                    | fraction       | %               | 0-100     |
| soil_moisture_gras_loamysilt_10cm_20cm            | mittel von bfgl02_ag    | mean soil moisture for meadow on loamy silt 10-20cm                                   | fraction       | %               | 0-100     |
| soil_moisture_gras_loamysilt_20cm_30cm            | mittel von bfgl03_ag    | mean soil moisture for meadow on loamy silt 20-30cm                                   | fraction       | %               | 0-100     |
| soil_moisture_gras_loamysilt_30cm_40cm            | mittel von bfgl04_ag    | mean soil moisture for meadow on loamy silt 30-40cm                                   | fraction       | %               | 0-100     |
| soil_moisture_gras_loamysilt_40cm_50cm            | mittel von bfgl05_ag    | mean soil moisture for meadow on loamy silt 40-50cm                                   | fraction       | %               | 0-100     |
| soil_moisture_gras_loamysilt_50cm_60cm            | mittel von bfgl06_ag    | mean soil moisture for meadow on loamy silt 50-60cm                                   | fraction       | %               | 0-100     |
| soil_moisture_gras_sand_00cm_60cm                 | mittel von bfgs_ag      | mean soil moisture for meadow on sand 0-60cm                                          | fraction       | %               | 0-100     |
| soil_moisture_gras_loamysilt_00cm_60cm            | mittel von bfgl_ag      | mean soil moisture for meadow on loamy silt 0-60cm                                    | fraction       | %               | 0-100     |
| soil_moisture_winterwheat_sand_00cm_60cm          | mittel von bfws_ag      | mean soil moisture for winter wheat on sand 0-60cm                                    | fraction       | %               | 0-100     |
| soil_moisture_winterwheat_loamysilt_00cm_60cm     | mittel von bfwl_ag      | mean soil moisture for winter wheat on loamy silt 0-60cm                              | fraction       | %               | 0-100     |
| soil_moisture_corn_sand_00cm_60cm                 | mittel von bfms_ag      | mean soil moisture for corn on sand 0-60cm                                            | fraction       | %               | 0-100     |
| soil_moisture_corn_loamysilt_00cm_60cm            | mittel von bfml_ag      | mean soil moisture for corn on loamy silt 0-60cm                                      | fraction       | %               | 0-100     |
| evapotranspiration_potential_gras_fao_last_24h    | summe von vpgfao        | sum of potential evapotranspiration for meadow (FAO method)                           | precipitation  | mm              | >=0       |
| evapotranspiration_potential_gras_haude_last_24h  | summe von vpgh          | sum of potential evapotranspiration for meadow (Haude method)                         | precipitation  | mm              | >=0       |
| evaporation_height_gras_sand                      | summe von vrgs_ag       | sum of evaporation height for meadow on sand                                          | precipitation  | mm              | >=0       |
| evaporation_height_gras_loamysilt                 | summe von vrgl_ag       | sum of evaporation height for meadow on loamy silt                                    | precipitation  | mm              | >=0       |
| evaporation_height_winterwheat_sand               | summe von vrws_ag       | sum of evaporation height for winter wheat on sand                                    | precipitation  | mm              | >=0       |
| evaporation_height_winterwheat_loamysilt          | summe von vrwl_ag       | sum of evaporation height for winter wheat on loamy silt                              | precipitation  | mm              | >=0       |
| evaporation_height_corn_sand                      | summe von vrms_ag       | sum of evaporation height for corn on sand                                            | precipitation  | mm              | >=0       |
| evaporation_height_corn_loamysilt                 | summe von vrml_ag       | sum of evaporation height for corn on loamy silt                                      | precipitation  | mm              | >=0       |

