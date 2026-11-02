# Pegel

## Overview

The administration of German waterways (WSV) is providing data of certain stations at german rivers
for maximum last 31 days. Data is provided kindly over a 
[REST API](https://pegelonline.wsv.de/webservices/rest-api/v2/stations.json). Measured parameters include
water level and discharge for most stations but may also include chemical, meteorologic and other types
of values. The recording interval is a property of the station rather than of the network, so the
resolutions below are not periods the network as a whole reports in: each station is listed under the
one it actually records at, which the API publishes as the `equidistance` of the timeseries. A station
that records different parameters at different intervals -- stage every 15 minutes, air temperature
every 60, say -- appears under both, and each parameter is only served under the resolution it belongs
to. Besides continuously measured values there are also a number of statistical values which are
fragmentary provided per each station:

- m_i -> first flood marking
- m_ii -> second flood marking
- m_iii -> third flood marking
- mnw -> mean of low water level
- mw -> mean of water level
- mhw -> mean of high water level
- hhw -> highest water level
- hsw -> highest of shipping water level

These are returned in metres, the unit `stage` comes back in by default, each converted from the unit
Pegelonline lists it in (`cm` for all of them at present; `m` is the unit of the limits of a gauge in metres above
sea level, which are no column); a level in a unit the reader does not know is null. `unit_targets` does not apply
to them, as they are no parameters: a stage asked for in centimetres
(`unit_targets={"length_medium": "centimeter"}`) is 100 times these.

Each station also lists the altitude of its stage gauge's zero, in metres, as `gauge_zero`, and the
vertical datum that altitude is given in, as Pegelonline publishes it, as `gauge_zero_datum`: mostly
`m. ü. NHN`, but `m. ü. NN` for some gauges, `m ü. A.` for the Austrian ones on the Danube and
`mü.M.` for Basel, so compare two gauge zeros only where their datums agree.

It also names the river the gauge is on, as Pegelonline publishes it (`ELBE`), as `river`, and the
gauge's position along it, in kilometres, as `river_kilometer`; the latter is null for the few gauges
that have none. It is the German waterway kilometre, which grows downstream; `imgw/hydrology` counts
its `river_kilometer` from the river's mouth instead.

```{toctree}
:hidden:

1_minute.md
5_minutes.md
10_minutes.md
15_minutes.md
hourly.md
```
