# Observation

## Overview

The Met Office MIDAS Open archive provides quality-controlled UK land surface station
observations at daily and hourly resolution, spanning eight datasets (daily rain, temperature
and weather; hourly rain, weather, mean wind, radiation and soil temperature). Data reaches back
to the 19th century for some stations.

MIDAS Open is *not* the (paid, forecast-oriented) Met Office Weather DataHub. It is the historical
archive, published as annual releases: each release covers data up to the end of the previous
complete year, so the most recent ~6–12 months are not yet available. The provider always reads
the latest release.

Access requires a free CEDA account. The archive is browsable anonymously, but downloading files
needs a bearer token, which the provider mints automatically from your CEDA credentials. Register
at [services.ceda.ac.uk](https://services.ceda.ac.uk) and configure the credentials via
`WD_AUTH__CEDA=<username>:<password>` (environment variable) or
`Settings(auth={"ceda": "<username>:<password>"})` (Python).

Station metadata comes from each dataset's `station-metadata.csv` catalogue; a station's `region` is
the historic county the catalogue files it under, as published (`shetland`). Observations are one
BADC-CSV file per station and year. The day of the daily quantities is the date of the row's
`ob_end_time`; the temperature is built from windows (below), and the others (sunshine, snow depth,
precipitation) are reported once per day, so the aggregation is effectively a de-duplication there.
Hourly datasets keep only the readings of one hour (`ob_hour_count` 1): the files of the rain and
radiation datasets also hold 12 and 24-hour totals. A wind direction of 0 beside a wind speed of 0 (a calm) and a total
cloud amount of 9 (the sky obscured) are null, with the text the file wrote in `quality_flags`.

Not every station measures every parameter — a station/parameter combination MIDAS doesn't have
simply contributes no rows.

The `quality_flags` column carries MIDAS's `MESQL` quality-control flag, a five-digit code that the
file writes as an integer (`2576` is `02576`), as the string the file writes; each digit encodes a
different aspect of the observation's quality (see the
[MIDAS QC flag documentation](https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html)),
so a larger number is not "worse".

## The daily temperature: the 24 hours ending 09Z

The daily `temperature_air_max_2m`, `temperature_air_min_2m` and `temperature_air_min_0_05m` are the
extremes of **the 24 hours ending 09Z on the stamped day (09-09Z)**, the Met Office's usual
climatological day, at every station. The MIDAS file holds them as windows of 12 or 24 hours
(`ob_hour_count`), each with the time it ends (`ob_end_time`): the TD table says "For air
temperatures, the observation period will usually be one of the following: 09-09Z, 09-21Z, 21-09Z"
([TD table](https://artefacts.ceda.ac.uk/badc_datadocs/ukmo-midas/TD_Table.html)). A station reports
either the 24 hour window (`DLY3208`, `SYNOP`) or its two 12 hour halves (`NCM`, `AWSDLY`), and a few
report both (96 station-years of 2015 and 2025: 64 with only 12 hour rows, 26 with only 24 hour rows,
6 with both, which are 16 days of 33,953). All six main synoptic stations (Lerwick, Kinloss, Valley,
Aldergrove, Heathrow, Camborne) are 12 hour stations.

| What the file holds for the day `D` | The value of `D` |
| --- | --- |
| a 24 hour row ending 09:00 on `D` | that row, as given (also where the 12 hour rows are there) |
| the 21-09Z row ending 09:00 on `D` and the 09-21Z row ending 21:00 on `D-1` | the maximum (minimum) of the two |
| only one of the two 12 hour rows | no row: the day is left out and an `other-window-left-out` warning tells it (never "no values") |

Before, the value of `D` was the maximum (minimum) of all rows ending on the calendar day `D`,
whatever their window. At a 12 hour station that was 21Z on `D-1` to 21Z on `D`, mostly the
afternoon of `D`, and at a 24 hour station 09Z on `D-1` to 09Z on `D`, mostly the afternoon of
`D-1`: a 24 hour station was a day behind a 12 hour station. On the 70 station-years with 12 hour
rows the old maximum differed from the 09-09Z day on 23,720 of 25,019 days (95 %, by 1.6 degC on
average, 11.6 at most) and the old minimum on 8,649 of 25,015 (35 %, 0.5 degC on average, 13.1 at
most). On a day with both kinds of row the 09-21Z row of `D` lies outside the 24 hours ending 09Z on
`D` and no longer counts (Spadeadam No 2 2015-12-01: 24 hour row 2.4, day row 11.0, returned 11.0
before). A year's first day reads the evening of 31 December from the file of the year before.

The minimum grass temperature is reported in the 21-09Z rows and the 24 hour rows only: of 28,594
rows of the 96 station-years that have a value, 24,200 are 12 hour rows ending 09:00 and 4,394 are
24 hour rows, and none is a 12 hour row ending 21:00 (the air temperatures have 25,097 and 25,091 of
those). Its 12 hour day is therefore the 21-09Z row alone, as before, and no day is left out for it.
Whether it should need both halves, which would leave it out at every 12 hour station, is open
(GH-3137).

## The source's own verdict (`source`)

The `quality_flags` of a value is its `MESQL`, "a five digit number (of the form MESQL), where each digit describes one
aspect of the quality of a meteorological element" ([MIDAS QC flags](https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html),
read 2026-11-02). The check `source` reads one digit, the third from the right, the status `S`
(`qc_status`, "Indicates 1 of up to 8 possible descriptions of the value of the element (e.g. reason for suspecting a
value)"): `1` "Observed and suspect (i.e. has failed the latest QC check), or there are strong grounds for suspecting the
accuracy of the observation", against `0` "Observed and not suspect". The file writes the number without leading zeros
(`2176` is `02176`), so a flag of fewer than three digits has no status and is not read. The other digits are not
read: the marker, the estimate (`E`) and the level (`L`) say nothing of a failed value; the other statuses are
estimates, "A correction (a reported value is assumed to be in error)" (the value returned is the corrected one),
"Value reverted to original" and "Original value verified by observer"; and the query (`Q`, `Failed climate QC range
check`, ...) "gives information about the original (as reported) value", which a correction may have replaced.

The mapping is made from the documentation and the fixtures of the tests alone: the live data of the archive needs a
CEDA login, which was not used, so how often a status of `1` occurs in the files is not known.

With `plausibility={"source": "hard"}` the value is null and the token is `rejected:source,raw:<text>`; the default is
`soft`, which keeps the value and writes `suspect:source`, so interpolation, summaries and climate stripes leave it
out. See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

## License

MIDAS Open is © Crown Copyright, Met Office, published under the
[UK Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
See the [dataset catalogue record](https://catalogue.ceda.ac.uk/uuid/dbd451271eb04662beade68da43546e1/)
for further information and usage conditions.

```{toctree}
:hidden:

daily.md
hourly.md
```
