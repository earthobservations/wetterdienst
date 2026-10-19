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
BADC-CSV file per station and year. A station may transmit several report types for the same period
(for example an overnight and a daytime 12-hour reading alongside a 24-hour one); these are
collapsed to a single value per calendar day (maximum for max-type parameters such as
`temperature_air_max_2m`, minimum for min-type ones). The day is the date of the row's
`ob_end_time`, the source's 09Z climatological day, and the daily temperature file mixes 12-hour
rows (ending 09:00 and 21:00) with 24-hour rows ending 09:00 (2,962 of the 14,334 rows of the
daily temperature files of 25 stations, 2022), so a 24-hour 09-09Z row falls on the day after most
of its coverage and the daily extremes of stations that transmit different report types do not
cover the same hours. The other daily quantities (sunshine, snow depth, precipitation) are reported
once per day, so the aggregation is effectively a de-duplication there. Hourly datasets keep only
the readings of one hour (`ob_hour_count` 1): the files of the rain and radiation datasets also
hold 12 and 24-hour totals. A wind direction of 0 beside a wind speed of 0 (a calm) and a total
cloud amount of 9 (the sky obscured) are null, with the text the file wrote in `quality_flags`.

Not every station measures every parameter — a station/parameter combination MIDAS doesn't have
simply contributes no rows.

The `quality_flags` column carries MIDAS's `MESQL` quality-control flag, a five-digit code that the
file writes as an integer (`2576` is `02576`), as the string the file writes; each digit encodes a
different aspect of the observation's quality (see the
[MIDAS QC flag documentation](https://dap.ceda.ac.uk/badc/ukmo-midas/metadata/doc/QC_J_flags.html)),
so a larger number is not "worse".

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
