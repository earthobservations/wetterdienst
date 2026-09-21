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
| `null`  | nothing is known -- the station ran no automated checks, said nothing, or sent only the flag table's own missing marker |

These numbers are this network's own. `quality` carries whatever a source publishes, and the scale
differs by provider -- DWD observation puts its `qn` codes there, where a *larger* number means a
more thorough check, so a number from one network says nothing about a number from another.

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

Wetterdienst removes none of these. It reports what DWD publishes, and a reading's plausibility is
left to the caller -- a road surface really does reach 60 °C in July sun, so a threshold that took
*out* the nonsense above would take genuine extremes with it. Two of those shapes it does **mark**,
in the `quality` column, which is a different thing: the reading stays exactly as published, and a
caller who wants the extremes keeps them. The two are the stuck sensors, and the part of the exact
round values that no reading could hold -- the `-75.00`, but not the `-30.00` or the `-25.00`.

Which of the first bullet's readings are marked depends on the sensor rather than the value: its
cold outliers are marked where the sensor that took them has stopped, and its warm ones are not
marked at all, 79.8 °C on a road in September being implausible rather than impossible.

##### sensors that have stopped

The first of the two is a sensor that has stopped. Where an air temperature, a dew point or a road
surface temperature reports the identical value for 24 readings -- six hours at this resolution --
`quality` becomes `1`. The reading is left exactly as published.

A run ends where the readings stop for more than four times the station's own usual interval, so
two three-hour plateaus either side of a three-day outage are not a six-hour one. Against the
station's own cadence rather than a fixed number of minutes, because a fixed one cannot separate
them: 99.5% of this network's intervals are the quarter hour it publishes on, but the tail reaches
405 minutes, longer than the six hours this looks for. A hole ends the run and nothing more -- a
sensor stopped on both sides of one is still stopped on both sides of it.

A road surface held at or below freezing is exempt for the readings whose own minute had air within
10 °C of freezing **either side** -- an ordinary thaw runs to +6 or +10 °C with snow still lying, and the road under
it stays pinned for hours. Not only at 0.00 °C: German roads are salted, and brine depresses the
freezing point, so a treated road in the same thaw sits at a constant sub-zero value by the same
physics. The exemption reaches 10 °C below freezing, a little past where rock salt stops working,
and no further -- which is what keeps a sensor stopped at −30 °C from being excused with it.
Melting ice holds a road at 0.00 °C for as long as the ice lasts, which is the condition this
network exists to report, and it cannot be told from a sensor stopped at zero by the reading alone.
The air tells it: ice does not melt on a road whose station reports 26 °C, which is what FN/P717's
does while its surface reads 0.00 all day. Where the air is unknown the reading is left alone too --
a missed fault is the safer error than a winter's worth of genuine readings marked suspect.

That threshold is measured, not chosen. Over a day of five station groups and around 700 stations
per quantity, a working sensor's longest run of one identical value was 14 readings for the air
temperature, 17 for the dew point and 9 for the road surface; a broken one held its value for 86 to
96 of the day's 96, every one of them reporting a single distinct value for the whole day. It is
applied only to those three quantities, because only for those is standing still a fault: the road
surface condition and the water film sit at `0` for the whole of a dry day, as does the
precipitation type, the humidity saturates in fog, and the wind falls calm.

This is also what the exact round values are. `-75.00`, `-30.00` and `-25.00` are not a sentinel to
be recognised but sensors that have stopped, and matching them by value would be worse than useless
for two of the three -- -25 °C and -30 °C are both reachable in a German winter.

Two things the run rule does not catch, and one it cannot:

- a run shorter than the window. A request covering less than six hours has too few readings for the
  question to be asked at all -- and because the check sees only the files the window selected, the
  same reading can come back `null` from a two-hour request and `1` from a full day's. A caller
  filtering on `quality` should ask for the window it means. The one exception is the line drawn in
  the next section, which reads a value rather than a run and so needs no window at all.
- a sensor that moves but is wrong. RH/L702 ran 76.5 to 79.8 °C across a day and HV/E237 46.9 to
  57.2 °C, both varying hour to hour exactly as a working sensor does.
- **the difference from air temperature cannot separate the two.** Over a full day of five groups,
  stations with no sign of a fault reached 42.0 K above their own air temperature, while E237 --
  which is certainly broken -- sat between 31.8 and 38.9 K. The broken station is inside the healthy
  range. There is no threshold here that catches one without condemning the other, which is why this
  library does not try.

##### temperatures no reading can hold

The second is marked whatever window was asked for: a temperature below **-60 °C**. It is the
`-75.00` of the exact round values above, and only that one.

Germany's record low air temperature is -45.9 °C, at a sinkhole that traps cold, and a road surface
tracks the air rather than running far beneath it; the line stands 14 K under that record and 29 K
above the world's, so nothing this network can publish as weather falls below it. The stopped
sensors of KM do, at `-75.00` °C to the hundredth, for days.

This is what a value-based check is good for and the run rule is not. Measured over one hour of the
whole network -- 809 stations, 11 505 temperature readings -- the run rule marks nothing at all for
the two stations sitting at -75 °C, having only five readings where it needs twenty-four; the line
marks all ten of their readings. Over twelve hours the run rule marks both stations too. The same
hour leaves `-30.00` and `-25.00` alone, as it should: those are readings until something other
than their value says otherwise.

No line is drawn at the warm end. A road surface in July sun passes 60 °C, and the 79.8 °C above is
implausible rather than impossible -- there is no temperature at that end which an honest reading
cannot reach.

##### what `quality` of `1` means

So `quality` of `1` means suspect, whether DWD said so or either of these checks did. They do not
have the same standing -- DWD's bit 7 is verified against the data, with no station within 5 K of its own air
temperature carrying it, where the run length is a threshold fitted to one day -- and the column
does not distinguish them. Nor do the two of ours stand alike: a run length is a threshold fitted to one day
of one network, where -60 °C is a statement about what temperatures exist. The log distinguishes all
three, for a caller who turns it up: each check writes a line at `DEBUG` naming the first five
stations it marked -- which neither the CLI nor the REST API prints by default -- and a station
stopped at -75 °C is named by both of ours. A `null` still means nobody has looked.
