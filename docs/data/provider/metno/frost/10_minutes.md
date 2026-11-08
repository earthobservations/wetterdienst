# 10 minutes

## metadata

| property      | value   |
|---------------|---------|
| name          | 10_minutes |
| original name | PT10M   |

## datasets

### data

#### parameters

| name                            | original name                          | description                                         | unit |
|---------------------------------|----------------------------------------|-----------------------------------------------------|------|
| {term}`temperature_air_max_2m` | max(air_temperature PT10M) | Highest recorded air temperature per ten minutes | degree_celsius |
| {term}`temperature_air_min_2m` | min(air_temperature PT10M) | Lowest recorded air temperature per ten minutes | degree_celsius |
| {term}`humidity_relative_max` | max(relative_humidity PT10M) | Maximum relative humidity per 10 min | percent |
| {term}`humidity_relative_min` | min(relative_humidity PT10M) | Minimum relative humidity per 10 min | percent |
| {term}`wind_gust_max` | max(wind_speed_of_gust PT10M) | Maximum wind gust for the last ten minutes. At a station with several heights (the platforms have 10 m and one at 44 to 142 m) the 10 m sensor, and the nearest height where it has no value. | meter_per_second |
| {term}`precipitation_amount` | sum(precipitation_amount PT10M) | Amount of precipitation per 10 minutes | millimeter |

## Notes

There is no `wind_direction_gust_max`. It read `max(wind_from_direction_of_gust PT10M)`, which Frost describes as "Varying
wind direction last 10 minutes. Upper limit": the upper limit of a wind direction that varies, not the direction of the
gust, as the glossary entry says. Frost lists that element only at `PT30M` (119 time series) and `PT1M` (5) and none at
`PT10M`: the listing for `PT10M` answers 404 "No data found", and a request for it 412 at 12 of the 12 stations tried,
four of which return the 10-minute `wind_gust_max` (read 2026-11-07). A request for the name is refused, as for any
parameter that was removed ([migrating](../../../../usage/migrating.md#removed)).

The gust of a platform is the 10 m sensor's, where it has a value, and otherwise the nearest other height (the platforms have a
sensor at 44 to 142 m too): the core used to serve the highest one in 96 % of the intervals
([Sensors at several heights](index.md#sensors-at-several-heights)).
