# 15_minutes

## metadata

| property      | value                                                                          |
|---------------|--------------------------------------------------------------------------------|
| name          | 15_minutes                                                                     |
| original_name | 15_minutes                                                                     |
| url           | [here](https://opendata.dwd.de/weather/weather_reports/road_weather_stations/) |

## datasets

### data

#### metadata

| property      | value                                                                          |
|---------------|--------------------------------------------------------------------------------|
| name          | data                                                                           |
| original_name | data                                                                           |
| description   | 15-minute road weather data of German highway stations                         |
| access        | [here](https://opendata.dwd.de/weather/weather_reports/road_weather_stations/) |

#### parameters

| name                                  | original name                            | description                      | unit | constraints |
|---------------------------------------|------------------------------------------|----------------------------------|------|-------------|
| {term}`humidity`                      | relativeHumidity                         | mean humidity                    | %    | >=0,<=100   |
| {term}`precipitation_type_flags`      | precipitationType                        | types of precipitation, as flags | -    | -           |
| {term}`precipitation_height`          | totalPrecipitationOrTotalWaterEquivalent | precipitation height             | mm   | >=0         |
| {term}`precipitation_intensity`       | intensityOfPrecipitation                 | precipitation intensity          | mm/s | >=0         |
| {term}`road_surface_condition`        | roadSurfaceCondition                     | road surface condition           | -    | -           |
| {term}`temperature_air_mean_2m`       | airTemperature                           | mean air temperature in 2m       | K    | -           |
| {term}`temperature_dew_point_mean_2m` | dewpointTemperature                      | mean dew point temperature in 2m | K    | -           |
| {term}`temperature_surface_mean`      | roadSurfaceTemperature                   | road surface temperature         | K    | -           |
| {term}`visibility_range`              | horizontalVisibility                     | visibility range                 | m    | >=0         |
| {term}`water_film_thickness`          | waterFilmThickness                       | thickness of water film          | cm   | >=0         |
| {term}`wind_direction`                | windDirection                            | mean direction of wind           | °    | >=0,<=360   |
| {term}`wind_direction_gust_max`       | maximumWindGustDirection                 | direction of maximum wind gust   | °    | >=0,<=360   |
| {term}`wind_gust_max`                 | maximumWindGustSpeed                     | maximum wind gust                | m/s  | >=0         |
| {term}`wind_speed`                    | windSpeed                                | mean wind speed                  | m/s  | >=0         |

#### precipitation type

{term}`precipitation_type_flags` is **not** a code like {term}`precipitation_form` elsewhere in this
library. It is BUFR `0 20 021`, a 30-bit flag table with one bit per type of precipitation, so a
value of `33554432` means rain rather than "type 33554432".

BUFR numbers a flag table's bits from the most significant end, so for this 30-bit field **bit `n`
is worth `2 ** (30 - n)`**:

| value | bit | meaning |
|---|---|---|
| `0` | -- | nothing flagged |
| `536870912` | 1 | precipitation, type unknown |
| `268435456` | 2 | liquid, not freezing |
| `134217728` | 3 | liquid, freezing |
| `67108864` | 4 | drizzle |
| `33554432` | 5 | rain |
| `16777216` | 6 | solid precipitation |
| `8388608` | 7 | snow |

and onwards through snow grains, snow pellets, ice pellets, ice crystals, diamond dust, small hail,
hail, glaze, rime, soft rime, hard rime, clear ice and wet snow to bit 20, then hoar frost, dew and
white dew at bits 21 to 23. Bit 30 (`1`) is the table's own missing value. To test for one type,
mask: `value & (1 << (30 - 5))` is true where rain was reported.

Several bits can be set at once in principle. In practice DWD sets at most one: across 37362
readings from 206 files, the only values seen were nothing flagged, rain, drizzle and
precipitation-of-unknown-type, never a combination.

It is reported raw and under its own name rather than decoded into {term}`precipitation_form`,
because that would need a correspondence DWD has not published: the flag table's twenty types would
have to collapse onto `wrtr`'s liquid/solid/unknown, and the freezing and depositional types --
glaze, rime, clear ice -- have no home there at all. On a road weather network that is exactly the
distinction worth keeping.

#### quality

Each reading carries the station's own verdict on the sensor that took it, in the `quality` column,
read from the `qualityInformationAwsData` flag (BUFR `0 33 005`) that ends every road subset:

| quality | meaning                                                             |
|---------|---------------------------------------------------------------------|
| `1`     | the station checked this quantity and reports it as **suspect**      |
| `0`     | the station checked this quantity and did not                        |
| `null`  | nothing is known -- the station ran no automated checks, or said nothing |

`null` is the common case, not the exception: in a network-wide sample of 1199 station-minutes, 817
reported "no automated meteorological data checks performed" and 40 carried no flag at all. It says
the station did not look, which is why it is not reported as `0`.

{term}`road_surface_condition` and {term}`water_film_thickness` are always `null`. Both are road
descriptors of DWD's own, and the flag table is the WMO's generic one for an automatic weather
station, which names neither: its nearest offers are "state of ground", about bare earth, and "water
content", the moisture in it. The road surface temperature is mapped to "ground temperature data
suspect" because the data confirms that reading of it, not because the wording is close -- and
nothing confirms the other two, so they get a null rather than a guess. A wrong `0` would be worse,
telling a caller filtering on quality that a suspect reading had been checked and found sound.

##### unflagged bad readings

The flag is reliable where it is set and does not catch everything. In that same sample, of 887
stations reporting a road surface temperature, **21 (2.4%) were more than 10 K from their own air
temperature** and the flag named only 4 of them. The rest reported "no automated checks performed".

A caller reading this network at face value should expect, at roughly one station in forty:

- **impossible values**, such as a road surface at 79.8 °C or 49.2 °C at 23:00 local in September,
  and air temperatures of -30.0 °C, -25.4 °C and 41.7 °C in the same hour;
- **exact round values that look like device defaults**, `-75.00 °C`, `-30.00 °C` and `-25.00 °C`
  repeating across stations of one group, where healthy readings spread across the decimals;
- **stuck sensors**, holding one value for a whole day -- one station's second road sensor read
  `-0.0 °C` in all 96 readings of a day while its first ran a normal 17.4 to 33.5 °C.

Wetterdienst does not filter these. It reports what DWD publishes, and the plausibility of a reading
is left to the caller -- a road surface really does reach 60 °C in July sun, so a threshold that
removed the nonsense above would remove genuine extremes with it. Filter on `quality` where the
station offers a verdict, and sanity-check against {term}`temperature_air_mean_2m` where it does not.
