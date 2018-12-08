# pydwd
Python Functions for Accessing Weatherdata from German Weatherservice (DWD)

## Introduction
pydwd was created as an alternative to [rdwd](https://github.com/brry/rdwd), an R package that I had used recently for downloading station data from German Weather Service (Deutscher Wetterdienst, short: DWD). It's my first Python project which is also meant for me to learn different ways to work with the language but might also be useful for you if you are interested in working with this data.

Germany has decided to make the data accessible to anyone on the internet. (Be careful with the license of the data) Therefor they are storing the data on an ftp server, what makes it an ease to access. However it's not always quite comforting looking at the subfolders et cetera to automatically generate file links and download and open them - especially when working manually with Excel or whatever.

The functions I created derive the data laying on the server, present the existing metadata (list of existing stations, list of existing station data files) to you and let you choose which data to download (by choosing a set of parameters and a station id).

## What kind of data can be downloaded?
