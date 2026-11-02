# Hydrology

## Overview

The EA runs the Hydrology interface as one of their offers to the public. Detailed information can be looked up at their
[EA Hydrology Reference](https://environment.data.gov.uk/hydrology/doc/reference). 
The data provided through ``wetterdienst`` includes:

- flow
- river water level (stage)
- groundwater level (15 minutes)

in resolutions 15 minutes and daily for stations in England.

## The source's own verdict (`source`)

Every reading carries the `quality` the API words as "quality: The quality of this reading: Good, Estimated, Suspect,
Unchecked, Missing" ([EA Hydrology Reference, Readings](https://environment.data.gov.uk/hydrology/doc/reference#readings-section)),
as the plain flag of `quality_flags`, followed by `completeness`. The check `source` reads `Suspect`. Not read: `Good`,
`Estimated` (a treatment), `Unchecked` (no control) and `Missing`. A `Suspect` reading comes with its value: of the 2,000
readings the API gave for 2024-01-01 (read 2026-11-02), 1,378 were `Good`, 563 `Unchecked`, 48 `Suspect`, 8 `Missing` and
3 `Estimated`, and a `Suspect` one reads `{"value": 0.411, "qcode": "Edited", "quality": "Suspect"}`, flagged
`Suspect,suspect:source`.

With `plausibility={"source": "hard"}` the value is null and the token is `rejected:source,raw:<text>`; the
default is `soft`, which keeps the value and writes `suspect:source`, so interpolation, summaries and climate stripes leave it
out. See [the check `source`](../../../plausibility.md#the-sources-own-verdict-source).

```{toctree}
:hidden:

15_minutes.md
daily.md
```