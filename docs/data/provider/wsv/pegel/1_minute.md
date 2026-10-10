# 1_minute

## metadata

| property      | value                                                        |
|---------------|--------------------------------------------------------------|
| name          | 1_minute                                                     |
| original name | 1_minute                                                     |
| url           | [here](https://www.pegelonline.wsv.de/webservice/ueberblick) |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                         |
| original name | data                                                         |
| description   | Recent data (last 30 days) of German waterways including water level and discharge for most stations but may also include chemical, meteorologic and other types of values ([details](https://www.pegelonline.wsv.de/webservice/ueberblick)) |
| access        | [here](https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json?includeTimeseries=true)                                                                                                                                          |

#### parameters

| name                            | original name           | description                                            | unit  | constraints |
|---------------------------------|-------------------------|--------------------------------------------------------|-------|-------------|
| {term}`stage`                   | W                       | average water level during time scale                  | cm    | >=0         |
| {term}`discharge`               | Q                       | average discharge during time scale                    | m³/s  | >=0         |
| {term}`temperature_water`       | WT                      | average water temperature during time scale            | °C    | -           |
| {term}`electric_conductivity`   | LF                      | average electric conductivity during time scale        | μS/cm | -           |
| {term}`clearance_height`        | DFH                     | average clearance height during time scale             | cm    | -           |
| {term}`temperature_air_2m`      | LT                      | average air temperature during time scale              | °C    | -           |
| {term}`flow_speed`              | VA                      | average flow speed during time scale                   | m/s   | -           |
| {term}`groundwater_level`       | GRU                     | average groundwater level during time scale            | m     | -           |
| {term}`wind_speed`              | WG                      | average wind speed during time scale                   | m/s   | -           |
| {term}`humidity_relative`       | HL                      | average relative humidity of the air during time scale | %     | >=0,<=100   |
| {term}`oxygen_level`            | O2                      | average oxygen level during time scale                 | mg/l  | >=0         |
| {term}`turbidity`               | TR                      | average turbidity during time scale                    | NTU   | -           |
| {term}`flow_direction`          | R                       | direction of the water current                         | °     | >=0,<=360   |
| {term}`wind_direction`          | WR                      | average wind direction during time scale               | °     | >=0,<=360   |
| {term}`precipitation_amount`    | NIEDERSCHLAG            | average precipitation height during time scale         | mm    | >=0         |
| {term}`precipitation_intensity` | NIEDERSCHLAGSINTENSITÄT | average precipitation intensity during time scale      | mm/h  | >=0         |
| {term}`wave_period`             | TP                      | average wave period during time scale                  | s     | >=0         |
| {term}`wave_height_significant` | SIGH                    | average significant wave height during time scale      | cm    | -           |
| {term}`wave_height_max`         | MAXH                    | max wave height during time scale                      | cm    | -           |
| {term}`ph_value`                | PH                      | average pH during time scale                           | -     | -           |
| {term}`chloride_concentration`  | CL                      | average chloride concentration during time scale       | mg/l  | -           |
