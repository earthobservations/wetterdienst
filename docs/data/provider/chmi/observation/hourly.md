# hourly

## metadata

| property      | value  |
|---------------|--------|
| name          | hourly |
| original name | hourly |

## datasets

### data

#### parameters

| name                             | original name | description                                                                                                                                                                                                                                      | unit |
|----------------------------------|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_dew_point_2m` | Td            | Dew point temperature at 2 m, from the hourly SYNOP report.                                                                                                                                                                                      | °C   |
| {term}`precipitation_amount`     | SRA1H         | Precipitation total of the hour up to the stamp. The source states no window; the 10 minute precipitation values stamped up to the hour add up to it (taking those to be stamped at the end of their interval, which the source does not state). | mm   |
| {term}`pressure_air_site`        | P             | Air pressure at station level, from the hourly SYNOP report (the sea-level pressure is the separate element P_hm).                                                                                                                               | hPa  |
