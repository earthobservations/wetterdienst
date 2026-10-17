# Quality flags

Every reading has one string column, `quality_flags` (in the wide shape `<parameter>_quality_flags`),
holding the flags its source publishes for it. It is null where the source gives none, which is the
case for every provider not listed below. Interpolated and summarized results have no such column, as
they are made of several stations' readings. The sources call the field by many names (DWD `QN`,
MIDAS `MESQL`, ECCC `Flag`, SMHI `Kvalitet`, GHCN `QFLAG`, NWS `qualityControl`, Frost `qualityCode`, Hubeau
`code_qualification_obs`, Météo-France `Q<parameter>`) and the meaning of a code differs from provider to
provider, so a code from one says nothing about one from another; none is a scale of better and worse
unless the table says so.

- A source with one flag: its plain code as the source writes it, only trimmed (`T`, `Good`, `3`).
- A source with several kinds of flag: the ordinary quality flag first as a plain code, then every other
  kind as `kind:code`, comma-separated, in a fixed order per provider (`G,measurement:T,source:7`,
  `3,element:E`). A blank flag is left out, so a plain token is always the quality flag, and
  `measurement:T` alone is a reading whose quality flag is blank.
- A value the provider maps from a missing-value sentinel carries the text the source wrote for it as the
  last token, `raw:<text>`, after the quality flag and the other kinds (`3,raw:-999`, `raw:-99.0`,
  `raw:NaN`). The value is null, or what the source documents the code to stand for (`0.0` for a
  precipitation of `-1.0`), and the text stays beside it. It is the cell as the source writes it, `-999.0`
  where the source writes that; where the value comes as a JSON number the text is the one the provider
  declares. The long shape drops the rows without a value by default, so the token shows with
  `drop_nulls=False` or in the wide shape; a filter on a null `quality_flags` as "no flag" meets
  these rows then.
- A value outside the physical range of its parameter that is no code (4021 degrees for a daily
  maximum, 17,802 mm for a month of rain) is treated the same way where the second table below names the
  provider: null, with `raw:<number>` as the last token, the number as short as it can be written
  (`raw:4021`, `raw:110.26`). The ranges are generous and, for the rain and the sunshine of a span,
  grow with the resolution (what is no reading of a minute is one of a day), so a value that is only odd
  stays.
- `str.split(",")` takes the tokens apart; where a numeric code was used before, cast it:
  `pl.col("quality_flags").cast(pl.Int64, strict=False)`; a code that is no number (IMGW's `Z`) and a
  value with several tokens become null, so take the first token of a code that can be followed by
  `raw:` or a further kind: `pl.col("quality_flags").str.split(",").list.first().cast(pl.Int64, strict=False)`. The sentinel of a reading is
  `pl.col("quality_flags").str.extract(r"raw:([^,]*)$")`.

The first table lists the plain codes and the further kinds; the `raw:` tokens are in the second one, below it.

| Provider | codes in `quality_flags` |
| --- | --- |
| DWD observation | `QN`, the quality control level of the file's row: `1` only formal control, `2` controlled with individually defined criteria, `3` automatic control and correction, `5` historic, subjective procedures, `7` second control done, before correction, `8` quality control outside routine, `9` not all parameters corrected, `10` quality control finished (data up to 1980 reach `5` at best; 10 minutes data `1` to `3`). A larger number is a more thorough check. Hourly `sun` adds `zone:woz` for a stamp of a period in the station's local true solar time, not UTC (`10,zone:woz`). Hourly `temperature_air` adds `zone:mez` for a stamp that was MEZ, UTC+1, in a period DWD's Metadaten_Parameter calls "Stundenwerte in MEZ (MD)" and is returned shifted to UTC (`3,zone:mez`). `DwdObservationRequest.describe_fields` prints the table of a dataset |
| DWD derived | hourly `radiation_global` and `sunshine_duration` (DUETT, `QN_952`): `500` DUETT data without station and satellite data, `501` on station data only, `502` on satellite data only, `503` on station and satellite data; the other derived datasets: null |
| DWD phenology | `Qualitaetsniveau`: `1` formal check only, `7` checked in routine but uncorrected, `10` checked and corrected |
| DWD road | the station's own verdict, from `qualityInformationAwsData`, or this library's: `1` suspect, `0` checked and not found suspect, null unknown ([details](provider/dwd/road/15_minutes.md)) |
| DWD mosmix, dmo, poi, swsmos, radar and the other DWD networks | null (apart from `raw:`) |
| Met Office observation | the MIDAS `*_q` flag `MESQL`, a five digit compound code, written by the file as an integer so that its leading zeros are missing (`2576` is `02576`; `str.zfill(5)` restores them) (marker, estimate, status, query, level: [QC flags](https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html)); not a scale |
| RMI | the validation of the value in `qc_flags`: `1` validated, `0` not validated |
| IMGW meteorology | the status column beside the value: `8` no measurement (value null), `9` the phenomenon did not occur (value 0), `Z` a collective total (`o_d` only); `11` is this library's own, for a day absent from a month that is present (`daily/precipitation`, value 0). Blank status is null |
| IMGW hydrology, WSV, FMI, KNMI, IPMA, LHMT, MeteoSwiss, AEMET, Geosphere, Météo-France synop | null (apart from `raw:`) |
| DMI | `qcStatus`: `manual` quality controlled by DMI's climatologists, `none` not controlled; then `validity:true` or `validity:false`, whether the climatologists consider the value valid ("Invalid data is generally not correct"; mostly Greenland) |
| Hubeau (Eaufrance) | `code_qualification_obs`: `0` neutre, `4` faible, `8` forte, `12` douteuse, `16` non qualifiée, `20` bonne, `30` estimée |
| MET Norway Frost | `qualityCode`: `0` controlled and found O.K., `1` controlled and corrected or interpolated, `2` slightly uncertain, not controlled, `4` slightly uncertain, not corrected, `5` very uncertain, not corrected, `6` very uncertain, model data, `7` erroneous, not corrected |
| ECCC | the `*_FLAG` letter of the value: `M` missing, `E` estimated, `T` trace, ... (null for monthly) |
| EA hydrology | the reading's `quality`: `Good`, `Estimated`, `Suspect`, `Unchecked`, `Missing`; then `completeness:Complete` or `completeness:Incomplete`, whether the value is based on complete data (`Good,completeness:Complete`). Only daily readings carry it, and not all of them; a reading without one has the quality alone |
| Météo-France observation | the `Q<parameter>` code: `9` filtered, `0` protected, `1` validated, `2` doubtful |
| NOAA GHCN daily | `QFLAG,measurement:MFLAG,source:SFLAG` of the value's attributes: the check it failed (`X` bounds, `G` gap, ...), how the value was made (`T` trace, ...) and where it came from (`0` U.S. Cooperative Summary of the Day, ...), as in the GHCN-Daily `readme.txt` |
| NOAA GHCN hourly (GHCNh) | `QUALITY,measurement:MEASUREMENT,source:SOURCE`: the `<element>_Quality_Code` of the value as the file writes it, case included (`q` and `Q` differ), kept for a suspect or erroneous value too, then its `<element>_Measurement_Code` (how the value was made, by element and by source as Table 2 of the documentation lists it: `N` a normal and `C` a calm wind, `D` a derived relative humidity or wet bulb, `0` to `8` the tendency of the 3-hour pressure change, `T` or `2` a trace of precipitation, `1` and `2` of a snow depth, ...) and its `<element>_Source_Code` (the data source, `335`, `223`, ... as `ghcnh-source-list.pdf` lists it); a code the file leaves blank, or writes `Null` (sources 245 and 367), is left out, so `4,source:335` has no measurement code. The meaning of the quality code (and of the measurement code) depends on the element's source, as Table 3 of the [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf) lists it. Sources 313, 314, 315, 322, 335, 343, 344, 346: `0` passed gross limits, `1` passed all checks, `2` suspect, `3` erroneous, `4` to `7` the same four from an NCEI data source, `9` passed gross limits if the element is present; sources 220, 221, 222, 223, 347, 348: `0` not checked, `1` good, `2` suspect, `3` erroneous, `4` calculated, `5` removed. Sources 345 and 382 have codes of their own, and some sources have codes Table 3 does not list (`0` and `1` of source 401). A letter is mostly a check of the integration run on temperature, dew point, station and sea level pressure, wind direction and wind speed (`c` climatological outlier, `s` spike, `f` frequent value, `o` odd cluster, ...); on a derived humidity or wet bulb `f` is a suspect input and `o` a relative humidity out of range; `A`, `P`, `U` and the `q` of source 382 are legacy letters |
| CHMI | daily, 10 minutes, hourly: `QUALITY`, then `element:FLAG`: `0` good, `1` suspect, `2` poor, `3` estimated, `4` missing, `5` unknown (`meta4.csv`), and the letter of the element's own table (`meta3.csv`: SRA `T` an amount too small to measure, ...). Monthly and annual (no `QUALITY`, no `FLAG`): `interrupted:I`, the value is computed although daily values of the period are missing (`FLAG_INTERRUPTED`); `repeat:*` (`FLAG_REPEAT`, a `MAX` or `MIN` reached on more than one day) is read too but sits on `MAX`/`MIN` rows only, which no monthly or annual parameter is, so it does not show today. CHMI documents neither flag; the meaning is read from the files against their daily files |
| NWS | the MADIS `qualityControl` flag: `Z`, `C`, `S`, `V`, `X`, `Q`, `G`, `B`, `T` |
| SMHI | the `Kvalitet` code: `G` approved, `Y` suspect or aggregated |

## Sentinels in `quality_flags`

| Provider | `raw:` text (value) |
| --- | --- |
| DWD observation | `-999` in every dataset (null); `-1` in the hourly cloud cover, `cloud_type` layers included, where the sky was not visible (null); `-99.9` in the five hourly `moisture` columns (null); `-1` in the hourly `weather_phenomena` `weather`, "not reported" (null); `990` in the wind direction of hourly and 10 minute `wind`, a variable direction (null) |
| DWD derived | `-999` and `-9999` (null) |
| DWD mosmix, dmo | `-` for a value the run does not have (null) |
| DWD poi | `---`, and any text that is no number (null) |
| DWD swsmos | any text that is no number (null); none is in the run file read on 2026-10-12 |
| AEMET | `99` in the wind direction of the daily maximum gust, calm or variable (null); any text that is no number in the daily, monthly and annual values (null) |
| DMI | `0` in the mean wind direction beside a mean wind speed of 0, calm (null); a value outside the range of its parameter at the resolution, such as the 17,802 mm of a month of rain or the 1978 mm of a day (null) |
| FMI | `NaN` (null); `-1.0` in `precipitation_amount` and `snow_depth`, none (0.0); any text that is no number (null) |
| Geosphere | `-1.0` in the daily `precipitation_amount` and `snow_depth`, and `-1` in the daily `snow_depth_manual` and `snow_depth_new`, none (0.0) |
| IMGW hydrology | `9999` in the stage, `99999.999` in the discharge, `99.9` and `9999` in the water temperature (null) |
| IPMA | `-99.0` (null); `0` in the wind direction, calm, or a code the eight points do not have (null) |
| KNMI | `NaN`, the fill value (null); `-1` in `precipitation_amount` and `sunshine_duration`, a trace (0.0); `0` and `990` in the hourly wind direction, calm and variable (null); `9` in the hourly and daily `cloud_cover_total`, the sky is invisible (null) |
| Met Office observation | `NA`, and any text that is no number (null); a day with an `NA` beside readings has the value of the readings |
| MET Norway Frost | `-1` in `snow_depth`, no snow (0.0); `-3` and `9` in `cloud_cover_total`, not estimated (null); the code as Frost documents it |
| Météo-France observation | `9` in the hourly cloud cover, the sky is invisible (null); `0` and `999` in the wind directions `DD` (hourly) and `DXI` (daily), no direction (null); any text that is no number (null) |
| Météo-France synop | `-0.1` in the precipitation, a trace (0.0); `101` in the cloud cover, the sky is obscured (null); any text that is no number (null) |
| RMI | a value outside the range of its parameter at the resolution, such as the 4021 degrees of a daily maximum or the 81.5 m/s of a daily gust (null) |
| NOAA GHCN hourly | `999` in `wind_direction`; `-9999` in `precipitation`; `-None` in any column (null) |

The other providers write their missing values as an empty field, a JSON null or a status that the plain code
already carries (IMGW meteorology: `8`), and have no `raw:` token. DWD road decodes BUFR, which has no text of a
missing value. CHMI, MeteoSwiss, SMHI, DWD phenology and the real-time values of AEMET read a text that is no
number as null without a token; none was found in their files, and DWD observation does the same for a letter
outside `P` and `I` in a measurement method.
