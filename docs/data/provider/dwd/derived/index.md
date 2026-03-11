# Derived

## Overview

The DWD provides several [data products](https://opendata.dwd.de/climate_environment/CDC/derived_germany/) that are derived from weather data.

The following resolutions are supported for the derived data/parameters on the file server
- **hourly** - measured once per hour
- **daily** - measured/summarized once per day
- **monthly** - measured/summarized once a month

Depending on the parameter selected following periods are supported:
- **historical** - values based on data which have completed quality control
- **recent** - newer values based on data which have not passed the full quality control yet

The derived products currently supported are:

**Technical Products:**
- [heating degreedays](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/heating_degreedays/hdd_3807/) for weather stations
- [cooling degreehours](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/cooling_degreehours/) for weather stations
- [climate correction factor](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly/climate_correction_factor/) for postal codes

**Climate Products:**
- [radiation global and sunshine duration](https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/) (hourly)
- [soil data](https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/) (daily and monthly)

**Not yet implemented Products:**
- [heating degreedays daily](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/daily/heating_degreedays/hdd_3807/)
- [bad weather days](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/daily/bad_weather_days/)
- [heating degreedays daily](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/daily/heating_degreedays/hdd_3807/)
- [windroses](https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/multi_annual/windroses/)
- [soil multiannual](https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/multi_annual/)
- [fire danger index](https://opendata.dwd.de/climate_environment/CDC/derived_germany/fire_danger_index/)


```{toctree}
:hidden:

hourly.md
daily.md
monthly.md
```