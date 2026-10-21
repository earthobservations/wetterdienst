# daily

## metadata

| property      | value                                                                               |
| ------------- | ----------------------------------------------------------------------------------- |
| name          | daily                                                                               |
| original name | daily                                                                               |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/daily/) |

## datasets

### soil

#### metadata

| property      | value                                                                                                    |
| ------------- | -------------------------------------------------------------------------------------------------------- |
| name          | soil                                                                                                     |
| original name | soil                                                                                                     |
| description   | Daily soil data including temperature at various depths, soil moisture, and evapotranspiration estimates |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/daily/)                      |

#### parameters

| name                                                      | original name | description                                            | unit | constraints |
|-----------------------------------------------------------|---------------|--------------------------------------------------------|------|-------------|
| {term}`temperature_soil_mean_0_05m`                       | ts05          | Mean soil temperature of a typical bare soil at 5 cm depth, calculated with the AMBETI model from observed weather, not measured. | °C   | -           |
| {term}`temperature_soil_mean_0_1m`                        | ts10          | Mean soil temperature of a typical bare soil at 10 cm depth, calculated with the AMBETI model from observed weather, not measured. | °C   | -           |
| {term}`temperature_soil_mean_0_2m`                        | ts20          | Mean soil temperature of a typical bare soil at 20 cm depth, calculated with the AMBETI model from observed weather, not measured. | °C   | -           |
| {term}`temperature_soil_mean_0_5m`                        | ts50          | Mean soil temperature of a typical bare soil at 50 cm depth, calculated with the AMBETI model from observed weather, not measured. | °C   | -           |
| {term}`temperature_soil_mean_1m`                          | ts100         | Mean soil temperature of a typical bare soil at 1 m depth, calculated with the AMBETI model from observed weather, not measured. | °C   | -           |
| {term}`temperature_soil_mean_loamy_sand_0_05m`            | tsls05        | Mean soil temperature at 5 cm depth in unvegetated loamy sand (BEKLIMA), calculated with the AMBETI model, not measured. | °C   | -           |
| {term}`temperature_soil_mean_loamy_silt_0_05m`            | tssl05        | Mean soil temperature at 5 cm depth in unvegetated loamy silt (BEKLIMA), calculated with the AMBETI model, not measured. | °C   | -           |
| {term}`frozen_ground_layer_thickness`                     | zfumi         | Frost penetration depth at midday on unvegetated ground, in cm (AMBETI model). | cm   | >=0         |
| {term}`thawing_thickness_plant_cover`                     | ztkmi         | Thawing layer at midday under vegetation (the sheet: unter Bestand; BEKLIMA), in cm. | cm   | >=0         |
| {term}`thawing_thickness_bare_ground`                     | ztumi         | Thawing layer at midday under unvegetated ground (BEKLIMA), in cm. | cm   | >=0         |
| {term}`soil_moisture_grass_loamy_silt_00cm_10cm`          | bfgl01_ag     | Soil moisture under grass on loamy silt at 0 to 10 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_grass_loamy_silt_10cm_20cm`          | bfgl02_ag     | Soil moisture under grass on loamy silt at 10 to 20 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_grass_loamy_silt_20cm_30cm`          | bfgl03_ag     | Soil moisture under grass on loamy silt at 20 to 30 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_grass_loamy_silt_30cm_40cm`          | bfgl04_ag     | Soil moisture under grass on loamy silt at 30 to 40 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_grass_loamy_silt_40cm_50cm`          | bfgl05_ag     | Soil moisture under grass on loamy silt at 40 to 50 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_grass_loamy_silt_50cm_60cm`          | bfgl06_ag     | Soil moisture under grass on loamy silt at 50 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_grass_sand_00cm_60cm`                | bfgs_ag       | Soil moisture under grass on sand at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_grass_loamy_silt_00cm_60cm`          | bfgl_ag       | Soil moisture under grass on loamy silt at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_winter_wheat_sand_00cm_60cm`         | bfws_ag       | Soil moisture under winter cereals on sand at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_winter_wheat_loamy_silt_00cm_60cm`   | bfwl_ag       | Soil moisture under winter cereals on loamy silt at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_corn_sand_00cm_60cm`                 | bfms_ag       | Soil moisture under maize on sand at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`soil_moisture_corn_loamy_silt_00cm_60cm`           | bfml_ag       | Soil moisture under maize on loamy silt at 0 to 60 cm depth, in % nFK (percent of the usable field capacity), calculated with the AMBAV model, not measured. | %    | >=0,<=100   |
| {term}`evapotranspiration_potential_grass_fao`            | vpgfao        | Potential evapotranspiration over grass (FAO method), in mm, a daily sum (AMBAV model). DWD prefers it to Haude's method because it takes many more influencing factors into account. | mm   | >=0         |
| {term}`evapotranspiration_potential_grass_haude`          | vpgh          | Potential evapotranspiration over grass (Haude method), in mm, a daily sum (AMBAV model). | mm   | >=0         |
| {term}`evaporation_amount_grass_sand`                     | vrgs_ag       | Real (actual) evaporation over grass on sand, in mm, a daily sum calculated with the AMBAV model. | mm   | >=0         |
| {term}`evaporation_amount_grass_loamy_silt`               | vrgl_ag       | Real (actual) evaporation over grass on loamy silt, in mm, a daily sum calculated with the AMBAV model. | mm   | >=0         |
| {term}`evaporation_amount_winter_wheat_sand`              | vrws_ag       | Real (actual) evaporation over winter cereals on sand, in mm, a daily sum calculated with the AMBAV model. | mm   | >=0         |
| {term}`evaporation_amount_winter_wheat_loamy_silt`        | vrwl_ag       | Real (actual) evaporation over winter cereals on loamy silt, in mm, a daily sum calculated with the AMBAV model. | mm   | >=0         |
| {term}`evaporation_amount_corn_sand`                      | vrms_ag       | Real (actual) evaporation over maize on sand, in mm, a daily sum calculated with the AMBAV model. | mm   | >=0         |
| {term}`evaporation_amount_corn_loamy_silt`                | vrml_ag       | Real (actual) evaporation over maize on loamy silt, in mm, a daily sum calculated with the AMBAV model. | mm   | >=0         |
