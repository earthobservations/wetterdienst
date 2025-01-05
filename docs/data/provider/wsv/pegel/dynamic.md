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

| name                    | original name           | description                                       | unit type                | unit   | constraints |
|-------------------------|-------------------------|---------------------------------------------------|--------------------------|--------|-------------|
| chlorid_concentration   | cl                      | average chlorid concentration during time scale   | concentration            | mg/l   | -           |
| clearance_height        | dfh                     | average clearance height during time scale        | length_short             | m      | -           |
| current                 | r                       | average current during time scale                 | magnetic_field_intensity | T      | -           |
| discharge               | q                       | average discharge during time scale               | volume_per_time          | m³/s   | >=0         |
| electric_conductivity   | lf                      | average electric conductivity during time scale   | conductivity             | μS/cm  | -           |
| flow_speed              | va                      | average flow speed during time scale              | speed                    | m/s    | -           |
| groundwater_level       | gru                     | average groundwater level during time scale       | length_medium            | m      | -           |
| humidity                | hl                      | average water level during time scale             | angle                    | °      | >=0,<=100   |
| oxygen_level            | o2                      | average oxygen level during time scale            | concentration            | mg/l   | >=0         |
| ph_value                | ph                      | average pH during time scale                      | dimensionless            | -      | -           |
| precipitation_height    | niederschlag            | average precipitation height during time scale    | precipitation            | mm     | >=0         |
| precipitation_intensity | niederschlagsintensität | average precipitation intensity during time scale | precipitation_intensity  | mm/h   | >=0         |
| temperature_air_mean_2m | lt                      | average air temperature during time scale         | temperature              | °C     | -           |
| temperature_water       | wt                      | average water temperature during time scale       | temperature              | °C     | -           |
| turbidity               | tr                      | average turbidity during time scale               | turbidity                | NTU    | -           |
| stage                   | w                       | average water level during time scale             | length_short             | cm     | >=0         |
| wave_height_max         | maxh                    | max wave height during time scale                 | length_short             | cm     | -           |
| wave_height_sign        | sigh                    | average wave height sign during time scale        | length_short             | cm     | -           |
| wave_period             | tp                      | average wave period during time scale             | wave_period              | 1/100s | >=0         |
| wind_direction          | wr                      | average wind direction during time scale          | angle                    | °      | >=0,<=360   |
| wind_speed              | wg                      | average wind speed during time scale              | speed                    | m/s    | -           |
