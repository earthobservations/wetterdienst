# monthly

## metadata

| property      | value                                                                                                 |
|---------------|-------------------------------------------------------------------------------------------------------|
| name          | monthly                                                                                               |
| original name | miesieczne                                                                                            |
| url           | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/miesieczne/) |

## datasets

### hydrology

#### metadata

| property      | value                                                                                                 |
|---------------|-------------------------------------------------------------------------------------------------------|
| name          | hydrology                                                                                             |
| original name | dane_hydrologiczne                                                                                    |
| description   | historical monthly hydrology data                                                                     |
| access        | [here](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/miesieczne/) |

#### parameters

| name                           | original name               | description                                                                                                                                                                                                                                                                                                                                             | unit | constraints |
|--------------------------------|-----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|-------------|
| {term}`discharge_max`          | maksymalna przepływ         | Monthly maximum of the discharge (Przepływ), in m³/s (the extremum indicator of the file is 3). The source's 99999.999 or NULL, no data or gaps in the month's observations, is null.                                                                                                                                                                   | m³/s | >=0         |
| {term}`discharge_mean`         | średnia przepływ            | Monthly mean of the discharge (Przepływ), in m³/s (the extremum indicator of the file is 2). The source's 99999.999 or NULL, no data or gaps in the month's observations, is null.                                                                                                                                                                      | m³/s | >=0         |
| {term}`discharge_min`          | minimalna przepływ          | Monthly minimum of the discharge (Przepływ), in m³/s (the extremum indicator of the file is 1). The source's 99999.999 or NULL, no data or gaps in the month's observations, is null.                                                                                                                                                                   | m³/s | >=0         |
| {term}`temperature_water_max`  | maksymalna temperatura wody | Monthly maximum of the water temperature (Temperatura wody), in °C (the extremum indicator of the file is 3). The source's 99.9 or NULL, no data or gaps in the month's observations, is null.                                                                                                                                                          | °C   | -           |
| {term}`temperature_water_mean` | średnia temperatura wody    | Monthly mean of the water temperature (Temperatura wody), in °C (the extremum indicator of the file is 2). The source's 99.9 or NULL, no data or gaps in the month's observations, is null.                                                                                                                                                             | °C   | -           |
| {term}`temperature_water_min`  | minimalna temperatura wody  | Monthly minimum of the water temperature (Temperatura wody), in °C (the extremum indicator of the file is 1). The source's 99.9 or NULL, no data or gaps in the month's observations, is null.                                                                                                                                                          | °C   | -           |
| {term}`stage_max`              | maksymalna stan wody        | Monthly maximum of the water level (Stan wody), in cm (the extremum indicator of the file is 3). The source's 9999 or NULL, no data or gaps in the month's observations, is null. The stage is measured from the zero of the station's gauge, so stations share no reference level; the station's `gauge_zero` is the altitude of that zero in m a.s.l. | cm   | -           |
| {term}`stage_mean`             | średnia stan wody           | Monthly mean of the water level (Stan wody), in cm (the extremum indicator of the file is 2). The source's 9999 or NULL, no data or gaps in the month's observations, is null. The stage is measured from the zero of the station's gauge, so stations share no reference level; the station's `gauge_zero` is the altitude of that zero in m a.s.l.    | cm   | -           |
| {term}`stage_min`              | minimalna stan wody         | Monthly minimum of the water level (Stan wody), in cm (the extremum indicator of the file is 1). The source's 9999 or NULL, no data or gaps in the month's observations, is null. The stage is measured from the zero of the station's gauge, so stations share no reference level; the station's `gauge_zero` is the altitude of that zero in m a.s.l. | cm   | -           |
