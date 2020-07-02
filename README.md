# Wetterdienst - a Python library to ease access to open weather data

[![Tests](https://github.com/earthobservations/wetterdienst/workflows/Tests/badge.svg)](https://github.com/earthobservations/wetterdienst/actions?workflow=Tests)
![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)
![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)
![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)
[![codecov](https://codecov.io/gh/earthobservations/wetterdienst/branch/master/graph/badge.svg)](https://codecov.io/gh/earthobservations/wetterdienst)
[![PyPI](https://img.shields.io/pypi/v/wetterdienst.svg)](https://pypi.org/project/wetterdienst/)
[![License](https://img.shields.io/github/license/earthobservations/wetterdienst)](https://github.com/earthobservations/wetterdienst/blob/master/LICENSE.md)

## 1. Introduction

The library **Wetterdienst** was created as an alternative to [rdwd](https://github.com/brry/rdwd),
an R package that I had used for downloading station data from the German Weather Service 
([Deutscher Wetterdienst](https://www.dwd.de/EN)). Though in the beginning it was a self chosen project to get into 
Python, over time and by the help of others the project evolved step by step to a solid project.

Speaking about the available data, discussion over the last years regarding the data policy of data collected by country
officials have led to a series of open-data initiatives and releases in Europe and Germany as part of it. The German 
Weather Service has in the followup deployed their data via a file server. However this file server is neither handy to
use (not even being compared with an API) nor has it a real structure but rather some really big bugs - or better be
called "anomalies". The library streamlines those anomalies to simplify the data gathering process.

**CAUTION**
Although the data is specified as being open, the DWD asks you to reference them as Copyright owner. To check out 
further, follow [this](https://www.dwd.de/EN/ourservices/opendata/opendata.html) and 
[this](https://www.dwd.de/EN/service/copyright/copyright_artikel.html?nn=495490&lsbId=627548)

## 2. Types of data

The library is based upon data available 
[here](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/). The approximate structure is 
covered in DWD_FILE_SERVER_STRUCTURE.md

The available parameters are sorted in different time scales:

- per minute / **1_minute**
- per 10 minutes / **10_minutes**
- per hour / **hourly**
- 3 times a day / **subdaily**
- per day / **daily**
- per month / **monthly**
- per year / **annual**

The available parameters are also sorted in different periods:

- historical values covering all the measured data / **historical**
- recent values covering data from latest plus a certain range of historical data / **recent**
- current values covering only latest data / **now**

It is also possible to use enumeration keywords. This table lists the available enumeration keyword mappings on the CDC server.

|Paramater/Granularity                       |1_minute                             |   10_minutes                    |hourly | subdaily | daily     |monthly | annual| 
|----------------|-------------------------------|-----------------------------|-----------------------------|----------------|-------------|-----------------------------|-----------------------------|
| `TEMPERATURE_SOIL = "soil_temperature"`  | :x: | :x: | :heavy_check_mark:| :x: | :heavy_check_mark: |:x: | :x:|
| `TEMPERATURE_AIR = "air_temperature"` |:x: | :heavy_check_mark:| :heavy_check_mark:| :heavy_check_mark:| :x:|:x: |:x: |
| `PRECIPITATION = "precipitation"`    | :heavy_check_mark: | :heavy_check_mark: |:x: |:x: | :x:| :x:|:x: |
| `TEMPERATURE_EXTREME = "extreme_temperature"` | :x:|:heavy_check_mark: | :x:|:x: | :x:|:x: |:x: |
| `WIND_EXTREME = "extreme_wind"  `  |:x: | :heavy_check_mark: | :x:| :x:|:x: |:x: |:x: |
| `SOLAR = "solar"`  | :x: | :heavy_check_mark: | :heavy_check_mark:|:x: | :heavy_check_mark:| :x:|:x: |
| `WIND = "wind"  ` |:x: |:heavy_check_mark: | :heavy_check_mark:|:heavy_check_mark:|:x: |:x: |:x: |
| `CLOUD_TYPE = "cloud_type"`  |:x: | :x: | :heavy_check_mark:|:x: |:x: |:x: |:x: |
| `CLOUDINESS = "cloudiness"  `    | :x: | :x: |:heavy_check_mark: |:heavy_check_mark: | :x:| :x:| :x:|
| `SUNSHINE_DURATION = "sun"` |:x: |:x: | :heavy_check_mark:| :x:|:x:|:x:|:x: |
| `VISBILITY = "visibility"`  | :x:|  :x:|:heavy_check_mark: |:heavy_check_mark: |:x: | :x:| :x:|
| `WATER_EQUIVALENT = "water_equiv"`  | :x:| :x: |:x: |:x: |:heavy_check_mark: |:x: | :x:|
| `PRECIPITATION_MORE = "more_precip"  `    | :x: | :x: |:x: |:x: | :heavy_check_mark:|:heavy_check_mark: | :heavy_check_mark:|
| `PRESSURE = "pressure"` | :x:|:x: | :heavy_check_mark:|:heavy_check_mark:|:x: |:x:|:x: |
| `CLIMATE_SUMMARY = "kl"`  |:x: | :x: |:x: | :heavy_check_mark:|:heavy_check_mark: |:heavy_check_mark: |:x: |
| `MOISTURE = "moisture"` |:x: | :x: |:x: | :heavy_check_mark:|:x: |:x: |:x: |
| `WIND_SYNOP = "wind_synop"` |:x: | :x: | :heavy_check_mark:|:x: |:x: |:x: |:x: |
| `DEW_POINT = "dew_point"` |:x: | :x: | :heavy_check_mark:|:x: |:x: |:x: |:x: |
| `WEATHER_PHENOMENA = "weather_phenomena"` |:x: | :x: |:x: |:x: | :heavy_check_mark:|:heavy_check_mark:|:heavy_check_mark:|

## 3. Functionality of the toolset

The toolset provides different functions/classes which are:

- metadata_for_dwd_data
    - discover what data for a set of parameters (parameter, time_resolution, period_type) is available, 
    especially which stations can be found. 
    - with **create_new_file_index**, the function can be forced to retrieve a new list of files from the server, 
    which is usually avoided as it rarely changes.
- create_file_list_for_dwd_server:
    - is used with the help of the metadata to retrieve file paths to files for a set of parameters + station id
    - here also **create_new_file_index** can be used
- download_dwd_data:
    - is used with the created file paths to **download and store** the data (second os optionally, in a hdf)
- parse_dwd_data:
    - is used to get the data into the Python environment in shape of a pandas DataFrame. 
    - the data will be ready to be analyzed by you!
- get_nearest_station:
    - calculates the nearest weather station based on the coordinates for the requested data
    - it returns a list of station ids that can be used to download the data
- collect_dwd_data:
    - combines create_file_list_for_dwd_server, download_dwd_data and parse_dwd_data for multiple stations
- DWDStationRequest:
    - a class that can combine multiple periods/date ranges for any number of stations for you
    
Additionally the following functions allow you to reset the cache:

- reset_file_index_cache:
    - reset the cached file index to get latest list of files (only required for constantly running system)
- reset_meta_index_cache:
    - reset the cached meta index to get latest list of files (only required for constantly running system)
 
### Basic usage:

To retrieve meta data and get a first insight:
```
import wetterdienst
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.parameter_enumeration import Parameter

metadata = wetterdienst.metadata_for_dwd_data(
    parameter=Parameter.PRECIPITATION_MORE,
    time_resolution=TimeResolution.DAILY,
    period_type=PeriodType.HISTORICAL
)
```

The column **HAS_FILE** indicates if the station has a file with data on the server.

To retrieve observation data:
``` 
import wetterdienst
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.enumerations.parameter_enumeration import Parameter

station_data = wetterdienst.collect_dwd_data(
    station_ids=[1048], 
    parameter=Parameter.CLIMATE_SUMMARY, 
    time_resolution=TimeResolution.DAILY, 
    period_type=PeriodType.HISTORICAL
)
```

Also one may try out DWDStationRequest, a class to define the whole request, which also covers the definition of a 
requested time range, which may combine different periods of one data for you.

Also check out the more advanced examples in the **example** folder.

## 4. About the metadata

The metadata is usually parsed from a txt file. That is not the case for 1-minute historical precipitation, where the
metadata is separately stored for each station. To get a comparable metadata sheet, the files for each station have to
be parsed and combined. This step takes a bit of time to fulfill, so don't expect an instantaneous return here.

## 5. Anomalies

As already said in the introduction, the file server has lots of special cases. We want to point out here hourly solar
data, which has no obvious given period type. Still one can find the thought of period in the file description, which
is **recent** and was defined as such in the library.

## 7. Conclusion

Feel free to use the library if you want to automate the data access and analyze the german climate. Be aware that this 
library is developed voluntarily and we rely on your feedback regarding bugs, features, etc...

## 8. Getting started
```
pip install wetterdienst
wetterdienst --help
```

## 9. Development
For hacking on the library, you might want to follow these steps:
```
# Acquire sources
git clone https://github.com/earthobservations/wetterdienst
cd wetterdienst

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Invoke comand line tool
poetry shell
wetterdienst --help
```

____

## Docker support

To use Wetterdienst in a Docker container, you just have to build the image from this project
```
docker build -t "wetterdienst" .
```

To run the tests in the given environment, just call 
```
docker run -ti -v $(pwd):/app wetterdienst:latest poetry run pytest tests
```
from the main directory. To work in an iPython shell you just have to change the command `pytest tests/` to `ipython`.

#### Command line script  
You can download data as csv files after building docker container.
Currently, only the `collect_dwd_data` is supported by this service.

```
docker run \
    -ti -v $(pwd):/app wetterdienst:latest poetry run python wetterdienst/run.py \
    collect_dwd_data "[1048]" "kl" "daily" "historical" /app/dwd_data/ False False True False True True
```

The `wetterdienst` command is also available through Docker:
```
docker run -ti -v $(pwd):/app wetterdienst:latest poetry run wetterdienst
```
