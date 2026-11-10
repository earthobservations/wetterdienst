# hourly

## metadata

| property      | value                                                                                        |
|---------------|----------------------------------------------------------------------------------------------|
| name          | hourly                                                                                       |
| original name | hourly                                                                                       |
| url           | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/) |

## datasets

### cloud_type

#### metadata

| property      | value                                                                                                                                                                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | cloud_type                                                                                                                                                                                                                                                                |
| original name | cloud_type                                                                                                                                                                                                                                                                |
| description   | Hourly station observations of cloud cover, cloud type and cloud height in up to 4 layers for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloud_type/DESCRIPTION_obsgermany_climate_hourly_cloud_type_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloud_type/)                                                                                                                                                                   |

#### parameters

| name                        | original name | description              | unit | constraints                            |
|-----------------------------|---------------|--------------------------|------|----------------------------------------|
| {term}`quality` | qn_8 | Quality flag. | -             | - |
| {term}`cloud_cover_total` | v_n | Total cloud cover. | 1/8 | >=0,<=8 |
| {term}`cloud_cover_total_measurement_method` | v_n_i | Index how measurement is taken, P = by human person,I = by instrument. Returned as 1 for P and 2 for I. | - | ∈ {1, 2} |
| {term}`cloud_type_layer1` | v_s1_cs | Cloud type of 1. layer. | - | ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9} |
| {term}`cloud_height_layer1` | v_s1_hhs | Lower boundary height of 1.layer. | m | >=0 |
| {term}`cloud_cover_layer1` | v_s1_ns | Cloud cover in the first layer. | 1/8 | >=0,<=8 |
| {term}`cloud_type_layer2` | v_s2_cs | Cloud type of 2. layer. | - | ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9} |
| {term}`cloud_height_layer2` | v_s2_hhs | Lower boundary height of 2.layer. | m | >=0 |
| {term}`cloud_cover_layer2` | v_s2_ns | Cloud cover in the second layer. | 1/8 | >=0,<=8 |
| {term}`cloud_type_layer3` | v_s3_cs | Cloud type of 3. layer. | - | ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9} |
| {term}`cloud_height_layer3` | v_s3_hhs | Lower boundary height of 3.layer. | m | >=0 |
| {term}`cloud_cover_layer3` | v_s3_ns | Cloud cover in the third layer. | 1/8 | >=0,<=8 |
| {term}`cloud_type_layer4` | v_s4_cs | Cloud type of 4. layer. | - | ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8, 9} |
| {term}`cloud_height_layer4` | v_s4_hhs | Lower boundary height of 4.layer. | m | >=0 |
| {term}`cloud_cover_layer4` | v_s4_ns | Cloud cover in the fourth layer. | 1/8 | >=0,<=8 |

Codes (cloud_type_layer):

| code | cloud type    |
|------|---------------|
| 0    | cirrus        |
| 1    | cirrocumulus  |
| 2    | cirrostratus  |
| 3    | altocumulus   |
| 4    | altostratus   |
| 5    | nimbostratus  |
| 6    | stratocumulus |
| 7    | stratus       |
| 8    | cumulus       |
| 9    | cumulonimbus  |

### cloudiness

#### metadata

| property      | value                                                                                                                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | cloudiness                                                                                                                                                                                                                |
| original name | cloudiness                                                                                                                                                                                                                |
| description   | Hourly station observations of cloudiness for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloudiness/DESCRIPTION_obsgermany_climate_hourly_cloudiness_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/cloudiness/)                                                                                                                   |

#### parameters

| name                            | original name | description                    | unit | constraints                         |
|---------------------------------|---------------|--------------------------------|------|-------------------------------------|
| {term}`quality` | qn_8 | Quality flag. | -             | - |
| {term}`cloud_cover_total_measurement_method` | v_n_i | Index how measurement is taken, P = by human person,I = by instrument. Returned as 1 for P and 2 for I. | - | ∈ {1, 2} |
| {term}`cloud_cover_total` | v_n | Total cloud cover. | 1/8 | >=0,<=8 |

Codes (cloud_cover_total_measurement_method):

| value | source letter | meaning      |
|-------|---------------|--------------|
| 1     | P             | human person |
| 2     | I             | instrument   |

### dew_point

#### metadata

| property      | value                                                                                                                                                                                                                                      |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | dew_point                                                                                                                                                                                                                                  |
| original name | dew_point                                                                                                                                                                                                                                  |
| description   | Hourly station observations of air and dew point temperature for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/dew_point/DESCRIPTION_obsgermany_climate_hourly_dew_point_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/dew_point/)                                                                                                                                     |

#### parameters

| name                                  | original name | description           | unit | constraints |
|---------------------------------------|---------------|-----------------------|------|-------------|
| {term}`quality` | qn_8 | Quality flag. | -             | - |
| {term}`temperature_air_2m` | tt | Air temperature. A reading taken at or before the stamp: the value at the stamp minus 10 min from 2001-04-01, at the stamp minus 30 min from 1994 to 2001-03-31 (20 to 30 min in 1991-1993, by station), measured against the 10-minute series of the same station; before 1991 the SYNOP report of the stamp hour (NOAA ISD). Times are UTC. | °C | - |
| {term}`temperature_dew_point_2m` | td | Dew point temperature. A reading taken at or before the stamp: the value at the stamp minus 10 min from 2001-04-01, at the stamp minus 30 min from 1994 to 2001-03-31 (20 to 30 min in 1991-1993, by station), measured against the 10-minute series of the same station; before 1991 the SYNOP report of the stamp hour (NOAA ISD). Times are UTC. | °C | - |

### moisture

#### metadata

| property      | value                                                                                                                                                                                                                          |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | moisture                                                                                                                                                                                                                       |
| original name | moisture                                                                                                                                                                                                                       |
| description   | Hourly station observations of moisture parameters for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/moisture/DESCRIPTION_obsgermany_climate_hourly_moisture_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/moisture/)                                                                                                                          |

#### parameters

| name                                  | original name | description                        | unit | constraints |
|---------------------------------------|---------------|------------------------------------|------|-------------|
| {term}`quality` | qn_4 | Quality flag. | -             | - |
| {term}`humidity_absolute` | absf_std | Computed hourly value of absolute humidity. | g/m³ | >=0 |
| {term}`pressure_vapor` | vp_std | Computed hourly value of vapour pressure. | hPa | >=0 |
| {term}`temperature_wet_2m`      | tf_std | Computed hourly value of wet bulb temperature. | °C | - |
| {term}`pressure_air_site` | p_std | Hourly value of barometric pressure. A station without a barometer carries one station constant in every row of a file, which is no reading: a run of 72 hourly readings of one value is flagged `suspect:stuck` in quality_flags and kept (the check `stuck`, soft by default), or null with `rejected:stuck,raw:997.3` where the check is hard. A reading taken at or before the stamp: the value at the stamp minus 10 min from 2001-04-01, at the stamp minus 20 min from 1995 to 2001-03-31 (1991-1994 not one offset, 0 to 30 min), measured against the 10-minute series of the same station; before 1991 the SYNOP report of the stamp hour (NOAA ISD). Times are UTC. | hPa | >=0 |
| {term}`temperature_air_2m` | tt_std | Air temperatur in 2m above ground. A reading taken at or before the stamp: the value at the stamp minus 10 min from 2001-04-01, at the stamp minus 30 min from 1994 to 2001-03-31 (20 to 30 min in 1991-1993, by station), measured against the 10-minute series of the same station; before 1991 the SYNOP report of the stamp hour (NOAA ISD). Times are UTC. | °C | - |
| {term}`humidity_relative` | rf_std | Relative humidity. A reading taken at or before the stamp: the value at the stamp minus 10 min from 2001-04-01, at the stamp minus 30 min from 1994 to 2001-03-31 (20 to 30 min in 1991-1993, by station), measured against the 10-minute series of the same station; before 1991 the SYNOP report of the stamp hour (NOAA ISD). Times are UTC. | % | >=0,<=100 |
| {term}`temperature_dew_point_2m` | td_std | Dew point temperature in 2m above ground. A reading taken at or before the stamp: the value at the stamp minus 10 min from 2001-04-01, at the stamp minus 30 min from 1994 to 2001-03-31 (20 to 30 min in 1991-1993, by station), measured against the 10-minute series of the same station; before 1991 the SYNOP report of the stamp hour (NOAA ISD). Times are UTC. | °C | - |

### precipitation

#### metadata

| property      | value                                                                                                                                                                                                                              |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | precipitation                                                                                                                                                                                                                      |
| original name | precipitation                                                                                                                                                                                                                      |
| description   | Hourly station observations of precipitation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/DESCRIPTION_obsgermany_climate_hourly_precipitation_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/)                                                                                                                         |

#### parameters

| name                         | original name | description           | unit | constraints                  |
|------------------------------|---------------|-----------------------|------|------------------------------|
| {term}`precipitation_amount` | r1 | Precipitation height during the previous hour: the sum of the six 10-minute values of the window (T-70, T-10] min from 2001-04-01 and of (T-90, T-30] from 1995-09 to 2001-03-31 (UTC, T the stamp), measured against the 10-minute series of the same station. | mm | >=0 |
| {term}`precipitation_index` | rs_ind | Precipitation indicator; 0 = no; 1 = yes. | - | ∈ {0, 1} |
| {term}`precipitation_form` | wrtr | Precipitation form; 0 = no precipitation; 1 = rain only (in historical data before 01.01.1979); 4 = form of precipitation unascertainable and depositional precipitation, automatic ascertainment; 6 = liquid precipitation, automatic ascertainment; 7 = solid precipitation, automatic ascertainment; 8 = liquid and solid precipitation, automatic ascertainment; 9 = missing value, form of precipitation unascertainable, automatic ascertainment; returned as null, the 9 stays as the last token of quality_flags, raw:9. The files also hold 2 and 3, which the current sheet does not define. | - | ∈ {0, 1, 2, 3, 4, 6, 7, 8} |

Codes (precipitation_indicator):

| code | meaning          |
|------|------------------|
| 0    | no precipitation |
| 1    | precipitation    |

Codes (precipitation_form):

| code | meaning                                                                                                                                                                                         |
|------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0    | no precipitation, for automatic stations this corresponds to WMO code 10                                                                                                                        |
| 1    | rain only (in historical data before 01.01.1979); the files also hold it after that (station 01048, 4 rows in 2001), where an earlier version of this page read "precipitation height only due to deposition (dew or frost)" |
| 2    | not defined by the current sheet; an earlier version of this page read "precipitation height only due to liquid deposition". In the files of station 01048 (2001 to 2021) it stands at 0.0 to 0.2 mm, mostly at night |
| 3    | not defined by the current sheet; an earlier version of this page read "precipitation height only due to solid precipitation". In the files of station 01048 (2002 to 2010) it stands at 0.0 to 0.2 mm, from October to February |
| 4    | form of precipitation unknown although precipitation was reported; falling and deposited precipitation cannot be told apart by automatic measurement (the English sheet: "form of precipitation unascertainable and depositional precipitation, automatic ascertainment") |
| 6    | liquid precipitation, automatic ascertainment, corresponds to WMO code 11                                                                                                                       |
| 7    | solid precipitation, automatic ascertainment, corresponds to WMO code 12                                                                                                                        |
| 8    | liquid and solid precipitation, automatic ascertainment, corresponds to WMO code 13                                                                                                             |
| 9    | missing value, form of precipitation unascertainable, automatic ascertainment, corresponds to WMO code 15; returned as null, the 9 stays as `raw:9` in `quality_flags` (GH-2703)                  |

### pressure

#### metadata

| property      | value                                                                                                                                                                                                               |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | pressure                                                                                                                                                                                                            |
| original name | pressure                                                                                                                                                                                                            |
| description   | Hourly station observations of pressure for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/DESCRIPTION_obsgermany_climate_hourly_pressure_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/pressure/)                                                                                                               |

#### parameters

| name                           | original name | description             | unit | constraints |
|--------------------------------|---------------|-------------------------|------|-------------|
| {term}`pressure_air_sea_level` | p | Barometric pressure at sea level NN, reduced from the station pressure and the air temperature of the same row. A reading taken at or before the stamp: the value at the stamp minus 10 min from 2001-04-01, at the stamp minus 20 min from 1995 to 2001-03-31 (1991-1994 not one offset, 0 to 30 min), measured against the 10-minute series of the same station; before 1991 the SYNOP report of the stamp hour (NOAA ISD). Times are UTC. | hPa | >=0 |
| {term}`pressure_air_site` | p0 | Barometric pressure at station height. A reading taken at or before the stamp: the value at the stamp minus 10 min from 2001-04-01, at the stamp minus 20 min from 1995 to 2001-03-31 (1991-1994 not one offset, 0 to 30 min), measured against the 10-minute series of the same station; before 1991 the SYNOP report of the stamp hour (NOAA ISD). Times are UTC. | hPa | >=0 |

### solar

#### metadata

| property      | value                                                                                                                                                                                                                                                               |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | solar                                                                                                                                                                                                                                                               |
| original name | solar                                                                                                                                                                                                                                                               |
| description   | Hourly station observations of solar incoming (total/diffuse) and longwave downward radiation for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/DESCRIPTION_obsgermany_climate_hourly_solar_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/solar/)                                                                                                                                                                  |

#### parameters

| name                                     | original name | description                               | unit  | constraints |
|------------------------------------------|---------------|-------------------------------------------|-------|-------------|
| {term}`radiation_sky_long_wave` | atmo_lberg | Hourly sum of longwave downward radiation. | J/cm² | >=0 |
| {term}`radiation_sky_short_wave_diffuse` | fd_lberg | Hourly sum of diffuse solar radiation. | J/cm² | >=0 |
| {term}`radiation_global` | fg_lberg | The solar incoming radiation includes the direct and the diffuse part of the solar radiation with respect to the horizontal plane. It is sometimes also referred to as shortwave, including the solar spectrum up to 2.8 micron, as opposed to longwave , which refers to the thermal radiation of the atmosphere. | J/cm² | >=0 |
| {term}`sunshine_duration` | sd_lberg | Hourly sum of sunshine duration. | min | >=0 |
| {term}`sun_zenith_angle` | zenit | Solar zenith angle at mid of interval. The solar zenith angle is between 0-180 and is defined as: ZENIT= 90 - solar_height. | ° | >=0,<=180 |
| {term}`true_local_time_offset` | mess_datum_woz | Local true solar time, published as a whole timestamp and returned as its distance from the timestamp of the record: the longitude correction plus the equation of time. | min | - |

### sun

#### metadata

| property      | value                                                                                                                                                                                                              |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | sun                                                                                                                                                                                                                |
| original name | sun                                                                                                                                                                                                                |
| description   | Hourly station observations of sunshine duration for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/DESCRIPTION_obsgermany_climate_hourly_sun_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/sun/)                                                                                                                   |

#### parameters

| name                      | original name | description              | unit | constraints |
|---------------------------|---------------|--------------------------|------|-------------|
| {term}`sunshine_duration` | sd_so | Hourly sunshine duration. The stamps of the periods that DWD's Metadaten_Parameter calls "Stundenwerte in WOZ" (the older periods of 528 of 636 stations, at some of them to 2006) are the hour of the station's local true solar time, not UTC: they are returned as written, not shifted, and their `quality_flags` carry `zone:woz` (`10,zone:woz`). The other stamps are UTC. | min | >=0 |

### temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                                     |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_air                                                                                                                                                                                                                                           |
| original name | air_temperature                                                                                                                                                                                                                                           |
| description   | Hourly station observations of 2 m air temperature and humidity for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/DESCRIPTION_obsgermany_climate_hourly_air_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/)                                                                                                                                              |

#### parameters

| name                            | original name | description          | unit | constraints |
|---------------------------------|---------------|----------------------|------|-------------|
| {term}`temperature_air_2m`      | tt_tu | Air temperature 2 m above ground. The stamps of the periods that DWD's Metadaten_Parameter calls "Stundenwerte in MEZ (MD)" (the eMD archive of 80 East German stations, up to 1991) are MEZ, UTC+1: they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`), and so are those of Diepholz from the stamp 1995-02-01 00 to the stamp 1996-05-31 23, Nürnberg from 1986-01-01 01 to 1988-11-01 00, Frankfurt/Main from 1990-05-01 01 to 1990-06-01 00, Trier-Petrisberg from 1989-08-01 01 to 1989-09-01 00 and Bremen from 1990-11-01 01 to 1991-03-01 00, periods the label calls plain MEZ that are MEZ in the values. So are the 808 station-months of 26 stations that an ISD offset fit and a diurnal-phase test both find in MEZ under each of the six one-at-a-time variants of the scan's constants (a full grid keeps 748), as blocks of whole UTC days (1955 to 1997, almost all before 1991; the table is `mez_blocks.csv`, GH-3776); of the 1973-01 to 1975-12 batch at 13 stations the shift is the 1 h of the clock, and the analog recorder's lag (about 0.4 h at 8 of them) stays in the values, flagged `zone:mez-1973-75`. The 1,316 station-months of 17 East German stations whose `MEZ (MD)` stamps are in the local time of the station's longitude (UTC plus the longitude over 15, 0.6 to 0.9 h: 1952 to 1961 at 16 stations, Potsdam 1973-01 to 1975-05, GH-3910) are shifted by the same hour and so are still 0.2 to 0.5 h early; their rows carry a `zone` token of their own instead of `zone:mez` (the legend of `quality_flags` names it). The other stamps are UTC. | °C | - |
| {term}`humidity_relative` | rf_tu | Relative humidity. The stamps of the periods that DWD's Metadaten_Parameter calls "Stundenwerte in MEZ (MD)" (the eMD archive of 76 East German stations, up to 1991) are MEZ, UTC+1: they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`), and so are those of Diepholz from the stamp 1995-02-01 00 to the stamp 1996-05-31 23, Nürnberg from 1986-01-01 01 to 1988-11-01 00, Frankfurt/Main from 1990-05-01 01 to 1990-06-01 00, Trier-Petrisberg from 1989-08-01 01 to 1989-09-01 00 and Bremen from 1990-11-01 01 to 1991-03-01 00, periods the label calls plain MEZ that are MEZ in the values. So are the 808 station-months of 26 stations that an ISD offset fit and a diurnal-phase test both find in MEZ under each of the six one-at-a-time variants of the scan's constants (a full grid keeps 748), as blocks of whole UTC days (1955 to 1997, almost all before 1991; the table is `mez_blocks.csv`, GH-3776); of the 1973-01 to 1975-12 batch at 13 stations the shift is the 1 h of the clock, and the analog recorder's lag (about 0.4 h at 8 of them) stays in the values, flagged `zone:mez-1973-75`. The 1,316 station-months of 17 East German stations whose `MEZ (MD)` stamps are in the local time of the station's longitude (UTC plus the longitude over 15, 0.6 to 0.9 h: 1952 to 1961 at 16 stations, Potsdam 1973-01 to 1975-05, GH-3910) are shifted by the same hour and so are still 0.2 to 0.5 h early; their rows carry a `zone` token of their own instead of `zone:mez` (the legend of `quality_flags` names it). The other stamps are UTC. | % | >=0,<=100 |

#### time reference

The stamps of the analog periods that DWD's `Metadaten_Parameter` calls plain `Stundenwerte in MEZ` (160 stations, to
2005) are UTC at most stations and in most months, and MEZ (UTC+1) in some. The label does not tell which, so the values
are shifted only where two methods that do not depend on each other agree
([#3776](https://github.com/earthobservations/wetterdienst/issues/3776)).

**Why a second source.** NOAA ISD holds the SYNOP reports of about 60 West German stations from 1955, three-hourly
(00, 03, ..., 21 UTC) before 1973 and hourly at some stations from 1973; the East German stations are in it too: the
10xxxx files (WMO block 10) hold FM-12 SYNOP at 00, 06, 12 and 18 UTC from 1952 (the 09xxxx files only from 1973 or
1976). The check of the hourly values against ISD that settled Diepholz, Nürnberg and the others (a month is at lag 0 or lag -1
where at least 85 % of its hours equal ISD's) cannot decide an analog year, as the chart values are not the SYNOP
readings: they are equal in about 20 % of the hours even at the right lag.

**The two methods**, each a verdict per station-month through a two-state UTC/MEZ forward-backward model:

- the ISD fractional-offset fit: the hourly values interpolated to the time of each ISD report and shifted by an offset
  delta (hours, a 0.1 h grid), the mean absolute difference least. UTC stations sit at delta -0.3 +- 0.2 h, MEZ ones at
  -0.8 to -1.3 h;
- the diurnal-phase test: the hour of the maximum of the first harmonic of the month's mean diurnal cycle against the
  same station's ISD-verified UTC months (or, with none, a pooled absolute profile). A clock shift of 1 h moves it by
  +0.9 to +1.3 h, the analog instrument by 0 to +0.4 h.

**The rule.** The scan of 2026-11-08 read all 160 stations (47,073 station-months, 1941 to 2005). Both methods say MEZ
in 996 months at 30 stations, 854 of them under each of the six one-at-a-time variants of the constants of the model (the base, and
one of the MEZ shift 0.8 or 1.2 h instead of 1.0, the probability of a switch 0.01 or 0.08 instead of 0.03, the
posterior threshold 0.8 or 0.97 instead of 0.9 changed at a time; a full grid of all 27 combinations keeps 748). Those 854 are shifted by -1 h and
flagged `zone:mez`: 46 of them were shifted already (Nürnberg 1986-02 to 1988-10 and Diepholz 1995-04 to 1996-05), so
the new blocks are 808 station-months at 26 stations, as `mez_blocks.csv` lists them (station, first and last month,
confidence, ISD delta and phase step; the largest are Regensburg 1979-12 to 1985-10, Nürnberg 1968-08 to 1971-11 and
Bremen 1973-01 to 1975-12). A block is whole UTC days, from the stamp 01 of its first day to the stamp 00 after its last
month, as the blocks above. The first moved row lands on the stamp 00 before the block, which the file has: the row that was moved is kept and
the other dropped, so a stamp never holds two rows. The hour after the block has no row, as the file has none. The humidity is shifted with the temperature: the
scan tested the temperature only, and both come from one logger.

**The batch of 1973-01 to 1975-12.** At 13 stations (Berlin-Alexanderplatz, Bremen, Feldberg/Schwarzwald, Freiburg,
Garmisch-Partenkirchen, Hannover, Kiel-Kronshagen, Lüchow, Norderney, Nürnberg, Osnabrück, Bad Salzuflen and Bocholt)
at least 12 of the 36 months are MEZ by both methods in the base run of the scan (before the cut to the robust core, which
leaves Norderney 9 months and Berlin-Alexanderplatz 12 in three pieces, and six stations all 36). The edges of the
batch fall on calendar boundaries, which looks like a processing batch. At 8 of the 13 both measures exceed 1 h (ISD
delta -1.4 to -1.6 h, phase step +1.2 to +1.5 h); Bad Salzuflen, Osnabrück and Feldberg sit at about -1.0 h. The clock
offset of MEZ is exactly 1 h, so the values are shifted by 1 h like the others and about 0.4 h remains at those 8: the
analog recorder's own lag, which stays in the values as in every other analog year. The rows are flagged `zone:mez-1973-75` instead of `zone:mez`, so that a
caller can leave them out.

**What stays as served.** The months that one method alone calls MEZ (3,135 months: ISD alone 428, the phase test alone
297 where ISD says UTC and 2,145 at 58 stations with no ISD value), those that both call MEZ under some variant only
(142 of the 996), and the undecided ones (3,193 months) are returned as written, UTC. ISD alone says MEZ from 1979-09 to
1980-10 at eight stations at once (Bremen, Nürnberg, Hamburg, Ingolstadt, Landsberg, Frankfurt Stadt, Ulm, Kaufbeuren)
where the phase test says UTC or is undecided, probably an ISD artefact. Winter boundaries (November to February) are
uncertain by 1 to 3 months; a month between two blocks that is not in the table stays as written, so a series can change
its clock at such a month. The phase test finds none of the blocks of one to four months of Frankfurt, Trier and Bremen.
The East German `MEZ (MD)` periods are not in the scan: they are shifted by the label, and that shift
is checked against ISD below. A caller who wants the series as DWD wrote it reads the rows flagged `zone:mez`,
`zone:mez-1973-75` or `zone:mez-local-mean-time` one hour later.

**The East German `MEZ (MD)` periods before 1962 and mean local time**
([#3910](https://github.com/earthobservations/wetterdienst/issues/3910)). Is the shift by -1 h of these periods right
before about 1970? The offset of the raw stamps to the ISD reports, fitted as above at 41 stations before 1976 (344
station-years) and at 47 in 1976 to 1991 (557 station-years), is -1.0 h in every year from 1962 to 1991 at every
station with an ISD twin (Potsdam: from 1975-06), and no station-year is UTC: from 1962 (Potsdam from 1975-06) the shift
is right to the whole hour. The diurnal phase against the station's own MEZ years of 1976 to 1990 (it steps by 0.3 to
0.6 h at 15 stations in 1962, by 1.0 h at none), the correlation of the first differences with the West German stations
that ISD confirms as UTC and the term files of DWD (from 1967-01 the hourly stamp S+1 equals the term S; at Potsdam from
1975-06) agree. One exception: in 1952 to 1961 at 16 stations in the west and centre (10.1 to 13.0 degrees east:
Brocken, Kaltennordheim, Sonneberg, Gardelegen, Schwerin, Weimar, Plauen, Rostock-Warnemünde, Halle-Kröllwitz,
Wernigerode, Leipzig-Holzhausen, Magdeburg, Leinefelde, Wittenberg, Chemnitz and Fichtelberg) and at Potsdam from
1973-01 to 1975-05 the offset is -0.5 to -0.8 h, ordered by longitude, so the stamps are the mean local time of the
station (UTC plus the longitude over 15, 0.6 to 0.9 h; a slope of -0.096 h per degree against -0.067, no pattern of the
equation of time, so mean and not true solar time), not MEZ. The regime begins at six stations in 1952-01 or 1952-02
and at the others between 1952-11 and 1957-05, and ends at all of them but Potsdam on
1962-01-01 (the monthly offset jumps at Brocken, Kaltennordheim and Magdeburg, the phase at 15 more); ISD ends at most
of them in 1960 or 1961, so the table stops there and the months up to 1961-12 that it does not hold are not flagged.

The shift by -1 h leaves these stamps 0.2 to 0.5 h early (the median is 0.3 h), which an hourly grid cannot correct, and
no shift would be better (0.6 to 0.9 h wrong). Values and timestamps are therefore not changed. The 1,316 station-months
(25 blocks, `local_mean_time_blocks.csv`: station, first and last month, the ISD offset, the phase against the MEZ years
and how early the stamp stays) are flagged `zone:mez-local-mean-time` instead of `zone:mez`. The months before 1951 at
Potsdam, Rostock-Warnemünde and Wahnsdorf were not checked against ISD, and winter boundaries are uncertain by 1 to 3
months. One block of the research is left out: Gardelegen 1952-01 to 1952-05 (5 months). Its own evidence is MEZ (the
ISD offset is -1.00 h, the stamp is not early, the phase equals that of the MEZ months next to it); the label "local
time" came from the switch penalty of the research's three-state model, and the months are `zone:mez`. A caller who
needs the hour exactly leaves the flagged rows out.

### temperature_soil

#### metadata

| property      | value                                                                                                                                                                                                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | temperature_soil                                                                                                                                                                                                                               |
| original name | soil_temperature                                                                                                                                                                                                                               |
| description   | Hourly station observations of soil temperature for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/soil_temperature/DESCRIPTION_obsgermany_climate_hourly_soil_temperature_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/soil_temperature/)                                                                                                                                  |

#### parameters

| name                                | original name | description                      | unit | constraints |
|-------------------------------------|---------------|----------------------------------|------|-------------|
| {term}`temperature_soil_0_02m`      | v_te002 | Soil temperature in 2 cm depth. Only the historical files carry a value, up to 2019: recent holds none. The stamps of the periods whose source DWD's Metadaten_Parameter gives as the archive of the eMD (74 East German stations, up to 1991, the terms 01, 04, ..., 22 MEZ) are MEZ, UTC+1: they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`). The other stamps are as written. | °C | - |
| {term}`temperature_soil_0_05m`      | v_te005 | Soil temperature in 5 cm depth. The stamps of the periods whose source DWD's Metadaten_Parameter gives as the archive of the eMD (74 East German stations, up to 1991, the terms 01, 04, ..., 22 MEZ) are MEZ, UTC+1: they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`). The other stamps are as written. | °C | - |
| {term}`temperature_soil_0_1m`      | v_te010 | Soil temperature in 10 cm depth. The stamps of the periods whose source DWD's Metadaten_Parameter gives as the archive of the eMD (74 East German stations, up to 1991, the terms 01, 04, ..., 22 MEZ) are MEZ, UTC+1: they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`). The other stamps are as written. | °C | - |
| {term}`temperature_soil_0_2m`      | v_te020 | Soil temperature in 20 cm depth. The stamps of the periods whose source DWD's Metadaten_Parameter gives as the archive of the eMD (74 East German stations, up to 1991, the terms 01, 04, ..., 22 MEZ) are MEZ, UTC+1: they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`). The other stamps are as written. | °C | - |
| {term}`temperature_soil_0_5m`      | v_te050 | Soil temperature in 50 cm depth. The stamps of the periods whose source DWD's Metadaten_Parameter gives as the archive of the eMD (74 East German stations, up to 1991, the terms 01, 04, ..., 22 MEZ) are MEZ, UTC+1: they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`). The other stamps are as written. | °C | - |
| {term}`temperature_soil_1m`      | v_te100 | Soil temperature in 100 cm depth. The stamps of the periods whose source DWD's Metadaten_Parameter gives as the archive of the eMD (74 East German stations, up to 1991, the terms 01, 04, ..., 22 MEZ) are MEZ, UTC+1: they are shifted to UTC and their `quality_flags` carry `zone:mez` (`3,zone:mez`). The other stamps are as written. | °C | - |

### urban_precipitation

#### metadata

| property      | value                                                                                                                                                                                                                                                                                           |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_precipitation                                                                                                                                                                                                                                                                             |
| original name | precipitation (climate_urban)                                                                                                                                                                                                                                                                   |
| description   | Recent hourly precipitation, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/precipitation/recent/DESCRIPTION_obsgermany_climate_urban_hourly_precipitation_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/precipitation/)                                                                                                                                                                                |

#### parameters

| name                         | original name      | description          | unit | constraints |
|------------------------------|--------------------|----------------------|------|-------------|
| {term}`precipitation_amount` | niederschlagshoehe | Precipitation height, the sum of the six 10-minute intervals of the previous hour (at UTC 11 the sum of the precipitation during UTC10-UTC11). | mm | >=0 |

### urban_pressure

#### metadata

| property      | value                                                                                                                                                                                                                                                                            |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_pressure                                                                                                                                                                                                                                                                   |
| original name | pressure (climate_urban)                                                                                                                                                                                                                                                         |
| description   | Recent hourly pressure, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/pressure/recent/DESCRIPTION_obsgermany_climate_urban_hourly_pressure_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/pressure/)                                                                                                                                                                      |

#### parameters

| name                           | original name           | description                        | unit | constraints |
|--------------------------------|-------------------------|------------------------------------|------|-------------|
| {term}`pressure_air_sea_level` | luftdruck_nn            | Air pressure reduced to sea level. DWD's German sheet says for all pressure values: "Stündliche Druckwerte sind entsprechend den SYNOP-Konventionen abgelegt. Dabei wird der Stunde x der Messwert von 10 min vorher zugeordnet" (at UTC 11 the value from UTC 10:50); the English sheet names the station height only. Confirmed at Berlin-Alexanderplatz (00399), the network's only station: it equals the 10-minute value of the stamp minus 10 min in 93,898 of 93,898 hours, 2015-08 to 2026-11. | hPa  | >=0         |
| {term}`pressure_air_site`      | luftdruck_stationshoehe | Pressure at station height, following the SYNOP conventions: the hour x corresponds to the measurement from 10 min before (at UTC 11 the value from UTC 10:50). | hPa  | >=0         |

### urban_temperature_air

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                 |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_air                                                                                                                                                                                                                                                                                 |
| original name | air_temperature (climate_urban)                                                                                                                                                                                                                                                                       |
| description   | Recent hourly air temperature and humidity, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/recent/DESCRIPTION_obsgermany_climate_urban_hourly_tu_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/air_temperature/)                                                                                                                                                                                    |

#### parameters

| name                            | original name  | description          | unit | constraints |
|---------------------------------|----------------|----------------------|------|-------------|
| {term}`temperature_air_2m`      | lufttemperatur | 2m air temperature, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | °C   | -           |
| {term}`humidity_relative`       | rel_feuchte    | 2m relative humidity, following the SYNOP conventions: at UTC 11 the mean value of the 1 minute interval ending UTC 10:50 is given. | %    | >=0,<=100   |

### urban_temperature_soil

#### metadata

| property      | value                                                                                                                                                                                                                                                                                                    |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_temperature_soil                                                                                                                                                                                                                                                                                   |
| original name | soil_temperature (climate_urban)                                                                                                                                                                                                                                                                         |
| description   | Recent hourly soil temperature, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/soil_temperature/recent/DESCRIPTION_obsgermany_climate_urban_hourly_soil_temperature_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/soil_temperature/)                                                                                                                                                                                      |

#### parameters

| name                                | original name | description                      | unit | constraints |
|-------------------------------------|---------------|----------------------------------|------|-------------|
| {term}`temperature_soil_0_05m`      | erdbt_005 | Soil temperature in 5 cm depth. DWD's sheet: the hour x holds the mean value of the 1 minute interval ending 10 min before (at UTC 11, ending UTC 10:50). Contradicted at Berlin-Alexanderplatz (00399), the network's only station: the value stamped H equals the instantaneous 10-minute value of H:50, 50 min after the stamp (10 to 100 cm, 93,038 of 93,038 hours, 2015-08 to 2026-11), so wetterdienst leaves the position null. | °C | - |
| {term}`temperature_soil_0_1m`      | erdbt_010 | Soil temperature in 10 cm depth. DWD's sheet: the hour x holds the mean value of the 1 minute interval ending 10 min before (at UTC 11, ending UTC 10:50). Contradicted at Berlin-Alexanderplatz (00399), the network's only station: the value stamped H equals the instantaneous 10-minute value of H:50, 50 min after the stamp (10 to 100 cm, 93,038 of 93,038 hours, 2015-08 to 2026-11), so wetterdienst leaves the position null. | °C | - |
| {term}`temperature_soil_0_2m`      | erdbt_020 | Soil temperature in 20 cm depth. DWD's sheet: the hour x holds the mean value of the 1 minute interval ending 10 min before (at UTC 11, ending UTC 10:50). Contradicted at Berlin-Alexanderplatz (00399), the network's only station: the value stamped H equals the instantaneous 10-minute value of H:50, 50 min after the stamp (10 to 100 cm, 93,038 of 93,038 hours, 2015-08 to 2026-11), so wetterdienst leaves the position null. | °C | - |
| {term}`temperature_soil_0_5m`      | erdbt_050 | Soil temperature in 50 cm depth. DWD's sheet: the hour x holds the mean value of the 1 minute interval ending 10 min before (at UTC 11, ending UTC 10:50). Contradicted at Berlin-Alexanderplatz (00399), the network's only station: the value stamped H equals the instantaneous 10-minute value of H:50, 50 min after the stamp (10 to 100 cm, 93,038 of 93,038 hours, 2015-08 to 2026-11), so wetterdienst leaves the position null. | °C | - |
| {term}`temperature_soil_1m`      | erdbt_100 | Soil temperature in 100 cm depth. DWD's sheet: the hour x holds the mean value of the 1 minute interval ending 10 min before (at UTC 11, ending UTC 10:50). Contradicted at Berlin-Alexanderplatz (00399), the network's only station: the value stamped H equals the instantaneous 10-minute value of H:50, 50 min after the stamp (10 to 100 cm, 93,038 of 93,038 hours, 2015-08 to 2026-11), so wetterdienst leaves the position null. | °C | - |

### urban_sun

#### metadata

| property      | value                                                                                                                                                                                                                                                                           |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_sun                                                                                                                                                                                                                                                                       |
| original name | sun (climate_urban)                                                                                                                                                                                                                                                             |
| description   | Recent hourly sunshine duration, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/sun/recent/DESCRIPTION_obsgermany_climate_urban_hourly_sun_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/sun/)                                                                                                                                                                          |

#### parameters

| name                      | original name     | description       | unit | constraints |
|---------------------------|-------------------|-------------------|------|-------------|
| {term}`sunshine_duration` | sonnenscheindauer | Sunshine duration, the sum of the six 10-minute intervals of the previous hour (at UTC 11 the sum of the sunshine during UTC10-UTC11). | min | >=0 |

### urban_wind

#### metadata

| property      | value                                                                                                                                                                                                                                                                                    |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | urban_wind                                                                                                                                                                                                                                                                               |
| original name | wind (climate_urban)                                                                                                                                                                                                                                                                     |
| description   | Recent hourly wind speed and direction, observed at urban stations for selected urban areas in Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/recent/DESCRIPTION_obsgermany_climate_urban_hourly_wind_recent_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/hourly/wind/)                                                                                                                                                                                  |

#### parameters

| name                   | original name       | description         | unit | constraints |
|------------------------|---------------------|---------------------|------|-------------|
| {term}`wind_speed_mean` | windgeschwindigkeit | Mean wind speed, the average of the six 10-minute intervals of the previous hour (at UTC 11 the average during UTC10-UTC11). DWD's sheet: measured at 368 m on Berlin's television tower (the other urban stations have their own sensor heights). | m/s | >=0 |
| {term}`wind_direction_mean` | windrichtung | Mean wind direction, the average of the six 10-minute intervals of the previous hour (at UTC 11 the average during UTC10-UTC11). DWD's sheet: measured at 368 m on Berlin's television tower (the other urban stations have their own sensor heights). The source's 0 comes with a wind speed above 0 and with six 10-minute directions spread over the compass, so it is neither a calm nor north (written 360) and is null. | ° | >=0,<=360 |

### visibility

#### metadata

| property      | value                                                                                                                                                                                                                     |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | visibility                                                                                                                                                                                                                |
| original name | visibility                                                                                                                                                                                                                |
| description   | Hourly station observations of visibility for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/DESCRIPTION_obsgermany_climate_hourly_visibility_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/visibility/)                                                                                                                   |

#### parameters

| name                           | original name | description                    | unit | constraints |
|--------------------------------|---------------|--------------------------------|------|-------------|
| {term}`visibility_measurement_method` | v_vv_i | Visibility index, noting how the measurement is taken,P=by human person,I=by an instrument. Returned as 1 for P and 2 for I. | - | ∈ {1, 2} |
| {term}`visibility` | v_vv | Visibility range. | m | >=0 |

Codes (visibility_measurement_method):

| value | source letter | meaning         |
|-------|---------------|-----------------|
| 1     | P             | by human person |
| 2     | I             | by instrument   |

### weather_phenomena

#### metadata

| property      | value                                                                                                                                                                                                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | weather_phenomena                                                                                                                                                                                                                              |
| original name | weather_phenomena                                                                                                                                                                                                                              |
| description   | Hourly station observations of weather phenomena for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/DESCRIPTION_obsgermany_climate_hourly_weather_phenomena_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/)                                                                                                                                 |

#### parameters

| name                 | original name | description                       | unit | constraints |
|----------------------|---------------|-----------------------------------|------|-------------|
| {term}`weather` | ww | Present weather code (for 20-29 and 120-126 that of the past hour). One column holds two tables with disjoint numbers: 0-99 is WMO code table 4677 (ww, manned stations), 100-199 is WMO code table 4680 (wawa, automatic stations) with 100 added. A station's historical file holds either or both, the recent file of an automated station only 100-199. The meaning of every code is in DWD's Wetter_Beschreibung.txt, the text its WW_Text column repeats. The source's -1 (weather not reported) is null. | - | - |

weather codes and descriptions: [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/weather_phenomena/recent/Wetter_Beschreibung.txt)

### wind

#### metadata

| property      | value                                                                                                                                                                                                                                            |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind                                                                                                                                                                                                                                             |
| original name | wind                                                                                                                                                                                                                                             |
| description   | Hourly mean value from station observations of wind speed and wind direction for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind/DESCRIPTION_obsgermany_climate_hourly_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind/)                                                                                                                                                |

#### parameters

| name                   | original name | description         | unit | constraints |
|------------------------|---------------|---------------------|------|-------------|
| {term}`wind_speed_mean` | f | Mean wind speed. | m/s | >=0 |
| {term}`wind_direction_mean` | d | Mean wind direction. The source's 0 beside a wind speed of 0 (a calm wind) is null; a 0 beside a wind that blows stays. | ° | >=0,<=360 |

### wind_extreme

#### metadata

| property      | value                                                                                                                                                                                                                                           |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_extreme                                                                                                                                                                                                                                    |
| original name | extreme_wind                                                                                                                                                                                                                                    |
| description   | Hourly maximum value from station observations of windspeed for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/extreme_wind/DESCRIPTION_obsgermany_climate_hourly_extreme_wind_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/extreme_wind/)                                                                                                                                       |

#### parameters

| name                  | original name | description                      | unit | constraints |
|-----------------------|---------------|----------------------------------|------|-------------|
| {term}`wind_gust_max` | fx_911 | Wind speed, wind gust: the highest wind peak of the last hour. | m/s | >=0 |

### wind_synoptic

#### metadata

| property      | value                                                                                                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | wind_synoptic                                                                                                                                                                                                                                |
| original name | wind_synop                                                                                                                                                                                                                                   |
| description   | Hourly station observations of wind speed and wind direction for Germany ([details](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind_synop/DESCRIPTION_obsgermany_climate_hourly_wind_synop_en.pdf)) |
| access        | [here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind_synop/)                                                                                                                                      |

#### parameters

| name                   | original name | description         | unit | constraints |
|------------------------|---------------|---------------------|------|-------------|
| {term}`wind_speed_mean_last_10min` | ff | 10-minute mean of the wind speed (DWD: "10-Min-Mittel der Windgeschwindigkeit"): the mean of the 10 minutes (T-20, T-10] from 2001-04-01 and (T-30, T-20] from 1995 to 2001-03-31 (1991-1994 not one offset, 0 to 30 min), T the stamp, measured against the 10-minute series of the same station; before 1991 the report of the stamp hour where NOAA ISD holds DWD's report (Stuttgart 1949-1965: 0.5 to 0.8 h before an independent USAF record). Times are UTC. | m/s | >=0 |
| {term}`wind_direction` | dd | Wind direction (DWD: "Windrichtung uml.,windstill DD=00"). The source's 0 (a calm or variable wind) is null. | ° | >=0,<=360 |
