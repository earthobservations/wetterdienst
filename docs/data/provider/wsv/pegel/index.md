# Pegel

## Overview

The administration of German waterways (WSV) is providing data of certain stations at german rivers
for maximum last 30 days. Data is provided kindly over a 
[REST API](https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json). Measured parameters include
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

```{toctree}
:hidden:

1_minute.md
5_minutes.md
10_minutes.md
15_minutes.md
hourly.md
```