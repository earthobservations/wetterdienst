# Mosmix

## Overview

[Mosmix](https://www.dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html) is a forecast product of 
the DWD that is based on global weather models and that uses statistical downscaling for land-based climate stations 
based on their historical observations to provide more precise, local forecast. Mosmix is available for over 5000
stations worldwide and is available in two versions, Mosmix-S and Mosmix-L. Mosmix-S comes with a set of 40 parameters 
and is published every hour while MOSMIX-L has a set of about 115 parameters and is released every 6 hours 
(3am, 9am, 3pm, 9pm). Both versions have a forecast limit of 240h. In addition, the `snow` dataset provides
[MOSMIX-SNOW](https://www.dwd.de/EN/ourservices/met_application_mosmix_snow/met_application_mosmix_snow.html), a set of
20 new/fresh snow forecast parameters for mountain stations that is published hourly from November to April (subject to
snow conditions) with a lead-time of 48h.

```{toctree}
:hidden:

hourly.md
```