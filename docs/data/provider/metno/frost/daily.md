# daily

## metadata

| property      | value |
|---------------|-------|
| name          | daily |
| original name | P1D   |

## datasets

### data

#### parameters

| name                                | original name                                       | description                                                                                                                                                                                                                                                                                                                            | unit |
|-------------------------------------|-----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|
| {term}`temperature_air_mean_2m` | mean(air_temperature P1D) | Daily mean temperature. The mean is an arithmetic mean of 24 hourly values (00-00 UTC), or a formula based mean value when only a limited number of observations is available (e.g. 06, 12, 18 UTC). Only the calendar-day series is returned (`timeOffset` PT0H: the hourly readings stamped 00:00 to 23:00); Frost also has a 06-06 UTC series (PT6H), at 1,063 stations of its listing that have both, which is left out, and a station that has no PT0H series returns no values. A date that only PT6H has is not returned and the answer says so (at least 3,694 days at 11 stations of the station list: a lower bound) (GH-3855). | degree_celsius |
| {term}`temperature_air_max_2m` | max(air_temperature P1D) | Highest recorded air temperature per 24 hours, 18-18 UTC: the 24 hours ending 18 UTC of the date (`timeOffset` PT18H, which Frost's table of standard offsets calls 19-18 UTC after the hourly readings stamped 19:00 to 18:00). Only this series is returned; Frost also has the series it files as the calendar day (PT0H: the hourly readings stamped 00:00 to 23:00), which is left out, and a station that has no PT18H series returns no values (GH-3843). | degree_celsius |
| {term}`temperature_air_min_2m` | min(air_temperature P1D) | Lowest recorded air temperature per 24 hours, 18-18 UTC: the 24 hours ending 18 UTC of the date (`timeOffset` PT18H, which Frost's table of standard offsets calls 19-18 UTC after the hourly readings stamped 19:00 to 18:00). Only this series is returned; Frost also has the series it files as the calendar day (PT0H: the hourly readings stamped 00:00 to 23:00), which is left out, and a station that has no PT18H series returns no values (GH-3843). | degree_celsius |
| {term}`precipitation_amount` | sum(precipitation_amount P1D) | Daily precipitation sum (between 06-06 UTC). Only this series is returned (`timeOffset` PT6H, the day from 06 UTC of the previous date); Frost also has the 18-18 UTC sum (PT18H). Code -1 means no precipitation (Frost's data clarifications, 0.0 mm) and is returned as 0.0 with `raw:-1`, at every station and in every year but one: SN81930 (Storstilla) up to and including 1993, a weekly reader whose -1 marks a day nobody read the gauge on, is null with `raw:-1` (GH-3820). | millimeter |
| {term}`wind_speed_mean` | mean(wind_speed P1D) | Daily mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available). | meter_per_second |
| {term}`wind_speed_rolling_mean_max` | max(wind_speed P1D) | Daily maximum mean wind speed of hourly observations (00, 01, 02,..., 23 UTC). If hourly observations do not exist then the main observation times are used (06, 12, 18 UTC and also 00 UTC where available). | meter_per_second |
| {term}`humidity_relative_mean` | mean(relative_humidity P1D) | Daily mean relative humidity. | percent |
| {term}`pressure_air_sea_level_mean` | mean(air_pressure_at_sea_level P1D) | Mean daily air pressure reduced to sea level. The parameter is usually called QFF in aviation and shows the measured air pressure reduced to mean sea level by applying actual atmospheric conditions. | hectopascal |
| {term}`pressure_air_site_mean` | mean(surface_air_pressure P1D) | Daily mean air pressure at the station. The parameter is usually called QFE in aviation and shows the measured air pressure reduced to the reference height of the station. | hectopascal |
| {term}`radiation_global_intensity_mean` | mean(surface_downwelling_shortwave_flux_in_air P1D) | Mean global radiation over the last 24 hours. Global radiation is the total downwelling shortwave radiation from the sun. Shortwave radiation have wavelengths in the area 295-2800 nm and therefore includes ultraviolet, visible and infrared light. The instrument measures the radiation flux through a horizontal surface (W/m2). | watt_per_square_meter |
| {term}`snow_depth` | surface_snow_thickness | The depth of the snow is measured in cm from the ground to the top of the snow cover. Code -1 means no snow (Frost's data clarifications: "Zero snowdepth or partial snow cover") and is returned as a depth of 0; code 0 means a depth of less than 0.5 cm and is returned as 0; code -3 means it was not possible to measure the depth, and is returned as null. | centimeter |
| {term}`sunshine_duration` | sum(duration_of_sunshine P1D) | Number of hours of sunshine over the last 24 hours. | hour |

## Notes

The daily precipitation sum is the 06-06 UTC series: the date `D` is the sum from `D-1` 06 UTC to `D` 06 UTC. Frost keeps
a second series of it, 18-18 UTC, at 987 of the 2,334 stations of its time-series listing (618 of them in the station list), and the reader used to return that one where there is
one. See the section [The two series of the daily and monthly precipitation sum](index.md#the-two-series-of-the-daily-and-monthly-precipitation-sum)
of the Frost page, which also says what the temperature extremes return.

Frost states that `-1` of the daily precipitation sum is 0.0 mm. It is returned as `0.0` with `raw:-1` as the last token of
`quality_flags`, at every station and in every year, with one exception: SN81930 (Storstilla) up to and including 1993 is a
weekly reader, and its `-1` marks a day nobody read the gauge on (the week's rain is in the next reading), so it is `null` with
`raw:-1` (no row at the default `drop_nulls`). Filter on `raw:-1` to find both
([#3820](https://github.com/earthobservations/wetterdienst/issues/3820)). The monthly sum and the other elements keep their
`-1` as they were. See the section [The daily `-1` and the weekly reader](index.md#the-daily--1-and-the-weekly-reader) of the
Frost page.

The `-1` of `snow_depth` ("Zero snowdepth or partial snow cover") is `0.0` with `raw:-1`, a `0` ("Snowdepth less than 0.5
cm") stays `0.0`, and a `-3` ("Not possible to measure snowdepth") is `null` with `raw:-3`. See the section
[The other coded values](index.md) of the Frost page.
