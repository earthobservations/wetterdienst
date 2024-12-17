# dynamic

## metadata

| property      | value                                                                 |
|---------------|-----------------------------------------------------------------------|
| name          | dynamic                                                               |
| original name | dynamic                                                               |
| url           | [here](https://www.pegelonline.wsv.de/webservice/ueberblick)          |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                                                                                                                                                         |
| original name | data                                                                                                                                                                                                                                         |
| description   | Recent data (last 30 days) of German waterways including water level and discharge for most stations but may also include chemical, meteorologic and other types of values ([details](https://www.pegelonline.wsv.de/webservice/ueberblick)) |
| access        | [here](https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json?includeTimeseries=true)                                                                                                                                          |

#### parameters

| name                    | original name           | description                                       | unit   | original unit | constraints |
|-------------------------|-------------------------|---------------------------------------------------|--------|---------------|-------------|
| chlorid_concentration   | cl                      | average chlorid concentration during time scale   | mg/l   | mg/l          | -           |
| clearance_height        | dfh                     | average clearance height during time scale        | m      | m             | -           |
| current                 | r                       | average current during time scale                 | T      | T             | -           |
| discharge               | q                       | average discharge during time scale               | m³/s   | m³/s          | >=0         |
| electric_conductivity   | lf                      | average electric conductivity during time scale   | S/m    | μS/cm         | -           |
| flow_speed              | va                      | average flow speed during time scale              | m/s    | m/s           | -           |
| groundwater_level       | gru                     | average flow speed during time scale              | m      | m             | -           |
| humidity                | hl                      | average water level during time scale             | °      | °             | >=0,<=100   |
| oxygen_level            | o2                      | average oxygen level during time scale            | mg/l   | mg/l          | >=0         |
| ph_value                | ph                      | average pH during time scale                      | -      | -             | -           |
| precipitation_height    | niederschlag            | average precipitation height during time scale    | kg/m²  | mm            | >=0         |
| precipitation_intensity | niederschlagsintensität | average precipitation intensity during time scale | mm/h   | mm/h          | >=0         |
| temperature_air_mean_2m | lt                      | average air temperature during time scale         | K      | °C            | -           |
| temperature_water       | wt                      | average water temperature during time scale       | K      | °C            | -           |
| turbidity               | tr                      | average turbidity during time scale               | NTU    | NTU           | -           |
| stage                   | w                       | average water level during time scale             | cm     | cm            | >=0         |
| wave_height_max         | maxh                    | max wave height during time scale                 | cm     | cm            | -           |
| wave_height_sign        | sigh                    | average wave height sign during time scale        | cm     | cm            | -           |
| wave_period             | tp                      | average wave period during time scale             | 1/100s | 1/100s        | >=0         |
| wind_direction          | wr                      | average wind direction during time scale          | °      | °             | >=0,<=360   |
| wind_speed              | wg                      | average wind speed during time scale              | m/s    | m/s           | -           |
