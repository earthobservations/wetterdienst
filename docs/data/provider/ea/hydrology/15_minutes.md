# 15_minutes

## metadata

| property      | value                                                                      |
|---------------|----------------------------------------------------------------------------|
| name          | 15_minutes                                                                 |
| original name | 15_minutes                                                                 |
| url           | [here](https://environment.data.gov.uk/hydrology/doc/reference)            |

## datasets

### data

#### metadata

| property      | value                                                                                                 |
|---------------|-------------------------------------------------------------------------------------------------------|
| name          | data                                                                                                  |
| original name | data                                                                                                  |
| description   | Historical 15 minute station observations of flow, river water level and groundwater level for the UK |
| access        | [here](https://environment.data.gov.uk/hydrology/doc/reference)                                       |

#### parameters

| name                      | original name        | description                                                                                           | unit | constraints |
|---------------------------|----------------------|-------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`discharge`         | flow-i-900           | instant flow at timestamp                                                                             | m³/s | >=0         |
| {term}`stage`             | level-i-900          | instant river water level at timestamp                                                                | m    | -           |
| {term}`groundwater_level` | gw-logged-i-subdaily | logged groundwater level at timestamp, in metres above ordnance datum, every 15 minutes to every hour | m    | -           |
