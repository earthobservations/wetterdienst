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

| name                                                     | original name | description                                            | unit | constraints |
|----------------------------------------------------------|---------------|--------------------------------------------------------|------|-------------|
| {term}`temperature_soil_mean_0_05m`                      | ts05          | mean soil temperature at 0.05m depth                   | °C   | -           |
| {term}`temperature_soil_mean_0_1m`                       | ts10          | mean soil temperature at 0.1m depth                    | °C   | -           |
| {term}`temperature_soil_mean_0_2m`                       | ts20          | mean soil temperature at 0.2m depth                    | °C   | -           |
| {term}`temperature_soil_mean_0_5m`                       | ts50          | mean soil temperature at 0.5m depth                    | °C   | -           |
| {term}`temperature_soil_mean_1m`                         | ts100         | mean soil temperature at 1m depth                      | °C   | -           |
| {term}`temperature_soil_mean_loamy_sand_0_05m`            | tsls05        | mean soil temperature for loamy sand at 0.05m depth    | °C   | -           |
| {term}`temperature_soil_mean_loamy_silt_0_05m`            | tssl05        | mean soil temperature for loamy silt at 0.05m depth    | °C   | -           |
| {term}`frozen_ground_layer_thickness`                    | zfumi         | frozen ground layer thickness                          | cm   | >=0         |
| {term}`thawing_thickness_plant_cover`                     | ztkmi         | thawing thickness under vegetation                     | cm   | >=0         |
| {term}`thawing_thickness_bare_ground`                           | ztumi         | thawing thickness under bare soil                      | cm   | >=0         |
| {term}`soil_moisture_grass_loamy_silt_00cm_10cm`           | bfgl01_ag     | soil moisture for meadow on loamy silt 0-10cm          | %    | 0-100       |
| {term}`soil_moisture_grass_loamy_silt_10cm_20cm`           | bfgl02_ag     | soil moisture for meadow on loamy silt 10-20cm         | %    | 0-100       |
| {term}`soil_moisture_grass_loamy_silt_20cm_30cm`           | bfgl03_ag     | soil moisture for meadow on loamy silt 20-30cm         | %    | 0-100       |
| {term}`soil_moisture_grass_loamy_silt_30cm_40cm`           | bfgl04_ag     | soil moisture for meadow on loamy silt 30-40cm         | %    | 0-100       |
| {term}`soil_moisture_grass_loamy_silt_40cm_50cm`           | bfgl05_ag     | soil moisture for meadow on loamy silt 40-50cm         | %    | 0-100       |
| {term}`soil_moisture_grass_loamy_silt_50cm_60cm`           | bfgl06_ag     | soil moisture for meadow on loamy silt 50-60cm         | %    | 0-100       |
| {term}`soil_moisture_grass_sand_00cm_60cm`                | bfgs_ag       | soil moisture for meadow on sand 0-60cm                | %    | 0-100       |
| {term}`soil_moisture_grass_loamy_silt_00cm_60cm`           | bfgl_ag       | soil moisture for meadow on loamy silt 0-60cm          | %    | 0-100       |
| {term}`soil_moisture_winter_wheat_sand_00cm_60cm`         | bfws_ag       | soil moisture for winter wheat on sand 0-60cm          | %    | 0-100       |
| {term}`soil_moisture_winter_wheat_loamy_silt_00cm_60cm`    | bfwl_ag       | soil moisture for winter wheat on loamy silt 0-60cm    | %    | 0-100       |
| {term}`soil_moisture_corn_sand_00cm_60cm`                | bfms_ag       | soil moisture for corn on sand 0-60cm                  | %    | 0-100       |
| {term}`soil_moisture_corn_loamy_silt_00cm_60cm`           | bfml_ag       | soil moisture for corn on loamy silt 0-60cm            | %    | 0-100       |
| {term}`evapotranspiration_potential_grass_fao_last_24h`   | vpgfao        | potential evapotranspiration for meadow (FAO method)   | mm   | >=0         |
| {term}`evapotranspiration_potential_grass_haude_last_24h` | vpgh          | potential evapotranspiration for meadow (Haude method) | mm   | >=0         |
| {term}`evaporation_height_grass_sand`                     | vrgs_ag       | evaporation height for meadow on sand                  | mm   | >=0         |
| {term}`evaporation_height_grass_loamy_silt`                | vrgl_ag       | evaporation height for meadow on loamy silt            | mm   | >=0         |
| {term}`evaporation_height_winter_wheat_sand`              | vrws_ag       | evaporation height for winter wheat on sand            | mm   | >=0         |
| {term}`evaporation_height_winter_wheat_loamy_silt`         | vrwl_ag       | evaporation height for winter wheat on loamy silt      | mm   | >=0         |
| {term}`evaporation_height_corn_sand`                     | vrms_ag       | evaporation height for corn on sand                    | mm   | >=0         |
| {term}`evaporation_height_corn_loamy_silt`                | vrml_ag       | evaporation height for corn on loamy silt              | mm   | >=0         |
