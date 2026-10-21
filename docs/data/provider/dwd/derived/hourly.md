# hourly

## metadata

| property      | value                                                                                    |
|---------------|------------------------------------------------------------------------------------------|
| name          | hourly                                                                                  |
| original name | hourly                                                                                  |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/) |

## datasets

### radiation_global

#### metadata

| property      | value                                                                                                                                                                                                               |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | radiation_global                                                                                                                                                                                                    |
| original name | radiation_global                                                                                                                                                                                                    |
| description   | Hourly global radiation data with quality flags and uncertainty estimates ([details](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/DESCRIPTION_derived_germany-climate-hourly-duett_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/)                                                                                                                       |

#### parameters

| name                                 | original name | description                     | unit                        | constraints |
|--------------------------------------|---------------|---------------------------------|-----------------------------|-------------|
| {term}`quality`                      | qn_952        | Quality flag.                   | dimensionless               | -           |
| {term}`radiation_global`             | fg_duett      | Global radiation (the sheet: surface irradiance, hourly mean surface downwelling shortwave radiation) of a DWD pseudo-station, in J/cm2: derived from gridded satellite and station data (DUETT) with a topography correction, not measured at the station. The hour is the synoptic hour ending at the stamp; the sheet states it as (HH-1):50 to HH:50 in one place and (HH-2):50 to (HH-1):50 in another. | joule_per_square_centimeter | >=0         |
| {term}`radiation_global_uncertainty` | fg_un_duett   | Uncertainty of the hourly global radiation of the pseudo-station, in J/cm2 (the sheet: estimated from the differences between the satellite and station data, the variability around the point and the geometric uncertainty of the cloud observation). | joule_per_square_centimeter | >=0         |

### sunshine_duration

#### metadata

| property      | value                                                                                                                                                                                                               |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | sunshine_duration                                                                                                                                                                                                   |
| original name | sunshine_duration                                                                                                                                                                                                   |
| description   | Hourly sunshine duration data with quality flags and uncertainty estimates ([details](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/DESCRIPTION_derived_germany-climate-hourly-duett_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/)                                                                                                                       |

#### parameters

| name                                  | original name | description                      | unit          | constraints |
|---------------------------------------|---------------|----------------------------------|---------------|-------------|
| {term}`quality`                       | qn_952        | Quality flag.                    | dimensionless | -           |
| {term}`sunshine_duration`             | sd_duett      | Sunshine duration of a DWD pseudo-station in the hour, in minutes: derived from gridded satellite and station data (DUETT), not measured at the station. The hour is the synoptic hour ending at the stamp; the sheet states it as (HH-1):50 to HH:50 in one place and (HH-2):50 to (HH-1):50 in another. | minute        | >=0         |
| {term}`sunshine_duration_uncertainty` | sd_un_duett   | Uncertainty of the hourly sunshine duration of the pseudo-station, in minutes (estimated as the uncertainty of the global radiation). | minute        | >=0         |
