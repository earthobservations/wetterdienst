### folder structure of dwd ftp server ###
main: ftp://ftp-cdc.dwd.de/pub/CDC/observations_germany/climate/

| Timescale    | Variable              |   Abbrevation                     |   Period              |   Filename |
|--------------|-----------------------|-----------------------------------|-----------------------|-------------------------------------------------------------------------|
| 10_minutes   | air_temperature       |   tu/TU/TU                        |   hist (= historical) |   10minutenwerte + abbrv. + statid + startdate + enddate + period       |
|              | extreme_temperature   |   tx/extrema_temp/extrema_temp    |   akt (= recent)      |   10minutenwerte + abbrv. + statid + period                             |
|              | extreme_wind          |   fx/extrema_wind/extrema_wind    |   now                 |                                                                         |
|              | precipitation         |   rr/nieder/nieder                |                       |                                                                         |
|              | solar                 |   solar/SOLAR/SOLAR               |                       |                                                                         |
|              | wind                  |   ff/wind/wind                    |                       |                                                                         |
|--------------|-----------------------|-----------------------------------|-----------------------|-------------------------------------------------------------------------|
| 1_minute     | precipitation         |   nieder/nieder/nieder            |   hist (= historical) |   YYYY/ 1minutenwerte + abbrv. + statid + startdate + enddate + period  |
|              |                       |                                   |   akt (= recent)      |   1minutenwerte + abbrv. + statid + startdate + enddate + period        |
|              |                       |                                   |   now                 |   1minutenwerte + abbrv. + statid + startdate + enddate + period        |
|--------------|-----------------------|-----------------------------------|-----------------------|-------------------------------------------------------------------------|
| annual       | kl                    |   KL/KL                           |   hist (= historical) |   jahreswerte + abbrv. + statid + startdate + enddate + period          |
|              | more_precip           |   RR/RR                           |   akt (= recent)      |   jahreswerte + abbrv. + statid + period                                |
|--------------|-----------------------|-----------------------------------|-----------------------|-------------------------------------------------------------------------|
| daily        | kl                    |   KL/KL                           |   hist (= historical) |   tageswerte + abbrv. + statid + startdate + enddate + period           |
|              | more_precip           |   RR/RR                           |   akt (= recent)      |   tageswerte + abbrv. + statid + period                                 |
|              | soil_temperature      |   EB/EB                           |                       |                                                                         |
|              | solar                 |   ST/ST                           |   now                 |   tageswerte + abbrv. + statid + period                                 |
|              | water_equiv           |   Wa/Wa                           |                       |                                                                         |
|--------------|-----------------------------------------------------------|-----------------------|-------------------------------------------------------------------------|
| hourly       | air_temperature       |   TU/TU                           |   hist (= historical) |   stundenwerte + abbrv. + statid + startdate + enddate + period         |
|              | cloud_type            |   CS/CS                           |   akt (= recent)      |   stundenwerte + abbrv. + statid + period                               |
|              | cloudiness            |   N/N                             |                       |                                                                         |
|              | precipitation         |   RR/RR                           |                       |                                                                         |
|              | pressure              |   P0/P0                           |                       |                                                                         |
|              | soil_temperature      |   EB/EB                           |                       |                                                                         |
|              | solar                 |   ST/ST                           |                       |                                                                         |
|              | sun                   |   SD/SD                           |                       |                                                                         |
|              | visibility            |   VV/VV                           |                       |                                                                         |
|              | wind                  |   FF/FF                           |                       |                                                                         |
|--------------|-----------------------|-----------------------------------|-----------------------|-------------------------------------------------------------------------|
| monthly      | kl                    |   KL/KL                           |   hist (= historical) |   monatswerte + abbrv. + statid + startdate + enddate + period          |
|              | more_precip           |   RR/RR                           |   akt (= recent)      |   monatswerte + abbrv. + statid + period                                |
