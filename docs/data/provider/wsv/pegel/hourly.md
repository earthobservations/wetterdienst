# hourly

## metadata

| property      | value                                                        |
|---------------|--------------------------------------------------------------|
| name          | hourly                                                       |
| original name | hourly                                                       |
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
| {term}`chlorid_concentration`   | CL                      | average chlorid concentration during time scale        | mg/l  | -           |
| {term}`clearance_height`        | DFH                     | average clearance height during time scale             | cm    | -           |
| {term}`discharge`               | Q                       | average discharge during time scale                    | m³/s  | >=0         |
| {term}`electric_conductivity`   | LF                      | average electric conductivity during time scale        | μS/cm | -           |
| {term}`flow_direction`          | R                       | direction of the water current                         | °     | >=0,<=360   |
| {term}`flow_speed`              | VA                      | average flow speed during time scale                   | m/s   | -           |
| {term}`groundwater_level`       | GRU                     | average groundwater level during time scale            | m     | -           |
| {term}`humidity`                | HL                      | average relative humidity of the air during time scale | %     | >=0,<=100   |
| {term}`oxygen_level`            | O2                      | average oxygen level during time scale                 | mg/l  | >=0         |
| {term}`ph_value`                | PH                      | average pH during time scale                           | -     | -           |
| {term}`precipitation_height`    | NIEDERSCHLAG            | average precipitation height during time scale         | mm    | >=0         |
| {term}`precipitation_intensity` | NIEDERSCHLAGSINTENSITÄT | average precipitation intensity during time scale      | mm/h  | >=0         |
| {term}`stage`                   | W                       | average water level during time scale                  | cm    | >=0         |
| {term}`temperature_air_mean_2m` | LT                      | average air temperature during time scale              | °C    | -           |
| {term}`temperature_water`       | WT                      | average water temperature during time scale            | °C    | -           |
| {term}`turbidity`               | TR                      | average turbidity during time scale                    | NTU   | -           |
| {term}`wave_height_max`         | MAXH                    | max wave height during time scale                      | cm    | -           |
| {term}`wave_height_sign`        | SIGH                    | average significant wave height during time scale      | cm    | -           |
| {term}`wave_period`             | TP                      | average wave period during time scale                  | s     | >=0         |
| {term}`wind_direction`          | WR                      | average wind direction during time scale               | °     | >=0,<=360   |
| {term}`wind_speed`              | WG                      | average wind speed during time scale                   | m/s   | -           |
