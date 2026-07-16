# Observation

## Overview

SMHI's Open Data platform provides access to 1-minute, hourly, daily and monthly
observation values from SMHI's meteorological station network across Sweden. No API
key or registration is required — the API is fully public.

SMHI splits history into overlapping periods: `corrected-archive` (quality-controlled
data up to roughly 3 months ago) and `latest-months` (the last ~4 months, still under
quality control). Both are fetched and merged automatically, so a request spanning the
boundary between them gets complete coverage without any extra configuration.

The `1_minute` resolution is different: SMHI only exposes a short rolling window for it
(via the `latest-day` period) — no historical backfill at all, similar to a real-time
observation feed.

Not every station measures every parameter — a station/parameter combination that
SMHI doesn't have simply contributes no rows, the same as a station reporting no data
for a requested date range.

## License

Data is © SMHI, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See
[SMHI Open Data](https://www.smhi.se/data/utforskaren-oppna-data) for further
information and usage conditions.

```{toctree}
:hidden:

1_minute.md
hourly.md
daily.md
monthly.md
```
