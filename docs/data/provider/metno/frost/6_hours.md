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
| {term}`precipitation_amount` | sum(precipitation_amount PT6H) | Amount of precipitation per six hours. Code -1, which Frost does not describe, is read as a dry period and is returned as 0. | millimeter |

## Notes

6-hourly data originates from the era of manned synoptic observations (typically pre-2010).
Most Norwegian stations switched to automated hourly reporting around 2010, so this
resolution is largely historical. Queries for recent periods will return no data.

### The code -1

The 6-hourly sums of Frost hold the value `-1`. Its description of the element ("Amount of precipitation per six
hours") says nothing of it: only snow depth's description documents a code ("Code=-1 means no snow"). That `-1` is a
dry period, a sum of 0 mm, is **our reading of the data, not a statement of Frost**. It is returned as `0.0`, and the
code stays in `quality_flags` as the last token (`0,raw:-1`).

The evidence, read from Frost on 2026-11-06 at 17 stations (1995 to 2024):

- `-1` is half of the readings (10,288 of 20,257), not an outlier. Oslo - Blindern (`SN18700`) has 8 readings in
  2005 to 2010: `-1` three times, `0` once, and 1.3, 0.4, 0.1 and 3.0 mm.
- At five stations, the 12-hourly sum (`PT12H`, which this provider does not serve) that holds a `-1` reading is dry in
  88 % of the cases (itself `-1` or `0`), the one that holds a reading above 0 in 2 %.
- The 12-hourly sum writes the code the same way. Added up to the daily sum of the day, with `-1` read as 0, it gives
  the daily sum in 99.9 % of the 9,865 days that have one, as often as the days without any `-1` do (99.7 %).
- A `0` is not the same as `-1`: a day that holds a 6-hourly `0` is dry as often as any day is (41 %), one that holds a
  `-1` in 70 %. The `0` is kept as `0.0`.

The code is read for this element alone. The other precipitation sums of Frost were measured too, and the evidence does
not reach them: the 10-minute and hourly sums carry no `-1` in 307,000 readings and the annual one none in 6,400. The
daily sum has 9 in 137,000 (eight of them at one station on eight days of February 2007, the other beside 1.1 mm of rain
in the hours of its day) and the monthly sum 6 in 103,000, all of 1915 to 1920 (each month has 0 on every day). A `-1`
there is not read: it is below the range of precipitation, so it comes back as a null with `rejected:range,raw:-1`.

A request for 6-hourly precipitation used to come back with "The source has no values" for a station that has readings
only of `-1`: the range check rejected them as below 0 mm (GH-3748).
