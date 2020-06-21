# python_dwd

Python Toolset For Accessing Weather Data From German Weather Service

## 1. Introduction

python_dwd was created as an alternative to [rdwd](https://github.com/brry/rdwd), an R package that I had used recently for downloading station data from German Weather Service (Deutscher Wetterdienst or DWD). It's my first Python project which is also meant for me to learn different ways to work with the language but might also be useful for you if you are interested in working with this data.

Germany has decided to make the data accessible to anyone on the internet (be careful with the license of the data and check this first!). Therefor they are storing the data on a public server, what makes it an ease to access. However it's not always quite comforting looking at the subfolders et cetera to automatically generate file links and download and open them - especially when working manually with Excel or whatever.

The functions we created derive the data laying on the server, present the existing metadata (list of existing stations, list of existing station data files) to you and let you choose which data to download (by choosing a set of parameters and a station id).

## 2. Types of data

First there is a large set of variables [available online](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/). Those can be seen in the 'dwd_ftp_structure' textfile.

Second those variables are available in different time scales. Those are:

- per minute | '1_minute'
- per 10 minutes | '10_minutes'
- per hour | 'hourly'
- per day | 'daily'
- per month | 'monthly'
- per year | 'annual'

Third those variables are also available in different tenses, which are:

- historical values covering all the measured data -> 'historical'
- recent values covering data from latest plus a certain range of historical data -> 'akt'
- current values covering only latest data -> 'now'

## 3. Functionality of the toolset

The toolset provides different functions which are:

- metadata_for_dwd_data
- create_file_list_for_dwd_server (+ reset_file_index_cache)
- download_dwd_data
- parse_dwd_data
- get_nearest_station
- collect_dwd_data
- restore_dwd_data
- store_dwd_data

All those functions have one same argument which is **folder**. It can be used to define in which folder relative to the working path all the files shall be stored. Otherwise a standard folder ('dwd_data') is used. The argument is entered as a **string**.

**metadata_for_dwd_data** is used to discover what data for a set of parameters (**var**, **res**, **per**) is available, specificly which stations can be found for the requested variable, resolution and period. Also it can be defined by **write_file**, if the resulting **DataFrame** should be written as **csv** to the given folder. **write_file** is a boolean value. Furthermore with **create_new_filelist**, by default set to **False**, the function can be forced to retrieve a new list of files from the ftp server, which is usually avoided if there's already a file existing in the explicit folder.

**create_file_list_for_dwd_server** is used with the help of the **information of the metadata** to retrieve filelinks to files that represent a **set of parameters** in combination with the requested **statid**. Here also **create_new_file_index** can be set to **True**, if the user is sure that the **file to a certain station id** is available but somehow the old **file index** doesn't contain a corresponding information.

**reset_file_index_cache** can be used to remove old file index in order to get the latest update of files in the remote server

**download_dwd_data** is used with the created filelinks of select_dwd to **download and store** the data in the given folder. Therefor it connects with the ftp and writes the corresponding file to the harddisk as defined. Furthermore it returns the local filelink or to be clear the link where the file is saved on the harddrive.

**parse_dwd_data** is used to get the data into the Python environment in shape of a pandas DataFrame. Therefor it opens the downloaded zipfile, reads its content and selects the file with the data (something like "produkt..."). Then the selected file is read and returned in shape of a DataFrame, ready to be analyzed!

**get_nearest_station** calculates the nearest weather station based on the coordinates for the requested data. It returns a list of station ids that can be used to download the data 
 
### Basic usage:

To retrieve observation data:
``` 
import python_dwd
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.parameter_enumeration import Parameter

# define requested data
remote_file_path = python_dwd.create_file_list_for_dwd_server(station_ids=[1048],
                                                              parameter=Parameter.CLIMATE_SUMMARY,
                                                              time_resolution=TimeResolution.DAILY,
                                                              period_type=PeriodType.HISTORICAL) 
# download data with generated remote file path
station_download = python_dwd.download_dwd_data(remote_file_path)
# parsing the data into a dataframe 
station_data = python_dwd.parse_dwd_data(station_download)
```
or alternatively:
```
# Combines the above functions with possible storing/restoring options
station_data = collect_dwd_data(
    station_ids=[1048],
    parameter=Parameter.CLIMATE_SUMMARY,
    time_resolution=TimeResolution.DAILY,
    period_type=PeriodType.HISTORICAL,
    ...
)
```
To retrieve meta data of a product: 
```
import python_dwd
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.enumerations.parameter_enumeration import Parameter

metadata = python_dwd.metadata_for_dwd_data(parameter=Parameter.PRECIPITATION_MORE,
                                            time_resolution=TimeResolution.DAILY,
                                            period_type=PeriodType.HISTORICAL)

```


## 4. Availability table 

It is also possible to use enumeration keywords. The availability table shows the enumeration keyword mapping the availability via python_dwd and on the CDC server.

|Paramater/Granularity                       |1_minute                             |   10_minutes                    |hourly | daily     |monthly | annual| 
|----------------|-------------------------------|-----------------------------|-----------------------------|-----------------------------|-----------------------------|-----------------------------|
| `TEMPERATURE_SOIL = "soil_temperature"`  | :x: | :x: | :heavy_check_mark:|:heavy_check_mark: |:x: | :x:|
| `TEMPERATURE_AIR = "air_temperature"` |:x: | :heavy_check_mark:| :heavy_check_mark:| :x:|:x: |:x: |
| `TEMPERATURE_AIR = "air_temperature"`  |:x: | :x: |:x: |:x: | :x:|:x: |
| `PRECIPITATION = "precipitation"`    | :heavy_check_mark: | :heavy_check_mark: |:x: | :x:| :x:|:x: |
| `TEMPERATURE_EXTREME = "extreme_temperature"` | :x:|:heavy_check_mark: | :x:|:x: | :x:|:x: |
| `WIND_EXTREME = "extreme_wind"  `  |:x: | :heavy_check_mark: | :x:| :x:|:x: |:x: |
| `SOLAR = "solar"`  | :x: | :heavy_check_mark: | :heavy_check_mark:| :heavy_check_mark:| :x:|:x: |
| `WIND = "wind"  ` |:x: |:heavy_check_mark: | :heavy_check_mark:|:x: |:x: |:x: |
| `CLOUD_TYPE = "cloud_type"`  |:x: | :x: | :heavy_check_mark:|:x: |:x: |:x: |
| `CLOUDINESS = "cloudiness"  `    | :x: | :x: |:heavy_check_mark: | :x:| :x:| :x:|
| `SUNSHINE_DURATION = "sun"` |:x: |:x: | :heavy_check_mark:| :x:|:x:|:x: |
| `VISBILITY = "visibility"`  | :x:|  :x:|:heavy_check_mark: |:x: | :x:| :x:|
| `WATER_EQUIVALENT = "water_equiv"`  | :x:| :x: |:x: |:heavy_check_mark: |:x: | :x:|
| `PRECIPITATION_MORE = "more_precip"  `    | :x: | :x: |:x: | :heavy_check_mark:|:heavy_check_mark: | :heavy_check_mark:|
| `PRESSURE = "pressure"` | :x:|:x: | :heavy_check_mark:|:x: |:x:|:x: |
| `CLIMATE_SUMMARY = "kl"`  |:x: | :x: |:x: | :heavy_check_mark:|:heavy_check_mark: |:heavy_check_mark: |


## 5. Listing server files

The server is constantly updated to add new values. This happens in a way that existing station data is appended by newly measured data approxamitly once a year somewhere after new year. This occasion requires the toolset to retrieve a new **filelist**, which has to beinitiated by the user when getting an error about this. For this purpose a function is scanning the server folder for a given parameter set if requested.

The created filelist is also used for the metadata, namely the column **HAS_FILE**. This is due to the fact that not every station listed in the given metadata also has a corresponding file. With this information one can simply filter the metadata with **HAS_FILE == True** to only get those stations that really have a file on the server.

## 6. About the metadata

The metadata for a set of parameters is not stored in a usual .csv but instead put in a .txt file next to the stationdata. This file has to be parsed first, as unfortunately there's no regular seperator in those files. After parsing the text from those files, a .csv is created which then can be read easily. There's one exception for this case: For 1-minute precipitation data, the metadata is stored in seperate zipfiles, which contain more detailed information. For this reason, when calling metadata_dwd with those parameters will download and read-in all the files and store them in a similar DataFrame to provide a seemless functionality over all parameter types. 

Also this data doesn't include the **STATE** information, which sometimes can be useful to filter the data for a certain region. To get this data into our metadata, we run another metadata request for the parameters of historical daily precipitation data, as we expect it to have the most information, because it is the most common station type in Germany. For some cases it still could happen that there's no STATE information as it might be that some stations are only run to individually measure the performance of some values at a special site.

## 7. Conclusion

Feel free to use the library if you want to automate the data access and analyze the german climate. Be aware that it could happen that the server is blocking the ftp client once in a while. It could be useful though to use a try-except-block and retry to get the data. For further examples of this library check the notebook **python_dwd_example.ipynb** in the **example** folder!

____

## Docker support

To use python_dwd in a Docker container, you just have to build the image from this project

```
docker build -t "python_dwd" .
```

To run the tests in the given environment, just call 

```
docker run -ti -v $(pwd):/app python_dwd:latest pytest tests/
```
from the main directory. To work in an iPython shell you just have to change the command `pytest tests/` to `ipython`.

#### Command line script  
You can download data as csv files after building docker container. Actually only the `collect_dwd_data` is supported from this service. 

```
docker run -ti -v $(pwd):/app python_dwd:latest python3 python_dwd/run.py collect_dwd_data "[1048]" "kl" "daily" "historical" /app/dwd_data/ False False True False True True
```
 
