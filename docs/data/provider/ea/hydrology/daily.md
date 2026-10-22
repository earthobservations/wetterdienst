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
| description   | Historical daily station observations of flow and river water level for the UK |
| access        | [here](https://environment.data.gov.uk/hydrology/doc/reference)                |

#### parameters

| name                   | original name   | description                                                                                                                                                                                                   | unit | constraints |
|------------------------|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`discharge_max`  | flow-max-86400  | daily maximum flow, within the 24 hours from 09:00 of the day it is dated to 09:00 of the next (the source gives no zone; read as UTC)                                                                        | m³/s | >=0         |
| {term}`discharge_mean` | flow-m-86400    | daily mean flow, over the 24 hours from 09:00 of the day it is dated to 09:00 of the next (the source gives no zone; read as UTC)                                                                             | m³/s | >=0         |
| {term}`discharge_min`  | flow-min-86400  | daily minimum flow, within the 24 hours from 09:00 of the day it is dated to 09:00 of the next (the source gives no zone; read as UTC)                                                                        | m³/s | >=0         |
| {term}`stage_max`      | level-max-86400 | daily maximum river water level, within the 24 hours from 09:00 of the day it is dated to 09:00 of the next (the source gives no zone; read as UTC), in the source's unit m, relative to an unspecified datum | m    | -           |
| {term}`stage_min`      | level-min-86400 | daily minimum river water level, within the 24 hours from 09:00 of the day it is dated to 09:00 of the next (the source gives no zone; read as UTC), in the source's unit m, relative to an unspecified datum | m    | -           |
