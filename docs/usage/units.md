# Units

## Overview

Wetterdienst offers conversion of units based on the parameter type and a number of predefined units. 

The default units per each unit type are shown below:

```python exec="on" source="above"
from wetterdienst.core.timeseries.unit import UnitConverter

unit_converter = UnitConverter()
print(unit_converter.targets)
```

All available units per each unit type:
    
```python exec="on" source="above"
from wetterdienst.core.timeseries.unit import UnitConverter

unit_converter = UnitConverter()
print(unit_converter.units)
```

To set a different unit, you can use the `ts_unit_targets` setting in the `Settings` class. The following example
shows how to convert the temperature to Fahrenheit:

```python exec="on" source="above"
from wetterdienst import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

settings = Settings(ts_unit_targets={"temperature": "degree_fahrenheit"})
request = DwdObservationRequest(
    parameters=[("daily", "kl", "temperature_air_mean_2m")],
    settings=settings
).filter_by_station_id(station_id="1048")
df = request.values.all().df
print(df)
```
