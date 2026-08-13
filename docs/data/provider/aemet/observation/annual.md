# annual

## metadata

| property      | value   |
|---------------|---------|
| name          | annual  |
| original name | anuales |

## datasets

### data

#### parameters

| name                                    | original name | description                                              | unit |
|-----------------------------------------|---------------|----------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | tm_mes | Annual mean temperature. | degree_celsius |
| {term}`temperature_air_max_2m_mean` | tm_max | Annual mean of the maximum temperatures. | degree_celsius |
| {term}`temperature_air_min_2m_mean` | tm_min | Annual mean of the minimum temperatures. | degree_celsius |
| {term}`temperature_air_max_2m_multiday` | ta_max | Absolute maximum temperature of the year, and its date. | degree_celsius |
| {term}`temperature_air_min_2m_multiday` | ta_min | Absolute minimum temperature of the year, and its date. | degree_celsius |
| {term}`precipitation_height` | p_mes | Total annual precipitation. | millimeter |
| {term}`precipitation_height_max` | p_max | Greatest daily precipitation of the year, and its date. | millimeter |

AEMET does not report a humidity field in the annual aggregate (unlike monthly), so
`humidity` is not available at this resolution.
