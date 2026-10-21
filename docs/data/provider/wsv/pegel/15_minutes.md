# 15_minutes

## metadata

| property      | value                                                        |
|---------------|--------------------------------------------------------------|
| name          | 15_minutes                                                   |
| original name | 15_minutes                                                   |
| url           | [here](https://pegelonline.wsv.de/webservice/ueberblick) |

## datasets

### data

#### metadata

| property      | value                                                                                                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name          | data                                                         |
| original name | data                                                         |
| description   | Recent data (last 31 days) of German waterways including water level and discharge for most stations but may also include chemical, meteorologic and other types of values ([details](https://pegelonline.wsv.de/webservice/ueberblick)) |
| access        | [here](https://pegelonline.wsv.de/webservices/rest-api/v2/stations.json?includeTimeseries=true)                                                                                                                                          |

#### parameters

| name                            | original name           | description                                            | unit  | constraints |
|---------------------------------|-------------------------|--------------------------------------------------------|-------|-------------|
| {term}`stage` | W | Water level (WASSERSTAND ROHDATEN, or WASSERSTAND at two gauges), published in cm or, at some gauges, in m+NN or m+PNP, and returned in cm. The m+PNP series and the cm series that carry a gauge zero (gaugeZero, the Pegelnullpunkt) are relative to it, and each gauge zero is that gauge's own. The m+NN series are relative to NN. 28 cm series (stations list of 2026-10-21) publish no gauge zero and the source states no reference for them, so values of different stations do not in general share a reference: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series. | cm | >=0 |
| {term}`discharge` | Q | Discharge (ABFLUSS_ROHDATEN, or ABFLUSS at some stations), in m³/s: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | m³/s | >=0 |
| {term}`temperature_water` | WT | Water temperature (WASSERTEMPERATUR ROHDATEN, or WASSERTEMPERATUR at some stations), in °C: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | °C | - |
| {term}`electric_conductivity` | LF | Electric conductivity (ELEKTRISCHE_LEITFÄHIGKEIT_ROHDATEN), published in µS/cm or mS/cm and returned in µS/cm: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | μS/cm | - |
| {term}`clearance_height` | DFH | Clearance height (DURCHFAHRTSHÖHE), in cm: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | cm | - |
| {term}`temperature_air_2m` | LT | Air temperature (LUFTTEMPERATUR ROHDATEN, or LUFTTEMPERATUR at some stations), in °C; the source states no height: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | °C | - |
| {term}`flow_speed` | VA | Flow speed (FLIESSGESCHWINDIGKEIT_ROHDATEN), published in m/s or cm/s and returned in m/s: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | m/s | - |
| {term}`groundwater_level` | GRU | Groundwater level (GRUNDWASSER ROHDATEN), in m above NHN (the series' unit m+NHN): unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | m | - |
| {term}`wind_speed` | WG | Wind speed (WINDGESCHWINDIGKEIT), in m/s; the source states no height: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | m/s | - |
| {term}`humidity_relative` | HL | Relative humidity of the air (LUFTFEUCHTE), in %: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | % | >=0,<=100 |
| {term}`oxygen_level` | O2 | Oxygen level (SAUERSTOFFGEHALT, or SAUERSTOFFGEHALT ROHDATEN at some stations), in mg/l: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | mg/l | >=0 |
| {term}`turbidity` | TR | Turbidity (TRÜBUNG, or TRÜBUNG_ROHDATEN at one station), published in FNU, TE/F or NTU, the formazin scale, and returned unscaled as NTU: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | NTU | - |
| {term}`flow_direction` | R | Direction of the water current (RICHTUNGSTROM). The series' unit is MGN, which the documentation does not explain; the value is returned as published, taken as degrees, and may be from magnetic rather than true north: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.                        | ° | >=0,<=360 |
| {term}`wind_direction` | WR | Wind direction (WINDRICHTUNG), in degrees; the source states no height: unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | ° | >=0,<=360 |
| {term}`precipitation_amount` | NIEDERSCHLAG | Precipitation height. No station on the source's stations list of 2026-10-21 has a series of this shortname.                                      | mm | >=0 |
| {term}`precipitation_intensity` | NIEDERSCHLAGSINTENSITÄT | Precipitation intensity. No station on the source's stations list of 2026-10-21 has a series of this shortname.                                      | mm/h | >=0 |
| {term}`wave_period` | TP | Wave period (WELLENPERIODE), published in 1/100 s and returned in s (the reader also accepts s): unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series. | s | >=0 |
| {term}`wave_height_significant` | SIGH | Significant wave height (SIGNIFIKANTEWELLENHÖHE), in cm (the reader also accepts m): unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.          | cm | - |
| {term}`wave_height_max` | MAXH | Maximum wave height (MAXIMALEWELLENHÖHE), in cm (the reader also accepts m): unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.          | cm | - |
| {term}`ph_value` | PH | pH (PH-WERT), a number without unit (the series' unit is --): unchecked raw data (the source's ungeprüfte Rohdaten), one value per recording interval of the series.    | - | - |
| {term}`chloride_concentration` | CL | Chloride concentration. No station on the source's stations list of 2026-10-21 has a series of this shortname.                                      | mg/l | - |
