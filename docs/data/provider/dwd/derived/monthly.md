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

| name                              | original name   | description                                                                | unit | constraints |
|-----------------------------------|-----------------|----------------------------------------------------------------------------|------|-------------|
| {term}`count_days_in_month`       | Anzahl Tage     | number of available values of mean daily air temperatures per month        | -    | >=0         |
| {term}`heating_degree_day`        | Monatsgradtage  | Degree days of the month (VDI 3807 part 1), in K*day: the sum, over the days with a daily mean air temperature below 15 degree Celsius, of 20 degree Celsius minus the daily mean (20 degree Celsius is the mean room temperature the file header states). Only given where every daily value of the month is available. | °Cd  | >=0         |
| {term}`count_days_heating_degree` | Anzahl Heiztage | number of days with daily mean air temperature less than 15 degree Celsius | -    | >=0         |

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

| name                               | original name       | description                                                                                             | unit | constraints |
|------------------------------------|---------------------|---------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`count_hours_in_month`       | Anzahl Stunden      | number of hours per month                                                                               | -    | >=0         |
| {term}`count_hours_cooling_degree` | Anzahl Kuehlstunden | Number of hours of the month with a positive difference between the hourly air temperature and the reference temperature of the dataset (13, 16 or 18 degree Celsius). | -    | >=0         |
| {term}`cooling_degree_hour`        | Kuehlgradstunden    | Cooling degree hours: the sum over the hours of the month of the hourly air temperature minus the reference temperature of the dataset (13, 16 or 18 degree Celsius), for the hours above it, in K*h. The sheet gives the unit as Kelvin * day, which the values rule out (for example 2,562.3 for 545 cooling hours at the reference of 13 degree Celsius, Grossenkneten, September 2026). | °Ch  | >=0         |
| {term}`count_days_cooling_degree`  | Kuehltage           | Number of days with at least one cooling hour.                                                          | -    | >=0         |

### climate_correction_factor

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                                    |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | climate_correction_factor                                                                                                                                                                                                                                                                                                |
| original name | climate_correction_factor                                                                                                                                                                                                                                                                                                |
| description   | Data on climate correction factors, comparing the degree days between a postal code and a reference station ([details](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/climate_correction_factor/recent/DESCRIPTION_derivgermany_techn_monthly_climate_correction_factor_recent_en.pdf))   |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/climate_correction_factor/)                                                                                                                                                                                                         |

#### parameters

| name                              | original name | description                                                                    | unit          | constraints |
|-----------------------------------|---------------|--------------------------------------------------------------------------------|---------------|-------------|
| {term}`climate_correction_factor` | KF            | Climate factor (KF) of a delivery postal code for the weather adjustment of energy consumption, relative to the reference location Potsdam (the test reference years TRY 2011), for the 12 months starting at the timestamp: KF = G(TRY, P) / G, the mean annual degree days of the reference station Potsdam computed with its test reference years (3666.8) over the annual degree days of the postal code in those 12 months (DWD's climate-factor page; the sheet states no formula). | -             | >=0         |

### soil

#### metadata

| property      | value                                                                                                                                                                                                   |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | soil                                                                                                                                                                                                    |
| original name | soil                                                                                                                                                                                                    |
| description   | Monthly aggregated soil data including temperature at various depths, soil moisture, and evapotranspiration estimates                                                                                   |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/monthly/)                                                                                                                   |

#### parameters

| name                                                         | original name        | description                                                   | unit | constraints |
|--------------------------------------------------------------|----------------------|---------------------------------------------------------------|------|-------------|
| {term}`temperature_soil_mean_0_05m`                          | mittel von ts05      | Monthly mean of the daily mean soil temperature of a typical bare soil at 5 cm depth (AMBETI model, not measured). | °C   | -           |
| {term}`temperature_soil_mean_0_1m`                           | mittel von ts10      | Monthly mean of the daily mean soil temperature of a typical bare soil at 10 cm depth (AMBETI model, not measured). | °C   | -           |
| {term}`temperature_soil_mean_0_2m`                           | mittel von ts20      | Monthly mean of the daily mean soil temperature of a typical bare soil at 20 cm depth (AMBETI model, not measured). | °C   | -           |
| {term}`temperature_soil_mean_0_5m`                           | mittel von ts50      | Monthly mean of the daily mean soil temperature of a typical bare soil at 50 cm depth (AMBETI model, not measured). | °C   | -           |
| {term}`temperature_soil_mean_1m`                             | mittel von ts100     | Monthly mean of the daily mean soil temperature of a typical bare soil at 1 m depth (AMBETI model, not measured). | °C   | -           |
| {term}`temperature_soil_mean_loamy_sand_0_05m`               | mittel von tsls05    | Monthly mean of the daily mean soil temperature at 5 cm depth in unvegetated loamy sand (BEKLIMA, AMBETI model, not measured). | °C   | -           |
| {term}`temperature_soil_mean_loamy_silt_0_05m`               | mittel von tssl05    | Monthly mean of the daily mean soil temperature at 5 cm depth in unvegetated loamy silt (BEKLIMA, AMBETI model, not measured). | °C   | -           |
| {term}`frozen_ground_layer_thickness_max_month`              | maximum von zfumi    | Maximum in the month of the frost penetration depth at midday on unvegetated ground, in cm (AMBETI model). | cm   | >=0         |
| {term}`thawing_thickness_plant_cover_max_month`              | maximum von ztkmi    | Maximum in the month of the thawing layer at midday under vegetation (the sheet: unter Bestand; BEKLIMA), in cm. | cm   | >=0         |
| {term}`thawing_thickness_bare_ground_max_month`              | maximum von ztumi    | Maximum in the month of the thawing layer at midday under unvegetated ground (BEKLIMA), in cm. | cm   | >=0         |
| {term}`soil_moisture_mean_grass_loamy_silt_00cm_10cm`        | mittel von bfgl01_ag | Monthly mean of the daily soil moisture under grass on loamy silt at 0 to 10 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_grass_loamy_silt_10cm_20cm`        | mittel von bfgl02_ag | Monthly mean of the daily soil moisture under grass on loamy silt at 10 to 20 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_grass_loamy_silt_20cm_30cm`        | mittel von bfgl03_ag | Monthly mean of the daily soil moisture under grass on loamy silt at 20 to 30 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_grass_loamy_silt_30cm_40cm`        | mittel von bfgl04_ag | Monthly mean of the daily soil moisture under grass on loamy silt at 30 to 40 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_grass_loamy_silt_40cm_50cm`        | mittel von bfgl05_ag | Monthly mean of the daily soil moisture under grass on loamy silt at 40 to 50 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_grass_loamy_silt_50cm_60cm`        | mittel von bfgl06_ag | Monthly mean of the daily soil moisture under grass on loamy silt at 50 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_grass_sand_00cm_60cm`              | mittel von bfgs_ag   | Monthly mean of the daily soil moisture under grass on sand at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_grass_loamy_silt_00cm_60cm`        | mittel von bfgl_ag   | Monthly mean of the daily soil moisture under grass on loamy silt at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_winter_cereals_sand_00cm_60cm`       | mittel von bfws_ag   | Monthly mean of the daily soil moisture under winter cereals on sand at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_winter_cereals_loamy_silt_00cm_60cm` | mittel von bfwl_ag   | Monthly mean of the daily soil moisture under winter cereals on loamy silt at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_corn_sand_00cm_60cm`               | mittel von bfms_ag   | Monthly mean of the daily soil moisture under maize on sand at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_mean_corn_loamy_silt_00cm_60cm`         | mittel von bfml_ag   | Monthly mean of the daily soil moisture under maize on loamy silt at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`evapotranspiration_potential_grass_fao`               | summe von vpgfao     | Monthly sum of the daily potential evapotranspiration over grass (FAO method), in mm. | mm   | >=0         |
| {term}`evapotranspiration_potential_grass_haude`             | summe von vpgh       | Monthly sum of the daily potential evapotranspiration over grass (Haude method), in mm. | mm   | >=0         |
| {term}`evaporation_amount_grass_sand`                        | summe von vrgs_ag    | Monthly sum of the daily real (actual) evaporation over grass on sand, in mm (AMBAV model). | mm   | >=0         |
| {term}`evaporation_amount_grass_loamy_silt`                  | summe von vrgl_ag    | Monthly sum of the daily real (actual) evaporation over grass on loamy silt, in mm (AMBAV model). | mm   | >=0         |
| {term}`evaporation_amount_winter_cereals_sand`                 | summe von vrws_ag    | Monthly sum of the daily real (actual) evaporation over winter cereals on sand, in mm (AMBAV model). | mm   | >=0         |
| {term}`evaporation_amount_winter_cereals_loamy_silt`           | summe von vrwl_ag    | Monthly sum of the daily real (actual) evaporation over winter cereals on loamy silt, in mm (AMBAV model). | mm   | >=0         |
| {term}`evaporation_amount_corn_sand`                         | summe von vrms_ag    | Monthly sum of the daily real (actual) evaporation over maize on sand, in mm (AMBAV model). | mm   | >=0         |
| {term}`evaporation_amount_corn_loamy_silt`                   | summe von vrml_ag    | Monthly sum of the daily real (actual) evaporation over maize on loamy silt, in mm (AMBAV model). | mm   | >=0         |

