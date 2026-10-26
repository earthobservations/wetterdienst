# Mosmix

## Overview

[Mosmix](https://www.dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html) is a forecast product of 
the DWD that is based on global weather models and that uses statistical downscaling for land-based climate stations 
based on their historical observations to provide more precise, local forecast. Mosmix is available for more than 5000
stations worldwide and is available in two versions, Mosmix-S and Mosmix-L. Mosmix-S comes with a set of 40 parameters 
and is published every hour while MOSMIX-L has a set of 114 parameters and is released every 6 hours 
(3am, 9am, 3pm, 9pm). Both versions have a forecast limit of 240h.

## Update date

A forecast is dated by its model run: the `data_updated_at` of the [`metadata`](../../../../usage/restapi.md#response-metadata) of an answer is the run the forecast is of
(`the `IssueTime` the file states`), not the time DWD published the file, so it is the same however often the run is read, and `retrieved_at`
less `data_updated_at` is how old the forecast is.

```{toctree}
:hidden:

hourly.md
```