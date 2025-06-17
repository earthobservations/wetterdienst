---
file_format: mystnb
kernelspec:
  name: python3
---

# Units

## Overview

Wetterdienst offers conversion of units based on the parameter type and a number of predefined units. 

The default units per each unit type are shown below:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.model.unit import UnitConverter

unit_converter = UnitConverter()
unit_converter.targets
```

All available units per each unit type:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.model.unit import UnitConverter

unit_converter = UnitConverter()
unit_converter.units
```

To set a different unit, you can use the `ts_unit_targets` setting in the `Settings` class. The following example
shows how to convert the temperature to Fahrenheit:

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

settings = Settings(ts_unit_targets={"temperature": "degree_fahrenheit"})
request = DwdObservationRequest(
    parameters=[("daily", "kl", "temperature_air_mean_2m")],
    settings=settings
)
stations = request.filter_by_station_id(station_id="1048")
values = stations.values.all()
df = values.df
df
```