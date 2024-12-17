# Pegel

## Overview

The administration of German waterways (WSV) is providing data of certain stations at german rivers
for maximum last 30 days. Data is provided kindly over a 
[REST API](https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json). Measured parameters include
water level and discharge for most stations but may also include chemical, meteorologic and other types
of values. The values of WSV Pegelonline have no fixed frequency but may be one of 1 minute, 5 minutes,
15 minutes or 60 minutes. Besides continuously measured values there are also a number of
statistical values which are fragmentary provided per each station:

- m_i -> first flood marking
- m_ii -> second flood marking
- m_iii -> third flood marking
- mnw -> mean of low water level
- mw -> mean of water level
- mhw -> mean of high water level
- hhw -> highest water level
- hsw -> highest of shipping water level
