# annual

## metadata

| property      | value   |
|---------------|---------|
| name          | annual  |
| original name | anuales |

## datasets

### data

#### parameters

| name                             | original name | unit type     | unit |
|-----------------------------------|---------------|----------------|------|
| temperature_air_mean_2m           | tm_mes        | temperature    | °C   |
| temperature_air_max_2m_mean       | tm_max        | temperature    | °C   |
| temperature_air_min_2m_mean       | tm_min        | temperature    | °C   |
| temperature_air_max_2m_multiday   | ta_max        | temperature    | °C   |
| temperature_air_min_2m_multiday   | ta_min        | temperature    | °C   |
| precipitation_height              | p_mes         | precipitation  | mm   |
| precipitation_height_max          | p_max         | precipitation  | mm   |

AEMET does not report a humidity field in the annual aggregate (unlike monthly), so
`humidity` is not available at this resolution.
