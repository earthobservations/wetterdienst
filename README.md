# python_dwd

Python Toolset For Accessing Weather Data From German Weather Service

## 1. Introduction

python_dwd was created as an alternative to [rdwd](https://github.com/brry/rdwd), an R package that I had used recently for downloading station data from German Weather Service (Deutscher Wetterdienst or DWD). It's my first Python project which is also meant for me to learn different ways to work with the language but might also be useful for you if you are interested in working with this data.

Germany has decided to make the data accessible to anyone on the internet. (Be careful with the license of the data) Therefor they are storing the data on an ftp server, what makes it an ease to access. However it's not always quite comforting looking at the subfolders et cetera to automatically generate file links and download and open them - especially when working manually with Excel or whatever.

The functions I created derive the data laying on the server, present the existing metadata (list of existing stations, list of existing station data files) to you and let you choose which data to download (by choosing a set of parameters and a station id).

## 2. What kind of data can be downloaded?

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

## 3. How does the toolset work?

The toolset consists of four functions which are:

- metadata_dwd
- select_dwd
- download_dwd
- read_dwd

All those functions have one same argument which is **folder**. It can be used to define in which folder relative to the working path all the files shall be stored. Otherwise a standard folder ('dwd_data') is used. The argument is entered as a **string**.

**metadata_dwd** is used to discover what data for a set of parameters (**var**, **res**, **per**) is available, specificly which stations can be found for the requested variable, resolution and period. Also it can be defined by **write_file**, if the resulting **DataFrame** should be written as **csv** to the given folder. **write_file** is a boolean value. Furthermore with **create_new_filelist**, by default set to **False**, the function can be forced to retrieve a new list of files from the ftp server, which is usually avoided if there's already a file existing in the explicit folder.

**select_dwd** is used with the help of the **information of the metadata** to retrieve filelinks to files that represent a **set of parameters** in combination with the requested **statid**. Here also **create_new_filelist** can be set to **True**, if the user is sure that the **file to a certain statid** is available but somehow the old **filelist** doesn't contain a corresponding information.

**download_dwd** ...

**read_dwd** ...