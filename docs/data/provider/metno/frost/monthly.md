# monthly

## metadata

| property      | value   |
|---------------|---------|
| name          | monthly |
| original name | P1M     |

## datasets

### data

#### parameters

| name                                  | original name                       | description                                                                                                                                                                                                     | unit |
|---------------------------------------|-------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | mean(air_temperature P1M) | Monthly mean temperature. The mean is an arithmetic mean of daily values. Only the calendar-month series is returned (`timeOffset` PT0H); Frost also has a 06-06 UTC series (PT6H), which is left out, and a month that only it has is not returned and the answer says so (901 months at 179 stations of the station list) (GH-3855). | degree_celsius |
| {term}`temperature_air_max_2m` | max(air_temperature P1M) | Highest recorded air temperature per month | degree_celsius |
| {term}`temperature_air_min_2m` | min(air_temperature P1M) | Lowest recorded air temperature per month | degree_celsius |
| {term}`temperature_dew_point_mean_2m` | mean(dew_point_temperature P1M) | Monthly mean dew-point temperature. Dew-point temperature is the temperature at which the air, when cooled, will become saturated (and dew is formed). | degree_celsius |
| {term}`precipitation_amount` | sum(precipitation_amount P1M) | Monthly precipitation sum. Only the series of `timeOffset` PT6H is returned: from 06 UTC on the last day of the previous month to 06 UTC on the last day of the month; Frost also has the 18-18 UTC series (PT18H). | millimeter |
| {term}`wind_speed_mean` | mean(wind_speed P1M) | Monthly mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available). | meter_per_second |
| {term}`wind_speed_rolling_mean_max` | max(wind_speed P1M) | Monthly maximum mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available). | meter_per_second |
| {term}`humidity_relative_mean` | mean(relative_humidity P1M) | Monthly mean relative humidity. | percent |
| {term}`pressure_air_sea_level_mean` | mean(air_pressure_at_sea_level P1M) | Monthly mean air pressure reduced to sea level. The parameter is usually called QFF in aviation and shows the measured air pressure reduced to mean sea level by applying actual atmospheric conditions. | hectopascal |
| {term}`pressure_air_site_mean` | mean(surface_air_pressure P1M) | Monthly mean air pressure at the station. The parameter is usually called QFE in aviation and shows the measured air pressure reduced to the reference height of the station. | hectopascal |
| {term}`cloud_cover_total_mean` | mean(cloud_area_fraction P1M) | Monthly mean cloud cover. The mean is an arithmetic mean of three daily observations (06, 12 and 18 UTC). | one_eighth |
| {term}`snow_depth_mean` | mean(surface_snow_thickness P1M) | Monthly mean snow depth. The mean value is an arithmetic mean of daily values. | centimeter |
| {term}`sunshine_duration` | sum(duration_of_sunshine P1M) | Number of hours of sunshine over the last month. | hour |

## Notes

The monthly precipitation sum is the series of `timeOffset` `PT6H`: the month `M`, stamped on its first day, is the sum
from 06 UTC on the last day of the previous month to 06 UTC on the last day of `M` (Frost: "the value of February 2018
has referenceTime = 2018-02-01T00:00 and is based on the period from 2018-01-31T06:00 to 2018-02-28T06:00"). Frost keeps
an 18-18 UTC series of it too at 964 of the 2,388 stations of its time-series listing (612 of them in the station list), which the reader used to return where there is one. See the
section [The two series of the daily and monthly precipitation sum](index.md#the-two-series-of-the-daily-and-monthly-precipitation-sum)
of the Frost page, which also says what the monthly mean temperature returns
([the two series of the mean](index.md#the-two-series-of-the-daily-and-monthly-mean-temperature)).

At a station with several heights the monthly mean temperature and humidity are of 2 m and the mean and the maximum of the
wind of 10 m, each where that height has a value, and otherwise of the nearest other height
([Sensors at several heights](index.md#sensors-at-several-heights)). The mean and the maximum of a month are chosen apart.
