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

Station metadata comes from each dataset's `station-metadata.csv` catalogue. Observations are one
BADC-CSV file per station and year. A station may transmit several report types for the same period
(for example an overnight and a daytime 12-hour reading alongside a 24-hour one); these are
collapsed to a single value per calendar day (maximum for max-type parameters such as
`temperature_air_max_2m`, minimum for min-type ones). For the daily temperature extremes this
recovers the true daily extreme regardless of which report types a station transmits; the other
daily quantities (sunshine, snow depth, precipitation) are reported once per day, so the aggregation
is effectively a de-duplication there. Hourly datasets carry one reading per hour.

Not every station measures every parameter — a station/parameter combination MIDAS doesn't have
simply contributes no rows.

The `quality` column carries MIDAS's raw five-digit `MESQL` quality-control flag verbatim; each
digit encodes a different aspect of the observation's quality (see the
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
