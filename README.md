# python_dwd

Python Toolset For Accessing Weather Data From German Weather Service

## 1. Introduction

python_dwd was created as an alternative to [rdwd](https://github.com/brry/rdwd), an R package that I had used recently for downloading station data from German Weather Service (Deutscher Wetterdienst or DWD). It's my first Python project which is also meant for me to learn different ways to work with the language but might also be useful for you if you are interested in working with this data.

Germany has decided to make the data accessible to anyone on the internet (be careful with the license of the data and check this first!). Therefor they are storing the data on a public server, what makes it an ease to access. However it's not always quite comforting looking at the subfolders et cetera to automatically generate file links and download and open them - especially when working manually with Excel or whatever.

The functions we created derive the data laying on the server, present the existing metadata (list of existing stations, list of existing station data files) to you and let you choose which data to download (by choosing a set of parameters and a station id).

## 2. Types of data

First there is a large set of variables available online. Those can be seen in the 'dwd_ftp_structure' textfile.

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

The toolset consists of four functions which are:

- metadata_for_dwd_data
- create_file_list_for_dwd_server
- download_dwd_data
- read_dwd_data

All those functions have one same argument which is **folder**. It can be used to define in which folder relative to the working path all the files shall be stored. Otherwise a standard folder ('dwd_data') is used. The argument is entered as a **string**.

**metadata_for_dwd_data** is used to discover what data for a set of parameters (**var**, **res**, **per**) is available, specificly which stations can be found for the requested variable, resolution and period. Also it can be defined by **write_file**, if the resulting **DataFrame** should be written as **csv** to the given folder. **write_file** is a boolean value. Furthermore with **create_new_filelist**, by default set to **False**, the function can be forced to retrieve a new list of files from the ftp server, which is usually avoided if there's already a file existing in the explicit folder.

**create_file_list_for_dwd_server** is used with the help of the **information of the metadata** to retrieve filelinks to files that represent a **set of parameters** in combination with the requested **statid**. Here also **create_new_filelist** can be set to **True**, if the user is sure that the **file to a certain statid** is available but somehow the old **filelist** doesn't contain a corresponding information.

**download_dwd_data** is used with the created filelinks of select_dwd to **download and store** the data in the given folder. Therefor it connects with the ftp and writes the corresponding file to the harddisk as defined. Furthermore it returns the local filelink or to be clear the link where the file is saved on the harddrive.

**read_dwd_data** is used to get the data into the Python environment in shape of a pandas DataFrame. Therefor it opens the downloaded zipfile, reads its content and selects the file with the data (something like "produkt..."). Then the selected file is read and returned in shape of a DataFrame, ready to be analyzed!

## 4. Listing server files

The server is constantly updated to add new values. This happens in a way that existing station data is appended by newly measured data approxamitly once a year somewhere after new year. This occasion requires the toolset to retrieve a new **filelist**, which has to beinitiated by the user when getting an error about this. For this purpose a function is scanning the server folder for a given parameter set if requested.

The created filelist is also used for the metadata, namely the column **HAS_FILE**. This is due to the fact that not every station listed in the given metadata also has a corresponding file. With this information one can simply filter the metadata with **HAS_FILE == True** to only get those stations that really have a file on the server.

## 5. About the metadata

The metadata for a set of parameters is not stored in a usual .csv but instead put in a .txt file next to the stationdata. This file has to be parsed first, as unfortunately there's no regular seperator in those files. After parsing the text from those files, a .csv is created which then can be read easily. There's one exception for this case: For 1-minute precipitation data, the metadata is stored in seperate zipfiles, which contain more detailed information. For this reason, when calling metadata_dwd with those parameters will download and read-in all the files and store them in a similar DataFrame to provide a seemless functionality over all parameter types. 

Also this data doesn't include the **STATE** information, which sometimes can be useful to filter the data for a certain region. To get this data into our metadata, we run another metadata request for the parameters of historical daily precipitation data, as we expect it to have the most information, because it is the most common station type in Germany. For some cases it still could happen that there's no STATE information as it might be that some stations are only run to individually measure the performance of some values at a special site.

## 6. Conclusion

Feel free to use the library if you want to automate the data access and analyze the german climate. Be aware that it could happen that the server is blocking the ftp client once in a while. It could be useful though to use a try-except-block and retry to get the data. For further examples of this library check the notebook **python_dwd_example.ipynb** in the **example** folder!
