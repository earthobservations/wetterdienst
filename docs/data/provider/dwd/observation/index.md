# Observation

## Overview

The big treasure of the DWD is buried under a clutter of a 
[file_server](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/).
The data you find here can reach back to 19th century and is represented by over 1000
stations in Germany according to the report referenced above. The amount of stations
that cover a specific parameter may differ strongly, so don't expect the amount of data
to be that generous for all the parameters.

Available data/parameters on the file server is sorted in different time resolutions:

- **1_minute** - measured every minute
- **5_minute** - measured every 5 minutes
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
every minute obviously results a much bigger amount of data and thus smaller chunks
of data are needed to lower the stress on data transfer, e.g. when updating your
database you probably won't need to stream all the historical data every day. On the
other hand this will also save you a lot of time as the size relates to the processing
time your machine will require.

The table below lists every (useful) dataset on the file server with its combinations
of available resolutions. In general only 1-minute and 10-minute data is offered
in the "now" period, although this may change in the future.

The two dataset strings reflect on how we call a dataset e.g. "PRECIPITATION" and
how the DWD calls the dataset e.g. "precipitation".

| Dataset \ Granularity                               | 1_minute | 5_minutes | 10_minutes | hourly | subdaily | daily | monthly | annual |
|-----------------------------------------------------|----------|-----------|------------|--------|----------|-------|---------|--------|
| `PRECIPITATION = "precipitation"`                   | ✅        | ✅         | ✅          | ❌      | ❌        | ❌     | ❌       | ❌      |
| `TEMPERATURE_AIR = "air_temperature"`               | ❌        | ❌         | ✅          | ✅      | ✅        | ❌     | ❌       | ❌      |
| `TEMPERATURE_EXTREME = "extreme_temperature"`       | ❌        | ❌         | ✅          | ❌      | ❌        | ❌     | ❌       | ❌      |
| `WIND_EXTREME = "extreme_wind"`                     | ❌        | ❌         | ✅          | ❌      | ❌        | ❌     | ❌       | ❌      |
| `SOLAR = "solar"`                                   | ❌        | ❌         | ✅          | ✅      | ❌        | ✅     | ❌       | ❌      |
| `WIND = "wind"`                                     | ❌        | ❌         | ✅          | ✅      | ✅        | ❌     | ❌       | ❌      |
| `CLOUD_TYPE = "cloud_type"`                         | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `CLOUDINESS = "cloudiness"`                         | ❌        | ❌         | ❌          | ✅      | ✅        | ❌     | ❌       | ❌      |
| `DEW_POINT = "dew_point"`                           | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `PRESSURE = "pressure"`                             | ❌        | ❌         | ❌          | ✅      | ✅        | ❌     | ❌       | ❌      |
| `TEMPERATURE_SOIL = "soil_temperature"`             | ❌        | ❌         | ❌          | ✅      | ❌        | ✅     | ❌       | ❌      |
| `SUNSHINE_DURATION = "sun"`                         | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `VISBILITY = "visibility"`                          | ❌        | ❌         | ❌          | ✅      | ✅        | ❌     | ❌       | ❌      |
| `WIND_SYNOPTIC = "wind_synop"`                      | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `MOISTURE = "moisture"`                             | ❌        | ❌         | ❌          | ✅      | ✅        | ❌     | ❌       | ❌      |
| `CLIMATE_SUMMARY = "kl"`                            | ❌        | ❌         | ❌          | ❌      | ✅        | ✅     | ✅       | ✅      |
| `PRECIPITATION_MORE = "more_precip"`                | ❌        | ❌         | ❌          | ❌      | ❌        | ✅     | ✅       | ✅      |
| `WATER_EQUIVALENT = "water_equiv"`                  | ❌        | ❌         | ❌          | ❌      | ❌        | ✅     | ❌       | ❌      |
| `WEATHER_PHENOMENA = "weather_phenomena"`           | ❌        | ❌         | ❌          | ❌      | ❌        | ✅     | ✅       | ✅      |
| `URBAN_TEMPERATURE_AIR = "urban_temperature_air"`   | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `URBAN_PRECIPITATION = "urban_precipitation"`       | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `URBAN_PRESSURE = "urban_pressure"`                 | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `URBAN_TEMPERATURE_SOIL = "urban_temperature_soil"` | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `URBAN_SUN = "urban_sun"`                           | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |
| `URBAN_WIND = "urban_wind"`                         | ❌        | ❌         | ❌          | ✅      | ❌        | ❌     | ❌       | ❌      |

This table and subsets of it can be printed with a function call of
``.discover()`` as described in the API section. Furthermore, individual
parameters can be queried.

## Parameter details

### Precipitation (5 minutes)

The precipitation dataset contains the following parameters:
- rs_05
- rth_05
- rwh_05
- rs_ind_05

of which only `rs_05` and `rs_ind_05` are available in the `recent` and `now` period.

### Cloud types

| Cloud type      | Code   |
|-----------------|--------|
| Cirrus          | 0      |
| Cirrocumulus    | 1      |
| Cirrostratus    | 2      |
| Altocumulus     | 3      |
| Altostratus     | 4      |
| Nimbostratus    | 5      |
| Stratocumulus   | 6      |
| Stratus         | 7      |
| Cumulus         | 8      |
| Cumulonimbus    | 9      |
| Automated       | -1     |

### Long parameters

DWD observation data excludes several parameters
which contain strings. Those parameters are:

- cloud type abbreviations (1 - 4) in **hourly cloud type** dataset
- total cloud cover indicator in **hourly cloudiness** dataset
- true local time in **hourly solar** dataset
- visibility indicator in **hourly visibility** dataset

### Quality

The DWD designates its data points with specific quality levels expressed as "quality bytes".

- The "recent" data have not completed quality control yet.
- The "historical" data are quality controlled measurements and observations.

The following information has been taken from PDF documents on the DWD open data
server like [data set description for historical hourly station observations of precipitation for Germany](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/historical/DESCRIPTION_obsgermany_climate_hourly_precipitation_historical_en.pdf).
Wetterdienst provides convenient access to the relevant details
by using routines to parse specific sections of the PDF documents.

For example, use commands like these for accessing this information::

    # Historical hourly station observations of precipitation for Germany.
    # English language.
    wetterdienst dwd about fields --parameter=precipitation --resolution=hourly --period=historical

    # Historical 10-minute station observations of pressure, air temperature (at 5cm and 2m height), humidity and dew point for Germany.
    # German language.
    wetterdienst dwd about fields --parameter=air_temperature --resolution=10_minutes --period=historical --language=de

or have a look at the example program [dwd_obs_climate_summary_describe_fields.py](https://github.com/earthobservations/wetterdienst/blob/main/examples/provider/dwd/observation/dwd_obs_climate_summary_describe_fields.py).

### Details

#### Validation and uncertainty estimate

Considerations of quality assurance are explained in Kaspar et al., 2013.

Several steps of quality control, including automatic tests for completeness,
temporal and internal consistency, and against statistical thresholds based
on the software QualiMet (see Spengler, 2002) and manual inspection had been
applied.

Data are provided "as observed", no homogenization has been carried out.

The history of instrumental design, observation practice, and possibly changing
representativity has to be considered for the individual stations when interpreting
changes in the statistical properties of the time series. It is strongly suggested
to investigate the records of the station history which are provided together with
the data. Note that in the 1990s many stations had the transition from manual to
automated stations, entailing possible changes in certain statistical properties.

#### Additional information

When data from both directories "historical" and "recent" are used together,
the difference in the quality control procedure should be considered.
There are still issues to be discovered in the historical data.
The DWD welcomes any hints to improve the data basis (see contact).

### Examples

As an example, these sections display different means of
quality designations related to ``daily``/``hourly`` and
``10_minutes`` resolutions/products.

#### Daily and hourly quality

The quality levels "Qualitätsniveau" (QN) given here
apply for the respective following columns. The values
are the minima of the QN of the respective daily
values. QN denotes the method of quality control,
with which erroneous values are identified and apply
for the whole set of parameters at a certain time.

For the individual parameters there exist quality bytes
in the internal DWD database, which are not published here.
Values identified as wrong are not published.

Various methods of quality control (at different levels) are
employed to decide which value is identified as wrong. In the
past, different procedures have been employed.
The quality procedures are coded as following.

Quality level (column header: ``QN_``):

```text
    1- Only formal control during decoding and import
    2- Controlled with individually defined criteria
    3- ROUTINE control with QUALIMET and QCSY
    5- Historic, subjective procedures
    7- ROUTINE control, not yet corrected
    8- Quality control outside ROUTINE
    9- ROUTINE control, not all parameters corrected
    10- ROUTINE control finished, respective corrections finished
```

#### 10 minutes quality

The quality level "Qualitätsniveau" (QN) given here
applies for the following columns. QN describes
the method of quality control applied to a complete
set of parameters, reported at a common time.

The individual parameters of the set are connected with
individual quality bytes in the DWD database, which are
not given here. Values marked as wrong are not given here.

Different quality control procedures (and at different
levels) have been applied to detect which values are
identified as erroneous or suspicious. Over time,
these procedures have changed.

Quality level (column header: ``QN``):

```text
    1- Only formal control during decoding and import
    2- Controlled with individually defined criteria
    3- ROUTINE automatic control and correction with QUALIMET
```
