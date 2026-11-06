# 6 hours

## metadata

| property      | value   |
|---------------|---------|
| name          | 6_hours |
| original name | PT6H    |
| description   | Synoptic observations reported every six hours. |

## datasets

### data

#### parameters

| name                         | original name                  | description                           | unit |
|------------------------------|--------------------------------|---------------------------------------|------|
| {term}`precipitation_amount` | sum(precipitation_amount PT6H) | Amount of precipitation per six hours. Code -1, which Frost does not describe, is read as a dry period from 1982 on and returned as 0, and as no information before it, where it is returned as null. | millimeter |

## Notes

6-hourly data originates from the era of manned synoptic observations. Most Norwegian stations
switched to automated hourly reporting around 2010, but 128 of the 243 series Frost lists are still open-ended (the
synoptic stations, and 124 WMO stations of other countries that Frost has listed since 2026-11-03 with a rolling archive of
about three days), so a request for a recent window returns what those report.

Frost writes a dry period as `-1`, which is read as `0.0` from 1982 on and as `null` before; see the section
[The code -1 of the precipitation sums](index.md) of the Frost page for the reading, the evidence and the exceptions.
