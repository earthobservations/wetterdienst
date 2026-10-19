# 10_minutes

## metadata

| property      | value                                                        |
|---------------|--------------------------------------------------------------|
| name          | 10_minutes                                                   |
| original name | 10_minutes                                                   |
| url           | [here](https://www.pegelonline.wsv.de/webservice/ueberblick) |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                         |
| original name | data                                                         |
| description   | Recent data (last 31 days) of German waterways including water level and discharge for most stations but may also include chemical, meteorologic and other types of values ([details](https://www.pegelonline.wsv.de/webservice/ueberblick)) |
| access        | [here](https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json?includeTimeseries=true)                                                                                                                                          |

#### parameters

| name                            | original name           | description                                            | unit  | constraints |
|---------------------------------|-------------------------|--------------------------------------------------------|-------|-------------|
| {term}`stage` | W | Water level (WASSERSTAND ROHDATEN; WASSERSTAND at two gauges), a reading at the recording interval of the series. | cm | >=0 |
| {term}`discharge` | Q | Discharge (ABFLUSS; ABFLUSS_ROHDATEN for the raw series), a reading at the recording interval of the series. | m³/s | >=0 |
| {term}`temperature_water` | WT | Water temperature (WASSERTEMPERATUR; WASSERTEMPERATUR ROHDATEN for the raw series), a reading at the recording interval of the series. | °C | - |
| {term}`electric_conductivity` | LF | Electric conductivity (ELEKTRISCHE_LEITFÄHIGKEIT_ROHDATEN), a reading at the recording interval of the series. | μS/cm | - |
| {term}`clearance_height` | DFH | Clearance height (DURCHFAHRTSHÖHE), a reading at the recording interval of the series. | cm | - |
| {term}`temperature_air_2m` | LT | Air temperature (LUFTTEMPERATUR; LUFTTEMPERATUR ROHDATEN for the raw series), a reading at the recording interval of the series. | °C | - |
| {term}`flow_speed` | VA | Flow speed (FLIESSGESCHWINDIGKEIT_ROHDATEN), a reading at the recording interval of the series. | m/s | - |
| {term}`groundwater_level` | GRU | Groundwater level (GRUNDWASSER ROHDATEN), a reading at the recording interval of the series. | m | - |
| {term}`wind_speed` | WG | Wind speed (WINDGESCHWINDIGKEIT), a reading at the recording interval of the series. | m/s | - |
| {term}`humidity_relative` | HL | Relative humidity of the air (LUFTFEUCHTE), a reading at the recording interval of the series. | % | >=0,<=100 |
| {term}`oxygen_level` | O2 | Oxygen level (SAUERSTOFFGEHALT; SAUERSTOFFGEHALT ROHDATEN for the raw series), a reading at the recording interval of the series. | mg/l | >=0 |
| {term}`turbidity` | TR | Turbidity (TRÜBUNG; TRÜBUNG_ROHDATEN for the raw series), a reading at the recording interval of the series. | NTU | - |
| {term}`flow_direction` | R | Direction of the water current (RICHTUNGSTROM), a reading at the recording interval of the series. | ° | >=0,<=360 |
| {term}`wind_direction` | WR | Wind direction (WINDRICHTUNG), a reading at the recording interval of the series. | ° | >=0,<=360 |
| {term}`precipitation_amount` | NIEDERSCHLAG | Precipitation height, a reading at the recording interval of the series. | mm | >=0 |
| {term}`precipitation_intensity` | NIEDERSCHLAGSINTENSITÄT | Precipitation intensity, a reading at the recording interval of the series. | mm/h | >=0 |
| {term}`wave_period` | TP | Wave period (WELLENPERIODE), a reading at the recording interval of the series. | s | >=0 |
| {term}`wave_height_significant` | SIGH | Significant wave height (SIGNIFIKANTEWELLENHÖHE), a reading at the recording interval of the series. | cm | - |
| {term}`wave_height_max` | MAXH | Maximum wave height (MAXIMALEWELLENHÖHE), a reading at the recording interval of the series. | cm | - |
| {term}`ph_value` | PH | pH (PH-WERT), a reading at the recording interval of the series. | - | - |
| {term}`chloride_concentration` | CL | Chloride concentration, a reading at the recording interval of the series. | mg/l | - |
