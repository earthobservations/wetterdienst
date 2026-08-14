# 6 hour

## metadata

| property      | value  |
|---------------|--------|
| name          | 6_hour |
| original name | PT6H   |
| description   | Synoptic observations reported every six hours. |

## datasets

### data

#### parameters

| name                         | original name                  | description                           | unit |
|------------------------------|--------------------------------|---------------------------------------|------|
| {term}`precipitation_height` | sum(precipitation_amount PT6H) | Amount of precipitation per six hours | millimeter |

## Notes

6-hourly data originates from the era of manned synoptic observations (typically pre-2010).
Most Norwegian stations switched to automated hourly reporting around 2010, so this
resolution is largely historical. Queries for recent periods will return no data.
