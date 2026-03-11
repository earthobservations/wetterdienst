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

| name                                             | original name | description                                            | unit type     | unit | constraints |
| ------------------------------------------------ | ------------- | ------------------------------------------------------ | ------------- | ---- | ----------- |
| temperature_soil_mean_0_05m                      | ts05          | mean soil temperature at 0.05m depth                   | temperature   | °C   | -           |
| temperature_soil_mean_0_1m                       | ts10          | mean soil temperature at 0.1m depth                    | temperature   | °C   | -           |
| temperature_soil_mean_0_2m                       | ts20          | mean soil temperature at 0.2m depth                    | temperature   | °C   | -           |
| temperature_soil_mean_0_5m                       | ts50          | mean soil temperature at 0.5m depth                    | temperature   | °C   | -           |
| temperature_soil_mean_1m                         | ts100         | mean soil temperature at 1m depth                      | temperature   | °C   | -           |
| temperature_soil_mean_loamysand_0_05m            | tsls05        | mean soil temperature for loamy sand at 0.05m depth    | temperature   | °C   | -           |
| temperature_soil_mean_loamysilt_0_05m            | tssl05        | mean soil temperature for loamy silt at 0.05m depth    | temperature   | °C   | -           |
| frozen_ground_layer_thickness                    | zfumi         | frozen ground layer thickness                          | length_short  | cm   | >=0         |
| thawing_thickness_plantstock                     | ztkmi         | thawing thickness under vegetation                     | length_short  | cm   | >=0         |
| thawing_thickness_bare                           | ztumi         | thawing thickness under bare soil                      | length_short  | cm   | >=0         |
| soil_moisture_gras_loamysilt_00cm_10cm           | bfgl01_ag     | soil moisture for meadow on loamy silt 0-10cm          | fraction      | %    | 0-100       |
| soil_moisture_gras_loamysilt_10cm_20cm           | bfgl02_ag     | soil moisture for meadow on loamy silt 10-20cm         | fraction      | %    | 0-100       |
| soil_moisture_gras_loamysilt_20cm_30cm           | bfgl03_ag     | soil moisture for meadow on loamy silt 20-30cm         | fraction      | %    | 0-100       |
| soil_moisture_gras_loamysilt_30cm_40cm           | bfgl04_ag     | soil moisture for meadow on loamy silt 30-40cm         | fraction      | %    | 0-100       |
| soil_moisture_gras_loamysilt_40cm_50cm           | bfgl05_ag     | soil moisture for meadow on loamy silt 40-50cm         | fraction      | %    | 0-100       |
| soil_moisture_gras_loamysilt_50cm_60cm           | bfgl06_ag     | soil moisture for meadow on loamy silt 50-60cm         | fraction      | %    | 0-100       |
| soil_moisture_gras_sand_00cm_60cm                | bfgs_ag       | soil moisture for meadow on sand 0-60cm                | fraction      | %    | 0-100       |
| soil_moisture_gras_loamysilt_00cm_60cm           | bfgl_ag       | soil moisture for meadow on loamy silt 0-60cm          | fraction      | %    | 0-100       |
| soil_moisture_winterwheat_sand_00cm_60cm         | bfws_ag       | soil moisture for winter wheat on sand 0-60cm          | fraction      | %    | 0-100       |
| soil_moisture_winterwheat_loamysilt_00cm_60cm    | bfwl_ag       | soil moisture for winter wheat on loamy silt 0-60cm    | fraction      | %    | 0-100       |
| soil_moisture_corn_sand_00cm_60cm                | bfms_ag       | soil moisture for corn on sand 0-60cm                  | fraction      | %    | 0-100       |
| soil_moisture_corn_loamysilt_00cm_60cm           | bfml_ag       | soil moisture for corn on loamy silt 0-60cm            | fraction      | %    | 0-100       |
| evapotranspiration_potential_gras_fao_last_24h   | vpgfao        | potential evapotranspiration for meadow (FAO method)   | precipitation | mm   | >=0         |
| evapotranspiration_potential_gras_haude_last_24h | vpgh          | potential evapotranspiration for meadow (Haude method) | precipitation | mm   | >=0         |
| evaporation_height_gras_sand                     | vrgs_ag       | evaporation height for meadow on sand                  | precipitation | mm   | >=0         |
| evaporation_height_gras_loamysilt                | vrgl_ag       | evaporation height for meadow on loamy silt            | precipitation | mm   | >=0         |
| evaporation_height_winterwheat_sand              | vrws_ag       | evaporation height for winter wheat on sand            | precipitation | mm   | >=0         |
| evaporation_height_winterwheat_loamysilt         | vrwl_ag       | evaporation height for winter wheat on loamy silt      | precipitation | mm   | >=0         |
| evaporation_height_corn_sand                     | vrms_ag       | evaporation height for corn on sand                    | precipitation | mm   | >=0         |
| evaporation_height_corn_loamysilt                | vrml_ag       | evaporation height for corn on loamy silt              | precipitation | mm   | >=0         |
