# 15_minutes

## metadata

| property      | value                                                                      |
|---------------|----------------------------------------------------------------------------|
| name          | 15_minutes                                                                 |
| original name | 15_minutes                                                                 |
| description   | no specific dataset is provided but parameters can be queried individually |
| url           | [here](https://environment.data.gov.uk/hydrology/doc/reference)            |

## datasets

### data

#### metadata

| property      | value                                                                              |
|---------------|------------------------------------------------------------------------------------|
| name          | data                                                                               |
| original name | data                                                                               |
| description   | Historical 15 minute station observations of flow and groundwater level for the UK |
| access        | [here](https://environment.data.gov.uk/hydrology/doc/reference)                    |

#### parameters

| name              | original name | description                            | unit type       | unit | constraints |
|-------------------|---------------|----------------------------------------|-----------------|------|-------------|
| discharge         | flow-i-900    | instant flow at timestamp              | volume_per_time | m³/s | >=0         |
| groundwater_level | level-i-900   | instant groundwater level at timestamp | length_medium   | m    | >=0         |
