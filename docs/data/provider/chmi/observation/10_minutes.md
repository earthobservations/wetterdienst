# 10_minutes

## metadata

| property      | value      |
|---------------|------------|
| name          | 10_minutes |
| original name | 10_minutes |

## datasets

### data

#### parameters

| name                       | original name | description                                                                                                                                                                                                                            | unit |
|----------------------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_2m` | T             | Air temperature at 2 m, one value every ten minutes. The source states no statistic; it publishes the 10 minute maximum and minimum separately, as TMA and TMI.                                                                        | °C   |
| {term}`humidity_relative`  | H             | Relative humidity at 2 m, one value every ten minutes. The source states no statistic.                                                                                                                                                 | %    |
| {term}`pressure_air_site`  | P             | Air pressure at station level (the hourly sea-level pressure is the separate element P_hm), one value every ten minutes. The source states no statistic.                                                                               | hPa  |
| {term}`wind_speed`         | F             | Wind speed at 10 m by convention (the source gives each series its own height: 10 m at most stations), one value every ten minutes. The source states no statistic; its "Rychlost prům" (prům = průměr) is the separate element Fprum. | m/s  |
