# hourly

## metadata

| property      | value  |
|---------------|--------|
| name          | hourly |
| original name | hourly |

## datasets

### data

#### metadata

| property      | value |
|---------------|-------|
| name          | data  |
| original name | data  |

#### parameters

| name                            | original name    | description                                                                                   | unit |
|---------------------------------|------------------|-----------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | airTemperature | Air temperature, °C. | °C |
| {term}`humidity` | relativeHumidity | Relative humidity of the air, %. | % |
| {term}`wind_speed` | windSpeed | Wind speed, m/s. | m/s |
| {term}`wind_gust_max` | windGust | Wind gust, m/s. The maximum gust over the hour. | m/s |
| {term}`wind_direction` | windDirection | Wind direction, °. Values: 0 is from the north, 180 is from the south, and so on. | ° |
| {term}`cloud_cover_total` | cloudCover | Cloud cover, %. Values: 0 is clear, 100 is overcast. Where the cloud cover cannot be determined, for example because of fog, null is returned. | % |
| {term}`pressure_air_sea_level` | seaLevelPressure | Pressure at sea level, hPa. | hPa |
| {term}`precipitation_height` | precipitation | Precipitation amount, mm. The precipitation sum over the hour. | mm |
| {term}`snow_depth` | snowDepth | Thickness of the snow cover, cm. | cm |
