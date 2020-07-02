# Folder structure of dwd ftp server ###

[LINK TO DWD](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate)

| Timescale | Variable | Abbrevation | Period | Filename |
| --- | --- | --- | --- | --- |
| 10_minutes | air_temperature <br> extreme_temperature <br> extreme_wind <br> precipitation <br> solar wind | tu/TU/TU <br> tx/extrema_temp/extrema_temp <br> fx/extrema_wind/extrema_wind <br> rr/nieder/nieder <br> solar/SOLAR/SOLAR <br> ff/wind/wind | hist (= historical) <br> akt (= recent) <br> now | 10minutenwerte + abbrv. + statid + startdate + enddate + period |
| 1_minute | precipitation | nieder/nieder/nieder | hist (= historical) <br> akt (= recent) <br> now | YYYY/ 1minutenwerte + abbrv. + statid + startdate + enddate + period <br> 1minutenwerte + abbrv. + statid + startdate + enddate + period <br> 1minutenwerte + abbrv. + statid + startdate + enddate + period |
| annual | kl <br> more_precip | KL/KL <br> RR/RR | hist (= historical) <br> akt (= recent) | jahreswerte + abbrv. + statid + startdate + enddate + period <br> jahreswerte + abbrv. + statid + period |
| daily | kl <br> more_precip <br> soil_temperature <br> solar <br> water_equiv | KL/KL <br> RR/RR <br> EB/EB <br> ST/ST <br> Wa/Wa | hist (= historical) <br> akt (= recent) <br><br> now | tageswerte + abbrv. + statid + startdate + enddate + period <br> tageswerte + abbrv. + statid + period <br><br> tageswerte + abbrv. + statid + period |
| hourly | air_temperature <br> cloud_type <br> cloudiness <br> precipitation <br> pressure <br> soil_temperature <br> solar <br> sun <br> visibility <br> wind | TU/TU <br> CS/CS <br> N/N <br> RR/RR <br> P0/P0 <br> EB/EB <br> ST/ST <br> SD/SD <br> VV/VV <br> FF/FF | hist (= historical) <br> akt (= recent) | stundenwerte + abbrv. + statid + startdate + enddate + period stundenwerte + abbrv. + statid + period |
| monthly | kl <br> more_precip | KL/KL <br> RR/RR | hist (= historical) <br> akt (= recent) | monatswerte + abbrv. + statid + startdate + enddate + period <br> monatswerte + abbrv. + statid + period |
