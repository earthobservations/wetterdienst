# daily

## metadata

| property      | value                                                                                          |
|---------------|------------------------------------------------------------------------------------------------|
| name          | daily                                                                                          |
| original name | daily                                                                                          |
| url           | [here](https://environment.data.gov.uk/hydrology/doc/reference)                                |

## datasets

### data

#### metadata

| property      | value                                                                          |
|---------------|--------------------------------------------------------------------------------|
| name          | data                                                                           |
| original name | data                                                                           |
| description   | Historical daily station observations of flow and groundwater level for the UK |
| access        | [here](https://environment.data.gov.uk/hydrology/doc/reference)                |

#### parameters

| name                          | original name   | description                     | unit | constraints |
|-------------------------------|-----------------|---------------------------------|------|-------------|
| {term}`discharge_max`         | flow-max-86400  | daily maximum flow              | m³/s | >=0         |
| {term}`discharge_mean`        | flow-m-86400    | daily mean flow                 | m³/s | >=0         |
| {term}`discharge_min`         | flow-min-86400  | daily min flow                  | m³/s | >=0         |
| {term}`groundwater_level_max` | level-max-86400 | daily maximum groundwater level | m    | >=0         |
| {term}`groundwater_level_min` | level-min-86400 | daily minimum groundwater level | m    | >=0         |
