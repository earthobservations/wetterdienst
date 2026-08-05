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

| name                            | original name           | description                                       | unit   | constraints |
|---------------------------------|-------------------------|---------------------------------------------------|--------|-------------|
| {term}`chlorid_concentration`   | cl                      | average chlorid concentration during time scale   | mg/l   | -           |
| {term}`clearance_height`        | dfh                     | average clearance height during time scale        | m      | -           |
| {term}`current`                 | r                       | average current during time scale                 | T      | -           |
| {term}`discharge`               | q                       | average discharge during time scale               | m³/s   | >=0         |
| {term}`electric_conductivity`   | lf                      | average electric conductivity during time scale   | μS/cm  | -           |
| {term}`flow_speed`              | va                      | average flow speed during time scale              | m/s    | -           |
| {term}`groundwater_level`       | gru                     | average groundwater level during time scale       | m      | -           |
| {term}`humidity`                | hl                      | average water level during time scale             | °      | >=0,<=100   |
| {term}`oxygen_level`            | o2                      | average oxygen level during time scale            | mg/l   | >=0         |
| {term}`ph_value`                | ph                      | average pH during time scale                      | -      | -           |
| {term}`precipitation_height`    | niederschlag            | average precipitation height during time scale    | mm     | >=0         |
| {term}`precipitation_intensity` | niederschlagsintensität | average precipitation intensity during time scale | mm/h   | >=0         |
| {term}`temperature_air_mean_2m` | lt                      | average air temperature during time scale         | °C     | -           |
| {term}`temperature_water`       | wt                      | average water temperature during time scale       | °C     | -           |
| {term}`turbidity`               | tr                      | average turbidity during time scale               | NTU    | -           |
| {term}`stage`                   | w                       | average water level during time scale             | cm     | >=0         |
| {term}`wave_height_max`         | maxh                    | max wave height during time scale                 | cm     | -           |
| {term}`wave_height_sign`        | sigh                    | average wave height sign during time scale        | cm     | -           |
| {term}`wave_period`             | tp                      | average wave period during time scale             | 1/100s | >=0         |
| {term}`wind_direction`          | wr                      | average wind direction during time scale          | °      | >=0,<=360   |
| {term}`wind_speed`              | wg                      | average wind speed during time scale              | m/s    | -           |
