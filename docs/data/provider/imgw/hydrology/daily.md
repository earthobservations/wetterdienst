# daily

## metadata

| property      | value                                                                                             |
|---------------|---------------------------------------------------------------------------------------------------|
| name          | daily                                                                                             |
| original name | dobowe                                                                                            |
| url           | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/) |

## datasets

### hydrology

#### metadata

| property      | value                                                                                             |
|---------------|---------------------------------------------------------------------------------------------------|
| name          | hydrology                                                                                         |
| original name | hydrologia                                                                                        |
| description   | historical daily hydrology data                                                                   |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/) |

#### parameters

| name                      | original name    | description                                                                                                                                                          | unit | constraints |
|---------------------------|------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`discharge`         | przepływ         | Discharge (Przepływ), in m³/s, one value per day. The source's 99999.999 or NULL, a discharge that was not worked out for the day, is null.                          | m³/s | >=0         |
| {term}`temperature_water` | temperatura wody | Water temperature (Temperatura wody), in °C, one value per day. The source's 99.9 or NULL (no data, for instance at a station that measures no temperature) is null. | °C   | -           |
| {term}`stage`             | stan wody        | Water level (Stan wody), in cm, one value per day. The source's 9999 or NULL (no data) is null.                                                                      | cm   | -           |
