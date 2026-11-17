# UVI

## Overview

UVI is the DWD's **forecast of the UV index** (the "UV-Gefahrenindex") for 38 places in Germany, made by its
medical meteorology. For each place it gives the highest UV index expected for today, tomorrow and the day after
tomorrow, as a whole number on the WHO scale (0 to 2 low, 3 to 5 moderate, 6 to 7 high, 8 to 10 very high,
11 and above extreme).

The data is one small JSON file,
[uvi.json](https://opendata.dwd.de/climate_environment/health/alerts/uvi.json), written once a day in the morning
and described in
[Beschreibung_uvi.pdf](https://opendata.dwd.de/climate_environment/health/alerts/Beschreibung_uvi.pdf) beside it.
It holds no earlier day and no other run, so there is no `issue`: the network is the latest forecast, with one daily
value for each of the three days. No authentication is required.

The 38 places are the stations. The file names a place by its city and gives no id and no position, and DWD says only
that it forecasts "für ausgewählte Stationen" without naming them. So the library keeps the places: the id is the name
as a slug (`Frankfurt/Main` is `frankfurt-main`, `Großer Arber` is `grosser-arber`, `München` is `muenchen`), and the
position is the library's pick of the city's main DWD station (a mountain, a lighthouse or an airfield for many of
them), or, for Bonn, of the gazetteer GeoNames. It is not DWD's reference of the forecast, which is not known. The
table, with the station each position is of, is `provider/dwd/uvi/places.py`.

A place that DWD adds to the file is skipped, with a warning that names it, until it is added to the table; a place of
the table that is not in the file has no values and is named in the `file-skipped` warning of the answer. A file that is
not the one described is a `DownloadError`.

The timestamp of a value is the date of its day at 00:00 UTC (the day is the German date of the file's
`forecast_day`; DWD states no hours of the day), and the value is the highest of that day.

## Update date

There is no model run: the `data_updated_at` of the
[`metadata`](../../../../usage/restapi.md#response-metadata) of an answer is when DWD last wrote the file (its
`Last-Modified`), the date DWD states in `last_update` having no time zone.

```{toctree}
:hidden:

daily.md
```
