# hourly

## metadata

| property      | value  |
|---------------|--------|
| name          | hourly |
| original name | hourly |

## datasets

### data

#### metadata

| property      | value |
|---------------|-------|
| name          | data  |
| original name | data  |

#### parameters

| name                                                    | original name | description                                                                         | unit |
|---------------------------------------------------------|---------------|-------------------------------------------------------------------------------------|------|
| {term}`temperature_air_2m`                              | TL            | Air temperature (DWD: "Lufttemperatur", from DWD's MOS, model output statistics); DWD's sheet states no height. | °C   |
| {term}`temperature_dew_point_2m`                        | TD            | Dew point temperature (DWD: "Taupunkttemperatur", from DWD's MOS, model output statistics); DWD's sheet states no height. | °C   |
| {term}`temperature_surface`                             | TS            | Temperature of the road surface (DWD: "Temperatur der Fahrbahnoberfläche"), from the METRo road weather model driven by DWD's MOS values. | °C   |
| {term}`precipitation_amount_liquid`                     | RRL1c         | Liquid precipitation of the last hour, in mm (DWD: "Niederschlag flüssig der letzten Stunde", from DWD's MOS). | mm   |
| {term}`precipitation_amount_liquid_last_6h`             | RR6           | Liquid precipitation of the last 6 hours, accumulated, in mm (DWD: "Niederschlag flüssig der letzten 6 Stunden akkumuliert"; from DWD's MOS). | mm   |
| {term}`probability_precipitation_liquid_last_6h`        | WWL6          | Probability of liquid precipitation in the last 6 hours, in % (DWD: "Niederschlag flüssig der letzten 6 Stunden Wahrscheinlichkeit"; from DWD's MOS). | %    |
| {term}`probability_precipitation_amount_gt_5mm_last_6h` | R650          | Probability of more than 5 mm of liquid and solid precipitation in the last 6 hours (DWD: "Niederschlag flüssig+fest mehr als 5mm der letzten 6 Stunden Wahrscheinlichkeit"; from DWD's MOS). | %    |
| {term}`road_surface_condition`                          | RC            | Condition of the road surface, as a code: 1 dry, 2 moist, 3 snow, 4 hoar frost, 5 freezing wetness, 6 glaze ice (DWD: "Straßenzustand", from the METRo road weather model driven by DWD's MOS values). | -    |
