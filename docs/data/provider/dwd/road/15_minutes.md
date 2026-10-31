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
| description   | Road weather data of the road weather stations on German roads (Glättemeldeanlagen of the road authorities of the Länder), reported in the standard period of 15 minutes                         |
| access        | [here](https://opendata.dwd.de/weather/weather_reports/road_weather_stations/) |

#### parameters

| name                                  | original name                            | description                      | unit | constraints |
|---------------------------------------|------------------------------------------|----------------------------------|------|-------------|
| {term}`humidity_relative` | relativeHumidity | relative humidity (BUFR 0 13 003, no time period or statistic attached) | % | >=0,<=100 |
| {term}`precipitation_type_flags` | precipitationType | type of precipitation, the bit flags of BUFR 0 20 021 (rain is bit 5 of 30, 33554432) | - | - |
| {term}`precipitation_amount` | totalPrecipitationOrTotalWaterEquivalent | precipitation height over the period the station states (15 minutes in most station groups, 10 at KO, RP and SD, none stated in some) | mm | >=0 |
| {term}`precipitation_intensity` | intensityOfPrecipitation | precipitation intensity | mm/s | >=0 |
| {term}`road_surface_condition` | roadSurfaceCondition | road surface condition, a code: 0 dry, 1 moist, 2 wet, 3 rime, 4 snow, 5 ice, 6 glaze, 7 not dry (BUFR code table 0 20 241, the same codes as 0 20 138); not the codes of DWD's SWSMOS forecast (1 dry, 2 moist, 3 snow, ...), which is `road_surface_condition_forecast` | - | - |
| {term}`temperature_air` | airTemperature | air temperature (BUFR 0 12 101, no time period or statistic attached); the sensor stands 4 to 5 m above ground (BUFR 0 07 032 reads 4.0, 4.05 or 5.0 m by station group, none in four of them) | K | - |
| {term}`temperature_dew_point` | dewpointTemperature | dew point temperature (BUFR 0 12 103, no time period or statistic attached); the sensor stands 4 to 5 m above ground (BUFR 0 07 032 reads 4.0, 4.05 or 5.0 m by station group, none in four of them) | K | - |
| {term}`temperature_surface` | roadSurfaceTemperature | road surface temperature (BUFR 0 12 241, no time period or statistic attached) | K | - |
| {term}`visibility` | horizontalVisibility | visibility range | m | >=0 |
| {term}`water_film_thickness` | waterFilmThickness | thickness of water film | m | >=0 |
| {term}`wind_direction` | windDirection | mean direction of wind over the period the station states (10 or 15 minutes, none stated in some station groups) | ° | >=0,<=360 |
| {term}`wind_direction_gust_max` | maximumWindGustDirection | direction of maximum wind gust | ° | >=0,<=360 |
| {term}`wind_gust_max` | maximumWindGustSpeed | maximum wind gust over the period the station states (10 or 15 minutes, none stated in some station groups) | m/s | >=0 |
| {term}`wind_speed` | windSpeed | mean wind speed over the period the station states (10 or 15 minutes, none stated in some station groups) | m/s | >=0 |

:::{note}
`wind_speed`, `wind_direction` and `wind_gust_max` carry no averaging window in their names because the
files do not agree on one. The BUFR template puts a time significance and a period before the wind,
and the `LATEST` file of each station group read on 2026-10-15 says a mean over the last 10 minutes in
FN, ER, HL, HV, JO, KA, KO, MC, NI, RH, RP and SD, over the last 15 minutes in HJ, KK and SH (KK and
SH write none in some subsets) and a time-averaged value over a period of 0 in DD, JA, KM, LH, ND, RB,
SP and WW. The dataset merges the groups under one name, so a `_last_10min` name would be wrong for
the others ([GH-2838](https://github.com/earthobservations/wetterdienst/issues/2838)). The period is
not read from the message.
:::

:::{note}
The `unit` column above is the unit this network **publishes** in, not the one a request returns,
the parser labelling the BUFR units of what it decodes and converting nothing itself. Six rows
differ from what comes back under the default targets: {term}`humidity_relative` is published `%` and
returned as a decimal, so 87 % reads 0.87; the three temperatures read `K` and come back in °C;
{term}`precipitation_intensity` is per second and comes back per hour; and
{term}`water_film_thickness` is metres and comes back centimetres. The `unit_targets` option
(`WD_TS_UNIT_TARGETS`) decides that other side, not this column.

Where the model spells a unit differently from BUFR the column carries the model's spelling of the
same quantity -- `mm` for a `kg m-2`, `°` for a `deg` -- and the two coded rows,
{term}`precipitation_type_flags` and {term}`road_surface_condition`, read `-` because a flag table
and a code table have no unit to give.

Two are published in units a reader might not expect, one per second and one in metres.
`intensityOfPrecipitation` is BUFR `0 13 055`, `kg m-2 s-1` -- a mass flux per area, which for water
is millimetres per second. The water film is metres, under either of the two descriptors these files
use for it: the road layout names it with DWD's own local `0 13 241` and the WMO template `3 07 102`
the rest arrive under reaches it as `0 13 116`. With the default unit targets a request serves the
first as mm/h and the second as cm, so a reading that arrives as `0.0056` comes back as `20.16` mm/h
and one that arrives as `0.002` as `0.2` cm.

Until [GH-1984](https://github.com/earthobservations/wetterdienst/issues/1984) both were declared in
a unit smaller than the one the files publish in -- `mm/h` for a rate in mm/s, `cm` for a length in
metres -- which is why the numbers came back too small: claiming a smaller unit claims a smaller
quantity. And because each of those was also its type's default target, nothing converted, so the
error was the whole factor, 3600 and 100.
:::

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

#### quality_flags

Each reading carries the station's own verdict on the sensor that took it, in the `quality_flags` column
(`"1"`, `"0"` or null), read from the `qualityInformationAwsData` flag (BUFR `0 33 005`) that ends every road subset:

| quality_flags | meaning                                                             |
|---------------|---------------------------------------------------------------------|
| `1`     | the station checked this quantity and reports it as **suspect**      |
| `0`     | the station checked this quantity and did not                        |
| `null`  | nothing is known -- the station ran no automated checks, said nothing, or sent only the flag table's own missing marker |

These codes are this network's own. `quality_flags` holds each provider's flags in its own way, and
the codes differ by provider -- DWD observation puts its `qn` codes there, where a *larger* number
means a more thorough check, so a code from one network says nothing about a code from another.

`null` is the common case, not the exception: in a network-wide sample of 1199 station-minutes, 817
reported "no automated meteorological data checks performed" and 40 carried no flag at all. It says
the station did not look, which is why it is not reported as `0`.

{term}`road_surface_condition` and {term}`water_film_thickness` always carry a `null` quality flag,
whatever they report as a value. The flag table is the WMO's generic one for an automatic weather
station and it names neither quantity -- the road layout carries them as DWD's own `0 20 241` and
`0 13 241`, and where the film instead arrives as WMO `0 13 116` the table still has no bit for it.
Its nearest offers are "state of ground", about bare earth, and "water content", the moisture in it.
The road surface temperature is mapped to "ground temperature data suspect" because the data
confirms that reading of it, not because the wording is close -- and nothing confirms the other two,
so they get a null rather than a guess. A wrong `0` would be worse, telling a caller filtering on
quality that a suspect reading had been checked and found sound.

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

**The road sensors are raw data.** Wetterdienst removes only what no sensor can have produced, and
two narrow combinations (below), and reports the rest as DWD publishes it, leaving a reading's
plausibility to the caller -- a road surface really does reach 60 °C in July sun, so a threshold
that took *out* the nonsense above would take genuine extremes with it. Do not read a value of this
network as checked because it came back: a sensor that moves but is wrong, such as a hygrometer
that reads 10 % for hours in fog, is returned. A value outside the physical range of its quantity,
the `-75.00` of the exact round values among them, is **null**, with the number DWD wrote as
`raw:198.15` in `quality_flags`, as DMI and RMI null theirs (see
[special values](../../../special_values.md)). The stuck sensors it **marks**, in the
`quality_flags` column, which is a different thing: the reading stays exactly as published, and a
caller who wants the extremes keeps them. Two rules (the section "readings inside every range that
are no reading" below) null a value as well, and keep the number the same way.

Which of the first bullet's readings are marked depends on the sensor rather than the value: its
cold outliers are marked where the sensor that took them has stopped, and its warm ones are not
marked at all, 79.8 °C on a road in September being implausible rather than impossible.

##### sensors that have stopped

The first of the two is a sensor that has stopped. Where an air temperature, a dew point or a road
surface temperature reports the identical value for 24 readings -- six hours at this resolution --
`quality_flags` becomes `1`. The reading is left exactly as published.

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
  filtering on `quality_flags` should ask for the window it means. The values nulled in the next
  section are the exception, as a range reads a value rather than a run and so needs no window at all.
- a sensor that moves but is wrong. RH/L702 ran 76.5 to 79.8 °C across a day and HV/E237 46.9 to
  57.2 °C, both varying hour to hour exactly as a working sensor does.
- **the difference from air temperature cannot separate the two by day.** Over a full day of five
  groups, stations with no sign of a fault reached 42.0 K above their own air temperature, while
  E237 -- which is certainly broken -- sat between 31.8 and 38.9 K. The broken station is inside the
  healthy range. There is no threshold that catches one without condemning the other, which is why
  this library does not try by day. By night it does, for a surface far above the air (the section
  "readings inside every range that are no reading" below).

##### values no reading can hold

A value outside the physical range of its quantity is null whatever window was asked for, with the
number DWD wrote as the last token of `quality_flags`, `raw:198.15` (GH-3222). Up to 0.163.0 it was
returned as published and marked `1`. The ranges are those every provider is held to (a humidity to
130 %, a wind speed to 115 m/s, a visibility to 200 km, a direction to 360 degrees, a water film to
1 m, the rain of 15 minutes to 300 mm), in DWD's own units; the surface condition and the
precipitation type are codes, held to none. The temperatures are narrower at the cold end: below
**-60 °C** a temperature is null. It is the `-75.00` of the exact round values above, and only that
one.

Germany's record low air temperature is -45.9 °C, at a sinkhole that traps cold, and a road surface
tracks the air rather than running far beneath it; the line stands 14 K under that record and 29 K
above the world's, so nothing this network can publish as weather falls below it. The stopped
sensors of KM do, at `-75.00` °C to the hundredth, for days.

This is what a value-based check is good for and the run rule is not. Measured over one hour of the
whole network -- 809 stations, 11 505 temperature readings -- the run rule marks nothing at all for
the two stations sitting at -75 °C, having only five readings where it needs twenty-four; the line
nulls all ten of their readings. Over twelve hours the run rule marks both stations too. The same
hour leaves `-30.00` and `-25.00` alone, as it should: those are readings until something other
than their value says otherwise.

No line is drawn at the warm end. A road surface in July sun passes 60 °C, and the 79.8 °C above is
implausible rather than impossible -- there is no temperature at that end which an honest reading
cannot reach.

##### readings inside every range that are no reading

Two rules null a value that is inside every range (GH-3624): the first reads the value alone, the
second the value beside the air temperature of its minute. The reading is null in `value` and the
number DWD wrote is the last token of `quality_flags`, `raw:0.1` or `raw:338.75` (the unit of the
source: %, K), as for a value outside a range. Nothing else of the sensors is judged, and there is
no comparison with neighbouring stations.

- **a relative humidity below 1 %** is no reading. A hygrometer that has failed writes it for hours
  while the value varies: P925 gave 0.1 % for 43 readings of a 12 hour window. The run rule does not
  look at a humidity at all, only at the air, the dew point and the road surface temperature. In the
  39 hours of every station group read on 2026-10-31 no humidity was below 5 %, so the rule nulled
  none there. From 1 % up the value is returned as the sensor wrote it, a dry one included.
- **a road surface temperature more than 20 K above the air temperature of the same minute, with the
  sun more than 6 degrees below the horizon** (the end of civil twilight, from the station's
  position and the time) is no reading. By night a road radiates to the air above it and keeps a few
  kelvin of the day's heat at most. In the same 39 hours, 99 % of the 62,895 night readings of 722
  stations lay within 8.6 K above the air, and seven stations sat 26 to 81 K above it for most or
  all of their night (P925, P034, V064, E237, B545, F053 and M080: a surface of 8 to 90 °C beside an
  air of -29 to 10 °C), 472 readings in all. The highest of the other stations was 19.2 K (M531), so
  the 20 K line lies in the one gap the sample has, between a road that runs warm and a sensor that
  reads something else. By day the sun heats a road legitimately, so the rule stands aside, as it
  does for a surface without an air temperature beside it, with one that is itself outside its range
  or that DWD's own flag marks suspect, and for a station without a position.

Both numbers are read from that one sample, in late October, and a hot summer night may keep the
road warmer than it did there: the line is set at more than twice what 99 % of the readings reached,
to leave that room. What the rules do not do:

- they do not say which sensor is wrong. At M080 it is the *air* temperature that reads -16 to -29
  °C beside a good surface of 8 to 13 °C, and it is the good surface that is nulled, the air being
  left as published (it is inside its range). Only an air that DWD's own flag marks suspect is not
  held against the surface, so an air sensor that has stopped at a plausible value (-25.00 °C) can
  still null a good surface; the run rule's verdict is not used, as it depends on the window the
  request asked for and the null would too;
- they do not catch a surface that is wrong by less than 20 K (E769 sat 6.6 to 8.5 K and M531 14 to
  19 K above the air for most of their night, which can be a heated road or a sensor that reads
  high), nor one that is wrong by day, nor a humidity above 1 % that is wrong (P925 read 10 % in
  that sample);
- a dew point beside a humidity below 1 % is returned, although it comes from the same probe;
- the rule on the surface reads the air whether the air is asked for or not.

##### what a quality flag of `1` means

So a quality flag of `1` means suspect, whether DWD said so or the run rule did. They do not
have the same standing -- DWD's bit 7 is verified against the data, with no station within 5 K of its own air
temperature carrying it, where the run length is a threshold fitted to one day -- and the column
does not distinguish them. The log does, for a caller who turns it up: the run rule writes a line at
`DEBUG` naming the first five stations it marked -- which neither the CLI nor the REST API prints by
default. A value nulled for its range or by one of the two rules above carries a `raw:` token
after the flag, `1,raw:198.15` where the sensor has stopped as well. A `null` flag still means
nobody has looked.
