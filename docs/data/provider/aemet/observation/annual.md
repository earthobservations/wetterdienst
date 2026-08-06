# annual

## metadata

| property      | value   |
|---------------|---------|
| name          | annual  |
| original name | anuales |

## datasets

### data

#### parameters

| name                                    | original name | unit |
|-----------------------------------------|---------------|------|
| {term}`temperature_air_mean_2m`         | tm_mes        | °C   |
| {term}`temperature_air_max_2m_mean`     | tm_max        | °C   |
| {term}`temperature_air_min_2m_mean`     | tm_min        | °C   |
| {term}`temperature_air_max_2m_multiday` | ta_max        | °C   |
| {term}`temperature_air_min_2m_multiday` | ta_min        | °C   |
| {term}`precipitation_height`            | p_mes         | mm   |
| {term}`precipitation_height_max`        | p_max         | mm   |

AEMET does not report a humidity field in the annual aggregate (unlike monthly), so
`humidity` is not available at this resolution.
