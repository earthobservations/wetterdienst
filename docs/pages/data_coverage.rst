Data Coverage
#############

The DWD offers various datasets including but not only:

- historical weather data
- MOSMIX -  forecasts for selected stations derived from weather models
- RADOLAN - radar based precipitation measuring system

For a quick overview of the work of the DWD check the current
`report <https://www.dwd.de/SharedDocs/downloads/DE/allgemein/zahlen_und_fakten.pdf?__blob=publicationFile&v=14>`_
(only in german).

Wetterdienst currently only supports historical weather data, but sets its target to
include MOSMIX and radolan as well in future iterations.

Historical Weather Data
***********************

The big treasure of the DWD is buried under a clutter of a
`file server <https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/>`_.
The data you find here can reach back to 19th century and is represented by over 1000
stations in Germany according to the report referenced above. The amount of stations
that cover a specific parameter may differ strongly, so don't expect the amount of data
to be that generous for all the parameters.

Available dataa/parameters on the file server is sorted in different time resolutions:

- **1_minute** - measured every minute
- **10_minutes** - measured every 10 minutes
- **hourly** - measured every hour
- **subdaily** - measured 3 times a day
- **daily** - measured once a day
- **monthly** - measured/summarized once a month
- **annual** - measured/summarized once a year

Depending on the time resolution of the parameter you may find different periods that
the data is offered in:

- **historical** - values covering all the measured data
- **recent** - recent values covering data from latest plus a certain range of historical data
- **now** - current values covering only latest data

The period relates to the amount of data that is measured, so measuring a parameter
every minute obviously results an a much bigger amount of data and thus smaller chunks
of data are needed to lower the stress on data transfer, e.g. when updating your
database you probably won't need to stream all the historical data every day. On the
other hand this will also save you a lot of time as the size relates to the processing
time your machine will require.

The table below lists every (useful) parameter on the file server with its combinations
of available time resolutions. In general only 1-minute and 10-minute data is offered
in the "now" period, although this may change in the future.

The two parameter strings reflect on how we call a parameter e.g. "PRECIPITATION" and
how the DWD calls the parameter e.g. "precipitation".

+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
|Parameter/Granularity                              | 1_minute              | 10_minutes            | hourly                | subdaily              | daily                 | monthly               | annual                |
+===================================================+=======================+=======================+=======================+=======================+=======================+=======================+=======================+
| `PRECIPITATION = "precipitation"`                 | |check|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `TEMPERATURE_AIR = "air_temperature"`             | |cross|               | |check|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `TEMPERATURE_EXTREME = "extreme_temperature"`     | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WIND_EXTREME = "extreme_wind"`                   | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `SOLAR = "solar"`                                 | |cross|               | |check|               | |check|               | |cross|               | |check|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WIND = "wind"`                                   | |cross|               | |check|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `CLOUD_TYPE = "cloud_type"`                       | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `CLOUDINESS = "cloudiness"`                       | |cross|               | |cross|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `DEW_POINT = "dew_point"`                         | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `PRESSURE = "pressure"`                           | |cross|               | |cross|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `TEMPERATURE_SOIL = "soil_temperature"`           | |cross|               | |cross|               | |check|               | |cross|               | |check|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `SUNSHINE_DURATION = "sun"`                       | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `VISBILITY = "visibility"`                        | |cross|               | |cross|               | |check|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WIND_SYNOPTIC = "wind_synop"`                    | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `MOISTURE = "moisture"`                           | |cross|               | |cross|               | |cross|               | |check|               | |cross|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `CLIMATE_SUMMARY = "kl"`                          | |cross|               | |cross|               | |cross|               | |check|               | |check|               | |check|               | |check|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `PRECIPITATION_MORE = "more_precip"`              | |cross|               | |cross|               | |cross|               | |cross|               | |check|               | |check|               | |check|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WATER_EQUIVALENT = "water_equiv"`                | |cross|               | |cross|               | |cross|               | |cross|               | |check|               | |cross|               | |cross|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+
| `WEATHER_PHENOMENA = "weather_phenomena"`         | |cross|               | |cross|               | |cross|               | |cross|               | |check|               | |check|               | |check|               |
+---------------------------------------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+-----------------------+

.. |check| + .. check mark
.. |cross| - .. cross mark

MOSMIX
******

Yet to be implemented...

RADOLAN
*******

Yet to be implemented...
