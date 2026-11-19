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

## Quality flag

Every value comes with SMHI's `Kvalitet` code in `quality_flags`, as the file writes it. In SMHI's words (customer
service, by mail, 2026-11-19): `G` is a verdict on a value after it was checked. `Y` is mostly that too, but it is also
the flag of a value that was not checked and of aggregated values (the 24 h maximum and minimum temperature are `Y`;
the values they are built from tell whether they are good). Leaving aggregates out, `Y` means the value is not checked
or was marked suspect by at least one control: no fault in the value, but a somewhat greater risk than `G`, so use it
with some caution. Not even `G` is a guarantee. Before 2010 only every third hour was checked.

wetterdienst returns the code and does not judge `Y`: it mixes unchecked, suspect and aggregated values, so it is no
verdict that the value failed a check. The reasoning is in
[plausibility](../../../plausibility.md#the-sources-own-verdict-source).

## License

Data is © SMHI, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See SMHI's
[terms of use](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning) (in Swedish) for the
conditions.

```{toctree}
:hidden:

1_minute.md
hourly.md
daily.md
monthly.md
```
